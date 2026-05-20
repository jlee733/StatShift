"""Unit tests for the Ollama HTTP client."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx

from rag.ollama_client import OllamaClient, OllamaError


class OllamaClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = OllamaClient(base_url="http://ollama.test", model="gemma2:2b")

    @patch("rag.ollama_client.httpx.get")
    def test_is_available_true(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        self.assertTrue(self.client.is_available())
        mock_get.assert_called_once_with("http://ollama.test/api/tags", timeout=5.0)

    @patch("rag.ollama_client.httpx.get")
    def test_is_available_false_on_error(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.ConnectError("down")
        self.assertFalse(self.client.is_available())

    @patch("rag.ollama_client.httpx.get")
    def test_list_models(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"models": [{"name": "gemma2:2b"}, {"name": "llama3"}]}),
        )
        self.assertEqual(self.client.list_models(), ["gemma2:2b", "llama3"])

    @patch("rag.ollama_client.httpx.post")
    def test_generate_returns_response_text(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"response": "  Answer text  "}),
        )
        result = self.client.generate("prompt")
        self.assertEqual(result, "Answer text")
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gemma2:2b")
        self.assertEqual(payload["prompt"], "prompt")
        self.assertFalse(payload["stream"])

    @patch("rag.ollama_client.httpx.post")
    def test_generate_missing_model_raises(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=404)
        with self.assertRaises(OllamaError) as ctx:
            self.client.generate("prompt")
        self.assertIn("gemma2:2b", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
