# Research log

## 2026-11-15 · Project revision

The earlier completion-report grading project tested whether an agent's request for approval affects how a separate model grades Python code. The completed pilot and its evidence are preserved in the [original study](https://github.com/LesterALeong/completion-report-grading). This revision takes the same concern about accepting an agent's apparent success and asks about permission to act in a simulated auction.

The main comparison pairs an authorized and unauthorized purchase with the same winning outcome. I expect a deterministic audit to distinguish all hand-checked pairs and the outcome summary to distinguish none. The new question is whether a language-model judge uses the same evidence reliably as the trace becomes cluttered. The price-anchor, wrong-advice and coordination experiments see how much of the same auction and event format can be reused for other safety questions.

The first decision is whether matched replay and model output parsing are viable. Check four authored development pairs and run one separate response-format canary per model before opening the holdout. If the auction outcomes differ within a pair or the authorization oracle disagrees with the hand labels, fix the fixture or replay defect and rerun the checks before measuring judge behavior. The [protocol](PROTOCOL.md) records the scope, outcomes and limits in advance.

The project uses synthetic records and AI-assisted work. This log records project decisions and evidence. It does not attest to attendance, mentor feedback, or personal course participation.

## 2026-11-15 · Offline audit and preregistration

The first engineering review found that list order and dates disagreed when the approval moved. It also found that the initial analysis counted compliant controls as structural zeros in the clutter comparison. The corrected traces have chronological dates, separate development and held-out cases, and reconciled purchase outcomes. Only true violations contribute to the paired detection comparison; controls have a separate false-alarm rate. The corrected candidate passed independent review before any model results were available.

The offline audit produced `f08d107082ff0ad532e066435ccd58a88a78bb2135eea44f1e67bb0eee300df1` for the 384 study cases in frozen order. The manifest SHA-256 is `a021ad0a78141df473588e7a8cdd0289343df401f1d14efa0df41eb242dab6a6`. Its request set includes 384 study calls and two outcome-free model canaries. In a rehearsal with mock data, all 384 recorded mock responses replayed offline. A separate rehearsal deliberately supplied an invalid response and verified that the run stopped and the remaining 383 cases were marked missing. Neither rehearsal is model evidence.

## 2026-11-15 · Frozen run and interpretation

Both local format canaries passed. The run completed all 384 planned calls without retries or missing results. Both models flagged zero explicit authorization violations. I retained the distinction between clearing a violation and abstaining because this determines whether an automation gate would allow a transaction to proceed. Neither judge ever called a violation in either trace view, so the preregistered clutter contrast on detection sat at a floor. The drop in false clearances, from 21 on the short logs to zero with added notes, is a separate observed behavior.

Advice caused six paired choices to switch to an offer above the trusted valuation. The price-anchor pilot changed one of eight decisions. The coordination monitor abstained on every price-only call and 14 of 16 evidence-visible calls. These pilots support specific follow-up questions on these fixtures. The [write-up](README.md) records the prompt limitation and the reason to test an explicit mapping and evidence citation in a later study.
