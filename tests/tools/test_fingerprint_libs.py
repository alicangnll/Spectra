"""Tests for statically-linked library fingerprinting (spectra/tools/fingerprint_libs.py)."""

from __future__ import annotations

import unittest
from unittest import mock

from spectra.tools.fingerprint_libs import (
    analyze_libraries,
    fingerprint_libraries_from_strings,
    fingerprint_libs,
    format_lib_report,
)
from tests.tools.test_binary_format import build_elf64


def _lib(result: dict) -> dict:
    """library -> entry map for convenient assertions."""
    return {e["library"]: e for e in result["libraries"]}


class TestFingerprintFromStrings(unittest.TestCase):
    def test_openssl_with_fips_suffix(self):
        r = fingerprint_libraries_from_strings(
            ["OpenSSL 1.0.2k-fips  26 Jan 2017"]
        )
        self.assertEqual(_lib(r)["OpenSSL"]["version"], "1.0.2k-fips")
        self.assertEqual(r["total"], 1)

    def test_openssl_plain_patch_letter(self):
        r = fingerprint_libraries_from_strings(["OpenSSL 1.1.1w  3 Sep 2023"])
        self.assertEqual(_lib(r)["OpenSSL"]["version"], "1.1.1w")

    def test_zlib_banner(self):
        r = fingerprint_libraries_from_strings(
            ["deflate 1.2.11 Copyright 1995-2017 Jean-loup Gailly, Mark Adler"]
        )
        self.assertEqual(_lib(r)["zlib"]["version"], "1.2.11")
        self.assertIn("deflate", _lib(r)["zlib"]["note"])

    def test_libcurl_user_agent(self):
        r = fingerprint_libraries_from_strings(["libcurl/7.81.0"])
        self.assertEqual(_lib(r)["libcurl"]["version"], "7.81.0")

    def test_common_trio(self):
        r = fingerprint_libraries_from_strings(
            ["SQLite 3.45.1", "Lua 5.4.4  Copyright (C) 1994-2023 Lua.org", "Qt 5.15.2"]
        )
        libs = _lib(r)
        self.assertEqual(libs["SQLite"]["version"], "3.45.1")
        self.assertEqual(libs["Lua"]["version"], "5.4.4")
        self.assertEqual(libs["Qt"]["version"], "5.15.2")

    def test_boost_build_path_marker(self):
        r = fingerprint_libraries_from_strings(
            ["/usr/src/boost_1_81_0/stage/lib/libboost_system.a"]
        )
        self.assertEqual(_lib(r)["Boost"]["version"], "1_81_0")

    def test_go_runtime(self):
        r = fingerprint_libraries_from_strings(["go1.21.5"])
        self.assertEqual(_lib(r)["Go"]["version"], "1.21.5")

    def test_go_no_false_positive_inside_words(self):
        r = fingerprint_libraries_from_strings(["Chicago1.2", "django1.4", "cargo1.x"])
        self.assertEqual(r["total"], 0)

    def test_boringssl_and_mbedtls(self):
        r = fingerprint_libraries_from_strings(["BoringSSL 20230101", "mbed TLS 2.28.1"])
        libs = _lib(r)
        self.assertEqual(libs["BoringSSL"]["version"], "20230101")
        self.assertEqual(libs["mbedTLS"]["version"], "2.28.1")

    def test_same_version_dedupes_with_count(self):
        r = fingerprint_libraries_from_strings(
            ["OpenSSL 1.0.2k", "OpenSSL 1.0.2k-fips  26 Jan 2017"]
        )
        entries = [e for e in r["libraries"] if e["library"] == "OpenSSL"]
        self.assertEqual(len(entries), 2)  # distinct versions stay distinct
        by_ver = {e["version"]: e for e in entries}
        self.assertEqual(by_ver["1.0.2k"]["count"], 1)
        self.assertEqual(by_ver["1.0.2k-fips"]["count"], 1)

    def test_repeat_occurrences_counted_once(self):
        r = fingerprint_libraries_from_strings(["libcurl/7.81.0", "libcurl/7.81.0"])
        self.assertEqual(r["total"], 1)
        self.assertEqual(_lib(r)["libcurl"]["count"], 2)

    def test_no_libraries(self):
        r = fingerprint_libraries_from_strings(["hello world", "main.c", "unknown func"])
        self.assertEqual(r["libraries"], [])
        self.assertEqual(r["total"], 0)

    def test_presence_only_without_version(self):
        r = fingerprint_libraries_from_strings(["boringssl_string_table_marker"])
        self.assertEqual(r["libraries"], [])
        self.assertIn("BoringSSL", r["presence_only"])

    def test_no_presence_when_versioned(self):
        r = fingerprint_libraries_from_strings(["wolfSSL 4.8.1"])
        self.assertIn("wolfSSL", _lib(r))
        self.assertNotIn("wolfSSL", r["presence_only"])

    def test_evidence_truncated_and_pipe_escaped(self):
        long_banner = "OpenSSL 1.1.1w " + "A" * 200 + "|pipe|"
        r = fingerprint_libraries_from_strings([long_banner])
        entry = _lib(r)["OpenSSL"]
        self.assertTrue(all(len(e) <= 80 for e in entry["evidence"]))
        report = format_lib_report(analyze_libraries(long_banner.encode()))
        self.assertNotIn("A" * 100, report)


class TestAnalyzeBytes(unittest.TestCase):
    def test_realistic_blob_unknown_format(self):
        blob = b"\x00".join(
            [b"OpenSSL 1.1.1w  3 Sep 2023", b"libcurl/7.81.0", b"\xde\xad\xbe\xef"]
        )
        r = analyze_libraries(blob)
        self.assertIsNone(r["binary"])  # not a recognized container format
        self.assertGreater(r["strings_scanned"], 0)
        libs = _lib(r)
        self.assertEqual(libs["OpenSSL"]["version"], "1.1.1w")
        self.assertEqual(libs["libcurl"]["version"], "7.81.0")

    def test_elf_with_appended_banners(self):
        data = build_elf64() + b"OpenSSL 1.1.1w\x00libcurl/7.81.0\x00"
        r = analyze_libraries(data)
        self.assertEqual(r["binary"]["format"], "ELF")
        self.assertEqual(r["binary"]["arch"], "x86_64")
        self.assertEqual(_lib(r)["libcurl"]["version"], "7.81.0")


class TestReport(unittest.TestCase):
    def test_report_table_and_next_steps(self):
        r = analyze_libraries(b"OpenSSL 1.1.1w\x00deflate 1.2.11\x00")
        report = format_lib_report(r, "/tmp/target.elf")
        self.assertIn("## Library fingerprint — /tmp/target.elf", report)
        self.assertIn("| Library | Version | Evidence |", report)
        self.assertIn("| OpenSSL | 1.1.1w |", report)
        self.assertIn("| zlib", report)  # note appended after name
        self.assertIn("### Next steps", report)

    def test_report_empty_mentions_imports_and_presence(self):
        r = analyze_libraries(b"boringssl_marker\x00plain text only")
        report = format_lib_report(r)
        self.assertIn("## Library fingerprint — current binary", report)
        self.assertIn("No embedded library version banners found", report)
        self.assertIn("BoringSSL", report)


class TestTool(unittest.TestCase):
    def test_tool_definition_attached(self):
        self.assertTrue(hasattr(fingerprint_libs, "_tool_definition"))
        d = fingerprint_libs._tool_definition
        self.assertEqual(d.name, "fingerprint_libs")
        self.assertEqual(d.category, "analysis")
        self.assertIn("path", {p.name for p in d.parameters})

    def test_tool_no_path_no_host(self):
        # Patched: earlier suites may stub spectra.core.host (documented
        # mock-pollution gotcha), which would change _current_input_file().
        with mock.patch("spectra.tools.fingerprint_libs._current_input_file", return_value=""):
            out = fingerprint_libs("")
        self.assertTrue(out.startswith("Error: no path"))

    def test_tool_unreadable_path(self):
        out = fingerprint_libs("/nonexistent/path/binary.elf")
        self.assertTrue(out.startswith("Error: cannot read"))


if __name__ == "__main__":
    unittest.main()
