"""Completion sources for the prompt input (pure, no Textual).

:class:`compute` decides which completion items to offer for the current
input line: slash commands, skill invocations, and contextual arguments
(model names, session ids). Items carry the *full replacement line* so the
input widget can accept them blindly.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .commands import COMMAND_SPECS, CommandSpec

MAX_ITEMS = 12


@dataclass(frozen=True)
class CompletionItem:
    insert: str  # full input line after accepting this item
    label: str  # left-hand display text
    hint: str = ""  # right-hand muted hint (usage/help)


def fuzzy_match(query: str, candidate: str) -> bool:
    """Case-insensitive subsequence match ('md' matches 'model')."""
    query, candidate = query.casefold(), candidate.casefold()
    if not query:
        return True
    it = iter(candidate)
    return all(ch in it for ch in query)


def _rank(query: str, name: str) -> tuple[int, str]:
    """Sort key: prefix matches first, then alphabetical."""
    return (0 if name.casefold().startswith(query.casefold()) else 1, name)


def _command_items(query: str, specs: Sequence[CommandSpec]) -> list[CompletionItem]:
    items: list[tuple[str, str, str, str]] = []
    for spec in specs:
        for name in spec.names:
            if fuzzy_match(query, name):
                items.append((name, f"/{name}", spec.display(), name))
    # One item per spec (prefer the canonical word, not every alias)
    seen: set[str] = set()
    deduped: list[tuple[str, str, str, str]] = []
    for name, label, hint, _ in sorted(items, key=lambda t: _rank(query, t[0])):
        if hint not in seen:
            seen.add(hint)
            deduped.append((name, label, hint, name))
    return [CompletionItem(insert=f"/{name} ", label=label, hint=hint) for name, label, hint, _ in deduped]


def _skill_items(query: str, skills: Iterable[str]) -> list[CompletionItem]:
    matched = [s for s in skills if fuzzy_match(query, s)]
    return [
        CompletionItem(insert=f"/{slug} ", label=f"/{slug}", hint="skill")
        for slug in sorted(matched, key=lambda s: _rank(query, s))
    ]


def compute(
    line: str,
    *,
    skills: Sequence[str] = (),
    models: Sequence[str] = (),
    sessions: Sequence[tuple[str, str]] = (),  # (id, summary)
    commands: Sequence[CommandSpec] = COMMAND_SPECS,
) -> list[CompletionItem]:
    """Completion items for the current input line (empty = no popup)."""
    if not line.startswith("/") or line.startswith("!"):
        return []
    token, sep, arg = line.partition(" ")
    if not sep:
        query = token[1:]
        items = _command_items(query, commands) + _skill_items(query, skills)
        return items[:MAX_ITEMS]
    # Argument position — contextual per command.
    command = token[1:].casefold()
    if command in ("model",) and models:
        return [CompletionItem(insert=f"/model {m} ", label=m, hint="model") for m in models if fuzzy_match(arg, m)][
            :MAX_ITEMS
        ]
    if command in ("load", "resume", "delete") and sessions:
        return [
            CompletionItem(insert=f"{token} {sid} ", label=sid, hint=summary[:50])
            for sid, summary in sessions
            if fuzzy_match(arg, sid) or fuzzy_match(arg, summary)
        ][:MAX_ITEMS]
    return []
