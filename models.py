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
    # ── core 1X2 / result ──
    MATCH_WINNER = "MATCH_WINNER"
    DOUBLE_CHANCE = "DOUBLE_CHANCE"
    DRAW_NO_BET = "DRAW_NO_BET"
    # ── goals totals ──
    OVER_UNDER = "OVER_UNDER"
    BTTS = "BTTS"
    TEAM_OVER_UNDER = "TEAM_OVER_UNDER"
    EXACT_GOALS = "EXACT_GOALS"
    TEAM_EXACT_GOALS = "TEAM_EXACT_GOALS"
    MULTI_GOALS = "MULTI_GOALS"
    ODD_EVEN = "ODD_EVEN"
    # ── correct score ──
    CORRECT_SCORE = "CORRECT_SCORE"
    # ── handicap ──
    ASIAN_HANDICAP = "ASIAN_HANDICAP"
    HANDICAP_RESULT = "HANDICAP_RESULT"
    # ── clean sheet / scorers ──
    CLEAN_SHEET = "CLEAN_SHEET"
    WIN_TO_NIL = "WIN_TO_NIL"
    FIRST_TEAM_TO_SCORE = "FIRST_TEAM_TO_SCORE"
    LAST_TEAM_TO_SCORE = "LAST_TEAM_TO_SCORE"
    # ── combo markets ──
    RESULT_BTTS = "RESULT_BTTS"
    RESULT_OVER_UNDER = "RESULT_OVER_UNDER"
    MARGIN_OF_VICTORY = "MARGIN_OF_VICTORY"
    # ── half-time ──
    HT_MATCH_WINNER = "HT_MATCH_WINNER"
    HT_OVER_UNDER = "HT_OVER_UNDER"
    HT_BTTS = "HT_BTTS"
    HT_DOUBLE_CHANCE = "HT_DOUBLE_CHANCE"
    HT_DRAW_NO_BET = "HT_DRAW_NO_BET"
    HT_ODD_EVEN = "HT_ODD_EVEN"
    HT_CORRECT_SCORE = "HT_CORRECT_SCORE"
    HT_ASIAN_HANDICAP = "HT_ASIAN_HANDICAP"
    # ── second half ──
    SECOND_HALF_MATCH_WINNER = "SECOND_HALF_MATCH_WINNER"
    SECOND_HALF_OVER_UNDER = "SECOND_HALF_OVER_UNDER"
    SECOND_HALF_BTTS = "SECOND_HALF_BTTS"
    SECOND_HALF_DOUBLE_CHANCE = "SECOND_HALF_DOUBLE_CHANCE"
    SECOND_HALF_DRAW_NO_BET = "SECOND_HALF_DRAW_NO_BET"
    SECOND_HALF_ODD_EVEN = "SECOND_HALF_ODD_EVEN"
    SECOND_HALF_CORRECT_SCORE = "SECOND_HALF_CORRECT_SCORE"
    # ── HT / FT combo ──
    HT_FT = "HT_FT"
    # ── cross-half ──
    TO_SCORE_IN_BOTH_HALVES = "TO_SCORE_IN_BOTH_HALVES"
    TO_WIN_EITHER_HALF = "TO_WIN_EITHER_HALF"
    TO_WIN_BOTH_HALVES = "TO_WIN_BOTH_HALVES"
    HIGHEST_SCORING_HALF = "HIGHEST_SCORING_HALF"
    BOTH_HALVES_OVER_UNDER = "BOTH_HALVES_OVER_UNDER"
    # ── statistics (corners / cards) ──
    CORNERS_OVER_UNDER = "CORNERS_OVER_UNDER"
    TEAM_CORNERS_OVER_UNDER = "TEAM_CORNERS_OVER_UNDER"
    CARDS_OVER_UNDER = "CARDS_OVER_UNDER"
    TEAM_CARDS_OVER_UNDER = "TEAM_CARDS_OVER_UNDER"
    # ── statistics (shots / fouls / offsides) ──
    SHOTS_OVER_UNDER = "SHOTS_OVER_UNDER"
    SHOTS_ON_TARGET_OVER_UNDER = "SHOTS_ON_TARGET_OVER_UNDER"
    FOULS_OVER_UNDER = "FOULS_OVER_UNDER"
    OFFSIDES_OVER_UNDER = "OFFSIDES_OVER_UNDER"
    # ── statistics comparison (which team has more) ──
    MOST_CORNERS = "MOST_CORNERS"
    MOST_CARDS = "MOST_CARDS"
    MOST_OFFSIDES = "MOST_OFFSIDES"
    MOST_FOULS = "MOST_FOULS"
    MOST_SHOTS = "MOST_SHOTS"
    MOST_SHOTS_ON_TARGET = "MOST_SHOTS_ON_TARGET"


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
    first_to_score: Optional[str] = None   # "HOME", "AWAY", or "NONE"
    last_to_score: Optional[str] = None    # "HOME", "AWAY", or "NONE"


@dataclass
class FixtureStatistics:
    fixture_id: int
    corners_home: Optional[int] = None
    corners_away: Optional[int] = None
    yellow_home: Optional[int] = None
    yellow_away: Optional[int] = None
    red_home: Optional[int] = None
    red_away: Optional[int] = None
    shots_home: Optional[int] = None
    shots_away: Optional[int] = None
    shots_on_target_home: Optional[int] = None
    shots_on_target_away: Optional[int] = None
    fouls_home: Optional[int] = None
    fouls_away: Optional[int] = None
    offsides_home: Optional[int] = None
    offsides_away: Optional[int] = None
