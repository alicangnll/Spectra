"""Chat widgets for the Spectra TUI.

:class:`ChatLog` implements the ``ChatSink`` protocol from
``spectra.cli.events`` — the app's event pump feeds it through the
:class:`EventMapper`. Interaction events (tool approval, questions, save
approval) are turned into Textual messages bubbled up to the app, which
answers them with modals.
"""

from __future__ import annotations

from typing import Any

from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Collapsible, Markdown, RichLog, Static

from ..core.logging import log_debug

# Hard cap on mounted widgets: keeps a 6-hour session from slowing the
# DOM to a crawl. Oldest widgets are removed beyond this point.
MAX_WIDGETS = 200

_ARG_SUMMARY_KEYS = {
    "read_file": "path",
    "write_file": "path",
    "edit_file": "path",
    "list_directory": "directory",
    "search_files": "pattern",
    "shell_command": "command",
    "spawn_subagent": "task",
}


def summarize_tool_args(name: str, args_json: str) -> str:
    """One-line human summary of a tool call's arguments."""
    import json

    try:
        args = json.loads(args_json) if args_json.strip() else {}
    except json.JSONDecodeError:
        return args_json[:60]
    if not isinstance(args, dict) or not args:
        return ""
    key = _ARG_SUMMARY_KEYS.get(name)
    value = args.get(key) if key in args else next(iter(args.values()), None)
    if value is None:
        return ""
    text = str(value)
    if len(text) > 60:
        text = text[:57] + "..."
    return text


# ---------------------------------------------------------------------------
# Interaction events bubbled to the app (answered via modals)
# ---------------------------------------------------------------------------


class ToolApprovalRequested(Message):
    def __init__(self, call_id: str, name: str, args_json: str, description: str) -> None:
        super().__init__()
        self.call_id = call_id
        self.name = name
        self.args_json = args_json
        self.description = description


class QuestionRequested(Message):
    def __init__(self, question: str, options: list[str], allow_text: bool, call_id: str) -> None:
        super().__init__()
        self.question = question
        self.options = options
        self.allow_text = allow_text
        self.call_id = call_id


class SaveApprovalRequested(Message):
    def __init__(self, summary: str, metadata: dict[str, Any]) -> None:
        super().__init__()
        self.summary = summary
        self.metadata = metadata


# ---------------------------------------------------------------------------
# Message widgets
# ---------------------------------------------------------------------------


class UserMessage(Static):
    def __init__(self, text: str) -> None:
        super().__init__(classes="message message--user")
        self._text = text

    def on_mount(self) -> None:
        self.update(f"[b]You[/b]\n{self._text}")


class QueuedMessage(Static):
    def __init__(self, text: str) -> None:
        super().__init__(classes="message message--queued")
        self._text = text

    def on_mount(self) -> None:
        self.update(
            f"[b]You[/b] [i message--queued-badge]\\[queued — runs after current response][/]\n{self._text}"
        )

    def matches(self, text: str) -> bool:
        return self._text == text


class SystemMessage(Static):
    def __init__(self, text: str) -> None:
        super().__init__(text, classes="message message--system", markup=False)


class ErrorMessage(Static):
    def __init__(self, text: str) -> None:
        super().__init__(classes="message message--error")
        self._text = text

    def on_mount(self) -> None:
        self.update(f"[b message--error-label]Error[/]\n{self._text}")


class MarkdownMessage(Static):
    """Non-streaming markdown bubble (session replay, /help output)."""

    def __init__(self, text: str) -> None:
        super().__init__(classes="message")
        self._text = text

    def compose(self):
        yield Markdown(self._text)


class SubagentBlock(Static):
    _ICONS = {"spawned": "▶", "progress": "…", "completed": "✔", "failed": "✘"}

    def __init__(self, status: str, name: str, detail: str) -> None:
        super().__init__(classes=f"subagent-block subagent--{status}")
        self._status = status
        self._name = name
        self._detail = detail

    def on_mount(self) -> None:
        icon = self._ICONS.get(self._status, "•")
        text = f"{icon} Subagent “{self._name}” {self._status}"
        if self._detail and self._status in ("completed", "failed"):
            text += f" — {self._detail}"
        self.update(text)


class PlanBlock(Static):
    def __init__(self, steps: list[str]) -> None:
        super().__init__(classes="plan-block")
        self._steps = list(steps)
        self._done: set[int] = set()

    def mark_step(self, index: int, done: bool) -> None:
        if done:
            self._done.add(index)
        self._render_steps()

    def _render_steps(self) -> None:
        lines = ["[b]Plan[/]"]
        for i, step in enumerate(self._steps):
            marker = "✔" if i in self._done else f"{i + 1}."
            style = "plan-step--done" if i in self._done else "plan-step--todo"
            lines.append(f"[{style}]{marker} {step}[/]")
        self.update("\n".join(lines))


class ShellEscapeBlock(Static):
    """Header line for a `!command` escape; output streams into the log."""

    def __init__(self, command: str) -> None:
        super().__init__(classes="shell-block")
        self.update(f"[shell-cmd]$ {command}[/]")


class ShellOutput(RichLog):
    """Streaming output area for `!command` runs."""

    def __init__(self) -> None:
        super().__init__(markup=False, highlight=False, wrap=True, max_lines=2000, id="shell-out")


# ---------------------------------------------------------------------------
# Assistant message with streaming markdown + thinking
# ---------------------------------------------------------------------------


class AssistantMessage(Static):
    """One assistant answer: streaming Markdown plus an optional thinking
    block. Text deltas are buffered; the app's async pump flushes them
    into the MarkdownStream (write() is async)."""

    def __init__(self) -> None:
        super().__init__(classes="message")
        self._buffer = ""
        self._flushed = ""
        self._stream = None
        self._finalized = False

    def on_mount(self) -> None:
        self._markdown = Markdown()
        self._thinking = ThinkingBlock()
        self.mount_all([self._thinking, self._markdown])

    # -- streaming --

    def begin_stream(self) -> None:
        """Create the MarkdownStream for this answer (once)."""
        if self._stream is None and not self._finalized:
            self._stream = Markdown.get_stream(self._markdown)

    async def flush(self) -> None:
        """Write buffered deltas into the stream (called from async pump)."""
        if self._stream is not None and self._buffer != self._flushed:
            pending = self._buffer[len(self._flushed) :]
            self._flushed = self._buffer
            await self._stream.write(pending)

    def append_text(self, text: str) -> None:
        self._buffer += text

    def replace_text(self, text: str) -> None:
        """Authoritative full-text reconciliation (held-back trailing chars)."""
        self._buffer = text

    async def finalize(self, full_text: str) -> None:
        """End the stream and render the final markdown once."""
        if self._finalized:
            return
        self._finalized = True
        if self._stream is not None:
            self._stream.stop()
            self._stream = None
        await self._markdown.update(full_text or self._buffer)

    # -- thinking --

    def append_thinking(self, text: str) -> None:
        self._thinking.append(text)

    def close_thinking(self) -> None:
        self._thinking.close_block()

    @property
    def full_text(self) -> str:
        return self._buffer


class ThinkingBlock(Static):
    """Collapsible reasoning block (empty and hidden until content)."""

    def __init__(self) -> None:
        super().__init__(classes="thinking-block")
        self._content = ""
        self._open = False
        self.display = False
        self._collapsible = Collapsible(title="Thinking…", collapsed=True)

    def on_mount(self) -> None:
        self.mount(self._collapsible)
        self._collapsible.mount(Static("", id="thinking-text", classes="thinking-content"))
        if self._content.strip():
            self._sync()

    def _sync(self) -> None:
        self.display = True
        label = "Thinking" if self._content.endswith("\n") else "Thinking…"
        self._collapsible.title = label
        try:
            static = self._collapsible.query_one("#thinking-text", Static)
            static.update(self._content.rstrip() or " ")
        except Exception:  # query before mount finished — retried on next append
            log_debug("thinking block not ready for update")

    def append(self, text: str) -> None:
        self._content += text
        self._sync()

    def close_block(self) -> None:
        if self.display:
            self._collapsible.title = "Thinking"

    def toggle(self) -> bool:
        self._collapsible.collapsed = not self._collapsible.collapsed
        return not self._collapsible.collapsed

    def set_expanded(self, expanded: bool) -> None:
        self.display = True
        self._collapsible.collapsed = not expanded

    @property
    def text(self) -> str:
        return self._content


# ---------------------------------------------------------------------------
# Tool block
# ---------------------------------------------------------------------------


class ToolCallBlock(Static):
    """One tool call: header with name + arg summary, collapsible details."""

    def __init__(self, call_id: str, name: str) -> None:
        super().__init__(classes="tool-block")
        self.call_id = call_id
        self.name = name
        self._args_json = ""
        self._summary = ""
        self._running = True
        self._header = Static("", classes="tool-header tool-header--running")
        self._collapsible = Collapsible(title="", collapsed=True)
        self._args_view = Static("", classes="tool-args")
        self._result_view = Static("", classes="tool-result")

    def on_mount(self) -> None:
        self.mount_all([self._header, self._collapsible])
        self._collapsible.mount_all([self._args_view, self._result_view])
        self._render()

    def set_args(self, args_json: str) -> None:
        self._args_json = args_json
        self._summary = summarize_tool_args(self.name, args_json)
        self._render()

    def set_result(self, result: str, is_error: bool) -> None:
        self._running = False
        shown = result.strip() or "(empty)"
        if len(shown) > 4000:
            shown = shown[:4000] + f"\n… ({len(result)} chars total)"
        self._result_view.update(shown)
        self._result_view.set_classes(
            "tool-result tool-result--error" if is_error else "tool-result"
        )
        self._render(error=is_error)

    def _render(self, error: bool = False) -> None:
        state = "… " if self._running else ("✘ " if error else "✔ ")
        summary = f" ({self._summary})" if self._summary else ""
        self._header.update(f"{state}{self.name}{summary}")
        self._header.set_classes(
            "tool-header tool-header--error" if error and not self._running else "tool-header"
            if not self._running
            else "tool-header tool-header--running"
        )
        self._collapsible.title = f"{self.name}{summary}"
        self._args_view.update(self._args_json or "(no arguments)")

    def toggle(self) -> None:
        self._collapsible.collapsed = not self._collapsible.collapsed


# ---------------------------------------------------------------------------
# ChatLog — the ChatSink implementation
# ---------------------------------------------------------------------------


class ChatLog(VerticalScroll):
    """Scrolling conversation view; implements the ChatSink protocol."""

    def __init__(self) -> None:
        super().__init__(id="chat-log")
        self._current_assistant: AssistantMessage | None = None
        self._pending_finalize: AssistantMessage | None = None
        self._current_plan: PlanBlock | None = None
        self._tool_blocks: dict[str, ToolCallBlock] = {}
        self._subagent_blocks: dict[str, SubagentBlock] = {}
        self._queued: list[QueuedMessage] = []
        self._follow = True
        self.last_usage: Any = None
        self.last_turn = 0
        self._running_tool: str | None = None

    # -- widget plumbing --

    def _add(self, widget: Any) -> None:
        self.mount(widget)
        # Cap the widget tree (drop oldest, keep the newest MAX_WIDGETS).
        children = list(self.children)
        if len(children) > MAX_WIDGETS:
            for old in children[: len(children) - MAX_WIDGETS]:
                old.remove()
        if self._follow:
            self.scroll_end(animate=False)

    def add_user(self, text: str) -> None:
        self._add(UserMessage(text))

    def add_system(self, text: str) -> None:
        self._add(SystemMessage(text))

    def add_markdown(self, text: str) -> None:
        self._add(MarkdownMessage(text))

    def add_error(self, text: str) -> None:
        self._add(ErrorMessage(text))

    def add_queued(self, text: str) -> None:
        widget = QueuedMessage(text)
        self._queued.append(widget)
        self._add(widget)

    def clear(self) -> None:
        """Remove every widget (fresh session via /new)."""
        self.remove_children()
        self._current_assistant = None
        self._pending_finalize = None
        self._current_plan = None
        self._tool_blocks.clear()
        self._subagent_blocks.clear()
        self._queued.clear()
        self._running_tool = None
        self.last_usage = None
        self.last_turn = 0

    def add_shell_escape(self, command: str) -> ShellOutput:
        """Mount a `!command` header + streaming output log; returns the log."""
        self._add(ShellEscapeBlock(command))
        output = ShellOutput()
        self._add(output)
        return output

    def pop_queued(self, text: str) -> None:
        """Remove the queued widget for a message that now starts running."""
        for widget in self._queued:
            if widget.matches(text):
                self._queued.remove(widget)
                widget.remove()
                return

    def remove_all_queued(self) -> None:
        for widget in list(self._queued):
            widget.remove()
        self._queued.clear()

    async def flush_streaming(self) -> None:
        """Flush buffered assistant deltas (called from the async pump)."""
        if self._current_assistant is not None:
            await self._current_assistant.flush()

    async def finalize_pending(self) -> None:
        """Close the assistant message finalized by the last TEXT_DONE."""
        message = self._pending_finalize
        self._pending_finalize = None
        if message is not None:
            await message.finalize(message.full_text)
            if self._current_assistant is message:
                self._current_assistant = None

    def toggle_last_tool(self) -> bool:
        """Collapse/expand the most recent tool block. Returns False when
        there is nothing to toggle."""
        if not self._tool_blocks:
            return False
        last = list(self._tool_blocks.values())[-1]
        last.toggle()
        return True

    def reveal_last_thinking(self, text: str) -> None:
        """Show a completed turn's captured thinking (Ctrl+O style)."""
        if self._current_assistant is not None and self._current_assistant._thinking.text.strip():
            self._current_assistant._thinking.set_expanded(True)
        elif text.strip():
            block = ThinkingBlock()
            self._add(block)
            block.append(text)
            block.close_block()
            block.set_expanded(True)

    # -- ChatSink protocol --

    def on_turn_start(self, turn_number: int) -> None:
        self.last_turn = turn_number
        if turn_number <= 1:
            self._current_assistant = None

    def on_thinking(self, text: str) -> None:
        if self._current_assistant is None:
            self._begin_assistant()
        self._current_assistant.append_thinking(text)

    def on_text_delta(self, text: str) -> None:
        if self._current_assistant is None:
            self._begin_assistant()
        self._current_assistant.append_text(text)

    def on_text_done(self, full_text: str) -> None:
        """TEXT_DONE carries the full (think-filtered) text of one turn.

        Reconciles the buffer with any held-back trailing characters, then
        flags the message for the pump to finalize (markdown update is async).
        """
        if self._current_assistant is None:
            self._begin_assistant()
        message = self._current_assistant
        if message.full_text != full_text:
            message.replace_text(full_text)
        message.close_thinking()
        self._pending_finalize = message

    def _begin_assistant(self) -> None:
        self._current_assistant = AssistantMessage()
        self._add(self._current_assistant)
        # begin_stream must happen post-mount; on_mount of the widget
        # cannot know when it is safe — the app pump calls begin_stream
        # on first flush via ensure_stream().

    def ensure_stream(self) -> None:
        if self._current_assistant is not None:
            self._current_assistant.begin_stream()

    # Events the app turns into modals:

    def on_tool_start(self, call_id: str, name: str) -> None:
        self._running_tool = name
        block = ToolCallBlock(call_id, name)
        self._tool_blocks[call_id] = block
        self._add(block)

    def on_tool_args_delta(self, call_id: str, delta: str) -> None:
        pass  # final args arrive with TOOL_CALL_DONE

    def on_tool_done(self, call_id: str, name: str, args_json: str) -> None:
        block = self._tool_blocks.get(call_id)
        if block is not None:
            block.set_args(args_json)

    def on_tool_result(self, call_id: str, name: str, result: str, is_error: bool) -> None:
        block = self._tool_blocks.get(call_id)
        if block is not None:
            block.set_result(result, is_error)
            self._tool_blocks.pop(call_id, None)
            self._tool_blocks[call_id] = block  # keep as "last" for /toggle
        if self._follow:
            self.scroll_end(animate=False)

    @property
    def running_tool(self) -> str | None:
        return self._running_tool

    def clear_running_tool(self) -> None:
        self._running_tool = None

    def on_error(self, message: str) -> None:
        self.add_error(message)

    def on_cancelled(self) -> None:
        self.add_system("⏹ Interrupted")

    def on_usage(self, usage: Any) -> None:
        self.last_usage = usage  # status bar reads this

    def on_question(self, question: str, options: list[str], allow_text: bool, call_id: str) -> None:
        self.post_message(QuestionRequested(question, options, allow_text, call_id))

    def on_tool_approval(self, call_id: str, name: str, args_json: str, description: str) -> None:
        self.post_message(ToolApprovalRequested(call_id, name, args_json, description))

    def on_plan(self, steps: list[str]) -> None:
        self._current_plan = PlanBlock(steps)
        self._add(self._current_plan)

    def on_plan_step(self, index: int, text: str, done: bool) -> None:
        if self._current_plan is not None:
            self._current_plan.mark_step(index, done)

    def on_save_approval(self, summary: str, metadata: dict[str, Any]) -> None:
        self.post_message(SaveApprovalRequested(summary, metadata))

    def on_save_completed(self, text: str) -> None:
        self.add_system(f"✔ {text}")

    def on_save_discarded(self, text: str) -> None:
        self.add_system(f"✘ {text}")

    def on_phase_change(self, from_phase: str, to_phase: str, reason: str) -> None:
        suffix = f" — {reason}" if reason else ""
        self.add_system(f"◆ Phase: {to_phase.upper()}{suffix}")

    def on_finding(self, summary: str, metadata: dict[str, Any]) -> None:
        category = metadata.get("category", "general")
        address = metadata.get("address")
        prefix = f"[{category}] @{address} " if address else f"[{category}] "
        self.add_system(f"{prefix}{summary}")

    def on_patch_applied(self, description: str, metadata: dict[str, Any]) -> None:
        address = metadata.get("address", "")
        self.add_system(f"✎ Patched {address}: {description}")

    def on_patch_verified(self, text: str, metadata: dict[str, Any]) -> None:
        status = "verified" if metadata.get("success") else "verification FAILED"
        self.add_system(f"✓ Patch {metadata.get('address', '')} {status}")

    def on_research_note(self, title: str, metadata: dict[str, Any]) -> None:
        icon = "✔" if metadata.get("review_passed", True) else "✎"
        genre = metadata.get("genre", "")
        path = metadata.get("path", "")
        self.add_system(f"{icon} Research note: {title} #{genre}\n  {path}")

    def on_research_review(self, title: str, metadata: dict[str, Any]) -> None:
        passed = "passed" if metadata.get("passed") else "needs revision"
        self.add_system(f"✎ Review — {title}: {passed}")

    def on_mutation(self, tool_name: str, description: str, metadata: dict[str, Any]) -> None:
        self.add_system(f"✎ {tool_name}: {description}")

    def on_subagent(self, status: str, name: str, detail: str) -> None:
        if status == "progress" and name in self._subagent_blocks:
            return  # progress noise — the status bar already shows activity
        block = SubagentBlock(status, name, detail)
        self._subagent_blocks[name] = block
        self._add(block)
