"""Pure mapping of agent :class:`TurnEvent`\\s to a chat sink protocol.

The TUI's pump feeds every drained event through :class:`EventMapper`,
which owns per-turn state (the ``<think>`` filter, visible-text
accumulation) and forwards normalized calls to a ``ChatSink``. Keeping
this pure lets scripted event lists drive the same code path the live
agent uses — the tests exercise the mapper without Textual.

The sink protocol is deliberately flat: one method per thing the chat
view can render. :class:`ChatLog` (spectra/cli/chat.py) implements it.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..agent.turn import TurnEvent, TurnEventType
from .think_filter import ThinkFilter


class ChatSink(Protocol):
    """What the event mapper needs from a chat view."""

    def on_turn_start(self, turn_number: int) -> None: ...
    def on_thinking(self, text: str) -> None: ...
    def on_text_delta(self, text: str) -> None: ...
    def on_text_done(self, full_text: str) -> None: ...
    def on_tool_start(self, call_id: str, name: str) -> None: ...
    def on_tool_args_delta(self, call_id: str, delta: str) -> None: ...
    def on_tool_done(self, call_id: str, name: str, args_json: str) -> None: ...
    def on_tool_result(self, call_id: str, name: str, result: str, is_error: bool) -> None: ...
    def on_error(self, message: str) -> None: ...
    def on_cancelled(self) -> None: ...
    def on_usage(self, usage: Any) -> None: ...
    def on_question(self, question: str, options: list[str], allow_text: bool, call_id: str) -> None: ...
    def on_tool_approval(self, call_id: str, name: str, args_json: str, description: str) -> None: ...
    def on_plan(self, steps: list[str]) -> None: ...
    def on_plan_step(self, index: int, text: str, done: bool) -> None: ...
    def on_save_approval(self, summary: str, metadata: dict[str, Any]) -> None: ...
    def on_save_completed(self, text: str) -> None: ...
    def on_save_discarded(self, text: str) -> None: ...
    def on_phase_change(self, from_phase: str, to_phase: str, reason: str) -> None: ...
    def on_finding(self, summary: str, metadata: dict[str, Any]) -> None: ...
    def on_patch_applied(self, description: str, metadata: dict[str, Any]) -> None: ...
    def on_patch_verified(self, text: str, metadata: dict[str, Any]) -> None: ...
    def on_research_note(self, title: str, metadata: dict[str, Any]) -> None: ...
    def on_research_review(self, title: str, metadata: dict[str, Any]) -> None: ...
    def on_mutation(self, tool_name: str, description: str, metadata: dict[str, Any]) -> None: ...
    def on_subagent(self, status: str, name: str, detail: str) -> None: ...


class EventMapper:
    """Stateful per-run mapping of TurnEvents onto a ChatSink."""

    def __init__(self, sink: ChatSink, think_filter: ThinkFilter | None = None):
        self.sink = sink
        self.think_filter = think_filter or ThinkFilter()
        self._visible_buffer = ""
        self._run_finished = False

    # --- Run lifecycle ---

    def begin_run(self) -> None:
        """Reset per-run state (called when a new agent run starts)."""
        self._visible_buffer = ""
        self._run_finished = False
        self.think_filter.reset_turn()

    @property
    def visible_text(self) -> str:
        """Visible (non-thinking) text accumulated this run."""
        return self._visible_buffer

    # --- Event dispatch ---

    def handle(self, event: TurnEvent) -> None:
        """Map one event to zero or more sink calls."""
        etype = event.type
        sink = self.sink

        if etype == TurnEventType.TURN_START:
            sink.on_turn_start(event.turn_number)
        elif etype == TurnEventType.TEXT_DELTA:
            visible = self.think_filter.feed(event.text)
            self._visible_buffer += visible
            if visible:
                sink.on_text_delta(visible)
        elif etype == TurnEventType.TEXT_DONE:
            held = self.think_filter.finish()
            if held:
                self._visible_buffer += held
            sink.on_text_done(self._visible_buffer)
            # TEXT_DONE fires once per LLM turn with that turn's full text;
            # the next turn (after tool calls) starts a fresh segment.
            self._visible_buffer = ""
        elif etype == TurnEventType.TOOL_CALL_START:
            sink.on_tool_start(event.tool_call_id, event.tool_name)
        elif etype == TurnEventType.TOOL_CALL_ARGS_DELTA:
            sink.on_tool_args_delta(event.tool_call_id, event.tool_args)
        elif etype == TurnEventType.TOOL_CALL_DONE:
            sink.on_tool_done(event.tool_call_id, event.tool_name, event.tool_args)
        elif etype == TurnEventType.TOOL_RESULT:
            sink.on_tool_result(event.tool_call_id, event.tool_name, event.tool_result, event.tool_is_error)
        elif etype == TurnEventType.ERROR:
            sink.on_error(event.error or "Unknown error")
        elif etype == TurnEventType.CANCELLED:
            sink.on_cancelled()
        elif etype == TurnEventType.USAGE_UPDATE:
            sink.on_usage(event.usage)
        elif etype == TurnEventType.USER_QUESTION:
            options = list(event.metadata.get("options") or [])
            allow_text = bool(event.metadata.get("allow_text", False))
            sink.on_question(event.text, options, allow_text, event.tool_call_id)
        elif etype == TurnEventType.TOOL_APPROVAL_REQUEST:
            sink.on_tool_approval(event.tool_call_id, event.tool_name, event.tool_args, event.text)
        elif etype == TurnEventType.PLAN_GENERATED:
            sink.on_plan(list(event.plan_steps or []))
        elif etype == TurnEventType.PLAN_STEP_START:
            sink.on_plan_step(event.plan_step_index, event.text, False)
        elif etype == TurnEventType.PLAN_STEP_DONE:
            sink.on_plan_step(event.plan_step_index, event.text, True)
        elif etype == TurnEventType.SAVE_APPROVAL_REQUEST:
            sink.on_save_approval(event.text, dict(event.metadata))
        elif etype == TurnEventType.SAVE_COMPLETED:
            sink.on_save_completed(event.text)
        elif etype == TurnEventType.SAVE_DISCARDED:
            sink.on_save_discarded(event.text)
        elif etype == TurnEventType.EXPLORATION_PHASE_CHANGE:
            sink.on_phase_change(
                str(event.metadata.get("from_phase", "")),
                str(event.metadata.get("to_phase", "")),
                event.text,
            )
        elif etype == TurnEventType.EXPLORATION_FINDING:
            sink.on_finding(event.text, dict(event.metadata))
        elif etype == TurnEventType.PATCH_APPLIED:
            sink.on_patch_applied(event.text, dict(event.metadata))
        elif etype == TurnEventType.PATCH_VERIFIED:
            sink.on_patch_verified(event.text, dict(event.metadata))
        elif etype == TurnEventType.RESEARCH_NOTE_SAVED:
            sink.on_research_note(event.text, dict(event.metadata))
        elif etype == TurnEventType.RESEARCH_NOTE_REVIEWED:
            sink.on_research_review(event.text, dict(event.metadata))
        elif etype == TurnEventType.MUTATION_RECORDED:
            sink.on_mutation(event.tool_name, event.text, dict(event.metadata))
        elif etype in (
            TurnEventType.SUBAGENT_SPAWNED,
            TurnEventType.SUBAGENT_PROGRESS,
            TurnEventType.SUBAGENT_COMPLETED,
            TurnEventType.SUBAGENT_FAILED,
        ):
            sink.on_subagent(
                _SUBAGENT_STATUS[etype],
                str(event.metadata.get("name", event.text)),
                event.error if etype == TurnEventType.SUBAGENT_FAILED else event.text,
            )
        # Unknown future event types are ignored by design — the pump must
        # never crash the UI over a new event the TUI hasn't learned yet.

    def finish_run(self) -> None:
        """Close the run: flush any unterminated think block."""
        if self._run_finished:
            return
        self._run_finished = True
        self.think_filter.finish()


_SUBAGENT_STATUS = {
    TurnEventType.SUBAGENT_SPAWNED: "spawned",
    TurnEventType.SUBAGENT_PROGRESS: "progress",
    TurnEventType.SUBAGENT_COMPLETED: "completed",
    TurnEventType.SUBAGENT_FAILED: "failed",
}


class RecordingSink:
    """Minimal ChatSink that records calls — test/diagnostic helper."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __getattr__(self, name: str):  # keeps the recording future-proof
        if name.startswith("on_"):

            def record(*args: Any) -> None:
                self.calls.append((name, *args))

            return record
        raise AttributeError(name)

    def last(self, name: str) -> tuple | None:
        for call in reversed(self.calls):
            if call[0] == name:
                return call
        return None
