"""MCP Agent: orchestrates LLM tool calls against the StatShift MCP server."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from config import settings
from llm.intent import IntentResult, PromptIntent, detect_prompt_intent
from llm.ollama_client import ChatResponse, OllamaClient, OllamaError, ToolCall

Route = Literal["conversational", "database"]


class MCPError(RuntimeError):
    """Error communicating with the MCP server."""

    pass


@dataclass
class ToolExecution:
    """Record of a tool call and its result."""

    name: str
    arguments: dict[str, Any]
    result: Any
    error: str | None = None


@dataclass
class AgentResult:
    """Final result from the MCP agent."""

    answer: str
    tool_executions: list[ToolExecution] = field(default_factory=list)
    model: str = ""
    iterations: int = 0
    route: Route = "database"
    intent_reason: str = ""


# Tool definitions for Ollama's chat API (Ollama format)
STATSHIFT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search fantasy football documents by keyword. Returns relevant "
                "articles about players, matchups, injuries, and fantasy analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Search query (e.g., 'Patrick Mahomes', 'week 12 matchups')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 5, max 20)",
                    },
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_players",
            "description": (
                "Search NFL players by name. Returns player summaries with position, "
                "team, and experience."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Player name to search (e.g., 'Mahomes', 'Justin Jefferson')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 20, max 100)",
                    },
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_player",
            "description": (
                "Get detailed player information including injuries, seasons played, "
                "and game logs. Requires the player's ESPN ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "espn_id": {
                        "type": "string",
                        "description": "ESPN player ID (get this from search_players first)",
                    },
                },
                "required": ["espn_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_players",
            "description": (
                "List NFL players, optionally filtered by last name initial. "
                "Use to browse players when you don't have a specific name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "letter": {
                        "type": "string",
                        "description": "Filter by last name initial (a-z)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 50, max 200)",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_categories",
            "description": "List available document categories in the StatShift database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "unused": {
                        "type": "string",
                        "description": "Leave empty; no parameters needed.",
                    },
                },
            },
        },
    },
]

CONVERSATIONAL_PROMPT = """You are StatShift, a friendly fantasy football analytics assistant.

Answer the user's message helpfully using your general NFL and fantasy football knowledge.
You may share opinions, context, and analysis in a conversational tone.

Do not claim you searched a database or cite specific StatShift records unless the user
asks for exact stats, game logs, or documented analysis from the app."""

TOOLS_SYSTEM_PROMPT = """You are StatShift, a fantasy football analytics assistant.

You have tools that query the StatShift database (NFL players, injuries, game logs,
fantasy analysis documents). Use them when you need specific facts from the database.

When answering:
1. Use search_players to find players by name, then get_player for detailed stats
2. Use search_documents for stored analysis articles
3. Prefer database facts when available; cite what the tools return"""

DEFINITIVE_FALLBACK_PREFIX = (
    f"{TOOLS_SYSTEM_PROMPT}\n\n"
    "Below is data retrieved from StatShift. Use it when relevant. "
    "If a section is empty, you may still answer using general football knowledge, "
    "but say when StatShift had no matching records.\n\n"
)


def _should_fallback_from_ollama_error(exc: OllamaError) -> bool:
    """Return True when tool-calling chat is unlikely to work."""
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "500",
            "memory",
            "tool",
            "parser",
            "not found",
            "unsupported",
        )
    )


_SKIP_NAME_TOKENS = frozenset(
    {"what", "who", "how", "when", "where", "why", "which", "the", "a", "an"}
)


def _player_search_terms(query: str) -> list[str]:
    """Build one or more name tokens to search in the player index."""
    cleaned = query.replace("?", " ").replace("'", " ")
    words = [w.strip(",.") for w in cleaned.split() if w.strip(",.")]
    terms: list[str] = []
    for word in words:
        if (
            word
            and word[0].isupper()
            and len(word) > 2
            and word.lower() not in _SKIP_NAME_TOKENS
            and word not in terms
        ):
            terms.append(word)
    if terms:
        return list(reversed(terms))
    fallback = cleaned.strip()
    return [fallback] if fallback else [query]


class MCPAgent:
    """Agent that uses LLM tool calling to query the StatShift API via MCP."""

    def __init__(
        self,
        ollama: OllamaClient | None = None,
        api_base_url: str | None = None,
        max_iterations: int = 5,
    ) -> None:
        self.ollama = ollama or OllamaClient()
        self.api_base_url = (api_base_url or settings.api_base_url).rstrip("/")
        self.max_iterations = max_iterations

    def _execute_tool(self, tool_call: ToolCall) -> ToolExecution:
        """Execute a tool call against the StatShift API."""
        name = tool_call.name
        args = tool_call.arguments

        endpoint_map = {
            "search_documents": "/search",
            "search_players": "/players/search",
            "get_player": "/players/{espn_id}",
            "list_players": "/players",
            "list_categories": "/categories",
        }

        endpoint = endpoint_map.get(name)
        if not endpoint:
            return ToolExecution(
                name=name,
                arguments=args,
                result=None,
                error=f"Unknown tool: {name}",
            )

        try:
            if name == "get_player":
                espn_id = args.get("espn_id", "")
                url = f"{self.api_base_url}/players/{espn_id}"
                response = httpx.get(url, timeout=15.0)
            else:
                url = f"{self.api_base_url}{endpoint}"
                response = httpx.get(url, params=args, timeout=15.0)

            if response.status_code == 404:
                return ToolExecution(
                    name=name,
                    arguments=args,
                    result=None,
                    error="Not found",
                )

            response.raise_for_status()
            result = response.json()

            return ToolExecution(
                name=name,
                arguments=args,
                result=result,
            )

        except httpx.HTTPError as e:
            return ToolExecution(
                name=name,
                arguments=args,
                result=None,
                error=f"API error: {type(e).__name__} - {str(e)}",
            )

    def _initial_messages(self, query: str, *, system: str) -> list[dict[str, Any]]:
        """Build chat messages (Gemma uses a minimal template; avoid system role)."""
        return [
            {
                "role": "user",
                "content": f"{system}\n\nUser question: {query}",
            },
        ]

    def _ask_conversational(self, query: str, *, intent_reason: str) -> AgentResult:
        """Open-ended chat with no database tools."""
        messages = self._initial_messages(query, system=CONVERSATIONAL_PROMPT)
        response = self.ollama.chat(messages=messages, tools=None)
        return AgentResult(
            answer=response.content or "I couldn't generate a response.",
            tool_executions=[],
            model=self.ollama.model,
            iterations=1,
            route="conversational",
            intent_reason=intent_reason,
        )

    def _ask_with_tools(self, query: str, *, intent_reason: str = "") -> AgentResult:
        """Process a user query using Ollama native tool calling."""
        messages = self._initial_messages(query, system=TOOLS_SYSTEM_PROMPT)
        tool_executions: list[ToolExecution] = []
        iterations = 0

        while iterations < self.max_iterations:
            iterations += 1

            response: ChatResponse = self.ollama.chat(
                messages=messages,
                tools=STATSHIFT_TOOLS,
            )

            if not response.tool_calls:
                return AgentResult(
                    answer=response.content or "I couldn't find relevant information.",
                    tool_executions=tool_executions,
                    model=self.ollama.model,
                    iterations=iterations,
                    route="database",
                    intent_reason=intent_reason,
                )

            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in response.tool_calls
                ],
            }
            messages.append(assistant_message)

            for tc in response.tool_calls:
                execution = self._execute_tool(tc)
                tool_executions.append(execution)

                if execution.error:
                    tool_result = {"error": execution.error}
                else:
                    tool_result = execution.result

                messages.append(
                    {
                        "role": "tool",
                        "tool_name": tc.name,
                        "content": json.dumps(tool_result, default=str),
                    }
                )

        return AgentResult(
            answer="I reached the maximum number of tool calls. Please try a simpler question.",
            tool_executions=tool_executions,
            model=self.ollama.model,
            iterations=iterations,
            route="database",
            intent_reason=intent_reason,
        )

    def _ask_with_prefetched_tools(
        self, query: str, *, intent_reason: str = ""
    ) -> AgentResult:
        """Fallback: call API tools directly, then ask the model without tool support."""
        tool_executions: list[ToolExecution] = []
        context_blocks: list[str] = []
        players_found: list[dict[str, Any]] = []

        for term in _player_search_terms(query):
            player_exec = self._execute_tool(
                ToolCall(name="search_players", arguments={"q": term, "limit": 10})
            )
            tool_executions.append(player_exec)
            if isinstance(player_exec.result, list) and player_exec.result:
                players_found = player_exec.result
                context_blocks.append(
                    f"search_players({term!r}):\n"
                    f"{json.dumps(player_exec.result, indent=2, default=str)}"
                )
                break
            if player_exec.error:
                context_blocks.append(f"search_players({term!r}) error: {player_exec.error}")

        doc_exec = self._execute_tool(
            ToolCall(name="search_documents", arguments={"q": query, "limit": 5})
        )
        tool_executions.append(doc_exec)
        if doc_exec.result:
            context_blocks.append(
                f"search_documents:\n{json.dumps(doc_exec.result, indent=2, default=str)}"
            )

        if players_found:
            top = players_found[0]
            espn_id = top.get("espn_id") if isinstance(top, dict) else None
            if espn_id:
                detail_exec = self._execute_tool(
                    ToolCall(name="get_player", arguments={"espn_id": str(espn_id)})
                )
                tool_executions.append(detail_exec)
                if detail_exec.result:
                    context_blocks.append(
                        f"get_player({espn_id}):\n"
                        f"{json.dumps(detail_exec.result, indent=2, default=str)}"
                    )

        context = "\n\n".join(context_blocks) or "No matching StatShift records were found."
        prompt = (
            f"{DEFINITIVE_FALLBACK_PREFIX}"
            f"Data from StatShift:\n{context}\n\n"
            f"User question: {query}\n\n"
            "Answer the user."
        )

        answer = self.ollama.generate(prompt, temperature=0.2)
        return AgentResult(
            answer=answer,
            tool_executions=tool_executions,
            model=self.ollama.model,
            iterations=1,
            route="database",
            intent_reason=intent_reason,
        )

    def ask(
        self,
        query: str,
        *,
        intent: IntentResult | None = None,
    ) -> AgentResult:
        """Route open-ended prompts to the LLM; factual prompts use the database.

        Args:
            query: User's natural language question.
            intent: Optional precomputed intent; detected automatically if omitted.

        Returns:
            AgentResult with the answer and tool execution history.

        Raises:
            OllamaError: On LLM communication errors (after fallback exhausted).
            MCPError: On API/tool execution errors that prevent answering.
        """
        resolved = intent or detect_prompt_intent(query)

        if resolved.intent == PromptIntent.CONVERSATIONAL:
            return self._ask_conversational(query, intent_reason=resolved.reason)

        try:
            return self._ask_with_tools(query, intent_reason=resolved.reason)
        except OllamaError as exc:
            if not _should_fallback_from_ollama_error(exc):
                raise
            try:
                return self._ask_with_prefetched_tools(
                    query, intent_reason=resolved.reason
                )
            except OllamaError:
                raise exc from None

    def health(self) -> dict[str, Any]:
        """Check health of the agent's dependencies."""
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
