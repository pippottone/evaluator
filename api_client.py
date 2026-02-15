from __future__ import annotations

import os
from typing import Any, Dict

import requests

from models import FixtureOutcome, FixtureStatistics


FINAL_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}


class APISportsClient:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("API_SPORTS_KEY")
        if not self.api_key:
            raise ValueError("Missing API key. Set API_SPORTS_KEY or pass api_key explicitly.")
        self.timeout = timeout

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = requests.get(
            url,
            params=params,
            headers={"x-apisports-key": self.api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if "response" not in payload:
            raise ValueError(f"Unexpected API response shape from {url}")
        return payload

    def get_fixture_outcome(self, fixture_id: int) -> FixtureOutcome:
        payload = self._get("fixtures", {"id": fixture_id})
        rows = payload.get("response", [])
        if not rows:
            raise ValueError(f"Fixture not found for id={fixture_id}")

        row = rows[0]
        fixture = row.get("fixture", {})
        goals = row.get("goals", {})
        score = row.get("score", {})

        status_short = (fixture.get("status", {}) or {}).get("short", "")
        halftime = score.get("halftime") or {}
        fulltime = score.get("fulltime") or {}
        penalty = score.get("penalty") or {}

        fulltime_home = fulltime.get("home")
        fulltime_away = fulltime.get("away")
        home_goals = fulltime_home if fulltime_home is not None else goals.get("home")
        away_goals = fulltime_away if fulltime_away is not None else goals.get("away")

        return FixtureOutcome(
            fixture_id=fixture_id,
            status_short=status_short,
            home_goals=home_goals,
            away_goals=away_goals,
            halftime_home=halftime.get("home"),
            halftime_away=halftime.get("away"),
            fulltime_home=fulltime_home,
            fulltime_away=fulltime_away,
            penalty_home=penalty.get("home"),
            penalty_away=penalty.get("away"),
        )

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "")
            if cleaned.isdigit():
                return int(cleaned)
        return None

    def get_fixture_statistics(self, fixture_id: int) -> FixtureStatistics:
        payload = self._get("fixtures/statistics", {"fixture": fixture_id})
        rows = payload.get("response", [])
        if not rows or len(rows) < 2:
            raise ValueError(f"Fixture statistics not found for id={fixture_id}")

        stats_by_team: list[dict[str, Any]] = []
        for row in rows:
            team_stats = {}
            for stat in row.get("statistics", []):
                key = (stat.get("type") or "").strip().upper()
                team_stats[key] = self._to_int(stat.get("value"))
            stats_by_team.append(team_stats)

        home_stats = stats_by_team[0]
        away_stats = stats_by_team[1]
        return FixtureStatistics(
            fixture_id=fixture_id,
            corners_home=home_stats.get("CORNER KICKS"),
            corners_away=away_stats.get("CORNER KICKS"),
            yellow_home=home_stats.get("YELLOW CARDS"),
            yellow_away=away_stats.get("YELLOW CARDS"),
            red_home=home_stats.get("RED CARDS"),
            red_away=away_stats.get("RED CARDS"),
        )

    @staticmethod
    def is_final_status(status_short: str) -> bool:
        return status_short in FINAL_STATUSES
