"""Checksec — binary mitigations report from raw file bytes.

Pure-Python mitigation detection for ELF, PE and Mach-O (including fat
binaries) built on :mod:`spectra.tools.binary_format`. No external command
and no pip dependency: header bits are parsed straight from the file.

The engine (:func:`analyze_security`) is pure and unit-testable; the
:func:`checksec` tool wraps it with a markdown formatter for the agent.
"""

from __future__ import annotations

from typing import Annotated

from .base import tool
from .binary_format import parse_binary

# Entropy of a section above this is treated as "possibly packed/encrypted"
# in the notes (the full entropy analysis lives in spectra/tools/entropy.py).


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


def _elf_checks(info: dict, checks: list[dict]) -> None:
    def add(name: str, ok: bool | None, status: str, note: str = "") -> None:
        checks.append({"name": name, "ok": ok, "status": status, "note": note})

    add("PIE", info["pie"], "yes" if info["pie"] else "no",
        "ET_DYN (position independent)" if info["pie"] else "ET_EXEC (fixed load address)")
    add("NX", info["nx"], "yes" if info["nx"] else "no",
        "non-executable stack" if info["nx"] else "executable stack (PT_GNU_STACK +X)")
    relro = info.get("relro")
    if relro is None:
        add("RELRO", None, "n/a")
    else:
        add("RELRO", relro == "full", relro,
            "GNU_RELRO + BIND_NOW" if relro == "full"
            else "GNU_RELRO without BIND_NOW — GOT writable at runtime" if relro == "partial"
            else "no RELRO — GOT overwrite viable")

    names = {s["name"] for s in info.get("symbols", [])}
    fortified = sorted(n for n in names if n.startswith("__") and n.endswith("_chk"))
    if info["canary"]:
        add("Stack canary", True, "yes", "__stack_chk_fail imported")
    else:
        add("Stack canary", False, "no", "no stack cookie — linear overflows")
    if fortified:
        add("FORTIFY", True, f"{len(fortified)} funcs",
            ", ".join(fortified[:10]) + ("…" if len(fortified) > 10 else ""))

    interp = info.get("interpreter", "")
    add("Type", None, "static" if info.get("static") else "dynamic", interp)


def _pe_checks(info: dict, checks: list[dict]) -> None:
    def add(name: str, ok: bool | None, status: str, note: str = "") -> None:
        checks.append({"name": name, "ok": ok, "status": status, "note": note})

    add("ASLR (DYNAMIC_BASE)", info["pie"], "yes" if info["pie"] else "no",
        "relocatable image" if info["pie"] else "fixed ImageBase")
    add("DEP (NX_COMPAT)", info["nx"], "yes" if info["nx"] else "no",
        "" if info["nx"] else "no data-execution-prevention flag")
    if info.get("high_entropy_va"):
        add("High-entropy ASLR", True, "yes", "64-bit ASLR entropy")
    add("CFG (GUARD_CF)", info.get("cfg"), "yes" if info.get("cfg") else "no",
        "indirect-call guarded" if info.get("cfg") else "no Control Flow Guard")
    if info.get("no_seh"):
        add("SEH", None, "disabled", "NO_SEH flag set")
    add("Stack cookie (/GS)", info["canary"], "yes" if info["canary"] else "no",
        "load-config present" if info["canary"] else "no load config")
    add("Authenticode", info.get("signed"), "signed" if info.get("signed") else "unsigned",
        "" if info.get("signed") else "patchable without breaking a signature")
    if info.get("has_tls_callbacks"):
        add("TLS callbacks", None, "present", "inspect for anti-debug tricks")


def _macho_checks(info: dict, checks: list[dict]) -> None:
    def add(name: str, ok: bool | None, status: str, note: str = "") -> None:
        checks.append({"name": name, "ok": ok, "status": status, "note": note})

    add("PIE", info["pie"], "yes" if info["pie"] else "no",
        "MH_PIE" if info["pie"] else "fixed load addresses")
    nx = info.get("nx")
    add("NX", nx, "yes" if nx else ("no" if nx is False else "n/a"),
        "__TEXT non-writable" if nx else "__TEXT writable")
    wx = [s["name"] for s in info.get("sections", []) if s.get("exec") and s.get("write")]
    if wx:
        add("WX segments", False, "present", ", ".join(wx[:5]))
    add("Stack canary", info["canary"], "yes" if info["canary"] else "no",
        "___stack_chk_guard" if info["canary"] else "")
    add("Code signature", info.get("signed"), "signed" if info.get("signed") else "unsigned",
        "" if info.get("signed") else "patches do not require re-signing")
    if info.get("encrypted"):
        add("FairPlay encryption", None, "encrypted", "LC_ENCRYPTION_INFO cryptid set — dump from memory")


def analyze_security(data: bytes) -> dict:
    """Pure engine: parse *data* and derive the mitigation report dict."""
    info = parse_binary(data)
    slices: list[dict] = []
    base = info
    if info["format"] == "Fat Mach-O":
        base = info["fat_slices"][0]
        for sub in info["fat_slices"]:
            checks: list[dict] = []
            _macho_checks(sub, checks)
            slices.append({"arch": sub["arch"], "checks": checks})

    checks = []
    if base["format"] == "ELF":
        _elf_checks(base, checks)
    elif base["format"] == "PE":
        _pe_checks(base, checks)
    else:
        _macho_checks(base, checks)

    info_out = {k: base[k] for k in ("format", "arch", "bits", "endian", "file_type")}
    if info["format"] == "Fat Mach-O":
        info_out["format"] = "Fat Mach-O"

    return {
        "info": info_out,
        "checks": checks,
        "fat_slices": slices,
        "symbols": len(base.get("symbols", [])),
    }


def _impact_notes(checks: list[dict]) -> list[str]:
    by_name = {c["name"]: c for c in checks}
    notes: list[str] = []
    pie = by_name.get("PIE") or by_name.get("ASLR (DYNAMIC_BASE)")
    if pie is not None and pie["ok"] is False:
        notes.append("No PIE/ASLR — code addresses are fixed: ROP chains can hardcode gadgets")
    nx = by_name.get("NX") or by_name.get("DEP (NX_COMPAT)")
    if nx is not None and nx["ok"] is False:
        notes.append("No NX/DEP — injected shellcode on the stack can execute")
    canary = by_name.get("Stack canary") or by_name.get("Stack cookie (/GS)")
    if canary is not None and canary["ok"] is False:
        notes.append("No stack canary — straightforward linear stack overflows")
    relro = by_name.get("RELRO")
    if relro is not None and relro["ok"] is False:
        notes.append(f"RELRO {relro['status']} — GOT overwrite is a viable hijack primitive")
    cfg = by_name.get("CFG (GUARD_CF)")
    if cfg is not None and cfg["ok"] is False:
        notes.append("No CFG — indirect calls/jumps can be redirected freely")
    return notes


def _format_checks(checks: list[dict]) -> str:
    lines = ["| Mitigation | Status | Note |", "|---|---|---|"]
    for c in checks:
        mark = "✅" if c["ok"] else ("❌" if c["ok"] is False else "➖")
        lines.append(f"| {mark} {c['name']} | {c['status']} | {c['note']} |")
    return "\n".join(lines)


def format_checksec_report(analysis: dict, path: str = "") -> str:
    info = analysis["info"]
    title = path or "current binary"
    out = [f"## Checksec — {title}", ""]
    out.append(
        f"**Format:** {info['format']} · {info['arch']} · {info['bits']}-bit · "
        f"{info['endian']}-endian · {info['file_type']}"
    )
    out.append("")
    out.append(_format_checks(analysis["checks"]))

    for sub in analysis.get("fat_slices", []):
        out.append("")
        out.append(f"### Fat slice — {sub['arch']}")
        out.append(_format_checks(sub["checks"]))

    notes = _impact_notes(analysis["checks"])
    if notes:
        out.append("")
        out.append("### Exploitation impact")
        out.extend(f"- {n}" for n in notes)
    return "\n".join(out)


@tool(category="analysis", description="Check binary mitigations (PIE, NX, RELRO, canary, CFG, signature) from the file headers")
def checksec(
    path: Annotated[str, "Binary path (empty = current input file)"] = "",
) -> str:
    """Report exploit mitigations compiled into the binary.

    Parses ELF / PE / Mach-O (fat included) headers directly in Python —
    no external checksec tool needed. Covers PIE/ASLR, NX/DEP, RELRO,
    stack canaries, FORTIFY, CFG, Authenticode/code-signature, FairPlay
    encryption and adds exploitation-impact notes for anything missing.
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
        analysis = analyze_security(data)
    except ValueError as e:
        return f"Error: {e}"
    return format_checksec_report(analysis, target)
