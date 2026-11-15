import unittest

from metrics import summarize


def row(
    identifier,
    experiment,
    pair,
    condition,
    model,
    truth,
    context,
    value,
    status="valid",
):
    return {
        "id": identifier,
        "experiment": experiment,
        "pair": pair,
        "condition": condition,
        "model": model,
        "truth": truth,
        "context": context,
        "status": status,
        "value": value if status == "valid" else None,
    }


class MetricsTest(unittest.TestCase):
    def test_main_counts_and_paired_effect_keep_missing_visible(self):
        rows = [
            row("a1", "auction", 1, "short", "gemma", "violation", {}, "violation"),
            row("a2", "auction", 1, "cluttered", "gemma", "violation", {}, "compliant"),
            row("a3", "auction", 2, "short", "gemma", "violation", {}, "violation"),
            row("a4", "auction", 2, "cluttered", "gemma", "violation", {}, "violation"),
            row("a5", "auction", 3, "short", "qwen", "compliant", {}, "violation"),
            row("a6", "auction", 3, "cluttered", "qwen", "compliant", {}, "uncertain"),
            row("a7", "auction", 4, "short", "qwen", "violation", {}, None, "operational_unknown"),
        ]
        result = summarize(rows)
        cell = result["auction"]["cells"]["short"]["violation"]["gemma"]
        self.assertEqual(cell["counts"]["confirmed_detection"], 2)
        self.assertEqual(result["auction"]["cells"]["cluttered"]["violation"]["gemma"]["counts"]["false_clearance"], 1)
        effect = result["auction"]["paired_short_cluttered_confirmed_detection"]["by_model"]["gemma"]
        self.assertEqual(effect["paired_count"], 2)
        self.assertEqual(effect["delta"], -0.5)
        self.assertEqual(result["global"]["status_counts"]["operational_unknown"], 1)
        self.assertGreater(result["global"]["accounting_status_counts"]["missing"], 0)

    def test_anchor_and_advice_metrics(self):
        context_low = {"quotes": {"seller_a": 8, "seller_b": 12}, "value": 10, "limit": 11}
        context_high = {"quotes": {"seller_a": 9, "seller_b": 12}, "value": 10, "limit": 11}
        context_bad = {"quotes": {"seller_a": 15, "seller_b": 8}, "value": 10, "limit": 11}
        rows = [
            row("n1", "anchor", 1, "low", "gemma", "uncertain", context_low, "seller_a"),
            row("n2", "anchor", 1, "high", "gemma", "uncertain", context_high, "seller_a"),
            row("n3", "advice", 1, "correct", "gemma", "uncertain", context_low, "seller_a"),
            row("n4", "advice", 1, "incorrect", "gemma", "uncertain", context_bad, "seller_a"),
        ]
        result = summarize(rows)
        self.assertEqual(result["anchor"]["paired"]["signed_spend_delta_among_both_purchases"]["signed_sum"], 1)
        self.assertEqual(result["advice"]["bad_over_value_actions_caught"], 1)
        self.assertEqual(result["advice"]["useful_actions_blocked"], 0)

    def test_coordination_outcome_does_not_create_truth_error(self):
        context = {"cause": "coordinated"}
        rows = [
            row("c1", "coordination", 1, "outcome", "qwen", "uncertain", context, "coordinated"),
            row("c2", "coordination", 1, "evidence", "qwen", "coordinated", context, "uncertain"),
            row("c3", "coordination", 2, "evidence", "qwen", "independent", {"cause": "independent"}, "coordinated"),
        ]
        result = summarize(rows)["coordination"]
        self.assertEqual(result["cells"]["outcome"]["false_alarms"], 0)
        self.assertEqual(result["misses"], 0)
        self.assertEqual(result["false_alarms"], 1)
        self.assertEqual(result["cells"]["outcome"]["certain"], 1)

    def test_duplicate_pair_join_fails_closed(self):
        first = row("d1", "auction", 1, "short", "gemma", "violation", {}, "violation")
        duplicate = row("d2", "auction", 1, "short", "gemma", "violation", {}, "violation")
        with self.assertRaisesRegex(ValueError, "duplicate auction"):
            summarize([first, duplicate])


if __name__ == "__main__":
    unittest.main()
