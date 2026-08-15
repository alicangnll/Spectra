"""MCP Server security validation and enforcement.

This module provides security controls for MCP server configurations to
prevent command execution vulnerabilities and unauthorized system access.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from ..core.logging import log_debug, log_error, log_info, log_warn

if TYPE_CHECKING:
    pass


# =============================================================================
# SECURITY POLICIES
# =============================================================================

# Whitelist of safe commands that can be used for MCP servers
# Format: (command_name, is_safe, description, risk_level)
SAFE_COMMANDS = {
    # Node.js package managers (safe, package execution only)
    "npx": (True, "Node.js package runner", "low"),
    "npm": (True, "Node.js package manager", "low"),
    "pnpm": (True, "Node.js package manager", "low"),
    "yarn": (True, "Node.js package manager", "low"),

    # Python executors (generally safe with proper environment)
    "python": (True, "Python interpreter", "medium"),
    "python3": (True, "Python 3 interpreter", "medium"),
    "python2": (False, "Python 2 (deprecated, insecure)", "high"),
    "uvx": (True, "UV tool runner", "low"),

    # Development tools (moderate risk)
    "node": (True, "Node.js runtime", "medium"),
    "deno": (True, "Deno runtime", "medium"),
    "bun": (True, "Bun runtime", "medium"),

    # Container tools (higher risk, requires validation)
    "docker": (False, "Docker (requires explicit approval)", "high"),
    "podman": (False, "Podman (requires explicit approval)", "high"),
}

# Commands that are NEVER allowed due to security risks
BLOCKED_COMMANDS = {
    # Shell commands (can lead to arbitrary command execution)
    "sh": False,
    "bash": False,
    "zsh": False,
    "fish": False,
    "cmd": False,
    "powershell": False,
    "pwsh": False,

    # System commands (can modify system state)
    "sudo": False,
    "su": False,
    "doas": False,
    "chmod": False,
    "chown": False,
    "mv": False,
    "cp": False,
    "rm": False,

    # Network tools (data exfiltration risk)
    "nc": False,
    "netcat": False,
    "telnet": False,
    "curl": False,
    "wget": False,
    "ftp": False,

    # Potentially dangerous system tools
    "vi": False,
    "vim": False,
    "nano": False,
    "ed": False,
}

# Dangerous patterns in arguments that should be blocked
DANGEROUS_PATTERNS = [
    # Command injection attempts
    r"\|.*\|\|",           # Pipe chains
    r";.*rm\s+",          # Command chaining with delete
    r";.*chmod\s+[777]",  # Permission escalation
    r"\$\([^)]*\)",       # Command substitution
    r"`[^`]*`",           # Backtick command substitution
    r"\${.*}",             # Variable expansion
    r">.*/.*",             # Output redirection to suspicious paths
    r"eval\s+",           # eval execution
    r"exec\s+",           # exec execution

    # Path traversal attempts
    r"\.\.\/",             # Parent directory traversal
    r"\.\.\\",             # Windows parent directory traversal

    # Suspicious network operations
    r"curl.*\|",           # Curl with pipe
    r"wget.*\|",           # Wget with pipe
    r"nc\s+",              # Netcat

    # System file access
    r"/etc/passwd",        # Password file access
    r"/etc/shadow",        # Shadow file access
    r"~/.ssh/",            # SSH key access
    r"~/.aws/",            # AWS credentials access

    # Code execution patterns
    r"__import__\s*\(",    # Python import execution
    r"exec\s*\(",          # Python exec
    r"eval\s*\(",          # Python/JS eval
    r"system\s*\(",        # System calls
]


def _check_dangerous_patterns(args: list[str]) -> tuple[bool, str | None]:
    """Check if arguments contain dangerous patterns.

    Returns:
        (is_safe, warning_message) - is_safe is False if dangerous pattern found
    """
    args_text = " ".join(args)

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, args_text, re.IGNORECASE):
            return False, f"Dangerous pattern detected: {pattern}"

    return True, None


def _check_path_security(env: dict[str, str]) -> tuple[bool, list[str]]:
    """Validate environment variables for path security.

    Returns:
        (is_safe, warnings) - List of security warnings
    """
    warnings = []

    # Check ALLOWED_PATHS if present
    if "ALLOWED_PATHS" in env:
        allowed_paths = env["ALLOWED_PATHS"].split(",")
        for path in allowed_paths:
            path = path.strip()

            # Warn about dangerous paths
            dangerous_paths = [
                "/",              # Root directory
                "/home",          # All home directories
                "/Users",          # All macOS users
                "C:\\",            # Windows root
                "/etc",            # System config
                "/root",           # Root user
                "~",               # Home directory shortcut
            ]

            if path in dangerous_paths:
                warnings.append(f"ALLOWED_PATHS includes potentially dangerous path: {path}")

            # Check for parent directory traversal in paths
            if ".." in path:
                warnings.append(f"ALLOWED_PATHS contains parent directory reference: {path}")

    # Check for other sensitive environment variables
    sensitive_keys = ["PASSWORD", "TOKEN", "KEY", "SECRET", "CREDENTIALS"]
    for key in env:
        if any(sensitive in key.upper() for sensitive in sensitive_keys):
            if env[key] and not any(redaction in env[key].lower() for redaction in ["****", "xxx", "redacted"]):
                warnings.append(f"Environment variable {key} may contain sensitive credentials")

    return True, warnings


class MCPSecurityValidator:
    """Validates MCP server configurations for security policy compliance."""

    def __init__(self, strict_mode: bool = True):
        """Initialize the security validator.

        Args:
            strict_mode: If True, block potentially dangerous configurations.
                        If False, warn but allow them.
        """
        self._strict_mode = strict_mode
        self._validation_history: list[dict] = []

    def validate_command(self, command: str) -> tuple[bool, str | None, str]:
        """Validate if a command is safe to execute.

        Args:
            command: The command to validate (e.g., "npx", "python3")

        Returns:
            (is_allowed, reason, risk_level) - risk_level is "low", "medium", or "high"
        """
        command_lower = command.lower().strip()

        # Check if command is explicitly blocked
        if command_lower in BLOCKED_COMMANDS:
            return False, f"Command '{command}' is blocked for security reasons", "critical"

        # Check if command is in whitelist
        if command_lower in SAFE_COMMANDS:
            is_safe, description, risk = SAFE_COMMANDS[command_lower]
            if is_safe:
                return True, description, risk
            else:
                if self._strict_mode:
                    return False, f"Command '{command}' is not allowed in strict mode: {description}", risk
                else:
                    log_warn(f"Allowing unsafe command '{command}' in non-strict mode")
                    return True, f"{description} (allowed in non-strict mode)", risk

        # Unknown command - warn but allow in non-strict mode
        if self._strict_mode:
            return False, f"Unknown command '{command}' - not in safe commands list", "medium"
        else:
            log_warn(f"Allowing unknown command '{command}' - user discretion advised")
            return True, f"Unknown command (allowed in non-strict mode)", "medium"

    def validate_arguments(self, args: list[str], command: str) -> tuple[bool, list[str]]:
        """Validate command arguments for security issues.

        Args:
            args: List of command arguments
            command: The command being run (for context)

        Returns:
            (is_safe, warnings) - List of security warnings
        """
        warnings = []

        # Check for dangerous patterns
        is_safe, pattern_warning = _check_dangerous_patterns(args)
        if not is_safe:
            if self._strict_mode:
                return False, [f"BLOCKED: {pattern_warning}"]
            else:
                warnings.append(f"WARNING: {pattern_warning}")

        # Check for suspicious argument patterns
        for arg in args:
            # Flag absolute paths to system directories
            if arg.startswith("/") and any(system_dir in arg for system_dir in ["/etc", "/root", "/boot"]):
                warnings.append(f"Argument accesses system directory: {arg}")

            # Flag potential code execution
            suspicious_keywords = ["eval", "exec", "system", "import", "__", "compile"]
            if any(keyword in arg.lower() for keyword in suspicious_keywords):
                warnings.append(f"Argument may trigger code execution: {arg}")

        return True, warnings

    def validate_environment(self, env: dict[str, str]) -> tuple[bool, list[str]]:
        """Validate environment variables for security issues.

        Args:
            env: Dictionary of environment variables

        Returns:
            (is_safe, warnings) - List of security warnings
        """
        return _check_path_security(env)

    def validate_server_config(
        self,
        name: str,
        command: str,
        args: list[str],
        env: dict[str, str],
        timeout: float
    ) -> tuple[bool, list[str]]:
        """Comprehensive validation of an MCP server configuration.

        Args:
            name: Server name
            command: Command to execute
            args: Command arguments
            env: Environment variables
            timeout: Timeout in seconds

        Returns:
            (is_allowed, warnings) - List of all security warnings
        """
        all_warnings = []

        # Validate command
        cmd_allowed, cmd_reason, risk_level = self.validate_command(command)
        if not cmd_allowed:
            log_error(f"MCP Server '{name}' blocked: {cmd_reason}")
            all_warnings.append(f"❌ BLOCKED: {cmd_reason}")
            # Still track blocked validations
            self._validation_history.append({
                "name": name,
                "command": command,
                "allowed": False,
                "warnings": all_warnings,
            })
            return False, all_warnings

        all_warnings.append(f"✓ Command '{command}' allowed (risk: {risk_level})")

        # Validate arguments
        args_safe, args_warnings = self.validate_arguments(args, command)
        all_warnings.extend(args_warnings)

        # Validate environment
        env_safe, env_warnings = self.validate_environment(env)
        all_warnings.extend(env_warnings)

        # Determine overall allowed status
        allowed = cmd_allowed and args_safe and env_safe

        # Log the validation
        self._validation_history.append({
            "name": name,
            "command": command,
            "allowed": allowed,
            "warnings": all_warnings,
        })

        # In strict mode, require all validations to pass
        if self._strict_mode and not allowed:
            return False, all_warnings

        return True, all_warnings

    def get_validation_summary(self) -> dict:
        """Get summary of validation history.

        Returns:
            Dictionary with validation statistics
        """
        total = len(self._validation_history)
        blocked = sum(1 for v in self._validation_history if not v["allowed"])
        allowed = total - blocked

        return {
            "total": total,
            "allowed": allowed,
            "blocked": blocked,
            "block_rate": f"{(blocked / total * 100):.1f}%" if total > 0 else "0%",
        }


# Global security validator instance
_security_validator: MCPSecurityValidator | None = None


def get_security_validator(strict_mode: bool = True) -> MCPSecurityValidator:
    """Get or create the global security validator instance.

    Args:
        strict_mode: Whether to enforce strict security validation

    Returns:
        MCPSecurityValidator instance
    """
    global _security_validator
    if _security_validator is None or _security_validator._strict_mode != strict_mode:
        _security_validator = MCPSecurityValidator(strict_mode=strict_mode)
    return _security_validator


def validate_command_quick(command: str, strict_mode: bool = True) -> tuple[bool, str]:
    """Quick command validation returning (is_allowed, reason).

    Convenience wrapper that returns only 2 values for simple checks.

    Args:
        command: Command to validate (e.g., "npx", "python3")
        strict_mode: Whether to enforce strict security validation

    Returns:
        (is_allowed, reason) - reason explains why blocked or what command does
    """
    validator = get_security_validator(strict_mode=strict_mode)
    is_allowed, reason, _risk = validator.validate_command(command)
    return is_allowed, reason


def is_safe_command(command: str) -> bool:
    """Quick check if a command is in the safe commands whitelist.

    Args:
        command: Command to check

    Returns:
        True if command is safe, False otherwise
    """
    command_lower = command.lower().strip()
    if command_lower in SAFE_COMMANDS:
        is_safe, _, _ = SAFE_COMMANDS[command_lower]
        return is_safe
    return False


def get_safe_commands_list() -> list[tuple[str, str, str]]:
    """Get list of safe commands with descriptions and risk levels.

    Returns:
        List of (command, description, risk_level) tuples
    """
    return [
        (cmd, info[1], info[2])
        for cmd, info in SAFE_COMMANDS.items()
        if info[0]  # Only include safe commands
    ]
