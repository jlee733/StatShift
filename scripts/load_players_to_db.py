#!/usr/bin/env python3
"""Load merged ESPN player JSON cache into SQLite."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.store import load_merged_cache_into_db


def main() -> None:
    result = load_merged_cache_into_db()
    print(
        f"Loaded {result['player_count']} players into {result['db_path']} "
        f"({result['injury_rows']} injuries, {result['gamelog_rows']} game logs)"
    )


if __name__ == "__main__":
    main()
