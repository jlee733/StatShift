"""Tests for ESPN player research helpers."""

from __future__ import annotations

import unittest
from datetime import datetime

from sdks.espn_player_loader import (
    _college_season_from_categories,
    is_upcoming_rookie,
    nfl_season_has_started,
)


class NflSeasonTests(unittest.TestCase):
    def test_season_not_started_before_september(self) -> None:
        now = datetime(2026, 5, 20)
        self.assertFalse(nfl_season_has_started(2026, now=now))

    def test_season_started_in_september(self) -> None:
        now = datetime(2026, 9, 10)
        self.assertTrue(nfl_season_has_started(2026, now=now))

    def test_rookie_when_drafted_this_year_pre_season(self) -> None:
        now = datetime(2026, 5, 20)
        self.assertTrue(is_upcoming_rookie(2026, now=now))

    def test_not_rookie_when_drafted_prior_year(self) -> None:
        now = datetime(2026, 5, 20)
        self.assertFalse(is_upcoming_rookie(2025, now=now))

    def test_not_rookie_after_season_starts(self) -> None:
        now = datetime(2026, 9, 10)
        self.assertFalse(is_upcoming_rookie(2026, now=now))


class CollegeStatsParsingTests(unittest.TestCase):
    def test_parses_categories_into_season_row(self) -> None:
        categories = [
            {
                "name": "general",
                "stats": [{"name": "gamesPlayed", "displayValue": "12"}],
            },
            {
                "name": "passing",
                "stats": [
                    {"name": "completions", "displayValue": "250"},
                    {"name": "netPassingYards", "displayValue": "3,000"},
                    {"name": "passingTouchdowns", "displayValue": "25"},
                    {"name": "interceptions", "displayValue": "5"},
                ],
            },
        ]
        row = _college_season_from_categories(2024, "MIA", categories)
        self.assertEqual(row.season, 2024)
        self.assertEqual(row.team, "MIA")
        self.assertEqual(row.games_played, "12")
        self.assertEqual(row.passing_yards, "3,000")


if __name__ == "__main__":
    unittest.main()
