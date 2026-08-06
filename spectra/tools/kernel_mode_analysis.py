"""Kernel Mode Analysis tool for IDA Pro and Binary Ninja.

Detects and analyzes Windows kernel drivers, IOCTL handlers, and
kernel-mode vulnerabilities including stack/heap overflows, use-after-free,
and privilege escalation paths.
"""

from __future__ import annotations

import re
from typing import Any

# Try to import IDA API
try:
    import idaapi
    import idc
    import idautils
    IDA_AVAILABLE = True
except ImportError:
    IDA_AVAILABLE = False

# Try to import Binary Ninja API
try:
    import binaryninja
    BINJA_AVAILABLE = True
except ImportError:
    BINJA_AVAILABLE = False


# Kernel driver IOCTL codes and patterns
IOCTL_PATTERNS = {
    "CTL_CODE": {
        "pattern": r"CTL_CODE\s*\(",
        "severity": "info",
        "description": "IOCTL code definition macro"
    },
    "METHOD_NEITHER": {
        "pattern": r"METHOD_NEITHER",
        "severity": "high",
        "description": "Dangerous I/O method - user pointers passed directly"
    },
    "METHOD_BUFFERED": {
        "pattern": r"METHOD_BUFFERED",
        "severity": "medium",
        "description": "Buffered I/O - safer but still validate input"
    },
    "METHOD_IN_DIRECT": {
        "pattern": r"METHOD_IN_DIRECT",
        "severity": "medium",
        "description": "Direct input I/O - validate buffer sizes"
    },
    "METHOD_OUT_DIRECT": {
        "pattern": r"METHOD_OUT_DIRECT",
        "severity": "medium",
        "description": "Direct output I/O - validate buffer sizes"
    },
}

# Kernel driver exports to identify
DRIVER_EXPORTS = {
    "DriverEntry": {"severity": "critical", "description": "Driver entry point"},
    "DriverUnload": {"severity": "info", "description": "Driver unload routine"},
    "IoAllocateMdl": {"severity": "info", "description": "MDL allocation"},
    "IoFreeMdl": {"severity": "info", "description": "MDL free"},
    "MmCopyMemory": {"severity": "high", "description": "Kernel memory copy - check bounds"},
    "ProbeForRead": {"severity": "medium", "description": "User buffer validation"},
    "ProbeForWrite": {"severity": "medium", "description": "User buffer validation"},
    "ExAllocatePoolWithTag": {"severity": "high", "description": "Pool allocation"},
    "ExFreePoolWithTag": {"severity": "high", "description": "Pool free - UAF risk"},
    "IoCreateDevice": {"severity": "critical", "description": "Device creation"},
    "IoCreateSymbolicLink": {"severity": "info", "description": "Symbolic link creation"},
    "IoDeleteDevice": {"severity": "info", "description": "Device deletion"},
}

# Dangerous kernel APIs
DANGEROUS_KERNEL_APIS = {
    "ZwOpenProcess": {"severity": "critical", "description": "Process handle - EPROCESS access"},
    "ZwOpenThread": {"severity": "high", "description": "Thread handle - ETHREAD access"},
    "PsLookupProcessByProcessId": {"severity": "high", "description": "Process lookup"},
    "PsGetCurrentProcess": {"severity": "high", "description": "Current EPROCESS"},
    "PsGetProcessImageFileName": {"severity": "medium", "description": "Process name leak"},
    "KeStackAttachProcess": {"severity": "critical", "description": "Process attachment"},
    "KeUnstackDetachProcess": {"severity": "critical", "description": "Process detachment"},
    "ObReferenceObjectByHandle": {"severity": "high", "description": "Object reference"},
    "ObDereferenceObject": {"severity": "high", "description": "Object dereference - refcount bug"},
}

# Vulnerability patterns
VULN_PATTERNS = {
    "memcpy": {
        "pattern": r"memcpy\s*\(",
        "severity": "high",
        "description": "Unbounded memory copy - potential overflow"
    },
    "strcpy": {
        "pattern": r"strcpy\s*\(",
        "severity": "critical",
        "description": "Unsafe string copy - always overflow risk"
    },
    "wcsncpy": {
        "pattern": r"wcsncpy\s*\(",
        "severity": "medium",
        "description": "Wide char copy - check length parameter"
    },
    "RtlCopyMemory": {
        "pattern": r"RtlCopyMemory\s*\(",
        "severity": "high",
        "description": "Kernel memcpy - validate size"
    },
    "memmove": {
        "pattern": r"memmove\s*\(",
        "severity": "medium",
        "description": "Memory move - check overlap"
    },
    "sprintf": {
        "pattern": r"sprintf\s*\(",
        "severity": "critical",
        "description": "Unsafe sprintf - buffer overflow"
    },
    "swprintf": {
        "pattern": r"swprintf\s*\(",
        "severity": "critical",
        "description": "Unsafe wide sprintf - buffer overflow"
    },
}


def _analyze_ida_kernel() -> dict[str, Any]:
    """Analyze kernel driver in IDA Pro."""
    if not IDA_AVAILABLE:
        return {"error": "IDA Pro API not available"}

    results = {
        "driver_entry": None,
        "ioctl_handlers": [],
        "driver_exports": [],
        "dangerous_apis": [],
        "vulnerabilities": [],
        "device_names": [],
        "mitigations": [],
    }

    # Find DriverEntry
    for func_ea in idautils.Functions():
        func_name = idc.get_func_name(func_ea)
        if "DriverEntry" in func_name or func_name.startswith("Driver"):
            results["driver_entry"] = {
                "address": func_ea,
                "name": func_name,
            }
            break

    # Search for IOCTL handlers
    for func_ea in idautils.Functions():
        func_name = idc.get_func_name(func_ea)

        # Check for IOCTL-related function names
        if any(keyword in func_name.lower() for keyword in ["ioctl", "deviceiocontrol", "irp", "dispatch"]):
            # Scan function for IOCTL patterns
            func_text = ""
            func = idaapi.get_func(func_ea)
            func_end = func.end_ea if func else func_ea
            for instr_ea in idautils.Heads(func_ea, func_end):
                disasm = idaapi.get_disasm(instr_ea)
                if not disasm:
                    mnem = idaapi.print_insn_mnem(instr_ea)
                    op1 = idaapi.print_operand(instr_ea, 0)
                    op2 = idaapi.print_operand(instr_ea, 1)
                    disasm = f"{mnem}"
                    if op1: disasm += f" {op1}"
                    if op2: disasm += f", {op2}"
                func_text += disasm.lower() + "\n"

            for pattern_name, pattern_info in IOCTL_PATTERNS.items():
                if re.search(pattern_info["pattern"], func_text, re.IGNORECASE):
                    results["ioctl_handlers"].append({
                        "address": func_ea,
                        "function": func_name,
                        "pattern": pattern_name,
                        "severity": pattern_info["severity"],
                        "description": pattern_info["description"],
                    })

    # Find driver exports
    import_list = []
    try:
        for imp_ea in idautils.Imports():
            imp_name = idc.get_name(imp_ea)
            for export_name, export_info in DRIVER_EXPORTS.items():
                if export_name.lower() in imp_name.lower():
                    results["driver_exports"].append({
                        "address": imp_ea,
                        "name": imp_name,
                        "severity": export_info["severity"],
                        "description": export_info["description"],
                    })
            for api_name, api_info in DANGEROUS_KERNEL_APIS.items():
                if api_name.lower() in imp_name.lower():
                    results["dangerous_apis"].append({
                        "address": imp_ea,
                        "name": imp_name,
                        "severity": api_info["severity"],
                        "description": api_info["description"],
                    })
    except Exception:
        pass

    # Search for vulnerability patterns
    for func_ea in idautils.Functions():
        func_name = idc.get_func_name(func_ea)

        # Get function pseudocode if available
        try:
            import ida_hexrays
            if ida_hexrays.init_hexrays_plugin():
                cfunc = ida_hexrays.decompile(func_ea)
                if cfunc:
                    func_text = str(cfunc)
                else:
                    func_text = ""
            else:
                func_text = ""
        except Exception:
            func_text = ""

        if not func_text:
            # Fallback to disassembly
            func = idaapi.get_func(func_ea)
            func_end = func.end_ea if func else func_ea
            for instr_ea in idautils.Heads(func_ea, func_end):
                disasm = idaapi.get_disasm(instr_ea)
                if not disasm:
                    mnem = idaapi.print_insn_mnem(instr_ea)
                    op1 = idaapi.print_operand(instr_ea, 0)
                    op2 = idaapi.print_operand(instr_ea, 1)
                    disasm = f"{mnem}"
                    if op1: disasm += f" {op1}"
                    if op2: disasm += f", {op2}"
                func_text += disasm + "\n"

        for vuln_name, vuln_info in VULN_PATTERNS.items():
            if re.search(vuln_info["pattern"], func_text, re.IGNORECASE):
                results["vulnerabilities"].append({
                    "address": func_ea,
                    "function": func_name,
                    "pattern": vuln_name,
                    "severity": vuln_info["severity"],
                    "description": vuln_info["description"],
                })

    # Search for device names in strings
    for seg_ea in idautils.Segments():
        if idc.get_segm_name(seg_ea).startswith((".data", ".rdata", "DATA")):
            for str_ea in idautils.Strings(seg_ea):
                string = str(str_ea)
                if "\\Device\\" in string or "\\DosDevices\\" in string:
                    results["device_names"].append({
                        "address": str_ea,
                        "name": string.strip(),
                    })

    return results


def _analyze_binja_kernel(bv) -> dict[str, Any]:
    """Analyze kernel driver in Binary Ninja."""
    if not BINJA_AVAILABLE:
        return {"error": "Binary Ninja API not available"}

    results = {
        "driver_entry": None,
        "ioctl_handlers": [],
        "driver_exports": [],
        "dangerous_apis": [],
        "vulnerabilities": [],
        "device_names": [],
        "mitigations": [],
    }

    # Find DriverEntry
    for func in bv.functions:
        if "DriverEntry" in func.name or func.name.startswith("Driver"):
            results["driver_entry"] = {
                "address": hex(func.start),
                "name": func.name,
            }
            break

    # Search for IOCTL handlers
    for func in bv.functions:
        if any(keyword in func.name.lower() for keyword in ["ioctl", "deviceiocontrol", "irp", "dispatch"]):
            for pattern_name, pattern_info in IOCTL_PATTERNS.items():
                # Search in function disassembly
                for instr in func.instructions:
                    disasm = str(instr)
                    if re.search(pattern_info["pattern"], disasm, re.IGNORECASE):
                        results["ioctl_handlers"].append({
                            "address": hex(func.start),
                            "function": func.name,
                            "pattern": pattern_name,
                            "severity": pattern_info["severity"],
                            "description": pattern_info["description"],
                        })
                        break

    # Find driver exports and dangerous APIs
    for func in bv.functions:
        for export_name, export_info in DRIVER_EXPORTS.items():
            if export_name.lower() in func.name.lower():
                results["driver_exports"].append({
                    "address": hex(func.start),
                    "name": func.name,
                    "severity": export_info["severity"],
                    "description": export_info["description"],
                })

        for api_name, api_info in DANGEROUS_KERNEL_APIS.items():
            if api_name.lower() in func.name.lower():
                results["dangerous_apis"].append({
                    "address": hex(func.start),
                    "name": func.name,
                    "severity": api_info["severity"],
                    "description": api_info["description"],
                })

    # Search for device names
    for func in bv.functions:
        for string in bv.get_strings(func.start):
            value = string.value
            if "\\Device\\" in value or "\\DosDevices\\" in value:
                results["device_names"].append({
                    "address": hex(string.start),
                    "name": value,
                })

    return results


def format_kernel_report(results: dict[str, Any]) -> str:
    """Format kernel analysis results as markdown report."""
    if "error" in results:
        return results["error"]

    report_lines = ["## Kernel Mode Analysis Report\n"]

    # Driver Entry
    if results.get("driver_entry"):
        entry = results["driver_entry"]
        report_lines.append(f"**Driver Entry:** `{entry['name']}` at `{entry['address']:X}`\n")

    # Device Names
    if results["device_names"]:
        report_lines.append("\n### Device Names\n")
        for dev in results["device_names"]:
            report_lines.append(f"- `{dev['name']}` at `{dev['address']:X}`\n")

    # IOCTL Handlers
    if results["ioctl_handlers"]:
        report_lines.append("\n### IOCTL Handlers\n")
        for handler in results["ioctl_handlers"]:
            severity_icon = {"critical": "[CRIT]", "high": "[HIGH]", "medium": "[MED]", "info": "[INFO]"}.get(
                handler["severity"], "[?]"
            )
            report_lines.append(
                f"- {severity_icon} **{handler['function']}** at `{handler['address']:X}`\n"
                f"  - *{handler['description']}* ({handler['pattern']})\n"
            )

    # Driver Exports
    if results["driver_exports"]:
        report_lines.append("\n### Driver Exports\n")
        for export in results["driver_exports"][:10]:  # Limit to 10
            severity_icon = {"critical": "[CRIT]", "high": "[HIGH]", "medium": "[MED]", "info": "[INFO]"}.get(
                export["severity"], "[?]"
            )
            report_lines.append(f"- {severity_icon} `{export['name']}` at `{export['address']:X}`\n")

    # Dangerous APIs
    if results["dangerous_apis"]:
        report_lines.append("\n### Dangerous Kernel APIs\n")
        for api in results["dangerous_apis"][:10]:
            severity_icon = {"critical": "[CRIT]", "high": "[HIGH]", "medium": "[MED]", "info": "[INFO]"}.get(
                api["severity"], "[?]"
            )
            report_lines.append(
                f"- {severity_icon} `{api['name']}` at `{api['address']:X}`\n"
                f"  - *{api['description']}*\n"
            )

    # Vulnerabilities
    if results["vulnerabilities"]:
        report_lines.append("\n### Potential Vulnerabilities\n")
        for vuln in results["vulnerabilities"][:10]:
            severity_icon = {"critical": "[CRIT]", "high": "[HIGH]", "medium": "[MED]", "info": "[INFO]"}.get(
                vuln["severity"], "[?]"
            )
            report_lines.append(
                f"- {severity_icon} **{vuln['function']}** at `{vuln['address']:X}`\n"
                f"  - *{vuln['description']}* ({vuln['pattern']})\n"
            )

    # Summary
    total_issues = (
        len(results["ioctl_handlers"])
        + len(results["dangerous_apis"])
        + len(results["vulnerabilities"])
    )
    critical_count = sum(
        1 for x in results["ioctl_handlers"] + results["dangerous_apis"] + results["vulnerabilities"]
        if x.get("severity") == "critical"
    )

    report_lines.append(f"\n### Summary\n")
    report_lines.append(f"- **Total findings:** {total_issues}\n")
    report_lines.append(f"- **Critical issues:** {critical_count}\n")

    if critical_count > 0:
        report_lines.append(f"\n**⚠️ CRITICAL:** This driver has {critical_count} critical vulnerability indicators.\n")

    return "\n".join(report_lines)


def analyze_kernel_mode(binary_view=None) -> str:
    """Main entry point for kernel mode analysis.

    Args:
        binary_view: Binary Ninja BinaryView object (optional)

    Returns:
        Formatted markdown report
    """
    if IDA_AVAILABLE:
        results = _analyze_ida_kernel()
    elif BINJA_AVAILABLE and binary_view:
        results = _analyze_binja_kernel(binary_view)
    else:
        return "Error: Neither IDA Pro nor Binary Ninja API is available"

    return format_kernel_report(results)


if __name__ == "__main__":
    print(analyze_kernel_mode())
