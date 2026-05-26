"""Tests for MCP agent helpers."""

from __future__ import annotations

import unittest

from llm.intent import PromptIntent, detect_prompt_intent
from llm.mcp_agent import (
    MCPAgent,
    _player_search_terms,
    _should_fallback_from_ollama_error,
)
from llm.ollama_client import ChatResponse, OllamaError, OllamaClient


class MCPAgentHelperTests(unittest.TestCase):
    def test_player_search_terms(self) -> None:
        self.assertEqual(
            _player_search_terms("What do you think about Gibbs?"),
            ["Gibbs"],
        )
        self.assertEqual(
            _player_search_terms("How is Patrick Mahomes doing?"),
            ["Mahomes", "Patrick"],
        )

    def test_mahomes_opinion_is_conversational(self) -> None:
        result = detect_prompt_intent("What do you think of Patick Mahomes?")
        self.assertEqual(result.intent, PromptIntent.CONVERSATIONAL)

    def test_ask_conversational_skips_tools(self) -> None:
        class FakeOllama(OllamaClient):
            def __init__(self) -> None:
                self.model = "test-model"
                self.base_url = "http://test"
                self.timeout = 1.0
                self.chat_calls = 0

            def chat(self, messages, *, tools=None, temperature=0.2):
                self.chat_calls += 1
                self.last_tools = tools
                return ChatResponse(content="Mahomes is elite.", tool_calls=[])

        fake = FakeOllama()
        agent = MCPAgent(ollama=fake)
        result = agent.ask("What do you think of Patrick Mahomes?")
        self.assertEqual(result.route, "conversational")
        self.assertEqual(result.answer, "Mahomes is elite.")
        self.assertEqual(fake.chat_calls, 1)
        self.assertIsNone(fake.last_tools)
        self.assertEqual(result.tool_executions, [])

    def test_should_fallback_on_memory_error(self) -> None:
        exc = OllamaError("Ollama error (HTTP 500): model requires more system memory")
        self.assertTrue(_should_fallback_from_ollama_error(exc))

    def test_should_not_fallback_on_connect_error(self) -> None:
        exc = OllamaError("Cannot connect to Ollama at http://127.0.0.1:11434")
        self.assertFalse(_should_fallback_from_ollama_error(exc))


if __name__ == "__main__":
    unittest.main()
