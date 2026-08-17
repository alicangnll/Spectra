"""Frida dynamic instrumentation tool integration.

Provides tools for:
- Attaching Frida to running processes
- Spawning processes with Frida instrumentation
- Listing devices and processes
- Running JavaScript instrumentation scripts
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Any

from ..core.logging import log_debug, log_info
from ..core.tool_infrastructure import ExternalTool
from ..tools.base import ParameterSchema, ToolDefinition


class FridaTool(ExternalTool):
    """Frida dynamic instrumentation tool."""

    tool_name = "Frida"
    executable_names = ["frida", "frida.exe"]
    common_paths = {
        "Linux": ["/usr/bin", "/usr/local/bin", "~/.local/bin"],
        "Darwin": ["/usr/local/bin", "/opt/homebrew/bin", "~/.local/bin"],
        "Windows": ["C:\\Program Files\\Frida", "%LOCALAPPDATA%\\Frida"],
    }

    def get_version_args(self) -> list[str]:
        return ["--version"]

    def _extract_version(self, output: str) -> str:
        """Extract Frida version."""
        import re

        match = re.search(r"Frida\s+(\d+\.\d+\.\d+)", output)
        return match.group(1) if match else ""


# Global Frida tool instance
_frida_instance: FridaTool | None = None


def get_frida() -> FridaTool:
    """Get or create Frida tool instance."""
    global _frida_instance
    if _frida_instance is None:
        _frida_instance = FridaTool()
    return _frida_instance


def check_frida_available() -> bool:
    """Check if Frida is available."""
    return get_frida().is_available()


def _ensure_frida() -> str:
    """Ensure Frida is available and return its path.

    Raises:
        RuntimeError: If Frida not available
    """
    frida = get_frida()
    if not frida.is_available():
        raise RuntimeError("Frida not found. Install from https://frida.re")
    return frida.get_path()


def _validate_device(device: str) -> bool:
    """Validate device identifier."""
    # Valid device formats: "local", "usb", "remote", or IP address
    if device in ("local", "usb", "remote"):
        return True

    # Check if it looks like an IP address
    import re

    if re.match(r"^(\d{1,3}\.){3}\d{1,3}(:\d+)?$", device):
        return True

    return False


# ============================================================================
# Tool Functions
# ============================================================================


def frida_list_devices() -> str:
    """List available Frida devices.

    Returns:
        JSON string of device list
    """
    frida_path = _ensure_frida()

    try:
        result = subprocess.run(
            [frida_path, "list", "devices"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return f"Error listing devices: {result.stderr}"

        return result.stdout

    except subprocess.TimeoutExpired:
        return "Error: Frida list devices timed out"
    except Exception as e:
        return f"Error: {e}"


def frida_list_processes(device: str = "local") -> str:
    """List processes on device.

    Args:
        device: Device identifier (default: "local")

    Returns:
        JSON string of process list
    """
    frida_path = _ensure_frida()

    if not _validate_device(device):
        return f"Error: Invalid device identifier '{device}'"

    try:
        result = subprocess.run(
            [frida_path, "-d", device, "ps", "aux"],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            return f"Error listing processes: {result.stderr}"

        return result.stdout

    except subprocess.TimeoutExpired:
        return "Error: Frida ps timed out"
    except Exception as e:
        return f"Error: {e}"


def frida_attach(target: str | int, script: str, device: str = "local") -> str:
    """Attach Frida to target process with instrumentation script.

    Args:
        target: Process name or PID
        script: JavaScript instrumentation script
        device: Device identifier (default: "local")

    Returns:
        Output from Frida instrumentation
    """
    frida_path = _ensure_frida()

    if not _validate_device(device):
        return f"Error: Invalid device identifier '{device}'"

    # Save script to temp file
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(script)
            script_path = f.name
    except Exception as e:
        return f"Error creating script file: {e}"

    try:
        cmd = [frida_path, "-d", device, "attach", str(target), "-l", script_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes
        )

        if result.returncode != 0:
            return f"Error attaching Frida: {result.stderr}"

        return result.stdout or "Frida attached successfully"

    except subprocess.TimeoutExpired:
        return "Error: Frida attach timed out after 5 minutes"
    except Exception as e:
        return f"Error: {e}"
    finally:
        # Clean up temp file
        try:
            os.unlink(script_path)
        except Exception:
            pass


def frida_spawn(target: str, args: str, script: str, device: str = "local") -> str:
    """Spawn target process with Frida instrumentation.

    Args:
        target: Target binary path
        args: Command-line arguments
        script: JavaScript instrumentation script
        device: Device identifier (default: "local")

    Returns:
        Output from Frida instrumentation
    """
    frida_path = _ensure_frida()

    if not _validate_device(device):
        return f"Error: Invalid device identifier '{device}'"

    # Save script to temp file
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(script)
            script_path = f.name
    except Exception as e:
        return f"Error creating script file: {e}"

    try:
        cmd = [frida_path, "-d", device, "spawn", target, "--", *args.split(), "-l", script_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            return f"Error spawning with Frida: {result.stderr}"

        return result.stdout or "Frida spawn successful"

    except subprocess.TimeoutExpired:
        return "Error: Frida spawn timed out after 5 minutes"
    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def frida_kill(target: str | int, device: str = "local") -> str:
    """Kill process attached/spawned by Frida.

    Args:
        target: Process name or PID
        device: Device identifier (default: "local")

    Returns:
        Result message
    """
    frida_path = _ensure_frida()

    if not _validate_device(device):
        return f"Error: Invalid device identifier '{device}'"

    try:
        result = subprocess.run(
            [frida_path, "-d", device, "kill", str(target)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return f"Error killing process: {result.stderr}"

        return f"Process {target} killed"

    except subprocess.TimeoutExpired:
        return "Error: Frida kill timed out"
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Tool Definitions
# ============================================================================


def create_frida_tools() -> list[ToolDefinition]:
    """Create Frida tool definitions.

    Returns:
        List of ToolDefinition objects
    """
    return [
        ToolDefinition(
            name="frida_list_devices",
            description="List available Frida devices (local, USB, remote)",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(
                    name="device", type="string", description="Device identifier filter (optional)", required=False
                ),
            ],
            handler=lambda **kwargs: frida_list_devices(),
        ),
        ToolDefinition(
            name="frida_list_processes",
            description="List processes on Frida device",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(
                    name="device",
                    type="string",
                    description="Device identifier (default: local)",
                    required=False,
                    default="local",
                ),
            ],
            handler=lambda device="local", **kwargs: frida_list_processes(device),
        ),
        ToolDefinition(
            name="frida_attach",
            description="Attach Frida to running process with JavaScript instrumentation",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(name="target", type="string", description="Process name or PID", required=True),
                ParameterSchema(
                    name="script", type="string", description="JavaScript instrumentation script", required=True
                ),
                ParameterSchema(
                    name="device",
                    type="string",
                    description="Device identifier (default: local)",
                    required=False,
                    default="local",
                ),
            ],
            handler=lambda target, script, device="local", **kwargs: frida_attach(target, script, device),
        ),
        ToolDefinition(
            name="frida_spawn",
            description="Spawn process with Frida instrumentation",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(name="target", type="string", description="Target binary path", required=True),
                ParameterSchema(
                    name="args", type="string", description="Command-line arguments", required=False, default=""
                ),
                ParameterSchema(
                    name="script", type="string", description="JavaScript instrumentation script", required=True
                ),
                ParameterSchema(
                    name="device",
                    type="string",
                    description="Device identifier (default: local)",
                    required=False,
                    default="local",
                ),
            ],
            handler=lambda target, script, args="", device="local", **kwargs: frida_spawn(target, args, script, device),
        ),
        ToolDefinition(
            name="frida_kill",
            description="Kill process attached/spawned by Frida",
            category="dynamic_analysis",
            parameters=[
                ParameterSchema(name="target", type="string", description="Process name or PID", required=True),
                ParameterSchema(
                    name="device",
                    type="string",
                    description="Device identifier (default: local)",
                    required=False,
                    default="local",
                ),
            ],
            handler=lambda target, device="local", **kwargs: frida_kill(target, device),
        ),
    ]


# Auto-detection function for tool registry
def register_frida_tools(registry: Any) -> int:
    """Register Frida tools if available.

    Args:
        registry: ToolRegistry instance

    Returns:
        Number of tools registered
    """
    if not check_frida_available():
        log_debug("Frida not available, skipping tool registration")
        return 0

    tools = create_frida_tools()
    for tool in tools:
        registry.register(tool)

    log_info(f"Registered {len(tools)} Frida tools")
    return len(tools)
