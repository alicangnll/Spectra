"""Binary diff tool: compare two versions of the same binary.

Classic 1-day patch hunting: given the binary before and after a vendor
patch, the functions whose bytes actually changed are usually exactly the
ones that were fixed. This module matches symbols by name across the two
files, ranks matched functions by byte similarity (:mod:`difflib`, so no
external dependency), and lists added/removed symbols. When both files are
stripped it falls back to an honest section-level comparison.

Everything is stdlib-only and built on the shared pure parser in
``spectra.tools.binary_format``. The engine (``diff_binaries`` and
``compare_sections``) is pure and directly testable, ``format_diff_report``
renders the markdown, and the ``binary_diff`` tool is the LLM-facing
wrapper that returns actionable error strings instead of tracebacks.

The tool is registered in the host tool registries separately — this
module must stay importable without a disassembler present.
"""

from __future__ import annotations

import difflib
import os
from typing import Annotated

from .base import tool
from .binary_format import parse_binary

# Byte similarity at/above this threshold counts as unchanged. ratn() is
# a float ratio, so a small epsilon below 1.0 absorbs rounding noise.
_UNCHANGED_SIMILARITY = 0.999

# Never pull more than this many bytes for one function — huge functions
# (or bogus symbol sizes) must not dominate the diff run.
MAX_BYTE_SLICE = 64 * 1024

# How many rows the markdown report lists per category before truncating.
MAX_REPORT_ROWS = 50


# ═══ Pure engine ═════════════════════════════════════════════════════════


def _summarize_info(info: dict) -> dict:
    """Trim a full parse_binary report down to what the report needs."""
    return {
        "format": info.get("format"),
        "arch": info.get("arch"),
        "bits": info.get("bits"),
        "file_type": info.get("file_type"),
        "file_size": info.get("file_size"),
        "num_symbols": len(info.get("symbols", [])),
        "num_sections": len(info.get("sections", [])),
    }


def _symbol_map(info: dict) -> dict[str, dict]:
    """Index symbols by name. When a name appears several times (symtab
    and dynsym, multiple sections), keep the entry with the largest size —
    the most informative one for byte extraction."""
    out: dict[str, dict] = {}
    for sym in info.get("symbols", []):
        name = sym.get("name")
        if not name:
            continue
        current = out.get(name)
        if current is None or sym.get("size", 0) > current.get("size", 0):
            out[name] = sym
    return out


def _function_bytes(data: bytes, info: dict, addr: int, size: int) -> bytes | None:
    """Extract a symbol's raw bytes, or None when impossible.

    Finds a section whose ``[vaddr, vaddr + size)`` range contains the
    symbol address, maps the address to a file offset, and slices out at
    most :data:`MAX_BYTE_SLICE` bytes.
    """
    if size <= 0:
        return None
    for sec in info.get("sections", []):
        sec_size = sec.get("size", 0)
        vaddr = sec.get("vaddr", 0)
        if sec_size <= 0 or not (vaddr <= addr < vaddr + sec_size):
            continue
        start = sec.get("offset", 0) + (addr - vaddr)
        if start < 0 or start >= len(data):
            return None
        chunk = data[start : start + min(size, MAX_BYTE_SLICE)]
        return chunk or None
    return None


def _raw_range(data: bytes | None, sec: dict | None) -> bytes | None:
    """Return a section's raw bytes when it lies fully inside the file."""
    if data is None or sec is None:
        return None
    off, size = sec.get("offset", 0), sec.get("size", 0)
    if size <= 0 or off < 0 or off + size > len(data):
        return None
    return data[off : off + size]


def compare_sections(
    old_info: dict, new_info: dict, old_data: bytes | None = None, new_data: bytes | None = None
) -> list[dict]:
    """Compare two parse-binary reports section by section (by name).

    Pure function over the report dicts; the raw file bytes are optional
    and enable byte-identity checks — when they are omitted (or a
    section's range is not valid in them) identical falls back to size
    equality. Returns ``[{name, old_size, new_size, identical}]`` sorted
    by name; a size of ``None`` means the section does not exist on that
    side.
    """
    old = {s.get("name", ""): s for s in old_info.get("sections", []) if s.get("name")}
    new = {s.get("name", ""): s for s in new_info.get("sections", []) if s.get("name")}

    changes: list[dict] = []
    for name in sorted(set(old) | set(new)):
        old_sec, new_sec = old.get(name), new.get(name)
        old_size = old_sec.get("size") if old_sec else None
        new_size = new_sec.get("size") if new_sec else None
        identical = old_size is not None and old_size == new_size
        if identical:
            old_bytes = _raw_range(old_data, old_sec)
            new_bytes = _raw_range(new_data, new_sec)
            if old_bytes is not None and new_bytes is not None:
                identical = old_bytes == new_bytes
        changes.append(
            {"name": name, "old_size": old_size, "new_size": new_size, "identical": identical}
        )
    return changes


def _match_rank(entry: dict) -> tuple:
    """Sort key: changed entries first, most-changed first, then by size."""
    sim = entry.get("similarity")
    divergence = 1.0 - sim if sim is not None else 1.0
    return (
        0 if entry.get("changed") else 1,
        -divergence,
        -max(entry.get("old_size", 0), entry.get("new_size", 0)),
        entry.get("name", ""),
    )


def diff_binaries(old_data: bytes, new_data: bytes) -> dict:
    """Pure diff engine over two raw binaries.

    Returns a dict with keys ``old_info`` / ``new_info`` (summarized
    parse reports), ``format_match``, ``matched`` (``[{name, old_addr,
    new_addr, old_size, new_size, similarity, changed}]``, most-changed
    first), ``added`` / ``removed`` (``[{name, addr, size}]``),
    ``stripped_fallback``, ``section_changes`` and ``totals``.

    Raises ValueError (from the parser) on empty or unrecognized input.
    """
    old_info = parse_binary(old_data)
    new_info = parse_binary(new_data)

    result: dict = {
        "old_info": _summarize_info(old_info),
        "new_info": _summarize_info(new_info),
        "format_match": old_info.get("format") == new_info.get("format")
        and old_info.get("arch") == new_info.get("arch"),
        "matched": [],
        "added": [],
        "removed": [],
        "stripped_fallback": False,
        "section_changes": [],
        "totals": {"matched": 0, "changed": 0, "added": 0, "removed": 0},
    }
    if not result["format_match"]:
        return result

    old_syms = _symbol_map(old_info)
    new_syms = _symbol_map(new_info)

    matched: list[dict] = []
    for name in sorted(set(old_syms) & set(new_syms)):
        old_sym, new_sym = old_syms[name], new_syms[name]
        old_size, new_size = old_sym.get("size", 0), new_sym.get("size", 0)
        old_bytes = _function_bytes(old_data, old_info, old_sym.get("addr", 0), old_size)
        new_bytes = _function_bytes(new_data, new_info, new_sym.get("addr", 0), new_size)

        if old_bytes is not None and new_bytes is not None:
            similarity: float | None = difflib.SequenceMatcher(None, old_bytes, new_bytes).ratio()
            changed = similarity < _UNCHANGED_SIMILARITY or old_size != new_size
        else:
            # No byte range on at least one side (size-0 symbol, address
            # outside every section, ...): compare sizes only.
            similarity = None
            changed = old_size != new_size

        matched.append(
            {
                "name": name,
                "old_addr": old_sym.get("addr", 0),
                "new_addr": new_sym.get("addr", 0),
                "old_size": old_size,
                "new_size": new_size,
                "similarity": similarity,
                "changed": changed,
            }
        )
    matched.sort(key=_match_rank)

    added = [
        {"name": name, "addr": new_syms[name].get("addr", 0), "size": new_syms[name].get("size", 0)}
        for name in sorted(set(new_syms) - set(old_syms))
    ]
    removed = [
        {"name": name, "addr": old_syms[name].get("addr", 0), "size": old_syms[name].get("size", 0)}
        for name in sorted(set(old_syms) - set(new_syms))
    ]

    result["matched"] = matched
    result["added"] = added
    result["removed"] = removed
    result["totals"] = {
        "matched": len(matched),
        "changed": sum(1 for m in matched if m["changed"]),
        "added": len(added),
        "removed": len(removed),
    }

    if not old_syms and not new_syms:
        # Both stripped: no names to match, so compare sections instead.
        result["stripped_fallback"] = True
        result["section_changes"] = compare_sections(old_info, new_info, old_data, new_data)

    return result


# ═══ Markdown formatting ═════════════════════════════════════════════════


def _describe_target(info: dict) -> str:
    if not info:
        return "unknown"
    arch = info.get("arch") or "?"
    fmt = info.get("format") or "?"
    ftype = f" {info['file_type']}" if info.get("file_type") else ""
    return f"{fmt}/{arch}{ftype} ({info.get('file_size', 0)} bytes)"


def format_diff_report(result: dict) -> str:
    """Render a :func:`diff_binaries` result as a markdown report."""
    old, new = result.get("old_info", {}), result.get("new_info", {})

    if not result.get("format_match", False):
        return (
            "## Binary Diff Report\n\n"
            f"**Cannot diff: not the same target.** OLD is {_describe_target(old)}, "
            f"NEW is {_describe_target(new)}.\n\n"
            "Comparing different binary formats or architectures is meaningless — "
            "check that both paths point to different builds of the same program."
        )

    totals = result.get("totals", {})
    lines = ["## Binary Diff Report\n"]
    lines.append(
        f"**Summary:** {totals.get('matched', 0)} functions matched "
        f"({totals.get('changed', 0)} changed), {totals.get('added', 0)} added, "
        f"{totals.get('removed', 0)} removed — OLD {_describe_target(old)} → "
        f"NEW {_describe_target(new)}\n"
    )

    if result.get("stripped_fallback"):
        lines.append(
            "Both binaries are stripped (no symbols), so named-function diffing is "
            "impossible — a symbol table (or exports) is needed to match functions "
            "by name. Falling back to a section-level comparison:\n"
        )
        lines.append("### Section Changes\n")
        changes = result.get("section_changes", [])
        if not changes:
            lines.append("- No section-level differences found.\n")
        for sc in changes:
            old_size, new_size = sc.get("old_size"), sc.get("new_size")
            if old_size is None:
                detail = f"new section, {new_size} bytes"
            elif new_size is None:
                detail = f"section removed (was {old_size} bytes)"
            else:
                state = "identical" if sc.get("identical") else "differs"
                detail = f"{old_size} → {new_size} bytes ({state})"
            lines.append(f"- `{sc.get('name', '?')}` — {detail}")
        lines.append("")
        return "\n".join(lines)

    changed = [m for m in result.get("matched", []) if m.get("changed")]
    lines.append(f"### Changed Functions ({len(changed)})\n")
    if not changed:
        lines.append("- None — no matched function changed.\n")
    for m in changed[:MAX_REPORT_ROWS]:
        sim = m.get("similarity")
        sim_txt = f"{sim * 100:.1f}% similar" if sim is not None else "size-only compare"
        lines.append(
            f"- `{m.get('name', '?')}` — {sim_txt}, {m.get('old_size', 0)} → "
            f"{m.get('new_size', 0)} bytes, {m.get('old_addr', 0):#x} → {m.get('new_addr', 0):#x}"
        )
    if len(changed) > MAX_REPORT_ROWS:
        lines.append(f"\n- ... {len(changed) - MAX_REPORT_ROWS} more changed functions not shown")
    lines.append("")

    added = result.get("added", [])
    lines.append(f"### Added Functions ({len(added)})\n")
    if not added:
        lines.append("- None.\n")
    for a in added[:MAX_REPORT_ROWS]:
        lines.append(f"- `{a.get('name', '?')}` at {a.get('addr', 0):#x} ({a.get('size', 0)} bytes)")
    if len(added) > MAX_REPORT_ROWS:
        lines.append(f"\n- ... {len(added) - MAX_REPORT_ROWS} more added functions not shown")
    lines.append("")

    removed = result.get("removed", [])
    lines.append(f"### Removed Functions ({len(removed)})\n")
    if not removed:
        lines.append("- None.\n")
    for r in removed[:MAX_REPORT_ROWS]:
        lines.append(f"- `{r.get('name', '?')}` at {r.get('addr', 0):#x} ({r.get('size', 0)} bytes)")
    if len(removed) > MAX_REPORT_ROWS:
        lines.append(f"\n- ... {len(removed) - MAX_REPORT_ROWS} more removed functions not shown")
    lines.append("")

    if totals.get("changed", 0):
        lines.append(
            "Start with the most-changed functions above — in a 1-day patch these are "
            "usually the fixed code paths."
        )
    return "\n".join(lines)


# ═══ Tool wrapper ════════════════════════════════════════════════════════


def _error(message: str) -> str:
    return f"**Error:** binary_diff failed — {message}"


@tool(
    category="analysis",
    description="Diff two versions of a binary: added/removed/changed functions (1-day patch hunting)",
)
def binary_diff(
    old_path: Annotated[str, "Path to the OLD binary version (e.g. before the patch)"],
    new_path: Annotated[str, "Path to the NEW binary version (e.g. after the patch)"],
) -> str:
    """Compare two versions of the same binary (ELF / PE / Mach-O).

    Matches functions by symbol name across the two files and ranks the
    changed ones by byte similarity — the usual starting point when
    hunting what a vendor patch actually fixed. Returns a markdown
    report, or an actionable error string for missing files, unparseable
    input or format/architecture mismatches.
    """
    for label, path in (("old", old_path), ("new", new_path)):
        if not os.path.isfile(path):
            hint = "pre-patch (old)" if label == "old" else "patched (new)"
            return _error(f"{label} binary not found: {path} — pass the full path to the {hint} version of the file")

    try:
        with open(old_path, "rb") as fh:
            old_data = fh.read()
        with open(new_path, "rb") as fh:
            new_data = fh.read()
    except OSError as exc:
        return _error(f"cannot read input files: {exc}")

    try:
        result = diff_binaries(old_data, new_data)
    except ValueError:
        details = []
        for label, data in (("old", old_data), ("new", new_data)):
            try:
                parse_binary(data)
            except ValueError as exc:
                details.append(f"{label}: {exc}")
        return _error(
            f"could not parse binaries ({'; '.join(details) or 'unrecognized input'}) — "
            "both files must be raw ELF, PE or Mach-O binaries"
        )

    return format_diff_report(result)
