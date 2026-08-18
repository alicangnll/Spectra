"""ADB (Android Debug Bridge) tools for Spectra.

Provides LLM-callable tools for Android device interaction with safety restrictions.
"""

from __future__ import annotations

import os
import re
import subprocess

from ..core.logging import log_debug, log_error, log_info, log_warning
from ..core.safety import unsafe_commands_allowed
from .base import tool

# Singleton ADB manager instance
_adb_manager = None


def get_adb_manager():
    """Get or create the singleton ADB manager."""
    global _adb_manager
    if _adb_manager is None:
        _adb_manager = _AdbManager()
    return _adb_manager


class _AdbManager:
    """Internal ADB manager with safety restrictions."""

    def __init__(self):
        self._adb_path = self._find_adb()
        self._validate_adb()
        self._connected_device: str | None = None

    def _find_adb(self) -> str:
        """Find ADB executable in system PATH."""
        possible_names = ["adb", "adb.exe"]

        for name in possible_names:
            try:
                result = subprocess.run(["which", name], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        # Try common installation paths
        common_paths = [
            "/usr/local/bin/adb",
            "/usr/bin/adb",
            "/opt/android-sdk/platform-tools/adb",
            os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
            os.path.expanduser("~/.local/bin/adb"),
            "C:\\Platform-tools\\adb.exe",
            "C:\\Android\\Sdk\\platform-tools\\adb.exe",
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        raise RuntimeError("ADB not found. Install Android Platform Tools")

    def _validate_adb(self) -> None:
        """Validate that ADB is working."""
        try:
            result = subprocess.run([self._adb_path, "version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                log_info(f"ADB found: {version.split()[4] if len(version.split()) > 4 else 'unknown'}")
        except Exception as e:
            log_error(f"Failed to validate ADB: {e}")

    def _check_shell_command_safety(self, command: str) -> tuple[bool, str]:
        """Check if a shell command is safe to execute."""
        if unsafe_commands_allowed():
            log_warning("ADB unsafe-command mode is enabled in Settings — safety checks bypassed")
            return True, "Unsafe-command mode enabled in Settings"

        dangerous_patterns = [
            r"\brm\b.*-[a-z]*r[a-z]*f",
            r"\brm\b.*/",
            r"\bformat\b",
            r"\bwipe\b",
            r"\bfdisk\b",
            r"\bdd\b\s*if=.*of=",
            r"\bmkfs\b",
            r"\bmount\b.*-o\s+remount",
            r"\bumount\b",
            r"\breboot\b.*-(bootloader|recovery|safe)",
            r"\bsystem/bin/rm",
            r"\brm\s+.*/system/",
            r"\brm\s+.*/data/",
            r"\bmv\s+.*/system/",
            r"\bchmod\s+777\s+/",
            r"\bchown\s+root\s+/",
            r"\blkeditor\b",
            r"\breditor\b",
            r"\bfactory\s+reset\b",
            r"\bkill\s+-9\s+\d+\s+\d+",
        ]

        safe_prefixes = [
            "ls",
            "cat",
            "getprop",
            "dumpsys",
            "ps",
            "pm",
            "am",
            "netstat",
            "netcfg",
            "ifconfig",
            "ip",
            "route",
            "env",
            "printenv",
            "which",
            "pwd",
            "id",
            "whoami",
            "date",
            "top",
            "grep",
            "find",
            "file",
            "strings",
            "head",
            "tail",
            "wc",
            "stat",
            "df",
            "du",
            "logcat",
            "dmesg",
            "sqlite3",
            "settings",
            "cmd",
            "dumpstate",
            "screencap",
            "screenrecord",
        ]

        command_lower = command.lower().strip()

        for pattern in dangerous_patterns:
            if re.search(pattern, command_lower, re.IGNORECASE):
                return False, f"Command matches dangerous pattern: {pattern}"

        cmd_parts = command_lower.split()
        if not cmd_parts:
            return False, "Empty command"

        base_cmd = cmd_parts[0]
        is_safe_prefix = any(base_cmd == safe_prefix for safe_prefix in safe_prefixes)

        if is_safe_prefix:
            return True, "OK"

        read_only_patterns = [r"^cat\s+", r"^ls\s+-", r"^grep\s+", r"^file\s+", r"^strings\s+"]
        for pattern in read_only_patterns:
            if re.match(pattern, command_lower):
                return True, "Read-only operation"

        return False, f"Command '{base_cmd}' not in safe list"


# ============================================================================
# ADB Tools (callable by LLM via @tool decorator)
# ============================================================================


@tool(
    name="adb_check",
    description="Check if ADB is available and list connected Android devices",
    category="adb",
)
def adb_check() -> str:
    """Check ADB availability and return device list."""
    manager = get_adb_manager()

    try:
        result = subprocess.run([manager._adb_path, "start-server"], capture_output=True, text=True, timeout=10)

        result = subprocess.run([manager._adb_path, "devices", "-l"], capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return f"ADB error: {result.stderr}"

        devices = []
        for line in result.stdout.strip().split("\n")[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])

        if not devices:
            return "ADB is available but no devices connected. Connect a device via USB (enable USB debugging) or wireless (adb connect IP:port)."

        return f"ADB available. Connected devices: {', '.join(devices)}"

    except Exception as e:
        return f"ADB check failed: {e}"


@tool(
    name="adb_connect",
    description="Connect to an Android device via ADB. Returns device info including model, Android version, and rooted status.",
    category="adb",
)
def adb_connect(device_id: str = "") -> str:
    """Connect to ADB device and return device information."""
    manager = get_adb_manager()

    try:
        if device_id and ":" in device_id:
            # Wireless connection
            result = subprocess.run(
                [manager._adb_path, "connect", device_id], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0 or "unable to connect" in result.stderr.lower():
                return f"Wireless connection failed: {result.stderr or 'Connection failed'}"

        # Get device list to find target
        devices_result = subprocess.run(
            [manager._adb_path, "devices", "-l"], capture_output=True, text=True, timeout=10
        )

        target_device = None
        for line in devices_result.stdout.strip().split("\n")[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                if not device_id or parts[0] == device_id:
                    target_device = parts[0]
                    break

        if not target_device:
            return "No device found. Connect a device via USB or wireless first."

        manager._connected_device = target_device

        # Get device properties
        props_result = subprocess.run(
            [manager._adb_path, "-s", target_device, "shell", "getprop"], capture_output=True, text=True, timeout=30
        )

        props = props_result.stdout

        def extract_prop(name):
            match = re.search(rf"\[{name}\]:\s*\[([^\]]+)\]", props)
            return match.group(1) if match else "unknown"

        manufacturer = extract_prop("ro.product.manufacturer")
        model = extract_prop("ro.product.model")
        android_version = extract_prop("ro.build.version.release")
        sdk_version = extract_prop("ro.build.version.sdk")
        architecture = extract_prop("ro.product.cpu.abi")

        # Check rooted
        rooted = "No"
        try:
            su_check = subprocess.run(
                [manager._adb_path, "-s", target_device, "shell", "which", "su"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if "su" in su_check.stdout and "not found" not in su_check.stdout:
                rooted = "Yes"
        except Exception:
            pass

        log_info(f"Connected to device: {model} ({manufacturer})")

        return f"""Connected to Android device:
  Device ID: {target_device}
  Manufacturer: {manufacturer}
  Model: {model}
  Android Version: {android_version}
  SDK Version: {sdk_version}
  Architecture: {architecture}
  Rooted: {rooted}"""

    except Exception as e:
        return f"Failed to connect to device: {e}"


# Wireless-debugging pair target: IPv4/IPv6 address plus port (e.g. 192.168.1.50:37027).
_PAIR_TARGET_RE = re.compile(r"^[0-9A-Fa-f:.]+$")
# Pairing code shown on the device (6 characters on stock Android).
# Must start alphanumeric so it can never be parsed as an adb switch.
_PAIR_CODE_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z-]{3,15}$")


def _validate_pair_target(ip_port: str, code: str) -> str | None:
    """Validate wireless-debugging pairing inputs; return an error message or None.

    Kept strict (no whitespace, shell metacharacters or leading dashes) so the
    values can never be mistaken for adb command-line switches.
    """
    ip_port = (ip_port or "").strip()
    code = (code or "").strip()
    if not ip_port or not code:
        return "Both ip_port (e.g. 192.168.1.50:37027) and the pairing code are required."
    if ":" not in ip_port or not _PAIR_TARGET_RE.match(ip_port):
        return (
            f"Invalid pairing address: {ip_port!r} — expected the IP:PORT shown under "
            "'Developer options → Wireless debugging → Pair device with pairing code'."
        )
    if not _PAIR_CODE_RE.match(code):
        return f"Invalid pairing code: {code!r} — use the code shown on the device's pairing dialog."
    return None


@tool(
    name="adb_pair",
    description=(
        "Pair with an Android device for wireless (TCP) debugging — Android 11+ one-time setup. "
        "Takes the IP:port and pairing code from 'Developer options → Wireless debugging → "
        "Pair device with pairing code'. After pairing, call adb_connect with the IP:port shown "
        "on the main Wireless debugging screen (the pairing port and connection port differ)."
    ),
    category="adb",
)
def adb_pair(ip_port: str, code: str) -> str:
    """Pair with a device for wireless debugging (one-time operation)."""
    error = _validate_pair_target(ip_port, code)
    if error:
        return error

    manager = get_adb_manager()
    target = ip_port.strip()
    try:
        result = subprocess.run(
            [manager._adb_path, "pair", target, code.strip()],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        if "Successfully paired" in output:
            log_info(f"Paired with Android device for wireless debugging: {target}")
            return (
                "Successfully paired with the device.\n"
                "Next step: the pairing port is NOT the connection port — open the main "
                "'Wireless debugging' screen and call adb_connect(\"<ip>:<port>\") with the "
                "address shown there."
            )
        return f"Pairing failed: {output or 'unknown error'}"
    except subprocess.TimeoutExpired:
        return "Pairing timed out after 30s. Check that the device and this machine are on the same network."
    except Exception as e:
        return f"Pairing failed: {e}"


@tool(
    name="adb_install",
    description="Install an APK file on the connected Android device",
    category="adb",
)
def adb_install(apk_path: str, replace: bool = True, grant_permissions: bool = True) -> str:
    """Install APK on connected device."""
    manager = get_adb_manager()

    if not os.path.exists(apk_path):
        return f"APK file not found: {apk_path}"

    if not manager._connected_device:
        # Try to connect automatically
        conn_result = adb_connect()
        if "Failed to connect" in conn_result or "No device found" in conn_result:
            return f"No device connected. {conn_result}"

    try:
        cmd = [manager._adb_path, "-s", manager._connected_device, "install"]
        if replace:
            cmd.append("-r")
        if grant_permissions:
            cmd.append("-g")
        cmd.append(apk_path)

        log_info(f"Installing APK: {apk_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            return f"APK installed successfully: {apk_path}\nOutput: {result.stdout}"
        else:
            return f"Installation failed: {result.stderr}"

    except subprocess.TimeoutExpired:
        return "Installation timed out (120s)"
    except Exception as e:
        return f"Installation error: {e}"


@tool(
    name="adb_uninstall",
    description="Uninstall an app from the connected Android device",
    category="adb",
)
def adb_uninstall(package_name: str, keep_data: bool = False) -> str:
    """Uninstall package from connected device."""
    manager = get_adb_manager()

    if not manager._connected_device:
        return "No device connected. Use adb_connect first."

    try:
        cmd = [manager._adb_path, "-s", manager._connected_device, "uninstall"]
        if keep_data:
            cmd.append("-k")
        cmd.append(package_name)

        log_info(f"Uninstalling package: {package_name}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return f"Package uninstalled successfully: {package_name}\nOutput: {result.stdout}"
        else:
            return f"Uninstallation failed: {result.stderr}"

    except Exception as e:
        return f"Uninstallation error: {e}"


@tool(
    name="adb_shell",
    description=(
        "Run a shell command on the Android device. Only read-only analysis "
        "commands are allowed for safety, unless the user enabled unsafe "
        "commands in Spectra Settings."
    ),
    category="adb",
)
def adb_shell(command: str) -> str:
    """Run safe shell command on device."""
    manager = get_adb_manager()

    if not manager._connected_device:
        return "No device connected. Use adb_connect first."

    # Safety check
    is_safe, reason = manager._check_shell_command_safety(command)
    if not is_safe:
        log_warning(f"Blocked unsafe shell command: {command} ({reason})")
        return f"Command not allowed for safety: {reason}"

    try:
        cmd = [manager._adb_path, "-s", manager._connected_device, "shell", command]
        log_debug(f"Running shell command: {command}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            output = result.stdout.strip()
            return output if output else "(command executed with no output)"
        else:
            return f"Command failed: {result.stderr}"

    except subprocess.TimeoutExpired:
        return "Command timed out (30s)"
    except Exception as e:
        return f"Command error: {e}"


@tool(
    name="adb_list_packages",
    description="List installed packages/apps on the connected Android device",
    category="adb",
)
def adb_list_packages(user_only: bool = True) -> str:
    """List installed packages."""
    manager = get_adb_manager()

    if not manager._connected_device:
        return "No device connected. Use adb_connect first."

    try:
        cmd = ["shell", "pm", "list", "packages"]
        if user_only:
            cmd.append("-3")

        output = subprocess.run(
            [manager._adb_path, "-s", manager._connected_device, *cmd], capture_output=True, text=True, timeout=30
        ).stdout

        packages = []
        for line in output.strip().split("\n"):
            if line.startswith("package:"):
                packages.append(line.replace("package:", "").strip())

        total = len(packages)
        preview = packages[:20]

        result = f"Found {total} packages:\n"
        result += "\n".join(preview)
        if total > 20:
            result += f"\n... and {total - 20} more packages"

        return result

    except Exception as e:
        return f"Failed to list packages: {e}"


@tool(
    name="adb_app_info",
    description="Get detailed information about an installed app including version, permissions, and data directory",
    category="adb",
)
def adb_app_info(package_name: str) -> str:
    """Get app information."""
    manager = get_adb_manager()

    if not manager._connected_device:
        return "No device connected. Use adb_connect first."

    try:
        output = subprocess.run(
            [manager._adb_path, "-s", manager._connected_device, "shell", "dumpsys", "package", package_name],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout

        def parse_field(name):
            match = re.search(rf"{name}=[=]?\s*([^\s,]+)", output)
            return match.group(1) if match else "unknown"

        version_code = parse_field("versionCode")
        version_name = parse_field("versionName")
        target_sdk = parse_field("targetSdk")
        data_dir = parse_field("dataDir")

        # Get permissions
        permissions = []
        in_permissions = False
        for line in output.split("\n"):
            line = line.strip()
            if "requested permissions:" in line.lower():
                in_permissions = True
                continue
            if in_permissions:
                if line.startswith("install") or not line:
                    break
                if "android.permission." in line or "com." in line:
                    permissions.append(line.strip())

        perm_preview = permissions[:15]
        result = f"""App Information for {package_name}:
  Version Code: {version_code}
  Version Name: {version_name}
  Target SDK: {target_sdk}
  Data Directory: {data_dir}
  Permissions ({len(permissions)}):"""

        for perm in perm_preview:
            result += f"\n    - {perm}"

        if len(permissions) > 15:
            result += f"\n    ... and {len(permissions) - 15} more permissions"

        return result

    except Exception as e:
        return f"Failed to get app info: {e}"


@tool(
    name="adb_pull",
    description="Pull a file from the Android device to local machine",
    category="adb",
)
def adb_pull(remote_path: str, local_path: str) -> str:
    """Pull file from device."""
    manager = get_adb_manager()

    if not manager._connected_device:
        return "No device connected. Use adb_connect first."

    try:
        result = subprocess.run(
            [manager._adb_path, "-s", manager._connected_device, "pull", remote_path, local_path],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return f"File pulled successfully: {remote_path} -> {local_path}"
        else:
            return f"Pull failed: {result.stderr}"

    except Exception as e:
        return f"Pull error: {e}"


@tool(
    name="adb_push",
    description="Push a file from local machine to the Android device",
    category="adb",
)
def adb_push(local_path: str, remote_path: str) -> str:
    """Push file to device."""
    manager = get_adb_manager()

    if not manager._connected_device:
        return "No device connected. Use adb_connect first."

    if not os.path.exists(local_path):
        return f"Local file not found: {local_path}"

    try:
        result = subprocess.run(
            [manager._adb_path, "-s", manager._connected_device, "push", local_path, remote_path],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return f"File pushed successfully: {local_path} -> {remote_path}"
        else:
            return f"Push failed: {result.stderr}"

    except Exception as e:
        return f"Push error: {e}"
