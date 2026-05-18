"""Data models for mock fantasy drafts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScoringFormat(str, Enum):
    PPR = "PPR"
    HALF_PPR = "Half-PPR"
    STANDARD = "Standard"


class Position(str, Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"
    K = "K"
    DEF = "DEF"


ROSTER_SLOTS: dict[str, int] = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "K": 1,
    "DEF": 1,
}


@dataclass(frozen=True)
class LeagueSettings:
    scoring: ScoringFormat
    league_size: int
    draft_slot: int
    rounds: int = 15

    def __post_init__(self) -> None:
        if self.league_size < 4 or self.league_size > 16:
            raise ValueError("league_size must be between 4 and 16")
        if self.draft_slot < 1 or self.draft_slot > self.league_size:
            raise ValueError("draft_slot must be between 1 and league_size")
        if self.rounds < 1:
            raise ValueError("rounds must be at least 1")


@dataclass
class Player:
    name: str
    position: Position
    fp_ppr: float
    fp_half: float
    fp_std: float
    team: str = ""
    adp: float = 99.0

    def fantasy_points(self, scoring: ScoringFormat) -> float:
        if scoring == ScoringFormat.PPR:
            return self.fp_ppr
        if scoring == ScoringFormat.HALF_PPR:
            return self.fp_half
        return self.fp_std


@dataclass
class DraftPick:
    round: int
    pick_in_round: int
    overall: int
    team_index: int
    player: Player


@dataclass
class TeamRoster:
    team_index: int
    picks: list[Player] = field(default_factory=list)

    def count(self, position: Position) -> int:
        return sum(1 for p in self.picks if p.position == position)

    def flex_eligible_count(self) -> int:
        return sum(
            1 for p in self.picks if p.position in (Position.RB, Position.WR, Position.TE)
        )
