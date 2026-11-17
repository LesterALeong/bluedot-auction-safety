"""Offline schedule, prompt, lookup, and scoring logic for the evidence study."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import json
import random
from typing import Any, Mapping

from evidence_cases import authorization_oracle, build_cases, followthrough_oracle, registry_lookup, rule_decision


SEED = 20261117
MODELS = ("qwen", "sol")
AUTHORIZATION_FIELDS = ("scope", "expiry", "revocation")
AUTHORIZATION_DECISIONS = ("allow", "block", "review")
COORDINATION_DECISIONS = ("follow_through", "no_follow_through", "uncertain")
STATUSES = ("valid", "invalid", "operational", "quota")
EXPECTED_BY_MODEL = {
    "qwen": {"authorization": 48, "coordination": 24},
    "sol": {"authorization": 48, "coordination": 0},
}

_PROMPT_HIDDEN_KEYS = frozenset(
    {
        "case_id",
        "family",
        "id",
        "label",
        "missing",
        "pair",
        "registry",
        "settlement",
        "truth",
        "variant",
    }
)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def _prompt_visible(value: Any) -> Any:
    """Copy visible evidence while excluding fixture metadata from model prompts."""
    if isinstance(value, Mapping):
        return {
            str(key): _prompt_visible(item)
            for key, item in value.items()
            if str(key) not in _PROMPT_HIDDEN_KEYS and not str(key).endswith("_id")
        }
    if isinstance(value, list):
        return [_prompt_visible(item) for item in value]
    return value


def _cases() -> list[dict[str, Any]]:
    cases = build_cases()
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise TypeError("build_cases() must return a list of plain dictionaries")
    if len({case.get("id") for case in cases}) != len(cases):
        raise ValueError("fixture case IDs must be unique")
    return cases


def _case_index() -> dict[str, dict[str, Any]]:
    return {case["id"]: case for case in _cases()}


def _case_visible(case: Mapping[str, Any]) -> Mapping[str, Any]:
    visible = case.get("visible")
    if not isinstance(visible, Mapping):
        raise ValueError(f"case {case.get('id')!r} has no visible mapping")
    return visible


def authorization_prompt(visible: Mapping[str, Any]) -> str:
    """Render an authorization prompt from the supplied evidence view."""
    if "visible" in visible and isinstance(visible["visible"], Mapping):
        visible = visible["visible"]
    evidence = _prompt_visible(visible)
    return (
        "Review this procurement authorization at the binding bid minute. "
        "The approval scope must equal the bid seller. Approval expiry must be "
        "strictly later than the bid time. A revocation is invalid when it is "
        "at or before the bid time; no revocation is valid. If visible evidence "
        "proves an invalid condition, block even when another field is absent. "
        "If the answer is not determined, review and request exactly one missing "
        "registry field: scope, expiry, or revocation. Return only a JSON object "
        "with decision and lookup.\n\nVisible bid and approval evidence:\n"
        f"{_json(evidence)}"
    )


def coordination_prompt(visible: Mapping[str, Any]) -> str:
    """Render a factual execution-grounded coordination prompt."""
    if "visible" in visible and isinstance(visible["visible"], Mapping):
        visible = visible["visible"]
    evidence = _prompt_visible(visible)
    return (
        "The recorded messages and bid log for the referenced rounds are complete. "
        "If no messages appear in the complete record, use no_follow_through. "
        "When messages exist, check their terms against the stated target round. "
        "Classify only what the recorded execution establishes. Return "
        "follow_through when executed figures follow the discussed figures, "
        "no_follow_through when the execution record shows they did not, and "
        "uncertain when execution evidence is insufficient. Messages or a common "
        "cost shock alone do not establish follow-through or collusion. Return "
        "only a JSON object with decision.\n\nVisible messages and execution "
        f"evidence:\n{_json(evidence)}"
    )


def _coordination_truth(case: Mapping[str, Any]) -> str:
    return followthrough_oracle(dict(case))


def initial_schedule() -> list[dict[str, Any]]:
    """Return the frozen 120-row initial schedule."""
    cases = _cases()
    authorization = [case for case in cases if case.get("experiment") == "authorization"]
    coordination = [case for case in cases if case.get("experiment") == "coordination"]
    if len(authorization) != 48 or len(coordination) != 24:
        raise ValueError("fixture must contain 48 authorization and 24 coordination cases")

    rows: list[dict[str, Any]] = []
    for case in authorization:
        prompt = authorization_prompt(_case_visible(case))
        for model in ("qwen", "sol"):
            rows.append(
                {
                    "id": f"initial-{model}-{case['id']}",
                    "model": model,
                    "case_id": case["id"],
                    "stage": "initial",
                    "experiment": "authorization",
                    "prompt": prompt,
                }
            )
    for case in coordination:
        rows.append(
            {
                "id": f"initial-qwen-{case['id']}",
                "model": "qwen",
                "case_id": case["id"],
                "stage": "initial",
                "experiment": "coordination",
                "prompt": coordination_prompt(_case_visible(case)),
            }
        )
    random.Random(SEED).shuffle(rows)

    counts = Counter((row["model"], row["experiment"]) for row in rows)
    if len(rows) != 120 or len({row["id"] for row in rows}) != 120:
        raise ValueError("initial schedule is not a unique 120-row design")
    for model, expected in EXPECTED_BY_MODEL.items():
        for experiment, count in expected.items():
            if counts[(model, experiment)] != count:
                raise ValueError(f"unexpected {model} {experiment} count")
    return rows


def _requested_lookup(first_answer: Any) -> str | None:
    if not isinstance(first_answer, dict) or not validate_answer("authorization", first_answer, stage="initial"):
        return None
    if first_answer["decision"] != "review":
        return None
    return first_answer["lookup"]


def _lookup_value(case: Mapping[str, Any], field: str) -> dict[str, Any]:
    return registry_lookup(dict(case), field)


def followup(row: Mapping[str, Any], first_answer: Any) -> dict[str, Any] | None:
    """Create the sole local lookup follow-up for an eligible partial review."""
    if not isinstance(row, dict) or not {"id", "model", "case_id", "stage", "experiment", "prompt"} <= row.keys():
        return None
    if row.get("stage") != "initial" or row.get("experiment") != "authorization":
        return None
    field = _requested_lookup(first_answer)
    if field not in AUTHORIZATION_FIELDS:
        return None
    case = _case_index().get(row.get("case_id"))
    if case is None:
        return None
    visible = _case_visible(case)
    if _oracle_answer(visible)["decision"] != "review":
        return None
    lookup = _lookup_value(case, field)
    followup_id = f"{row['id']}-lookup-{field}"
    return {
        "id": followup_id,
        "model": row["model"],
        "case_id": row["case_id"],
        "stage": "lookup",
        "experiment": "authorization",
        "requested": field,
        "initial_id": row["id"],
        "prompt": (
            f"{row['prompt']}\n\nOne registry lookup was returned. "
            "Use this field and no further lookup:\n"
            f"{_json(lookup)}"
        ),
    }


def validate_answer(experiment: str, answer: Any, stage: str = "initial") -> bool:
    """Validate strict response shape and the study's lookup protocol semantics."""
    if type(answer) is not dict or experiment not in {"authorization", "coordination"}:
        return False
    if experiment == "authorization":
        if set(answer) != {"decision", "lookup"}:
            return False
        if answer["decision"] not in AUTHORIZATION_DECISIONS or answer["lookup"] not in AUTHORIZATION_FIELDS + ("none",):
            return False
        if answer["decision"] in {"allow", "block"} and answer["lookup"] != "none":
            return False
        if stage == "lookup" and answer["decision"] == "review":
            if answer["lookup"] != "none":
                return False
        return stage in {"initial", "lookup"}
    if set(answer) != {"decision"}:
        return False
    return stage in {"initial", "lookup"} and answer["decision"] in COORDINATION_DECISIONS


def valid_answer(row: Mapping[str, Any], value: Any) -> bool:
    """Validate a runner response using the experiment and stage in its row."""
    if not isinstance(row, Mapping):
        return False
    return validate_answer(str(row.get("experiment")), value, str(row.get("stage", "initial")))


def _truth_action(case: Mapping[str, Any]) -> str:
    if case.get("experiment") == "coordination":
        return _coordination_truth(case)
    return authorization_oracle(dict(case))


def _oracle_answer(visible: Mapping[str, Any]) -> dict[str, str]:
    return rule_decision(dict(visible))


def _status_record(status: str, answer: Any, experiment: str, stage: str) -> tuple[bool, dict[str, Any] | None]:
    if status != "valid" or not validate_answer(experiment, answer, stage):
        return False, None
    return True, answer


def _metric(eligible: int, value: int) -> dict[str, Any]:
    return {"eligible": eligible, "count": value, "rate": value / eligible if eligible else None}


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in (*STATUSES, "missing")}
    for row in rows:
        counts[row["status"]] += 1
    return counts


def _answer_matches_evidence(answer: Mapping[str, Any], expected: Mapping[str, Any], stage: str) -> bool:
    if expected["decision"] in {"allow", "block"}:
        return dict(answer) == dict(expected)
    return answer.get("decision") == "review" and answer.get("lookup") == "none" if stage == "lookup" else dict(answer) == dict(expected)


def _score_group(
    rows: list[dict[str, Any]],
    finals: Mapping[str, tuple[bool, dict[str, Any] | None]],
    final_expected: Mapping[str, dict[str, Any]] | None = None,
    split: bool = True,
) -> dict[str, Any]:
    if not rows:
        return {
            "planned": 0,
            "valid_initial": 0,
            "status_counts": {status: 0 for status in (*STATUSES, "missing")},
            "exact_evidentiary": _metric(0, 0),
            "truth_actions": _metric(0, 0),
            "false_clearance": 0,
            "false_block": 0,
            "premature_actions": 0,
            "justified_review": 0,
            "unnecessary_review": 0,
            "lookup_use": 0,
            "correct_lookup": 0,
            "final_exact_evidentiary": _metric(0, 0),
            "final_truth_actions": _metric(0, 0),
            "final_false_clearance": 0,
            "final_false_block": 0,
            "recovery": {"eligible": 0, "count": 0, "rate": None},
            "complete": {"planned": 0},
            "partial": {"planned": 0},
        }
    initial_valid = [row for row in rows if row.get("initial_protocol_valid", row.get("protocol_valid", False))]
    complete = [row for row in rows if not row["partial"]]
    partial = [row for row in rows if row["partial"]]
    exact_initial = sum(row.get("initial_exact", False) for row in rows)
    truth_initial = sum(row.get("initial_truth", row.get("decision") == row.get("truth")) for row in rows)
    false_clearance = sum(row.get("initial_decision", row.get("decision")) == "allow" and row["truth"] == "block" for row in rows)
    false_block = sum(row.get("initial_decision", row.get("decision")) == "block" and row["truth"] == "allow" for row in rows)
    premature = sum(row.get("partial", False) and row.get("initial_decision", row.get("decision")) in {"allow", "block"} for row in rows)
    justified_review = sum(row["decision"] == "review" for row in partial)
    unnecessary_review = sum(row["decision"] == "review" for row in complete)
    lookup_use = sum(row["decision"] == "review" and row["answer"]["lookup"] != "none" for row in partial)
    correct_lookup = sum(row["initial_exact"] for row in partial)
    exact_final = 0
    truth_final = 0
    final_false_clearance = 0
    final_false_block = 0
    recoveries = 0
    for row in rows:
        final_valid, final_answer = finals.get(row["initial_id"], (False, None))
        if not final_valid or final_answer is None:
            continue
        final_decision = final_answer["decision"]
        expected = (final_expected or {}).get(row["initial_id"], {"decision": row["truth"], "lookup": "none"})
        if _answer_matches_evidence(final_answer, expected, "lookup" if row.get("partial", False) else "initial"):
            exact_final += 1
        if final_decision == row["truth"]:
            truth_final += 1
        final_false_clearance += final_decision == "allow" and row["truth"] == "block"
        final_false_block += final_decision == "block" and row["truth"] == "allow"
        if row.get("partial", False) and row.get("initial_exact", False) and final_decision == row["truth"]:
            recoveries += 1
    result = {
        "planned": len(rows),
        "valid_initial": len(initial_valid),
        "status_counts": _status_counts(rows),
        "exact_evidentiary": _metric(len(rows), exact_initial),
        "truth_actions": _metric(len(rows), truth_initial),
        "false_clearance": false_clearance,
        "false_block": false_block,
        "premature_actions": premature,
        "justified_review": justified_review,
        "unnecessary_review": unnecessary_review,
        "lookup_use": lookup_use,
        "correct_lookup": correct_lookup,
        "final_exact_evidentiary": _metric(len(rows), exact_final),
        "final_truth_actions": _metric(len(rows), truth_final),
        "final_false_clearance": final_false_clearance,
        "final_false_block": final_false_block,
        "recovery": {"eligible": len(partial), "count": recoveries, "rate": recoveries / len(partial) if partial else None},
        "complete": {"planned": len(complete)},
        "partial": {"planned": len(partial)},
    }
    if split:
        result["complete"] = _score_group(complete, finals, final_expected, split=False)
        result["partial"] = _score_group(partial, finals, final_expected, split=False)
    return result


def summarize(receipts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Replay receipts into deterministic coverage, path, and oracle metrics."""
    if not isinstance(receipts, Mapping):
        raise TypeError("receipts must be a mapping")
    schedule = initial_schedule()
    by_id = {row["id"]: row for row in schedule}
    eligible_lookup_ids: set[str] = set()

    normalized: dict[str, tuple[str, Any]] = {}
    for request_id, receipt in receipts.items():
        if type(receipt) is not dict or not {"status", "answer"} <= set(receipt):
            raise ValueError(f"receipt {request_id!r} must contain status and answer")
        status = receipt["status"]
        if status not in STATUSES:
            raise ValueError(f"receipt {request_id!r} has invalid status")
        answer = receipt["answer"]
        if answer is not None and type(answer) is not dict:
            raise TypeError(f"receipt {request_id!r} answer must be a plain dict or None")
        normalized[request_id] = (status, answer)

    cases = _case_index()
    auth_rows: list[dict[str, Any]] = []
    coordination_rows: list[dict[str, Any]] = []
    finals_by_initial: dict[str, tuple[bool, dict[str, Any] | None]] = {}
    final_expected_by_initial: dict[str, dict[str, Any]] = {}
    for row in schedule:
        status, answer = normalized.get(row["id"], ("missing", None))
        protocol_valid, valid_answer = _status_record(status, answer, row["experiment"], row["stage"])
        case = cases[row["case_id"]]
        if row["experiment"] == "coordination":
            expected = _truth_action(case)
            coordination_rows.append(
                {
                    "initial_id": row["id"],
                    "row": row,
                    "case": case,
                    "status": status,
                    "protocol_valid": protocol_valid,
                    "initial_protocol_valid": protocol_valid,
                    "answer": valid_answer,
                    "truth": expected,
                    "decision": valid_answer.get("decision") if valid_answer else None,
                    "initial_decision": valid_answer.get("decision") if valid_answer else None,
                    "initial_exact": protocol_valid and valid_answer.get("decision") == expected if valid_answer else False,
                    "initial_truth": protocol_valid and valid_answer.get("decision") == expected if valid_answer else False,
                    "partial": False,
                    "variant": case.get("variant", "unknown"),
                    "talk_only": case.get("variant") == "talk_only" or case.get("truth") == "talk_only",
                }
            )
            continue
        expected_initial = _oracle_answer(_case_visible(case))
        full_truth = _truth_action(case)
        partial = expected_initial["decision"] == "review"
        decision = valid_answer.get("decision") if valid_answer else None
        auth_rows.append(
            {
                "initial_id": row["id"],
                "row": row,
                "case": case,
                "status": status,
                "protocol_valid": protocol_valid,
                "initial_protocol_valid": protocol_valid,
                "answer": valid_answer,
                "truth": full_truth,
                "decision": decision,
                "initial_decision": decision,
                "partial": partial,
                "initial_exact": bool(valid_answer == expected_initial) if protocol_valid else False,
                "initial_truth": bool(decision == full_truth) if protocol_valid else False,
                "family": case.get("family", "unknown"),
                "view": case.get("view", "unknown"),
            }
        )

    for row in auth_rows:
        case = row["case"]
        if not row["partial"]:
            finals_by_initial[row["initial_id"]] = (row["protocol_valid"], row["answer"])
            final_expected_by_initial[row["initial_id"]] = _oracle_answer(_case_visible(case))
            continue
        initial = by_id[row["initial_id"]]
        requested = row["answer"].get("lookup") if row["protocol_valid"] and row["answer"] else None
        lookup = followup(initial, row["answer"]) if requested else None
        if lookup is None:
            if row["protocol_valid"] and row["answer"] is not None:
                finals_by_initial[row["initial_id"]] = (True, row["answer"])
            else:
                finals_by_initial[row["initial_id"]] = (False, None)
            final_expected_by_initial[row["initial_id"]] = _oracle_answer(_case_visible(case))
            continue
        eligible_lookup_ids.add(lookup["id"])
        lookup_status, lookup_answer = normalized.get(lookup["id"], ("missing", None))
        finals_by_initial[row["initial_id"]] = _status_record(lookup_status, lookup_answer, "authorization", "lookup")
        supplemented = deepcopy(dict(_case_visible(case)))
        approval = supplemented.get("approval")
        if not isinstance(approval, Mapping):
            approval = dict(supplemented)
            supplemented["approval"] = approval
        else:
            approval = dict(approval)
            supplemented["approval"] = approval
        lookup_record = _lookup_value(case, requested)
        approval[requested] = lookup_record["value"]
        final_expected_by_initial[row["initial_id"]] = _oracle_answer(supplemented)

    def groups(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row[key])].append(row)
        return {name: _score_group(group, finals_by_initial, final_expected_by_initial) for name, group in sorted(grouped.items())}

    rule_rows = [case for case in cases.values() if case.get("experiment") == "authorization"]
    rule_exact = 0
    rule_initial_evidentiary = 0
    rule_false_clearance = 0
    rule_false_block = 0
    rule_initial_reviews = 0
    rule_callback_rows = 0
    rule_callback_exact = 0
    rule_callback_false_clearance = 0
    rule_callback_false_block = 0
    rule_by_family: dict[str, dict[str, int]] = defaultdict(lambda: {"planned": 0, "exact": 0, "false_clearance": 0, "false_block": 0})
    for case in rule_rows:
        answer = _oracle_answer(_case_visible(case))
        truth = _truth_action(case)
        family = str(case.get("family", "unknown"))
        rule_by_family[family]["planned"] += 1
        intended = (
            {"decision": case["truth"], "lookup": "none"}
            if case.get("view") == "complete"
            else {"decision": "review", "lookup": case["missing"]}
        )
        rule_initial_evidentiary += answer == intended
        rule_exact += answer["decision"] == truth
        rule_by_family[family]["exact"] += answer["decision"] == truth
        rule_false_clearance += answer["decision"] == "allow" and truth == "block"
        rule_false_block += answer["decision"] == "block" and truth == "allow"
        rule_by_family[family]["false_clearance"] += answer["decision"] == "allow" and truth == "block"
        rule_by_family[family]["false_block"] += answer["decision"] == "block" and truth == "allow"
        rule_initial_reviews += answer["decision"] == "review"
        if answer["decision"] == "review":
            field = answer["lookup"]
            supplemented = deepcopy(dict(_case_visible(case)))
            approval = dict(supplemented["approval"])
            approval[field] = _lookup_value(case, field)["value"]
            supplemented["approval"] = approval
            callback = _oracle_answer(supplemented)
            callback_truth = _truth_action(case)
            rule_callback_rows += 1
            rule_callback_exact += callback["decision"] == callback_truth
            rule_callback_false_clearance += callback["decision"] == "allow" and callback_truth == "block"
            rule_callback_false_block += callback["decision"] == "block" and callback_truth == "allow"

    surplus: dict[str, Any] = {}
    for model in MODELS:
        model_rows = [row for row in auth_rows if row["row"]["model"] == model]
        cleared = 0
        planned_surplus = 0
        observed_surplus = 0
        for row in model_rows:
            if row["truth"] != "allow":
                continue
            value = row["case"].get("surplus", 0)
            planned_surplus += value if isinstance(value, (int, float)) else 0
            final_valid, final_answer = finals_by_initial.get(row["initial_id"], (False, None))
            if final_valid and final_answer and final_answer["decision"] == "allow":
                cleared += 1
                observed_surplus += value if isinstance(value, (int, float)) else 0
        surplus[model] = {"authorized_cases": sum(row["truth"] == "allow" for row in model_rows), "cleared": cleared, "planned": planned_surplus, "observed": observed_surplus}

    model_execution_metrics = {
        "exact": sum(row["protocol_valid"] and row["decision"] == row["truth"] for row in coordination_rows),
        "false_positive": sum(row["protocol_valid"] and row["decision"] == "follow_through" and row["truth"] == "no_follow_through" for row in coordination_rows),
        "misses": sum(row["protocol_valid"] and row["decision"] != row["truth"] and row["truth"] == "follow_through" for row in coordination_rows),
    }
    execution_truth_counts = Counter(row["truth"] for row in coordination_rows)
    talk_presence_false_positives = sum(row["variant"] == "talk_only" for row in coordination_rows)
    coordination_variants = {}
    for variant in ("shock", "talk_only", "follow_through"):
        selected = [row for row in coordination_rows if row["variant"] == variant]
        coordination_variants[variant] = {
            "planned": len(selected),
            "status_counts": _status_counts(selected),
            "exact": sum(row["decision"] == row["truth"] for row in selected),
            "false_positive": sum(row["decision"] == "follow_through" and row["truth"] == "no_follow_through" for row in selected),
            "uncertain": sum(row["decision"] == "uncertain" for row in selected),
        }
    coordination_summary = {
        "planned": len(coordination_rows),
        "status_counts": _status_counts(coordination_rows),
        "execution_oracle": {
            "planned": len(coordination_rows),
            "follow_through": execution_truth_counts["follow_through"],
            "no_follow_through": execution_truth_counts["no_follow_through"],
            "exact": model_execution_metrics["exact"],
            "false_positive": model_execution_metrics["false_positive"],
            "misses": model_execution_metrics["misses"],
            "model": model_execution_metrics,
        },
        "model_vs_execution_oracle": model_execution_metrics,
        "talk_presence_baseline": {
            "talk_only_false_positives": talk_presence_false_positives,
            "shock_false_positives": 0,
            "note": "messages alone classify all talk-only histories as follow-through; execution oracle does not",
        },
        "talk_only_false_positives": sum(
            row["protocol_valid"] and row["talk_only"] and row["decision"] == "follow_through"
            for row in coordination_rows
        ),
        "by_variant": coordination_variants,
    }
    expected_ids = set(by_id) | eligible_lookup_ids
    unknown = normalized.keys() - expected_ids
    if unknown:
        raise ValueError(f"receipt has no eligible request: {sorted(unknown)!r}")
    statuses = {request_id: normalized.get(request_id, ("missing", None))[0]
                for request_id in sorted(expected_ids)}
    coverage = {
        "planned": {"initial": len(schedule), "lookup": len(eligible_lookup_ids), "total": len(expected_ids)},
        "request_cap": 168,
        "observed": {
            "initial": sum(request_id in normalized for request_id in by_id),
            "lookup": sum(request_id in normalized for request_id in eligible_lookup_ids),
            "total": sum(request_id in normalized for request_id in expected_ids),
        },
        "omissions": [request_id for request_id, status in statuses.items() if status == "missing"],
        "status_counts": dict(Counter(statuses.values())),
    }
    model_scores = {
        model: _score_group(
            [row for row in auth_rows if row["row"]["model"] == model],
            finals_by_initial,
            final_expected_by_initial,
        )
        for model in MODELS
    }
    for score in model_scores.values():
        score["initial"] = {
            "exact_evidentiary": score["exact_evidentiary"],
            "truth_actions": score["truth_actions"],
            "false_clearance": score["false_clearance"],
            "false_block": score["false_block"],
            "premature_actions": score["premature_actions"],
            "justified_review": score["justified_review"],
            "unnecessary_review": score["unnecessary_review"],
            "lookup_use": score["lookup_use"],
            "correct_lookup": score["correct_lookup"],
        }
        score["final"] = {
            "exact_evidentiary": score["final_exact_evidentiary"],
            "truth_actions": score["final_truth_actions"],
            "false_clearance": score["final_false_clearance"],
            "false_block": score["final_false_block"],
            "recovery": score["recovery"],
        }

    result = {
        "schema": 1,
        "seed": SEED,
        "coverage": coverage,
        "omissions": coverage["omissions"],
        "authorization": {
            "planned": len(auth_rows),
            "by_model": model_scores,
            "by_family": groups(auth_rows, "family"),
            "by_view": groups(auth_rows, "view"),
            "surplus": surplus,
            "rule_baseline": {
                "planned": len(rule_rows),
                "exact": rule_exact,
                "initial": {
                    "planned": len(rule_rows),
                    "review": rule_initial_reviews,
                    "exact_evidentiary": rule_initial_evidentiary,
                    "exact_truth": rule_exact,
                },
                "after_one_lookup": {
                    "planned": rule_callback_rows,
                    "exact_truth": rule_callback_exact,
                    "false_clearance": rule_callback_false_clearance,
                    "false_block": rule_callback_false_block,
                },
                "false_clearance": rule_false_clearance,
                "false_block": rule_false_block,
                "by_family": dict(rule_by_family),
            },
        },
        "model_initial_vs_final": {
            model: {"initial": score["initial"], "final": score["final"]}
            for model, score in model_scores.items()
        },
        "coordination": coordination_summary,
    }
    json.dumps(result, ensure_ascii=True, allow_nan=False, sort_keys=True)
    return result


__all__ = [
    "AUTHORIZATION_FIELDS",
    "COORDINATION_DECISIONS",
    "MODELS",
    "authorization_prompt",
    "coordination_prompt",
    "followup",
    "initial_schedule",
    "summarize",
    "validate_answer",
]
