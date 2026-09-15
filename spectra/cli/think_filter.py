"""Pure streaming filter for ``<think>...</think>`` reasoning spans.

Ported from the legacy shell UI's ``_filter_think``/``_finish_think`` state
machine (spectra/cli/shell_ui.py). The CLI hides model reasoning by default
(Claude-CLI style), captures it for later inspection, and streams it live
only when the user opts in (Ctrl+O / ``/thinking``).

The filter is host-agnostic: visible text is returned from :meth:`feed`,
thinking fragments are delivered through the ``on_thinking`` callback so the
TUI can route them to a collapsible widget instead of stdout.
"""

from __future__ import annotations

from typing import Callable

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"


class ThinkFilter:
    """Strip ``<think>...</think>`` spans from streaming text.

    Thinking content is captured into ``thinking_buffer`` regardless of the
    display mode; only non-thinking text is returned for display. Tags split
    across chunk boundaries are held back until they resolve.
    """

    def __init__(self, on_thinking: Callable[[str], None] | None = None, show_thinking: bool = False):
        self._think_hold = ""
        self._think_mode = False
        self._thinking_buffer = ""
        self._last_thinking = ""
        self.show_thinking = show_thinking
        self._on_thinking = on_thinking or (lambda _text: None)

    @property
    def in_think_block(self) -> bool:
        """True while inside an unterminated ``<think>`` span."""
        return self._think_mode

    @property
    def thinking_buffer(self) -> str:
        """All thinking content captured during the current turn."""
        return self._thinking_buffer

    @property
    def last_thinking(self) -> str:
        """Thinking content of the most recently finished turn."""
        return self._last_thinking

    def _emit_thinking(self, text: str, end_of_block: bool = False) -> None:
        """Deliver thinking content to the sink when display is enabled."""
        if self.show_thinking and text:
            self._on_thinking(text)
        if end_of_block and self.show_thinking:
            self._on_thinking("\n")

    def feed(self, text: str) -> str:
        """Feed one streaming chunk; return the visible (non-thinking) text."""
        buf = self._think_hold + text
        self._think_hold = ""
        out: list[str] = []
        i = 0
        n = len(buf)
        while i < n:
            lt = buf.find("<", i)
            if lt == -1:
                rest = buf[i:]
                if self._think_mode:
                    self._thinking_buffer += rest
                    self._emit_thinking(rest)
                else:
                    out.append(rest)
                break
            prefix = buf[i:lt]
            if self._think_mode:
                self._thinking_buffer += prefix
                self._emit_thinking(prefix)
            elif prefix:
                out.append(prefix)
            if not self._think_mode and buf.startswith(_THINK_OPEN, lt):
                self._think_mode = True
                i = lt + len(_THINK_OPEN)
                if i < n and buf[i] == "\n":  # cosmetic: newline after tag
                    i += 1
                continue
            if self._think_mode and buf.startswith(_THINK_CLOSE, lt):
                self._emit_thinking("", end_of_block=True)
                self._think_mode = False
                i = lt + len(_THINK_CLOSE)
                continue
            tail = buf[lt:]
            tag = _THINK_CLOSE if self._think_mode else _THINK_OPEN
            if tag.startswith(tail):
                # Might be a completed tag once the next chunk arrives
                self._think_hold = tail
                break
            if self._think_mode:
                self._thinking_buffer += tail
                self._emit_thinking(tail)
            else:
                out.append(tail)
            break
        return "".join(out)

    def finish(self) -> str:
        """Close any open think span at end of turn; flush held text.

        Returns any held text that turned out to be visible answer content
        (a trailing ``<`` that never completed a tag) so the caller can
        append it to the visible buffer instead of losing it.
        """
        visible_held = ""
        if self._think_hold:
            held, self._think_hold = self._think_hold, ""
            if self._think_mode:
                self._thinking_buffer += held
                self._emit_thinking(held, end_of_block=True)
            else:
                # Trailing text that merely looked like a tag prefix — it is
                # visible answer text and must not be swallowed.
                visible_held = held
        if self._think_mode:
            self._think_mode = False
            self._emit_thinking("", end_of_block=True)
        self._last_thinking = self._thinking_buffer
        return visible_held

    def reset_turn(self) -> None:
        """Clear per-turn capture state before a new turn starts."""
        self._think_hold = ""
        self._think_mode = False
        self._thinking_buffer = ""

    def toggle(self) -> bool:
        """Toggle live thinking display. Returns the new state."""
        self.show_thinking = not self.show_thinking
        return self.show_thinking
