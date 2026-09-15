"""Headless smoke tests for the Spectra TUI (Textual run_test pilot).

A scripted :class:`FakeController` stands in for CLISessionController —
no provider, no runtime. These tests exercise the app wiring that pure
tests cannot: compose/focus, submit → start_agent, queue-while-running,
finish/drain restart, approval modals ("a" → allow_all regression),
interrupt (Ctrl+C) restoring the queue to the input, and /help.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import textual  # noqa: F401
    from textual.widgets import TextArea

    HAVE_TEXTUAL = True
except ImportError:  # pragma: no cover - CI without textual
    HAVE_TEXTUAL = False

from spectra.agent.turn import TurnEvent, TurnEventType  # noqa: E402
from spectra.cli.chat import ChatLog, ToolApprovalRequested  # noqa: E402


class FakeAgentLoop:
    def __init__(self) -> None:
        self.tool_approvals: list[str] = []
        self.user_answers: list[str] = []

    def submit_tool_approval(self, decision: str) -> None:
        self.tool_approvals.append(decision)

    def submit_user_answer(self, answer: str) -> None:
        self.user_answers.append(answer)


class FakeRunner:
    def __init__(self) -> None:
        self.agent_loop = FakeAgentLoop()


class FakeProvider:
    name = "anthropic"
    model = "claude-test"
    api_base = ""


class FakeConfig:
    def __init__(self, config_dir: str) -> None:
        self._config_dir = config_dir
        self.provider = FakeProvider()
        self.disclaimer_accepted = True
        self.shell_auto_approve_limit = 10
        self.checkpoint_auto_save = False

    @property
    def config_path(self) -> str:
        return os.path.join(self._config_dir, "config.json")

    def save(self) -> None:
        pass


class FakeController:
    """Scriptable stand-in for CLISessionController."""

    def __init__(self, config_dir: str) -> None:
        self.config = FakeConfig(config_dir)
        self.events: deque[TurnEvent] = deque()
        self.running = False
        self.started: list[str] = []
        self.queued: list[str] = []
        self.cancelled = 0
        self.finished_calls = 0
        self.saved_sessions: list[str] = []
        self._runner = FakeRunner()
        self._approval_installed = False

    # -- approval wiring (real bridge comes from install_shell_approval) --

    def install_shell_approval(self, presenter, call_from_thread):
        from spectra.cli.approval import ShellApprovalBridge, ShellApprovalState

        self._approval_installed = True
        state = ShellApprovalState(auto_approve_limit=self.config.shell_auto_approve_limit)
        bridge = ShellApprovalBridge()
        bridge.bind(presenter, call_from_thread)
        return state, bridge

    # -- lifecycle --

    def wait_for_runtime(self, timeout: float = 10.0) -> bool:
        return True

    def is_agent_running(self) -> bool:
        return self.running

    def get_runner(self) -> FakeRunner:
        return self._runner if self.running else None

    def start_agent(self, message: str) -> str | None:
        self.started.append(message)
        self.running = True
        return None

    def queue_message(self, text: str) -> None:
        self.queued.append(text)

    def get_event(self, timeout: float = 0):
        if self.events:
            return self.events.popleft()
        return None

    def cancel(self) -> list[str]:
        self.cancelled += 1
        self.running = False
        returned, self.queued = self.queued, []
        return returned

    def on_agent_finished(self) -> list[str]:
        self.finished_calls += 1
        self.running = False
        returned, self.queued = self.queued, []
        return returned

    # -- context --

    def list_skills(self) -> list[dict]:
        return [{"slug": "sqli-audit", "name": "SQLi", "description": ""}]

    def list_available_models(self) -> list[dict]:
        return [{"id": "claude-test", "name": "Claude Test"}]

    def list_sessions(self) -> list[dict]:
        return []

    # -- commands --

    def save_session(self, name: str) -> str:
        self.saved_sessions.append(name)
        return "/tmp/fake-session.json"

    def new_session(self) -> None:
        pass

    def set_model(self, name: str) -> str | None:
        self.config.provider.model = name
        return None


@unittest.skipUnless(HAVE_TEXTUAL, "textual not installed")
class TestTuiApp(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from spectra.cli.app import SpectraApp

        self._tmp = tempfile.TemporaryDirectory()
        self.controller = FakeController(self._tmp.name)
        self.app = SpectraApp(self.controller)
        self._ctx = self.app.run_test(size=(100, 30))
        self.pilot = await self._ctx.__aenter__()
        await self.pilot.pause()
        # Let the pump tick at least once.
        await asyncio.sleep(0.1)
        await self.pilot.pause()

    async def asyncTearDown(self):
        await self._ctx.__aexit__(None, None, None)
        self._tmp.cleanup()

    # -- helpers --

    async def _settle(self, seconds: float = 0.15) -> None:
        """Give the 20 Hz pump a few ticks, then flush the message queue."""
        await asyncio.sleep(seconds)
        await self.pilot.pause()

    async def _type(self, text: str) -> None:
        prompt = self.app.query_one("#prompt-input", TextArea)
        prompt.load_text(text)
        await self.pilot.pause()

    async def _submit(self, text: str) -> None:
        await self._type(text)
        await self.pilot.press("enter")
        await self._settle()

    def chat(self) -> ChatLog:
        return self.app.query_one("#chat-log", ChatLog)

    # -- tests --

    async def test_boot_focus_and_shell_approval_installed(self):
        from spectra.cli.input_area import PromptInput

        self.assertTrue(self.controller._approval_installed)
        prompt = self.app.query_one(PromptInput)
        self.assertTrue(prompt.has_focus)

    async def test_submit_starts_agent_and_adds_user_bubble(self):
        await self._submit("hello agent")
        self.assertEqual(self.controller.started, ["hello agent"])
        self.assertTrue(self.controller.running)
        children = list(self.chat().children)
        self.assertTrue(children, "user bubble missing")

    async def test_start_agent_prepends_working_directory(self):
        # The real controller prepends [Working directory: ...]; the app
        # passes the text through untouched.
        await self._submit("analyze this")
        self.assertTrue(self.controller.started[0].endswith("analyze this"))

    async def test_queue_while_running_then_drain(self):
        await self._submit("first")
        self.assertEqual(self.controller.started, ["first"])
        # Second message queues (agent busy).
        await self._submit("second")
        self.assertEqual(self.controller.queued, ["second"])
        self.assertEqual(self.controller.started, ["first"])  # not started yet
        # Agent finishes: emit text + sentinel state, then stop running.
        self.controller.events.append(TurnEvent.text_done("done answer"))
        self.controller.running = False
        await self._settle(0.3)
        # Drain: 'second' starts as the next run, queue empty again.
        self.assertEqual(self.controller.started, ["first", "second"])
        self.assertEqual(self.controller.queued, [])
        self.assertEqual(self.controller.finished_calls, 1)

    async def test_tool_approval_a_means_allow_all(self):
        """Regression: legacy CLI sent raw "a" which the loop treats as DENY."""
        # Answers need a live runner — the app drops them otherwise.
        self.controller.running = True
        self.controller.events.append(
            TurnEvent(
                type=TurnEventType.TOOL_APPROVAL_REQUEST,
                tool_call_id="c1",
                tool_name="write_file",
                tool_args='{"path": "/tmp/x"}',
                text="Writes a file",
            )
        )
        await self._settle()
        from spectra.cli.modals import ToolApprovalModal

        # The modal is the active screen (screen.query never includes the
        # screen itself, so an IsNotNone query there is vacuous).
        self.assertIsInstance(self.app.screen, ToolApprovalModal)
        await self.pilot.press("a")
        await self._settle()
        self.assertEqual(self.controller._runner.agent_loop.tool_approvals, ["allow_all"])

    async def test_tool_approval_escape_denies(self):
        self.controller.running = True
        self.controller.events.append(
            TurnEvent(
                type=TurnEventType.TOOL_APPROVAL_REQUEST,
                tool_call_id="c2",
                tool_name="shell_command",
                tool_args='{"command": "rm -rf /"}',
                text="Dangerous",
            )
        )
        await self._settle()
        await self.pilot.press("escape")
        await self._settle()
        self.assertEqual(self.controller._runner.agent_loop.tool_approvals, ["deny"])

    async def test_interrupt_returns_queue_to_input(self):
        await self._submit("long running task")
        await self._submit("queued follow-up")
        self.assertEqual(self.controller.queued, ["queued follow-up"])
        await self.pilot.press("ctrl+c")
        await self._settle()
        self.assertEqual(self.controller.cancelled, 1)
        prompt = self.app.query_one("#prompt-input", TextArea)
        self.assertEqual(prompt.text, "queued follow-up")
        # Pump observed finish (running False) → on_agent_finished drained.
        self.assertEqual(self.controller.finished_calls, 1)

    async def test_thinking_toggle(self):
        before = self.app._think_filter.show_thinking
        await self.pilot.press("ctrl+o")
        await self._settle()
        self.assertNotEqual(before, self.app._think_filter.show_thinking)

    async def test_help_command(self):
        await self._submit("/help")
        await self._settle()
        # /help adds a system bubble; nothing crashed and no agent run began.
        self.assertEqual(self.controller.started, [])
        self.assertTrue(len(list(self.chat().children)) >= 1)

    async def test_shell_escape_runs(self):
        await self._submit("!echo tui-shell-ok")
        await self._settle(0.8)
        from spectra.cli.chat import ShellOutput

        outputs = list(self.app.query(ShellOutput))
        self.assertTrue(outputs, "shell output log missing")

    async def test_completion_popup_for_slash(self):
        await self._type("/mo")
        await self._settle()
        popup = self.app.query_one("#completion-popup")
        self.assertIn("visible", popup.classes)
        # Accept with tab: /model + trailing space.
        await self.pilot.press("tab")
        prompt = self.app.query_one("#prompt-input", TextArea)
        self.assertEqual(prompt.text, "/model ")


if __name__ == "__main__":
    unittest.main()
