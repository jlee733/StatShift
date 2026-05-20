"""Unit tests for Sleeper loader."""

from __future__ import annotations

import unittest

from draft.sleeper_loader import _normalize_name, lookup_sleeper_rank, parse_sleeper_rankings


class SleeperLoaderTests(unittest.TestCase):
    def test_normalize_name_lowercase(self) -> None:
        self.assertEqual(_normalize_name("Patrick Mahomes"), "patrick mahomes")

    def test_normalize_name_strips_jr(self) -> None:
        self.assertEqual(_normalize_name("Marvin Harrison Jr"), "marvin harrison")

    def test_normalize_name_strips_sr(self) -> None:
        self.assertEqual(_normalize_name("John Smith Sr"), "john smith")

    def test_normalize_name_strips_ii(self) -> None:
        self.assertEqual(_normalize_name("Robert Griffin II"), "robert griffin")

    def test_normalize_name_strips_iii(self) -> None:
        self.assertEqual(_normalize_name("Robert Griffin III"), "robert griffin")

    def test_parse_sleeper_rankings_extracts_search_rank(self) -> None:
        raw = {
            "1234": {
                "first_name": "Patrick",
                "last_name": "Mahomes",
                "position": "QB",
                "search_rank": 5,
            },
            "5678": {
                "first_name": "Travis",
                "last_name": "Kelce",
                "position": "TE",
                "search_rank": 12,
            },
        }
        rankings = parse_sleeper_rankings(raw)
        self.assertEqual(rankings["patrick mahomes"], 5)
        self.assertEqual(rankings["travis kelce"], 12)

    def test_parse_sleeper_rankings_ignores_non_skill_positions(self) -> None:
        raw = {
            "1234": {
                "first_name": "Andy",
                "last_name": "Reid",
                "position": "HC",
                "search_rank": 100,
            },
        }
        rankings = parse_sleeper_rankings(raw)
        self.assertNotIn("andy reid", rankings)

    def test_parse_sleeper_rankings_handles_missing_search_rank(self) -> None:
        raw = {
            "1234": {
                "first_name": "Patrick",
                "last_name": "Mahomes",
                "position": "QB",
            },
        }
        rankings = parse_sleeper_rankings(raw)
        self.assertNotIn("patrick mahomes", rankings)

    def test_lookup_sleeper_rank_found(self) -> None:
        rankings = {"patrick mahomes": 5}
        rank = lookup_sleeper_rank("Patrick Mahomes", rankings)
        self.assertEqual(rank, 5.0)

    def test_lookup_sleeper_rank_not_found(self) -> None:
        rankings = {"patrick mahomes": 5}
        rank = lookup_sleeper_rank("Unknown Player", rankings)
        self.assertEqual(rank, 999.0)

    def test_lookup_sleeper_rank_with_suffix(self) -> None:
        rankings = {"marvin harrison": 3}
        rank = lookup_sleeper_rank("Marvin Harrison Jr", rankings)
        self.assertEqual(rank, 3.0)


if __name__ == "__main__":
    unittest.main()
