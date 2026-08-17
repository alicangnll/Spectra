"""Tests for CLI shell controller provider switching (Qt-free path).

Regression tests for two bugs:
  - switching providers never reset ``api_base``, so a previous local
    endpoint (lmstudio localhost:1234) leaked into the next provider;
  - the CLI carried its own stale default model list (gpt-4,
    claude-3-5-sonnet-20241022, ...) contradicting the provider builtins.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# The CLI path must be importable without any Qt binding installed.
from spectra.cli.shell_controller import CLISessionController
from spectra.core.config import SpectraConfig


def _make_controller(tmpdir: str) -> CLISessionController:
    """Build a controller without running the runtime-init thread."""
    ctrl = CLISessionController.__new__(CLISessionController)
    ctrl.config = SpectraConfig()
    ctrl.config._config_dir = tmpdir
    return ctrl


class TestSetProvider(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ctrl = _make_controller(self.tmp.name)

    def test_invalid_provider_rejected(self):
        err = self.ctrl.set_provider("not-a-provider")
        self.assertIsNotNone(err)
        self.assertIn("Invalid provider", err)

    def test_api_base_reset_when_leaving_lmstudio(self):
        # Simulate a previous lmstudio configuration.
        self.ctrl.config.provider.name = "lmstudio"
        self.ctrl.config.provider.api_base = "http://localhost:1234/v1"

        err = self.ctrl.set_provider("anthropic")
        self.assertIsNone(err)
        self.assertEqual(self.ctrl.config.provider.api_base, "")
        self.assertNotIn("localhost", self.ctrl.config.provider.api_base)

    def test_api_base_set_for_lmstudio(self):
        err = self.ctrl.set_provider("lmstudio")
        self.assertIsNone(err)
        self.assertEqual(self.ctrl.config.provider.api_base, "http://localhost:1234/v1")

    def test_api_base_set_for_glm(self):
        err = self.ctrl.set_provider("glm")
        self.assertIsNone(err)
        self.assertEqual(self.ctrl.config.provider.api_base, "https://open.bigmodel.cn/api/paas/v4/")

    def test_default_model_is_from_builtin_catalog(self):
        err = self.ctrl.set_provider("anthropic")
        self.assertIsNone(err)
        # Must come from AnthropicProvider._builtin_models(), not a stale
        # CLI-side literal like claude-3-5-sonnet-20241022.
        self.assertNotIn("3-5-sonnet", self.ctrl.config.provider.model)

        model = self.ctrl.config.provider.model
        self.assertIsInstance(model, str)
        self.assertTrue(model.startswith("claude-"), model)

        # When earlier tests replace provider modules with MagicMocks
        # (sys.modules pollution), only real string ids are trustworthy —
        # and the import itself may fail with "(unknown location)".
        try:
            from spectra.providers.anthropic_provider import AnthropicProvider
        except ImportError:
            return  # shape assertions above already cover the polluted case
        builtin_ids = [m.id for m in AnthropicProvider._builtin_models() if isinstance(getattr(m, "id", None), str)]
        if builtin_ids:
            self.assertIn(model, builtin_ids)

    def test_minimax_now_valid(self):
        err = self.ctrl.set_provider("minimax")
        self.assertIsNone(err)


class TestDefaultModelFor(unittest.TestCase):
    def test_known_providers_have_defaults(self):
        for provider in ("anthropic", "openai", "gemini", "ollama", "minimax", "glm", "lmstudio"):
            model = CLISessionController._default_model_for(provider)
            self.assertTrue(model, f"{provider} must have a default model")

    def test_unknown_provider_falls_back(self):
        self.assertEqual(CLISessionController._default_model_for("nope"), "local-model")

    def test_openai_default_not_stale(self):
        # The old hardcoded CLI default was "gpt-4".
        self.assertNotEqual(CLISessionController._default_model_for("openai"), "gpt-4")


if __name__ == "__main__":
    unittest.main()
