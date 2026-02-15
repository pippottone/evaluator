from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterable, List, Optional

from api_client import APISportsClient
from models import FixtureOutcome, FixtureStatistics, Market, Selection, SelectionResult, SelectionStatus


def _result_category(home: int, away: int) -> str:
    if home > away:
        return "HOME"
    if home < away:
        return "AWAY"
    return "DRAW"


def _fulltime_score(outcome: FixtureOutcome) -> tuple[int, int] | None:
    if outcome.home_goals is None or outcome.away_goals is None:
        return None
    return outcome.home_goals, outcome.away_goals


def _halftime_score(outcome: FixtureOutcome) -> tuple[int, int] | None:
    if outcome.halftime_home is None or outcome.halftime_away is None:
        return None
    return outcome.halftime_home, outcome.halftime_away


def _second_half_score(outcome: FixtureOutcome) -> tuple[int, int] | None:
    ft = _fulltime_score(outcome)
    ht = _halftime_score(outcome)
    if ft is None or ht is None:
        return None
    return ft[0] - ht[0], ft[1] - ht[1]


def _result_match_winner(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    actual = _result_category(outcome.home_goals, outcome.away_goals)

    if actual == "DRAW" and outcome.status_short == "PEN":
        if outcome.penalty_home is not None and outcome.penalty_away is not None:
            if outcome.penalty_home > outcome.penalty_away:
                actual = "HOME"
            elif outcome.penalty_home < outcome.penalty_away:
                actual = "AWAY"

    if actual == "HOME":
        score_msg = f"Home team won {outcome.home_goals}-{outcome.away_goals}"
    elif actual == "AWAY":
        score_msg = f"Away team won {outcome.home_goals}-{outcome.away_goals}"
    else:
        score_msg = f"Match ended draw {outcome.home_goals}-{outcome.away_goals}"

    status = SelectionStatus.WON if selection.pick.upper() == actual else SelectionStatus.LOST
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=status,
        reason=score_msg,
    )


def _result_double_chance(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    actual = _result_category(outcome.home_goals, outcome.away_goals)
    if actual == "DRAW" and outcome.status_short == "PEN":
        if outcome.penalty_home is not None and outcome.penalty_away is not None:
            if outcome.penalty_home > outcome.penalty_away:
                actual = "HOME"
            elif outcome.penalty_home < outcome.penalty_away:
                actual = "AWAY"

    pick = selection.pick.upper()
    valid = {
        "1X": {"HOME", "DRAW"},
        "X2": {"DRAW", "AWAY"},
        "12": {"HOME", "AWAY"},
    }
    if pick not in valid:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.LOST,
            reason=f"Invalid DOUBLE_CHANCE pick '{selection.pick}'. Use one of 1X, X2, 12.",
        )

    status = SelectionStatus.WON if actual in valid[pick] else SelectionStatus.LOST
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=status,
        reason=f"Final result category: {actual}",
    )


def _result_over_under(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    if selection.line is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.LOST,
            reason="OVER_UNDER requires 'line' (e.g. 2.5)",
        )

    total_goals = outcome.home_goals + outcome.away_goals
    pick = selection.pick.upper()

    if pick == "OVER":
        won = total_goals > selection.line
    elif pick == "UNDER":
        won = total_goals < selection.line
    else:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.LOST,
            reason="OVER_UNDER pick must be OVER or UNDER",
        )

    status = SelectionStatus.WON if won else SelectionStatus.LOST
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=status,
        reason=f"Total goals={total_goals}, line={selection.line}",
    )


def _result_btts(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    btts_yes = outcome.home_goals > 0 and outcome.away_goals > 0
    pick = selection.pick.upper()

    if pick not in {"YES", "NO"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.LOST,
            reason="BTTS pick must be YES or NO",
        )

    won = (pick == "YES" and btts_yes) or (pick == "NO" and not btts_yes)
    status = SelectionStatus.WON if won else SelectionStatus.LOST
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=status,
        reason=f"Goals home={outcome.home_goals}, away={outcome.away_goals}",
    )


def _result_draw_no_bet(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    pick = selection.pick.upper()
    if pick not in {"HOME", "AWAY"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="DRAW_NO_BET pick must be HOME or AWAY",
        )

    if outcome.home_goals == outcome.away_goals and not (
        outcome.status_short == "PEN"
        and outcome.penalty_home is not None
        and outcome.penalty_away is not None
        and outcome.penalty_home != outcome.penalty_away
    ):
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PUSH,
            reason=f"Draw result {outcome.home_goals}-{outcome.away_goals}: stake returned",
        )

    if outcome.home_goals > outcome.away_goals:
        actual = "HOME"
    elif outcome.home_goals < outcome.away_goals:
        actual = "AWAY"
    else:
        actual = "HOME" if (outcome.penalty_home or 0) > (outcome.penalty_away or 0) else "AWAY"
    status = SelectionStatus.WON if pick == actual else SelectionStatus.LOST
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=status,
        reason=f"Final result category: {actual}",
    )


def _result_team_over_under(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    if selection.line is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="TEAM_OVER_UNDER requires line",
        )

    team = (selection.team or "").strip().upper()
    if team not in {"HOME", "AWAY"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="TEAM_OVER_UNDER requires team=HOME or team=AWAY",
        )

    team_goals = outcome.home_goals if team == "HOME" else outcome.away_goals
    pick = selection.pick.upper()
    if pick == "OVER":
        won = team_goals > selection.line
    elif pick == "UNDER":
        won = team_goals < selection.line
    else:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="TEAM_OVER_UNDER pick must be OVER or UNDER",
        )

    if team_goals == selection.line:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PUSH,
            reason=f"Team goals={team_goals} matched line={selection.line}: stake returned",
        )

    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if won else SelectionStatus.LOST,
        reason=f"Team={team}, goals={team_goals}, line={selection.line}",
    )


def _result_correct_score(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    pick = selection.pick.strip().replace("-", ":")
    parts = pick.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="CORRECT_SCORE pick must be in H:A format, e.g. 2:1",
        )

    expected_home = int(parts[0])
    expected_away = int(parts[1])
    won = expected_home == outcome.home_goals and expected_away == outcome.away_goals
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if won else SelectionStatus.LOST,
        reason=f"Final score={outcome.home_goals}:{outcome.away_goals}",
    )


def _result_ht_match_winner(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    ht = _halftime_score(outcome)
    if ht is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason="Missing halftime score data",
        )
    actual = _result_category(ht[0], ht[1])
    pick = selection.pick.upper()
    if pick not in {"HOME", "DRAW", "AWAY"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="HT_MATCH_WINNER pick must be HOME, DRAW, or AWAY",
        )
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if pick == actual else SelectionStatus.LOST,
        reason=f"Halftime score={ht[0]}:{ht[1]}",
    )


def _result_second_half_match_winner(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    second_half = _second_half_score(outcome)
    if second_half is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason="Missing halftime/fulltime score data for 2H market",
        )
    actual = _result_category(second_half[0], second_half[1])
    pick = selection.pick.upper()
    if pick not in {"HOME", "DRAW", "AWAY"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="SECOND_HALF_MATCH_WINNER pick must be HOME, DRAW, or AWAY",
        )
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if pick == actual else SelectionStatus.LOST,
        reason=f"Second-half goals={second_half[0]}:{second_half[1]}",
    )


def _result_ht_over_under(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    ht = _halftime_score(outcome)
    if ht is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason="Missing halftime score data",
        )
    if selection.line is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="HT_OVER_UNDER requires line",
        )
    total = ht[0] + ht[1]
    pick = selection.pick.upper()
    if total == selection.line:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PUSH,
            reason=f"HT total goals={total} matched line={selection.line}",
        )
    if pick == "OVER":
        won = total > selection.line
    elif pick == "UNDER":
        won = total < selection.line
    else:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="HT_OVER_UNDER pick must be OVER or UNDER",
        )
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if won else SelectionStatus.LOST,
        reason=f"HT total goals={total}, line={selection.line}",
    )


def _result_second_half_over_under(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    second_half = _second_half_score(outcome)
    if second_half is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason="Missing halftime/fulltime score data for 2H market",
        )
    if selection.line is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="SECOND_HALF_OVER_UNDER requires line",
        )
    total = second_half[0] + second_half[1]
    pick = selection.pick.upper()
    if total == selection.line:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PUSH,
            reason=f"2H total goals={total} matched line={selection.line}",
        )
    if pick == "OVER":
        won = total > selection.line
    elif pick == "UNDER":
        won = total < selection.line
    else:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="SECOND_HALF_OVER_UNDER pick must be OVER or UNDER",
        )
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if won else SelectionStatus.LOST,
        reason=f"2H total goals={total}, line={selection.line}",
    )


def _result_ht_ft(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    ht = _halftime_score(outcome)
    ft = _fulltime_score(outcome)
    if ht is None or ft is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason="Missing halftime/fulltime score data",
        )

    normalized = selection.pick.strip().upper().replace("-", "/")
    parts = normalized.split("/")
    if len(parts) != 2:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="HT_FT pick must be in HT/FT form, e.g. HOME/DRAW",
        )

    label_map = {
        "1": "HOME",
        "X": "DRAW",
        "2": "AWAY",
        "HOME": "HOME",
        "DRAW": "DRAW",
        "AWAY": "AWAY",
    }
    if parts[0] not in label_map or parts[1] not in label_map:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="HT_FT pick tokens must be HOME/DRAW/AWAY (or 1/X/2)",
        )

    expected = f"{label_map[parts[0]]}/{label_map[parts[1]]}"
    actual = f"{_result_category(ht[0], ht[1])}/{_result_category(ft[0], ft[1])}"
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if expected == actual else SelectionStatus.LOST,
        reason=f"Actual HT/FT={actual}",
    )


def _result_asian_handicap(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    if selection.line is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="ASIAN_HANDICAP requires line",
        )

    pick = selection.pick.upper()
    if pick not in {"HOME", "AWAY"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="ASIAN_HANDICAP pick must be HOME or AWAY",
        )

    home_adjusted = outcome.home_goals + selection.line
    away_adjusted = outcome.away_goals
    if pick == "AWAY":
        home_adjusted = outcome.home_goals
        away_adjusted = outcome.away_goals + selection.line

    if home_adjusted == away_adjusted:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PUSH,
            reason=f"Adjusted score tied ({home_adjusted}-{away_adjusted})",
        )

    won = home_adjusted > away_adjusted if pick == "HOME" else away_adjusted > home_adjusted
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if won else SelectionStatus.LOST,
        reason=f"Adjusted score home={home_adjusted}, away={away_adjusted}",
    )


def _result_odd_even(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    total = outcome.home_goals + outcome.away_goals
    actual = "EVEN" if total % 2 == 0 else "ODD"
    pick = selection.pick.upper()
    if pick not in {"ODD", "EVEN"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="ODD_EVEN pick must be ODD or EVEN",
        )
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if pick == actual else SelectionStatus.LOST,
        reason=f"Total goals={total} ({actual})",
    )


def _result_win_to_nil(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    assert outcome.home_goals is not None and outcome.away_goals is not None
    pick = selection.pick.upper()
    if pick not in {"HOME", "AWAY"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="WIN_TO_NIL pick must be HOME or AWAY",
        )

    home_win_to_nil = outcome.home_goals > outcome.away_goals and outcome.away_goals == 0
    away_win_to_nil = outcome.away_goals > outcome.home_goals and outcome.home_goals == 0
    won = home_win_to_nil if pick == "HOME" else away_win_to_nil
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if won else SelectionStatus.LOST,
        reason=f"Final score={outcome.home_goals}:{outcome.away_goals}",
    )


def _settle_over_under_value(
    selection: Selection,
    value: Optional[int],
    label: str,
    requires_line_reason: str,
    invalid_pick_reason: str,
) -> SelectionResult:
    if value is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason=f"Missing statistics data for {label}",
        )
    if selection.line is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason=requires_line_reason,
        )

    pick = selection.pick.upper()
    if value == selection.line:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PUSH,
            reason=f"{label}={value} matched line={selection.line}",
        )
    if pick == "OVER":
        won = value > selection.line
    elif pick == "UNDER":
        won = value < selection.line
    else:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason=invalid_pick_reason,
        )

    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.WON if won else SelectionStatus.LOST,
        reason=f"{label}={value}, line={selection.line}",
    )


def _result_corners_over_under(selection: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason="Missing fixture statistics",
        )
    total = None
    if stats.corners_home is not None and stats.corners_away is not None:
        total = stats.corners_home + stats.corners_away
    return _settle_over_under_value(
        selection,
        total,
        "Total corners",
        "CORNERS_OVER_UNDER requires line",
        "CORNERS_OVER_UNDER pick must be OVER or UNDER",
    )


def _result_team_corners_over_under(selection: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason="Missing fixture statistics",
        )
    team = (selection.team or "").upper().strip()
    if team not in {"HOME", "AWAY"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="TEAM_CORNERS_OVER_UNDER requires team=HOME or team=AWAY",
        )
    value = stats.corners_home if team == "HOME" else stats.corners_away
    return _settle_over_under_value(
        selection,
        value,
        f"{team} corners",
        "TEAM_CORNERS_OVER_UNDER requires line",
        "TEAM_CORNERS_OVER_UNDER pick must be OVER or UNDER",
    )


def _result_cards_over_under(selection: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason="Missing fixture statistics",
        )
    if any(value is None for value in (stats.yellow_home, stats.yellow_away, stats.red_home, stats.red_away)):
        total_cards = None
    else:
        total_cards = (stats.yellow_home or 0) + (stats.yellow_away or 0) + (stats.red_home or 0) + (stats.red_away or 0)
    return _settle_over_under_value(
        selection,
        total_cards,
        "Total cards (yellow+red)",
        "CARDS_OVER_UNDER requires line",
        "CARDS_OVER_UNDER pick must be OVER or UNDER",
    )


def _result_team_cards_over_under(selection: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if stats is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason="Missing fixture statistics",
        )
    team = (selection.team or "").upper().strip()
    if team not in {"HOME", "AWAY"}:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason="TEAM_CARDS_OVER_UNDER requires team=HOME or team=AWAY",
        )
    yellow = stats.yellow_home if team == "HOME" else stats.yellow_away
    red = stats.red_home if team == "HOME" else stats.red_away
    value = None if yellow is None or red is None else yellow + red
    return _settle_over_under_value(
        selection,
        value,
        f"{team} cards (yellow+red)",
        "TEAM_CARDS_OVER_UNDER requires line",
        "TEAM_CARDS_OVER_UNDER pick must be OVER or UNDER",
    )


MARKET_EVALUATORS: dict[Market, Callable[[Selection, FixtureOutcome], SelectionResult]] = {
    Market.MATCH_WINNER: _result_match_winner,
    Market.DOUBLE_CHANCE: _result_double_chance,
    Market.OVER_UNDER: _result_over_under,
    Market.BTTS: _result_btts,
    Market.DRAW_NO_BET: _result_draw_no_bet,
    Market.TEAM_OVER_UNDER: _result_team_over_under,
    Market.CORRECT_SCORE: _result_correct_score,
    Market.HT_MATCH_WINNER: _result_ht_match_winner,
    Market.SECOND_HALF_MATCH_WINNER: _result_second_half_match_winner,
    Market.HT_OVER_UNDER: _result_ht_over_under,
    Market.SECOND_HALF_OVER_UNDER: _result_second_half_over_under,
    Market.HT_FT: _result_ht_ft,
    Market.ASIAN_HANDICAP: _result_asian_handicap,
    Market.ODD_EVEN: _result_odd_even,
    Market.WIN_TO_NIL: _result_win_to_nil,
}


STATS_MARKETS = {
    Market.CORNERS_OVER_UNDER,
    Market.TEAM_CORNERS_OVER_UNDER,
    Market.CARDS_OVER_UNDER,
    Market.TEAM_CARDS_OVER_UNDER,
}


def evaluate_selection(selection: Selection, outcome: FixtureOutcome) -> SelectionResult:
    if selection.market == Market.UNMAPPED:
        market_name = selection.raw_market or selection.market.value
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=market_name,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason=f"Market '{market_name}' is recognized as input but not yet implemented for settlement",
        )

    if outcome.home_goals is None or outcome.away_goals is None:
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=selection.market.value,
            pick=selection.pick,
            status=SelectionStatus.PENDING,
            reason=f"Missing goals data (status={outcome.status_short})",
        )

    evaluator = MARKET_EVALUATORS.get(selection.market)
    if evaluator is not None:
        return evaluator(selection, outcome)

    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.NOT_SUPPORTED,
        reason=f"Unsupported market {selection.market.value}",
    )


def evaluate_stats_selection(selection: Selection, stats: Optional[FixtureStatistics]) -> SelectionResult:
    if selection.market == Market.UNMAPPED:
        market_name = selection.raw_market or selection.market.value
        return SelectionResult(
            fixture_id=selection.fixture_id,
            market=market_name,
            pick=selection.pick,
            status=SelectionStatus.NOT_SUPPORTED,
            reason=f"Statistics market '{market_name}' is not yet implemented",
        )
    if selection.market == Market.CORNERS_OVER_UNDER:
        return _result_corners_over_under(selection, stats)
    if selection.market == Market.TEAM_CORNERS_OVER_UNDER:
        return _result_team_corners_over_under(selection, stats)
    if selection.market == Market.CARDS_OVER_UNDER:
        return _result_cards_over_under(selection, stats)
    if selection.market == Market.TEAM_CARDS_OVER_UNDER:
        return _result_team_cards_over_under(selection, stats)
    return SelectionResult(
        fixture_id=selection.fixture_id,
        market=selection.market.value,
        pick=selection.pick,
        status=SelectionStatus.NOT_SUPPORTED,
        reason=f"Unsupported statistics market {selection.market.value}",
    )


def _aggregate_slip_status(results: List[SelectionResult]) -> SelectionStatus:
    if not results:
        return SelectionStatus.PENDING

    statuses = [item.status for item in results]
    if SelectionStatus.LOST in statuses:
        return SelectionStatus.LOST
    if SelectionStatus.PENDING in statuses or SelectionStatus.NOT_SUPPORTED in statuses:
        return SelectionStatus.PENDING
    if all(status == SelectionStatus.WON for status in statuses):
        return SelectionStatus.WON
    non_loss_non_pending = {
        SelectionStatus.WON,
        SelectionStatus.PUSH,
        SelectionStatus.VOID,
        SelectionStatus.REFUND,
        SelectionStatus.CANCELLED,
    }
    if all(status in non_loss_non_pending for status in statuses):
        if SelectionStatus.WON in statuses:
            return SelectionStatus.WON
        return SelectionStatus.REFUND
    return SelectionStatus.PENDING


def evaluate_betslip(client: APISportsClient, selections: Iterable[Selection]) -> dict:
    results: List[SelectionResult] = []

    for selection in selections:
        if selection.market == Market.UNMAPPED:
            market_name = selection.raw_market or selection.market.value
            results.append(
                SelectionResult(
                    fixture_id=selection.fixture_id,
                    market=market_name,
                    pick=selection.pick,
                    status=SelectionStatus.NOT_SUPPORTED,
                    reason=f"Market '{market_name}' is not yet implemented",
                )
            )
            continue

        try:
            outcome = client.get_fixture_outcome(selection.fixture_id)
        except Exception as exc:
            results.append(
                SelectionResult(
                    fixture_id=selection.fixture_id,
                    market=selection.market.value,
                    pick=selection.pick,
                    status=SelectionStatus.PENDING,
                    reason=f"Could not fetch fixture outcome: {exc}",
                )
            )
            continue

        if not client.is_final_status(outcome.status_short):
            results.append(
                SelectionResult(
                    fixture_id=selection.fixture_id,
                    market=selection.market.value,
                    pick=selection.pick,
                    status=SelectionStatus.PENDING,
                    reason=f"Fixture not finalized yet (status={outcome.status_short})",
                )
            )
            continue

        if selection.market in STATS_MARKETS:
            try:
                stats = client.get_fixture_statistics(selection.fixture_id)
            except Exception as exc:
                results.append(
                    SelectionResult(
                        fixture_id=selection.fixture_id,
                        market=selection.market.value,
                        pick=selection.pick,
                        status=SelectionStatus.PENDING,
                        reason=f"Could not fetch fixture statistics: {exc}",
                    )
                )
                continue
            results.append(evaluate_stats_selection(selection, stats))
            continue

        results.append(evaluate_selection(selection, outcome))

    slip_status = _aggregate_slip_status(results)

    return {
        "status": slip_status.value,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "results": [
            {
                "fixture_id": item.fixture_id,
                "market": item.market,
                "pick": item.pick,
                "status": item.status.value,
                "reason": item.reason,
            }
            for item in results
        ],
    }
