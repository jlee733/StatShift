"""RAG orchestration: route by intent to API retrieval or Gemma chat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

from config import settings
from rag.intent import IntentResult, PromptIntent, detect_prompt_intent
from rag.ollama_client import OllamaClient, OllamaError


class APIError(RuntimeError):
    pass


Route = Literal["api", "gemma"]


@dataclass
class RAGResult:
    answer: str
    sources: list[dict[str, Any]]
    prompt: str
    intent: PromptIntent
    route: Route
    intent_reason: str


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
    def _answer_from_sources(sources: list[dict[str, Any]]) -> str:
        if not sources:
            return (
                "No matching records were found in the StatShift database for that question. "
                "Try rephrasing with a player, team, week, or season."
            )
        lines = ["Based on stored records:\n"]
        for idx, doc in enumerate(sources, start=1):
            lines.append(
                f"[{idx}] **{doc['title']}** ({doc['category']})\n{doc['content']}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _build_conversational_prompt(query: str) -> str:
        return f"""You are StatShift, a friendly fantasy football analytics assistant.
Answer the user's message helpfully. You may use general NFL and fantasy football knowledge.
If they ask for specific stats from the StatShift database, suggest they ask a direct factual question.

User: {query}

Assistant:"""

    def ask(self, query: str, *, intent: IntentResult | None = None) -> RAGResult:
        resolved = intent or detect_prompt_intent(query)

        if resolved.intent == PromptIntent.DEFINITIVE:
            sources = self._search(query)
            return RAGResult(
                answer=self._answer_from_sources(sources),
                sources=sources,
                prompt="",
                intent=resolved.intent,
                route="api",
                intent_reason=resolved.reason,
            )

        prompt = self._build_conversational_prompt(query)
        try:
            answer = self.ollama.generate(prompt)
        except httpx.HTTPError as exc:
            raise OllamaError(
                "Could not reach Ollama. Start it locally and ensure Gemma is pulled."
            ) from exc
        return RAGResult(
            answer=answer,
            sources=[],
            prompt=prompt,
            intent=resolved.intent,
            route="gemma",
            intent_reason=resolved.reason,
        )

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
