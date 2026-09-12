"""Tests for iris.ui.session_controller."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.mocks.ida_mock import install_ida_mocks

install_ida_mocks()

# Some UI tests stub modules in sys.modules; ensure this test gets real ones.
for _mod_name in [
    "spectra.core.types",
    "spectra.core.config",
    "spectra.core.logging",
    "spectra.agent.turn",
    "spectra.agent.mutation",
    "spectra.providers.auth_cache",
    "spectra.providers.anthropic_provider",
    "spectra.providers.ollama_provider",
    "spectra.providers.registry",
    "spectra.ui.chat_view",
    "spectra.ui.context_bar",
    "spectra.ui.input_area",
    "spectra.ui.styles",
    "spectra.ui.tool_widgets",
]:
    sys.modules.pop(_mod_name, None)

from spectra.agent.loop import AgentLoop, BackgroundAgentRunner
from spectra.core.config import SpectraConfig
from spectra.core.types import (
    Message,
    ProviderCapabilities,
    Role,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolResult,
)
from spectra.ida.ui.session_controller import IdaSessionController
from spectra.providers.base import LLMProvider
from spectra.tools.registry import ToolRegistry


class _AskUserProvider(LLMProvider):
    """Stub provider whose single response is an ask_user tool call.

    The agent loop parks in _wait_for_queue waiting for the user's answer,
    which is the state a "Clear Context" hit has to interrupt cleanly.
    """

    def __init__(self):
        super().__init__(api_key="test", model="stub-model")

    @property
    def name(self) -> str:
        return "stub"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    def _get_client(self):
        return None

    def _fetch_models_live(self):
        return []

    @staticmethod
    def _builtin_models():
        return []

    def _format_messages(self, messages):
        return messages

    def _normalize_response(self, raw):
        return raw

    def _build_request_kwargs(self, messages, tools, temperature, max_tokens, system):
        return {}

    def _call_api(self, client, kwargs):
        return None

    def _handle_api_error(self, e):
        raise e

    def _stream_chunks(self, client, kwargs):
        yield from ()

    def chat(self, messages, tools=None, temperature=0.3, max_tokens=4096, system=""):
        return Message(role=Role.ASSISTANT, content="ok")

    def chat_stream(self, messages, tools=None, temperature=0.3, max_tokens=4096, system=""):
        yield StreamChunk(is_tool_call_start=True, tool_call_id="call_ask", tool_name="ask_user")
        yield StreamChunk(tool_args_delta='{"question": "continue?"}', tool_call_id="call_ask")
        yield StreamChunk(is_tool_call_end=True, tool_call_id="call_ask", tool_name="ask_user")
        yield StreamChunk(usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2))


class _FinishProvider(_AskUserProvider):
    """Stub provider whose single response is plain text — the run
    completes immediately instead of parking on ask_user."""

    def chat_stream(self, messages, tools=None, temperature=0.3, max_tokens=4096, system=""):
        yield StreamChunk(text="done")
        yield StreamChunk(usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2))


class TestIdaSessionController(unittest.TestCase):
    def setUp(self):
        self.cfg = SpectraConfig()
        self.cfg._config_dir = tempfile.mkdtemp()
        self.ctrl = IdaSessionController(self.cfg)

    def tearDown(self):
        self.ctrl.shutdown()

    def test_initial_session_state(self):
        self.assertIsNotNone(self.ctrl.session)
        self.assertEqual(self.ctrl.session.provider_name, self.cfg.provider.name)
        self.assertEqual(self.ctrl.session.model_name, self.cfg.provider.model)

    def test_is_agent_running_initially_false(self):
        self.assertFalse(self.ctrl.is_agent_running)

    def test_get_event_without_runner_returns_none(self):
        self.assertIsNone(self.ctrl.get_event())

    def test_queue_and_drain_messages(self):
        self.ctrl.queue_message("first")
        self.ctrl.queue_message("second")

        # on_agent_finished drains the queue, oldest first
        self.assertEqual(self.ctrl.on_agent_finished(), ["first", "second"])

        # Subsequent calls return an empty list (queue was drained)
        self.assertEqual(self.ctrl.on_agent_finished(), [])

    def test_cancel_clears_pending_messages(self):
        self.ctrl.queue_message("will be cancelled")
        self.ctrl.cancel()
        self.assertEqual(self.ctrl.on_agent_finished(), [])

    def test_new_chat_creates_fresh_session(self):
        old_id = self.ctrl.session.id
        self.ctrl.session.add_message(Message(role=Role.USER, content="hello"))
        self.ctrl.new_chat()

        self.assertNotEqual(self.ctrl.session.id, old_id)
        self.assertEqual(len(self.ctrl.session.messages), 0)

    def test_new_chat_clears_pending_messages(self):
        self.ctrl.queue_message("pending")
        self.ctrl.new_chat()
        self.assertEqual(self.ctrl.on_agent_finished(), [])

    def test_queued_message_runs_after_agent_finishes(self):
        """Regression: a message queued while the agent runs must be
        processed as soon as the agent finishes its answer — previously
        on_agent_finished discarded the queue, so queued messages sat in
        the UI forever and were never answered.
        """
        self.cfg.auto_context = False
        with patch.object(
            self.ctrl._provider_registry, "get_or_create", return_value=_FinishProvider()
        ):
            self.assertIsNone(self.ctrl.start_agent("first question"))
            tab = self.ctrl.active_tab_id
            runner = self.ctrl._runners[tab]

            # User queues follow-ups while the agent is still working
            self.ctrl.queue_message("follow-up one")
            self.ctrl.queue_message("follow-up two")

            # Agent finishes its answer → queue drains, oldest first
            runner._thread.join(timeout=5.0)
            self.assertFalse(runner._thread.is_alive())
            self.assertTrue(
                any(m.content == "done" for m in self.ctrl.session.messages),
                "first run never produced its answer",
            )
            queued = self.ctrl.on_agent_finished()
            self.assertEqual(queued, ["follow-up one", "follow-up two"])

            # The drained message immediately starts the next run
            self.assertIsNone(self.ctrl.start_agent(queued[0]))
            next_runner = self.ctrl._runners[tab]
            next_runner._thread.join(timeout=5.0)
            self.assertFalse(next_runner._thread.is_alive())

    def test_new_chat_cancels_running_agent(self):
        """Regression: Clear Context must cancel the tab's running agent.

        The runner's AgentLoop holds a reference to the OLD session — if it
        is left alive it keeps streaming the cleared conversation and can
        answer follow-ups from the old context.
        """
        runner = MagicMock()
        runner.agent_loop.is_running = True
        self.ctrl._runners[self.ctrl.active_tab_id] = runner

        self.ctrl.new_chat()

        runner.cancel.assert_called_once()
        self.assertNotIn(self.ctrl.active_tab_id, self.ctrl._runners)
        self.assertFalse(self.ctrl.is_agent_running)
        self.assertEqual(len(self.ctrl.session.messages), 0)

    def test_new_chat_stops_agent_blocked_on_ask_user(self):
        """A live agent parked on ask_user must terminate after new_chat().

        Previously the loop kept waiting on the answer queue with the old
        session, so the next user message could be routed into the cleared
        conversation.
        """
        import time

        self.cfg.auto_context = False
        loop = AgentLoop(
            _AskUserProvider(),
            ToolRegistry(),
            self.cfg,
            self.ctrl.session,
            host_name="test",
        )
        runner = BackgroundAgentRunner(loop)
        runner.start("hello?")
        self.ctrl._runners[self.ctrl.active_tab_id] = runner

        # Wait until the loop is running (parked in ask_user's answer wait)
        deadline = time.time() + 5.0
        while not loop.is_running and time.time() < deadline:
            time.sleep(0.02)
        self.assertTrue(loop.is_running)

        self.ctrl.new_chat()

        runner._thread.join(timeout=5.0)
        self.assertFalse(runner._thread.is_alive())
        self.assertFalse(loop.is_running)
        # Session is fresh: the cleared run's messages are gone
        self.assertEqual(len(self.ctrl.session.messages), 0)

    def test_update_settings_syncs_session(self):
        self.cfg.provider.name = "test_provider"
        self.cfg.provider.model = "test_model"
        self.ctrl.update_settings()

        self.assertEqual(self.ctrl.session.provider_name, "test_provider")
        self.assertEqual(self.ctrl.session.model_name, "test_model")

    def test_skill_slugs_returns_list(self):
        slugs = self.ctrl.skill_slugs
        self.assertIsInstance(slugs, list)

    def test_on_agent_finished_auto_saves(self):
        self.cfg.checkpoint_auto_save = True
        self.ctrl.session.add_message(Message(role=Role.USER, content="test"))
        self.ctrl.on_agent_finished()

        # Verify session was saved to disk
        from spectra.state.history import SessionHistory

        history = SessionHistory(self.cfg)
        sessions = history.list_sessions(db_instance_id=self.ctrl._db_instance_id)
        self.assertTrue(any(s["id"] == self.ctrl.session.id for s in sessions))

    def test_restore_session(self):
        # Save a session first
        self.ctrl.session.add_message(Message(role=Role.USER, content="persisted"))
        self.cfg.checkpoint_auto_save = True
        self.ctrl.on_agent_finished()
        saved_id = self.ctrl.session.id

        # New chat, then restore
        self.ctrl.new_chat()
        self.assertNotEqual(self.ctrl.session.id, saved_id)

        restored = self.ctrl.restore_session()
        self.assertIsNotNone(restored)
        self.assertEqual(self.ctrl.session.id, saved_id)
        self.assertEqual(len(self.ctrl.session.messages), 1)
        self.assertEqual(self.ctrl.session.messages[0].content, "persisted")

    def test_restore_sessions_disabled_but_sessions_persist(self):
        """restore_sessions() intentionally returns [] (closed tabs must stay
        closed), but auto-saved sessions remain on disk and loadable."""
        self.ctrl.session.add_message(Message(role=Role.USER, content="persisted one"))
        self.cfg.checkpoint_auto_save = True
        self.ctrl.on_agent_finished()

        self.ctrl.new_chat()
        self.ctrl.session.add_message(Message(role=Role.USER, content="persisted two"))
        self.ctrl.on_agent_finished()

        # Both sessions were persisted to disk...
        from spectra.state.history import SessionHistory

        history = SessionHistory(self.cfg)
        sessions = history.list_sessions(db_instance_id=self.ctrl._db_instance_id)
        self.assertEqual(len(sessions), 2)
        self.assertTrue(all(s.get("message_count", 1) >= 0 for s in sessions))

        # ...but bulk auto-restore stays disabled by design.
        ctrl2 = IdaSessionController(self.cfg)
        restored = ctrl2.restore_sessions()
        self.assertEqual(restored, [])
        ctrl2.shutdown()

    def test_restore_preserves_token_usage(self):
        """Full round-trip: save with token usage -> restore -> verify preserved."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        self.ctrl.session.add_message(Message(role=Role.USER, content="question"))
        self.ctrl.session.add_message(
            Message(role=Role.ASSISTANT, content="answer", token_usage=usage),
        )
        self.cfg.checkpoint_auto_save = True
        self.ctrl.on_agent_finished()
        saved_id = self.ctrl.session.id

        # Create fresh controller to avoid in-memory state
        ctrl2 = IdaSessionController(self.cfg)
        restored = ctrl2.restore_session()
        self.assertIsNotNone(restored)
        self.assertEqual(restored.id, saved_id)
        self.assertEqual(len(restored.messages), 2)
        self.assertEqual(restored.messages[1].content, "answer")
        ctrl2.shutdown()

    def test_restore_preserves_tool_calls(self):
        """Full round-trip: save with tool calls -> restore -> verify preserved."""
        tc = ToolCall(id="tc_1", name="get_info", arguments={"addr": "0x1000"})
        tr = ToolResult(tool_call_id="tc_1", name="get_info", content="data here")
        self.ctrl.session.add_message(Message(role=Role.USER, content="analyze"))
        self.ctrl.session.add_message(
            Message(role=Role.ASSISTANT, content="", tool_calls=[tc]),
        )
        self.ctrl.session.add_message(Message(role=Role.TOOL, tool_results=[tr]))
        self.cfg.checkpoint_auto_save = True
        self.ctrl.on_agent_finished()

        ctrl2 = IdaSessionController(self.cfg)
        restored = ctrl2.restore_session()
        self.assertIsNotNone(restored)
        self.assertEqual(len(restored.messages), 3)
        self.assertEqual(len(restored.messages[1].tool_calls), 1)
        self.assertEqual(restored.messages[1].tool_calls[0].name, "get_info")
        self.assertEqual(restored.messages[2].tool_results[0].content, "data here")
        ctrl2.shutdown()

    def test_runtime_init_skips_external_mcp_discovery_when_none_enabled(self):
        self.ctrl.shutdown()

        with patch.object(self.cfg, "enabled_external_mcp", []):
            with patch("spectra.core.external_sources.discover_all_external_mcp") as discover_mcp:
                ctrl = IdaSessionController(self.cfg)
                ctrl._runtime_init_done.wait(timeout=5.0)
                ctrl.shutdown()

        self.assertFalse(discover_mcp.called)

    def test_runtime_init_discovers_external_mcp_when_enabled(self):
        self.ctrl.shutdown()

        with patch.object(self.cfg, "enabled_external_mcp", ["claude:test"]):
            with patch(
                "spectra.core.external_sources.discover_all_external_mcp", return_value={"claude": [], "codex": []}
            ) as discover_mcp:
                ctrl = IdaSessionController(self.cfg)
                ctrl._runtime_init_done.wait(timeout=5.0)
                ctrl.shutdown()

        self.assertTrue(discover_mcp.called)

    def test_shutdown_is_idempotent(self):
        self.ctrl.shutdown()
        self.ctrl.shutdown()  # Should not raise

    def test_fork_session_copies_messages(self):
        """Forking should create a new tab with a deep copy of messages."""
        self.ctrl.session.add_message(Message(role=Role.USER, content="hello"))
        self.ctrl.session.add_message(Message(role=Role.ASSISTANT, content="hi"))
        source_tab = self.ctrl.active_tab_id

        new_tab_id = self.ctrl.fork_session(source_tab)
        self.assertIsNotNone(new_tab_id)
        self.assertNotEqual(new_tab_id, source_tab)

        forked = self.ctrl._sessions[new_tab_id]
        self.assertEqual(len(forked.messages), 2)
        self.assertEqual(forked.messages[0].content, "hello")
        self.assertEqual(forked.messages[1].content, "hi")
        self.assertNotEqual(forked.id, self.ctrl.session.id)

    def test_fork_session_deep_copies(self):
        """Modifications to forked session should not affect the original."""
        self.ctrl.session.add_message(Message(role=Role.USER, content="original"))
        source_tab = self.ctrl.active_tab_id

        new_tab_id = self.ctrl.fork_session(source_tab)
        forked = self.ctrl._sessions[new_tab_id]
        forked.add_message(Message(role=Role.USER, content="forked-only"))

        self.assertEqual(len(self.ctrl.session.messages), 1)
        self.assertEqual(len(forked.messages), 2)

    def test_fork_nonexistent_tab_returns_none(self):
        result = self.ctrl.fork_session("nonexistent")
        self.assertIsNone(result)

    def test_fork_records_metadata(self):
        """Forked session should have forked_from metadata."""
        source_tab = self.ctrl.active_tab_id
        source_id = self.ctrl.session.id

        new_tab_id = self.ctrl.fork_session(source_tab)
        forked = self.ctrl._sessions[new_tab_id]
        self.assertEqual(forked.metadata.get("forked_from"), source_id)


if __name__ == "__main__":
    unittest.main()
