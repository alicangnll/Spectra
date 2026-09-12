"""Tests for the CLI entry key flow (spectra_cli.py).

Covers the encrypted-key path: a key saved encrypted (e.g. via the IDA
plugin's settings dialog) must be read from the shared config — prompting
for the decryption password — instead of falling through to the first-run
"enter an API key" onboarding.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from tests.mocks.ida_mock import install_ida_mocks

install_ida_mocks()

import spectra_cli
from spectra.core.config import SpectraConfig
from spectra.core.crypto import is_available


class _FakeGetpass:
    """Replace spectra_cli.getpass with canned answers."""

    def __init__(self, answers: list[str]):
        self.answers = iter(answers)

    def getpass(self, prompt: str = "") -> str:
        return next(self.answers)


def _install(answers: list[str]):
    original = spectra_cli.getpass
    spectra_cli.getpass = _FakeGetpass(answers)
    return original


@unittest.skipUnless(is_available(), "cryptography not installed")
class TestCliEncryptedKeyFlow(unittest.TestCase):
    def setUp(self):
        import shutil

        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def _save_encrypted(self, api_key: str, password: str) -> None:
        cfg = SpectraConfig()
        cfg._config_dir = self._tmp
        cfg.provider.name = "anthropic"
        cfg.provider.api_key = api_key
        cfg.encrypt_api_keys = True
        cfg.save(password=password)

    def _load(self) -> SpectraConfig:
        cfg = SpectraConfig()
        cfg._config_dir = self._tmp
        cfg.load()
        return cfg

    def test_encrypted_key_detected_and_disk_stays_encrypted(self):
        self._save_encrypted("sk-ant-test-123", "secret123")
        cfg = self._load()

        self.assertTrue(cfg.has_encrypted_keys())
        self.assertEqual(cfg.provider.api_key, "")  # deferred decryption
        disk = json.loads((Path(self._tmp) / "config.json").read_text())
        self.assertEqual(disk["provider"]["api_key"], "")
        self.assertTrue(disk["encryption"]["enabled"])

    def test_prompt_correct_password_decrypts(self):
        self._save_encrypted("sk-ant-test-123", "secret123")
        cfg = self._load()

        original = _install(["secret123"])
        try:
            self.assertTrue(spectra_cli.prompt_decrypt_password(cfg))
        finally:
            spectra_cli.getpass = original
        self.assertEqual(cfg.provider.api_key, "sk-ant-test-123")
        # check_api_key_from_config must now find the key
        has_key, provider = spectra_cli.check_api_key_from_config(cfg)
        self.assertTrue(has_key)
        self.assertEqual(provider, "anthropic")

    def test_prompt_three_wrong_passwords_stay_locked(self):
        self._save_encrypted("sk-ant-test-123", "secret123")
        cfg = self._load()

        original = _install(["nope", "nope", "nope"])
        try:
            self.assertFalse(spectra_cli.prompt_decrypt_password(cfg))
        finally:
            spectra_cli.getpass = original
        self.assertEqual(cfg.provider.api_key, "")
        has_key, _ = spectra_cli.check_api_key_from_config(cfg)
        self.assertFalse(has_key)

    def test_prompt_empty_password_cancels(self):
        self._save_encrypted("sk-ant-test-123", "secret123")
        cfg = self._load()

        original = _install([""])
        try:
            self.assertFalse(spectra_cli.prompt_decrypt_password(cfg))
        finally:
            spectra_cli.getpass = original

    def test_no_key_no_encryption_reports_missing(self):
        cfg = SpectraConfig()
        cfg._config_dir = self._tmp
        cfg.provider.name = "anthropic"
        cfg.provider.api_key = ""
        cfg.save()

        loaded = self._load()
        self.assertFalse(loaded.has_encrypted_keys())
        has_key, _ = spectra_cli.check_api_key_from_config(loaded)
        self.assertFalse(has_key)  # this state routes to onboarding


if __name__ == "__main__":
    unittest.main()
