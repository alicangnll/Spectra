"""Golden-set skill evals: does /vuln-audit actually find planted bugs?

These are REAL LLM evals — they cost money and are skipped by default.
Enable with:

    SPECTRA_EVAL=1 ANTHROPIC_API_KEY=sk-... python -m pytest tests/skills -v

Optional:
    SPECTRA_EVAL_MODEL      model to use (default: claude-sonnet-5)
    SPECTRA_EVAL_API_BASE   Anthropic-compatible endpoint (e.g. a proxy)
    SPECTRA_EVAL_API_KEY    key (falls back to ANTHROPIC_API_KEY)

Each fixture is a small C file with a planted bug. The skill is invoked via
its real /slug path (rewrite, doctrine composition, sanitization) against a
live provider with no tools, so the eval measures how well the SKILL TEXT
steers discovery — not tool plumbing. Assertions are keyword groups: every
group must be hit by at least one of its alternatives in the final report.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.mocks.ida_mock import install_ida_mocks

install_ida_mocks()

_EVAL_ON = os.environ.get("SPECTRA_EVAL", "").lower() in ("1", "true", "yes")
_API_KEY = os.environ.get("SPECTRA_EVAL_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")

FIXTURES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fixtures",
    "evals",
)


@unittest.skipUnless(_EVAL_ON and _API_KEY, "set SPECTRA_EVAL=1 and ANTHROPIC_API_KEY to run LLM evals")
class TestVulnAuditSkillEvals(unittest.TestCase):
    """One planted bug per fixture; the skill must surface it."""

    @classmethod
    def setUpClass(cls):
        from spectra.agent.loop import AgentLoop
        from spectra.core.config import SpectraConfig
        from spectra.providers.anthropic_provider import AnthropicProvider
        from spectra.skills.registry import SkillRegistry
        from spectra.state.session import SessionState
        from spectra.tools.registry import ToolRegistry

        model = os.environ.get("SPECTRA_EVAL_MODEL", "claude-sonnet-5")
        api_base = os.environ.get("SPECTRA_EVAL_API_BASE", "")
        cls.provider = AnthropicProvider(api_key=_API_KEY, api_base=api_base, model=model)

        cls.config = SpectraConfig()
        cls.config.auto_context = False
        cls.config.max_retries = 1

        cls.skill_registry = SkillRegistry("/nonexistent-user-skills")
        cls.skill_registry.discover()

    def _run_skill(self, fixture: str) -> str:
        """Invoke /vuln-audit on a fixture source; return the report text."""
        from spectra.agent.loop import AgentLoop
        from spectra.agent.turn import TurnEventType
        from spectra.state.session import SessionState
        from spectra.tools.registry import ToolRegistry

        with open(os.path.join(FIXTURES, fixture), encoding="utf-8") as f:
            source = f.read()

        session = SessionState(provider_name="anthropic", model_name=self.provider.model)
        loop = AgentLoop(
            self.provider,
            ToolRegistry(),
            self.config,
            session,
            skill_registry=self.skill_registry,
            host_name="eval",
        )
        message = (
            "/vuln-audit Audit the following C code for exploitable "
            "vulnerabilities. Apply the skill doctrine and report findings "
            "with the required provenance lines.\n\n```c\n" + source + "\n```"
        )

        report = ""
        for event in loop.run(message):
            if event.type == TurnEventType.TEXT_DONE and event.text:
                report = event.text
            elif event.type == TurnEventType.ERROR and event.error:
                self.fail(f"agent error during eval: {event.error}")
        self.assertTrue(report.strip(), "empty report from /vuln-audit eval run")
        return report

    def _assert_groups(self, report: str, groups: list[list[str]]) -> None:
        lowered = report.lower()
        for group in groups:
            with self.subTest(group=group):
                self.assertTrue(
                    any(kw.lower() in lowered for kw in group),
                    f"report does not mention any of {group}; report head: {report[:400]!r}",
                )

    def test_stack_overflow_fixture(self):
        report = self._run_skill("stack-bof.c")
        self._assert_groups(
            report,
            [
                ["overflow"],
                ["strcpy"],
                ["name_len", "name[", "32-byte", "32 byte"],
                ["critical"],
            ],
        )

    def test_integer_overflow_fixture(self):
        report = self._run_skill("int-overflow.c")
        self._assert_groups(
            report,
            [
                ["overflow"],
                ["integer", "wraps", "wrap", "0x20000000"],
                ["malloc", "alloc"],
                ["table", "count"],
            ],
        )

    def test_unsigned_underflow_fixture(self):
        report = self._run_skill("underflow-auth.c")
        self._assert_groups(
            report,
            [
                ["underflow", "wrap", "unsigned"],
                ["hdr_len", "body_len"],
                ["memcpy", "out of bounds", "oob"],
            ],
        )

    def test_provenance_directive_reaches_output(self):
        """End-to-end check that the shared doctrine's provenance
        requirement (added with the composition refactor) lands in the
        model's report."""
        report = self._run_skill("stack-bof.c")
        self.assertIn("provenance:", report.lower())


if __name__ == "__main__":
    unittest.main()
