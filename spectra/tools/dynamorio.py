"""DynamoRIO dynamic instrumentation tool integration.

Provides tools for:
- Running binaries under DynamoRIO instrumentation
- Code coverage analysis with drcov
- Symbol analysis with drsym
- Custom client library execution
- Memory access monitoring
- Trace generation
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..core.logging import log_debug, log_info
from ..core.tool_infrastructure import ExternalTool
from ..tools.base import ParameterSchema, ToolDefinition


class DynamoRIOTool(ExternalTool):
    """DynamoRIO dynamic instrumentation tool."""

    tool_name = "DynamoRIO"
    executable_names = ["drrun", "drrun.exe"]
    common_paths = {
        "Linux": ["/usr/local/bin", "/opt/dynamorio/bin", "~/.local/bin"],
        "Darwin": ["/usr/local/bin", "/opt/homebrew/bin", "/opt/dynamorio/bin"],
        "Windows": ["C:\\Program Files\\DynamoRIO", "C:\\DynamoRIO"],
    }

    # DynamoRIO utilities
    tool_executables = {
        "drrun": "drrun",
        "drcov": "drcov",
        "drsym": "drsym",
        "drstrace": "drstrace",
        "drmemory": "drmemory",
    }

    def __init__(self, required: bool = False):
        super().__init__(required)
        self._base_path: str | None = None

    def find_tool(self) -> Any:
        """Find DynamoRIO installation directory."""
        if self._location:
            return self._location if self._location.is_valid else None

        # Try to find drrun first
        for exe_name in self.executable_names:
            path = self._find_executable(exe_name)
            if path:
                # Determine base path (bin directory)
                bin_path = Path(path).parent
                self._base_path = str(bin_path)

                location = type(self._location)  # ToolLocation
                location.path = path
                location.version = self._extract_version(path)
                location.is_valid = True
                self._location = location
                return location

        # Search common paths
        system = self.get_platform()
        common_paths = self.common_paths.get(system, [])

        for base_path in common_paths:
            # Expand ~
            expanded = os.path.expanduser(base_path)
            if os.path.isdir(expanded):
                # Check for bin subdirectory
                bin_path = os.path.join(expanded, "bin64") if system == "Windows" else os.path.join(expanded, "bin")
                if os.path.isdir(bin_path):
                    drrun_path = os.path.join(bin_path, "drrun" + (".exe" if system == "Windows" else ""))
                    if os.path.isfile(drrun_path):
                        self._base_path = bin_path
                        from ..core.tool_infrastructure import ToolLocation

                        location = ToolLocation(path=drrun_path, version=self._extract_version(drrun_path))
                        self._location = location
                        return location

        return None

    def _find_executable(self, name: str) -> str | None:
        """Find specific DynamoRIO executable."""
        suffix = ".exe" if self.get_platform() == "Windows" else ""
        return shutil.which(name + suffix) or shutil.which(name)

    def get_tool_path(self, tool_name: str) -> str | None:
        """Get path to specific DynamoRIO tool."""
        if not self._base_path:
            if not self.find_tool():
                return None

        tool_exe = self.tool_executables.get(tool_name, tool_name)
        suffix = ".exe" if self.get_platform() == "Windows" else ""

        tool_path = os.path.join(self._base_path, tool_exe + suffix)
        if os.path.isfile(tool_path):
            return tool_path

        return None

    def get_version_args(self) -> list[str]:
        return ["--version"]

    def _extract_version(self, path: str) -> str:
        """Extract DynamoRIO version from executable."""
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # DynamoRIO version format: "DynamoRIO version 10.0.0"
                match = re.search(r"version\s+(\d+\.\d+\.\d+)", result.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return ""


# Global instance
_dynamorio_instance: DynamoRIOTool | None = None


def get_dynamorio() -> DynamoRIOTool:
    """Get or create DynamoRIO tool instance."""
    global _dynamorio_instance
    if _dynamorio_instance is None:
        _dynamorio_instance = DynamoRIOTool()
    return _dynamorio_instance


def check_dynamorio_available() -> bool:
    """Check if DynamoRIO is available."""
    return get_dynamorio().is_available()


def _ensure_dynamorio() -> str:
    """Ensure DynamoRIO is available and return drrun path."""
    dynamorio = get_dynamorio()
    if not dynamorio.is_available():
        raise RuntimeError("DynamoRIO not found. Install from https://dynamorio.org")
    path = dynamorio.get_tool_path("drrun")
    if not path:
        raise RuntimeError("drrun executable not found")
    return path


# ============================================================================
# Tool Functions
# ============================================================================


def dynamorio_run(binary: str, args: str, client_lib: str = "", output_dir: str = "") -> str:
    """Run binary under DynamoRIO instrumentation.

    Args:
        binary: Target binary path
        args: Command-line arguments for binary
        client_lib: Optional custom client library path
        output_dir: Optional output directory for logs

    Returns:
        DynamoRIO execution output
    """
    drrun_path = _ensure_dynamorio()

    cmd = [drrun_path]

    # Add client library if specified
    if client_lib:
        cmd.extend(["-c", client_lib])

    # Add output directory if specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        cmd.extend(["-out_dir", output_dir])

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
        return "Error: DynamoRIO run timed out after 5 minutes"
    except Exception as e:
        return f"Error: {e}"


def dynamorio_coverage(binary: str, args: str, output_file: str = "") -> str:
    """Run binary with code coverage analysis using drcov.

    Args:
        binary: Target binary path
        args: Command-line arguments
        output_file: Optional output file for coverage data

    Returns:
        Coverage analysis output
    """
    dynamorio = get_dynamorio()
    if not dynamorio.is_available():
        return "Error: DynamoRIO not available"

    drcov_path = dynamorio.get_tool_path("drcov")
    if not drcov_path:
        return "Error: drcov tool not found"

    cmd = [drcov_path]

    if output_file:
        cmd.extend(["-out_file", output_file])

    cmd.append("--")
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

        return result.stdout or "Coverage analysis complete"

    except subprocess.TimeoutExpired:
        return "Error: Coverage analysis timed out"
    except Exception as e:
        return f"Error: {e}"


def dynamorio_symbols(binary: str) -> str:
    """Extract symbols from binary using drsym.

    Args:
        binary: Binary path

    Returns:
        Symbol list output
    """
    dynamorio = get_dynamorio()
    if not dynamorio.is_available():
        return "Error: DynamoRIO not available"

    drsym_path = dynamorio.get_tool_path("drsym")
    if not drsym_path:
        return "Error: drsym tool not found"

    cmd = [drsym_path, "--", binary]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        return result.stdout

    except subprocess.TimeoutExpired:
        return "Error: Symbol extraction timed out"
    except Exception as e:
        return f"Error: {e}"


def dynamorio_strace(binary: str, args: str) -> str:
    """Trace system calls with drstrace.

    Args:
        binary: Target binary path
        args: Command-line arguments

    Returns:
        System call trace output
    """
    dynamorio = get_dynamorio()
    if not dynamorio.is_available():
        return "Error: DynamoRIO not available"

    drstrace_path = dynamorio.get_tool_path("drstrace")
    if not drstrace_path:
        return "Error: drstrace tool not found"

    cmd = [drstrace_path, "--", binary]
    if args:
        cmd.extend(args.split())

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        return result.stdout

    except subprocess.TimeoutExpired:
        return "Error: System call trace timed out"
    except Exception as e:
        return f"Error: {e}"


def dynamorio_memory(binary: str, args: str, leaks_only: bool = False) -> str:
    """Detect memory errors with Dr. Memory.

    Args:
        binary: Target binary path
        args: Command-line arguments
        leaks_only: Only report memory leaks

    Returns:
        Memory analysis output
    """
    dynamorio = get_dynamorio()
    if not dynamorio.is_available():
        return "Error: DynamoRIO not available"

    drmemory_path = dynamorio.get_tool_path("drmemory")
    if not drmemory_path:
        return "Error: Dr. Memory tool not found"

    cmd = [drmemory_path]

    if leaks_only:
        cmd.append("--leaks_only")

    cmd.append("--")
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

        return result.stdout or "Memory analysis complete"

    except subprocess.TimeoutExpired:
        return "Error: Memory analysis timed out"
    except Exception as e:
        return f"Error: {e}"


def dynamorio_analyze_trace(trace_file: str) -> str:
    """Analyze DynamoRIO trace file.

    Args:
        trace_file: Path to trace file

    Returns:
        Analysis results
    """
    if not os.path.isfile(trace_file):
        return f"Error: Trace file not found: {trace_file}"

    try:
        # Read and analyze trace file
        with open(trace_file) as f:
            trace_data = f.read()

        # Basic analysis
        lines = trace_data.split("\n")
        basic_blocks = len([ln for ln in lines if ln.strip() and not ln.startswith("#")])

        output = [
            f"Trace Analysis: {trace_file}",
            f"Total basic blocks: {basic_blocks}",
            f"Total lines: {len(lines)}",
        ]

        return "\n".join(output)

    except Exception as e:
        return f"Error analyzing trace: {e}"


# ============================================================================
# Tool Definitions
# ============================================================================


def create_dynamorio_tools() -> list[ToolDefinition]:
    """Create DynamoRIO tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="dynamorio_run",
            description="Run binary under DynamoRIO with optional custom client library",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
                ParameterSchema(
                    name="client_lib",
                    type="string",
                    description="Custom client library path (optional)",
                    required=False,
                    default="",
                ),
                ParameterSchema(
                    name="output_dir",
                    type="string",
                    description="Output directory for logs (optional)",
                    required=False,
                    default="",
                ),
            ],
            handler=lambda binary, args="", client_lib="", output_dir="", **kwargs: dynamorio_run(
                binary, args, client_lib, output_dir
            ),
        ),
        ToolDefinition(
            name="dynamorio_coverage",
            description="Run code coverage analysis using drcov",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
                ParameterSchema(
                    name="output_file",
                    type="string",
                    description="Output file for coverage data",
                    required=False,
                    default="",
                ),
            ],
            handler=lambda binary, args="", output_file="", **kwargs: dynamorio_coverage(binary, args, output_file),
        ),
        ToolDefinition(
            name="dynamorio_symbols",
            description="Extract symbols from binary using drsym",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
            ],
            handler=lambda binary, **kwargs: dynamorio_symbols(binary),
        ),
        ToolDefinition(
            name="dynamorio_strace",
            description="Trace system calls with drstrace",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
            ],
            handler=lambda binary, args="", **kwargs: dynamorio_strace(binary, args),
        ),
        ToolDefinition(
            name="dynamorio_memory",
            description="Detect memory errors with Dr. Memory",
            category="debugging",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
                ParameterSchema(
                    name="leaks_only",
                    type="boolean",
                    description="Only report memory leaks",
                    required=False,
                    default=False,
                ),
            ],
            handler=lambda binary, args="", leaks_only=False, **kwargs: dynamorio_memory(binary, args, leaks_only),
        ),
        ToolDefinition(
            name="dynamorio_analyze_trace",
            description="Analyze DynamoRIO trace file",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(name="trace_file", type="string", description="Path to trace file", required=True),
            ],
            handler=lambda trace_file, **kwargs: dynamorio_analyze_trace(trace_file),
        ),
    ]


def register_dynamorio_tools(registry: Any) -> int:
    """Register DynamoRIO tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_dynamorio_available():
        log_debug("DynamoRIO not available, skipping tool registration")
        return 0

    tools = create_dynamorio_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} DynamoRIO tools")
    return len(tools)
