"""YARA rule generation and scanning tools.

Rule *generation* is pure string building — no yara module is required —
so an exportable rule can always be produced. *Scanning* needs the
optional ``yara-python`` package; when it is missing the scan tool returns
an actionable install hint instead of a traceback.
"""

from __future__ import annotations

import os
import re
from typing import Annotated, Any

from .base import tool

# ─── Optional dependency: yara-python ──────────────────────────────────────


def check_yara_available() -> bool:
    """Return True when the yara-python module is importable."""
    try:
        import yara  # noqa: F401 — availability probe

        return True
    except ImportError:
        return False


_YARA_INSTALL_HINT = (
    "yara-python is not installed, so YARA scanning is unavailable.\n"
    "\n"
    "Install it with:\n"
    "    pip install yara-python\n"
    "\n"
    "Rule generation (`yara_generate`) works without it — generate the rule "
    "here and scan it with the standalone `yara` CLI or inside another host."
)


# ─── Pure rule builder ─────────────────────────────────────────────────────

_HEX_PATTERN = re.compile(r"[0-9a-fA-F?*]+")


def _sanitize_rule_name(name: str) -> str:
    """Coerce an arbitrary string into a valid YARA rule identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", (name or "").strip()).strip("_")
    if not cleaned:
        return "spectra_rule"
    if cleaned[0].isdigit():  # identifiers cannot start with a digit
        cleaned = f"_{cleaned}"
    return cleaned


def _escape_yara_string(value: str) -> str:
    """Escape a Python string as a YARA double-quoted text string.

    Backslashes, quotes and newlines are escaped; any other
    non-printable / non-ASCII byte becomes ``\\xNN``.
    """
    out: list[str] = []
    for byte in value.encode("utf-8"):
        if byte == 0x5C:  # backslash
            out.append("\\\\")
        elif byte == 0x22:  # double quote
            out.append('\\"')
        elif byte == 0x0A:
            out.append("\\n")
        elif byte == 0x0D:
            out.append("\\r")
        elif byte == 0x09:
            out.append("\\t")
        elif 0x20 <= byte <= 0x7E:  # printable ASCII
            out.append(chr(byte))
        else:
            out.append(f"\\x{byte:02x}")
    return "".join(out)


def _normalize_hex_pattern(pattern: str) -> str:
    """Validate a hex pattern loosely and pretty-print it for the rule body.

    Accepts hex nibbles, ``?`` nibble wildcards and ``*`` jump wildcards
    (spaces allowed anywhere). Raises ValueError on anything else or on a
    pattern whose nibble count is odd (unusable without jumps).
    """
    if not isinstance(pattern, str):
        raise ValueError(f"hex pattern must be a string, got {type(pattern).__name__}")
    compact = pattern.replace(" ", "").replace("\t", "").strip()
    if not compact or not _HEX_PATTERN.fullmatch(compact):
        raise ValueError(f"invalid hex pattern {pattern!r} (expected hex nibbles with ? and * wildcards)")
    upper = compact.upper()
    if "*" in upper:
        # Jump wildcards sit between bytes — keep the author's spacing.
        return pattern.strip().upper()
    if len(upper) % 2:
        raise ValueError(f"hex pattern {pattern!r} has an odd number of nibbles")
    return " ".join(upper[i : i + 2] for i in range(0, len(upper), 2))


def _build_condition(condition: str, total: int) -> str:
    """Combine an optional custom condition with the default strings check.

    ``any of them`` by default, ``2 of them`` when more than two strings
    are declared. A custom condition that already quantifies the declared
    strings (mentions ``of them`` or a ``$identifier``) stands alone;
    anything else is appended safely with ``and``.
    """
    default = "2 of them" if total > 2 else "any of them"
    custom = (condition or "").strip()
    if not custom:
        return default
    if "of them" in custom or "$" in custom:
        return custom
    return f"{custom} and {default}"


def generate_yara_rule(
    name: str = "spectra_rule",
    strings: list[str] | None = None,
    hex_patterns: list[str] | None = None,
    condition: str = "",
) -> str:
    """Build a well-formed YARA rule from literal strings and hex patterns.

    Pure rule builder — no yara dependency needed. The rule name is
    sanitized to a valid identifier (``"my rule!"`` becomes ``my_rule``),
    string literals are escaped, and hex patterns are validated loosely.
    Raises ValueError when the rule would be empty or a pattern is garbage.
    """
    lits = [s for s in (strings or []) if s]
    pats = [_normalize_hex_pattern(p) for p in (hex_patterns or []) if p and p.strip()]
    if not lits and not pats:
        raise ValueError("cannot generate an empty rule: provide at least one string or hex pattern")

    total = len(lits) + len(pats)
    desc_parts = []
    if lits:
        desc_parts.append(f"{len(lits)} literal string(s)")
    if pats:
        desc_parts.append(f"{len(pats)} hex pattern(s)")

    lines = [
        f"rule {_sanitize_rule_name(name)} {{",
        "    meta:",
        '        generated = "spectra"',
        f'        description = "Auto-generated by Spectra from {" and ".join(desc_parts)}"',
        "    strings:",
    ]
    for i, s in enumerate(lits, 1):
        lines.append(f'        $s{i} = "{_escape_yara_string(s)}"')
    for i, p in enumerate(pats, 1):
        lines.append(f"        $h{i} = {{ {p} }}")
    lines.append("    condition:")
    lines.append(f"        {_build_condition(condition, total)}")
    lines.append("}")
    return "\n".join(lines)


# ─── Match reporting ───────────────────────────────────────────────────────

_MAX_STRING_ROWS = 50
_MAX_PREVIEW_BYTES = 16


def _hex_preview(data: bytes, limit: int = _MAX_PREVIEW_BYTES) -> str:
    if not data:
        return ""
    return " ".join(f"{b:02x}" for b in data[:limit]) + (" …" if len(data) > limit else "")


def _match_strings(raw: Any) -> list[tuple[int, str, bytes]]:
    """Normalize matched-string shapes to (offset, identifier, data) tuples.

    Accepts the plain 3-tuples used by dict-shaped results, the tuples of
    yara-python 3.x, and the StringMatch/InstanceMatch objects of 4.x.
    """
    out: list[tuple[int, str, bytes]] = []
    for item in raw or []:
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            offset, ident = item[0], str(item[1])
            data = item[2] if len(item) >= 3 else b""
            if not isinstance(data, (bytes, bytearray)):
                data = str(data).encode("utf-8", "replace")
            try:
                off = int(offset)
            except (TypeError, ValueError):
                off = 0
            out.append((off, ident, bytes(data)))
            continue
        ident = str(getattr(item, "identifier", "?"))
        for inst in getattr(item, "instances", None) or []:
            try:
                out.append((int(inst.offset), ident, bytes(inst.matched_data)))
            except Exception:
                continue
    return out


def format_match_report(matches: list, path: str) -> str:
    """Format YARA match results (yara.Match objects OR plain dicts) as markdown."""
    lines = ["## YARA Scan Report\n", f"**Target:** `{path}`"]
    if not matches:
        lines.append("\n**Result:** no matches.")
        return "\n".join(lines)

    lines.append(f"\n**Result:** {len(matches)} rule(s) matched.\n")
    for m in matches:
        if isinstance(m, dict):
            rule = str(m.get("rule", "unknown"))
            tags = [str(t) for t in (m.get("tags") or [])]
            raw_strings = m.get("strings") or []
        else:
            rule = str(getattr(m, "rule", "unknown"))
            tags = [str(t) for t in (getattr(m, "tags", None) or [])]
            raw_strings = getattr(m, "strings", None) or []

        tag_txt = f" ({', '.join(tags)})" if tags else ""
        lines.append(f"### {rule}{tag_txt}\n")
        entries = _match_strings(raw_strings)
        if not entries:
            lines.append("- matched (no string details reported)")
        for off, ident, data in entries[:_MAX_STRING_ROWS]:
            lines.append(f"- `{off:#010x}` `{ident}` matched {len(data)} bytes: `{_hex_preview(data)}`")
        if len(entries) > _MAX_STRING_ROWS:
            lines.append(f"- … and {len(entries) - _MAX_STRING_ROWS} more string matches")
        lines.append("")
    return "\n".join(lines)


# ─── Tool entry points ─────────────────────────────────────────────────────


@tool(category="analysis", description="Generate a YARA rule from strings/hex patterns")
def yara_generate(
    strings: Annotated[list[str] | None, "Literal strings to match"] = None,
    hex_patterns: Annotated[list[str] | None, "Hex byte patterns, e.g. \"AA BB ?? CC\" (?/* wildcards)"] = None,
    name: Annotated[str, "Rule name (sanitized to a valid identifier)"] = "spectra_rule",
    condition: Annotated[str, "Optional extra condition, e.g. 'filesize < 100KB'"] = "",
) -> str:
    """Generate an exportable YARA rule from strings and/or hex patterns."""

    try:
        rule = generate_yara_rule(name=name, strings=strings or [], hex_patterns=hex_patterns or [], condition=condition)
    except ValueError as e:
        return f"Error: {e}"

    counts = f"{len(strings or [])} literal string(s), {len(hex_patterns or [])} hex pattern(s)"
    return f"Generated YARA rule ({counts}):\n\n```yara\n{rule}\n```\n\nScan a file with it via `yara_scan`."


@tool(category="analysis", description="Scan a file with a YARA rule")
def yara_scan(
    path: Annotated[str, "File to scan"],
    rule_text: Annotated[str, "Full YARA rule source"],
) -> str:
    """Compile a YARA rule and scan a file with it (requires yara-python)."""

    if not check_yara_available():
        return _YARA_INSTALL_HINT

    import yara

    if not rule_text or not rule_text.strip():
        return "Error: empty rule — pass the full rule source (see `yara_generate`)."
    if not path or not os.path.exists(path):
        return f"Error: file not found: `{path}`"

    try:
        rules = yara.compile(source=rule_text)
    except yara.Error as e:
        return f"YARA compile error — the rule source is invalid:\n\n```\n{e}\n```"

    try:
        matches = rules.match(path)
    except yara.Error as e:
        return f"YARA scan error for `{path}`:\n\n```\n{e}\n```"
    except OSError as e:
        return f"Error: cannot read `{path}`: {e}"

    return format_match_report(matches, path)
