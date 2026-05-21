"""Prefect flow: scrape all active NFL players by last-name letter (a-z).

Fetches every active athlete from ESPN, partitions by last name initial,
enriches each player with injury info and game logs (last 3 seasons),
writes per-letter JSON caches, merges into data/espn_active_players_full.json,
then loads all player data into SQLite for the API.

Expected runtime: tens of minutes depending on roster size and network.

Run:
    python -m jobs.scrape_active_players
"""

from __future__ import annotations

from prefect import flow

from espn.scrape import LETTERS
from jobs.espn_tasks import (
    list_active_refs_task,
    load_players_to_db_task,
    merge_letter_caches_task,
    scrape_letter_task,
)


@flow(name="scrape_active_players", log_prints=True)
def scrape_active_players_flow(
    *,
    seasons_back: int = 3,
    max_workers: int = 8,
) -> dict:
    """Scrape active NFL players partitioned by last-name initial a-z."""
    print("Listing active athlete refs from ESPN...")
    ref_data = list_active_refs_task()
    refs = ref_data["refs"]
    team_map = ref_data["team_map"]
    print(f"Found {len(refs)} active athlete refs")

    print("Scraping players by last-name letter (a-z)...")
    letter_results = scrape_letter_task.map(
        LETTERS,
        refs=[refs] * len(LETTERS),
        team_map=[team_map] * len(LETTERS),
        seasons_back=[seasons_back] * len(LETTERS),
        max_workers=[max_workers] * len(LETTERS),
    )

    total = sum(r["count"] for r in letter_results)
    print(f"Scraped {total} players across {len(LETTERS)} letter buckets")

    print("Merging letter caches...")
    merged = merge_letter_caches_task()
    print(f"Merged cache written to {merged['path']}")

    print("Loading players into SQLite...")
    db_result = load_players_to_db_task(merged["path"])
    print(
        f"Loaded {db_result['player_count']} players into {db_result['db_path']} "
        f"({db_result['gamelog_rows']} game log rows)"
    )

    return {
        "ref_count": len(refs),
        "player_count": db_result["player_count"],
        "merged_path": merged["path"],
        "db_path": db_result["db_path"],
        "letters": letter_results,
        "db_load": db_result,
    }


if __name__ == "__main__":
    scrape_active_players_flow()
