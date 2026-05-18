"""Snake-draft engine for mock fantasy leagues."""

from __future__ import annotations

from dataclasses import dataclass, field

from draft.models import (
    ROSTER_SLOTS,
    DraftPick,
    LeagueSettings,
    Player,
    Position,
    ScoringFormat,
    TeamRoster,
)
from draft.player_pool import get_players, max_rounds_for_league


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

    def __post_init__(self) -> None:
        if not self.pool:
            self.pool = get_players()
        self.rosters = [TeamRoster(team_index=i) for i in range(self.settings.league_size)]
        self.available = sorted(
            self.pool,
            key=lambda p: p.fantasy_points(self.settings.scoring),
            reverse=True,
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

    def rank_available(self, team_index: int | None = None) -> list[Player]:
        idx = team_index if team_index is not None else self.current_team_index
        roster = self.rosters[idx]
        scoring = self.settings.scoring

        def score(player: Player) -> float:
            value = player.fantasy_points(scoring)
            need = self._roster_need_score(roster, player)
            adp_bonus = max(0.0, (80.0 - player.adp) / 80.0) * 0.5
            return value + need * 2.0 + adp_bonus

        return sorted(self.available, key=score, reverse=True)

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
        return self.make_pick(ranked[0])

    def run_cpu_picks_until_user(self) -> list[DraftPick]:
        made: list[DraftPick] = []
        while not self.is_complete and not self.is_user_turn:
            if self.pool_exhausted:
                break
            made.append(self.auto_pick())
        return made

    def user_roster(self) -> TeamRoster:
        return self.rosters[self.settings.draft_slot - 1]

    @staticmethod
    def create(
        scoring: ScoringFormat,
        league_size: int,
        draft_slot: int,
        rounds: int = 15,
        *,
        pool: list[Player] | None = None,
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
        engine = MockDraftEngine(settings=settings, pool=player_pool)
        engine.requested_rounds = rounds
        engine.max_supported_rounds = supported
        return engine
