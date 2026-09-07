# Governed Agent Core Runtime Plan

Last updated: 2026-09-07
Date: 2026-09-06
Status: Active implementation workstream
Owner: Orket Core
Coordinating authority: `docs/projects/governed-agent-loop/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`
Durable contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`

## Objective

Implement the Orket host capabilities required to govern bounded agent loops and
fixed multi-model teams supplied by external extensions.

This plan owns everything that must remain authoritative even when the extension
or local model is replaced: workload admission, iteration progression, provider
resolution, budgets, effects, approvals, scheduling, recovery, inspection, and
terminal truth.

## Product outcome

An operator can submit one agent objective and loop policy, allow Orket to wake
and run bounded iterations through an external SDK workload, inspect every
decision and effect, interrupt or resume safely, and receive durable terminal
truth supported by verifier or operator evidence.

The host may remain continuously available. Agent iterations remain bounded and
must receive a fresh supervisor continuation decision.

## Preconditions and current status

1. Requirements acceptance was explicitly satisfied on 2026-09-06.
2. The accepted durable contract is in
   `docs/specs/GOVERNED_AGENT_LOOP_V1.md`.
3. The initial contract delta is recorded in
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_V1_2026-09-06.md`;
   behavior-changing slices must update it or add narrower deltas as required.
4. API/supervisor integration prerequisite: architectural-truth Slice B2 removes
   module-default API ownership and moves interface-owned composition into
   application containers. Its owner is
   `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`,
   Slice B items 4-5, and exception `AT-EX-002`. Independent contract/governor
   work can proceed.
5. Ongoing gate: any async-reachable paths touched by this work satisfy the repository's async
   safety rules and have bounded teardown.
6. Integration prerequisite: the SDK agent contract must be available from a pinned
   development wheel; final publication follows joint host/extension proof.
7. Slices 0-5 are implemented on bounded CLI/application paths. The dedicated
   catalog-resolved agent path owns a
   bounded application governor, durable SQLite repository, framed child
   adapter, host broker, deterministic verifier, and CLI inspection surface.
   The generic extension executor continues to refuse agent workloads.
8. Live Ollama inference, governed effects/approval/recovery, and fixed
   multi-model roles are proven. The durable wake queue, continuous supervisor,
   API/session composition, and generalized capacity ownership remain Slice 6
   work blocked by architectural-truth B2.

## Accepted authority and object mapping

The accepted V1 mapping is:

1. a catalog-resolved `WorkloadRecord` defines the executable workload; each
   submitted objective creates a separate `RunRecord` referencing that definition;
2. a crash/recovery generation maps to an `AttemptRecord`;
3. each admitted agent iteration maps to a stable orchestration `StepRecord`;
4. model calls, effect proposals, approvals, effects, and verification records
   link to that iteration step through durable refs;
5. an effect remains authoritative only through the existing governed effect
   and effect-journal path;
6. final objective truth remains one `FinalTruthRecord` supported by an admitted
   verifier or operator decision;
7. no `IterationRecord` is introduced in V1; any later new object needs an
   explicit contract delta.

## Design locks

1. The application layer owns loop progression and final truth.
2. Each iteration begins only after an explicit deterministic supervisor
   decision over durable inputs.
3. The extension is invoked as replaceable strategy and never receives direct
   control-plane repository access.
4. Model selection is resolved and snapshotted by the host.
5. Proposed effects route through existing approval, reservation, lease,
   execution, reconciliation, and journal authority.
6. A checkpoint records state but never grants resume authority.
7. The always-on component is an event-driven supervisor, not an unbounded model
   inference loop.
8. Logs, streams, and summaries remain projections of durable authority.

## Workstream 0 - Durable contracts and architecture gate

1. Bind the accepted object mapping, continuation vocabulary, budget semantics,
   effect behavior, operator commands, and Ollama-backed live integration to
   canonical schemas and implementation types.
2. Define the governed agent-loop admission seam now; register it and update the
   canonical workload/start-path matrix in Slice 2 only when the governed
   invocation path and its proof exist. Do not list a planned path as admitted.
3. Define schemas for loop submission, iteration exchange, continuation
   decision, budget snapshot, wake event, operator commands, and inspection.
4. Record event-taxonomy and current-authority deltas.
5. Review the proposed call path against every architecture compliance check.
6. Reuse `orket/runtime/config/provider_runtime_target.py` and the existing
   local-prompting profile authority for host model resolution; do not implement
   a competing provider discovery, quarantine, or prompting registry.
7. Inspect the existing extension publisher in
   `orket/extensions/workload_executor.py` and define the iteration invocation
   adapter beneath its independent-run lifecycle. The agent governor retains the
   parent run and iteration step; invoking strategy must not close that run.
8. Close S0-A across SDK install, persisted catalog reload, and executor dispatch.
   Revalidate every agent discriminator before execution artifacts or child
   startup; a generic registry/config entry cannot materialize the broker marker.
   Preserve a stable unavailable-runtime refusal until the governed path exists.
9. Define application governor/invocation ports and durable repository operations
   by reusing existing control-plane contracts. Specify dispatch intent, atomic
   compare-and-set result acceptance, cancellation/fencing checks, and recovery
   of interrupted publication; separate writes are not an atomicity guarantee.
10. Record the S0-B requirement-to-schema/host-validation mapping, and the
    architecture checklist with explicit `pass`, `partial`, or `fail` evidence.
    Interface extraction remains with B2, not a second implementation here.

Acceptance gates:

1. One canonical workload-admission seam exists.
2. Interfaces perform transport shaping only.
3. Decision nodes consume explicit inputs and return advisory recommendations.
4. No extension, provider adapter, or decision node can publish authoritative
   run transitions.
5. Installation, real catalog reload, and invocation refusal tests cover malformed
   and legacy agent declarations. A directly constructed manifest object or a
   monkeypatched artifact allocator alone does not prove the installed path.

## Workstream 1 - Agent loop governor

Implement an application-owned governor that:

1. admits the objective, acceptance contract, policy, model-profile requests,
   capabilities, and budgets;
2. creates the parent run and current attempt;
3. builds an immutable context package from authoritative references;
4. records the proposed next iteration before invocation;
5. invokes the external agent workload once;
6. validates and persists its advisory iteration result;
7. routes effect proposals and consumes verified receipts;
8. evaluates deterministic continuation and stop rules;
9. creates the next iteration step only when continuation is authorized;
10. publishes final truth only after the accepted terminal basis exists.

Acceptance gates:

1. No implementation path contains an implicit ungoverned `while continue`.
2. Every invocation has stable run, attempt, and iteration identity.
3. Duplicate submission and duplicate iteration dispatch are idempotent.
4. Malformed or missing extension results fail closed.
5. Persist dispatch intent before external work; atomically compare the current
   attempt, iteration, cancellation state, and fencing generation when accepting
   results or authorizing continuation. Duplicate matching results are idempotent;
   conflicting duplicates are rejected. Time and identity inputs are recorded
   explicitly so replay does not consult a live clock or re-run models.
6. Admission pins the resolved extension artifact, manifest, policy, verifier,
   and model-profile configuration by immutable identity/digest. Later catalog
   edits or extension upgrades cannot silently change an in-flight objective;
   changed artifacts require explicit re-admission/recovery policy.
7. Persist host model-call identity and reservation before dispatch and retain
   the observed receipt independently of the child result. A crash between
   provider response and publication yields recorded uncertainty, not a free
   retry or a reconstructed successful receipt.

## Workstream 2 - Budgets, progress, and terminal decisions

Add host-enforced limits for:

1. iteration count;
2. wall-clock deadline and active lease;
3. model calls and input/output tokens;
4. effect count and capability class;
5. output and artifact bytes;
6. consecutive failures and repair attempts;
7. repeated-state and no-progress thresholds;
8. per-role and total local inference concurrency.

Define deterministic stop priority when several limits trigger together. The
extension and model may observe remaining budget but cannot modify it.

Acceptance gates:

1. Budget exhaustion stops before the next model or effect call.
2. Usage reconciles from provider receipts through iteration and run totals.
3. Repeated-state and no-progress detection use versioned explicit rules.
4. Heuristics never masquerade as proof that the objective succeeded.
5. Per-call broker admission reserves usage before dispatch. Host receipts own
   budget truth; unknown token counts retain a conservative reservation, repairs
   count as calls, and expired provider work is not silently credited back.
6. Repeated-state comparison excludes timestamps and trace ids and uses an
   explicit versioned projection. Only verifier-observed progress resets the
   no-progress counter. Pause time does not silently reset wall-clock budgets.
7. Resolve all required limits from a versioned policy/budget snapshot before
   admission; validate per-role/per-iteration allocations against run totals.
   Cover zero/exhausted limits and partial/unknown usage explicitly, without
   requiring unused optional capability budgets to be positive.

## Workstream 3 - Model target registry and local capacity authority

1. Replace raw model-name-only selection for agent workloads with host-owned
   model target profiles.
2. Resolve each profile to provider, endpoint, model id, prompting profile,
   context/output limits, feature truth, timeout, and health posture.
3. Keep credentials and raw endpoint policy in host configuration.
4. Snapshot requested and resolved targets for every iteration.
5. Add provider health, concurrency, and local resource admission.
6. Represent GPU/model-server capacity with reservations and leases where shared
   use can conflict.
7. Define explicit unavailable, substituted, degraded, quarantined, and blocked
   outcomes.
8. Keep model-process start/stop/download outside the first slice unless a later
   adapter contract explicitly admits it.

Acceptance gates:

1. Planner, actor, and critic requests can resolve to distinct local models.
2. Per-profile endpoint selection does not depend on mutable global environment
   reads inside decision nodes.
3. Capacity exhaustion queues or blocks truthfully instead of oversubscribing.
4. Provider feature drift fails before an unsupported structured/tool call.

## Workstream 4 - Governed effect integration

1. Validate extension effect proposals against admitted capability and namespace
   scope.
2. Convert accepted proposals into the canonical governed tool/effect request
   shape.
3. Preserve proposal digest, authorization basis, idempotency identity, intended
   target, and iteration lineage.
4. Pause the loop on approval-required proposals.
5. Resume only from accepted checkpoint and explicit recovery/continuation
   authority after approval.
6. Stop or reconcile on uncertain effect boundaries.
7. Feed only verified effect observations into later iteration context.

Acceptance gates:

1. Proposed, approved, executed, observed, and narrated states remain distinct.
2. Approval denial performs no effect.
3. Crash-before-effect and crash-after-effect paths do not duplicate mutation.
4. Existing governed tool security boundaries are not widened.
5. Bind complete immutable arguments and target lineage to the approval digest;
   changed arguments invalidate approval. Prove the exact existing issue-scoped
   `write_file` path before admitting any agent-specific namespace or continuation.
6. Idempotency is an effect/adapter property, not an unconditional exactly-once
   promise. Crash-after-write-before-receipt requires observation/reconciliation
   before retry, even when a queue lease has expired.

## Workstream 5 - Durable wake queue and supervisor service

1. Add one durable agent-work queue for manual, API, scheduled, webhook, and
   recovery wake reasons.
2. Add one bounded `AgentWakeRecord` repository/table. Existing control-plane
   run, attempt, and step records cannot represent queued/claimed wake identity,
   reason, deduplication, lease/fence, and missed/coalesced-trigger truth without
   overloading execution lifecycle. A wake targets an existing nonterminal run
   or one new scheduled occurrence. This decision does not implement or admit
   the queue before Slice 6 and its B2 prerequisite.
3. Add idempotent enqueue, claim, lease renewal, release, cancellation, and
   missed-trigger behavior.
4. Enforce concurrency, fairness, namespace conflict, and capacity backpressure.
5. Recover expired claims without assuming the previous iteration was effect
   free.
6. Own supervisor tasks and teardown in the application runtime container.
7. Keep a process-level service running while ensuring each claimed run remains
   bounded.

Acceptance gates:

1. Restart preserves queued and claimed work truth.
2. Two supervisors cannot hold valid dispatch authority for the same iteration;
   stale computation cannot publish accepted results or effects.
3. Shutdown leaves no leaked task, subprocess, lease, or half-claimed work item.
4. Missed and coalesced schedule behavior is explicit and tested.
5. Claim acquisition is atomic and returns a fencing generation. A stale worker
   cannot call the broker, authorize effects, or publish accepted results after
   replacement. Do not redispatch while an earlier effect remains uncertain.
6. Wake evidence records whether it targets an existing nonterminal run or a
   new scheduled occurrence; duplicates do not create extra objectives and
   terminal runs are never implicitly reopened.

## Workstream 6 - Context, memory, and handoff assembly

1. Build each iteration context from versioned authoritative refs and admitted
   advisory memory.
2. Enforce truncation, redaction, ordering, byte/token bounds, and provenance.
3. Keep extension-private, role-private, team-shared, objective, and project
   memory scopes distinct.
4. Apply existing memory trust policy before synthesis.
5. Keep role handoffs typed and advisory within one process; cross-agent
   trust-handoff admission remains a later capability outside V1.
6. Prevent raw transcripts from becoming hidden authoritative state.
7. Make the full decision-relevant iteration input reconstructable offline.
8. Select a bounded delivery path for referenced objective, acceptance, fixture,
   prior output, and receipt contents in Slice 0. Host materialization or a scoped
   read-only broker resolver must check ownership, digest, size, provenance, and
   cancellation; the child may not read host paths or stores directly. Prove this
   delivery through the actual child process in Slice 2.

Acceptance gates:

1. Context reconstruction produces the same canonical input package from the
   same refs.
2. Stale or unverified memory is excluded according to policy.
3. Handoff scope and capability narrowing fail closed on drift.

## Workstream 7 - Completion verifier registry

1. Define admitted verifier classes:
   - deterministic predicate;
   - schema or contract validation;
   - integration observation;
   - operator decision;
   - model advisory evaluation.
2. Bind each objective to an accepted verifier or explicit operator-only
   completion policy.
3. Record verifier inputs, version, result, and evidence refs.
4. Prevent a model-only recommendation from yielding verified success.
5. Define evidence-insufficient, degraded, blocked, and failed terminal behavior.

Acceptance gates:

1. Verified success always links to an admitted non-advisory basis.
2. Missing or contradictory evidence fails closed.
3. Offline inspection explains why the run ended.

## Workstream 8 - Operator API, CLI, and session inspector

Expose application-backed commands to:

1. submit an objective;
2. inspect current state and timeline;
3. pause, resume, stop, and cancel with preconditions;
4. approve or deny pending effects;
5. inspect remaining budgets, active leases, provider targets, last verified
   progress, pending work, and terminal basis;
6. perform non-mutating replay of continuation decisions.

The first session inspector must show:

1. wake reason and queue/claim state;
2. run, attempt, and iteration identity;
3. requested and resolved model profile per role;
4. context and evidence refs;
5. effect and approval lifecycle;
6. budget deltas;
7. continuation decision and terminal truth.

Acceptance gates:

1. An operator can answer what is running, why it may continue, what it can
   affect, what it is waiting on, and why it stopped.
2. Commands are idempotent and produce operator-action authority.
3. Streaming remains a bounded projection and can reconnect from durable state.

## Workstream 9 - Recovery, replay, and proof envelope

Required deterministic fixtures:

1. verified success;
2. budget exhaustion;
3. repeated state/no progress;
4. denied effect;
5. uncertain effect;
6. crash before extension invocation;
7. crash after extension result but before continuation publication;
8. crash before effect;
9. crash after effect;
10. provider unavailable or substituted;
11. cancellation during model generation;
12. expired queue or execution lease.

Required test classification:

1. `unit`: deterministic continuation, budget, and context rules.
2. `contract`: all wire schemas, result vocabulary, and fail-closed parsing.
3. `integration`: repositories, queue claims, extension subprocess, provider
   profile resolution, approvals, effects, and recovery.
4. `end-to-end`: public submission through one terminal single-agent run and one
   fixed multi-model extension run using real local models.

Routine live proof must set `ORKET_DISABLE_SANDBOX=1`. Intentional sandbox proof
must prove teardown in the same execution path.

Acceptance gates:

1. Every continuation decision is explainable from durable recorded inputs.
2. Replay is non-mutating.
3. Restart proof observes no duplicated effect.
4. Live proof records path as primary, fallback, degraded, or blocked and result
   as success, failure, partial success, or environment blocker.
5. Architecture checklist results contain no new violation.

## Delivery sequence

Use the slice sequence and concrete report acceptance workload in
`docs/projects/governed-agent-loop/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`.
These workstreams describe core responsibilities; they do not override that
sequence. Start with two deterministic iterations, minimum inspection, and a
host broker; exercise the same workload with one local model before fixed roles
and durable wake processing. Slice 2's minimum submit/inspect/cancel/replay uses
the canonical CLI backed by application services. API/supervisor composition
waits for B2 even if attempted before Slice 6.

## Completion criteria

This plan is complete only when:

1. one canonical governed agent-loop workload exists;
2. an external SDK extension completes bounded iterations without private host
   access;
3. effects, approvals, checkpoints, recovery, and final truth reuse existing
   authority;
4. local multi-model profile selection and capacity admission are explicit;
5. durable scheduling survives restart and duplicate claims;
6. the operator inspector explains the full run;
7. deterministic, integration, and live end-to-end proof all pass;
8. all touched authority documents and runtime entrypoints agree;
9. the user accepts the live proof and explicitly closes the implementation
   lane.

## Non-goals

1. An unrestricted autonomous swarm.
2. Agent-controlled credentials, endpoints, capability grants, or budgets.
3. Treating model output as execution or completion truth.
4. A second workflow engine inside an extension.
5. Provider model download or GPU process management in the first slice.
6. Automatic resume solely because saved state exists.
