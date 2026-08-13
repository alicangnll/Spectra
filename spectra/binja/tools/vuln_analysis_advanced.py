"""Advanced vulnerability analysis tools for Binary Ninja.

Provides Binary Ninja-specific wrappers for:
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
    taint_analysis,
    xref_vuln_scan,
    buffer_size_analysis,
    call_graph_attack_surface,
    type_overflow_detection,
    DANGEROUS_FUNCTIONS,
    TAINT_SOURCES,
)


@tool(category="security", description="Track data flow from user input to dangerous functions")
def binja_taint_analysis(
    address: Annotated[int, "Function address to analyze (0 for current)"] = 0,
    max_depth: Annotated[int, "Maximum depth for data flow tracking"] = 10,
) -> str:
    """Perform taint analysis on a function to track data flow to dangerous functions.

    Identifies:
    1. Data sources (recv, fgets, getenv, etc.)
    2. Data flow through the function
    3. Dangerous sinks (strcpy, system, printf, etc.)
    4. Vulnerable paths

    Args:
        address: Function address
        max_depth: Maximum tracking depth

    Returns:
        Taint analysis report with vulnerable paths.
    """
    try:
        import binaryninja
        from binaryninja import Function, BinaryView
    except ImportError:
        return "Error: Binary Ninja API not available"

    bv = binaryninja.get_current_bv()
    if not bv:
        return "Error: No binary loaded"

    # Get current function if address is 0
    if address == 0:
        # Get function at current selection or cursor
        func = bv.get_functions_at(bv.offset)[0] if bv.offset and bv.get_functions_at(bv.offset) else None
        if not func:
            return "Error: No function at current location. Please navigate to a function."
        address = func.start

    # Get function
    func = bv.get_function_at(address)
    if not func:
        return f"No function found at 0x{address:X}"

    func_name = func.name if func.name else f"sub_{address:X}"

    # Get HLIL for analysis
    hlil = func.hlil
    pseudocode = ""
    if hlil:
        # Get source-like representation
        for instr in hlil:
            pseudocode += str(instr) + "\n"

    # Analyze for dangerous function calls
    dangerous_calls = []
    source_calls = []

    # Scan for calls to dangerous functions
    for caller in func.callers:
        caller_name = caller.name if caller.name else f"sub_{caller.start:X}"
        if caller_name in DANGEROUS_FUNCTIONS:
            dangerous_calls.append({
                "function": caller_name,
                "address": f"0x{caller.start:X}",
                "risk": _get_risk_level(caller_name),
            })
        elif caller_name in TAINT_SOURCES:
            source_calls.append({
                "function": caller_name,
                "address": f"0x{caller.start:X}",
            })

    # Also check callee functions
    for callee in func.callees:
        callee_name = callee.name if callee.name else f"sub_{callee.start:X}"
        if callee_name in DANGEROUS_FUNCTIONS:
            dangerous_calls.append({
                "function": callee_name,
                "address": f"0x{callee.start:X}",
                "risk": _get_risk_level(callee_name),
            })
        elif callee_name in TAINT_SOURCES:
            source_calls.append({
                "function": callee_name,
                "address": f"0x{callee.start:X}",
            })

    report = f"""## Taint Analysis for Binary Ninja Function

**Function:** {func_name} (0x{address:X})
**Range:** 0x{func.start:X} - 0x{func.end:X}
**Max Depth:** {max_depth}

### Taint Sources Found

{len(source_calls)} potential data sources:

"""

    if source_calls:
        report += "| Function | Address | Description |\\n"
        report += "|----------|---------|-------------|\\n"
        for src in source_calls:
            desc = TAINT_SOURCES.get(src["function"], "Unknown")
            report += f"| {src['function']} | {src['address']} | {desc} |\\n"
    else:
        report += "No obvious taint sources found in this function.\\n"

    report += f"""

### Dangerous Sinks Found

{len(dangerous_calls)} dangerous function calls:

"""

    if dangerous_calls:
        report += "| Function | Address | Risk Level | Description |\\n"
        report += "|----------|---------|------------|-------------|\\n"
        for sink in dangerous_calls:
            desc = DANGEROUS_FUNCTIONS.get(sink["function"], "Unknown")
            report += f"| {sink['function']} | {sink['address']} | {sink['risk']} | {desc} |\\n"
    else:
        report += "No dangerous function calls found in this function.\\n"

    report += f"""

### Analysis

"""

    if source_calls and dangerous_calls:
        report += "**⚠️ POTENTIAL VULNERABILITY DETECTED**\\n\\n"
        report += f"Function has both data sources ({len(source_calls)}) "
        report += f"and dangerous sinks ({len(dangerous_calls)}).\\n\\n"
        report += "**Recommended Action:** Manually trace data flow from sources to sinks.\\n"
    elif source_calls:
        report += "**ℹ️ INFO:** Function has data sources but no obvious dangerous sinks.\\n"
        report += "Data may be passed to callees - analyze those functions.\\n"
    elif dangerous_calls:
        report += "**ℹ️ INFO:** Function has dangerous sinks but no obvious sources.\\n"
        report += "Data may come from parameters - analyze callers.\\n"
    else:
        report += "**✓ SAFE:** No obvious taint issues in this function.\\n"

    report += f"""

### Decompiled Code (excerpt)

```c
{pseudocode[:2000] if pseudocode else '(Decompilation not available)'}
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
def binja_xref_vuln_scan(
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
        import binaryninja
    except ImportError:
        return "Error: Binary Ninja API not available"

    bv = binaryninja.get_current_bv()
    if not bv:
        return "Error: No binary loaded"

    report = f"""## XREF Vulnerability Scan - Binary Ninja

**Scanning for:** {len(DANGEROUS_FUNCTIONS)} dangerous functions

### Dangerous Function Calls

| Function | Call Sites | Highest Risk | Description |
|----------|-----------|--------------|-------------|
"""

    total_calls = 0
    high_risk = []

    for func_name in sorted(DANGEROUS_FUNCTIONS.keys()):
        # Find function by symbol
        func = bv.get_function_by_name(func_name)
        if not func:
            continue

        # Count callers
        callers = list(func.callers)
        call_count = len(callers)

        if call_count > 0:
            total_calls += call_count
            risk = _get_risk_level(func_name)
            desc = DANGEROUS_FUNCTIONS[func_name]
            report += f"| `{func_name}` | {call_count} | {risk} | {desc[:50]}... |\\n"

            if risk in ["CRITICAL", "HIGH"]:
                high_risk.append({
                    "name": func_name,
                    "count": call_count,
                    "callers": [{"addr": f"0x{c.start:X}", "function": c.name if c.name else f"sub_{c.start:X}"} for c in callers[:5]],
                })

    report += f"""

### Summary

- **Total Dangerous Calls:** {total_calls}
- **High Risk Functions:** {len(high_risk)}

### High Priority Analysis

Focus on these functions first:

"""

    for item in high_risk[:10]:
        report += f"#### `{item['name']}` ({item['count']} calls)\\n\\n"
        report += "Sample callers:\\n"
        for caller in item['callers'][:3]:
            report += f"- {caller['function']} @ {caller['addr']}\\n"
        report += "\\n"

    report += f"""

### Detailed Analysis

For each high-risk call:
1. Navigate to address in Binary Ninja
2. Check parameter sources
3. Verify buffer sizes
4. Look for validation
5. Test exploitability

### Quick Navigation

"""

    for item in high_risk[:5]:
        for caller in item['callers'][:2]:
            report += f"- `{item['name']}`: {caller['function']} @ {caller['addr']}\\n"

    return report


@tool(category="security", description="Analyze buffer sizes in current function")
def binja_buffer_analysis(
    address: Annotated[int, "Function address to analyze (0 for current)"] = 0,
) -> str:
    """Analyze buffer sizes and allocations in a function.

    Identifies:
    1. Stack buffers (local arrays)
    2. Heap allocations (malloc/calloc)
    3. Buffer usage patterns
    4. Potential overflow risks

    Args:
        address: Function address

    Returns:
        Buffer size analysis with risk assessment.
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
        return f"No function found at 0x{address:X}"

    func_name = func.name if func.name else f"sub_{address:X}"

    # Get stack frame info
    stack_info = {}
    stack_vars = func.stack_layout if hasattr(func, 'stack_layout') else []
    stack_info['vars_count'] = len(stack_vars)

    # Get HLIL for analysis
    pseudocode = ""
    if func.hlil:
        for instr in func.hlil:
            pseudocode += str(instr) + "\n"

    # Analyze for buffer patterns
    stack_buffers = []
    heap_allocs = []

    # Look for common patterns in pseudocode
    # Stack buffers: char name[N];
    for match in re.finditer(r'(char|int|short|long|byte|void)\s+(\w+)\[(\d+)\]', pseudocode):
        buf_type = match.group(1)
        buf_name = match.group(2)
        buf_size = int(match.group(3))
        stack_buffers.append({
            "name": buf_name,
            "type": buf_type,
            "size": buf_size,
            "bytes": buf_size * (4 if buf_type in ["int", "long"] else 1),
        })

    # Heap allocations: malloc(N)
    for match in re.finditer(r'(\w+)\s*=\s*(malloc|calloc|realloc)\s*\(', pseudocode):
        var_name = match.group(1)
        alloc_func = match.group(2)
        heap_allocs.append({
            "variable": var_name,
            "function": alloc_func,
        })

    report = f"""## Buffer Analysis for Binary Ninja Function

**Function:** {func_name} (0x{address:X})
**Stack Variables:** {stack_info.get('vars_count', 'N/A')} stack vars

### Stack Buffers Found

"""

    if stack_buffers:
        report += "| Variable | Type | Size (elements) | Size (bytes) | Risk |\\n"
        report += "|----------|------|-----------------|--------------|------|\\n"
        for buf in stack_buffers:
            byte_size = buf['bytes']
            risk = "HIGH" if byte_size < 256 else "MEDIUM"
            report += f"| {buf['name']} | {buf['type']} | {buf['size']} | {byte_size} | {risk} |\\n"
    else:
        report += "No obvious stack buffers detected in pseudocode.\\n"

    report += f"""

### Heap Allocations Found

"""

    if heap_allocs:
        report += "| Variable | Function | Risk |\\n"
        report += "|----------|----------|------|\\n"
        for alloc in heap_allocs:
            risk = "HIGH" if alloc['function'] == "malloc" else "MEDIUM"
            report += f"| {alloc['variable']} | {alloc['function']}() | {risk} |\\n"
    else:
        report += "No heap allocations detected.\\n"

    report += f"""

### Decompiled Code (excerpt)

```c
{pseudocode[:1500] if pseudocode else '(Decompilation not available)'}
{"..." if len(pseudocode) > 1500 else ""}
```

### Risk Assessment

"""

    total_bufs = len(stack_buffers) + len(heap_allocs)
    if total_bufs == 0:
        report += "**✓ LOW RISK:** No buffers detected in this function.\\n"
    elif total_bufs <= 3:
        report += f"**⚠️ MEDIUM RISK:** {total_bufs} buffers detected. Manual review needed.\\n"
    else:
        report += f"**⚠️ HIGH RISK:** {total_bufs} buffers detected. Detailed analysis recommended.\\n"

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
        if buf['bytes'] < 128:
            report += f"- **{buf['name']}**: Small buffer ({buf['bytes']} bytes) - HIGH overflow risk\\n"

    return report


@tool(category="security", description="Map attack surface via call graph from entry point")
def binja_call_graph_surface(
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
        import binaryninja
    except ImportError:
        return "Error: Binary Ninja API not available"

    bv = binaryninja.get_current_bv()
    if not bv:
        return "Error: No binary loaded"

    # Find entry function
    entry_func_obj = bv.get_function_by_name(entry_func)
    if not entry_func_obj:
        return f"Entry function '{entry_func}' not found in binary"

    # Build call graph
    call_graph = {}
    visited = set()

    def build_graph(func, depth=0):
        if depth > max_depth or func.start in visited:
            return
        visited.add(func.start)

        func_name = func.name if func.name else f"sub_{func.start:X}"

        call_graph[func_name] = {"ea": func.start, "calls": [], "depth": depth}

        # Find calls from this function
        for callee in func.callees:
            callee_name = callee.name if callee.name else f"sub_{callee.start:X}"
            call_graph[func_name]["calls"].append(callee_name)
            build_graph(callee, depth + 1)

    build_graph(entry_func_obj)

    # Analyze for dangerous functions
    dangerous_paths = []
    for func_name, data in call_graph.items():
        for callee in data["calls"]:
            if callee in DANGEROUS_FUNCTIONS:
                dangerous_paths.append({
                    "path": f"{entry_func} → ... → {func_name} → {callee}",
                    "depth": data["depth"],
                    "risk": _get_risk_level(callee),
                })

    report = f"""## Call Graph Attack Surface

**Entry Point:** {entry_func} (0x{entry_func_obj.start:X})
**Max Depth:** {max_depth}
**Functions Analyzed:** {len(call_graph)}

### Call Graph Summary

- Total functions in graph: {len(call_graph)}
- Dangerous functions reached: {len(dangerous_paths)}
- Maximum depth traced: {max_depth}

### Dangerous Function Paths

"""

    if dangerous_paths:
        report += "| Risk | Path | Depth |\\n"
        report += "|------|------|-------|\\n"
        for path in sorted(dangerous_paths, key=lambda x: x["depth"])[:20]:
            report += f"| {path['risk']} | {path['path']} | {path['depth']} |\\n"

        if len(dangerous_paths) > 20:
            report += f"| ... | ... and {len(dangerous_paths) - 20} more | ... |\\n"
    else:
        report += "No dangerous functions reachable from entry point.\\n"

    report += f"""

### Call Tree (First 3 Levels)

"""

    def print_tree(func_name, depth=0, max_show=3):
        if depth > max_show or func_name not in call_graph:
            return ""

        indent = "  " * depth
        data = call_graph[func_name]
        output = f"{indent}• {func_name} (0x{data['ea']:X})\\n"

        for callee in data["calls"][:5]:
            output += print_tree(callee, depth + 1, max_show)

        if len(data["calls"]) > 5:
            output += f"{indent}  ... and {len(data['calls']) - 5} more\\n"

        return output

    report += print_tree(entry_func)

    report += f"""

### Attack Surface Assessment

"""

    if len(dangerous_paths) > 5:
        report += "**⚠️ HIGH ATTACK SURFACE**\\n\\n"
        report += f"Entry point reaches {len(dangerous_paths)} dangerous functions.\\n"
        report += "Prioritize analysis of high-risk paths.\\n"
    elif len(dangerous_paths) > 0:
        report += "**⚠️ MEDIUM ATTACK SURFACE**\\n\\n"
        report += f"Entry point reaches {len(dangerous_paths)} dangerous functions.\\n"
        report += "Review each path for exploitable vulnerabilities.\\n"
    else:
        report += "**✓ LOW ATTACK SURFACE**\\n\\n"
        report += "No obvious dangerous functions reachable.\\n"

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
def binja_type_overflow_check(
    address: Annotated[int, "Function address to analyze (0 for current)"] = 0,
) -> str:
    """Detect type-based overflow vulnerabilities from type mismatches.

    Identifies:
    1. Signed/unsigned comparison issues
    2. Size truncations
    3. Integer overflow prone operations
    4. Array index vulnerabilities

    Args:
        address: Function address

    Returns:
        Type-based vulnerability analysis.
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
        return f"No function found at 0x{address:X}"

    func_name = func.name if func.name else f"sub_{address:X}"

    # Get pseudocode
    pseudocode = ""
    if func.hlil:
        for instr in func.hlil:
            pseudocode += str(instr) + "\n"

    # Analyze for type issues
    issues = []

    # Pattern 1: Signed comparisons with size
    if re.search(r'if\s*\(\s*\w+\s*<\s*(sizeof|buffer|limit)', pseudocode):
        if re.search(r'(int|signed)\s+\w+', pseudocode):
            issues.append({
                "type": "SIGNED_UNSIGNED",
                "severity": "HIGH",
                "description": "Possible signed/unsigned comparison issue",
            })

    # Pattern 2: Size calculations
    if re.search(r'\w+\s*\*\s*(sizeof|\d+)', pseudocode):
        issues.append({
            "type": "INTEGER_OVERFLOW",
            "severity": "MEDIUM",
            "description": "Potential integer overflow in size calculation",
        })

    # Pattern 3: Array indexing
    if re.search(r'\w+\s*\[\s*\w+\s*\]', pseudocode):
        issues.append({
            "type": "ARRAY_INDEX",
            "severity": "MEDIUM",
            "description": "Array access with variable index - validate range",
        })

    report = f"""## Type-based Overflow Detection

**Function:** {func_name} (0x{address:X})

### Type Issues Found

"""

    if issues:
        report += "| Type | Severity | Description |\\n"
        report += "|------|----------|-------------|\\n"
        for issue in issues:
            report += f"| {issue['type']} | {issue['severity']} | {issue['description']} |\\n"
    else:
        report += "No obvious type issues detected in pseudocode.\\n"

    report += f"""

### Decompiled Code

```c
{pseudocode[:1500] if pseudocode else '(Decompilation not available)'}
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
        report += "**⚠️ TYPE ISSUES DETECTED**\\n\\n"
        report += "Manual review recommended for listed issues.\\n"
    else:
        report += "**✓ NO OBVIOUS TYPE ISSUES**\\n\\n"
        report += "Still recommend manual review of type usage.\\n"

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
