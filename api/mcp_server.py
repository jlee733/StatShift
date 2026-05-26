"""MCP server exposing StatShift API endpoints as tools for LLM agents."""

from __future__ import annotations

from fastapi_mcp import FastApiMCP


def create_mcp_server(app) -> FastApiMCP:
    """Create an MCP server that wraps the FastAPI app endpoints as tools.

    The MCP server exposes these tools to LLM agents:
    - search_documents: Full-text search for fantasy football documents
    - list_players: List NFL players by last name initial
    - search_players: Search players by name
    - get_player: Get player details including injuries and game logs
    - list_categories: List available document categories

    Args:
        app: The FastAPI application instance.

    Returns:
        FastApiMCP instance ready to be mounted.
    """
    mcp = FastApiMCP(
        app,
        name="statshift",
        description=(
            "StatShift fantasy football API. Use these tools to query NFL player "
            "statistics, injuries, game logs, and fantasy football analysis documents."
        ),
        include_operations=[
            "search_documents",
            "list_documents",
            "get_document",
            "list_players",
            "search_players",
            "get_player",
            "list_categories",
        ],
    )
    return mcp
