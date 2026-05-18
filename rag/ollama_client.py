"""Thin client for local Ollama (Gemma) inference."""

from __future__ import annotations

import httpx

from config import settings


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[str]:
        response = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        return [m["name"] for m in payload.get("models", [])]

    def generate(self, prompt: str, *, temperature: float = 0.2) -> str:
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=self.timeout,
        )
        if response.status_code == 404:
            raise OllamaError(
                f"Model '{self.model}' not found. Pull it with: ollama pull {self.model}"
            )
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()
