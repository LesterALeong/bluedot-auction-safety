"""Offline tests for the deterministic auction fixture."""

import unittest

import auction


class AuctionFixtureTests(unittest.TestCase):
    def test_validate_fixture_reports_exact_counts(self) -> None:
        self.assertEqual(
            auction.validate_fixture(),
            {"approval": 320, "anchor": 16, "advice": 16, "coordination": 32},
        )

    def test_build_cases_is_repeatable(self) -> None:
        self.assertEqual(auction.build_cases(), auction.build_cases())

    def test_approval_hand_checked_development_pairs(self) -> None:
        cases = [case for case in auction.build_cases() if case["experiment"] == "approval"]
        self.assertFalse({case["pair"] for case in cases}.intersection(auction.DEVELOPMENT_PAIRS))
        for pair in auction.DEVELOPMENT_PAIRS:
            for truth in ("compliant", "violation"):
                events = auction._approval_events(pair, truth, False)
                self.assertEqual(auction.replay_approval(events), truth)
                day_by_kind = {event["kind"]: event["date"] for event in events}
                self.assertEqual(day_by_kind["approval"] < day_by_kind["bid"], truth == "compliant")

    def test_approval_views_preserve_decisive_order(self) -> None:
        cases = [case for case in auction.build_cases() if case["experiment"] == "approval"]
        for pair in range(1, 41):
            for truth in ("compliant", "violation"):
                matched = [case for case in cases if case["pair"] == pair and case["truth"] == truth and case["model"] == "gemma"]
                short = next(case for case in matched if case["condition"] == "short")
                cluttered = next(case for case in matched if case["condition"] == "cluttered")
                short_core = [event["kind"] for event in short["context"]["events"] if event["kind"] in {"quote", "approval", "bid", "settlement"}]
                cluttered_core = [event["kind"] for event in cluttered["context"]["events"] if event["kind"] in {"quote", "approval", "bid", "settlement"}]
                self.assertEqual(short_core, cluttered_core)

    def test_buyer_pairs_hold_quotes_and_controls_fixed(self) -> None:
        cases = [case for case in auction.build_cases() if case["experiment"] in {"anchor", "advice"}]
        for pair in range(1, 9):
            for experiment in ("anchor", "advice"):
                matched = [case for case in cases if case["pair"] == pair and case["experiment"] == experiment]
                self.assertEqual(len(matched), 2)
                self.assertEqual(matched[0]["context"]["quotes"], matched[1]["context"]["quotes"])
                self.assertEqual(matched[0]["context"]["value"], matched[1]["context"]["value"])
                self.assertEqual(matched[0]["context"]["limit"], matched[1]["context"]["limit"])

    def test_coordination_price_only_view_is_ambiguous(self) -> None:
        cases = [case for case in auction.build_cases() if case["experiment"] == "coordination"]
        for pair in range(1, 9):
            outcome = [case for case in cases if case["pair"] == pair and case["condition"] == "outcome"]
            self.assertEqual(len(outcome), 2)
            self.assertEqual(outcome[0]["context"]["price_path"], outcome[1]["context"]["price_path"])
            self.assertTrue(all(case["truth"] == "uncertain" for case in outcome))


if __name__ == "__main__":
    unittest.main()
