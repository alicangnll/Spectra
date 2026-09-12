"""Tests for CLI <think> reasoning display filter.

The CLI must hide ``<think>...</think>`` spans from streamed responses by
default (Claude-CLI style), capture them for later display, and expose them
via /thinking (and the Ctrl+O binding). These tests target the stream filter
state machine in ShellUI, including tags split across chunk boundaries.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Other test modules stub these in sys.modules; make sure this test gets
# the real ones (same pattern as tests/agent/test_session_controller.py).
for _mod in ("spectra.agent.turn", "spectra.cli.shell_ui"):
    sys.modules.pop(_mod, None)

from spectra.agent.turn import TurnEvent, TurnEventType
from spectra.cli.command_parser import CommandType, parse_command
from spectra.cli.shell_ui import ShellUI


def _drain(gen) -> None:
    for _ in gen:
        pass


class TestThinkFilter(unittest.TestCase):
    def setUp(self):
        self.ui = ShellUI(use_colors=False, use_markdown=False)

    def _stream(self, *chunks: str) -> str:
        """Feed chunks through the filter; return total visible text."""
        visible = ""
        for c in chunks:
            visible += self.ui._filter_think(c)
        return visible

    def test_single_chunk_block_hidden(self):
        out = self._stream("<think>secret reasoning</think>Hello!")
        self.assertEqual(out, "Hello!")
        self.assertEqual(self.ui._thinking_buffer, "secret reasoning")

    def test_tag_split_across_chunks(self):
        out = self._stream("<thi", "nk>reason", "ing</th", "ink>answer")
        self.assertEqual(out, "answer")
        self.assertEqual(self.ui._thinking_buffer, "reasoning")

    def test_multiple_blocks(self):
        out = self._stream("<think>a</think>one<think>b</think>two")
        self.assertEqual(out, "onetwo")
        self.assertEqual(self.ui._thinking_buffer, "ab")

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
        self.ui._finish_think()
        self.assertFalse(self.ui._think_mode)
        self.assertEqual(self.ui._last_thinking, "truncated reasoning...")

    def test_finish_flushes_visible_hold(self):
        # Answer ends with '<' — held as a potential tag, but it is visible
        # answer text and must be flushed, not swallowed.
        out = self._stream("answer ends with <")
        self.assertEqual(out, "answer ends with ")  # only the '<' is held
        self.ui._finish_think()
        self.assertEqual(self.ui._last_thinking, "")
        self.assertFalse(self.ui._think_mode)

    def test_newline_after_open_tag_stripped(self):
        out = self._stream("<think>\nthe reasoning</think>visible")
        self.assertEqual(out, "visible")
        self.assertEqual(self.ui._thinking_buffer, "the reasoning")

    def test_handle_event_never_buffers_thinking(self):
        _drain(self.ui._handle_event(TurnEvent(TurnEventType.TURN_START)))
        with redirect_stdout(io.StringIO()):
            _drain(self.ui._handle_event(TurnEvent(TurnEventType.TEXT_DELTA, text="<think>hidden</think>visible text")))
            _drain(self.ui._handle_event(TurnEvent(TurnEventType.TEXT_DONE)))
        self.assertEqual(self.ui._current_text_buffer, "")
        self.assertIn("hidden", self.ui._last_thinking)

    def test_toggle_shows_last_thinking(self):
        self._stream("<think>deep thoughts</think>answer")
        self.ui._finish_think()
        captured = io.StringIO()
        with redirect_stdout(captured):
            self.assertTrue(self.ui.toggle_thinking())
        self.assertIn("deep thoughts", captured.getvalue())
        self.assertFalse(self.ui.toggle_thinking())

    def test_show_thinking_streams_live(self):
        self.ui.show_thinking = True
        captured = io.StringIO()
        with redirect_stdout(captured):
            out = self._stream("<think>visible reasoning</think>answer")
        self.assertEqual(out, "answer")
        self.assertIn("visible reasoning", captured.getvalue())


class TestThinkingCommandParsing(unittest.TestCase):
    def test_thinking_command(self):
        self.assertEqual(parse_command("/thinking").type, CommandType.THINKING)

    def test_think_alias(self):
        self.assertEqual(parse_command("/think").type, CommandType.THINKING)

    def test_toggle_still_works(self):
        self.assertEqual(parse_command("/toggle").type, CommandType.TOGGLE)


if __name__ == "__main__":
    unittest.main()
