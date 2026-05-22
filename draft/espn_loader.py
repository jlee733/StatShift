"""Load active NFL players from ESPN into draft Player models."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from config import settings
from draft.models import Player, Position
from espn.rate_limit import wait_before_espn_request
from espn.scrape import list_active_athlete_refs

FANTASY_ABBREV: dict[str, Position] = {
    "QB": Position.QB,
    "RB": Position.RB,
    "WR": Position.WR,
    "TE": Position.TE,
    "K": Position.K,
    "PK": Position.K,
    "FB": Position.RB,
}

POSITION_BASE_FP: dict[Position, float] = {
    Position.QB: 17.0,
    Position.RB: 11.0,
    Position.WR: 10.0,
    Position.TE: 8.5,
    Position.K: 7.5,
}

CACHE_PATH = settings.project_root / "data" / "espn_active_players.json"
CACHE_MAX_AGE_HOURS = 24
_RESOLVE_WORKERS = 32


def _cache_path(path: Path | None = None) -> Path:
    return path or CACHE_PATH


def _estimate_fantasy_points(position: Position, experience_years: int) -> tuple[float, float, float]:
    base = POSITION_BASE_FP[position] + min(experience_years, 12) * 0.35
    if position in (Position.WR, Position.RB, Position.TE):
        return (
            round(base + 1.2, 1),
            round(base + 0.6, 1),
            round(base, 1),
        )
    return (round(base, 1), round(base, 1), round(base, 1))


def parse_athlete_payload(
    payload: dict[str, Any],
    team_abbreviations: dict[str, str],
) -> Player | None:
    from espn.scrape import team_id_from_ref

    pos_data = payload.get("position") or {}
    abbrev = (pos_data.get("abbreviation") or "").upper()
    position = FANTASY_ABBREV.get(abbrev)
    if position is None:
        return None

    name = payload.get("displayName") or payload.get("fullName") or ""
    if not name:
        return None

    experience = payload.get("experience") or {}
    years = int(experience.get("years") or 0)

    team = ""
    team_ref = payload.get("team") or {}
    if isinstance(team_ref, dict):
        ref = team_ref.get("$ref", "")
        team_id = team_ref.get("id") or team_id_from_ref(ref)
        if team_id:
            team = team_abbreviations.get(str(team_id), "")

    fp_ppr, fp_half, fp_std = _estimate_fantasy_points(position, years)

    return Player(
        name=name,
        position=position,
        fp_ppr=fp_ppr,
        fp_half=fp_half,
        fp_std=fp_std,
        team=team,
        adp=999.0,
    )


def _resolve_athlete(
    ref: str,
    team_map: dict[str, str],
    http: httpx.Client,
) -> Player | None:
    wait_before_espn_request()
    response = http.get(ref)
    response.raise_for_status()
    return parse_athlete_payload(response.json(), team_map)


def fetch_active_players(
    *,
    timeout: float = 30.0,
    max_workers: int = _RESOLVE_WORKERS,
) -> list[Player]:
    """Fetch all active NFL players draftable in fantasy (QB/RB/WR/TE/K)."""
    refs, team_map, _ = list_active_athlete_refs(timeout=timeout)

    with httpx.Client(timeout=timeout, follow_redirects=True) as http:
        players: list[Player] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_resolve_athlete, ref, team_map, http): ref
                for ref in refs
            }
            for future in as_completed(futures):
                try:
                    player = future.result()
                    if player is not None:
                        players.append(player)
                except httpx.HTTPError:
                    continue

    players.sort(key=lambda p: p.fp_ppr, reverse=True)
    for rank, player in enumerate(players, start=1):
        player.adp = float(rank)
    return players


def save_player_cache(players: list[Player], path: Path | None = None) -> Path:
    target = _cache_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(players),
        "players": [
            {
                "name": p.name,
                "position": p.position.value,
                "fp_ppr": p.fp_ppr,
                "fp_half": p.fp_half,
                "fp_std": p.fp_std,
                "team": p.team,
                "adp": p.adp,
            }
            for p in players
        ],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def load_player_cache(path: Path | None = None) -> list[Player] | None:
    target = _cache_path(path)
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    players: list[Player] = []
    for row in payload.get("players", []):
        try:
            players.append(
                Player(
                    name=row["name"],
                    position=Position(row["position"]),
                    fp_ppr=float(row["fp_ppr"]),
                    fp_half=float(row["fp_half"]),
                    fp_std=float(row["fp_std"]),
                    team=row.get("team", ""),
                    adp=float(row.get("adp", 999)),
                )
            )
        except (KeyError, ValueError):
            continue
    return players if players else None


def cache_is_fresh(path: Path | None = None, max_age_hours: int = CACHE_MAX_AGE_HOURS) -> bool:
    target = _cache_path(path)
    if not target.exists():
        return False
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        return age_hours < max_age_hours
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        return False


def load_active_players(
    *,
    force_refresh: bool = False,
    cache_path: Path | None = None,
) -> list[Player]:
    path = _cache_path(cache_path)
    if not force_refresh and cache_is_fresh(path):
        cached = load_player_cache(path)
        if cached:
            return cached

    players = fetch_active_players()
    save_player_cache(players, path)
    return players
