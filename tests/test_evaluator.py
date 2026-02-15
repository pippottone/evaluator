from __future__ import annotations

import unittest

from evaluator import evaluate_betslip
from models import FixtureOutcome, Market, Selection


class StubClient:
    def __init__(self, outcomes: dict[int, FixtureOutcome], statistics: dict[int, object] | None = None) -> None:
        self.outcomes = outcomes
        self.statistics = statistics or {}

    def get_fixture_outcome(self, fixture_id: int) -> FixtureOutcome:
        return self.outcomes[fixture_id]

    def get_fixture_statistics(self, fixture_id: int) -> object:
        return self.statistics[fixture_id]

    @staticmethod
    def is_final_status(status_short: str) -> bool:
        return status_short in {"FT", "AET", "PEN", "AWD", "WO"}


class EvaluatorTests(unittest.TestCase):
    def test_match_winner_won(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=2, away_goals=1),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.MATCH_WINNER, pick="HOME")]

        result = evaluate_betslip(client, selections)

        self.assertEqual(result["status"], "won")
        self.assertEqual(result["results"][0]["status"], "won")

    def test_slip_lost_if_any_lost(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=0, away_goals=1),
                2: FixtureOutcome(fixture_id=2, status_short="FT", home_goals=3, away_goals=1),
            }
        )
        selections = [
            Selection(fixture_id=1, market=Market.MATCH_WINNER, pick="HOME"),
            Selection(fixture_id=2, market=Market.OVER_UNDER, pick="OVER", line=2.5),
        ]

        result = evaluate_betslip(client, selections)

        self.assertEqual(result["status"], "lost")
        self.assertEqual(result["results"][0]["status"], "lost")
        self.assertEqual(result["results"][1]["status"], "won")

    def test_pending_if_fixture_not_finalized(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="NS", home_goals=None, away_goals=None),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.BTTS, pick="YES")]

        result = evaluate_betslip(client, selections)

        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["results"][0]["status"], "pending")

    def test_draw_no_bet_push_on_draw(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=1, away_goals=1),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.DRAW_NO_BET, pick="HOME")]

        result = evaluate_betslip(client, selections)

        self.assertEqual(result["status"], "refund")
        self.assertEqual(result["results"][0]["status"], "push")

    def test_team_over_under(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=3, away_goals=1),
            }
        )
        selections = [
            Selection(fixture_id=1, market=Market.TEAM_OVER_UNDER, pick="OVER", line=2.5, team="HOME")
        ]

        result = evaluate_betslip(client, selections)

        self.assertEqual(result["status"], "won")
        self.assertEqual(result["results"][0]["status"], "won")

    def test_correct_score(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=2, away_goals=1),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.CORRECT_SCORE, pick="2:1")]

        result = evaluate_betslip(client, selections)

        self.assertEqual(result["status"], "won")
        self.assertEqual(result["results"][0]["status"], "won")

    def test_ht_match_winner(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(
                    fixture_id=1,
                    status_short="FT",
                    home_goals=2,
                    away_goals=1,
                    halftime_home=1,
                    halftime_away=0,
                ),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.HT_MATCH_WINNER, pick="HOME")]
        result = evaluate_betslip(client, selections)
        self.assertEqual(result["results"][0]["status"], "won")

    def test_second_half_over_under(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(
                    fixture_id=1,
                    status_short="FT",
                    home_goals=3,
                    away_goals=1,
                    halftime_home=1,
                    halftime_away=1,
                ),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.SECOND_HALF_OVER_UNDER, pick="OVER", line=1.5)]
        result = evaluate_betslip(client, selections)
        self.assertEqual(result["results"][0]["status"], "won")

    def test_ht_ft_combo(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(
                    fixture_id=1,
                    status_short="FT",
                    home_goals=2,
                    away_goals=2,
                    halftime_home=1,
                    halftime_away=0,
                ),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.HT_FT, pick="HOME/DRAW")]
        result = evaluate_betslip(client, selections)
        self.assertEqual(result["results"][0]["status"], "won")

    def test_corners_over_under(self) -> None:
        from models import FixtureStatistics

        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=1, away_goals=0),
            },
            {
                1: FixtureStatistics(fixture_id=1, corners_home=7, corners_away=5),
            },
        )
        selections = [Selection(fixture_id=1, market=Market.CORNERS_OVER_UNDER, pick="OVER", line=10.5)]
        result = evaluate_betslip(client, selections)
        self.assertEqual(result["results"][0]["status"], "won")

    def test_team_cards_over_under(self) -> None:
        from models import FixtureStatistics

        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=1, away_goals=1),
            },
            {
                1: FixtureStatistics(fixture_id=1, yellow_home=2, red_home=1, yellow_away=1, red_away=0),
            },
        )
        selections = [
            Selection(fixture_id=1, market=Market.TEAM_CARDS_OVER_UNDER, pick="OVER", line=2.5, team="HOME")
        ]
        result = evaluate_betslip(client, selections)
        self.assertEqual(result["results"][0]["status"], "won")

    def test_unmapped_market_not_supported(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=1, away_goals=1),
            }
        )
        selections = [
            Selection(
                fixture_id=1,
                market=Market.UNMAPPED,
                pick="SOMETHING",
                raw_market="EXOTIC_SUPER_MARKET",
            )
        ]
        result = evaluate_betslip(client, selections)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["results"][0]["status"], "not_supported")

    def test_asian_handicap_won(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=1, away_goals=1),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.ASIAN_HANDICAP, pick="HOME", line=0.5)]
        result = evaluate_betslip(client, selections)
        self.assertEqual(result["results"][0]["status"], "won")

    def test_odd_even(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=2, away_goals=1),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.ODD_EVEN, pick="ODD")]
        result = evaluate_betslip(client, selections)
        self.assertEqual(result["results"][0]["status"], "won")

    def test_win_to_nil(self) -> None:
        client = StubClient(
            {
                1: FixtureOutcome(fixture_id=1, status_short="FT", home_goals=2, away_goals=0),
            }
        )
        selections = [Selection(fixture_id=1, market=Market.WIN_TO_NIL, pick="HOME")]
        result = evaluate_betslip(client, selections)
        self.assertEqual(result["results"][0]["status"], "won")


if __name__ == "__main__":
    unittest.main()
