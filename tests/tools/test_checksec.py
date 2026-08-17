"""Tests for spectra/tools/checksec.py using the synthetic binary builders."""

from __future__ import annotations

import unittest

from spectra.tools.checksec import analyze_security, format_checksec_report
from tests.tools.test_binary_format import (
    build_elf64,
    build_fat_macho,
    build_macho64,
    build_pe64,
)


def _byname(analysis: dict) -> dict:
    return {c["name"]: c for c in analysis["checks"]}


class TestChecksecElf(unittest.TestCase):
    def test_hardened_default_builder(self):
        a = analyze_security(build_elf64())
        self.assertFalse(_byname(a)["PIE"]["ok"])  # ET_EXEC builder
        checks = _byname(a)
        self.assertTrue(checks["NX"]["ok"])
        self.assertEqual(checks["RELRO"]["status"], "full")
        self.assertTrue(checks["Stack canary"]["ok"])
        self.assertEqual(a["info"]["format"], "ELF")

    def test_pie_binary(self):
        a = analyze_security(build_elf64(e_type=3))
        self.assertTrue(_byname(a)["PIE"]["ok"])

    def test_weak_binary_all_notes(self):
        a = analyze_security(build_elf64(e_type=2, gnu_stack_flags=1, bind_now=False))
        checks = _byname(a)
        self.assertFalse(checks["NX"]["ok"])
        self.assertEqual(checks["RELRO"]["status"], "partial")
        report = format_checksec_report(a, "/tmp/fake")
        self.assertIn("Exploitation impact", report)
        self.assertIn("executable stack", report)
        self.assertIn("GOT overwrite", report)


class TestChecksecPe(unittest.TestCase):
    def test_flags(self):
        a = analyze_security(build_pe64())
        checks = _byname(a)
        self.assertTrue(checks["ASLR (DYNAMIC_BASE)"]["ok"])
        self.assertTrue(checks["DEP (NX_COMPAT)"]["ok"])
        self.assertFalse(checks["CFG (GUARD_CF)"]["ok"])
        self.assertTrue(checks["Stack cookie (/GS)"]["ok"])
        self.assertFalse(checks["Authenticode"]["ok"])

    def test_unguarded(self):
        a = analyze_security(build_pe64(dll_chars=0))
        checks = _byname(a)
        self.assertFalse(checks["ASLR (DYNAMIC_BASE)"]["ok"])
        self.assertFalse(checks["DEP (NX_COMPAT)"]["ok"])


class TestChecksecMacho(unittest.TestCase):
    def test_flags(self):
        a = analyze_security(build_macho64())
        checks = _byname(a)
        self.assertTrue(checks["PIE"]["ok"])
        self.assertTrue(checks["NX"]["ok"])
        self.assertTrue(checks["Code signature"]["ok"])

    def test_fat_reports_all_slices(self):
        a = analyze_security(build_fat_macho())
        self.assertEqual(a["info"]["format"], "Fat Mach-O")
        self.assertTrue(a["fat_slices"])
        report = format_checksec_report(a)
        self.assertIn("Fat slice", report)


class TestReportFormat(unittest.TestCase):
    def test_markdown_tables(self):
        report = format_checksec_report(analyze_security(build_elf64()), "/bin/ls")
        self.assertIn("## Checksec — /bin/ls", report)
        self.assertIn("| Mitigation | Status | Note |", report)
        self.assertIn("✅", report)
        self.assertIn("❌", report)


if __name__ == "__main__":
    unittest.main()
