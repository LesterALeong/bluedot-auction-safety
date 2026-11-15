# Four Codex models on the authorization benchmark

The original prompt was already sufficient for every usable Codex judgment on these traces. Across GPT-6.1 Sol, GPT-6.1 Terra, GPT-6 Astra and GPT-6 Luna, the models correctly classified all **1,276 usable judgments**. The revised prompt added an evidence trail. Its **638 usable responses** all included the exact bid and approval dates.

| Codex model | Original violations detected | Revised violations detected | Revised responses with both dates correct |
| --- | ---: | ---: | ---: |
| GPT-6.1 Sol | 80/80 | 80/80 | 160/160 |
| GPT-6.1 Terra | 80/80 | 79/79 | 159/159 |
| GPT-6 Astra | 80/80 | 80/80 | 159/159 |
| GPT-6 Luna | 80/80 | 80/80 | 160/160 |

Denominators in the table are usable responses. There were zero false clearances on the 639 usable violation judgments, zero false alarms on the 637 usable compliant judgments, and zero abstentions. Across the 319 violation comparisons with a usable response under both prompts, explicit detection changed by **0 percentage points**. Every paired comparison was already correct under the original prompt, so the paired bootstrap also returned a zero-width interval for this fixture.

## What ran

The study reused the 40 matched authorization pairs from the local study. Each pair contributed one compliant run and one run with late approval, each shown with short and cluttered logs. Both prompts were run on all four models at low reasoning effort in fresh Codex sessions. The original prompt text and decision schema were unchanged. The revised prompt explained each verdict and requested the two event dates. The two sets of format checks passed on all four models before any auction judgments were sent.

All 1,280 planned judgments were attempted. Four HTTP 403 stream failures returned no usable verdict. The connection passed a neutral recovery check, and the remaining 1,203 unsent cases finished. The four failed reservations stayed in the accounting, with no other failed or omitted cases. One failure was Terra’s revised cluttered violation judgment. The other three were compliant traces. [Frozen protocol](CODEX_COMPARISON_PROTOCOL.md) · [Full accounting](results/codex-authorization-01/summary.json)

For example, in case 02, the bid in the violating trace is dated January 15 and approval is dated January 16. Both traces settle at the same price. The revised response has to point to that ordering, which the deterministic checker can audit independently of the model's verdict.

## Interpretation

These results support using the revised prompt when an evaluator needs checkable evidence alongside a verdict. There was no room for measured detection gains on this fixture. The earlier local run detected no violations, while this subscribed Codex run detected every violation with a usable response. Because the local and hosted configurations also differ in their runtime instructions and inference settings, the gap describes the tested configurations. These cases exercise one explicit order-of-events rule. They do not establish performance on incomplete records, ambiguous authorizations, or real procurement decisions.

## Replay

The published bundle contains normalized judgments and the frozen case and capture hashes. The local audit used the captured App Server events to verify the sent prompt, schema, clean completion, and returned answer before publication. The public replay rebuilds the case schedule and recomputes the metrics from the normalized evidence without a model or account.

```powershell
python -S -B replay_codex_comparison.py results/codex-authorization-01/judgments.json
```

Research design, implementation, and writing were AI-assisted.
