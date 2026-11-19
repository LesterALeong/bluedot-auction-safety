---
name: audit-model-benchmark
description: Freeze, review, or reconcile model comparisons in the auction benchmark, including format canaries, exact model profiles, prompt arms, response contracts, and failed or missing calls.
---

# Audit model benchmarks

Use [checks 026–050 and the run review record](../../../docs/research-improvements.md#026050--audit-model-benchmarks). In this checkout, the [four-model protocol](../../../CODEX_COMPARISON_PROTOCOL.md) records the baseline comparison and `replay_codex_comparison.py` recalculates it using saved judgments.

- Compare actual model IDs, effort, runtime identity, rendered prompt and schema, case IDs, and ordered request hashes across the intended arms. Record unavailable runtime metadata as unknown.
- Require an outcome-free format check per model and output contract before opening the study. Check the impossible response branch too, such as a definitive decision paired with a lookup. Canaries have separate accounting.
- Reconcile planned, reserved and attempted cases to usable, invalid, operational, quota, and missing statuses. A usable abstention is a judgment. A transport or schema failure is a coverage issue. Keep first receipts and retry history. Resume only unchanged unsent work permitted by the frozen plan.
- Report paired detection on comparable cases and exact evidence citations separately. If the baseline is at the ceiling, state that the comparison measured evidence quality without resolving detection gains.

For an existing run, start with `python -S -B research_toolkit.py audit`. Use `model_receipt_auditor` for independent reconciliation when identity or missingness affects the conclusion. Return a review with source paths and a clear coverage disposition. Model calls require an in-scope run request.
