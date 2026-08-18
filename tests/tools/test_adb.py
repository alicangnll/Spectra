"""Tests for ADB shell command safety and the unsafe-command bypass."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.tools.adb import _AdbManager


def _manager_without_init() -> _AdbManager:
    """Build an _AdbManager without running __init__ (no ADB lookup)."""
    return _AdbManager.__new__(_AdbManager)


class TestShellCommandSafety(unittest.TestCase):
    def test_curl_blocked_by_default(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.adb.unsafe_commands_allowed", return_value=False):
            ok, reason = mgr._check_shell_command_safety("curl http://example.com")
        self.assertFalse(ok)
        self.assertIn("not in safe list", reason)

    def test_known_safe_prefix_allowed(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.adb.unsafe_commands_allowed", return_value=False):
            ok, _reason = mgr._check_shell_command_safety("ls /data/local/tmp")
        self.assertTrue(ok)

    def test_dangerous_pattern_blocked_by_default(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.adb.unsafe_commands_allowed", return_value=False):
            ok, reason = mgr._check_shell_command_safety("rm -rf /data/something")
        self.assertFalse(ok)
        self.assertIn("dangerous pattern", reason)

    def test_empty_command_blocked(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.adb.unsafe_commands_allowed", return_value=False):
            ok, _ = mgr._check_shell_command_safety("   ")
        self.assertFalse(ok)


class TestUnsafeCommandsBypass(unittest.TestCase):
    """The Settings checkbox must bypass both the safe list and patterns."""

    def test_curl_allowed_when_enabled(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.adb.unsafe_commands_allowed", return_value=True):
            ok, reason = mgr._check_shell_command_safety("curl http://example.com")
        self.assertTrue(ok)
        self.assertIn("Unsafe-command mode", reason)

    def test_dangerous_pattern_allowed_when_enabled(self):
        mgr = _manager_without_init()
        with patch("spectra.tools.adb.unsafe_commands_allowed", return_value=True):
            ok, _ = mgr._check_shell_command_safety("rm -rf /data/something")
        self.assertTrue(ok)


class TestAdbPair(unittest.TestCase):
    """Wireless-debugging pairing tool: input validation and adb invocation."""

    def test_valid_target_passes_validation(self):
        from spectra.tools.adb import _validate_pair_target

        self.assertIsNone(_validate_pair_target("192.168.1.50:37027", "482913"))
        self.assertIsNone(_validate_pair_target(" 10.0.0.3:40112 ", " ab12cd "))

    def test_missing_inputs_rejected(self):
        from spectra.tools.adb import _validate_pair_target

        self.assertIn("required", _validate_pair_target("", "482913"))
        self.assertIn("required", _validate_pair_target("192.168.1.50:37027", ""))

    def test_address_without_port_rejected(self):
        from spectra.tools.adb import _validate_pair_target

        self.assertIn("Invalid pairing address", _validate_pair_target("192.168.1.50", "482913"))

    def test_shell_metacharacters_rejected(self):
        from spectra.tools.adb import _validate_pair_target

        self.assertIn("Invalid pairing address", _validate_pair_target("192.168.1.50;rm", "482913"))
        self.assertIn("Invalid pairing code", _validate_pair_target("192.168.1.50:37027", "-rf"))

    def _run_pair(self, ip_port, code, stdout="", stderr="", returncode=0):
        import spectra.tools.adb as adb_mod

        manager = _manager_without_init()
        manager._adb_path = "/usr/bin/adb"

        fake_result = type("_R", (), {"returncode": returncode, "stdout": stdout, "stderr": stderr})()
        with (
            patch("spectra.tools.adb.get_adb_manager", return_value=manager),
            patch("spectra.tools.adb.subprocess.run", return_value=fake_result) as fake_run,
        ):
            result = adb_mod.adb_pair(ip_port, code)
        return result, fake_run

    def test_successful_pair_reports_next_step(self):
        result, _ = self._run_pair("192.168.1.50:37027", "482913", stdout="Successfully paired to 192.168.1.50:37027")
        self.assertIn("Successfully paired", result)
        self.assertIn("adb_connect", result)

    def test_failed_pair_reports_adb_output(self):
        result, _ = self._run_pair(
            "192.168.1.50:37027", "000000", stderr="failed to authenticate to 192.168.1.50:37027"
        )
        self.assertIn("Pairing failed", result)
        self.assertIn("failed to authenticate", result)

    def test_invalid_input_never_invokes_adb(self):
        result, fake_run = self._run_pair("not-an-address", "482913")
        self.assertIn("Invalid pairing address", result)
        fake_run.assert_not_called()


class TestConfigRoundTrip(unittest.TestCase):
    """Persisted-flag plumbing for allow_unsafe_commands.

    Runs in a subprocess: several test modules in this suite replace
    sys.modules["spectra.core.config"] with synthetic stubs, so an
    in-process import cannot be trusted to exercise the real save/load
    path.
    """

    _SCRIPT = """
import json, sys, tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from spectra.core.config import CONFIG_FILE_NAME, SpectraConfig

with tempfile.TemporaryDirectory() as tmp:
    cfg = SpectraConfig(_config_dir=tmp)
    cfg.allow_unsafe_commands = True
    cfg.save()

    reloaded = SpectraConfig(_config_dir=tmp)
    reloaded.load()
    assert reloaded.allow_unsafe_commands is True, "flag lost through save/load"
    print("PERSIST_OK")

    # Simulate a config written before the flag existed
    (Path(tmp) / CONFIG_FILE_NAME).write_text(json.dumps({"provider": {"name": "anthropic"}}))
    old = SpectraConfig(_config_dir=tmp)
    old.load()
    assert old.allow_unsafe_commands is False, "old config should default to False"
    print("OLD_DEFAULT_OK")
"""

    def _run_script(self) -> str:
        import subprocess

        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        proc = subprocess.run(
            [sys.executable, "-c", self._SCRIPT, root],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc.stdout + "\n" + proc.stderr + f"\n(rc={proc.returncode})"

    def test_flag_persists_through_save_and_load(self):
        self.assertIn("PERSIST_OK", self._run_script())

    def test_defaults_to_false_for_old_configs(self):
        self.assertIn("OLD_DEFAULT_OK", self._run_script())


if __name__ == "__main__":
    unittest.main()
