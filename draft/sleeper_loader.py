"""Load player rankings from the Sleeper API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests

from config import settings

SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
CACHE_PATH = settings.project_root / "data" / "sleeper_players.json"
CACHE_MAX_AGE_HOURS = 24


def _normalize_name(name: str) -> str:
    """Normalize player name for matching: lowercase, strip suffixes."""
    name = name.lower().strip()
    for suffix in (" jr", " sr", " ii", " iii", " iv", " v"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def fetch_sleeper_players() -> dict[str, Any]:
    """Fetch all NFL players from Sleeper API."""
    resp = requests.get(SLEEPER_PLAYERS_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_sleeper_rankings(raw: dict[str, Any]) -> dict[str, int]:
    """
    Extract player name -> search_rank mapping from Sleeper data.
    
    Returns a dict mapping normalized player names to their search_rank.
    Lower search_rank = higher ranked player.
    """
    rankings: dict[str, int] = {}
    
    for player_id, data in raw.items():
        if not isinstance(data, dict):
            continue
        
        position = data.get("position", "")
        if position not in ("QB", "RB", "WR", "TE", "K", "DEF"):
            continue
        
        search_rank = data.get("search_rank")
        if search_rank is None or not isinstance(search_rank, (int, float)):
            continue
        
        first_name = data.get("first_name", "") or ""
        last_name = data.get("last_name", "") or ""
        full_name = f"{first_name} {last_name}".strip()
        
        if not full_name:
            continue
        
        normalized = _normalize_name(full_name)
        current = rankings.get(normalized)
        if current is None or search_rank < current:
            rankings[normalized] = int(search_rank)
    
    return rankings


def save_sleeper_cache(rankings: dict[str, int], path: Any = None) -> Any:
    """Save Sleeper rankings to cache file."""
    target = path or CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "sleeper",
        "count": len(rankings),
        "rankings": rankings,
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def load_sleeper_cache(path: Any = None) -> dict[str, int] | None:
    """Load cached Sleeper rankings if available and fresh."""
    target = path or CACHE_PATH
    if not target.exists():
        return None
    
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        
        if age_hours >= CACHE_MAX_AGE_HOURS:
            return None
        
        return payload.get("rankings", {})
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        return None


def get_sleeper_rankings(*, force_refresh: bool = False) -> dict[str, int]:
    """
    Get Sleeper search_rank for all NFL players.
    
    Returns a dict mapping normalized player names to their search_rank.
    Uses cached data if available and fresh (< 24 hours old).
    """
    if not force_refresh:
        cached = load_sleeper_cache()
        if cached is not None:
            return cached
    
    raw = fetch_sleeper_players()
    rankings = parse_sleeper_rankings(raw)
    save_sleeper_cache(rankings)
    return rankings


def lookup_sleeper_rank(name: str, rankings: dict[str, int]) -> float:
    """Look up a player's Sleeper rank by name, returning 999.0 if not found."""
    normalized = _normalize_name(name)
    rank = rankings.get(normalized)
    return float(rank) if rank is not None else 999.0
