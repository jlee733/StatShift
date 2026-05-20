"""Snake-draft engine for mock fantasy leagues."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

from draft.models import (
    ROSTER_SLOTS,
    TEAM_NAME_POOL,
    DraftPick,
    LeagueSettings,
    Player,
    Position,
    RankingSource,
    ScoringFormat,
    TeamRoster,
)
from draft.player_pool import get_players, max_rounds_for_league


def _generate_team_names(
    league_size: int,
    user_team_name: str = "My Team",
    user_slot: int = 1,
    rng: random.Random | None = None,
) -> list[str]:
    """Generate team names with user's name at their draft slot."""
    rng = rng or random.Random()
    cpu_names = rng.sample(TEAM_NAME_POOL, min(league_size - 1, len(TEAM_NAME_POOL)))
    
    names: list[str] = []
    cpu_idx = 0
    for i in range(league_size):
        if i == user_slot - 1:
            names.append(user_team_name)
        else:
            if cpu_idx < len(cpu_names):
                names.append(cpu_names[cpu_idx])
                cpu_idx += 1
            else:
                names.append(f"Team {i + 1}")
    return names


def _snake_team_index(round_num: int, pick_in_round: int, league_size: int) -> int:
    if round_num % 2 == 1:
        return pick_in_round - 1
    return league_size - pick_in_round


@dataclass
class MockDraftEngine:
    settings: LeagueSettings
    pool: list[Player] = field(default_factory=list)
    picks: list[DraftPick] = field(default_factory=list)
    rosters: list[TeamRoster] = field(default_factory=list)
    available: list[Player] = field(default_factory=list)
    requested_rounds: int = 15
    max_supported_rounds: int = 15
    cpu_randomness: float = 0.35
    cpu_top_k: int = 12
    seed: int | None = None
    ranking_source: RankingSource = RankingSource.YAHOO
    team_names: list[str] = field(default_factory=list)
    user_team_name: str = "My Team"
    pick_time_limit: int = 30
    pick_start_time: float | None = None
    _rng: random.Random = field(
        init=False, repr=False, compare=False, default_factory=random.Random
    )

    def __post_init__(self) -> None:
        if not self.pool:
            self.pool = get_players()
        self.rosters = [TeamRoster(team_index=i) for i in range(self.settings.league_size)]
        self.available = sorted(
            self.pool,
            key=lambda p: p.fantasy_points(self.settings.scoring),
            reverse=True,
        )
        self._rng = random.Random(self.seed)
        if not self.team_names:
            self.team_names = _generate_team_names(
                self.settings.league_size,
                self.user_team_name,
                self.settings.draft_slot,
                self._rng,
            )

    @property
    def total_picks(self) -> int:
        return self.settings.league_size * self.settings.rounds

    @property
    def pool_exhausted(self) -> bool:
        return not self.available

    @property
    def is_complete(self) -> bool:
        return len(self.picks) >= self.total_picks or self.pool_exhausted

    @property
    def current_overall(self) -> int:
        return len(self.picks) + 1

    @property
    def current_round(self) -> int:
        return (len(self.picks) // self.settings.league_size) + 1

    @property
    def current_pick_in_round(self) -> int:
        return (len(self.picks) % self.settings.league_size) + 1

    @property
    def current_team_index(self) -> int:
        return _snake_team_index(
            self.current_round,
            self.current_pick_in_round,
            self.settings.league_size,
        )

    @property
    def is_user_turn(self) -> bool:
        return (
            not self.is_complete
            and self.current_team_index == self.settings.draft_slot - 1
        )

    def start_pick_timer(self) -> None:
        """Start or reset the pick timer for the current pick."""
        self.pick_start_time = time.time()

    def time_remaining(self) -> int:
        """Return seconds remaining on the pick clock."""
        if self.pick_start_time is None:
            return self.pick_time_limit
        elapsed = time.time() - self.pick_start_time
        return max(0, self.pick_time_limit - int(elapsed))

    def is_timer_expired(self) -> bool:
        """Check if the pick timer has expired."""
        return self.pick_start_time is not None and self.time_remaining() <= 0

    def get_team_name(self, team_index: int) -> str:
        """Get the display name for a team."""
        if 0 <= team_index < len(self.team_names):
            return self.team_names[team_index]
        return f"Team {team_index + 1}"

    def drafted_names(self) -> set[str]:
        return {pick.player.name for pick in self.picks}

    def _roster_need_score(self, roster: TeamRoster, player: Player) -> float:
        pos = player.position
        counts = {p: roster.count(p) for p in Position}
        need = 0.0

        if pos == Position.QB and counts[Position.QB] < ROSTER_SLOTS["QB"]:
            need += 3.0
        elif pos == Position.RB and counts[Position.RB] < ROSTER_SLOTS["RB"]:
            need += 2.5
        elif pos == Position.WR and counts[Position.WR] < ROSTER_SLOTS["WR"]:
            need += 2.5
        elif pos == Position.TE and counts[Position.TE] < ROSTER_SLOTS["TE"]:
            need += 2.0
        elif pos in (Position.RB, Position.WR, Position.TE):
            starters = (
                min(counts[Position.RB], ROSTER_SLOTS["RB"])
                + min(counts[Position.WR], ROSTER_SLOTS["WR"])
                + min(counts[Position.TE], ROSTER_SLOTS["TE"])
            )
            flex_filled = roster.flex_eligible_count() - starters
            if flex_filled < ROSTER_SLOTS["FLEX"]:
                need += 1.5
        elif pos == Position.K and counts[Position.K] < ROSTER_SLOTS["K"]:
            need += 0.8
        elif pos == Position.DEF and counts[Position.DEF] < ROSTER_SLOTS["DEF"]:
            need += 0.8
        else:
            need -= 1.0

        return need

    def _candidate_score(self, player: Player, team_index: int) -> float:
        roster = self.rosters[team_index]
        scoring = self.settings.scoring
        value = player.fantasy_points(scoring)
        need = self._roster_need_score(roster, player)
        rank = player.rank_for_source(self.ranking_source)
        rank_bonus = max(0.0, (80.0 - rank) / 80.0) * 0.5
        return value + need * 2.0 + rank_bonus

    def rank_available(self, team_index: int | None = None) -> list[Player]:
        idx = team_index if team_index is not None else self.current_team_index
        return sorted(
            self.available,
            key=lambda p: self._candidate_score(p, idx),
            reverse=True,
        )

    def _sample_cpu_pick(self, candidates: list[Player]) -> Player:
        if not candidates:
            raise RuntimeError("No candidates available")
        if self.cpu_randomness <= 0.0 or len(candidates) == 1:
            return candidates[0]
        top_k = candidates[: max(1, self.cpu_top_k)]
        team_idx = self.current_team_index
        scores = [self._candidate_score(p, team_idx) for p in top_k]
        top = scores[0]
        # Softmax with temperature: 0.5 (near-deterministic) → 5.0 (nearly uniform)
        temperature = 0.5 + self.cpu_randomness * 4.5
        weights = [math.exp((s - top) / temperature) for s in scores]
        return self._rng.choices(top_k, weights=weights, k=1)[0]

    def make_pick(self, player: Player) -> DraftPick:
        if self.is_complete:
            raise RuntimeError("Draft is already complete")
        if player.name not in {p.name for p in self.available}:
            raise ValueError(f"{player.name} is not available")

        team_index = self.current_team_index
        pick = DraftPick(
            round=self.current_round,
            pick_in_round=self.current_pick_in_round,
            overall=self.current_overall,
            team_index=team_index,
            player=player,
        )
        self.picks.append(pick)
        self.rosters[team_index].picks.append(player)
        self.available = [p for p in self.available if p.name != player.name]
        return pick

    def auto_pick(self) -> DraftPick:
        ranked = self.rank_available()
        if not ranked:
            raise RuntimeError("No players available")
        return self.make_pick(self._sample_cpu_pick(ranked))

    def run_cpu_picks_until_user(self) -> list[DraftPick]:
        made: list[DraftPick] = []
        while not self.is_complete and not self.is_user_turn:
            if self.pool_exhausted:
                break
            made.append(self.auto_pick())
        return made

    def user_roster(self) -> TeamRoster:
        return self.rosters[self.settings.draft_slot - 1]

    def _clone_for_simulation(self) -> MockDraftEngine:
        """Lightweight copy that shares the immutable Player/pool references."""
        clone = MockDraftEngine(
            settings=self.settings,
            pool=self.pool,
            cpu_randomness=self.cpu_randomness,
            cpu_top_k=self.cpu_top_k,
            ranking_source=self.ranking_source,
            team_names=self.team_names,
            user_team_name=self.user_team_name,
            pick_time_limit=self.pick_time_limit,
        )
        clone.picks = list(self.picks)
        clone.rosters = [
            TeamRoster(team_index=r.team_index, picks=list(r.picks))
            for r in self.rosters
        ]
        clone.available = list(self.available)
        clone.requested_rounds = self.requested_rounds
        clone.max_supported_rounds = self.max_supported_rounds
        clone._rng = random.Random()
        return clone

    def simulate_availability_at_next_user_pick(
        self, *, num_sims: int = 40
    ) -> dict[str, float]:
        """
        Monte Carlo: probability each currently-available player is still on the
        board when the user is next on the clock.

        Each sim clones the engine and runs CPU picks (with cpu_randomness) until
        the user's next turn. If the user is currently on the clock, the sim
        treats that as an auto-pick (so the result describes the *following* pick).
        """
        if self.is_complete or self.pool_exhausted:
            return {p.name: 1.0 for p in self.available}

        counts: dict[str, int] = {p.name: 0 for p in self.available}

        for _ in range(num_sims):
            sim = self._clone_for_simulation()
            if sim.is_user_turn and not sim.pool_exhausted:
                sim.auto_pick()
            while not sim.is_complete and not sim.is_user_turn:
                sim.auto_pick()
            for player in sim.available:
                if player.name in counts:
                    counts[player.name] += 1

        return {name: count / num_sims for name, count in counts.items()}

    @staticmethod
    def create(
        scoring: ScoringFormat,
        league_size: int,
        draft_slot: int,
        rounds: int = 15,
        *,
        pool: list[Player] | None = None,
        cpu_randomness: float = 0.35,
        cpu_top_k: int = 12,
        seed: int | None = None,
        ranking_source: RankingSource = RankingSource.YAHOO,
        user_team_name: str = "My Team",
        pick_time_limit: int = 30,
    ) -> MockDraftEngine:
        player_pool = pool if pool is not None else get_players()
        if not player_pool:
            raise ValueError(
                "Player pool is empty. Refresh the player pool from ffanalytics first."
            )
        supported = len(player_pool) // max(league_size, 1)
        effective_rounds = max(1, min(rounds, supported))
        settings = LeagueSettings(
            scoring=scoring,
            league_size=league_size,
            draft_slot=draft_slot,
            rounds=effective_rounds,
        )
        engine = MockDraftEngine(
            settings=settings,
            pool=player_pool,
            cpu_randomness=cpu_randomness,
            cpu_top_k=cpu_top_k,
            seed=seed,
            ranking_source=ranking_source,
            user_team_name=user_team_name,
            pick_time_limit=pick_time_limit,
        )
        engine.requested_rounds = rounds
        engine.max_supported_rounds = supported
        engine.start_pick_timer()
        return engine
