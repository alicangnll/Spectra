"""Tests for the auto-updater, focused on checksum verification."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.core.updater import (
    UpdateInfo,
    Updater,
    _is_publishable_hash,
)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class TestIsPublishableHash(unittest.TestCase):
    """_is_publishable_hash separates real checksums from placeholders."""

    def test_pending_is_not_publishable(self):
        self.assertFalse(_is_publishable_hash("pending"))

    def test_empty_is_not_publishable(self):
        self.assertFalse(_is_publishable_hash(""))
        self.assertFalse(_is_publishable_hash(None))  # type: ignore[arg-type]

    def test_valid_hex_is_publishable(self):
        self.assertTrue(_is_publishable_hash("a" * 64))
        self.assertTrue(_is_publishable_hash("0123456789abcdef" * 4))

    def test_uppercase_hex_is_publishable(self):
        self.assertTrue(_is_publishable_hash("A" * 64))

    def test_wrong_length_is_not_publishable(self):
        self.assertFalse(_is_publishable_hash("a" * 63))
        self.assertFalse(_is_publishable_hash("a" * 65))

    def test_non_hex_is_not_publishable(self):
        self.assertFalse(_is_publishable_hash("z" * 64))


class TestVerifyChecksum(unittest.TestCase):
    """Updater.verify_checksum gates downloads on the published hash."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "update.zip"
        self.file.write_bytes(b"spectra update payload")

    def test_matching_hash_passes(self):
        expected = _sha256_of(self.file)
        self.assertTrue(Updater.verify_checksum(self.file, expected))

    def test_mismatching_hash_fails(self):
        wrong = "b" * 64
        self.assertFalse(Updater.verify_checksum(self.file, wrong))

    def test_pending_hash_is_tolerated(self):
        # No published checksum → nothing to verify against → allowed.
        self.assertTrue(Updater.verify_checksum(self.file, "pending"))
        self.assertTrue(Updater.verify_checksum(self.file, ""))

    def test_case_insensitive_match(self):
        expected = _sha256_of(self.file)
        self.assertTrue(Updater.verify_checksum(self.file, expected.upper()))


class TestUpdateInfo(unittest.TestCase):
    """UpdateInfo carries the checksum through the pipeline."""

    def test_sha256_defaults_to_empty(self):
        info = UpdateInfo(
            current_version="1.0.0",
            latest_version="1.1.0",
            download_url="https://example.com/s.zip",
            changelog=[],
            min_compatible_version="1.0.0",
            update_required=False,
            is_newer=True,
        )
        self.assertEqual(info.sha256, "")

    def test_sha256_field_set(self):
        info = UpdateInfo(
            current_version="1.0.0",
            latest_version="1.1.0",
            download_url="",
            changelog=[],
            min_compatible_version="1.0.0",
            update_required=False,
            is_newer=True,
            sha256="a" * 64,
        )
        self.assertEqual(info.sha256, "a" * 64)


class TestCompareVersions(unittest.TestCase):
    def test_newer(self):
        u = Updater.__new__(Updater)  # no config/network needed
        self.assertEqual(u._compare_versions("1.3.9", "1.3.8"), 1)

    def test_older(self):
        u = Updater.__new__(Updater)
        self.assertEqual(u._compare_versions("1.2.0", "1.3.8"), -1)

    def test_equal_with_padding(self):
        u = Updater.__new__(Updater)
        self.assertEqual(u._compare_versions("1.3", "1.3.0"), 0)


if __name__ == "__main__":
    unittest.main()
