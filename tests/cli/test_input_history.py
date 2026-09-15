"""Tests for CLI input history persistence (pure)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.cli.history import InputHistory, default_history_paths


class TestInputHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _paths(self):
        return self.base / "history.jsonl", self.base / ".spectra_history"

    def test_add_and_navigate(self):
        jsonl, _legacy = self._paths()
        hist = InputHistory(path=jsonl)
        hist.add("first")
        hist.add("second")
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist.get(0), "second")  # newest first
        self.assertEqual(hist.get(1), "first")
        self.assertIsNone(hist.get(5))

    def test_consecutive_duplicates_collapse(self):
        jsonl, _legacy = self._paths()
        hist = InputHistory(path=jsonl)
        hist.add("same")
        hist.add("same")
        self.assertEqual(len(hist), 1)

    def test_non_consecutive_duplicate_moves_to_front(self):
        jsonl, _legacy = self._paths()
        hist = InputHistory(path=jsonl)
        hist.add("a")
        hist.add("b")
        hist.add("a")
        self.assertEqual(hist.entries, ["a", "b"])  # 'a' moved to top, not duplicated

    def test_jsonl_roundtrip_preserves_multiline(self):
        jsonl, _legacy = self._paths()
        hist = InputHistory(path=jsonl)
        hist.add("line one\nline two\n")
        reloaded = InputHistory(path=jsonl)
        self.assertEqual(reloaded.load(), ["line one\nline two\n"])

    def test_jsonl_roundtrip_preserves_order(self):
        jsonl, _legacy = self._paths()
        hist = InputHistory(path=jsonl)
        for entry in ("one", "two", "three"):
            hist.add(entry)
        reloaded = InputHistory(path=jsonl)
        self.assertEqual(reloaded.load(), ["three", "two", "one"])

    def test_corrupt_json_lines_skipped(self):
        jsonl, _legacy = self._paths()
        jsonl.parent.mkdir(parents=True, exist_ok=True)
        jsonl.write_text('{"input": "good"}\nnot json\n{"input": "also good"}\n', encoding="utf-8")
        hist = InputHistory(path=jsonl)
        self.assertEqual(hist.load(), ["also good", "good"])

    def test_legacy_history_imported_once(self):
        jsonl, legacy = self._paths()
        legacy.write_text("old one\nold two\nold one\n_x\n", encoding="utf-8")
        hist = InputHistory(path=jsonl, legacy_path=legacy)
        entries = hist.load()
        # readline order is oldest→newest; newest ('old one', re-used) ends
        # up on top, the readline-internal "_x" entry is skipped
        self.assertEqual(entries, ["old one", "old two"])
        # The import persisted to JSONL...
        self.assertTrue(jsonl.exists())
        # ...and later legacy additions are NOT re-imported (jsonl wins).
        legacy.write_text("old one\nold two\nNEW ENTRY\n", encoding="utf-8")
        reloaded = InputHistory(path=jsonl, legacy_path=legacy)
        self.assertEqual(reloaded.load(), ["old one", "old two"])

    def test_no_legacy_file_no_import(self):
        jsonl, legacy = self._paths()
        hist = InputHistory(path=jsonl, legacy_path=legacy)
        self.assertEqual(hist.load(), [])
        self.assertFalse(jsonl.exists())

    def test_max_entries_cap(self):
        jsonl, _legacy = self._paths()
        hist = InputHistory(path=jsonl, max_entries=3)
        for i in range(10):
            hist.add(f"entry {i}")
        self.assertEqual(len(hist), 3)
        self.assertEqual(hist.entries[0], "entry 9")


class TestDefaultPaths(unittest.TestCase):
    def test_paths_use_config_dir_and_home_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            jsonl, legacy = default_history_paths(tmp)
            self.assertEqual(jsonl, Path(tmp) / "history.jsonl")
        # legacy always comes from $HOME regardless of config dir
        jsonl, legacy = default_history_paths("/tmp/custom")
        self.assertEqual(legacy, Path.home() / ".spectra_history")


if __name__ == "__main__":
    unittest.main()
