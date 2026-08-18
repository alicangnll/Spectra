"""Chat view: scrollable area containing message widgets."""

from __future__ import annotations

import json
import time

from ..agent.turn import TurnEvent, TurnEventType
from ..core.types import Message, Role
from .message_widgets import (
    AssistantMessageWidget,
    ErrorMessageWidget,
    ExplorationFindingWidget,
    ExplorationPhaseWidget,
    QueuedMessageWidget,
    ResearchNoteWidget,
    SubagentEventWidget,
    ThinkingWidget,
    UserMessageWidget,
    UserQuestionWidget,
)
from .plan_view import PlanView
from .qt_compat import (
    QFrame,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)
from .tool_widgets import ToolApprovalWidget, ToolCallWidget, ToolGroupWidget

_THINKING_MIN_DISPLAY_MS = 500

# Collapse consecutive tool runs once they reach this many calls.
# A single tool call is shown inline with its name visible;
# only 2+ consecutive calls get grouped into a collapsible widget.
_TOOL_GROUP_MIN_CALLS = 2

# Floating find-in-conversation bar (Ctrl+F), styled for the dark theme.
_FIND_BAR_STYLE = """
QFrame#chat_find_bar {
    background: #2d2d30;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
}
QLineEdit {
    background: #1e1e1e;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 12px;
}
QLabel {
    color: #9d9d9d;
    font-size: 11px;
}
QPushButton {
    background: #3c3c3c;
    color: #d4d4d4;
    border: none;
    border-radius: 4px;
    font-size: 11px;
}
QPushButton:hover { background: #4a4a4d; }
"""


def _is_hidden_system_user_message(content: str) -> bool:
    """Internal system hints are persisted as user messages but not shown in UI."""
    if not content:
        return False
    return content.lstrip().startswith("[SYSTEM]")


class ChatView(QScrollArea):
    """Scrollable chat area that renders TurnEvents into widgets."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("chat_scroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container.setObjectName("chat_container")
        # Prevent the container from requesting more width than the viewport;
        # this is critical for word-wrap to work inside a QScrollArea.
        self._container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self._layout.addStretch()
        self.setWidget(self._container)

        # Enable horizontal scrolling for "/" separators
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Track current assistant widget for streaming
        self._current_assistant: AssistantMessageWidget | None = None
        self._tool_widgets: dict[str, ToolCallWidget] = {}
        self._thinking: ThinkingWidget | None = None
        self._thinking_shown_at: float = 0.0
        self._plan_view: PlanView | None = None

        # Consecutive tool run state (collapsed when threshold is reached)
        self._tool_run_ids: list[str] = []
        self._tool_run_names: list[str] = []
        self._tool_run_widgets: list[ToolCallWidget] = []
        # Active collapsible group for the current run
        self._tool_group: ToolGroupWidget | None = None
        # Map tool_call_id -> group it belongs to (for result routing/status)
        self._group_map: dict[str, ToolGroupWidget] = {}

        # Member timer for scroll-to-bottom — coalesce at 80ms to reduce
        # layout thrashing during rapid streaming
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(80)
        self._scroll_timer.timeout.connect(self._do_scroll)

        # Timer for minimum thinking display duration (500ms)
        self._thinking_hide_timer = QTimer(self)
        self._thinking_hide_timer.setSingleShot(True)
        self._thinking_hide_timer.timeout.connect(self._force_hide_thinking)

        # Deferred relayout for restored content.  Session restore can run
        # while the panel is still hidden (OnCreate), so word-wrapped labels
        # keep stale pre-show geometry and paint nothing until an unrelated
        # insert forces a relayout.  Re-running the layout once the view has
        # its real size makes restored history visible immediately.
        self._relayout_timer = QTimer(self)
        self._relayout_timer.setSingleShot(True)
        self._relayout_timer.setInterval(0)
        self._relayout_timer.timeout.connect(self._relayout_content)

        # In-conversation search (Ctrl+F).  The bar is built lazily on first
        # open so that headless import paths never construct widgets.
        self._find_bar: QFrame | None = None
        self._find_edit: QLineEdit | None = None
        self._find_count_label: QLabel | None = None
        self._find_matches: list[QWidget] = []
        self._find_index = -1
        self._find_highlight_widget: QWidget | None = None
        self._find_highlight_style: str | None = None

        find_sc = QShortcut(QKeySequence("Ctrl+F"), self)
        find_sc.activated.connect(self._open_find_bar)

        # Plain Python callbacks avoid extra Qt signal traffic in the hot chat path.
        self._tool_approval_callback = None
        self._user_answer_callback = None

    def set_tool_approval_callback(self, callback) -> None:
        self._tool_approval_callback = callback

    def set_user_answer_callback(self, callback) -> None:
        self._user_answer_callback = callback

    def add_user_message(self, text: str) -> None:
        widget = UserMessageWidget(text)
        self._insert_widget(widget)
        self._current_assistant = None

    def add_error_message(self, text: str) -> None:
        self._insert_widget(ErrorMessageWidget(text))
        self._scroll_to_bottom()

    def add_queued_message(self, text: str) -> None:
        self._insert_widget(QueuedMessageWidget(text))
        self._scroll_to_bottom()

    def remove_queued_messages(self) -> None:
        """Remove all [queued] message widgets (e.g. on cancel)."""
        for i in reversed(range(self._layout.count())):
            item = self._layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QueuedMessageWidget):
                self._layout.removeWidget(widget)
                widget.deleteLater()

    def pop_first_queued_message(self) -> None:
        """Remove the first [queued] widget (when it gets submitted)."""
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QueuedMessageWidget):
                self._layout.removeWidget(widget)
                widget.deleteLater()
                return

    def _show_thinking(self) -> None:
        if self._thinking is not None:
            return
        self._thinking = ThinkingWidget()
        self._thinking_shown_at = time.monotonic()
        self._insert_widget(self._thinking)
        self._scroll_to_bottom()

    def _hide_thinking(self) -> None:
        # Don't auto-hide thinking anymore - let it persist to show AI's thought process
        # Only hide when explicitly forced (e.g., when actual text response starts)
        if self._thinking is None:
            return
        # Optional: Show elapsed time to indicate how long AI has been thinking
        _elapsed_ms = (time.monotonic() - self._thinking_shown_at) * 1000
        # Keep thinking widget visible - don't auto-hide
        # self._force_hide_thinking()

    def _force_hide_thinking(self) -> None:
        if self._thinking is None:
            return
        self._thinking.stop()
        self._layout.removeWidget(self._thinking)
        self._thinking.deleteLater()
        self._thinking = None

    def _reset_tool_run(self) -> None:
        """End the current consecutive tool run (state only)."""
        self._tool_group = None
        self._tool_run_ids.clear()
        self._tool_run_names.clear()
        self._tool_run_widgets.clear()

    def _register_tool_widget(self, tool_name: str, tool_id: str, widget: ToolCallWidget) -> None:
        """Attach a new tool widget to the current run, collapsing at threshold."""
        self._tool_run_ids.append(tool_id)
        self._tool_run_names.append(tool_name)
        self._tool_run_widgets.append(widget)

        run_len = len(self._tool_run_widgets)

        # Below threshold: show tool calls directly.
        if self._tool_group is None and run_len < _TOOL_GROUP_MIN_CALLS:
            self._insert_widget(widget)
            return

        # Threshold reached: move entire run into a new collapsible group.
        if self._tool_group is None and run_len == _TOOL_GROUP_MIN_CALLS:
            self._tool_group = ToolGroupWidget()
            self._insert_widget(self._tool_group)

            for idx, run_widget in enumerate(self._tool_run_widgets):
                self._layout.removeWidget(run_widget)
                run_widget.hide_preview()

                run_tool_id = self._tool_run_ids[idx]
                run_tool_name = self._tool_run_names[idx]
                self._tool_group.add_widget(run_widget, run_tool_name)
                self._group_map[run_tool_id] = self._tool_group
            return

        # Already collapsed: add new call directly to existing group.
        widget.hide_preview()
        if self._tool_group is not None:
            self._tool_group.add_widget(widget, tool_name)
            self._group_map[tool_id] = self._tool_group

    def handle_event(self, event: TurnEvent) -> None:
        """Process a TurnEvent and update the UI accordingly."""
        etype = event.type
        if etype in (TurnEventType.TEXT_DELTA, TurnEventType.TEXT_DONE):
            self._handle_text_event(event)
        elif etype in (
            TurnEventType.TOOL_CALL_START,
            TurnEventType.TOOL_CALL_ARGS_DELTA,
            TurnEventType.TOOL_CALL_DONE,
            TurnEventType.TOOL_RESULT,
            TurnEventType.TOOL_APPROVAL_REQUEST,
        ):
            self._handle_tool_event(event)
        elif etype in (
            TurnEventType.TURN_START,
            TurnEventType.TURN_END,
            TurnEventType.CANCELLED,
        ):
            self._handle_lifecycle_event(event)
        elif etype in (
            TurnEventType.PLAN_GENERATED,
            TurnEventType.PLAN_STEP_START,
            TurnEventType.PLAN_STEP_DONE,
        ):
            self._handle_plan_event(event)
        elif etype in (
            TurnEventType.EXPLORATION_PHASE_CHANGE,
            TurnEventType.EXPLORATION_FINDING,
        ):
            self._handle_exploration_event(event)
        elif etype in (
            TurnEventType.RESEARCH_NOTE_SAVED,
            TurnEventType.RESEARCH_NOTE_REVIEWED,
        ):
            self._handle_research_event(event)
        elif etype in (
            TurnEventType.USER_QUESTION,
            TurnEventType.SAVE_APPROVAL_REQUEST,
        ):
            self._handle_question_event(event)
        elif etype in (
            TurnEventType.SUBAGENT_SPAWNED,
            TurnEventType.SUBAGENT_COMPLETED,
            TurnEventType.SUBAGENT_FAILED,
        ):
            self._handle_subagent_event(event)
        elif etype == TurnEventType.ERROR:
            self._hide_thinking()
            self._reset_tool_run()
            self._insert_widget(ErrorMessageWidget(event.error or "Unknown error"))
            self._scroll_to_bottom()

    def _handle_text_event(self, event: TurnEvent) -> None:
        # Don't hide thinking - let it persist to show AI's thought process
        # self._hide_thinking()
        self._reset_tool_run()
        if event.type == TurnEventType.TEXT_DELTA:
            # Hide thinking only when we start showing actual text response
            if self._thinking is not None:
                self._force_hide_thinking()
            if self._current_assistant is None:
                self._current_assistant = AssistantMessageWidget()
                self._insert_widget(self._current_assistant)
            self._current_assistant.append_text(event.text)
            self._scroll_to_bottom()
        else:  # TEXT_DONE
            if self._current_assistant is not None:
                self._current_assistant.set_text(event.text)
            self._current_assistant = None

    def _handle_tool_event(self, event: TurnEvent) -> None:
        etype = event.type
        if etype == TurnEventType.TOOL_CALL_START:
            # Don't hide thinking - let tool calls appear below it
            # self._hide_thinking()
            tw = ToolCallWidget(event.tool_name, event.tool_call_id)
            self._tool_widgets[event.tool_call_id] = tw
            self._register_tool_widget(event.tool_name, event.tool_call_id, tw)
            self._scroll_to_bottom()
        elif etype == TurnEventType.TOOL_CALL_ARGS_DELTA:
            existing_tw = self._tool_widgets.get(event.tool_call_id)
            if existing_tw is not None:
                existing_tw.append_args_delta(event.tool_args)
        elif etype == TurnEventType.TOOL_CALL_DONE:
            existing_tw = self._tool_widgets.get(event.tool_call_id)
            if existing_tw is not None:
                existing_tw.set_arguments(event.tool_args, event.parameter_descriptions)
        elif etype == TurnEventType.TOOL_RESULT:
            self._reset_tool_run()
            existing_tw = self._tool_widgets.get(event.tool_call_id)
            if existing_tw is not None:
                existing_tw.set_result(event.tool_result, event.tool_is_error)
            group = self._group_map.get(event.tool_call_id)
            if group:
                group.notify_result(event.tool_is_error)
            self._scroll_to_bottom()
        elif etype == TurnEventType.TOOL_APPROVAL_REQUEST:
            # Don't hide thinking for approval requests either
            # self._hide_thinking()
            self._reset_tool_run()
            widget = ToolApprovalWidget(
                event.tool_call_id,
                event.tool_name,
                event.tool_args,
                event.text,
            )
            widget.set_approved_callback(self._on_tool_approval)
            self._insert_widget(widget)
            self._scroll_to_bottom()

    def _handle_lifecycle_event(self, event: TurnEvent) -> None:
        etype = event.type
        if etype == TurnEventType.TURN_START:
            self._current_assistant = None
            self._reset_tool_run()
            self._group_map.clear()
            self._show_thinking()
            self._scroll_to_bottom()
        elif etype == TurnEventType.TURN_END:
            self._hide_thinking()
            self._reset_tool_run()
            self._current_assistant = None
        elif etype == TurnEventType.CANCELLED:
            self._hide_thinking()
            self._reset_tool_run()
            self._insert_widget(ErrorMessageWidget("Cancelled by user"))
            self._scroll_to_bottom()

    def _handle_plan_event(self, event: TurnEvent) -> None:
        etype = event.type
        if etype == TurnEventType.PLAN_GENERATED:
            self._hide_thinking()
            self._reset_tool_run()
            self._plan_view = PlanView()
            if event.plan_steps:
                self._plan_view.set_plan(event.plan_steps)

            def _on_plan_approve(pv=self._plan_view):
                pv.set_buttons_visible(False)
                self._on_user_answer("approve")

            def _on_plan_reject(pv=self._plan_view):
                pv.set_buttons_visible(False)
                self._on_user_answer("reject")

            self._plan_view.set_approved_callback(_on_plan_approve)
            self._plan_view.set_rejected_callback(_on_plan_reject)
            self._insert_widget(self._plan_view)
            self._scroll_to_bottom()
        elif etype == TurnEventType.PLAN_STEP_START:
            if self._plan_view:
                self._plan_view.set_step_status(event.plan_step_index, "active")
                self._plan_view.set_buttons_visible(False)
            self._scroll_to_bottom()
        elif etype == TurnEventType.PLAN_STEP_DONE:
            if self._plan_view:
                self._plan_view.set_step_status(event.plan_step_index, "done")
            self._scroll_to_bottom()

    def _handle_exploration_event(self, event: TurnEvent) -> None:
        meta = event.metadata
        if event.type == TurnEventType.EXPLORATION_PHASE_CHANGE:
            self._hide_thinking()
            self._reset_tool_run()
            self._insert_widget(
                ExplorationPhaseWidget(
                    meta.get("from_phase", ""),
                    meta.get("to_phase", ""),
                    event.text,
                )
            )
        else:  # EXPLORATION_FINDING
            self._insert_widget(
                ExplorationFindingWidget(
                    meta.get("category", "general"),
                    event.text,
                    meta.get("address"),
                    meta.get("relevance", "medium"),
                )
            )
        self._scroll_to_bottom()

    def _handle_research_event(self, event: TurnEvent) -> None:
        meta = event.metadata
        if event.type == TurnEventType.RESEARCH_NOTE_SAVED:
            self._hide_thinking()
            self._reset_tool_run()
            self._insert_widget(
                ResearchNoteWidget(
                    title=event.text,
                    genre=meta.get("genre", "general"),
                    path=meta.get("path", ""),
                    preview=meta.get("preview", ""),
                    review_passed=meta.get("review_passed", True),
                )
            )
            self._scroll_to_bottom()
        # RESEARCH_NOTE_REVIEWED — no separate widget, info is in the saved event

    def _handle_subagent_event(self, event: TurnEvent) -> None:
        meta = event.metadata
        if event.type == TurnEventType.SUBAGENT_SPAWNED:
            name = event.text
            agent_type = meta.get("agent_type", "custom")
            self._insert_widget(SubagentEventWidget("spawned", name, f"type: {agent_type}"))
        elif event.type == TurnEventType.SUBAGENT_COMPLETED:
            name = meta.get("name", "")
            turns = meta.get("turn_count", 0)
            elapsed = meta.get("elapsed", 0.0)
            detail = f"{turns} turns, {elapsed:.0f}s"
            self._insert_widget(SubagentEventWidget("completed", name, detail))
        elif event.type == TurnEventType.SUBAGENT_FAILED:
            name = meta.get("name", "")
            error = event.error or "Unknown error"
            self._insert_widget(SubagentEventWidget("failed", name, error))
        self._scroll_to_bottom()

    def _handle_question_event(self, event: TurnEvent) -> None:
        self._hide_thinking()
        self._reset_tool_run()
        if event.type == TurnEventType.SAVE_APPROVAL_REQUEST:
            options = ["Save All", "Discard All"]
        else:  # USER_QUESTION
            options = event.metadata.get("options", [])
        widget = UserQuestionWidget(event.text, options)
        widget.set_option_selected_callback(self._on_user_answer)
        self._insert_widget(widget)
        self._scroll_to_bottom()

    def _on_tool_approval(self, tool_call_id: str, decision: str) -> None:
        """Forward tool approval decision to the panel/controller."""
        if self._tool_approval_callback is not None:
            self._tool_approval_callback(tool_call_id, decision)

    def _on_user_answer(self, answer: str) -> None:
        """Forward a button-selected answer to the panel/controller."""
        if self._user_answer_callback is not None:
            self._user_answer_callback(answer)

    # ------------------------------------------------------------------
    # Find-in-conversation (Ctrl+F)
    # ------------------------------------------------------------------

    def _open_find_bar(self) -> None:
        """Show the floating search bar (Ctrl+F) and focus its input."""
        if self._find_bar is None:
            self._build_find_bar()
        self._find_bar.show()
        self._find_bar.raise_()
        self._position_find_bar()
        self._find_edit.setFocus()
        self._find_edit.selectAll()

    def _build_find_bar(self) -> None:
        """Construct the floating find bar (once, on first Ctrl+F)."""
        bar = QFrame(self)
        bar.setObjectName("chat_find_bar")
        bar.setStyleSheet(_FIND_BAR_STYLE)
        bar.hide()

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        self._find_edit = QLineEdit()
        self._find_edit.setPlaceholderText("Find in conversation…")
        self._find_edit.setFixedWidth(200)
        self._find_edit.textChanged.connect(self._on_find_text_changed)
        self._find_edit.returnPressed.connect(self._on_find_next)
        layout.addWidget(self._find_edit)

        self._find_count_label = QLabel("")
        self._find_count_label.setFixedWidth(40)
        layout.addWidget(self._find_count_label)

        for text, slot in (
            ("▲", self._on_find_prev),
            ("▼", self._on_find_next),
            ("✕", self._close_find_bar),
        ):
            btn = QPushButton(text)
            btn.setFixedSize(24, 24)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        # Shift+Enter steps backwards; Enter alone (returnPressed) steps forward.
        prev_sc = QShortcut(QKeySequence("Shift+Return"), self._find_edit)
        prev_sc.activated.connect(self._on_find_prev)
        close_sc = QShortcut(QKeySequence("Escape"), bar)
        close_sc.activated.connect(self._close_find_bar)

        self._find_bar = bar

    def _position_find_bar(self) -> None:
        """Pin the bar to the top-right corner of the chat area."""
        if self._find_bar is None or not self._find_bar.isVisible():
            return
        try:
            width = self._find_bar.sizeHint().width()
            self._find_bar.move(max(8, self.width() - width - 20), 8)
        except RuntimeError:
            pass

    def _collect_find_matches(self, query: str) -> list[QWidget]:
        """Widgets whose searchable text contains the query, in visual order."""
        q = (query or "").strip().lower()
        if not q:
            return []
        matches: list[QWidget] = []
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            widget = item.widget() if item else None
            if widget is None or not hasattr(widget, "search_text"):
                continue
            try:
                text = widget.search_text()
            except RuntimeError:
                continue  # underlying C++ object already deleted
            if text and q in text.lower():
                matches.append(widget)
        return matches

    def _on_find_text_changed(self, text: str) -> None:
        self._find_matches = self._collect_find_matches(text)
        self._find_index = -1
        if self._find_matches:
            self._go_to_find_match(0)
        else:
            self._clear_find_highlight()
            self._find_count_label.setText("0/0" if text.strip() else "")

    def _on_find_next(self) -> None:
        if self._find_matches:
            self._go_to_find_match(self._find_index + 1)

    def _on_find_prev(self) -> None:
        if self._find_matches:
            self._go_to_find_match(self._find_index - 1)

    def _go_to_find_match(self, index: int) -> None:
        if not self._find_matches:
            return
        self._find_index = index % len(self._find_matches)
        widget = self._find_matches[self._find_index]
        self._apply_find_highlight(widget)
        try:
            self.ensureWidgetVisible(widget, 0, 12)
        except RuntimeError:
            pass
        self._find_count_label.setText(f"{self._find_index + 1}/{len(self._find_matches)}")

    def _apply_find_highlight(self, widget: QWidget) -> None:
        """Emphasize the current match with a golden border (reversible)."""
        self._clear_find_highlight()
        name = widget.objectName()
        if not name:
            return
        try:
            self._find_highlight_style = widget.styleSheet() or ""
            self._find_highlight_widget = widget
            widget.setStyleSheet(
                self._find_highlight_style + f"\n#{name} {{ border: 2px solid #f5c518; border-radius: 8px; }}"
            )
        except RuntimeError:
            pass

    def _clear_find_highlight(self) -> None:
        """Restore the previously highlighted message's original style."""
        if self._find_highlight_widget is not None:
            try:
                self._find_highlight_widget.setStyleSheet(self._find_highlight_style or "")
            except RuntimeError:
                pass
        self._find_highlight_widget = None
        self._find_highlight_style = None

    def _close_find_bar(self) -> None:
        """Hide the search bar and drop all search state."""
        self._clear_find_highlight()
        self._find_matches = []
        self._find_index = -1
        if self._find_bar is not None:
            try:
                self._find_bar.hide()
            except RuntimeError:
                pass

    def restore_from_messages(self, messages: list[Message]) -> None:
        """Replay saved Message objects into the chat view."""
        self.clear_chat()

        for msg in messages:
            if msg.role == Role.USER:
                if _is_hidden_system_user_message(msg.content):
                    continue
                self._reset_tool_run()
                self.add_user_message(msg.content)

            elif msg.role == Role.ASSISTANT:
                self._reset_tool_run()
                if msg.content:
                    w = AssistantMessageWidget()
                    w.set_text(msg.content)
                    self._insert_widget(w)

                for tc in msg.tool_calls:
                    tw = ToolCallWidget(tc.name, tc.id)
                    try:
                        args_str = json.dumps(tc.arguments, indent=2)
                    except (TypeError, ValueError):
                        args_str = str(tc.arguments)
                    tw.set_arguments(args_str)
                    tw.mark_done()
                    self._tool_widgets[tc.id] = tw
                    self._register_tool_widget(tc.name, tc.id, tw)

            elif msg.role == Role.TOOL:
                self._reset_tool_run()
                for tr in msg.tool_results:
                    existing_tw = self._tool_widgets.get(tr.tool_call_id)
                    if existing_tw is not None:
                        existing_tw.set_result(tr.content, tr.is_error)
                    group = self._group_map.get(tr.tool_call_id)
                    if group:
                        group.notify_result(tr.is_error)

        self._current_assistant = None
        self._reset_tool_run()
        self._scroll_to_bottom()
        self._relayout_timer.start()

    def clear_chat(self) -> None:
        self._close_find_bar()
        self._force_hide_thinking()
        self._thinking_hide_timer.stop()
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._current_assistant = None
        self._tool_widgets.clear()
        self._plan_view = None
        self._reset_tool_run()
        self._group_map.clear()

    def _insert_widget(self, widget: QWidget) -> None:
        """Insert before the stretch at the end."""
        idx = self._layout.count() - 1
        self._layout.insertWidget(idx, widget)

    def resizeEvent(self, event) -> None:
        """Keep the container width pinned to the viewport width.

        QScrollArea.setWidgetResizable(True) handles this when there is no
        horizontal scrollbar, but QLabel rich-text word-wrap still sometimes
        requests a wider sizeHint.  Explicitly clamping here guarantees text
        wraps to the visible area.
        """
        super().resizeEvent(event)
        if self._container is not None:
            self._container.setFixedWidth(self.viewport().width())
        self._position_find_bar()

    def showEvent(self, event) -> None:
        """Redo the layout when the view becomes visible.

        Widgets restored while the dock form was hidden were laid out
        against the pre-show (default) width; without this, the chat can
        paint empty until the next user interaction inserts a widget and
        forces a full relayout.
        """
        super().showEvent(event)
        self._relayout_timer.start()

    def _relayout_content(self) -> None:
        """Re-run the container layout and re-pin its width to the viewport."""
        if self._container is None:
            return
        try:
            self._container.setFixedWidth(self.viewport().width())
            self._layout.activate()
        except RuntimeError:
            # Underlying C++ object already deleted (panel tearing down)
            return
        self._scroll_to_bottom()

    def _is_near_bottom(self) -> bool:
        """True if the user hasn't scrolled up (within ~60px of bottom)."""
        sb = self.verticalScrollBar()
        return sb.maximum() - sb.value() < 60

    def _scroll_to_bottom(self) -> None:
        if self._is_near_bottom():
            self._scroll_timer.start()

    def _do_scroll(self) -> None:
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def shutdown(self) -> None:
        self._scroll_timer.stop()
        self._thinking_hide_timer.stop()
        self._relayout_timer.stop()
        self._force_hide_thinking()
        self._tool_approval_callback = None
        self._user_answer_callback = None
