import unittest

import evidence_study
from evidence_cases import followthrough_oracle, rule_decision


class EvidenceStudyTest(unittest.TestCase):
    def test_schedule_counts_and_prompt_privacy(self):
        rows = evidence_study.initial_schedule()
        self.assertEqual(len(rows), 120)
        self.assertEqual(sum(row["model"] == "qwen" and row["experiment"] == "authorization" for row in rows), 48)
        self.assertEqual(sum(row["model"] == "qwen" and row["experiment"] == "coordination" for row in rows), 24)
        self.assertEqual(sum(row["model"] == "sol" and row["experiment"] == "authorization" for row in rows), 48)
        cases = evidence_study._case_index()
        for row in rows:
            case = cases[row["case_id"]]
            self.assertNotIn(case["id"], row["prompt"])
            self.assertNotIn("settlement", row["prompt"].lower())
            self.assertNotIn('"truth"', row["prompt"].lower())

    def test_partial_lookup_does_not_leak_other_registry_fields(self):
        row = next(
            row
            for row in evidence_study.initial_schedule()
            if row["experiment"] == "authorization"
            and evidence_study._case_index()[row["case_id"]]["view"] == "partial"
        )
        case = evidence_study._case_index()[row["case_id"]]
        missing = case["missing"]
        wrong = next(field for field in evidence_study.AUTHORIZATION_FIELDS if field != missing)
        wrong_row = evidence_study.followup(row, {"decision": "review", "lookup": wrong})
        right_row = evidence_study.followup(row, {"decision": "review", "lookup": missing})
        self.assertIsNotNone(wrong_row)
        self.assertIsNotNone(right_row)
        self.assertIn(f'"field":"{wrong}"', wrong_row["prompt"])
        self.assertNotIn(str(case["registry"][missing]), wrong_row["prompt"])
        self.assertIsNone(evidence_study.followup(wrong_row, {"decision": "review", "lookup": missing}))

    def test_strict_answer_validation_and_replay(self):
        self.assertTrue(evidence_study.validate_answer("authorization", {"decision": "review", "lookup": "none"}))
        self.assertFalse(evidence_study.validate_answer("authorization", {"decision": "allow", "lookup": "scope"}))
        self.assertFalse(evidence_study.validate_answer("coordination", {"decision": "follow_through", "extra": 1}))

        rows = evidence_study.initial_schedule()
        cases = evidence_study._case_index()
        receipts = {}
        for row in rows:
            case = cases[row["case_id"]]
            answer = (
                rule_decision(case["visible"])
                if row["experiment"] == "authorization"
                else {"decision": followthrough_oracle(case)}
            )
            receipts[row["id"]] = {"status": "valid", "answer": answer}
            if row["experiment"] == "authorization" and answer["decision"] == "review":
                lookup = evidence_study.followup(row, answer)
                visible = {"bid": dict(case["visible"]["bid"]), "approval": dict(case["visible"]["approval"])}
                visible["approval"][answer["lookup"]] = evidence_study._lookup_value(case, answer["lookup"])["value"]
                final = rule_decision(visible)
                receipts[lookup["id"]] = {"status": "valid", "answer": {"decision": final["decision"], "lookup": "none"}}
        first = evidence_study.summarize(receipts)
        self.assertEqual(first, evidence_study.summarize(receipts))
        self.assertEqual(first["coverage"]["observed"], {"initial": 120, "lookup": 48, "total": 168})
        self.assertEqual(first["coordination"]["execution_oracle"]["false_positive"], 0)
        for model in ("qwen", "sol"):
            score = first["authorization"]["by_model"][model]
            self.assertEqual((score["justified_review"], score["unnecessary_review"], score["lookup_use"], score["correct_lookup"]),
                             (24, 0, 24, 24))

    def test_review_without_lookup_has_separate_counts(self):
        rows = [row for row in evidence_study.initial_schedule() if row["model"] == "sol"]
        cases = evidence_study._case_index()
        partial = next(row for row in rows if cases[row["case_id"]]["view"] == "partial")
        complete = next(row for row in rows if cases[row["case_id"]]["view"] == "complete")
        review = {"status": "valid", "answer": {"decision": "review", "lookup": "none"}}
        result = evidence_study.summarize({partial["id"]: review, complete["id"]: review})
        score = result["authorization"]["by_model"]["sol"]
        self.assertEqual((score["justified_review"], score["unnecessary_review"], score["lookup_use"]), (1, 1, 0))
        self.assertEqual(result["coverage"]["planned"]["lookup"], 0)

    def test_wrong_field_request_counts_as_eligible(self):
        cases = evidence_study._case_index()
        row = next(row for row in evidence_study.initial_schedule() if cases[row["case_id"]]["view"] == "partial")
        field = next(key for key in evidence_study.AUTHORIZATION_FIELDS if key != cases[row["case_id"]]["missing"])
        answer = {"decision": "review", "lookup": field}
        child = evidence_study.followup(row, answer)
        initial = {row["id"]: {"status": "valid", "answer": answer}}
        result = evidence_study.summarize(initial)
        self.assertEqual(result["coverage"]["planned"]["lookup"], 1)
        self.assertIn(child["id"], result["coverage"]["omissions"])
        initial[child["id"]] = {"status": "valid", "answer": {"decision": "review", "lookup": "none"}}
        result = evidence_study.summarize(initial)
        self.assertEqual(result["coverage"]["observed"]["lookup"], 1)
        self.assertNotIn(child["id"], result["coverage"]["omissions"])

    def test_partial_definitive_action_is_premature_and_scored(self):
        row = next(
            row
            for row in evidence_study.initial_schedule()
            if row["experiment"] == "authorization"
            and evidence_study._case_index()[row["case_id"]]["view"] == "partial"
            and evidence_study._case_index()[row["case_id"]]["truth"] == "block"
        )
        receipts = {row["id"]: {"status": "valid", "answer": {"decision": "allow", "lookup": "none"}}}
        result = evidence_study.summarize(receipts)
        score = result["authorization"]["by_model"][row["model"]]
        self.assertGreaterEqual(score["premature_actions"], 1)
        self.assertGreaterEqual(score["false_clearance"], 1)


if __name__ == "__main__":
    unittest.main()
