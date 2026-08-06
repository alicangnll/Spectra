#!/usr/bin/env python3
"""
Spectra ADB Plugin - Android Device Bridge Integration

This script provides ADB (Android Debug Bridge) integration for Spectra.
Works in multiple modes:
1. **Standalone CLI**: Direct execution from terminal
2. **IDA Pro Plugin**: Integrated with IDA Pro's Spectra
3. **Binary Ninja Plugin**: Integrated with Binary Ninja's Spectra
4. **Standalone Helper**: For APK analysis workflows

Features:
- Connect to USB and wireless ADB devices
- Install/uninstall APKs
- Run safe shell commands (read-only analysis)
- Pull/push files
- List packages and app information
- Safety restrictions to prevent system damage

Usage:
    # Connect and list devices
    python spectra_adb.py list

    # Connect to device
    python spectra_adb.py connect

    # Install APK
    python spectra_adb.py install app.apk

    # Run shell command
    python spectra_adb.py shell "getprop"

    # List packages
    python spectra_adb.py packages

Requirements:
    - ADB (Android Platform Tools): https://developer.android.com/studio/releases/platform-tools
    - Python 3.10+
    - Spectra dependencies (for IDA/BN integration)

Author: Ali Can Gönüllü
License: MIT
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Ali Can Gönüllü"

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Add Spectra to path
spectra_path = Path(__file__).parent
sys.path.insert(0, str(spectra_path))

# Try to import Spectra components
try:
    from spectra.adb import AdbManager, create_adb_tools
    SPECTRA_AVAILABLE = True
except ImportError:
    SPECTRA_AVAILABLE = False
    print("Warning: Spectra core not available, running in standalone mode")


def print_section(title: str) -> None:
    """Print formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_json(data: dict, pretty: bool = True) -> None:
    """Print JSON data."""
    if pretty:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data))


def cmd_check(args) -> int:
    """Check ADB availability and list devices."""
    print_section("ADB Status Check")

    try:
        manager = AdbManager()
        result = manager.check_adb_available()

        if result.get("adb_available"):
            print(f"✅ ADB is available")
            print(f"   Path: {result.get('adb_path')}")
            print(f"   Devices: {result.get('device_count', 0)}")

            if result.get("devices"):
                print(f"\nConnected devices:")
                for device in result.get("devices", []):
                    print(f"  - {device.get('id')}: {device.get('product', 'unknown')} ({device.get('model', 'unknown')})")
            else:
                print(f"\n⚠️  No devices connected. Connect a device via USB or wireless.")
                print(f"   USB: Enable USB debugging on device")
                print(f"   Wireless: adb connect <IP>:<port>")
        else:
            print(f"❌ ADB not available: {result.get('error')}")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_connect(args) -> int:
    """Connect to an ADB device."""
    print_section("Connect to ADB Device")

    try:
        manager = AdbManager()
        device_id = args.device if hasattr(args, 'device') and args.device else None

        result = manager.connect_to_device(device_id)

        if result.get("success"):
            print(f"✅ Connected to device")
            print(f"   ID: {result.get('device_id')}")
            print(f"   Manufacturer: {result.get('manufacturer')}")
            print(f"   Model: {result.get('model')}")
            print(f"   Android: {result.get('android_version')}")
            print(f"   SDK: {result.get('sdk_version')}")
            print(f"   Architecture: {result.get('architecture')}")
            print(f"   Rooted: {'Yes ⚠️' if result.get('rooted') else 'No'}")
        else:
            print(f"❌ Connection failed: {result.get('error')}")
            return 1

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_install(args) -> int:
    """Install APK on device."""
    print_section(f"Install APK: {args.apk}")

    try:
        manager = AdbManager()

        # First connect if not connected
        check = manager.check_adb_available()
        if check.get('device_count', 0) == 0:
            print("⚠️  No device connected. Connecting...")
            conn = manager.connect_to_device()
            if not conn.get("success"):
                print(f"❌ Failed to connect: {conn.get('error')}")
                return 1

        result = manager.install_apk(
            apk_path=args.apk,
            replace=not args.no_replace,
            grant_permissions=not args.no_grant
        )

        if result.get("success"):
            print(f"✅ APK installed successfully")
            print(f"   {result.get('output')}")
        else:
            print(f"❌ Installation failed: {result.get('error')}")
            return 1

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_uninstall(args) -> int:
    """Uninstall app from device."""
    print_section(f"Uninstall: {args.package}")

    try:
        manager = AdbManager()

        result = manager.uninstall_app(
            package_name=args.package,
            keep_data=args.keep_data
        )

        if result.get("success"):
            print(f"✅ Package uninstalled successfully")
            print(f"   {result.get('output')}")
        else:
            print(f"❌ Uninstallation failed: {result.get('error')}")
            return 1

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_shell(args) -> int:
    """Run shell command on device."""
    print_section(f"Shell Command: {args.command}")

    try:
        manager = AdbManager()

        result = manager.run_shell_command(args.command)

        if result.get("success"):
            output = result.get('output', '')
            if output:
                print(output)
            else:
                print("(No output)")
        else:
            error = result.get('error', '')
            print(f"❌ Command failed: {error}")
            return 1

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_packages(args) -> int:
    """List installed packages."""
    print_section("Installed Packages")

    try:
        manager = AdbManager()

        result = manager.list_packages(user_only=not args.all)

        if result.get("success"):
            packages = result.get('packages', [])
            print(f"Total packages: {result.get('count', 0)}\n")

            if args.filter:
                filtered = [p for p in packages if args.filter.lower() in p.lower()]
                packages = filtered

            for pkg in packages[:50]:  # Limit to first 50
                print(f"  - {pkg}")

            if len(packages) > 50:
                print(f"\n... and {len(packages) - 50} more packages")
        else:
            print(f"❌ Failed: {result.get('error')}")
            return 1

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_app_info(args) -> int:
    """Get app information."""
    print_section(f"App Info: {args.package}")

    try:
        manager = AdbManager()

        result = manager.get_app_info(args.package)

        if result.get("success"):
            print(f"Package: {result.get('package_name')}")
            print(f"Version Code: {result.get('version_code')}")
            print(f"Version Name: {result.get('version_name')}")
            print(f"Target SDK: {result.get('target_sdk')}")
            print(f"Data Dir: {result.get('data_dir')}")

            permissions = result.get('permissions', [])
            print(f"\nPermissions ({len(permissions)}):")
            for perm in permissions[:20]:
                print(f"  - {perm}")

            if len(permissions) > 20:
                print(f"  ... and {len(permissions) - 20} more permissions")
        else:
            print(f"❌ Failed: {result.get('error')}")
            return 1

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_pull(args) -> int:
    """Pull file from device."""
    print_section(f"Pull File: {args.remote}")

    try:
        manager = AdbManager()

        result = manager.pull_file(args.remote, args.local)

        if result.get("success"):
            print(f"✅ File pulled successfully")
            print(f"   From: {result.get('remote_path')}")
            print(f"   To: {result.get('local_path')}")
        else:
            print(f"❌ Failed: {result.get('error')}")
            return 1

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_push(args) -> int:
    """Push file to device."""
    print_section(f"Push File: {args.local}")

    try:
        manager = AdbManager()

        result = manager.push_file(args.local, args.remote)

        if result.get("success"):
            print(f"✅ File pushed successfully")
            print(f"   From: {result.get('local_path')}")
            print(f"   To: {result.get('remote_path')}")
        else:
            print(f"❌ Failed: {result.get('error')}")
            return 1

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_devices(args) -> int:
    """List all connected devices."""
    print_section("Connected Devices")

    try:
        manager = AdbManager()

        result = manager.list_devices()

        devices = result.get('devices', [])

        if devices:
            print(f"Found {len(devices)} device(s):\n")

            for device in devices:
                print(f"  ID: {device.get('id')}")
                print(f"  Status: {device.get('status')}")
                if device.get('model'):
                    print(f"  Model: {device.get('model')}")
                if device.get('product'):
                    print(f"  Product: {device.get('product')}")
                if device.get('device'):
                    print(f"  Device: {device.get('device')}")
                if device.get('usb'):
                    print(f"  USB: {device.get('usb')}")
                print()
        else:
            print("No devices found.")
            print("\nTo connect a device:")
            print("  USB: Enable USB debugging on device")
            print("  Wireless: adb connect <IP>:<port>")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def main() -> int:
    """Main entry point."""

    parser = argparse.ArgumentParser(
        description="Spectra ADB Plugin - Android Device Bridge Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s check                    # Check ADB availability
  %(prog)s devices                  # List connected devices
  %(prog)s connect                  # Connect to first available device
  %(prog)s connect 192.168.1.100:5555  # Connect to wireless device
  %(prog)s install app.apk         # Install APK
  %(prog)s uninstall com.example.app    # Uninstall app
  %(prog)s shell "getprop"          # Run shell command
  %(prog)s shell "ls /data/data"   # List data directory
  %(prog)s packages                 # List user apps
  %(prog)s packages --all          # List all apps (including system)
  %(prog)s app-info com.example.app  # Get app details
  %(prog)s pull /sdcard/file.txt ./file.txt  # Pull file
  %(prog)s push ./file.txt /sdcard/        # Push file

Safety:
  Shell commands are restricted to read-only operations for safety.
  Dangerous commands (rm, format, etc.) are blocked even on rooted devices.
        """
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Check command
    subparsers.add_parser("check", help="Check ADB availability")

    # Devices command
    subparsers.add_parser("devices", help="List connected devices")

    # Connect command
    connect_parser = subparsers.add_parser("connect", help="Connect to device")
    connect_parser.add_argument("device", nargs="?", help="Device ID (serial or IP:port)")

    # Install command
    install_parser = subparsers.add_parser("install", help="Install APK")
    install_parser.add_argument("apk", help="APK file path")
    install_parser.add_argument("--no-replace", action="store_true", help="Don't replace existing app")
    install_parser.add_argument("--no-grant", action="store_true", help="Don't auto-grant permissions")

    # Uninstall command
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall app")
    uninstall_parser.add_argument("package", help="Package name")
    uninstall_parser.add_argument("--keep-data", action="store_true", help="Keep app data")

    # Shell command
    shell_parser = subparsers.add_parser("shell", help="Run shell command")
    shell_parser.add_argument("command", help="Shell command to execute")

    # Packages command
    packages_parser = subparsers.add_parser("packages", help="List installed packages")
    packages_parser.add_argument("--all", action="store_true", help="Include system packages")
    packages_parser.add_argument("--filter", help="Filter package names")

    # App info command
    app_info_parser = subparsers.add_parser("app-info", help="Get app information")
    app_info_parser.add_argument("package", help="Package name")

    # Pull command
    pull_parser = subparsers.add_parser("pull", help="Pull file from device")
    pull_parser.add_argument("remote", help="Remote path")
    pull_parser.add_argument("local", help="Local destination path")

    # Push command
    push_parser = subparsers.add_parser("push", help="Push file to device")
    push_parser.add_argument("local", help="Local source path")
    push_parser.add_argument("remote", help="Remote destination path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to appropriate command handler
    command_handlers = {
        "check": cmd_check,
        "devices": cmd_devices,
        "connect": cmd_connect,
        "install": cmd_install,
        "uninstall": cmd_uninstall,
        "shell": cmd_shell,
        "packages": cmd_packages,
        "app-info": cmd_app_info,
        "pull": cmd_pull,
        "push": cmd_push,
    }

    handler = command_handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
