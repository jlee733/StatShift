"""Player pool for mock drafts — loaded from ffanalytics via rpy2."""

from __future__ import annotations

from draft.ffanalytics_loader import (
    CACHE_PATH,
    cache_is_fresh,
    load_active_players,
    load_player_cache,
)
from draft.models import Player

_players: list[Player] | None = None


def get_players(*, force_refresh: bool = False) -> list[Player]:
    """Return the draftable player pool (cached ffanalytics projections + ADP)."""
    global _players
    if force_refresh or _players is None:
        _players = load_active_players(force_refresh=force_refresh)
    return _players


def player_pool_size() -> int:
    if _players is not None:
        return len(_players)
    cached = load_player_cache()
    if cached:
        return len(cached)
    return 0


def max_rounds_for_league(league_size: int) -> int:
    """Maximum draft rounds supported without running out of players."""
    size = player_pool_size()
    if size == 0:
        return 15
    return size // max(league_size, 1)


# Lazy default for imports; call refresh_players() before draft in UI
PLAYERS: list[Player] = []


def refresh_players(*, force_refresh: bool = False) -> list[Player]:
    """Load or refresh pool and update module-level PLAYERS."""
    global PLAYERS, _players
    _players = load_active_players(force_refresh=force_refresh)
    PLAYERS = _players
    return _players


def cache_status() -> str:
    if cache_is_fresh():
        cached = load_player_cache()
        count = len(cached) if cached else 0
        return f"ffanalytics cache ({count} players) at {CACHE_PATH.name}"
    if CACHE_PATH.exists():
        return "ffanalytics cache stale — will refresh on next load"
    return "No ffanalytics cache — will scrape on first Mock Draft load"
