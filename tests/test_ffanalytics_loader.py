"""Unit tests for ffanalytics player parsing (no R required)."""

from __future__ import annotations

import unittest

from draft.ffanalytics_loader import (
    merge_projection_tables,
    parse_projection_row,
    _player_name_from_row,
    _adp_from_row,
    _per_source_adp_from_row,
)
from draft.models import Position


class ParseHelpersTests(unittest.TestCase):
    def test_player_name_from_first_last(self) -> None:
        row = {"first_name": "Josh", "last_name": "Allen", "pos": "QB"}
        self.assertEqual(_player_name_from_row(row), "Josh Allen")

    def test_adp_from_source_columns(self) -> None:
        row = {"id": "1", "adp_espn": 2.2, "adp_yahoo": 3.0}
        self.assertAlmostEqual(_adp_from_row(row), 2.6)

    def test_per_source_adp_from_row(self) -> None:
        row = {"id": "1", "adp_espn": 5.0, "adp_yahoo": 8.0, "adp_cbs": 6.0}
        result = _per_source_adp_from_row(row)
        self.assertEqual(result["espn"], 5.0)
        self.assertEqual(result["yahoo"], 8.0)
        self.assertEqual(result["cbs"], 6.0)

    def test_per_source_adp_ignores_zero_values(self) -> None:
        row = {"id": "1", "adp_espn": 5.0, "adp_yahoo": 0.0}
        result = _per_source_adp_from_row(row)
        self.assertEqual(result["espn"], 5.0)
        self.assertNotIn("yahoo", result)


class MergeProjectionTablesTests(unittest.TestCase):
    def test_merges_scoring_formats_and_adp(self) -> None:
        std_rows = [
            {
                "id": "1",
                "first_name": "Ja'Marr",
                "last_name": "Chase",
                "pos": "WR",
                "team": "CIN",
                "points": 18.0,
            },
            {
                "id": "2",
                "first_name": "Christian",
                "last_name": "McCaffrey",
                "pos": "RB",
                "team": "SF",
                "points": 20.0,
            },
        ]
        half_rows = [
            {
                "id": "1",
                "first_name": "Ja'Marr",
                "last_name": "Chase",
                "pos": "WR",
                "team": "CIN",
                "points": 19.0,
            },
            {
                "id": "2",
                "first_name": "Christian",
                "last_name": "McCaffrey",
                "pos": "RB",
                "team": "SF",
                "points": 20.5,
            },
        ]
        ppr_rows = [
            {
                "id": "1",
                "first_name": "Ja'Marr",
                "last_name": "Chase",
                "pos": "WR",
                "team": "CIN",
                "points": 20.0,
            },
            {
                "id": "2",
                "first_name": "Christian",
                "last_name": "McCaffrey",
                "pos": "RB",
                "team": "SF",
                "points": 21.0,
            },
        ]
        adp_rows = [
            {"id": "1", "adp_espn": 1.5},
            {"id": "2", "adp_espn": 2.0},
        ]
        players = merge_projection_tables(std_rows, half_rows, ppr_rows, adp_rows)
        self.assertEqual(len(players), 2)
        chase = next(p for p in players if p.name == "Ja'Marr Chase")
        self.assertEqual(chase.position, Position.WR)
        self.assertEqual(chase.fp_std, 18.0)
        self.assertEqual(chase.fp_half, 19.0)
        self.assertEqual(chase.fp_ppr, 20.0)
        self.assertEqual(chase.adp, 1.5)

    def test_skips_unknown_positions(self) -> None:
        row = {"id": "9", "player_name": "Some Lineman", "pos": "OT", "points": 5.0}
        player = parse_projection_row(row, points=5.0, adp_by_id={}, adp_by_name={})
        self.assertIsNone(player)

    def test_populates_per_source_rankings(self) -> None:
        std_rows = [
            {
                "id": "1",
                "first_name": "Patrick",
                "last_name": "Mahomes",
                "pos": "QB",
                "team": "KC",
                "points": 25.0,
            },
        ]
        half_rows = [
            {
                "id": "1",
                "first_name": "Patrick",
                "last_name": "Mahomes",
                "pos": "QB",
                "team": "KC",
                "points": 25.0,
            },
        ]
        ppr_rows = [
            {
                "id": "1",
                "first_name": "Patrick",
                "last_name": "Mahomes",
                "pos": "QB",
                "team": "KC",
                "points": 25.0,
            },
        ]
        adp_rows = [
            {"id": "1", "adp_espn": 10.0, "adp_yahoo": 12.0},
        ]
        players = merge_projection_tables(std_rows, half_rows, ppr_rows, adp_rows)
        self.assertEqual(len(players), 1)
        mahomes = players[0]
        self.assertEqual(mahomes.rank_espn, 10.0)
        self.assertEqual(mahomes.rank_yahoo, 12.0)
        self.assertEqual(mahomes.rank_sleeper, 999.0)


if __name__ == "__main__":
    unittest.main()
