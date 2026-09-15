"""Tests for the standalone-Python resolver (IDA host-binary guard).

Regression: under IDA ``sys.executable`` is the host binary
(ida64.exe / ida64). A subprocess call built from it launches new IDA
processes instead of Python — on Windows this looped (each spawned IDA
reloaded the plugin, whose auto-install spawned another IDA).
"""

import os
import sys
import unittest
from unittest import mock

from spectra.core.interpreter import is_python_interpreter, resolve_python_executable


class TestIsPythonInterpreter(unittest.TestCase):
    def test_accepts_real_interpreters(self):
        for name in ("python", "python3", "python3.13", "python.exe", "Python310.exe", "/usr/bin/python3.11"):
            self.assertTrue(is_python_interpreter(name), name)

    def test_rejects_ida_host_binaries(self):
        # The Windows fork-bomb: any ".exe" used to be accepted.
        for name in ("ida64.exe", "idat64.exe", "ida.exe", "C:\\Program Files\\IDA\\ida64.exe", "/opt/ida/ida64"):
            self.assertFalse(is_python_interpreter(name), name)

    def test_rejects_empty(self):
        self.assertFalse(is_python_interpreter(None))
        self.assertFalse(is_python_interpreter(""))


class TestResolvePythonExecutable(unittest.TestCase):
    def test_prefers_sys_executable_when_python(self):
        with mock.patch("spectra.core.interpreter.sys") as fake_sys:
            fake_sys.executable = sys.executable  # real interpreter in tests
            fake_sys.version_info = sys.version_info
            self.assertEqual(resolve_python_executable(), sys.executable)

    def test_falls_back_to_path_when_host_binary(self):
        # sys.executable = IDA host binary → must NOT be returned.
        with mock.patch("spectra.core.interpreter.sys") as fake_sys, mock.patch(
            "spectra.core.interpreter.shutil"
        ) as fake_shutil:
            fake_sys.executable = r"C:\Program Files\IDA Pro\ida64.exe"
            fake_sys.version_info = sys.version_info
            fake_shutil.which.side_effect = lambda name: f"/usr/bin/{name}" if name == "python3" else None
            resolved = resolve_python_executable()
            self.assertEqual(resolved, "/usr/bin/python3")
            self.assertNotIn("ida", os.path.basename(resolved).lower())

    def test_returns_none_when_nothing_found(self):
        with mock.patch("spectra.core.interpreter.sys") as fake_sys, mock.patch(
            "spectra.core.interpreter.shutil"
        ) as fake_shutil:
            fake_sys.executable = "ida64.exe"
            fake_sys.version_info = sys.version_info
            fake_shutil.which.return_value = None
            self.assertIsNone(resolve_python_executable())


if __name__ == "__main__":
    unittest.main()
