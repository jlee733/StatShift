"""Write scraped ESPN player data into SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings
from db.schema import SCHEMA_SQL
from espn.scrape import last_name_initial, merged_cache_path


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they do not exist."""
    conn.executescript(SCHEMA_SQL)


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_players_into_db(
    players: list[dict[str, Any]],
    db_path: Path | None = None,
    *,
    source: str = "espn",
) -> dict[str, Any]:
    """
    Replace all player rows in SQLite with the given scrape results.
    Clears existing players, injuries, and game logs, then inserts fresh data.
    """
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        ensure_schema(conn)

        conn.execute("DELETE FROM player_game_logs")
        conn.execute("DELETE FROM player_injuries")
        conn.execute("DELETE FROM players")

        player_rows: list[tuple[Any, ...]] = []
        injury_rows: list[tuple[Any, ...]] = []
        gamelog_rows: list[tuple[Any, ...]] = []
        now = datetime.now(timezone.utc).isoformat()

        for player in players:
            espn_id = str(player.get("id") or "").strip()
            if not espn_id:
                continue

            last_name = (player.get("lastName") or "").strip()
            initial = last_name_initial(last_name) or ""

            player_rows.append(
                (
                    espn_id,
                    player.get("firstName") or "",
                    last_name,
                    player.get("displayName") or "",
                    initial,
                    player.get("position") or "",
                    player.get("team") or "",
                    _int_or_none(player.get("experience")) or 0,
                    _int_or_none(player.get("draft_year")),
                    player.get("status") or "Active",
                    now,
                )
            )

            for injury in player.get("injuries") or []:
                injury_rows.append(
                    (
                        espn_id,
                        injury.get("status") or "",
                        injury.get("injury_type") or "",
                        injury.get("details") or "",
                        injury.get("date") or "",
                    )
                )

            game_logs = player.get("game_logs") or {}
            if isinstance(game_logs, dict):
                for season_key, entries in game_logs.items():
                    try:
                        season = int(season_key)
                    except (TypeError, ValueError):
                        continue
                    if not isinstance(entries, list):
                        continue
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        gamelog_rows.append(
                            (
                                espn_id,
                                season,
                                _int_or_none(entry.get("week")) or 0,
                                entry.get("opponent") or "",
                                entry.get("result") or "",
                                _int_or_none(entry.get("passing_yards")) or 0,
                                _int_or_none(entry.get("passing_tds")) or 0,
                                _int_or_none(entry.get("interceptions")) or 0,
                                _int_or_none(entry.get("rushing_yards")) or 0,
                                _int_or_none(entry.get("rushing_tds")) or 0,
                                _int_or_none(entry.get("receptions")) or 0,
                                _int_or_none(entry.get("receiving_yards")) or 0,
                                _int_or_none(entry.get("receiving_tds")) or 0,
                                _int_or_none(entry.get("fumbles_lost")) or 0,
                            )
                        )

        if player_rows:
            conn.executemany(
                """
                INSERT INTO players (
                    espn_id, first_name, last_name, display_name, last_name_initial,
                    position, team, experience, draft_year, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                player_rows,
            )

        if injury_rows:
            conn.executemany(
                """
                INSERT INTO player_injuries (
                    espn_id, status, injury_type, details, injury_date
                ) VALUES (?, ?, ?, ?, ?)
                """,
                injury_rows,
            )

        if gamelog_rows:
            conn.executemany(
                """
                INSERT INTO player_game_logs (
                    espn_id, season, week, opponent, result,
                    passing_yards, passing_tds, interceptions,
                    rushing_yards, rushing_tds, receptions, receiving_yards,
                    receiving_tds, fumbles_lost
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                gamelog_rows,
            )

        completed_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO scrape_runs (started_at, completed_at, player_count, source)
            VALUES (?, ?, ?, ?)
            """,
            (started_at, completed_at, len(player_rows), source),
        )
        conn.commit()

        return {
            "db_path": str(path),
            "player_count": len(player_rows),
            "injury_rows": len(injury_rows),
            "gamelog_rows": len(gamelog_rows),
            "completed_at": completed_at,
        }
    finally:
        conn.close()


def load_merged_cache_into_db(
    json_path: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Load players from the merged JSON cache file into SQLite."""
    target = json_path or merged_cache_path()
    if not target.exists():
        raise FileNotFoundError(f"Merged player cache not found: {target}")

    payload = json.loads(target.read_text(encoding="utf-8"))
    players = payload.get("players", [])
    if not isinstance(players, list):
        raise ValueError("Invalid merged cache: players must be a list")

    result = load_players_into_db(players, db_path=db_path)
    result["json_path"] = str(target)
    return result
