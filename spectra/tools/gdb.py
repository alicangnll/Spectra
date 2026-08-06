"""GDB debugger tool integration.

Provides tools for:
- Attaching GDB to processes
- Running binaries under GDB
- Setting breakpoints
- Reading memory and registers
- Controlling program execution
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from typing import Any

from ..core.tool_infrastructure import ExternalTool
from ..core.logging import log_debug, log_error, log_info
from ..tools.base import ParameterSchema, ToolDefinition


class GDBTool(ExternalTool):
    """GDB debugger tool."""

    tool_name = "GDB"
    executable_names = ["gdb", "gdb.exe"]
    common_paths = {
        "Linux": ["/usr/bin", "/usr/local/bin"],
        "Darwin": ["/usr/local/bin", "/opt/homebrew/bin"],
        "Windows": ["C:\\MinGW\\bin", "C:\\msys64\\mingw64\\bin"],
    }

    def get_version_args(self) -> list[str]:
        return ["--version"]

    def _extract_version(self, output: str) -> str:
        """Extract GDB version."""
        match = re.search(r"GNU gdb.*?\((\d+\.\d+)", output, re.IGNORECASE)
        return match.group(1) if match else ""


_gdb_instance: GDBTool | None = None


def get_gdb() -> GDBTool:
    """Get or create GDB tool instance."""
    global _gdb_instance
    if _gdb_instance is None:
        _gdb_instance = GDBTool()
    return _gdb_instance


def check_gdb_available() -> bool:
    """Check if GDB is available."""
    return get_gdb().is_available()


def _ensure_gdb() -> str:
    """Ensure GDB is available and return its path."""
    gdb = get_gdb()
    if not gdb.is_available():
        raise RuntimeError("GDB not found. Install gdb package")
    return gdb.get_path()


def _create_gdb_script(commands: list[str]) -> str:
    """Create GDB script file from commands.

    Args:
        commands: List of GDB commands

    Returns:
        Path to script file
    """
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gdb', delete=False) as f:
            for cmd in commands:
                f.write(cmd + "\n")
            return f.name
    except Exception as e:
        raise RuntimeError(f"Failed to create GDB script: {e}")


def gdb_attach(pid: int, commands: list[str] | None = None) -> str:
    """Attach GDB to process.

    Args:
        pid: Process ID
        commands: Optional list of GDB commands to run

    Returns:
        GDB output
    """
    gdb_path = _ensure_gdb()

    # Build GDB command
    cmd = [gdb_path, "-q", "-batch"]

    if commands:
        script_path = _create_gdb_script(commands)
        cmd.extend(["-x", script_path])

    cmd.extend(["-p", str(pid)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(result.stderr)

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: GDB attach timed out"
    except Exception as e:
        return f"Error: {e}"


def gdb_run(binary: str, args: str, breakpoints: list[int], commands: list[str] | None = None) -> str:
    """Run binary under GDB with breakpoints.

    Args:
        binary: Binary path
        args: Command-line arguments
        breakpoints: List of breakpoint addresses
        commands: Optional list of additional commands

    Returns:
        GDB output
    """
    gdb_path = _ensure_gdb()

    # Build GDB script
    gdb_commands = []

    # Set breakpoints
    for bp in breakpoints:
        gdb_commands.append(f"break *{bp}")

    # Add user commands
    if commands:
        gdb_commands.extend(commands)

    # Run and quit
    gdb_commands.append("run")
    gdb_commands.append("quit")

    script_path = _create_gdb_script(gdb_commands)

    cmd = [gdb_path, "-q", "-batch", "-x", script_path, binary]
    if args:
        cmd.extend(args.split())

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(result.stderr)

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: GDB run timed out"
    except Exception as e:
        return f"Error: {e}"


def gdb_get_registers(pid: int) -> str:
    """Get current register values.

    Args:
        pid: Process ID to attach to

    Returns:
        Register values
    """
    return gdb_attach(pid, ["info registers"])


def gdb_get_memory(pid: int, address: int, size: int) -> str:
    """Read memory at address.

    Args:
        pid: Process ID
        address: Memory address (hex or decimal)
        size: Number of bytes to read

    Returns:
        Memory dump
    """
    gdb_commands = [
        f"x/{size}xb 0x{address:x}",
    ]

    return gdb_attach(pid, gdb_commands)


def gdb_set_breakpoint(pid: int, address: int, condition: str = "") -> str:
    """Set breakpoint.

    Args:
        pid: Process ID
        address: Breakpoint address
        condition: Optional breakpoint condition

    Returns:
        Result message
    """
    gdb_commands = [f"break *{address:x}"]
    if condition:
        gdb_commands[0] += f" if {condition}"

    gdb_commands.append("info breakpoints")

    return gdb_attach(pid, gdb_commands)


def gdb_get_callstack(pid: int, max_frames: int = 10) -> str:
    """Get current call stack.

    Args:
        pid: Process ID
        max_frames: Maximum number of frames

    Returns:
        Call stack backtrace
    """
    gdb_commands = [
        f"backtrace {max_frames}",
    ]

    return gdb_attach(pid, gdb_commands)


def gdb_disassemble(pid: int, address: int, num_lines: int = 10) -> str:
    """Disassemble code at address.

    Args:
        pid: Process ID
        address: Address to disassemble at
        num_lines: Number of instructions

    Returns:
        Disassembly
    """
    gdb_commands = [
        f"disassemble {address:x}, +{num_lines}",
    ]

    return gdb_attach(pid, gdb_commands)


def create_gdb_tools() -> list[ToolDefinition]:
    """Create GDB tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="gdb_attach",
            description="Attach GDB to running process",
            category="debugging",
            parameters=[
                ParameterSchema(name="pid", type="integer", description="Process ID", required=True),
                ParameterSchema(name="commands", type="string", description="Optional GDB commands (semicolon-separated)", required=False, default=""),
            ],
            handler=lambda pid, commands="", **kwargs: gdb_attach(
                pid,
                commands.split(";") if commands else None
            ),
        ),

        ToolDefinition(
            name="gdb_run",
            description="Run binary under GDB with breakpoints",
            category="debugging",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(name="args", type="string", description="Command-line arguments", required=False, default=""),
                ParameterSchema(name="breakpoints", type="string", description="Comma-separated breakpoint addresses (hex)", required=False, default=""),
                ParameterSchema(name="commands", type="string", description="Additional GDB commands (semicolon-separated)", required=False, default=""),
            ],
            handler=lambda binary, args="", breakpoints="", commands="", **kwargs: gdb_run(
                binary,
                args,
                [int(bp, 16) for bp in breakpoints.split(",") if breakpoints],
                commands.split(";") if commands else None
            ),
        ),

        ToolDefinition(
            name="gdb_get_registers",
            description="Get register values from attached process",
            category="debugging",
            parameters=[
                ParameterSchema(name="pid", type="integer", description="Process ID", required=True),
            ],
            handler=lambda pid, **kwargs: gdb_get_registers(pid),
        ),

        ToolDefinition(
            name="gdb_get_memory",
            description="Read memory at address from attached process",
            category="debugging",
            parameters=[
                ParameterSchema(name="pid", type="integer", description="Process ID", required=True),
                ParameterSchema(name="address", type="string", description="Memory address (hex)", required=True),
                ParameterSchema(name="size", type="integer", description="Number of bytes", required=True, default=256),
            ],
            handler=lambda pid, address, size=256, **kwargs: gdb_get_memory(
                pid,
                int(address, 16) if isinstance(address, str) else address,
                size
            ),
        ),

        ToolDefinition(
            name="gdb_set_breakpoint",
            description="Set breakpoint in attached process",
            category="debugging",
            parameters=[
                ParameterSchema(name="pid", type="integer", description="Process ID", required=True),
                ParameterSchema(name="address", type="string", description="Breakpoint address (hex)", required=True),
                ParameterSchema(name="condition", type="string", description="Breakpoint condition", required=False, default=""),
            ],
            handler=lambda pid, address, condition="", **kwargs: gdb_set_breakpoint(pid, int(address, 16), condition),
        ),

        ToolDefinition(
            name="gdb_get_callstack",
            description="Get call stack backtrace",
            category="debugging",
            parameters=[
                ParameterSchema(name="pid", type="integer", description="Process ID", required=True),
                ParameterSchema(name="max_frames", type="integer", description="Maximum frames", required=False, default=10),
            ],
            handler=lambda pid, max_frames=10, **kwargs: gdb_get_callstack(pid, max_frames),
        ),

        ToolDefinition(
            name="gdb_disassemble",
            description="Disassemble code at address",
            category="debugging",
            parameters=[
                ParameterSchema(name="pid", type="integer", description="Process ID", required=True),
                ParameterSchema(name="address", type="string", description="Address (hex)", required=True),
                ParameterSchema(name="num_lines", type="integer", description="Number of instructions", required=False, default=10),
            ],
            handler=lambda pid, address, num_lines=10, **kwargs: gdb_disassemble(pid, int(address, 16), num_lines),
        ),
    ]


def register_gdb_tools(registry: Any) -> int:
    """Register GDB tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_gdb_available():
        log_debug("GDB not available, skipping tool registration")
        return 0

    tools = create_gdb_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} GDB tools")
    return len(tools)
