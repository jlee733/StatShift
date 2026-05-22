"""Prefect tasks for ESPN active player scraping."""

from __future__ import annotations

from typing import Any

import httpx
from prefect import task

from db.store import load_merged_cache_into_db
from espn.scrape import (
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
    active_athlete_refs_cache_fetched_at,
    active_athlete_refs_cache_path,
    list_active_athlete_refs,
    merge_letter_caches,
    save_letter_cache,
    scrape_active_players_for_letter,
)


@task(name="list_active_athlete_refs", retries=2, retry_delay_seconds=10)
def list_active_refs_task(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    force_refresh: bool = False,
    max_age_hours: float | None = None,
) -> dict[str, Any]:
    """Fetch all active athlete refs and team map (shared across letter tasks)."""
    cache_path = active_athlete_refs_cache_path()
    refs, team_map, from_cache = list_active_athlete_refs(
        timeout=timeout,
        force_refresh=force_refresh,
        cache_path=cache_path,
        max_age_hours=max_age_hours,
    )
    return {
        "refs": refs,
        "team_map": team_map,
        "ref_count": len(refs),
        "from_cache": from_cache,
        "cache_path": str(cache_path),
        "fetched_at": active_athlete_refs_cache_fetched_at(cache_path),
    }


@task(name="scrape_letter", retries=2, retry_delay_seconds=15)
def scrape_letter_task(
    letter: str,
    refs: list[str],
    team_map: dict[str, str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    seasons_back: int = 3,
    max_workers: int = DEFAULT_WORKERS,
) -> dict[str, Any]:
    """Scrape active players for one last-name letter and write per-letter cache."""
    with httpx.Client(timeout=timeout, follow_redirects=True) as http:
        players = scrape_active_players_for_letter(
            letter,
            refs,
            team_map,
            http,
            seasons_back=seasons_back,
            max_workers=max_workers,
        )
    path = save_letter_cache(letter, players)
    return {
        "letter": letter.lower(),
        "count": len(players),
        "path": str(path),
    }


@task(name="merge_letter_caches")
def merge_letter_caches_task() -> dict[str, Any]:
    """Merge per-letter caches into a single JSON file."""
    path = merge_letter_caches()
    return {"path": str(path)}


@task(name="load_players_to_sqlite", retries=1, retry_delay_seconds=5)
def load_players_to_db_task(merged_path: str) -> dict[str, Any]:
    """Load merged JSON scrape results into SQLite for the API."""
    from pathlib import Path

    return load_merged_cache_into_db(Path(merged_path))
