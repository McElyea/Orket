# Governed Agent Loop Requirements Definition Plan

Last updated: 2026-09-06
Status: Archived requirements phase; transitioned to active implementation
Owner: Orket Core

## Purpose

Define a bounded Orket capability that can supervise a looping agent without making model output, loop-local state, or a third-party agent framework authoritative for execution truth.

The user accepted this requirements direction and explicitly requested an
implementation plan on 2026-09-06. Durable contract authority now lives in
`docs/specs/GOVERNED_AGENT_LOOP_V1.md`; implementation sequencing lives in
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`.

## Product outcome

An operator can submit one agent workload with an explicit objective and loop policy. Orket decides whether each iteration may start, records what the iteration observed and proposed, authorizes or blocks effects through existing governed seams, and ends with durable terminal truth.

The first slice should govern one agent running iterations sequentially. Multi-agent fan-out, free-form workflow graphs, and unattended open-ended autonomy are later extensions, not first-slice shortcuts.

## Existing authority to reuse

1. Control-plane run, attempt, step, reservation, lease, checkpoint, recovery, effect-journal, and final-truth contracts under `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`.
2. Governed workload minting and start-path rules in `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`.
3. Approval continuation rules in `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md` and `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md`.
4. Cross-agent artifact admission in `docs/specs/TRUST_HANDOFF_PACKET1_V1.md`.
5. Runtime layering, deterministic authority, bounded decision nodes, verified effects, and replay rules in `docs/ARCHITECTURE.md`.

The loop governor must compose these authorities. It must not duplicate their records, vocabularies, or ownership rules.

## First-slice boundary

In scope:

1. one parent governed run for one loop session,
2. one sequential iteration at a time,
3. explicit objective, policy, budget, and acceptance inputs,
4. supervisor-owned continue, pause, stop, and terminal decisions,
5. existing governed tool and approval paths for effects,
6. checkpoint-backed recovery where the admitted path supports recovery,
7. durable per-iteration evidence and final truth,
8. a local deterministic fixture plus one real agent integration path for live proof.

Out of scope:

1. parallel agents or worker swarms,
2. multi-hop trust handoffs,
3. a general workflow language,
4. silent self-extension of budget or capability grants,
5. unrestricted shell, network, filesystem, or credential authority,
6. semantic claims that an objective is complete without an admitted verifier or operator decision,
7. automatic resume merely because a process restarts or saved state exists.

## Required design locks

1. The application layer owns loop progression and terminal truth. Agent or model output is advisory input.
2. Every iteration has a stable identity tied to the parent run and current attempt.
3. Starting another iteration is a fresh supervisor decision, not an implicit `while` continuation.
4. Budget exhaustion is terminal or operator-paused according to resolved policy; the agent cannot increase its own budget.
5. Proposed effects use existing capability, approval, reservation, lease, and effect-journal authority.
6. A checkpoint does not grant resume authority. Resume requires checkpoint acceptance and an explicit recovery decision.
7. Completion, failure, blocked, degraded, and advisory outcomes retain the canonical runtime vocabulary.
8. Repeated-state, no-progress, and policy-violation detection use explicit inputs and versioned rules.
9. Logs and summaries are projections of durable authority, not alternate authority.
10. First-slice integration must be replaceable at the adapter boundary; Orket governs the loop and does not become coupled to one agent vendor.

## Work items

### 1. Authority and object model

Define how the loop session maps onto existing `WorkloadRecord`, `RunRecord`, `AttemptRecord`, and `StepRecord` authority. Decide whether an iteration is a step or a child workload; do not invent an `IterationRecord` unless the existing model cannot represent required truth without ambiguity.

Acceptance questions:

1. Which existing object owns objective, loop policy, and terminal truth?
2. How are iteration ids minted deterministically?
3. What is the exact boundary between a retry attempt and a new loop iteration?
4. Which one seam may admit the loop workload?

### 2. Loop input and continuation contract

Define a versioned request containing the objective, initial context references, allowed capabilities, resolved policy reference, budget, completion verifier, and recovery posture. Define a versioned iteration result that separates observation, advisory proposal, effect requests, claimed progress, and completion recommendation.

Acceptance questions:

1. What minimum evidence permits `continue`?
2. What evidence permits a verified `success` terminal result?
3. When must an operator decide instead of an automated rule?
4. Which malformed or missing fields fail closed?

### 3. Budgets, progress, and termination

Define hard limits for iterations, wall-clock lease, model or provider use, tool effects, output size, and repeated failures. Define deterministic stop priority when several limits trigger together. Admit bounded no-progress and repeated-state rules without pretending that a heuristic proves task completion.

Required terminal or control reasons:

1. verified objective satisfied,
2. operator stop,
3. iteration budget exhausted,
4. time or lease expired,
5. effect or capability budget exhausted,
6. repeated state or no progress,
7. policy violation,
8. unrecoverable execution failure,
9. evidence insufficient for claimed completion.

### 4. Effect and approval governance

Route each proposed mutation through existing governed effect paths. Specify capability narrowing, namespace ownership, approval interruption, idempotency, effect reconciliation, and what the next iteration may observe after an effect succeeds, fails, or becomes uncertain.

The loop must stop or pause on effect-boundary uncertainty. It must not narrate an intended effect as completed or continue from an unverified mutation.

### 5. Context, artifacts, and handoffs

Define the bounded context assembled for each iteration from authoritative inputs and prior verified outputs. Specify artifact digests, truncation rules, redaction, context-size limits, and provenance. Use the existing trust-handoff contract when outputs cross agent boundaries; do not treat free-form conversation history as trusted state.

First-slice context should be reconstructable offline from durable references.

### 6. Operator control and inspection

Define read surfaces for current objective, iteration count, budgets, last verified progress, pending approvals, active leases, last effect, and terminal reason. Define explicit pause, resume, stop, approve, and deny commands with preconditions and idempotent behavior.

An operator must be able to answer: what is running, why may it continue, what can it affect, what is it waiting on, and what evidence supports its final state?

### 7. Replay, evaluation, and first live proof

Define non-mutating replay of continuation decisions from recorded inputs. Create deterministic fixtures for success, budget exhaustion, repeated state, denied effect, uncertain effect, crash before effect, and crash after effect. Then admit one real sequential agent path and run it end-to-end with sandbox creation disabled unless sandbox behavior is the explicit test target.

Completion requires:

1. contract tests for schema and fail-closed behavior,
2. integration proof for progression, approval, effects, stop, and recovery,
3. one live end-to-end run with the observed path and result recorded,
4. an offline inspection or replay artifact sufficient to explain every continuation decision,
5. architecture checklist results with no new authority or layering violation.

## Requirements acceptance record

On 2026-09-06 the user explicitly authorized the implementation-plan transition
for this requirements direction. The following categories were carried into the
durable contract; precise wire choices and integration details are Orket Core
decisions subject to implementation verification:

1. the single-agent sequential first-slice boundary,
2. the mapping from loop iterations to existing control-plane objects,
3. continuation and terminal decision vocabulary,
4. budget and stop-priority semantics,
5. effect, approval, checkpoint, and recovery behavior,
6. operator command and inspection surfaces,
7. the selected real agent integration for first live proof.

Transition actions completed on 2026-09-06:

1. durable contract extracted to `docs/specs/GOVERNED_AGENT_LOOP_V1.md`;
2. contract delta recorded at
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_V1_2026-09-06.md`;
3. canonical implementation plan created at
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`;
4. roadmap lane updated to point to the implementation plan;
5. the smallest end-to-end vertical slice remains first in implementation order
   before multi-model or continuous-supervisor breadth.

## Historical candidate follow-on capabilities

This list records the requirements-phase candidates. Current scope and delivery
order live in the coordinating implementation plan; inspector, bounded
evaluation, and scheduling work were subsequently admitted there.

1. Governed agent session inspector: a human-readable timeline over run, iteration, approval, effect, checkpoint, budget, and final-truth records.
2. Policy packs: reusable profiles such as read-only research, repository change, issue triage, and infrastructure review with explicit capability and budget envelopes.
3. Counterfactual replay: evaluate how a recorded loop would have stopped or continued under a different policy without re-executing effects.
4. Multi-agent delegation: parent-child budget allocation, capability narrowing, and trust-handoff admission for bounded fan-out.
5. Governed scheduler: durable queueing, concurrency limits, fairness, cancellation, and lease recovery across many loop sessions.
6. Outcome evaluator registry: admitted deterministic, contract, operator, and advisory evaluators with no ambiguous completion authority.
7. Incident and cost guardrails: circuit breakers over repeated failures, provider spend, rate limits, and anomalous effect patterns.

The strongest follow-on after the first vertical slice is the session inspector because it exposes whether the underlying authority is actually understandable before Orket adds concurrency or autonomy.

## Component implementation plans

The following three active component plans decompose the implementation while
remaining subordinate to the canonical coordinating plan:

1. SDK public-contract enablement:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_SDK_ENABLEMENT_PLAN.md`
2. External reference extension:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_LOCAL_AGENT_EXTENSION_PLAN.md`
3. Orket host/runtime enablement:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_CORE_RUNTIME_PLAN.md`

The plans do not create three independent execution authorities. Orket remains
authoritative for loop progression, budgets, approvals, effects, recovery, and
final truth; the SDK exposes public contracts; the extension supplies
replaceable agent strategy.

## Lane closeout

The requirements phase closed through explicit user acceptance on 2026-09-06.
Implementation completion and whole-lane closeout are governed by
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`.
