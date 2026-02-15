from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from api_client import APISportsClient
from evaluator import evaluate_betslip
from models import Market, Selection


# ═══════════════════════════════════════════════════════════════════════════════
#  All implemented markets (49 canonical)
# ═══════════════════════════════════════════════════════════════════════════════

IMPLEMENTED_MARKETS = {m for m in Market if m != Market.UNMAPPED}

# ═══════════════════════════════════════════════════════════════════════════════
#  Pydantic models
# ═══════════════════════════════════════════════════════════════════════════════


class SelectionIn(BaseModel):
    fixture_id: int = Field(gt=0)
    market: Market
    pick: str = Field(min_length=1)
    line: Optional[float] = None
    team: Optional[str] = None

    @field_validator("pick")
    @classmethod
    def normalize_pick(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_market_constraints(self) -> "SelectionIn":
        m = self.market

        # ── 1X2 / result ──
        if m == Market.MATCH_WINNER and self.pick not in {"HOME", "DRAW", "AWAY"}:
            raise ValueError("MATCH_WINNER pick must be HOME, DRAW, or AWAY")
        if m == Market.DOUBLE_CHANCE and self.pick not in {"1X", "X2", "12"}:
            raise ValueError("DOUBLE_CHANCE pick must be 1X, X2, or 12")
        if m == Market.DRAW_NO_BET and self.pick not in {"HOME", "AWAY"}:
            raise ValueError("DRAW_NO_BET pick must be HOME or AWAY")

        # ── over/under family ──
        _ou_markets = {
            Market.OVER_UNDER, Market.HT_OVER_UNDER, Market.SECOND_HALF_OVER_UNDER,
            Market.BOTH_HALVES_OVER_UNDER,
            Market.CORNERS_OVER_UNDER, Market.CARDS_OVER_UNDER,
            Market.SHOTS_OVER_UNDER, Market.SHOTS_ON_TARGET_OVER_UNDER,
            Market.FOULS_OVER_UNDER, Market.OFFSIDES_OVER_UNDER,
        }
        if m in _ou_markets:
            if self.pick not in {"OVER", "UNDER"}:
                raise ValueError(f"{m.value} pick must be OVER or UNDER")
            if self.line is None:
                raise ValueError(f"{m.value} requires line")

        # ── team over/under family ──
        _team_ou = {
            Market.TEAM_OVER_UNDER,
            Market.TEAM_CORNERS_OVER_UNDER, Market.TEAM_CARDS_OVER_UNDER,
        }
        if m in _team_ou:
            if self.pick not in {"OVER", "UNDER"}:
                raise ValueError(f"{m.value} pick must be OVER or UNDER")
            if self.line is None:
                raise ValueError(f"{m.value} requires line")
            tv = (self.team or "").strip().upper()
            if tv not in {"HOME", "AWAY"}:
                raise ValueError(f"{m.value} requires team=HOME or team=AWAY")
            self.team = tv

        # ── BTTS family ──
        if m in {Market.BTTS, Market.HT_BTTS, Market.SECOND_HALF_BTTS} and self.pick not in {"YES", "NO"}:
            raise ValueError(f"{m.value} pick must be YES or NO")

        # ── correct score family ──
        if m in {Market.CORRECT_SCORE, Market.HT_CORRECT_SCORE, Market.SECOND_HALF_CORRECT_SCORE}:
            if ":" not in self.pick and "-" not in self.pick:
                raise ValueError(f"{m.value} pick must be score format like 2:1")

        # ── period 1X2 ──
        if m in {Market.HT_MATCH_WINNER, Market.SECOND_HALF_MATCH_WINNER}:
            if self.pick not in {"HOME", "DRAW", "AWAY"}:
                raise ValueError(f"{m.value} pick must be HOME, DRAW, or AWAY")

        # ── period double chance ──
        if m in {Market.HT_DOUBLE_CHANCE, Market.SECOND_HALF_DOUBLE_CHANCE}:
            if self.pick not in {"1X", "X2", "12"}:
                raise ValueError(f"{m.value} pick must be 1X, X2, or 12")

        # ── period draw no bet ──
        if m in {Market.HT_DRAW_NO_BET, Market.SECOND_HALF_DRAW_NO_BET}:
            if self.pick not in {"HOME", "AWAY"}:
                raise ValueError(f"{m.value} pick must be HOME or AWAY")

        # ── period odd/even ──
        if m in {Market.ODD_EVEN, Market.HT_ODD_EVEN, Market.SECOND_HALF_ODD_EVEN}:
            if self.pick not in {"ODD", "EVEN"}:
                raise ValueError(f"{m.value} pick must be ODD or EVEN")

        # ── handicap ──
        if m in {Market.ASIAN_HANDICAP, Market.HT_ASIAN_HANDICAP}:
            if self.pick not in {"HOME", "AWAY"}:
                raise ValueError(f"{m.value} pick must be HOME or AWAY")
            if self.line is None:
                raise ValueError(f"{m.value} requires line")

        if m == Market.HANDICAP_RESULT:
            if self.pick not in {"HOME", "DRAW", "AWAY"}:
                raise ValueError("HANDICAP_RESULT pick must be HOME, DRAW, or AWAY")
            if self.line is None:
                raise ValueError("HANDICAP_RESULT requires line")

        # ── HT/FT ──
        if m == Market.HT_FT:
            norm = self.pick.replace("-", "/")
            if "/" not in norm:
                raise ValueError("HT_FT pick must be in format HOME/AWAY or 1/2")

        # ── win to nil ──
        if m == Market.WIN_TO_NIL and self.pick not in {"HOME", "AWAY"}:
            raise ValueError("WIN_TO_NIL pick must be HOME or AWAY")

        # ── clean sheet ──
        if m == Market.CLEAN_SHEET:
            if self.pick not in {"YES", "NO"}:
                raise ValueError("CLEAN_SHEET pick must be YES or NO")
            tv = (self.team or "").strip().upper()
            if tv not in {"HOME", "AWAY"}:
                raise ValueError("CLEAN_SHEET requires team=HOME or team=AWAY")
            self.team = tv

        # ── first/last team to score ──
        if m in {Market.FIRST_TEAM_TO_SCORE, Market.LAST_TEAM_TO_SCORE}:
            if self.pick not in {"HOME", "AWAY", "NONE"}:
                raise ValueError(f"{m.value} pick must be HOME, AWAY, or NONE")

        # ── cross-half ──
        if m == Market.TO_SCORE_IN_BOTH_HALVES:
            if self.pick not in {"YES", "NO"}:
                raise ValueError("TO_SCORE_IN_BOTH_HALVES pick must be YES or NO")
            tv = (self.team or "").strip().upper()
            if tv not in {"HOME", "AWAY"}:
                raise ValueError("TO_SCORE_IN_BOTH_HALVES requires team=HOME or team=AWAY")
            self.team = tv

        if m in {Market.TO_WIN_EITHER_HALF, Market.TO_WIN_BOTH_HALVES}:
            if self.pick not in {"HOME", "AWAY"}:
                raise ValueError(f"{m.value} pick must be HOME or AWAY")

        if m == Market.HIGHEST_SCORING_HALF:
            if self.pick not in {"FIRST", "SECOND", "EQUAL", "1ST", "2ND", "TIE"}:
                raise ValueError("HIGHEST_SCORING_HALF pick must be FIRST, SECOND, or EQUAL")

        return self


class BetslipValidationRequest(BaseModel):
    base_url: str = Field(min_length=1)
    api_key: Optional[str] = Field(default=None)
    selections: List[SelectionIn] = Field(min_length=1)


class TableRowIn(BaseModel):
    fixture_id: int = Field(gt=0)
    market: str = Field(min_length=1)
    pick: str = Field(min_length=1)
    line: Optional[float] = None
    team: Optional[str] = Field(default=None)


class TableValidationRequest(BaseModel):
    base_url: Optional[str] = Field(default=None)
    api_key: Optional[str] = Field(default=None)
    rows: List[TableRowIn] = Field(min_length=1)


# ═══════════════════════════════════════════════════════════════════════════════
#  Market normalization — ~200 aliases covering API-Football catalog names
# ═══════════════════════════════════════════════════════════════════════════════


def _normalize_market(value: str) -> Market:
    key = value.strip().upper()
    for ch in "-/ ().,?'":
        key = key.replace(ch, "_")
    while "__" in key:
        key = key.replace("__", "_")
    key = key.strip("_")

    m = _MARKET_ALIASES.get(key)
    return m if m is not None else Market.UNMAPPED


_MARKET_ALIASES: dict[str, Market] = {
    # ── Match Winner / 1X2 ──
    "MATCH_WINNER": Market.MATCH_WINNER,
    "1X2": Market.MATCH_WINNER,
    "MONEYLINE": Market.MATCH_WINNER,
    "HOME_AWAY": Market.MATCH_WINNER,
    "FULL_TIME_RESULT": Market.MATCH_WINNER,
    "FT_RESULT": Market.MATCH_WINNER,

    # ── Double Chance ──
    "DOUBLE_CHANCE": Market.DOUBLE_CHANCE,
    "DC": Market.DOUBLE_CHANCE,

    # ── Draw No Bet ──
    "DRAW_NO_BET": Market.DRAW_NO_BET,
    "DNB": Market.DRAW_NO_BET,

    # ── Over / Under ──
    "OVER_UNDER": Market.OVER_UNDER,
    "GOALS_OVER_UNDER": Market.OVER_UNDER,
    "OU": Market.OVER_UNDER,
    "TOTAL_GOALS": Market.OVER_UNDER,
    "GOALS_OVER_UNDER_ALTERNATIVE": Market.OVER_UNDER,

    # ── BTTS ──
    "BTTS": Market.BTTS,
    "BOTH_TEAMS_SCORE": Market.BTTS,
    "BOTH_TEAMS_TO_SCORE": Market.BTTS,
    "GGNG": Market.BTTS,

    # ── Team Over/Under ──
    "TEAM_OVER_UNDER": Market.TEAM_OVER_UNDER,
    "TEAM_TOTAL_GOALS": Market.TEAM_OVER_UNDER,
    "TOTAL_HOME": Market.TEAM_OVER_UNDER,
    "TOTAL_AWAY": Market.TEAM_OVER_UNDER,
    "HOME_TEAM_GOALS": Market.TEAM_OVER_UNDER,
    "AWAY_TEAM_GOALS": Market.TEAM_OVER_UNDER,
    "HOME_TEAM_OVER_UNDER": Market.TEAM_OVER_UNDER,
    "AWAY_TEAM_OVER_UNDER": Market.TEAM_OVER_UNDER,

    # ── Exact Goals ──
    "EXACT_GOALS": Market.EXACT_GOALS,
    "EXACT_GOALS_NUMBER": Market.EXACT_GOALS,
    "TOTAL_GOALS_EXACT": Market.EXACT_GOALS,

    # ── Team Exact Goals ──
    "TEAM_EXACT_GOALS": Market.TEAM_EXACT_GOALS,
    "HOME_TEAM_EXACT_GOALS": Market.TEAM_EXACT_GOALS,
    "AWAY_TEAM_EXACT_GOALS": Market.TEAM_EXACT_GOALS,

    # ── Multi Goals ──
    "MULTI_GOALS": Market.MULTI_GOALS,
    "MULTIGOALS": Market.MULTI_GOALS,
    "TOTAL_GOALS_RANGE": Market.MULTI_GOALS,

    # ── Odd / Even ──
    "ODD_EVEN": Market.ODD_EVEN,

    # ── Correct Score ──
    "CORRECT_SCORE": Market.CORRECT_SCORE,
    "EXACT_SCORE": Market.CORRECT_SCORE,
    "CS": Market.CORRECT_SCORE,

    # ── Asian Handicap ──
    "ASIAN_HANDICAP": Market.ASIAN_HANDICAP,
    "HANDICAP": Market.ASIAN_HANDICAP,
    "AH": Market.ASIAN_HANDICAP,
    "ASIAN_HANDICAP_ALTERNATIVE": Market.ASIAN_HANDICAP,

    # ── Handicap Result (European) ──
    "HANDICAP_RESULT": Market.HANDICAP_RESULT,
    "EUROPEAN_HANDICAP": Market.HANDICAP_RESULT,
    "3_WAY_HANDICAP": Market.HANDICAP_RESULT,

    # ── Clean Sheet ──
    "CLEAN_SHEET": Market.CLEAN_SHEET,
    "CLEAN_SHEET_HOME": Market.CLEAN_SHEET,
    "CLEAN_SHEET_AWAY": Market.CLEAN_SHEET,
    "HOME_CLEAN_SHEET": Market.CLEAN_SHEET,
    "AWAY_CLEAN_SHEET": Market.CLEAN_SHEET,

    # ── Win to Nil ──
    "WIN_TO_NIL": Market.WIN_TO_NIL,
    "HOME_WIN_TO_NIL": Market.WIN_TO_NIL,
    "AWAY_WIN_TO_NIL": Market.WIN_TO_NIL,
    "WIN_TO_NIL_HOME": Market.WIN_TO_NIL,
    "WIN_TO_NIL_AWAY": Market.WIN_TO_NIL,

    # ── First / Last Team to Score ──
    "FIRST_TEAM_TO_SCORE": Market.FIRST_TEAM_TO_SCORE,
    "FIRST_GOAL": Market.FIRST_TEAM_TO_SCORE,
    "LAST_TEAM_TO_SCORE": Market.LAST_TEAM_TO_SCORE,
    "LAST_GOAL": Market.LAST_TEAM_TO_SCORE,

    # ── Result + BTTS ──
    "RESULT_BTTS": Market.RESULT_BTTS,
    "RESULT_BOTH_TEAMS_SCORE": Market.RESULT_BTTS,
    "RESULT_BOTH_TEAMS_TO_SCORE": Market.RESULT_BTTS,
    "MATCH_RESULT_AND_BTTS": Market.RESULT_BTTS,

    # ── Result + Over/Under ──
    "RESULT_OVER_UNDER": Market.RESULT_OVER_UNDER,
    "RESULT_TOTAL_GOALS": Market.RESULT_OVER_UNDER,
    "HOME_AWAY_TOTAL": Market.RESULT_OVER_UNDER,
    "MATCH_RESULT_AND_TOTAL": Market.RESULT_OVER_UNDER,

    # ── Margin of Victory ──
    "MARGIN_OF_VICTORY": Market.MARGIN_OF_VICTORY,
    "WINNING_MARGIN": Market.MARGIN_OF_VICTORY,

    # ── HT Match Winner ──
    "HT_MATCH_WINNER": Market.HT_MATCH_WINNER,
    "HT_1X2": Market.HT_MATCH_WINNER,
    "1H_1X2": Market.HT_MATCH_WINNER,
    "FIRST_HALF_WINNER": Market.HT_MATCH_WINNER,
    "1ST_HALF_RESULT": Market.HT_MATCH_WINNER,

    # ── HT Over/Under ──
    "HT_OVER_UNDER": Market.HT_OVER_UNDER,
    "HT_OU": Market.HT_OVER_UNDER,
    "GOALS_OVER_UNDER_FIRST_HALF": Market.HT_OVER_UNDER,
    "FIRST_HALF_OVER_UNDER": Market.HT_OVER_UNDER,

    # ── HT BTTS ──
    "HT_BTTS": Market.HT_BTTS,
    "BOTH_TEAMS_SCORE_FIRST_HALF": Market.HT_BTTS,
    "BOTH_TEAMS_TO_SCORE_FIRST_HALF": Market.HT_BTTS,
    "BTTS_FIRST_HALF": Market.HT_BTTS,
    "1H_BTTS": Market.HT_BTTS,

    # ── HT Double Chance ──
    "HT_DOUBLE_CHANCE": Market.HT_DOUBLE_CHANCE,
    "DOUBLE_CHANCE_FIRST_HALF": Market.HT_DOUBLE_CHANCE,
    "1H_DOUBLE_CHANCE": Market.HT_DOUBLE_CHANCE,

    # ── HT Draw No Bet ──
    "HT_DRAW_NO_BET": Market.HT_DRAW_NO_BET,
    "DRAW_NO_BET_1ST_HALF": Market.HT_DRAW_NO_BET,
    "DNB_1ST_HALF": Market.HT_DRAW_NO_BET,
    "1H_DNB": Market.HT_DRAW_NO_BET,

    # ── HT Odd/Even ──
    "HT_ODD_EVEN": Market.HT_ODD_EVEN,
    "ODD_EVEN_FIRST_HALF": Market.HT_ODD_EVEN,
    "1H_ODD_EVEN": Market.HT_ODD_EVEN,

    # ── HT Correct Score ──
    "HT_CORRECT_SCORE": Market.HT_CORRECT_SCORE,
    "CORRECT_SCORE_FIRST_HALF": Market.HT_CORRECT_SCORE,
    "EXACT_SCORE_FIRST_HALF": Market.HT_CORRECT_SCORE,

    # ── HT Asian Handicap ──
    "HT_ASIAN_HANDICAP": Market.HT_ASIAN_HANDICAP,
    "ASIAN_HANDICAP_FIRST_HALF": Market.HT_ASIAN_HANDICAP,
    "1H_ASIAN_HANDICAP": Market.HT_ASIAN_HANDICAP,

    # ── 2H Match Winner ──
    "SECOND_HALF_MATCH_WINNER": Market.SECOND_HALF_MATCH_WINNER,
    "2H_1X2": Market.SECOND_HALF_MATCH_WINNER,
    "2H_MATCH_WINNER": Market.SECOND_HALF_MATCH_WINNER,
    "SECOND_HALF_WINNER": Market.SECOND_HALF_MATCH_WINNER,
    "2ND_HALF_RESULT": Market.SECOND_HALF_MATCH_WINNER,

    # ── 2H Over/Under ──
    "SECOND_HALF_OVER_UNDER": Market.SECOND_HALF_OVER_UNDER,
    "2H_OU": Market.SECOND_HALF_OVER_UNDER,
    "2H_OVER_UNDER": Market.SECOND_HALF_OVER_UNDER,
    "GOALS_OVER_UNDER_SECOND_HALF": Market.SECOND_HALF_OVER_UNDER,

    # ── 2H BTTS ──
    "SECOND_HALF_BTTS": Market.SECOND_HALF_BTTS,
    "2H_BTTS": Market.SECOND_HALF_BTTS,
    "BOTH_TEAMS_SCORE_SECOND_HALF": Market.SECOND_HALF_BTTS,
    "BOTH_TEAMS_TO_SCORE_SECOND_HALF": Market.SECOND_HALF_BTTS,
    "BTTS_SECOND_HALF": Market.SECOND_HALF_BTTS,

    # ── 2H Double Chance ──
    "SECOND_HALF_DOUBLE_CHANCE": Market.SECOND_HALF_DOUBLE_CHANCE,
    "2H_DOUBLE_CHANCE": Market.SECOND_HALF_DOUBLE_CHANCE,
    "DOUBLE_CHANCE_SECOND_HALF": Market.SECOND_HALF_DOUBLE_CHANCE,

    # ── 2H Draw No Bet ──
    "SECOND_HALF_DRAW_NO_BET": Market.SECOND_HALF_DRAW_NO_BET,
    "2H_DNB": Market.SECOND_HALF_DRAW_NO_BET,
    "DRAW_NO_BET_2ND_HALF": Market.SECOND_HALF_DRAW_NO_BET,
    "DNB_2ND_HALF": Market.SECOND_HALF_DRAW_NO_BET,

    # ── 2H Odd/Even ──
    "SECOND_HALF_ODD_EVEN": Market.SECOND_HALF_ODD_EVEN,
    "2H_ODD_EVEN": Market.SECOND_HALF_ODD_EVEN,
    "ODD_EVEN_SECOND_HALF": Market.SECOND_HALF_ODD_EVEN,

    # ── 2H Correct Score ──
    "SECOND_HALF_CORRECT_SCORE": Market.SECOND_HALF_CORRECT_SCORE,
    "2H_CORRECT_SCORE": Market.SECOND_HALF_CORRECT_SCORE,
    "CORRECT_SCORE_SECOND_HALF": Market.SECOND_HALF_CORRECT_SCORE,
    "EXACT_SCORE_SECOND_HALF": Market.SECOND_HALF_CORRECT_SCORE,

    # ── HT/FT ──
    "HT_FT": Market.HT_FT,
    "HTFT": Market.HT_FT,
    "HT_FT_DOUBLE": Market.HT_FT,
    "HALF_TIME_FULL_TIME": Market.HT_FT,

    # ── Cross-half ──
    "TO_SCORE_IN_BOTH_HALVES": Market.TO_SCORE_IN_BOTH_HALVES,
    "SCORE_BOTH_HALVES_BY_TEAMS": Market.TO_SCORE_IN_BOTH_HALVES,
    "TEAM_TO_SCORE_IN_BOTH_HALVES": Market.TO_SCORE_IN_BOTH_HALVES,
    "SCORE_IN_BOTH_HALVES": Market.TO_SCORE_IN_BOTH_HALVES,

    "TO_WIN_EITHER_HALF": Market.TO_WIN_EITHER_HALF,
    "WIN_EITHER_HALF": Market.TO_WIN_EITHER_HALF,

    "TO_WIN_BOTH_HALVES": Market.TO_WIN_BOTH_HALVES,
    "WIN_BOTH_HALVES": Market.TO_WIN_BOTH_HALVES,

    "HIGHEST_SCORING_HALF": Market.HIGHEST_SCORING_HALF,
    "HIGHEST_SCORING_HALF_HOME": Market.HIGHEST_SCORING_HALF,
    "HIGHEST_SCORING_HALF_AWAY": Market.HIGHEST_SCORING_HALF,

    "BOTH_HALVES_OVER_UNDER": Market.BOTH_HALVES_OVER_UNDER,
    "BOTH_HALVES_OVER": Market.BOTH_HALVES_OVER_UNDER,
    "BOTH_HALVES_UNDER": Market.BOTH_HALVES_OVER_UNDER,

    # ── Corners ──
    "CORNERS_OVER_UNDER": Market.CORNERS_OVER_UNDER,
    "TOTAL_CORNERS": Market.CORNERS_OVER_UNDER,
    "CORNERS_OU": Market.CORNERS_OVER_UNDER,
    "CORNERS_OVER_UNDER_FIRST_HALF": Market.CORNERS_OVER_UNDER,

    "TEAM_CORNERS_OVER_UNDER": Market.TEAM_CORNERS_OVER_UNDER,
    "TEAM_CORNERS_OU": Market.TEAM_CORNERS_OVER_UNDER,
    "HOME_CORNERS_OVER_UNDER": Market.TEAM_CORNERS_OVER_UNDER,
    "AWAY_CORNERS_OVER_UNDER": Market.TEAM_CORNERS_OVER_UNDER,
    "HOME_TOTAL_CORNERS": Market.TEAM_CORNERS_OVER_UNDER,
    "AWAY_TOTAL_CORNERS": Market.TEAM_CORNERS_OVER_UNDER,
    "HOME_TEAM_TOTAL_CORNERS": Market.TEAM_CORNERS_OVER_UNDER,
    "AWAY_TEAM_TOTAL_CORNERS": Market.TEAM_CORNERS_OVER_UNDER,

    # ── Cards ──
    "CARDS_OVER_UNDER": Market.CARDS_OVER_UNDER,
    "CARDS_OU": Market.CARDS_OVER_UNDER,
    "YELLOW_OVER_UNDER": Market.CARDS_OVER_UNDER,
    "RED_CARDS_OVER_UNDER": Market.CARDS_OVER_UNDER,
    "TOTAL_CARDS": Market.CARDS_OVER_UNDER,

    "TEAM_CARDS_OVER_UNDER": Market.TEAM_CARDS_OVER_UNDER,
    "TEAM_CARDS_OU": Market.TEAM_CARDS_OVER_UNDER,
    "HOME_TEAM_TOTAL_CARDS": Market.TEAM_CARDS_OVER_UNDER,
    "AWAY_TEAM_TOTAL_CARDS": Market.TEAM_CARDS_OVER_UNDER,
    "HOME_TEAM_YELLOW_CARDS": Market.TEAM_CARDS_OVER_UNDER,
    "AWAY_TEAM_YELLOW_CARDS": Market.TEAM_CARDS_OVER_UNDER,

    # ── Shots ──
    "SHOTS_OVER_UNDER": Market.SHOTS_OVER_UNDER,
    "TOTAL_SHOTS": Market.SHOTS_OVER_UNDER,
    "SHOTS_OU": Market.SHOTS_OVER_UNDER,

    "SHOTS_ON_TARGET_OVER_UNDER": Market.SHOTS_ON_TARGET_OVER_UNDER,
    "SHOTS_ON_TARGET": Market.SHOTS_ON_TARGET_OVER_UNDER,
    "TOTAL_SHOTS_ON_TARGET": Market.SHOTS_ON_TARGET_OVER_UNDER,

    # ── Fouls ──
    "FOULS_OVER_UNDER": Market.FOULS_OVER_UNDER,
    "TOTAL_FOULS": Market.FOULS_OVER_UNDER,
    "FOULS_OU": Market.FOULS_OVER_UNDER,

    # ── Offsides ──
    "OFFSIDES_OVER_UNDER": Market.OFFSIDES_OVER_UNDER,
    "TOTAL_OFFSIDES": Market.OFFSIDES_OVER_UNDER,
    "OFFSIDES_OU": Market.OFFSIDES_OVER_UNDER,
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Pick normalization
# ═══════════════════════════════════════════════════════════════════════════════

_1X2_MAP = {"1": "HOME", "H": "HOME", "HOME": "HOME",
            "X": "DRAW", "D": "DRAW", "DRAW": "DRAW",
            "2": "AWAY", "A": "AWAY", "AWAY": "AWAY"}

_OU_MAP = {"OVER": "OVER", "O": "OVER", "UNDER": "UNDER", "U": "UNDER"}

_YES_NO_MAP = {"YES": "YES", "Y": "YES", "GG": "YES", "NO": "NO", "N": "NO", "NG": "NO"}

_HOME_AWAY_MAP = {"1": "HOME", "HOME": "HOME", "2": "AWAY", "AWAY": "AWAY"}

_ODD_EVEN_MAP = {"ODD": "ODD", "EVEN": "EVEN"}

_DC_MAP = {"1X": "1X", "X2": "X2", "12": "12"}


def _normalize_pick(market: Market, pick: str) -> str:
    key = pick.strip().upper().replace(" ", "")
    m = market

    # ── simple lookups ──
    if m in {Market.MATCH_WINNER, Market.HT_MATCH_WINNER, Market.SECOND_HALF_MATCH_WINNER}:
        return _lookup(key, _1X2_MAP, pick, m)
    if m in {Market.DOUBLE_CHANCE, Market.HT_DOUBLE_CHANCE, Market.SECOND_HALF_DOUBLE_CHANCE}:
        return _lookup(key, _DC_MAP, pick, m)
    if m in {Market.DRAW_NO_BET, Market.HT_DRAW_NO_BET, Market.SECOND_HALF_DRAW_NO_BET,
             Market.WIN_TO_NIL, Market.ASIAN_HANDICAP, Market.HT_ASIAN_HANDICAP}:
        return _lookup(key, _HOME_AWAY_MAP, pick, m)
    if m in {Market.OVER_UNDER, Market.HT_OVER_UNDER, Market.SECOND_HALF_OVER_UNDER,
             Market.TEAM_OVER_UNDER, Market.BOTH_HALVES_OVER_UNDER,
             Market.CORNERS_OVER_UNDER, Market.TEAM_CORNERS_OVER_UNDER,
             Market.CARDS_OVER_UNDER, Market.TEAM_CARDS_OVER_UNDER,
             Market.SHOTS_OVER_UNDER, Market.SHOTS_ON_TARGET_OVER_UNDER,
             Market.FOULS_OVER_UNDER, Market.OFFSIDES_OVER_UNDER}:
        return _lookup(key, _OU_MAP, pick, m)
    if m in {Market.BTTS, Market.HT_BTTS, Market.SECOND_HALF_BTTS,
             Market.CLEAN_SHEET, Market.TO_SCORE_IN_BOTH_HALVES}:
        return _lookup(key, _YES_NO_MAP, pick, m)
    if m in {Market.ODD_EVEN, Market.HT_ODD_EVEN, Market.SECOND_HALF_ODD_EVEN}:
        return _lookup(key, _ODD_EVEN_MAP, pick, m)
    if m in {Market.TO_WIN_EITHER_HALF, Market.TO_WIN_BOTH_HALVES}:
        return _lookup(key, _HOME_AWAY_MAP, pick, m)
    if m == Market.HANDICAP_RESULT:
        return _lookup(key, _1X2_MAP, pick, m)
    if m in {Market.FIRST_TEAM_TO_SCORE, Market.LAST_TEAM_TO_SCORE}:
        extra = {**_HOME_AWAY_MAP, "NONE": "NONE", "NO_GOAL": "NONE", "NOGOAL": "NONE"}
        return _lookup(key, extra, pick, m)
    if m == Market.HIGHEST_SCORING_HALF:
        hmap = {"FIRST": "FIRST", "1ST": "FIRST", "1": "FIRST",
                "SECOND": "SECOND", "2ND": "SECOND", "2": "SECOND",
                "EQUAL": "EQUAL", "TIE": "EQUAL", "X": "EQUAL"}
        return _lookup(key, hmap, pick, m)

    # ── score formats ──
    if m in {Market.CORRECT_SCORE, Market.HT_CORRECT_SCORE, Market.SECOND_HALF_CORRECT_SCORE}:
        norm = key.replace("-", ":")
        parts = norm.split(":")
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            return norm
        raise ValueError(f"Unsupported pick '{pick}' for {m.value}")

    # ── HT/FT combo ──
    if m == Market.HT_FT:
        norm = key.replace("-", "/")
        tokens = norm.split("/")
        valid_tokens = {"1", "X", "2", "HOME", "DRAW", "AWAY"}
        if len(tokens) == 2 and all(t in valid_tokens for t in tokens):
            return norm
        raise ValueError(f"Unsupported pick '{pick}' for HT_FT")

    # ── combo: result/btts ──
    if m == Market.RESULT_BTTS:
        norm = key.replace("-", "/")
        parts = norm.split("/")
        if len(parts) != 2:
            raise ValueError(f"RESULT_BTTS pick must be RESULT/BTTS, e.g. HOME/YES or 1/GG")
        r_map = {"1": "HOME", "HOME": "HOME", "X": "DRAW", "DRAW": "DRAW", "2": "AWAY", "AWAY": "AWAY"}
        b_map = {"YES": "YES", "GG": "YES", "Y": "YES", "NO": "NO", "NG": "NO", "N": "NO"}
        if parts[0] not in r_map or parts[1] not in b_map:
            raise ValueError(f"Unsupported pick '{pick}' for RESULT_BTTS")
        return f"{r_map[parts[0]]}/{b_map[parts[1]]}"

    # ── combo: result/over-under ──
    if m == Market.RESULT_OVER_UNDER:
        norm = key.replace("-", "/")
        parts = norm.split("/")
        if len(parts) != 2:
            raise ValueError(f"RESULT_OVER_UNDER pick must be RESULT/OU, e.g. HOME/OVER")
        r_map = {"1": "HOME", "HOME": "HOME", "X": "DRAW", "DRAW": "DRAW", "2": "AWAY", "AWAY": "AWAY"}
        o_map = {"OVER": "OVER", "O": "OVER", "UNDER": "UNDER", "U": "UNDER"}
        if parts[0] not in r_map or parts[1] not in o_map:
            raise ValueError(f"Unsupported pick '{pick}' for RESULT_OVER_UNDER")
        return f"{r_map[parts[0]]}/{o_map[parts[1]]}"

    # ── numeric / range (exact goals, multi goals, margin) ──
    if m in {Market.EXACT_GOALS, Market.TEAM_EXACT_GOALS, Market.MULTI_GOALS, Market.MARGIN_OF_VICTORY}:
        return key  # pass through; evaluator will parse

    # fallback
    return key


def _lookup(key: str, mapping: dict[str, str], raw: str, m: Market) -> str:
    if key not in mapping:
        raise ValueError(f"Unsupported pick '{raw}' for market {m.value}")
    return mapping[key]


# ═══════════════════════════════════════════════════════════════════════════════
#  Row → Selection
# ═══════════════════════════════════════════════════════════════════════════════


def _row_to_selection(row: TableRowIn) -> Selection:
    market = _normalize_market(row.market)
    if market == Market.UNMAPPED:
        return Selection(
            fixture_id=row.fixture_id,
            market=Market.UNMAPPED,
            pick=row.pick.strip().upper(),
            line=row.line,
            team=(row.team or "").strip().upper() or None,
            raw_market=row.market,
        )

    normalized_pick = _normalize_pick(market, row.pick)

    # line-required validation
    _line_markets = {
        Market.OVER_UNDER, Market.HT_OVER_UNDER, Market.SECOND_HALF_OVER_UNDER,
        Market.TEAM_OVER_UNDER, Market.BOTH_HALVES_OVER_UNDER,
        Market.ASIAN_HANDICAP, Market.HT_ASIAN_HANDICAP, Market.HANDICAP_RESULT,
        Market.CORNERS_OVER_UNDER, Market.TEAM_CORNERS_OVER_UNDER,
        Market.CARDS_OVER_UNDER, Market.TEAM_CARDS_OVER_UNDER,
        Market.SHOTS_OVER_UNDER, Market.SHOTS_ON_TARGET_OVER_UNDER,
        Market.FOULS_OVER_UNDER, Market.OFFSIDES_OVER_UNDER,
        Market.RESULT_OVER_UNDER,
    }
    if market in _line_markets and row.line is None:
        raise ValueError(f"Row for fixture {row.fixture_id} requires line for {market.value}")

    # team-required validation
    _team_markets = {
        Market.TEAM_OVER_UNDER, Market.TEAM_CORNERS_OVER_UNDER, Market.TEAM_CARDS_OVER_UNDER,
        Market.CLEAN_SHEET, Market.TEAM_EXACT_GOALS, Market.TO_SCORE_IN_BOTH_HALVES,
    }
    normalized_team: Optional[str] = None
    if market in _team_markets:
        normalized_team = (row.team or "").strip().upper()
        if normalized_team not in {"HOME", "AWAY"}:
            raise ValueError(f"Row for fixture {row.fixture_id} requires team=HOME or team=AWAY for {market.value}")

    return Selection(
        fixture_id=row.fixture_id,
        market=market,
        pick=normalized_pick,
        line=row.line,
        team=normalized_team,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  FastAPI app
# ═══════════════════════════════════════════════════════════════════════════════


def _run_validation(base_url: str, api_key: Optional[str], selections: List[Selection]) -> dict:
    try:
        client = APISportsClient(base_url=base_url, api_key=api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return evaluate_betslip(client, selections)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected settlement error: {exc}") from exc


app = FastAPI(title="Betslip Validator API", version="2.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/markets/supported")
def supported_markets() -> dict:
    return {
        "implemented": sorted(m.value for m in IMPLEMENTED_MARKETS),
        "count": len(IMPLEMENTED_MARKETS),
    }


@app.get("/markets/discovered")
def discovered_markets(base_url: str, api_key: Optional[str] = None) -> dict:
    try:
        client = APISportsClient(base_url=base_url, api_key=api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        catalog = client.get_odds_bets_catalog()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch odds bet catalog: {exc}") from exc

    discovered = []
    for item in catalog:
        name = str(item.get("name") or "")
        norm = _normalize_market(name)
        discovered.append({
            "id": item.get("id"),
            "name": name,
            "values": item.get("values"),
            "implemented": norm in IMPLEMENTED_MARKETS,
        })
    implemented_count = sum(1 for d in discovered if d["implemented"])
    return {
        "total_discovered": len(discovered),
        "implemented_count": implemented_count,
        "not_implemented_count": len(discovered) - implemented_count,
        "markets": discovered,
    }


@app.post("/validate-betslip")
def validate_betslip(payload: BetslipValidationRequest) -> dict:
    selections = [
        Selection(fixture_id=s.fixture_id, market=s.market, pick=s.pick, line=s.line, team=s.team)
        for s in payload.selections
    ]
    return _run_validation(payload.base_url, payload.api_key, selections)


@app.post("/validate-betslip/table")
def validate_betslip_table(payload: TableValidationRequest) -> dict:
    base_url = payload.base_url or os.getenv("API_BASE_URL", "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="Missing base_url. Provide it or set API_BASE_URL.")
    try:
        selections = [_row_to_selection(row) for row in payload.rows]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _run_validation(base_url, payload.api_key, selections)
