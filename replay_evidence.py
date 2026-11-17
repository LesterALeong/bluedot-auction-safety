"""Verify the frozen evidence design and replay normalized verdicts offline."""

import argparse
from pathlib import Path

from evidence_cases import build_cases, validate_fixture
from evidence_study import followup, initial_schedule, summarize, valid_answer
from study import decode, encode, sha


ROOT = Path(__file__).resolve().parent
DESIGN_FILES = ("EVIDENCE_PROTOCOL.md", "auction.py", "study.py", "evidence_cases.py",
                "evidence_study.py", "replay_evidence.py")
LOOKUP_FIELDS = ("scope", "expiry", "revocation")
STATUSES = {"valid", "invalid", "operational", "quota"}


def row_digest(row):
    return sha(encode(row))


def frozen_design():
    cases = build_cases()
    validate_fixture(cases)
    scheduled = initial_schedule()
    initial = {row["id"]: row_digest(row) for row in scheduled}
    possible = {}
    for row in scheduled:
        for field in LOOKUP_FIELDS:
            child = followup(row, {"decision": "review", "lookup": field})
            if child is not None:
                possible[child["id"]] = row_digest(child)
    if (len(scheduled), len(initial), len(possible)) != (120, 120, 144):
        raise ValueError("request schedule does not match the registered design")
    return {
        "source_sha256": {name: sha((ROOT / name).read_text(encoding="utf-8").encode("utf-8"))
                          for name in DESIGN_FILES},
        "fixture_sha256": sha(encode(cases)),
        "initial_order": [row["id"] for row in scheduled],
        "initial": initial,
        "possible_followups": possible,
    }


def eligible_rows(judgments):
    rows = {}
    for row in initial_schedule():
        rows[row["id"]] = row
        receipt = judgments.get(row["id"], {})
        if receipt.get("status") == "valid":
            child = followup(row, receipt["answer"])
            if child is not None:
                rows[child["id"]] = child
    return rows


def verify_judgments(freeze, evidence):
    if freeze["design"] != frozen_design():
        raise ValueError("frozen design does not match checked-out source and cases")
    if evidence["freeze_sha256"] != sha(encode(freeze)):
        raise ValueError("judgments do not bind to this freeze")
    judgments = evidence["judgments"]
    if len(judgments) > 168:
        raise ValueError("study request cap exceeded")
    rows = eligible_rows(judgments)
    for request_id, receipt in judgments.items():
        if request_id not in rows or receipt["request_sha256"] != row_digest(rows[request_id]):
            raise ValueError(f"unscheduled or mismatched request {request_id}")
        status, answer = receipt["status"], receipt["answer"]
        if status not in STATUSES or (status == "valid" and not valid_answer(rows[request_id], answer)):
            raise ValueError(f"inconsistent receipt {request_id}")
        if status != "valid" and answer is not None:
            raise ValueError(f"inconsistent receipt {request_id}")
    return summarize(judgments)


def verify_lineage(freeze, original):
    """A source rebinding must leave every frozen case and request unchanged."""
    if freeze["original_freeze_sha256"] != sha(encode(original)):
        raise ValueError("original execution freeze digest does not match")
    if freeze["configuration"] != original["configuration"]:
        raise ValueError("runtime configuration differs from the original freeze")
    keys = set(freeze["design"]) - {"source_sha256"}
    if keys != set(original["design"]) - {"source_sha256"} or any(
        freeze["design"][key] != original["design"][key] for key in keys
    ):
        raise ValueError("fixture or request changed from the original freeze")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    freeze = decode((args.directory / "freeze.json").read_bytes())
    if "original_freeze_sha256" in freeze:
        verify_lineage(freeze, decode((args.directory / "original-freeze.json").read_bytes()))
    evidence = decode((args.directory / "judgments.json").read_bytes())
    summary = verify_judgments(freeze, evidence)
    if summary != decode((args.directory / "metrics.json").read_bytes()):
        raise ValueError("recorded metrics do not match the recomputed metrics")
    print(f"Replayed {len(evidence['judgments'])} recorded judgments against the frozen design.")


if __name__ == "__main__":
    main()
