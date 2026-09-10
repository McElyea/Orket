# Governed Continuous Agent Implementation Plan

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Last updated: 2026-09-09
Date: 2026-09-06
Status: Archived — accepted implementation closeout
Roadmap state: Retired from active execution
Execution state: All slices accepted; release boundary core 0.6.0 / SDK 0.6.0 / external 0.2.0
Owner: Orket Core

## Objective

Ship one continuously available but bounded Orket agent runtime in which an
external SDK extension can use fixed local-model roles while Orket alone governs
workload admission, every iteration, budgets, effects, approvals, recovery,
scheduling, and final truth.

## Activation record

The user accepted the requirements and explicitly authorized implementation on
2026-09-06.

Activation state:

1. requirements acceptance: recorded;
2. durable contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`;
3. contract delta:
   `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_V1_2026-09-06.md`;
4. roadmap lane: active at the top of `Priority Now`;
5. SDK, extension, and core runtime component plans: active subordinate
   workstreams;
6. runtime implementation: not yet present at plan activation; bounded Slices
   0-5 and the Slice 6A-6H durable API/manual/scheduled/webhook/effect supervisor/control and live-provider path were subsequently
   implemented as recorded below.

Implementation authorization covers the product direction. Concrete protocol,
provider, and packaging choices below are Orket Core design decisions and remain
subject to the recorded compatibility and integration gates; they are not claims
that the user separately approved every wire field.

## Canonical authority

This file is the sole roadmap-facing implementation plan for the lane. Detailed
execution requirements live in:

1. SDK: `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_SDK_ENABLEMENT_PLAN.md`;
2. reference extension:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_LOCAL_AGENT_EXTENSION_PLAN.md`;
3. core runtime:
   `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_CORE_RUNTIME_PLAN.md`.

Those files are component plans, not competing lane authorities. Durable
semantics live in `docs/specs/GOVERNED_AGENT_LOOP_V1.md`, and existing
control-plane and extension specs retain their declared precedence.

The implementation review refinement is recorded in
`docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_REVIEW_2026-09-06.md`.
It supersedes the initial delta where broker, compatibility, and proof details
were incomplete. Requirements-phase history is preserved in
`docs/projects/archive/governed-agent-loop/GAL09062026-REQUIREMENTS/GOVERNED_AGENT_LOOP_REQUIREMENTS_DEFINITION_PLAN.md`.

## Fixed implementation boundary

1. One `governed-agent-loop` run owns one objective.
2. Each iteration is one sequential control-plane step.
3. The extension is invoked once per admitted iteration.
4. The reference extension uses fixed planner, actor, and critic roles and may
   resolve them to multiple local models.
5. Fixed roles are stages inside one agent workload, not independent agents or
   child runs.
6. Orket resolves model profiles and capacity without exposing credentials or
   raw endpoint authority.
7. Extension outputs and model judgments are advisory.
8. Orket owns effect execution, approval interruption, recovery, continuation,
   and `FinalTruthRecord` publication.
9. The always-on supervisor is event-driven; every claimed operation and model
   invocation remains bounded.

## Current execution state

Active slice: Slice 7 -- Slices 6A-6H are implemented, and clean package build,
install, ownership, external validation, and installed-artifact live inference
including approval/denial, restart, and non-mutating replay are current. Eleven
installed live cases pass after the final reconciliation. Policy-governed
release actions, the broader architecture gate, and explicit user acceptance remain.

The 2026-09-09 audit closes staged context delivery, partial content verification,
persisted success refs, progress exhaustion, run pause/stop, objective memory,
atomic approval resolution, and observation-only recovery after process exit.
Current evidence and remaining release gates are consolidated in
`SLICE_7_ACCEPTANCE_PROOF_2026-09-09.md`. Earlier checkpoints remain historical;
they do not independently establish acceptance of these corrected behaviors.

Slices 0-5 are implemented on bounded CLI and application-service paths. Their
current proof is recorded in `SLICE_0_CONFORMANCE_MATRIX.md`,
`SLICE_1_2_PROOF_2026-09-07.md`, and `SLICE_3_5_PROOF_2026-09-07.md`:

1. the packaged Draft 2020-12 schema, semantic validator, immutable public SDK
   models, framed IPC codec, child proxies, and shared fixtures bind the full V1
   object family without importing host-private models;
2. SDK `0.5.0a1` and core `0.5.10` build as separate distributions; clean wheel
   and source-distribution inspection proves the core does not co-own
   `orket_extension_sdk`;
3. strict agent discrimination and feature negotiation fail closed across
   author validation, install, catalog reload, and generic invocation;
4. the dedicated governed-agent path resolves the extension through the
   persisted catalog and the canonical control-plane workload authority;
5. the application governor, SQLite repository, real child subprocess, and
   real framed host broker complete two sequential deterministic iterations;
6. the second request contains the first accepted result, each dispatch is
   fenced and compare-and-set accepted, continuation is deterministic, and only
   a host verifier publishes terminal truth;
7. inspect and replay are read-only, cancellation is durable, an in-process
   cancellation test reaps the child, and restart after prepared dispatch moves
   the run to recovery-pending uncertainty without redispatch;
8. the canonical CLI now selects either the deterministic fixture or exact
   installed Ollama identities and reports durable model receipts and proof
   posture;
9. a separately packaged public-SDK-only reference extension passes strict
   source-distribution validation and completes two-iteration live single-model
   and two-model planner/actor/critic paths through host verification;
10. issue-scoped `read_file` observation and approval-required `write_file`
    compose existing pending-gate, operator, reservation, tool-gate,
    effect-journal, checkpoint, recovery, and final-truth authorities;
11. denial performs no mutation, and restart after a write reconciles matching
    intended content without duplicate effect dispatch.

The former S0-A through S0-D blockers are closed by those artifacts and tests.
The Slice 6A queue, claim, bounded supervisor, teardown, and inspection
substrate, Slice 6B production composition, Slice 6C public manual transport,
and Slice 6D wake controls are implemented as recorded later in this plan.
Architectural-truth Slice B2 is
complete and `AT-EX-002` is
removed. Release actions and user acceptance remain open. Live Ollama
supervisor proof is complete in Slice 6E.

### Resolved wake-queue design question

Existing `RunRecord`, `AttemptRecord`, and `StepRecord` objects cannot truthfully
represent queued or claimed wake identity, reason, deduplication, lease/fence,
and missed/coalesced-trigger state without overloading execution lifecycle.
Slice 6 therefore uses one bounded `AgentWakeRecord` repository/table. A
wake targets either an existing nonterminal run or one new scheduled occurrence,
uses compare-and-set claim plus lease and fencing generation, and records manual,
API, scheduled, webhook, or recovery reason. Slice 6A implements and proves the
manual/API/recovery queue plus bounded supervisor substrate. Slice 6B adds
authenticated API wake transport and explicit opt-in production lifecycle
composition. Slice 6C adds public manual enqueue/list/inspect through the same
application ingress authority. Slice 6F adds durable schedule evaluation with
IANA timezone/DST, missed-trigger, and latest-coalescing semantics. Slice 6G
adds API-key plus HMAC authenticated webhook delivery, bounded timestamp replay
protection, and atomic delivery-receipt/wake publication.
Slice 6D adds durable wake-level cancellation/recovery and action inspection;
recovery remains evidence-gated and cannot itself authorize execution.
Slice 6H adds wake-fenced effect preparation plus authenticated approval/denial
and request-bound resume-wake dispatch without introducing another effect or
execution authority.

## Delivery sequence

Component workstream numbers organize responsibilities, not a second execution
order. Slice exit gates below govern progression. SDK development distributions
and the reference fixture are built together with the minimum host path; the
SDK's final release gate waits for integration proof in Slice 7.

### Slice 0 -- Contract bindings and architecture prerequisites

Purpose: make the accepted design executable without creating a second source
of truth.

Required work:

1. complete canonical JSON schemas for submission, iteration request/result,
   model-profile request/receipt, effect proposal, progress, usage, and
   cancellation;
2. add `pause_run` to shared operator-command bindings and validation;
3. define feature negotiation for `governed_agent_loop.v1` within
   `manifest_version: v0`;
4. define the application-owned governor interface and repository ports;
5. record the exact B2 dependency and its owning architectural-truth task;
   require its proof before API/supervisor integration, without duplicating that
   remediation inside this lane; this prerequisite was satisfied on 2026-09-07;
6. update the workload/start-path matrix only when the canonical catalog path is
   implemented;
7. add deterministic positive and negative fixtures shared by SDK contract and
   host tests, covering the S0-B conformance map;
8. specify the `agent_stdio_ipc.v1` broker operations, frame state machine,
   cancellation protocol, and adapter ports. Implement the minimum codec/proxy
   in Slice 1 and the host broker with fake host providers in Slice 2, before
   enabling live providers in Slice 3;
9. characterize old-manifest behavior and define refusal at strict validation
   and runtime admission; optional metadata alone is not a compatibility gate;
10. trace the existing extension run publisher and select an application-owned
    iteration adapter that reuses loading/execution without minting an unrelated
    extension run or finalizing the parent objective.

Acceptance gates:

1. each wire object has one schema authority and stable version;
2. unknown versions and unsupported host features fail closed;
3. no SDK type imports a host-private implementation model;
4. the architecture checklist reports no new authority or dependency violation;
5. existing SDK, extension, controller, and operator contracts remain green.
6. S0-A through S0-D have requirement-specific evidence; happy-path schema
   samples and a green regression suite alone cannot close these gates.

### Slice 1 -- Public SDK agent surface

Detailed authority:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_SDK_ENABLEMENT_PLAN.md`.

Required work:

1. add typed iteration request/result and supporting evidence models;
2. add an explicit async workload protocol, cancellation view, and bounded
   progress surface;
3. add provider-neutral multi-profile model requests and resolved-use receipts;
4. add effect, memory, handoff, usage, and continuation proposal models;
5. extend strict manifest validation and import scanning;
6. update the external template, author guide, and test helpers; build a local
   SDK development wheel for Slices 2-6. Final release evidence follows in Slice 7.

Acceptance gates:

1. a clean environment can author and validate an agent workload from the built
   SDK distribution;
2. planner, actor, and critic profiles can be requested distinctly;
3. effects and continuation remain proposals only;
4. current supported extension contracts retain their compatibility posture.

This slice implements the minimum agent request/result, SDK codec/proxies,
non-streaming model-call contract, and cancellation view first. The codec is
shared with the host; Slice 2 implements retained host authority and the minimum
broker. Required but unavailable features fail closed; streaming and richer
memory behavior cannot be advertised before their own host proof. Existing
`model.generate` and synchronous workloads keep their documented behavior.

### Slice 2 -- Deterministic governed vertical slice

Detailed authority:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_CORE_RUNTIME_PLAN.md`.

Required work:

1. register the workload through the canonical workload catalog;
2. admit one objective, policy, verifier, capability set, model profile, and
   budget;
3. create one run and attempt, then at least two sequential iteration steps;
4. scaffold the external reference package from the canonical template and
   invoke its deterministic fixture through the real child/broker path;
5. record its advisory result and issue one deterministic continuation or
   terminal decision;
6. publish final truth only through an admitted verifier;
7. expose minimal application-backed submit, inspect, cancel, and replay through
   the canonical CLI/catalog path. Do not add an agent API or singleton-backed
   supervisor; completed B2 supplies the application-owned lifecycle seam for
   the later Slice 6B integration.

Acceptance gates:

1. no ungoverned `while` loop or alternate start path exists;
2. malformed, duplicate, cancelled, and exhausted requests fail closed;
3. offline replay explains the continuation decision;
4. restart before or after extension invocation preserves truthful state.
5. the second iteration receives the first iteration's recorded evidence and a
   fresh authorization; a one-shot workload smoke is insufficient loop proof.
6. the real child process uses the real host broker with deterministic host model
   responses; cancellation, disconnect, stale results, and crash recovery are
   observed on that path. Fake inference is not live local-model proof.

### Slice 3 -- External single-model reference extension

Detailed authority:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_LOCAL_AGENT_EXTENSION_PLAN.md`.

Required work:

1. extend the external `GovernedLocalAgent` package scaffold used in Slice 2;
2. preserve the same deterministic fixture and acceptance objective;
3. implement one host-resolved Ollama model role through public SDK only;
4. add structured-output repair within issued budgets;
5. record actual model/profile identity, usage, latency, truncation, and finish
   reason;
6. prove strict author and host validation from the built distribution.

Acceptance gates:

1. the external package imports no private `orket.*` module;
2. one real single-model run crosses at least two admitted iterations and reaches
   a verified terminal state;
3. unavailable or incompatible local inference reports an environment blocker
   or explicit failure rather than false success.

### Slice 4 -- Governed effects, approval, and recovery

Required work:

1. translate extension proposals into the existing governed tool/effect path;
2. exercise one observe-only action and one bounded local mutation already
   admitted by the turn-tool approval contract;
3. add pause, resume, stop, approval, denial, and cancellation behavior;
4. add checkpoint acceptance and explicit recovery decisions;
5. cover crashes before proposal, after proposal, before effect, and after
   effect;
6. require reconciliation on uncertain boundaries.
7. prove the exact issue namespace, target run/attempt, approval request,
   checkpoint, and effect lineage when composing the current `write_file`
   approval path. Reusing a tool name does not admit a new agent namespace;
   record a narrower contract delta before widening any existing scope.

Acceptance gates:

1. no mutation occurs before host authorization;
2. approval denial applies no effect;
3. restart never duplicates an admitted effect;
4. checkpoint presence alone never resumes work;
5. later iterations receive only verified effect observations.

### Slice 5 -- Fixed multi-model planner, actor, and critic

Required work:

1. activate distinct planner, actor, and critic role requests;
2. preserve typed, bounded, advisory role handoffs;
3. enforce per-role and total model/token/concurrency budgets;
4. record requested and actual target identity per role;
5. support policy-approved substitution and explicit unavailable/degraded
   outcomes;
6. run the live Ollama proof with at least two distinct model identities.

Acceptance gates:

1. role and model identity remain distinct and inspectable;
2. one role failure cannot fabricate team success;
3. completion still requires a host-admitted verifier;
4. repeated-state and no-progress rules remain deterministic and versioned.

### Slice 6 -- Durable continuous supervisor and session inspector

Required work:

1. add one durable agent wake queue for manual, API, scheduled, webhook, and
   recovery reasons;
2. add idempotent claim, lease renewal, release, cancellation, backpressure, and
   expired-claim recovery;
3. own supervisor tasks and teardown in the application runtime container;
4. enforce provider and local-capacity admission;
5. add a session inspector covering wake, run, attempt, iteration, role,
   evidence, effect, approval, budget, continuation, and final truth;
6. keep replay non-mutating and rebuild projections from durable state.
7. ship durable manual/API wakes and recovery first, then scheduled and webhook
   ingress as separate checked increments within this slice; define schedule
   timezone, missed/coalesced triggers, webhook authentication, and deduplication;
8. use compare-and-set claims with fencing generations checked on every broker
   call, effect dispatch, and result publication; lease expiry alone does not
   establish that an old worker stopped.

Acceptance gates:

1. competing supervisors cannot obtain simultaneous valid dispatch ownership
   or publish accepted results/effects for the same iteration; stale computation
   may persist until confirmed stopped and must remain fenced from authority;
2. restart preserves queued and claimed truth;
3. shutdown leaks no task, subprocess, queue claim, or capacity lease;
4. an operator can explain what is running, why it may continue, what it can
   affect, what it awaits, and why it stopped.

Slice 6A checkpoint status: implemented on 2026-09-07. One SQLite queue now
admits only manual, API, and recovery provenance tokens; provides idempotent
enqueue, capacity backpressure, atomic claims, renewal, cancellation, release,
completion, monotonic fencing, and fail-closed expired-claim recovery; and is
consumed by a bounded event-driven application supervisor with a dispatcher
claim guard. The existing inspector now includes wake and claim truth for an
existing run, and `ApiRuntimeContainer` can own and close registered resources
plus their tasks. This is queue/supervisor substrate, not production continuous
operation: no public wake ingress, existing loop/broker/effect composition,
provider-capacity policy, scheduled/webhook ingress, or production API
lifecycle activation is admitted. B2 is now complete; those behaviors remain
for later Slice 6 increments. Evidence:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6A_PROOF_2026-09-07.md`.

Slice 6B checkpoint status: implemented on 2026-09-07. Each API factory app now
owns one governed-agent runtime graph and closes its supervisor, renewal task,
active dispatch, provider, and child process through the lifespan. Authenticated
API wakes persist even when supervision is disabled; explicit activation
dispatches new-run and existing-run work through the same catalog-resolved
bounded loop, broker, verifier, and final-truth authorities as the CLI. The
durable claim count is the configured provider/local capacity reservation,
claims renew while bounded work is active, and the wake guard is rechecked at
broker and result publication boundaries. Inspection composes wakes, roles and
model receipts, budgets, effects, approvals, checkpoints, operator actions,
continuation, and final truth, with a concise operator explanation. At the 6B
checkpoint, scheduled and webhook ingress, public manual-wake transport,
generalized wake-driven effect/recovery dispatch, and live Ollama supervisor
proof remained later checked increments. Evidence:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6B_PROOF_2026-09-07.md`.

Slice 6C checkpoint status: implemented on 2026-09-07. The nested `orket agent
wake` CLI now enqueues new-run or existing-run manual occurrences and lists or
inspects their durable state. Manual and API transports share one strict
application ingress service and use source-scoped stable identities. The CLI
does not start a supervisor, provider, child, or loop. End-to-end proof persists
the manual wake before API app construction, then observes the explicitly
enabled API-owned supervisor claim it and publish verifier-backed final truth.
Evidence: `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6C_PROOF_2026-09-07.md`.

Slice 6D checkpoint status: implemented on 2026-09-07. Authenticated API and
nested CLI wake controls now publish canonical operator actions,
cancellation/recovery transitions, and specialized wake-action receipts
atomically. Claimed cancellation retains uncertainty and
capacity; `requeue` and `confirm_cancelled` require matching fencing generation,
confirmed child stop, cleared effect uncertainty, and evidence references.
Exact replay is idempotent, contradictory reuse conflicts, restart preserves
the receipts, and composed run inspection includes both operator actions and
wake actions. Evidence:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6D_PROOF_2026-09-07.md`.

Slice 6E checkpoint status: proven on 2026-09-07. One authenticated API wake
was durably claimed by the API-owned supervisor, dispatched through the real
external child and exact installed `qwen2.5:7b` plus `qwen2.5-coder:7b` role
targets, completed two bounded iterations, published verifier-backed terminal
truth, and left zero tracked background tasks after lifespan shutdown. Evidence:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6E_PROOF_2026-09-07.md`.

Slice 6F checkpoint status: implemented on 2026-09-07. Authenticated schedule
evaluation converts explicit local occurrence times through an IANA timezone
and DST fold, applies bounded misfire grace plus `skip` or `fire_once`,
coalesces eligible occurrences to the latest, and atomically retains the
evaluation receipt with at most one selected `source=scheduled` wake. Fully
skipped evaluations remain durable. Exact evaluation replay is idempotent,
contradictory reuse conflicts, direct queue publication of scheduled provenance
fails closed, restart preserves receipts and wakes, and the existing supervisor
consumes selected work. Evidence:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6F_PROOF_2026-09-07.md`.

Slice 6G checkpoint status: implemented on 2026-09-07. The existing API-key
boundary is combined with issuer/key-bound HMAC-SHA256 verification over route
identity, canonical UTC timestamp, and raw-body digest. A bounded replay window
rejects stale and excessively future deliveries before JSON interpretation.
The durable delivery receipt and selected `source=webhook` wake publish
atomically; exact retries are idempotent, contradictory reuse conflicts, direct
queue publication fails closed, restart preserves truth, secrets/signatures are
not projected, and the existing supervisor consumes the wake through the real
external child path. Evidence:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6G_PROOF_2026-09-07.md`.

Slice 6H checkpoint status: implemented on 2026-09-07. A claimed wake now
prepares every accepted issue-scoped read/write proposal through the canonical
effect service while rechecking its fence before publication and after
external observation. The authenticated operator route resolves the existing
approval, performs no denied mutation, requires safe journals for every
proposal, accepts one aggregate checkpoint, records one exact request-bound
resume authorization, and enqueues an existing-run wake. The run remains
operator-blocked until that wake is claimed and validates the authorization;
unobserved writes move to recovery pending. Exact resolution retries and
process restart preserve one resume wake. Evidence:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_6H_PROOF_2026-09-07.md`.

### Slice 7 -- Release proof and lane closeout

Required proof:

1. `unit`: deterministic policies, serialization, context, and budget rules;
2. `contract`: schemas, manifests, negotiation, capabilities, and fail-closed
   validation;
3. `integration`: repositories, subprocesses, model profiles, approvals,
   effects, claims, recovery, and teardown;
4. `end-to-end`: deterministic fixture, Ollama single-model, Ollama fixed
   multi-model, denied effect, admitted effect, cancellation, and restart;
5. clean SDK build/install and external package build/install/validation;
6. architecture, documentation, dependency, lint, and canonical test gates;
7. operator inspection and non-mutating replay artifact.

Packaging checkpoint, 2026-09-07: item 5 is complete against a cache-free copy
of the current Git-visible worktree. Core `0.5.10`, SDK `0.5.0a1`, and external
starter `0.1.0` wheels and source distributions built; all three final wheels
installed into one fresh environment; `pip check`, installed CLI help, SDK
strict validation, and host strict validation passed. The core artifacts contain
zero SDK-namespace entries, and the external source distribution preserves its
manifest and test. Evidence:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_7_PACKAGING_CHECKPOINT_2026-09-07.md`.

Installed-runtime checkpoint, 2026-09-08: the first installed live runs exposed
a checkout-relative, unpackaged local prompt registry. The canonical registry
now ships inside core and resolves relative to its module without a fallback
copy. A rebuilt core wheel with the retained SDK wheel and extracted external
starter sdist passes five real Ollama flows: single-model CLI, multi-model CLI,
API supervision, approved write/restart/resume, and denied write. The effect
tests verify expected file contents, no preapproval or denied write, idempotent
resume publication, checkpoint acceptance, app-lifespan restart, exact role
identities, non-mutating replay, and zero tracked background tasks. Evidence:
`docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_7_INSTALLED_RUNTIME_CHECKPOINT_2026-09-08.md`.
This does not prove abrupt process-kill recovery or replace the distinct
external `GovernedLocalAgent` package's release gates with starter proof.
This checkpoint's shared request supplied both batches initially and therefore
did not establish incremental context delivery. The 2026-09-09 reconciliation
replaces that fixture path with host-owned continuation inputs: batch A first,
batch B plus the compact prior report next. Three fixed cases share the same
verifier and budgets across single/multi-model proof. The actual external
`GovernedLocalAgent` distribution, including its release verifier, is built and
installed separately. The new process-fault harness exits the API immediately
before or after a real write and restarts a fresh process against the same DB.
Only observed matching bytes can reconcile, with repeat writes prohibited.

Routine live proof must set `ORKET_DISABLE_SANDBOX=1`. Intentional sandbox work
must prove teardown in the same execution path.

Closeout requires:

1. actual observed paths and results recorded under contributor vocabulary;
2. all runtime, SDK, extension, docs, and authority surfaces aligned;
3. version and release actions completed under their separate policies;
4. user acceptance of the live proof;
5. plan and history archived according to contributor workflow.

## Dependency order

1. Slice 0 closes contract and refusal gaps before enabling agent execution.
   Its additive bindings and fail-closed admission fixes are not runtime support.
2. Slice 1's minimum development SDK precedes the external fixture in Slice 2;
   final SDK publication does not block development of its host integration.
3. Slice 2 precedes live local inference and continuous scheduling.
4. Slice 3 precedes multi-model behavior.
5. Slice 4 precedes unattended wake processing.
6. Slice 5 proves the requested multi-model value before general scheduling.
7. Slice 6 is the continuous-agent operational surface, not the starting point.

Work may overlap only when the shared contracts are already accepted and each
slice can be verified independently without temporary duplicate authority.

## Concrete acceptance workload and evidence

Use one bounded report objective throughout the lane: produce a JSON report of
ticket counts by status from two host-supplied fixture batches. The host owns
the source data and deterministic expected totals. Iteration 1 sees batch A;
iteration 2 receives batch B plus the prior recorded result. The verifier checks
counts, source references, completeness, and report contents; JSON shape alone
cannot establish success. Host publication persists the verified report.

Slice 4 adds one approved `write_file` materialization of that report inside a
disposable issue workspace through the admitted turn-tool path. Denial leaves
the target absent; a restart after an uncertain write requires observation before
retry. This proves a useful bounded task, not general-purpose coding autonomy.

Single-model and multi-model runs use the same inputs, verifier, and total
budget. Record at least three fixed fixture cases, actual model digests,
provider versions, model calls, repair calls, measured or unknown token usage,
wall time including loading, completion results, and peak admitted concurrency.
At least one case must require continuation; negative cases cover incorrect
totals and a false completion recommendation. Multi-model execution is a
capability demonstration; claim a quality benefit only if the comparison supports it.

Record SDK/core versions and commits, extension digest, resolved non-secret
configuration, verification commands, durable run refs, expected/observed
outcomes, and limitations for every slice. Rerunnable JSON reports use
`scripts.common.rerun_diff_ledger` and one stable path per script. Choose that
path before creating its producer; no timestamp-only proof files. Admission
tests must also cover stale workers, cancelled provider calls, unknown usage,
changed approval arguments, and broker disconnects.

## Review findings and disposition

The 2026-09-06 activation review found S0-A through S0-D gaps. Those findings
are historical and are superseded for current execution status by the Slice 0
matrix and Slices 1-2 proof report. Strict discrimination, complete bindings,
the retained parent-run adapter, clean package ownership, broker ownership,
cancellation, and stale-result fencing are now implemented.

Ship-risk debt now starts after Slice 6H: durable authenticated API and public
manual wakes,
production dispatcher composition, broker/result wake-fence propagation,
provider-capacity claims, composed inspection, and continuous API lifecycle
ownership plus evidence-gated wake controls and live Ollama supervisor proof
exist, including schedule and HMAC webhook ingress plus wake-fenced effect
preparation, authenticated resolution, aggregate checkpointing, and
request-bound resume wakes. Slice 7 packaging and clean-install compatibility
are now proven; final evidence reconciliation, release actions, and acceptance
remain open.

Self-deception debt remains explicit: live Ollama execution proves provider and
receipt behavior, not comparative model quality. The trusted Python extension
subprocess is not hostile-code containment, and deterministic continuous API
proof is not live local-model proof. The generic extension executor still
refuses agent workloads; only the dedicated catalog-resolved agent path is
admitted.

Exploration-safe debt: the SDK is a development prerelease and the reference
extension is a separate local package, not a hosted or published release.
Policy-approved substitution is not exposed by the exact-model CLI path. Final
release actions, evidence reconciliation, user acceptance, and full lane
closeout remain Slice 7 work.

Current verification and exact proof classifications are recorded in
`SLICE_7_ACCEPTANCE_PROOF_2026-09-09.md` for the current candidate, and historically in
`SLICE_1_2_PROOF_2026-09-07.md` and
`SLICE_3_5_PROOF_2026-09-07.md`, with continuous-operation checkpoints in
`SLICE_6A_PROOF_2026-09-07.md`, `SLICE_6B_PROOF_2026-09-07.md`,
`SLICE_6C_PROOF_2026-09-07.md`, `SLICE_6D_PROOF_2026-09-07.md`,
`SLICE_6F_PROOF_2026-09-07.md`, `SLICE_6G_PROOF_2026-09-07.md`, and
`SLICE_6H_PROOF_2026-09-07.md`.

## Non-goals

1. Open-ended autonomous execution.
2. Dynamic swarms or unrestricted child agents.
3. Agent-controlled credentials, endpoints, capabilities, budgets, or final
   truth.
4. A second workflow engine inside the extension.
5. Replacing controller workload v1.
6. Provider download or GPU-process management in the first implementation.

## Completion criteria

This plan completes only when:

1. the SDK, external extension, and Orket core slices meet their component
   acceptance gates;
2. one continuous supervisor can safely wake bounded agent work across restart;
3. the live fixed-role extension uses at least two local model identities;
4. effects, approvals, cancellation, recovery, and final truth remain host-owned;
5. the complete proof envelope is green and truthfully classified;
6. the operator experience is accepted by the user.
