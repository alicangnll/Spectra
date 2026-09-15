"""Tests for the CLI ``<think>`` reasoning filter.

The CLI must hide ``<think>...</think>`` spans from streamed responses by
default (Claude-CLI style), capture them for later display, and expose them
via /thinking (and the Ctrl+O binding). These tests target the
:class:`~spectra.cli.think_filter.ThinkFilter` state machine, including
tags split across chunk boundaries, plus the command registry entries for
the /thinking toggle.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.cli.commands import CommandKind, parse_command
from spectra.cli.think_filter import ThinkFilter


class TestThinkFilter(unittest.TestCase):
    def setUp(self):
        self.filter = ThinkFilter()

    def _stream(self, *chunks: str) -> str:
        """Feed chunks through the filter; return total visible text."""
        visible = ""
        for c in chunks:
            visible += self.filter.feed(c)
        return visible

    def test_single_chunk_block_hidden(self):
        out = self._stream("<think>secret reasoning</think>Hello!")
        self.assertEqual(out, "Hello!")
        self.assertEqual(self.filter.thinking_buffer, "secret reasoning")

    def test_tag_split_across_chunks(self):
        out = self._stream("<thi", "nk>reason", "ing</th", "ink>answer")
        self.assertEqual(out, "answer")
        self.assertEqual(self.filter.thinking_buffer, "reasoning")

    def test_multiple_blocks(self):
        out = self._stream("<think>a</think>one<think>b</think>two")
        self.assertEqual(out, "onetwo")
        self.assertEqual(self.filter.thinking_buffer, "ab")

    def test_no_thinking_passthrough_exact(self):
        text = "plain **answer** with < b and `code` intact"
        out = self._stream(text)
        self.assertEqual(out, text)

    def test_literal_angle_bracket_not_swallowed(self):
        # A '<' that cannot complete the tag must remain visible
        out = self._stream("a < b", " < c")
        self.assertEqual(out, "a < b < c")

    def test_finish_closes_unclosed_block(self):
        self._stream("<think>truncated reasoning...")
        self.filter.finish()
        self.assertFalse(self.filter.in_think_block)
        self.assertEqual(self.filter.last_thinking, "truncated reasoning...")

    def test_finish_flushes_visible_hold(self):
        # Answer ends with '<' — held as a potential tag, but it is visible
        # answer text and must be flushed, not swallowed.
        out = self._stream("answer ends with <")
        self.assertEqual(out, "answer ends with ")  # only the '<' is held
        held = self.filter.finish()
        self.assertEqual(held, "<")
        self.assertEqual(self.filter.last_thinking, "")
        self.assertFalse(self.filter.in_think_block)

    def test_newline_after_open_tag_stripped(self):
        out = self._stream("<think>\nthe reasoning</think>visible")
        self.assertEqual(out, "visible")
        self.assertEqual(self.filter.thinking_buffer, "the reasoning")

    def test_thinking_never_reaches_visible_buffer(self):
        # The mapper-level guarantee this filter exists for: reasoning text
        # must never leak into the visible answer text.
        out = self._stream("<think>hidden</think>visible text")
        self.filter.finish()
        self.assertEqual(out, "visible text")
        self.assertIn("hidden", self.filter.last_thinking)

    def test_show_thinking_streams_live_via_callback(self):
        seen: list[str] = []
        self.filter = ThinkFilter(on_thinking=seen.append, show_thinking=True)
        out = self._stream("<think>visible reasoning</think>answer")
        self.assertEqual(out, "answer")
        self.assertIn("visible reasoning", "".join(seen))

    def test_hidden_thinking_does_not_call_callback(self):
        seen: list[str] = []
        self.filter = ThinkFilter(on_thinking=seen.append, show_thinking=False)
        self._stream("<think>captured but not shown</think>answer")
        self.assertEqual(seen, [])
        self.assertEqual(self.filter.thinking_buffer, "captured but not shown")


class TestThinkingCommandParsing(unittest.TestCase):
    def test_thinking_command(self):
        self.assertIs(parse_command("/thinking").kind, CommandKind.THINKING)

    def test_think_alias(self):
        self.assertIs(parse_command("/think").kind, CommandKind.THINKING)

    def test_toggle_still_works(self):
        self.assertIs(parse_command("/toggle").kind, CommandKind.TOGGLE)


if __name__ == "__main__":
    unittest.main()
