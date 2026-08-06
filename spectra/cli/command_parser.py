"""Command parser for CLI slash commands.

Parses user input and routes to appropriate handlers:
- Skill invocation (/slug)
- Plan mode (/plan)
- Research mode (/research)
- Shell escape (!command)
- Session commands (/save, /load, /sessions, /new)
- Natural language (default)
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Optional


class CommandType(Enum):
    """Types of commands recognized by the CLI."""

    SKILL = "skill"  # /slug [args]
    PLAN = "plan"  # /plan <prompt>
    RESEARCH = "research"  # /research <prompt>
    SHELL = "shell"  # !command
    SESSION_SAVE = "session_save"  # /save [name]
    SESSION_LOAD = "session_load"  # /load <id>
    SESSION_LIST = "session_list"  # /sessions
    SESSION_NEW = "session_new"  # /new
    SESSION_DELETE = "session_delete"  # /delete <id>
    SKILLS_LIST = "skills_list"  # /skills
    MODEL_SET = "model_set"  # /model <model_name>
    PROVIDER_SET = "provider_set"  # /provider <provider_name>
    CONFIG_SHOW = "config_show"  # /config
    CONFIG_EDIT = "config_edit"  # /config_edit
    APIURL_SET = "apiurl_set"  # /apiurl <url>
    APIKEY_SET = "apikey_set"  # /apikey <key>
    SHELL_CONFIG = "shell_config"  # /shellconfig or /shelllimit
    TOGGLE = "toggle"  # /toggle
    HELP = "help"  # /help
    NATURAL_LANGUAGE = "natural_language"  # Any other input


@dataclasses.dataclass
class Command:
    """Parsed command result."""

    type: CommandType
    value: str  # The primary value (skill slug, prompt, command, etc.)
    args: str = ""  # Additional arguments

    def __repr__(self) -> str:
        return f"Command({self.type.value}, value={self.value!r}, args={self.args!r})"


def parse_command(input_text: str) -> Command:
    """Parse CLI input into a Command.

    Rules:
    1. /slug [args] → Skill invocation
    2. /plan <prompt> → Plan mode
    3. /research <prompt> → Research mode
    4. !command → Shell escape
    5. /save [name] → Save session
    6. /load <id> → Load session
    7. /sessions → List sessions
    8. /new → New session
    9. /skills → List skills
    10. /model <name> → Set model
    11. /provider <name> → Set provider
    12. /config → Show config
    13. /config_edit → Edit config in text editor
    14. /apiurl <url> → Set API base URL
    15. /apikey <key> → Set API key
    16. /help → Show help
    17. Anything else → Natural language

    Args:
        input_text: Raw user input

    Returns:
        Command with type and parsed values
    """
    text = input_text.strip()
    if not text:
        return Command(CommandType.NATURAL_LANGUAGE, "", "")

    # Shell escape (!command)
    if text.startswith("!"):
        return Command(CommandType.SHELL, text[1:], "")

    # Configuration commands
    if text.startswith("/model"):
        if text == "/model" or text == "/model ":
            return Command(CommandType.MODEL_SET, "", "")  # List models
        model = text[7:].strip()
        return Command(CommandType.MODEL_SET, model, "")

    if text.startswith("/provider "):
        provider = text[10:].strip()
        return Command(CommandType.PROVIDER_SET, provider, "")

    if text.startswith("/apikey "):
        key = text[8:].strip()
        return Command(CommandType.APIKEY_SET, key, "")

    if text.startswith("/apiurl"):
        if text == "/apiurl" or text == "/apiurl ":
            return Command(CommandType.APIURL_SET, "", "")  # Show current
        url = text[8:].strip()
        return Command(CommandType.APIURL_SET, url, "")

    if text == "/config":
        return Command(CommandType.CONFIG_SHOW, "", "")

    if text == "/config_edit":
        return Command(CommandType.CONFIG_EDIT, "", "")

    # Shell config commands
    if text.startswith("/autoapprove_limit "):
        limit_str = text[19:].strip()
        return Command(CommandType.SHELL_CONFIG, limit_str, "")

    if text.startswith("/autolimit "):
        limit_str = text[10:].strip()
        return Command(CommandType.SHELL_CONFIG, limit_str, "")

    if text == "/autoapprove_limit" or text == "/autolimit":
        return Command(CommandType.SHELL_CONFIG, "", "")  # Show current limit

    # Session commands
    if text.startswith("/save "):
        args = text[6:].strip()
        return Command(CommandType.SESSION_SAVE, args or "", "")
    if text == "/save":
        return Command(CommandType.SESSION_SAVE, "", "")

    if text.startswith("/load "):
        session_id = text[6:].strip()
        return Command(CommandType.SESSION_LOAD, session_id, "")

    if text == "/sessions":
        return Command(CommandType.SESSION_LIST, "", "")

    if text == "/new":
        return Command(CommandType.SESSION_NEW, "", "")

    if text.startswith("/delete "):
        session_id = text[8:].strip()
        return Command(CommandType.SESSION_DELETE, session_id, "")

    if text == "/skills":
        return Command(CommandType.SKILLS_LIST, "", "")

    if text == "/toggle":
        return Command(CommandType.TOGGLE, "", "")

    if text == "/help":
        return Command(CommandType.HELP, "", "")

    # Mode commands
    if text.startswith("/plan "):
        prompt = text[6:].strip()
        return Command(CommandType.PLAN, prompt, "")

    if text.startswith("/research "):
        prompt = text[10:].strip()
        return Command(CommandType.RESEARCH, prompt, "")

    # Skill invocation (/slug [args])
    if text.startswith("/"):
        parts = text[1:].split(None, 1)
        slug = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        return Command(CommandType.SKILL, slug, args)

    # Default: natural language
    return Command(CommandType.NATURAL_LANGUAGE, text, "")


# Slash command constants for help display
SKILL_COMMANDS = [
    ("/slug [args]", "Invoke a skill by slug"),
    ("/plan <prompt>", "Enter plan mode for implementation planning"),
    ("/research <prompt>", "Enter research mode with note capture"),
]

SESSION_COMMANDS = [
    ("/save [name]", "Save current session"),
    ("/load <id>", "Load a saved session"),
    ("/sessions", "List all saved sessions"),
    ("/delete <id>", "Delete a saved session"),
    ("/new", "Start a new session"),
]

CONFIG_COMMANDS = [
    ("/model", "List available models for current provider"),
    ("/model <name>", "Set AI model (e.g., claude-3-5-sonnet-20241022)"),
    ("/provider <name>", "Change AI provider (anthropic/openai/gemini/ollama/lmstudio)"),
    ("/apiurl", "Show current API base URL"),
    ("/apiurl <url>", "Set API base URL (e.g., http://localhost:1234/v1)"),
    ("/apikey <key>", "Set API key for current provider"),
    ("/config", "Show current configuration"),
    ("/config_edit", "Edit config file in text editor"),
    ("/autoapprove_limit", "Show shell auto-approve limit"),
    ("/autolimit <N>", "Set shell auto-approve limit (default: 10, 0 = disable)"),
]

SYSTEM_COMMANDS = [
    ("/skills", "List all available skills"),
    ("/toggle", "Toggle collapse/expand of last tool result"),
    ("/help", "Show this help message"),
    ("!command", "Execute shell command"),
]


def get_help_text() -> str:
    """Generate help text for CLI commands."""
    lines = [
        "Spectra CLI Commands",
        "",
        "Skill Commands:",
    ]
    for cmd, desc in SKILL_COMMANDS:
        lines.append(f"  {cmd:<30} {desc}")

    lines.extend([
        "",
        "Session Commands:",
    ])
    for cmd, desc in SESSION_COMMANDS:
        lines.append(f"  {cmd:<30} {desc}")

    lines.extend([
        "",
        "Configuration Commands:",
    ])
    for cmd, desc in CONFIG_COMMANDS:
        lines.append(f"  {cmd:<30} {desc}")

    lines.extend([
        "",
        "System Commands:",
    ])
    for cmd, desc in SYSTEM_COMMANDS:
        lines.append(f"  {cmd:<30} {desc}")

    lines.extend([
        "",
        "Natural Language:",
        "  Any other input is sent to the AI for analysis.",
        "",
        "Examples:",
        "  spectra> /vuln-audit",
        "  spectra> /plan Analyze this binary",
        "  spectra> /research crypto algorithms",
        "  spectra> /save my-analysis",
        "  spectra> /load abc123",
        "  spectra> /skills",
        "  spectra> /model claude-3-5-sonnet-20241022",
        "  spectra> /provider anthropic",
        "  spectra> /apikey sk-ant-xxx",
        "  spectra> /config",
        "  spectra> !ls -la",
        "  spectra> What vulnerabilities exist in this code?",
    ])

    return "\n".join(lines)
