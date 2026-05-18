"""Unit tests for ESPN player parsing."""

from __future__ import annotations

import unittest

from draft.espn_loader import parse_athlete_payload
from draft.models import Position


class ParseAthletePayloadTests(unittest.TestCase):
    def test_parses_skill_position(self) -> None:
        payload = {
            "id": "1",
            "displayName": "Ja'Marr Chase",
            "position": {"abbreviation": "WR"},
            "experience": {"years": 4},
            "team": {"id": "4", "$ref": "http://example/teams/4"},
        }
        player = parse_athlete_payload(payload, {"4": "CIN"})
        assert player is not None
        self.assertEqual(player.name, "Ja'Marr Chase")
        self.assertEqual(player.position, Position.WR)
        self.assertEqual(player.team, "CIN")

    def test_skips_offensive_line(self) -> None:
        payload = {
            "displayName": "Some Lineman",
            "position": {"abbreviation": "OT"},
            "experience": {"years": 3},
        }
        self.assertIsNone(parse_athlete_payload(payload, {}))

    def test_maps_pk_to_kicker(self) -> None:
        payload = {
            "displayName": "Justin Tucker",
            "position": {"abbreviation": "PK"},
            "experience": {"years": 10},
        }
        player = parse_athlete_payload(payload, {})
        assert player is not None
        self.assertEqual(player.position, Position.K)


if __name__ == "__main__":
    unittest.main()
