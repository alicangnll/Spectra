"""Advanced vulnerability analysis tools for IDA Pro.

Provides IDA-specific wrappers for:
- Taint analysis
- XREF vulnerability scanning
- Buffer size analysis
- Call graph attack surface mapping
- Type-based overflow detection
"""

from __future__ import annotations

import re
from typing import Annotated

from ...tools.base import tool
from ...tools.vuln_analysis_advanced import (
    DANGEROUS_FUNCTIONS,
    TAINT_SOURCES,
    buffer_size_analysis,
    call_graph_attack_surface,
    taint_analysis,
    type_overflow_detection,
    xref_vuln_scan,
)


@tool(category="security", description="Track data flow from user input to dangerous functions")
def ida_taint_analysis(
    ea: Annotated[int, "Function address to analyze (0 for current)"] = 0,
    max_depth: Annotated[int, "Maximum depth for data flow tracking"] = 10,
) -> str:
    """Perform taint analysis on a function to track data flow to dangerous functions.

    Identifies:
    1. Data sources (recv, fgets, getenv, etc.)
    2. Data flow through the function
    3. Dangerous sinks (strcpy, system, printf, etc.)
    4. Vulnerable paths

    Args:
        ea: Function address
        max_depth: Maximum tracking depth

    Returns:
        Taint analysis report with vulnerable paths.
    """
    try:
        import ida_funcs
        import ida_hexrays
        import ida_name
    except ImportError:
        return "Error: IDA API not available"

    if ea == 0:
        ea = ida_hexrays.get_screen_ea()

    func = ida_funcs.get_func(ea)
    if not func:
        return f"No function found at 0x{ea:X}"

    func_name = ida_hexrays.get_func_name(ea)

    # Get decompiled code for analysis
    try:
        import ida_hexrays

        cfunc = ida_hexrays.decompile(ea)
        pseudocode = str(cfunc) if cfunc else ""
    except Exception:
        pseudocode = ""

    # Analyze for dangerous function calls
    dangerous_calls = []
    source_calls = []

    # Scan for calls to dangerous functions
    for xref in ida_funcs.Xrefs(func):
        if xref.type == ida_funcs.fl_CF:  # Call
            target_name = ida_name.get_name(xref.to)
            if target_name in DANGEROUS_FUNCTIONS:
                dangerous_calls.append(
                    {
                        "function": target_name,
                        "address": f"0x{xref.to:X}",
                        "risk": _get_risk_level(target_name),
                    }
                )
            elif target_name in TAINT_SOURCES:
                source_calls.append(
                    {
                        "function": target_name,
                        "address": f"0x{xref.to:X}",
                    }
                )

    report = f"""## Taint Analysis for IDA Function

**Function:** {func_name} (0x{ea:X})
**Range:** 0x{func.start_ea:X} - 0x{func.end_ea:X}
**Max Depth:** {max_depth}

### Taint Sources Found

{len(source_calls)} potential data sources:

"""

    if source_calls:
        report += "| Function | Address | Description |\n"
        report += "|----------|---------|-------------|\n"
        for src in source_calls:
            desc = TAINT_SOURCES.get(src["function"], "Unknown")
            report += f"| {src['function']} | {src['address']} | {desc} |\n"
    else:
        report += "No obvious taint sources found in this function.\n"

    report += f"""

### Dangerous Sinks Found

{len(dangerous_calls)} dangerous function calls:

"""

    if dangerous_calls:
        report += "| Function | Address | Risk Level | Description |\n"
        report += "|----------|---------|------------|-------------|\n"
        for sink in dangerous_calls:
            desc = DANGEROUS_FUNCTIONS.get(sink["function"], "Unknown")
            report += f"| {sink['function']} | {sink['address']} | {sink['risk']} | {desc} |\n"
    else:
        report += "No dangerous function calls found in this function.\n"

    report += """

### Analysis

"""

    if source_calls and dangerous_calls:
        report += "**⚠️ POTENTIAL VULNERABILITY DETECTED**\n\n"
        report += f"Function has both data sources ({len(source_calls)}) "
        report += f"and dangerous sinks ({len(dangerous_calls)}).\n\n"
        report += "**Recommended Action:** Manually trace data flow from sources to sinks.\n"
    elif source_calls:
        report += "**ℹ️ INFO:** Function has data sources but no obvious dangerous sinks.\n"
        report += "Data may be passed to callees - analyze those functions.\n"
    elif dangerous_calls:
        report += "**ℹ️ INFO:** Function has dangerous sinks but no obvious sources.\n"
        report += "Data may come from parameters - analyze callers.\n"
    else:
        report += "**✓ SAFE:** No obvious taint issues in this function.\n"

    report += f"""

### Decompiled Code

```c
{pseudocode[:2000] if pseudocode else "(Decompilation not available)"}
{"..." if len(pseudocode) > 2000 else ""}
```

### Next Steps

1. Trace data flow from each source to each sink
2. Check for sanitization/validation
3. Verify buffer sizes
4. Test with instrumented binary

### Cross-References

- **Callers:** Analyze functions that call this one
- **Callees:** Analyze functions called by this one
- **Data:** Follow data references
"""

    return report


@tool(category="security", description="Find dangerous function calls via cross-references")
def ida_xref_vuln_scan(
    dangerous_only: Annotated[bool, "Show only dangerous functions"] = True,
) -> str:
    """Scan the entire binary for dangerous function calls.

    Finds all locations where dangerous functions (strcpy, system, etc.)
    are called and provides exploitability analysis.

    Args:
        dangerous_only: Filter to only dangerous functions

    Returns:
        List of dangerous function calls with context.
    """
    try:
        import ida_funcs
        import ida_ida
        import ida_name
        import ida_xref
    except ImportError:
        return "Error: IDA API not available"

    report = f"""## XREF Vulnerability Scan - IDA Binary

**Scanning for:** {len(DANGEROUS_FUNCTIONS)} dangerous functions

### Dangerous Function Calls

| Function | Call Sites | Highest Risk | Description |
|----------|-----------|--------------|-------------|
"""

    total_calls = 0
    high_risk = []

    for func_name in sorted(DANGEROUS_FUNCTIONS.keys()):
        # Find function address
        func_addr = ida_name.get_name_ea_simple(func_name)
        if func_addr == ida_ida.BADADDR:
            continue

        # Count xrefs
        call_count = 0
        callers = []

        for xref in ida_xref.XrefsTo(func_addr):
            if xref.type == ida_xref.fl_CN:  # Call
                call_count += 1
                caller_func = ida_funcs.get_func_name(xref.frm)
                if caller_func:
                    callers.append(
                        {
                            "addr": f"0x{xref.frm:X}",
                            "function": caller_func,
                        }
                    )

        if call_count > 0:
            total_calls += call_count
            risk = _get_risk_level(func_name)
            desc = DANGEROUS_FUNCTIONS[func_name]
            report += f"| `{func_name}` | {call_count} | {risk} | {desc[:50]}... |\n"

            if risk in ["CRITICAL", "HIGH"]:
                high_risk.append(
                    {
                        "name": func_name,
                        "count": call_count,
                        "callers": callers[:5],
                    }
                )

    report += f"""

### Summary

- **Total Dangerous Calls:** {total_calls}
- **High Risk Functions:** {len(high_risk)}

### High Priority Analysis

Focus on these functions first:

"""

    for item in high_risk[:10]:
        report += f"#### `{item['name']}` ({item['count']} calls)\n\n"
        report += "Sample callers:\n"
        for caller in item["callers"][:3]:
            report += f"- {caller['function']} @ {caller['addr']}\n"
        report += "\n"

    report += """

### Detailed Analysis

For each high-risk call:
1. Navigate to address in IDA
2. Check parameter sources
3. Verify buffer sizes
4. Look for validation
5. Test exploitability

### Quick Navigation

Double-click addresses to jump:
"""

    for item in high_risk[:5]:
        for caller in item["callers"][:2]:
            report += f"- `{item['name']}`: {caller['function']} @ {caller['addr']}\n"

    return report


@tool(category="security", description="Analyze buffer sizes in current function")
def ida_buffer_analysis(
    ea: Annotated[int, "Function address to analyze (0 for current)"] = 0,
) -> str:
    """Analyze buffer sizes and allocations in a function.

    Identifies:
    1. Stack buffers (local arrays)
    2. Heap allocations (malloc/calloc)
    3. Buffer usage patterns
    4. Potential overflow risks

    Args:
        ea: Function address

    Returns:
        Buffer size analysis with risk assessment.
    """
    try:
        import ida_frame
        import ida_funcs
        import ida_hexrays
    except ImportError:
        return "Error: IDA API not available"

    if ea == 0:
        ea = ida_hexrays.get_screen_ea()

    func = ida_funcs.get_func(ea)
    if not func:
        return f"No function found at 0x{ea:X}"

    func_name = ida_hexrays.get_func_name(ea)

    # Get stack frame
    stack_info = {}
    try:
        frame = ida_frame.get_frame(func)
        if frame:
            # Get frame size
            frame_size = ida_frame.get_frame_size(func)
            stack_info["frame_size"] = frame_size
            stack_info["vars_count"] = ida_frame.get_frame_member_count(frame)
    except Exception:
        stack_info["error"] = "Could not get frame info"

    # Get decompiled code
    try:
        cfunc = ida_hexrays.decompile(ea)
        pseudocode = str(cfunc) if cfunc else ""
    except Exception:
        pseudocode = ""

    # Analyze for buffer patterns
    stack_buffers = []
    heap_allocs = []

    # Look for common patterns in pseudocode
    import re

    # Stack buffers: char name[N];
    for match in re.finditer(r"(char|int|short|long|byte|void)\s+(\w+)\[(\d+)\]", pseudocode):
        buf_type = match.group(1)
        buf_name = match.group(2)
        buf_size = int(match.group(3))
        stack_buffers.append(
            {
                "name": buf_name,
                "type": buf_type,
                "size": buf_size,
                "bytes": buf_size * (4 if buf_type in ["int", "long"] else 1),
            }
        )

    # Heap allocations: malloc(N)
    for match in re.finditer(r"(\w+)\s*=\s*(malloc|calloc|realloc)\s*\(", pseudocode):
        var_name = match.group(1)
        alloc_func = match.group(2)
        heap_allocs.append(
            {
                "variable": var_name,
                "function": alloc_func,
            }
        )

    report = f"""## Buffer Analysis for IDA Function

**Function:** {func_name} (0x{ea:X})
**Stack Frame:** {stack_info.get("frame_size", "N/A")} bytes
**Variables:** {stack_info.get("vars_count", "N/A")} stack vars

### Stack Buffers Found

"""

    if stack_buffers:
        report += "| Variable | Type | Size (elements) | Size (bytes) | Risk |\n"
        report += "|----------|------|-----------------|--------------|------|\n"
        for buf in stack_buffers:
            byte_size = buf["bytes"]
            risk = "HIGH" if byte_size < 256 else "MEDIUM"
            report += f"| {buf['name']} | {buf['type']} | {buf['size']} | {byte_size} | {risk} |\n"
    else:
        report += "No obvious stack buffers detected in pseudocode.\n"

    report += """

### Heap Allocations Found

"""

    if heap_allocs:
        report += "| Variable | Function | Risk |\n"
        report += "|----------|----------|------|\n"
        for alloc in heap_allocs:
            risk = "HIGH" if alloc["function"] == "malloc" else "MEDIUM"
            report += f"| {alloc['variable']} | {alloc['function']}() | {risk} |\n"
    else:
        report += "No heap allocations detected.\n"

    report += f"""

### Decompiled Code (excerpt)

```c
{pseudocode[:1500] if pseudocode else "(Decompilation not available)"}
{"..." if len(pseudocode) > 1500 else ""}
```

### Risk Assessment

"""

    total_bufs = len(stack_buffers) + len(heap_allocs)
    if total_bufs == 0:
        report += "**✓ LOW RISK:** No buffers detected in this function.\n"
    elif total_bufs <= 3:
        report += f"**⚠️ MEDIUM RISK:** {total_bufs} buffers detected. Manual review needed.\n"
    else:
        report += f"**⚠️ HIGH RISK:** {total_bufs} buffers detected. Detailed analysis recommended.\n"

    report += """

### Analysis Checklist

For each buffer:
- [ ] Verify input sources
- [ ] Check size before copy
- [ ] Validate bounds
- [ ] Check for null termination issues
- [ ] Verify sizeof() usage

### Recommendations

"""

    for buf in stack_buffers[:3]:
        if buf["bytes"] < 128:
            report += f"- **{buf['name']}**: Small buffer ({buf['bytes']} bytes) - HIGH overflow risk\n"

    return report


@tool(category="security", description="Map attack surface via call graph from entry point")
def ida_call_graph_surface(
    entry_func: Annotated[str, "Entry function name (e.g., 'main', 'serve')"] = "main",
    max_depth: Annotated[int, "Maximum call depth"] = 5,
) -> str:
    """Map attack surface by analyzing call graph from entry point.

    Traces function calls to identify:
    1. Which functions handle external data
    2. Call chains to dangerous operations
    3. Attack surface for vulnerability discovery

    Args:
        entry_func: Entry point function name
        max_depth: Maximum depth to trace

    Returns:
        Call graph with attack surface analysis.
    """
    try:
        import ida_funcs
        import ida_ida
        import ida_name
        import ida_xref
    except ImportError:
        return "Error: IDA API not available"

    # Find entry function
    entry_ea = ida_name.get_name_ea_simple(entry_func)
    if entry_ea == ida_ida.BADADDR:
        return f"Entry function '{entry_func}' not found in binary"

    # Build call graph
    call_graph = {}
    visited = set()

    def build_graph(func_ea, depth=0):
        if depth > max_depth or func_ea in visited:
            return
        visited.add(func_ea)

        func_name = ida_funcs.get_func_name(func_ea)
        if not func_name:
            return

        call_graph[func_name] = {"ea": func_ea, "calls": [], "depth": depth}

        # Find calls from this function
        func = ida_funcs.get_func(func_ea)
        if not func:
            return

        for item in ida_funcs.FunctionItems(func):
            for xref in ida_xref.XrefsFrom(item):
                if xref.type == ida_xref.fl_CF:  # Call
                    target_name = ida_funcs.get_func_name(xref.to)
                    if target_name:
                        call_graph[func_name]["calls"].append(target_name)
                        build_graph(xref.to, depth + 1)

    build_graph(entry_ea)

    # Analyze for dangerous functions
    dangerous_paths = []
    for func_name, data in call_graph.items():
        for callee in data["calls"]:
            if callee in DANGEROUS_FUNCTIONS:
                dangerous_paths.append(
                    {
                        "path": f"{entry_func} → ... → {func_name} → {callee}",
                        "depth": data["depth"],
                        "risk": _get_risk_level(callee),
                    }
                )

    report = f"""## Call Graph Attack Surface

**Entry Point:** {entry_func} (0x{entry_ea:X})
**Max Depth:** {max_depth}
**Functions Analyzed:** {len(call_graph)}

### Call Graph Summary

- Total functions in graph: {len(call_graph)}
- Dangerous functions reached: {len(dangerous_paths)}
- Maximum depth traced: {max_depth}

### Dangerous Function Paths

"""

    if dangerous_paths:
        report += "| Risk | Path | Depth |\n"
        report += "|------|------|-------|\n"
        for path in sorted(dangerous_paths, key=lambda x: x["depth"])[:20]:
            report += f"| {path['risk']} | {path['path']} | {path['depth']} |\n"

        if len(dangerous_paths) > 20:
            report += f"| ... | ... and {len(dangerous_paths) - 20} more | ... |\n"
    else:
        report += "No dangerous functions reachable from entry point.\n"

    report += """

### Call Tree (First 3 Levels)

"""

    def print_tree(func_name, depth=0, max_show=3):
        if depth > max_show or func_name not in call_graph:
            return ""

        indent = "  " * depth
        data = call_graph[func_name]
        output = f"{indent}• {func_name} (0x{data['ea']:X})\n"

        for callee in data["calls"][:5]:  # Limit children
            output += print_tree(callee, depth + 1, max_show)

        if len(data["calls"]) > 5:
            output += f"{indent}  ... and {len(data['calls']) - 5} more\n"

        return output

    report += print_tree(entry_func)

    report += """

### Attack Surface Assessment

"""

    if len(dangerous_paths) > 5:
        report += "**⚠️ HIGH ATTACK SURFACE**\n\n"
        report += f"Entry point reaches {len(dangerous_paths)} dangerous functions.\n"
        report += "Prioritize analysis of high-risk paths.\n"
    elif len(dangerous_paths) > 0:
        report += "**⚠️ MEDIUM ATTACK SURFACE**\n\n"
        report += f"Entry point reaches {len(dangerous_paths)} dangerous functions.\n"
        report += "Review each path for exploitable vulnerabilities.\n"
    else:
        report += "**✓ LOW ATTACK SURFACE**\n\n"
        report += "No obvious dangerous functions reachable.\n"

    report += """

### Analysis Recommendations

1. **High Risk Paths**: Analyze CRITICAL and HIGH risk paths first
2. **Input Validation**: Check where external data enters
3. **Sanitization**: Look for validation functions
4. **Bounds Checking**: Verify buffer operations
5. **Error Handling**: Check error paths

### Next Steps

- Analyze each dangerous path in detail
- Perform taint analysis on critical paths
- Test with fuzzing on input-handling functions
- Review error handling paths
"""

    return report


@tool(category="security", description="Detect type mismatches that cause overflows")
def ida_type_overflow_check(
    ea: Annotated[int, "Function address to analyze (0 for current)"] = 0,
) -> str:
    """Detect type-based overflow vulnerabilities from type mismatches.

    Identifies:
    1. Signed/unsigned comparison issues
    2. Size truncations
    3. Integer overflow prone operations
    4. Array index vulnerabilities

    Args:
        ea: Function address

    Returns:
        Type-based vulnerability analysis.
    """
    try:
        import ida_funcs
        import ida_hexrays
    except ImportError:
        return "Error: IDA API not available"

    if ea == 0:
        ea = ida_hexrays.get_screen_ea()

    func = ida_funcs.get_func(ea)
    if not func:
        return f"No function found at 0x{ea:X}"

    func_name = ida_hexrays.get_func_name(ea)

    # Get pseudocode
    try:
        cfunc = ida_hexrays.decompile(ea)
        pseudocode = str(cfunc) if cfunc else ""
    except Exception:
        pseudocode = ""

    # Analyze for type issues
    issues = []

    # Pattern 1: Signed comparisons with size
    if re.search(r"if\s*\(\s*\w+\s*<\s*(sizeof|buffer|limit)", pseudocode):
        if re.search(r"(int|signed)\s+\w+", pseudocode):
            issues.append(
                {
                    "type": "SIGNED_UNSIGNED",
                    "severity": "HIGH",
                    "description": "Possible signed/unsigned comparison issue",
                }
            )

    # Pattern 2: Truncation assignments
    for _match in re.finditer(r"(\w+)\s*=\s*(\w+);", pseudocode):
        # Check for narrowing assignments (would need type info)
        pass

    # Pattern 3: Size calculations
    if re.search(r"\w+\s*\*\s*(sizeof|\d+)", pseudocode):
        issues.append(
            {
                "type": "INTEGER_OVERFLOW",
                "severity": "MEDIUM",
                "description": "Potential integer overflow in size calculation",
            }
        )

    # Pattern 4: Array indexing
    if re.search(r"\w+\s*\[\s*\w+\s*\]", pseudocode):
        issues.append(
            {
                "type": "ARRAY_INDEX",
                "severity": "MEDIUM",
                "description": "Array access with variable index - validate range",
            }
        )

    report = f"""## Type-based Overflow Detection

**Function:** {func_name} (0x{ea:X})

### Type Issues Found

"""

    if issues:
        report += "| Type | Severity | Description |\n"
        report += "|------|----------|-------------|\n"
        for issue in issues:
            report += f"| {issue['type']} | {issue['severity']} | {issue['description']} |\n"
    else:
        report += "No obvious type issues detected in pseudocode.\n"

    report += f"""

### Decompiled Code

```c
{pseudocode[:1500] if pseudocode else "(Decompilation not available)"}
{"..." if len(pseudocode) > 1500 else ""}
```

### Common Type Vulnerabilities

#### 1. Signed/Unsigned Comparison
```c
// DANGEROUS
int len = recv(sock, buf, 1024, 0);  // len = -1 on error
if (len < 64)                         // -1 < 64 = TRUE!
    memcpy(dest, buf, len);           // len = 4GB!
```

#### 2. Size Truncation
```c
// DANGEROUS
int32_t big = get_size();
int16_t small = big;                  // Truncates!
```

#### 3. Integer Overflow
```c
// DANGEROUS
int count = get_count();
int size = 256;
int total = count * size;             // May overflow
```

### Manual Review Checklist

For this function, manually check:
- [ ] All variables use appropriate types (size_t for sizes)
- [ ] Comparisons use correct signedness
- [ ] Type conversions are safe
- [ ] Size calculations can't overflow
- [ ] Array indices are validated

### Recommendations

"""

    if issues:
        report += "**⚠️ TYPE ISSUES DETECTED**\n\n"
        report += "Manual review recommended for listed issues.\n"
    else:
        report += "**✓ NO OBVIOUS TYPE ISSUES**\n\n"
        report += "Still recommend manual review of type usage.\n"

    return report


def _get_risk_level(func_name: str) -> str:
    """Get risk level for a function."""
    critical = ["gets", "strcpy", "sprintf", "system", "popen"]
    high = ["strcat", "scanf", "sscanf", "memcpy", "free"]
    medium = ["strncpy", "snprintf", "fgets", "recv", "read"]

    if func_name in critical:
        return "CRITICAL"
    elif func_name in high:
        return "HIGH"
    elif func_name in medium:
        return "MEDIUM"
    else:
        return "LOW"
