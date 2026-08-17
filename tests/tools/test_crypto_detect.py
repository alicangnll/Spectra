"""Tests for crypto constant detection (spectra/tools/crypto_detect.py).

The analyzer is a pure function over raw bytes, so every signature in the
catalog is exercised by planting the constant in a synthetic buffer — no
disassembler, no host API, no network. End-to-end coverage runs the @tool
entrypoint against a temp file.
"""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.core.errors import ToolError
from spectra.tools.crypto_detect import analyze_crypto, detect_crypto, format_crypto_report

AES_SBOX_HEAD = bytes.fromhex("637c777bf26b6fc53001672bfed7ab76")
AES_INV_SBOX_HEAD = bytes.fromhex("52096ad53036a538bf40a39e81f3d7fb")
DES_IP_HEAD = bytes.fromhex("3a322a221a120a02")  # 58,50,42,34,26,18,10,2
DES_FP_HEAD = bytes.fromhex("2808301038184020")  # 40,8,48,16,56,24,64,32
CHACHA_SIGMA = b"expand 32-byte k"
BASE64_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _names(results: dict) -> set[str]:
    return {entry["name"] for entry in results["detected"]}


def _algo(results: dict, name: str) -> dict:
    matches = [a for a in results["algorithms"] if a["name"] == name]
    assert matches, f"algorithm {name} not detected (got {_names(results)})"
    return matches[0]


class TestHashConstantDetection(unittest.TestCase):
    def test_md5_k_table_word(self):
        buf = b"A" * 100 + struct.pack("<I", 0xD76AA478) + b"B" * 32
        results = analyze_crypto(buf)
        entry = next(e for e in results["detected"] if e["name"] == "MD5")
        assert entry["file_offset"] == 100
        assert entry["confidence"] == "medium"
        assert entry["category"] == "hash"

    def test_md5_sha1_shared_init_word(self):
        buf = b"\x00" * 16 + struct.pack("<I", 0x67452301)
        results = analyze_crypto(buf)
        assert "MD5/SHA-1 init" in _names(results)

    def test_sha1_single_constant_is_medium(self):
        buf = struct.pack("<I", 0x5A827999)
        results = analyze_crypto(buf)
        assert _algo(results, "SHA-1")["confidence"] == "medium"

    def test_sha1_two_constants_upgrade_to_high(self):
        buf = struct.pack("<I", 0x5A827999) + b"\x00" * 8 + struct.pack(">I", 0x6ED9EBA1)
        results = analyze_crypto(buf)
        algo = _algo(results, "SHA-1")
        assert algo["confidence"] == "high"
        assert len(algo["constants_matched"]) == 2

    def test_sha256_single_word_is_medium(self):
        buf = struct.pack("<I", 0x428A2F98)
        results = analyze_crypto(buf)
        assert _algo(results, "SHA-256")["confidence"] == "medium"

    def test_sha256_k_and_iv_upgrade_to_high(self):
        buf = struct.pack("<I", 0x428A2F98) + b"\xcc" * 4 + struct.pack("<I", 0x6A09E667)
        results = analyze_crypto(buf)
        assert _algo(results, "SHA-256")["confidence"] == "high"

    def test_sha256_big_endian_variant_found(self):
        buf = b"Z" * 0x40 + struct.pack(">I", 0x6A09E667)
        results = analyze_crypto(buf)
        entry = next(e for e in results["detected"] if e["name"] == "SHA-256")
        assert entry["file_offset"] == 0x40
        assert "BE" in entry["constant"]

    def test_sha512_64bit_word_is_high(self):
        buf = struct.pack("<Q", 0x428A2F98D728AE22)
        results = analyze_crypto(buf)
        assert _algo(results, "SHA-512")["confidence"] == "high"
        # The documented overlap: the quadword's high word also triggers the
        # (medium) SHA-256 K[0] entry — labeled honestly, never silently.
        assert "SHA-256" in _names(results)

    def test_crc32_and_crc32c(self):
        buf = struct.pack("<I", 0xEDB88320) + b"\x00" * 4 + struct.pack("<I", 0x82F63B78)
        results = analyze_crypto(buf)
        assert {"CRC32", "CRC32C"} <= _names(results)
        assert _algo(results, "CRC32")["confidence"] == "medium"

    def test_crc16_ccitt(self):
        buf = b"Q" * 10 + struct.pack(">I", 0x1021)
        results = analyze_crypto(buf)
        assert "CRC-16-CCITT" in _names(results)


class TestCipherConstantDetection(unittest.TestCase):
    def test_aes_sbox_is_high(self):
        buf = b"M" * 0x30 + AES_SBOX_HEAD + b"N" * 16
        results = analyze_crypto(buf)
        entry = next(e for e in results["detected"] if e["name"] == "AES")
        assert entry["file_offset"] == 0x30
        assert entry["confidence"] == "high"
        assert entry["category"] == "cipher"

    def test_aes_inverse_sbox_is_high(self):
        results = analyze_crypto(AES_INV_SBOX_HEAD)
        assert _algo(results, "AES")["confidence"] == "high"

    def test_des_permutation_tables(self):
        results = analyze_crypto(DES_IP_HEAD)
        assert _algo(results, "DES")["confidence"] == "medium"
        both = analyze_crypto(DES_IP_HEAD + b"\x00" * 8 + DES_FP_HEAD)
        assert _algo(both, "DES")["confidence"] == "high"

    def test_tea_delta_alone_is_medium(self):
        buf = b"T" * 12 + struct.pack("<I", 0x9E3779B9)
        results = analyze_crypto(buf)
        entry = next(e for e in results["detected"] if e["name"] == "TEA/XTEA")
        assert entry["file_offset"] == 12
        assert entry["confidence"] == "medium"

    def test_tea_delta_and_sum_upgrade_to_high(self):
        buf = struct.pack("<I", 0x9E3779B9) + b"E" * 4 + struct.pack("<I", 0xC6EF3720)
        results = analyze_crypto(buf)
        assert _algo(results, "TEA/XTEA")["confidence"] == "high"

    def test_tea_swapped_delta_does_not_double_report(self):
        # The byte-swapped delta encodes to the same bytes as the original's
        # mirrored encoding — one offset must be listed exactly once.
        buf = struct.pack(">I", 0x9E3779B9)
        results = analyze_crypto(buf)
        algo = _algo(results, "TEA/XTEA")
        assert len(algo["occurrences"]) == 1

    def test_chacha_sigma_is_high(self):
        buf = b"C" * 0x10 + CHACHA_SIGMA
        results = analyze_crypto(buf)
        entry = next(e for e in results["detected"] if e["name"] == "ChaCha/Salsa")
        assert entry["file_offset"] == 0x10
        assert entry["confidence"] == "high"

    def test_blowfish_parray_word(self):
        results = analyze_crypto(struct.pack("<I", 0x243F6A88))
        algo = _algo(results, "Blowfish")
        assert algo["confidence"] == "medium"
        assert "ambiguous" in algo["hint"].lower()


class TestEncodingDetection(unittest.TestCase):
    def test_base64_standard_alphabet(self):
        buf = b"b64" + BASE64_ALPHABET + b"\x00"
        results = analyze_crypto(buf)
        entry = next(e for e in results["detected"] if e["name"] == "Base64")
        assert entry["file_offset"] == 3
        assert entry["confidence"] == "high"
        assert entry["category"] == "encoding"

    def test_base64_url_safe_alphabet(self):
        alphabet = BASE64_ALPHABET[:-2] + b"-_"
        results = analyze_crypto(alphabet)
        assert "Base64 (URL-safe)" in _names(results)
        assert "Base64" not in _names(results)  # standard entry is distinct

    def test_base64_utf16le_alphabet(self):
        results = analyze_crypto(BASE64_ALPHABET.decode().encode("utf-16-le"))
        assert "Base64 (UTF-16LE)" in _names(results)


class TestNoiseControl(unittest.TestCase):
    def test_no_false_positive_on_plain_ascii(self):
        filler = b"plain ascii text with no crypto constants at all, just words. " * 32
        results = analyze_crypto(filler)
        assert results["detected"] == []
        assert results["algorithms"] == []
        assert "No cryptographic constants" in results["summary"]

    def test_occurrences_capped_at_eight(self):
        buf = struct.pack("<I", 0x9E3779B9) * 12
        results = analyze_crypto(buf)
        algo = _algo(results, "TEA/XTEA")
        assert len(algo["occurrences"]) == 8
        assert len([e for e in results["detected"] if e["name"] == "TEA/XTEA"]) == 8

    def test_both_endians_counted_as_separate_occurrences(self):
        buf = struct.pack("<I", 0x6A09E667) + b"-" * 6 + struct.pack(">I", 0x6A09E667)
        results = analyze_crypto(buf)
        algo = _algo(results, "SHA-256")
        assert len(algo["occurrences"]) == 2
        # One constant seen in two byte orders is still one distinct pattern.
        assert algo["confidence"] == "medium"


class TestAddressMapping(unittest.TestCase):
    SECTIONS = [
        # Broad segment first, nested section second — the smaller must win.
        {"name": "__TEXT", "offset": 0, "size": 0x1000, "vaddr": 0x400000},
        {"name": ".crypto", "offset": 0, "size": 0x200, "vaddr": 0x400000},
        {"name": "__DATA", "offset": 0x1000, "size": 0x800, "vaddr": 0x401000},
    ]

    def test_offset_mapped_to_vaddr_and_section(self):
        buf = b"\x90" * 0x20 + struct.pack("<I", 0xD76AA478)
        results = analyze_crypto(buf, sections=self.SECTIONS)
        entry = next(e for e in results["detected"] if e["name"] == "MD5")
        assert entry["vaddr"] == 0x400020
        assert entry["section"] == ".crypto"  # smallest containing section

    def test_unmapped_offset_has_no_vaddr(self):
        buf = struct.pack("<I", 0xD76AA478)
        results = analyze_crypto(buf, sections=self.SECTIONS[:0])
        entry = next(e for e in results["detected"] if e["name"] == "MD5")
        assert "vaddr" not in entry
        assert "section" not in entry


class TestReportFormatting(unittest.TestCase):
    def test_report_groups_by_algorithm_with_hints(self):
        buf = (
            b"A" * 0x10
            + AES_SBOX_HEAD
            + struct.pack("<I", 0x9E3779B9)
            + CHACHA_SIGMA
        )
        report = format_crypto_report(analyze_crypto(buf))
        assert "## Crypto Detection Report" in report
        assert "### AES" in report
        assert "### ChaCha/Salsa" in report
        assert "Hint:" in report
        assert "0x10" in report  # hex offsets listed
        assert "aesenc" in report  # AES family hint

    def test_empty_report(self):
        report = format_crypto_report(analyze_crypto(b"\x00" * 64))
        assert "## Crypto Detection Report" in report
        assert "No embedded crypto constants matched" in report


class TestToolEntrypoint(unittest.TestCase):
    def test_detect_crypto_on_file(self):
        blob = b"MZ" + b"\x00" * 0x40 + AES_SBOX_HEAD + CHACHA_SIGMA
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "sample.bin")
            with open(target, "wb") as fh:
                fh.write(blob)
            report = detect_crypto(path=target)
        assert "## Crypto Detection Report" in report
        assert "AES" in report
        assert "ChaCha/Salsa" in report
        assert f"`{target}`" in report  # source echoed in the report

    def test_raw_blob_still_analyzed_without_sections(self):
        # Not a known binary format — offsets only, no crash.
        blob = b"XXXX" + struct.pack("<I", 0x5A827999) + b"Y" * 8
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "shellcode.bin")
            with open(target, "wb") as fh:
                fh.write(blob)
            report = detect_crypto(path=target)
        assert "SHA-1" in report

    def test_missing_file_raises_tool_error(self):
        with self.assertRaises(ToolError):
            detect_crypto(path="/nonexistent/crypto/sample.bin")


if __name__ == "__main__":
    unittest.main()
