"""Angr/Triton symbolic execution tool integration.

Provides tools for:
- Path exploration with Angr
- Constraint solving
- Vulnerability scanning with symbolic execution
- Taint analysis
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import Any

from ..core.logging import log_debug, log_info
from ..core.tool_infrastructure import ExternalTool
from ..tools.base import ParameterSchema, ToolDefinition


class AngrTool(ExternalTool):
    """Angr symbolic execution engine."""

    tool_name = "Angr"
    # Angr is a Python library
    executable_names = []

    def __init__(self, required: bool = False):
        super().__init__(required)

    def find_tool(self) -> Any:
        """Check if angr Python module is available."""
        try:
            import importlib.util

            spec = importlib.util.find_spec("angr")
            if spec is not None:
                from ..core.tool_infrastructure import ToolLocation

                # Try to get version
                try:
                    import angr

                    version = angr.__version__
                except Exception:
                    version = "unknown"
                location = ToolLocation(path="angr", version=version)
                location.is_valid = True
                self._location = location
                return location
        except Exception as e:
            log_debug(f"Angr check failed: {e}")
        return None


# Global instance
_angr_instance: AngrTool | None = None


def get_angr() -> AngrTool:
    """Get or create Angr tool instance."""
    global _angr_instance
    if _angr_instance is None:
        _angr_instance = AngrTool()
    return _angr_instance


def check_angr_available() -> bool:
    """Check if Angr is available."""
    return get_angr().is_available()


def _ensure_angr() -> bool:
    """Ensure Angr is available."""
    if not check_angr_available():
        raise RuntimeError("Angr not found. Install with: pip install angr")
    return True


def _run_angr_script(script: str) -> str:
    """Run Angr Python script.

    Args:
        script: Angr Python code

    Returns:
        Script output
    """
    _ensure_angr()

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            script_path = f.name

        cmd = [sys.executable, script_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(result.stderr)

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: Angr script timed out"
    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


# ============================================================================
# Tool Functions
# ============================================================================


def angr_explore(binary: str, address: int, constraints: list | None = None) -> str:
    """Explore paths with Angr.

    Args:
        binary: Binary path
        address: Address to start from (hex or decimal)
        constraints: List of constraint descriptions

    Returns:
        Path exploration results
    """
    _ensure_angr()
    if constraints is None:
        constraints = []

    addr = int(address, 16) if isinstance(address, str) and address.startswith("0x") else int(address)

    script = f"""
import angr
import claripy

# Load binary
proj = angr.Project("{binary}", auto_load_libs=False)

# Start from address
state = proj.factory.blank_state(addr={addr})

# Explore
simgr = proj.factory.simulation_manager(state)
print(f"Exploring from 0x{{addr:x}}")

try:
    simgr.explore(find=lambda s: True, avoid=lambda s: False, n=10)
    print(f"Found {{len(simgr.found)}} states")
    for i, state in enumerate(simgr.found[:5]):
        print(f"State {{i}}: 0x{{state.addr:x}}")
except Exception as e:
    print(f"Exploration error: {{e}}")
"""

    return _run_angr_script(script)


def angr_solve_constraint(binary: str, constraint: str) -> str:
    """Solve constraint with symbolic execution.

    Args:
        binary: Binary path
        constraint: Constraint description

    Returns:
        Constraint solution
    """
    _ensure_angr()

    script = f"""
import angr
import claripy

# Load binary
proj = angr.Project("{binary}", auto_load_libs=False)

# Create symbolic variables
print("Solving constraint: {constraint}")

# This is a placeholder - actual constraint solving depends on the binary
print("Note: Constraint solving requires:")
print("1. Identifying input symbols in binary")
print("2. Building path constraints")
print("3. Using z3 solver to find satisfying input")

# Example:
# sym_argv = claripy.SymArray("sym_argv", 100)
# state = proj.factory.entry_state(args=[sym_argv])
# simgr = proj.factory.simulation_manager(state)
# simgr.explore(find=lambda s: b"Success" in s.posix.dumps(1))
# if simgr.found:
#     solution = simgr.found[0].solver.eval(sym_argv, cast_to=bytes)
#     print(f"Solution: {{solution}}")
"""

    return _run_angr_script(script)


def angr_vulnerability_scan(binary: str) -> str:
    """Scan for vulnerabilities with symbolic execution.

    Args:
        binary: Binary path

    Returns:
        Vulnerability scan results
    """
    _ensure_angr()

    script = f"""
import angr
import claripy

# Load binary
proj = angr.Project("{binary}", auto_load_libs=False)

print("=== Angr Vulnerability Scan ===")
print(f"Binary: {binary}")
print(f"Arch: {{proj.arch.name}}")
print(f"Loader: {{proj.loader.main_object.__class__.__name__}}")

# Get functions
cfg = proj.analyses.CFG()
functions = list(cfg.functions.values())
print(f"Functions: {{len(functions)}}")

# Scan for potentially dangerous functions
dangerous = {
        (
            "strcpy",
            "gets",
            "sprintf",
            "vsprintf",
            "scanf",
            "sscanf",
            "fscanf",
            "system",
            "execl",
            "execv",
            "malloc",
            "calloc",
            "realloc",
        )
    }

print("\\nPotentially dangerous functions:")
for func in functions:
    if func.name in dangerous:
        print(f"  - {{func.name}} @ 0x{{func.addr:x}}")

# Scan for overflow-prone patterns
print("\\nOverflow patterns:")
for func in functions[:20]:
    if len(func.arguments) > 4:
        print(f"  - {{func.name}}: {{len(func.arguments)}} args (potential stack overflow?)")

print("\\nNote: Full vulnerability analysis requires symbolic execution on each function")
"""

    return _run_angr_script(script)


def angr_taint_analysis(binary: str, source: str, sink: str) -> str:
    """Perform taint analysis.

    Args:
        binary: Binary path
        source: Source location (function name or address)
        sink: Sink location (function name or address)

    Returns:
        Taint analysis results
    """
    _ensure_angr()

    script = f"""
import angr

# Load binary
proj = angr.Project("{binary}", auto_load_libs=False)

print("=== Angr Taint Analysis ===")
print(f"Binary: {binary}")
print(f"Source: {source}")
print(f"Sink: {sink}")

# This is a placeholder - actual taint analysis requires:
# 1. Identifying taint sources (user input, network, files)
# 2. Tracking data flow through program
# 3. Checking if tainted data reaches sensitive sinks

print("\\nTaint analysis steps:")
print("1. Identify taint sources (e.g., user input, network recv)")
print("2. Create symbolic variables for tainted data")
print("3. Track data flow using VEX/IR")
print("4. Check if tainted data reaches sink functions")

print("\\nCommon sinks to watch for:")
sinks = ['system', 'exec', 'strcpy', 'gets', 'mysql_query', 'sqlite3_exec']
for sink in sinks:
    print(f"  - {{sink}}")

print("\\nNote: Full taint analysis requires angr.exploration_techniques.SymbolicExploration")
"""

    return _run_angr_script(script)


def angr_reaching_definitions(binary: str, function: str) -> str:
    """Analyze reaching definitions for function.

    Args:
        binary: Binary path
        function: Function name

    Returns:
        Reaching definitions analysis
    """
    _ensure_angr()

    script = f"""
import angr

# Load binary
proj = angr.Project("{binary}", auto_load_libs=False)

print("=== Reaching Definitions Analysis ===")
print(f"Binary: {binary}")
print(f"Function: {function}")

# Get CFG
cfg = proj.analyses.CFG()

# Find function
target_func = cfg.functions.get("{function}")
if not target_func:
    print(f"Function '{{function}}' not found")
else:
    print(f"Function @ 0x{{target_func.addr:x}}")
    print(f"Blocks: {{len(target_func.blocks)}}")

    # Reaching definitions
    try:
        rdf = proj.analyses.ReachingDefinitions(subject=target_func)
        print(f"\\nDefinitions analyzed: {{len(rdf.graph)}}")
        print("\\nNote: Use rdf.graph to inspect data flow")
    except Exception as e:
        print(f"ReachingDefinitions analysis failed: {{e}}")
"""

    return _run_angr_script(script)


def angr_cg_level(binary: str) -> str:
    """Generate call graph.

    Args:
        binary: Binary path

    Returns:
        Call graph analysis
    """
    _ensure_angr()

    script = f"""
import angr

# Load binary
proj = angr.Project("{binary}", auto_load_libs=False)

print("=== Call Graph Analysis ===")
print(f"Binary: {binary}")

# Run CFG
cfg = proj.analyses.CFG(normalize=True)

# Get call graph
cg = proj.analyses.CallGraph()

print(f"\\nTotal functions: {{len(cfg.functions)}}")
print("Top 10 functions by call count:")

# Count calls
call_counts = {{}}
for func in cfg.functions.values():
    call_counts[func.name] = len(func.callgraph_calls)

# Show top callers
sorted_funcs = sorted(call_counts.items(), key=lambda x: x[1], reverse=True)
for name, count in sorted_funcs[:10]:
    print(f"  {{name}}: {{count}} calls")
"""

    return _run_angr_script(script)


# ============================================================================
# Tool Definitions
# ============================================================================


def create_angr_tools() -> list[ToolDefinition]:
    """Create Angr tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="angr_explore",
            description="Explore paths with Angr symbolic execution",
            category="symbolic_execution",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(
                    name="address", type="string", description="Start address (hex or decimal)", required=True
                ),
                ParameterSchema(
                    name="constraints",
                    type="string",
                    description="Optional constraints (JSON array)",
                    required=False,
                    default="[]",
                ),
            ],
            handler=lambda binary, address, constraints="[]", **kwargs: angr_explore(
                binary, address, json.loads(constraints) if constraints else []
            ),
        ),
        ToolDefinition(
            name="angr_solve_constraint",
            description="Solve constraint with symbolic execution",
            category="symbolic_execution",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(name="constraint", type="string", description="Constraint description", required=True),
            ],
            handler=lambda binary, constraint, **kwargs: angr_solve_constraint(binary, constraint),
        ),
        ToolDefinition(
            name="angr_vulnerability_scan",
            description="Scan binary for vulnerabilities with symbolic execution",
            category="symbolic_execution",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
            ],
            handler=lambda binary, **kwargs: angr_vulnerability_scan(binary),
        ),
        ToolDefinition(
            name="angr_taint_analysis",
            description="Perform taint analysis on binary",
            category="symbolic_execution",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(
                    name="source", type="string", description="Source location (function or address)", required=True
                ),
                ParameterSchema(
                    name="sink", type="string", description="Sink location (function or address)", required=True
                ),
            ],
            handler=lambda binary, source, sink, **kwargs: angr_taint_analysis(binary, source, sink),
        ),
        ToolDefinition(
            name="angr_reaching_definitions",
            description="Analyze reaching definitions for function",
            category="symbolic_execution",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(name="function", type="string", description="Function name", required=True),
            ],
            handler=lambda binary, function, **kwargs: angr_reaching_definitions(binary, function),
        ),
        ToolDefinition(
            name="angr_cg_level",
            description="Generate and analyze call graph",
            category="symbolic_execution",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
            ],
            handler=lambda binary, **kwargs: angr_cg_level(binary),
        ),
    ]


def register_angr_tools(registry: Any) -> int:
    """Register Angr tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_angr_available():
        log_debug("Angr not available, skipping tool registration")
        return 0

    tools = create_angr_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} Angr tools")
    return len(tools)
