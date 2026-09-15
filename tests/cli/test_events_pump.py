"""Tests for the pure TurnEvent → ChatSink mapper (no Textual needed)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.agent.turn import TurnEvent, TurnEventType
from spectra.cli.events import EventMapper, RecordingSink
from spectra.core.types import TokenUsage


def _names(sink: RecordingSink) -> list[str]:
    return [call[0] for call in sink.calls]


class TestTextMapping(unittest.TestCase):
    def test_think_split_tag_only_visible_passed(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.begin_run()
        mapper.handle(TurnEvent.text_delta("<thi"))
        mapper.handle(TurnEvent.text_delta("nk>secret</th"))
        mapper.handle(TurnEvent.text_delta("ink>answer"))
        mapper.handle(TurnEvent.text_done("<think>secret</think>answer"))

        deltas = [c for c in sink.calls if c[0] == "on_text_delta"]
        self.assertEqual("".join(d[1] for d in deltas), "answer")
        done = sink.last("on_text_done")
        self.assertEqual(done[1], "answer")

    def test_thinking_captured_not_forwarded_as_text(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.begin_run()
        mapper.handle(TurnEvent.text_delta("<think>hidden</think>visible"))
        self.assertNotIn("on_thinking", _names(sink))  # display off by default
        mapper.handle(TurnEvent.text_done("<think>hidden</think>visible"))
        done = sink.last("on_text_done")
        self.assertEqual(done[1], "visible")

    def test_visible_trailing_angle_bracket_recovered_on_done(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.begin_run()
        mapper.handle(TurnEvent.text_delta("5 < 6 <"))
        mapper.handle(TurnEvent.text_done("5 < 6 <"))
        self.assertEqual(sink.last("on_text_done")[1], "5 < 6 <")

    def test_text_done_resets_segment_for_next_turn(self):
        """TEXT_DONE fires per LLM turn; the second turn's done event must
        carry only the second turn's text (not the run total)."""
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.begin_run()
        mapper.handle(TurnEvent.text_delta("first answer"))
        mapper.handle(TurnEvent.text_done("first answer"))
        mapper.handle(TurnEvent.tool_call_start("c1", "search_files"))
        mapper.handle(TurnEvent.text_delta("second answer"))
        mapper.handle(TurnEvent.text_done("second answer"))
        dones = [c for c in sink.calls if c[0] == "on_text_done"]
        self.assertEqual([d[1] for d in dones], ["first answer", "second answer"])

    def test_finish_run_closes_unclosed_think(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.begin_run()
        mapper.handle(TurnEvent.text_delta("<think>truncated"))
        mapper.finish_run()
        self.assertEqual(mapper.think_filter.last_thinking, "truncated")

    def test_begin_run_resets_state(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.begin_run()
        mapper.handle(TurnEvent.text_delta("first"))
        mapper.begin_run()
        self.assertEqual(mapper.visible_text, "")


class TestToolMapping(unittest.TestCase):
    def test_tool_block_lifecycle_order(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.handle(TurnEvent.tool_call_start("call_1", "search_files"))
        mapper.handle(TurnEvent.tool_call_args_delta("call_1", '{"pattern":'))
        mapper.handle(TurnEvent.tool_call_done("call_1", "search_files", '{"pattern": "main"}'))
        mapper.handle(
            TurnEvent.tool_result_event("call_1", "search_files", "3 hits", is_error=False)
        )

        self.assertEqual(
            _names(sink),
            [
                "on_tool_start",
                "on_tool_args_delta",
                "on_tool_done",
                "on_tool_result",
            ],
        )
        self.assertEqual(sink.calls[0], ("on_tool_start", "call_1", "search_files"))
        self.assertEqual(sink.calls[2], ("on_tool_done", "call_1", "search_files", '{"pattern": "main"}'))
        self.assertEqual(sink.calls[3], ("on_tool_result", "call_1", "search_files", "3 hits", False))

    def test_usage_update_forwarded(self):
        sink = RecordingSink()
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        EventMapper(sink).handle(TurnEvent.usage_update(usage))
        self.assertEqual(sink.last("on_usage")[1], usage)

    def test_error_and_cancelled(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.handle(TurnEvent.error_event("boom"))
        mapper.handle(TurnEvent.cancelled_event())
        self.assertEqual(sink.last("on_error")[1], "boom")
        self.assertIn("on_cancelled", _names(sink))


class TestInteractionMapping(unittest.TestCase):
    def test_user_question_payload(self):
        sink = RecordingSink()
        EventMapper(sink).handle(TurnEvent.user_question("continue?", ["Yes", "No"], "call_9", allow_text=True))
        self.assertEqual(
            sink.last("on_question"),
            ("on_question", "continue?", ["Yes", "No"], True, "call_9"),
        )

    def test_tool_approval_payload(self):
        sink = RecordingSink()
        EventMapper(sink).handle(
            TurnEvent.tool_approval_request("call_2", "shell_command", '{"command": "ls"}', "Run ls")
        )
        self.assertEqual(
            sink.last("on_tool_approval"),
            ("on_tool_approval", "call_2", "shell_command", '{"command": "ls"}', "Run ls"),
        )

    def test_plan_lifecycle(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.handle(TurnEvent.plan_generated(["step one", "step two"]))
        mapper.handle(TurnEvent.plan_step_start(0, "step one"))
        mapper.handle(TurnEvent.plan_step_done(0, "done"))
        self.assertEqual(sink.last("on_plan"), ("on_plan", ["step one", "step two"]))
        self.assertEqual(sink.calls[-2], ("on_plan_step", 0, "step one", False))
        self.assertEqual(sink.calls[-1], ("on_plan_step", 0, "done", True))

    def test_save_approval_and_outcomes(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.handle(
            TurnEvent.save_approval_request(patch_count=2, total_bytes=8, all_verified=True)
        )
        mapper.handle(TurnEvent.save_completed(2, 8))
        mapper.handle(TurnEvent.save_discarded(2, rolled_back=True))
        approval = sink.last("on_save_approval")
        self.assertEqual(approval[1], "2 patches ready (8 bytes modified)")
        self.assertEqual(approval[2]["patch_count"], 2)
        self.assertIn("on_save_completed", _names(sink))
        self.assertIn("on_save_discarded", _names(sink))


class TestMiscEvents(unittest.TestCase):
    def test_subagent_statuses(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.handle(TurnEvent.subagent_spawned("a1", "scanner", "explore", "scan imports"))
        mapper.handle(TurnEvent.subagent_completed("a1", "scanner", "found 3", turn_count=2))
        mapper.handle(TurnEvent.subagent_failed("a2", "pwner", "no memory"))
        self.assertEqual(
            sink.last("on_subagent"),
            ("on_subagent", "failed", "pwner", "no memory"),
        )
        self.assertEqual(
            [c[1] for c in sink.calls if c[0] == "on_subagent"],
            ["spawned", "completed", "failed"],
        )

    def test_phase_change_and_finding(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        mapper.handle(TurnEvent.exploration_phase_change("explore", "plan", "enough data"))
        mapper.handle(TurnEvent.exploration_finding("import_usage", "uses OpenSSL", 0x401000))
        self.assertEqual(
            sink.last("on_phase_change"),
            ("on_phase_change", "explore", "plan", "enough data"),
        )
        finding = sink.last("on_finding")
        self.assertEqual(finding[1], "uses OpenSSL")
        self.assertEqual(finding[2]["address"], "0x401000")

    def test_mutation_recorded(self):
        sink = RecordingSink()
        EventMapper(sink).handle(
            TurnEvent(
                type=TurnEventType.MUTATION_RECORDED,
                tool_name="write_file",
                text="wrote notes.md",
                metadata={"reversible": True},
            )
        )
        call = sink.last("on_mutation")
        self.assertEqual(call[1], "write_file")
        self.assertEqual(call[2], "wrote notes.md")

    def test_unknown_event_type_ignored(self):
        sink = RecordingSink()
        mapper = EventMapper(sink)
        # A future event type the TUI hasn't learned yet (dataclass fields
        # are not validated, so a raw string type simulates this).
        mapper.handle(TurnEvent(type="future_thing"))
        self.assertEqual(sink.calls, [])


if __name__ == "__main__":
    unittest.main()
