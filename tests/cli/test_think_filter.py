"""Tests for the CLI ``<think>`` reasoning filter (pure port).

The CLI hides ``<think>...</think>`` spans from streamed responses by
default (Claude-CLI style), captures them for later display, and exposes
them via /thinking (and the Ctrl+O binding). These tests target the
stream-filter state machine in ``ThinkFilter`` — ported verbatim from the
legacy shell UI — including tags split across chunk boundaries.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.cli.think_filter import ThinkFilter


class TestThinkFilter(unittest.TestCase):
    def setUp(self):
        self.thinking_seen: list[str] = []
        self.ui = ThinkFilter(on_thinking=self.thinking_seen.append)

    def _stream(self, *chunks: str) -> str:
        """Feed chunks through the filter; return total visible text."""
        visible = ""
        for c in chunks:
            visible += self.ui.feed(c)
        return visible

    def test_single_chunk_block_hidden(self):
        out = self._stream("<think>secret reasoning</think>Hello!")
        self.assertEqual(out, "Hello!")
        self.assertEqual(self.ui.thinking_buffer, "secret reasoning")

    def test_tag_split_across_chunks(self):
        out = self._stream("<thi", "nk>reason", "ing</th", "ink>answer")
        self.assertEqual(out, "answer")
        self.assertEqual(self.ui.thinking_buffer, "reasoning")

    def test_multiple_blocks(self):
        out = self._stream("<think>a</think>one<think>b</think>two")
        self.assertEqual(out, "onetwo")
        self.assertEqual(self.ui.thinking_buffer, "ab")

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
        self.ui.finish()
        self.assertFalse(self.ui.in_think_block)
        self.assertEqual(self.ui.last_thinking, "truncated reasoning...")

    def test_finish_flushes_visible_hold(self):
        # Answer ends with '<' — held as a potential tag, but it is visible
        # answer text and must be returned by finish(), not swallowed.
        out = self._stream("answer ends with <")
        self.assertEqual(out, "answer ends with ")  # only the '<' is held
        held = self.ui.finish()
        self.assertEqual(held, "<")
        self.assertEqual(self.ui.last_thinking, "")
        self.assertFalse(self.ui.in_think_block)

    def test_newline_after_open_tag_stripped(self):
        out = self._stream("<think>\nthe reasoning</think>visible")
        self.assertEqual(out, "visible")
        self.assertEqual(self.ui.thinking_buffer, "the reasoning")

    def test_toggle_returns_new_state(self):
        self.assertFalse(self.ui.show_thinking)
        self.assertTrue(self.ui.toggle())
        self.assertTrue(self.ui.show_thinking)
        self.assertFalse(self.ui.toggle())

    def test_show_thinking_streams_live_to_sink(self):
        self.ui.show_thinking = True
        out = self._stream("<think>visible reasoning</think>answer")
        self.assertEqual(out, "answer")
        self.assertIn("visible reasoning", "".join(self.thinking_seen))

    def test_hidden_thinking_not_emitted(self):
        self._stream("<think>hidden reasoning</think>answer")
        self.assertEqual("".join(self.thinking_seen), "")

    def test_reset_turn_clears_capture(self):
        self._stream("<think>old reasoning</think>done")
        self.ui.finish()
        self.ui.reset_turn()
        self.assertEqual(self.ui.thinking_buffer, "")
        self.assertEqual(self.ui.last_thinking, "old reasoning")


if __name__ == "__main__":
    unittest.main()
