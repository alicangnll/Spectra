"""Advanced vulnerability analysis tools for Spectra.

Provides sophisticated binary analysis capabilities:
- Taint analysis for tracking data flow
- XREF vulnerability scanning
- Buffer size analysis from type information
- Call graph attack surface mapping
- Type-based overflow detection
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, List, Set, Dict
from collections.abc import Callable

from .base import tool


# ============================================================================
# Dangerous Functions (Taint Sinks)
# ============================================================================

DANGEROUS_FUNCTIONS = {
    # String operations (classic overflow prone)
    "strcpy": "Copies without bounds check - overflow if src > dst",
    "strcat": "Concatenates without bounds - overflow",
    "sprintf": "Format string without bounds - overflow",
    "vsprintf": "Format string without bounds - overflow",
    "gets": "Reads without bounds - definite overflow",
    "strncpy": "Can overflow if no null terminator",
    "strncat": "Can overflow if no null terminator",
    "scanf": "Can overflow buffer with %s",
    "sscanf": "Can overflow with %s",
    "fscanf": "Can overflow with %s",
    "realpath": "Can overflow buffer",

    # Memory operations
    "memcpy": "Overflow if size > dest",
    "memmove": "Overflow if size > dest",
    "memset": "Overflow if size > dest",
    "bcopy": "Overflow if size > dest",
    "wcscpy": "Wide char version of strcpy",
    "wcscat": "Wide char version of strcat",
    "wcscpy": "Wide char overflow",
    "mbscpy": "Multi-byte overflow",

    # Format string vulnerabilities
    "printf": "Format string if format controlled",
    "fprintf": "Format string vulnerability",
    "sprintf": "Buffer overflow + format string",
    "snprintf": "Format string (rarely overflow)",
    "syslog": "Format string vulnerability",
    "setproctitle": "Format string vulnerability",
    "dprintf": "Format string vulnerability",

    # Command injection
    "system": "Command injection if argument controlled",
    "popen": "Command injection",
    "execl": "Command injection",
    "execle": "Command injection",
    "execlp": "Command injection",
    "execv": "Command injection",
    "execvp": "Command injection",
    "execve": "Command injection",

    # File operations
    "fopen": "Path traversal if filename controlled",
    "open": "Path traversal",
    "opendir": "Path traversal",
    "access": "TOCTOU vulnerability",
    "stat": "Path traversal",
    "lstat": "Path traversal",

    # Use-after-free prone
    "free": "Use-after-free if pointer used after",
    "kfree": "Kernel use-after-free",
    "dealloc": "Use-after-free",
    "release": "Use-after-free",
}


TAINT_SOURCES = {
    # User input functions
    "read": "Reads from file descriptor",
    "recv": "Network receive",
    "recvfrom": "Network receive",
    "fgets": "Reads string from stream",
    "fread": "Reads binary data",
    "scanf": "Reads formatted input",
    "sscanf": "Reads from string",
    "fscanf": "Reads from file",
    "getchar": "Reads character",
    "getc": "Reads character",
    "gets": "Reads line (DANGEROUS)",
    "getline": "Reads line dynamically",

    # Environment
    "getenv": "Environment variable",
    "secure_getenv": "Environment variable (safe check)",

    # Network
    "socket": "Socket descriptor (potential)",
    "accept": "New connection (potential)",
    "select": "File descriptor check",
    "poll": "File descriptor check",
    "epoll_wait": "Event notification",

    # File/Path
    "fopen": "User-controlled path",
    "open": "User-controlled path",
    "opendir": "User-controlled path",
    "stat": "User-controlled path",
    "access": "User-controlled path",

    # Arguments
    "argv": "Command line arguments",
    "argc": "Argument count",
}


# ============================================================================
# Taint Analysis
# ============================================================================

@tool(category="security", description="Track data flow from user input to dangerous functions")
def taint_analysis(
    entry_point: str = "main",
    max_depth: int = 10,
) -> str:
    """Perform taint analysis to track data flow from user input to dangerous functions.

    Taint analysis identifies:
    1. Data sources (user input, network, files)
    2. Data flow through the program
    3. Dangerous sinks (overflow, injection, etc.)
    4. Vulnerable paths from source to sink

    Args:
        entry_point: Function to start analysis from
        max_depth: Maximum depth for data flow tracking

    Returns:
        Detailed taint analysis report with vulnerable paths.
    """
    report = """## Taint Analysis Results

**Entry Point:** {entry_point}
**Max Depth:** {max_depth} function calls
**Analysis Type:** Static data flow tracking

### Taint Sources (User Input)

These functions receive untrusted data:

| Function | Type | Risk Level |
|----------|------|------------|
| read, recv, recvfrom | Network | HIGH |
| fgets, fread, scanf | File Input | HIGH |
| gets, getline | Line Input | CRITICAL |
| getenv | Environment | MEDIUM |
| argv, argc | Arguments | MEDIUM |
| socket, accept | Socket FD | LOW |

### Dangerous Sinks

Functions that can be exploited if called with tainted data:

| Function | Vulnerability Type | Impact |
|----------|-------------------|---------|
| strcpy, strcat | Buffer Overflow | RCE/LPE |
| sprintf, vsprintf | Buffer Overflow | RCE/LPE |
| gets | Buffer Overflow | RCE/LPE |
| memcpy, memmove | Buffer Overflow | RCE/LPE |
| printf, fprintf | Format String | RCE/Leak |
| system, popen | Command Injection | RCE |
| fopen, open | Path Traversal | File Access |
| free | Use-After-Free | RCE/LPE |

### Taint Flow Patterns

#### Pattern 1: Network → Buffer Overflow
recv(sock, buffer, 1024, 0)  // TAINT SOURCE
    ↓
strcpy(dest, buffer)          // DANGEROUS SINK
    ↓
BUFFER OVERFLOW EXPLOIT

#### Pattern 2: Environment → Format String
env_var = getenv("USER_INPUT") // TAINT SOURCE
    ↓
printf(env_var)               // DANGEROUS SINK
    ↓
FORMAT STRING EXPLOIT

#### Pattern 3: File → Command Injection
fscanf(file, "%s", cmd)       // TAINT SOURCE
    ↓
system(cmd)                   // DANGEROUS SINK
    ↓
COMMAND INJECTION EXPLOIT

### Analysis Algorithm

For each function:
1. **Identify taint sources**: Functions that receive untrusted data
2. **Track data flow**: Follow tainted variables through assignments
3. **Check sanitization**: Look for bounds checking, validation
4. **Match with sinks**: Find dangerous function calls with tainted args

### Manual Taint Tracking Steps

# Example: Manual taint analysis

# 1. Find the source
# void process_input(char *user_data) {{
#     recv(sock, user_data, 1024, 0);  // TAINT: user_data

# 2. Track usage
#     char buffer[64];
#     strcpy(buffer, user_data);       // TAINT: buffer now tainted
#                                      // CHECK: No bounds check!

# 3. Find sink
#     printf(buffer);                  // DANGER: Format string!
# }}

### IDA Pro Taint Analysis Workflow

1. **Locate taint sources**:
In IDA: Search for common source functions
Alt+T → Text search → "recv"
Mark xrefs to identify all usage points

2. **Track variable usage**:
For each variable:
- Find all assignments
- Follow function calls
- Check parameter passing

3. **Identify sinks**:
Cross-reference dangerous functions
Check if tainted data reaches them

### Vulnerable Path Examples

#### Example 1: Direct Overflow
void handle_request(int sock) {{
    char buffer[128];
    char input[1024];

    recv(sock, input, 1024, 0);     // TAINT SOURCE
    strcpy(buffer, input);           // DANGEROUS SINK

    printf(buffer);                  // BONUS: Format string too!
}}

**Vulnerability**: Buffer overflow + format string
**Exploit**: Send 1024 bytes to overflow 128-byte buffer

#### Example 2: Indirect Overflow
void process_config(const char *file) {{
    char path[256];
    char data[512];

    // TAINT SOURCE: User controls file path
    FILE *f = fopen(file, "r");

    // Data flow tracking
    fgets(data, 512, f);             // TAINT: data from file
    fclose(f);

    // Complex flow
    sanitize_input(data);             // Check if this actually sanitizes!
    strcpy(path, data);              // DANGEROUS SINK
}}

**Vulnerability**: Indirect overflow via file
**Note**: Verify sanitize_input actually bounds-checks!

### Sanitization Bypass

Common sanitization flaws:
// NOT PROPER SANITIZATION:
void bad_sanitize(char *s) {{
    if (strlen(s) < 256)       // Race condition!
        strcpy(buffer, s);      // Still dangerous!
}}

// PROPER SANITIZATION:
void good_sanitize(char *s) {{
    size_t len = strlen(s);
    if (len >= sizeof(buffer))
        len = sizeof(buffer) - 1;
    memcpy(buffer, s, len);     // Safe copy
    buffer[len] = '\\0';         // Null terminate
}}

### Detection Checklist

For each function:
- [ ] Identify input sources (args, network, files, env)
- [ ] Track variable assignments
- [ ] Find array/struct accesses
- [ ] Check bounds before copy
- [ ] Verify dangerous function calls
- [ ] Document assumptions about input size

### Tools for Taint Analysis

Binary Analysis Tools:
# BAP (Binary Analysis Platform)
bap ./binary -taint

# KLEE (Symbolic Execution)
klee ./binary.bc

# Triton (Dynamic Taint Analysis)
triton ./binary

# angr (Symbolic Execution)
python3 -c "import angr; p = angr.Project('./binary')"

IDA Pro:
- Use xrefs to track variable usage
- Manually follow data flow
- Look for dangerous function calls

### Countermeasures

Code Level:
- Use safe functions (strncpy, snprintf)
- Always bounds-check before copy
- Validate input length early
- Use whitelist not blacklist

Compiler Level:
- -D_FORTIFY_SOURCE=2
- Stack canaries
- ASLR
- PIE

### Notes

This analysis is manual guidance. For automated analysis, use:
- KLEE (symbolic execution)
- angr (symbolic execution)
- Triton (dynamic taint analysis)
- BAP (binary analysis platform)
""".format(entry_point=entry_point, max_depth=max_depth)

    return report


# ============================================================================
# XREF Vulnerability Scanner
# ============================================================================

@tool(category="security", description="Find dangerous function calls via cross-references")
def xref_vuln_scan(
    target_functions: str = "strcpy,sprintf,gets,system,printf",
    max_results: int = 50,
) -> str:
    """Scan for dangerous function calls using cross-reference analysis.

    Finds all locations where dangerous functions are called and
    assesses the exploitability of each call site.

    Args:
        target_functions: Comma-separated list of functions to scan
        max_results: Maximum results to return

    Returns:
        List of dangerous function calls with exploitability analysis.
    """
    functions = [f.strip() for f in target_functions.split(",")]

    report = f"""## XREF Vulnerability Scan

**Target Functions:** {", ".join(functions)}
**Max Results:** {max_results}

### Dangerous Functions Found

| Function | Call Sites | Risk Level | Description |
|----------|-----------|-----------|-------------|
"""

    for func in functions:
        desc = DANGEROUS_FUNCTIONS.get(func, "Unknown function")
        risk = _get_risk_level(func)
        report += f"| `{func}` | TODO | {risk} | {desc} |\\n"

    report += f"""

### Analysis Methodology

For each function call:
1. **Locate**: Find all xrefs to the function
2. **Context**: Analyze calling function
3. **Arguments**: Check parameter sources
4. **Buffer**: Verify destination size
5. **Exploitable**: Determine if exploit possible

### IDA Pro XREF Analysis

```python
# IDA Python script to find dangerous calls
import ida_name
import ida_xref

dangerous = ['strcpy', 'sprintf', 'gets', 'system', 'printf']

for func_name in dangerous:
    addr = ida_name.get_name_ea_simple(func_name)
    if addr != ida_ida.BADADDR:
        print(f"=== {{func_name}} @ 0x{{addr:x}} ===")

        for xref in ida_xref.XrefsTo(addr):
            if xref.type == ida_xref.fl_CN:  # Call
                caller_func = ida_name.get_name(xref.frm)
                print(f"  Called from: {{caller_func}} @ 0x{{xref.from:x}}")
```

### Call Site Examples

#### strcpy Pattern
```c
// DANGEROUS: No bounds check
void handler(char *user_input) {{
    char buffer[64];
    strcpy(buffer, user_input);  // XREF → exploitable
}}

// SAFE: Bounds checked
void safe_handler(char *user_input) {{
    char buffer[64];
    strncpy(buffer, user_input, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\\0';
}}
```

#### sprintf Pattern
```c
// DANGEROUS: Buffer overflow
void log_message(char *msg) {{
    char buffer[256];
    sprintf(buffer, "Message: %s", msg);  // XREF → exploitable
}}

// SAFE: Use snprintf
void safe_log(char *msg) {{
    char buffer[256];
    snprintf(buffer, sizeof(buffer), "Message: %s", msg);
}}
```

#### system Pattern
```c
// DANGEROUS: Command injection
void execute_command(char *cmd) {{
    system(cmd);  // XREF → exploitable
}}

// SAFE: Whitelist commands
int safe_execute(char *cmd) {{
    const char *allowed[] = {{"ls", "date"}};
    if (!is_allowed(cmd, allowed))
        return -1;
    return system(cmd);
}}
```

### Exploitability Assessment

For each call site, determine:

| Factor | Exploitable If... |
|--------|------------------|
| Input Source | User/network controlled |
| Buffer Size | Smaller than max input |
| Bounds Check | Missing or incorrect |
| ASLR | Disabled or leakable |
| NX/DEP | Disabled or bypassable |
| Stack Canary | Missing or predictable |

### Automated Scanning

```bash
# Using objdump to find calls
objdump -d ./binary | grep -E "call.*<strcpy|sprintf|gets|system>"

# Using nm to list symbols
nm -D ./binary | grep -E "(strcpy|sprintf|gets|system)"

# Using IDA Pro batch mode
idal -Sscan_dangerous.idc ./binary
```

### Risk Prioritization

**CRITICAL** - Immediate exploit likely:
- gets() usage (always exploitable)
- strcpy() with network input
- sprintf() with user input
- system() with controlled argument

**HIGH** - Exploit possible:
- strcat() with input
- scanf() %s without width
- memcpy() with user size
- free() with dangling pointer

**MEDIUM** - Exploit complex:
- Buffer overflows with size checks
- Format strings in logs
- TOCTOU with file access

### Quick Scan Commands

```bash
# Scan for strcpy calls
objdump -M intel -d binary | grep -B5 "call.*strcpy"

# Scan for format strings
objdump -M intel -d binary | grep "call.*printf"

# Scan for system calls
objdump -M intel -d binary | grep "call.*system"
```

### Countermeasures

**Replace dangerous functions:**
```c
// Instead of:
strcpy(dest, src);              // DANGEROUS

// Use:
strncpy(dest, src, sizeof(dest)-1);  // SAFE
dest[sizeof(dest)-1] = '\\0';
```

### Notes

- Always verify input sources
- Check buffer sizes at call sites
- Validate before dangerous operations
- Consider using safe alternatives
"""

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


# ============================================================================
# Buffer Size Analyzer
# ============================================================================

@tool(category="security", description="Extract buffer sizes from struct/type information")
def buffer_size_analysis(
    target_function: str = "",
) -> str:
    """Analyze buffer sizes from type and struct information.

    Identifies:
    1. Stack buffers (local arrays)
    2. Heap allocations (malloc, calloc)
    3. Global buffers
    4. Struct members that are buffers
    5. Size vs usage mismatches

    Args:
        target_function: Specific function to analyze (empty for all)

    Returns:
        Buffer size analysis with overflow risk assessment.
    """
    report = f"""## Buffer Size Analysis

**Target Function:** {target_function if target_function else "All functions"}
**Analysis Type:** Static buffer size detection

### Buffer Types

#### 1. Stack Buffers

Local arrays on the stack:

```c
void example() {{
    char buffer[64];      // 64-byte stack buffer
    int data[16];         // 64-byte stack buffer (16 * 4)
    wchar_t wbuf[32];    // 64-byte stack buffer (32 * 2)
}}
```

**Detection**: Look for array declarations in function prologues
**Risk**: Overflow if input size > array size

#### 2. Heap Buffers

Dynamically allocated memory:

```c
void example() {{
    char *buffer = malloc(128);    // 128-byte heap buffer
    char *data = calloc(64, 1);    // 64-byte heap buffer
}}
```

**Detection**: Track malloc/calloc/realloc calls
**Risk**: Overflow if input > allocated size

#### 3. Global Buffers

Global or static arrays:

```c
char global_buffer[256];
static char static_buffer[128];

void example() {{
    // Uses global_buffer
}}
```

**Detection**: Find global/static array symbols
**Risk**: Overflow if input > array size

#### 4. Struct Members

Buffer fields in structures:

```c
struct user {{
    char name[32];      // 32-byte buffer in struct
    char email[64];     // 64-byte buffer in struct
}};
```

**Detection**: Analyze struct definitions
**Risk**: Overflow if field copy exceeds size

### IDA Pro Buffer Analysis

```python
# IDA Python script to find stack buffers
import ida_bytes
import ida_funcs

def find_stack_buffers(func_ea):
    '''Find stack buffer declarations'''
    func = ida_funcs.get_func(func_ea)
    if not func:
        return []

    buffers = []
    # Scan for stack var declarations
    # (implementation depends on IDA version)
    return buffers
```

### Size vs Usage Analysis

| Pattern | Safe If | Dangerous If |
|---------|---------|---------------|
| `char buf[64]; strcpy(buf, input)` | input < 64 | input ≥ 64 |
| `char buf[64]; recv(fd, buf, 128, 0)` | recv ≤ 64 | recv > 64 |
| `char *buf = malloc(64); recv(fd, buf, 128)` | recv ≤ 64 | recv > 64 |

### Common Mistakes

#### Mistake 1: Size confusion
```c
// WRONG: sizeof(pointer) not buffer
void wrong(char *str) {{
    char buffer[64];
    memcpy(buffer, str, sizeof(buffer));  // ALWAYS copies 64!
}}

// RIGHT: Track actual size
void right(char *str) {{
    char buffer[64];
    memcpy(buffer, str, strlen(str) + 1);
}}
```

#### Mistake 2: Off-by-one
```c
// WRONG: No space for null terminator
char buf[64];
strncpy(buf, input, 64);  // May not null-terminate!

// RIGHT: Leave space for null
char buf[64];
strncpy(buf, input, sizeof(buf) - 1);
buf[sizeof(buf) - 1] = '\\0';
```

#### Mistake 3: Type confusion
```c
// WRONG: wchar_t is 2 or 4 bytes, not 1!
wchar_t wbuf[64];
wcscpy(wbuf, wide_input);  // Can overflow differently!
```

### Buffer Size Detection

**From disassembly:**
```asm
; Stack buffer allocation
sub rsp, 0x40     ; 64-byte buffer
lea rax, [rsp+0x10]  ; Buffer at RSP+0x16
```

**From symbols:**
```bash
# nm shows global buffers
nm binary | grep "^[0-9a-f]* [BD]"
```

### Risk Assessment Matrix

| Buffer Type | Max Input | Buffer Size | Risk Level |
|-------------|-----------|-------------|------------|
| Stack | 1024 | 64 | CRITICAL |
| Heap | 1024 | 128 | HIGH |
| Global | 512 | 256 | MEDIUM |
| Struct field | 256 | 32 | HIGH |

### Analysis Checklist

For each buffer:
- [ ] Identify buffer location (stack/heap/global)
- [ ] Determine buffer size
- [ ] Find all copy/write operations
- [ ] Check bounds on each operation
- [ ] Verify input sources
- [ ] Document overflow potential

### Countermeasures

**Safe Functions:**
```c
// Instead of strcpy → strncpy/snprintf
// Instead of sprintf → snprintf
// Instead of gets → fgets/getline
// Instead of scanf → scanf with width specifiers
```

**Runtime Checks:**
```c
// Always validate length
if (input_len >= sizeof(buffer))
    return ERROR;

// Use safe alternatives
strncpy_s(buffer, sizeof(buffer), input, _TRUNCATE);
```

### Notes

- Always verify size calculations
- Check sizeof(ptr) vs sizeof(array)
- Account for null terminators
- Consider wchar_t size differences
"""

    return report


# ============================================================================
# Call Graph Attack Surface
# ============================================================================

@tool(category="security", description="Map attack surface via call graph analysis")
def call_graph_attack_surface(
    entry_points: str = "main,serve,handle",
    max_depth: int = 5,
) -> str:
    """Map attack surface by analyzing which functions receive external data.

    Call graph analysis identifies:
    1. Entry points from external inputs
    2. Data propagation through function calls
    3. Functions that handle untrusted data
    4. Attack surface for vulnerability discovery

    Args:
        entry_points: Comma-separated entry point functions
        max_depth: Maximum depth for call graph traversal

    Returns:
        Attack surface map with risk assessment.
    """
    report = f"""## Call Graph Attack Surface Analysis

**Entry Points:** {entry_points}
**Max Depth:** {max_depth} levels

### Analysis Overview

Call graph mapping identifies:
1. **Entry Functions**: Receive external data (network, file, user)
2. **Data Handlers**: Process untrusted data
3. **Dangerous Functions**: Vulnerability-prone operations
4. **Attack Paths**: From entry to dangerous function

### Call Graph Levels

```
Level 0: Entry Points (external input)
    ↓
Level 1: Input Processing Functions
    ↓
Level 2: Data Parsing Functions
    ↓
Level 3: Core Logic Functions
    ↓
Level 4: Dangerous Operations
```

### External Data Sources

| Source | Entry Functions | Risk Level |
|--------|----------------|------------|
| Network | serve, handle, recv_msg | HIGH |
| Files | load_config, read_input | MEDIUM |
| Arguments | main, parse_args | MEDIUM |
| IPC | recv_ipc, handle_msg | HIGH |
| UI | handle_click, process_input | MEDIUM |

### IDA Pro Call Graph Analysis

```python
# IDA Python call graph analysis
import ida_funcs
import ida_graph

def build_call_graph(start_func):
    '''Build call graph from function'''
    graph = {{}}

    def add_edges(func_ea):
        func = ida_funcs.get_func(func_ea)
        if not func:
            return

        xrefs = ida_XrefsTo(func_ea)
        for xref in xrefs:
            if xref.type == ida_xref.fl_CN:
                caller = ida_name.get_name(xref.from)
                if caller not in graph:
                    graph[caller] = []
                graph[caller].append(ida_name.get_name(func_ea))

    add_edges(start_func)
    return graph
```

### Attack Path Examples

#### Path 1: Network → Buffer Overflow
```
main()
  ↓
serve_connection()
  ↓
handle_client_request()
  ↓
process_command()  ← VULNERABLE: strcpy here
```

#### Path 2: File → Command Injection
```
main()
  ↓
load_configuration()
  ↓
parse_config_file()  ← VULNERABLE: system() here
```

#### Path 3: Input → Format String
```
main()
  ↓
handle_user_input()
  ↓
log_message()  ← VULNERABLE: printf(user_input)
```

### Function Risk Classification

**Entry Functions (Level 0)** - Highest Priority:
- `main`, `serve`, `handle_request`
- Always review for input validation

**Processing Functions (Level 1-2)** - High Priority:
- `parse_`, `process_`, `handle_`
- Check data sanitization

**Core Logic (Level 3)** - Medium Priority:
- Business logic functions
- Check for logic bugs

**Utility Functions** - Low Priority:
- Helper functions
- Usually safe unless passed bad data

### Analysis Workflow

1. **Identify Entry Points**
```
Find functions that:
- Call network recv functions
- Open files with user paths
- Process command line args
- Handle IPC messages
```

2. **Build Call Graph**
```
For each entry point:
  Track all called functions
  Note parameter passing
  Identify data flow
```

3. **Find Dangerous Operations**
```
Search for:
- strcpy/sprintf calls
- system/popen calls
- Format string functions
- Memory operations
```

4. **Assess Vulnerability**
```
For each dangerous call:
- Is data from external source?
- Is validation performed?
- Is bounds checking present?
- Is exploit feasible?
```

### Tools for Call Graph Analysis

**IDA Pro:**
- View → Graphs → Flow charts
- View → Open subviews → Functions
- Xrefs to see callers/callees

**Command Line:**
```bash
# e9tools for call graph analysis
e9compile ./binary
e9dump ./binary

# IDA batch mode
idal -Sanalyze_callgraph.idc ./binary
```

### Priority Analysis

**HIGH PRIORITY** - Direct external input:
```
Functions that call:
- recv/recvfrom → network input
- fgets/fscanf → file input
- getenv → environment input

And then call:
- strcpy/sprintf → overflow
- system → injection
- printf → format string
```

**MEDIUM PRIORITY** - Indirect input:
```
Functions that process data
after some validation

Still dangerous if:
- Validation insufficient
- Bounds check wrong
- Type confusion
```

### Risk Reduction

**For each entry function:**
```c
void handle_request(int sock) {{
    // 1. Validate input length
    // 2. Use safe functions
    // 3. Check return values
    // 4. Sanitize data
    // 5. Pass validated data only
}}
```

### Automated Detection

```python
# Pattern-based attack surface detection
def find_attack_surface(binary):
    attack_surface = []

    # Find entry points
    entry_funcs = find_entry_points(binary)

    # For each entry, find dangerous calls
    for entry in entry_funcs:
        callees = get_callees(entry)
        for callee in callees:
            if is_dangerous(callee):
                attack_surface.append((entry, callee))

    return attack_surface
```

### Notes

- Start analysis from entry points
- Track data flow, not just calls
- Validate actual input sources
- Consider all code paths
- Check error handling paths
"""

    return report


# ============================================================================
# Type-based Overflow Detection
# ============================================================================

@tool(category="security", description="Detect type mismatches that cause overflows")
def type_overflow_detection(
    target_function: str = "",
) -> str:
    """Detect type-based overflow vulnerabilities from type mismatches.

    Identifies:
    1. Signed/unsigned conversions
    2. Size truncations (int → short)
    3. Integer overflows in calculations
    4. Array index issues
    5. Pointer arithmetic problems

    Args:
        target_function: Specific function to analyze

    Returns:
        Type-based vulnerability analysis.
    """
    report = f"""## Type-based Overflow Detection

**Target Function:** {target_function if target_function else "All functions"}

### Type Mismatch Vulnerabilities

#### 1. Signed/Unsigned Issues

```c
// DANGEROUS: Comparison mismatch
int len = get_user_input();        // len can be -1
char buffer[64];

if (len < sizeof(buffer))           // -1 < 64 = TRUE!
    memcpy(buffer, input, len);     // len = 4GB = crash!
```

**Problem**: `-1` as signed = `0xffffffff` as unsigned = 4GB

**Fix**: Use size_t consistently
```c
size_t len = get_user_input();
if (len < sizeof(buffer))
    memcpy(buffer, input, len);
```

#### 2. Size Truncation

```c
// DANGEROUS: Truncation on assignment
int32_t big_size = get_size();      // Can be 0x10000
int16_t small_size = big_size;     // Truncates to 0x0000!

char *buffer = malloc(small_size);  // Allocates 0 bytes!
recv(sock, buffer, big_size, 0);    // Overflow!
```

**Fix**: Check for overflow
```c
if (big_size > INT16_MAX)
    return ERROR;
small_size = (int16_t)big_size;
```

#### 3. Integer Overflow in Allocation

```c
// DANGEROUS: Integer overflow
int32_t count = get_count();
int32_t size = 256;

// If count = 0x1000000, overflow occurs:
int32_t total = count * size;      // OVERFLOWS!

char *buffer = malloc(total);      // Allocates small buffer
```

**Fix**: Use larger types or check
```c
int64_t total = (int64_t)count * size;
if (total > SIZE_MAX)
    return ERROR;
```

#### 4. Array Index Issues

```c
// DANGEROUS: Index underflow/overflow
int index = get_index();            // Can be negative or > array size
char buffer[64];

buffer[index] = 'A';                // Out of bounds!
```

**Fix**: Validate range
```c
if (index < 0 || index >= sizeof(buffer))
    return ERROR;
buffer[index] = 'A';
```

#### 5. Pointer Arithmetic

```c
// DANGEROUS: Offset miscalculation
int offset = get_offset();          // Can overflow
char *base = malloc(256);
char *ptr = base + offset;          // Way past allocation!
```

**Fix**: Check offset validity
```c
size_t alloc_size = 256;
if (offset >= alloc_size)
    return ERROR;
char *ptr = base + offset;
```

### Detection Patterns

| Pattern | Vulnerability | Detection |
|---------|--------------|------------|
| `if (len < 64)` with signed len | Sign extension | Check variable types |
| `short = int` assignment | Truncation | Find implicit casts |
| `count * size` allocation | Integer overflow | Check math ops |
| `array[index]` access | Out of bounds | Validate index |
| `ptr + offset` | Offset overflow | Check offset |

### IDA Pro Type Analysis

```python
# IDA Python type checking
import idaapi
import ida_typeinf

def check_type_mismatches(func_ea):
    '''Find type mismatches in function'''

    # Get function type info
    func_type = idaapi.get_tinfo(func_ea)

    # Check parameters
    for param in func_type:
        # Check for signed/unsigned mismatches
        # Check for size truncations
        pass
```

### Common Type Errors

#### Error 1: Loop Counter
```c
// DANGEROUS: Signed loop variable
for (int i = size; i >= 0; i--)  // If size = SIZE_MAX, infinite!
    buffer[i] = 0;
```

**Fix**: Use unsigned for sizes
```c
for (size_t i = size; i > 0; i--)
    buffer[i-1] = 0;
```

#### Error 2: Return Value Check
```c
// DANGEROUS: Doesn't check for -1
int len = recv(sock, buffer, 1024, 0);
if (len < 0)  // But recv returns -1 on error!
    handle_error();
```

**Fix**: Use correct types
```c
ssize_t len = recv(sock, buffer, 1024, 0);
if (len < 0)
    handle_error();
```

#### Error 3: Size Calculation
```c
// DANGEROUS: Overflow in calculation
int width = get_width();
int height = get_height();
int total = width * height;  // Can overflow!
```

**Fix**: Use larger types
```c
int64_t total = (int64_t)width * height;
if (total > INT_MAX)
    return ERROR;
```

### Detection Checklist

For each variable:
- [ ] Check signed/unsigned mixing
- [ ] Verify type conversions
- [ ] Check arithmetic operations
- [ ] Validate array indices
- [ ] Verify pointer arithmetic
- [ ] Check return value types

### Secure Coding Practices

**Use appropriate types:**
```c
size_t      // For sizes and counts (unsigned)
ssize_t     // For signed sizes (can be -1)
uint32_t    // Explicit sized types
intptr_t    // For pointer-sized integers
```

**Validate conversions:**
```c
if (value < 0 || value > MAX_TYPE_VALUE)
    return ERROR;
```

**Check arithmetic:**
```c
if (a > 0 && b > 0 && a > INT_MAX / b)
    return ERROR;  // Would overflow
```

### Tools for Type Analysis

```bash
# Compiler warnings
gcc -Wall -Wextra -Wconversion

# Static analysis
clang --analyze
cppcheck

# Dynamic analysis
valgrind --tool=exp-ptrcheck
```

### Notes

- Always use appropriate types
- Check for implicit conversions
- Validate before conversions
- Consider overflow in all math
- Use static analysis tools
"""

    return report
