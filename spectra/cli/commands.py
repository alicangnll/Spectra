"""Pure slash-command registry and parser for the Spectra TUI.

Replaces the legacy ``command_parser.py`` with an exact-match registry
(the old prefix matching let ``/models`` fall into ``/model``) and adds
the aliases the TUI supports. Parsing is host-agnostic and returns a
:class:`ParsedCommand` the app dispatches on:

- known slash command → its :class:`CommandKind` plus argument text
- unknown ``/word`` → skill invocation (the agent loop resolves the slug)
- ``!text`` → shell escape
- anything else → natural language (start/queue an agent run)
"""

from __future__ import annotations

import dataclasses
from enum import Enum


class CommandKind(Enum):
    """What the parser decided the input is."""

    HELP = "help"
    SKILLS = "skills"
    SESSION_SAVE = "session_save"
    SESSION_LOAD = "session_load"
    SESSION_LIST = "session_list"
    SESSION_DELETE = "session_delete"
    SESSION_NEW = "session_new"
    MODEL = "model"
    PROVIDER = "provider"
    APIKEY = "apikey"
    APIURL = "apiurl"
    CONFIG_SHOW = "config_show"
    CONFIG_EDIT = "config_edit"
    AUTOLIMIT = "autolimit"
    TOGGLE = "toggle"
    THINKING = "thinking"
    PLAN = "plan"
    RESEARCH = "research"
    SKILL = "skill"
    SHELL_ESCAPE = "shell_escape"
    NATURAL_LANGUAGE = "natural_language"


@dataclasses.dataclass(frozen=True)
class CommandSpec:
    """One registered slash command."""

    kind: CommandKind
    word: str
    aliases: tuple[str, ...] = ()
    usage: str = ""
    help: str = ""
    takes_arg: bool = False

    @property
    def names(self) -> tuple[str, ...]:
        return (self.word, *self.aliases)

    def display(self) -> str:
        """Canonical form shown in help/completion, e.g. ``/load <id>``."""
        if not self.takes_arg:
            return f"/{self.word}"
        return f"/{self.word} {self.usage}".rstrip()


# Registry order = help display order.
COMMAND_SPECS: list[CommandSpec] = [
    CommandSpec(
        CommandKind.HELP,
        "help",
        aliases=("h", "?"),
        help="Show command help",
    ),
    CommandSpec(
        CommandKind.SKILLS,
        "skills",
        help="List available skills",
    ),
    CommandSpec(
        CommandKind.SESSION_SAVE,
        "save",
        usage="[name]",
        help="Save the current session",
        takes_arg=True,
    ),
    CommandSpec(
        CommandKind.SESSION_LOAD,
        "load",
        aliases=("resume",),
        usage="[id]",
        help="Load a session (no id = picker)",
        takes_arg=True,
    ),
    CommandSpec(
        CommandKind.SESSION_LIST,
        "sessions",
        help="List saved sessions",
    ),
    CommandSpec(
        CommandKind.SESSION_DELETE,
        "delete",
        usage="<id>",
        help="Delete a saved session",
        takes_arg=True,
    ),
    CommandSpec(
        CommandKind.SESSION_NEW,
        "new",
        aliases=("clear",),
        help="Start a new session (auto-saves the old one)",
    ),
    CommandSpec(
        CommandKind.MODEL,
        "model",
        usage="[name]",
        help="Show/select the model (no name = picker)",
        takes_arg=True,
    ),
    CommandSpec(
        CommandKind.PROVIDER,
        "provider",
        usage="[name]",
        help="Show/change the LLM provider",
        takes_arg=True,
    ),
    CommandSpec(
        CommandKind.APIKEY,
        "apikey",
        usage="<key>",
        help="Set the API key for the current provider",
        takes_arg=True,
    ),
    CommandSpec(
        CommandKind.APIURL,
        "apiurl",
        usage="[url]",
        help="Show/set the API base URL",
        takes_arg=True,
    ),
    CommandSpec(
        CommandKind.CONFIG_SHOW,
        "config",
        help="Show current configuration",
    ),
    CommandSpec(
        CommandKind.CONFIG_EDIT,
        "config_edit",
        help="Edit the config file in $EDITOR",
    ),
    CommandSpec(
        CommandKind.AUTOLIMIT,
        "autolimit",
        aliases=("autoapprove_limit",),
        usage="[N]",
        help="Show/set safe auto-approve limit (0 = unlimited, default 10)",
        takes_arg=True,
    ),
    CommandSpec(
        CommandKind.TOGGLE,
        "toggle",
        help="Collapse/expand the last tool result",
    ),
    CommandSpec(
        CommandKind.THINKING,
        "thinking",
        aliases=("think",),
        help="Toggle <think> reasoning display (Ctrl+O)",
    ),
    CommandSpec(
        CommandKind.PLAN,
        "plan",
        usage="<prompt>",
        help="Enter plan mode",
        takes_arg=True,
    ),
    CommandSpec(
        CommandKind.RESEARCH,
        "research",
        usage="<prompt>",
        help="Enter research mode with note capture",
        takes_arg=True,
    ),
]

# word (canonical or alias) -> spec, built once
_REGISTRY: dict[str, CommandSpec] = {name: spec for spec in COMMAND_SPECS for name in spec.names}


@dataclasses.dataclass(frozen=True)
class ParsedCommand:
    """Result of parsing one line of user input."""

    kind: CommandKind
    arg: str = ""  # argument text for command kinds; full text for natural language
    slug: str = ""  # skill slug for SKILL invocations


def parse_command(input_text: str) -> ParsedCommand:
    """Parse one line of input into a :class:`ParsedCommand`."""
    text = input_text.strip()
    if not text:
        return ParsedCommand(CommandKind.NATURAL_LANGUAGE, "")

    # Shell escape: "!command"
    if text.startswith("!"):
        return ParsedCommand(CommandKind.SHELL_ESCAPE, text[1:].strip())

    if text.startswith("/"):
        parts = text[1:].split(None, 1)
        word = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        spec = _REGISTRY.get(word)
        if spec is not None:
            return ParsedCommand(spec.kind, rest)

        # Unknown /word → skill invocation; the agent loop resolves the
        # slug (and applies mode upgrades) when it sees "/slug args".
        slug = word
        return ParsedCommand(CommandKind.SKILL, rest, slug=slug)

    return ParsedCommand(CommandKind.NATURAL_LANGUAGE, text)


def command_names_for_completion() -> list[str]:
    """All invocable command names (``/``-prefixed), canonical word first."""
    names: list[str] = []
    for spec in COMMAND_SPECS:
        for name in spec.names:
            names.append(f"/{name}")
    return names


def get_help_text() -> str:
    """Plain-text help table (also used as the modal fallback)."""
    lines = ["Spectra CLI Commands", ""]
    for spec in COMMAND_SPECS:
        lines.append(f"  {spec.display():<22} {spec.help}")
    lines.extend(
        [
            "  /<slug> [args]        Invoke a skill by slug",
            "  !command              Execute a shell command",
            "",
            "Anything else is sent to the agent as natural language.",
            "Enter queues messages while the agent runs; Esc interrupts.",
        ]
    )
    return "\n".join(lines)
