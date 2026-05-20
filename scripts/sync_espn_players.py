#!/usr/bin/env python3
"""Download active NFL players from ESPN and cache for mock drafts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from draft.espn_loader import CACHE_PATH, fetch_active_players, save_player_cache


def main() -> None:
    print("Fetching active NFL players from ESPN (this may take 1–2 minutes)...")
    players = fetch_active_players()
    path = save_player_cache(players)
    print(f"Saved {len(players)} draftable players to {path}")


if __name__ == "__main__":
    main()
