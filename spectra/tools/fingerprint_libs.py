"""Statically-linked library version fingerprinting.

Recover "what is compiled into this binary?" from version strings and
build markers: OpenSSL/BoringSSL/LibreSSL, zlib, libcurl, sqlite, Boost,
Qt, Go, and friends. Statically-linked libraries leave no imports to
match, but they almost always keep their version banners — this module
finds them and maps them to exact versions so known CVEs can be reasoned
about.

Pure analyzer (:func:`fingerprint_libraries_from_strings`) + markdown
formatter + thin :func:`fingerprint_libs` tool, mirroring the
ssl_pinning / crypto_detect engine idiom.
"""

from __future__ import annotations

import re
from typing import Annotated

from .base import tool
from .binary_format import parse_binary

# Library signature catalog: (library, compiled regex, reporting note).
# Every regex MUST expose the version in group 1 and be specific enough
# to survive concatenation with surrounding string data.
_LIB_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("OpenSSL", re.compile(r"OpenSSL\s+(\d+\.\d+\.\d+[a-z]?(?:[-+][\w.]+)?)"), ""),
    ("LibreSSL", re.compile(r"LibreSSL\s+(\d+\.\d+(?:\.\d+)?)"), "OpenBSD fork"),
    ("BoringSSL", re.compile(r"BoringSSL\s+(\d+)"), "Google fork — version is a date stamp"),
    ("mbedTLS", re.compile(r"mbed[\s_-]?TLS\s+(\d+\.\d+\.\d+)"), ""),
    ("wolfSSL", re.compile(r"wolfSSL\s+(\d+\.\d+\.\d+)"), ""),
    ("GnuTLS", re.compile(r"[Gg]nu[Tt][Ll][Ss]\s+(\d+\.\d+\.\d+)"), ""),
    ("libcurl", re.compile(r"libcurl/(\d+\.\d+\.\d+)"), ""),
    ("libssh2", re.compile(r"libssh2[\s_-]?(\d+\.\d+(?:\.\d+)?)"), ""),
    ("nghttp2", re.compile(r"nghttp2/(\d+\.\d+\.\d+)"), ""),
    ("libxml2", re.compile(r"libxml\s+(\d+\.\d+(?:\.\d+)?)"), ""),
    ("expat", re.compile(r"[Ee]xpat[\s_]?(\d+\.\d+(?:\.\d+)?)"), ""),
    ("SQLite", re.compile(r"SQLite\s+(\d+\.\d+(?:\.\d+)?)"), ""),
    ("zlib", re.compile(r"(?:deflate|inflate)\s+(\d+\.\d+(?:\.\d+)?)"), "banner is 'deflate/inflate <ver>'"),
    ("Lua", re.compile(r"^Lua\s+(\d+\.\d+(?:\.\d+)?)"), ""),
    ("libpng", re.compile(r"libpng\s+version\s+(\d+\.\d+\.\d+)"), ""),
    ("FreeType", re.compile(r"FreeType\s+(\d+\.\d+\.\d+)"), ""),
    ("libjpeg-turbo", re.compile(r"libjpeg-turbo[,\s]+version\s+(\d+\.\d+(\.\d+)?)"), ""),
    ("Boost", re.compile(r"boost[_/](\d+_\d+(?:_\d+)?)"), "build-path marker, underscores"),
    ("Qt", re.compile(r"^Qt\s+(\d+\.\d+\.\d+)"), ""),
    ("libuv", re.compile(r"libuv/(\d+\.\d+\.\d+)"), ""),
    ("Go", re.compile(r"\bgo(1\.\d+(?:\.\d+)?)"), "Go runtime/toolchain"),
]

# Presence-only markers (library embedded but no version banner found).
_PRESENCE_MARKERS: list[tuple[str, re.Pattern[str]]] = [
    ("BoringSSL", re.compile(r"BoringSSL", re.IGNORECASE)),
    ("wolfSSL", re.compile(r"wolfSSL", re.IGNORECASE)),
    ("mbedTLS", re.compile(r"mbed_?tls", re.IGNORECASE)),
]

MAX_EVIDENCE = 80
MAX_EVIDENCE_PER_LIB = 5


def _extract_ascii_strings(data: bytes, min_len: int = 4) -> list[str]:
    """ASCII printable runs (duplicated by design from ioc_collector so the
    module stays standalone like every other tool module)."""
    return [m.group(0).decode("ascii") for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, data)]


def fingerprint_libraries_from_strings(strings: list[str]) -> dict:
    """Pure engine: match library version banners in *strings*.

    Returns {"libraries": [{library, version, confidence, evidence, count}],
    "presence_only": [library, ...], "total": int}
    """
    found: dict[tuple[str, str], int] = {}
    evidence: dict[tuple[str, str], list[str]] = {}

    text = "\n".join(strings)
    notes: dict[str, str] = {}
    for s in strings:
        for lib, pattern, note in _LIB_PATTERNS:
            m = pattern.search(s)
            if not m:
                continue
            version = m.group(1)
            if note:
                notes[lib] = note
            key = (lib, version)
            if key not in evidence:
                evidence[key] = []
            if len(evidence[key]) < MAX_EVIDENCE_PER_LIB:
                evidence[key].append(s[:MAX_EVIDENCE])
            found[key] = found.get(key, 0) + 1

    libraries = [
        {
            "library": lib,
            "version": version,
            "confidence": "high",
            "note": notes.get(lib, ""),
            "evidence": evidence.get((lib, version), []),
            "count": count,
        }
        for (lib, version), count in sorted(found.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    ]

    seen = {entry["library"] for entry in libraries}
    presence_only: list[str] = []
    for lib, marker in _PRESENCE_MARKERS:
        if lib not in seen and marker.search(text):
            presence_only.append(lib)

    return {"libraries": libraries, "presence_only": sorted(presence_only), "total": len(libraries)}


def analyze_libraries(data: bytes) -> dict:
    """Extract strings from raw file bytes and fingerprint embedded libraries."""
    strings = _extract_ascii_strings(data)
    result = fingerprint_libraries_from_strings(strings)
    result["strings_scanned"] = len(strings)
    try:
        info = parse_binary(data)
        result["binary"] = {k: info[k] for k in ("format", "arch", "bits", "file_type")}
    except ValueError:
        result["binary"] = None
    return result


def format_lib_report(result: dict, path: str = "") -> str:
    title = path or "current binary"
    out = [f"## Library fingerprint — {title}", ""]
    if result.get("binary"):
        b = result["binary"]
        out.append(f"**Binary:** {b['format']} · {b['arch']} · {b['bits']}-bit · {b['file_type']}")
        out.append("")

    libs = result.get("libraries", [])
    if not libs:
        out.append(
            "No embedded library version banners found. Either the binary uses only "
            "system shared libraries (check imports) or banners were stripped."
        )
        if result.get("presence_only"):
            out.append("")
            out.append(
                "Presence-only markers (no version): " + ", ".join(result["presence_only"])
            )
        return "\n".join(out)

    out.append("| Library | Version | Evidence |")
    out.append("|---|---|---|")
    for entry in libs:
        ev = entry["evidence"][0] if entry["evidence"] else ""
        ev = ev.replace("|", "\\|")
        lib = entry["library"] + (f" — {entry['note']}" if entry.get("note") else "")
        out.append(f"| {lib} | {entry['version']} | `{ev}` |")
    if result.get("presence_only"):
        out.append("")
        out.append(
            f"Presence-only (version banner not found): {', '.join(result['presence_only'])}"
        )

    out.append("")
    out.append("### Next steps")
    out.append(
        "- Cross-check each exact version against known CVEs "
        "(the version is now pinned — no guessing)"
    )
    out.append(
        "- Statically-linked crypto stacks (OpenSSL family) are prime targets: "
        "find their import-style calls via the ssl_pinning detector"
    )
    return "\n".join(out)


def _current_input_file() -> str:
    """Best-effort path of the binary loaded in the host."""
    try:
        from ..core.host import get_database_path, is_ida

        if is_ida():
            import idaapi

            path = idaapi.get_input_file_path()
            if path:
                return str(path)
        return get_database_path()
    except Exception:
        return ""


@tool(category="analysis", description="Fingerprint statically-linked libraries and their exact versions (OpenSSL, zlib, libcurl, sqlite, Boost, Qt...)")
def fingerprint_libs(
    path: Annotated[str, "Binary path (empty = current input file)"] = "",
) -> str:
    """Identify library versions compiled into the binary.

    Statically-linked libraries keep version banners ("OpenSSL 1.0.2k",
    "deflate 1.2.11", "libcurl/7.81.0") even with no imports to match.
    Returns each library with its exact version and the evidence string,
    so known CVEs for that version can be checked. Pure Python.
    """
    target = path or _current_input_file()
    if not target:
        return "Error: no path given and no binary loaded in the host."
    try:
        with open(target, "rb") as fh:
            data = fh.read()
    except OSError as e:
        return f"Error: cannot read '{target}': {e}"
    return format_lib_report(analyze_libraries(data), target)
