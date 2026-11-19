"""Offline audit and check-in packet for the BlueDot auction studies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import evidence_cases
import evidence_study
import replay_codex_comparison
import replay_evidence
import study


ROOT = Path(__file__).resolve().parent
SUMMARY_FILES = {
    "local_auction": Path("results/study-01/summary.json"),
    "codex_authorization": Path("results/codex-authorization-01/summary.json"),
    "evidence_recovery": Path("results/evidence-01/metrics.json"),
}


def _case_06(judgments: dict[str, Any]) -> list[dict[str, Any]]:
    cases = [
        case
        for case in evidence_cases.build_cases()
        if case.get("experiment") == "authorization"
        and case.get("family") == "expiry"
        and case.get("pair") == 6
        and case.get("view") == "partial"
    ]
    branches = []
    scheduled = {
        row["case_id"]: row
        for row in evidence_study.initial_schedule()
        if row["model"] == "sol"
    }
    for case in cases:
        row = scheduled.get(case["id"])
        if row is None:
            raise ValueError(f"missing scheduled Sol case: {case['id']}")
        initial_id = row["id"]
        initial = judgments.get(initial_id)
        if initial is None or initial.get("status") != "valid":
            raise ValueError(f"missing valid Sol receipt: {initial_id}")
        child = evidence_study.followup(row, initial["answer"])
        if child is None or child["requested"] != "expiry":
            raise ValueError(f"Sol did not request the decisive expiry field: {initial_id}")
        followup = judgments.get(child["id"])
        if followup is None or followup.get("status") != "valid":
            raise ValueError(f"missing valid Sol lookup receipt: {child['id']}")
        truth = evidence_cases.authorization_oracle(case)
        if followup["answer"]["decision"] != truth:
            raise ValueError(f"Sol's final expiry decision disagrees with the oracle: {child['id']}")
        branches.append(
            {
                "bid": case["visible"]["bid"],
                "seller_a_quote": case["visible"]["bid"]["price"],
                "seller_b_quote": next(
                    event["price"]
                    for event in case["events"]
                    if event.get("kind") == "quote" and event.get("seller") == "seller_b"
                ),
                "expiry": evidence_cases.registry_lookup(case, "expiry")["value"],
                "followup_id": child["id"],
                "followup_answer": followup["answer"],
            }
        )
    if len(branches) != 2:
        raise ValueError(f"expected two expiry branches for pair 06, found {len(branches)}")
    return sorted(branches, key=lambda branch: branch["expiry"])


def audit() -> dict[str, Any]:
    """Recompute the frozen summaries from the checkout that supplies the scorers."""
    local_actual = study.analyze(ROOT / "results/study-01", study.plan_cases())
    codex_actual = replay_codex_comparison.verify_and_score(
        ROOT / "results/codex-authorization-01/judgments.json"
    )
    evidence_dir = ROOT / "results/evidence-01"
    evidence_freeze = study.decode((evidence_dir / "freeze.json").read_bytes())
    evidence_original = study.decode((evidence_dir / "original-freeze.json").read_bytes())
    evidence_records = study.decode((evidence_dir / "judgments.json").read_bytes())
    replay_evidence.verify_lineage(evidence_freeze, evidence_original)
    evidence_actual = replay_evidence.verify_judgments(evidence_freeze, evidence_records)
    actual = {
        "local_auction": local_actual,
        "codex_authorization": codex_actual,
        "evidence_recovery": evidence_actual,
    }
    studies = {}
    for name, relative in SUMMARY_FILES.items():
        raw = (ROOT / relative).read_bytes()
        try:
            expected = study.encode(study.decode(raw))
        except ValueError as exc:
            raise ValueError(f"invalid frozen summary {relative}: {exc}") from exc
        if study.encode(actual[name]) != expected:
            raise ValueError(f"replay differs from frozen summary: {relative}")
        studies[name] = {
            "status": "PASS",
            "summary": relative.as_posix(),
            "canonical_summary_sha256": study.sha(expected),
        }
    return {
        "studies": studies,
        "metrics": actual,
        "case_06": {"branches": _case_06(evidence_records["judgments"])},
    }


def _check_in(result: dict[str, Any]) -> str:
    local = result["studies"]["local_auction"]
    codex = result["studies"]["codex_authorization"]
    evidence = result["studies"]["evidence_recovery"]
    expired, active = result["case_06"]["branches"]
    bid = expired["bid"]
    local_cells = result["metrics"]["local_auction"]["approval"]["cells"]["short"]["violation"].values()
    false_clearances = sum(row["counts"]["false_clearance"] for row in local_cells)
    violation_calls = sum(row["valid"] for row in local_cells)
    comparison = result["metrics"]["codex_authorization"]
    paired = comparison["paired"]["aggregate"]
    recovery = result["metrics"]["evidence_recovery"]["authorization"]
    sol = recovery["by_model"]["sol"]["recovery"]
    rule = recovery["rule_baseline"]["after_one_lookup"]
    return f"""# BlueDot research check-in

## Completed evidence

- **Local authorization study.** The two auditors falsely cleared {false_clearances} of {violation_calls} violating short-log judgments. Source `{local['summary']}`.
- **Four-model prompt comparison.** {comparison['valid']:,} of {comparison['attempted']:,} attempted judgments were usable. {comparison['accounting_status_counts']['operational']} failed operationally. Detection changed by {paired['delta_percentage_points']:g} percentage points over {paired['paired_count']} usable violation comparisons. Source `{codex['summary']}`.
- **Missing-approval evidence.** Sol resolved {sol['count']} of {sol['eligible']} partial views after the decisive lookup. The deterministic check resolved {rule['exact_truth']} of {rule['planned']}. Source `{evidence['summary']}`.

Run `python -S -B research_toolkit.py audit` to verify the three summaries and display their canonical JSON hashes.

## Replayable expiry example

The buyer is choosing between two sellers for a simulated purchase. In pair 06, Seller A quoted **{expired['seller_a_quote']} simulated credits** per unit and Seller B quoted **{expired['seller_b_quote']}**. The recorded bid selects Seller A at simulated minute **{bid['at']}** for a {bid['resource']}, quantity {bid['quantity']}. Sol audited the record. It requested the missing expiry field before deciding whether the bid had permission.

| Registry expiry | Sol's recorded final decision | Interpretation |
| ---: | --- | --- |
| {expired['expiry']} | `{expired['followup_answer']['decision']}` | Approval expires at the bid minute. |
| {active['expiry']} | `{active['followup_answer']['decision']}` | Approval is still active at the bid minute. |

The bids and quotes match. The recorded answers are auditor verdicts on permission to buy. The receipts are `{expired['followup_id']}` and `{active['followup_id']}` in `results/evidence-01/judgments.json`.

## Next planned experiment

The AI buyer will use fixed instructions to bid or pass once per scenario. The study will replay each proposal in two arms and count passes separately.

1. **Baseline.** Ordinary market checks will decide whether the bid executes.
2. **Added execution check.** The simulator will look up missing approval evidence when needed. The lookup will advance the clock by one simulated minute. At commitment it will recheck quote availability, seller scope, expiry and revocation.

The study will measure unauthorized purchases prevented, authorized purchases delayed or lost, best-feasible-offer selection, and buyer surplus from trusted simulated values. Results will be added only after the paired scenarios and response accounting pass their frozen checks.

## Limits

The evidence covers controlled scripted cases with simulated currency. The reusable pieces for a future market test are the event log, actor-visible snapshots, commitment rule, and independent oracle. A new mechanism would need its own validation. The BlueDot submission remains on hold.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "check-in"))
    args = parser.parse_args()
    try:
        result = audit()
        if args.command == "audit":
            print(json.dumps(result["studies"], indent=2, sort_keys=True))
        else:
            print(_check_in(result))
    except (OSError, AssertionError, KeyError, TypeError, ValueError) as exc:
        parser.exit(1, f"Audit failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
