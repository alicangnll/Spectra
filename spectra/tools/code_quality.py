"""Code Quality Metrics analysis tool.

Analyzes binary code for complexity, maintainability, security issues,
and technical debt indicators.
"""

from __future__ import annotations

import re
from typing import Any

# Try to import IDA API
try:
    import idaapi
    import idautils
    import idc

    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False

# Import compatibility helpers
from .ida_helpers import get_disasm_text

# Try to import Binary Ninja API
try:
    import binaryninja  # noqa: F401 — availability probe

    BINJA_AVAILABLE = True
except ImportError:
    BINJA_AVAILABLE = False


# Complexity thresholds
COMPLEXITY_THRESHOLDS = {
    "very_high": 50,  # Cyclomatic complexity
    "high": 20,
    "medium": 10,
    "low": 5,
}

# Function size thresholds
SIZE_THRESHOLDS = {
    "very_large": 1000,  # Instructions
    "large": 500,
    "medium": 200,
    "small": 50,
}

# Code smell patterns
CODE_SMELL_PATTERNS = {
    "long_parameter_list": {
        "description": "Functions with too many parameters (>8)",
        "threshold": 8,
    },
    "deep_nesting": {
        "description": "Deep nesting levels (>4)",
        "threshold": 4,
    },
    "duplicate_code": {
        "description": "Potential code duplication",
        "threshold": 0.7,  # Similarity threshold
    },
    "large_switch": {
        "description": "Large switch statements (>10 cases)",
        "threshold": 10,
    },
    "magic_numbers": {
        "description": "Magic numbers without named constants",
        "pattern": r"\b(0x[0-9a-fA-F]+|[0-9]{3,})\b",
    },
    "god_function": {
        "description": "Functions doing too much ( > 500 instructions)",
        "threshold": 500,
    },
}

# Security anti-patterns
SECURITY_ANTI_PATTERNS = {
    "hardcoded_credentials": {
        "patterns": [
            r"password\s*=\s*[\"'][^\"']+[\"']",
            r"api_key\s*=\s*[\"'][^\"']+[\"']",
            r"secret\s*=\s*[\"'][^\"']+[\"']",
            r"token\s*=\s*[\"'][^\"']{20,}[\"']",
        ],
        "severity": "critical",
    },
    "weak_crypto": {
        "patterns": [
            r"MD5",
            r"SHA1",
            r"DES",
            r"RC4",
            r"md5",
            r"sha1",
        ],
        "severity": "high",
    },
    "random_without_seed": {
        "patterns": [
            r"rand\s*\(\s*\)",
            r"srand\s*\(\s*time\s*\(",
            r"random\s*\(\s*\)",
        ],
        "severity": "medium",
    },
    "unsafe_string_ops": {
        "patterns": [
            r"strcpy\s*\(",
            r"strcat\s*\(",
            r"sprintf\s*\(",
            r"gets\s*\(",
        ],
        "severity": "critical",
    },
    "null_ptr_deref": {
        "patterns": [
            r"\*\s*\w+\s*;",
            r"\w+\s*\[\s*\d+\s*\]\s*=",
        ],
        "severity": "high",
    },
}


def _calculate_cyclomatic_complexity_ida(func_ea: int) -> dict[str, Any]:
    """Calculate cyclomatic complexity for an IDA function."""
    if not IDA_AVAILABLE:
        return {"complexity": 0}

    complexity = 1  # Base complexity

    try:
        flow = idaapi.FlowChart(idaapi.get_func(func_ea))

        # Count decision points (basic blocks with multiple successors)
        for block in flow:
            successor_count = len(list(block.succs()))
            if successor_count > 1:
                complexity += successor_count - 1

    except Exception:
        pass

    return {
        "complexity": complexity,
        "rating": _get_complexity_rating(complexity),
    }


def _get_complexity_rating(complexity: int) -> str:
    """Get complexity rating label."""
    if complexity >= COMPLEXITY_THRESHOLDS["very_high"]:
        return "very_high"
    elif complexity >= COMPLEXITY_THRESHOLDS["high"]:
        return "high"
    elif complexity >= COMPLEXITY_THRESHOLDS["medium"]:
        return "medium"
    else:
        return "low"


def _get_size_rating(instruction_count: int) -> str:
    """Get size rating label."""
    if instruction_count >= SIZE_THRESHOLDS["very_large"]:
        return "very_large"
    elif instruction_count >= SIZE_THRESHOLDS["large"]:
        return "large"
    elif instruction_count >= SIZE_THRESHOLDS["medium"]:
        return "medium"
    else:
        return "small"


def _analyze_function_ida(func_ea: int) -> dict[str, Any]:
    """Analyze a single function for code quality metrics."""
    if not IDA_AVAILABLE:
        return {}

    func_name = idc.get_func_name(func_ea)

    # Count instructions
    instr_count = 0
    basic_blocks = 0
    _nesting_level = 0

    try:
        flow = idaapi.FlowChart(idaapi.get_func(func_ea))
        basic_blocks = flow.size

        for block in flow:
            instr_count += len(list(idautils.Heads(block.start_ea, block.end_ea)))

    except Exception:
        # Fallback to manual counting
        func = idaapi.get_func(func_ea)
        func_end = func.end_ea if func else func_ea
        for _instr_ea in idautils.Heads(func_ea, func_end):
            instr_count += 1

    # Calculate complexity
    complexity_data = _calculate_cyclomatic_complexity_ida(func_ea)

    # Get function text for pattern matching
    func_text = ""
    try:
        import ida_hexrays

        if ida_hexrays.init_hexrays_plugin():
            cfunc = ida_hexrays.decompile(func_ea)
            if cfunc:
                func_text = str(cfunc)
    except Exception:
        pass

    if not func_text:
        func = idaapi.get_func(func_ea)
        func_end = func.end_ea if func else func_ea
        for instr_ea in idautils.Heads(func_ea, func_end):
            disasm = get_disasm_text(instr_ea)
            if disasm:
                func_text += disasm + "\n"

    # Detect code smells
    code_smells = []
    issues = []

    # Check for god function
    if instr_count > CODE_SMELL_PATTERNS["god_function"]["threshold"]:
        code_smells.append("god_function")
        issues.append(f"Very large function ({instr_count} instructions)")

    # Check for magic numbers
    magic_matches = re.findall(CODE_SMELL_PATTERNS["magic_numbers"]["pattern"], func_text)
    if len(magic_matches) > 20:
        code_smells.append("magic_numbers")
        issues.append(f"Many magic numbers ({len(magic_matches)})")

    # Check security anti-patterns
    security_issues = []
    for vuln_type, vuln_info in SECURITY_ANTI_PATTERNS.items():
        for pattern in vuln_info["patterns"]:
            if re.search(pattern, func_text, re.IGNORECASE):
                security_issues.append(
                    {
                        "type": vuln_type,
                        "severity": vuln_info["severity"],
                        "pattern": pattern,
                    }
                )
                break

    return {
        "address": func_ea,
        "name": func_name,
        "instruction_count": instr_count,
        "basic_blocks": basic_blocks,
        "complexity": complexity_data["complexity"],
        "complexity_rating": complexity_data["rating"],
        "size_rating": _get_size_rating(instr_count),
        "code_smells": code_smells,
        "issues": issues,
        "security_issues": security_issues,
    }


def _calculate_security_score(issues: list) -> dict[str, Any]:
    """Calculate security score based on found issues."""
    score = 100
    severity_weights = {
        "critical": 20,
        "high": 10,
        "medium": 5,
        "low": 1,
    }

    issue_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for issue in issues:
        severity = issue.get("severity", "low")
        issue_counts[severity] = issue_counts.get(severity, 0) + 1
        score = max(0, score - severity_weights.get(severity, 1))

    grade = "A"
    if score < 50:
        grade = "F"
    elif score < 70:
        grade = "D"
    elif score < 85:
        grade = "C"
    elif score < 95:
        grade = "B"

    return {
        "score": score,
        "grade": grade,
        "issue_counts": issue_counts,
    }


def analyze_code_quality_ida() -> dict[str, Any]:
    """Analyze code quality for all functions in IDA Pro."""
    if not IDA_AVAILABLE:
        return {"error": "IDA Pro API not available"}

    functions = []
    security_issues = []
    total_complexity = 0
    total_size = 0
    high_complexity = 0
    large_functions = 0

    # Analyze each function
    for func_ea in idautils.Functions():
        func_data = _analyze_function_ida(func_ea)
        functions.append(func_data)

        total_complexity += func_data["complexity"]
        total_size += func_data["instruction_count"]

        if func_data["complexity_rating"] in ["high", "very_high"]:
            high_complexity += 1

        if func_data["size_rating"] in ["large", "very_large"]:
            large_functions += 1

        security_issues.extend(func_data["security_issues"])

    # Calculate aggregate metrics
    func_count = len(functions)
    avg_complexity = total_complexity / func_count if func_count > 0 else 0
    avg_size = total_size / func_count if func_count > 0 else 0

    # Find most complex functions
    most_complex = sorted(functions, key=lambda x: x["complexity"], reverse=True)[:10]
    largest = sorted(functions, key=lambda x: x["instruction_count"], reverse=True)[:10]

    # Calculate security score
    security_score = _calculate_security_score(security_issues)

    return {
        "function_count": func_count,
        "average_complexity": avg_complexity,
        "average_size": avg_size,
        "high_complexity_count": high_complexity,
        "large_function_count": large_functions,
        "most_complex": most_complex,
        "largest": largest,
        "security_issues": security_issues[:50],
        "security_score": security_score,
    }


def format_code_quality_report(results: dict[str, Any]) -> str:
    """Format code quality analysis results as markdown report."""
    if "error" in results:
        return results["error"]

    report_lines = ["## Code Quality Metrics Report\n"]

    # Summary
    report_lines.append("### Summary\n")
    report_lines.append(f"**Functions Analyzed:** {results['function_count']}\n")
    report_lines.append(f"**Average Complexity:** {results['average_complexity']:.1f}\n")
    report_lines.append(f"**Average Size:** {results['average_size']:.0f} instructions\n")
    report_lines.append(f"**High Complexity Functions:** {results['high_complexity_count']}\n")
    report_lines.append(f"**Large Functions:** {results['large_function_count']}\n")

    # Security Score
    sec_score = results["security_score"]
    report_lines.append("\n### Security Score\n")
    grade_color = {
        "A": "🟢",
        "B": "🟡",
        "C": "🟠",
        "D": "🔴",
        "F": "⚫",
    }.get(sec_score["grade"], "")
    report_lines.append(f"**Grade:** {grade_color} {sec_score['grade']} ({sec_score['score']}/100)\n")

    issue_counts = sec_score["issue_counts"]
    if any(issue_counts.values()):
        report_lines.append("\n**Security Issues Found:**\n")
        for severity, count in issue_counts.items():
            if count > 0:
                report_lines.append(f"- {severity.upper()}: {count}\n")

    # Most Complex Functions
    if results["most_complex"]:
        report_lines.append("\n### Most Complex Functions\n")
        for func in results["most_complex"][:10]:
            complexity_icon = {
                "very_high": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
            }.get(func["complexity_rating"], "")
            report_lines.append(
                f"- {complexity_icon} **{func['name']}** (Complexity: {func['complexity']})\n"
                f"  - Address: `0x{func['address']:X}`\n"
                f"  - Size: {func['instruction_count']} instructions, {func['basic_blocks']} blocks\n"
            )
            if func["issues"]:
                report_lines.append(f"  - Issues: {', '.join(func['issues'][:3])}\n")

    # Largest Functions
    if results["largest"]:
        report_lines.append("\n### Largest Functions\n")
        for func in results["largest"][:10]:
            size_icon = {
                "very_large": "🔴",
                "large": "🟠",
                "medium": "🟡",
                "small": "🟢",
            }.get(func["size_rating"], "")
            report_lines.append(
                f"- {size_icon} **{func['name']}** ({func['instruction_count']} instructions)\n"
                f"  - Address: `0x{func['address']:X}`\n"
                f"  - Complexity: {func['complexity']}\n"
            )

    # Security Issues
    if results["security_issues"]:
        report_lines.append("\n### Security Issues Detail\n")

        by_severity = {}
        for issue in results["security_issues"]:
            severity = issue["severity"]
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(issue)

        for severity in ["critical", "high", "medium", "low"]:
            if severity in by_severity:
                report_lines.append(f"\n#### {severity.upper()}\n")
                for issue in by_severity[severity][:10]:
                    report_lines.append(f"- **{issue['type']}** - Pattern: `{issue['pattern']}`\n")

    # Recommendations
    report_lines.append("\n### Recommendations\n")

    if results["high_complexity_count"] > results["function_count"] * 0.2:
        report_lines.append("- **High Complexity:** Consider refactoring complex functions\n")
        report_lines.append("  - Break down into smaller, focused functions\n")
        report_lines.append("  - Reduce nesting levels\n")

    if results["large_function_count"] > results["function_count"] * 0.1:
        report_lines.append("- **Large Functions:** Consider function decomposition\n")
        report_lines.append("  - Extract common patterns into helper functions\n")
        report_lines.append("  - Improve testability and maintainability\n")

    if sec_score["score"] < 80:
        report_lines.append("- **Security Issues:** Address critical and high severity issues\n")
        report_lines.append("  - Replace unsafe string operations\n")
        report_lines.append("  - Remove hardcoded credentials\n")
        report_lines.append("  - Update weak cryptographic algorithms\n")

    if sec_score["score"] >= 80 and results["high_complexity_count"] < results["function_count"] * 0.1:
        report_lines.append("- Code quality is good overall\n")
        report_lines.append("- Continue following best practices\n")

    return "\n".join(report_lines)


def analyze_code_quality(binary_view=None) -> str:
    """Main entry point for code quality analysis.

    Args:
        binary_view: Binary Ninja BinaryView object (optional)

    Returns:
        Formatted markdown report
    """
    if IDA_AVAILABLE:
        results = analyze_code_quality_ida()
    else:
        return "Error: IDA Pro API not available (Binary Ninja support coming soon)"

    return format_code_quality_report(results)


if __name__ == "__main__":
    print(analyze_code_quality())
