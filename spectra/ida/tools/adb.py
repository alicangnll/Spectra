"""ADB (Android Debug Bridge) tools for IDA Pro.

This module provides IDA Pro-specific wrappers for ADB functionality,
allowing Android device interaction during reverse engineering sessions.

Useful for:
- Dynamic analysis of Android binaries
- Testing hypotheses during static analysis
- Verifying behavior on real devices
- Pulling/pushing files for analysis
"""

from __future__ import annotations

from typing import Annotated

from ...tools.base import tool
from ...tools.adb import (
    adb_check,
    adb_connect,
    adb_install,
    adb_uninstall,
    adb_shell,
    adb_list_packages,
    adb_app_info,
    adb_pull,
    adb_push,
    get_adb_manager,
)


# Re-export the core ADB tools with IDA-specific descriptions
@tool(category="adb", description="Check ADB availability and list connected Android devices")
def ida_adb_check() -> str:
    """Check if ADB is available and list connected Android devices.

    Useful before starting dynamic analysis to ensure device connectivity.

    Returns:
        Device list and connection status.
    """
    return adb_check()


@tool(category="adb", description="Connect to an Android device via ADB")
def ida_adb_connect(
    device_id: Annotated[str, "Device ID (serial or IP:port for wireless). Leave empty for first available device."] = "",
) -> str:
    """Connect to an Android device and get device information.

    This is useful before performing dynamic analysis to verify:
    - Device model and manufacturer
    - Android version compatibility
    - Architecture matching
    - Root status (for advanced analysis)

    Args:
        device_id: Optional device serial or IP:port for wireless connection

    Returns:
        Device information including model, Android version, and rooted status.
    """
    return adb_connect(device_id=device_id)


@tool(category="adb", description="Install APK on connected Android device")
def ida_adb_install(
    apk_path: Annotated[str, "Path to the APK file to install"],
    replace: Annotated[bool, "Replace existing installation"] = True,
    grant_permissions: bool = True,
) -> str:
    """Install an APK on the connected Android device for dynamic analysis.

    Common workflow:
    1. Extract APK from device or download
    2. Install with ida_adb_install
    3. Analyze with JADX/IDA
    4. Test findings dynamically with adb_shell

    Args:
        apk_path: Path to the APK file
        replace: Replace existing version if already installed
        grant_permissions: Automatically grant all permissions

    Returns:
        Installation result with success/failure status.
    """
    return adb_install(apk_path=apk_path, replace=replace, grant_permissions=grant_permissions)


@tool(category="adb", description="Uninstall app from connected Android device")
def ida_adb_uninstall(
    package_name: Annotated[str, "Package name to uninstall (e.g., com.example.app)"],
    keep_data: Annotated[bool, "Keep app data and cache"] = False,
) -> str:
    """Uninstall an app from the connected device.

    Useful for:
    - Clean testing environments
    - Removing test builds
    - Resetting app state for retesting

    Args:
        package_name: Package name (e.g., com.example.app)
        keep_data: Preserve app data for later analysis

    Returns:
        Uninstallation result.
    """
    return adb_uninstall(package_name=package_name, keep_data=keep_data)


@tool(category="adb", description="Run safe shell command on Android device")
def ida_adb_shell(
    command: Annotated[str, "Shell command to execute (read-only commands only for safety)"],
) -> str:
    """Execute a shell command on the connected Android device.

    Safe commands include:
    - File operations: ls, cat, file, strings
    - Process info: ps, top
    - System info: getprop, dumpsys, dumpstate
    - Network: netstat, netcfg, ifconfig, ip
    - Package info: pm, am
    - Database: sqlite3
    - Logs: logcat, dmesg

    Safety: Dangerous commands (rm, format, wipe, etc.) are blocked.

    Args:
        command: Shell command to execute

    Returns:
        Command output.
    """
    return adb_shell(command=command)


@tool(category="adb", description="List installed packages on Android device")
def ida_adb_packages(
    user_only: Annotated[bool, "Show only user apps (exclude system)"] = True,
) -> str:
    """List installed packages on the connected Android device.

    Useful for:
    - Finding target apps for analysis
    - Checking if app is installed
    - Enumerating attack surface

    Args:
        user_only: Show only user-installed apps

    Returns:
        List of package names.
    """
    return adb_list_packages(user_only=user_only)


@tool(category="adb", description="Get detailed app information from Android device")
def ida_adb_app_info(
    package_name: Annotated[str, "Package name (e.g., com.example.app)"],
) -> str:
    """Get detailed information about an installed app.

    Returns:
        - Version code and name
        - Target SDK version
        - Data directory path
        - Permissions list
        - APK path

    This information is useful for:
        - Version-specific vulnerability research
        - Permission analysis
        - Finding data directories for forensics

    Args:
        package_name: Package name (e.g., com.example.app)

    Returns:
        Detailed app information.
    """
    return adb_app_info(package_name=package_name)


@tool(category="adb", description="Pull file from Android device")
def ida_adb_pull(
    remote_path: Annotated[str, "Path on the Android device (e.g., /data/data/com.example.app/databases/db.db)"],
    local_path: Annotated[str, "Local destination path (e.g., ./extracted.db)"],
) -> str:
    """Pull a file from the Android device to local machine.

    Common use cases:
    - Extract app databases for analysis
    - Pull configuration files
    - Download shared preferences
    - Get APK files from device
    - Extract log files

    Args:
        remote_path: Source path on the device
        local_path: Destination path on local machine

    Returns:
        File transfer result with paths.
    """
    return adb_pull(remote_path=remote_path, local_path=local_path)


@tool(category="adb", description="Push file to Android device")
def ida_adb_push(
    local_path: Annotated[str, "Local file path (e.g., ./test_file.txt)"],
    remote_path: Annotated[str, "Destination path on device (e.g., /sdcard/test_file.txt)"],
) -> str:
    """Push a file from local machine to the Android device.

    Common use cases:
    - Push test files for input validation
    - Upload modified configuration files
    - Transfer exploits for testing (authorized only)
    - Push analysis scripts

    Args:
        local_path: Source path on local machine
        remote_path: Destination path on the device

    Returns:
        File transfer result with paths.
    """
    return adb_push(local_path=local_path, remote_path=remote_path)


@tool(category="adb", description="List functions that call Android APIs related to current analysis")
def find_android_api_calls(
    ea: Annotated[int, "Function address to analyze"] = 0,
) -> str:
    """Find Android API calls in the current function.

    Scans the function for references to Android APIs and system calls.
    Useful for understanding what the app does and finding interesting
    functions for dynamic testing.

    Returns:
        List of Android API calls found with analysis.
    """
    try:
        import ida_hexrays
        import ida_name
        import ida_funcs
        import ida_xref
    except ImportError:
        return "Error: IDA API not available"

    if ea == 0:
        ea = ida_hexrays.get_screen_ea()

    func = ida_funcs.get_func(ea)
    if not func:
        return f"No function found at address 0x{ea:X}"

    # Look for Android API imports and calls
    android_symbols = []
    api_patterns = [
        "android::", "Java_", "JNI_", "ANative",
        "AAsset", "AConfiguration", "ALooper",
        "_Znj"  # C++ new (common in Android)
    ]

    # Scan for xrefs to potential Android APIs
    for xref in ida_xref.XrefsTo(ea, 0):
        target_name = ida_name.get_name(xref.to)
        if target_name:
            for pattern in api_patterns:
                if pattern in target_name:
                    android_symbols.append({
                        "name": target_name,
                        "address": f"0x{xref.to:X}",
                        "type": xref.type
                    })

    if not android_symbols:
        return f"No Android API calls found in function at 0x{ea:X}"

    report = f"""## Android API Calls Found

**Function Address:** 0x{ea:X}
**Function Name:** {ida_hexrays.get_func_name(ea)}
**API Calls Found:** {len(android_symbols)}

| Symbol | Address | Type |
|--------|---------|------|
"""
    for sym in android_symbols[:50]:
        report += f"| {sym['name']} | {sym['address']} | {sym['type']} |\n"

    if len(android_symbols) > 50:
        report += f"| ... | ... and {len(android_symbols) - 50} more | ... |\n"

    report += "\n**Suggestion:** Use `ida_adb_shell` to test these APIs dynamically."

    return report
