import json
import unittest

import codex_comparison_design as design
import study


class ComparisonDesignTests(unittest.TestCase):
    def test_schedule_is_frozen_sized_and_private(self):
        first = design.schedule()
        self.assertEqual(first, design.schedule())
        self.assertEqual(len(first), 1280)
        self.assertEqual({row["model"] for row in first}, set(design.MODELS))
        self.assertEqual({row["variant"] for row in first}, set(design.VARIANTS))
        self.assertEqual({row["view"] for row in first}, set(design.VIEWS))
        self.assertEqual({row["truth"] for row in first}, set(design.TRUTHS))
        self.assertEqual(
            set(first[0]),
            {
                "id",
                "model",
                "pair",
                "truth",
                "view",
                "variant",
                "prompt",
                "bid_date",
                "approval_date",
            },
        )
        source = next(
            case
            for case in study.plan_cases()
            if case["experiment"] == "approval"
            and case["pair"] == first[0]["pair"]
            and case["truth"] == first[0]["truth"]
            and case["condition"] == first[0]["view"]
        )
        if first[0]["variant"] == "original":
            self.assertEqual(first[0]["prompt"], source["prompt"])
        else:
            self.assertTrue(first[0]["prompt"].startswith(source["prompt"] + "\n\n"))
        self.assertNotIn(first[0]["model"], first[0]["prompt"])

    def test_output_schemas_are_exact_and_json_safe(self):
        original = design.output_schema("original")
        revised = design.output_schema("revised")
        self.assertEqual(original["required"], ["decision"])
        self.assertEqual(set(original["properties"]), {"decision"})
        self.assertEqual(revised["required"], ["decision", "bid_date", "approval_date"])
        self.assertEqual(revised["properties"]["bid_date"]["type"], ["string", "null"])
        self.assertEqual(
            revised["properties"]["approval_date"]["type"], ["string", "null"]
        )
        json.dumps(revised, allow_nan=False)

    def test_unknowns_duplicates_and_wrong_dates_are_explicit(self):
        rows = design.schedule()[:4]
        receipts = {
            rows[0]["id"]: {"status": "valid", "answer": {"decision": "violation"}},
            rows[1]["id"]: {"status": "invalid", "answer": None},
            rows[2]["id"]: {"status": "operational", "answer": None},
            rows[3]["id"]: {
                "status": "valid",
                "answer": {
                    "decision": "violation",
                    "bid_date": "1900-01-01",
                    "approval_date": "1900-01-02",
                },
            },
        }
        result = design.summarize(rows, receipts)
        self.assertEqual(result["unknown"], 1278)
        revised_cell = result["cells"][rows[3]["variant"]][rows[3]["view"]][
            rows[3]["truth"]
        ][rows[3]["model"]]
        self.assertEqual(revised_cell["status_counts"]["valid"], 1)
        self.assertEqual(revised_cell["date_citations"]["substantive_miss"], 1)
        self.assertEqual(revised_cell["status_counts"]["invalid"], 0)
        with self.assertRaisesRegex(ValueError, "duplicate case id"):
            design.summarize([rows[0], rows[0]], {})
        with self.assertRaisesRegex(ValueError, "receipt has no scheduled case"):
            design.summarize(rows, {"not-scheduled": {"status": "valid", "answer": {}}})

    def test_paired_contrasts_use_pair_clusters(self):
        rows = [row for row in design.schedule() if row["truth"] == "violation"]
        receipts = {
            row["id"]: {
                "status": "valid",
                "answer": {
                    "decision": "violation",
                    **(
                        {
                            "bid_date": row["bid_date"],
                            "approval_date": row["approval_date"],
                        }
                        if row["variant"] == "revised"
                        else {}
                    ),
                },
            }
            for row in rows
        }
        paired = design.summarize(rows, receipts)["paired"]
        model_result = paired["by_model"][design.MODELS[0]]
        self.assertEqual(model_result["short"]["cluster_count"], 40)
        self.assertEqual(model_result["cluttered"]["cluster_count"], 40)
        self.assertEqual(model_result["aggregate"]["paired_count"], 80)
        self.assertEqual(model_result["aggregate"]["cluster_count"], 40)
        self.assertEqual(paired["aggregate"]["paired_count"], 320)
        self.assertEqual(paired["aggregate"]["cluster_count"], 40)
        self.assertEqual(model_result["short"]["delta"], 0.0)
        json.dumps(paired, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
