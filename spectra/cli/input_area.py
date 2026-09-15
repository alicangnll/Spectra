"""Prompt input widget: TextArea with chat key bindings.

Keys (Claude-CLI style):
  - Enter submits the buffer (multi-line allowed)
  - Ctrl+J or Shift+Enter inserts a newline
  - Up/Down walk input history while the cursor sits at the buffer edge
  - Up/Down navigate the completion popup while it is visible
  - Tab or Enter accepts the selected completion
  - Escape hides the completion popup

The widget owns its :class:`~spectra.cli.history.InputHistory` (passed in)
and drives the completion popup indirectly: it posts
:class:`CompletionsChanged` messages and the app renders them into
``#completion-popup``.
"""

from __future__ import annotations

from typing import Sequence

from textual import events
from textual.message import Message
from textual.widgets import TextArea

from . import completion
from .history import InputHistory


class PromptInput(TextArea, inherit_bindings=False):
    """Multi-line chat input with history and slash-command completion."""

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class CompletionsChanged(Message):
        def __init__(self, items: Sequence[completion.CompletionItem], index: int) -> None:
            super().__init__()
            self.items = list(items)
            self.index = index

    def __init__(self, history: InputHistory) -> None:
        super().__init__("", id="prompt-input", soft_wrap=True, show_line_numbers=False)
        self._history = history
        self._history_pos: int | None = None  # None = not browsing
        self._history_draft = ""
        self._completion_items: list[completion.CompletionItem] = []
        self._completion_index = 0
        self._completion_visible = False
        self._completion_ctx: dict = {"skills": (), "models": (), "sessions": ()}

    # -- context from the app --

    def set_completion_context(
        self,
        *,
        skills: Sequence[str] = (),
        models: Sequence[str] = (),
        sessions: Sequence[tuple[str, str]] = (),
    ) -> None:
        self._completion_ctx = {"skills": tuple(skills), "models": tuple(models), "sessions": tuple(sessions)}
        self._recompute()

    # -- completion state --

    @property
    def completions_active(self) -> bool:
        return self._completion_visible and bool(self._completion_items)

    def _recompute(self) -> None:
        items = completion.compute(self.text, **self._completion_ctx)
        self._completion_items = items
        self._completion_index = 0 if items else -1
        self._completion_visible = bool(items)
        self.post_message(self.CompletionsChanged(items, self._completion_index))

    def hide_completions(self) -> None:
        if self._completion_visible:
            self._completion_visible = False
            self._completion_items = []
            self._completion_index = -1
            self.post_message(self.CompletionsChanged([], -1))

    def _accept_completion(self) -> bool:
        if not self.completions_active:
            return False
        item = self._completion_items[self._completion_index]
        self.load_text(item.insert)
        self._end_of_buffer()
        self._recompute()
        return True

    def _move_completion(self, delta: int) -> bool:
        if not self.completions_active:
            return False
        count = len(self._completion_items)
        self._completion_index = (self._completion_index + delta) % count
        self.post_message(self.CompletionsChanged(self._completion_items, self._completion_index))
        return True

    # -- history --

    def _at_first_position(self) -> bool:
        return self.cursor_location == (0, 0)

    def _at_last_position(self) -> bool:
        # TextArea (textual 8.x) exposes cursor predicates instead of a
        # line_count attribute; end-of-buffer means last line AND last col.
        return self.cursor_at_last_line and self.cursor_at_end_of_line

    def _load_history_text(self, text: str) -> None:
        self.load_text(text)
        self._end_of_buffer()

    def _end_of_buffer(self) -> None:
        lines = self.text.split("\n")
        self.move_cursor((len(lines) - 1, len(lines[-1])))

    def _history_back(self) -> bool:
        if not self._at_first_position():
            return False
        entries = self._history.load()
        if not entries:
            return False
        if self._history_pos is None:
            self._history_draft = self.text
            self._history_pos = 0
        elif self._history_pos >= len(entries) - 1:
            return True  # already at the oldest entry — swallow the keypress
        else:
            self._history_pos += 1
        self._load_history_text(entries[self._history_pos])
        return True

    def _history_forward(self) -> bool:
        if self._history_pos is None:
            return False
        self._history_pos -= 1
        if self._history_pos < 0:
            self._history_pos = None
            self._load_history_text(self._history_draft)
        else:
            entries = self._history.load()
            self._load_history_text(entries[self._history_pos])
        return True

    # -- submission --

    def _submit(self) -> None:
        text = self.text.strip("\n")
        self.hide_completions()
        if not text.strip():
            self.load_text("")
            return
        self._history.add(text)
        self._history_pos = None
        self._history_draft = ""
        self.load_text("")
        self.post_message(self.Submitted(text))

    # -- key routing --

    async def _on_key(self, event: events.Key) -> None:
        key = event.key
        if key == "escape":
            if self.completions_active:
                event.stop()
                event.prevent_default()
                self.hide_completions()
            return
        if self.completions_active:
            if key == "tab":
                event.stop()
                event.prevent_default()
                self._accept_completion()
                return
            if key == "enter":
                event.stop()
                event.prevent_default()
                # A fully typed command ("/help") + Enter submits; Enter only
                # accepts the popup when the typed text is still a prefix,
                # not an exact match of a suggestion.
                typed = self.text.strip()
                exact = any(
                    typed == item.label.strip() or typed == item.insert.strip()
                    for item in self._completion_items
                )
                if exact:
                    self._submit()
                else:
                    self._accept_completion()
                return
            if key == "up":
                event.stop()
                event.prevent_default()
                self._move_completion(-1)
                return
            if key == "down":
                event.stop()
                event.prevent_default()
                self._move_completion(1)
                return
        if key == "enter":
            event.stop()
            event.prevent_default()
            self._submit()
            return
        if key in ("shift+enter", "ctrl+j"):
            event.stop()
            event.prevent_default()
            self.insert("\n")
            return
        if key == "up" and self._history_back():
            event.stop()
            event.prevent_default()
            return
        if key == "down" and self._history_forward():
            event.stop()
            event.prevent_default()
            return
        await super()._on_key(event)

    # TextArea posts Changed on every edit — recompute completions from it.
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._recompute()

    # -- app helpers --

    def restore_text(self, text: str) -> None:
        """Refill the input (e.g. queue returned on interrupt)."""
        self.load_text(text)
        self._end_of_buffer()
        self.focus()
