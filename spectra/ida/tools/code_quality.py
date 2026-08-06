"""Code Quality Metrics tool for IDA Pro."""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from ...tools.code_quality import analyze_code_quality


@tool(category="analysis", description="Analyze code quality metrics and security score")
def analyze_code_metrics() -> str:
    """Perform comprehensive code quality analysis on the binary.

    Analyzes:
    - Cyclomatic complexity per function
    - Function size distribution
    - Code smells (god functions, magic numbers, etc.)
    - Security issues (hardcoded credentials, weak crypto, unsafe functions)
    - Security score with grade (A-F)

    Returns:
        Detailed report with:
        - Most complex functions
        - Largest functions
        - Security issues by severity
        - Overall security grade
        - Refactoring recommendations
    """
    return analyze_code_quality()


@tool(category="analysis", description="Get security score for a specific function")
def get_function_security_score(
    address: Annotated[int, "Function address to analyze"],
) -> str:
    """Analyze a specific function for security issues.

    Args:
        address: Function address

    Returns:
        Security analysis for the function including:
        - Complexity score
        - Security issues found
        - Code smells detected
        - Recommendations
    """
    from ...tools.code_quality import _analyze_function_ida, _calculate_security_score

    func_data = _analyze_function_ida(address)

    report = f"## Function Security Analysis\n\n"
    report += f"**Function:** {func_data['name']}\n"
    report += f"**Address:** `0x{func_data['address']:X}`\n"
    report += f"**Complexity:** {func_data['complexity']} ({func_data['complexity_rating']})\n"
    report += f"**Size:** {func_data['instruction_count']} instructions ({func_data['size_rating']})\n"

    # Security issues
    if func_data["security_issues"]:
        sec_score = _calculate_security_score(func_data["security_issues"])
        report += f"\n### Security Score\n"
        report += f"**Grade:** {sec_score['grade']} ({sec_score['score']}/100)\n"

        report += f"\n### Issues Found\n"
        for issue in func_data["security_issues"]:
            severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                issue["severity"], ""
            )
            report += f"- {severity_icon} **{issue['type']}** ({issue['severity']})\n"
    else:
        report += "\n### Security Score\n"
        report += "**Grade:** A (100/100)\n"
        report += "\nNo obvious security issues found.\n"

    # Code smells
    if func_data["code_smells"]:
        report += f"\n### Code Smells\n"
        for smell in func_data["code_smells"]:
            report += f"- {smell}\n"

    # Recommendations
    report += f"\n### Recommendations\n"
    if func_data["complexity_rating"] in ["high", "very_high"]:
        report += "- Consider refactoring to reduce complexity\n"

    if func_data["size_rating"] in ["large", "very_large"]:
        report += "- Consider splitting into smaller functions\n"

    if func_data["security_issues"]:
        report += "- Address security issues listed above\n"

    if not func_data["code_smells"] and func_data["complexity_rating"] == "low":
        report += "- Function appears well-structured\n"

    return report
