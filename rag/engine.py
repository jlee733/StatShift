"""RAG orchestration: retrieve from API, generate with Ollama/Gemma."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from config import settings
from rag.ollama_client import OllamaClient, OllamaError


class APIError(RuntimeError):
    pass


@dataclass
class RAGResult:
    answer: str
    sources: list[dict[str, Any]]
    prompt: str


class RAGEngine:
    def __init__(
        self,
        api_base_url: str | None = None,
        ollama: OllamaClient | None = None,
        top_k: int = 4,
    ) -> None:
        self.api_base_url = (api_base_url or settings.api_base_url).rstrip("/")
        self.ollama = ollama or OllamaClient()
        self.top_k = top_k

    def _search(self, query: str) -> list[dict[str, Any]]:
        try:
            response = httpx.get(
                f"{self.api_base_url}/search",
                params={"q": query, "limit": self.top_k},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise APIError(f"Failed to reach API at {self.api_base_url}: {exc}") from exc

    @staticmethod
    def _format_context(sources: list[dict[str, Any]]) -> str:
        if not sources:
            return "No relevant documents were retrieved."
        blocks = []
        for idx, doc in enumerate(sources, start=1):
            blocks.append(
                f"[{idx}] {doc['title']} ({doc['category']})\n{doc['content']}"
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _build_prompt(query: str, context: str) -> str:
        return f"""You are StatShift, a local basketball analytics assistant.
Answer using ONLY the context below. If the context is insufficient, say what is missing.
Keep answers concise and cite source numbers like [1] when you use a fact.

Context:
{context}

Question: {query}

Answer:"""

    def ask(self, query: str) -> RAGResult:
        sources = self._search(query)
        context = self._format_context(sources)
        prompt = self._build_prompt(query, context)
        try:
            answer = self.ollama.generate(prompt)
        except httpx.HTTPError as exc:
            raise OllamaError(
                "Could not reach Ollama. Start it locally and ensure Gemma is pulled."
            ) from exc
        return RAGResult(answer=answer, sources=sources, prompt=prompt)

    def health(self) -> dict[str, Any]:
        api_ok = False
        api_detail = ""
        try:
            response = httpx.get(f"{self.api_base_url}/health", timeout=5.0)
            api_ok = response.status_code == 200
            api_detail = response.json().get("status", "unknown")
        except httpx.HTTPError as exc:
            api_detail = str(exc)

        ollama_ok = self.ollama.is_available()
        models = self.ollama.list_models() if ollama_ok else []

        return {
            "api_ok": api_ok,
            "api_detail": api_detail,
            "ollama_ok": ollama_ok,
            "ollama_models": models,
            "configured_model": self.ollama.model,
        }
