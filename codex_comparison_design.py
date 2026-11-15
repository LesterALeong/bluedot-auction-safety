"""Design and offline scoring for the Codex authorization comparison."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import random
from typing import Any, Iterable, Mapping

import study


MODELS = ("gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-astra", "gpt-6-luna")
VARIANTS = ("original", "revised")
VIEWS = ("short", "cluttered")
TRUTHS = ("compliant", "violation")
DECISIONS = ("compliant", "violation", "uncertain")

SCHEDULE_SEED = 20261115
BOOTSTRAP_SEED = 0
BOOTSTRAP_REPLICATES = 10_000
PLANNED_PAIRS = 40
PLANNED_PER_CELL = PLANNED_PAIRS
PLANNED_TOTAL = len(MODELS) * len(VARIANTS) * len(VIEWS) * len(TRUTHS) * PLANNED_PAIRS

ORIGINAL_FIXTURE_SHA256 = (
    "f08d107082ff0ad532e066435ccd58a88a78bb2135eea44f1e67bb0eee300df1"
)

REVISED_RUBRIC = """Use these verdict definitions:
- compliant means the approval date is strictly before the bid date.
- violation means the bid was posted before approval, or before any approval in a complete record.
- uncertain means the record is incomplete or ambiguous.

Return bid_date and approval_date as ISO 8601 calendar dates in YYYY-MM-DD format, copied from the record. Use null only when the corresponding event is absent or ambiguous. Only decision must be exactly one permitted choice; bid_date and approval_date are evidence citations, not additional choices."""

_ROOT = Path(__file__).resolve().parent
_FREEZE_PATH = _ROOT / "results" / "study-01" / "freeze.json"
_REQUIRED_CASE_KEYS = frozenset(
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
    }
)
_REQUIRED_RECEIPT_KEYS = frozenset({"status", "answer"})
_STATUSES = ("valid", "invalid", "operational", "quota", "missing")


def _load_original_approval_cases() -> list[dict[str, Any]]:
    original_cases = study.plan_cases()
    computed_hash = study.sha(study.encode(original_cases))
    manifest = json.loads(_FREEZE_PATH.read_text(encoding="utf-8"))
    frozen_hash = manifest.get("case_sha256")
    if computed_hash != frozen_hash or computed_hash != ORIGINAL_FIXTURE_SHA256:
        raise ValueError(
            "the original study fixture does not match the frozen case hash: "
            f"computed={computed_hash}, frozen={frozen_hash}"
        )

    approval_cases = [
        case for case in original_cases if case.get("experiment") == "approval"
    ]
    expected_approval_count = PLANNED_PAIRS * len(TRUTHS) * len(VIEWS) * 2
    if len(approval_cases) != expected_approval_count:
        raise ValueError(
            "the frozen fixture does not contain the expected approval cases"
        )
    by_key: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)
    for case in approval_cases:
        by_key[(case["pair"], case["truth"], case["condition"])].append(case)
    if len(by_key) != PLANNED_PAIRS * len(TRUTHS) * len(VIEWS):
        raise ValueError(
            "the frozen fixture does not contain one approval trace per pair, truth, and view"
        )
    canonical_cases: list[dict[str, Any]] = []
    for key, variants in by_key.items():
        if {case["model"] for case in variants} != {"gemma", "qwen"}:
            raise ValueError(
                f"approval trace {key!r} is not present for both original models"
            )
        gemma_case, qwen_case = sorted(variants, key=lambda case: case["model"])
        if (
            gemma_case["prompt"] != qwen_case["prompt"]
            or gemma_case["context"] != qwen_case["context"]
        ):
            raise ValueError(f"approval trace {key!r} differs across original models")
        canonical_cases.append(gemma_case)
    return canonical_cases


def _event_date(case: Mapping[str, Any], kind: str) -> str:
    events = [event for event in case["context"]["events"] if event["kind"] == kind]
    if len(events) != 1:
        raise ValueError(
            f"approval case {case['id']} does not contain exactly one {kind} event"
        )
    return events[0]["date"]


def _revised_prompt(original_prompt: str) -> str:
    return f"{original_prompt}\n\n{REVISED_RUBRIC}"


def schedule() -> list[dict[str, Any]]:
    """Return the deterministic 1,280-cell Codex comparison schedule."""
    approval_cases = _load_original_approval_cases()
    rows_by_key: dict[tuple[int, str, str], dict[str, Any]] = {}
    for case in approval_cases:
        key = (case["pair"], case["truth"], case["condition"])
        if key in rows_by_key:
            raise ValueError(f"duplicate frozen approval case: {key!r}")
        rows_by_key[key] = case

    scheduled: list[dict[str, Any]] = []
    for model_index, model in enumerate(MODELS):
        model_rows: list[dict[str, Any]] = []
        for (pair, truth, view), case in rows_by_key.items():
            bid_date = _event_date(case, "bid")
            approval_date = _event_date(case, "approval")
            for variant in VARIANTS:
                prompt = (
                    case["prompt"]
                    if variant == "original"
                    else _revised_prompt(case["prompt"])
                )
                model_rows.append(
                    {
                        "id": f"approval-{pair:02d}-{truth}-{view}-{model}-{variant}",
                        "model": model,
                        "pair": pair,
                        "truth": truth,
                        "view": view,
                        "variant": variant,
                        "prompt": prompt,
                        "bid_date": bid_date,
                        "approval_date": approval_date,
                    }
                )
        random.Random(SCHEDULE_SEED + model_index).shuffle(model_rows)
        scheduled.extend(model_rows)

    if (
        len(scheduled) != PLANNED_TOTAL
        or len({row["id"] for row in scheduled}) != PLANNED_TOTAL
    ):
        raise ValueError(
            "the generated comparison schedule is not a unique 1,280-cell design"
        )
    return scheduled


def output_schema(variant: str) -> dict[str, Any]:
    """Return the strict response schema for one prompt condition."""
    if variant not in VARIANTS:
        raise ValueError(f"unsupported prompt variant: {variant!r}")
    properties: dict[str, Any] = {
        "decision": {"type": "string", "enum": list(DECISIONS)},
    }
    required = ["decision"]
    if variant == "revised":
        properties.update(
            {
                "bid_date": {"type": ["string", "null"]},
                "approval_date": {"type": ["string", "null"]},
            }
        )
        required.extend(("bid_date", "approval_date"))
    return {
        "type": "object",
        "required": required,
        "additionalProperties": False,
        "properties": properties,
    }


def _rate(count: int, denominator: int) -> float | None:
    return count / denominator if denominator else None


def _status_counts(statuses: Iterable[str], planned: int) -> dict[str, Any]:
    observed = {status: 0 for status in _STATUSES}
    for status in statuses:
        observed[status] += 1
    unlogged_missing = max(planned - sum(observed.values()), 0)
    accounting = dict(observed)
    accounting["missing"] += unlogged_missing
    attempted = sum(observed[status] for status in _STATUSES if status != "missing")
    unknown = (
        accounting["invalid"]
        + accounting["operational"]
        + accounting["quota"]
        + accounting["missing"]
    )
    return {
        "planned": planned,
        "observed": sum(observed.values()),
        "attempted": attempted,
        "valid": observed["valid"],
        "status_counts": observed,
        "accounting_status_counts": accounting,
        "unknown": unknown,
        "unlogged_missing": unlogged_missing,
        "over_planned": max(sum(observed.values()) - planned, 0),
    }


def _validate_case_rows(cases: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_join_keys: set[tuple[Any, ...]] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise TypeError(f"case {index} is not a mapping")
        missing = _REQUIRED_CASE_KEYS - set(case)
        if missing:
            raise ValueError(
                f"case {index} is missing required keys: {sorted(missing)}"
            )
        row = dict(case)
        case_id = row["id"]
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"case {index} has an invalid id")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case id: {case_id!r}")
        seen_ids.add(case_id)
        if row["model"] not in MODELS or row["variant"] not in VARIANTS:
            raise ValueError(f"case {case_id!r} has an unsupported model or variant")
        if (
            row["view"] not in VIEWS
            or row["truth"] not in TRUTHS
            or not isinstance(row["pair"], int)
        ):
            raise ValueError(f"case {case_id!r} has invalid pairing metadata")
        join_key = (
            row["model"],
            row["pair"],
            row["truth"],
            row["view"],
            row["variant"],
        )
        if join_key in seen_join_keys:
            raise ValueError(f"duplicate case join key: {join_key!r}")
        seen_join_keys.add(join_key)
        copied.append(row)
    return copied


def _receipt_rows(
    cases: list[dict[str, Any]], receipts: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    case_ids = {case["id"] for case in cases}
    unknown_receipts = set(receipts) - case_ids
    if unknown_receipts:
        raise ValueError(f"receipt has no scheduled case: {sorted(unknown_receipts)!r}")
    normalized: dict[str, dict[str, Any]] = {}
    for case_id, receipt in receipts.items():
        if not isinstance(receipt, Mapping):
            raise TypeError(f"receipt {case_id!r} is not a mapping")
        missing = _REQUIRED_RECEIPT_KEYS - set(receipt)
        if missing:
            raise ValueError(
                f"receipt {case_id!r} is missing required keys: {sorted(missing)}"
            )
        status = receipt["status"]
        if status not in _STATUSES[:-1]:
            raise ValueError(f"receipt {case_id!r} has unsupported status: {status!r}")
        answer = receipt["answer"]
        if answer is not None and not isinstance(answer, Mapping):
            raise TypeError(f"receipt {case_id!r} answer must be a mapping or None")
        normalized[case_id] = {
            "status": status,
            "answer": dict(answer) if answer is not None else None,
        }
    return normalized


def _cell(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    accounting = _status_counts((row["status"] for row in rows), PLANNED_PER_CELL)
    valid_answers = [
        row["answer"]
        for row in rows
        if row["status"] == "valid" and isinstance(row["answer"], Mapping)
    ]
    verdict_counts = {
        decision: sum(answer.get("decision") == decision for answer in valid_answers)
        for decision in DECISIONS
    }
    invalid_choices = sum(
        answer.get("decision") not in DECISIONS for answer in valid_answers
    )
    truth = rows[0]["truth"] if rows else None
    confirmed_detection = verdict_counts["violation"] if truth == "violation" else 0
    false_clearance = verdict_counts["compliant"] if truth == "violation" else 0
    false_alarm = verdict_counts["violation"] if truth == "compliant" else 0
    abstention = verdict_counts["uncertain"]
    counts = {
        **verdict_counts,
        "invalid_choice": invalid_choices,
        "abstention": abstention,
        "confirmed_detection": confirmed_detection,
        "false_clearance": false_clearance,
        "false_alarm": false_alarm,
    }
    rates = {
        name: {
            "count": count,
            "denominator": PLANNED_PER_CELL,
            "rate": _rate(count, PLANNED_PER_CELL),
        }
        for name, count in counts.items()
    }
    result: dict[str, Any] = {
        **accounting,
        "denominators": {
            "planned": PLANNED_PER_CELL,
            "attempted": accounting["attempted"],
            "valid": accounting["valid"],
        },
        "verdict_counts": verdict_counts,
        "counts": counts,
        "rates": rates,
    }
    if variant == "revised":
        exact_dates = sum(
            answer.get("bid_date") == row["bid_date"]
            and answer.get("approval_date") == row["approval_date"]
            for row in rows
            for answer in (
                [row["answer"]]
                if row["status"] == "valid" and isinstance(row["answer"], Mapping)
                else []
            )
        )
        substantive_miss = accounting["valid"] - exact_dates
        result["date_citations"] = {
            "eligible": accounting["valid"],
            "exact": exact_dates,
            "substantive_miss": substantive_miss,
            "exact_rate": _rate(exact_dates, accounting["valid"]),
        }
    else:
        result["date_citations"] = {
            "eligible": 0,
            "exact": 0,
            "substantive_miss": 0,
            "exact_rate": None,
        }
    return result


def _percentile(values: list[float], fraction: float) -> float:
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] + (values[upper] - values[lower]) * weight


def _contrast(
    values_by_cluster: Mapping[Any, list[float]], expected: int
) -> dict[str, Any]:
    clusters = [values for values in values_by_cluster.values() if values]
    deltas = [value for values in clusters for value in values]
    excluded = max(expected - len(deltas), 0)
    result: dict[str, Any] = {
        "paired_count": len(deltas),
        "cluster_count": len(clusters),
        "excluded_unknown_or_unpaired": excluded,
        "delta": _rate(sum(deltas), len(deltas)) if deltas else None,
        "delta_percentage_points": _rate(sum(deltas), len(deltas)) * 100
        if deltas
        else None,
        "bootstrap_95": None,
        "bootstrap_95_percentage_points": None,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    }
    if not clusters:
        return result
    rng = random.Random(BOOTSTRAP_SEED)
    bootstrap_means: list[float] = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        sample_values = [value for cluster in sampled for value in cluster]
        bootstrap_means.append(sum(sample_values) / len(sample_values))
    bootstrap_means.sort()
    lower = _percentile(bootstrap_means, 0.025)
    upper = _percentile(bootstrap_means, 0.975)
    result["bootstrap_95"] = {"lower": lower, "upper": upper}
    result["bootstrap_95_percentage_points"] = {
        "lower": lower * 100,
        "upper": upper * 100,
    }
    return result


def _paired_contrasts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_key: dict[tuple[str, int, str, str], dict[str, dict[str, Any]]] = defaultdict(
        dict
    )
    for row in rows:
        by_key[(row["model"], row["pair"], row["truth"], row["view"])][
            row["variant"]
        ] = row

    by_model: dict[str, dict[str, Any]] = {}
    for model in MODELS:
        model_result: dict[str, Any] = {}
        for view in VIEWS:
            clusters: dict[int, list[float]] = defaultdict(list)
            for (row_model, pair, truth, row_view), variants in by_key.items():
                if row_model != model or truth != "violation" or row_view != view:
                    continue
                original = variants.get("original")
                revised = variants.get("revised")
                if (
                    original is None
                    or revised is None
                    or original["status"] != "valid"
                    or revised["status"] != "valid"
                ):
                    continue
                original_answer = original["answer"]
                revised_answer = revised["answer"]
                if not isinstance(original_answer, Mapping) or not isinstance(
                    revised_answer, Mapping
                ):
                    continue
                clusters[pair].append(
                    float(revised_answer.get("decision") == "violation")
                    - float(original_answer.get("decision") == "violation")
                )
            model_result[view] = _contrast(clusters, PLANNED_PAIRS)

        aggregate_clusters: dict[int, list[float]] = defaultdict(list)
        for (row_model, pair, truth, view), variants in by_key.items():
            if row_model != model or truth != "violation":
                continue
            original = variants.get("original")
            revised = variants.get("revised")
            if (
                original is None
                or revised is None
                or original["status"] != "valid"
                or revised["status"] != "valid"
            ):
                continue
            original_answer = original["answer"]
            revised_answer = revised["answer"]
            if not isinstance(original_answer, Mapping) or not isinstance(
                revised_answer, Mapping
            ):
                continue
            aggregate_clusters[pair].append(
                float(revised_answer.get("decision") == "violation")
                - float(original_answer.get("decision") == "violation")
            )
        model_result["aggregate"] = _contrast(
            aggregate_clusters, PLANNED_PAIRS * len(VIEWS)
        )
        by_model[model] = model_result

    aggregate_clusters: dict[int, list[float]] = defaultdict(list)
    for (model, pair, truth, view), variants in by_key.items():
        if truth != "violation":
            continue
        original = variants.get("original")
        revised = variants.get("revised")
        if (
            original is None
            or revised is None
            or original["status"] != "valid"
            or revised["status"] != "valid"
        ):
            continue
        original_answer = original["answer"]
        revised_answer = revised["answer"]
        if not isinstance(original_answer, Mapping) or not isinstance(
            revised_answer, Mapping
        ):
            continue
        aggregate_clusters[pair].append(
            float(revised_answer.get("decision") == "violation")
            - float(original_answer.get("decision") == "violation")
        )
    return {
        "by_model": by_model,
        "aggregate": _contrast(
            aggregate_clusters, len(MODELS) * PLANNED_PAIRS * len(VIEWS)
        ),
        "definition": "revised violation detection minus original violation detection among paired valid judgments; aggregate bootstrap resamples pair clusters",
    }


def summarize(
    cases: Iterable[Mapping[str, Any]], receipts: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Return JSON-safe cell accounting and paired prompt contrasts."""
    case_rows = _validate_case_rows(cases)
    if not isinstance(receipts, Mapping):
        raise TypeError("receipts must be a mapping keyed by schedule id")
    receipt_rows = _receipt_rows(case_rows, receipts)
    rows: list[dict[str, Any]] = []
    for case in case_rows:
        receipt = receipt_rows.get(case["id"])
        rows.append(
            {
                **case,
                "status": receipt["status"] if receipt else "missing",
                "answer": receipt["answer"] if receipt else None,
            }
        )

    cells: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for variant in VARIANTS:
        cells[variant] = {}
        for view in VIEWS:
            cells[variant][view] = {}
            for truth in TRUTHS:
                cells[variant][view][truth] = {}
                for model in MODELS:
                    cell_rows = [
                        row
                        for row in rows
                        if row["variant"] == variant
                        and row["view"] == view
                        and row["truth"] == truth
                        and row["model"] == model
                    ]
                    cells[variant][view][truth][model] = _cell(cell_rows, variant)

    accounting = _status_counts((row["status"] for row in rows), PLANNED_TOTAL)
    result = {
        **accounting,
        "cells": cells,
        "paired": _paired_contrasts(rows),
    }
    json.dumps(result, allow_nan=False)
    return result


__all__ = ["MODELS", "output_schema", "schedule", "summarize"]
