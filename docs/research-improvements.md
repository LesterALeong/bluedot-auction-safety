# 100 ways to improve the research workflow

These are operating instructions for the four project skills. Each section gives the reviewer a specific decision and the evidence to inspect. The checks that require judgment, such as reading a slide, are performed by the assigned reviewer. The offline toolkit runs the evidence replays against the saved studies.

## 001–025 · Design paired market tests

Use `$design-paired-market-tests` and `paired_design_reviewer`. The reviewer returns `READY FOR PILOT` or names the blocking design flaw. The historical example is the [matched authorization protocol](../PROTOCOL.md).

001. **Write one outcome question.** Name the market action, the change being tested, and one primary outcome in a sentence.
002. **Name the decision the result will change.** Write what you would do after a positive, negative, or inconclusive pilot before collecting verdicts.
003. **Try the cheapest falsifier first.** Find a hand-checkable case that can invalidate the design without calling a model.
004. **Test the prompt and the enforcement rule at different stages.** Mark whether each intervention changes the proposed action or the ability to commit it.
005. **Choose the unit of comparison.** Name the case pair, market run, or participant that can legitimately be counted as independent.
006. **Write a pair invariant.** List the facts held constant and reject a matched pair if an unintended field differs.
007. **State when the market action binds.** Name the commitment event and the timestamp at which permission must hold.
008. **Identify each actor's authority.** Name who quotes, bids, authorizes, judges, and can stop simulated execution.
009. **Derive labels from full execution evidence.** Use an oracle that does not call the model or read a response to decide truth.
010. **Check the oracle against hand labels.** Include one known authorized and one known unauthorized case through the actual evaluator.
011. **Exercise the time boundary.** Include approval or quote expiry immediately before, exactly at, and immediately after commitment.
012. **Verify chronological ordering.** Compare the order of recorded events with their timestamps and declare how ties resolve.
013. **Create point-in-time views.** Derive buyer and auditor views from their available evidence at decision time so neither sees later events.
014. **Test indistinguishable partial views.** Require identical visible inputs across an opposite-truth pair before the decisive lookup.
015. **Isolate hidden truth and metadata.** Scan the actual rendered request for labels, branch identifiers, and future settlement information.
016. **Keep a useful authorized control.** Include a valid purchase the control should preserve so blocking everything cannot count as success.
017. **Include an irrelevant update.** Match the prominence of a real market update while leaving the best feasible offer unchanged.
018. **Distinguish shared shocks from seller behavior.** Include an authored common-cost control with a matching price pattern when testing execution classification.
019. **Include talk without follow-through.** Check whether a classification uses the actual recorded bids rather than conversation alone.
020. **Separate pilot and evaluation cases.** Fix prompts on development examples and hold new fixture groups back for the declared comparison.
021. **Register stopping rules.** Bound case count, compute, wall time, and what ends the run after an operational failure.
022. **Check fixture reachability.** Drive a known allow, block, and review through the production path whenever the policy supports all three.
023. **Predeclare denominators and exclusions.** Write eligible populations and handling for passes, invalid responses, and incomplete pairs.
024. **Constrain the research claim.** State which finding the authored synthetic scenario can identify and where more varied data would be needed.
025. **Freeze the one-page protocol.** Record design identity, hypothesis, controls, metrics, limits, and next decision before evaluation begins.

## 026–050 · Audit model benchmarks

Use `$audit-model-benchmark` and `model_receipt_auditor`. The reviewer reconciles planned requests to their terminal states. See the [four-model protocol](../CODEX_COMPARISON_PROTOCOL.md) and [evidence study protocol](../EVIDENCE_PROTOCOL.md).

026. **Record exact requested model IDs.** Store provider model IDs alongside friendly names such as Sol or Luna.
027. **Record runtime identity.** Retain local digest or returned provider metadata when available, and mark what the provider does not expose.
028. **Pin inference settings.** Save effort, temperature, token limit, and runner configuration where the runtime exposes them.
029. **Hash the exact rendered prompt.** Compare delivered bytes with the registered input for each request.
030. **Pin the output schema per arm.** Preserve the decision contract as part of request identity so response changes are attributable.
031. **Make legal decision and lookup combinations explicit.** The contract should state the required `lookup` value for both definitive decisions and review.
032. **Prove the validator rejects an illegal combination.** Run a malformed contract fixture through the same parser before interpreting model failures.
033. **Run outcome-free format checks per model and schema.** Use a neutral request that exercises the fields without exposing held-out outcomes.
034. **Keep canaries out of reported study counts.** Reconcile them in admission records with their own denominator.
035. **Compare identical scheduled cases.** Join by frozen case, truth, and view across the original and revised prompts.
036. **Change only the intended arm.** Diff the prompts, schema, effort, and runtime, then name every deliberate change in the interpretation.
037. **Start each judgment with clean context.** Verify that one case cannot carry its tool output or verdict into the next request.
038. **Freeze schedule order.** Save the request sequence and stable IDs so a restart cannot silently reorder the battery.
039. **Reserve before sending.** Persist the request ID and hash before inference and reject a duplicate reservation.
040. **Retain the first receipt.** Preserve the original response or failure and its provenance, including when a later request succeeds.
041. **Verify clean completion.** Require a complete response and successful transport before parsing a verdict.
042. **Account for every scheduled request.** Reconcile valid, invalid, operational, quota, and missing records to the planned population.
043. **Separate transport failures from invalid model output.** Use the retained status and error class to distinguish an unavailable answer from a broken response contract.
044. **Separate unusable answers from abstentions.** Count abstention only if a usable response explicitly expressed uncertainty.
045. **Report observed and usable coverage.** Give planned, attempted, and usable denominators at the study level and by model or arm when they differ.
046. **Record elapsed time against the budget.** Keep timing and cost with the receipt so later scheduling decisions have evidence.
047. **Pause on systemic failures.** Detect repeated transport or quota errors and apply the registered stop rule before starting more calls.
048. **Use an outcome-blind recovery check.** Prove the connection or parser works on a neutral case before considering unsent requests.
049. **Resume only eligible work.** Compare the original freeze and reservation log before continuing unchanged unsent requests under the registered rule.
050. **Validate cited evidence separately from verdicts.** Compare the response’s bid and approval dates with the fixture even when the decision is right.

## 051–075 · Replay market decisions

Use `$replay-market-decisions` and `market_replay_verifier`. The verifier returns the tested event, decision, metrics, and limitations. The [evidence recovery study](../EVIDENCE_RESULTS.md) supplies a recorded example.

051. **Rebuild the study offline.** Use the frozen case generators and saved responses to recompute all three published summaries.
052. **Check the freeze lineage.** On a source rebind, compare the original and current fixture, request schedule, and runtime identities.
053. **Bind metrics to retained evidence.** Compare the recomputed summary against its saved counterpart and retain the matching summary digest.
054. **Reconcile the quote to settlement.** Join the event record by quote, seller, item, price, and quantity before crediting any purchase.
055. **Apply seller scope at the binding event.** A valid time window cannot authorize a seller outside the approval scope.
056. **Use the earliest ending permission.** Recheck both expiry and revocation at commitment, using the declared boundary convention.
057. **Keep a justified review distinct.** Record that a decisive fact was missing and which fact would resolve the decision.
058. **Require a valid parent for follow-up.** Derive lookup eligibility from the actual response and the frozen lookup contract.
059. **Return only the named registry field.** Verify the reply contains that field and does not expose private labels or adjacent data.
060. **Measure redundant lookups.** Mark requests for already-visible fields so lookup activity cannot inflate recovery.
061. **Credit recovery only after decisive evidence.** Require a justified initial review, the missing field, and a correct final decision.
062. **Represent premature resolution.** Report definitive decisions on underdetermined views, even if a guessed result matches an unseen label.
063. **Replay both branches of the same recorded bid.** Fingerprint the buyer instruction, proposed offer, and starting state before changing the simulator rule.
064. **Keep baseline market checks identical.** Inspect price, budget, delivery, and quote-validity checks in both execution arms.
065. **Model review time explicitly.** In the buyer experiment, register elapsed simulated time and recheck quote and permission deadlines at the new commitment time.
066. **Count false clearances per eligible violation.** Report how many unauthorized proposals receive clearance and name the relevant denominator.
067. **Count false blocks per eligible valid action.** Report blocked authorized actions separately from elapsed-time losses and buyer passes.
068. **Count prevented unauthorized commitments as paired transitions.** Credit a prevention if baseline commits and the approval-check arm prevents that same unauthorized bid.
069. **Track authorized delay and loss separately.** Record whether a valid bid eventually clears and whether it misses an available quote after a pause.
070. **Compute buyer surplus from trusted inputs.** Multiply quantity by the difference between value per unit and price per unit. Record both prices and values in simulated credits.
071. **Benchmark opportunity cost against a feasible offer.** State the time, authorization and delivery constraints used to select the best feasible authorized purchase.
072. **Analyze paired effects at the right cluster level.** Keep repeated views of a scenario together and state incomplete-pair exclusions before calculating an interval.
073. **Expose ceilings and floors in detection.** Report the measured difference along with whether either arm could plausibly improve on that fixture.
074. **Keep inactive results out of the evidence ledger.** Label an illustrative policy replay or a proposed action test distinctly from completed model observations.
075. **Review the replay independently.** Give the verifier raw fixtures and receipts, have them reconstruct the boundary case, and compare their result with the check-in before use.

## 076–100 · Report and transfer findings

Use `$report-safety-research` and `research_claim_editor`. The editor returns the most important claim or visual corrections, with sources and acceptance checks. The [offline check-in](../README.md#research-workflow) supplies current evidence for the approved claims.

076. **Begin with one concrete decision.** The opening should say what the buyer proposes and what makes that action unsafe or uncertain.
077. **Define the market before describing the models.** Identify what is bought and how two quotes turn into a possible order.
078. **Explain the units next to the first price.** Call the price simulated credits and label price per unit separately from total spend.
079. **Label model roles on first use.** Say when a model was an auditor of saved traces and when a proposed model would choose a bid.
080. **Explain what instructions can do.** Describe the prompt's effect on the model and the simulator's separate control over commitment.
081. **Name the evidence status of each result.** Use recorded result, deterministic replay, illustration, or planned test where an audience could confuse them.
082. **Attach evidence to every material number.** Record the artifact path, metric field or replay command, and denominator in a claim ledger or speaker note.
083. **Include unusable results alongside performance.** Show coverage and major failure classes next to the scored model result.
084. **Carry uncertainty into headlines.** Describe a measured result for the tested synthetic cases, with the important inference limit on the same slide or paragraph.
085. **Show what changed at each check-in.** Date the new evidence or design change and identify the decision it informs.
086. **Pick one auditable demo.** Choose a compact case with a reproducible command and a legible before/after fact.
087. **Use chart types that express the comparison.** Use bars for matched quote prices and show a consistent axis and measurement unit.
088. **Use timelines for timing rules.** Place bid, expiry, and decision on a common time scale with labels at the exact boundary.
089. **Use flows for roles and controls.** Draw where the buyer, approval lookup, and simulator enter the process, using one node per decision.
090. **Use diagrams and charts for analytical graphics.** Choose a visual that explains the market; remove decorative item art or icons that distract from it.
091. **Put values in editable chart data.** When the source deck is available, compare plotted data and labels with the replay receipt before calling the chart checked.
092. **Cold-read the rendered slides.** Ask a fresh reader to explain the market, the credits, and the result from the slides alone. Report export or access limits when the source cannot be checked.
093. **Ask one check-in question.** End with a specific choice the mentor can help resolve, such as whether a one-minute lookup represents the intended cost.
094. **Tie a paper to an experiment change.** Record the primary source, applicability, change proposed, and a cheap test of whether it helps.
095. **Write a transfer card for each market mechanism.** List event fields, visibility, commitment, oracle, welfare measure, and assumptions that must be revalidated.
096. **Calibrate any transfer with known controls.** Preserve explicit common-shock, talk-only, and follow-through controls in authored market simulations when relevant.
097. **Limit transfer to established inputs.** Reuse independently shareable simulation methods and keep possible engagements and untested transfer conditional.
098. **Give subagents bounded assignments.** State the question, files, authority, expected evidence, and stop condition, then run only independent reviews in parallel.
099. **Keep the final research decision with the lead.** Review raw evidence, adjudicate conflicts, and record the most informative next experiment and the cost of running it.
100. **Respect artifact and submission boundaries.** Draft and verify the check-in locally, and carry the user's submission hold into every applicable handoff.

## Working records

Copy the corresponding line into the task or review artifact and fill it from the primary evidence.

| Record | Fields |
| --- | --- |
| One-page protocol | Question · intervention and comparator · invariant · actors and binding event · population and controls · metrics · budget and stop rule · frozen identity · next decision |
| Run review | Freeze and runtime identity · per-arm canaries · planned, attempted, usable and failure classes · request or receipt exceptions · disposition and source paths |
| Replay review | Case and source · identical state · changed fact · proposed action · binding time · branch verdicts or commitments · computation, units and denominator · limits |
| Claim ledger | Statement · recorded/replayed/illustrative/planned · evidence file and field · denominator and unit · qualification · action if unsupported |
| Transfer card | Mechanism · shared event fields · actor visibility · binding rule and oracle · safety and welfare measures · assumption to test · prerequisite evidence |
