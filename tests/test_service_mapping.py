from __future__ import annotations
import unittest
from models import Market
from service import TableRowIn, _row_to_selection


class ServiceMappingTests(unittest.TestCase):
    # ── core ──
    def test_1x2(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="1x2", pick="1"))
        self.assertEqual(s.market, Market.MATCH_WINNER)
        self.assertEqual(s.pick, "HOME")

    def test_moneyline(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="Moneyline", pick="2"))
        self.assertEqual(s.market, Market.MATCH_WINNER)
        self.assertEqual(s.pick, "AWAY")

    def test_dc(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="DC", pick="1X"))
        self.assertEqual(s.market, Market.DOUBLE_CHANCE)

    def test_dnb(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="DNB", pick="1"))
        self.assertEqual(s.market, Market.DRAW_NO_BET)
        self.assertEqual(s.pick, "HOME")

    # ── over/under ──
    def test_ou(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="OU", pick="O", line=2.5))
        self.assertEqual(s.market, Market.OVER_UNDER)
        self.assertEqual(s.pick, "OVER")

    def test_ou_requires_line(self):
        with self.assertRaises(ValueError):
            _row_to_selection(TableRowIn(fixture_id=1, market="OU", pick="OVER"))

    # ── BTTS ──
    def test_btts(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="GGNG", pick="GG"))
        self.assertEqual(s.market, Market.BTTS)
        self.assertEqual(s.pick, "YES")

    # ── team total ──
    def test_team_total_requires_team(self):
        with self.assertRaises(ValueError):
            _row_to_selection(TableRowIn(fixture_id=1, market="TEAM_TOTAL_GOALS", pick="OVER", line=1.5))

    def test_team_total(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="TEAM_TOTAL_GOALS", pick="OVER", line=1.5, team="home"))
        self.assertEqual(s.market, Market.TEAM_OVER_UNDER)
        self.assertEqual(s.team, "HOME")

    # ── correct score ──
    def test_cs(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="CS", pick="2-1"))
        self.assertEqual(s.market, Market.CORRECT_SCORE)
        self.assertEqual(s.pick, "2:1")

    # ── handicap ──
    def test_handicap(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="HANDICAP", pick="1", line=0.5))
        self.assertEqual(s.market, Market.ASIAN_HANDICAP)
        self.assertEqual(s.pick, "HOME")

    def test_european_handicap(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="EUROPEAN_HANDICAP", pick="X", line=-1.0))
        self.assertEqual(s.market, Market.HANDICAP_RESULT)
        self.assertEqual(s.pick, "DRAW")

    # ── odd/even ──
    def test_odd_even(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="ODD_EVEN", pick="ODD"))
        self.assertEqual(s.market, Market.ODD_EVEN)

    # ── win to nil ──
    def test_win_to_nil(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="HOME_WIN_TO_NIL", pick="1"))
        self.assertEqual(s.market, Market.WIN_TO_NIL)
        self.assertEqual(s.pick, "HOME")

    # ── clean sheet ──
    def test_clean_sheet(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="CLEAN_SHEET", pick="YES", team="home"))
        self.assertEqual(s.market, Market.CLEAN_SHEET)
        self.assertEqual(s.team, "HOME")

    # ── exact goals ──
    def test_exact_goals(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="EXACT_GOALS_NUMBER", pick="3"))
        self.assertEqual(s.market, Market.EXACT_GOALS)

    def test_team_exact_goals(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="HOME_TEAM_EXACT_GOALS", pick="2", team="home"))
        self.assertEqual(s.market, Market.TEAM_EXACT_GOALS)
        self.assertEqual(s.team, "HOME")

    # ── multi goals ──
    def test_multi_goals(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="MULTI_GOALS", pick="2-4"))
        self.assertEqual(s.market, Market.MULTI_GOALS)

    # ── first/last scorer ──
    def test_first_team(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="FIRST_TEAM_TO_SCORE", pick="1"))
        self.assertEqual(s.market, Market.FIRST_TEAM_TO_SCORE)
        self.assertEqual(s.pick, "HOME")

    def test_last_team(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="LAST_TEAM_TO_SCORE", pick="AWAY"))
        self.assertEqual(s.market, Market.LAST_TEAM_TO_SCORE)

    # ── combo markets ──
    def test_result_btts(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="RESULT_BTTS", pick="1/GG"))
        self.assertEqual(s.market, Market.RESULT_BTTS)
        self.assertEqual(s.pick, "HOME/YES")

    def test_result_over_under(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="RESULT_TOTAL_GOALS", pick="HOME/OVER", line=2.5))
        self.assertEqual(s.market, Market.RESULT_OVER_UNDER)
        self.assertEqual(s.pick, "HOME/OVER")

    def test_margin(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="WINNING_MARGIN", pick="HOME:2"))
        self.assertEqual(s.market, Market.MARGIN_OF_VICTORY)

    # ── HT markets ──
    def test_ht_1x2(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="HT_1X2", pick="X"))
        self.assertEqual(s.market, Market.HT_MATCH_WINNER)
        self.assertEqual(s.pick, "DRAW")

    def test_ht_btts(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="1H_BTTS", pick="NO"))
        self.assertEqual(s.market, Market.HT_BTTS)
        self.assertEqual(s.pick, "NO")

    def test_ht_dc(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="DOUBLE_CHANCE_FIRST_HALF", pick="1X"))
        self.assertEqual(s.market, Market.HT_DOUBLE_CHANCE)

    def test_ht_dnb(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="1H_DNB", pick="2"))
        self.assertEqual(s.market, Market.HT_DRAW_NO_BET)
        self.assertEqual(s.pick, "AWAY")

    def test_ht_odd_even(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="ODD_EVEN_FIRST_HALF", pick="EVEN"))
        self.assertEqual(s.market, Market.HT_ODD_EVEN)

    def test_ht_cs(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="CORRECT_SCORE_FIRST_HALF", pick="1:0"))
        self.assertEqual(s.market, Market.HT_CORRECT_SCORE)

    def test_ht_ah(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="ASIAN_HANDICAP_FIRST_HALF", pick="1", line=-0.5))
        self.assertEqual(s.market, Market.HT_ASIAN_HANDICAP)
        self.assertEqual(s.pick, "HOME")

    # ── 2H markets ──
    def test_2h_1x2(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="2H_1X2", pick="2"))
        self.assertEqual(s.market, Market.SECOND_HALF_MATCH_WINNER)
        self.assertEqual(s.pick, "AWAY")

    def test_2h_ou(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="2H_OU", pick="O", line=1.5))
        self.assertEqual(s.market, Market.SECOND_HALF_OVER_UNDER)
        self.assertEqual(s.pick, "OVER")

    def test_2h_btts(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="BTTS_SECOND_HALF", pick="YES"))
        self.assertEqual(s.market, Market.SECOND_HALF_BTTS)

    def test_2h_dc(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="2H_DOUBLE_CHANCE", pick="X2"))
        self.assertEqual(s.market, Market.SECOND_HALF_DOUBLE_CHANCE)

    def test_2h_dnb(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="2H_DNB", pick="1"))
        self.assertEqual(s.market, Market.SECOND_HALF_DRAW_NO_BET)
        self.assertEqual(s.pick, "HOME")

    def test_2h_odd_even(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="ODD_EVEN_SECOND_HALF", pick="ODD"))
        self.assertEqual(s.market, Market.SECOND_HALF_ODD_EVEN)

    def test_2h_cs(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="2H_CORRECT_SCORE", pick="1-0"))
        self.assertEqual(s.market, Market.SECOND_HALF_CORRECT_SCORE)
        self.assertEqual(s.pick, "1:0")

    # ── HT/FT ──
    def test_htft(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="HTFT", pick="1-X"))
        self.assertEqual(s.market, Market.HT_FT)
        self.assertEqual(s.pick, "1/X")

    # ── cross-half ──
    def test_score_both_halves(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="SCORE_IN_BOTH_HALVES", pick="YES", team="home"))
        self.assertEqual(s.market, Market.TO_SCORE_IN_BOTH_HALVES)
        self.assertEqual(s.team, "HOME")

    def test_win_either_half(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="WIN_EITHER_HALF", pick="2"))
        self.assertEqual(s.market, Market.TO_WIN_EITHER_HALF)
        self.assertEqual(s.pick, "AWAY")

    def test_win_both_halves(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="WIN_BOTH_HALVES", pick="1"))
        self.assertEqual(s.market, Market.TO_WIN_BOTH_HALVES)
        self.assertEqual(s.pick, "HOME")

    def test_highest_scoring_half(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="HIGHEST_SCORING_HALF", pick="1ST"))
        self.assertEqual(s.market, Market.HIGHEST_SCORING_HALF)
        self.assertEqual(s.pick, "FIRST")

    def test_both_halves_over(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="BOTH_HALVES_OVER", pick="O", line=0.5))
        self.assertEqual(s.market, Market.BOTH_HALVES_OVER_UNDER)
        self.assertEqual(s.pick, "OVER")

    # ── stats ──
    def test_corners_ou(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="CORNERS_OU", pick="U", line=8.5))
        self.assertEqual(s.market, Market.CORNERS_OVER_UNDER)
        self.assertEqual(s.pick, "UNDER")

    def test_team_cards_ou(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="TEAM_CARDS_OU", pick="OVER", line=2.5, team="away"))
        self.assertEqual(s.market, Market.TEAM_CARDS_OVER_UNDER)
        self.assertEqual(s.team, "AWAY")

    def test_shots_ou(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="TOTAL_SHOTS", pick="OVER", line=20.5))
        self.assertEqual(s.market, Market.SHOTS_OVER_UNDER)

    def test_shots_on_target(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="SHOTS_ON_TARGET", pick="UNDER", line=8.5))
        self.assertEqual(s.market, Market.SHOTS_ON_TARGET_OVER_UNDER)

    def test_fouls(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="TOTAL_FOULS", pick="OVER", line=20.5))
        self.assertEqual(s.market, Market.FOULS_OVER_UNDER)

    def test_offsides(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="TOTAL_OFFSIDES", pick="UNDER", line=5.5))
        self.assertEqual(s.market, Market.OFFSIDES_OVER_UNDER)

    # ── unmapped ──
    def test_unknown(self):
        s = _row_to_selection(TableRowIn(fixture_id=1, market="TOTALLY_UNKNOWN", pick="X"))
        self.assertEqual(s.market, Market.UNMAPPED)
        self.assertEqual(s.raw_market, "TOTALLY_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
