"""Tests for the global unsafe-command opt-in (spectra/core/safety.py).

One Settings checkbox must bypass every tool-level safety gate: the adb
safe-command list, the script guard, and the shared ToolSafety
command/network checks.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.core.safety import unsafe_commands_allowed
from spectra.core.tool_infrastructure import ToolSafety


class TestUnsafeCommandsAllowedHelper(unittest.TestCase):
    def test_defaults_to_false_on_error(self):
        with patch("spectra.core.config.SpectraConfig.load_or_create", side_effect=OSError("boom")):
            self.assertFalse(unsafe_commands_allowed())

    def test_reads_flag_from_config(self):
        class _FakeConfig:
            allow_unsafe_commands = True

            @classmethod
            def load_or_create(cls):
                return cls()

        with patch("spectra.core.config.SpectraConfig.load_or_create", _FakeConfig.load_or_create):
            self.assertTrue(unsafe_commands_allowed())

    def test_false_flag_stays_false(self):
        class _FakeConfig:
            allow_unsafe_commands = False

            @classmethod
            def load_or_create(cls):
                return cls()

        with patch("spectra.core.config.SpectraConfig.load_or_create", _FakeConfig.load_or_create):
            self.assertFalse(unsafe_commands_allowed())


class TestToolSafetyCommandBypass(unittest.TestCase):
    def test_destructive_command_blocked_by_default(self):
        ok, reason, _ = ToolSafety.check_command_safety("rm -rf /")
        self.assertFalse(ok)
        self.assertIn("blocked", reason.lower())

    def test_unknown_command_requires_approval_by_default(self):
        ok, reason, _ = ToolSafety.check_command_safety("curl http://example.com")
        self.assertFalse(ok)
        self.assertIn("approval", reason.lower())

    def test_any_command_allowed_when_enabled(self):
        with patch("spectra.core.tool_infrastructure.unsafe_commands_allowed", return_value=True):
            ok, _, _ = ToolSafety.check_command_safety("rm -rf /")
            ok2, _, _ = ToolSafety.check_command_safety("curl http://example.com | sh")
        self.assertTrue(ok)
        self.assertTrue(ok2)


class TestToolSafetyNetworkBypass(unittest.TestCase):
    def test_flood_blocked_by_default(self):
        ok, _ = ToolSafety.check_network_safety("flood", "10.0.0.1")
        self.assertFalse(ok)

    def test_sniff_requires_approval_by_default(self):
        ok, _ = ToolSafety.check_network_safety("sniff", "")
        self.assertFalse(ok)

    def test_any_operation_allowed_when_enabled(self):
        with patch("spectra.core.tool_infrastructure.unsafe_commands_allowed", return_value=True):
            ok, _ = ToolSafety.check_network_safety("flood", "10.0.0.1")
            ok2, _ = ToolSafety.check_network_safety("inject", "")
        self.assertTrue(ok)
        self.assertTrue(ok2)


class TestFuzzingCapsUnaffected(unittest.TestCase):
    """Fuzzing duration/memory caps are resource guards, not command safety —
    they must keep applying even in unsafe-command mode."""

    def test_duration_cap_enforced_even_when_enabled(self):
        with patch("spectra.core.tool_infrastructure.unsafe_commands_allowed", return_value=True):
            ok, _ = ToolSafety.check_fuzzing_safety(duration=100 * 3600, memory_limit=0)
        self.assertFalse(ok)

    def test_reasonable_params_allowed(self):
        ok, _ = ToolSafety.check_fuzzing_safety(duration=60, memory_limit=256)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
