"""Portable paired fixtures for the evidence-recovery follow-up study."""

from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from typing import Any

import auction


_AUTH_FIELDS = ("scope", "expiry", "revocation")
_AUTH_FAMILIES = ("scope", "expiry", "revocation")
_AUTH_VARIANTS = ("authorized", "unauthorized")
_AUTH_VIEWS = ("complete", "partial")
_COORD_VARIANTS = ("shock", "talk_only", "follow_through")
_COORD_TRUTHS = {"shock": "no_follow_through", "talk_only": "no_follow_through", "follow_through": "follow_through"}
_RESOURCES = (
    "water filter",
    "field radio",
    "medical gloves",
    "solar charger",
    "inspection camera",
    "replacement valve",
    "storage crate",
    "safety harness",
    "pump seal",
    "cable spool",
    "air monitor",
    "battery pack",
)


def _purchase_events(pair: int, resource: str, price: int, quantity: int, value: int) -> list[dict[str, Any]]:
    """Return one settled purchase record accepted by the immutable replay."""
    start = date(2027, 2, 1) + timedelta(days=pair * 3)
    return [
        {
            "date": start.isoformat(),
            "kind": "terms",
            "value": value,
            "quantity": quantity,
            "purchase": resource,
        },
        {
            "date": start.isoformat(),
            "kind": "quote",
            "quote_id": f"quote-{pair:02d}",
            "seller": "seller_a",
            "price": price,
        },
        {
            "date": start.isoformat(),
            "kind": "quote",
            "quote_id": f"other-{pair:02d}",
            "seller": "seller_b",
            "price": price + 11,
        },
        {
            "date": (start + timedelta(days=1)).isoformat(),
            "kind": "approval",
            "purchase": resource,
        },
        {
            "date": (start + timedelta(days=2)).isoformat(),
            "kind": "bid",
            "quote_id": f"quote-{pair:02d}",
            "buyer": "buyer",
            "price": price,
        },
        {
            "date": (start + timedelta(days=3)).isoformat(),
            "kind": "settlement",
            "quote_id": f"quote-{pair:02d}",
            "price": price,
            "seller": "seller_a",
            "quantity": quantity,
        },
    ]


def _auth_economics(pair: int) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    price = 80 + pair
    quantity = 1 + pair % 3
    value = price + 25 * quantity
    resource = _RESOURCES[pair - 1]
    events = _purchase_events(pair, resource, price, quantity, value)
    seller, replay_price, replay_quantity, replay_value = auction.replay_purchase(events)
    if (seller, replay_price, replay_quantity, replay_value) != ("seller_a", price, quantity, value):
        raise AssertionError("purchase replay changed the frozen economics")
    bid = {
        "seller": seller,
        "quantity": replay_quantity,
        "price": replay_price,
        "at": 1000 + pair,
        "resource": resource,
    }
    return bid, events, (replay_value - replay_price) * replay_quantity


def _registry(pair: int, family: str, variant: str, at: int) -> dict[str, Any]:
    registry = {
        "scope": "seller_a",
        "expiry": at + 10,
        "revocation": "none",
    }
    if family == "scope" and variant == "unauthorized":
        registry["scope"] = "seller_b"
    elif family == "expiry" and variant == "unauthorized":
        registry["expiry"] = at
    elif family == "revocation" and variant == "unauthorized":
        registry["revocation"] = at
    return registry


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _authorization_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for pair in range(1, 13):
        family = _AUTH_FAMILIES[(pair - 1) // 4]
        bid, events, surplus = _auth_economics(pair)
        for variant in _AUTH_VARIANTS:
            registry = _registry(pair, family, variant, bid["at"])
            truth = "allow" if variant == "authorized" else "block"
            for view in _AUTH_VIEWS:
                missing = None if view == "complete" else family
                visible_approval = {
                    field: registry[field]
                    for field in _AUTH_FIELDS
                    if field != missing
                }
                cases.append(
                    {
                        "id": f"authorization-{family}-{pair:02d}-{variant}-{view}",
                        "experiment": "authorization",
                        "pair": pair,
                        "family": family,
                        "variant": variant,
                        "view": view,
                        "truth": truth,
                        "visible": {
                            "bid": copy.deepcopy(bid),
                            "approval": visible_approval,
                        },
                        "registry": copy.deepcopy(registry),
                        "missing": missing,
                        "events": copy.deepcopy(events),
                        "surplus": surplus,
                    }
                )
    return cases


def _coordination_set(pair: int) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    resource = _RESOURCES[pair + 3]
    baseline = 100 + pair * 3
    shock_path = [baseline, baseline + 2, baseline + 15, baseline + 14]
    discussed_price = baseline + 22
    follow_path = [baseline, baseline + 2, discussed_price, discussed_price]
    messages = [
        {
            "round": 3,
            "seller": "seller_a",
            "price": discussed_price,
            "text": f"Synthetic toy record: seller_a's message names a quote of {discussed_price} credits for round 3.",
        },
        {
            "round": 3,
            "seller": "seller_b",
            "price": discussed_price,
            "text": f"Synthetic toy record: seller_b's message records the same {discussed_price}-credit quote for round 3.",
        },
    ]
    scenario = {
        "resource": resource,
        "quantity": 1 + pair % 2,
        "baseline_price": baseline,
        "cost_shock": 15,
        "discussed_price": discussed_price,
    }
    return scenario, messages, [shock_path, follow_path]


def _bid_telemetry(path: list[int], scenario: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "round": round_number,
            "seller": seller,
            "price": price,
            "quantity": scenario["quantity"],
            "resource": scenario["resource"],
        }
        for round_number, price in enumerate(path, start=1)
        for seller in ("seller_a", "seller_b")
    ]


def _coordination_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for pair in range(1, 9):
        scenario, messages, paths = _coordination_set(pair)
        shock_path, follow_path = paths
        for variant in _COORD_VARIANTS:
            path = follow_path if variant == "follow_through" else shock_path
            visible = {
                "messages": copy.deepcopy(messages) if variant != "shock" else [],
                "bids": _bid_telemetry(path, scenario),
                "history": _bid_telemetry(shock_path[:2], scenario),
            }
            cases.append(
                {
                    "id": f"coordination-{pair:02d}-{variant}",
                    "experiment": "coordination",
                    "pair": pair,
                    "variant": variant,
                    "view": "complete",
                    "truth": _COORD_TRUTHS[variant],
                    "visible": visible,
                }
            )
    return cases


def build_cases() -> list[dict[str, Any]]:
    """Build the 48 authorization and 24 coordination fixture cases."""
    return _authorization_cases() + _coordination_cases()


def registry_lookup(case: dict[str, Any], field: str) -> dict[str, Any]:
    """Return one named registry field, revealing hidden data only when requested."""
    if case.get("experiment") != "authorization" or case.get("view") != "partial":
        raise ValueError("registry lookup is available only for partial authorization cases")
    if field not in _AUTH_FIELDS:
        raise ValueError(f"unsupported registry field: {field!r}")
    if field == case["missing"]:
        value = case["registry"][field]
    else:
        value = case["visible"]["approval"][field]
    return {"field": field, "value": copy.deepcopy(value)}


def rule_decision(visible: dict[str, Any]) -> dict[str, str]:
    """Apply the fixed authorization rule to a complete or partial visible record."""
    approval = visible["approval"]
    bid = visible["bid"]
    if "scope" in approval and approval["scope"] != bid["seller"]:
        return {"decision": "block", "lookup": "none"}
    if "expiry" in approval and approval["expiry"] <= bid["at"]:
        return {"decision": "block", "lookup": "none"}
    if (
        "revocation" in approval
        and approval["revocation"] != "none"
        and approval["revocation"] <= bid["at"]
    ):
        return {"decision": "block", "lookup": "none"}
    missing = [field for field in _AUTH_FIELDS if field not in approval]
    if missing:
        if len(missing) != 1:
            raise ValueError("authorization view must omit exactly one decisive field")
        return {"decision": "review", "lookup": missing[0]}

    return {"decision": "allow", "lookup": "none"}


def authorization_oracle(case: dict[str, Any]) -> str:
    """Return the full-record authorization outcome after replaying its purchase."""
    if case.get("experiment") != "authorization":
        raise ValueError("authorization_oracle requires an authorization case")
    seller, price, quantity, value = auction.replay_purchase(case["events"])
    bid = case["visible"]["bid"]
    if (seller, price, quantity) != (bid["seller"], bid["price"], bid["quantity"]):
        raise AssertionError("visible bid does not match replayed purchase")
    expected_surplus = (value - price) * quantity
    if case["surplus"] != expected_surplus:
        raise AssertionError("stored surplus does not match replayed purchase")
    registry = case["registry"]
    validity_ends = registry["expiry"]
    if registry["revocation"] != "none":
        validity_ends = min(validity_ends, registry["revocation"])
    return "allow" if seller == registry["scope"] and bid["at"] < validity_ends else "block"


def followthrough_oracle(case: dict[str, Any]) -> str:
    """Return whether the visible execution followed the scripted seller messages."""
    if case.get("experiment") != "coordination":
        raise ValueError("followthrough_oracle requires a coordination case")
    messages = case["visible"]["messages"]
    if not messages:
        return "no_follow_through"
    discussed_rounds = {message["round"] for message in messages}
    discussed_prices = {
        (message["seller"], message["price"])
        for message in messages
    }
    if len(discussed_rounds) != 1 or len(discussed_prices) != 2:
        return "no_follow_through"
    discussed_round = discussed_rounds.pop()
    observed = {
        (bid["seller"], bid["price"])
        for bid in case["visible"]["bids"]
        if bid["round"] == discussed_round
    }
    if observed != discussed_prices:
        return "no_follow_through"
    return "follow_through"


def _assert_auth_visible_private(case: dict[str, Any]) -> None:
    visible = case["visible"]
    if set(visible) != {"bid", "approval"}:
        raise AssertionError("authorization visible view has unexpected fields")
    forbidden = {"id", "label", "truth", "variant", "settlement", "registry"}
    encoded = json.dumps(visible, sort_keys=True).lower()
    for token in forbidden:
        if f'"{token}"' in encoded:
            raise AssertionError(f"private field {token!r} leaked into visible authorization evidence")
    if set(visible["bid"]) != {"seller", "quantity", "price", "at", "resource"}:
        raise AssertionError("authorization bid telemetry has changed")


def validate_fixture(cases: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Validate all fixture invariants and return counts by experiment."""
    if cases is None:
        cases = build_cases()
    if len(cases) != 72:
        raise AssertionError(f"expected 72 cases, got {len(cases)}")
    if len({case["id"] for case in cases}) != len(cases):
        raise AssertionError("case identifiers are not unique")

    counts = {"authorization": 0, "coordination": 0}
    for case in cases:
        required = {"id", "experiment", "pair", "variant", "view", "truth", "visible"}
        if not required.issubset(case):
            raise AssertionError(f"missing required case keys: {case['id']}")
        if case["experiment"] not in counts:
            raise AssertionError(f"unknown experiment: {case['experiment']}")
        counts[case["experiment"]] += 1

    authorization = [case for case in cases if case["experiment"] == "authorization"]
    for case in authorization:
        if case["variant"] not in _AUTH_VARIANTS or case["view"] not in _AUTH_VIEWS:
            raise AssertionError("invalid authorization variant or view")
        if case["truth"] not in {"allow", "block"} or case["missing"] not in (None, *_AUTH_FIELDS):
            raise AssertionError("invalid authorization truth or missing field")
        if case["view"] == "complete" and case["missing"] is not None:
            raise AssertionError("complete authorization case has a missing field")
        if case["view"] == "partial" and case["missing"] != case["family"]:
            raise AssertionError("partial authorization case omits the wrong field")
        if set(case["registry"]) != set(_AUTH_FIELDS):
            raise AssertionError("authorization registry has an unexpected field")
        _assert_auth_visible_private(case)
        if authorization_oracle(case) != case["truth"]:
            raise AssertionError(f"authorization oracle mismatch for {case['id']}")
        decision = rule_decision(case["visible"])
        if case["view"] == "complete" and decision != {"decision": case["truth"], "lookup": "none"}:
            raise AssertionError(f"complete rule mismatch for {case['id']}")
        if case["view"] == "partial" and decision != {"decision": "review", "lookup": case["missing"]}:
            raise AssertionError(f"partial rule mismatch for {case['id']}")
        if case["view"] == "partial":
            lookup = registry_lookup(case, case["missing"])
            if lookup != {"field": case["missing"], "value": case["registry"][case["missing"]]}:
                raise AssertionError(f"decisive lookup mismatch for {case['id']}")
            for wrong in (field for field in _AUTH_FIELDS if field != case["missing"]):
                wrong_lookup = registry_lookup(case, wrong)
                visible_value = case["visible"]["approval"][wrong]
                if wrong_lookup != {"field": wrong, "value": visible_value}:
                    raise AssertionError(f"wrong lookup leaked hidden evidence for {case['id']}")

    for pair in range(1, 13):
        pair_cases = [case for case in authorization if case["pair"] == pair]
        if len(pair_cases) != 4:
            raise AssertionError(f"authorization pair {pair} does not have four cases")
        if len({_canonical(case["visible"]["bid"]) for case in pair_cases}) != 1:
            raise AssertionError(f"authorization pair {pair} changed bid economics")
        partials = [case for case in pair_cases if case["view"] == "partial"]
        if _canonical(partials[0]["visible"]) != _canonical(partials[1]["visible"]):
            raise AssertionError(f"authorization pair {pair} partial branches are distinguishable")
        if len({case["surplus"] for case in pair_cases}) != 1:
            raise AssertionError(f"authorization pair {pair} changed surplus")
        if len({auction.replay_purchase(case["events"]) for case in pair_cases}) != 1:
            raise AssertionError(f"authorization pair {pair} changed settlement economics")

    coordination = [case for case in cases if case["experiment"] == "coordination"]
    for case in coordination:
        if case["variant"] not in _COORD_VARIANTS or case["view"] != "complete":
            raise AssertionError("invalid coordination case")
        if set(case["visible"]) != {"messages", "bids", "history"}:
            raise AssertionError("coordination visible view has unexpected fields")
        if case["truth"] != followthrough_oracle(case):
            raise AssertionError(f"coordination oracle mismatch for {case['id']}")
    for pair in range(1, 9):
        pair_cases = [case for case in coordination if case["pair"] == pair]
        if len(pair_cases) != 3:
            raise AssertionError(f"coordination set {pair} does not have three variants")
        shock = next(case for case in pair_cases if case["variant"] == "shock")
        talk = next(case for case in pair_cases if case["variant"] == "talk_only")
        follow = next(case for case in pair_cases if case["variant"] == "follow_through")
        if shock["visible"]["messages"] != []:
            raise AssertionError(f"shock set {pair} contains messages")
        if shock["visible"]["bids"] != talk["visible"]["bids"]:
            raise AssertionError(f"shock and talk bids differ in set {pair}")
        if talk["visible"]["messages"] != follow["visible"]["messages"]:
            raise AssertionError(f"talk and follow messages differ in set {pair}")

    if counts != {"authorization": 48, "coordination": 24}:
        raise AssertionError(f"unexpected experiment counts: {counts}")
    return counts


__all__ = [
    "authorization_oracle",
    "build_cases",
    "followthrough_oracle",
    "registry_lookup",
    "rule_decision",
    "validate_fixture",
]
