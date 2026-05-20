"""Data models for mock fantasy drafts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScoringFormat(str, Enum):
    PPR = "PPR"
    HALF_PPR = "Half-PPR"
    STANDARD = "Standard"


class RankingSource(str, Enum):
    YAHOO = "Yahoo"
    ESPN = "ESPN"
    SLEEPER = "Sleeper"


class Position(str, Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"
    K = "K"
    DEF = "DEF"


# Sleeper-style position colors: (background, text)
POSITION_COLORS: dict[str, tuple[str, str]] = {
    "QB": ("#523C87", "#FFFFFF"),
    "RB": ("#2E7D5E", "#FFFFFF"),
    "WR": ("#2D7A4F", "#FFFFFF"),
    "TE": ("#C75724", "#FFFFFF"),
    "K": ("#6B6B6B", "#FFFFFF"),
    "DEF": ("#C72424", "#FFFFFF"),
}


ROSTER_SLOTS: dict[str, int] = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "K": 1,
    "DEF": 1,
}

TEAM_NAME_POOL: list[str] = [
    "Gridiron Gladiators",
    "Sunday Scaries",
    "The Algorithm",
    "Waiver Wire Wizards",
    "Trade Block Party",
    "Bench Warmers",
    "Fantasy Fiends",
    "TD Chasers",
    "Point Projectors",
    "Sleeper Agents",
    "Red Zone Rockets",
    "Fourth Quarter Comeback",
    "Bye Week Blues",
    "Commissioner's Picks",
    "Draft Day Disasters",
    "Playoff Bound",
    "Injury Reserve",
    "Monday Night Mayhem",
    "Touchdown Titans",
    "Roster Roulette",
]


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
    adp: float = 999.0
    rank_espn: float = 999.0
    rank_yahoo: float = 999.0
    rank_sleeper: float = 999.0

    def fantasy_points(self, scoring: ScoringFormat) -> float:
        if scoring == ScoringFormat.PPR:
            return self.fp_ppr
        if scoring == ScoringFormat.HALF_PPR:
            return self.fp_half
        return self.fp_std

    def rank_for_source(self, source: RankingSource) -> float:
        if source == RankingSource.ESPN:
            return self.rank_espn
        if source == RankingSource.YAHOO:
            return self.rank_yahoo
        return self.rank_sleeper


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
