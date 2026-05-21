"""Tests for ESPN active player scraper helpers."""

from __future__ import annotations

import unittest

from espn.player import GameLogEntry, InjuryInfo, gamelog_to_dict, injury_to_dict
from espn.scrape import last_name_initial


class LastNameInitialTests(unittest.TestCase):
    def test_smith(self) -> None:
        self.assertEqual(last_name_initial("Smith"), "s")

    def test_obrien(self) -> None:
        self.assertEqual(last_name_initial("O'Brien"), "o")

    def test_empty(self) -> None:
        self.assertIsNone(last_name_initial(""))

    def test_non_alpha(self) -> None:
        self.assertIsNone(last_name_initial("123"))

    def test_strips_whitespace(self) -> None:
        self.assertEqual(last_name_initial("  Ward "), "w")


class SerializationTests(unittest.TestCase):
    def test_injury_to_dict(self) -> None:
        injury = InjuryInfo(
            status="Active",
            injury_type="—",
            details="No injury information available",
            date="—",
        )
        data = injury_to_dict(injury)
        self.assertEqual(data["status"], "Active")
        self.assertEqual(data["injury_type"], "—")

    def test_gamelog_to_dict(self) -> None:
        entry = GameLogEntry(
            week=1,
            opponent="KC",
            result="W",
            passing_yards=250,
            passing_tds=2,
            interceptions=0,
            rushing_yards=10,
            rushing_tds=0,
            receptions=0,
            receiving_yards=0,
            receiving_tds=0,
            fumbles_lost=0,
        )
        data = gamelog_to_dict(entry)
        self.assertEqual(data["week"], 1)
        self.assertEqual(data["passing_yards"], 250)


class LetterFilterTests(unittest.TestCase):
    def test_matches_letter_bucket(self) -> None:
        self.assertEqual(last_name_initial("Mahomes"), "m")

    def test_skips_wrong_letter(self) -> None:
        self.assertNotEqual(last_name_initial("Smith"), "a")


if __name__ == "__main__":
    unittest.main()
