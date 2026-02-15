from __future__ import annotations

import os
from typing import Any, Dict, List

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

    # ── helpers ──────────────────────────────────────────────────────────────

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

    @staticmethod
    def is_final_status(status_short: str) -> bool:
        return status_short in FINAL_STATUSES

    # ── fixture outcome (scores + events) ────────────────────────────────────

    def get_fixture_outcome(self, fixture_id: int) -> FixtureOutcome:
        payload = self._get("fixtures", {"id": fixture_id})
        rows = payload.get("response", [])
        if not rows:
            raise ValueError(f"Fixture not found for id={fixture_id}")

        row = rows[0]
        fixture = row.get("fixture", {})
        goals = row.get("goals", {})
        score = row.get("score", {})
        teams = row.get("teams", {})
        events: List[Dict[str, Any]] = row.get("events") or []

        status_short = (fixture.get("status", {}) or {}).get("short", "")
        halftime = score.get("halftime") or {}
        fulltime = score.get("fulltime") or {}
        penalty = score.get("penalty") or {}

        fulltime_home = fulltime.get("home")
        fulltime_away = fulltime.get("away")
        home_goals = fulltime_home if fulltime_home is not None else goals.get("home")
        away_goals = fulltime_away if fulltime_away is not None else goals.get("away")

        # Determine first / last team to score from events
        home_team_id = (teams.get("home") or {}).get("id")
        first_to_score, last_to_score = self._parse_scorers(events, home_team_id, home_goals, away_goals)

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
            first_to_score=first_to_score,
            last_to_score=last_to_score,
        )

    @staticmethod
    def _parse_scorers(
        events: List[Dict[str, Any]],
        home_team_id: Any,
        home_goals: Any,
        away_goals: Any,
    ) -> tuple[str | None, str | None]:
        """Return (first_to_score, last_to_score) as 'HOME'/'AWAY'/'NONE'."""
        goal_events = []
        for ev in events:
            if (ev.get("type") or "").lower() != "goal":
                continue
            detail = (ev.get("detail") or "").lower()
            if "missed" in detail:
                continue
            elapsed = (ev.get("time") or {}).get("elapsed") or 0
            extra = (ev.get("time") or {}).get("extra") or 0
            team_id = (ev.get("team") or {}).get("id")
            side = "HOME" if team_id == home_team_id else "AWAY"
            goal_events.append((elapsed, extra, side))

        if not goal_events:
            # 0-0 or no event data
            if home_goals is not None and away_goals is not None and home_goals == 0 and away_goals == 0:
                return "NONE", "NONE"
            return None, None

        goal_events.sort(key=lambda g: (g[0], g[1]))
        return goal_events[0][2], goal_events[-1][2]

    # ── fixture statistics ───────────────────────────────────────────────────

    def get_fixture_statistics(self, fixture_id: int) -> FixtureStatistics:
        payload = self._get("fixtures/statistics", {"fixture": fixture_id})
        rows = payload.get("response", [])
        if not rows or len(rows) < 2:
            raise ValueError(f"Fixture statistics not found for id={fixture_id}")

        stats_by_team: list[dict[str, Any]] = []
        for row in rows:
            team_stats: dict[str, Any] = {}
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
            shots_home=home_stats.get("TOTAL SHOTS"),
            shots_away=away_stats.get("TOTAL SHOTS"),
            shots_on_target_home=home_stats.get("SHOTS ON GOAL"),
            shots_on_target_away=away_stats.get("SHOTS ON GOAL"),
            fouls_home=home_stats.get("FOULS"),
            fouls_away=away_stats.get("FOULS"),
            offsides_home=home_stats.get("OFFSIDES"),
            offsides_away=away_stats.get("OFFSIDES"),
        )

    # ── team search ──────────────────────────────────────────────────────────

    def search_teams(self, name: str) -> list[dict[str, Any]]:
        """Search teams by name. Returns list of {id, name, country, ...}."""
        payload = self._get("teams", {"search": name})
        results: list[dict[str, Any]] = []
        for row in payload.get("response", []):
            team = row.get("team", {})
            results.append({
                "id": team.get("id"),
                "name": team.get("name"),
                "country": team.get("country"),
                "logo": team.get("logo"),
            })
        return results

    # ── fixture search ───────────────────────────────────────────────────────

    def search_fixtures(self, team_id: int, date: str) -> list[dict[str, Any]]:
        """Search fixtures for a team on a specific date (YYYY-MM-DD).
        Auto-derives season from date (European football: Aug-Dec = year, Jan-Jul = year-1)."""
        # Derive season from date
        parts = date.split("-")
        year = int(parts[0])
        month = int(parts[1])
        season = year if month >= 7 else year - 1

        results: list[dict[str, Any]] = []
        # Try the derived season and also the alternate one
        for s in [season, season + 1 if month >= 7 else season - 1]:
            payload = self._get("fixtures", {"team": team_id, "date": date, "season": s})
            for row in payload.get("response", []):
                fixture = row.get("fixture", {})
                teams = row.get("teams", {})
                goals = row.get("goals", {})
                league = row.get("league", {})
                status = (fixture.get("status", {}) or {}).get("short", "")
                results.append({
                    "fixture_id": fixture.get("id"),
                    "date": fixture.get("date"),
                    "status": status,
                    "home_team": (teams.get("home") or {}).get("name"),
                    "home_team_id": (teams.get("home") or {}).get("id"),
                    "away_team": (teams.get("away") or {}).get("name"),
                    "away_team_id": (teams.get("away") or {}).get("id"),
                    "home_goals": goals.get("home"),
                    "away_goals": goals.get("away"),
                    "league": league.get("name"),
                    "country": league.get("country"),
                })
            if results:
                break  # found fixtures, no need to try alternate season
        return results

    def find_fixture(self, home_name: str, away_name: str, date: str) -> dict[str, Any] | None:
        """
        Find a fixture by team names and date.
        1. Try local teams DB to resolve team IDs (no API calls)
        2. Search fixtures by team_id + date
        3. Fall back to API team search if local DB miss
        """
        from teams_db import lookup_team_id

        def _normalise(s: str) -> str:
            return s.strip().lower().replace(".", "").replace("'", "")

        h_norm = _normalise(home_name)
        a_norm = _normalise(away_name)

        # 1. Try local DB lookup
        home_id = lookup_team_id(home_name)
        away_id = lookup_team_id(away_name)

        # Try with whichever team ID we found
        for team_id in [tid for tid in [home_id, away_id] if tid is not None]:
            fixtures = self.search_fixtures(team_id, date)
            for fx in fixtures:
                fx_h = _normalise(fx.get("home_team") or "")
                fx_a = _normalise(fx.get("away_team") or "")
                # Check if both teams match (either direction)
                if self._teams_match(h_norm, fx_h) and self._teams_match(a_norm, fx_a):
                    return fx
                if self._teams_match(h_norm, fx_a) and self._teams_match(a_norm, fx_h):
                    fx["_swapped"] = True
                    return fx
            # If only one fixture on that date for this team, it's likely the one
            if len(fixtures) == 1:
                return fixtures[0]

        # 2. Fall back to API team search (uses 1 extra API call)
        if home_id is None:
            api_results = self.search_teams(home_name.strip())
            for team in api_results[:3]:
                fixtures = self.search_fixtures(team["id"], date)
                for fx in fixtures:
                    fx_h = _normalise(fx.get("home_team") or "")
                    fx_a = _normalise(fx.get("away_team") or "")
                    if self._teams_match(h_norm, fx_h) and self._teams_match(a_norm, fx_a):
                        return fx
                    if self._teams_match(h_norm, fx_a) and self._teams_match(a_norm, fx_h):
                        fx["_swapped"] = True
                        return fx

        return None

    @staticmethod
    def _teams_match(input_name: str, fixture_name: str) -> bool:
        """Check if two team names likely refer to the same team."""
        if not input_name or not fixture_name:
            return False
        if input_name == fixture_name:
            return True
        if input_name in fixture_name or fixture_name in input_name:
            return True
        # Strip common decorators and try again
        from teams_db import _strip_decorators
        a = _strip_decorators(input_name)
        b = _strip_decorators(fixture_name)
        if a and b and (a in b or b in a):
            return True
        return False

    # ── odds catalog ─────────────────────────────────────────────────────────

    def get_odds_bets_catalog(self) -> list[dict[str, Any]]:
        payload = self._get("odds/bets", {})
        rows = payload.get("response", [])
        catalog: list[dict[str, Any]] = []
        for row in rows:
            catalog.append(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "values": row.get("values") or [],
                }
            )
        return catalog
