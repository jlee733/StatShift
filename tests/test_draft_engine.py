"""Unit tests for mock draft engine."""

from __future__ import annotations

import unittest

from draft.engine import MockDraftEngine, _snake_team_index
from draft.models import Player, Position, RankingSource, ScoringFormat


def _test_pool() -> list[Player]:
    return [
        Player(
            f"QB {i}", Position.QB, 20.0, 20.0, 20.0,
            adp=float(i),
            rank_espn=float(i),
            rank_yahoo=float(5 - i) if i <= 4 else 999.0,
            rank_sleeper=float(i * 2),
        )
        for i in range(1, 5)
    ] + [
        Player(
            f"RB {i}", Position.RB, 15.0, 14.0, 13.0,
            adp=float(10 + i),
            rank_espn=float(10 + i),
            rank_yahoo=float(20 - i),
            rank_sleeper=float(5 + i),
        )
        for i in range(1, 10)
    ] + [
        Player(
            f"WR {i}", Position.WR, 14.0, 13.0, 12.0,
            adp=float(20 + i),
            rank_espn=float(20 + i),
            rank_yahoo=float(10 + i),
            rank_sleeper=float(15 + i),
        )
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


class MonteCarloDraftTests(unittest.TestCase):
    def _run_full(self, *, cpu_randomness: float, seed: int | None) -> list[str]:
        draft = MockDraftEngine.create(
            scoring=ScoringFormat.PPR,
            league_size=4,
            draft_slot=2,
            rounds=3,
            pool=_test_pool(),
            cpu_randomness=cpu_randomness,
            seed=seed,
        )
        while not draft.is_complete:
            draft.auto_pick()
        return [p.player.name for p in draft.picks]

    def test_randomness_zero_is_deterministic(self) -> None:
        # seed should be irrelevant when randomness is off
        a = self._run_full(cpu_randomness=0.0, seed=None)
        b = self._run_full(cpu_randomness=0.0, seed=999)
        self.assertEqual(a, b)

    def test_seed_reproduces_random_draft(self) -> None:
        a = self._run_full(cpu_randomness=0.6, seed=42)
        b = self._run_full(cpu_randomness=0.6, seed=42)
        self.assertEqual(a, b)

    def test_different_seeds_diverge(self) -> None:
        a = self._run_full(cpu_randomness=0.8, seed=1)
        b = self._run_full(cpu_randomness=0.8, seed=2)
        self.assertNotEqual(a, b)

    def test_simulate_availability_returns_probabilities(self) -> None:
        draft = MockDraftEngine.create(
            scoring=ScoringFormat.PPR,
            league_size=4,
            draft_slot=2,
            rounds=2,
            pool=_test_pool(),
            cpu_randomness=0.5,
            seed=7,
        )
        draft.run_cpu_picks_until_user()
        self.assertTrue(draft.is_user_turn)

        probs = draft.simulate_availability_at_next_user_pick(num_sims=10)

        self.assertEqual(set(probs.keys()), {p.name for p in draft.available})
        self.assertTrue(all(0.0 <= v <= 1.0 for v in probs.values()))

    def test_simulate_does_not_mutate_live_draft(self) -> None:
        draft = MockDraftEngine.create(
            scoring=ScoringFormat.PPR,
            league_size=4,
            draft_slot=2,
            rounds=2,
            pool=_test_pool(),
            cpu_randomness=0.4,
            seed=11,
        )
        draft.run_cpu_picks_until_user()
        picks_before = len(draft.picks)
        available_before = [p.name for p in draft.available]

        draft.simulate_availability_at_next_user_pick(num_sims=5)

        self.assertEqual(len(draft.picks), picks_before)
        self.assertEqual([p.name for p in draft.available], available_before)


class RankingSourceTests(unittest.TestCase):
    def test_player_rank_for_source_espn(self) -> None:
        player = Player(
            "Test Player", Position.QB, 20.0, 20.0, 20.0,
            rank_espn=5.0, rank_yahoo=10.0, rank_sleeper=15.0,
        )
        self.assertEqual(player.rank_for_source(RankingSource.ESPN), 5.0)

    def test_player_rank_for_source_yahoo(self) -> None:
        player = Player(
            "Test Player", Position.QB, 20.0, 20.0, 20.0,
            rank_espn=5.0, rank_yahoo=10.0, rank_sleeper=15.0,
        )
        self.assertEqual(player.rank_for_source(RankingSource.YAHOO), 10.0)

    def test_player_rank_for_source_sleeper(self) -> None:
        player = Player(
            "Test Player", Position.QB, 20.0, 20.0, 20.0,
            rank_espn=5.0, rank_yahoo=10.0, rank_sleeper=15.0,
        )
        self.assertEqual(player.rank_for_source(RankingSource.SLEEPER), 15.0)

    def test_different_ranking_sources_produce_different_orders(self) -> None:
        pool = _test_pool()
        
        draft_yahoo = MockDraftEngine.create(
            scoring=ScoringFormat.PPR,
            league_size=4,
            draft_slot=2,
            rounds=2,
            pool=pool,
            cpu_randomness=0.0,
            ranking_source=RankingSource.YAHOO,
        )
        draft_espn = MockDraftEngine.create(
            scoring=ScoringFormat.PPR,
            league_size=4,
            draft_slot=2,
            rounds=2,
            pool=pool,
            cpu_randomness=0.0,
            ranking_source=RankingSource.ESPN,
        )
        
        while not draft_yahoo.is_complete:
            draft_yahoo.auto_pick()
        while not draft_espn.is_complete:
            draft_espn.auto_pick()
        
        yahoo_picks = [p.player.name for p in draft_yahoo.picks]
        espn_picks = [p.player.name for p in draft_espn.picks]
        
        self.assertNotEqual(yahoo_picks, espn_picks)

    def test_default_ranking_source_is_yahoo(self) -> None:
        draft = MockDraftEngine.create(
            scoring=ScoringFormat.PPR,
            league_size=4,
            draft_slot=1,
            rounds=1,
            pool=_test_pool(),
        )
        self.assertEqual(draft.ranking_source, RankingSource.YAHOO)

    def test_ranking_source_passed_to_create(self) -> None:
        draft = MockDraftEngine.create(
            scoring=ScoringFormat.PPR,
            league_size=4,
            draft_slot=1,
            rounds=1,
            pool=_test_pool(),
            ranking_source=RankingSource.SLEEPER,
        )
        self.assertEqual(draft.ranking_source, RankingSource.SLEEPER)

    def test_clone_preserves_ranking_source(self) -> None:
        draft = MockDraftEngine.create(
            scoring=ScoringFormat.PPR,
            league_size=4,
            draft_slot=2,
            rounds=2,
            pool=_test_pool(),
            ranking_source=RankingSource.ESPN,
        )
        clone = draft._clone_for_simulation()
        self.assertEqual(clone.ranking_source, RankingSource.ESPN)


if __name__ == "__main__":
    unittest.main()
