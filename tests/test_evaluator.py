from __future__ import annotations
import unittest
from evaluator import evaluate_betslip
from models import FixtureOutcome, FixtureStatistics, Market, Selection


class StubClient:
    def __init__(self, outcomes: dict[int, FixtureOutcome],
                 statistics: dict[int, FixtureStatistics] | None = None) -> None:
        self.outcomes = outcomes
        self.statistics = statistics or {}

    def get_fixture_outcome(self, fixture_id: int) -> FixtureOutcome:
        return self.outcomes[fixture_id]

    def get_fixture_statistics(self, fixture_id: int) -> FixtureStatistics:
        return self.statistics[fixture_id]

    @staticmethod
    def is_final_status(status_short: str) -> bool:
        return status_short in {"FT", "AET", "PEN", "AWD", "WO"}


def _result(client, selections):
    return evaluate_betslip(client, selections)


def _status(client, selections, index=0):
    return _result(client, selections)["results"][index]["status"]


# ── fixture factories ────────────────────────────────────────────────────────

FT = lambda hg, ag, **kw: FixtureOutcome(fixture_id=1, status_short="FT",
                                          home_goals=hg, away_goals=ag, **kw)
STATS = lambda **kw: FixtureStatistics(fixture_id=1, **kw)


class TestCoreMarkets(unittest.TestCase):
    """Tests for the original 19 markets plus new ones."""

    def test_match_winner_won(self):
        c = StubClient({1: FT(2, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.MATCH_WINNER, "HOME")]), "won")

    def test_match_winner_lost(self):
        c = StubClient({1: FT(0, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.MATCH_WINNER, "HOME")]), "lost")

    def test_double_chance(self):
        c = StubClient({1: FT(1, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.DOUBLE_CHANCE, "1X")]), "won")

    def test_over_under_won(self):
        c = StubClient({1: FT(3, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.OVER_UNDER, "OVER", line=2.5)]), "won")

    def test_over_under_lost(self):
        c = StubClient({1: FT(1, 0)})
        self.assertEqual(_status(c, [Selection(1, Market.OVER_UNDER, "OVER", line=2.5)]), "lost")

    def test_btts_yes(self):
        c = StubClient({1: FT(1, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.BTTS, "YES")]), "won")

    def test_btts_no(self):
        c = StubClient({1: FT(1, 0)})
        self.assertEqual(_status(c, [Selection(1, Market.BTTS, "NO")]), "won")

    def test_draw_no_bet_push(self):
        c = StubClient({1: FT(1, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.DRAW_NO_BET, "HOME")]), "push")

    def test_team_over_under(self):
        c = StubClient({1: FT(3, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.TEAM_OVER_UNDER, "OVER", line=2.5, team="HOME")]), "won")

    def test_correct_score(self):
        c = StubClient({1: FT(2, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.CORRECT_SCORE, "2:1")]), "won")

    def test_asian_handicap_won(self):
        c = StubClient({1: FT(1, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.ASIAN_HANDICAP, "HOME", line=0.5)]), "won")

    def test_asian_handicap_push(self):
        c = StubClient({1: FT(1, 0)})
        self.assertEqual(_status(c, [Selection(1, Market.ASIAN_HANDICAP, "HOME", line=-1.0)]), "push")

    def test_odd_even(self):
        c = StubClient({1: FT(2, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.ODD_EVEN, "ODD")]), "won")

    def test_win_to_nil(self):
        c = StubClient({1: FT(2, 0)})
        self.assertEqual(_status(c, [Selection(1, Market.WIN_TO_NIL, "HOME")]), "won")

    def test_pending(self):
        c = StubClient({1: FixtureOutcome(1, "NS", None, None)})
        self.assertEqual(_status(c, [Selection(1, Market.BTTS, "YES")]), "pending")

    def test_unmapped(self):
        c = StubClient({1: FT(1, 1)})
        sel = Selection(1, Market.UNMAPPED, "X", raw_market="EXOTIC")
        self.assertEqual(_status(c, [sel]), "not_supported")

    def test_slip_lost_if_any_lost(self):
        c = StubClient({
            1: FT(0, 1),
            2: FT(3, 1),
        })
        r = _result(c, [
            Selection(1, Market.MATCH_WINNER, "HOME"),
            Selection(2, Market.OVER_UNDER, "OVER", line=2.5),
        ])
        self.assertEqual(r["status"], "lost")


class TestHalfTimeMarkets(unittest.TestCase):
    def _ht(self):
        return FT(2, 1, halftime_home=1, halftime_away=0)

    def test_ht_match_winner(self):
        c = StubClient({1: self._ht()})
        self.assertEqual(_status(c, [Selection(1, Market.HT_MATCH_WINNER, "HOME")]), "won")

    def test_ht_over_under(self):
        c = StubClient({1: self._ht()})
        self.assertEqual(_status(c, [Selection(1, Market.HT_OVER_UNDER, "UNDER", line=1.5)]), "won")

    def test_ht_btts(self):
        c = StubClient({1: FT(2, 1, halftime_home=1, halftime_away=1)})
        self.assertEqual(_status(c, [Selection(1, Market.HT_BTTS, "YES")]), "won")

    def test_ht_double_chance(self):
        c = StubClient({1: self._ht()})
        self.assertEqual(_status(c, [Selection(1, Market.HT_DOUBLE_CHANCE, "1X")]), "won")

    def test_ht_draw_no_bet(self):
        c = StubClient({1: FT(2, 1, halftime_home=0, halftime_away=0)})
        self.assertEqual(_status(c, [Selection(1, Market.HT_DRAW_NO_BET, "HOME")]), "push")

    def test_ht_odd_even(self):
        c = StubClient({1: self._ht()})
        self.assertEqual(_status(c, [Selection(1, Market.HT_ODD_EVEN, "ODD")]), "won")

    def test_ht_correct_score(self):
        c = StubClient({1: self._ht()})
        self.assertEqual(_status(c, [Selection(1, Market.HT_CORRECT_SCORE, "1:0")]), "won")

    def test_ht_asian_handicap(self):
        c = StubClient({1: self._ht()})
        self.assertEqual(_status(c, [Selection(1, Market.HT_ASIAN_HANDICAP, "HOME", line=-0.5)]), "won")


class TestSecondHalfMarkets(unittest.TestCase):
    def _o(self):
        # FT 3-1, HT 1-0 → 2H is 2-1
        return FT(3, 1, halftime_home=1, halftime_away=0)

    def test_2h_match_winner(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.SECOND_HALF_MATCH_WINNER, "HOME")]), "won")

    def test_2h_over_under(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.SECOND_HALF_OVER_UNDER, "OVER", line=1.5)]), "won")

    def test_2h_btts(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.SECOND_HALF_BTTS, "YES")]), "won")

    def test_2h_double_chance(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.SECOND_HALF_DOUBLE_CHANCE, "12")]), "won")

    def test_2h_draw_no_bet(self):
        # 2H is 1-1 (FT 2-1, HT 1-0)
        c = StubClient({1: FT(2, 1, halftime_home=1, halftime_away=0)})
        self.assertEqual(_status(c, [Selection(1, Market.SECOND_HALF_DRAW_NO_BET, "HOME")]), "push")

    def test_2h_odd_even(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.SECOND_HALF_ODD_EVEN, "ODD")]), "won")

    def test_2h_correct_score(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.SECOND_HALF_CORRECT_SCORE, "2:1")]), "won")


class TestHTFTCombo(unittest.TestCase):
    def test_ht_ft(self):
        c = StubClient({1: FT(2, 2, halftime_home=1, halftime_away=0)})
        self.assertEqual(_status(c, [Selection(1, Market.HT_FT, "HOME/DRAW")]), "won")


class TestNewScoreMarkets(unittest.TestCase):
    def test_clean_sheet_yes(self):
        c = StubClient({1: FT(1, 0)})
        self.assertEqual(_status(c, [Selection(1, Market.CLEAN_SHEET, "YES", team="HOME")]), "won")

    def test_clean_sheet_no(self):
        c = StubClient({1: FT(1, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.CLEAN_SHEET, "YES", team="HOME")]), "lost")

    def test_exact_goals(self):
        c = StubClient({1: FT(2, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.EXACT_GOALS, "3")]), "won")

    def test_exact_goals_plus(self):
        c = StubClient({1: FT(3, 2)})
        self.assertEqual(_status(c, [Selection(1, Market.EXACT_GOALS, "4+")]), "won")

    def test_team_exact_goals(self):
        c = StubClient({1: FT(2, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.TEAM_EXACT_GOALS, "2", team="HOME")]), "won")

    def test_multi_goals_range(self):
        c = StubClient({1: FT(2, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.MULTI_GOALS, "2-4")]), "won")

    def test_multi_goals_range_lost(self):
        c = StubClient({1: FT(0, 0)})
        self.assertEqual(_status(c, [Selection(1, Market.MULTI_GOALS, "2-4")]), "lost")

    def test_multi_goals_plus(self):
        c = StubClient({1: FT(3, 2)})
        self.assertEqual(_status(c, [Selection(1, Market.MULTI_GOALS, "4+")]), "won")

    def test_handicap_result(self):
        # Home 1-0, handicap -1 → adjusted 0-0 → DRAW
        c = StubClient({1: FT(1, 0)})
        self.assertEqual(_status(c, [Selection(1, Market.HANDICAP_RESULT, "DRAW", line=-1.0)]), "won")

    def test_result_btts(self):
        c = StubClient({1: FT(2, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.RESULT_BTTS, "HOME/YES")]), "won")

    def test_result_btts_lost(self):
        c = StubClient({1: FT(2, 0)})
        self.assertEqual(_status(c, [Selection(1, Market.RESULT_BTTS, "HOME/YES")]), "lost")

    def test_result_over_under(self):
        c = StubClient({1: FT(2, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.RESULT_OVER_UNDER, "HOME/OVER", line=2.5)]), "won")

    def test_margin_of_victory_home(self):
        c = StubClient({1: FT(3, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.MARGIN_OF_VICTORY, "HOME:2")]), "won")

    def test_margin_of_victory_draw(self):
        c = StubClient({1: FT(1, 1)})
        self.assertEqual(_status(c, [Selection(1, Market.MARGIN_OF_VICTORY, "DRAW")]), "won")

    def test_margin_of_victory_plus(self):
        c = StubClient({1: FT(4, 0)})
        self.assertEqual(_status(c, [Selection(1, Market.MARGIN_OF_VICTORY, "HOME:3+")]), "won")

    def test_first_team_to_score(self):
        c = StubClient({1: FT(1, 0, first_to_score="HOME", last_to_score="HOME")})
        self.assertEqual(_status(c, [Selection(1, Market.FIRST_TEAM_TO_SCORE, "HOME")]), "won")

    def test_first_team_to_score_none(self):
        c = StubClient({1: FT(0, 0, first_to_score="NONE", last_to_score="NONE")})
        self.assertEqual(_status(c, [Selection(1, Market.FIRST_TEAM_TO_SCORE, "NONE")]), "won")

    def test_last_team_to_score(self):
        c = StubClient({1: FT(2, 1, first_to_score="HOME", last_to_score="AWAY")})
        self.assertEqual(_status(c, [Selection(1, Market.LAST_TEAM_TO_SCORE, "AWAY")]), "won")


class TestCrossHalfMarkets(unittest.TestCase):
    def _o(self):
        # FT 3-1, HT 1-0 → 2H 2-1; home scored both halves, away only 2H
        return FT(3, 1, halftime_home=1, halftime_away=0)

    def test_to_score_in_both_halves_yes(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.TO_SCORE_IN_BOTH_HALVES, "YES", team="HOME")]), "won")

    def test_to_score_in_both_halves_no(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.TO_SCORE_IN_BOTH_HALVES, "YES", team="AWAY")]), "lost")

    def test_to_win_either_half(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.TO_WIN_EITHER_HALF, "HOME")]), "won")

    def test_to_win_both_halves(self):
        c = StubClient({1: self._o()})
        self.assertEqual(_status(c, [Selection(1, Market.TO_WIN_BOTH_HALVES, "HOME")]), "won")

    def test_to_win_both_halves_lost(self):
        # FT 2-2, HT 1-0 → 2H 1-2; home won HT lost 2H
        c = StubClient({1: FT(2, 2, halftime_home=1, halftime_away=0)})
        self.assertEqual(_status(c, [Selection(1, Market.TO_WIN_BOTH_HALVES, "HOME")]), "lost")

    def test_highest_scoring_half_first(self):
        # FT 3-1, HT 2-1 → HT=3, 2H=1 → FIRST
        c = StubClient({1: FT(3, 1, halftime_home=2, halftime_away=1)})
        self.assertEqual(_status(c, [Selection(1, Market.HIGHEST_SCORING_HALF, "FIRST")]), "won")

    def test_highest_scoring_half_equal(self):
        # FT 2-2, HT 1-1 → HT=2, 2H=2 → EQUAL
        c = StubClient({1: FT(2, 2, halftime_home=1, halftime_away=1)})
        self.assertEqual(_status(c, [Selection(1, Market.HIGHEST_SCORING_HALF, "EQUAL")]), "won")

    def test_both_halves_over(self):
        # FT 3-1, HT 2-0 → HT=2, 2H=2 → both > 0.5
        c = StubClient({1: FT(3, 1, halftime_home=2, halftime_away=0)})
        self.assertEqual(_status(c, [Selection(1, Market.BOTH_HALVES_OVER_UNDER, "OVER", line=0.5)]), "won")

    def test_both_halves_over_lost(self):
        # FT 1-0, HT 1-0 → HT=1, 2H=0 → 2H not > 0.5
        c = StubClient({1: FT(1, 0, halftime_home=1, halftime_away=0)})
        self.assertEqual(_status(c, [Selection(1, Market.BOTH_HALVES_OVER_UNDER, "OVER", line=0.5)]), "lost")


class TestStatsMarkets(unittest.TestCase):
    def _c(self, **kw):
        return StubClient({1: FT(1, 0)}, {1: STATS(**kw)})

    def test_corners_over_under(self):
        c = self._c(corners_home=7, corners_away=5)
        self.assertEqual(_status(c, [Selection(1, Market.CORNERS_OVER_UNDER, "OVER", line=10.5)]), "won")

    def test_team_corners_over_under(self):
        c = self._c(corners_home=7, corners_away=3)
        self.assertEqual(_status(c, [Selection(1, Market.TEAM_CORNERS_OVER_UNDER, "OVER", line=5.5, team="HOME")]), "won")

    def test_cards_over_under(self):
        c = self._c(yellow_home=2, yellow_away=3, red_home=0, red_away=1)
        self.assertEqual(_status(c, [Selection(1, Market.CARDS_OVER_UNDER, "OVER", line=5.5)]), "won")

    def test_team_cards_over_under(self):
        c = self._c(yellow_home=2, red_home=1, yellow_away=1, red_away=0)
        self.assertEqual(_status(c, [Selection(1, Market.TEAM_CARDS_OVER_UNDER, "OVER", line=2.5, team="HOME")]), "won")

    def test_shots_over_under(self):
        c = self._c(shots_home=10, shots_away=8)
        self.assertEqual(_status(c, [Selection(1, Market.SHOTS_OVER_UNDER, "OVER", line=15.5)]), "won")

    def test_shots_on_target_over_under(self):
        c = self._c(shots_on_target_home=5, shots_on_target_away=3)
        self.assertEqual(_status(c, [Selection(1, Market.SHOTS_ON_TARGET_OVER_UNDER, "OVER", line=6.5)]), "won")

    def test_fouls_over_under(self):
        c = self._c(fouls_home=12, fouls_away=14)
        self.assertEqual(_status(c, [Selection(1, Market.FOULS_OVER_UNDER, "OVER", line=20.5)]), "won")

    def test_offsides_over_under(self):
        c = self._c(offsides_home=3, offsides_away=2)
        self.assertEqual(_status(c, [Selection(1, Market.OFFSIDES_OVER_UNDER, "UNDER", line=6.5)]), "won")


if __name__ == "__main__":
    unittest.main()
