from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SelectionStatus(str, Enum):
    WON = "won"
    LOST = "lost"
    PENDING = "pending"
    VOID = "void"
    PUSH = "push"
    REFUND = "refund"
    CANCELLED = "cancelled"
    NOT_SUPPORTED = "not_supported"


class Market(str, Enum):
    UNMAPPED = "UNMAPPED"
    MATCH_WINNER = "MATCH_WINNER"
    DOUBLE_CHANCE = "DOUBLE_CHANCE"
    OVER_UNDER = "OVER_UNDER"
    BTTS = "BTTS"
    DRAW_NO_BET = "DRAW_NO_BET"
    TEAM_OVER_UNDER = "TEAM_OVER_UNDER"
    CORRECT_SCORE = "CORRECT_SCORE"
    HT_MATCH_WINNER = "HT_MATCH_WINNER"
    SECOND_HALF_MATCH_WINNER = "SECOND_HALF_MATCH_WINNER"
    HT_OVER_UNDER = "HT_OVER_UNDER"
    SECOND_HALF_OVER_UNDER = "SECOND_HALF_OVER_UNDER"
    HT_FT = "HT_FT"
    CORNERS_OVER_UNDER = "CORNERS_OVER_UNDER"
    TEAM_CORNERS_OVER_UNDER = "TEAM_CORNERS_OVER_UNDER"
    CARDS_OVER_UNDER = "CARDS_OVER_UNDER"
    TEAM_CARDS_OVER_UNDER = "TEAM_CARDS_OVER_UNDER"
    ASIAN_HANDICAP = "ASIAN_HANDICAP"
    ODD_EVEN = "ODD_EVEN"
    WIN_TO_NIL = "WIN_TO_NIL"


@dataclass
class Selection:
    fixture_id: int
    market: Market
    pick: str
    line: Optional[float] = None
    team: Optional[str] = None
    raw_market: Optional[str] = None


@dataclass
class SelectionResult:
    fixture_id: int
    market: str
    pick: str
    status: SelectionStatus
    reason: str


@dataclass
class FixtureOutcome:
    fixture_id: int
    status_short: str
    home_goals: Optional[int]
    away_goals: Optional[int]
    halftime_home: Optional[int] = None
    halftime_away: Optional[int] = None
    fulltime_home: Optional[int] = None
    fulltime_away: Optional[int] = None
    penalty_home: Optional[int] = None
    penalty_away: Optional[int] = None


@dataclass
class FixtureStatistics:
    fixture_id: int
    corners_home: Optional[int] = None
    corners_away: Optional[int] = None
    yellow_home: Optional[int] = None
    yellow_away: Optional[int] = None
    red_home: Optional[int] = None
    red_away: Optional[int] = None
