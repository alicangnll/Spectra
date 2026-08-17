"""Tests for spectra/tools/str_decode.py.

All tests are synthetic: the classic decoders are pure functions, the
stack-string engine runs over hand-written disassembly lines (both IDA and
Binary Ninja text styles), and the host collectors are exercised through
fake objects. No disassembler is required.
"""

from __future__ import annotations

import base64
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.tools import str_decode
from spectra.tools.str_decode import (
    decode_value,
    find_stack_strings_in_lines,
    format_decode_report,
    format_stack_strings_report,
)

# --- Part 1: classic decoders ------------------------------------------------


class TestDecodeValue(unittest.TestCase):
    def test_hex(self):
        result = decode_value("48656c6c6f", "hex")
        assert len(result["candidates"]) == 1
        cand = result["candidates"][0]
        assert cand["scheme"] == "hex"
        assert cand["result"] == "Hello"
        assert cand["score"] == 1.0
        assert cand["printable"] is True

    def test_hex_auto_ranks_decode_first(self):
        result = decode_value("48656c6c6f")
        assert result["value"] == "48656c6c6f"
        assert result["candidates"][0]["result"] == "Hello"
        assert any(c["scheme"] == "hex" and c["result"] == "Hello" for c in result["candidates"])

    def test_hex_with_0x_prefix_and_spaces(self):
        assert decode_value("0x48 65 6c 6c 6f", "hex")["candidates"][0]["result"] == "Hello"

    def test_base64(self):
        encoded = base64.b64encode(b"Hello World").decode()
        result = decode_value(encoded, "base64")
        assert result["candidates"][0]["result"] == "Hello World"
        # And auto ranks the real payload first
        assert decode_value(encoded)["candidates"][0]["result"] == "Hello World"

    def test_base64url(self):
        encoded = base64.urlsafe_b64encode(b"Hi~There").decode()
        result = decode_value(encoded, "base64url")
        assert result["candidates"][0]["result"] == "Hi~There"

    def test_base32(self):
        encoded = base64.b32encode(b"Hello").decode()
        assert encoded == "JBSWY3DP"
        result = decode_value(encoded, "base32")
        assert result["candidates"][0]["result"] == "Hello"

    def test_rot13(self):
        result = decode_value("Uryyb", "rot13")
        assert result["candidates"][0]["result"] == "Hello"
        # Round trip
        assert decode_value("Hello", "rot13")["candidates"][0]["result"] == "Uryyb"

    def test_rot47(self):
        # rot47("Hello") == "w6==@" (hand-computed expectation, not impl echo)
        result = decode_value("w6==@", "rot47")
        assert result["candidates"][0]["result"] == "Hello"

    def test_reverse(self):
        result = decode_value("olleH", "reverse")
        assert result["candidates"][0]["result"] == "Hello"

    def test_decimal_space_separated(self):
        result = decode_value("72 101 108 108 111", "decimal")
        assert result["candidates"][0]["result"] == "Hello"

    def test_decimal_comma_separated(self):
        result = decode_value("72,101,108,108,111", "decimal")
        assert result["candidates"][0]["result"] == "Hello"

    def test_decimal_rejects_out_of_range(self):
        assert decode_value("72 999", "decimal")["candidates"] == []
        assert decode_value("72, abc", "decimal")["candidates"] == []

    def test_xor_brute_on_hex_encoded_ciphertext(self):
        ciphertext = bytes(b ^ 0x2A for b in b"Hello").hex()
        result = decode_value(ciphertext, "xor_brute")
        candidates = result["candidates"]
        assert 1 <= len(candidates) <= 3
        hello = [c for c in candidates if c["result"] == "Hello"]
        assert hello, f"Hello missing from {candidates}"
        assert hello[0]["key"] == 0x2A
        assert hello[0]["score"] >= 0.9
        # distinct results only
        assert len({c["result"] for c in candidates}) == len(candidates)

    def test_xor_brute_on_literal_string_bytes(self):
        # "Rjwia" is not valid hex, so the literal bytes get brute forced.
        ciphertext = bytes(b ^ 0x05 for b in b"World").decode()
        assert ciphertext == "Rjwia"
        result = decode_value(ciphertext, "xor_brute")
        hello = [c for c in result["candidates"] if c["result"] == "World"]
        assert hello and hello[0]["key"] == 0x05

    def test_xor_brute_caps_distinct_candidates(self):
        # "61616161" is b"aaaa": many keys yield a printable repeated letter,
        # but only the top 3 distinct candidates may be kept.
        result = decode_value("61616161", "xor_brute")
        assert 1 <= len(result["candidates"]) <= 3
        results = [c["result"] for c in result["candidates"]]
        assert len(set(results)) == len(results)

    def test_garbage_input_never_crashes(self):
        for scheme in ("auto", "hex", "base32", "base64", "base64url", "rot13", "rot47", "reverse", "xor_brute", "decimal"):
            result = decode_value("!!!@@@###", scheme)
            assert isinstance(result, dict)
            assert isinstance(result["candidates"], list)

    def test_malformed_input_for_scheme_skips_it(self):
        assert decode_value("zzzz", "hex")["candidates"] == []
        assert decode_value("zzzz", "base32")["candidates"] == []
        assert decode_value("a", "base64")["candidates"] == []

    def test_empty_and_whitespace_values(self):
        assert decode_value("")["candidates"] == []
        assert decode_value("   \t\n")["candidates"] == []

    def test_unknown_scheme_returns_empty(self):
        result = decode_value("48656c6c6f", "rot26")
        assert result["candidates"] == []
        assert result["value"] == "48656c6c6f"

    def test_candidate_contract_keys(self):
        result = decode_value("48656c6c6f")
        assert result["candidates"]
        for cand in result["candidates"]:
            assert set(cand) >= {"scheme", "result", "score", "printable"}
            assert isinstance(cand["result"], str)
            assert 0.0 <= cand["score"] <= 1.0
            assert isinstance(cand["printable"], bool)

    def test_non_string_value_is_coerced(self):
        result = decode_value(b"48656c6c6f")  # type: ignore[arg-type]
        assert any(c["result"] == "Hello" for c in result["candidates"])

    def test_decode_report_markdown(self):
        report = format_decode_report(decode_value("48656c6c6f"))
        assert report.startswith("## String Decode Report")
        assert "Hello" in report
        assert "hex" in report

    def test_decode_report_no_candidates(self):
        report = format_decode_report({"value": "???", "candidates": []})
        assert "No decodable candidates" in report

    def test_decode_string_tool_returns_markdown(self):
        out = str_decode.decode_string("48656c6c6f")
        assert isinstance(out, str)
        assert "Hello" in out
        # explicit scheme argument passes through the tool wrapper
        out2 = str_decode.decode_string("Uryyb", "rot13")
        assert "Hello" in out2


# --- Part 2: stack-string engine ---------------------------------------------


class TestFindStackStringsInLines(unittest.TestCase):
    def test_ida_style_hello(self):
        lines = [
            (0x1000, "mov     [rbp+var_10], 6C6C6548h"),
            (0x1005, "mov     [rbp+var_C], 6Fh"),
        ]
        results = find_stack_strings_in_lines(lines)
        assert len(results) == 1
        entry = results[0]
        assert entry["string"] == "Hello"
        assert entry["address"] == 0x1000
        assert entry["end_address"] == 0x1005
        assert entry["instructions"] == [0x1000, 0x1005]
        assert entry["func_hint"] is None

    def test_binja_style_longer_string_with_one_gap(self):
        lines = [
            (0x2000, "movabs rax, 0x57202c6f6c6c6548"),  # "Hello, W"
            (0x2007, "mov qword ptr [rsp+0x10 {var_10}], rax"),  # gap (register move)
            (0x200E, "movabs rax, 0x21646c726f"),  # "orld!"
        ]
        results = find_stack_strings_in_lines(lines)
        assert len(results) == 1
        entry = results[0]
        assert entry["string"] == "Hello, World!"
        assert entry["address"] == 0x2000
        assert entry["end_address"] == 0x200E
        assert entry["instructions"] == [0x2000, 0x200E]

    def test_one_gap_tolerance_boundary(self):
        # Exactly one non-immediate instruction between immediates is bridged.
        lines = [
            (0x100, "push 6C6C6548h"),
            (0x102, "lea rdi, [rsp+18h] ; setup"),
            (0x104, "push 6F57206Fh"),  # "o Wo"
        ]
        results = find_stack_strings_in_lines(lines)
        assert [r["string"] for r in results] == ["Hello Wo"]

    def test_two_gaps_break_the_run(self):
        lines = [
            (0x4000, "push 6C6C6548h"),  # "Hell"
            (0x4002, "nop"),
            (0x4003, "xor eax, eax"),
            (0x4004, "push 6F57206Fh"),  # "o Wo"
        ]
        results = find_stack_strings_in_lines(lines)
        assert [r["string"] for r in results] == ["Hell", "o Wo"]
        assert results[0]["instructions"] == [0x4000]
        assert results[1]["instructions"] == [0x4004]

    def test_non_printable_immediate_breaks_run(self):
        lines = [
            (0x3000, "mov     [rbp+var_8], 6C6C6548h"),  # "Hell"
            (0x3005, "mov     eax, 0Ah"),  # non-printable immediate -> break
            (0x300A, "mov     [rbp+var_4], 6Fh"),  # "o" (below min length)
        ]
        results = find_stack_strings_in_lines(lines)
        assert [r["string"] for r in results] == ["Hell"]

    def test_below_minimum_length_dropped(self):
        lines = [
            (0x5000, "mov [rbp+var_14], 65h"),  # "e"
            (0x5005, "mov [rbp+var_10], 6Ch"),  # "l"
        ]
        assert find_stack_strings_in_lines(lines) == []

    def test_single_8byte_immediate_qualifies(self):
        lines = [(0x6000, "push 0x57202c6f6c6c6548")]  # "Hello, W"
        results = find_stack_strings_in_lines(lines)
        assert len(results) == 1
        assert results[0]["string"] == "Hello, W"
        assert results[0]["address"] == results[0]["end_address"] == 0x6000

    def test_quoted_char_immediates(self):
        lines = [
            (0x7000, "mov [rbp+var_8], 'ab'"),
            (0x7005, "mov [rbp+var_4], 'cd'"),
        ]
        results = find_stack_strings_in_lines(lines)
        assert [r["string"] for r in results] == ["abcd"]

    def test_uppercase_h_suffix(self):
        lines = [(0x7100, "push 6C6C6548H")]
        assert [r["string"] for r in find_stack_strings_in_lines(lines)] == ["Hell"]

    def test_wider_than_8_bytes_rejected(self):
        # 0x4141414141414141 is exactly 8 bytes -> accepted
        lines = [(0x7200, "movabs rax, 0x4141414141414141")]
        assert [r["string"] for r in find_stack_strings_in_lines(lines)] == ["AAAAAAAA"]
        # 9 bytes -> non-char immediate, breaks the (empty) run
        lines = [(0x7210, "movabs rax, 0x104141414141414141")]
        assert find_stack_strings_in_lines(lines) == []

    def test_plain_decimal_immediates_are_gaps(self):
        lines = [
            (0x8000, "mov [rbp+var_8], 6C6C6548h"),
            (0x8005, "mov eax, 116"),  # decimal immediate: skipped, counts as gap
            (0x800A, "mov [rbp+var_4], 6Fh"),
        ]
        results = find_stack_strings_in_lines(lines)
        assert [r["string"] for r in results] == ["Hello"]

    def test_result_structure_fields(self):
        results = find_stack_strings_in_lines([(0x9000, "push 74657374h")])  # "test"
        assert len(results) == 1
        expected = {"func_hint", "address", "end_address", "string", "instructions"}
        assert expected <= set(results[0])

    def test_empty_and_malformed_input(self):
        assert find_stack_strings_in_lines([]) == []
        assert find_stack_strings_in_lines(None) == []
        assert find_stack_strings_in_lines([("0x1000", "push 74657374h")]) != []  # str addr coerced
        assert find_stack_strings_in_lines([(None, "push 74657374h")]) == []  # bad addr skipped


# --- Report formatting --------------------------------------------------------


class TestFormatStackStringsReport(unittest.TestCase):
    def _sample(self):
        return {
            "host": "ida",
            "total": 2,
            "functions": [
                {
                    "address": 0x401000,
                    "name": "sub_401000",
                    "strings": [
                        {
                            "func_hint": None,
                            "address": 0x401010,
                            "end_address": 0x40101A,
                            "string": "Hello",
                            "instructions": [0x401010, 0x401012, 0x40101A],
                        },
                        {
                            "func_hint": None,
                            "address": 0x401020,
                            "end_address": 0x401028,
                            "string": "Mozilla/5.0",
                            "instructions": [0x401020, 0x401028],
                        },
                    ],
                }
            ],
        }

    def test_report_contents(self):
        report = format_stack_strings_report(self._sample())
        assert report.startswith("## Stack String Recovery Report")
        assert "sub_401000" in report
        assert "Hello" in report
        assert "Mozilla/5.0" in report
        assert "2 stack string(s)" in report
        assert "1 function(s)" in report
        assert "0x401010" in report

    def test_report_empty(self):
        report = format_stack_strings_report({"functions": [], "total": 0})
        assert "No stack strings" in report

    def test_report_truncates_long_lists(self):
        entry = {
            "func_hint": None,
            "address": 0x1000,
            "end_address": 0x1008,
            "string": "abcdefgh",
            "instructions": [0x1000, 0x1008],
        }
        result = {
            "total": 12,
            "functions": [{"address": 0x1000, "name": "big", "strings": [entry] * 12}],
        }
        report = format_stack_strings_report(result)
        assert "more string(s)" in report


# --- Binary Ninja collector (fake objects, no host API) -----------------------


class _FakeBinjaFunction:
    def __init__(self, lines, addrs, name="sub_1000", start=0x1000):
        self.name = name
        self.start = start
        self._lines = list(lines)
        self._addrs = list(addrs)

    def get_disassembly(self):
        return "\n".join(self._lines)

    @property
    def instructions(self):
        return [(b"\x90", addr) for addr in self._addrs]


class TestBinjaCollector(unittest.TestCase):
    def test_collect_lines_pairs_addresses(self):
        func = _FakeBinjaFunction(
            [
                "movabs rax, 0x6C6C6548",
                "mov qword ptr [rbp-0x8 {var_8}], rax",
                "mov byte ptr [rbp-0x4 {var_4}], 0x6F",
            ],
            [0x1000, 0x1007, 0x100E],
            name="build_hello",
        )
        lines = str_decode._collect_lines_binja(func)
        assert lines == [
            (0x1000, "movabs rax, 0x6C6C6548"),
            (0x1007, "mov qword ptr [rbp-0x8 {var_8}], rax"),
            (0x100E, "mov byte ptr [rbp-0x4 {var_4}], 0x6F"),
        ]
        found = find_stack_strings_in_lines(lines)
        assert [f["string"] for f in found] == ["Hello"]

    def test_line_address_mismatch_skips_function(self):
        func = _FakeBinjaFunction(["nop", "nop", "nop"], [0x1000, 0x1001])  # 3 lines, 2 addrs
        assert str_decode._collect_lines_binja(func) == []

    def test_get_disassembly_failure_is_guarded(self):
        class _ExplodingDisasm:
            def get_disassembly(self):
                raise RuntimeError("boom")

        assert str_decode._collect_lines_binja(_ExplodingDisasm()) == []

    def test_instructions_failure_is_guarded(self):
        class _ExplodingInstructions:
            def get_disassembly(self):
                return "nop"

            @property
            def instructions(self):
                raise RuntimeError("API drift")

        assert str_decode._collect_lines_binja(_ExplodingInstructions()) == []

    def test_find_stack_strings_binja_pipeline(self):
        func = _FakeBinjaFunction(
            [
                "movabs rax, 0x57202c6f6c6c6548",
                "mov qword ptr [rsp+0x10 {var_10}], rax",
                "movabs rax, 0x21646c726f",
            ],
            [0x1000, 0x1007, 0x100E],
            name="build_str",
        )
        other = _FakeBinjaFunction(["ret"], [0x2000], name="empty", start=0x2000)
        bv = types.SimpleNamespace(functions=[func, other])

        with (
            mock.patch.object(str_decode, "BINJA_AVAILABLE", True),
            mock.patch.object(str_decode, "get_binary_ninja_view", return_value=bv),
        ):
            result = str_decode._find_stack_strings_binja()

        assert result["total"] == 1
        assert len(result["functions"]) == 1
        entry = result["functions"][0]
        assert entry["name"] == "build_str"
        assert entry["address"] == 0x1000
        assert entry["strings"][0]["string"] == "Hello, World!"

        report = format_stack_strings_report(result)
        assert "Hello, World!" in report
        assert "build_str" in report


# --- No-host tool path --------------------------------------------------------


class TestNoHost(unittest.TestCase):
    def test_find_stack_strings_without_host_mentions_unavailable(self):
        with (
            mock.patch.object(str_decode, "IDA_AVAILABLE", False),
            mock.patch.object(str_decode, "BINJA_AVAILABLE", False),
        ):
            out = str_decode.find_stack_strings()
        assert isinstance(out, str)
        lowered = out.lower()
        assert "host" in lowered
        assert "unavailable" in lowered

    def test_collect_stack_strings_without_host(self):
        with (
            mock.patch.object(str_decode, "IDA_AVAILABLE", False),
            mock.patch.object(str_decode, "BINJA_AVAILABLE", False),
        ):
            result = str_decode.collect_stack_strings()
        assert result == {"host": None, "functions": [], "total": 0}

    def test_binja_without_view_returns_empty(self):
        with (
            mock.patch.object(str_decode, "BINJA_AVAILABLE", True),
            mock.patch.object(str_decode, "get_binary_ninja_view", return_value=None),
        ):
            result = str_decode._find_stack_strings_binja()
        assert result == {"functions": [], "total": 0}


if __name__ == "__main__":
    unittest.main()
