"""Scrape active NFL players from ESPN, partitioned by last-name initial."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from config import settings
from espn.client import ESPNEndpoint
from espn.rate_limit import wait_before_espn_request
from espn.player import (
    gamelog_to_dict,
    get_player_gamelog,
    get_player_injuries,
    get_player_seasons,
    injury_to_dict,
)

LIST_PAGE_SIZE = 1000
DEFAULT_TIMEOUT = 30.0
DEFAULT_WORKERS = 8
LETTERS = [chr(c) for c in range(ord("a"), ord("z") + 1)]


def letter_cache_dir() -> Path:
    return settings.espn_letter_cache_dir


def merged_cache_path() -> Path:
    return settings.espn_active_players_full_path


def active_athlete_refs_cache_path() -> Path:
    return settings.espn_active_athlete_refs_cache_path


def team_id_from_ref(ref: str) -> str | None:
    match = re.search(r"/teams/(\d+)", ref)
    return match.group(1) if match else None


def last_name_initial(last_name: str) -> str | None:
    """Return a-z bucket for a last name, or None if not alphabetic."""
    cleaned = (last_name or "").strip()
    if not cleaned:
        return None
    first = cleaned[0].lower()
    return first if first.isalpha() and "a" <= first <= "z" else None


def load_team_abbreviations(
    http: httpx.Client,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, str]:
    """Build team id -> abbreviation map from ESPN teams endpoint."""
    teams_api = ESPNEndpoint("teams", client=http, timeout=timeout)
    mapping: dict[str, str] = {}
    for item in teams_api.iter_items(limit=50):
        payload = teams_api.resolve_ref(item)
        team_id = str(payload.get("id", ""))
        abbrev = payload.get("abbreviation") or payload.get("shortDisplayName") or ""
        if team_id and abbrev:
            mapping[team_id] = abbrev
    return mapping


def fetch_active_athlete_refs_from_api(
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[list[str], dict[str, str]]:
    """Fetch all active athlete $ref URLs and team abbreviation map from ESPN."""
    with ESPNEndpoint("athletes", timeout=timeout) as api:
        team_map = load_team_abbreviations(api.client, timeout=timeout)
        refs: list[str] = []
        for page in api.iter_pages(limit=LIST_PAGE_SIZE, params={"active": "true"}):
            for item in page.get("items", []):
                ref = item.get("$ref")
                if ref:
                    refs.append(ref)
        return refs, team_map


def save_active_athlete_refs_cache(
    refs: list[str],
    team_map: dict[str, str],
    path: Path | None = None,
) -> Path:
    """Persist athlete refs and team map for reuse across scrape runs."""
    target = path or active_athlete_refs_cache_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ref_count": len(refs),
        "refs": refs,
        "team_map": team_map,
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def load_active_athlete_refs_cache(
    path: Path | None = None,
) -> tuple[list[str], dict[str, str]] | None:
    """Load cached refs and team map, or None if missing or invalid."""
    target = path or active_athlete_refs_cache_path()
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        refs = payload.get("refs")
        team_map = payload.get("team_map")
        if not isinstance(refs, list) or not isinstance(team_map, dict):
            return None
        if not refs:
            return None
        return [str(r) for r in refs], {str(k): str(v) for k, v in team_map.items()}
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def active_athlete_refs_cache_is_fresh(
    path: Path | None = None,
    *,
    max_age_hours: float | None = None,
) -> bool:
    """True if cache file exists and is younger than max_age_hours."""
    target = path or active_athlete_refs_cache_path()
    if not target.exists():
        return False
    limit = (
        max_age_hours
        if max_age_hours is not None
        else settings.espn_active_athlete_refs_cache_max_age_hours
    )
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        return age_hours < limit
    except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError):
        return False


def active_athlete_refs_cache_fetched_at(path: Path | None = None) -> str | None:
    """ISO timestamp from cache metadata, if present."""
    target = path or active_athlete_refs_cache_path()
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        value = payload.get("fetched_at")
        return str(value) if value else None
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def list_active_athlete_refs(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    force_refresh: bool = False,
    cache_path: Path | None = None,
    max_age_hours: float | None = None,
) -> tuple[list[str], dict[str, str], bool]:
    """Return active athlete refs, team map, and whether the JSON cache was used."""
    path = cache_path or active_athlete_refs_cache_path()
    if not force_refresh and active_athlete_refs_cache_is_fresh(
        path, max_age_hours=max_age_hours
    ):
        cached = load_active_athlete_refs_cache(path)
        if cached is not None:
            return cached[0], cached[1], True

    refs, team_map = fetch_active_athlete_refs_from_api(timeout=timeout)
    save_active_athlete_refs_cache(refs, team_map, path)
    return refs, team_map, False


def resolve_athlete_summary(
    ref: str,
    team_map: dict[str, str],
    http: httpx.Client,
) -> dict[str, Any] | None:
    """Resolve an athlete ref to core summary fields."""
    try:
        wait_before_espn_request()
        response = http.get(ref)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError:
        return None

    last_name = (payload.get("lastName") or "").strip()
    if not last_name:
        return None

    team = ""
    team_ref = payload.get("team") or {}
    if isinstance(team_ref, dict):
        team_ref_url = team_ref.get("$ref", "")
        team_id = team_ref.get("id") or team_id_from_ref(team_ref_url)
        if team_id:
            team = team_map.get(str(team_id), "")

    pos_data = payload.get("position") or {}
    draft = payload.get("draft") or {}
    status_data = payload.get("status") or {}
    experience = payload.get("experience") or {}

    return {
        "id": str(payload.get("id") or ""),
        "firstName": payload.get("firstName") or "",
        "lastName": last_name,
        "displayName": payload.get("displayName") or payload.get("fullName") or "",
        "position": pos_data.get("abbreviation") or pos_data.get("displayName") or "",
        "team": team,
        "experience": int(experience.get("years") or 0),
        "draft_year": draft.get("year"),
        "status": status_data.get("name") or status_data.get("type") or "Active",
    }


def enrich_player_stats_and_injuries(
    player_id: str,
    *,
    seasons_back: int = 3,
) -> dict[str, Any]:
    """Fetch injuries and recent season game logs for a player."""
    injuries = [injury_to_dict(i) for i in get_player_injuries(player_id)]
    seasons = get_player_seasons(player_id)
    selected_seasons = seasons[:seasons_back] if seasons else []

    game_logs: dict[str, list[dict[str, Any]]] = {}
    for season in selected_seasons:
        entries = get_player_gamelog(player_id, season)
        if entries:
            game_logs[str(season)] = [gamelog_to_dict(e) for e in entries]

    return {
        "injuries": injuries,
        "seasons": selected_seasons,
        "game_logs": game_logs,
    }


def _process_ref_for_letter(
    ref: str,
    letter: str,
    team_map: dict[str, str],
    http: httpx.Client,
    *,
    seasons_back: int,
) -> dict[str, Any] | None:
    summary = resolve_athlete_summary(ref, team_map, http)
    if summary is None:
        return None
    if last_name_initial(summary["lastName"]) != letter:
        return None

    player_id = summary["id"]
    if not player_id:
        return None

    try:
        enrichment = enrich_player_stats_and_injuries(
            player_id, seasons_back=seasons_back
        )
    except httpx.HTTPError:
        enrichment = {"injuries": [], "seasons": [], "game_logs": {}}

    return {**summary, **enrichment}


def scrape_active_players_for_letter(
    letter: str,
    refs: list[str],
    team_map: dict[str, str],
    http: httpx.Client,
    *,
    seasons_back: int = 3,
    max_workers: int = DEFAULT_WORKERS,
) -> list[dict[str, Any]]:
    """Scrape active players whose last name starts with the given letter."""
    letter = letter.lower().strip()
    if letter not in LETTERS:
        raise ValueError(f"letter must be a-z, got {letter!r}")

    players: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _process_ref_for_letter,
                ref,
                letter,
                team_map,
                http,
                seasons_back=seasons_back,
            ): ref
            for ref in refs
        }
        for future in as_completed(futures):
            try:
                record = future.result()
                if record is not None:
                    players.append(record)
            except httpx.HTTPError:
                continue

    players.sort(key=lambda p: p.get("lastName", "").lower())
    return players


def save_letter_cache(letter: str, players: list[dict[str, Any]]) -> Path:
    """Write per-letter JSON cache."""
    letter = letter.lower()
    target_dir = letter_cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{letter}.json"
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "letter": letter,
        "count": len(players),
        "players": players,
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def load_letter_cache(letter: str) -> list[dict[str, Any]]:
    """Load players from a per-letter cache file."""
    target = letter_cache_dir() / f"{letter.lower()}.json"
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return payload.get("players", [])


def merge_letter_caches() -> Path:
    """Merge all letter caches into a single JSON file."""
    all_players: list[dict[str, Any]] = []
    for letter in LETTERS:
        all_players.extend(load_letter_cache(letter))

    all_players.sort(key=lambda p: (p.get("lastName", "").lower(), p.get("displayName", "")))
    target = merged_cache_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(all_players),
        "players": all_players,
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target
