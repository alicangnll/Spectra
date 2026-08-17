"""iOS device tools for Spectra (libimobiledevice wrapper).

Provides LLM-callable tools for iOS device interaction over usbmuxd, the
direct counterpart of the ADB tools for Android. All shell access targets
jailbroken devices over SSH and goes through the same safety gate as
adb_shell (safe-command list + dangerous patterns + the global
unsafe-commands opt-in in Settings).
"""

from __future__ import annotations

import os
import plistlib
import re
import shutil
import socket
import subprocess

from ..core.logging import log_debug, log_error, log_info, log_warning
from ..core.safety import unsafe_commands_allowed
from .base import tool

# Singleton iOS device manager
_ios_manager = None


def get_ios_manager():
    """Get or create the singleton iOS device manager."""
    global _ios_manager
    if _ios_manager is None:
        _ios_manager = _IosManager()
    return _ios_manager


# libimobiledevice binaries this module can use. Only the first two are
# required for basic connectivity; the rest enable specific tools and are
# resolved lazily with a per-feature install hint.
_CORE_TOOLS = ("idevice_id", "ideviceinfo")

_TOOL_HINTS = {
    "ideviceinstaller": "app management (ios_install/ios_uninstall/ios_list_apps)",
    "idevicesyslog": "log capture (ios_syslog)",
    "idevicescreenshot": "screenshots (ios_screenshot)",
    "idevicecrashreport": "crash report extraction (ios_pull_crash_reports)",
    "idevicebackup2": "device backup (ios_backup)",
    "idevicepair": "pairing (ios_pair)",
}

_INSTALL_HINT = (
    "Install libimobiledevice: macOS `brew install libimobiledevice`, "
    "Ubuntu/Debian `sudo apt install libimobiledevice-utils usbmuxd`, "
    "Windows: use WSL or a libimobiledevice-windows build. "
    "Python alternative: `pip install pymobiledevice3`."
)

# Directories searched when a tool is not on PATH (Homebrew layouts, etc.)
_EXTRA_BIN_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/opt/local/bin",
    "/usr/bin",
)


class _IosManager:
    """Internal iOS device manager with safety restrictions."""

    def __init__(self):
        self._binaries: dict[str, str] = {}
        self._discover_binaries()
        self._connected_udid: str | None = None

    # ------------------------------------------------------------------
    # Binary discovery
    # ------------------------------------------------------------------

    def _discover_binaries(self) -> None:
        """Locate libimobiledevice executables on this system."""
        names = _CORE_TOOLS + tuple(_TOOL_HINTS)
        for name in names:
            self._binaries[name] = self._find_tool(name) or ""
        ssh = self._find_tool("ssh")
        self._binaries["ssh"] = ssh or ""
        self._binaries["sshpass"] = self._find_tool("sshpass") or ""

    def _find_tool(self, name: str) -> str | None:
        """Find an executable in PATH or common install directories."""
        found = shutil.which(name)
        if found:
            return found

        candidates = [name]
        if os.name == "nt":
            candidates.append(name + ".exe")

        for directory in _EXTRA_BIN_DIRS:
            for candidate in candidates:
                path = os.path.join(directory, candidate)
                if os.path.exists(path):
                    return path
        return None

    def _require(self, *names: str) -> list[str]:
        """Return executable paths or raise with an actionable message."""
        missing = [n for n in names if not self._binaries.get(n)]
        if missing:
            for name in missing:
                hint = _TOOL_HINTS.get(name, "device connectivity")
                log_error(f"Missing libimobiledevice tool: {name} ({hint})")
            raise RuntimeError(
                f"Required tool(s) not found: {', '.join(missing)}. {_INSTALL_HINT}"
            )
        return [self._binaries[n] for n in names]

    # ------------------------------------------------------------------
    # Device helpers
    # ------------------------------------------------------------------

    def _list_udids(self) -> list[str]:
        """Return UDIDs of USB-connected devices."""
        idevice_id = self._require("idevice_id")[0]
        result = subprocess.run([idevice_id, "-l"], capture_output=True, text=True, timeout=10)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _resolve_udid(self, udid: str = "") -> str:
        """Return the requested UDID, the connected one, or the only device."""
        if udid:
            return udid
        if self._connected_udid:
            return self._connected_udid
        devices = self._list_udids()
        if not devices:
            raise RuntimeError("No iOS device connected. Connect via USB and pair first (ios_pair).")
        return devices[0]

    def _lockdown_query(self, udid: str, key: str, domain: str = "") -> str:
        """Read a single lockdown value; returns 'unknown' on any failure."""
        ideviceinfo = self._require("ideviceinfo")[0]
        cmd = [ideviceinfo, "-u", udid]
        if domain:
            cmd += ["-q", domain]
        cmd += ["-k", key]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            value = result.stdout.strip()
            return value if result.returncode == 0 and value else "unknown"
        except Exception:
            return "unknown"

    def _run(self, cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a subprocess with the standard timeout and capture."""
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    # ------------------------------------------------------------------
    # Safety gate (mirrors adb.py; shared unsafe-commands opt-in)
    # ------------------------------------------------------------------

    def _check_shell_command_safety(self, command: str) -> tuple[bool, str]:
        """Check if an SSH shell command is safe to execute on the device."""
        if unsafe_commands_allowed():
            log_warning("iOS unsafe-command mode is enabled in Settings - safety checks bypassed")
            return True, "Unsafe-command mode enabled in Settings"

        dangerous_patterns = [
            r"\brm\b.*-[a-z]*r[a-z]*f",
            r"\brm\b.*/",
            r"\bdd\b\s*if=.*of=",
            r"\bmkfs\b",
            r"\bfsck\b",
            r"\breboot\b",
            r"\bshutdown\b",
            r"\bhalt\b",
            r"\bnvram\b",
            r"\bfactory\s+reset\b",
            r"\bapt(-get)?\s+(install|remove|purge|upgrade)\b",
            r"\bdpkg\s+(-i|--install|-r|--remove|--purge)\b",
            r"\bkillall\b",
            r"\blaunchctl\s+(unload|remove|reboot)\b",
            r"\buicache\b",
            r"\bchmod\s+777\s+/",
            r"\bchown\s+root\s+/",
            r"\bpasswd\b",
            r"\bcurl\b.*\|\s*(ba)?sh",
            r"\bwget\b.*\|\s*(ba)?sh",
        ]

        safe_prefixes = [
            "ls",
            "cat",
            "ps",
            "file",
            "strings",
            "head",
            "tail",
            "wc",
            "stat",
            "df",
            "du",
            "id",
            "whoami",
            "uname",
            "sw_vers",
            "hostname",
            "grep",
            "find",
            "which",
            "pwd",
            "date",
            "env",
            "printenv",
            "print",
        ]

        command_lower = command.lower().strip()

        for pattern in dangerous_patterns:
            if re.search(pattern, command_lower, re.IGNORECASE):
                return False, f"Command matches dangerous pattern: {pattern}"

        cmd_parts = command_lower.split()
        if not cmd_parts:
            return False, "Empty command"

        base_cmd = cmd_parts[0]
        if any(base_cmd == safe_prefix for safe_prefix in safe_prefixes):
            return True, "OK"

        # Read-only invocations of otherwise stateful tools.
        read_only_patterns = [
            r"^dpkg\s+(-l|--list)\b",
            r"^plutil\s+-p\b",
            r"^otool\s+-[lL]\b",
        ]
        for pattern in read_only_patterns:
            if re.match(pattern, command_lower):
                return True, "Read-only operation"

        return False, f"Command '{base_cmd}' not in safe list"


# ============================================================================
# iOS Tools (callable by LLM via @tool decorator)
# ============================================================================


@tool(
    name="ios_check",
    description="Check if libimobiledevice is available and list connected iOS devices",
    category="ios",
)
def ios_check() -> str:
    """Check iOS tooling availability and return the device list."""
    manager = get_ios_manager()

    try:
        missing_core = [n for n in _CORE_TOOLS if not manager._binaries.get(n)]
        if missing_core:
            return f"libimobiledevice not found (missing {', '.join(missing_core)}). {_INSTALL_HINT}"

        devices = manager._list_udids()
        if not devices:
            return (
                "iOS tooling available but no devices connected. "
                "Connect a device via USB and make sure it is unlocked."
            )

        lines = ["iOS tooling available. Connected devices:"]
        for udid in devices:
            name = manager._lockdown_query(udid, "DeviceName")
            version = manager._lockdown_query(udid, "ProductVersion")
            lines.append(f"  {udid}  (Name: {name}, iOS: {version})")
        lines.append("Use ios_connect <udid> to select a device.")

        return "\n".join(lines)

    except Exception as e:
        return f"iOS check failed: {e}"


@tool(
    name="ios_pair",
    description="Pair with the connected iOS device (accept the Trust dialog on the device)",
    category="ios",
)
def ios_pair() -> str:
    """Pair the host with the USB-connected device."""
    manager = get_ios_manager()

    try:
        idevicepair = manager._require("idevicepair")[0]
        udid = manager._resolve_udid()

        pair = subprocess.run(
            [idevicepair, "-u", udid, "pair"], capture_output=True, text=True, timeout=30
        )
        if pair.returncode != 0:
            return (
                f"Pairing failed: {pair.stderr.strip() or pair.stdout.strip()}\n"
                "Unlock the device, tap Trust when prompted, then retry."
            )

        validate = subprocess.run(
            [idevicepair, "-u", udid, "validate"], capture_output=True, text=True, timeout=30
        )
        if validate.returncode == 0:
            manager._connected_udid = udid
            return f"Paired and validated with device {udid}."
        return f"Paired, but validation failed: {validate.stderr.strip()} (may need re-pairing)."

    except Exception as e:
        return f"Pairing error: {e}"


@tool(
    name="ios_connect",
    description=(
        "Connect to an iOS device and return device info (name, iOS version, "
        "model, serial). Pairing is validated first."
    ),
    category="ios",
)
def ios_connect(udid: str = "") -> str:
    """Connect to an iOS device and return device information."""
    manager = get_ios_manager()

    try:
        idevicepair = manager._require("idevicepair")[0]
        target = manager._resolve_udid(udid)

        validate = subprocess.run(
            [idevicepair, "-u", target, "validate"], capture_output=True, text=True, timeout=15
        )
        if validate.returncode != 0:
            return (
                f"Device {target} is not paired (or pairing is stale): "
                f"{validate.stderr.strip()}. Run ios_pair and accept the Trust dialog."
            )

        manager._connected_udid = target

        fields = {
            "Device Name": manager._lockdown_query(target, "DeviceName"),
            "iOS Version": manager._lockdown_query(target, "ProductVersion"),
            "Build": manager._lockdown_query(target, "BuildVersion"),
            "Product Type": manager._lockdown_query(target, "ProductType"),
            "Hardware Model": manager._lockdown_query(target, "HardwareModel"),
            "Serial Number": manager._lockdown_query(target, "SerialNumber"),
            "Activation": manager._lockdown_query(target, "ActivationState"),
        }

        log_info(f"Connected to iOS device: {fields['Device Name']} ({fields['Product Type']})")

        info = "\n".join(f"  {key}: {value}" for key, value in fields.items())
        return (
            f"Connected to iOS device:\n"
            f"  UDID: {target}\n"
            f"{info}\n"
            "  Jailbroken: unknown (probe SSH with ios_jailbreak_check; "
            "shell access via ios_shell requires a jailbroken device)"
        )

    except Exception as e:
        return f"Failed to connect to device: {e}"


@tool(
    name="ios_info",
    description="Query lockdown values from the device (optionally per domain/key), e.g. domain com.apple.mobile.iTunes",
    category="ios",
)
def ios_info(domain: str = "", key: str = "") -> str:
    """Run ideviceinfo and return raw lockdown values."""
    manager = get_ios_manager()

    try:
        ideviceinfo = manager._require("ideviceinfo")[0]
        udid = manager._resolve_udid()

        cmd = [ideviceinfo, "-u", udid]
        if domain:
            cmd += ["-q", domain]
        if key:
            cmd += ["-k", key]

        result = manager._run(cmd)
        if result.returncode != 0:
            return f"ideviceinfo failed: {result.stderr.strip()}"

        output = result.stdout.strip()
        if not output:
            return "(no values returned)"
        return output if output else "(no output)"

    except Exception as e:
        return f"Failed to query device info: {e}"


@tool(
    name="ios_syslog",
    description="Capture device syslog for a few seconds and return the last N lines (like adb logcat)",
    category="ios",
)
def ios_syslog(lines: int = 200, duration: int = 5) -> str:
    """Capture a slice of the unified syslog from the device."""
    manager = get_ios_manager()

    try:
        idevicesyslog = manager._require("idevicesyslog")[0]
        udid = manager._resolve_udid()

        duration = max(1, min(int(duration), 15))
        max_lines = max(1, min(int(lines), 2000))

        log_debug(f"Capturing syslog for {duration}s")
        proc = subprocess.Popen(
            [idevicesyslog, "-u", udid],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            out, _err = proc.communicate(timeout=duration)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _err = proc.communicate()

        captured = [line for line in (out or "").splitlines() if line.strip()]
        if not captured:
            return f"No syslog output captured in {duration}s."

        tail = captured[-max_lines:]
        dropped = len(captured) - len(tail)
        header = f"Syslog: last {len(tail)} of {len(captured)} lines"
        if dropped:
            header += f" ({dropped} earlier lines dropped)"
        return header + "\n" + "\n".join(tail)

    except Exception as e:
        return f"Syslog capture failed: {e}"


@tool(
    name="ios_list_apps",
    description="List installed apps on the connected iOS device (user apps by default, system apps optional)",
    category="ios",
)
def ios_list_apps(include_system: bool = False) -> str:
    """List installed apps via ideviceinstaller."""
    manager = get_ios_manager()

    try:
        ideviceinstaller = manager._require("ideviceinstaller")[0]
        udid = manager._resolve_udid()

        cmd = [ideviceinstaller, "-u", udid, "-l"]
        if include_system:
            cmd += ["-o", "list_all"]

        result = manager._run(cmd, timeout=60)
        if result.returncode != 0:
            return f"Failed to list apps: {result.stderr.strip()}"

        entries = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or "Total:" in line:
                continue
            entries.append(line)

        if not entries:
            return "No apps found."

        preview = entries[:20]
        out = f"Found {len(entries)} apps:\n" + "\n".join(preview)
        if len(entries) > 20:
            out += f"\n... and {len(entries) - 20} more apps"
        return out

    except Exception as e:
        return f"Failed to list apps: {e}"


@tool(
    name="ios_app_info",
    description="Get detailed information about an installed iOS app (version, bundle id, install path)",
    category="ios",
)
def ios_app_info(bundle_id: str) -> str:
    """Get app details by parsing the ideviceinstaller XML listing."""
    manager = get_ios_manager()

    try:
        ideviceinstaller = manager._require("ideviceinstaller")[0]
        udid = manager._resolve_udid()

        result = manager._run(
            [ideviceinstaller, "-u", udid, "-l", "-o", "xml", "-o", "list_all"], timeout=60
        )
        if result.returncode != 0:
            return f"Failed to query app list: {result.stderr.strip()}"

        app = None
        try:
            apps = plistlib.loads(result.stdout.encode() if isinstance(result.stdout, str) else result.stdout)
            if isinstance(apps, dict):
                apps = list(apps.values())
            for entry in apps:
                if isinstance(entry, dict) and entry.get("CFBundleIdentifier") == bundle_id:
                    app = entry
                    break
        except Exception as e:
            log_debug(f"plist parse failed ({e}); falling back to text search")

        if app is not None:
            keys = (
                "CFBundleIdentifier",
                "CFBundleDisplayName",
                "CFBundleName",
                "CFBundleShortVersionString",
                "CFBundleVersion",
                "CFBundleExecutable",
                "Path",
                "Container",
            )
            lines = [f"App Information for {bundle_id}:"]
            for k in keys:
                if k in app:
                    lines.append(f"  {k}: {app[k]}")
            extra = [k for k in app if k not in keys]
            if extra:
                lines.append(f"  (other keys: {', '.join(sorted(extra))})")
            return "\n".join(lines)

        # Fallback: plain text grep of the non-XML listing
        text_result = manager._run(
            [ideviceinstaller, "-u", udid, "-l", "-o", "list_all"], timeout=60
        )
        matches = [ln for ln in text_result.stdout.splitlines() if bundle_id in ln]
        if matches:
            return "\n".join(matches)
        return f"App not found: {bundle_id}"

    except Exception as e:
        return f"Failed to get app info: {e}"


@tool(
    name="ios_install",
    description="Install an IPA file on the connected iOS device (requires prior pairing)",
    category="ios",
)
def ios_install(ipa_path: str) -> str:
    """Install IPA on connected device."""
    manager = get_ios_manager()

    if not os.path.exists(ipa_path):
        return f"IPA file not found: {ipa_path}"

    try:
        ideviceinstaller = manager._require("ideviceinstaller")[0]
        udid = manager._resolve_udid()

        log_info(f"Installing IPA: {ipa_path}")
        result = manager._run([ideviceinstaller, "-u", udid, "-i", ipa_path], timeout=300)

        if result.returncode == 0:
            return f"IPA installed successfully: {ipa_path}\nOutput: {result.stdout.strip()}"
        return (
            f"Installation failed: {result.stderr.strip() or result.stdout.strip()}\n"
            "(Jailbroken/sideload installs may need AppSync; signed IPAs need a matching provision profile.)"
        )

    except subprocess.TimeoutExpired:
        return "Installation timed out (300s)"
    except Exception as e:
        return f"Installation error: {e}"


@tool(
    name="ios_uninstall",
    description="Uninstall an app from the connected iOS device by bundle id",
    category="ios",
)
def ios_uninstall(bundle_id: str) -> str:
    """Uninstall app from connected device."""
    manager = get_ios_manager()

    try:
        ideviceinstaller = manager._require("ideviceinstaller")[0]
        udid = manager._resolve_udid()

        log_info(f"Uninstalling app: {bundle_id}")
        result = manager._run([ideviceinstaller, "-u", udid, "-U", bundle_id], timeout=60)

        if result.returncode == 0:
            return f"App uninstalled successfully: {bundle_id}\nOutput: {result.stdout.strip()}"
        return f"Uninstallation failed: {result.stderr.strip()}"

    except Exception as e:
        return f"Uninstallation error: {e}"


@tool(
    name="ios_screenshot",
    description="Take a screenshot on the connected iOS device and save it locally",
    category="ios",
)
def ios_screenshot(local_path: str = "") -> str:
    """Capture the device screen to a PNG file."""
    manager = get_ios_manager()

    try:
        idevicescreenshot = manager._require("idevicescreenshot")[0]
        udid = manager._resolve_udid()

        if not local_path:
            local_path = os.path.join(os.getcwd(), "ios_screenshot.png")
        if not local_path.lower().endswith(".png"):
            local_path += ".png"

        result = manager._run([idevicescreenshot, "-u", udid, local_path], timeout=30)
        if result.returncode == 0 and os.path.exists(local_path):
            return f"Screenshot saved: {local_path}"
        return f"Screenshot failed: {result.stderr.strip() or result.stdout.strip()}"

    except Exception as e:
        return f"Screenshot error: {e}"


@tool(
    name="ios_pull_crash_reports",
    description="Pull crash reports from the iOS device to a local directory (very useful for RE triage)",
    category="ios",
)
def ios_pull_crash_reports(local_dir: str) -> str:
    """Copy crash reports from the device to local_dir."""
    manager = get_ios_manager()

    try:
        idevicecrashreport = manager._require("idevicecrashreport")[0]
        udid = manager._resolve_udid()

        os.makedirs(local_dir, exist_ok=True)
        result = manager._run([idevicecrashreport, "-u", udid, "-e", local_dir], timeout=120)

        if result.returncode == 0:
            pulled = [f for f in os.listdir(local_dir) if not f.startswith(".")]
            preview = "\n".join(f"  {name}" for name in pulled[:15])
            summary = f"Crash reports pulled to {local_dir} ({len(pulled)} entries)."
            if pulled:
                summary += "\n" + preview
                if len(pulled) > 15:
                    summary += f"\n  ... and {len(pulled) - 15} more"
            return summary
        return f"Crash report pull failed: {result.stderr.strip()}"

    except Exception as e:
        return f"Crash report error: {e}"


@tool(
    name="ios_backup",
    description="Create a local backup of the connected iOS device (long-running; 15 min timeout)",
    category="ios",
)
def ios_backup(dest_dir: str) -> str:
    """Back up the device with idevicebackup2."""
    manager = get_ios_manager()

    try:
        idevicebackup2 = manager._require("idevicebackup2")[0]
        udid = manager._resolve_udid()

        os.makedirs(dest_dir, exist_ok=True)
        log_info(f"Starting device backup to {dest_dir}")
        result = manager._run([idevicebackup2, "-u", udid, "backup", dest_dir], timeout=900)

        if result.returncode == 0:
            return f"Backup completed: {dest_dir}\nOutput: {result.stdout.strip()[-500:]}"
        return (
            f"Backup failed: {result.stderr.strip()[-500:]}\n"
            "(Full backup requires a paired, unlocked, trusted device; encrypted backups need the password.)"
        )

    except subprocess.TimeoutExpired:
        return "Backup timed out (900s) - retry with a smaller data set or keep the device unlocked"
    except Exception as e:
        return f"Backup error: {e}"


@tool(
    name="ios_jailbreak_check",
    description="Probe whether the device is jailbroken by testing an SSH port forwarded over USB (iproxy)",
    category="ios",
)
def ios_jailbreak_check(host: str = "127.0.0.1", port: int = 2222) -> str:
    """Probe an iproxy-forwarded SSH port on the device."""
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            return (
                f"Port {host}:{port} is OPEN - an SSH service is reachable "
                "(usually OpenSSH on a jailbroken device). Use ios_shell to run commands."
            )
    except (ConnectionRefusedError, OSError):
        return (
            f"Port {host}:{port} is not reachable. Either the device is not jailbroken, "
            "or iproxy is not forwarding. Start it manually: "
            f"`iproxy {port} 22` (bundled with libimobiledevice), then retry."
        )


@tool(
    name="ios_shell",
    description=(
        "Run an SSH shell command on a jailbroken iOS device (default root@127.0.0.1:2222 "
        "via iproxy). Only read-only analysis commands are allowed for safety, unless the "
        "user enabled unsafe commands in Spectra Settings."
    ),
    category="ios",
)
def ios_shell(
    command: str,
    host: str = "127.0.0.1",
    port: int = 2222,
    user: str = "root",
    password: str = "alpine",
) -> str:
    """Run a safe shell command on a jailbroken device over SSH."""
    manager = get_ios_manager()

    try:
        ssh = manager._require("ssh")[0]
    except RuntimeError as e:
        return str(e)

    if not manager._connected_udid:
        devices = []
        try:
            devices = manager._list_udids()
        except Exception:
            pass
        if not devices:
            return "No iOS device connected. Use ios_connect first."

    # Safety check
    is_safe, reason = manager._check_shell_command_safety(command)
    if not is_safe:
        log_warning(f"Blocked unsafe iOS shell command: {command} ({reason})")
        return f"Command not allowed for safety: {reason}"

    cmd = [ssh, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
           "-o", "ConnectTimeout=8", "-p", str(int(port)), f"{user}@{host}", command]

    if password:
        sshpass = manager._binaries.get("sshpass", "")
        if not sshpass:
            return (
                "sshpass is required for password authentication. Install it "
                "(brew install hudochenkov/sshpass/sshpass / apt install sshpass) "
                "or set up key-based SSH and pass password=''."
            )
        cmd = [sshpass, "-p", password, *cmd]

    try:
        log_debug(f"Running iOS shell command via {host}:{port}")
        result = manager._run(cmd, timeout=30)

        if result.returncode == 0:
            output = result.stdout.strip()
            return output if output else "(command executed with no output)"
        return f"Command failed: {result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return "Command timed out (30s)"
    except Exception as e:
        return f"Command error: {e}"
