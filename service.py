from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from api_client import APISportsClient
from evaluator import evaluate_betslip
from models import Market, Selection


IMPLEMENTED_MARKETS = {
    Market.MATCH_WINNER,
    Market.DOUBLE_CHANCE,
    Market.OVER_UNDER,
    Market.BTTS,
    Market.DRAW_NO_BET,
    Market.TEAM_OVER_UNDER,
    Market.CORRECT_SCORE,
    Market.HT_MATCH_WINNER,
    Market.SECOND_HALF_MATCH_WINNER,
    Market.HT_OVER_UNDER,
    Market.SECOND_HALF_OVER_UNDER,
    Market.HT_FT,
    Market.CORNERS_OVER_UNDER,
    Market.TEAM_CORNERS_OVER_UNDER,
    Market.CARDS_OVER_UNDER,
    Market.TEAM_CARDS_OVER_UNDER,
    Market.ASIAN_HANDICAP,
    Market.ODD_EVEN,
    Market.WIN_TO_NIL,
}


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
        if self.market == Market.MATCH_WINNER and self.pick not in {"HOME", "DRAW", "AWAY"}:
            raise ValueError("MATCH_WINNER pick must be one of HOME, DRAW, AWAY")
        if self.market == Market.DOUBLE_CHANCE and self.pick not in {"1X", "X2", "12"}:
            raise ValueError("DOUBLE_CHANCE pick must be one of 1X, X2, 12")
        if self.market == Market.OVER_UNDER:
            if self.pick not in {"OVER", "UNDER"}:
                raise ValueError("OVER_UNDER pick must be OVER or UNDER")
            if self.line is None:
                raise ValueError("OVER_UNDER requires line")
        if self.market == Market.BTTS and self.pick not in {"YES", "NO"}:
            raise ValueError("BTTS pick must be YES or NO")
        if self.market == Market.DRAW_NO_BET and self.pick not in {"HOME", "AWAY"}:
            raise ValueError("DRAW_NO_BET pick must be HOME or AWAY")
        if self.market == Market.TEAM_OVER_UNDER:
            if self.pick not in {"OVER", "UNDER"}:
                raise ValueError("TEAM_OVER_UNDER pick must be OVER or UNDER")
            if self.line is None:
                raise ValueError("TEAM_OVER_UNDER requires line")
            team_value = (self.team or "").strip().upper()
            if team_value not in {"HOME", "AWAY"}:
                raise ValueError("TEAM_OVER_UNDER requires team=HOME or team=AWAY")
            self.team = team_value
        if self.market == Market.CORRECT_SCORE and ":" not in self.pick and "-" not in self.pick:
            raise ValueError("CORRECT_SCORE pick must be score format like 2:1")
        if self.market in {Market.HT_MATCH_WINNER, Market.SECOND_HALF_MATCH_WINNER} and self.pick not in {
            "HOME",
            "DRAW",
            "AWAY",
        }:
            raise ValueError(f"{self.market.value} pick must be HOME, DRAW, or AWAY")
        if self.market in {Market.HT_OVER_UNDER, Market.SECOND_HALF_OVER_UNDER}:
            if self.pick not in {"OVER", "UNDER"}:
                raise ValueError(f"{self.market.value} pick must be OVER or UNDER")
            if self.line is None:
                raise ValueError(f"{self.market.value} requires line")
        if self.market == Market.HT_FT:
            normalized = self.pick.replace("-", "/")
            if "/" not in normalized:
                raise ValueError("HT_FT pick must be in format HOME/AWAY or 1/2")
        if self.market in {
            Market.CORNERS_OVER_UNDER,
            Market.CARDS_OVER_UNDER,
            Market.TEAM_CORNERS_OVER_UNDER,
            Market.TEAM_CARDS_OVER_UNDER,
        }:
            if self.pick not in {"OVER", "UNDER"}:
                raise ValueError(f"{self.market.value} pick must be OVER or UNDER")
            if self.line is None:
                raise ValueError(f"{self.market.value} requires line")
        if self.market in {Market.TEAM_CORNERS_OVER_UNDER, Market.TEAM_CARDS_OVER_UNDER}:
            team_value = (self.team or "").strip().upper()
            if team_value not in {"HOME", "AWAY"}:
                raise ValueError(f"{self.market.value} requires team=HOME or team=AWAY")
            self.team = team_value
        if self.market == Market.ASIAN_HANDICAP:
            if self.pick not in {"HOME", "AWAY"}:
                raise ValueError("ASIAN_HANDICAP pick must be HOME or AWAY")
            if self.line is None:
                raise ValueError("ASIAN_HANDICAP requires line")
        if self.market == Market.ODD_EVEN and self.pick not in {"ODD", "EVEN"}:
            raise ValueError("ODD_EVEN pick must be ODD or EVEN")
        if self.market == Market.WIN_TO_NIL and self.pick not in {"HOME", "AWAY"}:
            raise ValueError("WIN_TO_NIL pick must be HOME or AWAY")
        return self


class BetslipValidationRequest(BaseModel):
    base_url: str = Field(min_length=1, description="API-Sports base URL, e.g. https://v3.football.api-sports.io")
    api_key: Optional[str] = Field(default=None, description="Optional API key, else API_SPORTS_KEY env var is used")
    selections: List[SelectionIn] = Field(min_length=1)


class TableRowIn(BaseModel):
    fixture_id: int = Field(gt=0)
    market: str = Field(min_length=1, description="Examples: MATCH_WINNER, 1X2, DOUBLE_CHANCE, OVER_UNDER, BTTS")
    pick: str = Field(min_length=1, description="Examples: HOME, 1, X, OVER, YES")
    line: Optional[float] = None
    team: Optional[str] = Field(default=None, description="For team-based markets: HOME or AWAY")


class TableValidationRequest(BaseModel):
    base_url: Optional[str] = Field(default=None, description="If omitted, API_BASE_URL env var is used")
    api_key: Optional[str] = Field(default=None, description="Optional API key, else API_SPORTS_KEY env var is used")
    rows: List[TableRowIn] = Field(min_length=1)


def _normalize_market(value: str) -> Market:
    key = value.strip().upper()
    for token in ["-", " ", "/", "(", ")", ".", "?", "'", ","]:
        key = key.replace(token, "_")
    while "__" in key:
        key = key.replace("__", "_")
    key = key.strip("_")
    aliases = {
        "MATCH_WINNER": Market.MATCH_WINNER,
        "1X2": Market.MATCH_WINNER,
        "MONEYLINE": Market.MATCH_WINNER,
        "FIRST_HALF_WINNER": Market.HT_MATCH_WINNER,
        "SECOND_HALF_WINNER": Market.SECOND_HALF_MATCH_WINNER,
        "DOUBLE_CHANCE": Market.DOUBLE_CHANCE,
        "DOUBLE_CHANCE_FIRST_HALF": Market.DOUBLE_CHANCE,
        "DOUBLE_CHANCE_SECOND_HALF": Market.DOUBLE_CHANCE,
        "DC": Market.DOUBLE_CHANCE,
        "OVER_UNDER": Market.OVER_UNDER,
        "GOALS_OVER_UNDER": Market.OVER_UNDER,
        "OU": Market.OVER_UNDER,
        "GOALS_OVER_UNDER_FIRST_HALF": Market.HT_OVER_UNDER,
        "GOALS_OVER_UNDER_SECOND_HALF": Market.SECOND_HALF_OVER_UNDER,
        "BTTS": Market.BTTS,
        "BOTH_TEAMS_SCORE": Market.BTTS,
        "BOTH_TEAMS_TO_SCORE": Market.BTTS,
        "BOTH_TEAMS_TO_SCORE": Market.BTTS,
        "GGNG": Market.BTTS,
        "DRAW_NO_BET": Market.DRAW_NO_BET,
        "DRAW_NO_BET_1ST_HALF": Market.DRAW_NO_BET,
        "DRAW_NO_BET_2ND_HALF": Market.DRAW_NO_BET,
        "DNB": Market.DRAW_NO_BET,
        "TEAM_OVER_UNDER": Market.TEAM_OVER_UNDER,
        "TEAM_TOTAL_GOALS": Market.TEAM_OVER_UNDER,
        "TOTAL_HOME": Market.TEAM_OVER_UNDER,
        "TOTAL_AWAY": Market.TEAM_OVER_UNDER,
        "CORRECT_SCORE": Market.CORRECT_SCORE,
        "EXACT_SCORE": Market.CORRECT_SCORE,
        "CS": Market.CORRECT_SCORE,
        "HT_MATCH_WINNER": Market.HT_MATCH_WINNER,
        "HT_1X2": Market.HT_MATCH_WINNER,
        "1H_1X2": Market.HT_MATCH_WINNER,
        "SECOND_HALF_MATCH_WINNER": Market.SECOND_HALF_MATCH_WINNER,
        "2H_1X2": Market.SECOND_HALF_MATCH_WINNER,
        "HT_OVER_UNDER": Market.HT_OVER_UNDER,
        "HT_OU": Market.HT_OVER_UNDER,
        "SECOND_HALF_OVER_UNDER": Market.SECOND_HALF_OVER_UNDER,
        "2H_OU": Market.SECOND_HALF_OVER_UNDER,
        "HT_FT": Market.HT_FT,
        "HTFT": Market.HT_FT,
        "HT_FT_DOUBLE": Market.HT_FT,
        "CORNERS_OVER_UNDER": Market.CORNERS_OVER_UNDER,
        "CORNERS_OVER_UNDER": Market.CORNERS_OVER_UNDER,
        "CORNERS_OVER_UNDER_FIRST_HALF": Market.CORNERS_OVER_UNDER,
        "TOTAL_CORNERS": Market.CORNERS_OVER_UNDER,
        "CORNERS_OU": Market.CORNERS_OVER_UNDER,
        "TEAM_CORNERS_OVER_UNDER": Market.TEAM_CORNERS_OVER_UNDER,
        "HOME_CORNERS_OVER_UNDER": Market.TEAM_CORNERS_OVER_UNDER,
        "AWAY_CORNERS_OVER_UNDER": Market.TEAM_CORNERS_OVER_UNDER,
        "HOME_TOTAL_CORNERS": Market.TEAM_CORNERS_OVER_UNDER,
        "AWAY_TOTAL_CORNERS": Market.TEAM_CORNERS_OVER_UNDER,
        "TEAM_CORNERS_OU": Market.TEAM_CORNERS_OVER_UNDER,
        "CARDS_OVER_UNDER": Market.CARDS_OVER_UNDER,
        "YELLOW_OVER_UNDER": Market.CARDS_OVER_UNDER,
        "RED_CARDS_OVER_UNDER": Market.CARDS_OVER_UNDER,
        "CARDS_OU": Market.CARDS_OVER_UNDER,
        "TEAM_CARDS_OVER_UNDER": Market.TEAM_CARDS_OVER_UNDER,
        "HOME_TEAM_TOTAL_CARDS": Market.TEAM_CARDS_OVER_UNDER,
        "AWAY_TEAM_TOTAL_CARDS": Market.TEAM_CARDS_OVER_UNDER,
        "HOME_TEAM_YELLOW_CARDS": Market.TEAM_CARDS_OVER_UNDER,
        "AWAY_TEAM_YELLOW_CARDS": Market.TEAM_CARDS_OVER_UNDER,
        "TEAM_CARDS_OU": Market.TEAM_CARDS_OVER_UNDER,
        "ASIAN_HANDICAP": Market.ASIAN_HANDICAP,
        "HANDICAP": Market.ASIAN_HANDICAP,
        "ODD_EVEN": Market.ODD_EVEN,
        "ODD_EVEN_FIRST_HALF": Market.ODD_EVEN,
        "ODD_EVEN_SECOND_HALF": Market.ODD_EVEN,
        "WIN_TO_NIL": Market.WIN_TO_NIL,
        "WIN_TO_NIL_HOME": Market.WIN_TO_NIL,
        "WIN_TO_NIL_AWAY": Market.WIN_TO_NIL,
        "HOME_WIN_TO_NIL": Market.WIN_TO_NIL,
        "AWAY_WIN_TO_NIL": Market.WIN_TO_NIL,
    }
    if key not in aliases:
        return Market.UNMAPPED
    return aliases[key]


def _normalize_pick(market: Market, pick: str) -> str:
    key = pick.strip().upper().replace(" ", "")

    if market == Market.MATCH_WINNER:
        mapping = {
            "1": "HOME",
            "H": "HOME",
            "HOME": "HOME",
            "X": "DRAW",
            "D": "DRAW",
            "DRAW": "DRAW",
            "2": "AWAY",
            "A": "AWAY",
            "AWAY": "AWAY",
        }
    elif market == Market.DOUBLE_CHANCE:
        mapping = {
            "1X": "1X",
            "X2": "X2",
            "12": "12",
        }
    elif market == Market.OVER_UNDER:
        mapping = {
            "OVER": "OVER",
            "O": "OVER",
            "UNDER": "UNDER",
            "U": "UNDER",
        }
    elif market == Market.DRAW_NO_BET:
        mapping = {
            "1": "HOME",
            "HOME": "HOME",
            "2": "AWAY",
            "AWAY": "AWAY",
        }
    elif market == Market.TEAM_OVER_UNDER:
        mapping = {
            "OVER": "OVER",
            "O": "OVER",
            "UNDER": "UNDER",
            "U": "UNDER",
        }
    elif market == Market.CORRECT_SCORE:
        normalized = key.replace("-", ":")
        parts = normalized.split(":")
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            return normalized
        raise ValueError(f"Unsupported pick '{pick}' for market {market.value}")
    elif market in {Market.HT_MATCH_WINNER, Market.SECOND_HALF_MATCH_WINNER}:
        mapping = {
            "1": "HOME",
            "H": "HOME",
            "HOME": "HOME",
            "X": "DRAW",
            "D": "DRAW",
            "DRAW": "DRAW",
            "2": "AWAY",
            "A": "AWAY",
            "AWAY": "AWAY",
        }
    elif market in {Market.HT_OVER_UNDER, Market.SECOND_HALF_OVER_UNDER}:
        mapping = {
            "OVER": "OVER",
            "O": "OVER",
            "UNDER": "UNDER",
            "U": "UNDER",
        }
    elif market in {
        Market.CORNERS_OVER_UNDER,
        Market.CARDS_OVER_UNDER,
        Market.TEAM_CORNERS_OVER_UNDER,
        Market.TEAM_CARDS_OVER_UNDER,
    }:
        mapping = {
            "OVER": "OVER",
            "O": "OVER",
            "UNDER": "UNDER",
            "U": "UNDER",
        }
    elif market == Market.HT_FT:
        normalized = key.replace("-", "/")
        tokens = normalized.split("/")
        valid_tokens = {"1", "X", "2", "HOME", "DRAW", "AWAY"}
        if len(tokens) == 2 and all(token in valid_tokens for token in tokens):
            return normalized
        raise ValueError(f"Unsupported pick '{pick}' for market {market.value}")
    elif market == Market.ASIAN_HANDICAP:
        mapping = {
            "1": "HOME",
            "HOME": "HOME",
            "2": "AWAY",
            "AWAY": "AWAY",
        }
    elif market == Market.ODD_EVEN:
        mapping = {
            "ODD": "ODD",
            "EVEN": "EVEN",
        }
    elif market == Market.WIN_TO_NIL:
        mapping = {
            "HOME": "HOME",
            "AWAY": "AWAY",
            "1": "HOME",
            "2": "AWAY",
        }
    else:
        mapping = {
            "YES": "YES",
            "Y": "YES",
            "GG": "YES",
            "NO": "NO",
            "N": "NO",
            "NG": "NO",
        }

    if key not in mapping:
        raise ValueError(f"Unsupported pick '{pick}' for market {market.value}")
    return mapping[key]


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
    if market == Market.OVER_UNDER and row.line is None:
        raise ValueError(f"Row for fixture {row.fixture_id} requires line for OVER_UNDER")
    if market == Market.TEAM_OVER_UNDER and row.line is None:
        raise ValueError(f"Row for fixture {row.fixture_id} requires line for TEAM_OVER_UNDER")
    if market in {
        Market.CORNERS_OVER_UNDER,
        Market.CARDS_OVER_UNDER,
        Market.TEAM_CORNERS_OVER_UNDER,
        Market.TEAM_CARDS_OVER_UNDER,
    } and row.line is None:
        raise ValueError(f"Row for fixture {row.fixture_id} requires line for {market.value}")
    if market == Market.ASIAN_HANDICAP and row.line is None:
        raise ValueError(f"Row for fixture {row.fixture_id} requires line for ASIAN_HANDICAP")
    normalized_team: Optional[str] = None
    if market == Market.TEAM_OVER_UNDER:
        normalized_team = (row.team or "").strip().upper()
        if normalized_team not in {"HOME", "AWAY"}:
            raise ValueError(f"Row for fixture {row.fixture_id} requires team=HOME or team=AWAY")
    if market in {Market.TEAM_CORNERS_OVER_UNDER, Market.TEAM_CARDS_OVER_UNDER}:
        normalized_team = (row.team or "").strip().upper()
        if normalized_team not in {"HOME", "AWAY"}:
            raise ValueError(f"Row for fixture {row.fixture_id} requires team=HOME or team=AWAY")
    return Selection(
        fixture_id=row.fixture_id,
        market=market,
        pick=normalized_pick,
        line=row.line,
        team=normalized_team,
    )


def _run_validation(base_url: str, api_key: Optional[str], selections: List[Selection]) -> dict:
    try:
        client = APISportsClient(base_url=base_url, api_key=api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return evaluate_betslip(client, selections)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected settlement error: {exc}") from exc


app = FastAPI(title="Betslip Validator API", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/markets/supported")
def supported_markets() -> dict:
    return {
        "implemented": sorted([market.value for market in IMPLEMENTED_MARKETS]),
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
        market_name = str(item.get("name") or "")
        normalized_market = _normalize_market(market_name)
        discovered.append(
            {
                "id": item.get("id"),
                "name": market_name,
                "values": item.get("values"),
                "implemented": normalized_market in IMPLEMENTED_MARKETS,
            }
        )

    implemented_count = sum(1 for item in discovered if item["implemented"])
    return {
        "total_discovered": len(discovered),
        "implemented_count": implemented_count,
        "not_implemented_count": len(discovered) - implemented_count,
        "markets": discovered,
    }


@app.post("/validate-betslip")
def validate_betslip(payload: BetslipValidationRequest) -> dict:
    selections = [
        Selection(
            fixture_id=item.fixture_id,
            market=item.market,
            pick=item.pick,
            line=item.line,
            team=item.team,
        )
        for item in payload.selections
    ]

    return _run_validation(base_url=payload.base_url, api_key=payload.api_key, selections=selections)


@app.post("/validate-betslip/table")
def validate_betslip_table(payload: TableValidationRequest) -> dict:
    base_url = payload.base_url or os.getenv("API_BASE_URL", "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="Missing base_url. Provide it in request or set API_BASE_URL.")

    try:
        selections = [_row_to_selection(row) for row in payload.rows]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _run_validation(base_url=base_url, api_key=payload.api_key, selections=selections)
