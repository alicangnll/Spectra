"""Cryptographic constant detection tool.

Identifies crypto algorithms embedded in a binary by searching for their
*structural constants* — lookup tables, round constants, initial vectors and
magic strings — never by guessing from nearby strings. A constant match is
hard evidence: the bytes at that offset are mathematically tied to the
algorithm family (AES S-box bytes, SHA round words, the TEA golden-ratio
delta, the ChaCha sigma constant, ...).

Engine layout mirrors ``ssl_pinning``: a pure analyzer over raw bytes
(:func:`analyze_crypto`), a markdown formatter (:func:`format_crypto_report`)
and a thin ``@tool`` entrypoint (:func:`detect_crypto`) that resolves the
input path and maps file offsets to virtual addresses via the shared
``binary_format.parse_binary`` sections. Registration happens elsewhere —
this module only defines the tool.
"""

from __future__ import annotations

import struct
from typing import Annotated, Any

from ..core.errors import ToolError
from .base import tool
from .binary_format import parse_binary

# Cap on listed matches per algorithm (see "dedupe" note in analyze_crypto).
MAX_OCCURRENCES = 8


def _current_input_file() -> str:
    """Best-effort path of the binary loaded in the host (IDA / BN / none)."""
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


def _le32(word: int) -> bytes:
    """Little-endian encoding of a 32-bit constant."""
    return struct.pack("<I", word)


def _be32(word: int) -> bytes:
    """Big-endian encoding of a 32-bit constant."""
    return struct.pack(">I", word)


def _le64(word: int) -> bytes:
    """Little-endian encoding of a 64-bit constant."""
    return struct.pack("<Q", word)


def _be64(word: int) -> bytes:
    """Big-endian encoding of a 64-bit constant."""
    return struct.pack(">Q", word)


def _w32(word: int, label: str, value: int | None = None) -> list[dict[str, Any]]:
    """A 32-bit constant searched in both byte orders (endianness unknown).

    Both encodings carry the same ``value`` id so the analyzer counts them as
    ONE distinct constant — seeing a word in LE and BE is not corroboration.
    ``value`` lets a byte-swapped alias share its parent constant's id.
    """
    value = word if value is None else value
    return [
        {"bytes": _le32(word), "label": f"{label} (LE 0x{word:08x})", "value": value},
        {"bytes": _be32(word), "label": f"{label} (BE 0x{word:08x})", "value": value},
    ]


def _w64(word: int, label: str) -> list[dict[str, Any]]:
    """A 64-bit constant searched in both byte orders (one distinct value)."""
    return [
        {"bytes": _le64(word), "label": f"{label} (LE 0x{word:016x})", "value": word},
        {"bytes": _be64(word), "label": f"{label} (BE 0x{word:016x})", "value": word},
    ]


# ---------------------------------------------------------------------------
# Signature catalog
#
# Every entry:
#   name        algorithm label used in the report
#   category    cipher | hash | prng | encoding
#   confidence  verdict for a single matched constant ("high" = full table /
#               magic string, "medium" = single word)
#   upgrade     optional (confidence, N) — raise the verdict when N or more
#               *distinct* constants of the family are present
#   hint        analyst hint shown in the report
#   patterns    [{bytes, label}] — byte patterns to search
#
# 32/64-bit words are searched in both little- and big-endian encodings
# because the compiler's byte order is unknown ahead of time.
# ---------------------------------------------------------------------------

CRYPTO_SIGNATURES: list[dict[str, Any]] = [
    {
        "name": "MD5",
        "category": "hash",
        "confidence": "medium",
        "hint": "MD5 K-table word — look for the 64-entry T[] table loop (sine-derived constants).",
        "patterns": _w32(0xD76AA478, "MD5 K[0]"),
    },
    {
        # 0x67452301 is h0/A of MD5 *and* h0 of SHA-1 — the two share their
        # initial word, so this match cannot separate them. Labeled honestly.
        "name": "MD5/SHA-1 init",
        "category": "hash",
        "confidence": "medium",
        "hint": "Shared MD5/SHA-1 initial word h0 — check neighbouring init words to separate them.",
        "patterns": _w32(0x67452301, "MD5/SHA-1 init word"),
    },
    {
        "name": "SHA-1",
        "category": "hash",
        "confidence": "medium",
        "upgrade": ("high", 2),
        "hint": "SHA-1 round constants — a 20-round loop with 5-step rotations is the implementation.",
        "patterns": [
            *_w32(0x5A827999, "SHA-1 K1"),
            *_w32(0x6ED9EBA1, "SHA-1 K2"),
            *_w32(0x8F1BBCDC, "SHA-1 K3"),
            *_w32(0xCA62C1D6, "SHA-1 K4"),
        ],
    },
    {
        # 0x428a2f98 is also the high word of the SHA-512 K[0] quadword, so a
        # SHA-512 table also triggers this (medium) SHA-256 match — honest
        # overlap, resolved by the SHA-512 entry below.
        "name": "SHA-256",
        "category": "hash",
        "confidence": "medium",
        "upgrade": ("high", 2),
        "hint": "SHA-256 K-table / IV word — look for the 64-entry K table and message schedule.",
        "patterns": [
            *_w32(0x428A2F98, "SHA-256 K[0]"),
            *_w32(0x6A09E667, "SHA-256 IV h0"),
        ],
    },
    {
        "name": "SHA-512",
        "category": "hash",
        "confidence": "high",
        "hint": "Full 64-bit SHA-512 constants — an unambiguous SHA-512/384 table.",
        "patterns": [
            *_w64(0x428A2F98D728AE22, "SHA-512 K[0]"),
            *_w64(0x6A09E667F3BCC908, "SHA-512 IV h0"),
        ],
    },
    {
        "name": "CRC32",
        "category": "hash",
        "confidence": "medium",
        "hint": "CRC32 (reflected, zlib) polynomial word — often materialised as a 256-entry table.",
        "patterns": _w32(0xEDB88320, "CRC32 reflected polynomial"),
    },
    {
        "name": "CRC32C",
        "category": "hash",
        "confidence": "medium",
        "hint": "CRC32C (Castagnoli) polynomial — used by iSCSI/SSE4.2 code.",
        "patterns": _w32(0x82F63B78, "CRC32C reflected polynomial"),
    },
    {
        "name": "CRC-16-CCITT",
        "category": "hash",
        "confidence": "medium",
        "hint": "CRC-16-CCITT polynomial word — short (2-byte) pattern, verify by context.",
        "patterns": _w32(0x1021, "CRC-16-CCITT polynomial"),
    },
    {
        "name": "AES",
        "category": "cipher",
        "confidence": "high",
        "hint": "AES S-box tables — look for key schedule loops or AES-NI `aesenc` nearby.",
        "patterns": [
            {
                "bytes": bytes.fromhex("637c777bf26b6fc53001672bfed7ab76"),
                "label": "AES S-box (first 16 bytes)",
            },
            {
                "bytes": bytes.fromhex("52096ad53036a538bf40a39e81f3d7fb"),
                "label": "AES inverse S-box (first 16 bytes)",
            },
        ],
    },
    {
        # DES: only the IP / FP permutation tables are used verbatim across
        # implementations (FIPS 46 order). The packed S-box longs (e.g.
        # 0x3000000021966009) were deliberately NOT included — their byte
        # layout differs between implementations (SP-box vs S-box form), and
        # a wrong constant is worse than no constant. Table-less DES (OpenSSL,
        # glibc) computes IP via bit ops and will not match either entry.
        "name": "DES",
        "category": "cipher",
        "confidence": "medium",
        "upgrade": ("high", 2),
        "hint": "DES permutation tables — an old-style table-driven DES implementation.",
        "patterns": [
            {
                "bytes": bytes.fromhex("3a322a221a120a02"),  # IP: 58,50,42,34,26,18,10,2
                "label": "DES IP table start",
            },
            {
                "bytes": bytes.fromhex("2808301038184020"),  # FP: 40,8,48,16,56,24,64,32
                "label": "DES FP (IP^-1) table start",
            },
        ],
    },
    {
        # 0x9e3779b9 (golden ratio) is also popular in non-crypto hash
        # functions (Knuth multiplicative, xxHash) — medium confidence alone.
        # The byte-swapped delta 0xb979379e is listed explicitly; its LE/BE
        # encodings coincide with the original word's mirrored encodings, so
        # duplicate offsets are deduped by the analyzer AND it shares the
        # delta's value id (it is the same constant, stored byte-reversed —
        # not independent corroboration).
        # 0xc6ef3720 = delta * 32 rounds (the classic TEA "sum" after loop).
        # Two distinct family constants together (e.g. delta + sum) upgrade
        # to high — that combination is practically TEA/XTEA-only.
        "name": "TEA/XTEA",
        "category": "cipher",
        "confidence": "medium",
        "upgrade": ("high", 2),
        "hint": "TEA delta / sum constant — classic TEA/XTEA decrypt loops nearby.",
        "patterns": [
            *_w32(0x9E3779B9, "TEA delta (golden ratio)"),
            *_w32(0xB979379E, "TEA delta byte-swapped", value=0x9E3779B9),
            *_w32(0xC6EF3720, "TEA sum (delta x 32)"),
        ],
    },
    {
        "name": "ChaCha/Salsa",
        "category": "cipher",
        "confidence": "high",
        "hint": "ChaCha/Salsa sigma constant — a 20-round quarter-function stream cipher.",
        "patterns": [{"bytes": b"expand 32-byte k", "label": "ChaCha/Salsa sigma string"}],
    },
    {
        # 0x243f6a88 = first digits of pi — the Blowfish P-array seed, but
        # also reused by other pi-derived constants; medium confidence only.
        "name": "Blowfish",
        "category": "cipher",
        "confidence": "medium",
        "hint": "Blowfish P-array word (pi digits) — ambiguous, also seen in other pi-derived tables.",
        "patterns": _w32(0x243F6A88, "Blowfish P[0] / pi digits"),
    },
    {
        "name": "Base64",
        "category": "encoding",
        "confidence": "high",
        "hint": "Base64 standard alphabet — look for an encode/decode index loop using it.",
        "patterns": [
            {
                "bytes": b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
                "label": "Base64 standard alphabet",
            }
        ],
    },
    {
        "name": "Base64 (URL-safe)",
        "category": "encoding",
        "confidence": "high",
        "hint": "URL-safe Base64 alphabet ('-_' tail) — token / URL-safe encoding.",
        "patterns": [
            {
                "bytes": b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
                "label": "Base64 URL-safe alphabet",
            }
        ],
    },
    {
        "name": "Base64 (UTF-16LE)",
        "category": "encoding",
        "confidence": "high",
        "hint": "Base64 alphabet stored as UTF-16LE — common in Windows binaries.",
        "patterns": [
            {
                # Standard alphabet with a NUL byte after every character.
                "bytes": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".encode(
                    "utf-16-le"
                ),
                "label": "Base64 standard alphabet (UTF-16LE)",
            }
        ],
    },
    # Deliberately omitted:
    # - RC4: stateless, contains no structural constant (only the KSA loop).
    # - AES Rcon: single small table, weak signal next to the S-box entries.
]

_CONFIDENCE_ICONS = {"high": "[HIGH]", "medium": "[MED]"}


# ---------------------------------------------------------------------------
# Pure analyzer
# ---------------------------------------------------------------------------


def _find_all(data: bytes, needle: bytes, cap: int = MAX_OCCURRENCES) -> list[int]:
    """All offsets of *needle* in *data*, capped at *cap* occurrences."""
    offsets: list[int] = []
    start = 0
    while len(offsets) < cap:
        idx = data.find(needle, start)
        if idx < 0:
            break
        offsets.append(idx)
        start = idx + 1
    return offsets


def _map_offset(sections: list[dict[str, Any]] | None, offset: int) -> tuple[int | None, str | None]:
    """Map a file offset to (vaddr, section name) using parse_binary sections.

    When several sections contain the offset (Mach-O segments also list their
    sections), the smallest — most specific — one wins. Returns (None, None)
    for offsets outside every section (headers, overlay data).
    """
    if not sections:
        return None, None
    best: dict[str, Any] | None = None
    for sec in sections:
        start = sec.get("offset", 0)
        end = start + sec.get("size", 0)
        if start <= offset < end:
            if best is None or sec.get("size", 0) < best.get("size", 0):
                best = sec
    if best is None:
        return None, None
    return int(best.get("vaddr", 0)) + (offset - int(best.get("offset", 0))), best.get("name") or ""


def analyze_crypto(data: bytes, sections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Scan raw bytes for embedded cryptographic constants.

    Pure function — no disassembler, no filesystem. ``sections`` (as produced
    by ``binary_format.parse_binary()["sections"]``) is optional; when given,
    each match is annotated with the mapped virtual address and section name.

    Returns::

        {
          "detected":   [{name, category, confidence, constant, file_offset,
                          vaddr?, section?}]          # one entry per occurrence
          "algorithms": [{name, category, confidence, hint, constants_matched,
                          occurrences: [{file_offset, vaddr?, section?}]}]
          "summary":    one-line verdict
        }

    The same constant repeated many times (filler, relocated tables) is
    deduped and every algorithm lists at most ``MAX_OCCURRENCES`` hits.
    """
    detected: list[dict[str, Any]] = []
    algorithms: list[dict[str, Any]] = []

    for sig in CRYPTO_SIGNATURES:
        # Collect matches per signature, deduping offsets (the TEA delta and
        # its byte-swapped form encode to overlapping byte patterns).
        matches: dict[int, str] = {}
        distinct: set[Any] = set()
        for pat in sig["patterns"]:
            found = _find_all(data, pat["bytes"])
            if found:
                distinct.add(pat.get("value", pat["bytes"]))
            for off in found:
                matches.setdefault(off, pat["label"])
        if not matches:
            continue

        confidence = sig["confidence"]
        upgrade = sig.get("upgrade")
        if upgrade and len(distinct) >= upgrade[1]:
            confidence = upgrade[0]

        occurrences: list[dict[str, Any]] = []
        for off in sorted(matches)[:MAX_OCCURRENCES]:
            entry = {
                "name": sig["name"],
                "category": sig["category"],
                "confidence": confidence,
                "constant": matches[off],
                "file_offset": off,
            }
            vaddr, section = _map_offset(sections, off)
            if vaddr is not None:
                entry["vaddr"] = vaddr
                entry["section"] = section
            detected.append(entry)
            occ = {"file_offset": off, "constant": matches[off]}
            if vaddr is not None:
                occ["vaddr"] = vaddr
                occ["section"] = section
            occurrences.append(occ)

        algorithms.append(
            {
                "name": sig["name"],
                "category": sig["category"],
                "confidence": confidence,
                "hint": sig["hint"],
                "constants_matched": sorted({matches[off] for off in matches}),
                "occurrences": occurrences,
            }
        )

    if algorithms:
        summary = ", ".join(f"{a['name']} ({a['confidence']})" for a in algorithms)
        summary = f"{len(algorithms)} crypto algorithm(s) detected: {summary}"
    else:
        summary = "No cryptographic constants detected"

    return {"detected": detected, "algorithms": algorithms, "summary": summary}


# ---------------------------------------------------------------------------
# Markdown formatter
# ---------------------------------------------------------------------------


def format_crypto_report(results: dict[str, Any]) -> str:
    """Render :func:`analyze_crypto` results as a markdown report."""
    lines = ["## Crypto Detection Report\n"]

    source = results.get("source")
    if source:
        lines.append(f"**Target:** `{source}`")
    lines.append(f"**Summary:** {results.get('summary', 'No cryptographic constants detected')}\n")

    algorithms = results.get("algorithms") or []
    if not algorithms:
        lines.append("No embedded crypto constants matched. Note: table-less implementations")
        lines.append("(AES-NI intrinsics, bitsliced DES, computed CRC) carry no searchable constant.")
        return "\n".join(lines)

    for algo in algorithms:
        icon = _CONFIDENCE_ICONS.get(algo["confidence"], "[?]")
        lines.append(
            f"### {algo['name']} — {algo['category']} — {icon} {algo['confidence']}\n"
        )
        lines.append(f"**Constants matched:** {', '.join(algo['constants_matched'])}")
        lines.append(f"**Hint:** {algo['hint']}\n")
        for occ in algo["occurrences"]:
            parts = [f"file `0x{occ['file_offset']:x}`"]
            if "vaddr" in occ:
                parts.append(f"vaddr `0x{occ['vaddr']:x}`")
            if occ.get("section"):
                parts.append(f"section `{occ['section']}`")
            lines.append(f"- {' · '.join(parts)} — {occ['constant']}")
        if len(algo["occurrences"]) >= MAX_OCCURRENCES:
            lines.append(f"- … listing capped at {MAX_OCCURRENCES} occurrences")
        lines.append("")

    high = [a["name"] for a in algorithms if a["confidence"] == "high"]
    if high:
        lines.append("### Next Steps\n")
        lines.append(f"- High-confidence families: {', '.join(high)} — inspect the addresses above first.")
        lines.append("- Trace cross-references to the constant's address to find the wrapper function.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool entrypoint
# ---------------------------------------------------------------------------


def _parse_sections(data: bytes) -> list[dict[str, Any]]:
    """Sections from the shared parser; [] when the bytes are not a known format.

    Analysis must also work on raw blobs (shellcode, dumps), so any parse
    failure degrades gracefully to offset-only reporting.
    """
    try:
        return parse_binary(data).get("sections") or []
    except Exception:
        return []


@tool(
    category="analysis",
    description=(
        "Detect cryptographic algorithms by their embedded constants "
        "(AES tables, SHA/MD5 words, TEA delta, CRC tables...)"
    ),
)
def detect_crypto(path: Annotated[str, "Binary path (empty = current input file)"] = "") -> str:
    """Detect cryptographic algorithms in a binary by their embedded constants."""
    resolved = (path or "").strip() or _current_input_file()
    if not resolved:
        raise ToolError("No binary path given and no input file is open in the host")

    try:
        with open(resolved, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise ToolError(f"Cannot read binary '{resolved}': {exc}") from exc

    results = analyze_crypto(data, sections=_parse_sections(data))
    results["source"] = resolved
    return format_crypto_report(results)
