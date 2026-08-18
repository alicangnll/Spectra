"""Tests for spectra.ui.chat_view — pure logic helpers."""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock

from tests.qt_stubs import ensure_pyside6_stubs

ensure_pyside6_stubs()

# Stub all heavy submodules that chat_view imports.
# Reinstall them unconditionally because other tests may have left behind
# incomplete stubs in sys.modules.
for _mod_name in [
    "spectra.agent.turn",
    "spectra.core.types",
]:
    _stub = types.ModuleType(_mod_name)
    # Add commonly-needed attrs
    for _attr in [
        "PlanView",
        "TurnEvent",
        "TurnEventType",
        "Message",
        "Role",
    ]:
        setattr(_stub, _attr, MagicMock())
    sys.modules[_mod_name] = _stub

# Other tests may leave stubbed UI modules behind; force fresh imports.
for _mod_name in [
    "spectra.ui.chat_view",
    "spectra.ui.message_widgets",
    "spectra.ui.plan_view",
    "spectra.ui.tool_widgets",
]:
    sys.modules.pop(_mod_name, None)

from spectra.ui.bulk_renamer import BulkRenamerWidget
from spectra.ui.chat_view import (
    _FIND_BAR_STYLE,
    _TOOL_GROUP_MIN_CALLS,
    ChatView,
    _is_hidden_system_user_message,
)

# ---------------------------------------------------------------------------
# _is_hidden_system_user_message
# ---------------------------------------------------------------------------


class TestIsHiddenSystemUserMessage(unittest.TestCase):
    def test_empty_string_returns_false(self):
        self.assertFalse(_is_hidden_system_user_message(""))

    def test_none_equivalent_empty_returns_false(self):
        self.assertFalse(_is_hidden_system_user_message(""))

    def test_system_prefix_returns_true(self):
        self.assertTrue(_is_hidden_system_user_message("[SYSTEM] some hint"))

    def test_system_prefix_with_leading_whitespace(self):
        self.assertTrue(_is_hidden_system_user_message("   [SYSTEM] some hint"))

    def test_regular_message_returns_false(self):
        self.assertFalse(_is_hidden_system_user_message("Hello world"))

    def test_lowercase_system_returns_false(self):
        self.assertFalse(_is_hidden_system_user_message("[system] hint"))

    def test_partial_system_keyword_returns_false(self):
        self.assertFalse(_is_hidden_system_user_message("SYSTEM"))

    def test_system_in_middle_returns_false(self):
        self.assertFalse(_is_hidden_system_user_message("not [SYSTEM] hint"))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestChatViewConstants(unittest.TestCase):
    def test_tool_group_min_calls_is_positive(self):
        self.assertGreater(_TOOL_GROUP_MIN_CALLS, 0)

    def test_tool_group_min_calls_value(self):
        self.assertEqual(_TOOL_GROUP_MIN_CALLS, 2)


class TestBulkRenamerLookup(unittest.TestCase):
    def test_find_row_prefers_cached_mapping(self):
        widget = object.__new__(BulkRenamerWidget)
        widget._addr_to_row = {0x401000: 7}
        widget._table = MagicMock()
        self.assertEqual(widget._find_row_for_address(0x401000), 7)
        widget._table.rowCount.assert_not_called()


# ---------------------------------------------------------------------------
# Find-in-conversation (Ctrl+F)
# ---------------------------------------------------------------------------


class _SearchableMessage:
    """Minimal stand-in for a message widget exposing search_text()."""

    def __init__(self, text: str):
        self._text = text
        self._style = ""


    def search_text(self) -> str:
        return self._text


    def objectName(self) -> str:
        return "message_user"


    def styleSheet(self) -> str:
        return self._style


    def setStyleSheet(self, style: str) -> None:
        self._style = style


class _FakeLayoutItem:
    def __init__(self, widget):
        self._widget = widget


    def widget(self):
        return self._widget


class _FakeLayout:
    def __init__(self, widgets):
        self._widgets = widgets


    def count(self) -> int:
        return len(self._widgets)


    def itemAt(self, index):
        if 0 <= index < len(self._widgets):
            return _FakeLayoutItem(self._widgets[index])
        return None


def _view_without_qt(layout_widgets):
    """A ChatView instance built via __new__ (no Qt construction)."""
    view = object.__new__(ChatView)
    view._layout = _FakeLayout(layout_widgets)
    view._find_count_label = MagicMock()
    view._find_matches = []
    view._find_index = -1
    view._find_highlight_widget = None
    view._find_highlight_style = None
    view._find_bar = None
    view.ensureWidgetVisible = MagicMock()
    return view


class TestFindInConversation(unittest.TestCase):
    def test_find_methods_exist(self):
        for name in (
            "_open_find_bar",
            "_close_find_bar",
            "_collect_find_matches",
            "_on_find_next",
            "_on_find_prev",
        ):
            self.assertTrue(hasattr(ChatView, name), name)

    def test_find_bar_style_styles_input(self):
        self.assertIn("QLineEdit", _FIND_BAR_STYLE)

    def test_collect_matches_is_case_insensitive_and_ordered(self):
        widgets = [
            _SearchableMessage("Analyze this BINARY"),
            object(),  # not searchable (e.g. tool call widget)
            _SearchableMessage("no match here"),
            _SearchableMessage("binary differs"),
        ]
        view = _view_without_qt(widgets)
        matches = view._collect_find_matches("BiNaRy")
        self.assertEqual(len(matches), 2)
        self.assertIs(matches[0], widgets[0])
        self.assertIs(matches[1], widgets[3])

    def test_collect_matches_empty_query_returns_nothing(self):
        view = _view_without_qt([_SearchableMessage("hello")])
        self.assertEqual(view._collect_find_matches("   "), [])
        self.assertEqual(view._collect_find_matches(""), [])

    def test_text_changed_jumps_to_first_match(self):
        view = _view_without_qt([_SearchableMessage("alpha"), _SearchableMessage("beta alpha")])
        view._on_find_text_changed("alpha")
        self.assertEqual(len(view._find_matches), 2)
        self.assertEqual(view._find_index, 0)
        view._find_count_label.setText.assert_called_with("1/2")

    def test_text_changed_no_match_shows_zero(self):
        view = _view_without_qt([_SearchableMessage("alpha")])
        view._on_find_text_changed("zzz")
        view._find_count_label.setText.assert_called_with("0/0")
        self.assertIsNone(view._find_highlight_widget)

    def test_next_and_prev_wrap_around(self):
        view = _view_without_qt([_SearchableMessage("x"), _SearchableMessage("x")])
        view._on_find_text_changed("x")
        view._on_find_next()  # 0 -> 1
        self.assertEqual(view._find_index, 1)
        view._on_find_next()  # 1 -> wraps to 0
        self.assertEqual(view._find_index, 0)
        view._on_find_prev()  # 0 -> wraps to 1
        self.assertEqual(view._find_index, 1)

    def test_close_clears_state(self):
        view = _view_without_qt([_SearchableMessage("x")])
        view._on_find_text_changed("x")
        view._close_find_bar()
        self.assertEqual(view._find_matches, [])
        self.assertEqual(view._find_index, -1)
        self.assertIsNone(view._find_highlight_widget)


if __name__ == "__main__":
    unittest.main()
