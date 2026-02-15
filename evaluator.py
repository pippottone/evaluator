from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterable, List, Optional

from api_client import APISportsClient
from models import (
    FixtureOutcome,
    FixtureStatistics,
    Market,
    Selection,
    SelectionResult,
    SelectionStatus,
)

# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _r(sel: Selection, status: SelectionStatus, reason: str) -> SelectionResult:
    """Shorthand result builder."""
    return SelectionResult(
        fixture_id=sel.fixture_id,
        market=sel.market.value,
        pick=sel.pick,
        status=status,
        reason=reason,
    )


def _result_category(home: int, away: int) -> str:
    if home > away:
        return "HOME"
    if home < away:
        return "AWAY"
    return "DRAW"


def _fulltime_score(o: FixtureOutcome) -> tuple[int, int] | None:
    if o.home_goals is None or o.away_goals is None:
        return None
    return o.home_goals, o.away_goals


def _halftime_score(o: FixtureOutcome) -> tuple[int, int] | None:
    if o.halftime_home is None or o.halftime_away is None:
        return None
    return o.halftime_home, o.halftime_away


def _second_half_score(o: FixtureOutcome) -> tuple[int, int] | None:
    ft = _fulltime_score(o)
    ht = _halftime_score(o)
    if ft is None or ht is None:
        return None
    return ft[0] - ht[0], ft[1] - ht[1]


def _period_score(o: FixtureOutcome, period: str) -> tuple[int, int] | None:
    if period == "FT":
        return _fulltime_score(o)
    if period == "HT":
        return _halftime_score(o)
    if period == "2H":
        return _second_half_score(o)
    return None


W = SelectionStatus.WON
L = SelectionStatus.LOST
P = SelectionStatus.PENDING
NS = SelectionStatus.NOT_SUPPORTED
PUSH = SelectionStatus.PUSH


# ═══════════════════════════════════════════════════════════════════════════════
#  Generic period-parametrised helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _eval_period_match_winner(sel: Selection, o: FixtureOutcome, period: str) -> SelectionResult:
    sc = _period_score(o, period)
    if sc is None:
        return _r(sel, P, f"Missing {period} score data")
    actual = _result_category(sc[0], sc[1])
    if period == "FT" and actual == "DRAW" and o.status_short == "PEN":
        if o.penalty_home is not None and o.penalty_away is not None:
            if o.penalty_home > o.penalty_away:
                actual = "HOME"
            elif o.penalty_home < o.penalty_away:
                actual = "AWAY"
    pick = sel.pick.upper()
    if pick not in {"HOME", "DRAW", "AWAY"}:
        return _r(sel, NS, f"Pick must be HOME, DRAW, or AWAY")
    label = {"FT": "Final", "HT": "Halftime", "2H": "2nd-half"}[period]
    return _r(sel, W if pick == actual else L, f"{label} score={sc[0]}:{sc[1]}")


def _eval_period_double_chance(sel: Selection, o: FixtureOutcome, period: str) -> SelectionResult:
    sc = _period_score(o, period)
    if sc is None:
        return _r(sel, P, f"Missing {period} score data")
    actual = _result_category(sc[0], sc[1])
    pick = sel.pick.upper()
    valid = {"1X": {"HOME", "DRAW"}, "X2": {"DRAW", "AWAY"}, "12": {"HOME", "AWAY"}}
    if pick not in valid:
        return _r(sel, L, f"Invalid DOUBLE_CHANCE pick '{sel.pick}'. Use 1X, X2, 12.")
    return _r(sel, W if actual in valid[pick] else L, f"{period} result: {actual}")


def _eval_period_over_under(sel: Selection, o: FixtureOutcome, period: str) -> SelectionResult:
    sc = _period_score(o, period)
    if sc is None:
        return _r(sel, P, f"Missing {period} score data")
    if sel.line is None:
        return _r(sel, NS, "Requires line")
    total = sc[0] + sc[1]
    pick = sel.pick.upper()
    if total == sel.line:
        return _r(sel, PUSH, f"{period} total={total} matched line={sel.line}")
    if pick == "OVER":
        won = total > sel.line
    elif pick == "UNDER":
        won = total < sel.line
    else:
        return _r(sel, NS, "Pick must be OVER or UNDER")
    return _r(sel, W if won else L, f"{period} total={total}, line={sel.line}")


def _eval_period_btts(sel: Selection, o: FixtureOutcome, period: str) -> SelectionResult:
    sc = _period_score(o, period)
    if sc is None:
        return _r(sel, P, f"Missing {period} score data")
    btts = sc[0] > 0 and sc[1] > 0
    pick = sel.pick.upper()
    if pick not in {"YES", "NO"}:
        return _r(sel, NS, "Pick must be YES or NO")
    won = (pick == "YES" and btts) or (pick == "NO" and not btts)
    return _r(sel, W if won else L, f"{period} goals={sc[0]}:{sc[1]}")


def _eval_period_draw_no_bet(sel: Selection, o: FixtureOutcome, period: str) -> SelectionResult:
    sc = _period_score(o, period)
    if sc is None:
        return _r(sel, P, f"Missing {period} score data")
    pick = sel.pick.upper()
    if pick not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Pick must be HOME or AWAY")
    if sc[0] == sc[1]:
        return _r(sel, PUSH, f"{period} draw {sc[0]}:{sc[1]}: stake returned")
    actual = "HOME" if sc[0] > sc[1] else "AWAY"
    return _r(sel, W if pick == actual else L, f"{period} result: {actual}")


def _eval_period_odd_even(sel: Selection, o: FixtureOutcome, period: str) -> SelectionResult:
    sc = _period_score(o, period)
    if sc is None:
        return _r(sel, P, f"Missing {period} score data")
    total = sc[0] + sc[1]
    actual = "EVEN" if total % 2 == 0 else "ODD"
    pick = sel.pick.upper()
    if pick not in {"ODD", "EVEN"}:
        return _r(sel, NS, "Pick must be ODD or EVEN")
    return _r(sel, W if pick == actual else L, f"{period} total={total} ({actual})")


def _eval_period_correct_score(sel: Selection, o: FixtureOutcome, period: str) -> SelectionResult:
    sc = _period_score(o, period)
    if sc is None:
        return _r(sel, P, f"Missing {period} score data")
    pick = sel.pick.strip().replace("-", ":")
    parts = pick.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return _r(sel, NS, "Pick must be in H:A format, e.g. 2:1")
    won = int(parts[0]) == sc[0] and int(parts[1]) == sc[1]
    return _r(sel, W if won else L, f"{period} score={sc[0]}:{sc[1]}")


def _eval_period_asian_handicap(sel: Selection, o: FixtureOutcome, period: str) -> SelectionResult:
    sc = _period_score(o, period)
    if sc is None:
        return _r(sel, P, f"Missing {period} score data")
    if sel.line is None:
        return _r(sel, NS, "Requires line")
    pick = sel.pick.upper()
    if pick not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Pick must be HOME or AWAY")
    if pick == "HOME":
        h, a = sc[0] + sel.line, float(sc[1])
    else:
        h, a = float(sc[0]), sc[1] + sel.line
    if h == a:
        return _r(sel, PUSH, f"Adjusted score tied ({h}-{a})")
    won = h > a if pick == "HOME" else a > h
    return _r(sel, W if won else L, f"Adjusted score home={h}, away={a}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Full-time evaluators (delegate to period helpers)
# ═══════════════════════════════════════════════════════════════════════════════


def _result_match_winner(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_match_winner(sel, o, "FT")


def _result_double_chance(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_double_chance(sel, o, "FT")


def _result_over_under(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_over_under(sel, o, "FT")


def _result_btts(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_btts(sel, o, "FT")


def _result_draw_no_bet(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_draw_no_bet(sel, o, "FT")


def _result_odd_even(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_odd_even(sel, o, "FT")


def _result_correct_score(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_correct_score(sel, o, "FT")


def _result_asian_handicap(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_asian_handicap(sel, o, "FT")


# ── half-time evaluators ─────────────────────────────────────────────────────

def _result_ht_match_winner(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_match_winner(sel, o, "HT")


def _result_ht_over_under(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_over_under(sel, o, "HT")


def _result_ht_btts(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_btts(sel, o, "HT")


def _result_ht_double_chance(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_double_chance(sel, o, "HT")


def _result_ht_draw_no_bet(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_draw_no_bet(sel, o, "HT")


def _result_ht_odd_even(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_odd_even(sel, o, "HT")


def _result_ht_correct_score(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_correct_score(sel, o, "HT")


def _result_ht_asian_handicap(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_asian_handicap(sel, o, "HT")


# ── second-half evaluators ───────────────────────────────────────────────────

def _result_2h_match_winner(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_match_winner(sel, o, "2H")


def _result_2h_over_under(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_over_under(sel, o, "2H")


def _result_2h_btts(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_btts(sel, o, "2H")


def _result_2h_double_chance(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_double_chance(sel, o, "2H")


def _result_2h_draw_no_bet(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_draw_no_bet(sel, o, "2H")


def _result_2h_odd_even(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_odd_even(sel, o, "2H")


def _result_2h_correct_score(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    return _eval_period_correct_score(sel, o, "2H")


# ═══════════════════════════════════════════════════════════════════════════════
#  Standalone score-based evaluators
# ═══════════════════════════════════════════════════════════════════════════════


def _result_team_over_under(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    assert o.home_goals is not None and o.away_goals is not None
    if sel.line is None:
        return _r(sel, NS, "Requires line")
    team = (sel.team or "").upper()
    if team not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Requires team=HOME or team=AWAY")
    goals = o.home_goals if team == "HOME" else o.away_goals
    pick = sel.pick.upper()
    if goals == sel.line:
        return _r(sel, PUSH, f"Team goals={goals} matched line={sel.line}")
    if pick == "OVER":
        won = goals > sel.line
    elif pick == "UNDER":
        won = goals < sel.line
    else:
        return _r(sel, NS, "Pick must be OVER or UNDER")
    return _r(sel, W if won else L, f"Team={team}, goals={goals}, line={sel.line}")


def _result_clean_sheet(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    assert o.home_goals is not None and o.away_goals is not None
    team = (sel.team or "").upper()
    if team not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Requires team=HOME or team=AWAY")
    pick = sel.pick.upper()
    if pick not in {"YES", "NO"}:
        return _r(sel, NS, "Pick must be YES or NO")
    # Home clean sheet means away scored 0 and vice-versa
    clean = o.away_goals == 0 if team == "HOME" else o.home_goals == 0
    won = (pick == "YES" and clean) or (pick == "NO" and not clean)
    return _r(sel, W if won else L, f"Score={o.home_goals}:{o.away_goals}")


def _result_win_to_nil(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    assert o.home_goals is not None and o.away_goals is not None
    pick = sel.pick.upper()
    if pick not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Pick must be HOME or AWAY")
    if pick == "HOME":
        won = o.home_goals > 0 and o.away_goals == 0
    else:
        won = o.away_goals > 0 and o.home_goals == 0
    return _r(sel, W if won else L, f"Score={o.home_goals}:{o.away_goals}")


def _result_exact_goals(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    assert o.home_goals is not None and o.away_goals is not None
    total = o.home_goals + o.away_goals
    pick = sel.pick.strip()
    if pick.endswith("+"):
        try:
            threshold = int(pick[:-1])
        except ValueError:
            return _r(sel, NS, f"Cannot parse pick '{pick}'")
        won = total >= threshold
    else:
        try:
            target = int(pick)
        except ValueError:
            return _r(sel, NS, f"Cannot parse pick '{pick}'")
        won = total == target
    return _r(sel, W if won else L, f"Total goals={total}")


def _result_team_exact_goals(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    assert o.home_goals is not None and o.away_goals is not None
    team = (sel.team or "").upper()
    if team not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Requires team=HOME or team=AWAY")
    goals = o.home_goals if team == "HOME" else o.away_goals
    pick = sel.pick.strip()
    if pick.endswith("+"):
        try:
            threshold = int(pick[:-1])
        except ValueError:
            return _r(sel, NS, f"Cannot parse pick '{pick}'")
        won = goals >= threshold
    else:
        try:
            target = int(pick)
        except ValueError:
            return _r(sel, NS, f"Cannot parse pick '{pick}'")
        won = goals == target
    return _r(sel, W if won else L, f"Team={team}, goals={goals}")


def _result_multi_goals(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    assert o.home_goals is not None and o.away_goals is not None
    total = o.home_goals + o.away_goals
    pick = sel.pick.strip()
    if pick.endswith("+"):
        try:
            low = int(pick[:-1])
        except ValueError:
            return _r(sel, NS, f"Cannot parse pick '{pick}'")
        won = total >= low
    elif "-" in pick:
        parts = pick.split("-")
        if len(parts) != 2:
            return _r(sel, NS, f"Cannot parse pick '{pick}'")
        try:
            low, high = int(parts[0]), int(parts[1])
        except ValueError:
            return _r(sel, NS, f"Cannot parse pick '{pick}'")
        won = low <= total <= high
    else:
        return _r(sel, NS, f"Cannot parse pick '{pick}'. Use range (e.g. 2-3) or threshold (e.g. 4+)")
    return _r(sel, W if won else L, f"Total goals={total}")


def _result_handicap_result(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    """European (3-way) handicap: line applied to home team, settle HOME/DRAW/AWAY."""
    assert o.home_goals is not None and o.away_goals is not None
    if sel.line is None:
        return _r(sel, NS, "Requires line")
    pick = sel.pick.upper()
    if pick not in {"HOME", "DRAW", "AWAY"}:
        return _r(sel, NS, "Pick must be HOME, DRAW, or AWAY")
    adjusted_home = o.home_goals + sel.line
    actual = _result_category(adjusted_home, o.away_goals)
    return _r(sel, W if pick == actual else L, f"Adjusted home={adjusted_home}, away={o.away_goals}")


def _result_ht_ft(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    ht = _halftime_score(o)
    ft = _fulltime_score(o)
    if ht is None or ft is None:
        return _r(sel, P, "Missing halftime/fulltime score data")
    normalized = sel.pick.strip().upper().replace("-", "/")
    parts = normalized.split("/")
    if len(parts) != 2:
        return _r(sel, NS, "HT_FT pick must be in HT/FT form, e.g. HOME/DRAW")
    label_map = {"1": "HOME", "X": "DRAW", "2": "AWAY", "HOME": "HOME", "DRAW": "DRAW", "AWAY": "AWAY"}
    if parts[0] not in label_map or parts[1] not in label_map:
        return _r(sel, NS, "HT_FT pick tokens must be HOME/DRAW/AWAY (or 1/X/2)")
    expected = f"{label_map[parts[0]]}/{label_map[parts[1]]}"
    actual = f"{_result_category(ht[0], ht[1])}/{_result_category(ft[0], ft[1])}"
    return _r(sel, W if expected == actual else L, f"Actual HT/FT={actual}")


def _result_result_btts(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    """Combined Result + BTTS. Pick format: HOME/YES, DRAW/NO, AWAY/YES, etc."""
    assert o.home_goals is not None and o.away_goals is not None
    normalized = sel.pick.strip().upper().replace("-", "/")
    parts = normalized.split("/")
    if len(parts) != 2:
        return _r(sel, NS, "Pick must be RESULT/BTTS, e.g. HOME/YES")
    result_map = {"1": "HOME", "HOME": "HOME", "X": "DRAW", "DRAW": "DRAW", "2": "AWAY", "AWAY": "AWAY"}
    btts_map = {"YES": True, "GG": True, "NO": False, "NG": False}
    if parts[0] not in result_map:
        return _r(sel, NS, f"Unknown result token '{parts[0]}'")
    if parts[1] not in btts_map:
        return _r(sel, NS, f"Unknown BTTS token '{parts[1]}'")
    actual_result = _result_category(o.home_goals, o.away_goals)
    btts_yes = o.home_goals > 0 and o.away_goals > 0
    result_ok = result_map[parts[0]] == actual_result
    btts_ok = btts_map[parts[1]] == btts_yes
    won = result_ok and btts_ok
    return _r(sel, W if won else L, f"Result={actual_result}, BTTS={'Yes' if btts_yes else 'No'}")


def _result_result_over_under(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    """Combined Result + Over/Under. Pick format: HOME/OVER, AWAY/UNDER, etc."""
    assert o.home_goals is not None and o.away_goals is not None
    if sel.line is None:
        return _r(sel, NS, "Requires line")
    normalized = sel.pick.strip().upper().replace("-", "/")
    parts = normalized.split("/")
    if len(parts) != 2:
        return _r(sel, NS, "Pick must be RESULT/OU, e.g. HOME/OVER")
    result_map = {"1": "HOME", "HOME": "HOME", "X": "DRAW", "DRAW": "DRAW", "2": "AWAY", "AWAY": "AWAY"}
    ou_map = {"OVER": "OVER", "O": "OVER", "UNDER": "UNDER", "U": "UNDER"}
    if parts[0] not in result_map or parts[1] not in ou_map:
        return _r(sel, NS, f"Cannot parse pick '{sel.pick}'")
    actual_result = _result_category(o.home_goals, o.away_goals)
    total = o.home_goals + o.away_goals
    result_ok = result_map[parts[0]] == actual_result
    if ou_map[parts[1]] == "OVER":
        ou_ok = total > sel.line
    else:
        ou_ok = total < sel.line
    won = result_ok and ou_ok
    return _r(sel, W if won else L, f"Result={actual_result}, Total={total}, line={sel.line}")


def _result_margin_of_victory(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    """Winning margin. Pick: DRAW or TEAM:N or TEAM:N+  (e.g. HOME:2, AWAY:3+)."""
    assert o.home_goals is not None and o.away_goals is not None
    diff = o.home_goals - o.away_goals
    pick = sel.pick.strip().upper()
    if pick == "DRAW":
        won = diff == 0
        return _r(sel, W if won else L, f"Score={o.home_goals}:{o.away_goals}")

    parts = pick.replace(" ", ":").split(":")
    if len(parts) != 2:
        return _r(sel, NS, "Pick must be DRAW or TEAM:N (e.g. HOME:2, AWAY:3+)")
    team_part, margin_part = parts
    if team_part not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Team token must be HOME or AWAY")
    actual_margin = diff if team_part == "HOME" else -diff
    if margin_part.endswith("+"):
        try:
            threshold = int(margin_part[:-1])
        except ValueError:
            return _r(sel, NS, f"Cannot parse margin '{margin_part}'")
        won = actual_margin >= threshold
    else:
        try:
            target = int(margin_part)
        except ValueError:
            return _r(sel, NS, f"Cannot parse margin '{margin_part}'")
        won = actual_margin == target
    return _r(sel, W if won else L, f"Score={o.home_goals}:{o.away_goals}, margin={actual_margin}")


def _result_first_team_to_score(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    pick = sel.pick.upper()
    if pick not in {"HOME", "AWAY", "NONE"}:
        return _r(sel, NS, "Pick must be HOME, AWAY, or NONE")
    if o.first_to_score is None:
        return _r(sel, P, "Missing goal-event data")
    won = pick == o.first_to_score
    return _r(sel, W if won else L, f"First scorer: {o.first_to_score}")


def _result_last_team_to_score(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    pick = sel.pick.upper()
    if pick not in {"HOME", "AWAY", "NONE"}:
        return _r(sel, NS, "Pick must be HOME, AWAY, or NONE")
    if o.last_to_score is None:
        return _r(sel, P, "Missing goal-event data")
    won = pick == o.last_to_score
    return _r(sel, W if won else L, f"Last scorer: {o.last_to_score}")


# ── cross-half markets ───────────────────────────────────────────────────────

def _result_to_score_in_both_halves(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    ht = _halftime_score(o)
    sh = _second_half_score(o)
    if ht is None or sh is None:
        return _r(sel, P, "Missing period score data")
    team = (sel.team or "").upper()
    if team not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Requires team=HOME or team=AWAY")
    pick = sel.pick.upper()
    if pick not in {"YES", "NO"}:
        return _r(sel, NS, "Pick must be YES or NO")
    if team == "HOME":
        scored_both = ht[0] > 0 and sh[0] > 0
    else:
        scored_both = ht[1] > 0 and sh[1] > 0
    won = (pick == "YES" and scored_both) or (pick == "NO" and not scored_both)
    return _r(sel, W if won else L, f"HT={ht[0]}:{ht[1]}, 2H={sh[0]}:{sh[1]}")


def _result_to_win_either_half(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    ht = _halftime_score(o)
    sh = _second_half_score(o)
    if ht is None or sh is None:
        return _r(sel, P, "Missing period score data")
    pick = sel.pick.upper()
    if pick not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Pick must be HOME or AWAY")
    if pick == "HOME":
        won = ht[0] > ht[1] or sh[0] > sh[1]
    else:
        won = ht[1] > ht[0] or sh[1] > sh[0]
    return _r(sel, W if won else L, f"HT={ht[0]}:{ht[1]}, 2H={sh[0]}:{sh[1]}")


def _result_to_win_both_halves(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    ht = _halftime_score(o)
    sh = _second_half_score(o)
    if ht is None or sh is None:
        return _r(sel, P, "Missing period score data")
    pick = sel.pick.upper()
    if pick not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Pick must be HOME or AWAY")
    if pick == "HOME":
        won = ht[0] > ht[1] and sh[0] > sh[1]
    else:
        won = ht[1] > ht[0] and sh[1] > sh[0]
    return _r(sel, W if won else L, f"HT={ht[0]}:{ht[1]}, 2H={sh[0]}:{sh[1]}")


def _result_highest_scoring_half(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    ht = _halftime_score(o)
    sh = _second_half_score(o)
    if ht is None or sh is None:
        return _r(sel, P, "Missing period score data")
    ht_total = ht[0] + ht[1]
    sh_total = sh[0] + sh[1]
    if ht_total > sh_total:
        actual = "FIRST"
    elif sh_total > ht_total:
        actual = "SECOND"
    else:
        actual = "EQUAL"
    pick = sel.pick.upper()
    if pick not in {"FIRST", "SECOND", "EQUAL", "1ST", "2ND", "TIE"}:
        return _r(sel, NS, "Pick must be FIRST, SECOND, or EQUAL")
    norm = {"1ST": "FIRST", "2ND": "SECOND", "TIE": "EQUAL"}.get(pick, pick)
    return _r(sel, W if norm == actual else L, f"HT total={ht_total}, 2H total={sh_total}")


def _result_both_halves_over_under(sel: Selection, o: FixtureOutcome) -> SelectionResult:
    ht = _halftime_score(o)
    sh = _second_half_score(o)
    if ht is None or sh is None:
        return _r(sel, P, "Missing period score data")
    if sel.line is None:
        return _r(sel, NS, "Requires line")
    pick = sel.pick.upper()
    ht_total = ht[0] + ht[1]
    sh_total = sh[0] + sh[1]
    if pick == "OVER":
        won = ht_total > sel.line and sh_total > sel.line
    elif pick == "UNDER":
        won = ht_total < sel.line and sh_total < sel.line
    else:
        return _r(sel, NS, "Pick must be OVER or UNDER")
    return _r(sel, W if won else L, f"HT total={ht_total}, 2H total={sh_total}, line={sel.line}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Statistics-based evaluators
# ═══════════════════════════════════════════════════════════════════════════════


def _settle_ou(
    sel: Selection, value: Optional[int], label: str,
) -> SelectionResult:
    """Generic over/under settlement on a stat value."""
    if value is None:
        return _r(sel, P, f"Missing statistics for {label}")
    if sel.line is None:
        return _r(sel, NS, "Requires line")
    pick = sel.pick.upper()
    if value == sel.line:
        return _r(sel, PUSH, f"{label}={value} matched line={sel.line}")
    if pick == "OVER":
        won = value > sel.line
    elif pick == "UNDER":
        won = value < sel.line
    else:
        return _r(sel, NS, "Pick must be OVER or UNDER")
    return _r(sel, W if won else L, f"{label}={value}, line={sel.line}")


def _team_value(stats: FixtureStatistics, team: str, home_attr: str, away_attr: str) -> Optional[int]:
    return getattr(stats, home_attr) if team == "HOME" else getattr(stats, away_attr)


def _total_value(stats: FixtureStatistics, home_attr: str, away_attr: str) -> Optional[int]:
    h = getattr(stats, home_attr)
    a = getattr(stats, away_attr)
    if h is None or a is None:
        return None
    return h + a


def _result_corners_over_under(sel: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return _r(sel, P, "Missing fixture statistics")
    return _settle_ou(sel, _total_value(stats, "corners_home", "corners_away"), "Total corners")


def _result_team_corners_over_under(sel: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return _r(sel, P, "Missing fixture statistics")
    team = (sel.team or "").upper()
    if team not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Requires team=HOME or team=AWAY")
    return _settle_ou(sel, _team_value(stats, team, "corners_home", "corners_away"), f"{team} corners")


def _result_cards_over_under(sel: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return _r(sel, P, "Missing fixture statistics")
    vals = [stats.yellow_home, stats.yellow_away, stats.red_home, stats.red_away]
    total = sum(v or 0 for v in vals) if all(v is not None for v in vals) else None
    return _settle_ou(sel, total, "Total cards")


def _result_team_cards_over_under(sel: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return _r(sel, P, "Missing fixture statistics")
    team = (sel.team or "").upper()
    if team not in {"HOME", "AWAY"}:
        return _r(sel, NS, "Requires team=HOME or team=AWAY")
    yellow = stats.yellow_home if team == "HOME" else stats.yellow_away
    red = stats.red_home if team == "HOME" else stats.red_away
    value = None if yellow is None or red is None else yellow + red
    return _settle_ou(sel, value, f"{team} cards")


def _result_shots_over_under(sel: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return _r(sel, P, "Missing fixture statistics")
    return _settle_ou(sel, _total_value(stats, "shots_home", "shots_away"), "Total shots")


def _result_shots_on_target_over_under(sel: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return _r(sel, P, "Missing fixture statistics")
    return _settle_ou(sel, _total_value(stats, "shots_on_target_home", "shots_on_target_away"), "Shots on target")


def _result_fouls_over_under(sel: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return _r(sel, P, "Missing fixture statistics")
    return _settle_ou(sel, _total_value(stats, "fouls_home", "fouls_away"), "Total fouls")


def _result_offsides_over_under(sel: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return _r(sel, P, "Missing fixture statistics")
    return _settle_ou(sel, _total_value(stats, "offsides_home", "offsides_away"), "Total offsides")


# ═══════════════════════════════════════════════════════════════════════════════
#  Registry
# ═══════════════════════════════════════════════════════════════════════════════

MARKET_EVALUATORS: dict[Market, Callable[[Selection, FixtureOutcome], SelectionResult]] = {
    # FT core
    Market.MATCH_WINNER: _result_match_winner,
    Market.DOUBLE_CHANCE: _result_double_chance,
    Market.DRAW_NO_BET: _result_draw_no_bet,
    Market.OVER_UNDER: _result_over_under,
    Market.BTTS: _result_btts,
    Market.ODD_EVEN: _result_odd_even,
    Market.CORRECT_SCORE: _result_correct_score,
    Market.ASIAN_HANDICAP: _result_asian_handicap,
    Market.TEAM_OVER_UNDER: _result_team_over_under,
    Market.EXACT_GOALS: _result_exact_goals,
    Market.TEAM_EXACT_GOALS: _result_team_exact_goals,
    Market.MULTI_GOALS: _result_multi_goals,
    Market.HANDICAP_RESULT: _result_handicap_result,
    Market.CLEAN_SHEET: _result_clean_sheet,
    Market.WIN_TO_NIL: _result_win_to_nil,
    Market.FIRST_TEAM_TO_SCORE: _result_first_team_to_score,
    Market.LAST_TEAM_TO_SCORE: _result_last_team_to_score,
    Market.RESULT_BTTS: _result_result_btts,
    Market.RESULT_OVER_UNDER: _result_result_over_under,
    Market.MARGIN_OF_VICTORY: _result_margin_of_victory,
    # HT
    Market.HT_MATCH_WINNER: _result_ht_match_winner,
    Market.HT_OVER_UNDER: _result_ht_over_under,
    Market.HT_BTTS: _result_ht_btts,
    Market.HT_DOUBLE_CHANCE: _result_ht_double_chance,
    Market.HT_DRAW_NO_BET: _result_ht_draw_no_bet,
    Market.HT_ODD_EVEN: _result_ht_odd_even,
    Market.HT_CORRECT_SCORE: _result_ht_correct_score,
    Market.HT_ASIAN_HANDICAP: _result_ht_asian_handicap,
    # 2H
    Market.SECOND_HALF_MATCH_WINNER: _result_2h_match_winner,
    Market.SECOND_HALF_OVER_UNDER: _result_2h_over_under,
    Market.SECOND_HALF_BTTS: _result_2h_btts,
    Market.SECOND_HALF_DOUBLE_CHANCE: _result_2h_double_chance,
    Market.SECOND_HALF_DRAW_NO_BET: _result_2h_draw_no_bet,
    Market.SECOND_HALF_ODD_EVEN: _result_2h_odd_even,
    Market.SECOND_HALF_CORRECT_SCORE: _result_2h_correct_score,
    # HT/FT & cross-half
    Market.HT_FT: _result_ht_ft,
    Market.TO_SCORE_IN_BOTH_HALVES: _result_to_score_in_both_halves,
    Market.TO_WIN_EITHER_HALF: _result_to_win_either_half,
    Market.TO_WIN_BOTH_HALVES: _result_to_win_both_halves,
    Market.HIGHEST_SCORING_HALF: _result_highest_scoring_half,
    Market.BOTH_HALVES_OVER_UNDER: _result_both_halves_over_under,
}


STATS_MARKET_EVALUATORS: dict[Market, Callable[[Selection, Optional[FixtureStatistics]], SelectionResult]] = {
    Market.CORNERS_OVER_UNDER: _result_corners_over_under,
    Market.TEAM_CORNERS_OVER_UNDER: _result_team_corners_over_under,
    Market.CARDS_OVER_UNDER: _result_cards_over_under,
    Market.TEAM_CARDS_OVER_UNDER: _result_team_cards_over_under,
    Market.SHOTS_OVER_UNDER: _result_shots_over_under,
    Market.SHOTS_ON_TARGET_OVER_UNDER: _result_shots_on_target_over_under,
    Market.FOULS_OVER_UNDER: _result_fouls_over_under,
    Market.OFFSIDES_OVER_UNDER: _result_offsides_over_under,
}


STATS_MARKETS = set(STATS_MARKET_EVALUATORS.keys())


# ═══════════════════════════════════════════════════════════════════════════════
#  Orchestration
# ═══════════════════════════════════════════════════════════════════════════════


def evaluate_selection(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    if selection.market == Market.UNMAPPED:
        name = selection.raw_market or selection.market.value
        return _r(selection, NS, f"Market '{name}' is recognized but not yet implemented")
    if outcome.home_goals is None or outcome.away_goals is None:
        return _r(selection, P, f"Missing goals data (status={outcome.status_short})")
    evaluator = MARKET_EVALUATORS.get(selection.market)
    if evaluator is not None:
        return evaluator(selection, outcome)
    return _r(selection, NS, f"Unsupported market {selection.market.value}")


def evaluate_stats_selection(selection: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if selection.market == Market.UNMAPPED:
        name = selection.raw_market or selection.market.value
        return _r(selection, NS, f"Statistics market '{name}' is not yet implemented")
    evaluator = STATS_MARKET_EVALUATORS.get(selection.market)
    if evaluator is not None:
        return evaluator(selection, stats)
    return _r(selection, NS, f"Unsupported statistics market {selection.market.value}")


def _aggregate_slip_status(results: List[SelectionResult]) -> SelectionStatus:
    if not results:
        return SelectionStatus.PENDING
    statuses = [r.status for r in results]
    if SelectionStatus.LOST in statuses:
        return SelectionStatus.LOST
    if SelectionStatus.PENDING in statuses or SelectionStatus.NOT_SUPPORTED in statuses:
        return SelectionStatus.PENDING
    if all(s == SelectionStatus.WON for s in statuses):
        return SelectionStatus.WON
    non_loss = {W, PUSH, SelectionStatus.VOID, SelectionStatus.REFUND, SelectionStatus.CANCELLED}
    if all(s in non_loss for s in statuses):
        return W if W in statuses else SelectionStatus.REFUND
    return SelectionStatus.PENDING


def evaluate_betslip(client: APISportsClient, selections: Iterable[Selection]) -> dict:
    results: List[SelectionResult] = []

    for sel in selections:
        if sel.market == Market.UNMAPPED:
            name = sel.raw_market or sel.market.value
            results.append(SelectionResult(
                fixture_id=sel.fixture_id, market=name, pick=sel.pick,
                status=NS, reason=f"Market '{name}' is not yet implemented",
            ))
            continue

        try:
            outcome = client.get_fixture_outcome(sel.fixture_id)
        except Exception as exc:
            results.append(_r(sel, P, f"Could not fetch fixture outcome: {exc}"))
            continue

        if not client.is_final_status(outcome.status_short):
            results.append(_r(sel, P, f"Fixture not finalized yet (status={outcome.status_short})"))
            continue

        if sel.market in STATS_MARKETS:
            try:
                stats = client.get_fixture_statistics(sel.fixture_id)
            except Exception as exc:
                results.append(_r(sel, P, f"Could not fetch fixture statistics: {exc}"))
                continue
            results.append(evaluate_stats_selection(sel, stats))
            continue

        results.append(evaluate_selection(sel, outcome))

    return {
        "status": _aggregate_slip_status(results).value,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "results": [
            {"fixture_id": r.fixture_id, "market": r.market, "pick": r.pick,
             "status": r.status.value, "reason": r.reason}
            for r in results
        ],
    }
