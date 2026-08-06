"""CLI shell tools - Shell command execution.

Provides tools for:
- Executing shell commands (with safety checks and user approval)
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Annotated, Callable

from ...tools.base import tool


def _load_dangerous_commands() -> dict:
    """Load dangerous command patterns from JSON file.

    Returns:
        Dictionary with command categories and their patterns
    """
    json_path = Path(__file__).parent / "dangerous_commands.json"

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("categories", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Fallback to minimal defaults if JSON not found
        print(f"Warning: Could not load dangerous_commands.json: {e}")
        return {
            "critical": {"patterns": ["rm -rf /", "dd if=/dev/"]},
            "filesystem": {"patterns": ["rm -rf", "dd of=/dev/"]},
        }


# Load patterns from JSON
_DANGEROUS_CATEGORIES = _load_dangerous_commands()

# Extract patterns by category for backward compatibility
_DANGEROUS_PATTERNS = _DANGEROUS_CATEGORIES.get("critical", {}).get("patterns", [])
_FILESYSTEM_MODIFYING_PATTERNS = _DANGEROUS_CATEGORIES.get("filesystem", {}).get("patterns", [])
_PRIVILEGE_ESCALATION_PATTERNS = _DANGEROUS_CATEGORIES.get("privilege_escalation", {}).get("patterns", [])
_DATA_EXFILTRATION_PATTERNS = _DANGEROUS_CATEGORIES.get("data_exfiltration", {}).get("patterns", [])
_INSTALL_PATTERNS = _DANGEROUS_CATEGORIES.get("package_installation", {}).get("patterns", [])


def reload_dangerous_commands() -> bool:
    """Reload dangerous command patterns from JSON file.

    Useful for updating patterns without restarting the CLI.

    Returns:
        True if reload successful, False otherwise
    """
    global _DANGEROUS_CATEGORIES
    global _DANGEROUS_PATTERNS
    global _FILESYSTEM_MODIFYING_PATTERNS
    global _PRIVILEGE_ESCALATION_PATTERNS
    global _DATA_EXFILTRATION_PATTERNS
    global _INSTALL_PATTERNS

    try:
        _DANGEROUS_CATEGORIES = _load_dangerous_commands()
        _DANGEROUS_PATTERNS = _DANGEROUS_CATEGORIES.get("critical", {}).get("patterns", [])
        _FILESYSTEM_MODIFYING_PATTERNS = _DANGEROUS_CATEGORIES.get("filesystem", {}).get("patterns", [])
        _PRIVILEGE_ESCALATION_PATTERNS = _DANGEROUS_CATEGORIES.get("privilege_escalation", {}).get("patterns", [])
        _DATA_EXFILTRATION_PATTERNS = _DANGEROUS_CATEGORIES.get("data_exfiltration", {}).get("patterns", [])
        _INSTALL_PATTERNS = _DANGEROUS_CATEGORIES.get("package_installation", {}).get("patterns", [])
        return True
    except Exception as e:
        print(f"Error reloading dangerous commands: {e}")
        return False


def check_dangerous_command(command: str) -> tuple[bool, str, list[str]]:
    """Check if a command is dangerous and return details.

    Args:
        command: Shell command to check

    Returns:
        Tuple of (is_dangerous, danger_reason, detected_patterns)
    """
    command_lower = command.lower()
    detected_patterns = []
    highest_severity = None

    # Check each category from JSON
    for category_name, category_data in _DANGEROUS_CATEGORIES.items():
        severity = category_data.get("severity", "MEDIUM")
        patterns = category_data.get("patterns", [])

        for pattern in patterns:
            if pattern in command_lower:
                detected_patterns.append(pattern)

                # Track highest severity
                if highest_severity is None or _severity_rank(severity) > _severity_rank(highest_severity):
                    highest_severity = severity

                # CRITICAL commands return immediately
                if severity == "CRITICAL":
                    reason = f"CRITICAL: This command could cause irreversible damage!"
                    return True, reason, [pattern]

    if detected_patterns and highest_severity:
        if highest_severity == "HIGH":
            reason = f"HIGH: This command poses significant risk ({_get_risk_description(detected_patterns)})"
            return True, reason, detected_patterns
        elif highest_severity == "MEDIUM":
            reason = f"MEDIUM: This command has potential risks ({_get_risk_description(detected_patterns)})"
            return True, reason, detected_patterns

    return False, "", []


def check_dangerous_python_code(code: str) -> tuple[bool, str, list[str]]:
    """Check if Python code contains dangerous patterns.

    Args:
        code: Python code string to check

    Returns:
        Tuple of (is_dangerous, danger_reason, detected_patterns)
    """
    code_lower = code.lower()
    detected_patterns = []
    highest_severity = None

    # Check Python-specific categories from JSON
    python_categories = {
        k: v for k, v in _DANGEROUS_CATEGORIES.items()
        if k.startswith("python_")
    }

    for category_name, category_data in python_categories.items():
        severity = category_data.get("severity", "MEDIUM")
        patterns = category_data.get("patterns", [])

        for pattern in patterns:
            # Use regex for more flexible pattern matching
            import re
            try:
                # Convert shell wildcard patterns to regex
                regex_pattern = pattern.replace(".*", r".*").replace(".", r"\.")
                if re.search(regex_pattern, code_lower):
                    detected_patterns.append(pattern)

                    # Track highest severity
                    if highest_severity is None or _severity_rank(severity) > _severity_rank(highest_severity):
                        highest_severity = severity

                    # CRITICAL commands return immediately
                    if severity == "CRITICAL":
                        reason = f"CRITICAL: This Python code could cause irreversible damage!"
                        return True, reason, [pattern]
            except re.error:
                # Fallback to substring match if regex fails
                if pattern in code_lower:
                    detected_patterns.append(pattern)
                    if highest_severity is None or _severity_rank(severity) > _severity_rank(highest_severity):
                        highest_severity = severity
                    if severity == "CRITICAL":
                        reason = f"CRITICAL: This Python code could cause irreversible damage!"
                        return True, reason, [pattern]

    if detected_patterns and highest_severity:
        if highest_severity == "HIGH":
            reason = f"HIGH: This Python code poses significant risk ({_get_python_risk_description(detected_patterns)})"
            return True, reason, detected_patterns
        elif highest_severity == "MEDIUM":
            reason = f"MEDIUM: This Python code has potential risks ({_get_python_risk_description(detected_patterns)})"
            return True, reason, detected_patterns

    return False, "", []


def _get_python_risk_description(patterns: list[str]) -> str:
    """Get human-readable description of detected Python risk patterns."""
    if not patterns:
        return "unknown risk"

    # Check what types of patterns were detected
    has_filesystem = any("remove" in p or "rmtree" in p or "unlink" in p for p in patterns)
    has_exec = any("exec" in p or "eval" in p or "compile" in p for p in patterns)
    has_install = any("pip install" in p for p in patterns)
    has_network = any("post" in p or "send" in p or "storbinary" in p for p in patterns)

    risks = []
    if has_filesystem:
        risks.append("filesystem modification")
    if has_exec:
        risks.append("arbitrary code execution")
    if has_install:
        risks.append("package installation")
    if has_network:
        risks.append("network data transfer")

    return ", ".join(risks) if risks else "potential risks"


def _severity_rank(severity: str) -> int:
    """Convert severity string to numeric rank for comparison."""
    ranks = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
    return ranks.get(severity, 0)


def _get_risk_description(patterns: list[str]) -> str:
    """Get human-readable description of detected risk patterns."""
    if not patterns:
        return "unknown risk"

    # Check what types of patterns were detected
    has_filesystem = any(p in _FILESYSTEM_MODIFYING_PATTERNS for p in patterns)
    has_privilege = any(p in _PRIVILEGE_ESCALATION_PATTERNS for p in patterns)
    has_exfil = any(p in _DATA_EXFILTRATION_PATTERNS for p in patterns)
    has_install = any(p in _INSTALL_PATTERNS for p in patterns)

    risks = []
    if has_filesystem:
        risks.append("filesystem modification")
    if has_privilege:
        risks.append("privilege escalation")
    if has_exfil:
        risks.append("data exfiltration")
    if has_install:
        risks.append("package installation")

    return ", ".join(risks) if risks else "potential risks"


# Global approval callback (set by the CLI controller)
_approval_callback: Callable[[str, bool, str], bool] | None = None

# Shell approval state for output synchronization
_in_shell_approval = False
_approval_lock = threading.Lock()

# Execution lock to prevent concurrent shell command executions
_shell_execution_lock = threading.Lock()
_current_command: threading.Value | None = None

# Active subprocess tracking for Ctrl+C handling
_active_subprocesses: list[subprocess.Popen] = []
_subprocess_lock = threading.Lock()


def is_in_shell_approval() -> bool:
    """Check if currently in shell command approval prompt.

    Returns:
        True if currently waiting for shell command approval input
    """
    with _approval_lock:
        return _in_shell_approval


def set_shell_approval_state(state: bool) -> None:
    """Set shell approval state for output synchronization.

    Args:
        state: True to indicate approval prompt is active, False otherwise
    """
    global _in_shell_approval
    with _approval_lock:
        _in_shell_approval = state


def get_active_subprocesses() -> list[subprocess.Popen]:
    """Get list of active subprocesses for cancellation."""
    with _subprocess_lock:
        return list(_active_subprocesses)


def kill_all_subprocesses() -> None:
    """Kill all active shell command subprocesses."""
    with _subprocess_lock:
        for proc in _active_subprocesses:
            try:
                if proc.poll() is None:  # Still running
                    proc.terminate()
                    # Give it a moment to terminate gracefully
                    import time
                    time.sleep(0.01)
                    if proc.poll() is None:  # Still running
                        proc.kill()
            except Exception:
                pass
        _active_subprocesses.clear()


def register_subprocess(proc: subprocess.Popen) -> None:
    """Register a subprocess for potential cancellation."""
    with _subprocess_lock:
        _active_subprocesses.append(proc)


def unregister_subprocess(proc: subprocess.Popen) -> None:
    """Unregister a subprocess after completion."""
    with _subprocess_lock:
        try:
            _active_subprocesses.remove(proc)
        except ValueError:
            pass  # Already removed


def set_approval_callback(callback: Callable[[str, bool, str], bool] | None) -> None:
    """Set the approval callback for shell command execution.

    Args:
        callback: Function that takes (command, is_dangerous, danger_reason)
                  and returns True if approved, False otherwise.
    """
    global _approval_callback
    _approval_callback = callback


@tool(name="shell_command", category="shell", mutating=True)
def shell_command(
    command: Annotated[str, "Shell command to execute"],
    timeout: Annotated[int, "Timeout in seconds (default: 7200 = 2 hours)"] = 7200,
) -> str:
    """Execute a shell command with safety checks and user approval.

    WARNING: This executes arbitrary shell commands. Use with caution.
    ALL commands require user approval. Dangerous commands show extra warnings.

    Args:
        command: Shell command to execute
        timeout: Maximum time to wait (default: 7200 seconds = 2 hours for large codebase analysis)

    Returns:
        Command output (stdout + stderr)

    Example:
        shell_command("ls -la")
        shell_command("grep -r password /etc")

    Safety:
        - ALL commands require user approval
        - Dangerous commands trigger extra warnings
        - Timeout prevents hanging
        - Output is truncated if too long
        - Execution lock prevents concurrent commands
    """
    global _current_command

    # Acquire execution lock to prevent concurrent shell commands
    acquired = _shell_execution_lock.acquire(blocking=False)
    if not acquired:
        return "ERROR: Another shell command is currently executing. Please wait for it to complete."

    try:
        # Check if command is dangerous
        is_dangerous, danger_reason, detected_patterns = check_dangerous_command(command)

        # Request user approval - DEFAULT DENY if no callback set
        if _approval_callback is None:
            # Safety: No callback configured = deny execution
            import sys
            print()
            print("\033[31m" + "⚠️  ERROR: Shell command approval not configured!" + "\033[0m")
            print("\033[33m" + "    The shell_command tool requires an approval callback to be set." + "\033[0m")
            print("\033[33m" + "    Please restart the CLI or configure shell approval properly." + "\033[0m")
            print()
            return "ERROR: Shell command approval not configured. Command execution denied."

        approved = _approval_callback(command, is_dangerous, danger_reason)
        if not approved:
            return "Command execution cancelled by user."

        # Show execution indicator
        print(f"\033[36m⏳ Running command...\033[0m", end="", flush=True)

        # Execute command with Popen for better cancellation support
        # Note: Popen doesn't support capture_output, use stdout/stderr PIPE
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Register subprocess for potential cancellation
        register_subprocess(proc)

        try:
            # Wait for completion with timeout
            import time
            start_time = time.time()

            while proc.poll() is None:
                if time.time() - start_time > timeout:
                    proc.terminate()
                    time.sleep(0.1)
                    if proc.poll() is None:
                        proc.kill()
                    return f"Error: Command timed out after {timeout} seconds"
                time.sleep(0.01)

            # Process completed
            stdout, stderr = proc.communicate()

            # Combine output
            output = []
            if stdout:
                output.append(stdout)
            if stderr:
                output.append(f"STDERR: {stderr}")

            combined = "\n".join(output) if output else "(no output)"

            # Truncate if too long
            if len(combined) > 5000:
                combined = combined[:5000] + "\n... (truncated)"

            # Add exit code info
            if proc.returncode != 0:
                combined = f"[Exit code: {proc.returncode}]\n{combined}"

            # Clear the "Running..." indicator and show completion
            print("\r\033[36m✓ Command completed\033[0m")

            return combined

        except KeyboardInterrupt:
            # User pressed Ctrl+C - terminate subprocess
            proc.terminate()
            time.sleep(0.05)
            if proc.poll() is None:
                proc.kill()
            print("\r\033[33m⏹  Command interrupted\033[0m")
            return "\n\n⏹  Command interrupted by user (Ctrl+C)."

    except subprocess.TimeoutExpired:
        print("\r\033[31m⏱  Command timed out\033[0m")
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        print("\r\033[31m✗  Command failed\033[0m")
        return f"Error: {e}"
    finally:
        # Always cleanup: unregister subprocess and release lock
        try:
            unregister_subprocess(proc)
        except:
            pass
        _shell_execution_lock.release()


@tool(name="which", category="shell")
def which(
    command: Annotated[str, "Command to locate"],
) -> str:
    """Locate a command in the system PATH.

    Args:
        command: Command name to search for

    Returns:
        Path to command or "not found"

    Example:
        which("python3")
        which("gcc")
    """
    try:
        import shutil
        path = shutil.which(command)
        if path:
            return path
        return f"{command}: not found"
    except Exception as e:
        return f"Error: {e}"


@tool(name="get_env", category="shell")
def get_env(
    variable: Annotated[str, "Environment variable name"],
    default: Annotated[str, "Default value if not set"] = "",
) -> str:
    """Get an environment variable value.

    Args:
        variable: Name of the environment variable
        default: Default value if variable is not set

    Returns:
        Environment variable value or default

    Example:
        get_env("PATH")
        get_env("HOME")
    """
    import os
    return os.environ.get(variable, default)


@tool(name="set_env", category="shell", mutating=True)
def set_env(
    variable: Annotated[str, "Environment variable name"],
    value: Annotated[str, "Value to set"],
) -> str:
    """Set an environment variable for current session.

    Note: This only sets the variable for the current Python process,
    not for the parent shell.

    Args:
        variable: Name of the environment variable
        value: Value to set

    Returns:
        Success message

    Example:
        set_env("MY_VAR", "my_value")
    """
    import os
    os.environ[variable] = value
    return f"Set {variable}={value}"
