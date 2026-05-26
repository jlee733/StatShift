"""Thin client for local Ollama inference (Gemma 4 by default)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from config import settings


class OllamaError(RuntimeError):
    pass


@dataclass
class ToolCall:
    """Represents a tool call request from the LLM."""

    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResponse:
    """Response from the chat API, potentially including tool calls."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    done: bool = True


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or httpx.Timeout(
            connect=30.0,
            read=settings.ollama_timeout_seconds,
            write=30.0,
            pool=30.0,
        )

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
        """Simple text generation without tool support (legacy search mode)."""
        try:
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
        except httpx.ConnectError as e:
            raise OllamaError(
                f"Cannot connect to Ollama at {self.base_url}. Error: {str(e)}"
            ) from e
        except httpx.TimeoutException as e:
            raise self._timeout_error(e) from e
        except httpx.HTTPStatusError as e:
            raise self._http_status_error(e) from e
        except httpx.HTTPError as e:
            raise OllamaError(
                f"Network error connecting to Ollama at {self.base_url}: {type(e).__name__} - {str(e)}"
            ) from e

    def _timeout_error(self, exc: httpx.TimeoutException) -> OllamaError:
        read_limit = settings.ollama_timeout_seconds
        if isinstance(self.timeout, httpx.Timeout):
            read_limit = self.timeout.read or read_limit
        return OllamaError(
            f"Ollama at {self.base_url} did not respond within {read_limit:.0f}s. "
            "The model may still be loading into memory (first request after startup "
            "can take 1–3 minutes). Wait for startup to finish, then try again."
            f" ({exc})"
        )

    @staticmethod
    def _http_status_error(exc: httpx.HTTPStatusError) -> OllamaError:
        detail = str(exc)
        try:
            body = exc.response.json()
            if isinstance(body, dict) and body.get("error"):
                detail = body["error"]
        except (json.JSONDecodeError, ValueError):
            pass
        return OllamaError(
            f"Ollama error (HTTP {exc.response.status_code}): {detail}"
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> ChatResponse:
        """Chat completion with optional tool calling support.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                      Roles: 'system', 'user', 'assistant', 'tool'.
            tools: Optional list of tool definitions in Ollama format.
            temperature: Sampling temperature.

        Returns:
            ChatResponse with content and any tool calls requested by the model.

        Raises:
            OllamaError: On connection, timeout, or API errors.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code == 404:
                raise OllamaError(
                    f"Model '{self.model}' not found. Pull it with: ollama pull {self.model}"
                )
            response.raise_for_status()
            data = response.json()

            message = data.get("message", {})
            content = (message.get("content") or "").strip()

            tool_calls: list[ToolCall] = []
            raw_tool_calls = message.get("tool_calls", [])
            for tc in raw_tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                arguments = func.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments) if arguments else {}
                    except json.JSONDecodeError:
                        arguments = {}
                if not isinstance(arguments, dict):
                    arguments = {}
                if name:
                    tool_calls.append(ToolCall(name=name, arguments=arguments))

            return ChatResponse(
                content=content,
                tool_calls=tool_calls,
                done=data.get("done", True),
            )

        except httpx.ConnectError as e:
            raise OllamaError(
                f"Cannot connect to Ollama at {self.base_url}. Error: {str(e)}"
            ) from e
        except httpx.TimeoutException as e:
            raise self._timeout_error(e) from e
        except httpx.HTTPStatusError as e:
            raise self._http_status_error(e) from e
        except httpx.HTTPError as e:
            raise OllamaError(
                f"Network error connecting to Ollama at {self.base_url}: {type(e).__name__} - {str(e)}"
            ) from e
