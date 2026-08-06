"""IDA Pro API compatibility helpers.

Provides wrapper functions for deprecated or missing IDA API calls
to ensure compatibility across different IDA Pro versions.
"""

from __future__ import annotations

try:
    import idaapi
    import idc
    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False


def get_disasm_text(ea: int) -> str:
    """Get disassembly text for an address, compatible with IDA Pro 9.x.

    Replaces the deprecated idc.generate_disasm_text() which was removed
    in IDA Pro 9.1.

    Args:
        ea: Effective address to get disassembly for

    Returns:
        Disassembly text string, or placeholder if unavailable
    """
    if not IDA_AVAILABLE:
        return f"loc_{ea:x}"

    try:
        # Try the modern API first
        disasm = idaapi.get_disasm(ea)
        if disasm:
            return disasm
    except Exception:
        pass

    # Fallback: build from mnemonic and operands
    try:
        mnem = idaapi.print_insn_mnem(ea)
        if not mnem:
            return f"loc_{ea:x}"

        op0 = idaapi.print_operand(ea, 0)
        op1 = idaapi.print_operand(ea, 1)

        result = mnem
        if op0:
            result += f" {op0}"
        if op1:
            result += f", {op1}"
        return result
    except Exception:
        return f"loc_{ea:x}"
