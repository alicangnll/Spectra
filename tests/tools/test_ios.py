"""Tests for the iOS device tools (spectra/tools/ios.py).

Mirrors tests/tools/test_adb.py: safety gate defaults, the unsafe-command
bypass, binary discovery, and device selection — all without a real device
or libimobiledevice install.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.tools import ios
from spectra.tools.ios import _IosManager, get_ios_manager
from spectra.tools.registry import ToolRegistry


def _manager_without_init() -> _IosManager:
    """Build an _IosManager without running __init__ (no binary lookup)."""
    mgr = _IosManager.__new__(_IosManager)
    mgr._connected_udid = None
    mgr._binaries = {}
    return mgr


class TestShellCommandSafety(unittest.TestCase):
    def test_curl_blocked_by_default(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.unsafe_commands_allowed", return_value=False):
            ok, reason = mgr._check_shell_command_safety("curl http://example.com")
        self.assertFalse(ok)
        self.assertIn("not in safe list", reason)

    def test_known_safe_prefix_allowed(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.unsafe_commands_allowed", return_value=False):
            ok, _reason = mgr._check_shell_command_safety("ls /var/mobile/Containers")
        self.assertTrue(ok)

    def test_rm_rf_blocked_by_default(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.unsafe_commands_allowed", return_value=False):
            ok, reason = mgr._check_shell_command_safety("rm -rf /var/mobile/Media")
        self.assertFalse(ok)
        self.assertIn("dangerous pattern", reason)

    def test_dangerous_prefix_variants_blocked(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.unsafe_commands_allowed", return_value=False):
            for command in ("reboot", "dpkg -r com.example.app", "killall SpringBoard", "passwd"):
                ok, _ = mgr._check_shell_command_safety(command)
                self.assertFalse(ok, command)

    def test_read_only_dpkg_list_allowed(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.unsafe_commands_allowed", return_value=False):
            ok, reason = mgr._check_shell_command_safety("dpkg -l")
        self.assertTrue(ok)
        self.assertIn("Read-only", reason)

    def test_read_only_plutil_print_allowed(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.unsafe_commands_allowed", return_value=False):
            ok, _ = mgr._check_shell_command_safety("plutil -p /var/mobile/Library/Preferences/com.apple.springboard.plist")
        self.assertTrue(ok)

    def test_empty_command_blocked(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.unsafe_commands_allowed", return_value=False):
            ok, _ = mgr._check_shell_command_safety("   ")
        self.assertFalse(ok)


class TestUnsafeCommandsBypass(unittest.TestCase):
    """The Settings checkbox must bypass both the safe list and patterns."""

    def test_curl_allowed_when_enabled(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.unsafe_commands_allowed", return_value=True):
            ok, reason = mgr._check_shell_command_safety("curl http://example.com")
        self.assertTrue(ok)
        self.assertIn("Unsafe-command mode", reason)

    def test_rm_rf_allowed_when_enabled(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.unsafe_commands_allowed", return_value=True):
            ok, _ = mgr._check_shell_command_safety("rm -rf /var/mobile/Media")
        self.assertTrue(ok)


class TestBinaryDiscovery(unittest.TestCase):
    def test_find_tool_via_which(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.shutil.which", return_value="/opt/homebrew/bin/ideviceinfo"):
            self.assertEqual(mgr._find_tool("ideviceinfo"), "/opt/homebrew/bin/ideviceinfo")

    def test_find_tool_in_common_dir(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.shutil.which", return_value=None), patch(
            "spectra.tools.ios._EXTRA_BIN_DIRS", ("/opt/fake/bin",)
        ), patch("spectra.tools.ios.os.path.exists", return_value=True):
            self.assertEqual(mgr._find_tool("idevice_id"), "/opt/fake/bin/idevice_id")

    def test_find_tool_missing(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.ios.shutil.which", return_value=None), patch(
            "spectra.tools.ios._EXTRA_BIN_DIRS", ()
        ):
            self.assertIsNone(mgr._find_tool("idevice_id"))

    def test_require_reports_missing_tools_with_hint(self):
        mgr = _manager_without_init()
        mgr._binaries = {"ideviceinfo": "", "ideviceinstaller": "/usr/bin/ideviceinstaller"}
        with self.assertRaises(RuntimeError) as ctx:
            mgr._require("ideviceinfo", "ideviceinstaller")
        self.assertIn("ideviceinfo", str(ctx.exception))
        self.assertIn("libimobiledevice", str(ctx.exception))


class TestResolveUdid(unittest.TestCase):
    def test_explicit_udid_wins(self):
        mgr = _manager_without_init()
        self.assertEqual(mgr._resolve_udid("AAA-111"), "AAA-111")

    def test_connected_udid_used_when_no_argument(self):
        mgr = _manager_without_init()
        mgr._connected_udid = "BBB-222"
        self.assertEqual(mgr._resolve_udid(), "BBB-222")

    def test_single_device_selected_automatically(self):
        mgr = _manager_without_init()
        with patch.object(_IosManager, "_list_udids", return_value=["CCC-333", "DDD-444"]):
            self.assertEqual(mgr._resolve_udid(), "CCC-333")

    def test_no_device_raises_actionable_error(self):
        mgr = _manager_without_init()
        with patch.object(_IosManager, "_list_udids", return_value=[]):
            with self.assertRaises(RuntimeError) as ctx:
                mgr._resolve_udid()
        self.assertIn("ios_pair", str(ctx.exception))


class TestJailbreakCheck(unittest.TestCase):
    def test_closed_port_reports_iproxy_hint(self):
        # Port 1 on localhost: nothing listens there in test environments.
        result = ios.ios_jailbreak_check(port=1)
        self.assertIn("not reachable", result)
        self.assertIn("iproxy", result)


class TestToolRegistration(unittest.TestCase):
    def test_module_registers_all_ios_tools(self):
        registry = ToolRegistry()
        registry.register_module(ios)
        names = set(registry.list_names())
        expected = {
            "ios_check",
            "ios_pair",
            "ios_connect",
            "ios_info",
            "ios_syslog",
            "ios_list_apps",
            "ios_app_info",
            "ios_install",
            "ios_uninstall",
            "ios_screenshot",
            "ios_pull_crash_reports",
            "ios_backup",
            "ios_jailbreak_check",
            "ios_shell",
        }
        self.assertEqual(names, expected)

    def test_manager_is_singleton(self):
        self.assertIs(get_ios_manager(), get_ios_manager())


if __name__ == "__main__":
    unittest.main()
