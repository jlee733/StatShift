"""Tests for ESPN active player scraper helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from espn.player import GameLogEntry, InjuryInfo, gamelog_to_dict, injury_to_dict
from espn.scrape import (
    active_athlete_refs_cache_is_fresh,
    last_name_initial,
    load_active_athlete_refs_cache,
    save_active_athlete_refs_cache,
)


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


class ActiveAthleteRefsCacheTests(unittest.TestCase):
    def test_save_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "refs.json"
            refs = ["https://example.com/athlete/1"]
            team_map = {"1": "KC"}
            save_active_athlete_refs_cache(refs, team_map, path)
            loaded = load_active_athlete_refs_cache(path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded[0], refs)
            self.assertEqual(loaded[1], team_map)

    def test_freshness_within_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "refs.json"
            fetched_at = datetime.now(timezone.utc).isoformat()
            path.write_text(
                json.dumps(
                    {
                        "fetched_at": fetched_at,
                        "ref_count": 1,
                        "refs": ["https://example.com/athlete/1"],
                        "team_map": {"1": "KC"},
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(active_athlete_refs_cache_is_fresh(path, max_age_hours=24))

    def test_stale_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "refs.json"
            fetched_at = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
            path.write_text(
                json.dumps(
                    {
                        "fetched_at": fetched_at,
                        "ref_count": 1,
                        "refs": ["https://example.com/athlete/1"],
                        "team_map": {"1": "KC"},
                    }
                ),
                encoding="utf-8",
            )
            self.assertFalse(active_athlete_refs_cache_is_fresh(path, max_age_hours=24))


class LetterFilterTests(unittest.TestCase):
    def test_matches_letter_bucket(self) -> None:
        self.assertEqual(last_name_initial("Mahomes"), "m")

    def test_skips_wrong_letter(self) -> None:
        self.assertNotEqual(last_name_initial("Smith"), "a")


if __name__ == "__main__":
    unittest.main()
