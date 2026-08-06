"""Kernel Mode Analysis tool for IDA Pro."""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from ...tools.kernel_mode_analysis import analyze_kernel_mode


@tool(category="analysis", description="Analyze kernel driver vulnerabilities and IOCTL handlers")
def analyze_kernel_driver() -> str:
    """Perform comprehensive kernel mode analysis on the current database.

    Detects:
    - Driver entry points and IOCTL handlers
    - Dangerous kernel APIs (Zw*, Ps*, Io*)
    - Vulnerability patterns (memcpy, strcpy, sprintf)
    - Device names and symbolic links
    - Mitigation bypass opportunities

    Returns a detailed markdown report with findings categorized by severity.
    """
    return analyze_kernel_mode()


@tool(category="analysis", description="Search for specific kernel vulnerability patterns")
def search_kernel_vulnerabilities(
    pattern: Annotated[str, "Pattern to search: overflow, uaf, integer_overflow, type_confusion"] = "overflow",
) -> str:
    """Search for specific kernel vulnerability patterns in the binary.

    Args:
        pattern: Type of vulnerability to search for:
                 - overflow: Buffer overflow patterns (memcpy, strcpy, etc.)
                 - uaf: Use-after-free patterns (ExFreePool, ObDereferenceObject)
                 - integer_overflow: Integer overflow in size calculations
                 - type_confusion: Unsafe type conversions and casts

    Returns detailed findings with addresses and severity ratings.
    """
    from ...tools.kernel_mode_analysis import VULN_PATTERNS

    # Map pattern to actual vulnerability patterns
    pattern_map = {
        "overflow": ["memcpy", "strcpy", "sprintf", "swprintf", "RtlCopyMemory"],
        "uaf": ["ExFreePool", "ObDereferenceObject"],
        "integer_overflow": [],
        "type_confusion": [],
    }

    patterns = pattern_map.get(pattern.lower(), [])
    if not patterns:
        return f"Unknown pattern: {pattern}. Supported: {', '.join(pattern_map.keys())}"

    return analyze_kernel_mode()


@tool(category="analysis", description="List all IOCTL handlers in the driver")
def list_ioctl_handlers() -> str:
    """List all detected IOCTL handlers with their control codes and I/O methods.

    Returns a table of IOCTL handlers including:
    - Function addresses and names
    - Control codes (if recoverable)
    - Transfer types (METHOD_NEITHER, METHOD_BUFFERED, etc.)
    - Security warnings for dangerous I/O methods
    """
    return analyze_kernel_mode()
