from __future__ import annotations

import unittest

from models import Market
from service import TableRowIn, _row_to_selection


class ServiceMappingTests(unittest.TestCase):
    def test_match_winner_aliases(self) -> None:
        row = TableRowIn(fixture_id=10, market="1x2", pick="1")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.MATCH_WINNER)
        self.assertEqual(selection.pick, "HOME")

    def test_over_under_requires_line(self) -> None:
        row = TableRowIn(fixture_id=11, market="OU", pick="OVER")
        with self.assertRaises(ValueError):
            _row_to_selection(row)

    def test_btts_aliases(self) -> None:
        row = TableRowIn(fixture_id=12, market="GGNG", pick="GG")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.BTTS)
        self.assertEqual(selection.pick, "YES")

    def test_dnb_alias(self) -> None:
        row = TableRowIn(fixture_id=13, market="DNB", pick="1")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.DRAW_NO_BET)
        self.assertEqual(selection.pick, "HOME")

    def test_team_total_requires_team(self) -> None:
        row = TableRowIn(fixture_id=14, market="TEAM_TOTAL_GOALS", pick="OVER", line=1.5)
        with self.assertRaises(ValueError):
            _row_to_selection(row)

    def test_correct_score_alias(self) -> None:
        row = TableRowIn(fixture_id=15, market="CS", pick="2-1")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.CORRECT_SCORE)
        self.assertEqual(selection.pick, "2:1")

    def test_ht_match_winner_alias(self) -> None:
        row = TableRowIn(fixture_id=16, market="HT_1X2", pick="X")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.HT_MATCH_WINNER)
        self.assertEqual(selection.pick, "DRAW")

    def test_second_half_ou_alias(self) -> None:
        row = TableRowIn(fixture_id=17, market="2H_OU", pick="O", line=1.5)
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.SECOND_HALF_OVER_UNDER)
        self.assertEqual(selection.pick, "OVER")

    def test_ht_ft_alias(self) -> None:
        row = TableRowIn(fixture_id=18, market="HTFT", pick="1-X")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.HT_FT)
        self.assertEqual(selection.pick, "1/X")

    def test_corners_ou_alias(self) -> None:
        row = TableRowIn(fixture_id=19, market="CORNERS_OU", pick="U", line=8.5)
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.CORNERS_OVER_UNDER)
        self.assertEqual(selection.pick, "UNDER")

    def test_team_cards_ou_alias(self) -> None:
        row = TableRowIn(fixture_id=20, market="TEAM_CARDS_OU", pick="OVER", line=2.5, team="away")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.TEAM_CARDS_OVER_UNDER)
        self.assertEqual(selection.team, "AWAY")

    def test_unknown_market_maps_to_unmapped(self) -> None:
        row = TableRowIn(fixture_id=21, market="TOTALLY_UNKNOWN_MARKET", pick="ANY")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.UNMAPPED)
        self.assertEqual(selection.raw_market, "TOTALLY_UNKNOWN_MARKET")

    def test_asian_handicap_alias(self) -> None:
        row = TableRowIn(fixture_id=22, market="HANDICAP", pick="1", line=0.5)
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.ASIAN_HANDICAP)
        self.assertEqual(selection.pick, "HOME")

    def test_odd_even_alias(self) -> None:
        row = TableRowIn(fixture_id=23, market="ODD_EVEN", pick="ODD")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.ODD_EVEN)
        self.assertEqual(selection.pick, "ODD")

    def test_win_to_nil_alias(self) -> None:
        row = TableRowIn(fixture_id=24, market="HOME_WIN_TO_NIL", pick="1")
        selection = _row_to_selection(row)
        self.assertEqual(selection.market, Market.WIN_TO_NIL)
        self.assertEqual(selection.pick, "HOME")


if __name__ == "__main__":
    unittest.main()
