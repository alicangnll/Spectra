"""Persistent CLI input history (JSONL) with legacy readline import.

The legacy CLI stored history with readline in ``~/.spectra_history`` (one
physical line per entry, multi-line input mangled). The TUI stores every
entry — multi-line included — as one JSON line in ``history.jsonl`` inside
the Spectra config directory, importing the legacy file once on first use.
"""

from __future__ import annotations

import json
from pathlib import Path


class InputHistory:
    """Load/add input entries, deduping consecutive repeats."""

    def __init__(self, path: Path | None = None, legacy_path: Path | None = None, max_entries: int = 2000):
        self._path = path
        self._legacy_path = legacy_path
        self._max_entries = max_entries
        self._entries: list[str] = []
        self._loaded = False

    # --- Loading ---

    def load(self) -> list[str]:
        """Load persisted entries (importing legacy history once)."""
        if self._loaded:
            return list(self._entries)
        self._loaded = True

        if self._path is not None and self._path.exists():
            for line in self._path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line).get("input", "")
                except (json.JSONDecodeError, AttributeError):
                    continue
                if isinstance(entry, str) and entry:
                    self._append_unique(entry)
        elif self._legacy_path is not None and self._legacy_path.exists():
            # First run after upgrade: import the readline history once.
            for raw in self._legacy_path.read_text(encoding="utf-8", errors="replace").splitlines():
                entry = raw.rstrip("\n").strip()
                if entry and not entry.startswith("_"):
                    self._append_unique(entry)
            if self._entries:
                self._persist_all()

        return list(self._entries)

    # --- Access ---

    @property
    def entries(self) -> list[str]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, index: int) -> str | None:
        """Entry at ``index`` (0 = newest), or None when out of range."""
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None

    # --- Adding ---

    def add(self, entry: str) -> None:
        """Record a submitted input; consecutive duplicates collapse."""
        if self._append_unique(entry):
            self._persist_append(entry)

    # --- Internals ---

    def _append_unique(self, entry: str) -> bool:
        # Full dedupe with move-to-front: re-submitting an earlier input
        # moves it to the top (most recent use), matching readline-style
        # history after `history -d` cleanup.
        try:
            self._entries.remove(entry)
        except ValueError:
            pass
        self._entries.insert(0, entry)
        del self._entries[self._max_entries :]
        return True

    def _persist_append(self, entry: str) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"input": entry}) + "\n")
        except OSError:
            pass  # history is best-effort; never break input over it

    def _persist_all(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as fh:
                # entries[0] is newest; file is written oldest-first so
                # appending later keeps a consistent order.
                for entry in reversed(self._entries):
                    fh.write(json.dumps({"input": entry}) + "\n")
        except OSError:
            pass


def default_history_paths(config_dir: Path | str | None = None) -> tuple[Path, Path]:
    """Return ``(jsonl_path, legacy_path)``.

    The JSONL store lives in the Spectra config dir (default ``~/.spectra``);
    the legacy readline history always lived at ``~/.spectra_history``.
    """
    base = Path(config_dir) if config_dir else (Path.home() / ".spectra")
    return base / "history.jsonl", Path.home() / ".spectra_history"
