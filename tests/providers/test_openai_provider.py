"""Tests for OpenAI provider: message formatting, normalization, error handling."""

from __future__ import annotations

import json
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.mocks.ida_mock import install_ida_mocks

install_ida_mocks()

from spectra.core.types import Message, Role, ToolCall, ToolResult


def _make_provider():
    from spectra.providers.openai_provider import OpenAIProvider

    return OpenAIProvider(api_key="test-key", model="gpt-test")


class TestOpenAIFormatMessages(unittest.TestCase):
    def test_user_message(self):
        p = _make_provider()
        msgs = [Message(role=Role.USER, content="Hello")]
        result = p._format_messages(msgs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")

    def test_system_message_included(self):
        """OpenAI keeps system messages in the message array."""
        p = _make_provider()
        msgs = [
            Message(role=Role.SYSTEM, content="You are a helper"),
            Message(role=Role.USER, content="Hi"),
        ]
        result = p._format_messages(msgs)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "system")

    def test_assistant_with_tool_calls(self):
        p = _make_provider()
        msgs = [
            Message(
                role=Role.ASSISTANT,
                content="Checking",
                tool_calls=[ToolCall(id="tc_1", name="get_info", arguments={"x": 1})],
            )
        ]
        result = p._format_messages(msgs)
        self.assertEqual(result[0]["role"], "assistant")
        self.assertEqual(result[0]["content"], "Checking")
        self.assertEqual(len(result[0]["tool_calls"]), 1)
        tc = result[0]["tool_calls"][0]
        self.assertEqual(tc["id"], "tc_1")
        self.assertEqual(tc["type"], "function")
        self.assertEqual(tc["function"]["name"], "get_info")
        self.assertEqual(json.loads(tc["function"]["arguments"]), {"x": 1})

    def test_tool_results_use_tool_role(self):
        """OpenAI keeps tool results as 'tool' role messages."""
        p = _make_provider()
        msgs = [
            Message(
                role=Role.TOOL,
                tool_results=[
                    ToolResult(tool_call_id="tc_1", name="get_info", content="result"),
                ],
            )
        ]
        result = p._format_messages(msgs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "tool")
        self.assertEqual(result[0]["tool_call_id"], "tc_1")
        self.assertEqual(result[0]["content"], "result")


class TestOpenAINormalizeResponse(unittest.TestCase):
    def test_text_response(self):
        p = _make_provider()
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Hello", tool_calls=None),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        msg = p._normalize_response(response)
        self.assertEqual(msg.content, "Hello")
        self.assertEqual(msg.tool_calls, [])
        self.assertEqual(msg.token_usage.total_tokens, 15)

    def test_tool_call_response(self):
        p = _make_provider()
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="tc_1",
                                function=SimpleNamespace(
                                    name="test_tool",
                                    arguments='{"key": "val"}',
                                ),
                            )
                        ],
                    ),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )
        msg = p._normalize_response(response)
        self.assertEqual(msg.content, "")
        self.assertEqual(len(msg.tool_calls), 1)
        self.assertEqual(msg.tool_calls[0].name, "test_tool")
        self.assertEqual(msg.tool_calls[0].arguments, {"key": "val"})

    def test_no_usage(self):
        p = _make_provider()
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="OK", tool_calls=None),
                )
            ],
            usage=None,
        )
        msg = p._normalize_response(response)
        self.assertEqual(msg.token_usage.total_tokens, 0)


class TestOpenAIHandleApiError(unittest.TestCase):
    def test_generic_error_raises_provider_error(self):
        from spectra.core.errors import ProviderError

        p = _make_provider()
        with self.assertRaises(ProviderError):
            p._handle_api_error(RuntimeError("something broke"))

    def test_context_length_string(self):
        from spectra.core.errors import ProviderError

        p = _make_provider()
        with self.assertRaises(ProviderError):
            p._handle_api_error(RuntimeError("maximum context length exceeded"))


class TestOpenAIRequestKwargs(unittest.TestCase):
    """Reasoning models reject temperature/max_tokens — kwargs must adapt."""

    def _kwargs(self, model: str):
        p = _make_provider()
        p.model = model
        return p._build_request_kwargs(
            messages=[Message(role=Role.USER, content="hi")],
            tools=None,
            temperature=0.2,
            max_tokens=4096,
            system="You are Spectra.",
        )

    def test_standard_model_gets_max_tokens_and_temperature(self):
        kw = self._kwargs("gpt-4o")
        self.assertEqual(kw["max_tokens"], 4096)
        self.assertEqual(kw["temperature"], 0.2)
        self.assertNotIn("max_completion_tokens", kw)

    def test_reasoning_model_o3_gets_max_completion_tokens(self):
        kw = self._kwargs("o3-mini")
        self.assertEqual(kw["max_completion_tokens"], 4096)
        self.assertNotIn("max_tokens", kw)
        self.assertNotIn("temperature", kw)

    def test_reasoning_model_gpt5_gets_max_completion_tokens(self):
        kw = self._kwargs("gpt-5")
        self.assertEqual(kw["max_completion_tokens"], 4096)
        self.assertNotIn("temperature", kw)

    def test_is_reasoning_model_detection(self):
        from spectra.providers.openai_provider import OpenAIProvider

        for model in ("o1", "o1-mini", "o3-mini", "o4-mini", "gpt-5", "GPT-5-Mini"):
            self.assertTrue(OpenAIProvider._is_reasoning_model(model), model)
        for model in ("gpt-4o", "gpt-4.1", "gpt-4o-mini"):
            self.assertFalse(OpenAIProvider._is_reasoning_model(model), model)

    def test_builtin_models_include_current_generation(self):
        from spectra.providers.openai_provider import OpenAIProvider

        ids = [m.id for m in OpenAIProvider._builtin_models()]
        self.assertIn("gpt-4o", ids)  # legacy fallback still present
        self.assertTrue(any(m.startswith("gpt-5") for m in ids), ids)
        self.assertTrue(any(m.startswith("gpt-4.1") for m in ids), ids)


if __name__ == "__main__":
    unittest.main()
