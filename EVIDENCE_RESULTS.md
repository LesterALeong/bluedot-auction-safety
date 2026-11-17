# Can an auction auditor recover a missing approval fact?

[Protocol](EVIDENCE_PROTOCOL.md) · [Evidence and replay metrics](results/evidence-01)

Earlier studies asked whether an auditor could read the order of purchase approval and a binding bid. This follow-up holds the bid and hypothetical settlement fixed and changes one authorization fact. In half the views that fact is withheld. The auditor can review the bid and ask for one registry field before making a final decision.

## Authorization and evidence recovery

The 12 matched pairs cover seller scope, approval expiry and revocation. In each pair, the two partial prompts are byte-identical even though the full records require opposite decisions. Each model saw 24 complete views and 24 partial views. The deterministic check used the same views and the same one-field lookup as the models. The full-record oracle independently derived the authorization label from the replayed seller and registry validity interval.

| Judge | Correct on complete evidence | Reviewed partial evidence | Requested decisive field | Resolved after decisive lookup |
| --- | ---: | ---: | ---: | ---: |
| Deterministic check | 24/24 | 24/24 | 24/24 | 24/24 |
| Sol, low effort | 24/24 | 24/24 | 24/24 | 24/24 |
| Qwen 3.5 9B, local Q4 | 0/24 | 8/24 | 6/24 | 0/24 |

Sol recovered both branches of all 12 pairs, including 8/8 views for each authorization family. Sol and the deterministic check recorded zero false clearances and zero false blocks. In each of the complete and partial views, each cleared all 12 authorized outcomes, preserving all 1,400 credits of eligible buyer surplus in that view.

Qwen made eight lookup requests, two for fields already visible. Across its authorization calls, 45 responses returned `block` alongside a named lookup despite the protocol requiring definitive decisions to pair with `lookup: none`. One complete-view request failed at the local runtime. Qwen's two usable final decisions were both blocks, one on an authorized case. The other matched the full-record label but came after a lookup that left the decisive evidence hidden. A workflow that clears only usable `allow` decisions would have preserved 0 of 1,400 eligible surplus credits in each view and cleared zero unauthorized outcomes. These figures replay a proposed decision rule over hypothetical settlements.

The frozen prompt named the lookup options and told the judge when to request one. It left the exact `lookup: none` mapping implicit in the prose. Qwen's result combines policy reasoning and compliance with that response contract. The raw authorization responses that completed contained zero `allow` decisions, so simply dropping the lookup field would still leave every authorized case without clearance. Sol's ceiling is on short, structured cases with a single omitted field. The experiment uses one prompt and runtime configuration per judge and 12 matched pairs.

## Scripted coordination

| History | Execution label | Qwen correct | Qwen false positives | False positives from flagging any seller discussion |
| --- | --- | ---: | ---: | ---: |
| Common cost shock | No follow-through | 7/8 | 1/8 | 0/8 |
| Seller talk with different bids | No follow-through | 8/8 | 0/8 | 8/8 |
| Bids match the discussion | Follow-through | 8/8 | — | — |

The rule reading the stated round and actual bids matched all 24 scripted labels. Qwen matched 23/24. The two negative controls isolate different mistakes. One tests whether shared price movements alone raise an alarm, and the other tests whether messages raise an alarm when the recorded bids differ. These are eight groups of authored scenarios and measure classification of recorded follow-through.

## Transfer to a larger market testbed

- Give each market mechanism its own clearing and commitment rules. Use a shared event envelope for timestamp, actor, resource, quantity and price. Explicitly mark the applicable rule and the moment a proposed bid becomes binding.
- Store a complete execution record and derive the evidence visible to each participant or auditor as of the decision time. Save both views for replay. Verify that paired scenarios with different ground truth can genuinely look identical to an auditor.
- Use a trusted simulator rule to label authorization and use paired, scripted histories to calibrate classifiers. Include a common shock, discussion without matching execution, and scripted follow-through. A classifier can then be evaluated on false positives, abstention and missing evidence before using it on ambiguous histories.
- Pair behavior metrics with economic measures. This pilot replays authorized buyer surplus from known valuations and settlements. A multi-mechanism evaluation can use the same event stream to calculate clearing and welfare measures appropriate to each mechanism.

These design choices align with the public Phase I interest in instrumented simulated markets, behavioral classification and economic impact. The benchmark uses a single procurement mechanism and authored toy cases. [DARPA Phase I overview](https://www.darpa.mil/research/programs/influence-benchmarks-ai-systems)

The reusable Python entry points are `build_cases()` for fixtures, `initial_schedule()` and `followup()` for model requests, and `summarize()` for scoring normalized responses. A market or model adapter can consume those interfaces with the same replay checks. [Fixtures](evidence_cases.py) · [Schedule and scoring](evidence_study.py)

## Reproduce the run accounting

```powershell
python -S -B replay_evidence.py results/evidence-01
```

The run recorded all 152 eligible requests. Of 120 initial views and 32 follow-ups, 106 were usable, 45 failed the decision and lookup contract, and one local request returned HTTP 500. The local runtime passed a neutral recovery check before the remaining unsent requests ran. The failed request was retained. Qwen ran on Ollama `0.40.16` with the same model digest as the prior study. Sol used the signed-in Codex runner at low effort. The replay verifies the original request freeze and the final source binding. The scoring code was corrected during review to use an independent authorization oracle and count follow-up coverage only when a valid parent actually requested a field. The fixture and all initial and possible follow-up request hashes stayed identical.
