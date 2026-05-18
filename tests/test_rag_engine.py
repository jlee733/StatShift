"""Unit tests for RAG orchestration."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx

from rag.engine import APIError, RAGEngine
from rag.ollama_client import OllamaClient, OllamaError


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

    def test_build_prompt_includes_query_and_context(self) -> None:
        prompt = RAGEngine._build_prompt("Who led scoring?", "ctx block")
        self.assertIn("StatShift", prompt)
        self.assertIn("ctx block", prompt)
        self.assertIn("Who led scoring?", prompt)

    @patch("rag.engine.httpx.get")
    def test_ask_returns_rag_result(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(
                return_value=[
                    {
                        "id": 1,
                        "title": "Curry splits",
                        "category": "player",
                        "content": "26.4 PPG",
                    }
                ]
            ),
        )
        self.mock_ollama.generate.return_value = "Curry averaged 26.4 PPG [1]."

        result = self.engine.ask("How did Curry score?")

        self.assertEqual(result.answer, "Curry averaged 26.4 PPG [1].")
        self.assertEqual(len(result.sources), 1)
        self.assertIn("Curry splits", result.prompt)
        mock_get.assert_called_once_with(
            "http://api.test/search",
            params={"q": "How did Curry score?", "limit": 2},
            timeout=15.0,
        )
        self.mock_ollama.generate.assert_called_once()

    @patch("rag.engine.httpx.get")
    def test_search_api_error_raises(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.ConnectError("refused")
        with self.assertRaises(APIError):
            self.engine.ask("test")

    @patch("rag.engine.httpx.get")
    def test_ask_ollama_error_wrapped(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value=[]),
        )
        self.mock_ollama.generate.side_effect = httpx.ConnectError("down")
        with self.assertRaises(OllamaError):
            self.engine.ask("test")

    @patch("rag.engine.httpx.get")
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
