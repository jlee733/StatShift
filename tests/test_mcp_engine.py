"""Unit tests for legacy search engine orchestration."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx

from llm.engine import APIError, RAGEngine
from llm.intent import IntentResult, PromptIntent
from llm.ollama_client import OllamaClient, OllamaError


class RAGEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_ollama = MagicMock(spec=OllamaClient)
        self.mock_ollama.model = "gemma2:2b"
        self.engine = RAGEngine(
            api_base_url="http://api.test",
            ollama=self.mock_ollama,
            top_k=2,
        )

    def test_format_context_empty(self) -> None:
        self.assertEqual(
            RAGEngine._format_context([]),
            "No relevant documents were retrieved.",
        )

    def test_format_context_numbered_blocks(self) -> None:
        sources = [
            {"title": "Doc A", "category": "team", "content": "Line one."},
            {"title": "Doc B", "category": "player", "content": "Line two."},
        ]
        context = RAGEngine._format_context(sources)
        self.assertIn("[1] Doc A (team)", context)
        self.assertIn("[2] Doc B (player)", context)
        self.assertIn("Line one.", context)

    def test_answer_from_sources_empty(self) -> None:
        answer = RAGEngine._answer_from_sources([])
        self.assertIn("No matching records", answer)

    def test_answer_from_sources_includes_content(self) -> None:
        sources = [
            {
                "title": "Ja'Marr Chase 2024 target share",
                "category": "player",
                "content": "175 targets",
            },
        ]
        answer = RAGEngine._answer_from_sources(sources)
        self.assertIn("175 targets", answer)
        self.assertIn("Chase", answer)

    def test_build_conversational_prompt_includes_query(self) -> None:
        prompt = RAGEngine._build_conversational_prompt("Tell me a fun fact")
        self.assertIn("Tell me a fun fact", prompt)
        self.assertIn("StatShift", prompt)

    @patch("llm.engine.httpx.get")
    def test_ask_definitive_uses_api_not_gemma(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(
                return_value=[
                    {
                        "id": 1,
                        "title": "Ja'Marr Chase 2024 target share",
                        "category": "player",
                        "content": "175 targets",
                    }
                ]
            ),
        )
        intent = IntentResult(PromptIntent.DEFINITIVE, reason="test")

        result = self.engine.ask("How many targets did Chase have?", intent=intent)

        self.assertEqual(result.route, "api")
        self.assertIn("175 targets", result.answer)
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(result.prompt, "")
        mock_get.assert_called_once()
        self.mock_ollama.generate.assert_not_called()

    @patch("llm.engine.httpx.get")
    def test_ask_conversational_uses_gemma_not_api(self, mock_get: MagicMock) -> None:
        self.mock_ollama.generate.return_value = "Fantasy football is a weekly game."
        intent = IntentResult(PromptIntent.CONVERSATIONAL, reason="test")

        result = self.engine.ask("Hello!", intent=intent)

        self.assertEqual(result.route, "gemma")
        self.assertEqual(result.answer, "Fantasy football is a weekly game.")
        self.assertEqual(result.sources, [])
        self.assertIn("Hello!", result.prompt)
        mock_get.assert_not_called()
        self.mock_ollama.generate.assert_called_once()

    @patch("llm.engine.httpx.get")
    def test_search_api_error_raises(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.ConnectError("refused")
        intent = IntentResult(PromptIntent.DEFINITIVE, reason="test")
        with self.assertRaises(APIError):
            self.engine.ask("How many yards did Burrow throw for?", intent=intent)

    @patch("llm.engine.httpx.get")
    def test_ask_ollama_error_wrapped(self, mock_get: MagicMock) -> None:
        self.mock_ollama.generate.side_effect = httpx.ConnectError("down")
        intent = IntentResult(PromptIntent.CONVERSATIONAL, reason="test")
        with self.assertRaises(OllamaError):
            self.engine.ask("Hi there", intent=intent)
        mock_get.assert_not_called()

    @patch("llm.engine.httpx.get")
    def test_health_reports_status(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"status": "ok"}),
        )
        self.mock_ollama.is_available.return_value = True
        self.mock_ollama.list_models.return_value = ["gemma2:2b"]

        health = self.engine.health()

        self.assertTrue(health["api_ok"])
        self.assertEqual(health["api_detail"], "ok")
        self.assertTrue(health["ollama_ok"])
        self.assertEqual(health["ollama_models"], ["gemma2:2b"])
        self.assertEqual(health["configured_model"], "gemma2:2b")


if __name__ == "__main__":
    unittest.main()
