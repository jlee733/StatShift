#!/usr/bin/env python3
"""Scrape ffanalytics projections/ADP and cache for mock drafts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from draft.ffanalytics_loader import CACHE_PATH, fetch_ffanalytics_players, save_player_cache


def main() -> None:
    print("Scraping projections and ADP via ffanalytics (may take several minutes)...")
    players = fetch_ffanalytics_players()
    path = save_player_cache(players)
    print(f"Saved {len(players)} draftable players to {path}")


if __name__ == "__main__":
    main()
