"""Tool integration infrastructure for external security tools.

This module provides base classes and utilities for integrating external tools
(Frida, GDB, Wireshark, etc.) into Spectra's tool framework.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .logging import log_debug, log_error, log_info


@dataclass
class ToolLocation:
    """Represents a discovered tool location."""

    path: str
    version: str = ""
    is_valid: bool = True


class ExternalTool:
    """Base class for external tool integrations.

    Provides common functionality for:
    - Tool discovery (PATH, common locations)
    - Version validation
    - Availability checking
    - Safe command execution

    Subclasses should override:
    - tool_name: Display name
    - executable_names: Possible executable names
    - common_paths: Platform-specific installation paths
    - version_args: Arguments to get version
    - version_pattern: Regex to extract version from output
    """

    tool_name: str = "base_tool"
    executable_names: list[str] = field(default_factory=list)
    common_paths: dict[str, list[str]] = field(default_factory=dict)

    def __init__(self, required: bool = False):
        self.required = required
        self._location: ToolLocation | None = None
        self._available: bool | None = None

    def get_platform(self) -> str:
        """Get current platform."""
        return platform.system()

    def find_tool(self) -> ToolLocation | None:
        """Search for tool in PATH and common locations.

        Returns ToolLocation if found, None otherwise.
        """
        if self._location:
            return self._location if self._location.is_valid else None

        # 1. Search PATH
        for exe_name in self.executable_names:
            path = shutil.which(exe_name)
            if path:
                location = ToolLocation(path=path)
                if self._validate_location(location):
                    self._location = location
                    return location

        # 2. Search common paths
        system = self.get_platform()
        common_paths = self.common_paths.get(system, [])

        for exe_name in self.executable_names:
            for base_path in common_paths:
                possible_paths = [
                    os.path.join(base_path, exe_name),
                    os.path.join(base_path, exe_name + ".exe"),  # Windows
                    os.path.join(base_path, exe_name + ".app", "Contents", "MacOS", exe_name),  # macOS
                ]

                for possible_path in possible_paths:
                    if os.path.isfile(possible_path) and os.access(possible_path, os.X_OK):
                        location = ToolLocation(path=possible_path)
                        if self._validate_location(location):
                            self._location = location
                            return location

        # 3. Not found
        if self.required:
            log_error(f"{self.tool_name} not found. Install and add to PATH.")

        return None

    def _validate_location(self, location: ToolLocation) -> bool:
        """Validate that the tool at location is working.

        Runs version command and checks exit code.
        """
        try:
            result = subprocess.run(
                [location.path, *self.get_version_args()],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Extract version
                version = self._extract_version(result.stdout + result.stderr)
                location.version = version
                log_info(f"{self.tool_name} found: {location.path} (version {version or 'unknown'})")
                return True

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            log_debug(f"Failed to validate {self.tool_name} at {location.path}: {e}")

        location.is_valid = False
        return False

    def get_version_args(self) -> list[str]:
        """Return arguments to get version string."""
        return ["--version"]

    def _extract_version(self, output: str) -> str:
        """Extract version from tool output.

        Subclasses can override for custom version extraction.
        """
        # Look for common version patterns
        patterns = [
            r"v?(\d+\.\d+\.\d+)",
            r"v?(\d+\.\d+)",
            r"Version:?\s*(\d+\.\d+\.\d+)",
            r"version\s+(\d+\.\d+\.\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)

        return ""

    def is_available(self) -> bool:
        """Check if tool is available."""
        if self._available is not None:
            return self._available

        self._available = self.find_tool() is not None
        return self._available

    def get_path(self) -> str | None:
        """Get tool executable path."""
        location = self.find_tool()
        return location.path if location else None

    def run_command(self, args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """Run tool command with safety checks.

        Args:
            args: Command arguments
            timeout: Timeout in seconds

        Returns:
            subprocess.CompletedProcess result

        Raises:
            RuntimeError: If tool not available
            subprocess.TimeoutExpired: If command times out
        """
        path = self.get_path()
        if not path:
            raise RuntimeError(f"{self.tool_name} not available")

        cmd = [path, *args]

        log_debug(f"Running {self.tool_name}: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return result


class ToolSafety:
    """Safety checks for tool operations.

    Reuses existing shell_tools.py patterns for:
    - Dangerous command detection
    - Safe command whitelisting
    - Operation approval
    """

    # Dangerous patterns (from shell_tools.py)
    CRITICAL_PATTERNS = [
        r"\brm\b.*\s+-rf?\s*/",  # rm -rf /
        r"\bdd\b\s*if=/dev/zero",  # dd if=/devzero
        r"\bmkfs\b",  # Format filesystem
        r"\bfdisk\b",  # Partition disk
        r":\(REDACTED\)",  # Avoid redacted paths
    ]

    HIGH_RISK_PATTERNS = [
        r"\brm\b.*\s+",  # rm with arguments
        r"\bformat\b",  # Format commands
        r"\bwipe\b",  # Wipe commands
        r"\bshutdown\b",  # Shutdown
        r"\breboot\b",  # Reboot
    ]

    MEDIUM_RISK_PATTERNS = [
        r"\bcurl\b.*\|\s*sh",  # Pipe to shell
        r"\bwget\b.*\|\s*sh",  # Pipe to shell
        r"\bchmod\b.*777",  # chmod 777
    ]

    # Safe command prefixes
    SAFE_PREFIXES = {
        # Analysis tools
        "frida-",
        "tshark",
        "tcpdump",
        "ngrep",
        "gdb",
        "lldb",
        "windbg",
        "valgrind",
        "strace",
        "ltrace",
        "radare2",
        "r2",
        # File operations (read-only)
        "ls",
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "file",
        "strings",
        "hexdump",
        # Network (read-only)
        "netstat",
        "ss",
        "lsof",
        # System info
        "ps",
        "top",
        "htop",
        "vmstat",
        "free",
        "uname",
        "hostname",
        "id",
        "whoami",
    }

    @staticmethod
    def check_command_safety(command: str) -> tuple[bool, str, list[str]]:
        """Check if command is safe to execute.

        Args:
            command: Command string to check

        Returns:
            Tuple of (is_safe, reason, detected_patterns)
        """
        detected_patterns = []

        # Check critical patterns
        for pattern in ToolSafety.CRITICAL_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, "CRITICAL: System-destructive command blocked", [pattern]

        # Check high-risk patterns
        for pattern in ToolSafety.HIGH_RISK_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                detected_patterns.append(pattern)

        # Check medium-risk patterns
        for pattern in ToolSafety.MEDIUM_RISK_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                detected_patterns.append(pattern)

        # Check if command starts with safe prefix
        for prefix in ToolSafety.SAFE_PREFIXES:
            if command.strip().startswith(prefix):
                return True, "", []

        # If patterns detected, require approval
        if detected_patterns:
            return (
                False,
                f"Command requires approval: matched {len(detected_patterns)} risk patterns",
                detected_patterns,
            )

        # Unknown command - require approval
        return False, "Unknown command - requires approval", []

    @staticmethod
    def check_network_safety(operation: str, target: str = "") -> tuple[bool, str]:
        """Check if network operation is safe.

        Args:
            operation: Network operation (e.g., "sniff", "send", "scan")
            target: Target address/host

        Returns:
            Tuple of (is_safe, reason)
        """
        # Explicitly safe operations
        safe_operations = {"parse", "analyze", "read", "extract", "statistics"}
        if operation.lower() in safe_operations:
            return True, ""

        # Operations requiring approval
        approval_operations = {"sniff", "send", "inject", "flood", "scan"}
        if operation.lower() in approval_operations:
            return False, f"Network operation '{operation}' requires approval"

        # Explicitly blocked operations
        blocked_operations = {"flood", "dos", "syn flood"}
        if operation.lower() in blocked_operations:
            return False, f"CRITICAL: Network operation '{operation}' blocked"

        return False, "Unknown network operation - requires approval"

    @staticmethod
    def check_fuzzing_safety(duration: int = 0, memory_limit: int = 0) -> tuple[bool, str]:
        """Check if fuzzing parameters are safe.

        Args:
            duration: Fuzzing duration in seconds
            memory_limit: Memory limit in MB

        Returns:
            Tuple of (is_safe, reason)
        """
        # Enforce reasonable limits
        MAX_DURATION = 8 * 3600  # 8 hours
        MAX_MEMORY = 8 * 1024  # 8 GB

        if duration > MAX_DURATION:
            return False, f"Fuzzing duration {duration}s exceeds maximum {MAX_DURATION}s"

        if memory_limit > MAX_MEMORY:
            return False, f"Memory limit {memory_limit}MB exceeds maximum {MAX_MEMORY}MB"

        return True, ""


class ToolCapabilities:
    """Tool capability detection and management."""

    @staticmethod
    def detect_platform_capabilities() -> dict[str, bool]:
        """Detect platform-specific capabilities.

        Returns:
            Dict of capability names to boolean availability
        """
        capabilities = {
            "windows": platform.system() == "Windows",
            "linux": platform.system() == "Linux",
            "macos": platform.system() == "Darwin",
            "docker": ToolCapabilities._has_docker(),
            "kubernetes": ToolCapabilities._has_kubectl(),
            "root": os.geteuid() == 0 if platform.system() == "Linux" else False,
        }

        log_debug(f"Platform capabilities: {capabilities}")
        return capabilities

    @staticmethod
    def _has_docker() -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _has_kubectl() -> bool:
        """Check if kubectl is available."""
        try:
            result = subprocess.run(
                ["kubectl", "version", "--client"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False


class ToolConfig:
    """Configuration management for external tools."""

    # Default configuration locations
    CONFIG_DIR = Path.home() / ".idapro" / "spectra"
    TOOLS_CONFIG_FILE = CONFIG_DIR / "tools.json"

    @classmethod
    def load_config(cls) -> dict[str, Any]:
        """Load tool configuration from file.

        Returns:
            Dict of tool configurations
        """
        if not cls.TOOLS_CONFIG_FILE.exists():
            return {}

        try:
            import json

            with open(cls.TOOLS_CONFIG_FILE) as f:
                config = json.load(f)

            log_debug(f"Loaded tool config from {cls.TOOLS_CONFIG_FILE}")
            return config

        except (json.JSONDecodeError, OSError) as e:
            log_error(f"Failed to load tool config: {e}")
            return {}

    @classmethod
    def save_config(cls, config: dict[str, Any]) -> None:
        """Save tool configuration to file.

        Args:
            config: Configuration dictionary
        """
        try:
            import json

            cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            with open(cls.TOOLS_CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)

            log_info(f"Saved tool config to {cls.TOOLS_CONFIG_FILE}")

        except OSError as e:
            log_error(f"Failed to save tool config: {e}")

    @classmethod
    def get_tool_config(cls, tool_name: str) -> dict[str, Any]:
        """Get configuration for specific tool.

        Args:
            tool_name: Name of tool

        Returns:
            Configuration dict for tool, or empty dict if not found
        """
        config = cls.load_config()
        return config.get(tool_name, {})

    @classmethod
    def set_tool_config(cls, tool_name: str, tool_config: dict[str, Any]) -> None:
        """Set configuration for specific tool.

        Args:
            tool_name: Name of tool
            tool_config: Configuration dict
        """
        config = cls.load_config()
        config[tool_name] = tool_config
        cls.save_config(config)


# Tool-specific location patterns
TOOL_LOCATIONS = {
    "Linux": {
        "usr_bin": ["/usr/bin", "/usr/local/bin"],
        "opt": ["/opt"],
        "home": [str(Path.home() / ".local/bin"), str(Path.home() / "bin")],
    },
    "Darwin": {
        "usr_bin": ["/usr/local/bin", "/opt/homebrew/bin"],
        "home": [str(Path.home() / ".local/bin"), str(Path.home() / "bin")],
        "applications": ["/Applications"],
    },
    "Windows": {
        "program_files": [os.environ.get("ProgramFiles", "C:\\Program Files")],
        "program_files_x86": [os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")],
        "local_app_data": [os.environ.get("LOCALAPPDATA", "")],
    },
}
