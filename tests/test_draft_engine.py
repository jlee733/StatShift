"""Unit tests for mock draft engine."""

from __future__ import annotations

import unittest

from draft.engine import MockDraftEngine, _snake_team_index
from draft.models import Player, Position, ScoringFormat


def _test_pool() -> list[Player]:
    return [
        Player(f"QB {i}", Position.QB, 20.0, 20.0, 20.0, adp=float(i))
        for i in range(1, 5)
    ] + [
        Player(f"RB {i}", Position.RB, 15.0, 14.0, 13.0, adp=float(10 + i))
        for i in range(1, 10)
    ] + [
        Player(f"WR {i}", Position.WR, 14.0, 13.0, 12.0, adp=float(20 + i))
        for i in range(1, 10)
    ]


class SnakeDraftTests(unittest.TestCase):
    def test_snake_order_round_two_reverses(self) -> None:
        self.assertEqual(_snake_team_index(1, 1, 10), 0)
        self.assertEqual(_snake_team_index(1, 10, 10), 9)
        self.assertEqual(_snake_team_index(2, 1, 10), 9)
        self.assertEqual(_snake_team_index(2, 10, 10), 0)

    def test_ppr_ranks_pass_catchers_higher(self) -> None:
        pool = _test_pool()
        draft = MockDraftEngine.create(
            scoring=ScoringFormat.PPR,
            league_size=4,
            draft_slot=1,
            rounds=1,
            pool=pool,
        )
        wr = next(p for p in draft.rank_available() if p.position == Position.WR)
        draft.make_pick(wr)
        self.assertEqual(draft.picks[0].player.position, Position.WR)

    def test_auto_pick_reduces_available_pool(self) -> None:
        draft = MockDraftEngine.create(
            scoring=ScoringFormat.STANDARD,
            league_size=4,
            draft_slot=4,
            rounds=2,
            pool=_test_pool(),
        )
        draft.run_cpu_picks_until_user()
        self.assertEqual(len(draft.picks), 3)
        self.assertTrue(draft.is_user_turn)

    def test_create_rejects_empty_pool(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            MockDraftEngine.create(
                scoring=ScoringFormat.PPR,
                league_size=12,
                draft_slot=1,
                rounds=15,
                pool=[],
            )
        self.assertIn("empty", str(ctx.exception).lower())

    def test_draft_completes_after_all_rounds(self) -> None:
        pool = _test_pool()
        draft = MockDraftEngine.create(
            scoring=ScoringFormat.HALF_PPR,
            league_size=4,
            draft_slot=1,
            rounds=2,
            pool=pool,
        )
        while not draft.is_complete:
            draft.auto_pick()
        self.assertEqual(len(draft.picks), 8)
        self.assertEqual(len(draft.available), len(pool) - 8)


if __name__ == "__main__":
    unittest.main()
