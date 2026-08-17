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


class _InfiniteResponse:
    """Fake urlopen response whose read() never hits EOF — a stalled stream."""

    headers = {"Content-Length": "1073741824"}  # 1 GiB, never reachable

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, _size: int = -1) -> bytes:
        return b"a" * 65536


class TestDownloadDeadline(unittest.TestCase):
    """A stalled download must abort at the overall deadline, not hang."""

    def _info(self) -> UpdateInfo:
        return UpdateInfo(
            current_version="1.0.0",
            latest_version="1.1.0",
            download_url="https://example.com/s.zip",
            changelog=[],
            min_compatible_version="1.0.0",
            update_required=False,
            is_newer=True,
        )

    def test_deadline_aborts_and_cleans_partial_file(self):
        from unittest.mock import patch

        u = Updater.__new__(Updater)
        u.current_version = "1.0.0"

        with tempfile.TemporaryDirectory() as tmp:
            with patch("urllib.request.urlopen", return_value=_InfiniteResponse()):
                # max_seconds=0 → the very first loop iteration is past deadline
                result = u.download_update(self._info(), dest_dir=Path(tmp), max_seconds=0)

            self.assertIsNone(result)
            self.assertFalse((Path(tmp) / "spectra_update.zip").exists())


class TestBackupRoot(unittest.TestCase):
    """Backups are anchored to the user config dir, not the process CWD."""

    def test_backup_root_is_absolute(self):
        self.assertTrue(Updater._backup_root().is_absolute())

    def test_backup_root_independent_of_cwd(self):
        import os

        before = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                self.assertNotEqual(Updater._backup_root(), Path(tmp) / ".spectra_backup")
        finally:
            os.chdir(before)


class TestBackupRestoreRoundTrip(unittest.TestCase):
    """Backup/restore is pure-Python (tarfile) and round-trips an install."""

    def _make_updater(self, root: Path, backups: Path) -> Updater:
        u = Updater.__new__(Updater)
        u.current_version = "9.9.9"
        u._install_root = lambda: root  # type: ignore[method-assign]
        u._backup_root = lambda: backups  # type: ignore[method-assign]
        return u

    def test_backup_and_restore_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            install_root = tmp_path / "install"
            pkg = install_root / "spectra"
            pkg.mkdir(parents=True)
            (pkg / "core").mkdir()
            (pkg / "core" / "marker.txt").write_text("original")

            backups = tmp_path / "backups"
            u = self._make_updater(install_root, backups)

            self.assertTrue(u.backup_installation())
            archive = backups / "backup_9.9.9.tar.gz"
            self.assertTrue(archive.exists())
            self.assertGreater(archive.stat().st_size, 0)

            # Mutate the installation, then restore
            (pkg / "core" / "marker.txt").write_text("changed")
            (pkg / "core" / "extra.txt").write_text("junk")

            self.assertTrue(u.restore_backup())
            self.assertEqual((pkg / "core" / "marker.txt").read_text(), "original")
            # Restore overlays the backup (same semantics as tar -x):
            # files added after the backup are left in place, not deleted.
            self.assertTrue((pkg / "core" / "extra.txt").exists())

    def test_restore_without_backups_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            u = self._make_updater(tmp_path / "install", tmp_path / "backups")
            self.assertFalse(u.restore_backup())


class TestStartupCheckWorker(unittest.TestCase):
    """_startup_check_worker notifies only when a newer release exists."""

    def _info(self, newer: bool) -> UpdateInfo:
        return UpdateInfo(
            current_version="1.0.0",
            latest_version="1.1.0" if newer else "1.0.0",
            download_url="",
            changelog=[],
            min_compatible_version="1.0.0",
            update_required=False,
            is_newer=newer,
        )

    def test_notify_called_when_newer(self):
        from unittest.mock import patch

        received = []
        with patch.object(Updater, "check_for_updates", return_value=self._info(True), create=True):
            from spectra.core.updater import _startup_check_worker

            _startup_check_worker(received.append)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].latest_version, "1.1.0")

    def test_notify_skipped_when_current(self):
        from unittest.mock import patch

        received = []
        with patch.object(Updater, "check_for_updates", return_value=self._info(False), create=True):
            from spectra.core.updater import _startup_check_worker

            _startup_check_worker(received.append)
        self.assertEqual(received, [])

    def test_worker_swallows_errors(self):
        from unittest.mock import patch

        def _boom(self):
            raise RuntimeError("network down")

        with patch.object(Updater, "check_for_updates", _boom, create=True):
            from spectra.core.updater import _startup_check_worker

            _startup_check_worker(None)  # must not raise


if __name__ == "__main__":
    unittest.main()
