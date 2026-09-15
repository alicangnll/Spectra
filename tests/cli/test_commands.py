"""Tests for the TUI slash-command registry and parser (pure)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spectra.cli.commands import (
    COMMAND_SPECS,
    CommandKind,
    command_names_for_completion,
    get_help_text,
    parse_command,
)


class TestParseCommand(unittest.TestCase):
    def test_empty_input_is_natural_language(self):
        parsed = parse_command("   ")
        self.assertEqual(parsed.kind, CommandKind.NATURAL_LANGUAGE)
        self.assertEqual(parsed.arg, "")

    def test_natural_language_passthrough(self):
        parsed = parse_command("What vulnerabilities exist here?")
        self.assertEqual(parsed.kind, CommandKind.NATURAL_LANGUAGE)
        self.assertEqual(parsed.arg, "What vulnerabilities exist here?")

    def test_shell_escape(self):
        parsed = parse_command("!ls -la /tmp")
        self.assertEqual(parsed.kind, CommandKind.SHELL_ESCAPE)
        self.assertEqual(parsed.arg, "ls -la /tmp")

    def test_bare_bang_is_empty_escape(self):
        parsed = parse_command("!")
        self.assertEqual(parsed.kind, CommandKind.SHELL_ESCAPE)
        self.assertEqual(parsed.arg, "")

    def test_help_and_aliases(self):
        for word in ("/help", "/h", "/?"):
            self.assertEqual(parse_command(word).kind, CommandKind.HELP, word)

    def test_alias_sets(self):
        cases = {
            "/load abc": CommandKind.SESSION_LOAD,
            "/resume abc": CommandKind.SESSION_LOAD,
            "/new": CommandKind.SESSION_NEW,
            "/clear": CommandKind.SESSION_NEW,
            "/thinking": CommandKind.THINKING,
            "/think": CommandKind.THINKING,
            "/autolimit 5": CommandKind.AUTOLIMIT,
            "/autoapprove_limit 5": CommandKind.AUTOLIMIT,
        }
        for text, kind in cases.items():
            self.assertEqual(parse_command(text).kind, kind, text)

    def test_model_with_and_without_arg(self):
        self.assertEqual(parse_command("/model").kind, CommandKind.MODEL)
        self.assertEqual(parse_command("/model").arg, "")
        parsed = parse_command("/model claude-sonnet-5")
        self.assertEqual(parsed.kind, CommandKind.MODEL)
        self.assertEqual(parsed.arg, "claude-sonnet-5")

    def test_model_prefix_no_longer_shadowed(self):
        # Legacy parser matched startswith("/model"), so "/models" parsed
        # as MODEL with name "s". Exact word matching must not.
        parsed = parse_command("/models")
        self.assertEqual(parsed.kind, CommandKind.SKILL)
        self.assertEqual(parsed.slug, "models")

    def test_save_optional_name(self):
        self.assertEqual(parse_command("/save").arg, "")
        self.assertEqual(parse_command("/save my analysis").arg, "my analysis")

    def test_delete_requires_arg_semantically(self):
        parsed = parse_command("/delete abc123")
        self.assertEqual(parsed.kind, CommandKind.SESSION_DELETE)
        self.assertEqual(parsed.arg, "abc123")

    def test_provider_bare_shows_current(self):
        parsed = parse_command("/provider")
        self.assertEqual(parsed.kind, CommandKind.PROVIDER)
        self.assertEqual(parsed.arg, "")
        self.assertEqual(parse_command("/provider glm").arg, "glm")

    def test_plan_and_research_take_prompts(self):
        self.assertEqual(parse_command("/plan Analyze this").arg, "Analyze this")
        self.assertEqual(parse_command("/research crypto").arg, "crypto")
        self.assertEqual(parse_command("/plan").arg, "")

    def test_unknown_slash_is_skill_invocation(self):
        parsed = parse_command("/vuln-audit --deep target.exe")
        self.assertEqual(parsed.kind, CommandKind.SKILL)
        self.assertEqual(parsed.slug, "vuln-audit")
        self.assertEqual(parsed.arg, "--deep target.exe")

    def test_skill_slug_only(self):
        parsed = parse_command("/exploit-dev")
        self.assertEqual(parsed.kind, CommandKind.SKILL)
        self.assertEqual(parsed.slug, "exploit-dev")
        self.assertEqual(parsed.arg, "")

    def test_command_word_is_case_insensitive(self):
        self.assertEqual(parse_command("/HELP").kind, CommandKind.HELP)
        self.assertEqual(parse_command("/Model gpt-4o").kind, CommandKind.MODEL)

    def test_help_builtin_words_are_not_swallowed(self):
        # Legacy cmd.Cmd ate natural language starting with help/exit/quit.
        # Everything non-slash, non-bang must stay natural language.
        for text in ("help me analyze this binary", "exit strategy?", "quit smoking tips", "clear the cache"):
            self.assertEqual(parse_command(text).kind, CommandKind.NATURAL_LANGUAGE, text)


class TestRegistry(unittest.TestCase):
    def test_no_duplicate_names(self):
        names = [name for spec in COMMAND_SPECS for name in spec.names]
        self.assertEqual(len(names), len(set(names)))

    def test_completion_names_are_slash_prefixed(self):
        names = command_names_for_completion()
        self.assertIn("/help", names)
        self.assertIn("/h", names)
        self.assertIn("/resume", names)
        self.assertTrue(all(n.startswith("/") for n in names))

    def test_help_text_covers_every_spec(self):
        text = get_help_text()
        for spec in COMMAND_SPECS:
            self.assertIn(f"/{spec.word}", text)


if __name__ == "__main__":
    unittest.main()
