"""Novel Vulnerability Hunter tools for Binary Ninja.

This module provides Binary Ninja-specific wrappers for the novel vulnerability hunter
functionality, allowing it to be used as an agent tool in the Spectra Binary Ninja plugin.
"""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from ...tools.novel_hunter import (
    NovelVulnerabilityHunterCore,
    VulnerabilityFinding,
    analyze_novel_vulnerabilities,
    check_novelty_indicators,
    generate_exploit_template,
)


@tool(category="security", description="Analyze decompiled code for novel vulnerabilities")
def analyze_decompiled_novel_vulns(
    address: Annotated[int, "Function address to decompile and analyze"] = 0,
    focus_area: Annotated[str, "Specific area to focus on (e.g., 'custom allocator', 'SIMD', 'JIT')"] = "general",
) -> str:
    """Analyze decompiled code for novel vulnerabilities using advanced detection.

    This function:
    1. Decompiles the function at the given address
    2. Analyzes the pseudocode for novel vulnerability patterns
    3. Filters out known CVE patterns
    4. Identifies previously undocumented vulnerabilities

    Focus Areas:
    - custom allocator: Custom memory pool/arena implementations
    - SIMD: Vector operation overflow patterns
    - JIT: Runtime compilation vulnerabilities
    - general: Comprehensive analysis

    Returns:
        Comprehensive vulnerability report with novelty confidence scores.
    """
    try:
        import binaryninja
    except ImportError:
        return "Error: Binary Ninja API not available"

    bv = binaryninja.get_current_bv()
    if not bv:
        return "Error: No binary loaded"

    # Get current function if address is 0
    if address == 0:
        func = bv.get_functions_at(bv.offset)[0] if bv.offset and bv.get_functions_at(bv.offset) else None
        if not func:
            return "Error: No function at current location"
        address = func.start

    func = bv.get_function_at(address)
    if not func:
        return f"Error: No function found at address 0x{address:X}"

    func_name = func.name if func.name else f"sub_{address:X}"

    # Get HLIL for analysis
    pseudocode = ""
    if func.hlil:
        for instr in func.hlil:
            pseudocode += str(instr) + "\n"

    if not pseudocode:
        return f"Error: Could not decompile function at 0x{address:X}"

    # Use the shared analyzer
    result = analyze_novel_vulnerabilities(code=pseudocode, focus_area=focus_area)

    # Add Binary Ninja-specific header
    header = f"""## Novel Vulnerability Analysis for Binary Ninja Function

**Function Address:** 0x{address:X}
**Function Name:** {func_name}
**Decompiled Lines:** {len(pseudocode.splitlines())}

---

"""
    return header + result


@tool(category="security", description="Check current function for novelty indicators")
def check_function_novelty(
    address: Annotated[int, "Function address to check"] = 0,
) -> str:
    """Analyze the current function for indicators of novel vulnerability patterns.

    Scans for:
    - Recent code additions (git timestamps, comments)
    - Custom allocator implementations
    - Compiler optimization issues
    - SIMD/vector processing
    - JIT compilation patterns
    - Previously undocumented patterns

    Returns a novelty score and detailed analysis of indicators found.
    """
    try:
        import binaryninja
    except ImportError:
        return "Error: Binary Ninja API not available"

    bv = binaryninja.get_current_bv()
    if not bv:
        return "Error: No binary loaded"

    # Get current function if address is 0
    if address == 0:
        func = bv.get_functions_at(bv.offset)[0] if bv.offset and bv.get_functions_at(bv.offset) else None
        if not func:
            return "Error: No function at current location"
        address = func.start

    func = bv.get_function_at(address)
    if not func:
        return f"Error: No function found at address 0x{address:X}"

    func_name = func.name if func.name else f"sub_{address:X}"

    # Get disassembly text
    disasm_text = ""
    for block in func.basic_blocks:
        for instr in block.disassembly_text:
            disasm_text += instr + "\n"

    # Get HLIL if available
    pseudocode = ""
    if func.hlil:
        for instr in func.hlil:
            pseudocode += str(instr) + "\n"

    combined_text = f"# Disassembly\n{disasm_text}\n\n# HLIL\n{pseudocode}" if pseudocode else disasm_text

    # Use the shared checker
    result = check_novelty_indicators(text=combined_text)

    # Add Binary Ninja-specific header
    header = f"""## Novelty Analysis for Binary Ninja Function

**Function Address:** 0x{address:X}
**Function Name:** {func_name}
**Start:** 0x{func.start:X}
**End:** 0x{func.end:X}
**Size:** {func.end - func.start} bytes

---

"""
    return header + result


@tool(category="exploit", description="Generate exploit for vulnerability at current address")
def generate_exploit_for_address(
    vuln_type: Annotated[
        str, "Type of vulnerability (stack_overflow, heap_overflow, use_after_free, command_injection, etc.)"
    ],
    address: Annotated[int, "Address of the vulnerability"] = 0,
    description: Annotated[str, "Description of the vulnerability"] = "",
) -> str:
    """Generate a weaponized exploit template for a vulnerability at a specific address.

    Creates a Python exploit with:
    - Target address configuration
    - Vulnerability-specific payload generation
    - Network/web exploitation support
    - ROP gadget placeholders (for memory corruption)
    - Proof-of-concept code

    Args:
        vuln_type: Type of vulnerability to exploit
        address: Address where vulnerability is located
        description: Additional context about the vulnerability

    Returns:
        Complete, ready-to-use Python exploit code.
    """
    try:
        import binaryninja
    except ImportError:
        return "Error: Binary Ninja API not available"

    bv = binaryninja.get_current_bv()
    if not bv:
        return "Error: No binary loaded"

    # Get current function if address is 0
    if address == 0:
        func = bv.get_functions_at(bv.offset)[0] if bv.offset and bv.get_functions_at(bv.offset) else None
        if func:
            address = func.start

    func_name = ""
    if address:
        func = bv.get_function_at(address)
        if func:
            func_name = func.name if func.name else f"sub_{address:X}"

    location = f"0x{address:X} ({func_name})" if address else "current location"

    if not description:
        description = (
            f"Vulnerability in function {func_name} at address 0x{address:X}"
            if address
            else "Vulnerability at current location"
        )

    # Use the shared exploit generator
    return generate_exploit_template(
        vuln_type=vuln_type,
        location=location,
        description=description,
    )


@tool(category="security", description="Scan binary for custom allocator implementations")
def find_custom_allocators() -> str:
    """Scan the binary for custom memory allocator implementations.

    Custom allocators are a common source of novel vulnerabilities:
    - Pool allocators without bounds checking
    - Arena allocators with overflow issues
    - Region-based allocators with use-after-free
    - Bump allocators with wraparound bugs

    Returns:
        List of potential custom allocator functions with analysis.
    """
    try:
        import binaryninja
    except ImportError:
        return "Error: Binary Ninja API not available"

    bv = binaryninja.get_current_bv()
    if not bv:
        return "Error: No binary loaded"

    allocator_patterns = [
        "alloc",
        "malloc",
        "calloc",
        "realloc",
        "free",
        "pool",
        "arena",
        "region",
        "bump",
        "cache",
        "mem_",
        "memory",
        "buffer",
        "heap",
        "stack",
    ]

    findings = []

    # Scan all functions
    for func in bv.functions:
        func_name = func.name if func.name else ""

        # Check if function name suggests allocator
        if any(pattern in func_name.lower() for pattern in allocator_patterns):
            findings.append(
                {
                    "address": f"0x{func.start:X}",
                    "name": func_name,
                    "size": func.end - func.start,
                    "type": "allocator_candidate",
                }
            )

    if not findings:
        return "No custom allocator candidates found. The binary likely uses standard library allocators."

    # Build report
    report = f"""## Custom Allocator Candidates

**Found:** {len(findings)} potential custom allocator functions

| Address | Name | Size (bytes) |
|---------|------|--------------|
"""
    for f in findings[:50]:
        report += f"| {f['address']} | {f['name']} | {f['size']} |\n"

    if len(findings) > 50:
        report += f"| ... | ... and {len(findings) - 50} more | ... |\n"

    report += (
        "\n**Recommendation:** Use `analyze_decompiled_novel_vulns` on each candidate to identify vulnerabilities."
    )

    return report


@tool(category="security", description="Deep analysis of novel vulnerability patterns")
def deep_novel_analysis(
    address: Annotated[int, "Function address to analyze deeply"] = 0,
) -> str:
    """Perform deep, iterative analysis on a function to find novel vulnerabilities.

    This function:
    1. Decompiles and analyzes the function
    2. Checks for known patterns (excludes)
    3. Analyzes control flow for novel patterns
    4. Checks for compiler-induced bugs
    5. Assesses exploitability with multiple iterations
    6. Generates exploit if exploitable

    Returns comprehensive analysis with exploit code if applicable.
    """
    try:
        import binaryninja
    except ImportError:
        return "Error: Binary Ninja API not available"

    bv = binaryninja.get_current_bv()
    if not bv:
        return "Error: No binary loaded"

    # Get current function if address is 0
    if address == 0:
        func = bv.get_functions_at(bv.offset)[0] if bv.offset and bv.get_functions_at(bv.offset) else None
        if not func:
            return "Error: No function at current location"
        address = func.start

    func = bv.get_function_at(address)
    if not func:
        return f"Error: No function found at address 0x{address:X}"

    func_name = func.name if func.name else f"sub_{address:X}"

    # Get HLIL for analysis
    pseudocode = ""
    if func.hlil:
        for instr in func.hlil:
            pseudocode += str(instr) + "\n"

    if not pseudocode:
        return f"Error: Could not decompile function at 0x{address:X}"

    # Use the shared analyzer
    analysis_result = analyze_novel_vulnerabilities(code=pseudocode, focus_area="deep analysis")

    # Add control flow information
    flow_info = f"\n## Control Flow Analysis\n\n**Basic Blocks:** {len(func.basic_blocks)}\n"
    flow_info += f"**Function Size:** {func.end - func.start} bytes\n"

    # Count instructions
    insn_count = sum(len(list(block.disassembly_text)) for block in func.basic_blocks)
    flow_info += f"**Instructions:** {insn_count}\n"

    return f"""## Deep Novel Vulnerability Analysis

**Function:** {func_name} (0x{address:X})
{flow_info}

---

{analysis_result}
"""
