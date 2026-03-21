# ODR Context Continuity Requirements

Last updated: 2026-03-21
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: ODR continuity and convergence hardening

## 1. Objective

Establish the requirements for preserving within-run conversational continuity across ODR model unload, reload, and role swap boundaries so that coordinated refinement can approximate the practical continuity of a long-running frontier-model browser session without depending on provider-native session persistence.

This lane exists to answer a bounded question:

**Can ODR converge more reliably when Orket preserves and reloads a stronger shared run context than the current thin replay path?**

The lane must produce requirements authority for:

1. a control continuity mode representing the frozen current replay behavior,
2. a bounded V0 continuity mode based on log-derived replay,
3. a stronger V1 continuity mode based on compiled shared run state,
4. a fair comparison framework for measuring whether continuity changes improve convergence,
5. an explicit decision rule for determining whether V0 or V1 is worth follow-on implementation work.

## 2. Problem Statement

Current ODR runs are stateless at the provider session boundary and rely on reconstructed prompt context rather than a native long-lived chat session. This creates a risk that, after model eject, reload, or role swap, the active model no longer receives enough durable context to preserve accepted decisions, unresolved issues, prior critique, and the causal path that produced the current draft.

The result may be one or more of the following:

1. repeated re-argument of already settled points,
2. reopened or contradicted prior decisions,
3. slower convergence due to rounds spent re-establishing context,
4. misleading conclusions about model-pair quality when the real defect is insufficient continuity.

These requirements therefore govern **within-run continuity restoration** for ODR. They do not establish a general-purpose long-term memory platform.

## 3. Scope

### In scope

This lane establishes requirements for:

1. preserving shared ODR run context across model unload, reload, and role swap events,
2. defining three explicit continuity modes for controlled comparison,
3. defining the minimum authoritative run state that must survive round transitions,
4. defining the distinction between shared authoritative state and optional auxiliary recall,
5. defining explicit state-transition semantics for continuity-tracked items,
6. evaluating continuity changes against fixed scenarios, model pairs, and round budgets,
7. recording the evidence needed to determine whether continuity improvements materially improve convergence.

### Out of scope

This lane does not establish:

1. a cross-run or user-global memory system,
2. vector retrieval as an authoritative truth surface,
3. provider-native persistent chat sessions as a requirement,
4. generalized multi-agent memory beyond the bounded ODR lane,
5. new tool-safety policy or tool-execution changes,
6. Qwen-specific remediation work beyond excluding structurally unreliable pairs from the primary comparison matrix when needed,
7. the implementation plan for this lane.

## 4. Non-Goals

The following are explicit non-goals:

1. turning this lane into a general memory architecture for all Orket workloads,
2. replacing durable run artifacts with fuzzy semantic retrieval,
3. allowing each model role to maintain its own authoritative version of run truth,
4. using a raw unfiltered event log as the sole active prompt context for all rounds,
5. changing acceptance criteria merely to make weak continuity modes appear successful.

## 5. Definitions

### 5.1 Control continuity mode

The currently shipped ODR context replay behavior used as the experiment baseline.

### 5.2 V0 log-derived replay mode

A bounded continuity mode in which prior run history is used to construct a deterministic replay block for the next round without introducing a full compiled state model.

### 5.3 V1 compiled-state replay mode

A continuity mode in which Orket maintains and reloads a shared structured run-state object and derives role-specific round views from that shared state.

### 5.4 Shared authoritative run state

The canonical within-run truth surface that all participating models must treat as the same current state of the run.

### 5.5 Auxiliary recall

Non-authoritative contextual material that may help a model reason about the run but may not supersede or redefine shared authoritative run state.

### 5.6 Reopened decision

A decision that was previously accepted as part of the run state and later reintroduced as unresolved, contradicted, or superseded without an explicit governed reason.

### 5.7 Carry-forward integrity

The degree to which accepted decisions, invariants, and resolved issues remain preserved across later rounds without silent loss or contradiction.

### 5.8 Superseded item

A previously accepted or unresolved item that is intentionally replaced by a newer item through an explicit recorded transition that names both the prior item and the reason for supersession.

### 5.9 Contradiction

A round state in which an accepted decision or invariant is negated, omitted in a materially conflicting way, or replaced without an explicit supersession transition.

### 5.10 Regression

A round state in which previously closed or preserved continuity state degrades into unresolved, contradictory, or missing status without governed justification.

## 6. Decision Lock

The chosen target for this lane is:

**bounded within-run continuity hardening for ODR via explicit control, V0, and V1 continuity modes.**

The following alternatives are explicitly excluded from this lane:

1. jumping directly to a general-purpose memory subsystem for all workloads,
2. relying on provider-native chat persistence as the primary solution,
3. treating vector retrieval as the primary authority for current run truth,
4. skipping the control comparison and evaluating only a new continuity mode.

## 7. Control Freeze

The control continuity mode is frozen for the duration of this lane.

The control contract is:

1. use the currently shipped replay path without continuity-specific enhancement,
2. preserve existing acceptance criteria, stop rules, and evaluation logic,
3. record the exact control prompt-context inputs per round,
4. record the control continuity mode as `control_current_replay`,
5. prohibit any control-only prompt additions, replay summaries, compiled shared state, or auxiliary retrieval additions that did not exist before this lane.

If the existing replay behavior must change for unrelated reasons while this lane is active, the continuity comparison must either:

1. continue against the frozen pre-change control contract, or
2. restart with a newly frozen control and explicit invalidation of prior comparison claims.

## 8. Core Requirements

### R1. Explicit continuity modes

ODR must support three explicitly distinguishable continuity modes:

1. `control_current_replay`
2. `v0_log_derived_replay`
3. `v1_compiled_shared_state`

Each run artifact and comparison output must record which continuity mode was used.

### R2. Shared truth must survive model boundaries

A participating model may be unloaded, reloaded, or swapped with another model role during the run without causing loss of shared authoritative run truth.

At minimum, the continuity mechanism must preserve enough information to restore:

1. the current canonical artifact under refinement,
2. accepted decisions still in force,
3. unresolved issues still open,
4. known invariants that must remain true,
5. the most recent architect-side change or proposal,
6. the most recent auditor-side critique or objection,
7. the causal continuity needed to understand why the current draft reached its present form.

### R3. Shared authority must remain model-agnostic

The authoritative within-run truth surface must be shared across model roles. No role-specific or model-specific private memory may become the authoritative definition of current run state.

Model-local continuity, if later introduced, must remain auxiliary and must not override shared run truth.

### R4. V0 must remain bounded

V0 exists to test whether stronger replay from prior run history materially improves convergence over the current replay path.

Therefore V0 must:

1. derive its continuity input from durable prior run history,
2. produce a deterministic bounded replay context for the next round,
3. avoid depending on provider-native session persistence,
4. avoid requiring a full structured compiled-state system,
5. remain a bounded experiment rather than a disguised general memory subsystem.

### R5. V0 explicit exclusions

V0 may not include any of the following:

1. a compiled authoritative state object that independently stores accepted, rejected, unresolved, and superseded items as first-class structured fields,
2. role-specific state derivation from a shared compiled-state object,
3. vector retrieval or semantic search as part of the active continuity path,
4. role-local persistent memory stores,
5. provider-native persistent session continuation,
6. hidden manual curation that changes the replay contents outside the deterministic replay-building rules,
7. arbitrary full-log dumping without a deterministic bounded selection and formatting rule.

### R6. V1 must provide compiled shared state

V1 must introduce a compiled shared run-state representation that is authoritative for the active run.

V1 must support distinct role views derived from the same shared state so that architect and auditor can receive role-appropriate instructions without diverging on run truth.

### R7. Raw logs may be durable history but not sole active authority

Durable logs may serve as a source for replay or compilation. However, a raw append-only event log may not, by itself, serve as the sole authoritative working context unless Orket also provides a deterministic interpretation of which state is current, accepted, unresolved, and superseded.

### R8. No authoritative dependence on fuzzy retrieval

Vector retrieval or similar semantic recall may be used only as auxiliary recall in this lane. It may not be the primary or sole source of authoritative run truth for current ODR continuity.

### R9. Continuity must be replayable and inspectable

The continuity mechanism for each mode must leave behind enough artifacts to make the active context restorable and inspectable after the run.

A reviewer must be able to determine, from run artifacts, what context was loaded for a given round and why.

### R10. Fair comparison requirement

The lane must support fair comparison across continuity modes.

Comparison runs must keep fixed, unless intentionally varied as part of the comparison:

1. scenario set,
2. acceptance criteria,
3. stop rules,
4. role pair,
5. round budget,
6. evaluation logic.

### R11. Round-budget sensitivity must be evaluated explicitly

The comparison framework must use the following locked round budgets:

1. lower budget: `5` rounds,
2. higher budget: `9` rounds.

No other round budget may be used for the primary comparison claims in this lane.

### R12. Primary comparison matrix must stay bounded

The primary continuity comparison matrix for this lane must focus on the currently healthiest non-structurally-broken model-role pairs.

The inclusion and exclusion rules for the primary matrix must be pre-registered from prior artifacts before continuity experiments begin.

### R13. Continuity evaluation must measure more than pass/fail

The required comparison evidence must include, at minimum:

1. convergence result,
2. stop reason,
3. rounds consumed,
4. latency behavior,
5. active-context size behavior,
6. reopened-decision behavior,
7. carry-forward integrity for accepted decisions,
8. contradiction or regression behavior across rounds.

### R14. Continuity changes must not weaken truthfulness gates

A stronger continuity mode may not bypass, relax, or blur the existing validation and truthfulness gates merely to increase apparent convergence.

Any convergence gain must be achieved while preserving the existing evaluation discipline.

### R15. Requirements/plan workflow boundary

This lane governs within-run continuity for ODR requirement and implementation-plan refinement loops, but it does not itself authorize a merged requirements-and-plan memory system. The continuity design must preserve the distinction between the current artifact under refinement and other adjacent artifacts or stages.

Adjacent artifacts may appear only as auxiliary recall if they are explicitly marked non-authoritative. At minimum, this applies to:

1. prior related requirement documents,
2. prior related implementation plans,
3. historical notes or analyses,
4. older branches or abandoned drafts,
5. related proof or evaluation artifacts.

The following may not become authoritative run truth for the active round unless they are compiled into the continuity mode’s current authoritative surface under this lane’s rules:

1. adjacent requirement documents,
2. adjacent implementation plans,
3. retrieved historical notes,
4. vector-store recall,
5. model-local scratchpads.

## 9. Required Authoritative State Categories

The authoritative within-run continuity surface must be able to represent the following categories of state:

1. current canonical artifact content,
2. accepted decisions still in force,
3. rejected proposals or paths that must not be silently reintroduced,
4. unresolved issues still requiring closure,
5. invariant constraints that must survive each round,
6. the latest architect-side delta,
7. the latest auditor-side delta,
8. a concise causal account of the recent path to the current state.

These categories are required authority categories for the lane. The exact storage shape is implementation work and is not fixed here.

## 10. Required State-Transition Semantics

The continuity-tracked items must obey the following state semantics:

### 10.1 Allowed item states

An item tracked for continuity may be in exactly one of the following states at a time:

1. `unresolved`
2. `accepted`
3. `rejected`
4. `superseded`

### 10.2 Allowed transitions

The allowed transitions are:

1. `unresolved -> accepted`
2. `unresolved -> rejected`
3. `accepted -> superseded`
4. `unresolved -> superseded` only if an explicit successor item absorbs and closes the original issue

The following direct transitions are forbidden unless represented as a two-step governed sequence through a newly created item:

1. `accepted -> unresolved`
2. `accepted -> rejected`
3. `rejected -> accepted`
4. silent deletion of any tracked item from the authoritative state

### 10.3 Reopened items

A reopened item is not a normal state. It is an evaluation event recorded when a previously `accepted` item later appears to have returned to unresolved, contradictory, omitted, or implicitly replaced status without explicit supersession.

### 10.4 Supersession requirement

Any supersession must explicitly record:

1. the prior item identifier,
2. the successor item identifier,
3. the reason for supersession,
4. the round in which the supersession occurred.

### 10.5 Contradiction rule

A contradiction event must be recorded when a later round materially conflicts with an accepted decision or invariant without an explicit supersession record.

### 10.6 Regression rule

A regression event must be recorded when a later round degrades previously preserved continuity state into missing, unresolved, contradictory, or materially weakened form without governed explanation.

## 11. Inspectability Artifact Requirements

For every round in every continuity mode, the run artifacts must preserve enough information to reconstruct the loaded context.

At minimum, the per-round inspectability surface must include:

1. the loaded context artifact for that round,
2. the source inputs used to construct that loaded context,
3. the continuity mode identifier,
4. a stable hash of the loaded context artifact,
5. a stable hash of each source input artifact,
6. for V0, the bounded replay artifact and its source-history references,
7. for V1, the compiled shared-state snapshot for that round,
8. for V1, the role-view derivation artifact or equivalent prompt-ready projection for that round,
9. enough metadata to determine why the loaded context changed from the prior round.

## 12. Evaluation Metric Semantics

The following metric definitions are locked for this lane.

### 12.1 Active-context size behavior

Active-context size behavior must be measured in both:

1. UTF-8 bytes of the final provider-bound prompt input, and
2. provider-request token count when the provider exposes a trustworthy pre-generation token count.

If provider token count is unavailable, bytes remain the required comparison unit.

### 12.2 Reopened-decision count

A reopened-decision event is counted once each time a previously accepted item is later detected as unresolved, contradicted, omitted in a materially conflicting way, or implicitly replaced without explicit supersession.

### 12.3 Carry-forward integrity

Carry-forward integrity is defined per run as:

`accepted decisions preserved without contradiction or unauthorized reopening in later rounds / total accepted decisions created before the final round`

This must be reported as both a fraction and a percentage.

### 12.4 Contradiction count

A contradiction event is counted once per accepted item or invariant per round when a later round materially conflicts with that item or invariant without explicit supersession.

### 12.5 Regression count

A regression event is counted once per item per round when continuity state that had previously been preserved becomes missing, weakened, unresolved, or contradictory without governed justification.

### 12.6 Primary aggregation unit

The primary aggregation unit for this lane is the `scenario-run`.

A scenario-run is exactly one scenario executed under one:

1. continuity mode,
2. model-role pair,
3. locked round budget.

### 12.7 Scenario-run metrics

For each scenario-run, Orket must compute and record at minimum:

1. convergence result as `0` or `1`,
2. reopened-decision count,
3. contradiction count,
4. regression count,
5. carry-forward integrity,
6. median round latency for that scenario-run,
7. median round active-context size for that scenario-run.

### 12.8 Pair-budget aggregation

For each continuity mode, pair, and locked round budget, Orket must compute pair-budget aggregates from the scenario-runs for that exact pair-budget slice.

The pair-budget aggregate rules are:

1. convergence rate = arithmetic mean of scenario-run convergence results,
2. reopened-decision rate = arithmetic mean of scenario-run reopened-decision counts,
3. contradiction rate = arithmetic mean of scenario-run contradiction counts,
4. regression rate = arithmetic mean of scenario-run regression counts,
5. carry-forward integrity = arithmetic mean of scenario-run carry-forward integrity values,
6. median per-round latency = arithmetic median of scenario-run median round latencies,
7. median per-round active-context size = arithmetic median of scenario-run median round active-context sizes.

### 12.9 Primary threshold pooling rule

All threshold decisions in Section 15 must be made separately for each locked round budget.

For a given continuity mode and locked round budget, the primary comparison value for each metric is the arithmetic mean of the corresponding pair-budget aggregate across all pre-registered included pairs.

This makes pairs equally weighted in the threshold decision regardless of scenario count.

### 12.10 Absolute case delta requirement

Whenever a percentage-point improvement claim is reported for convergence, Orket must also report the absolute delta in converged scenario-runs at the same locked round budget.

### 12.11 Zero-tolerance interpretation

The `does not increase` rules in Section 15 are intentionally strict.

For this lane, `does not increase` means the relevant budget-scoped pair-equal aggregate rate must be numerically less than or equal to the comparison mode value. No noise tolerance, rounding tolerance, or discretionary exception may be applied.

## 13. Pair Selection Pre-Registration

The primary continuity comparison matrix must be pre-registered before continuity experiments begin.

The pre-registration must name:

1. the included model-role pairs,
2. the excluded model-role pairs,
3. the artifact evidence used for that decision,
4. the explicit thresholds used.

The selection policy for this lane is:

**use the best currently available continuity-testable pairs, while excluding pairs whose prior evidence is too structurally contaminated to make continuity conclusions trustworthy.**

The default selection thresholds for this lane are:

1. for each candidate pair, cite at least one baseline artifact and one compare or swap artifact when both exist,
2. compute `overall_structural_failure_rate` for each candidate pair as `(format-failure scenario-runs + provider-leak scenario-runs + code-leak scenario-runs) / total cited prior scenario-runs for that pair`,
3. compute `compare_structural_failure_rate` for each candidate pair as `(format-failure scenario-runs + provider-leak scenario-runs + code-leak scenario-runs in compare or swap artifacts only) / total cited prior compare or swap scenario-runs for that pair`,
4. exclude any pair with `overall_structural_failure_rate > 0.5`,
5. exclude any pair with `compare_structural_failure_rate > 0.5`,
6. exclude any pair whose dominant observed failure mode is structural in more than half of its cited compare or swap artifacts,
7. include only pairs whose remaining dominant failure modes are primarily semantic, such as max-round stall, unresolved decisions, or invalid convergence without structural failure,
8. if more than two pairs satisfy the thresholds, rank them in this order:

   1. lower `overall_structural_failure_rate`,
   2. lower `compare_structural_failure_rate`,
   3. higher semantic-failure share,
   4. higher prior convergence rate across the cited artifacts,
9. select the top two ranked pairs when two or more pairs qualify.

If only one pair satisfies these thresholds, the lane may proceed with a single-pair primary matrix, but all acceptance and final reporting must explicitly state that the primary comparison evidence is single-pair bounded.

If multiple pairs satisfy these thresholds but exactly one pair is uniquely top-ranked under the pre-registered ranking order, the lane may designate that pair as the primary pair and treat the remaining qualifying pairs only as secondary sensitivity checks.

This preference rule may not be used to alter the locked threshold outcomes. It exists only to preserve continuity-signal clarity when admissibility is broader than true credibility.

If no pair satisfies these thresholds, the lane must explicitly record that no currently available pair is continuity-testable under this authority rather than loosening the thresholds silently.

## 14. Evaluation Requirements

### 14.1 Control requirement

The currently shipped replay behavior must remain runnable as the control so that continuity changes can be compared against a real baseline.

### 14.2 Bounded pair requirement

The primary experiment set must use the pre-registered bounded set of model-role pairs selected under Section 13 so that continuity rather than structural instability is being tested.

### 14.3 Fixed-scenario comparison requirement

Continuity modes must be compared on the same bounded scenario set so that run-to-run differences are attributable to continuity mode and round budget rather than scenario drift.

### 14.4 Evidence requirement

The comparison output must make it possible to answer all of the following:

1. Did stronger continuity improve convergence?
2. Did stronger continuity reduce reopened decisions and contradictions?
3. Did stronger continuity mainly help at the 5-round budget, the 9-round budget, or both?
4. Did stronger continuity increase cost or latency in a way that outweighed the gain?
5. Did V1 materially outperform V0 enough to justify the stronger abstraction?

## 15. Material-Improvement Decision Rule

This lane must use the following locked decision rule for determining whether V0 or V1 is worthwhile.

All worthwhile determinations are budget-scoped first.

A continuity mode may therefore receive any of the following verdict forms:

1. `worthwhile_at_5_rounds`
2. `worthwhile_at_9_rounds`
3. `worthwhile_at_both_locked_budgets`
4. `continuity_quality_success_only`
5. `not_materially_worthwhile`

A mode may be described as worthwhile without a budget qualifier only if it is worthwhile at both locked budgets.

### 15.1 V0 worthwhile threshold

V0 is considered materially worthwhile at a given locked round budget only if, relative to the frozen control and on the pre-registered primary matrix at that same budget:

1. the budget-scoped pair-equal aggregate convergence rate improves by at least `20` percentage points,
2. the absolute delta in converged scenario-runs is at least `+1`,
3. the budget-scoped pair-equal reopened-decision rate does not increase,
4. the budget-scoped pair-equal contradiction rate does not increase,
5. the budget-scoped pair-equal median per-round active-context size does not exceed `2.0x` the control,
6. the budget-scoped pair-equal median per-round latency does not exceed `2.5x` the control.

### 15.2 V0 cross-budget rule

If V0 satisfies Section 15.1 at one locked budget but not the other, Orket may claim only the corresponding budget-scoped worthwhile verdict.

A global worthwhile claim for V0 requires qualification at both locked budgets.

### 15.3 V1 full worthwhile threshold

V1 is considered materially worthwhile at a given locked round budget only if, relative to V0 and on the same primary matrix at that same budget:

1. the budget-scoped pair-equal aggregate convergence rate improves by at least `10` additional percentage points,
2. the absolute delta in converged scenario-runs is at least `+1`,
3. the budget-scoped pair-equal reopened-decision rate does not increase,
4. the budget-scoped pair-equal contradiction rate does not increase,
5. the budget-scoped pair-equal median per-round active-context size does not exceed `1.5x` V0,
6. the budget-scoped pair-equal median per-round latency does not exceed `1.75x` V0.

### 15.4 V1 continuity-quality success threshold

If V1 does not satisfy Section 15.3, it may still qualify for the verdict `continuity_quality_success_only` at a given locked round budget only if, relative to V0 at that same budget:

1. the budget-scoped pair-equal carry-forward integrity improves by at least `15` percentage points,
2. the budget-scoped pair-equal aggregate convergence rate does not decrease,
3. the absolute delta in converged scenario-runs is not negative,
4. the budget-scoped pair-equal reopened-decision rate does not increase,
5. the budget-scoped pair-equal contradiction rate does not increase,
6. the budget-scoped pair-equal median per-round active-context size does not exceed `1.5x` V0,
7. the budget-scoped pair-equal median per-round latency does not exceed `1.75x` V0.

A `continuity_quality_success_only` verdict may not be described as improved convergence reliability.

### 15.5 Cross-budget degradation rule

If a continuity mode qualifies at one locked budget but shows both:

1. a convergence-rate decline greater than `5` percentage points at the other locked budget, and
2. an increase in either reopened-decision rate or contradiction rate at that other locked budget,

then only the budget-scoped verdict may be claimed. No cross-budget generalization is allowed.

### 15.6 Non-qualification rule

If a continuity mode fails its applicable worthwhile threshold, the lane may still report interesting findings, but it may not claim that the mode materially improved ODR continuity for the purpose of acceptance or follow-on authorization.

## 16. Acceptance Criteria

This lane is not complete merely because V0 or V1 exists.

The lane is complete only when the requirements-defined comparison produces enough trustworthy evidence to determine:

1. whether log-derived replay materially improves ODR continuity over the frozen control,
2. whether compiled shared state materially improves ODR continuity over V0,
3. whether the healthier model-role pairs benefit from additional rounds when continuity is improved,
4. whether the resulting improvement is substantive enough to justify follow-on implementation work.

## 17. Follow-On Boundary

If the comparison shows that continuity work is beneficial, follow-on lanes may address:

1. broader memory abstractions,
2. auxiliary retrieval layers,
3. optional role-local scratchpads,
4. continuity support for additional workloads.

Those follow-on items are not authorized by this requirements document and must be separately scoped.

## 18. Final Intent

This lane is successful if ODR stops behaving like a fresh prompt with a thin memory of the last critique and starts behaving like a stateless execution model over a durable, inspectable, shared run context.
