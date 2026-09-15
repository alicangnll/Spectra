"""Modal dialogs: tool approval, shell approval, questions, save, confirm.

All modals dismiss with a plain result. The app's ``on_*`` handlers turn
that result into the matching ``submit_*`` call on the agent loop:

- ToolApprovalModal  → ``submit_tool_approval("allow"|"allow_all"|"deny")``
- QuestionModal      → ``submit_user_answer(text)`` (plan approvals and save
  decisions ride the same queue — answers parse via ``parse_approval`` /
  ``parse_save_decision``)
- ShellApprovalModal → resolves the ``ShellApprovalBridge`` event
- ConfirmModal       → generic yes/no for destructive commands
"""

from __future__ import annotations

from typing import Any

from textual import events
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

from .approval import decision_for_keystroke


class _ModalFrame(Vertical):
    """Centered dialog frame (.modal / .modal-danger from spectra.tcss)."""

    def __init__(self, danger: bool = False) -> None:
        super().__init__(classes="modal modal-danger" if danger else "modal")


class ToolApprovalModal(ModalScreen[str]):
    """Approve a mutating tool call. y=once, a=always this run, n/esc=deny."""

    BINDINGS = [
        ("y", "decide('allow')", "Allow once"),
        ("a", "decide('allow_all')", "Always this run"),
        ("n,escape", "decide('deny')", "Deny"),
    ]

    def __init__(self, name: str, args_json: str, description: str) -> None:
        super().__init__()
        self.tool_name = name
        self.args_json = args_json
        self.description = description

    def compose(self):
        with _ModalFrame(danger=True):
            yield Static("Tool approval", classes="modal-title")
            body = f"{self.tool_name}\n\n{self.description or ''}"
            yield Static(body, classes="modal-body", markup=False)
            if self.args_json.strip():
                yield Static(self.args_json, classes="tool-args", markup=False)
            yield Static(
                "[y] allow once   [a] always this run   [n] deny",
                classes="modal-hint",
                markup=False,
            )
            with Vertical(classes="modal-buttons"):
                yield Button("Allow", variant="warning", id="allow")
                yield Button("Always", variant="error", id="allow_all")
                yield Button("Deny", variant="default", id="deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id or "deny")

    def on_mount(self) -> None:
        # Take focus so plain letter keys reach these screen bindings
        # instead of the chat input hidden underneath.
        buttons = self.query(Button)
        if buttons:
            buttons.first().focus()

    def action_decide(self, decision: str) -> None:
        self.dismiss(decision)


class ShellApprovalModal(ModalScreen[bool]):
    """Approve a shell command from the agent thread's approval callback."""

    def __init__(self, command: str, is_dangerous: bool, danger_reason: str) -> None:
        super().__init__()
        self.command = command
        self.is_dangerous = is_dangerous
        self.danger_reason = danger_reason

    def compose(self):
        with _ModalFrame(danger=self.is_dangerous):
            title = "Dangerous command" if self.is_dangerous else "Shell command"
            yield Static(title, classes="modal-title")
            yield Static(f"$ {self.command}", classes="modal-body", markup=False)
            if self.danger_reason:
                yield Static(f"⚠ {self.danger_reason}", classes="modal-hint", markup=False)
            yield Static(
                "[y] approve   [a] approve all safe this run   [n] deny",
                classes="modal-hint",
                markup=False,
            )
            with Vertical(classes="modal-buttons"):
                yield Button("Approve", variant="warning", id="yes")
                yield Button("Deny", variant="default", id="no")

    def on_key(self, event: events.Key) -> None:
        decision = decision_for_keystroke(event.key)
        if event.key in ("y", "a", "n", "escape"):
            event.stop()
            event.prevent_default()
            self.dismiss(decision in ("allow", "allow_all"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def on_mount(self) -> None:
        buttons = self.query(Button)
        if buttons:
            buttons.first().focus()


class QuestionInput(TextArea):
    """Free-text answer box; Enter submits the typed answer."""

    class Submitted(events.Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self) -> None:
        super().__init__("", id="question-input", soft_wrap=True, show_line_numbers=False)

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.post_message(self.Submitted(self.text.strip()))
            return
        await super()._on_key(event)


class QuestionModal(ModalScreen[str]):
    """Ask-user question: option buttons plus optional free text."""

    def __init__(
        self,
        question: str,
        options: list[str] | None = None,
        allow_text: bool = False,
    ) -> None:
        super().__init__()
        self.question = question
        self.options = options or []
        self.allow_text = allow_text

    def compose(self):
        with _ModalFrame():
            yield Static("Question", classes="modal-title")
            yield Static(self.question, classes="modal-body", markup=False)
            if self.options:
                with Vertical(classes="modal-buttons"):
                    for i, option in enumerate(self.options):
                        yield Button(option, variant="primary", id=f"opt{i}")
            if self.allow_text:
                yield QuestionInput()

    def on_mount(self) -> None:
        if self.allow_text:
            self.query_one("#question-input", QuestionInput).focus()
        else:
            buttons = self.query(Button)
            if buttons:
                buttons.first().focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        idx = int(event.button.id.removeprefix("opt"))
        self.dismiss(self.options[idx])

    def on_question_input_submitted(self, event: QuestionInput.Submitted) -> None:
        if event.text:
            self.dismiss(event.text)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            event.prevent_default()
            self.dismiss("")


class SaveApprovalModal(ModalScreen[str]):
    """Save the session before exit? → 'save' or 'discard' (parse_save_decision)."""

    BINDINGS = [
        ("y,s", "decide('save')", "Save"),
        ("n,d,escape", "decide('discard')", "Discard"),
    ]

    def __init__(self, summary: str) -> None:
        super().__init__()
        self.summary = summary

    def compose(self):
        with _ModalFrame():
            yield Static("Save session?", classes="modal-title")
            yield Static(self.summary or "Save this session before it is closed?", classes="modal-body", markup=False)
            yield Static("[y] save   [n] discard", classes="modal-hint", markup=False)
            with Vertical(classes="modal-buttons"):
                yield Button("Save", variant="success", id="save")
                yield Button("Discard", variant="default", id="discard")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id or "discard")

    def on_mount(self) -> None:
        buttons = self.query(Button)
        if buttons:
            buttons.first().focus()

    def action_decide(self, decision: str) -> None:
        self.dismiss(decision)


class ConfirmModal(ModalScreen[bool]):
    """Generic destructive-action confirmation (e.g. /delete)."""

    BINDINGS = [
        ("y,enter", "decide(True)", "Confirm"),
        ("escape,n", "decide(False)", "Cancel"),
    ]

    def __init__(self, title: str, body: str, confirm_label: str = "Confirm") -> None:
        super().__init__()
        self.modal_title = title
        self.body = body
        self.confirm_label = confirm_label

    def compose(self):
        with _ModalFrame(danger=True):
            yield Static(self.modal_title, classes="modal-title")
            yield Static(self.body, classes="modal-body", markup=False)
            yield Static("[y] confirm   [esc] cancel", classes="modal-hint", markup=False)
            with Vertical(classes="modal-buttons"):
                yield Button(self.confirm_label, variant="error", id="ok")
                yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "ok")

    def action_decide(self, confirmed: bool) -> None:
        self.dismiss(bool(confirmed))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "ok")


def format_tool_args(args_json: str, metadata: dict[str, Any] | None = None) -> str:
    """Best-effort pretty text for tool args in modals."""
    import json

    try:
        parsed = json.loads(args_json) if args_json.strip() else {}
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return args_json
