---
name: design-paired-market-tests
description: Design or review synthetic paired market safety experiments before inference, including authorization, information shocks, and execution controls. Use for the next pilot, protocol, fixtures, or test of a proposed simulator rule.
---

# Design paired market tests

Use [checks 001–025 and the one-page protocol](../../../docs/research-improvements.md#001025--design-paired-market-tests). Inspect the current study protocol, event generator, and offline tests before proposing the smallest design that answers the decision question.

- Write the hypothesis, comparator, paired invariant, event at which the action binds, population, and decision that will change. Identify the cheapest falsifier and the pass, fail, inconclusive, and stop conditions.
- Derive ground truth independently from the full record. Generate the time-bounded buyer or auditor view separately and audit the exact rendered input for hidden labels or future events. Exercise both authorized and unauthorized paths, including the timing boundary.
- For the planned buyer test, record each bid once and replay it against the ordinary market rules and those same rules plus the approval check. A lookup advances the simulated clock. Separate quote expiry, revoked permission, false blocks, and buyer passes. Freeze the prompt, quote and initial market state across execution arms.
- Ask `paired_design_reviewer` for a bounded independent review when the design determines a comparison or a consequential decision. Give it the protocol and runnable fixtures without a proposed verdict.

Return a pilot-ready protocol and the offline checks that justify readiness, or name the unresolved design defect. Keep model batteries and BlueDot submission outside design work.
