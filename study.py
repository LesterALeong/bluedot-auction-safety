"""Freeze, run, and replay the synthetic auction evaluation."""

import argparse
import base64
import hashlib
import http.client
import json
import random
import time
from datetime import UTC, datetime
from pathlib import Path

from auction import build_cases, validate_fixture
from metrics import summarize


ROOT = Path(__file__).resolve().parent
MODELS = {
    "gemma": ("gemma4:e4b-it-qat", "ee665637121887cf3befff38abbb1be4ee117c7db867d97a67e29049ecd7e15f"),
    "qwen": ("qwen3.5:9b-q4_K_M", "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"),
}
SERVER_VERSION = "0.40.14"
OPTIONS = {"temperature": 0, "seed": 20261115, "num_ctx": 4096, "num_predict": 96, "num_thread": 2}
CALL_SECONDS = 45
CAMPAIGN_SECONDS = 1200
RESPONSE_LIMIT = 262_144
EXPECTED_COUNTS = {"approval": 320, "anchor": 16, "advice": 16, "coordination": 32}


def encode(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def invalid_constant(value):
    raise ValueError(f"nonstandard JSON constant: {value}")


def decode(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def utc_now():
    return datetime.now(UTC).isoformat()


def request_bytes(case):
    return encode({
        "model": MODELS[case["model"]][0],
        "messages": [{"role": "user", "content": case["prompt"]}],
        "format": {
            "type": "object", "required": ["decision"], "additionalProperties": False,
            "properties": {"decision": {"type": "string", "enum": case["choices"]}},
        },
        "stream": False, "think": False, "tools": [], "keep_alive": "60s", "options": OPTIONS,
    })


def http_request(method, route, timeout, data=None):
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=timeout)
    try:
        connection.request(method, route, body=data, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read(RESPONSE_LIMIT + 1)
        if len(raw) > RESPONSE_LIMIT:
            raise ValueError("response exceeded byte limit")
        return response.status, raw
    finally:
        connection.close()


def get_metadata(route):
    status, raw = http_request("GET", route, 10)
    if status != 200:
        raise RuntimeError(f"HTTP {status} for local Ollama metadata")
    return decode(raw)


def verify_runtime():
    version = get_metadata("/api/version")["version"]
    installed = {entry["name"]: entry["digest"] for entry in get_metadata("/api/tags")["models"]}
    if version != SERVER_VERSION or any(installed.get(tag) != digest for tag, digest in MODELS.values()):
        raise RuntimeError("local Ollama version or model digest differs from the frozen design")
    return {"version": version, "models": {tag: installed[tag] for tag, _ in MODELS.values()}}


def parse_decision(case, http_status, raw):
    if http_status != 200:
        raise ValueError(f"HTTP {http_status}")
    reply = decode(raw)
    if not isinstance(reply, dict) or reply.get("model") != MODELS[case["model"]][0]:
        raise ValueError("unexpected response model")
    if reply.get("done") is not True or reply.get("done_reason") != "stop":
        raise ValueError("incomplete generation")
    message = reply.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ValueError("invalid assistant message")
    if message.get("tool_calls") or message.get("thinking"):
        raise ValueError("unexpected tool or thinking output")
    content = message.get("content")
    obj = decode(content) if isinstance(content, str) else None
    if not isinstance(obj, dict) or set(obj) != {"decision"} or obj["decision"] not in case["choices"]:
        raise ValueError("decision did not match the schema")
    return obj["decision"]


def canary(alias):
    return {"id": f"smoke-{alias}", "model": alias, "choices": ["ready"],
            "prompt": 'This is an output format check. Return a JSON object with decision equal to "ready".'}


def plan_cases():
    validate_fixture()
    cases = build_cases()
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("duplicate planned case IDs")
    for experiment, count in EXPECTED_COUNTS.items():
        if sum(case["experiment"] == experiment for case in cases) != count:
            raise ValueError(f"incorrect planned count: {experiment}")
    if len(cases) != sum(EXPECTED_COUNTS.values()):
        raise ValueError("unexpected extra cases")
    rng = random.Random(20261115)
    schedule = []
    for model in MODELS:
        rows = [case for case in cases if case["model"] == model]
        rng.shuffle(rows)
        schedule.extend(rows)
    if len(schedule) != len(cases):
        raise ValueError("unknown case model")
    return schedule


def manifest(cases):
    return {
        "schema": 1, "counts": EXPECTED_COUNTS, "model_identity": MODELS,
        "version": SERVER_VERSION, "options": OPTIONS, "case_sha256": sha(encode(cases)),
        "source_sha256_lf": {name: sha((ROOT / name).read_bytes().replace(b"\r\n", b"\n"))
                          for name in ("PROTOCOL.md", "auction.py", "study.py", "metrics.py")},
        "request_sha256": {case["id"]: sha(request_bytes(case))
                           for case in [*cases, *(canary(alias) for alias in MODELS)]},
    }


def write_new(path, obj):
    with path.open("xb") as handle:
        handle.write(encode(obj) + b"\n")


def append_log(handle, entry):
    handle.write(encode(entry) + b"\n")
    handle.flush()


def record_call(case, reservations, receipts, timeout):
    payload = request_bytes(case)
    reservation = {"id": case["id"], "model": case["model"], "request_sha256": sha(payload), "start": utc_now()}
    append_log(reservations, reservation)
    start = time.monotonic()
    receipt = {**reservation, "http_status": None, "body": None, "body_sha256": None, "error": None}
    try:
        status, raw = http_request("POST", "/api/chat", timeout, payload)
    except (OSError, http.client.HTTPException, ValueError) as exc:
        receipt["error"] = type(exc).__name__
    else:
        receipt.update(http_status=status, body=base64.b64encode(raw).decode("ascii"), body_sha256=sha(raw))
    receipt["elapsed_ms"] = round((time.monotonic() - start) * 1000)
    append_log(receipts, receipt)
    return evaluate_receipt(case, receipt)


def evaluate_receipt(case, receipt):
    if receipt["body"] is None:
        return "operational_unknown", None
    raw = base64.b64decode(receipt["body"], validate=True)
    if sha(raw) != receipt["body_sha256"]:
        raise ValueError("response body hash mismatch")
    try:
        value = parse_decision(case, receipt["http_status"], raw)
    except (ValueError, TypeError):
        return "invalid" if receipt["http_status"] == 200 else "operational_unknown", None
    return "valid", value


def read_log(path):
    result = {}
    if not path.exists():
        return result
    for line in path.read_bytes().splitlines():
        entry = decode(line)
        if entry["id"] in result:
            raise ValueError("duplicate evidence ID")
        result[entry["id"]] = entry
    return result


def verify_frozen(path, cases):
    expected = manifest(cases)
    if encode(decode((path / "freeze.json").read_bytes())) != encode(expected):
        raise ValueError("frozen source, inputs, or requests changed")
    return expected


def run(path, cases):
    verify_frozen(path, cases)
    deadline = time.monotonic() + CAMPAIGN_SECONDS
    write_new(path / "runtime.json", verify_runtime())
    with (path / "reservations.jsonl").open("xb") as reserved, (path / "receipts.jsonl").open("xb") as receipts:
        for alias in MODELS:
            verify_runtime()
            if record_call(canary(alias), reserved, receipts, CALL_SECONDS) != ("valid", "ready"):
                raise RuntimeError(f"{alias} output-format smoke test failed")
            print(f"{alias}: output-format smoke passed", flush=True)
        for index, case in enumerate(cases):
            if index == 0 or case["model"] != cases[index - 1]["model"]:
                verify_runtime()
            budget = min(CALL_SECONDS, deadline - time.monotonic())
            if budget <= 1:
                raise RuntimeError("campaign deadline reached")
            status, _ = record_call(case, reserved, receipts, budget)
            if status != "valid":
                raise RuntimeError(f"study response was {status} at attempt {index + 1}; partial evidence retained")
            if (index + 1) % 32 == 0:
                print(f"Recorded {index + 1}/{len(cases)} study attempts", flush=True)
    verify_runtime()
    write_new(path / "run-complete.json", {"attempted": len(cases), "end": utc_now()})


def analyze(path, cases):
    frozen = verify_frozen(path, cases)
    reservations = read_log(path / "reservations.jsonl")
    receipts = read_log(path / "receipts.jsonl")
    if not receipts.keys() <= reservations.keys() <= frozen["request_sha256"].keys():
        raise ValueError("unknown or unreserved evidence ID")
    schedule = [*(canary(alias) for alias in MODELS), *cases]
    planned = {case["id"]: case for case in schedule}
    if list(reservations) != list(planned)[:len(reservations)] or list(receipts) != list(reservations)[:len(receipts)]:
        raise ValueError("evidence does not follow the frozen attempt order")
    if reservations:
        expected_runtime = {"version": SERVER_VERSION, "models": dict(MODELS.values())}
        if decode((path / "runtime.json").read_bytes()) != expected_runtime:
            raise ValueError("runtime does not match the frozen model identity")
    for case_id, reservation in reservations.items():
        if (reservation["request_sha256"] != frozen["request_sha256"][case_id]
                or reservation["model"] != planned[case_id]["model"]):
            raise ValueError("reservation does not match the frozen request")
        if case_id in receipts and any(receipts[case_id][key] != value for key, value in reservation.items()):
            raise ValueError("receipt does not match its reservation")
    rows = []
    for case in cases:
        case_id = case["id"]
        status = "operational_unknown" if case_id in reservations else "missing"
        value = None
        if case_id in receipts:
            status, value = evaluate_receipt(case, receipts[case_id])
        rows.append({**case, "status": status, "value": value})
    results = summarize(rows)
    results["admission"] = {
        alias: evaluate_receipt(canary(alias), receipts[f"smoke-{alias}"])[0]
        if f"smoke-{alias}" in receipts else "missing" for alias in MODELS
    }
    completed = path / "run-complete.json"
    results["run_completed_marker"] = completed.is_file()
    if completed.is_file() and (len(receipts) != len(planned) or decode(completed.read_bytes())["attempted"] != len(cases)):
        raise ValueError("completion marker disagrees with retained receipts")
    results["publication_ready"] = (completed.is_file()
                                    and set(results["admission"].values()) == {"valid"}
                                    and all(row["status"] == "valid" for row in rows))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "freeze", "run", "analyze"))
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    cases = plan_cases()
    if args.action == "audit":
        print(json.dumps({"counts": EXPECTED_COUNTS, "case_sha256": sha(encode(cases))}, indent=2))
        return
    if args.directory is None:
        parser.error("--directory is required for freeze, run, and analyze")
    path = args.directory.resolve()
    if args.action == "freeze":
        path.mkdir(parents=True, exist_ok=False)
        write_new(path / "freeze.json", manifest(cases))
        print(f"Frozen {len(cases)} study requests and {len(MODELS)} canaries in {path}")
    elif args.action == "run":
        run(path, cases)
    else:
        results = analyze(path, cases)
        print(json.dumps(results, indent=2, sort_keys=True))
        if not results["publication_ready"]:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
