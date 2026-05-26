"""Tests for player search (profile lookup endpoint, no scrape throttle)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from espn.player import search_players


class SearchPlayersTests(unittest.TestCase):
    @patch("espn.player._search_players_from_db", return_value=[])
    @patch("espn.player._fetch_athlete_core")
    @patch("espn.player._get_json")
    def test_espn_search_uses_profile_athlete_endpoint(
        self,
        mock_get_json: MagicMock,
        mock_fetch: MagicMock,
        _mock_db: MagicMock,
    ) -> None:
        mock_get_json.return_value = {
            "items": [
                {
                    "id": "3139477",
                    "displayName": "Patrick Mahomes",
                    "isActive": True,
                    "isRetired": False,
                    "teamRelationships": [
                        {"type": "team", "displayName": "Kansas City Chiefs"},
                    ],
                },
            ]
        }
        mock_fetch.return_value = {
            "id": "3139477",
            "displayName": "Patrick Mahomes",
            "position": {"abbreviation": "QB"},
            "status": {"name": "Active"},
        }

        results = search_players("Mahomes", limit=10)

        mock_get_json.assert_called_once()
        mock_fetch.assert_called_once_with("3139477")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["position"], "QB")
        self.assertIs(results[0]["athlete"], mock_fetch.return_value)


if __name__ == "__main__":
    unittest.main()
