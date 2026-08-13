"""Novel Vulnerability Hunter tools for IDA Pro.

This module provides IDA Pro-specific wrappers for the novel vulnerability hunter
functionality, allowing it to be used as an agent tool in the Spectra IDA plugin.
"""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from ...tools.novel_hunter import (
    analyze_novel_vulnerabilities,
    check_novelty_indicators,
    generate_exploit_template,
    NovelVulnerabilityHunterCore,
    VulnerabilityFinding,
)


@tool(category="security", description="Analyze decompiled code for novel vulnerabilities")
def analyze_decompiled_novel_vulns(
    ea: Annotated[int, "Function address to decompile and analyze"] = 0,
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
        import ida_hexrays
    except ImportError:
        return "Error: Hex-Rays decompiler not available. Please ensure IDA Pro with Hex-Rays is installed."

    if ea == 0:
        ea = ida_hexrays.get_screen_ea()

    # Attempt to decompile the function
    try:
        cfunc = ida_hexrays.decompile(ea)
        if cfunc is None:
            return f"Error: Could not decompile function at 0x{ea:X}"

        # Get pseudocode as text
        pseudocode = str(cfunc)

        # Use the shared analyzer
        result = analyze_novel_vulnerabilities(code=pseudocode, focus_area=focus_area)

        # Add IDA-specific header
        header = f"""## Novel Vulnerability Analysis for IDA Function

**Function Address:** 0x{ea:X}
**Function Name:** {ida_hexrays.get_func_name(ea)}
**Decompiled Lines:** {len(pseudocode.splitlines())}

---

"""
        return header + result

    except Exception as e:
        return f"Error during analysis: {e}"


@tool(category="security", description="Check current function for novelty indicators")
def check_function_novelty(
    ea: Annotated[int, "Function address to check"] = 0,
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
        import ida_hexrays
        import ida_bytes
        import ida_funcs
        import ida_ua
    except ImportError:
        return "Error: IDA API not available"

    if ea == 0:
        ea = ida_hexrays.get_screen_ea()

    # Collect function information
    func_name = ida_hexrays.get_func_name(ea)
    func = ida_funcs.get_func(ea)

    if func is None:
        return f"Error: No function found at address 0x{ea:X}"

    # Get disassembly
    text_parts = []
    for head in ida_heads(func.start_ea, func.end_ea):
        disasm = ida_ua.generate_disasm_line(head, 0)
        text_parts.append(disasm)

    disasm_text = "\n".join(text_parts)

    # Try to get pseudocode if available
    try:
        cfunc = ida_hexrays.decompile(ea)
        if cfunc:
            pseudocode = str(cfunc)
            combined_text = f"# Disassembly\n{disasm_text}\n\n# Pseudocode\n{pseudocode}"
        else:
            combined_text = disasm_text
    except:
        combined_text = disasm_text

    # Use the shared checker
    result = check_novelty_indicators(text=combined_text)

    # Add IDA-specific header
    header = f"""## Novelty Analysis for IDA Function

**Function Address:** 0x{ea:X}
**Function Name:** {func_name}
**Start:** 0x{func.start_ea:X}
**End:** 0x{func.end_ea:X}
**Size:** {func.end_ea - func.start_ea} bytes

---

"""
    return header + result


@tool(category="exploit", description="Generate exploit for vulnerability at current address")
def generate_exploit_for_address(
    vuln_type: Annotated[str, "Type of vulnerability (stack_overflow, heap_overflow, use_after_free, command_injection, etc.)"],
    ea: Annotated[int, "Address of the vulnerability"] = 0,
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
        ea: Address where vulnerability is located
        description: Additional context about the vulnerability

    Returns:
        Complete, ready-to-use Python exploit code.
    """
    try:
        import ida_hexrays
        import ida_name
        import ida_funcs
    except ImportError:
        return "Error: IDA API not available"

    if ea == 0:
        ea = ida_hexrays.get_screen_ea()

    func_name = ida_hexrays.get_func_name(ea)
    location = f"0x{ea:X} ({func_name})"

    if not description:
        description = f"Vulnerability in function {func_name} at address 0x{ea:X}"

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
        import ida_funcs
        import ida_name
        import ida_bytes
        import ida_ua
    except ImportError:
        return "Error: IDA API not available"

    allocator_patterns = [
        "alloc", "malloc", "calloc", "realloc", "free",
        "pool", "arena", "region", "bump", "cache",
        "mem_", "memory", "buffer", "heap", "stack"
    ]

    findings = []

    # Scan all functions
    for ea in ida_funcs.Functions():
        func_name = ida_name.get_name(ea)

        # Check if function name suggests allocator
        if any(pattern in func_name.lower() for pattern in allocator_patterns):
            func = ida_funcs.get_func(ea)
            if func:
                findings.append({
                    "address": f"0x{ea:X}",
                    "name": func_name,
                    "size": func.end_ea - func.start_ea,
                    "type": "allocator_candidate"
                })

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

    report += "\n**Recommendation:** Use `analyze_decompiled_novel_vulns` on each candidate to identify vulnerabilities."

    return report


@tool(category="security", description="Deep analysis of novel vulnerability patterns")
def deep_novel_analysis(
    ea: Annotated[int, "Function address to analyze deeply"] = 0,
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
        import ida_hexrays
        import ida_funcs
        import ida_ua
        import ida_gdl
    except ImportError:
        return "Error: IDA API not available"

    if ea == 0:
        ea = ida_hexrays.get_screen_ea()

    func_name = ida_hexrays.get_func_name(ea)

    # Get decompiled code
    try:
        cfunc = ida_hexrays.decompile(ea)
        if cfunc is None:
            return f"Error: Could not decompile function at 0x{ea:X}"
        pseudocode = str(cfunc)
    except Exception as e:
        return f"Error decompiling: {e}"

    # Use the shared analyzer
    analysis_result = analyze_novel_vulnerabilities(
        code=pseudocode,
        focus_area="deep analysis"
    )

    # Add control flow information
    try:
        func = ida_funcs.get_func(ea)
        flow_graph = ida_gdl.FlowChart(func)

        flow_info = f"\n## Control Flow Analysis\n\n**Basic Blocks:** {len(list(flow_graph))}\n"
        flow_info += f"**Function Size:** {func.end_ea - func.start_ea} bytes\n"

        # Count instructions
        insn_count = 0
        for head in ida_heads(func.start_ea, func.end_ea):
            insn_count += 1
        flow_info += f"**Instructions:** {insn_count}\n"

        return f"""## Deep Novel Vulnerability Analysis

**Function:** {func_name} (0x{ea:X})
{flow_info}

---

{analysis_result}
"""
    except:
        return f"""## Deep Novel Vulnerability Analysis

**Function:** {func_name} (0x{ea:X})

---

{analysis_result}
"""


# Helper function for iterating over instructions (similar to idautils.Heads)
def ida_heads(start_ea, end_ea):
    """Iterator over instruction addresses in range."""
    ea = start_ea
    while ea < end_ea:
        yield ea
        ea = ida_ua.next_head(ea, end_ea)
