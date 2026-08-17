"""Tests for the file metadata tool (spectra/tools/file_meta.py).

Binary fixtures come from the synthetic builders in
tests/tools/test_binary_format.py — no real files, so the suite runs
identically on every platform. pefile is not installed in CI: its absence
is asserted to surface as an "Optional" note, never an error.
"""

from __future__ import annotations

import hashlib
import os
import struct
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.tools.file_meta import (
    check_pefile_available,
    compute_hashes,
    file_meta,
    find_go_buildinfo,
    find_pdb_path,
    format_meta_report,
)
from tests.tools.test_binary_format import build_elf64, build_macho64, build_pe64


class TestComputeHashes(unittest.TestCase):
    def test_matches_hashlib_on_same_bytes(self):
        data = build_pe64()
        hashes = compute_hashes(data)
        self.assertEqual(hashes["md5"], hashlib.md5(data).hexdigest())
        self.assertEqual(hashes["sha1"], hashlib.sha1(data).hexdigest())
        self.assertEqual(hashes["sha256"], hashlib.sha256(data).hexdigest())

    def test_digest_lengths(self):
        hashes = compute_hashes(b"abc")
        self.assertEqual(len(hashes["md5"]), 32)
        self.assertEqual(len(hashes["sha1"]), 40)
        self.assertEqual(len(hashes["sha256"]), 64)


class TestFindPdbPath(unittest.TestCase):
    def _rsds(self, path: bytes, guid: bytes = b"\x00" * 16) -> bytes:
        return b"RSDS" + guid + struct.pack("<I", 2) + path + b"\x00"

    def test_synthetic_record(self):
        data = b"junk-before" + self._rsds(b"/build/path.pdb") + b"trailing"
        self.assertEqual(find_pdb_path(data), "/build/path.pdb")

    def test_pe_builder_has_no_pdb(self):
        self.assertEqual(find_pdb_path(build_pe64()), "")

    def test_prefers_real_pdb_over_stray_magic(self):
        stray = b"RSDS" + b"\x00" * 16 + b"\x01\x00\x00\x00" + b"not-a-real-path"
        real = self._rsds(b"D:\\build\\app.pdb")
        self.assertEqual(find_pdb_path(stray + real), "D:\\build\\app.pdb")

    def test_no_magic_returns_empty(self):
        self.assertEqual(find_pdb_path(b"\x00\x01\x02 nothing here"), "")


class TestFindGoBuildinfo(unittest.TestCase):
    def test_version_string(self):
        evidence = find_go_buildinfo(b"\x00\x01prefix go1.21.0 suffix")
        self.assertIn("go1.21.0", evidence)

    def test_build_id_marker(self):
        evidence = find_go_buildinfo(b"\xff Go build ID: \"abc/def/ghi\"\xff")
        self.assertIn("Go build ID", evidence)

    def test_combined_evidence(self):
        evidence = find_go_buildinfo(b"Go build ID: \"x/go1.22.1/y\"")
        self.assertIn("Go build ID", evidence)
        self.assertIn("go1.22.1", evidence)

    def test_non_go_payload(self):
        self.assertEqual(find_go_buildinfo(build_elf64()), "")
        self.assertEqual(find_go_buildinfo(b"plain data"), "")


class TestFormatMetaReport(unittest.TestCase):
    def test_import_cap_per_dll(self):
        info = {
            "format": "PE",
            "file_type": "executable",
            "arch": "x86_64",
            "bits": 64,
            "endian": "little",
            "file_size": 10,
            "sections": [],
            "symbols": [],
            "exports": [],
            "imports": {"BIG.DLL": [f"fn{i}" for i in range(250)]},
        }
        report = format_meta_report(info, {"path": "/tmp/big.bin"})
        self.assertIn("**BIG.DLL** (250):", report)
        self.assertIn("`fn0`", report)
        self.assertIn("+50 more", report)
        self.assertNotIn("fn249", report)

    def test_minimal_info_and_extras_do_not_crash(self):
        report = format_meta_report({"format": "Mach-O", "file_size": 3}, {})
        self.assertIn("File Metadata Report", report)
        self.assertIn("nothing notable", report)


class _TempFileTest(unittest.TestCase):
    """Base: writes bytes to a temp file and hands the path to the tool."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.path = os.path.join(self._tmpdir.name, "sample.bin")
        with open(self.path, "wb") as fh:
            fh.write(self.payload)

    @property
    def payload(self) -> bytes:  # overridden per subclass
        raise NotImplementedError


class TestFileMetaPe(_TempFileTest):
    @property
    def payload(self) -> bytes:
        return build_pe64()  # timestamp 0x5F000000, overlay b"OVERLAY!"

    def test_overview_hashes_and_type(self):
        report = file_meta(path=self.path)
        self.assertIn("File Metadata Report", report)
        self.assertIn("**Format:** PE — executable", report)
        self.assertIn("x86_64", report)
        self.assertIn("64-bit", report)
        self.assertIn("**Subsystem:** windows-cui", report)
        self.assertIn(hashlib.sha256(self.payload).hexdigest(), report)
        self.assertIn(hashlib.md5(self.payload).hexdigest(), report)

    def test_imports_and_exports(self):
        report = file_meta(path=self.path)
        self.assertIn("KERNEL32.DLL", report)
        self.assertIn("CreateFileW", report)
        self.assertIn("DllMain", report)

    def test_compile_timestamp_formatted(self):
        report = file_meta(path=self.path)
        expected = datetime.fromtimestamp(0x5F000000, UTC).strftime("%Y-%m-%d %H:%M:%S")
        self.assertIn(expected, report)
        self.assertIn("UTC", report)

    def test_overlay_reported(self):
        report = file_meta(path=self.path)
        self.assertIn("Overlay", report)
        self.assertIn(f"{len('OVERLAY!')} bytes", report)
        self.assertIn("`0x800`", report)

    def test_sections_table(self):
        report = file_meta(path=self.path)
        self.assertIn("| .text |", report)
        self.assertIn("| .idata |", report)

    def test_pdb_absent(self):
        report = file_meta(path=self.path)
        self.assertNotIn("PDB path", report)
        self.assertNotIn("path.pdb", report)

    def test_pefile_absence_is_optional_note_not_error(self):
        report = file_meta(path=self.path)
        if check_pefile_available():
            self.assertNotIn("pip install pefile", report)
        else:
            self.assertIn("### Optional", report)
            self.assertIn("pefile not installed — imphash unavailable (pip install pefile)", report)
        self.assertNotIn("Error", report)


class TestFileMetaElf(_TempFileTest):
    @property
    def payload(self) -> bytes:
        return build_elf64()

    def test_interpreter_needed_and_dynamic(self):
        report = file_meta(path=self.path)
        self.assertIn("/lib64/ld-linux-x86-64.so.2", report)
        self.assertIn("libc.so.6", report)
        self.assertIn("**Static:** no", report)

    def test_mitigations_line(self):
        report = file_meta(path=self.path)
        self.assertIn("RELRO: full", report)


class TestFileMetaMacho(_TempFileTest):
    @property
    def payload(self) -> bytes:
        return build_macho64()

    def test_signed_and_dylibs(self):
        report = file_meta(path=self.path)
        self.assertIn("Mach-O", report)
        self.assertIn("/usr/lib/libSystem.B.dylib", report)
        self.assertIn("Signed: yes", report)


class TestFileMetaErrors(unittest.TestCase):
    def test_empty_path_without_host_is_actionable(self):
        with mock.patch("spectra.tools.file_meta._current_input_file", return_value=""):
            report = file_meta(path="")
        self.assertIn("No file specified", report)
        self.assertIn("file_meta(path=", report)  # shows how to call it

    def test_missing_file_reported(self):
        report = file_meta(path="/nonexistent/dir/sample.bin")
        self.assertIn("file not found", report)
        self.assertIn("/nonexistent/dir/sample.bin", report)

    def test_unparseable_file_reported(self):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as fh:
            fh.write(b"definitely not an elf/pe/macho payload")
            tmp = fh.name
        try:
            report = file_meta(path=tmp)
        finally:
            os.unlink(tmp)
        self.assertIn("Error parsing", report)
        self.assertIn("ELF, PE and Mach-O", report)


if __name__ == "__main__":
    unittest.main()
