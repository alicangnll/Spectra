"""Tests for YARA rule generation and scanning (spectra/tools/yara_tools.py).

Rule building and match-report formatting are pure functions and always
run. The scan tests need the optional yara-python package: they either
assert the actionable install message (when it is missing) or run a real
compile+scan against a temp file (when it is installed). No network.
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.tools.yara_tools import (
    check_yara_available,
    format_match_report,
    generate_yara_rule,
    yara_generate,
    yara_scan,
)

YARA_INSTALLED = check_yara_available()


class TestRuleNameSanitization(unittest.TestCase):
    def test_bad_name_sanitized(self):
        rule = generate_yara_rule(name="my rule!", strings=["abc"])
        self.assertIn("rule my_rule {", rule)
        self.assertNotIn("my rule!", rule)

    def test_default_name_untouched(self):
        rule = generate_yara_rule(strings=["abc"])
        self.assertIn("rule spectra_rule {", rule)

    def test_empty_name_falls_back(self):
        rule = generate_yara_rule(name="!!!", strings=["abc"])
        self.assertIn("rule spectra_rule {", rule)

    def test_leading_digit_prefixed(self):
        rule = generate_yara_rule(name="123abc", strings=["abc"])
        self.assertIn("rule _123abc {", rule)


class TestStringEscaping(unittest.TestCase):
    def _rule(self, s: str) -> str:
        return generate_yara_rule(strings=[s])

    def test_double_quotes_escaped(self):
        rule = self._rule('she said "hi"')
        self.assertIn('$s1 = "she said \\"hi\\""', rule)

    def test_backslash_escaped(self):
        rule = self._rule("C:\\temp\\x")
        self.assertIn("C:\\\\temp\\\\x", rule)

    def test_newline_escaped(self):
        rule = self._rule("line1\nline2")
        self.assertIn("line1\\nline2", rule)

    def test_tab_escaped(self):
        rule = self._rule("a\tb")
        self.assertIn("a\\tb", rule)

    def test_non_printable_as_hex_escape(self):
        rule = self._rule("ctl\x00\x01\x7f")
        self.assertIn("ctl\\x00\\x01\\x7f", rule)

    def test_plain_string_verbatim(self):
        rule = self._rule("CreateFileW")
        self.assertIn('$s1 = "CreateFileW"', rule)


class TestHexPatterns(unittest.TestCase):
    def test_hex_pattern_emitted_with_braces(self):
        rule = generate_yara_rule(strings=["abc"], hex_patterns=["AA BB ?? CC"])
        self.assertIn("$h1 = { AA BB ?? CC }", rule)

    def test_compact_hex_respaced(self):
        rule = generate_yara_rule(hex_patterns=["deadbeef"])
        self.assertIn("$h1 = { DE AD BE EF }", rule)

    def test_jump_wildcard_kept(self):
        rule = generate_yara_rule(hex_patterns=["AA * BB"])
        self.assertIn("$h1 = { AA * BB }", rule)

    def test_garbage_rejected(self):
        for bad in ("XYZ!", "GG", "not hex", "0x4D", "AA BB ZZ"):
            with self.subTest(pattern=bad), self.assertRaises(ValueError):
                generate_yara_rule(hex_patterns=[bad])

    def test_odd_nibble_count_rejected(self):
        with self.assertRaises(ValueError):
            generate_yara_rule(hex_patterns=["ABC"])


class TestRuleStructure(unittest.TestCase):
    def test_rule_block_meta_and_strings(self):
        rule = generate_yara_rule(strings=["abc", "def"])
        lines = rule.splitlines()
        self.assertEqual(lines[0], "rule spectra_rule {")
        self.assertEqual(lines[-1], "}")
        self.assertIn("    meta:", rule)
        self.assertIn('        generated = "spectra"', rule)
        self.assertIn('        description = "', rule)
        self.assertIn("    strings:", rule)
        self.assertIn('$s1 = "abc"', rule)
        self.assertIn('$s2 = "def"', rule)

    def test_default_condition_any_of_them(self):
        rule = generate_yara_rule(strings=["a", "b"])
        self.assertIn("        any of them", rule)

    def test_default_condition_two_of_them_beyond_two_strings(self):
        rule = generate_yara_rule(strings=["a", "b", "c"])
        self.assertIn("        2 of them", rule)
        self.assertNotIn("any of them", rule)

    def test_mixed_patterns_count_toward_threshold(self):
        rule = generate_yara_rule(strings=["a", "b"], hex_patterns=["CC DD"])
        self.assertIn("        2 of them", rule)

    def test_custom_condition_appended_safely(self):
        rule = generate_yara_rule(strings=["a"], condition="filesize < 100KB")
        self.assertIn("        filesize < 100KB and any of them", rule)

    def test_condition_referencing_them_stands_alone(self):
        rule = generate_yara_rule(strings=["a", "b"], condition="all of them")
        self.assertIn("        all of them", rule)
        self.assertNotIn("all of them and", rule)

    def test_empty_rule_rejected(self):
        with self.assertRaises(ValueError):
            generate_yara_rule()
        with self.assertRaises(ValueError):
            generate_yara_rule(strings=[""], hex_patterns=["  "])

    def test_blank_strings_skipped(self):
        rule = generate_yara_rule(strings=["", "keep"])
        self.assertEqual(rule.count("$s"), 1)
        self.assertIn('$s1 = "keep"', rule)


class TestFormatMatchReport(unittest.TestCase):
    def test_plain_dict_matches(self):
        matches = [
            {
                "rule": "demo_rule",
                "tags": ["malware", "test"],
                "strings": [(0x10, "$s1", b"ABCDEF")],
            }
        ]
        report = format_match_report(matches, "/tmp/sample.bin")
        self.assertIn("YARA Scan Report", report)
        self.assertIn("`/tmp/sample.bin`", report)
        self.assertIn("1 rule(s) matched", report)
        self.assertIn("### demo_rule (malware, test)", report)
        self.assertIn("`0x00000010`", report)
        self.assertIn("`$s1`", report)
        self.assertIn("41 42 43", report)  # hex preview of b"ABCDEF"

    def test_dict_without_strings_still_rendered(self):
        report = format_match_report([{"rule": "bare", "tags": [], "strings": []}], "p")
        self.assertIn("### bare", report)
        self.assertIn("no string details", report)

    def test_no_matches(self):
        report = format_match_report([], "p")
        self.assertIn("no matches", report)

    def test_yara4_style_string_match_objects(self):
        instance = types.SimpleNamespace(offset=4, matched_data=b"XY")
        match = types.SimpleNamespace(
            rule="r4", tags=["t"], strings=[types.SimpleNamespace(identifier="$a", instances=[instance])]
        )
        report = format_match_report([match], "p")
        self.assertIn("### r4 (t)", report)
        self.assertIn("`0x00000004`", report)
        self.assertIn("`$a`", report)
        self.assertIn("58 59", report)


class TestYaraGenerateTool(unittest.TestCase):
    def test_returns_markdown_rule(self):
        result = yara_generate(strings=["abc"], hex_patterns=["AA BB"])
        self.assertIn("```yara", result)
        self.assertIn("rule spectra_rule {", result)
        self.assertIn('$s1 = "abc"', result)
        self.assertIn("$h1 = { AA BB }", result)

    def test_bad_input_returns_error_not_exception(self):
        result = yara_generate(hex_patterns=["ZZ"])
        self.assertTrue(result.startswith("Error"), result)

    def test_tool_definition(self):
        self.assertEqual(yara_generate._tool_definition.name, "yara_generate")
        self.assertEqual(yara_generate._tool_definition.category, "analysis")


class TestYaraScanTool(unittest.TestCase):
    @unittest.skipIf(YARA_INSTALLED, "yara-python installed")
    def test_actionable_install_message_when_missing(self):
        result = yara_scan(path="/tmp/does-not-matter", rule_text="rule r { condition: true }")
        self.assertIn("yara-python is not installed", result)
        self.assertIn("pip install yara-python", result)
        self.assertNotIn("Traceback", result)

    @unittest.skipUnless(YARA_INSTALLED, "yara-python not installed")
    def test_real_compile_and_scan(self):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as fh:
            fh.write(b"leading padding SPECTRA-MARKER-123 trailing bytes")
            tmp = fh.name
        try:
            rule = generate_yara_rule(name="spectra_scan_test", strings=["SPECTRA-MARKER-123"])
            report = yara_scan(path=tmp, rule_text=rule)
            self.assertIn("spectra_scan_test", report)
            self.assertIn("1 rule(s) matched", report)
            self.assertNotIn("no matches", report)
        finally:
            os.unlink(tmp)

    @unittest.skipUnless(YARA_INSTALLED, "yara-python not installed")
    def test_real_scan_no_match(self):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as fh:
            fh.write(b"nothing interesting here")
            tmp = fh.name
        try:
            rule = generate_yara_rule(name="absent_rule", strings=["SPECTRA-MARKER-123"])
            report = yara_scan(path=tmp, rule_text=rule)
            self.assertIn("no matches", report)
        finally:
            os.unlink(tmp)

    @unittest.skipUnless(YARA_INSTALLED, "yara-python not installed")
    def test_compile_error_labeled_not_traceback(self):
        result = yara_scan(path="/tmp/any", rule_text="rule broken { condition: }")
        self.assertIn("compile error", result.lower())
        self.assertNotIn("Traceback", result)

    @unittest.skipUnless(YARA_INSTALLED, "yara-python not installed")
    def test_missing_file_reported(self):
        result = yara_scan(path="/nonexistent/path/file.bin", rule_text="rule r { condition: true }")
        self.assertIn("file not found", result)

    @unittest.skipUnless(YARA_INSTALLED, "yara-python not installed")
    def test_empty_rule_reported(self):
        result = yara_scan(path="/tmp/any", rule_text="   ")
        self.assertTrue(result.startswith("Error"), result)


if __name__ == "__main__":
    unittest.main()
