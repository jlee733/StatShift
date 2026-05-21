"""Tests for loading scraped players into SQLite."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.read import ReadOnlyDatabase
from db.store import load_players_into_db
from scripts.init_db import init_database


SAMPLE_PLAYERS = [
    {
        "id": "1001",
        "firstName": "Patrick",
        "lastName": "Mahomes",
        "displayName": "Patrick Mahomes",
        "position": "QB",
        "team": "KC",
        "experience": 8,
        "draft_year": 2017,
        "status": "Active",
        "injuries": [
            {
                "status": "Active",
                "injury_type": "—",
                "details": "No injury information available",
                "date": "—",
            }
        ],
        "seasons": [2024],
        "game_logs": {
            "2024": [
                {
                    "week": 1,
                    "opponent": "BAL",
                    "result": "W",
                    "passing_yards": 291,
                    "passing_tds": 1,
                    "interceptions": 1,
                    "rushing_yards": 3,
                    "rushing_tds": 0,
                    "receptions": 0,
                    "receiving_yards": 0,
                    "receiving_tds": 0,
                    "fumbles_lost": 0,
                }
            ]
        },
    }
]


class PlayerStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test.db"
        init_database(self.db_path)
        self.db = ReadOnlyDatabase(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_load_players_into_db(self) -> None:
        result = load_players_into_db(SAMPLE_PLAYERS, self.db_path)
        self.assertEqual(result["player_count"], 1)
        self.assertEqual(result["gamelog_rows"], 1)

        self.assertEqual(self.db.count_players(), 1)
        player = self.db.get_player("1001")
        assert player is not None
        self.assertEqual(player["display_name"], "Patrick Mahomes")
        self.assertEqual(player["last_name_initial"], "m")
        self.assertEqual(len(player["injuries"]), 1)
        self.assertIn("2024", player["game_logs"])
        self.assertEqual(player["game_logs"]["2024"][0]["passing_yards"], 291)


if __name__ == "__main__":
    unittest.main()
