"""VM/Obfuscation Detection tool for Binary Ninja."""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from ...tools.vm_obfuscation_detection import (
    detect_vm_obfuscation,
    get_deobfuscation_suggestions,
)
from .compat import require_bv


@tool(category="analysis", description="Detect virtual machines and code obfuscation")
def detect_obfuscation() -> str:
    """Scan the binary for virtualization and obfuscation patterns.

    Detects:
    - Known protectors (VMProtect, Themida, UPX, etc.)
    - Control flow flattening (dispatcher patterns)
    - Opaque predicates (always-true/false conditions)
    - Junk code insertion
    - Function complexity anomalies

    Returns a detailed report with detected protectors,
    suspicious functions, and deobfuscation recommendations.
    """
    bv = require_bv()
    return detect_vm_obfuscation(binary_view=bv)


@tool(category="analysis", description="Get deobfuscation suggestions for detected protectors")
def get_deobfuscation_advice(
    protector: Annotated[str, "Protector name (vmprotect, themida, upx, tigress)"] = "auto",
) -> str:
    """Get specific deobfuscation advice for a detected protector.

    Args:
        protector: The name of the protector to get advice for.
                   Use "auto" to auto-detect and provide advice for all detected protectors.

    Returns:
        Tool recommendations, methods, and difficulty ratings for unpacking/devirtualization.
    """
    bv = require_bv()

    if protector == "auto":
        from ...tools.vm_obfuscation_detection import _detect_vm_protector_binja

        detection = _detect_vm_protector_binja(bv)
        detected = detection.get("detectors", [])

        if not detected:
            return "No known protectors detected. Binary appears to be unobfuscated."

        suggestions = get_deobfuscation_suggestions(detected)
        return f"Detected protectors: {', '.join(detected)}\n\nDeobfuscation suggestions:\n{suggestions}"

    suggestions = get_deobfuscation_suggestions([protector])
    return f"Deobfuscation suggestions for {protector}:\n{suggestions}"


@tool(category="analysis", description="Analyze function complexity for obfuscation indicators")
def analyze_obfuscated_functions(
    threshold: Annotated[int, "Minimum instruction count to consider (default: 200)"] = 200,
) -> str:
    """Identify potentially obfuscated functions based on complexity metrics.

    Args:
        threshold: Minimum instruction count for a function to be flagged.

    Returns a list of functions that exceed the threshold with their
    complexity metrics (instruction count, basic blocks, cyclomatic complexity).
    """
    from ...tools.vm_obfuscation_detection import _analyze_function_complexity_binja

    bv = require_bv()
    results = _analyze_function_complexity_binja(bv)

    if not results.get("complex_functions"):
        return f"No functions found with instruction count > {threshold}"

    report = f"## Potentially Obfuscated Functions (threshold: {threshold} instructions)\n\n"

    for func in results["complex_functions"][:15]:
        report += f"### {func['name']} at {func['address']}\n"
        report += f"- Instructions: {func['instr_count']}\n"
        report += f"- Basic blocks: {func['block_count']}\n"
        report += "- Issues:\n"
        for issue in func.get("issues", []):
            report += f"  - {issue}\n"
        report += "\n"

    if len(results["complex_functions"]) > 15:
        report += f"_... and {len(results['complex_functions']) - 15} more_\n"

    return report
