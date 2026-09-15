"""Approval plumbing for the TUI: pure state, keystroke decisions, bridge.

Three pieces:

- :class:`ShellApprovalState` — ported from the legacy controller's inner
  ``ApprovalState``: safe auto-approve with a command-count limit and a
  reject-all mode. Dangerous commands are never auto-approved.
- :func:`decision_for_keystroke` — maps the approval modal's one-key choices
  to the strings ``AgentLoop._wait_for_approval`` understands. The legacy
  CLI sent a raw ``"a"`` which silently DENIED the call; ``"a"`` must map
  to ``"allow_all"``.
- :class:`ShellApprovalBridge` — the agent-thread side of the shell-approval
  modal. ``shell_tools`` calls :meth:`request` from the agent thread; the
  TUI pushes a modal via ``call_from_thread`` and resolves it. No TUI (or
  TUI shutting down) means deny, never deadlock.
"""

from __future__ import annotations

import threading
from typing import Any, Protocol


class ShellApprovalState:
    """Track shell approval mode with automatic reset after N commands."""

    def __init__(self, auto_approve_limit: int = 10):
        self.safe_auto_approve = False
        self.reject_all = False
        self.command_count = 0  # commands approved in auto-approve mode
        self.auto_approve_limit = auto_approve_limit  # 0 = unlimited

    def reset(self) -> None:
        """Reset all modes back to manual approval."""
        self.safe_auto_approve = False
        self.reject_all = False
        self.command_count = 0

    def increment_command_count(self) -> bool:
        """Increment the count; True when auto-approve just expired."""
        self.command_count += 1
        # Only check limit if limit > 0 (0 means unlimited)
        if self.safe_auto_approve and self.auto_approve_limit > 0 and self.command_count >= self.auto_approve_limit:
            self.safe_auto_approve = False
            self.command_count = 0
            return True
        return False

    def should_auto_approve(self, is_dangerous: bool) -> tuple[bool, bool]:
        """Decide auto-approval for one command.

        Returns ``(approved, expired)``: ``approved`` is the decision,
        ``expired`` flags that the limit fired this call so the UI can say
        so. Dangerous commands are never auto-approved.
        """
        if self.reject_all:
            return False, False
        if not self.safe_auto_approve or is_dangerous:
            return False, False
        expired = self.increment_command_count()
        return (not expired), expired

    def get_status(self) -> str:
        """Current status string for display."""
        if self.reject_all:
            return "Reject all ON"
        if self.safe_auto_approve:
            if self.auto_approve_limit == 0:
                return "Safe auto-approve ON (unlimited)"
            return f"Safe auto-approve ON ({self.command_count}/{self.auto_approve_limit})"
        return "Manual approval"


# Keystroke → AgentLoop approval vocabulary. Anything not listed denies.
_TOOL_DECISIONS = {
    "y": "allow",
    "a": "allow_all",
    "n": "deny",
    "escape": "deny",
}


def decision_for_keystroke(key: str) -> str:
    """Map an approval-modal key to ``allow``/``allow_all``/``deny``.

    Regression guard: the legacy CLI sent a raw ``"a"`` (and "always"),
    which ``AgentLoop._wait_for_approval`` treats as deny — only
    ``allow_all`` enables session-wide always-allow.
    """
    return _TOOL_DECISIONS.get(key.lower(), "deny")


class ApprovalPresenter(Protocol):
    """What the bridge needs from the UI side."""

    def push_shell_approval(
        self, command: str, is_dangerous: bool, danger_reason: str, bridge: ShellApprovalBridge
    ) -> None:
        """Show the shell-approval UI and later call ``bridge.resolve()``."""
        ...


class ShellApprovalBridge:
    """Carries one shell-approval request between agent thread and UI.

    The shell tool invokes :meth:`request` on the agent thread. It pushes
    the modal onto the UI through the presenter (via ``call_from_thread``,
    supplied by the app when it binds) and blocks on an event until the
    user answers or the app unmounts (:meth:`shutdown` denies waiters).
    """

    def __init__(self) -> None:
        self._event = threading.Event()
        self._result: bool | None = None
        self._presenter: ApprovalPresenter | None = None
        self._call_from_thread: Any | None = None  # app.call_from_thread
        self._lock = threading.Lock()

    def bind(self, presenter: ApprovalPresenter, call_from_thread: Any) -> None:
        """Attach the live UI (called from the UI thread on mount)."""
        with self._lock:
            self._presenter = presenter
            self._call_from_thread = call_from_thread

    def unbind(self) -> None:
        """Detach the UI and deny any pending request (app unmount)."""
        with self._lock:
            self._presenter = None
            self._call_from_thread = None
        self.resolve(False)

    def request(self, command: str, is_dangerous: bool, danger_reason: str) -> bool:
        """Ask the user; blocks the agent thread until answered."""
        with self._lock:
            presenter = self._presenter
            call_from_thread = self._call_from_thread
        if presenter is None or call_from_thread is None:
            return False  # no UI → deny rather than hang

        self._event.clear()
        self._result = None
        try:
            call_from_thread(self._present, command, is_dangerous, danger_reason)
        except Exception:
            return False
        # Wait for resolve(); unbind() guarantees this wakes on shutdown.
        self._event.wait()
        return bool(self._result)

    def _present(self, command: str, is_dangerous: bool, danger_reason: str) -> None:
        """Runs on the UI thread: show the modal."""
        presenter = self._presenter
        if presenter is not None:
            presenter.push_shell_approval(command, is_dangerous, danger_reason, self)

    def resolve(self, approved: bool) -> None:
        """UI side: deliver the user's answer and wake the agent thread."""
        self._result = approved
        self._event.set()
