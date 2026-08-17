"""Tests for spectra/tools/entropy.py."""

from __future__ import annotations

import random
import unittest

from spectra.tools.entropy import (
    HIGH_ENTROPY,
    analyze_entropy,
    detect_packer,
    format_entropy_report,
    section_report,
    shannon_entropy,
)
from tests.tools.test_binary_format import build_pe64


class TestShannonEntropy(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(shannon_entropy(b""), 0.0)
        self.assertEqual(shannon_entropy(b"\x00" * 100), 0.0)
        self.assertAlmostEqual(shannon_entropy(bytes(range(256))), 8.0, places=6)
        text = b"the quick brown fox jumps over the lazy dog " * 10
        self.assertLess(shannon_entropy(text), 5.0)

    def test_section_report(self):
        r = section_report(".rodata", b"A" * 1000)
        self.assertEqual(r["entropy"], 0.0)
        self.assertFalse(r["high"])
        r2 = section_report(".enc", random.Random(42).randbytes(4096))
        self.assertGreater(r2["entropy"], HIGH_ENTROPY)
        self.assertTrue(r2["high"])


class TestPackerDetection(unittest.TestCase):
    def test_upx_section_name(self):
        info = {"sections": [{"name": "UPX1", "offset": 0, "size": 10}]}
        self.assertIn("UPX", detect_packer(info, b"\x00" * 16))

    def test_upx_magic(self):
        info = {"sections": []}
        self.assertIn("UPX", detect_packer(info, b"junkjunkUPX!junk"))

    def test_clean_binary(self):
        info = {"sections": [{"name": ".text", "offset": 0, "size": 10}]}
        self.assertEqual(detect_packer(info, b"\x90" * 16), [])


class TestAnalyzeEntropy(unittest.TestCase):
    def test_pe_low_entropy_text(self):
        a = analyze_entropy(build_pe64())  # .text is all 0xCC
        self.assertEqual(a["verdict"], "normal")
        text = next(s for s in a["sections"] if s["name"] == ".text")
        self.assertLess(text["entropy"], 1.0)
        self.assertFalse(text["high"])

    def test_pe_with_encrypted_text(self):
        blob = bytearray(build_pe64())
        blob[0x400 : 0x600] = random.Random(7).randbytes(0x200)  # .text raw
        a = analyze_entropy(bytes(blob))
        self.assertEqual(a["verdict"], "likely packed/encrypted code")
        text = next(s for s in a["sections"] if s["name"] == ".text")
        self.assertTrue(text["high"])

    def test_overlay_reported(self):
        blob = build_pe64() + random.Random(3).randbytes(0x1000)
        a = analyze_entropy(blob)
        self.assertGreaterEqual(a["overlay"]["size"], 0x1000 + 8)
        report = format_entropy_report(a)
        self.assertIn("Overlay", report)
        self.assertIn("inspect overlay", report)


class TestReport(unittest.TestCase):
    def test_markdown(self):
        a = analyze_entropy(build_pe64())
        r = format_entropy_report(a, "/tmp/x.bin")
        self.assertIn("## Entropy analysis — /tmp/x.bin", r)
        self.assertIn("**Verdict:** normal", r)
        self.assertIn("| Section | Size | Entropy | Flags |", r)


if __name__ == "__main__":
    unittest.main()
