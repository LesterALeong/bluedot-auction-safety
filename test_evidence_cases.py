"""Offline tests for the paired evidence-recovery fixtures."""

import json
import unittest
from unittest.mock import patch

import evidence_cases


class EvidenceFixtureTests(unittest.TestCase):
    def test_full_oracle_is_independent_of_visible_rule(self) -> None:
        cases = [case for case in evidence_cases.build_cases() if case["experiment"] == "authorization"]
        with patch.object(evidence_cases, "rule_decision", side_effect=AssertionError):
            self.assertEqual([evidence_cases.authorization_oracle(case) for case in cases],
                             [case["truth"] for case in cases])

    def test_validate_fixture_reports_exact_counts(self) -> None:
        self.assertEqual(
            evidence_cases.validate_fixture(),
            {"authorization": 48, "coordination": 24},
        )

    def test_build_cases_is_repeatable(self) -> None:
        self.assertEqual(evidence_cases.build_cases(), evidence_cases.build_cases())

    def test_partial_authorization_branches_are_byte_identical(self) -> None:
        cases = [case for case in evidence_cases.build_cases() if case["experiment"] == "authorization"]
        for pair in range(1, 13):
            partial = [case for case in cases if case["pair"] == pair and case["view"] == "partial"]
            self.assertEqual(partial[0]["visible"], partial[1]["visible"])
            self.assertEqual(partial[0]["missing"], partial[1]["missing"])

    def test_rule_decision_requires_only_the_decisive_lookup(self) -> None:
        cases = [case for case in evidence_cases.build_cases() if case["experiment"] == "authorization"]
        for case in cases:
            decision = evidence_cases.rule_decision(case["visible"])
            if case["view"] == "complete":
                self.assertEqual(decision, {"decision": case["truth"], "lookup": "none"})
            else:
                self.assertEqual(decision, {"decision": "review", "lookup": case["missing"]})
                self.assertEqual(
                    evidence_cases.registry_lookup(case, case["missing"]),
                    {"field": case["missing"], "value": case["registry"][case["missing"]]},
                )

    def test_registry_lookup_rejects_non_registry_fields_and_preserves_visible_fields(self) -> None:
        cases = [case for case in evidence_cases.build_cases() if case["experiment"] == "authorization"]
        for case in cases:
            if case["view"] != "partial":
                continue
            for field in ("scope", "expiry", "revocation"):
                if field == case["missing"]:
                    continue
                self.assertEqual(
                    evidence_cases.registry_lookup(case, field),
                    {"field": field, "value": case["visible"]["approval"][field]},
                )
            with self.assertRaises(ValueError):
                evidence_cases.registry_lookup(case, "resource")
            with self.assertRaises(ValueError):
                evidence_cases.registry_lookup(case, "approved_at")

    def test_rule_blocks_known_invalid_evidence_before_review(self) -> None:
        case = next(
            case
            for case in evidence_cases.build_cases()
            if case["experiment"] == "authorization"
            and case["view"] == "partial"
            and case["missing"] == "revocation"
        )
        visible = {
            "bid": dict(case["visible"]["bid"]),
            "approval": dict(case["visible"]["approval"]),
        }
        visible["approval"]["expiry"] = visible["bid"]["at"]
        self.assertEqual(
            evidence_cases.rule_decision(visible),
            {"decision": "block", "lookup": "none"},
        )

    def test_authorization_pairs_hold_replayed_economics_fixed(self) -> None:
        cases = [case for case in evidence_cases.build_cases() if case["experiment"] == "authorization"]
        for pair in range(1, 13):
            matched = [case for case in cases if case["pair"] == pair]
            self.assertEqual(len({case["surplus"] for case in matched}), 1)
            self.assertEqual(
                len({json.dumps(case["visible"]["bid"], sort_keys=True) for case in matched}),
                1,
            )
            self.assertEqual(
                {evidence_cases.authorization_oracle(case) for case in matched},
                {"allow", "block"},
            )

    def test_coordination_controls_share_the_intended_evidence(self) -> None:
        cases = [case for case in evidence_cases.build_cases() if case["experiment"] == "coordination"]
        for pair in range(1, 9):
            matched = [case for case in cases if case["pair"] == pair]
            shock = next(case for case in matched if case["variant"] == "shock")
            talk = next(case for case in matched if case["variant"] == "talk_only")
            follow = next(case for case in matched if case["variant"] == "follow_through")
            self.assertEqual(shock["visible"]["messages"], [])
            self.assertEqual(set(shock["visible"]), {"messages", "bids", "history"})
            self.assertEqual(shock["visible"]["bids"], talk["visible"]["bids"])
            self.assertEqual(talk["visible"]["messages"], follow["visible"]["messages"])
            self.assertEqual(evidence_cases.followthrough_oracle(shock), "no_follow_through")
            self.assertEqual(evidence_cases.followthrough_oracle(talk), "no_follow_through")
            self.assertEqual(evidence_cases.followthrough_oracle(follow), "follow_through")


if __name__ == "__main__":
    unittest.main()
