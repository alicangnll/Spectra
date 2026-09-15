"""Tests for TUI approval state, keystroke decisions, and the bridge (pure)."""

from __future__ import annotations

import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.cli.approval import ShellApprovalBridge, ShellApprovalState, decision_for_keystroke


class TestShellApprovalState(unittest.TestCase):
    def test_defaults_are_manual(self):
        state = ShellApprovalState()
        self.assertEqual(state.get_status(), "Manual approval")
        self.assertFalse(state.safe_auto_approve)
        self.assertFalse(state.reject_all)

    def test_safe_mode_auto_approves_and_counts(self):
        state = ShellApprovalState(auto_approve_limit=3)
        state.safe_auto_approve = True
        approved, expired = state.should_auto_approve(False)
        self.assertTrue(approved)
        self.assertFalse(expired)
        self.assertEqual(state.command_count, 1)
        self.assertIn("1/3", state.get_status())

    def test_dangerous_never_auto_approved(self):
        state = ShellApprovalState(auto_approve_limit=3)
        state.safe_auto_approve = True
        approved, _expired = state.should_auto_approve(True)
        self.assertFalse(approved)
        self.assertEqual(state.command_count, 0)  # not even counted

    def test_limit_expires_auto_approve(self):
        state = ShellApprovalState(auto_approve_limit=2)
        state.safe_auto_approve = True
        self.assertTrue(state.should_auto_approve(False)[0])
        approved, expired = state.should_auto_approve(False)
        self.assertFalse(approved)  # the expiring command is NOT approved
        self.assertTrue(expired)
        self.assertEqual(state.get_status(), "Manual approval")
        self.assertEqual(state.command_count, 0)

    def test_zero_limit_means_unlimited(self):
        state = ShellApprovalState(auto_approve_limit=0)
        state.safe_auto_approve = True
        for _ in range(50):
            approved, expired = state.should_auto_approve(False)
            self.assertTrue(approved)
            self.assertFalse(expired)
        self.assertIn("unlimited", state.get_status())

    def test_reject_all_blocks_everything(self):
        state = ShellApprovalState()
        state.safe_auto_approve = True
        state.reject_all = True
        approved, _expired = state.should_auto_approve(False)
        self.assertFalse(approved)
        self.assertEqual(state.get_status(), "Reject all ON")

    def test_reset_clears_modes(self):
        state = ShellApprovalState()
        state.safe_auto_approve = True
        state.command_count = 4
        state.reject_all = True
        state.reset()
        self.assertEqual(state.get_status(), "Manual approval")
        self.assertEqual(state.command_count, 0)

    def test_increment_command_count_expiry_signal(self):
        state = ShellApprovalState(auto_approve_limit=1)
        state.safe_auto_approve = True
        self.assertTrue(state.increment_command_count())
        self.assertFalse(state.safe_auto_approve)


class TestDecisionForKeystroke(unittest.TestCase):
    def test_y_maps_to_allow(self):
        self.assertEqual(decision_for_keystroke("y"), "allow")

    def test_a_maps_to_allow_all_regression(self):
        """The legacy CLI sent a raw "a" which AgentLoop treats as DENY."""
        self.assertEqual(decision_for_keystroke("a"), "allow_all")

    def test_n_and_escape_map_to_deny(self):
        self.assertEqual(decision_for_keystroke("n"), "deny")
        self.assertEqual(decision_for_keystroke("escape"), "deny")

    def test_unknown_keys_deny(self):
        for key in ("", "x", "q", "always", "yes"):
            self.assertEqual(decision_for_keystroke(key), "deny", key)


class _FakePresenter:
    def __init__(self, approve_after: float):
        self._approve_after = approve_after
        self.seen: list[tuple] = []

    def push_shell_approval(self, command, is_dangerous, danger_reason, bridge):
        self.seen.append((command, is_dangerous, danger_reason))

        def answer():
            bridge.resolve(True)

        threading.Timer(self._approve_after, answer).start()


class TestShellApprovalBridge(unittest.TestCase):
    def _bound_bridge(self, presenter):
        bridge = ShellApprovalBridge()
        # Simulate the app: call_from_thread runs the callable immediately.
        bridge.bind(presenter, lambda fn, *a, **k: fn(*a, **k))
        return bridge

    def test_request_returns_user_decision(self):
        presenter = _FakePresenter(approve_after=0.01)
        bridge = self._bound_bridge(presenter)
        approved = bridge.request("ls -la", False, "")
        self.assertTrue(approved)
        self.assertEqual(presenter.seen, [("ls -la", False, "")])

    def test_request_denies_without_ui(self):
        bridge = ShellApprovalBridge()  # never bound
        self.assertFalse(bridge.request("rm -rf /", True, "destructive"))

    def test_unbind_denies_waiters(self):
        presenter = _FakePresenter(approve_after=60)  # user never answers
        bridge = self._bound_bridge(presenter)

        result: list[bool] = []
        thread = threading.Thread(target=lambda: result.append(bridge.request("ls", False, "")))
        thread.start()

        bridge.unbind()  # app unmounts while agent waits
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [False])

    def test_unbind_detaches_presenter(self):
        bridge = self._bound_bridge(_FakePresenter(0.0))
        bridge.unbind()
        self.assertFalse(bridge.request("ls", False, ""))


if __name__ == "__main__":
    unittest.main()
