"""Radare2 disassembler and reverse engineering tool integration.

Provides tools for:
- Opening and analyzing binaries
- Disassembly
- String extraction
- Function analysis
- Cross-references
- Symbol analysis
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from typing import Any

from ..core.logging import log_debug, log_info
from ..core.tool_infrastructure import ExternalTool
from ..tools.base import ParameterSchema, ToolDefinition


class Radare2Tool(ExternalTool):
    """Radare2 reverse engineering tool."""

    tool_name = "Radare2"
    executable_names = ["r2", "radare2"]
    common_paths = {
        "Linux": ["/usr/bin", "/usr/local/bin", "~/.local/bin"],
        "Darwin": ["/usr/local/bin", "/opt/homebrew/bin"],
        "Windows": ["C:\\radare2", "C:\\Program Files\\radare2"],
    }

    def get_version_args(self) -> list[str]:
        return ["-v"]

    def _extract_version(self, output: str) -> str:
        """Extract Radare2 version."""
        match = re.search(r"radare2\s+(\d+\.\d+\.\d+)", output, re.IGNORECASE)
        return match.group(1) if match else ""


# Global instance
_r2_instance: Radare2Tool | None = None


def get_radare2() -> Radare2Tool:
    """Get or create Radare2 tool instance."""
    global _r2_instance
    if _r2_instance is None:
        _r2_instance = Radare2Tool()
    return _r2_instance


def check_radare2_available() -> bool:
    """Check if Radare2 is available."""
    return get_radare2().is_available()


def _ensure_radare2() -> str:
    """Ensure Radare2 is available and return its path."""
    r2 = get_radare2()
    if not r2.is_available():
        raise RuntimeError("Radare2 not found. Install from https://rada.re")
    return r2.get_path()


def _run_r2_command(binary: str, commands: list[str], analyze: bool = False) -> str:
    """Run Radare2 commands on binary.

    Args:
        binary: Binary path
        commands: List of r2 commands
        analyze: Whether to analyze binary first

    Returns:
        Command output
    """
    r2_path = _ensure_radare2()

    if not os.path.isfile(binary):
        return f"Error: Binary not found: {binary}"

    # Build r2 script
    script_commands = []
    if analyze:
        script_commands.append("aaa")  # Analyze all

    script_commands.extend(commands)
    script_commands.append("q")  # Quit

    script = "\n".join(script_commands)

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".r2", delete=False) as f:
            f.write(script)
            script_path = f.name

        cmd = [r2_path, "-q", "-i", script_path, binary]

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
        return "Error: Radare2 operation timed out"
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


def radare2_open(binary: str) -> str:
    """Open binary in Radare2 and show basic info.

    Args:
        binary: Binary path

    Returns:
        Binary information
    """
    commands = [
        "i",  # Info
        "ii",  # Imports
        "ie",  # Exports
        "is",  # Symbols
    ]

    return _run_r2_command(binary, commands, analyze=False)


def radare2_disassemble(binary: str, address: str, num_lines: int = 10) -> str:
    """Disassemble at address.

    Args:
        binary: Binary path
        address: Address (hex string or "main" for entry)
        num_lines: Number of lines

    Returns:
        Disassembly output
    """
    addr = "main" if address.lower() == "main" else address

    commands = [
        f"s {addr}",  # Seek to address
        f"pd {num_lines}",  # Print disassembly
    ]

    return _run_r2_command(binary, commands, analyze=True)


def radare2_analyze_functions(binary: str) -> str:
    """Analyze all functions.

    Args:
        binary: Binary path

    Returns:
        Function analysis output
    """
    commands = [
        "aaa",  # Analyze all
        "afl",  # List functions
    ]

    return _run_r2_command(binary, commands, analyze=False)


def radare2_get_strings(binary: str, min_length: int = 4) -> str:
    """Extract strings from binary.

    Args:
        binary: Binary path
        min_length: Minimum string length

    Returns:
        Strings output
    """
    commands = [
        f"iz {min_length}",  # List strings
    ]

    return _run_r2_command(binary, commands, analyze=False)


def radare2_xrefs(binary: str, address: str) -> str:
    """Get cross-references.

    Args:
        binary: Binary path
        address: Address

    Returns:
        Cross-references output
    """
    commands = [
        f"s {address}",  # Seek to address
        "axt",  # Cross-references to
        "axf",  # Cross-references from
    ]

    return _run_r2_command(binary, commands, analyze=True)


def radare2_imports(binary: str) -> str:
    """Get imported functions.

    Args:
        binary: Binary path

    Returns:
        Imports output
    """
    commands = [
        "ii",  # Imports
    ]

    return _run_r2_command(binary, commands, analyze=False)


def radare2_exports(binary: str) -> str:
    """Get exported functions.

    Args:
        binary: Binary path

    Returns:
        Exports output
    """
    commands = [
        "ie",  # Exports
    ]

    return _run_r2_command(binary, commands, analyze=False)


def radare2_sections(binary: str) -> str:
    """Get binary sections.

    Args:
        binary: Binary path

    Returns:
        Sections output
    """
    commands = [
        "iS",  # Sections
    ]

    return _run_r2_command(binary, commands, analyze=False)


def radare2_entropy(binary: str) -> str:
    """Calculate entropy of sections.

    Args:
        binary: Binary path

    Returns:
        Entropy analysis output
    """
    commands = [
        "iS",  # Get sections first
        "pc",  # Calculate entropy
    ]

    return _run_r2_command(binary, commands, analyze=False)


def radare2_search(binary: str, pattern: str, type: str = "hex") -> str:
    """Search for pattern in binary.

    Args:
        binary: Binary path
        pattern: Search pattern
        type: Pattern type (hex|string|asm)

    Returns:
        Search results
    """
    if type == "hex":
        cmd = f"x {pattern}"
    elif type == "string":
        cmd = f"/ {pattern}"
    elif type == "asm":
        cmd = f"/a {pattern}"
    else:
        cmd = f"/x {pattern}"

    commands = [
        cmd,
    ]

    return _run_r2_command(binary, commands, analyze=False)


def radare2_function_info(binary: str, function: str) -> str:
    """Get function information.

    Args:
        binary: Binary path
        function: Function name or address

    Returns:
        Function info
    """
    commands = [
        f"s {function}",  # Seek to function
        "afi",  # Function info
        "pdf",  # Print disassembly of function
    ]

    return _run_r2_command(binary, commands, analyze=True)


def radare2_hexdump(binary: str, address: str, size: int = 256) -> str:
    """Hex dump at address.

    Args:
        binary: Binary path
        address: Address
        size: Number of bytes

    Returns:
        Hex dump output
    """
    commands = [
        f"s {address}",  # Seek to address
        f"px {size}",  # Print hex
    ]

    return _run_r2_command(binary, commands, analyze=False)


def radare2_write_bytes(binary: str, address: str, bytes: str) -> str:
    """Write bytes to binary (requires write mode).

    Args:
        binary: Binary path
        address: Address
        bytes: Hex bytes to write

    Returns:
        Write result
    """
    commands = [
        f"s {address}",  # Seek to address
        f"wx {bytes}",  # Write hex
    ]

    # Note: This requires opening with -w flag
    r2_path = _ensure_radare2()

    script = "\n".join([*commands, "q"])

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".r2", delete=False) as f:
            f.write(script)
            script_path = f.name

        cmd = [r2_path, "-q", "-w", "-i", script_path, binary]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        return result.stdout or "Bytes written (use -w flag for write mode)"

    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


# ============================================================================
# Tool Definitions
# ============================================================================


def create_radare2_tools() -> list[ToolDefinition]:
    """Create Radare2 tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="radare2_open",
            description="Open binary in Radare2 and show basic info",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
            ],
            handler=lambda binary, **kwargs: radare2_open(binary),
        ),
        ToolDefinition(
            name="radare2_disassemble",
            description="Disassemble code at address",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(name="address", type="string", description="Address (hex or 'main')", required=True),
                ParameterSchema(
                    name="num_lines", type="integer", description="Number of lines", required=False, default=10
                ),
            ],
            handler=lambda binary, address, num_lines=10, **kwargs: radare2_disassemble(binary, address, num_lines),
        ),
        ToolDefinition(
            name="radare2_analyze_functions",
            description="Analyze all functions in binary",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
            ],
            handler=lambda binary, **kwargs: radare2_analyze_functions(binary),
        ),
        ToolDefinition(
            name="radare2_get_strings",
            description="Extract strings from binary",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(
                    name="min_length", type="integer", description="Minimum string length", required=False, default=4
                ),
            ],
            handler=lambda binary, min_length=4, **kwargs: radare2_get_strings(binary, min_length),
        ),
        ToolDefinition(
            name="radare2_xrefs",
            description="Get cross-references for address",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(name="address", type="string", description="Address", required=True),
            ],
            handler=lambda binary, address, **kwargs: radare2_xrefs(binary, address),
        ),
        ToolDefinition(
            name="radare2_imports",
            description="Get imported functions",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
            ],
            handler=lambda binary, **kwargs: radare2_imports(binary),
        ),
        ToolDefinition(
            name="radare2_exports",
            description="Get exported functions",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
            ],
            handler=lambda binary, **kwargs: radare2_exports(binary),
        ),
        ToolDefinition(
            name="radare2_sections",
            description="Get binary sections",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
            ],
            handler=lambda binary, **kwargs: radare2_sections(binary),
        ),
        ToolDefinition(
            name="radare2_entropy",
            description="Calculate entropy of sections",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
            ],
            handler=lambda binary, **kwargs: radare2_entropy(binary),
        ),
        ToolDefinition(
            name="radare2_search",
            description="Search for pattern in binary",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(name="pattern", type="string", description="Search pattern", required=True),
                ParameterSchema(
                    name="type",
                    type="string",
                    description="Pattern type",
                    required=False,
                    default="hex",
                    enum=["hex", "string", "asm"],
                ),
            ],
            handler=lambda binary, pattern, type="hex", **kwargs: radare2_search(binary, pattern, type),
        ),
        ToolDefinition(
            name="radare2_function_info",
            description="Get function information and disassembly",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(name="function", type="string", description="Function name or address", required=True),
            ],
            handler=lambda binary, function, **kwargs: radare2_function_info(binary, function),
        ),
        ToolDefinition(
            name="radare2_hexdump",
            description="Hex dump at address",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(name="address", type="string", description="Address", required=True),
                ParameterSchema(
                    name="size", type="integer", description="Number of bytes", required=False, default=256
                ),
            ],
            handler=lambda binary, address, size=256, **kwargs: radare2_hexdump(binary, address, size),
        ),
        ToolDefinition(
            name="radare2_write_bytes",
            description="Write bytes to binary (requires write mode)",
            category="disassembler",
            parameters=[
                ParameterSchema(name="binary", type="string", description="Binary path", required=True),
                ParameterSchema(name="address", type="string", description="Address", required=True),
                ParameterSchema(name="bytes", type="string", description="Hex bytes to write", required=True),
            ],
            handler=lambda binary, address, bytes, **kwargs: radare2_write_bytes(binary, address, bytes),
        ),
    ]


def register_radare2_tools(registry: Any) -> int:
    """Register Radare2 tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_radare2_available():
        log_debug("Radare2 not available, skipping tool registration")
        return 0

    tools = create_radare2_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} Radare2 tools")
    return len(tools)
