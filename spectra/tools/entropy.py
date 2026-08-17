"""Entropy & packer analysis over raw file bytes.

Shannon entropy per section, whole-file entropy, overlay measurement and
known-packer fingerprints — all pure Python on top of
:mod:`spectra.tools.binary_format`. Answers the triage question
"is this packed / encrypted, and where?" without running any external tool.
"""

from __future__ import annotations

import math
from typing import Annotated

from .base import tool
from .binary_format import parse_binary

HIGH_ENTROPY = 7.2          # bits/byte above which data looks packed/encrypted
MIN_SECTION_BYTES = 64      # smaller regions carry no meaningful entropy
PACKER_SCAN_BYTES = 2 * 1024 * 1024  # magic scan budget

# Section-name fragments → packer family (checked case-insensitively).
_PACKER_SECTION_NAMES = {
    "upx": "UPX",
    "themida": "Themida",
    "boom": "Themedia/Boom",
    "vmp": "VMProtect",
    "aspack": "ASPack",
    "adata": "ASPack",
    "mpress": "MPRESS",
    "petite": "Petite",
    "nsp1": "NsPack",
    "nsp2": "NsPack",
    "pebundle": "PEBundle",
    "svkp": "SVKP",
    "rmnet": "Red Mist",
}

_PACKER_MAGICS = {
    b"UPX!": "UPX",
    b"UPX0": "UPX",
    b"UPX1": "UPX",
}


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


def shannon_entropy(data: bytes) -> float:
    """Shannon entropy of *data* in bits per byte (0.0-8.0)."""
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    total = len(data)
    ent = 0.0
    for c in counts:
        if c:
            p = c / total
            ent -= p * math.log2(p)
    return ent


def section_report(name: str, blob: bytes) -> dict:
    """Entropy verdict for one section body (pure, unit-testable)."""
    entropy = shannon_entropy(blob)
    return {
        "name": name,
        "size": len(blob),
        "entropy": round(entropy, 3),
        "high": entropy >= HIGH_ENTROPY,
    }


def detect_packer(info: dict, data: bytes) -> list[str]:
    """Known-packer fingerprints from section names and byte magics."""
    found: set[str] = set()
    for sec in info.get("sections", []):
        low = sec.get("name", "").lower()
        for frag, family in _PACKER_SECTION_NAMES.items():
            if frag in low:
                found.add(family)
    head = data[:PACKER_SCAN_BYTES]
    for magic, family in _PACKER_MAGICS.items():
        if magic in head:
            found.add(family)
    return sorted(found)


def analyze_entropy(data: bytes) -> dict:
    """Pure engine: whole-file + per-section entropy and packer verdict."""
    info = parse_binary(data)
    sections = []
    for sec in info.get("sections", []):
        off, size = sec.get("offset", 0), sec.get("size", 0)
        if size < MIN_SECTION_BYTES or off + size > len(data):
            continue
        sections.append({**section_report(sec["name"], data[off : off + size]),
                         "exec": bool(sec.get("exec")), "write": bool(sec.get("write"))})

    packers = detect_packer(info, data)
    high_exec = [s for s in sections if s["high"] and s["exec"]]
    high_any = [s for s in sections if s["high"]]

    overlay = info.get("overlay", {"offset": 0, "size": 0})
    overlay_entropy = 0.0
    if overlay["size"] >= MIN_SECTION_BYTES:
        overlay_entropy = shannon_entropy(data[overlay["offset"] :])

    if packers:
        verdict = "packed"
    elif high_exec:
        verdict = "likely packed/encrypted code"
    elif high_any:
        verdict = "embedded encrypted/compressed region"
    else:
        verdict = "normal"

    return {
        "info": {k: info[k] for k in ("format", "arch", "bits", "file_type")},
        "file_entropy": round(shannon_entropy(data), 3),
        "file_size": len(data),
        "sections": sections,
        "packers": packers,
        "verdict": verdict,
        "overlay": {"size": overlay["size"], "entropy": round(overlay_entropy, 3)},
    }


def format_entropy_report(analysis: dict, path: str = "") -> str:
    title = path or "current binary"
    out = [
        f"## Entropy analysis — {title}",
        "",
        f"**Verdict:** {analysis['verdict']}"
        + (f" ({', '.join(analysis['packers'])})" if analysis["packers"] else ""),
        "",
        f"Whole file: {analysis['file_entropy']:.3f} bits/byte · "
        f"{analysis['file_size']:,} bytes",
        "",
        "| Section | Size | Entropy | Flags |",
        "|---|---|---|---|",
    ]
    for s in analysis["sections"]:
        flags = []
        if s["exec"]:
            flags.append("exec")
        if s["write"]:
            flags.append("write")
        if s["high"]:
            flags.append("**HIGH**")
        out.append(
            f"| {s['name']} | {s['size']:,} | {s['entropy']:.3f} | {', '.join(flags) or '—'} |"
        )

    ov = analysis["overlay"]
    if ov["size"]:
        out.append("")
        note = " — inspect overlay!" if ov["size"] > 4096 or ov["entropy"] >= HIGH_ENTROPY else ""
        out.append(f"Overlay: {ov['size']:,} bytes, entropy {ov['entropy']:.3f}{note}")

    if analysis["verdict"] != "normal":
        out.append("")
        out.append(
            "High-entropy code usually means a packer or embedded crypto/compressed payload — "
            "look for an unpacking stub at the entry point, or dump after the unpack loop."
        )
    return "\n".join(out)


@tool(category="analysis", description="Per-section entropy + packer detection (is this binary packed?)")
def entropy_report(
    path: Annotated[str, "Binary path (empty = current input file)"] = "",
) -> str:
    """Shannon entropy per section plus known-packer fingerprints.

    Flags packed/encrypted code sections (entropy ≥ 7.2 bits/byte), detects
    UPX/Themida/VMProtect/ASPack-style section names, and measures overlay
    data. Pure Python — no external tool required.
    """
    target = path or _current_input_file()
    if not target:
        return "Error: no path given and no binary loaded in the host."
    try:
        with open(target, "rb") as fh:
            data = fh.read()
    except OSError as e:
        return f"Error: cannot read '{target}': {e}"
    try:
        analysis = analyze_entropy(data)
    except ValueError as e:
        return f"Error: {e}"
    return format_entropy_report(analysis, target)
