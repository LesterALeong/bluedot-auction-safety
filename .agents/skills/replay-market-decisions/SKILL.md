---
name: replay-market-decisions
description: Verify a recorded simulated market decision or approval lookup offline, reconcile matched bids and rule branches, and calculate safety and economic metrics from trusted evidence.
---

# Replay market decisions

Use [checks 051–075 and the replay record](../../../docs/research-improvements.md#051075--replay-market-decisions). Start with `python -S -B research_toolkit.py audit`. Read the fixture, applicable rule, and receipt for the particular claim under review.

- Reconcile the quote, buyer proposal, and settlement by seller, item, price and quantity. Identify the commitment time and the truth source for scope, expiry, and revocation. In this project an expiry equal to commitment disallows the action.
- Reconstruct both known truth branches from the same visible evidence. Distinguish a recorded `review` from an allowable lookup, and credit recovery only when the retained decisive field preceded a valid final answer.
- Distinguish correctness of an auditor verdict from what a purchase policy would do with it. Log false clearance, false block, unresolved cases, and outcome coverage. Use trusted simulator values for retained surplus and show the feasible comparison for any opportunity cost.
- For a future same-bid rule test, compare both arms at their actual simulated commitment time and account for authorized delays and losses. Use future tense until the matching transaction traces exist.

Use `market_replay_verifier` to reconstruct a consequential demo independently from raw files. Return sources, the observed or replayed result, and meaningful limits. Stop and identify the first mismatch if evidence fails verification.
