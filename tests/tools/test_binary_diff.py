"""Tests for the binary diff engine/tool (spectra/tools/binary_diff.py).

The synthetic ELF/PE/Mach-O builders are reused from test_binary_format;
 ELF variants are produced by patching builder output in place (symbol
address/size, symbol name, e_machine) so every scenario stays synthetic.
"""

from __future__ import annotations

import struct
import tempfile
import unittest

from spectra.tools.binary_diff import (
    binary_diff,
    compare_sections,
    diff_binaries,
    format_diff_report,
)
from tests.tools.test_binary_format import build_elf64, build_macho64, build_pe64

# build_elf64 layout constants (see tests/tools/test_binary_format.py).
_TEXT_OFF = 0x240
_DYNSTR_OFF = 0x180
_SYMTAB_OFF = 0x1D0
_MAIN_STR_OFF = 28  # "main\x00" inside .dynstr


def _elf_main_in_text(text: bytes = b"\x48\x31\xc0\xc3", size: int = 4) -> bytes:
    """build_elf64 with the symtab `main` entry pointed into .text so the
    engine can extract real bytes for it (the stock builder parks main at
    0x1000, outside every section)."""
    buf = bytearray(build_elf64())
    entry = _SYMTAB_OFF + 24  # symtab entry index 1 = main
    struct.pack_into("<Q", buf, entry + 8, _TEXT_OFF)  # st_value → .text
    struct.pack_into("<Q", buf, entry + 16, size)  # st_size
    buf[_TEXT_OFF : _TEXT_OFF + len(text)] = text
    return bytes(buf)


def _elf_main_size(size: int) -> bytes:
    """build_elf64 with only main's st_size changed (address still outside
    every section → no bytes → size-only comparison)."""
    buf = bytearray(build_elf64())
    struct.pack_into("<Q", buf, _SYMTAB_OFF + 24 + 16, size)
    return bytes(buf)


def _elf_rename_main(new_name: bytes) -> bytes:
    """build_elf64 with `main` renamed in .dynstr (same string length)."""
    buf = bytearray(build_elf64())
    assert len(new_name) == 5  # replaces b"main\x00" byte-for-byte
    buf[_DYNSTR_OFF + _MAIN_STR_OFF : _DYNSTR_OFF + _MAIN_STR_OFF + 5] = new_name
    return bytes(buf)


def _fake_result() -> dict:
    """A hand-built engine result for formatter tests."""
    return {
        "old_info": {
            "format": "ELF", "arch": "x86_64", "bits": 64, "file_type": "executable",
            "file_size": 1000, "num_symbols": 2, "num_sections": 8,
        },
        "new_info": {
            "format": "ELF", "arch": "x86_64", "bits": 64, "file_type": "executable",
            "file_size": 1010, "num_symbols": 3, "num_sections": 8,
        },
        "format_match": True,
        "matched": [
            {"name": "auth_check", "old_addr": 0x1000, "new_addr": 0x1000,
             "old_size": 120, "new_size": 180, "similarity": 0.42, "changed": True},
            {"name": "helper", "old_addr": 0x2000, "new_addr": 0x2000,
             "old_size": 40, "new_size": 40, "similarity": 0.91, "changed": True},
            {"name": "untouched", "old_addr": 0x3000, "new_addr": 0x3000,
             "old_size": 60, "new_size": 60, "similarity": 1.0, "changed": False},
        ],
        "added": [{"name": "fresh_func", "addr": 0x5000, "size": 64}],
        "removed": [{"name": "dead_func", "addr": 0x6000, "size": 32}],
        "stripped_fallback": False,
        "section_changes": [],
        "totals": {"matched": 3, "changed": 2, "added": 1, "removed": 1},
    }


# ═══════════════════════════════ Engine ═══════════════════════════════════


class TestDiffEngine(unittest.TestCase):
    def test_self_diff_fully_matched(self):
        elf = build_elf64()
        result = diff_binaries(elf, elf)
        self.assertTrue(result["format_match"])
        self.assertFalse(result["stripped_fallback"])
        self.assertEqual(result["section_changes"], [])
        self.assertEqual(result["totals"], {"matched": 2, "changed": 0, "added": 0, "removed": 0})
        names = {m["name"] for m in result["matched"]}
        self.assertEqual(names, {"main", "__stack_chk_fail"})
        # Summarized parse info rides along.
        self.assertEqual(result["old_info"]["format"], "ELF")
        self.assertEqual(result["old_info"]["num_symbols"], 2)
        self.assertEqual(result["old_info"]["file_size"], len(elf))

    def test_changed_function_bytes(self):
        old = _elf_main_in_text(b"\x48\x31\xc0\xc3")
        new = _elf_main_in_text(b"\x48\x31\xdb\xc3")
        result = diff_binaries(old, new)
        self.assertEqual(result["totals"], {"matched": 2, "changed": 1, "added": 0, "removed": 0})
        # main is changed and ranked first; 2 of 4 bytes match → ratio 0.75.
        main = result["matched"][0]
        self.assertEqual(main["name"], "main")
        self.assertTrue(main["changed"])
        self.assertAlmostEqual(main["similarity"], 0.75)
        self.assertEqual((main["old_size"], main["new_size"]), (4, 4))
        self.assertEqual((main["old_addr"], main["new_addr"]), (_TEXT_OFF, _TEXT_OFF))
        # __stack_chk_fail has no extractable bytes → size-only, unchanged.
        other = next(m for m in result["matched"] if m["name"] == "__stack_chk_fail")
        self.assertFalse(other["changed"])
        self.assertIsNone(other["similarity"])

    def test_identical_bytes_similarity_one(self):
        old = new = _elf_main_in_text()
        result = diff_binaries(old, new)
        main = next(m for m in result["matched"] if m["name"] == "main")
        self.assertEqual(main["similarity"], 1.0)
        self.assertFalse(main["changed"])
        self.assertEqual(result["totals"]["changed"], 0)

    def test_size_only_compare_when_bytes_unavailable(self):
        result = diff_binaries(build_elf64(), _elf_main_size(50))
        main = next(m for m in result["matched"] if m["name"] == "main")
        self.assertIsNone(main["similarity"])
        self.assertTrue(main["changed"])  # 42 → 50 bytes
        self.assertEqual(result["totals"]["changed"], 1)

    def test_added_and_removed_symbols(self):
        result = diff_binaries(build_elf64(), _elf_rename_main(b"mazn\x00"))
        self.assertEqual(result["added"], [{"name": "mazn", "addr": 0x1000, "size": 42}])
        self.assertEqual(result["removed"], [{"name": "main", "addr": 0x1000, "size": 42}])
        self.assertEqual(result["totals"], {"matched": 1, "changed": 0, "added": 1, "removed": 1})
        # The survivor is the symbol present under the same name on both sides.
        self.assertEqual(result["matched"][0]["name"], "__stack_chk_fail")

    def test_format_mismatch_detected(self):
        result = diff_binaries(build_elf64(), build_pe64())
        self.assertFalse(result["format_match"])
        self.assertEqual(result["totals"], {"matched": 0, "changed": 0, "added": 0, "removed": 0})
        self.assertEqual(result["matched"], [])
        self.assertFalse(result["stripped_fallback"])

    def test_arch_mismatch_detected(self):
        aarch64 = bytearray(build_elf64())
        struct.pack_into("<H", aarch64, 18, 0xB7)  # e_machine → aarch64
        result = diff_binaries(build_elf64(), bytes(aarch64))
        self.assertFalse(result["format_match"])  # ELF vs ELF, x86_64 vs aarch64

    def test_empty_and_garbage_raise_value_error(self):
        with self.assertRaises(ValueError):
            diff_binaries(b"", b"")
        with self.assertRaises(ValueError):
            diff_binaries(b"\x00\x01\x02\x03garbage", b"definitely not a binary")

    def test_stripped_macho_falls_back_to_sections(self):
        old = build_macho64()  # builder emits no LC_SYMTAB → zero symbols
        result = diff_binaries(old, old)
        self.assertTrue(result["format_match"])
        self.assertTrue(result["stripped_fallback"])
        self.assertEqual(result["totals"]["matched"], 0)
        by_name = {c["name"]: c for c in result["section_changes"]}
        self.assertTrue(by_name["__TEXT"]["identical"])

        mutated = bytearray(old)
        mutated[0x100] ^= 0xFF  # inside __TEXT, past the load commands
        result = diff_binaries(old, bytes(mutated))
        self.assertTrue(result["stripped_fallback"])
        text = {c["name"]: c for c in result["section_changes"]}["__TEXT"]
        self.assertFalse(text["identical"])  # same size, different bytes
        self.assertEqual(text["old_size"], text["new_size"])


# ═══════════════════════ Section comparison (pure) ════════════════════════


class TestCompareSections(unittest.TestCase):
    OLD = {
        "sections": [
            {"name": ".text", "offset": 0, "size": 16, "vaddr": 0x1000, "exec": True, "write": False},
            {"name": ".data", "offset": 16, "size": 8, "vaddr": 0x2000, "exec": False, "write": True},
        ]
    }
    NEW = {
        "sections": [
            {"name": ".text", "offset": 0, "size": 32, "vaddr": 0x1000, "exec": True, "write": False},
            {"name": ".data", "offset": 32, "size": 8, "vaddr": 0x2000, "exec": False, "write": True},
            {"name": ".bss", "offset": 40, "size": 4, "vaddr": 0x3000, "exec": False, "write": True},
        ]
    }

    def test_sizes_and_presence_without_raw_data(self):
        changes = {c["name"]: c for c in compare_sections(self.OLD, self.NEW)}
        self.assertEqual(changes[".text"], {"name": ".text", "old_size": 16, "new_size": 32, "identical": False})
        # Same size, no bytes to compare → size-based fallback says identical.
        self.assertTrue(changes[".data"]["identical"])
        self.assertIsNone(changes[".bss"]["old_size"])  # new section
        self.assertFalse(changes[".bss"]["identical"])

    def test_removed_section(self):
        changes = {c["name"]: c for c in compare_sections(self.NEW, self.OLD)}
        self.assertIsNone(changes[".bss"]["new_size"])
        self.assertFalse(changes[".bss"]["identical"])

    def test_byte_identical_sections(self):
        old_data = bytes(16) + b"DATADAT!"
        new_data = bytes(32) + b"DATADAT!"
        changes = {c["name"]: c for c in compare_sections(self.OLD, self.NEW, old_data, new_data)}
        self.assertTrue(changes[".data"]["identical"])  # same bytes verified
        self.assertFalse(changes[".text"]["identical"])  # 16 vs 32 bytes

    def test_same_size_different_bytes(self):
        old_data = bytes(16) + b"DATADAT!"
        new_data = bytes(32) + b"DATADIF!"
        changes = {c["name"]: c for c in compare_sections(self.OLD, self.NEW, old_data, new_data)}
        self.assertFalse(changes[".data"]["identical"])
        self.assertEqual(changes[".data"]["old_size"], changes[".data"]["new_size"])

    def test_out_of_range_sections_fall_back_to_sizes(self):
        truncated = {
            "sections": [{"name": ".text", "offset": 100, "size": 16, "vaddr": 0x1000, "exec": True, "write": False}]
        }
        changes = compare_sections(truncated, truncated, b"short", b"also-short")
        self.assertEqual(changes, [{"name": ".text", "old_size": 16, "new_size": 16, "identical": True}])


# ═══════════════════════════ Report formatting ═══════════════════════════


class TestFormatDiffReport(unittest.TestCase):
    def test_summary_changed_added_removed(self):
        report = format_diff_report(_fake_result())
        self.assertIn("## Binary Diff Report", report)
        self.assertIn("**Summary:** 3 functions matched (2 changed), 1 added, 1 removed", report)
        self.assertIn("auth_check", report)
        self.assertIn("42.0% similar", report)
        self.assertIn("120 → 180 bytes", report)
        self.assertIn("0x1000 → 0x1000", report)
        # Changed section leads; unchanged symbol is not listed as changed.
        self.assertIn("Changed Functions (2)", report)
        self.assertNotIn("`untouched`", report)
        self.assertIn("fresh_func", report)
        self.assertIn("dead_func", report)

    def test_size_only_rows_rendered(self):
        result = _fake_result()
        result["matched"][1]["similarity"] = None  # helper compared by size only
        report = format_diff_report(result)
        self.assertIn("size-only compare", report)
        self.assertIn("helper", report)

    def test_truncated_at_50_changed(self):
        result = _fake_result()
        result["matched"] = [
            {"name": f"fn_{i}", "old_addr": 0x1000, "new_addr": 0x1000,
             "old_size": 10 + i, "new_size": 10 + i, "similarity": i / 100, "changed": True}
            for i in range(60)
        ]
        result["totals"]["changed"] = 60
        report = format_diff_report(result)
        self.assertEqual(report.count("% similar"), 50)
        self.assertIn("10 more changed functions not shown", report)

    def test_no_changes_message(self):
        result = _fake_result()
        result["matched"] = [
            {"name": "same", "old_addr": 1, "new_addr": 1, "old_size": 5,
             "new_size": 5, "similarity": 1.0, "changed": False}
        ]
        result["added"] = []
        result["removed"] = []
        result["totals"] = {"matched": 1, "changed": 0, "added": 0, "removed": 0}
        report = format_diff_report(result)
        self.assertIn("Changed Functions (0)", report)
        self.assertIn("no matched function changed", report)

    def test_stripped_report_is_honest(self):
        result = _fake_result()
        result["stripped_fallback"] = True
        result["section_changes"] = [
            {"name": ".text", "old_size": 4096, "new_size": 4352, "identical": False},
            {"name": ".data", "old_size": 256, "new_size": 256, "identical": True},
        ]
        report = format_diff_report(result)
        self.assertIn("stripped", report)
        self.assertIn("symbol", report)  # honest: named diffing needs symbols
        self.assertIn(".text", report)
        self.assertIn("4096 → 4352 bytes (differs)", report)
        self.assertIn("256 → 256 bytes (identical)", report)
        self.assertNotIn("Changed Functions", report)

    def test_format_mismatch_message(self):
        result = _fake_result()
        result["format_match"] = False
        result["new_info"] = dict(result["new_info"], format="PE", arch="x86_64")
        report = format_diff_report(result)
        self.assertIn("not the same target", report)
        self.assertIn("ELF", report)
        self.assertIn("PE", report)


# ═══════════════════════════ Tool wrapper ════════════════════════════════


class TestBinaryDiffTool(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._dir = self._tmp.name

    def _write(self, name: str, data: bytes) -> str:
        path = f"{self._dir}/{name}"
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_missing_file_is_actionable(self):
        report = binary_diff(f"{self._dir}/old.elf", f"{self._dir}/new.elf")
        self.assertIn("old binary not found", report)
        self.assertIn(f"{self._dir}/old.elf", report)
        # When only the new file is missing, the error names it.
        old = self._write("old.elf", build_elf64())
        report = binary_diff(old, f"{self._dir}/missing.elf")
        self.assertIn("new binary not found", report)
        self.assertIn("missing.elf", report)

    def test_format_mismatch_message(self):
        old = self._write("old.elf", build_elf64())
        new = self._write("new.pe", build_pe64())
        report = binary_diff(old, new)
        self.assertIn("not the same target", report)

    def test_garbage_input_is_actionable(self):
        old = self._write("old.bin", b"definitely not a binary\n")
        new = self._write("new.elf", build_elf64())
        report = binary_diff(old, new)
        self.assertIn("Error", report)
        self.assertIn("old", report)
        self.assertIn("ELF, PE or Mach-O", report)

    def test_happy_path_report(self):
        old = self._write("old.elf", build_elf64())
        new = self._write("new.elf", _elf_rename_main(b"mazn\x00"))
        report = binary_diff(old, new)
        self.assertIn("## Binary Diff Report", report)
        self.assertIn("1 functions matched", report)
        self.assertIn("1 added", report)
        self.assertIn("1 removed", report)
        self.assertIn("mazn", report)
        self.assertIn("main", report)
        self.assertIn("0x1000", report)

    def test_tool_definition_metadata(self):
        defn = binary_diff._tool_definition
        self.assertEqual(defn.name, "binary_diff")
        self.assertEqual(defn.category, "analysis")
        self.assertEqual([p.name for p in defn.parameters], ["old_path", "new_path"])
        self.assertTrue(all(p.required for p in defn.parameters))
        self.assertIn("diff", defn.description.lower())


if __name__ == "__main__":
    unittest.main()
