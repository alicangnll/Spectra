"""Valgrind memory debugging and profiling tool integration.

Provides tools for:
- Memory leak detection with memcheck
- Memory profiling with Massif
- Performance profiling with Callgrind
- Cache profiling with cachegrind
- Helgrind thread error detection
- DRD thread error detection
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

from ..core.logging import log_debug, log_info
from ..core.tool_infrastructure import ExternalTool
from ..tools.base import ParameterSchema, ToolDefinition


class ValgrindTool(ExternalTool):
    """Valgrind memory debugging tool."""

    tool_name = "Valgrind"
    executable_names = ["valgrind"]
    common_paths = {
        "Linux": ["/usr/bin", "/usr/local/bin"],
        "Darwin": ["/usr/local/bin", "/opt/homebrew/bin"],
    }

    def get_version_args(self) -> list[str]:
        return ["--version"]

    def _extract_version(self, output: str) -> str:
        """Extract Valgrind version."""
        match = re.search(r"valgrind-(\d+\.\d+\.\d+)", output, re.IGNORECASE)
        return match.group(1) if match else ""


# Global instance
_valgrind_instance: ValgrindTool | None = None


def get_valgrind() -> ValgrindTool:
    """Get or create Valgrind tool instance."""
    global _valgrind_instance
    if _valgrind_instance is None:
        _valgrind_instance = ValgrindTool()
    return _valgrind_instance


def check_valgrind_available() -> bool:
    """Check if Valgrind is available."""
    return get_valgrind().is_available()


def _ensure_valgrind() -> str:
    """Ensure Valgrind is available and return its path."""
    valgrind = get_valgrind()
    if not valgrind.is_available():
        raise RuntimeError("Valgrind not found. Install valgrind package")
    return valgrind.get_path()


# ============================================================================
# Tool Functions
# ============================================================================


def valgrind_memcheck(
    binary: str, args: str, leak_check: str = "summary", track_origins: bool = False, verbose: bool = False
) -> str:
    """Run binary under Valgrind memcheck for memory error detection.

    Args:
        binary: Target binary path
        args: Command-line arguments for binary
        leak_check: Leak check level (summary|no|full|yes)
        track_origins: Track origins of uninitialized values
        verbose: Enable verbose output

    Returns:
        Memcheck analysis output
    """
    valgrind_path = _ensure_valgrind()

    cmd = [
        valgrind_path,
        "--tool=memcheck",
        f"--leak-check={leak_check}",
    ]

    if track_origins:
        cmd.append("--track-origins=yes")

    if verbose:
        cmd.append("-v")

    # Add binary and arguments
    cmd.append(binary)
    if args:
        cmd.extend(args.split())

    try:
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
        return "Error: Valgrind memcheck timed out after 5 minutes"
    except Exception as e:
        return f"Error: {e}"


def valgrind_massif(binary: str, args: str, snapshot_freq: str = "10", detailed_freq: int = 10) -> str:
    """Profile memory usage with Massif heap profiler.

    Args:
        binary: Target binary path
        args: Command-line arguments
        snapshot_freq: Snapshot frequency (instructions or milliseconds)
        detailed_freq: Detailed snapshot frequency

    Returns:
        Massif profiling output
    """
    valgrind_path = _ensure_valgrind()

    cmd = [
        valgrind_path,
        "--tool=massif",
        "--massif-out-file=massif.out.%p",
        f"--snapshot-freq={snapshot_freq}",
        f"--detailed-freq={detailed_freq}",
    ]

    cmd.append(binary)
    if args:
        cmd.extend(args.split())

    try:
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

        output.append("\nMassif profile saved to massif.out.* files")
        output.append("Use ms_print massif.out.<pid> to view results")

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: Valgrind massif timed out"
    except Exception as e:
        return f"Error: {e}"


def valgrind_callgrind(binary: str, args: str, callgraph: bool = True, branch_simulation: bool = False) -> str:
    """Profile performance with Callgrind.

    Args:
        binary: Target binary path
        args: Command-line arguments
        callgraph: Generate call graph
        branch_simulation: Enable branch prediction simulation

    Returns:
        Callgrind profiling output
    """
    valgrind_path = _ensure_valgrind()

    cmd = [
        valgrind_path,
        "--tool=callgrind",
        "--callgrind-out-file=callgrind.out.%p",
    ]

    if callgraph:
        cmd.append("--call-graph=yes")

    if branch_simulation:
        cmd.append("--branch-sim=yes")

    cmd.append(binary)
    if args:
        cmd.extend(args.split())

    try:
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

        output.append("\nCallgrind profile saved to callgrind.out.* files")
        output.append("Use callgrind_annotate callgrind.out.<pid> to view results")

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: Valgrind callgrind timed out"
    except Exception as e:
        return f"Error: {e}"


def valgrind_cachegrind(binary: str, args: str, cache_sim: bool = True, branch_sim: bool = False) -> str:
    """Profile cache performance with cachegrind.

    Args:
        binary: Target binary path
        args: Command-line arguments
        cache_sim: Enable cache simulation
        branch_sim: Enable branch prediction simulation

    Returns:
        Cachegrind profiling output
    """
    valgrind_path = _ensure_valgrind()

    cmd = [
        valgrind_path,
        "--tool=cachegrind",
        "--cachegrind-out-file=cachegrind.out.%p",
    ]

    if not cache_sim:
        cmd.append("--cache-sim=no")

    if branch_sim:
        cmd.append("--branch-sim=yes")

    cmd.append(binary)
    if args:
        cmd.extend(args.split())

    try:
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

        output.append("\nCachegrind profile saved to cachegrind.out.* files")
        output.append("Use cg_annotate cachegrind.out.<pid> to view results")

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: Valgrind cachegrind timed out"
    except Exception as e:
        return f"Error: {e}"


def valgrind_helgrind(binary: str, args: str, history_level: str = "full") -> str:
    """Detect thread errors with Helgrind.

    Args:
        binary: Target binary path
        args: Command-line arguments
        history_level: History level for data races (full|approx|none)

    Returns:
        Helgrind analysis output
    """
    valgrind_path = _ensure_valgrind()

    cmd = [
        valgrind_path,
        "--tool=helgrind",
        f"--history-level={history_level}",
    ]

    cmd.append(binary)
    if args:
        cmd.extend(args.split())

    try:
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
        return "Error: Valgrind helgrind timed out"
    except Exception as e:
        return f"Error: {e}"


def valgrind_drd(binary: str, args: str) -> str:
    """Detect thread errors with DRD (alternative to Helgrind).

    Args:
        binary: Target binary path
        args: Command-line arguments

    Returns:
        DRD analysis output
    """
    valgrind_path = _ensure_valgrind()

    cmd = [
        valgrind_path,
        "--tool=drd",
    ]

    cmd.append(binary)
    if args:
        cmd.extend(args.split())

    try:
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
        return "Error: Valgrind DRD timed out"
    except Exception as e:
        return f"Error: {e}"


def valgrind_parse_suppressions(suppressions_file: str) -> str:
    """Parse and display Valgrind suppressions file.

    Args:
        suppressions_file: Path to suppressions file

    Returns:
        Parsed suppressions
    """
    if not os.path.isfile(suppressions_file):
        return f"Error: Suppressions file not found: {suppressions_file}"

    try:
        with open(suppressions_file) as f:
            content = f.read()

        # Basic validation
        if not content.strip():
            return "Suppressions file is empty"

        lines = content.split("\n")
        suppression_count = len([ln for ln in lines if ln.strip().startswith("{")])

        output = [
            f"Suppressions file: {suppressions_file}",
            f"Total suppressions: {suppression_count}",
            "First few lines:",
            "\n".join(lines[:10]),
        ]

        return "\n".join(output)

    except Exception as e:
        return f"Error parsing suppressions: {e}"


# ============================================================================
# Tool Definitions
# ============================================================================


def create_valgrind_tools() -> list[ToolDefinition]:
    """Create Valgrind tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="valgrind_memcheck",
            description="Run binary under Valgrind memcheck for memory error detection",
            category="debugging",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
                ParameterSchema(
                    name="leak_check",
                    type="string",
                    description="Leak check level (summary|no|full|yes)",
                    required=False,
                    default="summary",
                ),
                ParameterSchema(
                    name="track_origins",
                    type="boolean",
                    description="Track origins of uninitialized values",
                    required=False,
                    default=False,
                ),
                ParameterSchema(
                    name="verbose", type="boolean", description="Enable verbose output", required=False, default=False
                ),
            ],
            handler=lambda binary, args="", leak_check="summary", track_origins=False, verbose=False, **kwargs: (
                valgrind_memcheck(binary, args, leak_check, track_origins, verbose)
            ),
        ),
        ToolDefinition(
            name="valgrind_massif",
            description="Profile memory usage with Massif heap profiler",
            category="debugging",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
                ParameterSchema(
                    name="snapshot_freq",
                    type="string",
                    description="Snapshot frequency (instructions or ms)",
                    required=False,
                    default="10",
                ),
                ParameterSchema(
                    name="detailed_freq",
                    type="integer",
                    description="Detailed snapshot frequency",
                    required=False,
                    default=10,
                ),
            ],
            handler=lambda binary, args="", snapshot_freq="10", detailed_freq=10, **kwargs: valgrind_massif(
                binary, args, snapshot_freq, detailed_freq
            ),
        ),
        ToolDefinition(
            name="valgrind_callgrind",
            description="Profile performance with Callgrind",
            category="debugging",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
                ParameterSchema(
                    name="callgraph", type="boolean", description="Generate call graph", required=False, default=True
                ),
                ParameterSchema(
                    name="branch_simulation",
                    type="boolean",
                    description="Enable branch prediction simulation",
                    required=False,
                    default=False,
                ),
            ],
            handler=lambda binary, args="", callgraph=True, branch_simulation=False, **kwargs: valgrind_callgrind(
                binary, args, callgraph, branch_simulation
            ),
        ),
        ToolDefinition(
            name="valgrind_cachegrind",
            description="Profile cache performance with cachegrind",
            category="debugging",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
                ParameterSchema(
                    name="cache_sim",
                    type="boolean",
                    description="Enable cache simulation",
                    required=False,
                    default=True,
                ),
                ParameterSchema(
                    name="branch_sim",
                    type="boolean",
                    description="Enable branch prediction simulation",
                    required=False,
                    default=False,
                ),
            ],
            handler=lambda binary, args="", cache_sim=True, branch_sim=False, **kwargs: valgrind_cachegrind(
                binary, args, cache_sim, branch_sim
            ),
        ),
        ToolDefinition(
            name="valgrind_helgrind",
            description="Detect thread errors with Helgrind",
            category="debugging",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
                ParameterSchema(
                    name="history_level",
                    type="string",
                    description="History level (full|approx|none)",
                    required=False,
                    default="full",
                ),
            ],
            handler=lambda binary, args="", history_level="full", **kwargs: valgrind_helgrind(
                binary, args, history_level
            ),
        ),
        ToolDefinition(
            name="valgrind_drd",
            description="Detect thread errors with DRD (alternative to Helgrind)",
            category="debugging",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
            ],
            handler=lambda binary, args="", **kwargs: valgrind_drd(binary, args),
        ),
        ToolDefinition(
            name="valgrind_parse_suppressions",
            description="Parse and display Valgrind suppressions file",
            category="debugging",
            parameters=[
                ParameterSchema(
                    name="suppressions_file", type="string", description="Path to suppressions file", required=True
                ),
            ],
            handler=lambda suppressions_file, **kwargs: valgrind_parse_suppressions(suppressions_file),
        ),
    ]


def register_valgrind_tools(registry: Any) -> int:
    """Register Valgrind tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_valgrind_available():
        log_debug("Valgrind not available, skipping tool registration")
        return 0

    tools = create_valgrind_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} Valgrind tools")
    return len(tools)
