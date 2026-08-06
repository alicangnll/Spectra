"""VM/Obfuscation Detection tool for IDA Pro and Binary Ninja.

Detects virtual machine-based obfuscation (VMProtect, Themida, Tigress, etc.)
and code obfuscation patterns including control flow flattening,
opaque predicates, and junk code insertion.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# Try to import IDA API
try:
    import idaapi
    import idc
    import idautils
    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False

# Import compatibility helpers
from .ida_helpers import get_disasm_text

# Try to import Binary Ninja API
try:
    import binaryninja
    BINJA_AVAILABLE = True
except ImportError:
    BINJA_AVAILABLE = False


# VM/Obfuscator signatures
VM_PROTECTOR_SIGNATURES = {
    "VMProtect": {
        "strings": ["VMProtect", "vmp", "VMProtectSDK", "VMProtectBegin", "VMProtectEnd"],
        "imports": ["VMProtectIsProtected", "VMProtectIsDebuggerPresent", "VMProtectDecryptStringA"],
        "sections": [".vmp0", ".vmp1", ".vmp2", ".vmp3"],
        "description": "VMProtect virtualization"
    },
    "Themida": {
        "strings": ["Themida", "WinLicense", "ThemidaSDK", "SecureEngine"],
        "imports": ["CodeVirtualizerBegin", "CodeVirtualizerEnd", "Themida"],
        "sections": [".themida", ".winlice"],
        "description": "Themida/WinLicense protection"
    },
    "Tigress": {
        "strings": ["Tigress", "Tigress_transform", "Tigress_obfuscate"],
        "imports": ["tigress_", "Tigress_"],
        "sections": [".tigs"],
        "description": "Tigress code protection"
    },
    "VMPsoft": {
        "strings": ["VMPsoft", "Virtual_Machine"],
        "imports": ["VMP_"],
        "sections": [".vmp"],
        "description": "VMPsoft virtual machine"
    },
    "Enigma": {
        "strings": ["Enigma", "EnigmaVB", "Enigma Protector"],
        "imports": ["ENIGMA_", "Enigma_"],
        "sections": [".enigma"],
        "description": "Enigma Protector"
    },
    "UPX": {
        "strings": ["UPX!", "UPX compressed"],
        "imports": ["UPX"],
        "sections": ["UPX0", "UPX1", "UPX2"],
        "description": "UPX packer (can be unpacked)"
    },
    "ASPack": {
        "strings": ["ASPack", "ASPack compressed"],
        "imports": ["ASPack"],
        "sections": [".aspack"],
        "description": "ASPack packer"
    },
    "PECompact": {
        "strings": ["PECompact", "PECompact2"],
        "imports": ["PEC2", "PECompact"],
        "sections": [".pec", ".pec2"],
        "description": "PECompact packer"
    },
}

# Control flow obfuscation patterns
CF_OBFUSCATION_PATTERNS = {
    "dispatcher": {
        "description": "Dispatcher-based control flow (switch/jump table)",
        "indicators": [
            "large switch statement",
            "jump table",
            "indirect jump via register",
            "computed goto"
        ]
    },
    "opaque_predicate": {
        "description": "Opaque predicates (always true/false conditions)",
        "indicators": [
            "xor reg, reg; test reg, reg",
            "cmp reg, reg",
            "always zero comparison",
            "redundant comparison"
        ]
    },
    "junk_code": {
        "description": "Junk code insertion",
        "indicators": [
            "useless mov instructions",
            "push/pop without effect",
            "nop sequences",
            "dead store"
        ]
    },
    "instruction_substitution": {
        "description": "Instruction substitution (e.g., xor reg, reg vs mov reg, 0)",
        "indicators": [
            "xor for zeroing",
            "sub for negation",
            "push/pop for mov",
            "complex single-purpose sequences"
        ]
    },
    "call_obfuscation": {
        "description": "Call obfuscation (trampolines, push/ret)",
        "indicators": [
            "push addr; ret",
            "jmp [reg+off]",
            "call table lookup",
            "nested calls"
        ]
    },
}

# Function complexity metrics for detecting obfuscation
OBFUSCATION_METRICS = {
    "high_instruction_count": {"threshold": 500, "description": "Very high instruction count"},
    "high_basic_block_count": {"threshold": 50, "description": "Excessive basic blocks"},
    "high_cyclomatic_complexity": {"threshold": 30, "description": "High cyclomatic complexity"},
    "low_degree": {"threshold": 1.5, "description": "Low average degree (sparse CFG)"},
    "high_self_loop_ratio": {"threshold": 0.3, "description": "High self-loop ratio"},
}


def _detect_protector_ida() -> dict[str, Any]:
    """Detect known protectors in IDA Pro."""
    if not IDA_AVAILABLE:
        return {"detectors": [], "confidence": {}}

    detected_protectors = []
    confidence_scores = {}

    # Check strings
    for seg_ea in idautils.Segments():
        seg_name = idc.get_segm_name(seg_ea)
        if not seg_name.startswith((".data", ".rdata", "DATA")):
            continue

        for str_ea in idautils.Strings(seg_ea):
            string = str(str_ea).lower()

            for protector, signatures in VM_PROTECTOR_SIGNATURES.items():
                for sig_string in signatures["strings"]:
                    if sig_string.lower() in string:
                        if protector not in detected_protectors:
                            detected_protectors.append(protector)
                        confidence_scores[protector] = confidence_scores.get(protector, 0) + 10

    # Check section names
    for seg_ea in idautils.Segments():
        seg_name = idc.get_segm_name(seg_ea).lower()

        for protector, signatures in VM_PROTECTOR_SIGNATURES.items():
            for section in signatures["sections"]:
                if section.lower() in seg_name:
                    if protector not in detected_protectors:
                        detected_protectors.append(protector)
                    confidence_scores[protector] = confidence_scores.get(protector, 0) + 20

    # Check imports
    try:
        for imp_ea in idautils.Imports():
            imp_name = idc.get_name(imp_ea).lower()

            for protector, signatures in VM_PROTECTOR_SIGNATURES.items():
                for imp_sig in signatures["imports"]:
                    if imp_sig.lower() in imp_name:
                        if protector not in detected_protectors:
                            detected_protectors.append(protector)
                        confidence_scores[protector] = confidence_scores.get(protector, 0) + 15
    except Exception:
        pass

    return {
        "detectors": detected_protectors,
        "confidence": confidence_scores,
    }


def _analyze_function_complexity_ida() -> dict[str, Any]:
    """Analyze function complexity to detect obfuscation in IDA Pro."""
    if not IDA_AVAILABLE:
        return {}

    complex_functions = []
    suspicious_patterns = []

    for func_ea in idautils.Functions():
        func_name = idc.get_func_name(func_ea)

        # Count basic blocks
        block_count = 0
        instr_count = 0
        self_loops = 0
        edge_count = 0

        try:
            flow = idaapi.FlowChart(idaapi.get_func(func_ea))
            block_count = flow.size

            for block in flow:
                instr_count += len(list(idautils.Heads(block.start_ea, block.end_ea)))
                edge_count += len(list(block.succs()))

                # Check for self-loops
                for succ in block.succs():
                    if succ.id == block.id:
                        self_loops += 1

            # Calculate metrics
            if block_count > 0:
                avg_degree = edge_count / block_count if block_count > 0 else 0
                self_loop_ratio = self_loops / block_count

                # Check against thresholds
                issues = []
                if instr_count > OBFUSCATION_METRICS["high_instruction_count"]["threshold"]:
                    issues.append(f"High instruction count: {instr_count}")
                if block_count > OBFUSCATION_METRICS["high_basic_block_count"]["threshold"]:
                    issues.append(f"High basic block count: {block_count}")
                if avg_degree < OBFUSCATION_METRICS["low_degree"]["threshold"]:
                    issues.append(f"Low CFG degree: {avg_degree:.2f}")
                if self_loop_ratio > OBFUSCATION_METRICS["high_self_loop_ratio"]["threshold"]:
                    issues.append(f"High self-loop ratio: {self_loop_ratio:.2f}")

                if issues:
                    complex_functions.append({
                        "address": func_ea,
                        "name": func_name,
                        "instr_count": instr_count,
                        "block_count": block_count,
                        "issues": issues,
                    })

                    # Look for obfuscation patterns
                    func_text = ""
                    func = idaapi.get_func(func_ea)
                    func_end = func.end_ea if func else func_ea
                    for instr_ea in idautils.Heads(func_ea, func_end):
                        disasm = get_disasm_text(instr_ea)
                        if disasm:
                            func_text += disasm.lower() + "\n"

                    # Check for dispatcher pattern
                    if "jmp" in func_text and ("qword ptr" in func_text or "dword ptr" in func_text):
                        jump_count = func_text.count("jmp")
                        if jump_count > 10:
                            suspicious_patterns.append({
                                "function": func_name,
                                "address": func_ea,
                                "pattern": "dispatcher",
                                "description": f"Dispatcher pattern detected ({jump_count} indirect jumps)",
                            })

                    # Check for opaque predicates
                    if "xor" in func_text and "test" in func_text:
                        suspicious_patterns.append({
                            "function": func_name,
                            "address": func_ea,
                            "pattern": "opaque_predicate",
                            "description": "Potential opaque predicates (xor/test patterns)",
                        })

                    # Check for junk code
                    nop_count = func_text.count("nop")
                    if nop_count > 5:
                        suspicious_patterns.append({
                            "function": func_name,
                            "address": func_ea,
                            "pattern": "junk_code",
                            "description": f"Excessive NOPs ({nop_count})",
                        })

        except Exception:
            pass

    return {
        "complex_functions": complex_functions[:20],  # Limit to 20
        "suspicious_patterns": suspicious_patterns[:20],
    }


def _detect_vm_protector_binja(bv) -> dict[str, Any]:
    """Detect known protectors in Binary Ninja."""
    if not BINJA_AVAILABLE:
        return {"detectors": [], "confidence": {}}

    detected_protectors = []
    confidence_scores = {}

    # Check strings
    for string in bv.get_strings():
        value = string.value.lower()

        for protector, signatures in VM_PROTECTOR_SIGNATURES.items():
            for sig_string in signatures["strings"]:
                if sig_string.lower() in value:
                    if protector not in detected_protectors:
                        detected_protectors.append(protector)
                    confidence_scores[protector] = confidence_scores.get(protector, 0) + 10

    # Check section names
    for section in bv.sections:
        sec_name = section.name.lower()

        for protector, signatures in VM_PROTECTOR_SIGNATURES.items():
            for section_sig in signatures["sections"]:
                if section_sig.lower() in sec_name:
                    if protector not in detected_protectors:
                        detected_protectors.append(protector)
                    confidence_scores[protector] = confidence_scores.get(protector, 0) + 20

    # Check symbols/imports
    for func in bv.functions:
        func_name_lower = func.name.lower()

        for protector, signatures in VM_PROTECTOR_SIGNATURES.items():
            for imp_sig in signatures["imports"]:
                if imp_sig.lower() in func_name_lower:
                    if protector not in detected_protectors:
                        detected_protectors.append(protector)
                    confidence_scores[protector] = confidence_scores.get(protector, 0) + 15

    return {
        "detectors": detected_protectors,
        "confidence": confidence_scores,
    }


def _analyze_function_complexity_binja(bv) -> dict[str, Any]:
    """Analyze function complexity to detect obfuscation in Binary Ninja."""
    if not BINJA_AVAILABLE:
        return {}

    complex_functions = []
    suspicious_patterns = []

    for func in bv.functions:
        instr_count = len(list(func.instructions))
        block_count = len(list(func.basic_blocks))

        if block_count == 0:
            continue

        # Calculate metrics
        if instr_count > OBFUSCATION_METRICS["high_instruction_count"]["threshold"] or \
           block_count > OBFUSCATION_METRICS["high_basic_block_count"]["threshold"]:

            issues = []
            if instr_count > OBFUSCATION_METRICS["high_instruction_count"]["threshold"]:
                issues.append(f"High instruction count: {instr_count}")
            if block_count > OBFUSCATION_METRICS["high_basic_block_count"]["threshold"]:
                issues.append(f"High basic block count: {block_count}")

            complex_functions.append({
                "address": hex(func.start),
                "name": func.name,
                "instr_count": instr_count,
                "block_count": block_count,
                "issues": issues,
            })

            # Look for obfuscation patterns in disassembly
            func_text = "\n".join(str(instr) for instr in func.instructions).lower()

            if "jmp" in func_text and ("qword" in func_text or "dword" in func_text):
                suspicious_patterns.append({
                    "function": func.name,
                    "address": hex(func.start),
                    "pattern": "dispatcher",
                    "description": "Dispatcher pattern detected",
                })

    return {
        "complex_functions": complex_functions[:20],
        "suspicious_patterns": suspicious_patterns[:20],
    }


def format_obfuscation_report(protector_detection: dict, complexity: dict) -> str:
    """Format obfuscation detection results as markdown report."""
    report_lines = ["## VM/Obfuscation Detection Report\n"]

    # Detected Protectors
    if protector_detection.get("detectors"):
        report_lines.append("### Detected Protectors\n")
        for protector in protector_detection["detectors"]:
            confidence = protector_detection["confidence"].get(protector, 0)
            sig = VM_PROTECTOR_SIGNATURES.get(protector, {})
            report_lines.append(
                f"- **{protector}** (confidence: {confidence}%)\n"
                f"  - *{sig.get('description', 'Unknown protector')}*\n"
            )
    else:
        report_lines.append("### Detected Protectors\n")
        report_lines.append("*No known protectors detected*\n")

    # Complex Functions (potential obfuscation)
    if complexity.get("complex_functions"):
        report_lines.append("\n### Potentially Obfuscated Functions\n")
        for func in complexity["complex_functions"][:10]:
            report_lines.append(
                f"- **{func['name']}** at `{func['address']:X}`\n"
                f"  - Instructions: {func['instr_count']}, Blocks: {func['block_count']}\n"
            )
            for issue in func.get("issues", []):
                report_lines.append(f"  - ⚠️ {issue}\n")
    else:
        report_lines.append("\n### Potentially Obfuscated Functions\n")
        report_lines.append("*No highly complex functions detected*\n")

    # Suspicious Patterns
    if complexity.get("suspicious_patterns"):
        report_lines.append("\n### Obfuscation Patterns Detected\n")
        patterns_by_type = {}
        for pattern in complexity["suspicious_patterns"]:
            pattern_type = pattern["pattern"]
            if pattern_type not in patterns_by_type:
                patterns_by_type[pattern_type] = []
            patterns_by_type[pattern_type].append(pattern)

        for pattern_type, patterns in patterns_by_type.items():
            report_lines.append(f"#### {pattern_type.replace('_', ' ').title()}\n")
            for pattern in patterns[:5]:
                report_lines.append(f"- **{pattern['function']}** at `{pattern['address']:X}`\n")
                report_lines.append(f"  - *{pattern['description']}*\n")

    # Recommendations
    report_lines.append("\n### Recommendations\n")

    if protector_detection.get("detectors"):
        report_lines.append("**⚠️ Known protector detected - consider unpacking/devirtualization**\n")

        # Add specific advice per protector
        for protector in protector_detection["detectors"]:
            if protector == "UPX":
                report_lines.append(f"- **{protector}**: Can be unpacked with UPX -d\n")
            elif protector == "VMProtect":
                report_lines.append(f"- **{protector}**: Use VMProtect devirtualization tools or dynamic analysis\n")
            elif protector == "Themida":
                report_lines.append(f"- **{protector}**: Dump from memory after unpacking stub\n")
            else:
                report_lines.append(f"- **{protector}**: Research specific unpacking techniques\n")

    if complexity.get("complex_functions"):
        report_lines.append("\n**⚠️ High complexity functions detected - may indicate obfuscation**\n")
        report_lines.append("- Consider deobfuscation tools (Flare-Emu, D810, etc.)\n")
        report_lines.append("- Use dynamic analysis to understand actual behavior\n")
        report_lines.append("- Look for dispatcher patterns and trace execution\n")

    if not protector_detection.get("detectors") and not complexity.get("complex_functions"):
        report_lines.append("*No significant obfuscation detected - binary appears clean*\n")

    return "\n".join(report_lines)


def detect_vm_obfuscation(binary_view=None) -> str:
    """Main entry point for VM/obfuscation detection.

    Args:
        binary_view: Binary Ninja BinaryView object (optional)

    Returns:
        Formatted markdown report
    """
    protector_detection = {}
    complexity = {}

    if IDA_AVAILABLE:
        protector_detection = _detect_protector_ida()
        complexity = _analyze_function_complexity_ida()
    elif BINJA_AVAILABLE and binary_view:
        protector_detection = _detect_vm_protector_binja(binary_view)
        complexity = _analyze_function_complexity_binja(binary_view)
    else:
        return "Error: Neither IDA Pro nor Binary Ninja API is available"

    return format_obfuscation_report(protector_detection, complexity)


def get_deobfuscation_suggestions(detected_protectors: list[str]) -> str:
    """Get specific deobfuscation suggestions based on detected protectors."""
    suggestions = []

    for protector in detected_protectors:
        if protector == "VMProtect":
            suggestions.append({
                "tool": "VMProtect Devirtualizer",
                "method": "Use VMP3 devirtualization tools or trace VM handlers",
                "difficulty": "Hard",
            })
        elif protector == "Themida":
            suggestions.append({
                "tool": "Themida Unpacker",
                "method": "Dump from memory after unpacking stub, rebuild IAT",
                "difficulty": "Medium",
            })
        elif protector == "UPX":
            suggestions.append({
                "tool": "UPX",
                "method": "upx -d filename.exe",
                "difficulty": "Easy",
            })
        elif protector == "Tigress":
            suggestions.append({
                "tool": "Tigress Deobfuscator",
                "method": "Use symbolic execution or partial evaluation",
                "difficulty": "Very Hard",
            })

    return "\n".join(
        f"- **{s['tool']}** ({s['difficulty']}): {s['method']}\n"
        for s in suggestions
    )


if __name__ == "__main__":
    print(detect_vm_obfuscation())
