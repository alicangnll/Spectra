"""Rich file metadata: hashes, format details, sections, imports, PDB path, Go build info.

Built on the pure stdlib parser in :mod:`spectra.tools.binary_format`, so
the core report never requires a pip package. The optional ``pefile``
module only enriches the PE report (imphash, parser warnings); when it is
absent a note under the report's "Optional" section explains how to get
the missing piece — it is never treated as an error.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import UTC, datetime
from typing import Annotated, Any

from .base import tool
from .binary_format import parse_binary

# ─── Optional dependency: pefile ───────────────────────────────────────────


def check_pefile_available() -> bool:
    """Return True when the optional pefile module is importable."""
    try:
        import pefile  # noqa: F401 — availability probe

        return True
    except ImportError:
        return False


# ─── Pure byte-level helpers ───────────────────────────────────────────────

_PDB_MAGIC = b"RSDS"  # CodeView NB10 debug record: magic + 16-byte GUID + 4-byte age + path
_PDB_EXT = ".pdb"
_MAX_PDB_CANDIDATES = 64

_GO_BUILD_ID = b"Go build ID:"
_GO_VERSION = re.compile(rb"go1\.[0-9]{1,2}(?:\.[0-9]{1,2})?")

# PE timestamps are 32-bit seconds; anything past 2100 is nonsense.
_MAX_SANE_TIMESTAMP = 4102444800

# Report caps — keep the markdown bounded for huge binaries.
_MAX_IMPORTS_PER_DLL = 200
_MAX_EXPORTS_SHOWN = 20


def compute_hashes(data: bytes) -> dict[str, str]:
    """Compute md5/sha1/sha256 hex digests (stdlib only)."""
    return {
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def find_pdb_path(data: bytes) -> str:
    """Extract the PDB path from an RSDS CodeView record — '' when absent.

    Pure bytes scan: finds ``b"RSDS"``, skips the 16-byte GUID plus the
    4-byte age, then reads the NUL-terminated path. Candidates that
    actually contain ``.pdb`` win over stray magic occurrences.
    """
    fallback = ""
    pos = data.find(_PDB_MAGIC)
    for _ in range(_MAX_PDB_CANDIDATES):
        if pos == -1:
            break
        start = pos + len(_PDB_MAGIC) + 16 + 4
        end = data.find(b"\x00", start, min(len(data), start + 4096))
        if end < 0:
            end = min(len(data), start + 4096)
        candidate = data[start:end].decode("utf-8", "replace") if start < len(data) else ""
        if candidate:
            if _PDB_EXT in candidate.lower():
                return candidate
            if not fallback:
                fallback = candidate
        pos = data.find(_PDB_MAGIC, pos + 1)
    return fallback


def find_go_buildinfo(data: bytes) -> str:
    """Return short Go build evidence ('' for non-Go payloads).

    Detects the classic ``Go build ID:`` marker and/or an embedded
    toolchain version string such as ``go1.21.0``.
    """
    evidence: list[str] = []
    idx = data.find(_GO_BUILD_ID)
    if idx != -1:
        evidence.append(f"Go build ID at offset {idx:#x}")
    m = _GO_VERSION.search(data)
    if m:
        evidence.append(f"Go toolchain {m.group(0).decode('ascii', 'replace')}")
    return "; ".join(evidence)


# ─── Report formatting ─────────────────────────────────────────────────────

_FLAG_LABELS = (
    ("pie", "PIE"),
    ("nx", "NX"),
    ("relro", "RELRO"),
    ("canary", "Canary"),
    ("cfg", "CFG"),
    ("signed", "Signed"),
    ("high_entropy_va", "High-entropy VA"),
    ("no_seh", "No SEH"),
)


def _flag(value: Any) -> str:
    if value is None:
        return "n/a"
    return "yes" if value else "no"


def format_meta_report(info: dict, extras: dict) -> str:
    """Render a parse_binary() report plus computed extras as markdown."""
    lines: list[str] = ["## File Metadata Report\n"]

    # Overview
    path = str(extras.get("path", "") or "")
    if path:
        lines.append(f"**Path:** `{path}`")
    lines.append(f"**Format:** {info.get('format', '?')} — {info.get('file_type', '?')}")
    lines.append(
        f"**Architecture:** {info.get('arch', '?')} / {info.get('bits', '?')}-bit / "
        f"{info.get('endian', '?')}-endian"
    )
    if info.get("subsystem"):
        lines.append(f"**Subsystem:** {info['subsystem']}")
    lines.append(f"**Size:** {info.get('file_size', 0):,} bytes")
    for algo in ("md5", "sha1", "sha256"):
        digest = extras.get(algo)
        if digest:
            lines.append(f"**{algo.upper()}:** `{digest}`")
    lines.append("")

    # Mitigation / hardening flags the report actually carries
    flags = []
    for key, label in _FLAG_LABELS:
        if key in info:
            value = info[key]
            flags.append(f"{label}: {value if isinstance(value, str) else _flag(value)}")
    if flags:
        lines.append("**Mitigations:** " + " | ".join(flags) + "\n")

    # Sections
    sections = info.get("sections") or []
    lines.append(f"### Sections ({len(sections)})\n")
    if sections:
        lines.append("| Name | Offset | Size | VAddr | Exec | Write |")
        lines.append("|------|--------|------|-------|------|-------|")
        for s in sections:
            lines.append(
                f"| {s.get('name', '')} | `{s.get('offset', 0):#x}` | {s.get('size', 0):,} | "
                f"`{s.get('vaddr', 0):#x}` | {'x' if s.get('exec') else '-'} | "
                f"{'w' if s.get('write') else '-'} |"
            )
    else:
        lines.append("- no section metadata")
    lines.append("")

    # Imports: PE import tables, otherwise the needed/dylib list
    lines.append("### Imports\n")
    imports = info.get("imports")
    if imports:
        for dll, funcs in list(imports.items()):
            funcs = funcs or []
            shown = ", ".join(f"`{f}`" for f in funcs[:_MAX_IMPORTS_PER_DLL])
            more = len(funcs) - _MAX_IMPORTS_PER_DLL
            tail = f" … +{more} more" if more > 0 else ""
            lines.append(f"- **{dll}** ({len(funcs)}): {shown}{tail}")
    elif info.get("needed"):
        for lib in info["needed"]:
            lines.append(f"- {lib}")
    else:
        lines.append("- none found")
    lines.append("")

    # Symbols / exports counts
    lines.append("### Symbols & Exports\n")
    lines.append(f"- Defined symbols: {len(info.get('symbols') or [])}")
    if "exports" in info:
        exports = info.get("exports") or []
        lines.append(f"- Exports: {len(exports)}")
        for e in exports[:_MAX_EXPORTS_SHOWN]:
            lines.append(f"  - `{e.get('name', '')}` @ `{e.get('addr', 0):#x}`")
    lines.append("")

    # Extras: everything computed on top of the parsed structure
    lines.append("### Extras\n")
    extra_rows: list[str] = []
    if extras.get("pdb_path"):
        extra_rows.append(f"- **PDB path:** `{extras['pdb_path']}`")
    if extras.get("go_buildinfo"):
        extra_rows.append(f"- **Go:** {extras['go_buildinfo']}")
    if extras.get("compiled"):
        extra_rows.append(f"- **Compiled:** {extras['compiled']}")
    if extras.get("imphash"):
        extra_rows.append(f"- **imphash:** `{extras['imphash']}`")
    if info.get("interpreter"):
        extra_rows.append(f"- **Interpreter:** `{info['interpreter']}`")
    if "static" in info:
        extra_rows.append(f"- **Static:** {'yes' if info['static'] else 'no'}")
    overlay = info.get("overlay") or {}
    if overlay.get("size"):
        extra_rows.append(f"- **Overlay:** {overlay['size']:,} bytes at offset `{overlay['offset']:#x}`")
    if info.get("has_tls_callbacks"):
        extra_rows.append("- **TLS callbacks:** present")
    if info.get("has_debug_dir"):
        extra_rows.append("- **Debug directory:** present")
    for w in extras.get("pe_warnings") or []:
        extra_rows.append(f"- **pefile warning:** {w}")
    lines.extend(extra_rows if extra_rows else ["- nothing notable"])
    lines.append("")

    # Optional-dependency notes — informational, never an error
    optional_notes = extras.get("optional_notes") or []
    if optional_notes:
        lines.append("### Optional\n")
        for note in optional_notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)


# ─── PE enrichment (needs pefile) ──────────────────────────────────────────


def _format_timestamp(ts: int) -> str:
    """Render a PE compile timestamp in UTC; keep the raw value for nonsense dates."""
    try:
        if ts <= 0 or ts > _MAX_SANE_TIMESTAMP:
            raise ValueError("timestamp out of plausible range")
        stamp = datetime.fromtimestamp(ts, UTC)
        return f"{stamp.strftime('%Y-%m-%d %H:%M:%S')} UTC (raw {ts:#x})"
    except (ValueError, OverflowError, OSError):
        return f"raw {ts:#x} (implausible timestamp)"


def _add_pefile_extras(data: bytes, extras: dict[str, Any]) -> None:
    """Add imphash and pefile warnings when pefile is installed; otherwise note it."""
    if not check_pefile_available():
        extras.setdefault("optional_notes", []).append(
            "pefile not installed — imphash unavailable (pip install pefile)"
        )
        return

    import pefile

    try:
        pe = pefile.PE(data=data, fast_load=True)
    except Exception as e:  # pefile raises assorted parse errors on garbage
        extras.setdefault("pe_warnings", []).append(f"pefile could not parse the file: {e}")
        return

    try:
        imphash = pe.get_imphash()
        if imphash:
            extras["imphash"] = str(imphash)
    except Exception:
        pass
    extras["pe_warnings"] = [str(w) for w in (getattr(pe, "warnings", None) or [])][:10]
    try:
        pe.close()
    except Exception:
        pass


# ─── Host integration ──────────────────────────────────────────────────────


def _current_input_file() -> str:
    try:
        from ..core.host import get_database_path, is_ida

        if is_ida():
            import idaapi

            p = idaapi.get_input_file_path()
            if p:
                return str(p)
        return get_database_path()
    except Exception:
        return ""


# ─── Tool entry point ──────────────────────────────────────────────────────


@tool(
    category="analysis",
    description="Rich file metadata: hashes, format details, sections, imports, PDB path, Go build info",
)
def file_meta(path: Annotated[str, "Binary path (empty = current input file)"] = "") -> str:
    """Hash a binary and report its structure, PDB path and build info."""

    resolved = (path or "").strip() or _current_input_file()
    if not resolved:
        return (
            "No file specified and no input file is loaded in the host.\n"
            "\n"
            "Pass a path explicitly, e.g. `file_meta(path='/path/to/binary')`, "
            "or load a binary into the IDA / Binary Ninja database first."
        )

    if not os.path.isfile(resolved):
        return f"Error: file not found: `{resolved}`"

    try:
        with open(resolved, "rb") as fh:
            data = fh.read()
    except OSError as e:
        return f"Error: cannot read `{resolved}`: {e}"

    try:
        info = parse_binary(data)
    except ValueError as e:
        return (
            f"Error parsing `{resolved}`: {e}\n"
            "\n"
            "file_meta covers ELF, PE and Mach-O. For other formats compute "
            "hashes with a shell tool (e.g. `shasum -a 256 <file>`)."
        )

    extras: dict[str, Any] = {"path": resolved, **compute_hashes(data)}

    if info.get("format") == "PE":
        extras["pdb_path"] = find_pdb_path(data)
        ts = info.get("timestamp")
        if isinstance(ts, int) and ts:
            extras["compiled"] = _format_timestamp(ts)
        _add_pefile_extras(data, extras)

    go_info = find_go_buildinfo(data)  # any format can embed Go build info
    if go_info:
        extras["go_buildinfo"] = go_info

    return format_meta_report(info, extras)
