# Architectural Truth Remediation Plan

Date: 2026-07-29
Last updated: 2026-09-11
Status: Active implementation plan; September scope planned, not implemented
Roadmap state: Priority Now
Owner: Orket Core

## Objective and authority

Make Orket capable of completing a broader range of useful work with bounded
autonomy, reliable recovery, independently verified outcomes, and measurable
performance. More tools, turns, models, or concurrency count as improvements only
when authorization, actual effects, and retained evidence remain aligned.

This revision addresses every finding in the
[behavioral review](BEHAVIORAL_TRUTH_ARCHITECTURE_REVIEW_2026-09-10.md) and its
[evidence companion](BEHAVIORAL_TRUTH_REVIEW_EVIDENCE_2026-09-10.md), while retaining
the unfinished July work. It replaces the previous instruction to implement
Slice C next. This remains the lane's single canonical execution plan.

The user activated the original lane on 2026-07-29 and requested this expanded
plan on 2026-09-11. This revision is planning work only. Proposed schemas,
migrations, exit mappings, and capability admissions are future requirements,
not current guarantees or newly accepted durable contracts. Before implementing
a changed contract, settle its semantics in the existing spec and record a delta
using `docs/architecture/CONTRACT_DELTA_TEMPLATE.md`. Extract accepted new durable
contracts into `docs/specs/` before implementation. New capability requirements
remain proposed until accepted for implementation.

Workflow authority remains `docs/CONTRIBUTOR.md`; execution priority remains
`docs/ROADMAP.md`; current runtime authority remains `CURRENT_AUTHORITY.md`.
Preserve provider promotion first in Priority Now and this lane's current position.
Within this lane, behavioral repairs precede structural cleanup. No contributor
workflow or current runtime contract changes in this planning revision.

## Findings and complete disposition

All 18 September findings remain open planning obligations. A mapped slice is
not a fix; closure requires its acceptance evidence and updated authority.
Historical counts and failures below are September 10 observations, not reruns.

### Ship-risk debt

| Finding | Correction | Owning slice and decisive proof |
|---|---|---|
| SR-01: old approval executes another write | Bind authorization to one immutable effect | BT-1: two same-tool writes; retry approval 1 before/after restart while approval 2 is pending; file 2 stays absent |
| SR-02: duplicate execution, one ledger event | Durable pre-dispatch claim, fencing, journal, uncertain recovery | BT-1: concurrent authenticated retries across processes and dispatch crash points; independently observe at most one effect or a blocked unresolved boundary |
| SR-03: approval and denial both succeed | Conditional decision and atomic publication | BT-1: approve/deny, approve/expire and two-operator races; one winner and consistent projection after restart |
| SR-04: expiry depends on queue reads | Enforce deadline inside the decision transaction | BT-1: direct approval before, at and after expiry without prior list/get; expired authorization causes no effect |
| SR-05: verification reseals corruption | Read-only checks against retained commitments | BT-2: mutate/delete/reorder stored events; reject without evidence changes; compare a previously retained external anchor |
| SR-06: truncated ledger called complete | Snapshot traversal, independent count/head | BT-2: 4,999/5,000/5,001 events and concurrent append; include the snapshot tail or disclose incomplete output |
| SR-07: absent checks become done intent | Acceptance-specific evidence sufficiency through persistence | BT-3: composed card runs with absent, syntax-only, incorrect and sufficient behavioral evidence |
| SR-08: cancelled child keeps writing | Own the entire admitted command lifetime | BT-4: cancel public verification mid-command; no later writes or surviving descendants after confirmed shutdown |
| SR-09: durable failure exits zero | Typed terminal result at the process boundary | BT-4: installed successful, blocked, incomplete and failed epics; compare durable outcome, output and exit |

### Exploration-safe debt

| Finding | Correction or capability progression | Owning slice and decisive proof |
|---|---|---|
| ES-01: execution families have different guarantees | Explicit claim ceilings, then reuse proven authority primitives | BT-5: family-by-family conformance and migration proof; a shared facade is not convergence |
| ES-02: verifier is ticket-fixture-specific | Workload-owned, versioned, digest-bound acceptance/verifiers | CAP-1 after BT-3/BT-5: multiple non-ticket workloads, wrong-output controls, unsupported-objective refusal and live llama.cpp proof |
| ES-03: trusted code is not hostile-code containment | Preserve trusted admission; expand only behind a proven OS boundary | CAP-2: containment/resource/teardown tests and unavailable-boundary refusal; unsupported hosts remain unadmitted |

### Self-deception debt

| Finding | Correction | Owning slice and decisive proof |
|---|---|---|
| SD-01: gate enforces a weaker graph | Allowed-edge model, exact exceptions, pure core/explicit inputs | C/D: forbidden edges/effects fail; code and architecture share policy authority |
| SD-02: empty replay says matched | Insufficient evidence, scope/count and completeness checks | BT-3: empty/missing/corrupt/populated snapshots; read-only continuation comparison |
| SD-03: success stories miss races; taxonomy conflicts | Adversarial regressions throughout; canonical pytest classification | BT-0 through BT-5 and E1: independently observed boundary proof and marker-aware strict taxonomy |
| SD-04: lint red; no-op/size inventories noisy | Repair checker semantics, clear real debt, decompose by authority | E1/E2: no known type-only false positives; canonical quality envelope passes; shrinking size baseline |
| SD-05: connector timing is fabricated | Measured monotonic elapsed time/provenance, or unavailable | BT-4: slow command, timeout, cancellation and failure against independent elapsed observation |
| SD-06: current authority is a journal | Bounded manifest-backed snapshot with proof ceilings | E2: generated-output/command parity, scope consistency and history moved out |

## Preserved checkpoints and present evidence

| Earlier work | Preserved evidence | Remaining obligation |
|---|---|---|
| Workstream 0 baseline | Existing collector and stable `docs/projects/architectural-truth/architectural_truth_baseline.json` | Refresh against implementation candidate; collection success differs from release readiness |
| Workstream 1 / Slice A | `COMMAND_ROOT_PROOF_2026-07-30.md`, `SLICE_A_PROOF_2026-07-29.md`: help, onboarding, fatal exits, quickstart EOF, packaged demo | SR-09 concerns nonexceptional outcomes beyond that proof |
| Workstream 2 / Slice B1 | `API_INSTANCE_B1_PROOF_2026-07-30.md`: distinct apps, roots, engines, contexts and bounded teardown | Preserve isolation through migration |
| Workstream 2 / Slice B2 | `API_COMPOSITION_B2_PROOF_2026-09-07.md`: import-pure API, application composition; AT-EX-002 removed | Broader facade debt remains AT-EX-003 |

The review ran nine adverse local probes and reported 4,576 passed, 73 skipped in
the mixed suite. Its baseline truthfully returned `collection_ok=true`,
`release_ready=false`. SR-09 was structural; SR-07 stopped at generated status
intent. Those evidence limits must survive planning.

During this planning revision all 16 source fingerprints in the companion matched
current file bytes. That is structural continuity, not another probe execution or
a freeze of transitive dependencies. Substantial provider work exists in the dirty
tree. Implementation proof must identify the candidate, dirty posture, installed
versions and provider configuration, preserving unrelated edits.

Keep `main.py` and hidden `--rock` compatibility through 0.6.x. Removal requires
the explicit 0.7.0 delta and installed-root proof in `docs/CONTRIBUTOR.md` and
`docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_RELEASE_2026-09-10.md`.

## Execution sequence and dependencies

Orket Core owns each slice; assign one responsible maintainer at slice opening.
Each handoff names the next unclosed gate. Order is within this lane, not a
cross-project roadmap reorder.

| Order | Slice | Dependency and release condition |
|---|---|---|
| 1 | BT-0: counterexamples and contract decisions | Prepare BT-1 without repository-wide cleanup prerequisites |
| 2 | BT-1: exact authorization and durable effects | BT-0; SR-01 through SR-04 are one outward-effect release gate |
| 3 | BT-2: integrity and complete export | Agree atomic publication with BT-1; outward expansion waits for both |
| 4 | BT-3: evidence-based completion and scoped replay | BT-0; can proceed independently of outward storage |
| 5 | BT-4: cancellation, outcomes, telemetry | BT-0; cancellation can be repaired immediately; completion integrates BT-3 |
| 6 | BT-5: converge authority | BT-1 through BT-4, with real migration proof |
| 7 | C/D: dependency cutover, purity, async safety | Preserve behavioral gates while removing architectural debt |
| 8 | E1/E2: quality gates, authority, decomposition | Tests start at BT-0; final cleanup follows C/D |
| 9 | CAP-1: broader verified workloads | BT-1 through BT-5; applicable C/D/E gates green; requirements accepted |
| 10 | CAP-2: admitted untrusted execution | BT-4, CAP-1 acceptance interface, accepted threat model/platform |
| 11 | CAP-3: capacity and operator acceptance | Final admitted workload/provider/isolation configuration |

CAP-1 need not wait for unrelated cosmetic extraction, but cannot bypass applicable
authorization, evidence, lifetime or quality gates. No new outward effect capability
is admitted until BT-1 and BT-2 are live-proven. Local fixture proof does not depend
on provider promotion; final provider claims consume the actual result of the
existing llama.cpp lane. Unavailable llama.cpp never triggers a provider switch.

## BT-0 — Establish executable boundaries

1. Convert September counterexamples into classified regressions using real
   temporary SQLite, files and subprocesses. Assert the healthy opposite, not
   collector exit zero. Demonstrate pre-fix failures; retain non-reproductions and
   their schedule/environment rather than claiming a fix.
2. Add composed card/installed CLI cases for SR-07/SR-09 and authenticated HTTP
   approval paths. Use bounded synchronization and separate connections/processes
   for races; a lucky sleep or serialized fake is inadequate.
3. Reuse the baseline and exception register. September findings remain defects,
   not newly accepted exceptions that make a gate green.
4. Settle transaction ownership, effect identity, expiry, dispatch/recovery states,
   ledger migration/order, evidence requirements and result mappings in affected
   specs before changing those contracts.
5. Preserve the admitted single-turn proof-kernel ceiling. Repairing executable
   multi-turn behavior does not extend formal scope.

Candidate surfaces are the source-fingerprinted modules in the companion,
`orket/interfaces/routers/approvals.py`, and existing application/interface tests.
Model responses may be fixtures for authority regressions; retain separate live
provider acceptance. Exit: executable cases or explicit missing-proof obligations
cover all findings, and BT-1 contract decisions are concrete enough to implement.

## BT-1 — Exact authorization and durable effect lifecycle

Addresses SR-01 through SR-04 and their SD-03 blind spots. Primary surfaces:
`outward_approval_service.py`, `outward_run_execution_service.py`,
`outward_run_execution_plan.py`, outward domain records/stores, connector dispatch
and approvals router. Review `governed_agent_effect_service.py` and existing
supervisor approval/effect contracts before adding abstractions. Reuse stronger
CAS, fencing, journal and reconciliation semantics where they fit.

Required changes:

1. Persist an immutable binding of run, attempt or execution generation, turn/step,
   proposal ID, connector/version, canonical argument digest, target/namespace,
   resolved policy digest/version and expiry. Store the complete bound call in
   protected authoritative storage; previews and the latest model call cannot
   authorize dispatch. Changed arguments, target, generation or policy require
   admission again. Revalidate scope at dispatch without broadening approval.
2. Conditionally transition pending status and check expiry inside one transaction.
   Proposed boundary: `now >= expires_at` is expired. Sample the application clock
   at the serialized decision boundary, not before an unbounded lock wait.
   Separately decide whether approved work has a dispatch deadline; enforce its
   accepted semantics after delays/restart. Queue reads are unnecessary for safety.
3. Atomically publish decision, active authorization/run projection and event when
   co-located. If an existing store boundary requires an outbox, persist it in that
   transaction and project idempotently. Identical retries return the original
   decision; contradictory reuse returns that decision or explicit conflict, never
   a second successful acknowledgement. Preserve operator/idempotency-key scope.
4. Durably claim the exact approved effect before dispatch. Keep an authoritative
   effect pointer after pending-queue removal. Old proposal retries return their
   own receipt and cannot advance the current turn. Use a fenced execution owner;
   lease expiry does not prove an old worker stopped causing effects.
5. Journal claim, dispatch intent, confirmed observation and terminal publication
   through existing effect authority. Dispatch intent without a conclusive receipt
   means unresolved execution. Reconcile before retry. Pass stable idempotency keys
   only where connectors enforce them; uncertain arbitrary commands stay blocked
   or observation-only. SQLite cannot promise generic exactly-once external effects.
6. Route every API/retry/resume worker through that authority. Persistence failure
   prevents new dispatch. If an effect occurred but publication failed, preserve
   its uncertainty; never re-execute to repair a missing event.

Acceptance:

- Run two same-tool writes through proposal generation, retry approval 1 while
  approval 2 is pending, restart and repeat. Verify file contents, binding,
  proposal/receipt identity and no second effect/turn advancement. Include changed
  arguments, policy, scope and generation.
- Race approve/approve, approve/deny, approve/expire and conflicting idempotency
  reuse through separate connections/processes and authenticated HTTP. Require
  one authoritative decision and claim; unauthorized callers cannot dispatch.
  Exercise expiry directly and beyond the pending-scan cap.
- Crash before claim, after claim, before dispatch, after dispatch/before receipt,
  and after receipt/before terminal publication; reopen in a new process. Observe
  actual append/file effects independently. At most one effect may occur;
  uncertainty blocks until reconciled. Duplicate-event `IntegrityError` fails the
  gate even when another request succeeds.

Migration: inventory/back up old rows. Records missing the binding require a new
proposal or explicit quarantine; do not reconstruct permission from the current
model call. Preserve historical receipts and uncertainty. Prohibit mixed old/new
dispatch writers. Rehearse upgrade/restart on copied stores. Rollback stops
dispatch while retaining claims/journals; it cannot revive reusable approvals.

## BT-2 — Independent integrity and complete ledger export

Addresses SR-05/SR-06. Surfaces: `outward_ledger_service.py`,
`outward_run_event_store.py`, `orket/core/domain/outward_ledger.py`, ledger routes,
offline verification and `docs/specs/LEDGER_EXPORT_V1.md`.

1. Make verification read-only; remove implicit hash repair from verification and
   ordinary export. Separate legacy first-time sealing/migration. Sealing today
   cannot claim retroactive authenticity.
2. Commit event bytes, ordering identity, chain link and retained run head atomically
   on append. Define stable append order. V1 sorts by `(run_id, turn, at, event_id)`;
   later insertions can sort earlier. Changing order/hash inputs needs versioning
   and explicit old-export compatibility, not silent v1 reinterpretation.
3. Traverse all pages from one snapshot with independent count and retained head/
   high-water mark queried in that snapshot. Do not derive completeness from
   returned rows. Resource bounds reject or disclose partial output. Pagination
   uses stable order.
4. Preserve redaction/partial-view omission anchors and PII audit behavior. Commit
   a required export audit event before opening the snapshot. Read-only verification
   cannot accidentally reuse that mutating export path.
5. Separate export self-consistency, retained integrity, snapshot completeness and
   authenticity. Compare a prior external anchor. An attacker rewriting events and
   local heads defeats a local-only chain; protected external retention or signing
   is a separate trust boundary.

Acceptance: change payload/hash/order; delete middle/tail events; verify twice
without changing logical database contents. Test 4,999/5,000/5,001 events, multiple
pages, empty runs, concurrent append, filtered export and PII audit insertion.
Compare count/head with independent queries and a prior external anchor. State
which corruptions local commitments versus external anchors detect. A valid
prefix alone cannot prove completeness.

Migration: retain original v1 exports and corrupt rows. Never overwrite mismatches.
Explicit backfill of eligible unsealed records needs provenance and bounded claims.
Rehearse interrupted migration/restart; rollback preserves evidence and prevents
incompatible writers.

## BT-3 — Evidence-based completion and scoped replay

Addresses SR-07/SD-02 and prepares ES-02. Surfaces: `runtime_verifier.py`, prompt
preparation, turn model flow, `turn_executor_runtime.py`, final card-state gates
and `governed_agent_inspection_service.py`.

1. Carry typed acceptance requirements/evidence through all consumers. Distinguish
   absent evaluation, syntax checks, command execution, behavioral verification
   and objective satisfaction. Replace completion's `runtime_verifier_ok` dependency
   with sufficiency plus acceptance/verifier/policy references.
2. Bind evidence to exact artifacts, workload, inputs and run/attempt. Missing,
   stale, substituted or unverifiable evidence cannot authorize done. Exit zero
   proves only what the accepted verifier tests; model self-report stays advisory
   except under a separately admitted attestation policy.
3. Apply the same gate to synthesized and explicit model status calls, application
   completion and final persistence. Keep termination distinct from success. Tell
   operators which evidence/work remains missing.
4. Empty continuation replay reports insufficient/not-evaluated evidence. Include
   scope, expected/compared counts and diagnostics; reject missing middle/tail
   snapshots, absent inputs and digest mismatch. A matching surviving subset is
   not complete comparison. Replay stays read-only and cannot rerun models/tools
   or claim external-effect/full-execution verification.

Acceptance: composed card runs reach final persistence with no plan, empty
workspace, syntax-only proof, syntactically valid wrong behavior, failed checks,
stale/cross-run artifacts and correct behavior. Test explicit and synthesized
done. Only evidence satisfying declared acceptance produces successful done.
Inspect zero/one/multiple/missing/corrupt replay snapshots through the real
inspector and public surface, proving no durable changes.

Update existing truthful-runtime/governed-agent contracts and taxonomy as needed.
Keep the ticket-report verifier scoped; unsupported objectives cannot inherit it
as a universal default.

## BT-4 — Owned cancellation, terminal results and measured telemetry

Addresses SR-08/SR-09/SD-05 and part of AT-EX-005.

1. Give verification an application-owned process supervisor. On cancellation,
   timeout or failure stop admission, terminate owned children/descendants,
   escalate within bounded deadlines and await confirmed exit. Protect cleanup
   against repeated cancellation; propagate cancellation after cleanup. Preserve
   uncertainty when termination cannot be confirmed.
2. Define actual Windows/Linux descendant ownership using supported OS supervision;
   reuse suitable existing helpers. Killing only the direct child is insufficient.
   Thread-offloaded blocking work also needs truthful lifetime semantics.
3. Return a typed application result from epic finalization through orchestration,
   card dispatch and CLI: run ID, lifecycle, result class, evidence sufficiency and
   durable references. Transcripts become projections. Define nonzero exits for
   failed, blocked, incomplete, cancelled and unresolved runs; success alone exits
   zero. Preserve usage/EOF and wrapper compatibility through explicit deltas.
4. Measure connector duration with an injected monotonic source, scope and provenance.
   Timing stays outside deterministic decisions unless explicitly captured as input.
   Missing measurement is unavailable, not zero. Audit timeout/cancellation/error
   and summary paths for fabricated defaults.

Acceptance: cancel public verification after child/grandchild startup, including
repeated cancellation and app shutdown. After confirmed teardown, independently
observe no surviving processes or later writes. Retain diagnostics if the OS
refuses termination. Run installed successful/incomplete/blocked/failed/cancelled
epics outside the checkout; compare exit, narration, durable state and evidence.
Use fixture models for repeatable boundaries plus separate live llama.cpp success
and unsuccessful flow; mocked finalizer results are insufficient. Compare a slow
command and timeout with independent timing using a declared tolerance.

## BT-5 — Converge authority without replacing every executor

Addresses ES-01. Reuse existing control-plane admission, effect journal,
checkpoint/recovery, workload catalog and terminal-truth seams.

1. Extend the governed start-path matrix for cards, outward runs, governed agents,
   SDK/legacy workloads, quickstart, review and ODR. Name executor, authorization
   owner, effect owner, terminal authority, replay scope, public surface, supported
   objectives and unsupported cases for each.
2. Reconcile contradictions against code/proof before claiming coverage. The inspected
   start-path matrix still calls schedule/webhook ingress unadmitted while
   `GOVERNED_AGENT_LOOP_V1.md` describes implemented slices. Neither paragraph alone
   establishes current admission.
3. Reuse minimum common contracts for immutable authorization, CAS, fencing, observed
   effects, evidence sufficiency and result projection. Applications authorize;
   adapters perform effects. Preserve one workload-ID authority.
4. Migrate outward/cards consumers first without weakening governed-agent behavior.
   Other families may keep distinct executors when semantics differ, with explicit
   ceilings. A shared class hierarchy is not required.
5. Parameterize conformance by each family's admitted guarantees. Read-only comparisons
   can help migration; never dual-dispatch effects. Remove superseded authority at
   cutover; compatibility follows existing approval/removal-ticket rules.

Exit: each family has one named authority chain. Families claiming shared guarantees
pass the same adversarial cases through real composed paths. Renames or another
orchestration framework do not count as convergence.

## C/D — Dependency cutover, core purity and async safety

Retains Workstreams 3, 4 and 5 and previous Slice C/D obligations.

### C: One enforceable dependency model

1. Ratify how runtime/orchestration/kernel/services/platform and other packages map
   to the five normative layers. Use one machine-readable allowed-edge policy;
   reject unknown classifications, unexpected edges, authority cycles and dynamic
   import bypasses.
2. Retain only exact exceptions with source/target, owner, reason, introduction date,
   removal trigger and optional expiry. Report consumption separately; broad layer
   exemptions cannot hide new edges.
3. Generate policy reports/documentation from that authority and update architecture
   in the same cutover. Separate observed graph from verdict. Deliberately test
   forbidden adapters-to-application, interfaces-to-adapters,
   core-to-services/platform and runtime-to-interfaces edges.

Exit: enforce documented architecture plus individually governed exceptions.
Until cutover, green means only current transition-policy pass.

### D: Pure core, explicit inputs and owned effects

1. Split FailureReporter into pure value construction and application artifact/event
   publication. Move reconciliation traversal/writes/logging out of core. Move
   AST/iDesign dependencies out of core or invert behind contracts.
2. Inject clocks, identity, randomness, environment/provider settings and decision
   context as immutable inputs. Decision nodes cannot inspect filesystem, runtime
   state, databases, environment or hidden caches for missing context. Declare and
   enforce adapter side-effect classification.
3. Inventory async reachability; replace blocking subprocess/file/HTTP/sleep paths
   with async operations or an owned worker. Include extension install/integrity
   and runtime-policy reads; retain explicit standalone CLI/CI exemptions only.
4. Prove deterministic core parity for identical inputs and real application effect
   parity. Prove responsiveness under concurrent requests, cancellation, timeout
   and shutdown against a latency bound set before measurement.

Exit: clean core imports/effects and explicit decision inputs, no unexplained async
blocking, confirmed teardown. Preserve BT regressions and A/B guarantees.

## E1/E2 — Reliable quality gates and maintainable authority

Retains Workstreams 6, 7 and 8 and previous Slice E obligations.

### E1: Repair checkers and clear real debt

1. Make pytest markers `unit`, `contract`, `integration`, `end_to_end` canonical,
   including inherited/parameterized classification. Layer and live-provider/fixture
   posture are separate. Replace the prose regex: 3,479 missing labels were checker
   output, not proof those tests lack markers. Correct AT-EX-013 accordingly.
2. Migrate bounded test directories, then enforce zero missing/invalid layers.
   End-to-end requires a public surface; disclose fixtures and absent provider
   proof. Boundary regressions run from BT-0, not only after cleanup.
3. Repair no-op analysis for TYPE_CHECKING, Protocol/abstract declarations and actual
   executable empty bodies. Add positive/negative checker cases, then fix real
   findings. No broad ignores to obtain green.
4. Clear Ruff over canonical `orket tests`, separately reporting narrower/root-wide
   scopes. Preserve Quality workflow coverage thresholds. Pytest alone is not the
   full quality envelope.
5. Recompute size inventory with nested-router context. Maintain a no-growth,
   shrinking baseline; September's 76 oversized files and 241 functions indicate
   change risk, not 317 proven runtime defects.
6. Implement/validate automation in `.gitea/workflows/` first. Keep applicable
   Linux/Python matrix and separate Windows lifetime/installed proof. Never weaken
   policy so baseline collection appears release-ready.

Exit: marker taxonomy, corrected no-op checks, Ruff, canonical pytest and applicable
Quality jobs pass on the same candidate, including actual coverage gates.

### E2: Bounded authority and focused decomposition

1. Define a small current-authority manifest for install/commands, executor and
   authorization/effect/terminal owners, durable paths, active contracts,
   compatibility expiry, claim ceilings and proof references/status. Reference the
   architecture policy/start-path matrix instead of duplicating definitions.
2. Preserve current authority until a same-change cutover to manifest and generated
   CURRENT_AUTHORITY view. Validate unique keys, paths, spec status, command parity,
   proof freshness, contradictions, expiry and generated equality. Move history
   into release/closeout records with links; do not discard evidence or create an
   equally unbounded machine-readable journal.
3. Extract by authority/lifetime in order: API facade, bundle CLI, orchestrator_ops,
   turn_tool_dispatcher, turn_message_builder and oversized truth/evidence collectors.
   Preserve genuine public contracts; no new __getattr__ proxies or copied owners.
4. Apply existing 400-line file, 70-line function and 10-public-method limits to new
   structures, with explicit correctness exceptions. Each extraction reduces
   measured coupling/ownership debt and proves behavior parity.

Exit: bounded validated authority, no historical journal in its active view, current
commands with live or explicitly unavailable proof, and decreasing hotspot debt
without semantic/dependency drift.

## CAP-1 — Broader useful work with independent completion verification

This is the main capability progression for ES-02. It is proposed scope, not a
claim that arbitrary objectives are supported.

1. Add workload-owned acceptance/verifier selection bound to immutable workload,
   artifacts, inputs, policy, verifier version and configuration digests. Unsupported
   objectives fail admission with the missing contract/verifier identified. Reuse
   workload catalog and host verification authority.
2. Admit concrete families individually: repository changes verified by behavior
   tests; structured transformations checked against schemas/source records;
   artifacts/reports checked for content, provenance and completeness. Retain
   ticket-report regression coverage. Criteria must be independent of the producing
   model's completion recommendation.
3. Exercise staged inputs, bounded memory, pause/resume, tools, approval, budgets
   and recovery through existing governed-agent primitives. Each family needs
   no-progress/policy stop, cancellation and uncertain-effect handling. Add no
   competing memory or continuation authority.
4. Admit bounded parallel work only for proven independent scopes/effects. Reuse
   reservations/budgets, propagate cancellation and verify joined results.
   Conflicting writes require serialization or explicit conflict resolution.
5. Record actual model/provider identity on the final llama.cpp target. Other
   providers require explicit selection and separate conformance evidence.

Acceptance: at least two distinct non-ticket families pass installed/API flows,
including correct output, plausible wrong output, absent/stale evidence, restart
and policy/budget stop. Independent verification rejects wrong output even when
the model reports success. Before admitting parallelism, prove one independent
workload and one intentionally conflicting case. Publish a supported-objective
matrix and actionable refusal reasons; do not claim a universal objective verifier.

## CAP-2 — Separately admitted OS containment for untrusted extensions

Immediate ES-03 disposition: preserve accurate trusted-code admission. Untrusted
execution requires an accepted containment contract; it is not a prerequisite
for useful trusted workloads and cannot be waived by relabeling them.

1. Define adversary, supported hosts, package trust, mounts, secrets, network,
   descendants, quotas, artifact egress and supply-chain responsibilities.
2. Select one enforceable OS backend on a named platform, reusing an existing
   suitable boundary when proven. Missing boundary or denied capabilities refuses
   admission. Subprocesses, Python guards, socket patches and path checks alone
   remain insufficient.
3. Run bounded adversarial tests for host/credential access, egress, cross-workspace
   access, undeclared capabilities, exhaustion, descendants and cancellation under
   the actual boundary. Independently inspect host effects/resource use.
4. Prove teardown in the same acceptance path. Intentional `orket-sandbox-*` creation
   requires explicit sandbox acceptance and removal before workspace cleanup.
   Unsupported OS/backend configurations remain unadmitted.

Exit: claims remain bounded by the proven threat model/platform. If the boundary
cannot be provided, retain trusted-only admission and its exact blocker; hostile
containment is not complete. Formal proof extensions and paused cloud lanes keep
their explicit reopen rules.

## CAP-3 — Measured capacity and operator acceptance

Required confidence work after correctness gates:

1. Baseline a fixed corpus on identified hardware/model/profile/policy/package
   versions. Measure verified completion rate, incorrect success, unauthorized or
   duplicate effects, unresolved boundaries, restart completion, p50/p95 latency,
   throughput, tokens/cost, memory and leaks. Use BT-4 timing; missing stays missing.
2. Set workload-specific latency, budget and capacity thresholds before campaigns.
   Require zero observed unauthorized/duplicate effects and false success in the
   accepted corpus; state finite sample size/coverage. Do not invent a universal
   performance target in this plan.
3. Exercise slow/unavailable providers, concurrent approvals, long ledgers,
   cancellation storms, restart and competing scopes under bounded concurrency.
   Include operator recovery of deliberate uncertainty. Establish a supported
   operating limit with saturation testing.
4. Optimize measured bottlenecks. Caches preserve input/policy identity; concurrency
   preserves fencing/budgets. Compare quality, recovery, resources and latency after
   changes and rerun the invariant suite.

Optional after required gates: extra tuning, workload/connector families,
visualization and platform coverage, each with bounded acceptance. Agent-proposed
shareable benchmarks stay in `benchmarks/staging/` until approved; follow contributor
index synchronization. Existing local proof result paths retain their authority.

## Contract, migration and exception closure map

| Change | Authority updated in its implementation slice |
|---|---|
| BT-1 approval, claims, recovery | API/frontend and connector surfaces; existing supervisor approval/checkpoint/effect contracts; domain/storage schemas; event taxonomy; CURRENT_AUTHORITY and RUNBOOK |
| BT-2 ledger order/integrity/completeness | LEDGER_EXPORT_V1, API/frontend, applicable outward witness/claim-tier compatibility, taxonomy and CURRENT_AUTHORITY |
| BT-3 evidence/replay; CAP-1 verifiers | Existing truthful-runtime specs, GOVERNED_AGENT_LOOP_V1, workload and status/API contracts, CURRENT_AUTHORITY |
| BT-4 lifetime/results/timing | Runtime/CLI and wrapper contracts, RUNBOOK, taxonomy, API lifecycle and CURRENT_AUTHORITY |
| BT-5/C/D | Governed start-path matrix, dependency policy, ARCHITECTURE, exception register, CURRENT_AUTHORITY |
| E1/E2 | Governance tools, .gitea jobs, manifest/generated view; CONTRIBUTOR in the same change if workflow expectations change |
| CAP-2 | Accepted isolation/threat-model contract, SECURITY, extension contracts, deployment/runbook and CURRENT_AUTHORITY |

Original exceptions remain governed by `ARCHITECTURE_EXCEPTION_REGISTER.json`:

| Exceptions | Closure owner |
|---|---|
| AT-EX-001 | C: allowed-edge cutover |
| AT-EX-003 | BT-5/E2: transport-only interfaces/application composition |
| AT-EX-004, AT-EX-007, AT-EX-008 | D: pure core, explicit decision and time/identity inputs |
| AT-EX-005 | BT-4/D: async reachability and process lifetime |
| AT-EX-006 | Explicit 0.7.0 removal; retain until authorized |
| AT-EX-009, AT-EX-010 | BT-3/E2: migrate replay-diagnostic and verification-index consumers; retire compatibility only under accepted conditions |
| AT-EX-011 | BT-2/BT-4/E2: version/migrate observability identity without dual event authority |
| AT-EX-012 | E2: move durable-path/ReviewRun v0 specifics into durable contracts with parity proof |
| AT-EX-013, AT-EX-014, AT-EX-015 | E1: taxonomy, no-op correctness and canonical lint |
| AT-EX-016 | E2: bounded manifest-backed authority |

AT-EX-002 stays removed. Retained compatibility is not conformance. Removal needs
proof of the existing condition, not a moved file or another lane's stronger
behavior. Preserve explicit owners/removal conditions for remaining exceptions.

For every authority/schema cutover: inventory/back up persisted state, rehearse
migration/restart on copies, prohibit incompatible mixed writers and retain
recovery evidence. Prefer roll-forward repair over restoring unsafe dispatch.
Rollback may disable a capability while preserving claims/effects/uncertainty; it
must never erase history to recover a green result.

## Required proof envelope

Each slice records finding/contract IDs, candidate commit/dirty posture, authority
edges, actual provider/model/backend, input/artifact hashes, test layer, public
surface, independently observed effects/state, exit, teardown and exact files.
Report separately:

- Proof: live local integration/public surface, live provider, structural or absent.
- Path: `primary`, `fallback`, `degraded` or `blocked`.
- Result: `success`, `failure`, `partial success` or `environment blocker`.
- Claim ceiling, missing proof and any exact environment blocker.

Changed runtime/integration behavior requires real end-to-end execution. Routine
proof sets `ORKET_DISABLE_SANDBOX=1`; intentional sandbox acceptance proves teardown.
Provider-neutral live tests use llama.cpp; no automatic switch is permitted.
An unattempted external path is absent proof, not an invented environment blocker.

Current commands, used as appropriate to each slice:

```powershell
$env:ORKET_DISABLE_SANDBOX = '1'
python -m pytest -q
python -m ruff check orket tests
python scripts/governance/enforce_test_taxonomy.py --strict
python scripts/governance/check_dependency_direction.py --legacy-edge-enforcement fail
python scripts/governance/check_noop_critical_paths.py
python scripts/governance/build_architectural_truth_baseline.py
python scripts/governance/check_docs_project_hygiene.py
```

These do not substitute for races, corruption, child shutdown, installed commands
or provider proof. Reuse governed-agent/llama.cpp proof entrypoints named in
CURRENT_AUTHORITY. Applicable .gitea Quality jobs, coverage thresholds, fresh
installed-wheel proof, Windows lifetime and supported Linux/Python matrix remain
final acceptance obligations. Import/dry-run/mock success cannot close them.

New scripts writing rerunnable JSON use existing rerun diff-ledger helpers and
one declared stable output. Extend the baseline rather than create competing
success authority. Keep September evidence immutable as review history.

## Completion, blockers and next action

The remediation milestone requires decisive proof for all SR and SD findings,
BT-5/C/D/E obligations, preserved A/B guarantees and explicitly governed remaining
compatibility. The capability milestone additionally requires accepted CAP-1
proof, a proven or explicitly still-unadmitted CAP-2 disposition and CAP-3 operating
limits. An unavailable required capability is partial success, not completion.

Close the whole lane only after user acceptance of proof and explicit closure or
retirement of remaining scope. Archive completed slice documents under
`docs/projects/archive/architectural-truth/` while this umbrella remains active
for later slices. Extract durable contracts before archiving project history.
Follow contributor version/changelog/tag policy when committing; this revision
performs no release, commit or push.

Remaining blockers or drift at this planning handoff:

- The nine ship-risk and six self-deception findings remain unfixed. Architecture,
  async, quality and authority debt remains; exploration-safe limitations keep
  their current claim ceilings.
- Source fingerprints matched, but adverse probes, full suite, installed builds,
  providers and external boundaries were not rerun for this documentation change.
- Existing provider edits/promotion need their own final-candidate proof. Paused
  cloud work, formal-proof extensions and other lanes are not reopened here.
- OS isolation feasibility, remote idempotency, supported-host acceptance and
  performance thresholds remain work in their named slices.

Next implementation action: BT-0 followed by BT-1. Reproduce stale same-tool
approval and concurrent duplicate execution, settle immutable authorization and
transaction/recovery semantics, then repair that boundary before expanding
outward autonomy or resuming the old Slice C-first sequence.
