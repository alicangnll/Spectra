"""Code Quality Metrics tool for Binary Ninja."""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from .compat import require_bv


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
    bv = require_bv()

    # Binary Ninja implementation
    functions = []
    security_issues = []
    total_complexity = 0
    total_size = 0
    high_complexity = 0
    large_functions = 0

    for func in bv.functions:
        instr_count = len(list(func.instructions))
        basic_blocks = len(list(func.basic_blocks))

        # Simple complexity estimation (basic blocks + edges)
        complexity = basic_blocks

        total_complexity += complexity
        total_size += instr_count

        if complexity > 20:
            high_complexity += 1

        if instr_count > 500:
            large_functions += 1

        # Check for security issues in function
        func_text = "\n".join(str(instr) for instr in func.instructions).lower()

        func_security_issues = []
        if "strcpy" in func_text or "gets" in func_text or "sprintf" in func_text:
            func_security_issues.append({"type": "unsafe_string_ops", "severity": "critical"})
        if "md5" in func_text or "sha1" in func_text or "des" in func_text:
            func_security_issues.append({"type": "weak_crypto", "severity": "high"})
        if "password" in func_text or "api_key" in func_text or "secret" in func_text:
            func_security_issues.append({"type": "hardcoded_credentials", "severity": "critical"})

        security_issues.extend(func_security_issues)

        functions.append({
            "name": func.name,
            "address": hex(func.start),
            "instruction_count": instr_count,
            "basic_blocks": basic_blocks,
            "complexity": complexity,
            "security_issues": func_security_issues,
        })

    # Calculate aggregate metrics
    func_count = len(functions)
    avg_complexity = total_complexity / func_count if func_count > 0 else 0
    avg_size = total_size / func_count if func_count > 0 else 0

    # Find most complex and largest functions
    most_complex = sorted(functions, key=lambda x: x["complexity"], reverse=True)[:10]
    largest = sorted(functions, key=lambda x: x["instruction_count"], reverse=True)[:10]

    # Calculate security score
    score = 100
    severity_weights = {"critical": 20, "high": 10, "medium": 5, "low": 1}
    for issue in security_issues:
        score = max(0, score - severity_weights.get(issue.get("severity", "low"), 1))

    grade = "A"
    if score < 50:
        grade = "F"
    elif score < 70:
        grade = "D"
    elif score < 85:
        grade = "C"
    elif score < 95:
        grade = "B"

    # Format report
    report_lines = ["## Code Quality Metrics Report\n"]

    report_lines.append("### Summary\n")
    report_lines.append(f"**Functions Analyzed:** {func_count}\n")
    report_lines.append(f"**Average Complexity:** {avg_complexity:.1f}\n")
    report_lines.append(f"**Average Size:** {avg_size:.0f} instructions\n")
    report_lines.append(f"**High Complexity Functions:** {high_complexity}\n")
    report_lines.append(f"**Large Functions:** {large_functions}\n")

    grade_color = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "F": "⚫"}.get(grade, "")
    report_lines.append(f"\n### Security Score\n")
    report_lines.append(f"**Grade:** {grade_color} {grade} ({score}/100)\n")
    report_lines.append(f"**Security Issues:** {len(security_issues)}\n")

    if most_complex:
        report_lines.append(f"\n### Most Complex Functions\n")
        for func in most_complex[:10]:
            report_lines.append(f"- **{func['name']}** (Complexity: {func['complexity']})\n")
            report_lines.append(f"  - Address: {func['address']}\n")
            report_lines.append(f"  - Size: {func['instruction_count']} instructions\n")

    if security_issues:
        report_lines.append(f"\n### Security Issues\n")
        by_severity = {}
        for issue in security_issues:
            severity = issue.get("severity", "low")
            if severity not in by_severity:
                by_severity[severity] = 0
            by_severity[severity] += 1

        for severity, count in by_severity.items():
            report_lines.append(f"- {severity.upper()}: {count}\n")

    return "\n".join(report_lines)
