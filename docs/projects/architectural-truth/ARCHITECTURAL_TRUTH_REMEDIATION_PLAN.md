# Architectural Truth Remediation Plan

Date: 2026-07-29
Last updated: 2026-09-17
Status: Active implementation plan; scoped BT-1 through BT-5 accepted; C/D is the next ordered gate
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
the unfinished July work. The September expansion placed behavioral repairs before
Slice C; their scoped acceptance now makes C/D the next ordered gate. This remains
the lane's single canonical execution plan.

The user activated the original lane on 2026-07-29, requested this expanded
plan on 2026-09-11, and then requested implementation in a separate worktree.
The subsequent complete-plan objective authorizes continued implementation.
The outward approval/effect lifecycle is settled in
`docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`; its scoped BT-1 acceptance is
recorded below. Other unimplemented schemas, migrations, exit mappings and capability
admissions remain requirements, not current guarantees. Before implementing
a changed contract, settle its semantics in the existing spec and record a delta
using `docs/architecture/CONTRACT_DELTA_TEMPLATE.md`. Extract accepted new durable
contracts into `docs/specs/` before implementation. New capability requirements
remain proposed until accepted for implementation.

Workflow authority remains `docs/CONTRIBUTOR.md`; execution priority remains
`docs/ROADMAP.md`; current runtime authority remains `CURRENT_AUTHORITY.md`.
The completed provider-promotion lane is archived on the integrated 0.6.2 base;
architectural truth is now the first Priority Now item in the existing roadmap.
Within this lane, behavioral repairs precede structural cleanup. Contributor
workflow now identifies shared repository inventory and the optional review-copy
command; runtime contracts change with their implementation and proof records below.

## Findings and complete disposition

SR-01 through SR-06 now pass their scoped BT-1/BT-2 behavioral acceptance gates
on the current dirty candidate; the installed acceptance and closure checkpoint
below records the requirement audit and proof ceilings. SD-02 now passes the
scoped replay acceptance recorded in BT-3. SR-07 now passes the builtin card
completion gate recorded in the final BT-3 audit. SR-08/SR-09/SD-05 pass the
current combined BT-4 gate recorded in its requirement table. ES-01 passes the
scoped five-requirement BT-5 disposition. Six September findings remain open.
A mapped slice is not a fix; closure requires its acceptance
evidence and updated authority. This does not constitute a core release or new
workload, containment or formal-proof admission.
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

### BT-0 opening checkpoint: 2026-09-11

Responsible maintainer: Codex for Orket Core. Worktree:
`C:/Source/Orket-architectural-truth`, branch `codex/architectural-truth-bt0`, base
`4ae960fc39e84fef14320be25c56061e076a4c05`. The worktree carries the user's current
contributor guide, roadmap, lane plan/registry and referenced provider-promotion
plan as documentation inputs. Provider implementation edits remain in the original
checkout. This is a dirty source candidate, not a clean release or installed-wheel
proof. No runtime code, release version, commit, tag or primary-checkout file changed.

Added `tests/integration/test_outward_authorization_boundary.py` with reusable
fixtures in `tests/helpers/outward_authorization.py`. Every case is classified
integration and asserts the healthy contract. There are no skips, expected-failure
markers or exception-register waivers for these defects. The resulting red tests
intentionally block acceptance until repaired; they are not a shippable checkpoint.

| Finding/control | Executed boundary and observation | Proof / path / result |
|---|---|---|
| SR-01 | `/approve` and `/decision`; two same-tool writes; stale retry in the same app, reopened app, and new Python process. All six write file 2 while proposal 2 stays pending, add a second tool event, and mark the run completed. First file contents and original approval response are retained. | live local authenticated ASGI + SQLite/files; process restart for two cases / primary / failure |
| SR-02 | Hold the first real connector until the second authenticated retry reads the live run on another SQLite connection. Both real Python commands append `effect`; only one tool event persists; one response is HTTP 500. | live local authenticated ASGI + SQLite/subprocess/files / primary / failure |
| SR-03 | Rendezvous after two real pending-row reads on separate connections, then approve/deny through authenticated requests. Both acknowledge HTTP 200 with contradictory decisions and both decision events persist. | live local authenticated ASGI + SQLite / primary / failure |
| SR-04 | Direct `/approve` at and one second after expiry, without queue/review reads, writes the file and records approval/tool success. | live local authenticated ASGI + SQLite/files, injected clock / primary / failure |
| Pre-expiry control | Direct approval one second before expiry writes once. | live local integration / primary / success |
| Authentication control | Wrong API key cannot change the proposal, ledger or filesystem. | live local integration / primary / success |

The schedule instrumentation delays real reads/dispatch; it does not supply fake
storage results or connector success. ASGI transport executes real authentication,
routers and application services in process; it is not a deployed HTTP listener.
Model responses are `fake-provider` / `fake-model` fixtures. No live model backend
was contacted. `ORKET_DISABLE_SANDBOX=1`; only isolated pytest workspaces/SQLite
databases and bounded local child commands were used. App containers close on every
path; created subprocesses are awaited, with bounded kill/wait for the restart
worker. Full API startup/background-service and descendant-cancellation proof is
outside this fixture's boundary.

Environment: Windows, Python 3.13.11, pytest 9.0.3, aiosqlite 0.22.1, FastAPI 0.136.1,
httpx 0.28.1. Source imports resolve inside this worktree. Installed distribution
metadata reports Orket 0.6.0 while the checkout is 0.6.1; no install/upgrade occurred,
and these observations cannot certify package-version parity.

Retained SHA-256 fingerprints (raw worktree file bytes; test sources also define
the fixture inputs, and the baseline is the retained rerunnable artifact):

| File | SHA-256 |
|---|---|
| `tests/helpers/outward_authorization.py` | `4bf76d3c870f14932039d7a8e3b8d8cb87bca569677aaaa3c15445c5a46e815c` |
| `tests/integration/test_outward_authorization_boundary.py` | `9e6e5469ff7834b19e433ce0d1cbd5e4da7ec3ae020b109e93e6a9768a19f2e8` |
| `orket/application/services/outward_approval_service.py` | `89ce9798f4ce3669b513e43fb71bae2ec9e95c41cd01fb4201a0655e00b8416d` |
| `orket/application/services/outward_run_execution_service.py` | `ad29ab123c5558efa0b773c0b4a99fc07df4500aa99b02741905b0095480e20d` |
| `docs/projects/architectural-truth/architectural_truth_baseline.json` | `c88629d73ac65d8b82bfef37d0a6c4fc789ee48bde4bae63b18d058b7c6efc46` |

Verification commands/results (with `ORKET_DISABLE_SANDBOX=1`):

- `python -m pytest -q tests/integration/test_outward_authorization_boundary.py --tb=short`:
  exit 1, **10 failed, 2 passed**; failures reproduce SR-01 through SR-04.
- `python -m pytest -q tests/application/test_outward_approval_service.py tests/application/test_outward_run_execution_service.py tests/interfaces/test_northstar_phase2_approvals_api.py tests/scripts/test_build_architectural_truth_baseline.py`:
  exit 0, **17 passed**. Includes live isolated API-factory baseline proof; these
  older positive tests do not negate the new counterexamples.
- `python -m ruff check tests/helpers/outward_authorization.py tests/integration/test_outward_authorization_boundary.py`:
  pass; structural proof only.
- `python scripts/governance/build_architectural_truth_baseline.py`: exit 0,
  `collection_ok=true`, `release_ready=false`; canonical baseline refreshed with
  its existing diff ledger. It collects command/factory and structural observations,
  not the new behavioral tests. Its Ruff scope is `orket` and reports 128 findings.
- `python scripts/governance/enforce_test_taxonomy.py --strict`: fails. After making
  the five new test functions readable to its existing comment-based parser,
  3,479 pre-existing unlabeled reports remain; no new test is unlabeled. The marker
  versus parser mismatch remains E1 debt, not a reason to waive these tests.
- `python scripts/governance/check_docs_project_hygiene.py`: pass.

BT-1 decisions are concrete proposals in
`docs/architecture/CONTRACT_DELTA_OUTWARD_AUTHORIZATION_BT1_2026-09-11.md`: immutable
binding, one serialized decision transaction, expiry at the decision boundary,
original-decision retries, fenced effect ownership, existing journal reuse,
uncertain recovery, and quarantine of unbound legacy rows. They are not effective
contracts. Settle/extract them into affected active specs before runtime changes.

Missing proof remains explicit:

| Obligation | Next owner/gate; current proof limit |
|---|---|
| SR-01 remaining binding variants | BT-1: mutate arguments, policy, scope and generation; inspect retained binding/effect receipts after repair. |
| SR-02/SR-03 crash and race envelope | BT-1: race independent worker processes, approve/approve before decision, approve/expire, two operators, persistence faults and all dispatch crash points. Current races use independent connections in one app; restart is a separate SR-01 case. |
| SR-04 full expiry gate | BT-1: lock-wait clock sampling, pending-scan-cap overflow and delayed approved dispatch. |
| SR-05/SR-06 | BT-2: corruption, independent anchors and complete snapshot export; September counterexamples not rerun here. |
| SR-07/SR-09 | BT-3/BT-4: composed final-card persistence and installed CLI outcome proof; the review's earlier evidence limits remain. |
| SR-08/SD-05 | BT-4: descendant lifetime and measured connector timing; awaited test children do not close those defects. |
| SD-02 | BT-3: empty/missing/corrupt/populated replay; existing edits in the primary checkout are outside this candidate. |
| SD-01/SD-03/SD-04/SD-06 | C/D/E: dependency/purity enforcement, full taxonomy/quality envelope and bounded authority; baseline collection does not close them. |
| ES-01/ES-02/ES-03 | BT-5/CAP: executor conformance, workload acceptance, OS containment; no new admission. |

BT-0 remains active. Full pytest, fresh wheel, supported Linux/Python matrix,
live llama.cpp and external services were not attempted at this checkpoint;
their proof is absent, not an invented environment blocker. All 18 findings
remain open. Next unclosed gate: active-contract settlement and remaining BT-0
counterexamples before the complete BT-1 authorization/effect repair gate.

## BT-1 — Exact authorization and durable effect lifecycle

### Decision transaction checkpoint: 2026-09-11

Historical checkpoint preceding the binding/effect implementation below.

The previous goal turn made progress by adding counterexamples; this continuation
implements the first decision boundary. Same worktree/branch/base and interpreter
as the BT-0 checkpoint; no primary-checkout edits, release, commit or tag.

Application-owned proposal creation and decisions now use
`OutwardStoreUnitOfWork`: one `BEGIN IMMEDIATE` connection for approval, run
projection and event. The application samples its clock after acquiring the lock,
uses pending-status CAS, and commits or rolls back all three records together.
Direct expiry is independent of queue reads and the 500-row scan limit. Original
decisions/operator metadata survive contradictory retries. Split-database paths
are rejected. Proposal numbering counts the entire run history. Routers only
continue a decision matching the returned approval status.

The complete lifecycle contract is now active in
`docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`; the delta, API/frontend
contract, taxonomy, runbook and CURRENT_AUTHORITY identify this implemented
boundary and the missing dispatch guarantees. No migration or binding backfill
has been performed. Old approval rows have not acquired new effect authority.

Proof: live local authenticated ASGI, real SQLite/files/subprocesses, with fixture
model/time inputs; path `primary`; result `partial success` for BT-1. Nine new
transaction cases pass: approve/deny rollback after actual SQLite projection or
event aborts, retry after reopening, deadline crossing during a real writer-lock
wait, direct expiry beyond 500 pending rows, atomic pending publication,
split-database refusal, and two independent authenticated API processes racing
different operator decisions. The last case waits until both processes attempt
the locked write and verifies one stored decision/event, matching acknowledgements,
operator retention and the corresponding filesystem effect after process exit.
These process workers are awaited and killed/waited on timeout. This is not live
provider proof or deployed-listener proof.

Verification:

- Outward application, event-store, approval/ledger API and new transaction tests:
  **41 passed**. The older positive execution test now approves before its stored
  deadline; its previous one-minute clock jump relied on the expired-approval bug.
- BT-0 boundary suite: **7 failed, 5 passed**. SR-03's two-connection approve/deny
  case and SR-04's exact/late deadline cases now pass. Six stale same-tool retry
  cases and concurrent duplicate command execution still fail without waivers.
- Scoped Ruff, dependency direction with `--legacy-edge-enforcement fail`, and
  docs project hygiene pass; these are structural checks, not full architecture
  conformance. The canonical baseline remains `release_ready=false`.
- Compliance: AC-01 through AC-06 pass for this change's imports, explicit clock,
  application policy and async storage. AC-08 passes with unchanged event fields.
  AC-07/AC-09/AC-10 are partial for the overall outward lifecycle: dispatch and
  effect/recovery evidence remain open BT-1/BT-2 obligations, explicitly described
  in current authority. No corresponding pre-existing exception was widened.

Files changed in this continuation:

- Runtime: `orket/adapters/storage/sqlite_connection.py`,
  `orket/adapters/storage/outward_approval_store.py`,
  `orket/adapters/storage/outward_run_store.py`,
  `orket/adapters/storage/outward_run_event_store.py`,
  `orket/adapters/storage/outward_store_transaction.py`,
  `orket/application/services/outward_approval_service.py`,
  `orket/interfaces/routers/approvals.py`.
- Tests: `tests/helpers/outward_authorization.py`,
  `tests/helpers/outward_decision_worker.py`,
  `tests/integration/test_outward_authorization_boundary.py`,
  `tests/integration/test_outward_approval_transactions.py`,
  `tests/application/test_outward_run_execution_service.py`.
- Authority/evidence: `CURRENT_AUTHORITY.md`, `docs/API_FRONTEND_CONTRACT.md`,
  `docs/RUNBOOK.md`, `docs/architecture/event_taxonomy.md`,
  `docs/architecture/CONTRACT_DELTA_OUTWARD_AUTHORIZATION_BT1_2026-09-11.md`,
  `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`, this canonical plan,
  `docs/projects/architectural-truth/README.md`, and
  `docs/projects/architectural-truth/architectural_truth_baseline.json`.

Remaining: immutable call/generation/policy binding, durable claim and fencing,
effect journal/reconciliation and atomic receipt/terminal publication, mixed-writer
prohibition and copied-store migration, complete process/crash envelope, and all
later slices. No SR-01 through SR-04 release gate or entire lane is closed. Next
action is the exact effect binding and pre-dispatch claim, reusing the existing
effect journal rather than adding a competing effect history. Full pytest,
installed-wheel, Linux matrix, live llama.cpp and other external proof remain absent.

### Binding and effect checkpoint: 2026-09-11

Historical checkpoint preceding the explicit pre-intent recovery implementation below.

Candidate: the same `C:/Source/Orket-architectural-truth` worktree and
`codex/architectural-truth-bt0` branch, based on `4ae960fc39e84fef14320be25c56061e076a4c05`.
Source version 0.6.1; installed metadata remains 0.6.0. Tests import the worktree.
No original-checkout edits, active-database upgrade, commit, tag, release or package
installation occurred. Source/provider/time limits remain those of BT-0.

Implemented:

- Immutable full call/argument and policy digests, namespace, resolved root/target,
  connector contract version, persistent execution generation and turn/step binding.
  Runtime composition shares the approval/dispatch connector policy owner. Public
  proposal previews remain redacted; complete calls stay in protected storage.
- Serialized schema initialization and proposal metadata/decision/history guards.
  New runs persist generation 1; legacy unbound rows cannot dispatch. Populated
  old stores refuse automatic migration. The new offline command backs up and
  upgrades a separate copy without switching the active store. Retiring the old
  approval table name makes legacy readers/writers fail closed; already authorized
  old processes still require explicit shutdown before migration.
- A unique proposal-derived effect record, per-invocation owner from explicit
  runtime inputs, fixed initial fencing generation and committed claim/intent.
  No lease takeover or automatic abandoned-claim reassignment is implemented.
- Shared `EffectJournalEntryRecord` schema/storage/chain validation, extracted
  from the existing repository. Claim, intent, receipt and publication retain one
  authoritative journal. Intent without receipt blocks retry, including possible
  crashes before invocation. The dispatcher reads only the protected bound call.
- Immutable receipts and atomic tool/turn/terminal event publication with the run
  result/progression and publication marker. A publication retry consumes the
  receipt; it never executes to repair an event. Published stale approvals cannot
  advance another turn. Shared lifecycle helpers preserve v1 event field/order
  semantics while shrinking the existing oversized execution service/repository.

Proof is **live local integration**, not provider or deployed-listener proof:
authenticated ASGI, real SQLite, real file/append commands, distinct API processes,
fixture model output and injected time. Observed path: `primary`; BT-1 result:
`partial success`. The original BT-0 boundary suite now has **12 passed**, including
six same-tool stale retries across endpoint/restart variants and concurrent append.
New proof includes nine dispatch-input drift variants; binding mutation/replacement
refusal; admitted approval followed by delayed dispatch; process deaths after
claim, intent, actual invocation, receipt and publication; two API processes
contending for one intent; and receipt republication after a real SQLite trigger
aborts ledger publication. Commands independently leave at most one append.

Copied migration proof includes preserved original/backup history, the actual
migration CLI/report, old table read/write refusal, no overwrite without new paths,
missing shutdown-acknowledgement refusal, and authenticated legacy approved/pending
retry refusal. The final targeted envelope has **89 passed, 1 failed**; no xfail,
waiver or resealing hides the failure. Full pytest, installed builds, Linux matrix,
live llama.cpp and other external boundaries remain unverified.

Remaining blockers or drift:

- `tests/kernel/v1/test_trust_handoff_admission.py::test_verified_handoff_admission_precedes_run_start`
  rejects before execution with `source_witness_bundle_invalid` / `MATH-CHECK-012`.
  The unchanged base fixture retains ledger digest
  `56bf4ba697be95e1f69770dcf1bf89b5f7a2c8cdbb72ff85f3fab20b49f45ec1`, while its
  ledger bytes hash to `4f92a9f4f11e90335f004eeb0fab7bffd03b01cf8ca3145a33cb5c050ec43d68`.
  Both fixture files and the verifier/contract/emitter match HEAD. Preserve the
  evidence; investigate/rebuild the fixture from valid provenance under BT-2.
- Abandoned pre-intent claims and legacy active runs remain blocked pending an
  explicit reconciliation/new-admission path that cannot revive an old owner.
  A process death after multi-turn publication but before the next model call can
  leave that next turn awaiting admission. An old approval deliberately cannot
  drive it. Implement an explicit durable admission/recovery owner and adverse
  process proof before closing BT-1.
- Remaining BT-1 adverse coverage includes migration interruption, claim/receipt
  storage failure/corruption variants, target filesystem replacement and complete
  supported-host proof. No generic exactly-once or new workload claim is admitted.
- Scoped Ruff for changed runtime/tests/new migration command passes. The two
  existing approved/denied proof scripts, changed only to supply workspace_root,
  retain 29 existing E402/ASYNC240 reports; CLI async exemptions do not make Ruff
  green. Full repository quality and the weaker legacy dependency policy remain E1/C.

Structural verification: dependency direction with `--legacy-edge-enforcement fail`
passes; new Python files/functions satisfy the 400/70-line bounds. Docs hygiene
and `git diff --check` pass. The canonical baseline refresh reports
`collection_ok=true`, `release_ready=false`, with 127 existing Ruff reports and
3,479 legacy taxonomy reports. New tests carry both integration markers and the
pre-definition layer comments required by the current limited taxonomy checker.
Compliance AC-01 through AC-06/AC-08 pass for changed imports, explicit inputs,
application authority, classified I/O adapters and unchanged event schema.
AC-07/AC-09 remain partial for full completion/replay/recovery under BT-1/BT-2/BT-3;
AC-10 is partial for the unchanged fixture and broader baseline drift documented
here. This checkpoint does not close the combined SR-01 through SR-04 release gate.

### Exact worktree file inventory at effect checkpoint

This inventory includes the original plan/roadmap/provider-plan documentation
carried into the worktree at BT-0; it does not imply provider implementation edits.

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/CONTRIBUTOR.md`
- `docs/ROADMAP.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_OUTWARD_AUTHORIZATION_BT1_2026-09-11.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/projects/local-provider-promotion/LLAMA_CPP_QWEN38_PROMOTION_PLAN.md`
- `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`
- `orket/adapters/storage/async_control_plane_record_repository.py`
- `orket/adapters/storage/control_plane_effect_journal_store.py`
- `orket/adapters/storage/outward_approval_migrations.py`
- `orket/adapters/storage/outward_approval_store.py`
- `orket/adapters/storage/outward_approval_upgrade.py`
- `orket/adapters/storage/outward_effect_store.py`
- `orket/adapters/storage/outward_run_event_store.py`
- `orket/adapters/storage/outward_run_store.py`
- `orket/adapters/storage/outward_store_transaction.py`
- `orket/adapters/storage/sqlite_connection.py`
- `orket/adapters/tools/registry.py`
- `orket/application/services/api_runtime_composition.py`
- `orket/application/services/outward_approval_service.py`
- `orket/application/services/outward_authorization_service.py`
- `orket/application/services/outward_connector_service.py`
- `orket/application/services/outward_effect_publication.py`
- `orket/application/services/outward_effect_service.py`
- `orket/application/services/outward_run_execution_plan.py`
- `orket/application/services/outward_run_execution_service.py`
- `orket/application/services/outward_run_lifecycle.py`
- `orket/application/services/outward_run_service.py`
- `orket/application/services/runtime_input_service.py`
- `orket/core/domain/outward_approvals.py`
- `orket/core/domain/outward_authorization.py`
- `orket/core/domain/outward_effects.py`
- `orket/core/domain/outward_runs.py`
- `orket/interfaces/routers/approvals.py`
- `scripts/governance/migrate_outward_approvals.py`
- `scripts/proof/run_outward_write_file_approved_proof.py`
- `scripts/proof/run_outward_write_file_denied_proof.py`
- `scripts/proof/run_outward_write_file_policy_rejected_proof.py`
- `tests/application/test_outward_approval_service.py`
- `tests/application/test_outward_run_execution_service.py`
- `tests/helpers/outward_authorization.py`
- `tests/helpers/outward_decision_worker.py`
- `tests/helpers/outward_effect_worker.py`
- `tests/integration/test_outward_approval_migration.py`
- `tests/integration/test_outward_approval_transactions.py`
- `tests/integration/test_outward_authorization_binding.py`
- `tests/integration/test_outward_authorization_boundary.py`
- `tests/integration/test_outward_effect_recovery.py`
- `tests/interfaces/test_northstar_phase2_approvals_api.py`
- `tests/kernel/v1/test_trust_handoff_admission.py`

### Historical pre-intent recovery checkpoint: 2026-09-12

The previous goal turn made progress; this continuation uses the same worktree,
branch, source version and environment. No commit, tag, package installation,
production-store switch or original-checkout mutation occurred.

The operator can now inspect `/v1/approvals/{id}/effect` and explicitly recover a
`claimed` effect through `/effect/recover`. Recovery compares the observed owner
and fencing generation, validates the original binding/run/policy/journal, and
atomically records generation N+1, its journal entry, a shared control-plane
`RecoveryDecisionRecord` and `OperatorActionRecord`. Existing shared storage
helpers are reused/extracted; no parallel recovery/operator history was added.
The complete bound arguments and receipt contents are absent from the inspection
response. The server supplies actor identity from authentication.

Recovery and intent contend on the same SQLite writer lock. Replacing a claim
prevents the old worker from committing intent even if that worker is alive.
Intent committed first cannot be reassigned, even after process death. Recovery
request identity binds proposal, request key, expected owner/fence and actor.
Identical retries reuse their original claim/receipt; changed or superseded
requests conflict. Missing, deleted or contradictory recovery authority blocks
inspection/dispatch without repairing history. A normal approval retry never
reassigns a claim. Initial journal references and all superseded claims remain
retained; new owners have generation-specific references.

Effect schema v2 adds the retained recovery pointer and controlled pre-intent
owner transition. A copied real generation-1 claim represented under canonical
v1 schema can upgrade and recover; a real SQLite failure at migration-record
publication rolls back the column/trigger changes and leaves the old claim intact.
The original copy remains unchanged. This proof does not claim power-loss testing
or generic mixed-host store portability.

Proof: **live local integration**, authenticated ASGI with real SQLite/commands
and isolated API processes; fixture model/time; path `primary`; BT-1 result
`partial success`. Fifteen pre-intent recovery cases pass: live old-owner fencing,
post-intent refusal after death, atomic recovery/operator failure rollback,
authentication/stale-input/conflicting-actor refusal, superseded recovery refusal,
recovery process deaths after claim/intent/dispatch/receipt/publication, and
recovery record deletion/contradiction. Two copied effect-schema migration cases
also pass. All worker handles are terminated/awaited on failure or fixture exit.

The next model-admission defect now has an executable public-entrypoint regression
in `tests/integration/test_outward_model_admission_recovery.py`. It kills an API
worker after effect publication, verifies the first file and published receipt,
then reopens the API. Retrying the old approval leaves the second file absent.
Resubmitting the same run returns `running`, turn 2, with no pending proposal;
the expected next governed proposal is missing. This test remains red without
xfail/waiver. A durable owner for model admission is required; merely calling the
current model helper on every retry would allow competing workers to overwrite
its fixed turn/evidence paths and publish competing proposals.

Final targeted envelope: **106 passed, 2 failed**. Failures are that new admission
regression and the unchanged trust-handoff fixture digest mismatch recorded in the
previous checkpoint. The existing SR-01 through SR-04 boundary cases remain green.
Full suite, installed-wheel, Linux, deployed-listener and live llama.cpp proof are
absent. Scoped Ruff, new Python size bounds, dependency direction with
`--legacy-edge-enforcement fail`, docs hygiene and `git diff --check` pass. The
refreshed canonical baseline reports `collection_ok=true`, `release_ready=false`,
127 Ruff reports and 3,479 legacy taxonomy reports. The two unchanged proof
script lint backlogs and incomplete repository release baseline remain open.

Remaining blockers or drift: implement durable next-turn model admission and
safe recovery with retained attempt evidence; provide bounded legacy-active-run
quarantine/new admission; finish remaining corruption/target-replacement/migration
proof and the wider plan gates. Unobserved dispatch remains explicitly uncertain.
The shared control-plane primitives and local fixture proof do not expand Packet 1,
formal single-turn claims, arbitrary-code admission or provider-selection scope.

### Historical durable model admission checkpoint: 2026-09-12

Candidate: dirty `codex/architectural-truth-bt0` at
`4ae960fc39e84fef14320be25c56061e076a4c05`, source 0.6.1, in
`C:\Source\Orket-architectural-truth`. Python 3.13.11 (Anaconda), pytest 9.0.3,
aiosqlite 0.22.1, FastAPI 0.136.1 and httpx 0.28.1; installed distribution metadata
still reports Orket 0.6.0. The primary checkout has independently advanced to
`11256920` (0.6.2) and is clean. This checkpoint has not integrated that commit;
the earlier carried provider documentation/roadmap remains part of this worktree
and needs reconciliation at integration. No commit, tag, install, production DB
migration or primary-checkout mutation occurred.

Run start and successful effect advancement now atomically create a ready model
admission alongside their existing run projection and events. Its immutable input
snapshot binds run generation, turn and step. A serialized claim admits exactly
one producer; concurrent requests cannot call the provider for the same admission.
The extracted call and original model artifact references/digests are retained in
an observed record before publication. Public run reentry can claim ready work or
publish an observed result without another model invocation. Proposal, complete
authorization, model event, run projection and admission publication commit
atomically. Model error and policy rejection use that same boundary.

A claimed admission without a retained result stays unresolved after process
loss, including a returned model response lost before observation. Ordinary run
retry returns conflict rather than minting another owner. Explicit replacement
with retained attempt evidence remains an open gate. Older running rows without
admission are not backfilled. Changed run inputs or unavailable/corrupt artifacts
block publication without rewriting evidence. The original extraction artifact
stays immutable; admission/proposal/events establish acceptance. An old
approval cannot initiate this separate model-admission recovery operation.

The executor shrank from 392 to 218 lines by extracting model admission and
transactional publication authority. New Python modules remain below 400 lines,
with no new function over 70 lines. Existing larger model production/evidence
functions were not expanded. The redundant post-publication extraction writer was
removed; no compatibility shim or second acceptance authority was added.

Proof: **live local integration**, authenticated ASGI, real SQLite transactions,
actual files/commands and isolated API worker processes. Model output and time are
fixtures; the new model fixture independently appends each invocation to a file.
Path: `primary`. Result for the bounded admission cases: `success`; complete BT-1:
`partial success`. Routine runs set `ORKET_DISABLE_SANDBOX=1`; each worker was
terminated or completed and awaited, and each API context confirmed no owned
background tasks on close.

Seventeen admission regressions pass: next-turn reentry after an effect-publication
crash; process death after ready/claim/response/observation/publication; competing
producer refusal and concurrent retained-result publication; actual approval
insert failure with complete publication rollback/restart; input/artifact drift
without repair; atomic initial-admission insertion failure; and SQL guards against
owner/input/result replacement, deletion and `INSERT OR REPLACE`. Ready and
observed recovery produce one model invocation and no file effect before their
own approval. Claimed uncertainty invokes no second producer. Existing approval,
effect, recovery and copied migration coverage stays green.

The 20-file targeted command from the previous checkpoint, including the expanded
admission file, now reports **123 passed, 1 failed in 107.67s**. The remaining
failure is unchanged
`test_verified_handoff_admission_precedes_run_start`: retained fixture digest
mismatch described above. It was not resealed or waived. The narrower admission,
execution and approval run reports **27 passed in 31.69s**. Scoped Ruff and the
current dependency-direction gate pass; this gate still enforces the transition
policy rather than C/D's full target model. The canonical collector reports
`collection_ok=true`, `release_ready=false`, 127 Ruff reports and 3,479 legacy
taxonomy reports. The final shared context-summary wording and extraction-hash
assertion also pass all 6 execution-service regressions (1.30s). Full pytest,
installed wheel, deployed
TCP listener, live llama.cpp and the Linux matrix were not run here; no environment
blocker is inferred for those unattempted paths.

Final Ruff over every changed runtime/test Python file, docs project hygiene and
`git diff --check` pass. Existing proof-script lint debt remains outside that
scoped runtime/test pass; the repository-wide baseline is still release-red.

Current source fingerprints (SHA-256, dirty candidate):

| Source | Digest |
|---|---|
| `orket/application/services/outward_model_admission_service.py` | `4ea531d498b64cdd6e33d084a45d437c71a9eb97831ae178dbebcb7a58788771` |
| `orket/adapters/storage/outward_model_admission_store.py` | `d87adcf0a3981c66e69b9815c4d5089aa4d672f4198f22e19588e1380f80bfbc` |
| `tests/integration/test_outward_model_admission_recovery.py` | `3c59fed4c60a7a3b99859fdc5c1cfd5fdb4ab83055e356f85dea04222dc676e0` |

Next unclosed BT-1 work: explicit recovery/disposition for claimed model admission
without a result, durable attempt-scoped evidence before any owner replacement,
legacy-active-run quarantine/new admission, and remaining corruption/target/migration
acceptance. Then proceed through BT-2 onward under the full objective. This
checkpoint does not close the combined SR-01 through SR-04 release gate, extend
formal single-turn claims or admit broader autonomy.

### Model-owner recovery and retained fixture checkpoint: 2026-09-12

The previous goal turn made progress. This continuation uses the same dirty
`codex/architectural-truth-bt0` worktree and source base
`4ae960fc39e84fef14320be25c56061e076a4c05` (0.6.1). The Python/package environment
is unchanged. Main integration with 0.6.2 remains pending; no commit, tag, install,
production store migration, or primary-checkout mutation occurred.

Authenticated current-admission inspection and explicit model recovery are now
implemented. Recovery compares the requested run/generation/turn/step/owner/fence,
requires unchanged inputs and an unobserved latest claim, and atomically appends a
ready attempt at fence N+1 with shared recovery/operator records. The old attempt
remains unchanged and unresolved. The new row commits a digest of its paired
recovery records; missing or changed authority blocks inspection and continuation.
Shared recovery persistence was extracted from the effect-only store and reused,
without a parallel operator/recovery history.

The recovery endpoint admits work but never calls a provider. Normal run reentry
claims the ready attempt. Identical recovery retries return their original attempt
without incrementing a fence or advancing another turn; conflicting actors/bodies
and superseded requests fail. If a replacement also loses its response, another
replacement needs a new explicit request with its current owner/fence. Observation
and recovery serialize on the same transaction boundary. A late old response
cannot observe or publish after replacement, even if its process remains alive.

New model evidence has an attempt-specific directory under
`workspace/<namespace>/runs/<run>/model_attempts/<scope-digest>/`. Files are created
exclusively; new attempts emit no shared latest aliases. A late old response can
retain its own files without changing the chosen attempt's commitments. The
published proposal references its admitted attempt. Provider invocation/billing
uncertainty remains explicit; recovery is not remote cancellation, provider
idempotency, or authority to retry a governed connector.

Model-admission schema v2 retains complete v1 rows and original artifacts while
retiring the old table name. Copied claimed/observed legacy fixtures use the real
model/evidence service in legacy layout. Migration success and injected migration
record failure show complete rollback, original-source preservation, retained
artifact hashes, old-writer SQL refusal, and successful API continuation or explicit
replacement on retry. Replacement always uses the isolated layout. This is not
hardware power-loss proof or an installed old-binary campaign.

The historical trust-handoff failure is now explained and repaired without
resealing. All six frozen approved/denied/policy-rejected ledger and bundle files
had been converted from their committed CRLF bytes to LF by Git. For every file,
the original CRLF representation exactly matches its existing manifest digest.
Those original bytes are restored. Manifests, retained digests, package IDs,
verifier algorithms and claims are unchanged. `.gitattributes` disables text
conversion for sealed outward fixtures and treats retained CR as a line ending
while retaining ordinary whitespace checks. Git clean-filter hashes now equal
unfiltered hashes for every manifest-committed file. This is a byte-preservation
repair, not broader BT-2 ledger-integrity completion.

Proof: **live local integration**, authenticated ASGI, real SQLite, artifact files,
commands and isolated API worker processes; fixture model/time. Path `primary`.
The bounded recovery and fixture corrections succeed; the full BT-1 gate remains
`partial success`. All worker handles are completed or killed and awaited; API
contexts close with no owned tasks. Routine proof sets `ORKET_DISABLE_SANDBOX=1`.

The final three-file model-admission envelope reports **35 passed in 61.21s**.
It includes 14 owner-recovery cases, 4 copied migration cases, and the 17 retained
admission regressions. Decisive cases cover a live old provider response arriving
after replacement publication, independent invocation counting, two successive
replacements, lost recovery responses, actor/body/stale-scope refusal, observation
winning against replacement, atomic recovery/attempt insertion failure, missing
predecessors, missing or corrupted recovery records, and an old request while the
next turn awaits approval. The selected output alone reaches its approved file.
The fixture/handoff/negative-corruption envelope reports **17 passed in 1.84s**.

Before the fixture-byte correction the expanded 23-file envelope reported
148 passed / 1 failed; that sole failure was the now-repaired trust-handoff fixture.
The final combined 28-file envelope reports **163 passed in 160.55s** after the
byte correction. It includes the prior 23-file envelope plus the frozen approved,
denied, policy-rejected and corruption contract files and the offline package
verifier tests. The previously failing authenticated handoff now admits its run;
negative corruption cases still reject. Scoped Ruff over all changed runtime/test
Python files, new file/function size limits, the current dependency gate, docs
hygiene and `git diff --check` pass. The latter recognizes retained CRLF while
keeping blank-at-eol/eof and space-before-tab checks. The canonical collector
reports `collection_ok=true`, `release_ready=false`, with 127 Ruff and 3,479 legacy
taxonomy reports; this is still not a release-ready repository baseline.

Current source fingerprints (SHA-256, dirty candidate):

| Source | Digest |
|---|---|
| `orket/application/services/outward_model_recovery_service.py` | `b28a9e5e41a6e43489393a1af07821e39e0976614318a589a9c095c39eae1a47` |
| `orket/application/services/outward_model_recovery_records.py` | `6ebe96de0852e6f5f24960a45535fdea07c2212f389037020cb2696d655af5ea` |
| `orket/adapters/storage/outward_model_admission_migrations.py` | `15deedd26f92da9953b6bc6c482092b0765ba7d8e3200ff5e6a66f5b6017a7cc` |
| `tests/integration/test_outward_model_owner_recovery.py` | `e928d70d810728f6ab7d584404e81121815563be0bb54e3d7d833f66cee6d5b8` |
| `.gitattributes` | `f1facef9ad7e476d8b7313bcb2e1585a865f23fcd2cee5154abe959201fa9aab` |

Full pytest, installed-wheel/old-binary, deployed-listener, live llama.cpp, supported
Linux/Python and power-loss proof remain absent. No environment blocker is inferred
for unattempted paths. Main integration and reconciliation of earlier carried
provider docs/roadmap remain required before final-candidate acceptance. Legacy
active-run quarantine/new admission and remaining target/corruption/migration
proof are the next BT-1 implementation gates; BT-2 onward and the capability
milestones remain active obligations under the full objective.

### Exact worktree file inventory at model recovery checkpoint

Includes the earlier carried documentation as well as implementation and proof.
Total: 88 files.

- `.gitattributes`
- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/CONTRIBUTOR.md`
- `docs/ROADMAP.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_OUTWARD_AUTHORIZATION_BT1_2026-09-11.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/projects/local-provider-promotion/LLAMA_CPP_QWEN38_PROMOTION_PLAN.md`
- `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`
- `docs/specs/OUTWARD_RUN_WITNESS_V1.md`
- `orket/adapters/storage/async_control_plane_record_repository.py`
- `orket/adapters/storage/control_plane_effect_journal_store.py`
- `orket/adapters/storage/control_plane_operator_action_support.py`
- `orket/adapters/storage/control_plane_recovery_store.py`
- `orket/adapters/storage/outward_approval_migrations.py`
- `orket/adapters/storage/outward_approval_store.py`
- `orket/adapters/storage/outward_approval_upgrade.py`
- `orket/adapters/storage/outward_effect_migrations.py`
- `orket/adapters/storage/outward_effect_store.py`
- `orket/adapters/storage/outward_model_admission_migrations.py`
- `orket/adapters/storage/outward_model_admission_store.py`
- `orket/adapters/storage/outward_run_event_store.py`
- `orket/adapters/storage/outward_run_store.py`
- `orket/adapters/storage/outward_store_transaction.py`
- `orket/adapters/storage/sqlite_connection.py`
- `orket/adapters/tools/registry.py`
- `orket/application/services/api_runtime_composition.py`
- `orket/application/services/outward_approval_service.py`
- `orket/application/services/outward_authorization_service.py`
- `orket/application/services/outward_connector_service.py`
- `orket/application/services/outward_effect_publication.py`
- `orket/application/services/outward_effect_recovery_records.py`
- `orket/application/services/outward_effect_service.py`
- `orket/application/services/outward_model_admission_inputs.py`
- `orket/application/services/outward_model_admission_service.py`
- `orket/application/services/outward_model_observability.py`
- `orket/application/services/outward_model_publication.py`
- `orket/application/services/outward_model_recovery_records.py`
- `orket/application/services/outward_model_recovery_service.py`
- `orket/application/services/outward_model_tool_call_service.py`
- `orket/application/services/outward_run_execution_plan.py`
- `orket/application/services/outward_run_execution_service.py`
- `orket/application/services/outward_run_lifecycle.py`
- `orket/application/services/outward_run_service.py`
- `orket/application/services/runtime_input_service.py`
- `orket/core/domain/outward_approvals.py`
- `orket/core/domain/outward_authorization.py`
- `orket/core/domain/outward_effects.py`
- `orket/core/domain/outward_model_admission.py`
- `orket/core/domain/outward_model_recovery.py`
- `orket/core/domain/outward_runs.py`
- `orket/interfaces/api.py`
- `orket/interfaces/routers/approvals.py`
- `orket/interfaces/routers/outward_effects.py`
- `orket/interfaces/routers/outward_models.py`
- `orket/interfaces/routers/runs.py`
- `scripts/governance/migrate_outward_approvals.py`
- `scripts/proof/run_outward_write_file_approved_proof.py`
- `scripts/proof/run_outward_write_file_denied_proof.py`
- `scripts/proof/run_outward_write_file_policy_rejected_proof.py`
- `tests/application/test_outward_approval_service.py`
- `tests/application/test_outward_run_execution_service.py`
- `tests/helpers/outward_authorization.py`
- `tests/helpers/outward_decision_worker.py`
- `tests/helpers/outward_effect_worker.py`
- `tests/helpers/outward_model_admission.py`
- `tests/integration/test_outward_approval_migration.py`
- `tests/integration/test_outward_approval_transactions.py`
- `tests/integration/test_outward_authorization_binding.py`
- `tests/integration/test_outward_authorization_boundary.py`
- `tests/integration/test_outward_effect_recovery.py`
- `tests/integration/test_outward_effect_schema_migration.py`
- `tests/integration/test_outward_model_admission_migration.py`
- `tests/integration/test_outward_model_admission_recovery.py`
- `tests/integration/test_outward_model_owner_recovery.py`
- `tests/integration/test_outward_pre_intent_recovery.py`
- `tests/interfaces/test_northstar_phase2_approvals_api.py`
- `tests/kernel/v1/test_trust_handoff_admission.py`
- `tests/proof_fixtures/outward_run/base_approved_package/ledger_export.json`
- `tests/proof_fixtures/outward_run/base_approved_package/outward_witness_bundle.json`
- `tests/proof_fixtures/outward_run/base_denied_package/ledger_export.json`
- `tests/proof_fixtures/outward_run/base_denied_package/outward_witness_bundle.json`
- `tests/proof_fixtures/outward_run/base_policy_rejected_package/ledger_export.json`
- `tests/proof_fixtures/outward_run/base_policy_rejected_package/outward_witness_bundle.json`

### Historical main integration and legacy-history quarantine checkpoint: 2026-09-12

Candidate: `C:/Source/Orket-architectural-truth`, branch
`codex/architectural-truth-bt0`, now based on main commit
`112569206211aaa5a009a5e5ef7af43af545c744` (0.6.2). The original checkout remains
clean and untouched. Installed distribution metadata still reports 0.6.0; source
imports resolve to this worktree. No release, package installation, new branch
commit/tag, active database migration or provider invocation occurred here.

Integration retained all carried remediation source content. Documentation
conflicts preserve the implementation checkpoints plus main's provider release.
The archived provider plan remains canonical; its obsolete carried active copy
is removed. CONTRIBUTOR and ROADMAP now match main exactly, with architectural
truth first in Priority Now. The outward proof script retains main's shared
llama.cpp defaults and the remediation's workspace binding. The stale extension
model-list default in API_FRONTEND_CONTRACT is corrected to the integrated
`llama_cpp` behavior. Main's bounded empty-replay refusal is included in regression
coverage; it does not establish complete BT-3 evidence sufficiency.

Before integration, all 88 changed files were backed up with raw-byte SHA-256
commitments in `C:/Users/jonmc/AppData/Local/Temp/orket-bt1-pre-main-integration-gg6mrgq1/`.
The backup stash `1ba16f38232e3f7487af73447897568fe11054f8` is retained. Git may
normalize ordinary source line endings; all six sealed fixtures retain their
exact pre-integration bytes and original manifest commitments. No manifests or
verifier rules changed. The index is empty and there are no unresolved conflicts.

Legacy-history repair:

- Generation-0 submission reentry, direct start and denial continuation fail
  before inventing a missing submission event or changing run/event history.
  This includes terminal records; ordinary status inspection remains available.
  `E_OUTWARD_LEGACY_RUN_QUARANTINED` describes admission, not a rewritten status.
- Pending approvals without complete bindings retain their historical statuses
  through reads and expiry sweeps. New decisions fail with
  `E_OUTWARD_AUTHORIZATION_REQUIRED` before deadline-based relabeling. The sweep
  selects bound records before its 500-row limit, so retained legacy rows cannot
  starve currently admitted expiry. The decision transaction still checks time
  after acquiring the writer lock.
- A fresh independent generation-1 run can complete its separately approved write
  alongside the retained old history. This does not reconcile the old run, free
  its namespace, prove physical target isolation or establish absence of old
  effects. Explicit replacement of old work remains an open BT-1 gate.

`test_outward_legacy_run_quarantine.py` uses real frozen-v1 SQLite stores, copied
migration, authenticated ASGI, fresh API contexts and independently inspected
rows/files. The first run reproduced **8 failures and 1 passing fresh-work
control**. After repair, the ten cases include five legacy statuses, both denial
routes, read/sweep/decision preservation, an independently approved real write,
and 501 retained unbound rows ahead of a bound deadline. No skipped or expected
failures were added. App contexts close with zero owned tasks; model output/time
are fixtures. Proof is **live local integration**, path `primary`; result
`partial success` for BT-1. No live provider, deployed listener or hostile-code
boundary is claimed. Routine proof sets `ORKET_DISABLE_SANDBOX=1`.

Verification:

- The integrated 31-file regression envelope passed **180 tests in 158.38s**.
- The final focused quarantine/approval/transaction/API envelope passed
  **31 tests in 9.83s**, including the ten new quarantine cases.
- The final 32-file envelope passed **190 tests in 151.62s** on the integrated
  source with the completed quarantine correction. It includes the previous
  28-file outward envelope, provider-default/render and empty-replay regressions,
  and all ten new quarantine cases.
- `python -m pytest -q --tb=short` failed collection in 16.03s:
  `tests/platform/test_no_old_namespaces.py` imports missing `project_dump`.
  The original checkout has an ignored `project_dump.py` (gitignore rules 57/58),
  but this tracked test and `tests/platform/test_project_dump.py` depend on that
  private local file. The canonical suite ran no tests. This is pre-existing
  repository portability/authority drift, not a missing pip dependency. No copy,
  import-path injection, skip, xfail or collection exclusion was used to hide it.
- Scoped Ruff over all 65 changed runtime/test Python files, new Python
  file/function limits, dependency direction with legacy-edge enforcement, docs
  project hygiene and `git diff --check` pass. Six sealed raw fixture hashes and
  Git filtered/unfiltered object hashes match. These are structural checks.
- The refreshed canonical baseline reports `collection_ok=true`,
  `release_ready=false`, 126 Ruff findings and
  3,497 legacy taxonomy reports. Collector success does not certify
  canonical pytest or repository release readiness.

Architecture compliance for the affected integration/quarantine behavior:

| Check | Result and scope |
|---|---|
| AC-01 | pass: changed imports retain interface/application/core/storage direction; dependency transition gate passes. |
| AC-02 | pass: no decision-node changes or new decision-node effects; generation admission is a pure domain check in `orket/core/domain/outward_runs.py`. |
| AC-03 | pass: admission consumes the persisted run generation and proposal binding; no new hidden decision input. |
| AC-04 | pass: no new clock/identity source; expiry retains the injected application clock after the writer lock. |
| AC-05 | pass: application services own refusal and expiry selection; `outward_approval_store.py` only translates the requested bound-row query. |
| AC-06 | partial: `orket/adapters/storage/outward_approval_store.py`, `outward_run_store.py` and `outward_run_event_store.py` still lack explicit class-level side-effect classification. This pre-existing metadata debt is not widened; C/D in this plan owns classification/caller enforcement. Earlier checkpoint shorthand about async storage is not proof that this metadata gate is complete. |
| AC-07 | partial: new quarantine paths preserve actual retained history and the fresh-write control checks the real file; broader completion/uncertainty in `outward_run_execution_service.py` and connector outcome/timing in `outward_connector_service.py` remain BT-1/BT-3/BT-4 obligations. No claim ceiling is widened. |
| AC-08 | pass: quarantine adds no ledger event type or historical relabeling; shared model/recovery schemas and existing taxonomy remain authoritative. |
| AC-09 | partial: retained history/artifacts survive these operations, but `outward_ledger_service.py` / `outward_run_event_store.py` still need BT-2 read-only corruption/completeness proof. No new repair-on-read behavior is introduced. |
| AC-10 | partial: affected lifecycle/API/runbook/current-authority docs match the new behavior and provider integration; ignored-tool test dependency in the two exact platform test paths above blocks canonical full-suite portability. E1 owns removal of that dependency with tracked, tested authority. |

Remaining blockers or drift: canonical full-suite collection, explicit legacy-run
reconciliation/replacement, remaining target/corruption/migration acceptance,
fresh installed-wheel/old-binary and supported-host/provider proof, and all later
plan slices remain open. Installed metadata differs from source. No environment
blocker is inferred for unattempted provider/host paths. The next required proof
repair is portable test collection; do not turn the ignored local exporter into
an undocumented compatibility dependency. Then continue the BT-1 gate without
inferring previous effect absence or erasing uncertain history.

Current source fingerprints (SHA-256, dirty integrated candidate):

| Source | Digest |
|---|---|
| `orket/core/domain/outward_runs.py` | `a9fa7d6967d432f2242b2d381e73bd4e4181493b2a50c3ce90acbc7eddad980a` |
| `orket/application/services/outward_approval_service.py` | `f9d8d6f3d83bd653c829727c0849ce407bc82c217f38425364db1b4f38188e5b` |
| `tests/integration/test_outward_legacy_run_quarantine.py` | `995911b726db37b782caafab9530f4373dda65a3a60c71f64d42b279877d7910` |

### Portable-suite and live-provider checkpoint: 2026-09-12

Same worktree/branch and 0.6.2 base `112569206211aaa5a009a5e5ef7af43af545c744`.
The original checkout is unchanged. This is a dirty source candidate; installed
metadata remains 0.6.0 and no release, install, commit, tag or push occurred.
This checkpoint supersedes the previous full-suite collection blocker and the
previous missing-live-provider statement, preserving their historical observations.

Repository proof repair:

- Git inventory now belongs to `scripts/common/git_inventory.py`; namespace
  tests and the repository review-copy CLI import it. Real Git/worktree/CLI tests
  cover ignored files, unusual names, missing repository, read errors, bounded
  partial output and preservation of prior output on discovery/read failure.
  The ten targeted tests passed. No ignored local exporter, import-path injection,
  skip or collection exclusion is needed.
- The first executable canonical suite returned **5 failed, 4,716 passed,
  74 skipped in 683.51s**. Failures identified two tests depending on ignored
  prompt thresholds, an archived ODR artifact prerequisite, a frozen input fixture
  missing the current owner-ID contract, and mismatched authority dates.
- Prompt thresholds are now tracked beside their CLI. Missing/invalid overrides
  fail before comparison. A real subprocess counterexample on HEAD's original
  script returned exit 0, `pass=true`, `criteria={}` for missing thresholds and a
  90% guard-pass fixture. The changed CLI returns exit 2 without a report; its
  default 95% criterion rejects that fixture from a foreign working directory.
- The ODR contract test checks its tracked frozen registry; separate temporary
  source-file fixtures prove loader resolution and missing-input refusal. No
  historical benchmark result was copied, published or certified. The timeout
  fixture inherits `RuntimeInputService`; both authority dates agree.
- The focused six-file failure/CLI envelope passed **28 tests in 2.56s**.
  The completed canonical rerun, `python -m pytest -q --tb=short`, passed
  **4,736 tests, 74 skipped, 2 warnings in 642.62s**. The two warnings concern
  the existing `orket.domain` import and a fixture's low generation token cap.
  Runtime behavior was fixed before this run; only documentation and test-label/
  import-spacing corrections followed. The final authority/CLI supplement passed
  **12 tests in 0.40s**. No new skip or expected-failure marker was introduced.

Live provider repair and proof:

- The existing approved-write proof initially failed before model generation:
  the outward planner requested native tooling from the admitted llama.cpp JSON
  wrapper profile. Shared request construction now consumes the resolved profile
  mode when the planner explicitly requests profile-selected transport. Native
  profiles and explicit native caller refusal retain their behavior. The focused
  helper/provider/outward envelope passed **46 tests**.
- `python scripts/proof/run_outward_write_file_approved_proof.py --provider llama_cpp
  --model orcarouter_qwen3.8-27b-uncensored-q4_k_l --json` now reports path `primary`,
  result `success`, approval required, accepted witness/artifact/corruption checks
  and no missing evidence. An independent file/SQLite inspection found exactly
  `outward proof live content`, one published effect and one tool event.
- Endpoint: `http://127.0.0.1:8080/v1`; server build `b10809-5266f24da`;
  model alias as above. Retained invocation: 386 prompt tokens, 28 completion
  tokens, 6,550ms, `tool_call_extracted`. This is real provider HTTP plus application
  services, SQLite and filesystem, with an injected clock. It is not a deployed
  authenticated API listener or a multi-turn/provider-crash acceptance run.
- Stable report: `benchmarks/results/proof/outward_write_file_approved_proof_run.json`;
  package: `benchmarks/results/proof/outward_run_witness_package.v1`.
  The report's diff ledger retains the failed and successful digests. Failed DB
  and local evidence remain at `.tmp/outward-write-file-approved-proof-native-request-failure`;
  successful evidence is under `.tmp/outward-write-file-approved-proof`.
  These are ignored local proof artifacts, not newly published benchmarks.
- Output SHA-256: `84db311bf4865a2acfd8b31b7cf2c522e994830cd2567f706f30f391c17f77bd`.
  Response-content SHA-256: `2d8ca0e3077aa706b896b2823b241741aadef07a5ce48f40202cf8729261a24d`.
  Server-template SHA-256: `8fc57a9f65eaaaee48e80771aea4775f7d3a8adb466a6193d8de551fa124d578`.
  The provider checks rendering before generation; outward invocation artifacts
  do not retain raw render/native-tool telemetry. No broader telemetry claim is made.
  `ORKET_DISABLE_SANDBOX=1`; no sandbox was created. Clients closed and the
  operator-owned server remained running.

Scope correction: BT-1 migration permits a new proposal **or explicit quarantine**.
The implemented and tested quarantine is the chosen legacy disposition. Earlier
notes incorrectly made old-run replacement a new mandatory workflow. The active
lifecycle contract, delta, runbook and authority now correct that drift. This
does not resolve unknown old effects, free targets or admit legacy-run replacement.
Remaining specific BT-1 proof includes physical target replacement and an explicit
independent-worker approve/expire race. The current two-operator worker signals
its first `BEGIN IMMEDIATE`, which can be schema initialization; tighten that
barrier after initialization before claiming synchronized decision contention.
Wider corruption/migration review and the
final installed-build/host envelope remain. All later slices remain active.

Structural checks: scoped Ruff for the inventory/export and changed tests passes;
Ruff over all 82 changed Python files reports 60 pre-existing findings across
`scripts/prompt_lab/compare_candidates.py` (31),
`scripts/proof/run_outward_write_file_approved_proof.py` (14), and
`scripts/proof/run_outward_write_file_denied_proof.py` (15). No
lint rule was disabled. Dependency transition enforcement and docs hygiene pass.
AC-01 through AC-05 and AC-08 pass for these changes. AC-06 remains partial for
the storage-adapter metadata paths identified in the prior checkpoint; AC-07 and
AC-09 remain partial for broader completion and BT-2 integrity. AC-10's ignored
local-tool/config prerequisites are repaired and the canonical suite passes.
All 45 new Python files satisfy the 400-line file and 70-line function limits.
The canonical baseline reports `collection_ok=true`, `release_ready=false`, 126
runtime Ruff findings and 3,491 legacy taxonomy reports. It is a separate
collection/readiness observation, not full architecture acceptance.

### Bound filesystem and decision contention checkpoint: 2026-09-12

Same worktree, branch and 0.6.2 base. No commit, tag, release or push. This
checkpoint supersedes the pending target-replacement and approve/expire proof
items above; it does not close all BT-1 or finding acceptance gates.

- A real symlink replacement after committed dispatch intent redirected an
  approved write into the replacement directory: the original test run returned
  **1 failed, 3 passed in 6.88s**. Filesystem dispatch now consumes the retained
  binding and operates through checked OS handles. Windows holds local-drive
  ancestor and leaf handles without delete sharing and rejects reparse entries;
  POSIX uses descriptor-relative, no-follow traversal. The original model path
  cannot redirect the actual read/write after those handles are acquired.
- The binding remains a canonical pathname commitment, not a historical inode,
  file-ID or content commitment. Windows and POSIX have different rename behavior;
  both tested paths protect the replacement target. This is not hostile-process
  containment or CAP-2 admission. Missing required host primitives fail closed.
- Cancellation retains ownership of the filesystem thread until it finishes and
  closes its handles. A canceled approval can leave a real write and unresolved
  dispatch intent; retry returns conflict instead of executing again. Tests inspect
  the file, journal and effect independently and prove handles close after success
  and cancellation. CRUD tests preserve the original argument digest.
- Independent authenticated workers now initialize schemas before signaling
  readiness. Both reach their actual decision transaction while a parent holds
  the SQLite writer lock. Approve/approve, approve/deny and approve/expire variants
  retain one authoritative decision and at most one effect. The final Windows
  transaction file passed **11 tests in 9.50s**.
- Windows outward regression envelope: **112 passed in 154.30s**, followed by the
  final transaction supplement above. The canonical Windows suite on the final
  runtime and test changes passed **4,746 tests, 74 skipped, 2 warnings in 640.37s**.
  Warnings remain the existing deprecated domain import and low generation cap.
- A fresh isolated Ubuntu 24.04 / Python 3.12.3 editable installation completed
  using the contributor command, including the SDK testing and root dev extras.
  Its 13-file outward envelope passed **112 tests in 412.73s**. A final supplement
  after the POSIX access-mode and replacement-link refinements passed **19 tests
  in 44.56s**. The previous supplement's terminal output was lost during context
  truncation; no pytest process remained, and this retained rerun supplies the
  evidence. No skipped or mocked host implementation substitutes for these cases.
- Linux environment: `/home/jon/.cache/orket-architectural-truth/venv-fiydvdck`,
  source at `/mnt/c/Source/Orket-architectural-truth`. Installed Orket 0.6.2,
  SDK 0.6.0, pytest 9.1.1, aiosqlite 0.22.1 and FastAPI 0.141.1. This is editable
  installation proof, not wheel or full supported-host/matrix acceptance.
  Linux installation created ignored worktree egg metadata. Windows Python from
  a foreign working directory still resolves installed metadata 0.6.0 and the
  original checkout; worktree-local metadata 0.6.2 does not prove Windows install
  parity. The Windows full suite exercises worktree source under Python 3.13.11.
- The live llama.cpp approved-write proof was rerun after the handle repair:
  path `primary`, result `success`, exactly one published effect and one tool
  event. The independently read output digest remains
  `84db311bf4865a2acfd8b31b7cf2c522e994830cd2567f706f30f391c17f77bd`.
  The retained invocation reports 386 prompt tokens, 28 completion tokens and
  1,015ms; artifact digest
  `a039dfb19ca6fb4d2510844dd698df3086fccb68873e4574fc80f58f6f7ff770`.
  The stable proof report's diff-ledger entry at `2026-09-12T11:01:10.714344Z`
  records an unchanged successful summary. Previous successful raw evidence is
  preserved at `.tmp/outward-write-file-approved-proof-before-bound-handles`;
  current raw evidence uses the canonical `.tmp/outward-write-file-approved-proof`.
  Provider endpoint/model and bounded proof scope remain those recorded above.

All runs use `ORKET_DISABLE_SANDBOX=1`; children and API clients are closed and
the operator's provider remains running. Contract delta:
`docs/architecture/CONTRACT_DELTA_OUTWARD_BOUND_FILESYSTEM_2026-09-12.md`.
Scoped Ruff and dependency transition enforcement pass. AC-01 through AC-05,
AC-08 and touched AC-10 pass; the new bound filesystem executor declares its
side effects. Existing AC-06 storage metadata debt, broader AC-07 completion and
AC-09 integrity obligations remain with C/D, BT-3 and BT-2. The canonical
baseline still reports `collection_ok=true`, `release_ready=false`; it does not
certify the complete architectural plan.

### Exact current worktree file inventory

- `.gitattributes`
- `.gitignore`
- `CURRENT_AUTHORITY.md`
- `core/artifacts/run_evidence_graph_schema.json`
- `core/artifacts/run_graph_schema.json`
- `core/artifacts/run_summary_schema.json`
- `core/artifacts/schema_registry.yaml`
- `core/policies/artifact_retention_tiers.yaml`
- `core/policies/prompt_budget.yaml`
- `core/tools/compatibility_map.yaml`
- `core/tools/compatibility_map_schema.yaml`
- `core/tools/tool_registry.yaml`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/ARCHITECTURE.md`
- `docs/CONTRIBUTOR.md`
- `docs/ROADMAP.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_API_REQUEST_OWNERSHIP_BT4_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_API_SHUTDOWN_BT4_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_CARD_ACCEPTANCE_ADMISSION_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_CARD_COMPLETION_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_CARD_DEPENDENCY_ACCEPTANCE_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_CARD_PROMPT_TRUTH_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_CARD_RETRY_REQUEUE_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_COMPLETION_GUARD_BT3_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_CONNECTOR_FILESYSTEM_LIFETIME_BT4_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_CONNECTOR_TIMING_BT4_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_ADMISSION_RECOVERY_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_APPROVAL_PAUSE_BT3_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_APPROVAL_RECOVERY_BT3_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_CLOSEOUT_PUBLICATION_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_EXPORT_RECOVERY_BT3_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_PREPARATION_RECOVERY_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_PUBLICATION_RECOVERY_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_RUN_ADMISSION_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_WORKLOAD_OUTCOME_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_EXECUTION_GRAPH_ACCEPTANCE_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_FIXTURE_LIFETIME_BT4_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_GITEA_EXPORT_RECEIPT_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_REPLAY_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_OPERATOR_COMPLETION_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_OUTWARD_AUTHORIZATION_BT1_2026-09-11.md`
- `docs/architecture/CONTRACT_DELTA_OUTWARD_BOUND_FILESYSTEM_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_OUTWARD_COMMAND_LIFETIME_BT4_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_OUTWARD_LEDGER_BT2_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_REPOSITORY_INVENTORY_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_RUNTIME_CONTRACT_ASSETS_BT3_2026-09-12.md`
- `docs/architecture/CONTRACT_DELTA_RUNTIME_RESULTS_BT4_2026-09-13.md`
- `docs/architecture/CONTRACT_DELTA_VERIFICATION_LIFETIME_BT4_2026-09-13.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md`
- `docs/specs/CONNECTOR_INVOCATION_TIMING.md`
- `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
- `docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md`
- `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`
- `docs/specs/GOVERNED_AGENT_LOOP_V1.md`
- `docs/specs/LEDGER_EXPORT_V1.md`
- `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`
- `docs/specs/OUTWARD_LEDGER_STORAGE_V2.md`
- `docs/specs/OUTWARD_RUN_WITNESS_V1.md`
- `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
- `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`
- `docs/specs/RUNTIME_INVARIANTS.md`
- `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
- `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
- `docs/specs/TOOL_CONTRACT_TEMPLATE.md`
- `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
- `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`
- `model/core/rocks/run_the_business.json`
- `orket/adapters/execution/fixture_docker.py`
- `orket/adapters/execution/owned_command_linux.py`
- `orket/adapters/execution/owned_command_process.py`
- `orket/adapters/execution/owned_command_windows.py`
- `orket/adapters/execution/owned_command_worker.py`
- `orket/adapters/execution/owned_io.py`
- `orket/adapters/execution/process_lifecycle.py`
- `orket/adapters/llm/local_model_provider.py`
- `orket/adapters/llm/openai_compat_runtime.py`
- `orket/adapters/llm/openai_native_tools.py`
- `orket/adapters/storage/async_card_repository.py`
- `orket/adapters/storage/async_control_plane_execution_repository.py`
- `orket/adapters/storage/async_control_plane_record_repository.py`
- `orket/adapters/storage/async_repositories.py`
- `orket/adapters/storage/bound_filesystem.py`
- `orket/adapters/storage/bound_filesystem_posix.py`
- `orket/adapters/storage/bound_filesystem_windows.py`
- `orket/adapters/storage/card_acceptance_artifacts.py`
- `orket/adapters/storage/card_acceptance_evidence_store.py`
- `orket/adapters/storage/card_completion_migrations.py`
- `orket/adapters/storage/card_migrations.py`
- `orket/adapters/storage/card_misc_ops.py`
- `orket/adapters/storage/card_record_codec.py`
- `orket/adapters/storage/card_write_ops.py`
- `orket/adapters/storage/control_plane_effect_journal_store.py`
- `orket/adapters/storage/control_plane_operator_action_support.py`
- `orket/adapters/storage/control_plane_recovery_store.py`
- `orket/adapters/storage/control_plane_transaction.py`
- `orket/adapters/storage/epic_approval_pause_store.py`
- `orket/adapters/storage/epic_continuation_lock.py`
- `orket/adapters/storage/epic_export_dispatch_store.py`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/adapters/storage/governed_agent_decision_store.py`
- `orket/adapters/storage/governed_agent_replay_store.py`
- `orket/adapters/storage/governed_agent_repository_support.py`
- `orket/adapters/storage/outward_approval_migrations.py`
- `orket/adapters/storage/outward_approval_store.py`
- `orket/adapters/storage/outward_approval_upgrade.py`
- `orket/adapters/storage/outward_effect_migrations.py`
- `orket/adapters/storage/outward_effect_store.py`
- `orket/adapters/storage/outward_ledger_append_store.py`
- `orket/adapters/storage/outward_ledger_legacy_import.py`
- `orket/adapters/storage/outward_ledger_snapshot_store.py`
- `orket/adapters/storage/outward_ledger_upgrade.py`
- `orket/adapters/storage/outward_model_admission_migrations.py`
- `orket/adapters/storage/outward_model_admission_store.py`
- `orket/adapters/storage/outward_run_event_store.py`
- `orket/adapters/storage/outward_run_store.py`
- `orket/adapters/storage/outward_store_transaction.py`
- `orket/adapters/storage/sqlite_backup.py`
- `orket/adapters/storage/sqlite_connection.py`
- `orket/adapters/tools/builtin_connectors.py`
- `orket/adapters/tools/families/cards.py`
- `orket/adapters/tools/families/filesystem.py`
- `orket/adapters/tools/registry.py`
- `orket/adapters/tools/runtime.py`
- `orket/adapters/vcs/gitea_artifact_exporter.py`
- `orket/adapters/vcs/gitea_export_git.py`
- `orket/adapters/vcs/gitea_webhook_handlers.py`
- `orket/application/services/api_runtime_composition.py`
- `orket/application/services/api_runtime_container.py`
- `orket/application/services/card_acceptance_evaluation.py`
- `orket/application/services/card_acceptance_service.py`
- `orket/application/services/card_artifact_acceptance_evaluation.py`
- `orket/application/services/card_completion_composition.py`
- `orket/application/services/card_completion_outcome_service.py`
- `orket/application/services/card_completion_prompt.py`
- `orket/application/services/card_completion_service.py`
- `orket/application/services/card_completion_turn_service.py`
- `orket/application/services/card_dependency_service.py`
- `orket/application/services/card_workspace_mutation_service.py`
- `orket/application/services/cards_epic_closeout.py`
- `orket/application/services/cards_epic_control_plane_service.py`
- `orket/application/services/command_process_supervisor.py`
- `orket/application/services/connector_invocation_timing.py`
- `orket/application/services/epic_admission_service.py`
- `orket/application/services/epic_approval_pause_service.py`
- `orket/application/services/epic_approval_recovery_service.py`
- `orket/application/services/epic_dispatch_batch.py`
- `orket/application/services/epic_export_recovery_service.py`
- `orket/application/services/epic_preparation_service.py`
- `orket/application/services/epic_publication_service.py`
- `orket/application/services/epic_setup_service.py`
- `orket/application/services/epic_workload_outcome_service.py`
- `orket/application/services/execution_graph_service.py`
- `orket/application/services/fixture_container_owner.py`
- `orket/application/services/fixture_verification_service.py`
- `orket/application/services/governed_agent_api_composition.py`
- `orket/application/services/governed_agent_execution_composition.py`
- `orket/application/services/governed_agent_inspection_service.py`
- `orket/application/services/governed_agent_replay_service.py`
- `orket/application/services/governed_turn_tool_approval_continuation_service.py`
- `orket/application/services/guard_review_payload.py`
- `orket/application/services/operator_completion_service.py`
- `orket/application/services/orchestrator_failure_handler.py`
- `orket/application/services/orchestrator_review_preflight_service.py`
- `orket/application/services/orchestrator_turn_context_builder.py`
- `orket/application/services/orchestrator_turn_preparation_service.py`
- `orket/application/services/orchestrator_turn_success_handler.py`
- `orket/application/services/outward_approval_service.py`
- `orket/application/services/outward_authorization_service.py`
- `orket/application/services/outward_connector_service.py`
- `orket/application/services/outward_effect_publication.py`
- `orket/application/services/outward_effect_recovery_records.py`
- `orket/application/services/outward_effect_service.py`
- `orket/application/services/outward_ledger_service.py`
- `orket/application/services/outward_model_admission_inputs.py`
- `orket/application/services/outward_model_admission_service.py`
- `orket/application/services/outward_model_observability.py`
- `orket/application/services/outward_model_publication.py`
- `orket/application/services/outward_model_recovery_records.py`
- `orket/application/services/outward_model_recovery_service.py`
- `orket/application/services/outward_model_tool_call_service.py`
- `orket/application/services/outward_run_execution_plan.py`
- `orket/application/services/outward_run_execution_service.py`
- `orket/application/services/outward_run_lifecycle.py`
- `orket/application/services/outward_run_service.py`
- `orket/application/services/runtime_execution_observation.py`
- `orket/application/services/runtime_execution_result_service.py`
- `orket/application/services/runtime_input_service.py`
- `orket/application/services/runtime_result_lifetime.py`
- `orket/application/services/runtime_result_projection.py`
- `orket/application/services/runtime_verifier.py`
- `orket/application/services/runtime_verifier_capture.py`
- `orket/application/services/tool_approval_control_plane_reservation_service.py`
- `orket/application/services/turn_tool_checkpoint_authority.py`
- `orket/application/services/turn_tool_control_plane_recovery.py`
- `orket/application/workflows/epic_approval_checkpoint.py`
- `orket/application/workflows/orchestrator.py`
- `orket/application/workflows/orchestrator_ops.py`
- `orket/application/workflows/prompt_budget_guard.py`
- `orket/application/workflows/turn_checkpoint_snapshot.py`
- `orket/application/workflows/turn_contract_validator.py`
- `orket/application/workflows/turn_corrective_prompt.py`
- `orket/application/workflows/turn_executor_control_plane.py`
- `orket/application/workflows/turn_executor_control_plane_evidence.py`
- `orket/application/workflows/turn_executor_ops.py`
- `orket/application/workflows/turn_executor_resume_replay.py`
- `orket/application/workflows/turn_executor_runtime.py`
- `orket/application/workflows/turn_message_builder.py`
- `orket/application/workflows/turn_response_parser.py`
- `orket/application/workflows/turn_tool_dispatcher.py`
- `orket/application/workflows/turn_tool_dispatcher_protocol.py`
- `orket/cli.py`
- `orket/core/contracts/card_acceptance_inputs.py`
- `orket/core/contracts/card_completion.py`
- `orket/core/contracts/card_completion_commit.py`
- `orket/core/contracts/control_plane_transaction.py`
- `orket/core/contracts/epic_approval_pause.py`
- `orket/core/contracts/epic_approval_recovery.py`
- `orket/core/contracts/epic_export_recovery.py`
- `orket/core/contracts/epic_publication.py`
- `orket/core/contracts/gitea_export.py`
- `orket/core/contracts/governed_agent_replay.py`
- `orket/core/contracts/invocation_timing.py`
- `orket/core/contracts/owned_command.py`
- `orket/core/contracts/owned_container.py`
- `orket/core/contracts/repositories.py`
- `orket/core/contracts/runtime_execution_result.py`
- `orket/core/domain/fixture_verifier.py`
- `orket/core/domain/outward_approvals.py`
- `orket/core/domain/outward_authorization.py`
- `orket/core/domain/outward_effects.py`
- `orket/core/domain/outward_ledger.py`
- `orket/core/domain/outward_ledger_integrity.py`
- `orket/core/domain/outward_model_admission.py`
- `orket/core/domain/outward_model_recovery.py`
- `orket/core/domain/outward_run_events.py`
- `orket/core/domain/outward_runs.py`
- `orket/core/domain/records.py`
- `orket/core/domain/verification.py`
- `orket/core/domain/workitem_transition.py`
- `orket/core/policies/card_acceptance_admission.py`
- `orket/core/policies/card_completion.py`
- `orket/decision_nodes/builtins.py`
- `orket/driver_support_resources.py`
- `orket/exceptions.py`
- `orket/extensions/governed_agent_invoker.py`
- `orket/extensions/governed_agent_process.py`
- `orket/extensions/runtime.py`
- `orket/extensions/sdk_workload_subprocess.py`
- `orket/interfaces/api.py`
- `orket/interfaces/api_app_context_middleware.py`
- `orket/interfaces/cli.py`
- `orket/interfaces/governed_agent_cli.py`
- `orket/interfaces/operator_view_models.py`
- `orket/interfaces/operator_view_support.py`
- `orket/interfaces/routers/approvals.py`
- `orket/interfaces/routers/cards.py`
- `orket/interfaces/routers/outward_effects.py`
- `orket/interfaces/routers/outward_ledger.py`
- `orket/interfaces/routers/outward_models.py`
- `orket/interfaces/routers/runs.py`
- `orket/interfaces/routers/streaming.py`
- `orket/logging.py`
- `orket/orchestration/engine.py`
- `orket/orchestration/engine_approvals.py`
- `orket/orchestration/engine_services.py`
- `orket/organization_loop.py`
- `orket/runtime/config/__init__.py`
- `orket/runtime/config/assets/artifacts/run_evidence_graph_schema.json`
- `orket/runtime/config/assets/artifacts/run_graph_schema.json`
- `orket/runtime/config/assets/artifacts/run_summary_schema.json`
- `orket/runtime/config/assets/artifacts/schema_registry.yaml`
- `orket/runtime/config/assets/contracts/RUNTIME_INVARIANTS.md`
- `orket/runtime/config/assets/policies/artifact_retention_tiers.yaml`
- `orket/runtime/config/assets/policies/prompt_budget.yaml`
- `orket/runtime/config/assets/tools/compatibility_map.yaml`
- `orket/runtime/config/assets/tools/compatibility_map_schema.yaml`
- `orket/runtime/config/assets/tools/tool_registry.yaml`
- `orket/runtime/config/compact_turn_packet.py`
- `orket/runtime/config/contract_assets.py`
- `orket/runtime/config/provider_truth_table.py`
- `orket/runtime/config/runtime_context.py`
- `orket/runtime/config/turn_prompt_contracts.py`
- `orket/runtime/execution/__init__.py`
- `orket/runtime/execution/epic_run_approval.py`
- `orket/runtime/execution/epic_run_finalize.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/epic_run_result_boundary.py`
- `orket/runtime/execution/epic_run_support.py`
- `orket/runtime/execution/epic_run_types.py`
- `orket/runtime/execution/execution_pipeline.py`
- `orket/runtime/execution/execution_pipeline_card_dispatch.py`
- `orket/runtime/execution/execution_pipeline_ledger_events.py`
- `orket/runtime/execution/execution_pipeline_resume.py`
- `orket/runtime/execution/execution_pipeline_run_summary.py`
- `orket/runtime/execution/gitea_state_loop.py`
- `orket/runtime/execution/live_acceptance_assets.py`
- `orket/runtime/execution/live_acceptance_contracts.py`
- `orket/runtime/execution/pipeline_wiring_service.py`
- `orket/runtime/policy/prompt_budget_policy.py`
- `orket/runtime/registry/contract_bootstrap.py`
- `orket/runtime/registry/runtime_invariant_registry.py`
- `orket/runtime_paths.py`
- `orket/schema.py`
- `orket/tools.py`
- `pyproject.toml`
- `scripts/acceptance/report_live_acceptance_patterns.py`
- `scripts/acceptance/run_live_acceptance_loop.py`
- `scripts/acceptance/verify_fixture_container_lifetime.py`
- `scripts/common/git_inventory.py`
- `scripts/governance/check_runtime_invariant_registry.py`
- `scripts/governance/export_review_packet.py`
- `scripts/governance/migrate_outward_approvals.py`
- `scripts/governance/migrate_outward_ledger.py`
- `scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py`
- `scripts/governance/record_truthful_runtime_packet1_live_proof.py`
- `scripts/governance/record_truthful_runtime_packet2_repair_live_proof.py`
- `scripts/probes/probe_support.py`
- `scripts/productflow/run_governed_write_file_flow.py`
- `scripts/prompt_lab/README.md`
- `scripts/prompt_lab/compare_candidates.py`
- `scripts/prompt_lab/prompt_promotion_thresholds.json`
- `scripts/proof/run_outward_write_file_approved_proof.py`
- `scripts/proof/run_outward_write_file_denied_proof.py`
- `scripts/proof/run_outward_write_file_policy_rejected_proof.py`
- `scripts/run_provider_codegen_matrix.py`
- `scripts/security/build_tool_gate_audit.py`
- `tests/adapters/test_async_card_repository.py`
- `tests/adapters/test_card_ops_components.py`
- `tests/adapters/test_gitea_artifact_exporter.py`
- `tests/adapters/test_gitea_webhook.py`
- `tests/adapters/test_local_model_provider_telemetry.py`
- `tests/adapters/test_model_invocation.py`
- `tests/adapters/test_openai_native_tools.py`
- `tests/adapters/test_verification_subprocess.py`
- `tests/application/test_async_executor_service.py`
- `tests/application/test_control_plane_workload_authority_governance.py`
- `tests/application/test_decision_nodes_planner.py`
- `tests/application/test_engine_approvals.py`
- `tests/application/test_engine_refactor.py`
- `tests/application/test_execution_pipeline_cards_epic_control_plane.py`
- `tests/application/test_execution_pipeline_gitea_state_loop.py`
- `tests/application/test_execution_pipeline_issue_entrypoints.py`
- `tests/application/test_execution_pipeline_protocol_run_ledger.py`
- `tests/application/test_execution_pipeline_run_ledger.py`
- `tests/application/test_execution_pipeline_session_status.py`
- `tests/application/test_execution_pipeline_workload_shell.py`
- `tests/application/test_odr_prebuild_continuation.py`
- `tests/application/test_orchestrator_epic.py`
- `tests/application/test_orchestrator_verification_async.py`
- `tests/application/test_organization_loop.py`
- `tests/application/test_outward_approval_service.py`
- `tests/application/test_outward_connector_service.py`
- `tests/application/test_outward_ledger_service.py`
- `tests/application/test_outward_run_execution_service.py`
- `tests/application/test_parallel_execution.py`
- `tests/application/test_prompt_candidate_comparison.py`
- `tests/application/test_prompt_promotion_thresholds.py`
- `tests/application/test_tool_gate_enforcement_closure.py`
- `tests/application/test_turn_executor_middleware.py`
- `tests/contract/test_api_request_lifecycle.py`
- `tests/contract/test_api_shutdown_outcomes.py`
- `tests/contract/test_connector_invocation_timing.py`
- `tests/contract/test_epic_batch_result_priority.py`
- `tests/contract/test_epic_export_recovery.py`
- `tests/contract/test_fixture_container_ownership.py`
- `tests/contract/test_outward_command_deadline_observation.py`
- `tests/contract/test_runtime_result_cleanup.py`
- `tests/contract/test_runtime_result_projection.py`
- `tests/contract/test_verification_supervisor_protocol.py`
- `tests/contracts/test_card_retry_transition.py`
- `tests/contracts/test_run_evidence_graph_contract.py`
- `tests/contracts/test_turn_prompt_truth.py`
- `tests/core/test_card_completion.py`
- `tests/core/test_card_management_state_machine.py`
- `tests/core/test_runtime_event_logging.py`
- `tests/helpers/card_completion.py`
- `tests/helpers/card_dispatch.py`
- `tests/helpers/epic_approval_recovery_worker.py`
- `tests/helpers/epic_continuation_lock_worker.py`
- `tests/helpers/epic_export_recovery.py`
- `tests/helpers/epic_publication_recovery_worker.py`
- `tests/helpers/epic_publication_worker.py`
- `tests/helpers/gitea_server.py`
- `tests/helpers/outward_authorization.py`
- `tests/helpers/outward_decision_worker.py`
- `tests/helpers/outward_effect_worker.py`
- `tests/helpers/outward_ledger.py`
- `tests/helpers/outward_ledger_migration.py`
- `tests/helpers/outward_ledger_migration_worker.py`
- `tests/helpers/outward_model_admission.py`
- `tests/helpers/protocol_ledger_clock.py`
- `tests/helpers/runtime_cli_lifecycle_worker.py`
- `tests/helpers/runtime_result.py`
- `tests/integration/policy_enforcement/test_runtime_policy_enforcement.py`
- `tests/integration/test_api_active_request_ownership.py`
- `tests/integration/test_api_shutdown_ownership.py`
- `tests/integration/test_api_stream_request_ownership.py`
- `tests/integration/test_card_acceptance_admission.py`
- `tests/integration/test_card_acceptance_service.py`
- `tests/integration/test_card_artifact_acceptance.py`
- `tests/integration/test_card_completion_control_plane.py`
- `tests/integration/test_card_completion_epic_outcomes.py`
- `tests/integration/test_card_completion_persistence.py`
- `tests/integration/test_card_completion_prompt_authority.py`
- `tests/integration/test_card_completion_receipt_inspection.py`
- `tests/integration/test_card_completion_transactions.py`
- `tests/integration/test_card_completion_turn.py`
- `tests/integration/test_card_completion_workspace_guard.py`
- `tests/integration/test_card_dependency_acceptance.py`
- `tests/integration/test_card_retry_recovery.py`
- `tests/integration/test_empirical_verification.py`
- `tests/integration/test_engine_boundaries.py`
- `tests/integration/test_epic_admission_recovery.py`
- `tests/integration/test_epic_approval_continuation.py`
- `tests/integration/test_epic_approval_recovery.py`
- `tests/integration/test_epic_approval_recovery_competing.py`
- `tests/integration/test_epic_approval_recovery_history.py`
- `tests/integration/test_epic_closeout_process.py`
- `tests/integration/test_epic_completion_publication.py`
- `tests/integration/test_epic_continuation_lock.py`
- `tests/integration/test_epic_outcome_recovery.py`
- `tests/integration/test_epic_preparation_recovery.py`
- `tests/integration/test_epic_publication_clock_inputs.py`
- `tests/integration/test_epic_publication_recovery.py`
- `tests/integration/test_epic_publication_recovery_process.py`
- `tests/integration/test_epic_run_admission.py`
- `tests/integration/test_execution_graph_acceptance.py`
- `tests/integration/test_gitea_epic_export_recovery.py`
- `tests/integration/test_gitea_export_owner_recovery.py`
- `tests/integration/test_golden_flow.py`
- `tests/integration/test_governed_agent_effect_service.py`
- `tests/integration/test_governed_agent_empty_replay.py`
- `tests/integration/test_governed_agent_import_origin.py`
- `tests/integration/test_governed_agent_replay_evidence.py`
- `tests/integration/test_governed_agent_supervisor.py`
- `tests/integration/test_governed_agent_wake_controls.py`
- `tests/integration/test_governed_guard_epic_rejection.py`
- `tests/integration/test_governed_guard_rejection.py`
- `tests/integration/test_idesign_enforcement.py`
- `tests/integration/test_operator_completion_views.py`
- `tests/integration/test_outward_approval_migration.py`
- `tests/integration/test_outward_approval_transactions.py`
- `tests/integration/test_outward_authorization_binding.py`
- `tests/integration/test_outward_authorization_boundary.py`
- `tests/integration/test_outward_bound_filesystem.py`
- `tests/integration/test_outward_command_capture.py`
- `tests/integration/test_outward_command_lifetime.py`
- `tests/integration/test_outward_command_uncertainty.py`
- `tests/integration/test_outward_connector_timing.py`
- `tests/integration/test_outward_effect_recovery.py`
- `tests/integration/test_outward_effect_schema_migration.py`
- `tests/integration/test_outward_filesystem_lifetime.py`
- `tests/integration/test_outward_ledger_api_integrity.py`
- `tests/integration/test_outward_ledger_commitments.py`
- `tests/integration/test_outward_ledger_integrity.py`
- `tests/integration/test_outward_ledger_migration.py`
- `tests/integration/test_outward_ledger_migration_refusal.py`
- `tests/integration/test_outward_ledger_migration_restart.py`
- `tests/integration/test_outward_ledger_offline.py`
- `tests/integration/test_outward_ledger_resource_limits.py`
- `tests/integration/test_outward_ledger_snapshot.py`
- `tests/integration/test_outward_legacy_run_quarantine.py`
- `tests/integration/test_outward_model_admission_migration.py`
- `tests/integration/test_outward_model_admission_recovery.py`
- `tests/integration/test_outward_model_owner_recovery.py`
- `tests/integration/test_outward_pre_intent_recovery.py`
- `tests/integration/test_outward_target_replacement.py`
- `tests/integration/test_runtime_cli_lifecycle.py`
- `tests/integration/test_runtime_contract_package_assets.py`
- `tests/integration/test_runtime_event_schema_reporting.py`
- `tests/integration/test_runtime_execution_results.py`
- `tests/integration/test_runtime_verifier_output_integrity.py`
- `tests/integration/test_system_acceptance_flow.py`
- `tests/integration/test_verification_process_lifetime.py`
- `tests/integration/test_verification_shutdown.py`
- `tests/integration/test_verification_supervisor_receipts.py`
- `tests/integration/verification_lifetime_worker.py`
- `tests/integration/verification_shutdown_worker.py`
- `tests/interfaces/test_api.py`
- `tests/interfaces/test_api_expansion_gate.py`
- `tests/interfaces/test_api_operator_views.py`
- `tests/interfaces/test_cli_startup_semantics.py`
- `tests/interfaces/test_northstar_e2e_acceptance.py`
- `tests/interfaces/test_northstar_phase2_approvals_api.py`
- `tests/interfaces/test_operator_view_models.py`
- `tests/interfaces/test_orket_bundle_cli.py`
- `tests/kernel/v1/test_trust_handoff_admission.py`
- `tests/live/test_system_acceptance_pipeline.py`
- `tests/platform/test_no_old_namespaces.py`
- `tests/platform/test_project_dump.py`
- `tests/platform/test_review_packet.py`
- `tests/proof_fixtures/outward_run/base_approved_package/ledger_export.json`
- `tests/proof_fixtures/outward_run/base_approved_package/outward_witness_bundle.json`
- `tests/proof_fixtures/outward_run/base_denied_package/ledger_export.json`
- `tests/proof_fixtures/outward_run/base_denied_package/outward_witness_bundle.json`
- `tests/proof_fixtures/outward_run/base_policy_rejected_package/ledger_export.json`
- `tests/proof_fixtures/outward_run/base_policy_rejected_package/outward_witness_bundle.json`
- `tests/runtime/test_artifact_retention_tiers.py`
- `tests/runtime/test_epic_run_orchestrator.py`
- `tests/runtime/test_extension_components.py`
- `tests/runtime/test_governed_agent_loop.py`
- `tests/runtime/test_run_summary.py`
- `tests/scripts/test_outward_run_invariant_checker.py`
- `tests/scripts/test_prompt_candidate_cli.py`
- `tests/scripts/test_round_cap_probe.py`

### Required implementation and acceptance

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

### Historical opening retained-integrity counterexamples: 2026-09-12

The real SQLite/application-service envelope in
`tests/integration/test_outward_ledger_integrity.py` returned **9 failed, 3 passed
in 159.24s**. Observed path: `primary`; result: `failure`. This is live local
storage/service proof with injected timestamps; no authenticated listener,
external anchor or new migration was exercised. Tests deliberately assert the
required behavior and are neither skipped nor marked expected failure.

- Append leaves `event_hash` absent until a read performs sealing.
- After payload, event-hash, chain-hash, order or middle-row corruption,
  verification changes the retained logical database. An independent read-only
  SQLite dump before and after two calls demonstrates the mutation.
- Deleting the tail returns `valid` twice without any retained count/head detecting
  the missing event.
- Counts 0, 4,999 and 5,000 export successfully. With 5,001 actual rows, the export
  labels its 5,000-row prefix complete. Independent SQL confirms the missing tail.
- A second PII export above the old cap raises `sqlite3.IntegrityError` for a
  duplicate `run_events.event_id`; its audit identity reused the capped count.

The full Windows suite result above predates these new failing tests. The current
worktree is therefore **not a green or shippable checkpoint**. The new failures
expose pre-existing defects; no BT-2 runtime repair is implemented yet.

Implementation decision:
`docs/architecture/CONTRACT_DELTA_OUTWARD_LEDGER_BT2_2026-09-12.md` selects separate
v2 retained append commitments and a complete read-only snapshot, with v1 export
order/hash semantics preserved as a derived projection. It requires separate
integrity/completeness/authenticity claims, prior external-prefix comparison and
explicit copied legacy migration. No active database or retained fixture was
migrated or resealed as part of this checkpoint. BT-1 atomic publication remains
the integration boundary; paused formal-proof extensions stay paused.

### Native retained-storage checkpoint: 2026-09-12

Same user-requested worktree/branch and 0.6.2 base. Native append now commits the
event, canonical hash, per-run append sequence, v2 chain and head/count in the
existing SQLite publication transaction. Normal old-style insert, replacement,
update and delete attempts against native events fail the database guards.
Verification uses one read-only snapshot with independent counts/head and all
pages; no schema initialization, missing-database creation or hash repair occurs.
`_ensure_hashes` and `update_hashes` are removed. Durable authority is
`docs/specs/OUTWARD_LEDGER_STORAGE_V2.md`.

V1 order and hashes remain derived export projections. Live retained integrity,
snapshot completeness, offline export self-consistency and authenticity are
separate claims. PII audit identities use serialized append sequence and the
authenticated actor. Ledger transport moved out of the oversized API module into
`orket/interfaces/routers/outward_ledger.py`. Authenticated POST verification
accepts an independently retained prefix anchor. A rewrite of all local events
and local heads can pass local integrity but fails comparison with the prior
external anchor; later legitimate appends preserve the prefix comparison.

Native proof and corrections:

- All nine opening failures are repaired. The 52-test Windows storage/API/decision/
  legacy-quarantine envelope passed in 47.15s after native writer guards. Real
  snapshot tests pause between pages while a second WAL writer commits; the first
  export retains its original count/head and the later export includes the append.
  Corruption tests remove write guards explicitly to model alteration of the
  database itself, then verify twice without changing its logical contents.
- The first broader suite returned **4 failed, 4,774 passed, 74 skipped, 2 warnings
  in 615.59s**. The four failures were generated denial/policy-rejection fixtures
  with rejection timestamps later than completion. Their two synthetic timestamp
  assignments were corrected; strict v1 ordering was retained. All 40 focused
  invariant/package/offline tests passed in 3.05s. The actual sealed packages were
  already valid, and all six ledger/bundle digests still match the retained
  originals. No sealed fixture was regenerated or resealed.
- A further real SQLite barrier case exposed caller mutation between hashing and
  payload serialization: **1 failed, 13 deselected in 0.21s**. Append now captures
  the JSON payload once at the serialized writer boundary before awaiting the
  commitment write. The final Windows append/ledger/API/decision envelope passed
  **50 tests in 27.08s**. Separate validation covers wrong heads/counts, sequence
  gaps, orphan commitments, changed provenance, malformed anchors, empty-run
  identity, huge/overlapping span bounds and rehashed noncanonical v1 ordering.
- Ubuntu 24.04 / Python 3.12.3 in the previously isolated editable environment
  passed **59 tests in 43.39s** on the final native runtime and ledger tests. This
  includes real SQLite, HTTP middleware, independent decision processes and an
  actual offline CLI subprocess. It is not the complete host/package matrix.
- The final Windows canonical suite, `python -m pytest -q --tb=short`, passed
  **4,794 tests, 74 skipped, 2 warnings in 629.56s**. The two warnings remain the
  deprecated domain import and a fixture's low generation cap. Runtime and test
  behavior were frozen; only docs and test-label comment placement changed during
  the run. No new skip or expected-failure marker was introduced.

Live llama.cpp proof on the final append implementation reports path `primary`,
result `success`, accepted witness/artifact/corruption checks and no missing
evidence. Independent read-only inspection found one published effect, one tool
event, ten event rows and ten commitments. The retained head is
`6e95f8e52b55075142560b007a4d2653d327991a8cb8dcc1bb14d0644cfe0a20`.
Output remains `outward proof live content`, SHA-256
`84db311bf4865a2acfd8b31b7cf2c522e994830cd2567f706f30f391c17f77bd`.
The invocation artifact reports 386 prompt tokens, 28 completion tokens, 981ms
and `tool_call_extracted`; its digest is
`69ad4bfff4116d28833747b65444f849f3dea51667814819ed7cb21653a8faea`.
The stable proof report retains the successful diff-ledger entry at
`2026-09-12T12:04:30.005146Z`. Prior raw proof remains at
`.tmp/outward-write-file-approved-proof-before-ledger-v2` and
`.tmp/outward-write-file-approved-proof-before-ledger-payload-capture`; current
evidence remains at the canonical `.tmp/outward-write-file-approved-proof`.
This is real provider HTTP plus application, SQLite and file effects with an
injected clock, not a deployed listener or wider provider/workload acceptance.
Routine runs set `ORKET_DISABLE_SANDBOX=1`; children and API contexts close and
the operator-owned provider stays running.

Scoped Ruff passes for all current BT-2 runtime and test files. New Python files
remain below 400 lines and new functions below 70. Native event storage now
declares its side effects, and snapshot storage declares read-only behavior.
Dependency transition enforcement and docs hygiene pass. Test labels now occupy
the existing taxonomy checker's recognized pre-definition context; its 3,491
legacy missing-label reports are not widened. The canonical baseline remains
`collection_ok=true`, `release_ready=false`, with 126 runtime Ruff findings.
AC-01 through AC-05, AC-08 and the touched AC-10 authority are addressed; broader
AC-06 storage metadata, AC-07 completion and AC-09 migrated-history obligations
remain with C/D, BT-3 and BT-2. No engine release, commit, tag or push occurred.

At the native checkpoint, remaining BT-2 work was explicit copied legacy backfill/quarantine with provenance,
corrupt-input refusal, interruption/restart and old-writer rejection; resource
limit extremes; final installed-build/host acceptance. Existing unsealed rows
remain retained and cannot be exported or appended as native authority. Reserved
legacy origin references do not constitute an implemented migration command.
BT-1's wider installed/host/migration gate and every later slice remain active.

### Copied ledger migration checkpoint: 2026-09-12

Same worktree/branch and 0.6.2 base. `migrate_outward_ledger_copy` and the real
`python -m scripts.governance.migrate_outward_ledger` command now implement the
copied migration contract in `docs/specs/OUTWARD_LEDGER_STORAGE_V2.md`. The shared
SQLite backup helper also replaces the approval migration's duplicated copy
code; its regression envelope remains green.

The command requires stopped-writer acknowledgement and new backup/destination
paths, protects SQLite sidecars and report hardlink aliases, retains committed
WAL data in the backup, and never activates its candidate. Its one candidate
writer transaction checks canonical schemas, migration records, indexes and
writer guards; refuses orphan or partial native state; verifies every available
v1 hash in original order; and backfills/validates all commitments before commit.
Missing hash cells need explicit `--allow-unsealed`; mismatches are never repaired.
Original event cells, retained exports and execution generations remain unchanged.
Existing native anchors preserve their origins. Imported origins bind the complete
backup digest. Generation-0 histories still refuse authenticated reentry and
direct execution across API restart; import does not grant execution authority.

Proof observed path `primary`, result `success`:

- Windows ledger/migration/approval/legacy-quarantine regression envelope:
  **104 passed in 52.56s**. It includes the real CLI with retained v1 export
  comparison at 0, 4 and 5,001 events, explicit unsealed refusal/import, unchanged
  legacy cells, mixed native/legacy histories, new append prefix compatibility,
  old-writer rejection, committed WAL copying, corrupt hash/schema/metadata
  refusal, no-overwrite/path-collision guards and authenticated quarantine.
- A separate worker executes 1,000 real uncommitted commitment inserts, then
  pauses at an injected barrier. Killing that process leaves `state: started`,
  replacing a previous successful report. Independent reopen finds complete
  transaction rollback and unchanged source/backup evidence. Reusing output
  paths fails; a fresh-copy retry imports all 2,001 events. This is real process
  interruption with an injected scheduling barrier, not a mock database result.
- Actual resource extremes, without lowering production limits:
  **2 passed in 9.89s**. Exactly 100,000 events or 64 MiB of aggregate payload JSON
  imports and verifies; one more event/byte refuses import. A subsequent native
  append beyond either bound causes snapshot resource rejection, never a prefix
  labeled complete. These are correctness bounds, not capacity or memory-usage
  acceptance.
- Ubuntu 24.04 / Python 3.12.3 in the isolated editable environment:
  **80 passed in 106.06s**, including copied migration, process kill/restart,
  resource extremes, native integrity, authenticated API, offline CLI and approval
  migration.
- Final Windows canonical suite, `python -m pytest -q --tb=short`:
  **4,825 passed, 74 skipped, 2 warnings in 650.34s**. Runtime/test behavior stayed
  frozen during the run. The warnings remain the deprecated domain import and
  fixture low-generation-cap warning; no skip or expected-failure waiver was added.

The production migration CLI also ran against the retained pre-v2 database from
the earlier real llama.cpp approved-write proof:
`.tmp/outward-write-file-approved-proof-before-ledger-v2/outward.sqlite3`.
It produced the inactive candidate and backup under
`.tmp/bt2-legacy-ledger-migration/`, with the stable report `report.json`.
The successful report entry is `2026-09-12T12:40:15.028380Z`. All ten events and
twenty existing hash cells validated, with zero unsealed events. The backup digest
is `f69d81806b1186abcbfb99950ad7010e08807c59fa6f2befe4af8278c3b30bb8`,
the derived original v1 chain is
`744128c28fe77efad92cbb25d3ed951ac073a57dbbeddb23ba59181e145060ff`,
and the imported v2 head is
`738e7ce33627de260ff6fcbc68f06ee9fa97d9167231409469dd38cb15ab9087`.
Independent read-only SQLite inspection found identical source/backup logical
contents and unchanged candidate event, run and effect rows. Retained verification,
v1 export verification and external-prefix comparison passed without changing
candidate contents. This is live copied migration of retained provider evidence;
no new provider call, effect dispatch, production-store activation or sandbox
resource creation occurred. Historical authenticity remains unestablished.

Scoped Ruff, dependency direction and docs hygiene pass. The refreshed baseline records `collection_ok=true`, `release_ready=false`,
126 runtime Ruff findings and 3,491 pre-existing missing test labels across
4,388 test functions. All 70 new Python files remain below 400 lines, with no
new function above 70 lines. The six sealed fixture hashes still match their
retained originals. AC-01 through
AC-05, AC-08 and touched AC-10 authority remain addressed; new migration adapters
declare side effects and the snapshot reader stays read-only. AC-06's pre-existing
storage-classification debt remains with C/D, broader AC-07 completion with BT-3,
and final AC-09 installed/host migration acceptance remains open. The migration
does not establish history that disappeared before its source snapshot or
authenticate the backup independently. No finding release gate, capability gate
or whole-lane acceptance is closed by these bounded results.

Initial installed-wheel proof also passes on Windows / Python 3.12.2. Core and
SDK wheels were built from this frozen worktree and installed with dev/testing
extras into `.tmp/architectural-truth-wheel-acceptance/win-py312`:

- `orket-0.6.2-py3-none-any.whl`, SHA-256
  `871565399f5d4c0fbaf5efe53f6f0a7805575a1a048c0e20e68d3d551e81bfea`.
- `orket_extension_sdk-0.6.0-py3-none-any.whl`, SHA-256
  `59bbd692e0fb844ec737901c167fb7951f6b2c7f050d220bc1b4db6a050130bc`.

From `C:/Users/jonmc/AppData/Local/Temp/orket-wheel-foreign-py312-k5i39tx7`,
the installed `orket demo governed-run` and `orket-quickstart --decision approve`
commands exit zero. The latter writes `hello from a governed Orket action` plus
a newline, SHA-256
`da54b6d10ad4b8c232b40cdd216c490fd7dd9142da645bf3fb5b8abf80c5c383`;
the installed independent quickstart verifier accepts its six-event ledger.
Using `python -I` and assertions that imports resolve inside the isolated
`site-packages`, the installed migration adapter imports the retained provider
database, validates all twenty hash cells, preserves event/run/effect rows and
verifies its v1 projection. Its independent backup digest is
`fbc593d55ea02c7267441fa587a2e6eece3b57fad35ec1c21d5937d1e9ce71f2`;
imported head is `ff33f81f2b31cb9ae1ef71c2c3cc55256cef4072cb8e2f93f61f4377d5d8e40d`.
`pip check` reports no broken requirements. All commands terminate and database
connections close; no source checkout is installed globally or active store
replaced. This proves the stated installed entrypoints and copied adapter path,
not the complete BT-1/BT-2 wheel/API/process envelope. Linux and Windows Python
3.11 wheel acceptance remains unverified. The migration CLI is repository tooling;
its adapter is shipped in the core wheel. The earlier global Windows installation
remains outside this isolated proof.

### Required implementation and acceptance

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

### Installed acceptance and BT-1/BT-2 closure: 2026-09-12

Candidate remains the user-requested `C:/Source/Orket-architectural-truth`
worktree, branch `codex/architectural-truth-bt0`, based on
`112569206211aaa5a009a5e5ef7af43af545c744` (0.6.2), with the dirty changes listed
in the exact inventory. Original checkout remains clean; no commit, tag, release,
push or production-store activation occurred. This checkpoint closes the combined
SR-01 through SR-04 outward-effect behavioral gate and SR-05/SR-06 ledger gate for
the recorded Windows/Linux Python 3.11/3.12 scope. It does not close the whole
architectural-truth lane or admit another workload, provider, formal claim or
hostile-process boundary. BT-3 is the next implementation slice.

The initial installed matrix exposed a real defect that source-only Python 3.13
proof had missed:

| Original wheel | Result |
|---|---|
| Windows / Python 3.11.14 | 1 failed, 191 passed in 171.99s |
| Windows / Python 3.12.2 | 192 passed in 212.98s |
| Linux / Python 3.11.16 | 1 failed, 191 passed in 140.77s |
| Linux / Python 3.12.3 | 192 passed in 146.68s |

Both 3.11 failures reached the real filesystem worker barrier, then the cancelled
HTTP request completed while that thread could still write. A focused Windows
3.11 repeat reproduced the failure in 1.06s. `outward_connector_service.py` now
uses an `asyncio.timeout` scope in the owning task instead of a `wait_for` task
wrapper. The bound executor retains its existing thread-drain responsibility.
The integration test now exercises one and three cancellation requests. A new
real deadline case proves that timeout publication also waits for the worker,
retains the timeout receipt, and cannot redispatch an already completed write.
No sleep was enlarged, assertion weakened, test skipped or failure reclassified
as a platform waiver. The focused repaired Windows 3.11 envelope passed 13 tests
in 3.49s before rebuilding the wheel.

The repaired core wheel is
`.tmp/architectural-truth-wheel-acceptance/cancellation-fix-wheels/orket-0.6.2-py3-none-any.whl`,
SHA-256 `9fb86a5b5db199129796cd61880577d6a19ed08f915893adacea60a429675557`.
The SDK wheel remains 0.6.0, SHA-256
`59bbd692e0fb844ec737901c167fb7951f6b2c7f050d220bc1b4db6a050130bc`.
The original failing core wheel remains unchanged under the preceding `wheels/`
directory. Separate environments install the wheel, with dev/testing dependencies,
rather than editable runtime source. `pip check` passes in all four environments.

The test harness copies 1,510 Git-visible test/script/config files with byte-digest
checks, including retained fixtures, into a foreign directory. It contains no
`orket/` or SDK source package. All 22 `tests/integration/test_outward*.py` modules
run there, so child workers whose cwd is the test root also use the installed
runtime. `PYTHONPATH` is cleared. Every final report records 747 loaded core/SDK
module origins inside that environment's `site-packages`, with zero unexpected
origins, the wheel archive hash and selected test hashes. These controls prevent
a green source import from masquerading as wheel proof.

| Repaired wheel matrix | Observed result | Final report SHA-256 |
|---|---|---|
| Windows / Python 3.11.14 | 194 passed in 184.75s | `19cf4fcb001efca35d59ef446c2e31a0cb612a00f4512509fa09e052d0a227ef` |
| Windows / Python 3.12.2 | 194 passed in 227.47s | `777907119ab16a4900c2962c4357e420c249deadf0f344c4ac4c87dd2fcebbd9` |
| Ubuntu 24.04 / Python 3.11.16 | 194 passed in 201.98s | `109034f35499fc4ef2752fc0e042a44eaa108beac36d18aed02a6b2f9d1e9e97` |
| Ubuntu 24.04 / Python 3.12.3 | 194 passed in 204.48s | `b6e5c642616bcd351660aa897d3ef1b233929e3635142b884fb1896fbe191af8` |

These are 194 cases repeated in each matrix cell, not 776 distinct cases. Linux
runs use the WSL Linux home filesystem, including effect targets and SQLite files,
rather than the mounted Windows checkout. The Windows harness is
`C:/Users/jonmc/AppData/Local/Temp/orket-wheel-bt12-harness-ib4ifck7`; the Linux
harness is `/home/jon/.cache/orket-architectural-truth/wheel-bt12-harness`.
Each retains `wheel-results/<cell>/report.json`, `junit.xml`, the original pytest
temporary data and a separate `pytest-temp-cancellation-fixed` tree. Original
inputs and complete failing/passing reports are preserved under
`preserved-before-cancellation-fix`. The copy manifest remains at
`.tmp/architectural-truth-wheel-acceptance/harness-manifest.json`; the repaired
driver digest is `08cb31088dc3bcc4e2e30ed7926c263d39ea43d8f3bc9e73bb2816405842eec3`.
All test processes are terminal and API contexts/owned child processes are closed.

Requirement audit below references tests under `tests/integration/` unless another
path is given. Every row is backed by the repaired installed matrix, the canonical
suite, or the separate live provider/API evidence stated here; code inspection
alone is not its acceptance proof.

| Requirement | Decisive current evidence and conclusion |
|---|---|
| BT-1 change 1: complete immutable binding | `test_outward_authorization_binding.py` rejects argument, namespace, generation, turn, step, policy, connector-version, allowlist and workspace drift; retained complete arguments and SQLite immutable-row guards pass. |
| BT-1 change 2: serialized expiry | `test_outward_authorization_boundary.py` and `test_outward_approval_transactions.py` cover before/exact/after expiry without queue reads, beyond-cap history and the clock sampled after a real writer-lock wait. |
| BT-1 change 3: conditional decision and atomic publication | Real SQLite aborts roll back proposal/run/event/head together; independent approve/approve, approve/deny and approve/expire workers yield one durable decision and preserve operator identity. |
| BT-1 change 4: exact durable effect claim | Same-tool stale retries through authenticated endpoints and a new process return the original effect; another pending write stays absent. Separate API workers cannot share a claim. |
| BT-1 change 5: journal/uncertainty/fence | `test_outward_effect_recovery.py` and `test_outward_pre_intent_recovery.py` validate shared journal chains, owned claim recovery and blocked unobserved intent. Arbitrary append commands are never assumed idempotent. |
| BT-1 change 6: all outward retry/start paths | `test_outward_legacy_run_quarantine.py`, model-admission/recovery tests and effect-publication tests cover authenticated/direct reentry, persisted ready/observed work, owner replacement and publication failure without redispatch. |
| BT-1 acceptance: races/restart/crash | The matrix exercises claim, intent, dispatch, receipt and publication process-death barriers; independent files/append lines agree with durable state. Corruption, duplicate publication and unauthorized requests are rejected. |
| BT-1 migration and rollback | Approval/effect/model migration tests preserve old records and uncertain artifacts, retire incompatible writer tables, refuse unsafe reuse and retain generation-0 quarantine. The BT-2 copied migration never grants new execution authority. |
| BT-1 physical target/lifetime | `test_outward_target_replacement.py` and `test_outward_bound_filesystem.py` prove before/after-intent target binding, actual handle exclusion/descriptor isolation, one/repeated cancellation and deadline-drain behavior on both recorded hosts. |
| BT-2 change 1: read-only retained checks | `test_outward_ledger_integrity.py`, snapshot and commitment tests reject mutated payload/hash/order and deleted middle/tail evidence; repeat verification leaves logical contents unchanged. Missing/legacy storage is not silently initialized or sealed. |
| BT-2 change 2: atomic versioned append | Append/head failure injection, caller-payload mutation and native writer-guard tests prove captured event bytes, sequence, chain and head publish together. V1 hashes/order remain a derived projection. |
| BT-2 change 3: independent snapshot completeness | Real 0/4,999/5,000/5,001-event cases, page barriers with a concurrent WAL writer and independent counts/head pass. Actual 100,000-event/64 MiB bounds accept exactly the limit and reject overflow. |
| BT-2 change 4: filtered/PII audit | Native API tests prove serialized audit identity and authenticated actor. `tests/interfaces/test_northstar_phase4_ledger_api.py` and `tests/kernel/v1/test_outbound_policy_gate.py` remain green in the canonical suite; filtered/redacted exports retain omission anchors. |
| BT-2 change 5: distinct integrity/authenticity claims | Offline CLI reports only file self-consistency. Local rewrite can pass local checks but fails an independently retained prefix anchor; valid later appends retain the prefix. No signing or historical authenticity is claimed. |
| BT-2 migration | Copied-store tests retain original v1 exports/cells, validate every available hash, require explicit unsealed disposition, refuse corrupt/partial native state and bind the SQLite backup digest including committed WAL data. Killing the real backfill worker rolls back all candidate commitments; restart requires new paths and preserves every copy. |

Final source verification: `python -m pytest -q --tb=short` passed **4,827 tests,
74 skipped, 2 warnings in 663.56s**. The two warnings remain the deprecated domain
import and fixture low-generation cap. Runtime/test code stayed frozen during the
run. Scoped Ruff, dependency direction and docs hygiene pass. The refreshed
baseline stays `collection_ok=true`, `release_ready=false`, with 126 pre-existing
runtime Ruff findings and 3,491 missing legacy test labels across 4,389 functions.
That debt remains with the later quality/architecture slices.

Live installed proof uses the repaired Windows Python 3.11 wheel and the existing
operator-owned llama.cpp server, model
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`, without provider fallback. The approved
application proof reports path `primary`, result `success`, accepted witness,
artifact and corruption checks, and no missing evidence. Independent SQLite reads
find one published effect, ten events and ten commitments; head
`d0bd36a43ee2e506edf8e81dc0cbd358ebeae964f63e64ac8578cbfbaee19601`.
The output is `outward proof live content`, SHA-256
`84db311bf4865a2acfd8b31b7cf2c522e994830cd2567f706f30f391c17f77bd`.
The invocation retains 386 prompt tokens, 28 completion tokens, 983ms and
`tool_call_extracted`, artifact SHA-256
`a168cd4dac0bd9eba9b8258a4bc4a442848ca204824f630c03e7c2dcb22ed542`.
Reports/package/raw data remain in the Windows harness at
`wheel-results/live-provider/` and `.tmp/outward-write-file-approved-proof/`.

A separate installed-wheel Uvicorn listener on an ephemeral localhost TCP port
passes real authenticated HTTP submission, live model proposal generation,
unauthorized approval rejection (403 with no file), authorized approval, retained
verification/external-prefix comparison and stale approval retry. Independent
SQLite inspection finds one published effect and one tool event. The retained
head is `0be6c7628090f950b91e7c13106556d081522d2a37c0dca8f0c95b20aad12f9e`;
the output digest matches the approved application proof. The listener exits 0,
with its API context closed and zero background tasks. Evidence remains under
`wheel-results/live-http-bootstrap-fixed/`. The first harness attempt constructed
the app inside an already-running event loop and was correctly refused by the
existing bootstrap guard; the corrected harness follows the canonical synchronous
app-construction order. Its original empty startup directory is retained. This
was a harness correction, not a change to the runtime startup contract.

All routine proof set `ORKET_DISABLE_SANDBOX=1`; no Docker sandbox resource was
created, and the existing provider server remains operator-owned. Local fixture
models/time in adversarial tests are explicitly distinct from the two live
provider flows. Acceptance does not imply remote idempotency, untested platform
support, generic objective completion, subprocess-descendant containment or
measured connector timing. Those remaining claims belong to BT-3/BT-4/BT-5 and
the later capability/architecture gates. No phase-scoped execution document was
created outside this active umbrella; durable contract deltas/specs remain active.

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

### BT-3 replay checkpoint: 2026-09-12

The replay portion passes scoped SD-02 acceptance; SR-07 card completion and the
whole BT-3 gate remain open. Eleven September findings remain.
No capability, packaging release, production-store upgrade or historical
authenticity claim is admitted.

Changes:

- `governed_agent_replay.v2` uses a core replay-evidence port, one read-only SQLite
  transaction, and the independent control-plane step inventory. Expected,
  retained, compared and matched counts expose a missing first/middle/tail row
  instead of treating surviving matches as a complete history.
- The application validates source identity, request/result/decision/input
  digests, typed continuation inputs, and step references before running the
  existing pure continuation decision. It never invokes the provider, child,
  tools, effect executor or terminal publisher during replay.
- New decision publication retains an input digest atomically. Serialized normal
  initialization adds a nullable column to existing stores without sealing old
  evidence. Replay never creates a database or initializes its schema.
- Missing/unreadable/resource-limited evidence cannot report matched. Actual
  10,000-row and 64 MiB limits are exercised. Completeness is relative to retained
  step records in that snapshot; coordinated privileged rewriting of the whole
  database remains outside this evidence. External effects, objective satisfaction
  and full execution are not verified by a replay match.

Verification (observed path `primary`, result `success` for completed checks):

- Initial expanded integration envelope: **47 passed in 37.55s**, including
  repository publication, real child invocation, API/CLI and existing controls.
- Expanded corruption/API/legacy/concurrent-read checks plus run-control
  regression: **26 passed in 9.18s**. The first multi-row fixture attempt failed
  because nested SDK identities still referenced iteration one; the fixture was
  corrected before acceptance. Runtime validation was retained.
- Windows Python 3.11.14 source envelope: **35 passed in 17.23s**. Linux Ubuntu
  24.04/Python 3.11.16 source envelope: **35 passed in 22.76s**. Both used existing
  isolated environments with current worktree runtime source, and reported two
  existing Starlette/AnyIO dependency deprecations. These are not new installed
  wheel results. The actual resource-limit cases subsequently passed on Windows
  Python 3.13.11: **2 passed in 1.83s**.
- Live llama.cpp API/supervisor/memory/replay flow: **1 passed in 15.83s** using
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l` at localhost port 8080. Two real child
  iterations reached persisted completed state with six measured model receipts.
  API transport was in-process HTTP through TestClient; provider inference was
  live. Owned application background tasks returned to zero. No sandbox resources
  were requested; the existing operator-owned provider was left running.
- Independent read of retained live evidence matched expected/compared count two
  and preserved the complete logical database dump. Logical SHA-256:
  `16cc8bb8531d5171a76279e3510a2a5dcb94a2f4d5f0f45bee16d6fae4e86cfa`.
  Stable report: `.tmp/bt3-replay-proof/report.json` (shared diff ledger).
  Raw store: `.tmp/bt3-replay-live-proof/test_live_llama_cpp_api_wake_m0/agent.sqlite3`;
  JUnit: `.tmp/bt3-replay-live-junit.xml`.
- Canonical suite: **4,853 passed, 74 skipped, 2 warnings in 654.76s**. JUnit:
  `.tmp/bt3-replay-full-suite.xml`. This run preceded the final missing-table count,
  human CLI diagnostic and child import-hook refinements. Those refinements and
  their new tests passed the final installed-wheel envelope below. Existing
  warnings are the deprecated domain namespace and low fixture generation cap.
- Scoped Ruff, dependency direction with legacy enforcement `fail`, project docs
  hygiene and whitespace checks pass. All six original sealed fixture digests
  still match. No original history was resealed.
- Final baseline collection succeeds and reports `release_ready=false`: 126
  existing runtime Ruff findings and 3,488 missing legacy test labels across
  4,402 test functions. New/modified replay tests carry individual integration
  labels. The 75 new Python files satisfy the size checks. The original `main`
  checkout is clean; the worktree has 161 changed paths and an empty index.

Final installed replay/import acceptance:

The final 39-case source envelope passed on Windows 3.11/3.12 and Linux 3.11.
Linux Python 3.12 instead had **5 failed, 34 passed in 21.21s**: real children
disconnected with `RecursionError` while the import hook constructed a `Path`
to inspect its caller. On POSIX Python 3.12, that constructor imports `ntpath`
and recursively calls the same hook. The failure is retained in
`.tmp/bt3-replay-linux312.xml`; diagnostic driver `.tmp/bt3_child_trace.py` traced
the original installed child. Source-envelope parents imported worktree code;
sanitized child processes imported the previously installed wheel, whose hook
matched the unchanged source at the time. This failure was not replay success
or an environment exemption.

`sdk_workload_subprocess.py` now uses thread-local state only during its own
origin inspection, resetting it before extension loading. A real-process
regression retains undeclared stdlib and host-module denial, including another
thread while the inspecting thread is active. No allowlist or containment claim
was expanded.

A fresh core wheel was built with `pip wheel . --no-deps` under Windows Python
3.12.2: `.tmp/bt3-replay-wheels/orket-0.6.2-py3-none-any.whl`, SHA-256
`74ecb0e93b22e5dd25442744dfc5278cae5b4c7b7f0ab49d19d4f4fd53ed93de`.
The existing isolated four-cell environments were explicitly updated to this
wheel. The previous BT-1/BT-2 wheels and reports remain retained; global Python
installations were not replaced. `pip check` passes in all four environments.

The **44-case** installed envelope includes replay/CLI/real child composition,
the new origin-inspection regression, and existing host-module/dynamic stdlib
denial checks. It passes from foreign working directories containing 1,518
Git-visible tests/scripts/template/config files and no core or SDK runtime source:

| Installed host | Result | Duration | Loaded core/SDK modules outside site-packages |
|---|---|---|---|
| Windows Python 3.11.14 | 44 passed | 22.17s | 0 of 791 |
| Windows Python 3.12.2 | 44 passed | 24.50s | 0 of 791 |
| Ubuntu 24.04 Python 3.11.16 | 44 passed | 20.04s | 0 of 791 |
| Ubuntu 24.04 Python 3.12.3 | 44 passed | 20.10s | 0 of 791 |

All cells report the wheel digest above and the same two Starlette/AnyIO
dependency deprecations. These are 44 distinct cases repeated on four hosts,
not 176 distinct cases. Harness inventory:
`.tmp/bt3-replay-proof/harness-manifest.json`. Windows harness:
`C:/Users/jonmc/AppData/Local/Temp/orket-bt3-wheel-harness-8hm5_uma`; Linux harness:
`/home/jon/.cache/orket-architectural-truth/bt3-wheel-harness`. Each harness retains
`results/<cell>/report.json` with a shared diff ledger, runtime origins, selected
tests and wheel provenance, plus `junit.xml` and test databases. The harness-copy
process was awaited after an early Linux invocation found no driver yet; that
setup attempt ran no tests.

The repaired installed Windows Python 3.12 wheel also passed the live llama.cpp
API/supervisor/memory/replay test: **1 passed in 15.98s**. Six measured model
receipts and two persisted iterations reached completed state; replay compared
both without changing the logical database. Logical SHA-256:
`3f955dd5051dd1154ad2e555f77bc6df0cdf19211be5237576647fbab8c762d7`.
Report/raw evidence: Windows harness `results/live-provider/report.json` and
`results/live-provider/pytest-temp-ready/test_live_llama_cpp_api_wake_m0/agent.sqlite3`.
The initial live harness fixture failed before execution because its parent
temporary directory was missing; its JUnit remains `junit-setup-error.xml`.
The corrected run used the exact model/provider above, in-process HTTP transport,
real child processes, and confirmed zero owned background tasks at shutdown.

Architecture audit: AC-01 through AC-06 pass for new replay code: application
composition owns the adapter, the adapter imports the core port/data contract,
and replay receives explicit recorded inputs with no new clock/random source or
side effects. Existing adapter/application dependencies on decision publication
remain deferred to the named dependency slice. AC-07/AC-09 pass for scoped
continuation comparison and remain partial for card completion and whole-run
truth. AC-08 changes no event type; the public response is explicitly V2.
AC-10 is reflected in the governed-agent spec, current authority, runbook and
`CONTRACT_DELTA_GOVERNED_AGENT_REPLAY_BT3_2026-09-12.md`.

Not verified: whole BT-3 card completion, hostile whole-store rewrite detection,
independent objective/effect verification through replay, and the remaining
plan slices. No environment blocker is
inferred for unattempted work. The completion trace still includes Boolean
reduction in `orchestrator_prompt_preparation_service.py`, synthesized done in
`turn_executor_runtime.py`, and separate final card/control-plane persistence.
Continue with composed persistence counterexamples and the typed evidence
contract before changing those gates.

### BT-3 card acceptance contract checkpoint: 2026-09-12

SR-07 and BT-3 remain open. This checkpoint reproduces the persistence defect and
adds the shared acceptance contract; it does not yet wire runtime enforcement.

The composed counterexample uses the real `RuntimeVerifier`, `TurnExecutor`,
`ToolDispatcher`, `ToolBox`, card tools and SQLite repository. The model is an
explicit deterministic completion-request fixture. It does not stand in for the
verifier, tool result or storage write. All six cases persisted `done`:

| Workspace/check | Verifier observation | Synthesized request | Explicit request |
| --- | --- | --- | --- |
| Empty workspace | `ok=true`, `not_evaluated` | Unsupported `done` persisted | Unsupported `done` persisted |
| Wrong-output Python, syntax checks only | `ok=true`, `syntax_only` | Unsupported `done` persisted | Unsupported `done` persisted |
| Wrong-output Python, exit zero | `ok=true`, `command_execution` | Unsupported `done` persisted | Unsupported `done` persisted |

Observed path: `primary`. Observed result: `failure` of the acceptance boundary.
This is integration evidence through actual child commands and SQLite, with a
deterministic model fixture; it is not provider-backed live acceptance. The local
driver is `.tmp/bt3_card_completion_counterexample.py`, run with
`ORKET_DISABLE_SANDBOX=1` and the worktree on `PYTHONPATH`. Stable report:
`.tmp/bt3-card-counterexample/report.json` (shared diff ledger); initial report
SHA-256 `16b21be4c2849b75dc6f8e7b62ba092e47b32cce477a86e0736ba5a1dfc0258c`.
The six case directories retain their actual databases and turn artifacts.

Implemented foundation:

- `card_completion.py` core contracts bind declared criteria to policy and
  verifier digests, workload, card/run/attempt, inputs, artifact manifest and
  retained evidence identities. Inputs are immutable, versioned and reject
  unknown fields. Empty or ambiguous acceptance cannot be admitted by these types.
- The core policy compares every expected criterion. Classes do not imply a
  coverage ranking. Missing inventory, stale or substituted bindings, duplicate
  or contradictory observations, aliased evidence references, inadmissible model
  self-report and failed accepted checks cannot produce sufficient acceptance.
- `card_completion_decision.v1` reports missing criteria and diagnostics with the
  exact scope and acceptance references. It is not a storage permission. The
  application still must validate retained evidence and enforce final persistence.
- Durable authority is `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`, with
  the same-change BT-3 contract delta and explicit packet-1 projection boundary.

Verification: **30 contract cases passed in 0.15s** on Windows/Python 3.13.11;
JUnit `.tmp/bt3-card-contract.xml`. This is structural proof of the pure contract,
not a repaired completion flow. Scoped Ruff, dependency direction with
`--legacy-edge-enforcement fail`, docs project hygiene and `git diff --check`
passed. New files remain within size limits. The repository baseline remains
release-red: `collection_ok=true`, `release_ready=false`, 126 runtime Ruff issues,
3,488 missing legacy layer labels and 4,410 test functions. All eight new test
functions are labeled; their parameterizations account for the 30 contract cases.
The six sealed fixture digests remain unchanged. The original `main` worktree is
clean, and this worktree has no staged changes. Earlier installed replay/outward and live provider proof retains
its original scope and wheel identity.

Architecture checklist: AC-01/02/03/04 pass for the new deterministic core-only
inputs and comparison. AC-05/06 add no new side effects or adapter callers.
AC-07 is still failed on the unchanged composed card path, as reproduced above.
AC-08 adds no runtime event schema. AC-09 remains partial until the application
retains and verifies the completion evidence. AC-10 is recorded in the durable
contract, delta, current authority and this plan. These open items remain owned
by Orket Core under BT-3; the contract tests do not close them.

Not verified: accepted verifier admission, evidence collection/authenticity and
retention, prompt/context propagation, synthesized/explicit/application/final
storage gates, stale evidence after a write, bypass and concurrency cases, and a
sufficient provider-backed card run. No environment blocker is inferred for
these unimplemented paths. Eleven September findings still remain.

Exact files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CARD_COMPLETION_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
- `orket/core/contracts/card_completion.py`
- `orket/core/policies/card_completion.py`
- `tests/core/test_card_completion.py`

Next at that checkpoint: implement application-owned admission and retained evidence against this
contract, then enforce it through all completion paths and final storage. Extend
the composed proof with failed, stale/cross-run, post-verification mutation and
sufficient accepted behavior. Keep the no-plan, empty and wrong-output cases as
negative acceptance obligations; do not promote their current outcomes to green.

### BT-3 card acceptance service checkpoint: 2026-09-12

The declared acceptance contract now has a real application verification and
retained-evidence path. SR-07 remains open because card orchestration, tool calls
and final card writes do not yet enforce that path. No new public workload,
production migration or whole-BT-3 acceptance is claimed.

Changes:

- `CardAcceptanceService` executes explicitly declared Python CLI JSON cases
  against fresh copies of captured artifact bytes, with a sanitized child
  environment. It preserves argument boundaries, checks exact normalized JSON
  results and refuses a changed verification snapshot. Absent definitions and
  missing artifacts cannot produce sufficient acceptance.
- Retained packages bind policy/verifier definitions, all declared cases,
  workload inputs, interpreter/environment, artifact bytes, command receipts and
  card/run/attempt scope. The content-addressed SQLite store has immutable-row
  triggers and a bounded read-only inspection path. Inspection revalidates the
  package and all criteria instead of trusting saved success flags.
- Actual limits are exercised: 1 MiB per artifact, 8 MiB aggregate snapshot and
  32 MiB evidence bodies. Missing stores remain absent during inspection.
  Repeated cancellation stops the next case, drains a normally exiting current
  child, removes its temporary snapshot and propagates cancellation. This does
  not close BT-4 descendant termination or raw-stream memory-bound requirements.
- The shared `RuntimeVerifier` no longer lets clipped stdout hide an invalid
  suffix, or replacement decoding turn invalid UTF-8 into accepted JSON. Receipts
  expose raw byte counts/digests, encoding validity and truncation. JSON checks
  fail closed on lossy/unverified capture while retaining the actual process
  exit code. Exact argv is retained; empty/whitespace arguments are preserved.
  The existing oversized verifier file shrank by eight lines.

Verification (observed path `primary`, result `success` for repaired/service
checks; proof is real subprocess/filesystem/SQLite integration plus pure contract
checks, without provider inference or final card transitions):

- The opening output-integrity run had four failures: two reproduced false
  acceptance, one exposed inaccurate oversized-output classification, and one
  showed missing capture metadata. Before/after JUnit files are
  `.tmp/bt3-verifier-output-before.xml` and `.tmp/bt3-verifier-output-after.xml`.
  The initial shared-verifier/artifact envelope then passed **31 cases in 3.27s**.
- The first service envelope had **2 failed, 46 passed** because fixture assertions
  assumed LF bytes after Windows text writes. Fixtures now write exact bytes and
  explicitly cover both LF and CRLF; runtime byte capture was preserved.
- Final scoped source envelope: **81 passed in 5.56s** on Windows/Python 3.13.11,
  **81 passed in 5.36s** on Windows/Python 3.11.14, and **81 passed in 6.29s** on
  Ubuntu 24.04/Python 3.12.3. These are source runs using the worktree, not new
  installed-wheel acceptance. JUnit:
  `.tmp/bt3-card-acceptance-service-final.xml`,
  `.tmp/bt3-card-acceptance-win311.xml`, and
  `.tmp/bt3-card-acceptance-linux312.xml`.
- Retained service proof executes two increment cases, rejects wrong behavior,
  and rejects reusing the earlier evidence after artifact mutation. Stable report:
  `.tmp/bt3-card-acceptance-proof/report.json` (shared diff ledger); database:
  `.tmp/bt3-card-acceptance-proof/evidence.sqlite3`. Read inspection preserves the
  logical SQLite digest
  `d7ea747c25644a43c2c10e85370828ee18773db1c28cf109e79848d818e973d5`.
  Sufficient evidence reference:
  `41961ad6ab7a6e9925426d1fd570792e070c959549fd034ca68466fa625346b2`;
  wrong-behavior reference:
  `7128f437a2c2cd45e94c13de43f26df455a7773c66d65b680c9402e5e82b0cb0`.
- Scoped Ruff, dependency direction with `--legacy-edge-enforcement fail`, and
  docs project hygiene pass. New files/functions remain within size limits.
- The canonical full suite passes on the final code: **4,910 passed, 74 skipped,
  two existing warnings in 646.71s**. JUnit:
  `.tmp/bt3-card-service-full-suite.xml`. This is regression proof with the suite's
  mixed layers, not live acceptance of every runtime path.
- Refreshed baseline: `collection_ok=true`, `release_ready=false`, 125 runtime
  Ruff issues, 3,488 missing legacy layer labels, and 4,425 test functions. All 15
  new integration test functions have layer labels. The candidate has 176 changed
  paths and 86 new Python files, all within the new-file size limit.

Architecture checklist: AC-01/02/03/04 pass for the touched dependency/input
boundaries. AC-05/06 pass for the new application-owned service and explicitly
side-effecting adapters. AC-07 remains failed at final card completion; service
evidence does not authorize a card write. AC-08 adds receipt fields and failure
classifications under the same existing event names. AC-09 passes for this
retained service snapshot and remains partial for card completion. AC-10 is
recorded in the acceptance contract, delta, packet-1 boundary and current authority.

Not verified: public card admission/context propagation, explicit/synthesized
completion, direct application/save/update bypasses, current-attempt fencing and
the final persistence race, provider-backed card completion, and installed-wheel
acceptance of this service. The inspector requires the caller's current scope;
the eventual card gate must refresh and enforce that scope. Privileged coordinated
host/store rewriting and hostile-code containment are not proved. Eleven
September findings remain open; no environment blocker is inferred for the
unimplemented card gates.

Exact files touched by this service checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CARD_COMPLETION_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
- `orket/adapters/storage/card_acceptance_artifacts.py`
- `orket/adapters/storage/card_acceptance_evidence_store.py`
- `orket/application/services/card_acceptance_evaluation.py`
- `orket/application/services/card_acceptance_service.py`
- `orket/application/services/runtime_verifier.py`
- `orket/application/services/runtime_verifier_capture.py`
- `orket/core/contracts/card_acceptance_inputs.py`
- `tests/integration/test_card_acceptance_service.py`
- `tests/integration/test_runtime_verifier_output_integrity.py`

Next: wire the service into card admission/review and propagate typed acceptance
references. Enforce the shared gate at explicit and synthesized status requests,
application transitions and final card storage, including cached completion paths.
Use fresh composed runs when checking the original six counterexamples; an old
turn/artifact cache must not masquerade as proof that a persistence bypass closed.

### BT-3 card persistence checkpoint: 2026-09-12

Configured final card storage now enforces evidence acceptance and has composed
turn proof. SR-07 and whole BT-3 remain open. Standard runtime configuration and
application completion outcomes are not wired yet; default repositories reject
new successful completion. No production database, release, tag or push changed.

Changes:

- Core context/request/receipt contracts bind card/run/attempt, generation,
  workspace, acceptance definition and card inputs. Attempt admission uses
  compare-and-swap. Status/input changes invalidate the active binding.
- Application final review recaptures artifact/interpreter/environment scope
  through the same capture implementation as verification, then re-inspects
  retained acceptance. A configured application authority is required inside
  the SQLite writer transaction. Receipt, status and history commit together;
  identical admitted retries retain one receipt/history row.
- Card schema v2 adds generation/context/reference columns and immutable receipts
  with conservative direct-SQL backstops. Saves reject new terminal success and
  terminal input changes. Legacy terminal rows keep history without invented
  acceptance; support annotations preserve original input bytes. Ordinary saves
  no longer replace the row or erase unrelated columns.
- Explicit tools forward typed evidence requests from application context and
  expose available diagnostics. Synthesized success requires a typed sufficient
  decision, then final evidence review. `runtime_verifier_ok` is not authority.
  Normal tool-result caches cannot replace successful completion review.
- ToolBox file writes/directory creation share the card writer guard. Repeated
  cancellation drains the owned write before releasing it. Other workspace
  writers and completed-turn replay remain unintegrated.

Verification (path `primary`; result `success` for the bounded proof and
`partial success` for the unfinished BT-3 task):

- Initial storage/service run: **2 failed, 67 passed, 2 skipped**. Direct-`done`
  setup fixtures now complete through real Python checks and SQLite. Retry-column
  tests construct the actual legacy schema before v2, avoiding trigger-blocked
  drop-column skips. The storage/service/component envelope then passed **98 in
  6.98s**. A separate migration fixture omitted the old required type/priority;
  the fixture was corrected without adding runtime defaults.
- Final-write tests cover absent/empty/syntax-only/wrong/failed checks, all public
  save/status bypasses, stale artifacts/inputs/policy/run/attempt, bulk reset and
  archive, independent repository races, missing evidence, rollback, cancellation,
  legacy preservation and direct-SQL backstops. File-tool tests prove waiting and
  cancellation drain against the real writer lock.
- Fresh composed turns exercise verifier, dispatcher, ToolBox and SQLite for six
  evidence states with explicit and synthesized completion. Only the admitted
  passing behavior persists `done`. Reopening with wrong output and the same
  turn/tool cache identifiers rejects resumed success. Gate/middleware envelope:
  **92 passed in 8.82s**, `.tmp/bt3-card-gates-current.xml`.
- Final review restored existing audit behavior for repeated nonterminal status
  updates while preserving the active completion context/generation. A real
  SQLite/acceptance regression covers that parity; identical successful
  completion remains idempotent.
- The final **98-case** contract/integration source envelope passes on Windows
  Python 3.13.11 (**10.65s**), Windows Python 3.11.14 (**15.34s**) and Ubuntu 24.04
  Python 3.12.3 (**10.27s**). JUnit: `.tmp/bt3-card-persistence-win313.xml`,
  `.tmp/bt3-card-persistence-win311.xml`, `.tmp/bt3-card-persistence-linux312.xml`.
  These runs use real files, processes, tools and SQLite with deterministic model
  fixtures; they are not new installed-wheel or provider-inference acceptance.
- Retained composed proof: `.tmp/bt3-card-persistence-proof/report.json`, shared
  diff ledger, **12 passing cases** and retained card/evidence databases. Driver:
  `.tmp/bt3_card_persistence_proof.py`, with fresh dispatch identities on reruns.
  Its first run exposed invalid Windows filename characters in harness session
  IDs; portable IDs and rejection of unrelated unexpected errors corrected the
  harness. That failure is not negative acceptance. Sufficient receipt references:
  `8f62e9b5c63300b22685f668b758255bfa527a4392914b23559c1feb6e58dbe1`
  (synthesized) and
  `23fd3a565b159cebac5fe942c558b604380e8af8dac6fca27d5cce0f18a50d20`
  (explicit).
- The canonical full suite finishes **20 failed, 4,933 passed, 74 skipped**, two
  existing warnings, **647.12s**. JUnit:
  `.tmp/bt3-card-persistence-full-suite.xml`. Eighteen failures expose missing
  configured completion authority in existing runtime or fixture transitions;
  one card-type test expects unsupported successful completion; one session
  resumption fixture seeds `done` through `save`. These remain required runtime
  and test updates, not an environment blocker or green regression proof.
  That full run precedes the localized nonterminal-history parity fix and its
  added test. The final 98-case matrix and retained 12-case proof pass after the
  fix; the full suite has not been rerun after it. No full-suite pass is claimed.
- Scoped Ruff, docs project hygiene, `git diff --check`, and dependency direction
  with `--legacy-edge-enforcement fail` pass. The main checkout remains clean,
  the index empty, all original plan headings retained, and all six sealed
  fixture hashes unchanged. Refreshed
  baseline: `collection_ok=true`, `release_ready=false`, 124 runtime Ruff issues,
  3,484 missing legacy layer labels and 4,442 test functions. New/modified tests
  have layer labels. All 97 new Python files and their functions fit size limits.
  The touched oversized middleware test shrinks by two lines; the protocol module
  retains its original 448 lines.

Architecture checklist: AC-01/02/03/04 pass for explicit contracts/application
inputs; AC-05 passes for injected final review and owned file writes. AC-06 is
pass for the touched persistence/tool adapters after explicit classification;
other adapter debt remains under C/D. AC-07/09 pass for the exercised final
transaction but remain partial for runtime outcomes, completed replay and other
writers. AC-08 retains event names and adds versioned receipts/structured tool
failures. AC-10 is recorded in the contract, delta, packet-1 boundary and current
authority. Orket Core owns remaining integration under this active BT-3 plan.

Not verified: standard runtime factory/admission/review/context propagation,
completed-turn replay, final application outcomes, every workspace writer,
provider-backed completion and rebuilt installed wheels. Snapshot proof does not
establish hostile-code OS containment or protection against privileged coordinated
host/store rewrites. Full-suite failures remain required triage. Eleven findings
remain open; no external environment blocker is inferred for unfinished code.

Exact files touched by this persistence checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CARD_COMPLETION_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
- `orket/adapters/storage/async_card_repository.py`
- `orket/adapters/storage/card_completion_migrations.py`
- `orket/adapters/storage/card_migrations.py`
- `orket/adapters/storage/card_record_codec.py`
- `orket/adapters/storage/card_write_ops.py`
- `orket/adapters/tools/families/cards.py`
- `orket/adapters/tools/families/filesystem.py`
- `orket/application/services/card_acceptance_service.py`
- `orket/application/services/card_completion_service.py`
- `orket/application/services/card_workspace_mutation_service.py`
- `orket/application/workflows/turn_executor_runtime.py`
- `orket/application/workflows/turn_tool_dispatcher_protocol.py`
- `orket/core/contracts/card_completion_commit.py`
- `orket/core/contracts/repositories.py`
- `orket/core/domain/records.py`
- `orket/tools.py`
- `tests/adapters/test_async_card_repository.py`
- `tests/application/test_turn_executor_middleware.py`
- `tests/helpers/card_completion.py`
- `tests/integration/test_card_completion_persistence.py`
- `tests/integration/test_card_completion_transactions.py`
- `tests/integration/test_card_completion_turn.py`
- `tests/integration/test_card_completion_workspace_guard.py`

Next: finish standard runtime composition/context and final outcomes, completed
replay and all writers; resolve regressions and run installed/llama.cpp acceptance
before closing SR-07/BT-3. Preserve accepted replay/outward proof and every later
required slice.


### BT-3 standard runtime and completion publication checkpoint: 2026-09-12

This checkpoint supersedes the preceding persistence checkpoint's unwired-runtime
and completed-replay status. Standard composition and bounded live completion now
work; SR-07 and whole BT-3 remain open. Work stays in the requested worktree,
with no production migration, commit, tag, push or release.

Changes:

- The runtime context composes one application completion service and binds it to
  its default card repository. Evidence defaults to
  `<runtime-db-filename>.card_acceptance.sqlite3` beside the card DB. Caller-injected
  repositories retain their explicit configuration and fail closed when unconfigured.
- Turn preparation binds actual dispatch run/attempt identities and evaluates the
  declared plan. Explicit successful status tools refresh their request; final
  storage still independently reviews current inputs/artifacts. Disabling the
  legacy verifier does not disable declared acceptance.
- Successful tool results include the committed receipt digest. Read-only card
  inspection validates current status, generation, input/context binding and
  retained acceptance; it does not initialize missing stores or rerun commands.
  Reopened cards, stale attempts, substituted references and missing evidence
  reject completion claims. Historical snapshot inspection does not recapture
  the workspace or promise that accepted files stay unchanged forever.
- The dispatcher now validates receipt claims before final success publication.
  Status-only successful writes enter that publication path. Completed turn reentry
  validates the receipt without model/tool redispatch or durable store changes.
  Orchestrator post-turn handling also checks receipts before processing success.
  Remaining scheduler, legacy-terminal and wider outcome consumers still need audit.
- Builtin vision, academy and Reforger writers now share the card writer guard,
  selected by actual callable even through a strategy alias. Timeout/cancellation
  retains ownership until synchronous worker threads drain. Custom writer paths
  and hostile external mutation are outside this bounded proof.
- Live inference exposed compact prompts dropping acceptance, available tool names
  and per-call JSON shape. Compaction now preserves those fields and no longer
  derives a completion instruction from the legacy verifier boolean.

Verification (observed path `primary`; result `success` for bounded flows and
`partial success` for the unfinished BT-3 task):

- Standard engine/provider-adapter/tool/SQLite integration passes an admitted
  program and rejects missing plans or wrong behavior with the legacy verifier
  disabled. The HTTP response fixture is deterministic; these tests are not live
  provider proof. Receipt inspection and existing control-plane regressions passed
  31 cases; the initial writer/runtime envelope passed 22.
- New real-store publication/reentry tests cover protocol and non-protocol
  status-only completion, reopen before publication, retained replay, new attempt,
  wrong scope, missing evidence and no durable changes during reentry. Real sync
  writer tests cover timeout, repeated cancellation and cancellation during timeout
  drain. Rendering tests cover compact and uncompressed acceptance prompts.
- The first source matrix passed 125 cases on Windows 3.13 and Linux 3.12, but
  Windows 3.11 exposed repeated cancellation escaping `asyncio.wait_for` while its
  guarded writer continued. The caller now explicitly owns and drains the
  application task. The final **126-case** source envelope passes on Windows
  Python 3.13.11 (**28.05s**), Windows Python 3.11.14 (**27.26s**) and Ubuntu 24.04
  Python 3.12.3 (**31.61s**). JUnit files:
  `.tmp/bt3-runtime-composition-win313.xml`,
  `.tmp/bt3-runtime-composition-win311.xml`,
  `.tmp/bt3-runtime-composition-linux312.xml`. These are source runs, not rebuilt
  installed-wheel acceptance. An additional message-builder/publication envelope
  passed 39 cases before the final drain repair and three added cases.
- Live standard `OrchestrationEngine.run_card` proof passes against the existing
  operator-owned llama.cpp server at `http://127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`. Two actual inference receipts lead
  through real file tools, declared CLI checks and SQLite to a readable completion
  receipt. `ORKET_DISABLE_SANDBOX=1`; the engine closes and the operator server
  remains running. Stable report: `.tmp/bt3-standard-runtime-live/report.json`,
  shared diff ledger; driver `.tmp/bt3_standard_runtime_live.py`. Final session:
  `card-live-0a13ae4bf32f447aaedd75ef0e2725bb`; completion receipt `67aba4a9b251aba6d400bb04335f43e6cc83a1147f75f518d18e78355a00a37f`.
  The opening harness failed before inference by bootstrapping inside an event
  loop; it now bootstraps before that loop. Two retained inference failures exposed
  the compact-prompt defect before repair. They are failures, not negative acceptance.
- Canonical full-suite observation: **34 failed, 4,944 passed, 74 skipped**, two
  warnings, **7,176.40s**; `.tmp/bt3-runtime-composition-full-suite.xml`. Nineteen
  remaining cases require declared completion in runtime/fixture transitions,
  a card-type expectation or terminal-save setup. Fifteen failures use incomplete
  `SimpleNamespace` turn doubles without `tool_calls` in
  `test_orchestrator_epic.py` and `test_odr_prebuild_continuation.py`. Do not add a
  production fallback that treats malformed turns as verified success. This run
  started before the final prompt/drain changes and three added cases; the final
  targeted matrix passes after those changes, but no final full-suite pass is claimed.
- Scoped Ruff, docs project hygiene, `git diff --check` and dependency direction
  (`--legacy-edge-enforcement fail`) pass.
  Baseline collection succeeds with `release_ready=false`: 122 runtime Ruff issues,
  3,483 missing legacy layer labels, 4,450 test functions. All 101 new Python files
  and their functions meet size limits. Touched oversized orchestration/dispatch
  files shrink; compact packet and message builder do not grow. Original main is
  clean, the worktree index is empty and the six sealed fixture digests are unchanged.

Architecture checklist: AC-01/02/03/04 pass for the changed explicit contracts and
application inputs; composition retains the legacy runtime-context import boundary
without reflection or a new decision-node side effect. AC-05/06 pass for the owned
builtin writers and classified runtime adapter. AC-07/09 pass for exercised
publication/reentry, and remain partial for wider outcome/custom-writer paths.
AC-08 preserves event names and adds the receipt reference to successful tool
results. AC-10 is recorded in current authority, durable paths, acceptance/packet-1
contracts and the contract delta. Orket Core owns the remaining BT-3 integration.

Not verified: final full-suite green, rebuilt installed wheels, complete application
outcome coverage, arbitrary custom writers, live-provider negative controls,
descendant cancellation and hostile-code/whole-store containment. These remain
required work; no external environment blocker is inferred. All eleven remaining
findings and every later ordered slice stay active.

Exact files touched by this runtime composition checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/architecture/CONTRACT_DELTA_CARD_COMPLETION_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
- `orket/adapters/storage/async_card_repository.py`
- `orket/adapters/storage/card_write_ops.py`
- `orket/adapters/tools/families/cards.py`
- `orket/adapters/tools/runtime.py`
- `orket/application/services/card_completion_composition.py`
- `orket/application/services/card_completion_service.py`
- `orket/application/services/card_completion_turn_service.py`
- `orket/application/services/orchestrator_turn_success_handler.py`
- `orket/application/workflows/orchestrator.py`
- `orket/application/workflows/orchestrator_ops.py`
- `orket/application/workflows/turn_executor_control_plane.py`
- `orket/application/workflows/turn_executor_ops.py`
- `orket/application/workflows/turn_message_builder.py`
- `orket/application/workflows/turn_tool_dispatcher.py`
- `orket/core/contracts/card_completion_commit.py`
- `orket/core/contracts/repositories.py`
- `orket/runtime/config/compact_turn_packet.py`
- `orket/runtime/config/runtime_context.py`
- `orket/runtime/execution/execution_pipeline.py`
- `orket/runtime/execution/pipeline_wiring_service.py`
- `orket/tools.py`
- `tests/adapters/test_model_invocation.py`
- `tests/integration/test_card_completion_control_plane.py`
- `tests/integration/test_card_completion_receipt_inspection.py`
- `tests/integration/test_card_completion_workspace_guard.py`

Next: repair the remaining truthful completion fixtures and outcome consumers,
then prove installed-wheel and full BT-3 acceptance before moving to BT-4 onward.


### BT-3 build outcome and regression repair checkpoint: 2026-09-12

This checkpoint supersedes the preceding checkpoint's whole-build outcome and
remaining-fixture status. SR-07 and whole BT-3 remain open. Work stays in
`C:\Source\Orket-architectural-truth` on `codex/architectural-truth-bt0`;
original main remains clean. No commit, tag, push, release or production database
migration was performed.

Changes:

- Application-owned build inspection holds one writer guard across the complete
  inventory and retained receipt reads. It checks every admitted card is present,
  every observed card has accepted `done`/`guard_approved` state, and each receipt
  matches its captured row. It retains `card_completion_outcome.v1` with receipt
  references and per-card diagnostics in run artifacts.
- Empty, missing, canceled, archived, historical receiptless and evidence-unreadable
  cards cannot authorize session `done`. Nonempty workflow-terminal failures
  receive an explicit completion diagnostic; nonterminal or empty work stays
  incomplete. Existing source-attribution gates still apply.
- The loop emits `orchestrator_epic_stopped`. It ignores strategy-supplied
  completion event names. `orchestrator_epic_complete` follows accepted finalization
  through the control plane and run ledger. The runtime-local card protocol is
  removed in favor of the canonical core repository contract.
- Ten older state/control-plane/API fixtures now obtain real declared acceptance
  before arranging successful cards. Turn and ODR selection/cleanup fixtures use
  actual `ExecutionTurn` values and nonterminal review state, and are labeled unit
  tests. Their prompt assertions account for the application acceptance section.
  They do not manufacture verified objective success.
- Inspection proves a consistent retained snapshot. It does not rerun commands,
  promise permanent workspace currency, or make downstream multi-store publication
  atomic. The guard is released before that publication.

Verification (observed path `primary`; bounded flows `success`, ongoing BT-3 task
`partial success`):

- The **136-case** source completion envelope passes on Windows Python 3.13.11
  (**54.50s**), Windows Python 3.11.14 (**58.40s**) and Ubuntu 24.04 Python 3.12.3
  (**40.58s**). It exercises real CLI checks, files, SQLite, writer coordination,
  receipt inspection, publication/reentry, build outcomes and standard runtime
  composition. Deterministic model responses remain integration proof, not live
  provider proof. JUnit: `.tmp/bt3-build-outcomes-win313.xml`,
  `.tmp/bt3-build-outcomes-win311.xml`, `.tmp/bt3-build-outcomes-linux312.xml`.
- An additional forged strategy completion-event negative control passes on all
  three hosts (**0.80s**, **1.15s**, **4.60s** respectively). Canceled work still emits
  only the loop-stop event and finalizes as failure. JUnit:
  `.tmp/bt3-build-forged-event-win313.xml`,
  `.tmp/bt3-build-forged-event-win311.xml`,
  `.tmp/bt3-build-forged-event-linux312.xml`.
- The broader changed-fixture and outcome regression envelope passes **161 cases
  in 34.19s**: `.tmp/bt3-build-outcome-regressions.xml`. The initial 54-case
  finalizer regression envelope passed before the later event and turn-fixture
  changes. Initial fixture failures (missing reviewer seat and old exact prompt
  expectations) were repaired before the final observations above.
- A fresh standard `OrchestrationEngine.run_card` live flow passes through the
  existing llama.cpp server at `http://127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, to actual file tools, declared CLI
  acceptance, card receipt and ledger session `done`. The ledger outcome references
  the same accepted receipt. Session `card-live-a30075b8c5cd484da7ec15456e494544`;
  receipt `5e98bf2ef21b10e84f2a5db7c8856e31608b77e8c611de486c4d90da6ecdff79`.
  Retained driver `.tmp/bt3_standard_runtime_live.py`; stable report and shared diff
  ledger `.tmp/bt3-standard-runtime-live/report.json`. The engine closes, the operator
  server remains running, and `ORKET_DISABLE_SANDBOX=1` prevents routine sandbox creation.
- Rerunning all **34 prior failing tests** gives **25 passed, 9 failed in 42.85s**:
  `.tmp/bt3-build-original-failures.xml`. The nine failures remain in parallel
  execution (two), empirical verification (one), golden flow/resumption (two),
  system acceptance (three), and the deterministic role pipeline (one). They lack
  declared acceptance for their actual workloads or use a raw successful save.
  Do not replace text, empirical or sum-program acceptance with the increment
  fixture merely to pass. This is a targeted rerun, not a new full-suite result.
  The last full suite remains **34 failed, 4,944 passed, 74 skipped** and predates
  these repairs.
- Scoped Ruff, dependency direction with `--legacy-edge-enforcement fail`, docs
  project hygiene and `git diff --check` pass. Baseline collection succeeds with
  `release_ready=false`: **119** runtime Ruff issues, **3,457** missing legacy layer
  labels, **4,453** test functions. All **103** new Python files/functions meet size
  limits. Touched oversized finalizer, orchestration and API test files shrink.
  The worktree index is empty; all six sealed outward fixture digests are unchanged.

Architecture checklist: AC-01 through AC-06 pass for the changed core port,
application-owned reads and pure loop-policy output. AC-07/08/09 pass for exercised
build snapshot and event boundaries; wider consumers and multi-store publication
remain partial. AC-10 is reflected in current authority, the acceptance contract,
event taxonomy and contract delta. Orket Core owns the remaining BT-3 work.

Not verified / remaining blockers or drift: final full-suite green, the nine
remaining workload regressions, rebuilt installed-card wheels, scheduler dependency
acceptance, wider operator projections, cross-store publication interruption,
custom writers, live-provider negative controls, descendant ownership and hostile
code/store containment. These are required implementation/proof work, not an
inferred external environment blocker. All eleven remaining findings and later
ordered slices remain active.

Exact files touched by this build outcome checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CARD_COMPLETION_BT3_2026-09-12.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/application/services/card_completion_outcome_service.py`
- `orket/application/workflows/orchestrator_ops.py`
- `orket/core/contracts/repositories.py`
- `orket/decision_nodes/builtins.py`
- `orket/runtime/execution/epic_run_finalize.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/epic_run_support.py`
- `orket/runtime/execution/epic_run_types.py`
- `tests/application/test_decision_nodes_planner.py`
- `tests/application/test_execution_pipeline_cards_epic_control_plane.py`
- `tests/application/test_execution_pipeline_run_ledger.py`
- `tests/application/test_odr_prebuild_continuation.py`
- `tests/application/test_orchestrator_epic.py`
- `tests/core/test_card_management_state_machine.py`
- `tests/helpers/card_completion.py`
- `tests/integration/test_card_completion_epic_outcomes.py`
- `tests/interfaces/test_api.py`
- `tests/interfaces/test_api_expansion_gate.py`
- `tests/interfaces/test_api_operator_views.py`
- `tests/runtime/test_epic_run_orchestrator.py`

Next: finish declared acceptance for the remaining real workloads and audit
scheduler/operator outcome consumers, then prove installed-wheel and full BT-3
acceptance before moving to BT-4 onward.


### BT-3 artifact workload and installed-boundary checkpoint: 2026-09-12

This checkpoint supersedes the preceding checkpoint's remaining-workload test
status. SR-07 and whole BT-3 remain open. Work remains in the requested worktree
on `codex/architectural-truth-bt0`; no commit, tag, push, release or production
database migration was performed.

Changes:

- Added explicitly declared `card_artifact_acceptance.v1`, with strict UTF-8
  literal text and selected JSON object-value comparisons. Application verifiers
  compare actual captured bytes, retain `artifact_verification` evidence and
  reconstruct that evidence on inspection. They never execute artifact files.
  Artifact packages use v2 without command receipts; CLI v1 serialization and
  digest identity remain unchanged. Both families enforce the existing final
  current-input/artifact gate and immutable receipt boundary.
- Canonical tiny summation assets now declare stage-specific acceptance: the
  literal requirement, selected design fields, three real CLI sum cases for
  implementation/review, and optional exact source-attribution JSON. These are
  bounded checks, not general requirements/design/program quality or CAP-1 proof.
  Prompts expose criteria from validated persisted attempt inputs.
- Repaired the nine outstanding workload fixtures using their actual files and
  objectives. Parallel work writes independent per-card outputs. Golden-flow
  resumption retains a real completion receipt. The empirical fixture proves
  support-only success cannot authorize undeclared completion. That flow exposed
  a real overwrite: preparation saved stale in-memory verification data after
  the verifier persisted its observations. Preparation now preserves the saved
  result and scenarios. Touched engine fixtures close their engines.
- Added `json_object` to the existing explicit OpenAI-compatible response-format
  override. Request-shape proof covers all three supported tokens. This changes
  neither provider selection nor parsing/acceptance rules. The new runtime module
  is listed in its package's public surface. The protocol-ledger failure fixture
  now expects the actual unverified-completion diagnostic.

Verification (source and retained-storage paths `primary`; overall result
`partial success`; live and installed failures remain explicit):

- The 11 remaining workload tests pass in **43.43s**, including all nine previous
  failures; the authoritative combined matrix below includes all 11. An earlier 11-case
  attempt failed the empirical observation assertion, exposing the overwrite
  above, before the runtime repair.
- The **166-case** source matrix passes on Windows Python 3.13.11 (**95.61s**),
  Windows Python 3.11.14 (**97.51s**) and Ubuntu 24.04 Python 3.12.3 (**96.97s**).
  JUnit: `.tmp/bt3-artifact-workloads-win313.xml`,
  `.tmp/bt3-artifact-workloads-win311.xml`,
  `.tmp/bt3-artifact-workloads-linux312.xml`. These use actual files, SQLite and
  CLI checks with deterministic model fixtures; they are integration proof,
  not live provider proof. One legacy `orket.domain` monkeypatch warning remains.
- An added actual Python-file sentinel check proves artifact verification and
  retained inspection do not execute the file, and rejects artifact evidence in
  a CLI v1 package. The final artifact suite passes **17 cases in 1.25s**:
  `.tmp/bt3-artifact-extra-negatives.xml`. Provider request-shape tests pass
  **33 cases in 0.50s**: `.tmp/bt3-json-object-provider.xml` (structural HTTP
  transport fixtures). Protocol-ledger/public-surface checks pass **9 cases in
  2.77s**: `.tmp/bt3-artifact-full-suite-repairs.xml`.
- The first complete suite finished **2 failed, 5,005 passed, 74 skipped in
  814.13s**: `.tmp/bt3-artifact-workloads-full-suite.xml`. Its two failures were
  the missing public-module export and stale failure-reason assertion repaired
  above. The prior 34 failures are no longer that suite's current result.
  The final canonical rerun passes **5,010 tests, 74 skipped, two warnings in
  815.77s**: `.tmp/bt3-artifact-workloads-final-suite.xml`. This is source-suite
  proof on Windows Python 3.13.11, with sandbox creation disabled. The warnings
  concern a legacy `orket.domain` monkeypatch and a small model token budget.
- The formerly slow extension capability audit passed a focused repeat in
  **15.41s**, with its call taking **15.20s**. The previous 6,526.529s observation
  remains historical. No cause was established and no audit implementation was
  changed: `.tmp/bt3-capability-audit-observation.xml`.
- Current code re-read the earlier live CLI receipt
  `5e98bf2ef21b10e84f2a5db7c8856e31608b77e8c611de486c4d90da6ecdff79`, with both
  card/evidence database SHA-256 values unchanged. This is actual retained-store
  compatibility proof, not a new provider invocation:
  `.tmp/bt3-artifact-cli-compatibility/report.json`.
- Three canonical live llama.cpp attempts failed at the first requirements turn
  with `E_MARKDOWN_FENCE`: sessions `canonical-live-61c1ae39f70c423aa41d9a26e0e5995d`,
  `canonical-live-5871b3de97164894aafea31f0fd716fd` and
  `canonical-live-6553accc2428440d86175bed967c568e`. The second adds an explicit
  no-fence reminder; the third also requests `json_object`. Actual response
  artifacts remain under `.tmp/bt3-canonical-workload-live/<session>/workspace`;
  `.tmp/bt3-canonical-workload-live/report.json` retains the shared diff ledger.
  No canonical artifact-workload live success is claimed.
- A separate real HTTP probe captures the outgoing `json_object` request and
  receives `{"answer":42}`. Repeating the canonical tool prompt with request
  capture confirms that the same selected server returns fenced output despite
  receiving the option. Reports: `.tmp/bt3-json-object-wire/report.json` and
  `.tmp/bt3-json-object-tool-wire/report.json`. Provider is `llama_cpp`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, server `b10809-5266f24da` at
  `http://127.0.0.1:8080/v1`. The parser refuses that output; it is a live failure,
  not evidence of accepted card completion. The operator server remains running;
  engines/providers close and `ORKET_DISABLE_SANDBOX=1` avoids sandbox resources.
- A fresh 0.6.2 wheel builds through standard isolated `pip wheel . --no-deps`:
  `.tmp/bt3-card-wheels/orket-0.6.2-py3-none-any.whl`, SHA-256
  `9504806717ad92be6b86c95eea33e1d6a9f20c62c3acfffd7f0580f6034b0cbe`.
  The attempted no-build-isolation invocation first failed because the isolated
  Windows Python 3.12 environment has no setuptools; the standard build succeeds.
  The four dedicated wheel environments were updated; all `pip check` calls pass.
  Global installs were not changed.
- The **209-case** installed envelope returns **173 passed, 36 failed** on all
  four hosts: Windows 3.11.14 (**36.825s JUnit duration**), Windows 3.12.2
  (**40.266s**), Ubuntu 3.11.16 (**58.650s**), Ubuntu 3.12.3 (**57.534s**).
  All **622** loaded core/SDK modules originate in each environment's site-packages.
  The harness has 1,530 Git-visible test/script/template/config files and no
  runtime source. Inventory: `.tmp/bt3-card-wheel-proof/harness-manifest.json`.
  Windows harness: `C:/Users/jonmc/AppData/Local/Temp/orket-bt3-card-wheel-3yl5i1kf`;
  Linux harness: `/home/jon/.cache/orket-architectural-truth/bt3-card-wheel-harness`.
  Each retains `results/<cell>/report.json` and `junit.xml`.
- Of those 36 failures, 35 concern card flows reading unshipped CWD-relative
  defaults: `core/policies/prompt_budget.yaml` and
  `core/artifacts/schema_registry.yaml`. Five assert the missing prompt budget,
  one reaches a secondary assertion after that missing-policy failure, and 29
  report the missing schema registry. This is a runtime packaging gap, not an
  excuse to copy checkout defaults into the harness. The other failure is a
  source-layout test that compares repository paths with installed package
  exports; it is inappropriate for this source-free harness and must be excluded
  from the next installed selection, while remaining in source-suite proof.
  That file's two other source-layout tests pass vacuously without checkout
  runtime directories and add no installed proof; exclude the entire file from
  the next installed selection. Retain all 209 observed outcomes as reported.

Architecture checklist: AC-01 through AC-06 pass for the scoped typed comparisons
and application-owned evidence flow. AC-07/09 pass for exercised retained evidence,
negative final persistence and read-only compatibility; broader runtime claims
remain partial. No event schema changes were introduced here (AC-08). AC-10 is
reflected in current authority, the two durable contracts and the contract delta.
Scoped Ruff (21 Python files), dependency direction with
`--legacy-edge-enforcement fail`, docs project hygiene and `git diff --check` pass.
The touched legacy protocol-ledger test import order was sorted; its six tests
then pass in 2.78s (`.tmp/bt3-protocol-ledger-import-order.xml`). Baseline collection
reports `collection_ok=true`, `release_ready=false`: 119 runtime Ruff issues,
3,444 missing legacy layer labels, 4,458 test functions, 75 oversized runtime
files and 241 long functions. All 106 new Python files/functions meet the size
limits. Touched oversized provider and test files do not grow. The inventory
contains 246 Git-visible paths; the index is empty and original main is clean.
All six sealed outward fixture digests remain unchanged.

Not verified / remaining blockers or drift:

- The canonical artifact workload still lacks live completion proof. Captured
  prompts also reveal overlapping extracted acceptance sections and a legacy
  no-argument verifier instruction while that verifier is disabled. Repair that
  prompt truth and diagnose selected-server JSON enforcement before claiming the
  canonical flow succeeds. Do not weaken parsing or change providers silently.
- Ship the runtime's required default contracts/policies through one canonical
  resource authority, then rerun installed card flows without checkout assets.
  Existing installed outward/replay acceptance does not prove installed cards.
- Scheduler/dependency/operator consumers, custom writers and multi-store final
  publication interruption remain BT-3 work. Acceptance-definition origin/admission
  also needs an explicit audit for model-created or model-modified cards; parsing
  persisted criteria establishes schema validity, not authority to choose them.
  All eleven remaining findings and
  the later ordered slices stay active. This checkpoint is not release-ready.

Exact files touched by this artifact-workload checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CARD_COMPLETION_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
- `orket/adapters/llm/local_model_provider.py`
- `orket/application/services/card_acceptance_evaluation.py`
- `orket/application/services/card_acceptance_service.py`
- `orket/application/services/card_artifact_acceptance_evaluation.py`
- `orket/application/services/card_completion_service.py`
- `orket/application/services/card_completion_turn_service.py`
- `orket/application/services/orchestrator_review_preflight_service.py`
- `orket/core/contracts/card_acceptance_inputs.py`
- `orket/core/contracts/card_completion.py`
- `orket/runtime/execution/__init__.py`
- `orket/runtime/execution/live_acceptance_assets.py`
- `orket/runtime/execution/live_acceptance_contracts.py`
- `tests/adapters/test_local_model_provider_telemetry.py`
- `tests/application/test_execution_pipeline_protocol_run_ledger.py`
- `tests/application/test_parallel_execution.py`
- `tests/helpers/card_completion.py`
- `tests/integration/test_card_artifact_acceptance.py`
- `tests/integration/test_empirical_verification.py`
- `tests/integration/test_golden_flow.py`
- `tests/integration/test_system_acceptance_flow.py`
- `tests/live/test_system_acceptance_pipeline.py`

Next: repair package-owned runtime defaults and canonical prompt truth, then
continue remaining outcome consumers and the full BT-3 acceptance envelope.

### BT-3 package defaults and installed card proof checkpoint: 2026-09-12

This checkpoint resolves the preceding checkpoint's installed default-resource
failures for the exercised card flows. SR-07 and whole BT-3 remain open. Work
continues in the requested worktree on `codex/architectural-truth-bt0`; no commit,
tag, push, release or production database migration was performed.

Changes:

- Moved the nine canonical registry, compatibility, policy and artifact schema
  files from repository `core/` into `orket/runtime/config/assets/`. Every data
  file retains its original bytes. `contract_assets.py` owns their installed
  locations; runtime peer modules import it through the config package surface.
  Package metadata includes these files in both wheels and source archives.
- Runtime contract loaders and orchestration prompt budgeting now use the same
  packaged defaults, independently of CWD. Explicit valid paths remain honored;
  explicit missing/invalid inputs fail. Malformed files placed in a CWD `core/`
  directory cannot silently become policy or registry authority.
- After the first repair, installed runs exposed another checkout dependency:
  invariant snapshot collection read `docs/specs/RUNTIME_INVARIANTS.md` from CWD.
  The invariant contract is now a tenth packaged asset under `assets/contracts/`.
  Its former spec path is a documentation index, with no duplicate statements.
  The existing parser and startup drift gate still run. The invariant contract's
  INV-004 registry reference uses the new location; schema versions and parser
  semantics are unchanged. New snapshots report their selected source path.
- Active specifications and the invariant-checker help text use the new
  authority. The touched checker imports the shared ledger helper normally;
  its unnecessary manual module-execution fallback is removed. Historical proof
  reports and retained runtime snapshots are not rewritten.

Verification (observed path `primary`; package repair and installed flows
`success`; whole BT-3 `partial success`):

- The initial default-resource suite passes **100 tests in 10.53s** after fixing
  two runtime peer imports to use the public config module surface. It covers
  actual files, invalid CWD impostors, explicit overrides, schemas and context
  composition: `.tmp/bt3-package-defaults-targeted-final.xml`. Its first run was
  **99 passed, one structural boundary failure**; that guard was retained.
- The broader source suite passes **5,012 tests, 74 skipped, two warnings in
  874.63s**: `.tmp/bt3-package-defaults-full-suite.xml`. Collection predates the
  final invariant relocation and the additional invariant/CWD negative case;
  it is not a fresh full-suite claim for that later change. The final invariant,
  drift-gate and checker envelope passes **24 tests in 0.32s** after replacing
  the old spec with its index: `.tmp/bt3-package-invariant-final.xml`.
- The source archive builds with direct subprocess exit zero. A wheel then
  builds from that archive, rather than relying on a checkout-only wheel build.
  Final sdist `.tmp/bt3-package-defaults-sdist/orket-0.6.2.tar.gz`, SHA-256
  `9a6f5ee1d0f9032578115bc1e093b968faf07867bc8089ba6454760bc7fcbbaf`;
  final wheel `.tmp/bt3-package-defaults-final-wheels/orket-0.6.2-py3-none-any.whl`,
  SHA-256 `f9910eecd7a3763b760fb8444122830a6ad66a8d76f17b1b58f4e65fb61f3faf`.
  All ten packaged resource hashes match their canonical sources in both
  distributions. Reports with shared diff ledgers:
  `.tmp/bt3-package-defaults-proof/relocation.json`, `invariant-relocation.json`,
  `sdist-build.json` and `distribution-content.json`. The first PowerShell sdist
  invocation reported exit one despite a successful-build log; subsequent
  direct subprocess builds report zero and the resulting archives are inspected.
- The first repaired wheel (`6ed139830cae6d528b3f8a8307e74db5d0e49204a6bd092e1068e00f97a9442e`)
  passes **203 installed tests and fails 29** on each host, exposing the invariant
  document dependency. Its live installed session
  `card-live-b5ae4a8e9d4c480e855292b3ec52af15` fails before inference with
  `E_RUN_TRUTH_CONTRACT_DRIFT`. Those reports remain under Windows harness
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt3-package-assets-wheel-gwrps1j_`
  and Linux harness
  `/home/jon/.cache/orket-architectural-truth/bt3-package-defaults-wheel-harness`.
- The final **254-case installed envelope passes on all four hosts**. It includes
  actual acceptance commands, SQLite, card/build/turn boundaries, canonical
  deterministic workloads, contract assets, invariant parsing and the drift gate.
  Source-layout tests are excluded from this installed selection and retained in
  source proof; no empty source-directory walk counts as installed acceptance.

| Installed host | Result | JUnit duration | Runtime imports outside site-packages |
|---|---|---|---|
| Windows Python 3.11.14 | 254 passed | 100.493s | 0 of 626 |
| Windows Python 3.12.2 | 254 passed | 103.861s | 0 of 626 |
| Ubuntu 24.04 Python 3.11.16 | 254 passed | 138.236s | 0 of 626 |
| Ubuntu 24.04 Python 3.12.3 | 254 passed | 130.724s | 0 of 626 |

  These are 254 distinct cases repeated on four hosts, with deterministic model
  fixtures rather than live inference. Each reports one legacy `orket.domain`
  monkeypatch warning. All four `pip check` calls pass. Global installations are
  unchanged. Final harnesses contain 1,531 Git-visible tests/scripts/template/config
  files, no runtime source and no copied CWD `core/` assets. Inventory:
  `.tmp/bt3-package-defaults-proof/final-harness-manifest.json`. Windows harness:
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt3-package-final-wheel-s5y80m73`;
  Linux harness:
  `/home/jon/.cache/orket-architectural-truth/bt3-package-defaults-final-wheel-harness`.
  Each retains `results/<cell>/report.json` with wheel provenance and runtime
  origins, plus `junit.xml` and test databases.

- The final Windows Python 3.12 wheel also passes a real
  `OrchestrationEngine.run_card` flow using the existing llama.cpp server and
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`. Two actual model receipts lead to file
  tools, declared increment CLI checks, persisted card completion and session
  `done`, with the same receipt in the build outcome. Session
  `card-live-c4f7445e40b642eea1bf0681ef81f0b9`; receipt
  `20361dfbbce6c2eabf4c5473267ae3e0600cc01cd4f2e21756dc2143fb4aab89`.
  All 579 observed core-module origins are in site-packages. Driver
  `bt3_package_live.py` and stable report
  `.tmp/bt3-package-defaults-live/report.json` reside in the final Windows harness.
  The engine closes; the operator-owned server stays running. All routine proof
  uses `ORKET_DISABLE_SANDBOX=1` and creates no sandbox resources.

Architecture checklist: AC-01 through AC-06 pass for explicit resource selection,
unchanged validators and application-owned execution. AC-07/09 pass for the
exercised live and installed completion boundaries; broader outcome guarantees
remain partial. Event schemas are unchanged (AC-08). AC-10 is reflected in the
current authority, five active specifications, invariant contract/index and
`CONTRACT_DELTA_RUNTIME_CONTRACT_ASSETS_BT3_2026-09-12.md`.
Structural verification passes: scoped Ruff on all thirteen Python paths,
dependency direction with legacy-edge enforcement set to `fail`, documentation
project hygiene and `git diff --check`. All 108 new Python files and their
functions meet the 400/70-line limits. The index is empty, original `main` is
clean, and all six sealed outward fixtures retain their checkpoint hashes.
Current baseline: `collection_ok=true`, `release_ready=false`, 118 runtime Ruff
issues, 3,441 missing labels among 4,461 test functions, 75 oversized runtime
files and 241 long functions. These remaining repository metrics are not a
passing release gate. The worktree contains 284 Git-visible changed paths.
The invariant checker's final import simplification also passes its three
source tests (0.15s); the installed matrix above predates that script-only
cleanup and does not claim to cover it.

Not verified / remaining blockers or drift:

- The full source suite has not been rerun after the final invariant relocation;
  its later focused and installed proof is scoped above. Cross-installation
  resume of runs with pre-relocation contract snapshots remains unverified.
- Canonical summation live acceptance remains open. Its prior fenced responses
  and overlapping/contradictory prompt sections are not repaired by packaging.
- Acceptance-definition origin/admission, scheduler/dependency/operator outcome
  consumers, custom writers and multi-store publication interruption remain
  BT-3 work. All eleven remaining findings and later ordered slices stay active.
  This checkpoint does not establish general workload quality, hostile-code OS
  containment, supported capacity or release readiness.

Exact paths touched by this package-default checkpoint (moves list both ends):

- `CURRENT_AUTHORITY.md`
- `core/artifacts/run_evidence_graph_schema.json`
- `core/artifacts/run_graph_schema.json`
- `core/artifacts/run_summary_schema.json`
- `core/artifacts/schema_registry.yaml`
- `core/policies/artifact_retention_tiers.yaml`
- `core/policies/prompt_budget.yaml`
- `core/tools/compatibility_map.yaml`
- `core/tools/compatibility_map_schema.yaml`
- `core/tools/tool_registry.yaml`
- `docs/architecture/CONTRACT_DELTA_RUNTIME_CONTRACT_ASSETS_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
- `docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md`
- `docs/specs/RUNTIME_INVARIANTS.md`
- `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
- `docs/specs/TOOL_CONTRACT_TEMPLATE.md`
- `orket/application/services/orchestrator_turn_context_builder.py`
- `orket/application/workflows/prompt_budget_guard.py`
- `orket/runtime/config/__init__.py`
- `orket/runtime/config/assets/artifacts/run_evidence_graph_schema.json`
- `orket/runtime/config/assets/artifacts/run_graph_schema.json`
- `orket/runtime/config/assets/artifacts/run_summary_schema.json`
- `orket/runtime/config/assets/artifacts/schema_registry.yaml`
- `orket/runtime/config/assets/contracts/RUNTIME_INVARIANTS.md`
- `orket/runtime/config/assets/policies/artifact_retention_tiers.yaml`
- `orket/runtime/config/assets/policies/prompt_budget.yaml`
- `orket/runtime/config/assets/tools/compatibility_map.yaml`
- `orket/runtime/config/assets/tools/compatibility_map_schema.yaml`
- `orket/runtime/config/assets/tools/tool_registry.yaml`
- `orket/runtime/config/contract_assets.py`
- `orket/runtime/policy/prompt_budget_policy.py`
- `orket/runtime/registry/contract_bootstrap.py`
- `orket/runtime/registry/runtime_invariant_registry.py`
- `pyproject.toml`
- `scripts/governance/check_runtime_invariant_registry.py`
- `tests/application/test_orchestrator_epic.py`
- `tests/contracts/test_run_evidence_graph_contract.py`
- `tests/integration/test_runtime_contract_package_assets.py`
- `tests/runtime/test_artifact_retention_tiers.py`
- `tests/runtime/test_run_summary.py`

Next: repair canonical prompt truth and prove its live workload, then finish
definition-admission and outcome-consumer audits before the complete BT-3 gate.

### BT-3 prompt truth and canonical live workload checkpoint: 2026-09-12

Canonical four-card summation now passes source live acceptance on the selected
llama.cpp host. This closes the preceding checkpoint's fenced-output blocker for
the exercised configuration. SR-07 and whole BT-3 remain open. Work continues in
the requested worktree on `codex/architectural-truth-bt0`; no commit, tag, push,
release or production migration was performed.

Changes:

- Compact prompt extraction bounds project context, patch and acceptance sections
  at the next named section. Paragraphs are retained, and later acceptance is no
  longer copied into preceding sections.
- Standard orchestration supplies its resolved legacy `runtime_verifier_enabled`
  boolean. Both renderers share `turn_prompt_contracts.py`; disabled commands are
  omitted, and explicit commands replace the inferred no-argument app command.
  Disabled verification also removes its inferred support-file read from review
  context. Explicit turn-contract reads and declared card acceptance remain active.
- llama.cpp's explicit `json_object` request now carries `schema: {type: object}`.
  The selected host enforces this documented request form where the bare form
  emits Markdown. The adapter does not change provider, model or tool transport,
  clean responses, relax parsing, add a retry, or opt unset callers into JSON mode.
  The provider truth table and active prompting contract describe this encoding.
- Canonical requirements, design and optional attribution stages use their own
  artifact profiles and review paths; implementation/review use app contracts.
  The deterministic requirements provider no longer creates placeholder Python
  to satisfy an incorrectly inferred app review. The touched optional live test
  also uses the canonical provider-neutral model default.

Verification (observed path `primary`; repaired source workload `success`;
whole BT-3 `partial success`):

- The new prompt cases first report **14 failed, six passed** in 3.17s
  (`.tmp/bt3-prompt-truth-before.xml`): missing application enable input,
  contradictory explicit/inferred commands and duplicated compact sections.
  After repair, the initial orchestration/prompt/completion envelope passes
  **125 tests in 20.65s** (`.tmp/bt3-prompt-truth-after.xml`). The expanded final
  source envelope passes **208 tests in 43.42s**
  (`.tmp/bt3-prompt-truth-envelope.xml`), including settings precedence, retained
  acceptance, verifier service, model adapter/profile and namespace checks.
  These contract/integration tests use deterministic model fixtures; they are
  not live model proof.
- The six provider request-shape cases pass in 0.26s for explicit text,
  JSON-object and JSON-schema modes on the llama.cpp and LM Studio branches
  (`.tmp/bt3-object-schema-request.xml`). Mock HTTP proves request encoding only.
- The deterministic canonical pipeline passes without the former requirements
  placeholder (`.tmp/bt3-stage-artifacts.xml`: two passed in 7.71s). Final result
  after aligning the touched optional live test's default: **two passed, one
  opt-in live test skipped in 8.11s** (`.tmp/bt3-stage-artifacts-final.xml`).
- The first repaired source live run, `canonical-live-12147f77043a4df9b75aed6cd12af0a3`,
  still fails with `E_MARKDOWN_FENCE`. Its actual prompt has one acceptance
  section and no disabled-verifier command. A raw HTTP diagnostic compares bare
  JSON-object, explicit schema and literal grammar requests on the same host:
  `.tmp/bt3-response-format-diagnostic/report.json`. Bare mode returns fenced
  tool output; the latter two obey their deliberately constrained diagnostic
  response. These probes execute no tools. A subsequent general object-schema
  probe emits valid tool-envelope JSON:
  `.tmp/bt3-object-schema-wire/report.json`.
- After request encoding is repaired, source session
  `canonical-live-cdd53258d76d4f67ba799ca95c27877a` advances through two real
  model calls and exposes the requirements guard's nonexistent `main.py` read.
  The resulting failed-tool retry also exposes an invalid
  `awaiting_guard_review -> ready` transition. Stage contracts are repaired;
  general failed-tool recovery is still required and is not proven by later success.
- Source session `canonical-live-9cff7162a65141f89d35a98923701f3d` then completes
  all four stages with eight actual model receipts. The final run removes the
  diagnostic prompt patch and also succeeds:
  **`canonical-live-bb39ce94ac8a477eb730b0972e4f7812`**, Windows Python 3.13.11,
  llama.cpp **`b10809-5266f24da`**, model
  **`orcarouter_qwen3.8-27b-uncensored-q4_k_l`**, eight model receipts. It performs
  real read/write tools, artifact checks and CLI checks for `(17,25) -> 42`,
  `(-5,2) -> -3` and `(0,0) -> 0`. All cards are `done`, their retained acceptance
  receipts are readable, and the session's build outcome contains the same digests:

| Card | Accepted receipt digest |
|---|---|
| REQ-1 | `54f1a55d585bc0fcdf4599a3df0ede4e73cb60797605e24564ee22896a5bd096` |
| ARC-1 | `f7fbd3c5e6c4b23899d15a3e926dcc1f88749e2da6571f037027226fd40f80c9` |
| COD-1 | `e6cd226147f7a0adfe82b997249661fe0384380e5b3a5b9f4cb8a93a5f4fe5c4` |
| REV-1 | `d14386689eb7cb8e3885b8ea94b928856eb2d284a63cf0d797bee16b91b15a58` |

  Driver `.tmp/bt3_canonical_workload_live.py` retains actual session directories,
  databases, prompt/model artifacts and a stable diff-ledger report at
  `.tmp/bt3-canonical-workload-live/report.json`. All eight final prompt artifacts
  have exactly one acceptance section and omit the disabled verifier contract.
  The final invocation uses explicit `ORKET_LLM_OPENAI_RESPONSE_FORMAT=json_object`,
  `ORKET_PROTOCOL_GOVERNED_ENABLED=true`, `ORKET_LOCAL_PROMPTING_MODE=enforce`,
  `ORKET_DISABLE_RUNTIME_VERIFIER=true`, an empty prompt patch and
  `ORKET_DISABLE_SANDBOX=1`. Declared acceptance still executes. The engine closes;
  the operator's server stays running. No sandbox resources are created.

Architecture checklist: AC-01 through AC-06 pass for scoped dependency direction,
explicit application settings, pure rendering and unchanged effect ownership.
AC-07/09 pass for the exercised source workload and retained acceptance boundaries;
whole outcome/recovery guarantees remain partial under BT-3. Event schemas remain
unchanged (AC-08). AC-10 is reflected in current authority, the two active contracts
and `CONTRACT_DELTA_CARD_PROMPT_TRUTH_BT3_2026-09-12.md`.
Scoped Ruff on all fifteen Python paths, dependency direction with legacy-edge
enforcement `fail`, and docs project hygiene pass. All 110 new Python files and
their functions meet the 400/70-line limits. The refreshed baseline reports
`collection_ok=true`, `release_ready=false`: 118 runtime Ruff issues, 3,441 missing
labels among 4,464 test functions, 75 oversized runtime files and 241 long
functions. The worktree contains 289 Git-visible changed paths. The original
`main` is clean, the index is empty and all six sealed outward fixtures retain
their checkpoint hashes. These structural results are not a passing release gate.

Not verified / remaining blockers or drift:

- The full source suite and installed matrix have not been rerun for this prompt,
  request-encoding and stage-definition change. Earlier package-default installed
  proof remains scoped to its checkpoint. The final live proof is Windows source,
  not an installed or Linux live claim. Optional source-attribution live execution,
  enabled legacy-verifier live execution and general provider conformance are not
  established by the four-card disabled-legacy-verifier run.
- Failed-tool recovery's invalid guard-review-to-ready transition remains open.
  Acceptance-definition origin/admission, scheduler/dependency/operator consumers,
  custom writers and multi-store publication interruption remain BT-3 work.
- Cross-installation resume with pre-relocation snapshots remains unverified.
  All eleven remaining findings and later ordered slices stay active. This
  checkpoint does not establish general workload quality, hostile-code containment,
  supported capacity or release readiness.

Exact Git-visible paths touched by this prompt-truth checkpoint (ignored proof
drivers and artifacts are referenced above):

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CARD_PROMPT_TRUTH_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
- `orket/adapters/llm/local_model_provider.py`
- `orket/adapters/llm/openai_compat_runtime.py`
- `orket/application/services/orchestrator_turn_context_builder.py`
- `orket/application/workflows/orchestrator_ops.py`
- `orket/application/workflows/turn_message_builder.py`
- `orket/runtime/config/__init__.py`
- `orket/runtime/config/compact_turn_packet.py`
- `orket/runtime/config/provider_truth_table.py`
- `orket/runtime/config/turn_prompt_contracts.py`
- `orket/runtime/execution/live_acceptance_assets.py`
- `orket/runtime/execution/live_acceptance_contracts.py`
- `tests/adapters/test_local_model_provider_telemetry.py`
- `tests/contracts/test_turn_prompt_truth.py`
- `tests/integration/test_card_completion_control_plane.py`
- `tests/live/test_system_acceptance_pipeline.py`

Next: finish definition-admission and outcome-consumer audits, repair failed-tool
recovery, then rebuild the installed envelope and prove the complete BT-3 gate.

### BT-3 model definition admission checkpoint: 2026-09-12

The model driver can no longer write its own completion criteria into epic/rock
configuration. Shared pure core policy rejects nested `completion_acceptance`
members before structural writes and before builtin `create_issue` storage.
Driver rejection is explicit, has no success suffix and logs to the configured
operator workspace. The trusted operator/application config boundary remains;
there is no new admission endpoint, serialized trust flag or provenance inference.
SR-07 and whole BT-3 remain open in the requested worktree.

The scoped audit also finds that card-authoring inputs and ODR results remain
nested data; they are not promoted to top-level acceptance. Team-replan cards and
ordinary model-created cards carry no implicit criteria. Existing programmatic
repository/service callers remain responsible for independently admitted workload
requirements. Existing config bytes alone cannot establish historical authorship.
No `completion_acceptance` declaration was found in the current source `model/`
or `config/` JSON inventory; this is structural observation, not a provenance audit.

Verification:

- The corrected regression fixtures first report **seven failed, one passed in
  0.46s** (`.tmp/bt3-definition-admission-regression.xml`). Five structural shapes
  incorrectly succeed, and two builtin calls silently ignore the reserved input.
  The preceding eight fixture-setup failures in
  `.tmp/bt3-definition-admission-before.xml` are not behavioral counterexamples.
- Final focused driver/card/API envelope: **61 passed in 2.28s**
  (`.tmp/bt3-definition-admission-final.xml`). Integration cases exercise real
  asset files and SQLite, including legacy `cards` children, nested rock children,
  both builtin argument shapes, unchanged bytes and refusal before DB creation.
  An ordinary created card remains `not_evaluated`; an unsupported `done` write
  is rejected. Deterministic providers in this envelope are not live proof.
- Live source session **`admission-live-199e29745be247719bfcfdd5e954d0e7`** uses
  Windows Python 3.13.11, llama.cpp at `127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, explicit JSON-object schema output
  and strict driver parsing. The real HTTP response preserves the supplied
  negative-control definition in `new_asset.issues[0].params`; the driver returns
  `E_CARD_ACCEPTANCE_MODEL_DEFINITION_FORBIDDEN`, with identical before/after
  asset inventories and hashes. The refusal event is retained in the isolated
  operator workspace. Observed path **`degraded`**, result **`success`**: the
  isolated project has no `skill.operations_lead` or `dialect.qwen` assets, so
  driver prompting is explicitly `fallback`. No response was substituted.
  This is refusal proof, not a governed-driver configuration or workload proof.
- Driver `.tmp/bt3_definition_admission_live.py` retains a stable diff-ledger
  report at `.tmp/bt3-definition-admission-live/report.json`. Two earlier proof
  startup attempts failed before inference with `SettingsBridgeError` because the
  synchronous driver constructor ran inside the event loop; construction now
  runs in a worker thread. The actual provider closes, `ORKET_DISABLE_SANDBOX=1`
  is set, no sandbox resources are created and the operator server stays running.
- Scoped Ruff, enforced dependency direction and docs project hygiene pass.
  Baseline collection succeeds but `release_ready=false`: 118 runtime Ruff
  issues, 3,441 missing labels among 4,467 test functions, 75 oversized runtime
  files and 241 long functions. All 112 new Python files/functions meet 400/70
  limits. The worktree has 293 Git-visible changed paths; original main is clean,
  the index is empty and six sealed outward fixture hashes remain unchanged.

Architecture checklist: AC-01/02/03/04/06 pass for scoped pure policy, explicit
payload input and unchanged adapter effects. AC-05 remains partial because
`orket/driver_support_resources.py` is a pre-existing mixed root-layer resource
owner; the later layering slice owns its decomposition. No new effect owner or
adapter-to-application import is introduced. AC-07/09 pass for the exercised
refusals; whole completion truth remains partial. AC-08/10 are recorded in the
event taxonomy, current authority, active contract and admission contract delta.

Not verified / remaining blockers or drift: full source and installed matrices
have not been rerun for this change. Governed-driver assets, historical definition
authorship and custom/privileged writers are outside this live proof. Existing
source config is a trusted application input, not a hostile-input admission API.
Scheduler/dependency/operator consumers, failed-tool recovery, custom writers and
multi-store publication interruption remain BT-3 work. Cross-installation resume
and all later ordered capability gates remain unverified. No commit, tag, push,
release, production migration or whole-lane closure was performed.

Exact Git-visible files touched by this admission checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CARD_ACCEPTANCE_ADMISSION_BT3_2026-09-12.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/adapters/tools/families/cards.py`
- `orket/core/policies/card_acceptance_admission.py`
- `orket/driver_support_resources.py`
- `tests/integration/test_card_acceptance_admission.py`

Next: repair the remaining outcome consumers and failed-tool recovery, then
finish custom-writer/publication review and rebuild the complete BT-3 envelope.

### BT-3 guard retry requeue checkpoint: 2026-09-12

The reproduced `awaiting_guard_review -> ready` failure is repaired. The pure
transition service extends its existing system retry exception to this source
state, restricted to `ready` and the two existing scheduling reasons. It retains
both gate hooks and does not add an ordinary model transition or guard decision.
The failure handler's existing retry count, failed dispatch closeout and card
completion invalidation now run to their intended result. Whole BT-3 remains open.

Verification (scoped recovery path `primary`, result `success`; whole BT-3
`partial success`):

- Corrected counterexamples report **four failed, twelve passed in 6.60s**
  (`.tmp/bt3-retry-recovery-counterexample.xml`): both system reasons reject the
  guard retry, and real missing-read turns reproduce the failure through both
  protocol and non-protocol dispatch. Earlier fixture revisions in
  `.tmp/bt3-retry-recovery-before.xml` and `-regression.xml` also contained a
  progress-contract omission and an incorrect enum-token assertion; those
  fixture errors are not behavioral regressions.
- After repair, the focused transition/card/orchestrator envelope reports
  **101 passed in 16.54s** (`.tmp/bt3-retry-recovery-after.xml`). Actual SQLite
  integration covers in-progress, code-review and guard-review failed reads,
  retry-count persistence, cleared completion bindings, stale request rejection,
  failed/unsatisfied dispatch truth and a new attempt generation. A comment
  written during the failed turn remains present; failure is not evidence that
  no effects occurred. Exhaustion retains blocked/unsatisfied truth.
- An additional final integration case passes in **0.42s**
  (`.tmp/bt3-retry-model-refusal.xml`): builtin `update_issue_status` still rejects
  the model's `ready` request when its arguments claim `system_set_status` and
  `retry_scheduled`. The stored card remains unchanged. These tests use
  deterministic model fixtures and are not live model proof.
- Live source session **`retry-live-c65293a7489948a098d79ba2b4c3b27f`** uses the
  existing llama.cpp server and `orcarouter_qwen3.8-27b-uncensored-q4_k_l` on
  Windows Python 3.13.11. Two real model responses drive a missing-file read plus
  retained comment, the actual failure handler/system requeue, rejection of the
  old completion request, and a separately dispatched accepted review of the
  prepared increment fixture. Final current receipt digest:
  `49f15d6d9afd829b7e127d6e18d0cd7c776e47ddf51824f9434674c0c29ed2f8`.
  The new turn performs real read/status tools and fresh CLI acceptance.
  This composed proof manually dispatches the later review; it does not prove
  automatic engine restart, whole-build completion or a model-authored program.
- Driver `.tmp/bt3_retry_recovery_live.py` retains model HTTP bodies, source roots,
  card/attempt truth and the receipt through the stable diff-ledger report
  `.tmp/bt3-retry-recovery-live/report.json`. Its first attempt,
  `retry-live-ef9d1f2d08d94866a0a6d15ad0ffac45`, failed before the intended probe:
  unsectioned instructions were absent from the compact packet and the model's
  invented `guard_review_passed` status was refused. The driver now supplies its
  explicit probe in the existing `PATCH` section and includes declared acceptance.
  No response substitution or parser relaxation was used. Provider closes;
  `ORKET_DISABLE_SANDBOX=1` prevents sandbox creation; operator server stays running.
- New test files pass Ruff; the touched runtime file retains one pre-existing
  `UP042` finding on `TransitionErrorCode(str, Enum)`, confirmed in HEAD. Dependency
  direction with legacy-edge enforcement `fail`, docs hygiene and diff checks
  pass. Refreshed baseline: `collection_ok=true`, `release_ready=false`, 118 runtime
  Ruff issues, 3,441 missing labels among 4,473 test functions, 75 oversized runtime
  files and 241 long functions. All 114 new Python files/functions meet 400/70
  limits. There are 297 Git-visible changed paths; original main is clean, index
  empty, and six sealed outward fixture hashes remain unchanged.

Architecture checklist: scoped AC-01 through AC-06 pass; the change is a pure
input/transition rule with existing application-owned effects. AC-07/09 pass for
the recorded failure/requeue/fresh-acceptance outcomes and remain partial for
whole recovery guarantees. Event shapes are unchanged (AC-08). AC-10 is recorded
in current authority, the active completion contract and the retry contract delta.

Not verified / remaining blockers or drift: full source and installed matrices,
automatic restart/retry, interrupted multi-store publication and custom-writer
effects remain outside this checkpoint. Scheduler selection still uses status-only
`CardMiscOps.get_independent_ready_issues`, while `_build_dependency_context`
accepts archived prerequisites; these consumers require retained acceptance and
consistent scope before BT-3 can close. Remaining operator projections and later
ordered slices stay active. No commit, tag, push, release or production migration.

Exact Git-visible files touched by this retry checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CARD_RETRY_REQUEUE_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/core/domain/workitem_transition.py`
- `tests/contracts/test_card_retry_transition.py`
- `tests/integration/test_card_retry_recovery.py`

Next: replace status-only dependency/dispatch consumption with application-owned
retained-acceptance inspection; finish remaining consumers and publication/writer
review, then rebuild and prove the complete BT-3 envelope.

### BT-3 dependency acceptance and dispatch checkpoint: 2026-09-12

Scheduling and pre-turn context now share application-owned retained acceptance
and build scope. The adapter's status-only readiness method is removed.
`card_completion_outcome_service.require_accepted_card_receipt` is reused by build
finalization and the new `card_dependency_service`. Only current-build accepted
`done`/`guard_approved` prerequisites unlock a card. The complete dispatch inventory
is observed under the existing writer guard. Strategies receive admitted copies,
select identities and cannot replace the dispatch payload, repeat a selection or
select an unadmitted card. Targeted and review dispatch obey the same boundary.

Before preflight or turn effects, the application rechecks the target's dependency
inputs/build/status and prerequisite acceptance. Changed inputs/status or missing
targets fail explicitly; newly unresolved prerequisites prevent the turn.
Context carries accepted receipt digests and rejection reasons. The stalled event
now includes per-dependent rejection diagnostics. Guards are released before model
calls; this is not permanent artifact currency or atomic publication across stores.

Verification (source path `primary`, result `success`; whole BT-3 `partial success`):

- Opening integration counterexamples: **five failed, four passed in 1.74s**
  (`.tmp/bt3-dependency-before.xml`). Accepted guard approvals were withheld,
  archived prerequisites resolved in context, legacy/unreadable-evidence `done`
  rows unlocked work, and foreign-build acceptance resolved in context. The
  repaired initial dependency/build-finalization envelope passes **19 tests in
  5.62s** (`.tmp/bt3-dependency-after.xml`).
- Final source envelope: **167 passed in 18.14s**
  (`.tmp/bt3-dependency-final.xml`). Real files/SQLite cover both accepted terminal
  statuses, pending/reopened/archived/canceled/missing/legacy/foreign prerequisites,
  missing evidence, targeted ready/in-progress/review dispatch, changed dependency
  edges or target lifecycle, prerequisite reopening, duplicate/unknown planner
  selections and planner mutation isolation. Existing aggregate writer-guard and
  final build evidence tests remain included. The intermediate envelope had one
  unit-fixture failure (`.tmp/bt3-dependency-envelope.xml`: one failed, 157 passed)
  because a manually composed fake repository lacked the new application double.
  It was migrated without adding a production fallback.
- Three old status-only tests are replaced by the stronger dependency integration
  cases. Isolated orchestration tests now explicitly stub the application service
  through `tests/helpers/card_dispatch.py`; these model-heavy unit fixtures are
  not evidence for acceptance enforcement. Modified cases carry unit labels.
- Additional runtime/turn/retry envelope: **37 passed, one opt-in live test
  skipped in 30.14s** (`.tmp/bt3-dependency-runtime.xml`). This includes the
  deterministic canonical pipeline, current turn receipts and retained retry
  behavior. No mock model is counted as provider-backed proof.
- The canonical standard runtime passes live again:
  **`canonical-live-c1f24128f7a1412f968aca21ae9aebde`**, Windows Python 3.13.11,
  selected llama.cpp host/model, **eight actual model responses**, four accepted
  cards and session `done`. Real dependencies are `REQ-1 -> ARC-1 -> COD-1 -> REV-1`;
  all corresponding later prompts report the resolved prerequisite lifecycle.
  Card and build receipt digests match:

| Card | Accepted receipt digest |
|---|---|
| REQ-1 | `331def57aaf59b02d096b3e3074ad3e78cbf264622505efa973332fe893b4ce2` |
| ARC-1 | `b7f3c0a4c6ea344529ccf0ac1349b8e31311a27f3777b80d725252827d4e3e2b` |
| COD-1 | `470f60a2ded014183c81902ca44424d053c902f63eea31688849a45b3a318514` |
| REV-1 | `e82608d1dbba8d5582d6e67f73e904a2dee5722d738233787191e0545d41526e` |

  The existing `.tmp/bt3_canonical_workload_live.py` driver retains its stable
  diff-ledger report at `.tmp/bt3-canonical-workload-live/report.json`, databases,
  prompt/model artifacts and prior sessions. This run uses
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, explicit JSON-object output,
  enforced local prompting, disabled legacy verification, no prompt patch and
  `ORKET_DISABLE_SANDBOX=1`. Actual artifact and summation CLI acceptance still
  execute. Engine closes; no sandbox is created; the operator server stays running.
- All eleven touched Python paths pass Ruff. Enforced dependency direction,
  docs project hygiene and diff checks pass. Baseline collection succeeds with
  `release_ready=false`: 118 runtime Ruff issues, 3,425 missing labels among 4,474
  test functions, 75 oversized runtime files and 241 long functions. All 117 new
  Python files/functions meet 400/70 limits. The oversized operational and test
  modules shrink. Worktree inventory is 303 Git-visible changed paths; original
  main is clean, index empty and six sealed outward fixture hashes are preserved.

Architecture checklist: AC-01 through AC-06 pass for scoped dependency direction,
application ownership, explicit strategy inputs/copies and unchanged effect
adapters. AC-07/09 pass for the recorded dependency and canonical workload outcomes;
whole concurrency/publication guarantees remain partial. AC-08/10 are recorded in
the event taxonomy, current authority, active contract and dependency contract delta.

Not verified / remaining blockers or drift: the full source suite and installed
matrix had not been rebuilt for these dependency changes. At that checkpoint,
the API execution graph still derived dependency satisfaction from raw status,
including `archived`; the following operator graph checkpoint repairs that consumer. Custom writers, changes after the final observation, multi-store
publication interruption and cross-installation resume remain open. No general
workload capability, hostile-code containment, capacity or release readiness is
claimed. All later ordered slices remain active; no commit, tag, push or production
migration was performed.

Exact Git-visible paths touched by this dependency checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CARD_DEPENDENCY_ACCEPTANCE_BT3_2026-09-12.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/adapters/storage/async_card_repository.py`
- `orket/adapters/storage/card_misc_ops.py`
- `orket/application/services/card_completion_outcome_service.py`
- `orket/application/services/card_dependency_service.py`
- `orket/application/workflows/orchestrator_ops.py`
- `tests/adapters/test_async_card_repository.py`
- `tests/adapters/test_card_ops_components.py`
- `tests/application/test_odr_prebuild_continuation.py`
- `tests/application/test_orchestrator_epic.py`
- `tests/helpers/card_dispatch.py`
- `tests/integration/test_card_dependency_acceptance.py`

Next at the dependency checkpoint: repair the operator graph (recorded below),
then finish remaining consumer/writer and publication review and prove BT-3.

### BT-3 operator execution graph checkpoint: 2026-09-12

The authenticated execution graph now uses application-owned inspection and the
same retained acceptance/build-scope check as pre-turn dependency context. Typed
session inventory and all referenced prerequisite reads share one card writer
guard. Raw lifecycle remains visible alongside validated completion references
and rejection reasons. Archived, receiptless, unreadable-evidence and foreign-build
prerequisites cannot appear satisfied; a valid same-build prerequisite outside
the displayed session can resolve. A terminal node can still report blocked
prerequisites. The existing graph-specific `unresolved_dependencies` field retains
its missing-from-view meaning; acceptance failures have separate diagnostics.

Graph topology is a pure projection of inspected node dependencies. Handoff edges
remain observational and do not confer acceptance or change topological order.
Canonical stored cards have no parent field; the unreachable parent/spawn inference
is removed. Snapshot persistence moves to the application service and shared
workspace mutation guard. Write failures are logged, while inspection remains a
point-in-time read rather than atomic publication or permanent artifact currency.
The API module shrinks to 1,828 lines; the new service is 98 lines.

Verification (source path `primary`, result `success`; whole BT-3 `partial success`):

- The opening API integration counterexamples reproduce **five failures and four
  passes in 3.20s** (`.tmp/bt3-graph-before.xml`): archived, historical done,
  missing-evidence and foreign-build prerequisites were incorrectly satisfied;
  accepted prerequisites outside the session view were incorrectly blocked.
  The initial harness had nine setup failures from an incorrect composition
  keyword; those were corrected before recording behavioral counterexamples.
- Initial repaired dependency/graph envelope: **29 passed in 6.91s**
  (`.tmp/bt3-graph-after.xml`). Broader API/repository envelope: **160 passed in
  21.51s** (`.tmp/bt3-graph-envelope.xml`). Final envelope including new negative
  controls and workspace guard regressions: **169 passed in 24.28s**
  (`.tmp/bt3-graph-final.xml`). Real stores/files exercise receipt diagnostics,
  evidence loss across repeated requests, snapshot content, missing and foreign
  prerequisites, cycles, terminal lifecycle with failed dependencies, observed
  handoff deduplication, and a real obstructed snapshot write with logged failure.
  Isolated tests remain structural/integration evidence, not provider proof.
- Live TCP/API proof **`graph-live-9603870a60454651ac32b306f7ac6ddd`** succeeds on
  Windows Python 3.13.11 using the worktree source and prepared real increment-CLI
  acceptance. Nine separate app/server lifecycles cover done, guard-approved,
  archived, canceled, historical receiptless done, missing card, missing evidence,
  foreign build and accepted outside-view cases. All nine unauthenticated reads
  are rejected. All ten authenticated reads pass, including reinspection after
  deleting evidence. Retained snapshots match the latest responses; deleted
  evidence is not recreated. Every server stops and every runtime context closes.
  Driver: `.tmp/bt3_execution_graph_live.py`; stable diff-ledger report:
  `.tmp/bt3-execution-graph-live/report.json`. It records **zero model calls** and
  `ORKET_DISABLE_SANDBOX=1`; no sandbox is created. The operator llama.cpp server
  is unchanged. A first live harness attempt failed before server startup because
  synchronous runtime composition ran inside the event loop. Construction now
  runs in a worker thread; no production bootstrap bypass was introduced.
- Six touched Python paths pass Ruff; enforced dependency direction, docs project
  hygiene and diff checks pass. Fresh baseline collection succeeds with
  `release_ready=false`: **118 runtime Ruff issues, 3,425 missing labels among
  4,479 test functions, 75 oversized runtime files and 240 long functions**.
  All 119 new Python files/functions meet 400/70 limits. The worktree contains
  306 Git-visible changed paths; original main is clean, index empty and all six
  retained outward fixture hashes match without resealing.

Architecture checklist: AC-01/02/03/04 pass for scoped layering, unchanged strategy
inputs and deterministic topology. AC-05/06 pass for application-owned guarded
persistence through the existing file adapter. AC-07/09 pass for observed graph
truth and retained diagnostic references; complete publication atomicity remains
partial under BT-3. AC-08 uses existing logging without a new structured event;
AC-10 is reflected in the active acceptance spec, frontend contract, current
authority and execution-graph contract delta.

Not verified / remaining blockers or drift: no fresh full source suite, rebuilt
installed matrix or provider-backed workload was run for this graph change. The
live proof is scoped to authenticated operator reads with prepared acceptance,
not model-produced output. Remaining operator consumers, custom writers,
multi-store publication interruption, automatic retry/resume and cross-installation
resume remain required work. Existing status fields still describe lifecycle;
clients must use the new acceptance fields for completion claims. SR-07 and the
remaining 11 findings stay open, as do every later ordered slice. No commit, tag,
push, release or production migration was performed.

Exact Git-visible paths touched by this operator graph checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/architecture/CONTRACT_DELTA_EXECUTION_GRAPH_ACCEPTANCE_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/adapters/storage/async_card_repository.py`
- `orket/application/services/card_dependency_service.py`
- `orket/application/services/execution_graph_service.py`
- `orket/core/contracts/repositories.py`
- `orket/interfaces/api.py`
- `tests/integration/test_execution_graph_acceptance.py`

Next: finish remaining consumer/writer and publication review, then rebuild and
prove the complete BT-3 envelope before proceeding to BT-4.

### BT-3 card and run operator views checkpoint: 2026-09-12

Card and run views now require application-owned retained acceptance inspection.
Card reads and list filtering share the execution graph's receipt projection;
accepted done and guard-approved rows enter the completed bucket, while unaccepted
successful-looking lifecycle requires review. Typed card detail payloads use JSON
serialization so enum values remain correct status tokens. Card summaries and
completion no longer inherit the last run's success, and an independently accepted
card stays completed even when its run fails. The last run remains separately
named. Unfiltered card pagination now applies offset once; filtered requests retain
the explicit existing 500-card scan bound.

Run verification requires successful retained lifecycle and a published completion
outcome matching a fresh sufficient build inspection, including expected IDs and
receipt digests. Attribution-only metadata cannot confer verification. Missing,
substituted or stale outcomes, reopened cards, new receipts and unreadable evidence
are rejected. Source attribution stays separately visible. The API no longer
assumes output exists merely because lifecycle says completed. Shared loading and
classification authority lives in `operator_completion_service`; duplicate run
loaders and status-only card filtering are removed from interfaces. The graph's
receipt projection is reused without changing its contract.

Verification (path `primary`, result `success`; whole BT-3 `partial success`):

- Opening real-store/API counterexamples: **10 failed in 5.47s**
  (`.tmp/bt3-operator-before.xml`). Attribution falsely verified archived, canceled,
  historical receiptless, missing, evidence-unreadable and foreign-build cases;
  deleting evidence retained a verified claim. Typed accepted card details were
  also incorrectly classified as open.
- The first repaired envelope had **25 passed, four failed in 10.46s**
  (`.tmp/bt3-operator-after.xml`). Three presentation contract fixtures lacked the
  newly required explicit acceptance input; the real positive fixture lacked its
  retained build outcome. These fixtures now supply explicit projection input or
  an actual inspected outcome. Later harness negatives initially used an artifact
  update to remove a key despite merge semantics, and attempted a fresh receipt
  without reopening the card. They were corrected to omit the original outcome
  and reopen through the real application boundary; no production checks were
  weakened. The focused intermediate result was 34 passed/one fixture failure;
  an intermediate broad result was 165 passed/one fixture failure.
- Final source envelope: **167 passed in 29.59s**
  (`.tmp/bt3-operator-final.xml`), covering operator/read models, authenticated card
  and run list/detail/filter endpoints, graph parity, real card repositories and
  existing API contracts. Negatives cover missing/substituted receipts, build
  scope, unsupported outcome schema, unpublished/failed run lifecycle, evidence
  loss, reopening and a new accepted receipt that cannot validate an older run.
- An additional integration proof passes **one test in 1.33s**
  (`.tmp/bt3-operator-readonly.xml`). Card, run-ledger and acceptance-store hashes
  remain identical across all four view routes. Replacing workspace code with a
  raising program does not rerun it or alter retained acceptance. This proves the
  documented retained-snapshot scope, not currency of current workspace contents.
- Final live source TCP/API proof:
  **`operator-live-a80f5415d7354afeb857a98a4b72ab80`**, Windows Python 3.13.11.
  Nine real app/server lifecycles cover done, guard-approved, archived, canceled,
  historical receiptless done, missing card/evidence, foreign build and accepted
  outside-view prerequisites. Every case deliberately carries source-attribution
  metadata marked verified. Only sufficient current retained acceptance yields
  verified run views. All nine unauthenticated requests are rejected; card detail
  correctly returns 404 for the missing card. Evidence deletion revokes both
  card and run acceptance on subsequent authenticated reads. Every server stops
  and runtime closes. The preceding live run
  `operator-live-7278774ecce841669bcb3c21bc5d07eb` also passed before the final scoped
  summary-text clarification; the stable report retains its diff history.
  Driver: `.tmp/bt3_operator_views_live.py`; report:
  `.tmp/bt3-operator-views-live/report.json`. These use prepared real increment-CLI
  acceptance, not model-produced output or independent source-attribution proof.
  No model inference is requested; `ORKET_DISABLE_SANDBOX=1`, no sandbox is created
  and the operator llama.cpp server is unchanged.
- Eleven touched Python paths pass Ruff; enforced dependency direction, docs
  hygiene and diff checks pass. Baseline collection succeeds, `release_ready=false`:
  **111 runtime Ruff issues, 3,425 missing labels among 4,484 test functions,
  75 oversized runtime files and 240 long functions**. The removed unused imports
  clear seven pre-existing lint findings. All 121 new Python files/functions meet
  400/70 limits. The worktree has **314 Git-visible changed paths**; original main
  is clean, index empty and six sealed outward fixture digests remain unchanged.

Architecture checklist: AC-01 through AC-06 pass for scoped application-owned
inspection, explicit projection inputs, shared receipt policy and unchanged
adapter effect ownership. AC-07/09 pass for observed retained acceptance and
read-only evidence preservation; cross-store publication remains partial under
BT-3. AC-08 introduces no new structured event schema. AC-10 is reflected in the
completion contract, card viewer spec, frontend contract, current authority and
operator-completion contract delta.

Not verified / remaining blockers or drift: no fresh full source suite, installed
matrix or provider-backed workload was run for this view change. Published outcome
metadata is checked against current receipts; this is not historical storage
authenticity or an atomic read across all stores. Remaining custom writers and
interrupted multi-store publication still require proof and repair. In particular,
`EpicRunFinalizer` currently completes the session and records success before
control-plane/run-ledger finalization; interruption at those boundaries needs a
behavioral counterexample and an authoritative recovery design. Automatic retry,
cross-installation resume and the full BT-3 gate remain unverified. Other execution
families need separately admitted completion proof. All 11 remaining findings and
later ordered slices stay open. No commit, tag, push, release or production
migration was performed.

Exact Git-visible paths touched by this operator views checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/architecture/CONTRACT_DELTA_OPERATOR_COMPLETION_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md`
- `orket/application/services/card_completion_outcome_service.py`
- `orket/application/services/execution_graph_service.py`
- `orket/application/services/operator_completion_service.py`
- `orket/core/contracts/repositories.py`
- `orket/interfaces/operator_view_models.py`
- `orket/interfaces/operator_view_support.py`
- `orket/interfaces/routers/cards.py`
- `orket/interfaces/routers/runs.py`
- `tests/integration/test_operator_completion_views.py`
- `tests/interfaces/test_api_operator_views.py`
- `tests/interfaces/test_operator_view_models.py`

Next at the operator views checkpoint: reproduce and repair interrupted completion publication, finish writer
coverage, then rebuild and prove the complete BT-3 envelope before BT-4.

### BT-3 atomic epic closeout and publication ordering checkpoint: 2026-09-12

Status: scoped repair implemented and verified; SR-07 and the whole BT-3 gate
remain open. The requested worktree remains
`C:\Source\Orket-architectural-truth`, branch `codex/architectural-truth-bt0`,
based on `112569206211aaa5a009a5e5ef7af43af545c744` (0.6.2).

Control-plane epic closeout now uses an explicit core transaction port and a
SQLite adapter that lends one connection to execution and record repositories.
Attempt, closeout step/effect, final truth and run state commit together. An abort
or cancellation before commit rolls them back. Standalone repository callers
retain their existing commit behavior. Independent processes serialize through
SQLite. Matching reentry validates retained references and the canonical journal
digest chain, then returns the existing records without rewriting evidence;
missing, conflicting or damaged history is rejected. Existing database locations
and schemas are unchanged.

Session completion and success-ledger publication now follow successful
control-plane and run-ledger finalization. Publication exceptions propagate with
their original cause; failed-workload finalization no longer attempts to downgrade
an accepted control-plane outcome. These are scoped ordering and control-plane
atomicity guarantees. They do not make session, run ledger, snapshot, success
ledger and filesystem publication one transaction.

Verification (path `primary`, result `success`; whole BT-3 `partial success`):

- Opening real SQLite counterexamples: **two failed in 1.33s**
  (`.tmp/bt3-publication-before.xml`). Actual abort triggers on control-plane and
  run-ledger finalization left a prematurely completed session and success row.
  A separate filesystem obstruction reproduced the masked-publication-error bug:
  **one failed in 0.85s** (`.tmp/bt3-publication-reclassification-before.xml`).
- Final targeted source envelope: **57 passed in 24.88s**
  (`.tmp/bt3-publication-final.xml`). This covers real aborts, cancellation while
  the transaction contains a completed attempt, concurrent matching reentry,
  conflicting terminal requests, missing closeout evidence, corrupted journal
  digest rejection and retained-byte preservation, plus existing card outcome,
  orchestrator, control-plane and run-ledger integration contracts.
- Separate repository/publication envelope: **50 passed in 12.36s**
  (`.tmp/bt3-publication-repositories.xml`). Execution/record repository behavior,
  checkpoint publication, application publication, turn closeout and card
  control-plane integration remain green.
- Native process proof: **two passed in 5.34s**
  (`.tmp/bt3-publication-process.xml`), also included in the final 57-case envelope.
  A real worker is killed immediately before or after the control-plane commit.
  A fresh reader sees either the complete prior state or complete committed
  closeout. Two independent new workers concurrently finish or reuse that same
  closeout, preserving final truth and exactly two effect journal entries. Owned
  workers are drained. This is control-plane closeout reentry only; the test
  explicitly observes that the session remains unfinished.
- Final live source standard runtime proof:
  **`canonical-live-18e5e42820774dc9b02ce279193597ff`**, Windows Python 3.13.11,
  selected llama.cpp at `http://127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`. The four-card requirements, design,
  implementation and review chain completes with eight actual model receipts,
  all four accepted card receipts and a done run ledger with sufficient retained
  completion outcome. Explicit `json_object` output and enforced local prompting
  are used without a prompt patch. The driver closes the runtime before writing
  the successful report, keeps the operator provider server and sets
  `ORKET_DISABLE_SANDBOX=1`; no sandbox is created. Driver:
  `.tmp/bt3_canonical_workload_live.py`; stable diff-ledger report:
  `.tmp/bt3-canonical-workload-live/report.json`.
- Thirteen touched Python paths pass Ruff; enforced dependency direction, docs
  project hygiene and diff checks pass.
  Baseline collection succeeds, `release_ready=false`: **110 runtime Ruff issues,
  3,425 missing labels among 4,489 test functions, 75 oversized runtime files and
  239 long functions**. The extracted closeout reduces the service size;
  the existing oversized record repository does not grow. All **127 new Python
  files** meet the 400-line file and 70-line function limits. There are **323
  Git-visible changed paths**. Original main is clean, the index is empty, and
  all six sealed outward fixture hashes match their retained digests.

Architecture checklist: AC-01/02/03/05/06 pass for the scoped explicit transaction,
application-owned closeout and adapter effect declaration. AC-04 remains partial:
existing closeout timestamps still use the service clock; explicit time input is
remaining D work and this extraction adds no new source. AC-07 passes at the
observed publication boundaries; wider interruption recovery remains BT-3 work.
AC-08/10 are reflected in the event taxonomy, completion contract, current
authority and epic closeout contract delta. AC-09 passes for retained closeout
references and non-rewriting reentry; full cross-store recovery remains partial.

Not verified / Remaining blockers or drift: no fresh full source suite or
installed Windows/Linux matrix was run for this repair. Later session, snapshot,
success-store and export failures can still leave partial publication. Full
orchestration restart is not the tested control-plane-only reentry: existing
setup may reset cards or create another invocation. An authoritative publication
recovery design, its crash/restart proof, remaining custom writers,
cross-installation resume and pre-relocation contract snapshots remain required
before the whole BT-3 gate can pass. This does not establish historical storage
authenticity or completion proof for other execution families. All 11 remaining
findings and later ordered slices remain open. No commit, tag, push, release or
production migration was performed.

Exact Git-visible paths touched by this publication checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_CLOSEOUT_PUBLICATION_BT3_2026-09-12.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/core/contracts/control_plane_transaction.py`
- `orket/adapters/storage/sqlite_connection.py`
- `orket/adapters/storage/async_control_plane_record_repository.py`
- `orket/adapters/storage/async_control_plane_execution_repository.py`
- `orket/adapters/storage/control_plane_transaction.py`
- `orket/application/services/cards_epic_control_plane_service.py`
- `orket/application/services/cards_epic_closeout.py`
- `orket/runtime/execution/execution_pipeline.py`
- `orket/runtime/execution/epic_run_finalize.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `tests/integration/test_epic_completion_publication.py`
- `tests/helpers/epic_publication_worker.py`
- `tests/integration/test_epic_closeout_process.py`

Next at the publication ordering checkpoint: prove and repair remaining multi-store publication recovery and custom
writers, then refresh the complete source/installed BT-3 envelope before BT-4.

### BT-3 retained epic publication recovery checkpoint: 2026-09-12

Status: prepared publication recovery is implemented and verified. SR-07, BT-3
and all later required slices remain active in the requested worktree,
`C:\Source\Orket-architectural-truth`, branch `codex/architectural-truth-bt0`.

`EpicPublicationService` retains an `epic_publication.v1` plan after control-plane,
summary and current export preparation, before final run-ledger publication.
The new core port and SQLite adapter retain immutable publication arguments,
request binding, transcript and monotonic progress in
`<runtime_db>.epic-publications.sqlite3`. Each step serializes through a journal
transaction, uses its original repository and verifies readback before advancing.
Committed matching rows are reused, retaining their values and timestamps. This
covers ledger, session, snapshot and success publication; it is not one transaction
across those stores.

Standard runtime reentry now checks the journal before card reset or another
workload invocation. Matching same-session reentry finishes publication or returns
verified retained history. Fresh work uses a new session ID. Request drift,
changed acceptance, damaged journal history and missing completed effects are
rejected without resealing. A failed workload still raises after recovered failure
publication. Existing finalized invocations without a plan are refused before
reset; no historical plan is invented. Readbacks leave missing runtime tables
missing. Application publication owns completion events; interruption can repeat
an observation, so this does not claim exactly-once event delivery.

Verification (path `primary`, result `success`; whole BT-3 `partial success`):

- Opening real-store restart counterexamples: **four failed in 3.48s**
  (`.tmp/bt3-publication-recovery-before.xml`). Actual SQLite aborts at ledger,
  session, snapshot and success writes caused fresh runtime reentry to redispatch
  accepted work. The repaired opening envelope passed 10 tests.
- The first wider envelope found 15 protocol timestamp-ordering failures and one
  old same-session/new-invocation expectation. Ledger time is now retained after
  summary/export preparation; protocol monotonicity remains enforced. The
  intentional reentry contract test now also proves a new session creates a new
  invocation. An isolated session double was corrected to carry the real Started
  lifecycle token after strict readback checks exposed its missing state.
- Source envelope: **114 passed in 74.16s**
  (`.tmp/bt3-publication-recovery-final.xml`), covering native restart, completion
  publication, card outcomes, failed/incomplete outcomes, protocol and dual-write
  ledgers, backend selection and session repositories. Final missing-table and
  conflict proof: **10 passed in 11.34s**
  (`.tmp/bt3-publication-recovery-missing-tables.xml`), including the subsequently
  added run-ledger table-loss case. These are overlapping envelopes, not 124
  distinct tests. The isolated collaborator test is structural composition proof.
- Native process tests kill a real worker after each of the four effects commits
  but before journal progress advances. Two independent new workers reenter via
  the standard pipeline and finish publication without dispatch. Already published
  rows, timestamps and control-plane identity remain unchanged; one snapshot and
  one success row remain. All owned workers are drained. Negative reentry covers
  request/acceptance drift, unsupported schema, damaged digest, deleted plan,
  missing success and all four deleted runtime tables. Rejection preserves the
  damaged database and journal bytes. Native proof uses prepared real CLI
  acceptance rather than model inference.
- Final live source recovery: **`publication-live-12b4d86df29249429c111a97a5b2e29a`**,
  Windows Python 3.13.11, selected llama.cpp at `http://127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`. Four cards reach accepted completion;
  an actual SQLite trigger then aborts success publication. A fresh runtime using
  the same request finishes publication with eight model receipts before and
  after, unchanged model-receipt hashes and unchanged run ledger. Both runtimes
  close. Driver: `.tmp/bt3_publication_recovery_live.py`; stable diff-ledger report:
  `.tmp/bt3-publication-recovery-live/report.json`. A separate normal canonical
  live run, `canonical-live-f9c56fab09c34f87a99f0e4d2a74a0c1`, also passed.
  These use explicit object-schema output, enforced local prompting, no prompt
  patch and `ORKET_DISABLE_SANDBOX=1`. No sandbox is created; the operator provider
  server remains running.
- Thirteen touched Python paths pass Ruff; enforced dependency direction, docs
  project hygiene and diff checks pass.
  All **133 new Python files** meet the 400-line file and 70-line function limits.
  The finalizer shrinks to 310 lines; the already oversized repository shrinks
  from 556 to 555 lines. Baseline collection succeeds, `release_ready=false`:
  **110 runtime Ruff issues, 3,425 missing labels among 4,493 test functions,
  74 oversized runtime files and 239 long functions**. The requested worktree
  contains **331 Git-visible changed paths**. Original main remains clean, the
  index is empty and all six sealed outward fixture digests remain unchanged.

Architecture checklist: AC-01/02/03/05/06 pass for the scoped core journal port,
application publication authority and declared storage effects. AC-04 remains
partial under D: existing runtime timestamps are retained inputs for reentry but
their first creation still uses the service clock. AC-07 passes for confirmed
publication and failure-preserving recovery. AC-08/10 are reflected in the
completion spec, event taxonomy, durable-path authority, runbook and contract
delta. AC-09 passes for the observed prepared-plan restart boundaries; upstream
preparation and cross-installation resume remain partial.

Not verified / Remaining blockers or drift: no fresh full source suite, installed
matrix or native Linux restart proof for this change. Preparation still precedes
journal retention: control-plane, summary and export interruption require their
own retained inputs and recovery design, including ambiguous remote effects.
The current Gitea export callback retains its existing best-effort behavior; this
checkpoint does not prove remote export completion. Arbitrary custom-writer
bindings, cross-installation relocation, pre-relocation contract snapshots and
the full BT-3 envelope remain required. This journal does not establish independent
historical authenticity or globally atomic observations. All 11 remaining findings
and later ordered slices stay open. No commit, tag, push, release or production
migration was performed.

Exact Git-visible paths touched by this recovery checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_PUBLICATION_RECOVERY_BT3_2026-09-12.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/core/contracts/epic_publication.py`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/adapters/storage/async_repositories.py`
- `orket/application/services/epic_publication_service.py`
- `orket/runtime/execution/epic_run_finalize.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/epic_run_types.py`
- `orket/runtime/execution/execution_pipeline.py`
- `tests/integration/test_epic_publication_recovery.py`
- `tests/integration/test_epic_publication_recovery_process.py`
- `tests/helpers/epic_publication_recovery_worker.py`
- `tests/runtime/test_epic_run_orchestrator.py`
- `tests/application/test_execution_pipeline_cards_epic_control_plane.py`

Next at that checkpoint: extend retained preparation and recovery across the earlier closeout,
summary and export boundaries, finish custom-writer coverage, then refresh the
complete source/installed BT-3 envelope before BT-4.

### BT-3 retained preparation and export uncertainty checkpoint: 2026-09-12

Status: upstream preparation recovery and uncertain-export refusal are implemented
and verified within the scope below. SR-07, whole BT-3 and all later required
slices remain active in the requested worktree, branch `codex/architectural-truth-bt0`.

Application-owned `EpicPreparationService` retains original inputs before
control-plane closeout, protocol receipts, summary and export. The additive
`epic_preparation.v1` record uses the existing publication journal. Local stage
outputs and monotonic progress survive restart; preparation completion and ready
publication-plan insertion commit together. Standard reentry resumes preparation
before resetting accepted cards or dispatching work. Full epic/team/environment
definitions and build identity now bind the request; changed or insufficient old
bindings reject reentry. Ready publication still verifies each original store.

Export settings are frozen without authentication secrets, credential-bearing URLs
are rejected and the standard flow supplies a retained export date. Existing sync
Gitea setup calls now run through `asyncio.to_thread`. Enabled exports commit an
attempt marker before the callback; fresh reentry without a retained result raises
`E_EPIC_EXPORT_OUTCOME_UNCERTAIN`. Receipt, summary-write and export failures now
propagate. Explicit degraded summary generation remains separately identified.
Unknown remote outcomes require receipt recovery/reconciliation; this checkpoint
neither retries them nor claims remote completion.

Verification (path `primary`, result `success`; whole BT-3 `partial success`):

- Opening real-store preparation counterexamples: **3 failed in 2.70s**
  (`.tmp/bt3-preparation-before.xml`). Closeout, receipt and summary interruptions
  previously caused redispatch or missing recovery evidence. The repaired source
  envelope passes **131 tests in 86.82s** (`.tmp/bt3-preparation-final.xml`).
  Final error envelope: **5 passed in 4.40s** (`.tmp/bt3-preparation-errors.xml`),
  including the subsequently added enabled-export lost-reply case. These overlap.
- Native process envelope: **9 passed in 28.97s**
  (`.tmp/bt3-preparation-process.xml`). Owned workers are killed after actual local
  effects at closeout, receipts, summary, disabled export and all four publication
  stores; independent new workers finish standard reentry without redispatch.
  An enabled-export probe performs a real local file effect and loses its result;
  two fresh workers refuse uncertain reentry with unchanged effect and database
  rows. All owned workers are drained. This probe does not exercise Gitea transport.
- The wider envelope exposed an old different-build/same-session expectation.
  The corrected contract rejects changed build identity and full epic definitions;
  refusal preserves journal/database bytes. Fresh sessions remain supported.
  Isolated collaborator tests establish structural composition only.
- Final live source standard runtime recovery:
  **`publication-live-03a5e8f5e5ca4a288fd72e1dd57f70a7`**, Windows Python 3.13.11,
  llama.cpp at `http://127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`. Four cards achieve actual acceptance;
  a directory obstructing `run_summary.json` causes the real write to fail.
  After removing that obstruction, a fresh runtime completes preparation and
  publication. Eight model receipts and their hashes remain unchanged, as does
  control-plane invocation identity. The ledger advances from running to done;
  session completion and success are confirmed. Both runtimes close. Driver:
  `.tmp/bt3_publication_recovery_live.py summary`; stable diff-ledger report:
  `.tmp/bt3-publication-recovery-live/report.json`. Explicit object-schema output,
  enforced local prompting, no prompt patch and `ORKET_DISABLE_SANDBOX=1` apply.
  No sandbox is created; the operator provider stays running.
- Seventeen touched Python paths pass Ruff. Enforced dependency direction, docs
  hygiene and diff checks pass. All **135 new Python files** meet the 400-line
  file and 70-line function limits. The finalizer shrinks to **186 lines**.
  The refreshed baseline collects successfully with `release_ready=false`:
  **110 runtime Ruff issues, 3,422 missing labels among 4,498 test functions,
  74 oversized runtime files and 239 long functions**. The worktree contains
  **338 Git-visible changed paths**. Original main is clean, the index is empty,
  all six sealed fixture digests match and every original plan section remains.

Architecture checklist: AC-01/02/03/05/06 pass for the explicit core records,
application preparation authority and declared adapter effects. AC-04 passes for
new preparation timing and export date supplied as explicit retained inputs;
remaining runtime clock debt stays under D. AC-07 passes for the scoped failure
and uncertainty boundaries. AC-08/10 are reflected in the spec, authority, runbook,
taxonomy and contract delta. AC-09 remains partial: local retained-input recovery
passes, while initial retention, custom writers, uncertain remote reconciliation
and cross-installation recovery remain required under BT-3.

Not verified / Remaining blockers or drift: no fresh full source suite, installed
Windows/Linux matrix or native Linux restart proof for these changes. Read-only
environment inspection shows Gitea export disabled and target/user/password
unconfigured, so no actual Gitea flow was attempted. Local export probes establish
only the uncertainty boundary. The workload-outcome to initial preparation-retention
gap, receipt recovery/reconciliation, arbitrary custom writers, cross-installation
relocation and pre-relocation contract snapshots remain open. No independent
historical authenticity, globally atomic observations or exactly-once external
effects are claimed. All 11 remaining findings and later ordered slices stay open.
No commit, tag, push, release or production migration was performed.

Exact Git-visible paths touched by this preparation checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_PREPARATION_RECOVERY_BT3_2026-09-12.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/core/contracts/epic_publication.py`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/application/services/epic_publication_service.py`
- `orket/application/services/epic_preparation_service.py`
- `orket/adapters/vcs/gitea_artifact_exporter.py`
- `orket/runtime/execution/epic_run_finalize.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/execution_pipeline.py`
- `orket/runtime/execution/execution_pipeline_ledger_events.py`
- `orket/runtime/execution/execution_pipeline_run_summary.py`
- `tests/integration/test_epic_preparation_recovery.py`
- `tests/integration/test_epic_publication_recovery.py`
- `tests/integration/test_epic_publication_recovery_process.py`
- `tests/helpers/epic_publication_recovery_worker.py`
- `tests/runtime/test_epic_run_orchestrator.py`
- `tests/application/test_execution_pipeline_run_ledger.py`
- `tests/adapters/test_gitea_artifact_exporter.py`

Next at that checkpoint: close the initial preparation-retention gap and uncertain-export receipt
recovery, finish custom-writer coverage, then refresh the complete source/installed
BT-3 envelope before BT-4.

### BT-3 retained workload outcome checkpoint: 2026-09-12

Status: retained workload termination now bridges completion inspection and the
first preparation write. Unknown termination refuses redispatch. SR-07, whole
BT-3 and all later required gates remain active in the requested worktree.

`EpicWorkloadOutcomeService` retains `epic_workload_outcome.v1` in the existing
publication journal before asynchronous finalization work. It captures original
request/policy/export binding, artifacts, observation time, transcript, effective
configuration and observed return or failure. A returned workload is not itself
accepted completion. Matching reentry resumes inspection/preparation from those
inputs, keeps current acceptance gates, and preserves failure reason/class.
Journal checks serialize recovery decisions with preparation progress. Completed
preparation/publication can advance while another caller enters recovery.

A started invocation without any retained outcome/preparation/publication record
now raises `E_EPIC_WORKLOAD_OUTCOME_UNCERTAIN` before card reset or dispatch.
Surviving accepted cards cannot prove whether the workload returned or failed.
This covers process loss/cancellation before outcome retention without silently
reexecuting work. Automatic takeover and reconciliation of that uncertain owner
remain required work; this is not a claim that interrupted execution resumed.

Verification (path `primary`, result `success`; whole BT-3 `partial success`):

- Opening counterexamples: **3 failed in 2.20s** (`.tmp/bt3-outcome-before.xml`).
  Actual inspection obstruction, cancellation after accepted work, and a SQLite
  abort on first preparation insertion all allowed restart to redispatch.
- Source regression envelope: **144 passed in 129.02s**
  (`.tmp/bt3-outcome-final.xml`), covering the new outcome boundaries and existing
  preparation, publication, closeout, card completion, protocol/dual-write ledger
  and backend paths. An isolated collaborator test initially omitted issue
  definitions from its serialized epic; the double now supplies them. That test
  remains structural composition proof.
- Final snapshot/transcript and native envelope: **22 passed in 51.58s**
  (`.tmp/bt3-outcome-snapshot.xml`), after retaining the effective configuration
  separately from the original request. Recovery preserves a nonempty transcript
  and configuration captured after setup. The envelopes overlap. An earlier
  native envelope passed 16 tests before the final six damage cases/refinement.
- Native workers stop after the actual outcome commit and before preparation;
  two fresh workers complete standard reentry without workload dispatch. A retained
  failure after card acceptance remains failed in both new workers. Death before
  workload return leaves uncertainty; reentry preserves running rows and publishes
  no success. Every owned child is drained. Negative tests reject damaged digest,
  unsupported schema, missing outcome, changed request and missing/conflicting
  run evidence with unchanged database/journal bytes.
- Final live source recovery: **`publication-live-c44e6665389b47308223da53db59f370`**,
  Windows Python 3.13.11, llama.cpp at `http://127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`. The canonical four-card workload
  satisfies actual acceptance; a SQLite trigger aborts the first preparation
  insert. A fresh runtime recovers from the retained outcome and reaches done,
  session completion and success. Eight model receipts and their hashes remain
  unchanged; control-plane invocation identity is unchanged. Both runtimes close.
  Driver: `.tmp/bt3_publication_recovery_live.py preparation`; stable diff-ledger
  report: `.tmp/bt3-publication-recovery-live/report.json`. An earlier live run
  also passed before the effective-snapshot refinement. Explicit object-schema
  output, enforced local prompting, no prompt patch and `ORKET_DISABLE_SANDBOX=1`
  apply. No sandbox is created; the operator provider remains running.
- Ten touched Python paths pass Ruff; enforced dependency direction, docs hygiene
  and diff checks pass. All **137 new Python files** meet 400-line file and 70-line
  function limits. The finalizer is 193 lines and the orchestrator 363 lines.
  Refreshed baseline: `collection_ok=true`, `release_ready=false`, **110 runtime
  Ruff issues, 3,422 missing labels among 4,502 test functions, 74 oversized runtime
  files and 239 long functions**. The worktree has **341 Git-visible changed paths**;
  original main is clean, the index is empty and all six sealed digests match.

Architecture checklist: AC-01/02/03/05/06 pass for the explicit core outcome,
application retention service and existing declared journal adapter. AC-04 passes
for retained observation time through the injected clock; wider clock debt stays
under D. AC-07 passes for distinguishing termination, acceptance, failure and
uncertainty. AC-08/10 are reflected in the spec, authority, runbook, taxonomy and
contract delta. AC-09 passes at the observed retained-outcome boundary and remains
partial for uncertain owner recovery, custom writers and cross-installation work.

Not verified / Remaining blockers or drift: no fresh full source suite, installed
Windows/Linux matrix or native Linux restart proof for this change. Gitea remains
unconfigured; actual remote acceptance and uncertain-export receipt reconciliation
are still required. Workload termination lost before the outcome commit is refused,
not reconstructed; owner recovery/fencing remains open. Initial admission races,
arbitrary custom writers, cross-installation relocation, pre-relocation contract
snapshots and the full BT-3 acceptance envelope remain required. No independent
historical authenticity, global transaction or exactly-once effects are claimed.
All 11 remaining findings and later ordered gates stay open. No commit, tag, push,
release or production migration was performed.

Exact Git-visible paths touched by this outcome checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_WORKLOAD_OUTCOME_BT3_2026-09-12.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/core/contracts/epic_publication.py`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/application/services/epic_publication_service.py`
- `orket/application/services/epic_workload_outcome_service.py`
- `orket/runtime/execution/epic_run_finalize.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `tests/integration/test_epic_outcome_recovery.py`
- `tests/helpers/epic_publication_recovery_worker.py`
- `tests/integration/test_epic_publication_recovery_process.py`
- `tests/runtime/test_epic_run_orchestrator.py`

Next at that checkpoint: complete uncertain-export receipt recovery/reconciliation and custom-writer
coverage; retain explicit workload uncertainty pending owner recovery. Refresh the
complete source/installed BT-3 envelope before BT-4 and later gates.

### BT-3 retained Gitea export receipt checkpoint: 2026-09-12

Status: confirmed remote exports now recover through retained commit evidence.
Unconfirmed attempts still refuse automatic retry. Whole BT-3/SR-07 and all later
required gates remain active in the requested worktree.

Epic preparation now retains `gitea_export_intent.v1` in `epic_preparation.v2`
before remote repository creation or push. The intent binds the original run,
effective non-secret target/workspace/author settings, captured payload, commit,
subtree and run path. Only the claiming call dispatches the exact commit. Standard
reentry confirms remote branch ancestry, subtree and manifest identity without
another push or workload dispatch; missing evidence retains uncertainty. Receipts
use immutable commit URLs. Payload paths include a run-ID hash suffix, and source
symlinks/reparse points reject preparation, including top-level Windows junctions.

Git and HTTP execution are asynchronous. Existing process cleanup helpers moved
to the shared execution adapter; the governed-agent caller imports that authority
directly. This extraction does not close BT-4 descendant ownership or fencing.
Preparation v1 and old insufficient bindings reject without digest rewriting or
intent backfill. The durable contract is `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`;
the same-change delta records migration, rollback and direct-caller implications.

Verification (path `primary`, result `success`; whole BT-3 `partial success`):

- Opening remote counterexample: **1 failed in 7.80s**
  (`.tmp/bt3-gitea-recovery-before.xml`). A real successful push with a lost local
  result could not recover. Owned localhost Gitea teardown was confirmed.
- Source regression envelope: **155 passed in 158.42s**
  (`.tmp/bt3-gitea-recovery-final.xml`). It includes actual Gitea push/recovery,
  native death after push and before dispatch, concurrent fresh workers, retained
  payload identity and substitution rejection, existing card/outcome/preparation/
  publication/ledger paths, and the shared process helper's governed-agent caller.
  Native death after push recovers one remote commit; death before push preserves
  the journal/database and publishes no success. Structural collaborators remain
  fixtures, not live model proof.
- Final review exposed a top-level Windows junction escaping the new descendant
  checks: **1 failed in 2.53s** (`.tmp/bt3-gitea-junction-before.xml`). The repaired
  boundary rejects before remote access and preserves the junction target. Final
  exporter envelope: **13 passed in 37.53s** (`.tmp/bt3-gitea-junction-final.xml`),
  including all four actual Gitea cases after this refinement. These envelopes
  overlap; the 155-case envelope preceded the final junction check.
- An earlier envelope had two proof failures: Gitea 1.25.4's legacy contents API
  panicked in optional commit metadata, and an immediate commits API read returned
  409 while its empty-repository projection lagged the Git push. Independent payload
  proof now uses the supported `contents-ext` file-content response, and API proof
  waits at most 20 seconds on that 409 projection. Neither retries a mutation or
  weakens content/commit assertions. The runtime confirms through Git. The observed
  panic and endpoint distinction are supported by Gitea's versioned
  [contents implementation](https://raw.githubusercontent.com/go-gitea/gitea/v1.25.4/services/repository/files/content.go)
  and [API handlers](https://raw.githubusercontent.com/go-gitea/gitea/v1.25.4/routers/api/v1/repo/file.go).
- Final live source run: **`publication-live-8a0ff62859814265a72417f60e6913b7`**,
  Windows Python 3.13.11, llama.cpp at `http://127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, actual disposable Gitea **1.25.4**.
  The canonical four-card workload satisfies acceptance, pushes commit
  `36748ff9a0fd625c5cf44d262998c34ac544082d`, then loses its local export result.
  A fresh runtime confirms that commit and reaches done/session success with eight
  unchanged model receipts and unchanged control-plane invocation identity. The
  independent remote commit count stays one. Both runtimes close; the owned Gitea
  container and anonymous volumes are removed before the report is written.
  Driver: `.tmp/bt3_publication_recovery_live.py gitea`; stable diff-ledger report:
  `.tmp/bt3-publication-recovery-live/report.json`. This final run includes the
  junction refinement. Explicit object-schema output, enforced local prompting,
  no prompt patch and `ORKET_DISABLE_SANDBOX=1` apply.
- The 17 touched Python paths pass Ruff. Enforced dependency direction, docs
  hygiene and diff checks pass. All **142 new Python files** meet 400/70-line limits.
  Refreshed baseline: `collection_ok=true`, `release_ready=false`, **110 runtime
  Ruff issues, 3,422 missing labels among 4,507 test functions, 74 oversized runtime
  files and 238 long functions**. The worktree has **350 Git-visible changed paths**;
  original main is clean, the index is empty and all six sealed fixture hashes match.

Architecture checklist: AC-01/02/03/05/06 pass for the explicit core intent,
application admission and declared adapters. AC-04 passes for retained export time
and author inputs; broader timing debt stays under D/BT-4. AC-07 passes at the
verified remote commit boundary, including refusal to infer success from a marker.
AC-08/10 are reflected in the spec, authority, runbook, taxonomy and delta. AC-09
passes for retained commit confirmation and remains partial for unconfirmed-owner
recovery, custom writers and cross-installation work.

Not verified / Remaining blockers or drift: no fresh full source suite, installed
Windows/Linux matrix or native Linux Gitea recovery proof for this change. Actual
Gitea proof uses an explicitly owned localhost server, not the production service.
Unconfirmed workload/export owner recovery and fencing, initial admission races,
custom-writer coverage, cross-installation relocation and pre-relocation contract
snapshots remain required before the full BT-3 gate. The source tests require
`ORKET_RUN_GITEA_EXPORT_ACCEPTANCE=1`; their default skip is not remote proof.
No independent historical authenticity, global atomicity or arbitrary-writer
exactly-once effects are claimed. All 11 remaining findings and later gates stay
open. No source commit/tag/push, release or production migration was performed;
actual test artifact pushes went only to the disposable localhost instances.
Production `vibe-rail-gitea` and the operator's llama.cpp server remain untouched.

Exact Git-visible paths touched by this Gitea receipt checkpoint (27):

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_GITEA_EXPORT_RECEIPT_BT3_2026-09-12.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`
- `orket/adapters/execution/process_lifecycle.py`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/adapters/vcs/gitea_artifact_exporter.py`
- `orket/adapters/vcs/gitea_export_git.py`
- `orket/application/services/epic_preparation_service.py`
- `orket/core/contracts/epic_publication.py`
- `orket/core/contracts/gitea_export.py`
- `orket/extensions/governed_agent_invoker.py`
- `orket/extensions/governed_agent_process.py`
- `orket/runtime/execution/execution_pipeline.py`
- `orket/runtime/execution/execution_pipeline_run_summary.py`
- `tests/adapters/test_gitea_artifact_exporter.py`
- `tests/helpers/epic_publication_recovery_worker.py`
- `tests/helpers/gitea_server.py`
- `tests/integration/test_epic_preparation_recovery.py`
- `tests/integration/test_gitea_epic_export_recovery.py`
- `tests/runtime/test_epic_run_orchestrator.py`

The ignored live driver above was also updated; rerunnable reports remain at their
existing stable paths. The full Git-visible inventory above includes prior slices.

Next at that checkpoint: settle unconfirmed workload/export owner recovery and admission races, then
complete custom-writer/cross-installation proof and refresh the complete source/
installed BT-3 envelope before BT-4 and later gates.

### BT-3 run and resource admission checkpoint: 2026-09-12

Status: standard entries now reserve their resources before epic initialization.
Competing same-session and shared-resource entries reject before card writes.
Interrupted claims retain uncertainty. Whole BT-3/SR-07 and later gates stay open.

`EpicAdmissionService` retains `epic_run_admission.v1` in the existing publication
journal before session creation, card reset/reconciliation, control-plane start or
workload dispatch. Claim and conflict checking commit together. The immutable
record binds the original request/export settings, injected owner identity/time,
canonical workspace, build and declared card IDs. Active records sharing any of
those resources exclude new standard entries through the selected journal;
disjoint resources remain admissible. Admission is not evidence of dispatch or
workload return, and a stopped process does not release its claim.

New run artifacts carry the original admission digest/owner reference. Preparation
and publication validate that reference before further completion effects. Only
complete publication with verified effect readback releases the reservation;
the admission history remains retained. New admission checks validate released
records against their completed publication, so a lost publication record cannot
authorize another writer. Retained history is streamed and checked before conflict
filtering; this checkpoint does not establish capacity at large history sizes.
Older publication without an admission is not backfilled. The durable semantics
and delta are in `CARD_COMPLETION_ACCEPTANCE_CONTRACT.md` and
`CONTRACT_DELTA_EPIC_RUN_ADMISSION_BT3_2026-09-12.md`.

Verification (path `primary`, result `success`; whole BT-3 `partial success`):

- Opening counterexamples: **2 failed in 3.91s** (`.tmp/bt3-admission-before.xml`).
  While one standard runtime paused before card initialization, a same-session
  caller or another session completed competing work instead of being refused.
- Admission boundaries: **12 passed in 15.82s**
  (`.tmp/bt3-admission-boundaries.xml`). They separately exercise workspace, build
  and card conflicts; disjoint work; missing/damaged/prematurely released evidence;
  verified release; retained history; and lost-publication refusal. Native workers
  observe a claim while its owner is alive, then after killing it before the run
  ledger exists. Three fresh observers refuse initialization; journal bytes and
  logical runtime rows remain unchanged. Every owned worker is drained.
- Final source regression envelope: **168 passed in 169.27s**
  (`.tmp/bt3-admission-final.xml`), covering admission plus card completion,
  outcome/preparation/publication recovery, control-plane closeout, ledger modes,
  Gitea recovery and the existing process-helper consumer. An earlier 36-case
  overlapping envelope passed after correcting the isolated runtime-input fixture
  to supply owner/time inputs. Collaborator doubles remain structural proof.
- The first broad run passed 167 tests and failed one independent payload read:
  Gitea's `contents-ext` API also returned HTTP 500. Its precise cause was not
  established. The payload proof now reads the retained commit directly from the
  owned server's Git repository, independently of Orket's adapter. It compares
  content including leading/trailing whitespace; the helper preserves that output.
  The isolated server-side read passed, followed by the complete 168-case envelope.
  This does not claim that Gitea's content API was repaired.
- Final live source admission/recovery run:
  **`publication-live-e824df2758224a1d95adc2c2f415d3c5`**, Windows Python 3.13.11,
  llama.cpp at `http://127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, disposable Gitea **1.25.4**. A second
  standard runtime was refused at the retained resource claim before any model
  receipt or competing session existed. The owner then satisfied all four cards,
  pushed commit `110c431707c9e030b6472fa98afe56ee2c511421`, and lost its local export
  result. Its admission remained active. Fresh runtime recovery confirmed the
  remote receipt and released that same admission only after verified publication.
  Eight model receipts/hashes and control-plane invocation identity stayed unchanged;
  the remote commit count stayed one. All three runtimes closed, and the owned
  Gitea container/anonymous volumes were removed before the report was written.
  Driver: `.tmp/bt3_publication_recovery_live.py gitea`; stable diff-ledger report:
  `.tmp/bt3-publication-recovery-live/report.json`. Explicit object-schema output,
  enforced local prompting, no prompt patch and `ORKET_DISABLE_SANDBOX=1` apply.
- All 13 touched Python paths pass Ruff; dependency direction, docs hygiene and
  diff checks pass. All **144 new Python files** remain within 400/70-line limits.
  The orchestrator remains 369 lines. Refreshed baseline: `collection_ok=true`,
  `release_ready=false`, **110 runtime Ruff issues, 3,422 missing labels among
  4,512 test functions, 74 oversized runtime files and 238 long functions**.
  The worktree has **353 Git-visible changed paths**. Original main is clean,
  the index is empty and the six sealed fixture hashes still match.

Architecture checklist: AC-01/02/03/05/06 pass for core admission records,
application resource policy and the declared journal adapter. AC-04 passes for
injected owner/time inputs and retained request identity. AC-07 passes for refusal
before competing initialization and release after confirmed publication. Existing
event fields are unchanged (AC-08); source-of-truth documents and the contract delta
record the new authority (AC-10). AC-09 passes for the retained admission reference
and remains partial for uncertain-owner recovery and broader writer coordination.

Not verified / Remaining blockers or drift: no fresh full source suite or installed
Windows/Linux Python matrix, and no native Linux admission proof. The gate applies
to standard entries sharing the selected journal. It does not fence separate
journals that share a workspace, arbitrary custom writers, surviving descendants,
or owners granted takeover. Interrupted admission/workload/export owner recovery
and fencing remain required; no retry permission is inferred from process death,
elapsed time or absent receipts. Cross-installation relocation, pre-relocation
contract snapshots, capacity proof and the complete BT-3 envelope remain required.
All 11 remaining findings and later gates stay active. No source commit/tag/push,
release or production migration was performed. Test pushes were confined to owned
localhost Gitea; production Gitea and the operator's llama.cpp server were untouched.

Exact Git-visible paths touched by this admission checkpoint (21):

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_RUN_ADMISSION_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/application/services/epic_admission_service.py`
- `orket/application/services/epic_preparation_service.py`
- `orket/application/services/epic_publication_service.py`
- `orket/core/contracts/epic_publication.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/epic_run_support.py`
- `orket/runtime/execution/epic_run_types.py`
- `tests/helpers/epic_publication_recovery_worker.py`
- `tests/helpers/gitea_server.py`
- `tests/integration/test_epic_run_admission.py`
- `tests/integration/test_gitea_epic_export_recovery.py`
- `tests/runtime/test_epic_run_orchestrator.py`

The ignored live driver above was also updated. The full Git-visible inventory
above includes the preserved earlier slices.

Next at that checkpoint: implement evidenced owner recovery/fencing for interrupted admissions,
workloads and exports; coordinate separately configured journals sharing resources.
Complete custom-writer/cross-installation proof and refresh the full source/installed
BT-3 envelope before advancing to BT-4 and the remaining ordered gates.

### BT-3 recovery before initialization checkpoint: 2026-09-12

Status: explicit replacement of an uninitialized admission owner passes scoped
source, native-process and live-provider proof. Whole BT-3/SR-07 stays open.

The canonical Python `run_card` epic entry accepts a bound
`epic_admission_recovery_request.v1` with an explicit matching session ID, expected
owner/generation/claim digest, stable request ID, operator and reason references.
`EpicAdmissionService` transfers only an active uninitialized claim with matching
original request/export settings and no retained outcome/preparation/publication.
Admission v2 retains owner generations and the complete recovery history, including
the common `OperatorActionRecord`, in the existing journal transaction. No failed
control-plane attempt is invented before initialization. History validates each
predecessor claim and the corresponding operator action.

Both fresh and replacement callers must atomically consume initialization before
session/card/control-plane writes. A paused original owner fails that comparison.
Identical recovery requests observe the existing replacement and cannot initialize
twice; changed or superseded requests reject. Later retained publication may resume
through the same request without workload redispatch. Once initialization is
marked, this operation refuses transfer even if no ledger exists. Admission v1
cannot establish that precondition and is rejected without marker/digest backfill.
The accepted semantics and delta are in `CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
and `CONTRACT_DELTA_EPIC_ADMISSION_RECOVERY_BT3_2026-09-12.md`.

Verification (path `primary`, result `success`; whole BT-3 `partial success`):

- Opening request failed with the unsupported `admission_recovery` argument:
  **1 failed in 1.06s**, `.tmp/bt3-owner-recovery-before.xml`. This establishes
  absence of the explicit operation, not a pre-existing stale-owner fence failure.
- Final recovery module: **16 passed in 11.31s**,
  `.tmp/bt3-owner-recovery-native.xml`. It exercises actual journal transactions,
  composed runtime initialization, duplicate/stale/superseded requests, damaged
  history with a recomputed outer digest, unsupported admission version and refusal
  after the initialization marker. Two native replacement workers compete after
  the original is killed or while it remains paused. An independent dispatch file
  contains one entry; retained session/run/success rows contain one completed run.
  Resuming the original process yields a fence error without another dispatch or
  changed runtime rows. Owned processes are drained. Workload execution in these
  deterministic integration cases uses acceptance fixtures, not a live model.
- Final source envelope: **184 passed in 180.49s**,
  `.tmp/bt3-owner-recovery-final.xml`, across 21 modules covering card completion,
  admission, outcome/preparation/publication recovery, closeout, ledger modes,
  actual disposable Gitea and the existing process-helper consumer. Earlier
  14/22/183-case passes precede the final native paused-owner variant and do not
  replace this final result. Collaborator doubles are structural proof only.
- Final live canonical Python source run:
  **`publication-live-b78bcfa094864e77bb83225dc410b5cc`**, Windows Python 3.13.11,
  llama.cpp `http://127.0.0.1:8080/v1`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, disposable Gitea **1.25.4**.
  A competing session was refused with zero model receipts. Explicit replacement
  of the paused original then completed all four cards. The original failed its
  fence before initialization. The replacement pushed commit
  `4f132a923c8f689fe39164054284f6e8d49794b3` and lost its local export result.
  Repeating the identical operator request through a fresh runtime confirmed that
  commit and completed publication. Eight model receipts and their hashes, the
  control-plane invocation and the single remote commit remained unchanged;
  the run ledger advanced to completion. Generation 2 and its one recovery action
  remained retained after verified release. All three runtimes closed and the
  owned Gitea container/anonymous volumes were removed in the proof path.
  Driver `.tmp/bt3_publication_recovery_live.py gitea`; stable diff-ledger report
  `.tmp/bt3-publication-recovery-live/report.json`. Explicit object-schema output,
  enforced local prompting, no prompt patch and `ORKET_DISABLE_SANDBOX=1` apply.
- Targeted Ruff passes for all nine Python paths. The enforced transition-policy
  dependency check passes with zero violations and 4/10 legacy edges. All **145
  new Python files** meet the 400/70-line limits. Refreshed baseline remains
  `collection_ok=true`, `release_ready=false`: **110 runtime Ruff issues, 3,422
  missing labels among 4,518 test functions, 74 oversized runtime files and 238
  long functions**. These inventories do not establish the later quality gate.
  The worktree has **357 Git-visible changed paths**; the index is empty, original
  main is clean and all six sealed fixture hashes match their retained commitments.
  Docs project hygiene and tracked/new-scope whitespace checks pass; the inventory
  matches Git and all 18 original plan sections remain present.

Architecture checklist: AC-01 passes the current transition-policy gate; normative
layering remains C/D work. AC-02/03/05/06 pass for unchanged decision nodes, explicit
request contracts, application-owned recovery and the declared journal adapter.
AC-04 passes for injected owner/time inputs. AC-07 passes for verified replacement,
fenced initialization and confirmed publication. AC-08 passes with unchanged event
fields and the canonical operator-action type retained in admission history.
AC-09 passes for this retained recovery chain and remains partial for recovery
after initialization and broader coordination. AC-10 is covered by the same-change
spec, delta, current authority, architecture and operator runbook updates.

Not verified / Remaining blockers or drift: no fresh full source suite, installed
Windows/Linux Python matrix, native Linux owner-recovery proof or production
migration. Recovery is a trusted local Python operation, with no new CLI or
authenticated remote endpoint. It does not fence separately configured journals,
arbitrary custom writers or surviving descendants. Post-initialization workload/
export owner recovery, cross-installation relocation, pre-relocation contract
snapshots, capacity and complete BT-3 acceptance remain required. The existing
oversized `orket/orchestration/engine.py` grows from 455 to 457 lines solely to carry
the required canonical public argument; its existing 78-line initializer and wider
facade decomposition remain E2 debt. The changed orchestrator is 378 lines.
All 11 remaining findings and later gates stay active. No source commit/tag/push,
release or production migration was performed; test pushes used owned localhost
Gitea. Production Gitea and the operator's llama.cpp server were untouched.

Exact Git-visible paths touched by this recovery checkpoint (17):

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_ADMISSION_RECOVERY_BT3_2026-09-12.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/application/services/epic_admission_service.py`
- `orket/core/contracts/epic_publication.py`
- `orket/orchestration/engine.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/execution_pipeline_card_dispatch.py`
- `tests/helpers/epic_publication_recovery_worker.py`
- `tests/integration/test_epic_admission_recovery.py`
- `tests/integration/test_epic_publication_recovery_process.py`

The existing ignored live driver was also updated. The full Git-visible inventory
above includes preserved earlier slices.

Next at the pre-initialization checkpoint: settle recovery/fencing after initialization for interrupted workloads and
exports, and coordinate journals sharing resources. Complete custom-writer and
cross-installation coverage, then refresh the full source/installed BT-3 envelope
before advancing to BT-4 and the remaining ordered gates.

### BT-3 expanded candidate audit checkpoint: 2026-09-13

Status: candidate acceptance failed. This audit prioritizes an existing governed
approval-continuation regression before broader recovery expansion. SR-07, whole
BT-3 and all later required gates remain active in the requested worktree.

The original BT-3 requirements remain the acceptance authority:

| Requirement | Present evidence and remaining limit |
|---|---|
| Typed requirements and evidence through completion consumers | Application, persistence, scheduler, dependency, graph and operator-view cases are included in the expanded candidate. Arbitrary custom writers and the full acceptance envelope remain open. |
| Exact artifact/workload/input/run binding | Existing negative cases remain exercised. The provenance fixture now supplies explicit production timestamps instead of relying on filesystem timestamp resolution; runtime selection and assertions are unchanged. Cross-installation relocation and pre-relocation snapshots remain open. |
| One explicit/synthesized/application/persistence gate; termination differs from success | Existing completion negatives remain exercised, but standard epic approval continuation fails because the pending approval becomes a terminal epic failure before continuation. This is the next runtime repair. |
| Read-only replay with counts, scope and digests | The accepted SD-02 cases are included in the installed audit. Their bounded passing results do not make the aggregate candidate green or admit external-effect replay. |

Five existing test modules were repaired without production-code changes. The
driver resource harness supplies its required workspace accessor. Engine forwarding
doubles accept the canonical admission-recovery argument. Workload-shell assertions
observe the actual initial ledger metadata and truthful final incomplete result.
Scheduler requeue cases preserve old session/publication history, prove refusal of
changed same-session requests, and exercise real reservation/lease transitions in a
fresh invocation. These fixture repairs do not redefine approval continuation as a
fresh run. The provenance fixture supplies distinct file mtimes for its declared
output order. No success assertion or runtime acceptance gate was weakened.

Verification (path `primary`; focused repairs `success`, aggregate candidate
`failure`, ongoing BT-3 `partial success`):

- Full source collection: **5,274 cases**. The source run reported **5,192 passed,
  8 failed, 74 skipped, 2 warnings in 1,098.58s**,
  `.tmp/bt3-full-candidate.xml`. It collected before the fixture repairs and is not
  post-repair full proof. Seven failures were fixture mismatches in the four
  repaired driver/engine/scheduler/workload modules. Their opening reproduction
  was **7 failed, 9 passed in 4.29s**. The final four modules plus the provenance
  case pass **17 tests in 7.11s**, `.tmp/bt3-candidate-fixture-repairs.xml`.
  Engine collaborator assertions are structural unit proof; real filesystem,
  ledger and scheduler assertions are deterministic integration proof.
- The unchanged composed system-acceptance approval test still fails. A retained
  independent rerun reports **1 failed in 2.58s**,
  `.tmp/bt3-approval-continuation-before.xml`. Read-only SQLite inspection of that
  run confirms approval `ba451ca5-cc0f-4ef1-88c9-48d95ffea853` is `approved`, child
  `turn-tool-run:6712595a:ISSUE-A:lead_architect:0001` is still `executing` with no
  final truth, the epic ledger is `failed`, ISSUE-A remains `in_progress`, and
  `approved.txt` is absent. Preparation/publication phases are 5/4 and the epic
  admission is released despite the unfinished child. All retained store hashes
  are unchanged by inspection. Stable diff-ledger report:
  `.tmp/bt3-approval-continuation-investigation/report.json`. This is live composed
  runtime behavior with a fixture provider, not live-model proof.
- Local wheel and source archive build successfully with
  `python -m build --no-isolation --wheel --sdist --outdir .tmp/bt3-completion-candidate-dist`.
  Wheel `orket-0.6.2-py3-none-any.whl` SHA-256:
  `e8bc840deee77092a3cdba56be2288957e075245057049b3cbc9ff2d7543b151`;
  source archive SHA-256:
  `be3bf7da21ae6584422699e68e9cdfa8fccedae4afa82dfc1cbf3ae227fa05a2`.
  These are local failed-candidate artifacts, not accepted release artifacts.
- The same wheel is installed in four isolated environments. All four `pip check`
  commands pass. Separate harnesses outside the checkout contain Git-visible test
  and script support, with no runtime source package; `PYTHONPATH` is unset. The
  **63-selector, 567-case** campaign confirms **855 runtime/SDK modules** from each
  installation with zero unexpected origins. `ORKET_DISABLE_SANDBOX=1` applies.
  Stable `.tmp/bt3-completion-matrix/manifest.json` records artifact, source-fixture
  and proof-driver hashes; `.tmp/bt3-completion-matrix/report.json` retains the
  aggregate failure and links each original cell report and followup.

| Installed cell | Initial result | Failures |
|---|---|---|
| Windows Python 3.11.14 | 565 passed, 2 failed; 402.77s | Approval continuation; parallel throughput |
| Windows Python 3.12.2 | 566 passed, 1 failed; 408.51s | Approval continuation |
| Linux Python 3.11.16 | 560 passed, 6 failed, 1 skipped; 759.99s | Approval continuation; provenance fixture; four Gitea environment failures |
| Linux Python 3.12.3 | 560 passed, 6 failed, 1 skipped; 710.47s | Approval continuation; provenance fixture; four Gitea environment failures |

Both Linux skips identify the native Windows junction boundary. Their four Gitea
failures are environment blockers: `wsl --exec docker version` cannot execute
`docker` (`execvpe(docker): No such file or directory`). The corresponding Windows
Gitea cases pass with owned-container teardown. Linux Gitea acceptance is absent.
No host/provider fallback was substituted. The Windows 3.11 throughput observation
was parallel **18.412303s** versus serial **9.618629s**. The initial campaigns ran
concurrently; causation is not established. The unchanged throughput case passes
after the campaigns stop, but that isolated result does not establish the
performance gate. The repaired provenance case passes in all four installations;
the manifest preserves the original fixture hash and its followup hash. Initial
matrix results remain failed; focused followups do not replace a full rerun.

The lifecycle trace requires a distinction between a retained approval pause and
terminal workload failure. `GovernedTurnToolApprovalContinuationService` currently
reenters `run_card(issue_id, session_id=original)` after the epic finalizer has
published an immutable failure. The changed issue target first triggers
`E_EPIC_PREPARATION_REQUEST_CONFLICT`; fixing that target alone cannot repair the
terminal-publication and admission inconsistency. Settle the bounded pause,
authorized continuation and denial semantics in the existing contracts before
implementation. Preserve the original governed child identity, approval binding,
evidence and any already published failure history. Prove no early write, approved
write plus accepted card/epic outcome, denial without a write, repeated decision,
restart and concurrent continuation before claiming this repair. Do not clear the
journal, relax request binding or change the existing test to expect refusal.

No production Python changed in this checkpoint. Targeted Ruff passes all five
modified test modules. Current authority, the runbook, card-completion contract,
supervisor approval contract and project registry now disclose the actual
regression without withdrawing the continuation requirement. Checklist AC-01
through AC-06 and AC-08 have no new runtime changes; AC-07/AC-09 remain partial for
the approval lifecycle until its repair and acceptance. AC-10 passes for candid
same-change implementation-status corrections. Orket Core owns the next repair
under this active BT-3 plan.

Final structural checks: docs project hygiene and tracked/new-scope whitespace
checks pass, preserving intentional Markdown hard breaks. The exact inventory
matches **362 Git-visible changed paths** and all **18 original plan sections**
remain in order. All **145 new Python files** pass the 400/70-line checks. Refreshed
baseline at `2026-09-13T06:10:59Z` remains `collection_ok=true`,
`release_ready=false`: **110 runtime Ruff issues, 3,422 missing labels among
4,518 test functions, 74 oversized runtime files and 238 long functions**. These
inventories remain later quality work. The index is empty, original main is clean,
and all six sealed outward fixture hashes match their retained commitments. Only
the pre-existing production `vibe-rail-gitea` container remains; acceptance
containers have been removed.

Not verified / Remaining blockers or drift: approval continuation is unrepaired;
there is no passing full source suite or installed matrix after these repairs.
No fresh live-model proof or production migration was performed. The earlier
live llama.cpp/Gitea owner-recovery proof remains bounded historical evidence.
Post-initialization interrupted-owner recovery, separate-journal coordination,
custom-writer coverage, relocation/pre-relocation snapshots, capacity and later
ordered gates remain required. A general owner-takeover design also depends on
the BT-4 lifetime and BT-5 shared-authority obligations; this audit does not close
or remove them. No source commit/tag/push or release was performed. Test pushes
used disposable localhost Gitea; production Gitea and operator llama.cpp were
untouched.

Exact Git-visible paths touched by this candidate-audit checkpoint (12):

- `CURRENT_AUTHORITY.md`
- `docs/RUNBOOK.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
- `tests/application/test_async_executor_service.py`
- `tests/application/test_engine_refactor.py`
- `tests/application/test_execution_pipeline_run_ledger.py`
- `tests/application/test_execution_pipeline_session_status.py`
- `tests/application/test_execution_pipeline_workload_shell.py`

Ignored local proof drivers, external installed-test harnesses and retained
candidate reports are additional verification artifacts. The full Git-visible
inventory above includes all preserved earlier slices.

Next: repair the demonstrated approval-continuation lifecycle, then rerun its
source/installed acceptance and the complete candidate envelope. Keep the broader
recovery, writer and relocation obligations active while progressing through the
original BT-3 requirements and subsequent ordered gates.

### BT-3 epic approval pause repair checkpoint: 2026-09-13

Status: the demonstrated standard epic approval regression is repaired in the
worktree. The complete BT-3 gate and the remaining ordered slices stay active.
This supersedes the candidate-audit checkpoint's current regression status while
preserving its original failing tests, databases and installed results.

An `ApprovalPending` result now retains unfinished execution instead of publishing
terminal epic failure. The additive `epic_approval_pause.v1` journal record binds
the original asset key, request/export configuration, execution artifacts,
transcript and exact approval identities. Admission and the parent ledger remain
active. After all decisions resolve, one journal transaction claims continuation;
reentry restores the original parent and child identities without resetting cards,
repeating setup or relaxing the existing same-attempt pre-effect checkpoint.

Approval decisions use the pending-store conditional write. Competing approve and
deny requests have one durable winner; repeated identical decisions publish
idempotently and can finish a previously recorded decision. Denial terminal-stops
unfinished governed children and publishes parent failure without executing their
authorized effects. Actual prior effect steps are retained in denial truth. A
later post-effect pause does not authorize further recovery: the original checkpoint
refusal remains required and is exercised explicitly. Dispatch batches are drained
before a pause is retained, and shared setup behavior is extracted into an
application service to keep the already oversized orchestrator from growing.

Live proof exposed a second real defect: custom runtime DB composition selected
two different control-plane stores. Engine, epic and turn composition now share
`control_plane_db_for_runtime`, selecting the sibling of an absolute runtime DB and
resolving relative DB selection against the explicit workspace. Previously split
custom/global stores and old terminal failures are preserved. No automatic merge,
migration, backfill or historical-kernel continuation is inferred. Relative SQLite
runtime DB paths still use the process directory while this existing control-plane
policy uses the workspace. A live SQLite `PRAGMA database_list` observation plus
source composition inspection confirms different parents when those bases differ:
`.tmp/bt3-epic-approval-relative-db-observation.json` (primary path, failure of
co-location; temporary DB teardown confirmed). This is not composed relative-path
acceptance. Absolute DB paths define the verified scope; Orket Core retains the
relative-path convergence obligation under BT-5.

Verification in this checkpoint:

- Before repair, default-layout approval and denial both failed the parent-running
  assertion: `.tmp/bt3-epic-approval-before.xml` (2 failures). The custom-layout
  missing-target defect separately reproduces in
  `.tmp/bt3-epic-approval-custom-before.xml` (2 failures).
- The required original system approval test passes unchanged alongside restart
  approval/denial. The final focused source campaign reports 31 passed in 22.03s:
  `.tmp/bt3-epic-approval-final-focused.xml`. Its fixture provider exercises actual
  files, SQLite journals and runtime composition; this is composed integration
  proof, not live provider proof. Subsequent import cleanup and label comments are
  checked in the final source campaign recorded below.
- Live primary path, success: the actual localhost llama.cpp four-card flow pauses
  before the first write, closes the runtime, approves through a new runtime and
  completes the original epic and governed child. Default and custom database
  layouts pass. The custom run `approval-live-32a41a3a42e2464f9ad4e794ec9851aa`
  retains eight model receipt hashes, the original first response, four accepted
  card receipts, one final parent ledger row and a released admission. Repeating
  the decision preserves the ledger and every response hash. Evidence and prior
  run bodies: `.tmp/bt3-epic-approval-live/report.json`; driver:
  `.tmp/bt3_epic_approval_live.py`. Provider `llama_cpp`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, Windows source Python 3.13.11,
  explicit approval loop policy, sandbox disabled. This is live source proof;
  installed acceptance below uses fixture providers.
- Initial isolated package campaign: all 264 selected cases passed on Windows
  3.11.14/3.12.2 and Linux 3.11.16/3.12.3. Every cell passed `pip check` and
  retained 793 runtime/SDK imports under its own site-packages with no unexpected
  origin. External harnesses contain tests/support scripts, no runtime source
  package, and run with `PYTHONPATH` absent. Evidence and exact artifact hashes:
  `.tmp/bt3-epic-approval-matrix/report.json`, `manifest.json`, and `initial/`.
  Final adjustment verification is recorded below. This is a 17-selector approval
  envelope; it does not replace the earlier 567-case installed campaign.

Final adjustment and structural verification:

- After consolidating decision handling, the 264-case envelope passes again in
  all four installations: Windows 167.18s/164.08s; Linux 316.39s/303.37s. Wheel
  SHA-256: `9df8d83631e9e28d895d5f9e01837ffe82ea9182b928ee6ff0755c5f7ff55b01`.
  The final source then removes one unused import and adds mechanical test-label
  comments. The rebuilt wheel passes 31 focused cases in each installation
  (Windows 29.86s/28.00s; Linux 75.43s/74.19s), with `pip check` and all 793
  runtime/SDK import origins still valid. Report phases `decision-adjustment`
  and `final-cleanup` preserve their different scopes and exact source manifests.
- Cleanup-stage wheel SHA-256:
  `48bb872d89cc4d2e05d28f18e51d0972db4bb81d15b25fd60fbf5f4ffeef8d4a`;
  sdist SHA-256:
  `2174a03dc459e0ef850b7dca4fffb84fab03b832f3e3ce5b58b9306b9d457f48`.
  The build exits zero. All 917 packaged Python files exactly match current
  source bytes (`.tmp/bt3-epic-approval-artifact-source.json`); that comparison is
  structural proof, separate from the installed runtime checks.
- Final live custom-layout run
  `approval-live-057aa53752ca42878351b76b064121e0` also succeeds after the decision
  adjustment and import cleanup. The retained report preserves earlier default
  and custom runs. Both runtimes close; the original response and all eight final
  model receipts remain unchanged by the repeated decision.
- Targeted Ruff passes all 29 Python files in this 38-path repair. All 152 new
  Python files across the worktree pass 400/70-line checks; the modified decision
  function is 69 lines. The existing oversized `orchestrator_ops.py` and
  `engine_approvals.py` shrink against HEAD; no new oversized file is introduced. The exact inventory
  contains 379 Git-visible changed paths and all 18 original level-two plan
  headings remain exact and ordered. Six sealed fixture hashes match their
  retained commitments without resealing. Evidence:
  `.tmp/bt3-epic-approval-audit.json`.
- Refreshed baseline at `2026-09-13T07:08:48Z` remains `collection_ok=true`,
  `release_ready=false`: 110 runtime Ruff issues, 3,419 missing labels among
  4,524 test functions, 74 oversized runtime files and 237 long functions.
  Docs project hygiene and scoped Python/Markdown whitespace checks pass.
  These structural checks do not close the live lifecycle or quality gates.

The full final-source campaign reports **5,202 passed, 3 failed, 78 skipped and
2 warnings in 1,025.84s** (`.tmp/bt3-epic-approval-full-source.xml` and `.log`).
All three failures are structural: CURRENT_AUTHORITY's embedded JSON date differed
from its header, its bounded shipped-family wording lost an existing contract
phrase, and the new `epic_run_approval` module was missing from the execution
package's explicit public surface. The date, truthful existing-family wording
and `__all__` declaration are corrected. All 12 unchanged affected contract tests
then pass in 0.36s (`.tmp/bt3-epic-approval-full-followup.xml`). This does not turn
the retained full-run result into a passing full suite.

All runtime test cases in that source campaign either pass or skip. Four additional
skips compared with the earlier candidate are the opt-in localhost Gitea export
cases (`Explicit owned localhost Gitea acceptance required`); this campaign did
not enable that acceptance fixture. The previous owned-Gitea proof remains
historical evidence, not a fresh Gitea run. Exact skip comparison:
`.tmp/bt3-epic-approval-full-source-skips.json`. The earlier throughput case passes
in this complete source run; no extra timing rerun is inferred from that result.

After the public-surface correction, the current final wheel is
`778eab5d2146e11104ae512061351ebacd1fe37f8364035f840b39dbca9bd391`
and the sdist is
`87f966f0824feca4e5c3304d1260fc967c8bbec37b1c25571a1a669047b9d75f`.
All 917 packaged Python files again match current source exactly. Each isolated
installation passes `pip check`, checks its actual package directory against
`execution.__all__`, and runs all five original composed system-acceptance cases,
including same-governed-run approval: Windows 13.02s/20.05s and Linux 21.77s/20.24s.
The matrix report's `public-surface` phase retains these final checks; its prior
phases retain the 264-case and 31-case envelopes with their own hashes and scopes.
These final package tests use fixture providers, not a new live-provider campaign.
The index remains empty and original main remains clean. Only the pre-existing
production `vibe-rail-gitea` container is present; this repair created no Docker
resources. Both temporary databases from the relative-path observation are removed.

The shared contract delta is
`docs/architecture/CONTRACT_DELTA_EPIC_APPROVAL_PAUSE_BT3_2026-09-13.md`.
Current authority, architecture, runbook, card-completion and supervisor contracts
now describe the actual repair and retained-history limits in the same change.
The decision routes and admitted tool families are unchanged.

Checklist assessment for this repair: AC-01/02/03/04/05/06/08 pass for the scoped
changes: typed core retention, application-owned transitions, async SQLite adapter
with explicit `side_effecting=True`, explicit original runtime identities, no new
decision-node policy or event schema. AC-07/09 are partial for the full lifecycle:
restart and race proof pass, while claimed-pause owner death, mixed batch failure
with another unfinished child, and cross-store historical recovery remain required
BT-3/BT-4/BT-5 work owned by Orket Core. AC-10 passes for same-change authority
updates. The old repository-wide dependency, determinism and size exceptions
remain in the exception register; this does not establish target conformance.

Not verified / Remaining blockers or drift: the complete source/installed envelope
is not replaced by these scoped checks. No production migration or old split-store
reconciliation is proved. A consumed pause with no subsequent pause/outcome remains
uncertain and refuses automatic redispatch; post-effect continuation remains
outside the admitted checkpoint. Composed parent-level restart proof here covers
`write_file`; the existing direct-turn tests also cover `create_directory` and
`create_issue`, without implying identical live provider proof for all three.
Post-initialization workload/export owner recovery, separate-journal coordination,
custom writers, relocation/pre-relocation snapshots, capacity and the remaining
ordered gates stay required. Linux Gitea acceptance still has the previously
observed missing-Docker environment blocker. No source commit, release, tag or
push is performed by this repair.

Exact Git-visible paths touched by this approval repair (38):

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_APPROVAL_PAUSE_BT3_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
- `orket/adapters/storage/epic_approval_pause_store.py`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/application/services/epic_approval_pause_service.py`
- `orket/application/services/epic_dispatch_batch.py`
- `orket/application/services/epic_publication_service.py`
- `orket/application/services/epic_setup_service.py`
- `orket/application/services/governed_turn_tool_approval_continuation_service.py`
- `orket/application/services/orchestrator_failure_handler.py`
- `orket/application/services/orchestrator_turn_preparation_service.py`
- `orket/application/services/tool_approval_control_plane_reservation_service.py`
- `orket/application/workflows/orchestrator.py`
- `orket/application/workflows/orchestrator_ops.py`
- `orket/core/contracts/epic_approval_pause.py`
- `orket/core/contracts/epic_publication.py`
- `orket/exceptions.py`
- `orket/orchestration/engine.py`
- `orket/orchestration/engine_approvals.py`
- `orket/orchestration/engine_services.py`
- `orket/runtime/execution/__init__.py`
- `orket/runtime/execution/epic_run_approval.py`
- `orket/runtime/execution/epic_run_finalize.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/epic_run_support.py`
- `orket/runtime/execution/epic_run_types.py`
- `orket/runtime/execution/execution_pipeline.py`
- `orket/runtime_paths.py`
- `tests/application/test_engine_approvals.py`
- `tests/application/test_engine_refactor.py`
- `tests/integration/test_epic_approval_continuation.py`

Ignored proof scripts, local retained reports/stores, build artifacts and isolated
external test installations are additional verification artifacts. The exact full
worktree inventory above retains earlier slices as well.
Next: retain the repaired approval lifecycle and finish the remaining BT-3
acceptance/owner-recovery obligations. Keep the relative-path and historical-store
reconciliation findings in BT-5, and resolve the BT-4 lifetime prerequisites
without claiming either gate closed. A green full-suite result and the complete
installed envelope remain required; targeted corrections do not substitute for them.


### BT-3 explicit export owner recovery checkpoint: 2026-09-13

Status: bound exact-commit export recovery implemented and scoped proof passed;
BT-3 remains open for unknown workload ownership and the wider recovery envelope.

An interrupted phase-four export now has an explicit trusted local Python recovery
operation. `run_card(..., export_recovery=...)` binds the original epic/session,
request, acceptance, intent and current owner evidence. It records the replacement
and canonical operator action under the existing journal writer, confirms remote
delivery first, and grants only the new caller one exact-commit retry if needed.
An old caller paused outside the writer is fenced; an already entered callback
must settle or lose its connection before a replacement can enter. Identical
requests observe their prior grant and cannot dispatch again. A lost retry result
needs confirmation or a new explicit request. This does not establish termination
of work already accepted by a remote server or exactly one transport submission.

New `epic_export_dispatch.v1` records commit with phase-four intent markers. The
original reference lives in preparation artifacts, preserving existing v2 schema
bodies. Successful publication atomically settles the owner and validates its
final reference and commit/tree receipt. Admission, outcome, accepted cards and
intent remain unchanged. Unmarked older v2 preparations retain confirmation-only
handling; no inferred owner, digest backfill, payload rebuild, merge or force-push
is admitted. Pre-initialization admission recovery remains a separate operation;
the two recovery inputs are mutually exclusive.

Authority: `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md` and
`docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`; contract delta:
`docs/architecture/CONTRACT_DELTA_EPIC_EXPORT_RECOVERY_BT3_2026-09-13.md`.
Observed path: `primary`. Scoped result: `success`.

Evidence retained in the worktree:

- Initial regression: 23 passed in 29.56 seconds;
  `.tmp/bt3-export-recovery-initial-regression.log/.xml`.
- Contract expansion: 15 passed, then 20 passed in 21.15 seconds;
  `.tmp/bt3-export-recovery-contract-initial.log/.xml` and `-expanded.log/.xml`.
  These exercise real SQLite ownership with simulated export callbacks. Damage,
  stale/conflicting requests, identical/superseded races, lost retry results,
  invalid public inputs and published-reference removal reject. The unmarked
  legacy case is a synthetic old-format fixture, not production migration proof.
- Actual localhost Gitea: initial killed/resumed-owner cases passed two; the
  expanded source selection passed seven in 59.76 seconds, retained in
  `.tmp/bt3-export-recovery-gitea-initial.log/.xml` and `-expanded.log/.xml`.
  Native competing recovery processes produce one observed admitted push and
  the original commit; changed remote history refuses the ordinary push without
  publishing success. An existing lost-reply test now checks the typed unresolved
  result instead of its stale raised-exception expectation. Touched acceptance
  docs likewise describe retained failure through the current typed result.
- Frozen canonical source command `python -m pytest -q` (with short diagnostics
  and JUnit output): **5,379 passed, three failed, 81 skipped, 1271.36 seconds**;
  `.tmp/bt3-export-recovery-full-source-report.json/.log/.xml`. Git-visible Python
  hashes match before/after. Explicit Gitea tests are separately admitted, not
  silently counted as passing by their default skip. Other skips/warnings remain
  visible in the full log and are not proof of their unavailable paths. All three
  failures are the old `_FakePipeline.run_card` signature in
  `tests/application/test_engine_refactor.py` rejecting `export_recovery`.
  The corrected double and a non-None forwarding assertion pass all nine file
  cases from source (`.tmp/bt3-export-recovery-fixture-followup.xml`) and all four
  installed cells in separate external harnesses
  (`.tmp/bt3-export-recovery-followup/report.json`). Runtime/wheel bytes remain
  unchanged. Only this test file differs from the full/live/main-matrix source
  manifests; the follow-up manifests bind its corrected bytes. The complete
  source suite was not rerun after this fixture correction and is not reported
  as a green full-suite gate.
- Fresh live llama.cpp `orcarouter_qwen3.8-27b-uncensored-q4_k_l` completed four accepted cards, then hit
  an injected interruption after intent retention and before push. Automatic
  reentry stayed unresolved; explicit recovery published the original commit.
  All 8 model receipt hashes and four acceptance receipts
  remained unchanged, with no workload redispatch. Matching request reentry
  succeeded, both engines closed, and localhost Gitea 1.25.4 plus its anonymous
  volumes were removed. The report binds the frozen Python source hashes:
  `.tmp/bt3-export-recovery-live/report.json` and `.tmp/bt3-export-recovery-live.log`.
  Remote commit: `c62449e4e2735b778528959dc4ff407de48be104`.
- The first live proof driver consumed the first Git argument in its counting
  wrapper and reported zero pushes. Its assertion failed although the retained
  journal reached settled generation two/phase five. The preserved failure is
  `.tmp/bt3-export-recovery-live/initial-report.json` and `initial.log`. Correcting
  the probe signature, then running a fresh live workload, observed one actual
  push. No runtime behavior was changed to satisfy this probe. PowerShell's
  final redirected stderr command also reports shell status 1 for expected runtime
  diagnostics; a zero-native-exit stderr probe reproduces that shell behavior in
  `.tmp/bt3-export-recovery-powershell-stderr-probe.log`. The live success claim
  rests on retained checked effects/teardown and report assertions, not that shell
  status. Future proof launches should explicitly preserve the native exit code.

Final wheel acceptance ran from external test harnesses without runtime source,
with `PYTHONPATH` removed, isolated `pip check`, before/after harness hashes and
all 643 imported core/SDK module origins verified under installed site-packages.

| Installed cell | Passed | Failed / skipped | Seconds (JUnit) | Actual Gitea |
| --- | ---: | ---: | ---: | --- |
| win-py311 | 95 | 0 / 0 | 237.418 | Yes |
| win-py312 | 95 | 0 / 0 | 245.728 | Yes |
| linux-py311 | 88 | 0 / 0 | 269.468 | No |
| linux-py312 | 88 | 0 / 0 | 263.101 | No |

The common 88-case envelope covers real journals, native process recovery and
scoped callback contracts. Each Windows cell additionally runs the seven actual
localhost Gitea cases. Linux Gitea delivery was not run: WSL Docker integration
is not configured. Windows live results do not establish Linux Git transport.
Reports: `.tmp/bt3-export-recovery-matrix/report.json` and `final/`.

Archives: `.tmp/bt3-export-recovery-dist/`.

- Wheel SHA-256: `5d6a0a1593623c0dcc0c82a796fe03fb1c59695e9e3bbbd907fd866f782cdaed`.
- Sdist SHA-256: `f7d33443d2491a96ccfca298a7738a297af9767841f897189f1b8090fbd842dd`.

The final audit binds all 938 runtime Python files to source/wheel/sdist and checks
six unchanged fixture seals, original clean main, empty index, native/container
cleanup, 18 unchanged H2 plan headings and exact inventories:
`.tmp/bt3-export-recovery-audit.json`. All 22 scoped Python files are Ruff-clean
against preceding-candidate bytes; the existing 458-line engine does not grow.
Architecture checklist AC-01 through AC-10 pass for this bounded local export
operation. Broader ownership and historical authenticity remain explicit limits.
The baseline collects successfully and keeps `release_ready=false`: 110 Ruff
issues, 3,387 missing labels across 4,587 test functions, 74 oversized runtime files
and 235 oversized functions. The end-to-end taxonomy mismatch remains E1 work.
No commit, tag, release, global install or sandbox resource is created here. Git
pushes in this checkpoint target the owned disposable localhost Gitea fixtures.

Not verified / remaining blockers or drift: unknown post-initialization workload
ownership, interrupted claimed approval pauses, old custom/global store
reconciliation, independent-journal coordination, arbitrary custom writers,
cross-installation relocation, production Gitea and arbitrary remote-hook effects.
The full installed repository suite was not run. The selected 3.11/3.12 envelope
and live provider proof do not close BT-3, BT-4, BT-5, C/D, E or CAP gates.

Exact files touched in this checkpoint (31):

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_EXPORT_RECOVERY_BT3_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`
- `orket/adapters/storage/epic_export_dispatch_store.py`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/adapters/vcs/gitea_artifact_exporter.py`
- `orket/adapters/vcs/gitea_export_git.py`
- `orket/application/services/epic_export_recovery_service.py`
- `orket/application/services/epic_preparation_service.py`
- `orket/application/services/epic_publication_service.py`
- `orket/core/contracts/epic_export_recovery.py`
- `orket/core/contracts/epic_publication.py`
- `orket/orchestration/engine.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/epic_run_result_boundary.py`
- `orket/runtime/execution/execution_pipeline.py`
- `orket/runtime/execution/execution_pipeline_card_dispatch.py`
- `tests/application/test_engine_refactor.py`
- `tests/contract/test_epic_export_recovery.py`
- `tests/helpers/epic_export_recovery.py`
- `tests/helpers/epic_publication_recovery_worker.py`
- `tests/integration/test_epic_publication_recovery_process.py`
- `tests/integration/test_gitea_epic_export_recovery.py`
- `tests/integration/test_gitea_export_owner_recovery.py`
- `tests/runtime/test_epic_run_orchestrator.py`

### BT-3 interrupted approval recovery checkpoint: 2026-09-13

Status: the explicit, locally guarded pre-effect approval recovery slice is
implemented and passes its scoped final proof. BT-3 and the umbrella lane remain
open. Work remains in `C:/Source/Orket-architectural-truth` on
`codex/architectural-truth-bt0`; original main stays clean. No commit, tag,
release or repository push was performed in this checkpoint. Git pushes in the
acceptance flows target only owned disposable localhost Gitea fixtures.

The opening native counterexample at
`.tmp/bt3-approval-recovery-before/report.json` killed a fixture-provider process
after its claimed pause committed. The original caller was reaped; no child
steps/effects or output existed, yet reentry remained unresolved. Its `failure`
result records the unmet recovery requirement, not a failed observation script.

New approval claims bind `epic_continuation_lock.v1` to the original journal,
session and stable native file identity. An application-owned lock covers claim,
restoration, workload and durable outcome/next-pause retention, then releases
before that caller enters export. Other callers may independently finalize an
already retained outcome. An active holder excludes recovery; age, timeout and empty effect
observations cannot transfer ownership. Canonical Python `run_card` now accepts
an explicit `approval_recovery` input, mutually exclusive with admission/export
recovery. It binds the original pause and history head, retains one request and
canonical operator action, and never resets claimed state or rewrites the pause.
Identical grants observe their disposition without dispatch; another interruption
needs a new explicit request. Outcome/publication references must match history.

Read-only admission shares the existing checkpoint rules and snapshot semantics.
All referenced approved children must remain pre-effect. Completed children,
known steps/effects, orphan operation files and insufficient checkpoint evidence
refuse this operation. Denial follows the existing stop path. The resumed turn
still uses its original checkpoint and authorization checks. Unmarked old claims
stay unresolved. These locks coordinate cooperating callers on the same local
journal; they do not establish remote-effect termination, hostile-writer
containment or coordination across independent journals.

Verification and retained attempts:

- Initial Windows and Linux source native-lock checks each passed six cases;
  `.tmp/bt3-approval-recovery-lock-initial.log/.xml` and
  `.tmp/bt3-approval-recovery-lock-linux-initial.xml`. The existing approval plus
  initial lock regression passed 17 (`.tmp/bt3-approval-recovery-initial.log/.xml`).
- The first composed native driver emitted a pause body larger than its pipe
  line limit; all six cases failed in the harness. A smaller marker then exposed
  a second harness mistake: treating a journal path as a runtime DB path added
  the journal suffix again. That run failed six and passed nine unit cases.
  `.tmp/bt3-approval-recovery-native-initial.log/.xml` and
  `-native-followup.log/.xml` preserve both failures. Reading the actual runtime
  database fixed the driver; `-native-followup2.log/.xml` passed all six.
- Expanded source regression passed 57 in 103.03 seconds
  (`.tmp/bt3-approval-recovery-regression.log/.xml`). The subsequent three-case
  history/independent-process selection passed in 16.05 seconds
  (`.tmp/bt3-approval-recovery-edges.log/.xml`). These use real native processes,
  files, SQLite and the deterministic fixture provider. They establish killed
  and active owner behavior, one competing grant, interrupted/idempotent/stale
  history, referenced-history loss, denial, post-effect refusal, cancellation
  during lock acquisition/close and outcome-before-unlock.
- The frozen canonical source suite (`python -m pytest -q`, short diagnostics
  and JUnit capture) passed **5,399**, failed zero and skipped **81**
  in **1405.46 seconds**; interpreter `3.13.11`.
  `.tmp/bt3-approval-recovery-full-source-report.json/.log/.xml` retains matching
  Git-visible Python hashes before/after. Skips remain disclosed and are not
  proof of their unavailable flows. The later Linux fixture correction changes
  only `tests/integration/test_epic_approval_recovery.py`; it passes all seven
  current cases from source (`.tmp/bt3-approval-recovery-fixture-followup.xml`).
  The full source suite was not rerun after that fixture-only path correction.
  Runtime bytes are identical across the full suite, live run and final archives.
- Initial installed acceptance passed 138 on each Windows cell, while each Linux
  cell passed 129 and failed two negative fixtures. Those fixtures hard-coded
  `ISSUE-A` in an artifact path whose canonical directory is `issue-a`.
  Windows case insensitivity concealed the fixture mistake. Both now resolve
  the actual directory using `TurnArtifactWriter` and retained approval identity.
  Initial logs/manifests/results remain under
  `.tmp/bt3-approval-recovery-matrix/`; corrected, separate external harnesses
  and final results live under `.tmp/bt3-approval-recovery-final-matrix/`.

| Installed cell | Selected tests passed | JUnit seconds | Loaded core/SDK origins | Actual Gitea |
| --- | ---: | ---: | ---: | --- |
| win-py311 | 138 | 256.898 | 653 | yes |
| win-py312 | 138 | 264.941 | 653 | yes |
| linux-py311 | 131 | 356.511 | 653 | no |
| linux-py312 | 131 | 348.157 | 653 | no |

All final cells have zero failures/errors/skips and zero unexpected origins.
Each force-installs the unchanged candidate wheel in its isolated Python 3.11 or
3.12 environment, passes `pip check`, excludes source core/SDK trees and validates
harness bytes before/after. The common selection is 131 tests; Windows adds seven
actual localhost Gitea cases. Linux Gitea transport remains unverified because
Docker is unavailable inside this WSL distribution; this is not a provider or
native-lock failure. The whole installed repository suite was not run.

Final archives contain the same 944 runtime Python files as source:

- wheel SHA-256: `60c6b452566e27a91a85f74fc52a6152528cfc16f1b3a2ff4dc8023dc0680271`;
- sdist SHA-256: `170b55e5c337ae8e5062eb2ae11ec28c50d293f69f278ff3474776ff93ecd616`;
- artifacts: `.tmp/bt3-approval-recovery-dist/`.

Fresh source live llama.cpp `orcarouter_qwen3.8-27b-uncensored-q4_k_l` and actual localhost Gitea pass
in `.tmp/bt3-approval-recovery-live/report.json` and
`.tmp/bt3-approval-recovery-live.log`. Session `approval-recovery-live-415959605439465ba630c0ed88f0c8a2` pauses
after the actual approval claim. The active native holder rejects explicit
takeover. Killing/reaping it leaves automatic reentry unresolved; the explicit
request then completes the original checkpoint and all four accepted cards.
The first model receipt remains unchanged within eight final model receipts.
Identical reentry leaves all eight receipts and the four acceptance receipts
unchanged. The original pause/admission/child identity is preserved, one recovery
record is retained, and one observed push delivers commit
`3ea9dc2ada39463900887587befb3da52ea74b89`. The native process was killed/reaped (not gracefully
closed); the restarted engine closed and the Gitea container/volumes were removed
in this path. The driver returned native exit zero and its before/after source
hashes match. It uses the explicit fixture approval policy for the requirements
card; it does not claim default production-policy acceptance.

Structural checks: all 30 scoped Python files pass Ruff with no introduced
diagnostics; engine stays 458 lines and the touched checkpoint recovery module
shrinks to 428. New Python files remain within 400 lines and new functions within
70. Source/wheel/sdist runtime bytes match, all 18 plan H2 headings are preserved,
the six sealed outward fixtures are unchanged, original main is clean and the
index is empty. `.tmp/bt3-approval-recovery-audit.json` binds exact inventories,
archives, manifests, JUnit/live results, cleanup and documentation hygiene.
The refreshed baseline collects successfully with release readiness false:
108 existing Ruff diagnostics,
3387 missing layer labels among
4598 test functions, and
74 runtime files /
235 functions above size limits.
The taxonomy collector's existing omission of valid `end-to-end` labels remains
E-1 drift; this checkpoint does not reinterpret those checks as runtime proof.

Architecture checklist: AC-01/02/03/05/06/07/08/09/10 pass for the changed scope.
AC-04 is partial: the new operator timestamp is injected, but the shared existing
checkpoint-resume implementation still calls its pre-existing wall-clock helper
(`turn_tool_control_plane_recovery.py`, `turn_tool_control_plane_support.py`).
That deterministic-input exception remains in the architecture exception register
and the active Slice D work; this extraction does not widen it.

Remaining blockers or drift: arbitrary post-initialization workload ownership,
post-effect/previously unmarked claimed-pause reconciliation, old custom/global
store reconciliation, independent-journal coordination, custom writers,
cross-installation relocation, production Gitea/remote-hook effects, full installed
repository acceptance, and the remaining BT-3/BT-4/BT-5/C/D/E/CAP gates remain open.
This checkpoint supplies a bounded prerequisite and does not close the lane.

Exact files touched in this checkpoint (39):

- `CURRENT_AUTHORITY.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_EPIC_APPROVAL_RECOVERY_BT3_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`
- `orket/adapters/storage/epic_approval_pause_store.py`
- `orket/adapters/storage/epic_continuation_lock.py`
- `orket/adapters/storage/epic_publication_repository.py`
- `orket/application/services/epic_approval_pause_service.py`
- `orket/application/services/epic_approval_recovery_service.py`
- `orket/application/services/epic_publication_service.py`
- `orket/application/services/epic_workload_outcome_service.py`
- `orket/application/services/runtime_execution_observation.py`
- `orket/application/services/turn_tool_checkpoint_authority.py`
- `orket/application/services/turn_tool_control_plane_recovery.py`
- `orket/application/workflows/epic_approval_checkpoint.py`
- `orket/application/workflows/turn_checkpoint_snapshot.py`
- `orket/application/workflows/turn_executor_control_plane_evidence.py`
- `orket/application/workflows/turn_executor_resume_replay.py`
- `orket/core/contracts/epic_approval_pause.py`
- `orket/core/contracts/epic_approval_recovery.py`
- `orket/orchestration/engine.py`
- `orket/runtime/execution/epic_run_approval.py`
- `orket/runtime/execution/epic_run_finalize.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/epic_run_result_boundary.py`
- `orket/runtime/execution/execution_pipeline.py`
- `orket/runtime/execution/execution_pipeline_card_dispatch.py`
- `tests/application/test_engine_refactor.py`
- `tests/helpers/epic_approval_recovery_worker.py`
- `tests/helpers/epic_continuation_lock_worker.py`
- `tests/integration/test_epic_approval_recovery.py`
- `tests/integration/test_epic_approval_recovery_competing.py`
- `tests/integration/test_epic_approval_recovery_history.py`
- `tests/integration/test_epic_continuation_lock.py`

### BT-3 completion authority and governed rejection gate audit: 2026-09-13

Status: scoped BT-3/SR-07 acceptance passed. The four numbered obligations
are verified for builtin card completion and governed-agent replay; broader
recovery, authority, quality and capability obligations remain active.
The worktree and branch remain `C:/Source/Orket-architectural-truth` and
`codex/architectural-truth-bt0`; no commit, tag, release or push is part of this work.

The audit uses the four numbered BT-3 requirements above, unchanged from HEAD.
Accumulated recovery work remains required under its recorded contracts and the
broader recovery, lifetime and capability gates. It does not redefine evidence
sufficiency or turn truthful unresolved execution into accepted completion.

| BT-3 requirement | Current enforcement and decisive regression |
|---|---|
| Typed acceptance through consumers | Application acceptance and shared prompt projection; `test_card_completion_prompt_authority.py` covers normal/compact prompts for absent, empty, syntax-only, wrong and accepted output |
| Artifact/input/run/attempt binding | Application final authorization, retained evidence and SQLite receipt transaction; persistence, transaction, workspace-guard and receipt-inspection integrations |
| Same gate and actionable unsuccessful outcome | Explicit/synthesized turn tests, application/persistence bypass controls, build/publication/operator tests, governed guard rejection through actual storage and engine publication |
| Complete read-only replay | Existing empty and replay-evidence tests exercise zero/one/multiple decisions, missing/corrupt inventory and inputs, CLI/API, resource limits and unchanged stores |

Two contradictions were reproduced before repair. Ten prompt cases still told
guards to choose done when the legacy verifier passed, although empty or
syntax-only support checks returned true. A strict single-envelope blocked call
could not pass guard validation because both consumers searched empty turn content
for a second JSON object. Opening failures are retained in
`.tmp/bt3-completion-gate-prompt-before.log/.xml` and
`.tmp/bt3-completion-gate-rejection-before.log/.xml`.

The application now projects the typed acceptance decision into both prompt
formats. Missing authority remains unevaluated. Guard guidance distinguishes
support checks from admitted acceptance. Rejection metadata is bound to
`update_issue_status.args.guard_review` within the existing envelope. Shared
extraction supplies pre-dispatch validation and post-dispatch events, removing
duplicate legacy scanners. Missing, malformed, empty and conflicting blocked
metadata cannot mutate the card. Existing non-governed text extraction remains.
The durable contract and delta are updated in the same change.

Initial focused proof: 60 prompt/completion regressions passed; then 143 mixed
prompt/parser/guard/orchestrator regressions passed. The expanded composed run
passed 23 and failed its new engine fixture because inferred support verification
attempted an absent main.py before guard dispatch. The fixture now writes a real
support program. Its follow-up passes through successful support verification,
actual guard rejection events, blocked card storage and published unsuccessful
epic truth. This fixture repair did not disable the verifier or change the gate.
Reports use `.tmp/bt3-completion-gate-guard-initial`, `-guard-composed`, and
`-guard-epic-followup` log/XML stems.

Fresh live source proof succeeds in `.tmp/bt3-completion-gate-live/report.json`:
llama.cpp, `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, Windows Python 3.13.11.
The standard four-card workload reaches accepted card/build completion with eight
model responses. A separate real guard turn sees missing acceptance despite
successful empty support checks, proposes valid rejection metadata, and persists
blocked with no completion receipt. That direct turn adds one model response;
its post-dispatch epic handling is covered by the composed fixture, not by that
live direct-turn invocation. Both provider flows use the primary path; result
success means the declared test expectations were met, including refusal of
objective success. Sandbox creation is disabled, and owned runtime/provider
clients close. The canonical frozen source suite passes **5,429 tests with 81 skips** in
1,134.21s, with unchanged Python hashes throughout; the two warnings are the
existing deprecated domain namespace and small fixture generation cap. Results:
`.tmp/bt3-completion-gate-full-source.log/.xml` and `-full-source-report.json`.
Afterward, only unused imports, import ordering and the obsolete validator text
wrapper were cleaned up in three workflow files. All **206 focused source tests**
then pass in 34.33s, with a fresh hash freeze in `-final-source-report.json`.
The full suite was not repeated after that cleanup. The packaged candidate has
947 byte-identical runtime Python files across source, wheel and sdist. Scoped Ruff reports
zero introduced diagnostics and one pre-existing parser import-order diagnostic.

Dependency direction with legacy enforcement `fail` and docs hygiene pass.
Architecture checklist: AC-01/02/03/04/05/06 pass for pure projections and the
shared application reader; no new decision-node effects or nondeterministic
inputs. AC-07 passes the scoped persisted rejection and live provider checks.
AC-08 preserves existing event fields. AC-09/10 use the source/archive
bindings, installed-origin checks and documented failure dispositions below.
Existing wider quality/authority debt remains under C/D/E; no release readiness
is claimed.

Installed candidate and failure dispositions:

The frozen runtime wheel is
`62e766b64b8bf9ec9ba611315176d470d9957f0b844bcf3b823ab48f237c992d`;
sdist is `3dea1a4d65e41b2ef8cd8bc87832e28733c18ddd91ef7091c1c6b6c3ccbe9958`.
Both are under `.tmp/bt3-completion-gate-dist/`. The external harness imports
875 core/SDK modules from installed site-packages, with no runtime checkout
imports; dependency checks pass. Initial results remain failures:

| Initial 702-case installed selection | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Windows Python 3.11 | 700 | 2 | 0 |
| Windows Python 3.12 | 700 | 2 | 0 |
| Linux Python 3.11 | 698 | 3 | 1 |
| Linux Python 3.12 | 699 | 2 | 1 |

Every cell omitted the six-file external governed-agent template from its copied
harness, causing two `E_AGENT_EXTENSION_ROOT_MISSING` failures. Fresh harnesses
include those Git-visible fixture files; the entire affected three-case file
passes on all four cells against the unchanged wheel (531 installed origins).
The initial selection was not repeated. Evidence: the `initial` report under
`.tmp/bt3-completion-gate-matrix/` and the `verified` report under
`.tmp/bt3-completion-gate-fixture-matrix/`. The Linux skip is Windows junction
coverage, not omitted completion behavior.

Linux 3.11 also retained a publication refusal:
`test_execution_pipeline_supports_protocol_run_ledger_incomplete_path` supplied
a final timestamp older than the preceding ledger event. The real boundary
returned unresolved with `E_LEDGER_TIMESTAMP_NON_MONOTONIC`; the test ignored
that result and expected a finalized ledger. Original event bytes could not be
recovered from the pytest temporary directory. The cause of that timestamp
reversal remains unverified; no system-clock diagnosis or environmental exemption
is claimed. Ledger time is not clamped, fabricated or accepted out of order.

The incomplete-path fixture now injects a shared increasing clock into publication
and the ledger and checks the returned outcome. A separate real SQLite/ledger
integration deliberately reverses that input at the export boundary: ordered
time publishes incomplete, while reversal retains running/phase-zero publication
and returns unresolved. The first new fixture run failed because independent
run-identity wall time made its midnight seed invalid. The corrected fixture seeds
ahead of that clock and claims only ordering, not duration or universal clock
injection. Two focused cases pass, then all eight selected source cases pass in
5.06s. Both files pass all eight cases on each installed Windows/Linux 3.11/3.12
cell, with 644 installed origins and unchanged runtime bytes. Evidence:
`-clock-contract`, `-clock-contract-followup`, `-clock-final-source` log/XML stems
and `.tmp/bt3-completion-gate-clock-matrix/report.json`. This test-only delta
follows the 206-case source freeze; the 5,429-case full suite was not repeated.
Clock convergence and the unexplained original ordering remain C/D drift.

Installed live proof uses Windows Python 3.11, the same llama.cpp model and wheel,
JSON-object enforcement, no prompt patch and disabled sandbox creation. The
standard four-card run completed with eight model responses, and a direct guard
turn blocked absent acceptance with a ninth response. The appended upstream
negative epic correctly refused the model's unsupported done proposal, but its
proof driver expected a rejection-review event. Its report remains failure in
`.tmp/bt3-completion-gate-installed-live/report.json`. A second upstream attempt
also retains failure in `-installed-guard-live/report.json`. Inspection found
that builtin upstream guards allow only done, while blocked is admitted on the
final review card; changing a role description did not change the compact packet's
allowed statuses. These attempts prove refusal, not the post-dispatch review path.

A fresh canonical four-card run removes only REV-1 acceptance and reaches the
final review rejection path with eight actual model responses. The model supplies
`args.guard_review`; engine events retain its diagnostics, REV-1 stays blocked
without a receipt, the other three cards retain accepted done, and publication
phase 4/terminal_failure records `card_completion_unverified:REV-1`. Its initial
driver report remains failure because it counted all four cards' review events
instead of REV-1's one event. Read-only SQLite/event/raw-response validation
corrects that scope and succeeds without changing any retained bytes or repeating
the runtime. Evidence: `-installed-final-review-live/report.json` and
`.tmp/bt3-completion-gate-installed-final-review-audit.json`; session
`installed-final-review-live-b02b651a1a8445fe97521a0628e2b02e`.
The live standard drivers disable legacy runtime support verification; declared
acceptance still runs. Successful support verification plus rejected acceptance
is separately exercised in the direct live turn and composed engine regression.
All owned engines/providers close. There is no provider switch or Gitea rerun.

Claim ceiling and remaining blockers or drift:

- The four numbered BT-3 obligations concern the builtin card completion and
  governed-agent replay surfaces exercised above. They do not admit custom
  writers, arbitrary objectives, remote effect replay or host takeover.
- Unknown workload ownership, post-effect/unmarked approval reconciliation,
  separate-journal coordination and old custom/global store reconciliation remain
  required under BT-4/BT-5 and later capability/recovery gates. Missing evidence
  continues to refuse success; these obligations are not discarded.
- The fresh canonical baseline reports collection_ok=true, release_ready=false:
  109 Ruff diagnostics, 3,387 missing labels among 4,609 test functions, 74 runtime
  files over 400 lines and 236 functions over 70. Scope comparison adds no Ruff
  diagnostics; the pre-existing parser import-order diagnostic remains.
- The gate audit binds this scope to the source freezes, unchanged archives,
  initial failed runs and affected follow-ups. It preserves all six sealed outward
  fixtures, 18 plan headings, a clean original main worktree and an empty index.
  Full installed reruns, Linux live-provider proof, general recovery and release
  acceptance are not claimed by this checkpoint.

Exact files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/ROADMAP.md`
- `docs/architecture/CONTRACT_DELTA_COMPLETION_GUARD_BT3_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`
- `orket/application/services/card_completion_prompt.py`
- `orket/application/services/card_completion_turn_service.py`
- `orket/application/services/guard_review_payload.py`
- `orket/application/services/orchestrator_turn_success_handler.py`
- `orket/application/workflows/orchestrator_ops.py`
- `orket/application/workflows/turn_contract_validator.py`
- `orket/application/workflows/turn_corrective_prompt.py`
- `orket/application/workflows/turn_message_builder.py`
- `orket/application/workflows/turn_response_parser.py`
- `orket/runtime/config/compact_turn_packet.py`
- `tests/application/test_execution_pipeline_protocol_run_ledger.py`
- `tests/helpers/protocol_ledger_clock.py`
- `tests/integration/test_card_completion_prompt_authority.py`
- `tests/integration/test_epic_publication_clock_inputs.py`
- `tests/integration/test_governed_guard_epic_rejection.py`
- `tests/integration/test_governed_guard_rejection.py`

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

### BT-4 current requirement-to-evidence reconciliation: 2026-09-13

Status: scoped combined acceptance passed; BT-5 is next. This is the current
BT-4 disposition; the checkpoint-specific open-gate notes below are historical.
The read-only handoff verifier passed all eight checks before edits: core and
reference worktrees, original checkouts, checkpoint scope, retained proof files,
handoff bytes and links match the saved snapshot. The core branch remains
`codex/architectural-truth-bt0` with 608 accumulated changed paths at resumption;
the reference worktree retains four. This verifies transfer continuity, not
runtime acceptance. Historical checkpoint counts below retain their own scope.

| Requirement | Admitted public path and inspected controls | Exact retained evidence and current artifact binding | Acceptance predicate; current results below |
|---|---|---|---|
| 1. Verification cancellation, deadlines, failure and shutdown | `RuntimeVerifier.verify()` through the application supervisor; `tests/integration/test_verification_process_lifetime.py`, `test_verification_shutdown.py`, and API shutdown/request ownership cases independently observe child/grandchild identities and unchanged heartbeat files after cleanup. Repeated cancellation, detached/resistant descendants, timeout and leader failure are explicit cases. | `.tmp/bt4-gate-filesystem-audit.json`; corrected ten-case verifier follow-up in `.tmp/bt4-gate-verifier-fixture-matrix/report.json`; API/request selections retained in the earlier combined manifest. Their old wheels are historical; current wheel identity is below. | Execute these controls together against current source and installed Windows/Linux Python 3.11/3.12 artifacts. Require confirmed native teardown and no later writes; protocol refusal/uncertain cleanup controls must remain non-success. |
| 2. Windows/Linux descendant and blocking-worker ownership | Native Windows Job/Linux subreaper owners; direct and bound filesystem operations, API request close, extension capability offloads and host Piper use their declared owners. `test_outward_filesystem_lifetime.py` and the extension/Piper controls hold actual work through cancellation. | `.tmp/bt4-gate-filesystem-audit.json`, `.tmp/bt4-generation-lifetime-audit.json`, `.tmp/bt4-extension-offloads-audit.json`, `.tmp/bt4-piper-supervision-audit.json`, `.tmp/bt4-piper-voice-truth-audit.json`; native voice evidence remains `.tmp/bt4-piper-voice-truth-api/report.json`. | Include the later ownership selections in the current combined matrix. Retain honest pending cleanup for stuck threads and refusal of unsupported takeover; do not infer forced thread termination, remote-effect rollback, Linux Piper or host-death recovery. |
| 3. Typed result, durable truth and process exits | Stock `orket runtime --card/--epic/--rock` projection plus `tests/integration/test_runtime_cli_lifecycle.py` and `test_runtime_execution_results.py`. Fixture-backed CLI controls inspect real SQLite/publication/admission state; interrupted runs remain unfinished and exit nonzero. | `.tmp/bt4-cli-lifecycle-matrix/report.json`, `.tmp/bt4-result-matrix/report.json`, and `.tmp/bt4-gate-cli-installed/report.json`. Earlier actual llama.cpp success/failure used an older wheel and disclosed degraded structural-reconciliation startup. | Repeat installed successful, incomplete, blocked, failed and cancelled controls outside the checkout with current artifacts. Run separate stock installed llama.cpp success and unsuccessful flows, bind actual model receipts, and compare output/exit with ledger, final truth and publication. Disclose any degraded startup; a fixture finalizer is insufficient. |
| 4. Measured timing and unavailable-state propagation | Connector invoke, interrupted event/log/receipt projection, validator/model/provider timing, scored reports, dashboards/trends and raw/selector admission. `test_outward_connector_timing.py` declares a 50 ms outer-observation allowance before measuring slow commands, failure, timeout and cancellation; missing/invalid clocks and absent metrics remain unavailable. | `.tmp/bt4-validator-timing-audit.json`, `.tmp/bt4-model-timing-audit.json`, `.tmp/bt4-provider-timing-audit.json`, `.tmp/bt4-summary-timing-audit.json`, `.tmp/bt4-benchmark-admission-audit.json`; current four-package identities in `.tmp/bt4-benchmark-admission-matrix-handoff/manifest.json`. | Run the union of connector and later timing/summary selections on the same candidate. Require independent elapsed comparisons, explicit unavailable values and rejected missing selector latency. Model-reported metrics remain `reported_unverified`; generic benchmark runner lifetime and CAP-3 performance/cost authenticity are separate obligations. |

The current core wheel is SHA-256
`208409495b4ae79d68e9d92472c3b2c9e0227157a22924c0f8deaf299af81479`;
SDK `0.7.0a1`, reference `0.3.0a1` and starter `0.3.0a1` retain the exact
wheel/sdist identities in that manifest. Preflight compared package source
bytes with the declared wheels/sdists and bound current copied test/script inputs.
The combined selection derives from the earlier gate plus each subsequent scoped
manifest; the old 58-file helper was not run unchanged. The resulting local
execution inventory and results are under `.tmp/bt4-combined-gate/` and do not
replace this requirement table or the canonical baseline as authority.

The table's remaining execution predicates were then run without a runtime repair.
All four numbered requirements pass for the admitted paths and declared ceilings
above. The current audit is `.tmp/bt4-combined-gate/audit.json`; its 15 checks pass,
including identical unique test identities, current input/artifact hashes and
the separate actual llama.cpp observations. The earlier 58-path selection and
the subsequent scoped manifests resolve to 136 selected paths (including the
SDK test directory), 1,646 copied inputs and 1,344 unique tests per run.

| Current envelope | Passed | Failed / errors / skipped | JUnit seconds |
|---|---:|---|---:|
| Source, Windows Python 3.11 | 1,344 | 0 / 0 / 0 | 469.932 |
| Installed, Windows Python 3.11 | 1,344 | 0 / 0 / 0 | 469.870 |
| Installed, Windows Python 3.12 | 1,344 | 0 / 0 / 0 | 565.045 |
| Installed, Linux Python 3.11 | 1,344 | 0 / 0 / 0 | 459.913 |
| Installed, Linux Python 3.12 | 1,344 | 0 / 0 / 0 | 449.176 |

Each installed cell verifies 876 package origins under its own site-packages,
wheel identities, pip dependencies, and unchanged copied inputs before/after
execution. Structural preflight verifies all 953 core and 29 SDK Python files
against source, wheel and sdist bytes. Existing artifacts were reused; no package
source, wheel or environment installation changed. Native/contract tests use
explicit model/policy/fault fixtures; their passing counts are not provider proof.

Separate fresh stock installed Windows 3.11 `orket runtime --card` runs use actual
llama.cpp `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, server build
`b10809-5266f24da`, with two model receipts each. The success control exits 0 and
retains `done`; required missing attribution exits 1 and retains
`terminal_failure`. Narration, final truth, phase-4 publication, released admission
and confirmed Windows Job cleanup agree. Evidence is `cli-success.json` and
`cli-failure.json` under the combined gate root, including retained file hashes.
Both are **degraded / success** proof observations: discovery reconciliation
tries the missing `<installed site-packages>/model` path, while execution consumes
the staged workload root. The fresh `discovery_reconcile_failed` log identifies
that cause; resolving this root-authority mismatch belongs to BT-5. This is not a
provider fallback or primary-startup proof. The combined audit inherits that
degraded path; the native/fixture matrix is primary / success.

Source bytes stayed unchanged during execution. Prior native generation,
extension and Piper evidence hashes still match; that retained evidence is
historical, not newly executed voice/platform coverage. The refreshed canonical
baseline at `2026-09-14T02:01:13.515639Z` reports `collection_ok=true` and
`release_ready=false`. Docs hygiene passes. Broader thread/host/remote-effect
ownership, full-suite/hosted-CI/release proof and BT-5/C/D/E/CAP obligations remain
open; none is inferred from these 1,344-case runs.

This resumed gate changes only the canonical plan, project registry, roadmap
execution note, current-authority proof pointer, runtime-result contract status,
and canonical baseline. Local helper/evidence paths are
`.tmp/bt4_combined_gate.py`, `.tmp/bt4_gate_cli_installed.py` and
`.tmp/bt4-combined-gate/`. The original handoff snapshot and failed checkpoint
observations remain unchanged. No commit, tag, release, push or whole-lane closure
is included.

Exact repository-visible files touched by this resumed gate:

- `CURRENT_AUTHORITY.md`
- `docs/ROADMAP.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`

### BT-4 native verification lifetime checkpoint: 2026-09-13

Status: native-command repair implemented and scoped verification complete; BT-4 remains open.

`RuntimeVerifier` now delegates native commands to an application-owned supervisor.
A Windows Job Object owns the initially suspended command before execution;
Linux establishes a subreaper before dispatch and reaps adopted children.
Commands stop descendants on normal completion, failure, timeout and cancellation.
Cleanup survives repeated caller cancellation and ordinary `asyncio.run` shutdown,
retains capture through cancelled collectors, and reports missing acknowledgement
as uncertainty. Failed commands stop subsequent admission. Raw output has a 4 MiB
bound per stream; excess output cannot pass acceptance. The cancellation exception
retains its observed result. The versioned lifetime contract, delta, authority,
runbook and taxonomy name this boundary without claiming other executors migrated.

Evidence retained in this worktree:

- Before repair, two public `RuntimeVerifier.verify()` cases failed in 5.60 s:
  cancellation left descendants running, and a one-second timeout still awaited
  inherited pipes at the five-second test deadline. Evidence:
  `.tmp/bt4-verification-lifetime-before.xml`.
- Initial Windows and Linux process/output checks each passed six cases. Expanded
  descendant/shutdown checks then passed nine per OS. These use real subprocesses
  and independent psutil identities and heartbeat files, with fixture teardown.
- The first broader source run was 48 passed and two failed. Both failures were
  the successful leader-exit test's five-second budget also timing a second Python
  startup. That success-only bound is now ten seconds; cleanup-only cases retain
  five seconds. Both corrected cases passed in 13.22 s. Original failure evidence
  remains `.tmp/bt4-verification-supervisor-source.xml`; follow-up:
  `.tmp/bt4-verification-leader-followup.xml`. Final results are recorded below.
- Installed Windows/Linux Python 3.11/3.12 proof is collected under
  `.tmp/bt4-verification-lifetime-matrix/`. Each harness is outside the checkout,
  omits runtime source, removes `PYTHONPATH`, validates installed origins and runs
  `pip check`. Reports identify the exact wheel; no global installation changes.
- Real llama.cpp standard-runtime success: session
  `verification-live-fe82df0191004614bec8dfccf18b1a04`, model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, Windows Python 3.13.11 source.
  Four cards and the original session reached accepted `done`; 15 retained CLI
  acceptance commands recorded `windows_job`, exit zero, complete capture and
  confirmed cleanup. All recorded supervisor PIDs were absent at the subsequent
  observation, and the engine closed. The legacy runtime-verifier stage was
  disabled; declared card CLI acceptance still invokes the new `RuntimeVerifier`.
  This proves that actual acceptance path, not legacy fixture execution. Evidence:
  `.tmp/bt4-verification-live/report.json`. No sandbox was created.
- The first installed campaign exposed 46 failures and 43 passes on each Windows
  interpreter, while both Linux interpreters passed all 89 cases. Windows venv
  redirectors separate the launched PID from the interpreter PID; the original
  equality check rejected otherwise valid acknowledgements. A separate direct
  process probe also reproduced CPython's buffered-stdin daemon shutdown abort
  (exit 3221225477). The transport now binds a private request nonce, requires
  normal exit, and retains transport/supervisor PIDs separately; the worker reads
  the raw descriptor. The intermediate source repair still had 16 failures and
  nine passes before fixing PID correlation. After both repairs, all 26 targeted
  source cases passed on Windows Python 3.11 in 10.02 s. Both unsuccessful
  campaigns remain retained; they are not rewritten as successful proof.
- The final installed campaign passes all 94 selected cases in every cell, with
  zero failures, errors or skips. Each checked 561 runtime/SDK module origins,
  all in its isolated `site-packages`, and confirmed the packaged worker/backend
  paths. This is the scoped native-verifier/card-acceptance envelope, not the full
  installed release envelope.

| Installed cell | Passed | Seconds (JUnit) |
|---|---:|---:|
| Windows Python 3.11.14 | 94 | 32.500 |
| Windows Python 3.12.2 | 94 | 32.940 |
| Linux Python 3.11.16 | 94 | 18.489 |
| Linux Python 3.12.3 | 94 | 18.624 |

Final artifacts: wheel SHA-256
`4b438456a39717a9833189c61f70bddb0104bd8537452d6eed528c4ef9589cdf`;
sdist SHA-256
`16d0732e9e2c86903fdb595ec1907880790145ed52558dbba62f091fb3d7da6f`.
All 923 packaged Python files match current source with no missing or extra files:
`.tmp/bt4-verification-artifact-source.json`. Matrix details and the initial failed
campaign remain in `.tmp/bt4-verification-lifetime-matrix/report.json` and its
`initial/` and `final/` directories.

The final canonical source campaign passed: **5,231 passed, 78 skipped, two
warnings in 1,081.73 s** (`python -m pytest -q`, with JUnit/log capture and
`ORKET_DISABLE_SANDBOX=1`). Evidence: `.tmp/bt4-verification-full-source.xml`,
`.tmp/bt4-verification-full-source.log`, and
`.tmp/bt4-verification-full-source-report.json`. This campaign
also verifies the earlier three BT-3 structural corrections. Skips remain explicit
coverage exclusions, including opt-in localhost Gitea cases; they do not become
runtime proof. The pre-existing warnings concern the deprecated domain import and
a governed generation budget below 256 tokens. This mixed-layer test campaign
does not close the baseline's lint, taxonomy or architectural exceptions.

The final live run, after the Windows repairs, is
`verification-live-b580e14d72444076a0be4e6cd2ae1ca5`. It again completed all four
cards and the original session, retained eight model receipts and 15 passing
native command receipts, observed both transport and supervisor PIDs absent, and
closed the engine. The canonical live report retains the preceding run too.

Structural verification: targeted Ruff and docs-project hygiene pass. The refreshed
baseline at `2026-09-13T08:29:19.821727Z` reports `collection_ok=true` and
`release_ready=false`: 110 pre-existing runtime Ruff issues, 3,419 missing layer
labels among 4,531 test functions, 74 oversized runtime files and 236 oversized
functions. All 18 original plan H2 headings and six sealed proof hashes are
preserved. Full worktree inventory is 393 changed paths; this checkpoint touches
the 22 paths listed below. Final inspection found no remaining owned supervisor or
fixture processes on Windows or Linux. Docker still lists only the pre-existing
`vibe-rail-gitea` container. The original main checkout is clean, this worktree's
index is empty, and `git diff --check` passes. Final audit:
`.tmp/bt4-verification-audit.json`. No commit, tag or release was created.

Architecture checklist: AC-01/02/03/04/06/08/10 pass for this changed boundary.
OS time and correlation identity belong to effect supervision, not pure decisions;
the standalone worker imports only fixed package-owned backends. AC-05/07/09 are
partial for the broader runtime: legacy execution remains unowned, cancellation
events are not a durable recovery journal, and epic consumers still need truthful
uncertainty propagation. BT-4 owns those explicit follow-ups.

Proof classification: actual native process and provider flows are live / primary /
success for their recorded positive observations. Baseline reproductions are
live / primary / failure. Substitute-supervisor protocol negatives are contract
fault injection, not live proof that an OS refused termination. Broader authority
checks, inventory, hashes, taxonomy and lint are structural.

Remaining blockers or drift: legacy `Orchestrator.verify_issue` still offloads
`VerificationEngine.verify` into a thread with independent blocking subprocesses;
Docker container lifetime and older process helpers have not migrated. Process
tests cover ordinary asyncio shutdown, not every API/engine shutdown path or abrupt
host loss. OS termination refusal and durable propagation/fencing of unconfirmed
cleanup remain unproved. Typed epic/CLI outcomes, live unsuccessful epics and
measured connector telemetry remain BT-4 work. Earlier BT-3 recovery, BT-5 relative
database authority and all later gates stay open. This checkpoint cannot authorize
terminal-state release when an owned effect remains uncertain.

The remaining legacy cancellation failure is now reproduced through public
`Orchestrator.verify_issue` with a real SQLite card and native fixture. After
caller cancellation, all three fixture processes remained alive and each heartbeat
grew by 28 bytes over the next 200 ms. The proof driver then stopped those exact
process identities and drained its offloaded executor; teardown is confirmed.
Evidence: `.tmp/bt4-legacy-verification-reproduction/report.json`, live / primary /
failure, Windows Python 3.13.11. This direct-entrypoint reproduction cancels before
the optional sandbox stage; it is not full engine startup/shutdown proof. The next
repair must share the existing fixture policy/result authority while replacing
its abandoned thread/subprocess lifetime, without treating Docker CLI termination
as container teardown.

Exact files touched in this checkpoint (22):

- `CURRENT_AUTHORITY.md`
- `docs/ROADMAP.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_VERIFICATION_LIFETIME_BT4_2026-09-13.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`
- `orket/adapters/execution/owned_command_linux.py`
- `orket/adapters/execution/owned_command_process.py`
- `orket/adapters/execution/owned_command_windows.py`
- `orket/adapters/execution/owned_command_worker.py`
- `orket/application/services/runtime_verifier.py`
- `orket/application/services/verification_process_supervisor.py`
- `orket/core/contracts/owned_command.py`
- `tests/contract/test_verification_supervisor_protocol.py`
- `tests/integration/test_verification_process_lifetime.py`
- `tests/integration/test_verification_shutdown.py`
- `tests/integration/test_verification_supervisor_receipts.py`
- `tests/integration/verification_lifetime_worker.py`
- `tests/integration/verification_shutdown_worker.py`

### BT-4 fixture lifetime cutover: 2026-09-13

Status: implemented; scoped verification complete. BT-4 remains open.

The opening public `verify_issue` cancellation reproduced three real fixture
processes continuing to write after cancellation. The proof driver confirmed
teardown; `.tmp/bt4-legacy-verification-reproduction/report.json` retains that
primary-path failure. This checkpoint replaces the offloaded synchronous path
with `FixtureVerificationService`, one pure fixture policy/result interpreter,
the existing native supervisor, and a separate Docker resource owner. Contract
delta: `docs/architecture/CONTRACT_DELTA_FIXTURE_LIFETIME_BT4_2026-09-13.md`.
Durable authority: `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`.
Starting source inventory: `.tmp/bt4-fixture-start.json`.

Native and Docker execution share one runner and result interpreter. Scenario
changes are applied only after the observed outcome. Unknown modes and invalid
timeouts fail before execution; the production native guard is preserved.
Native containment is a path policy, not read-only storage or hostile-code
isolation. Docker retains a fresh name/owner before creation, verifies its full
immutable ID and label, attaches to that ID, inspects terminal state, and requires
agreement with the attached CLI exit code. Cleanup removes only the bound ID
and requires a successful daemon absence observation. An empty listing after a
lost create acknowledgement remains uncertain because a daemon request may still
be in flight. Unexpected adapter errors also run cleanup and retain diagnostics.

Nullable `VerificationResult.process_lifetime` persists either native
`owned_command.v1` or container `owned_container.v1` observations. Cancellation
and `FixtureVerificationUncertain` do not publish scenario changes or a new
`last_run`. Cancellation exceptions retain actual cleanup observations. Events
are diagnostic and do not substitute for a durable recovery journal.

Removal ticket **BT4-FIXTURE-SYNC-RETIRE**: Orket Core removes the existing
`FixtureVerifier.verify` and `VerificationEngine.verify` migration tombstones and
deprecated exports during the 0.7.0 compatibility cutover after caller inventory
and contract acceptance. Until removal they refuse execution before effects;
they must not forward into application code or create another event loop.

Observed verification:

- Source fixture regression: 28 passed, including public real-SQLite persistence,
  native descendants, timeout, repeated cancellation and loop responsiveness.
  Final source fixture selection: **43 passed** in **10.52 s**
  (`.tmp/bt4-fixture-final-targeted.xml`). The opening seven failures were test-driver reads treating `IssueRecord` as a
  dictionary; corrected tests use its actual model projection.
- Native supervisor/regression selection: 36 passed before the final five
  ownership-negative cases. All 15 final fixture ownership contract cases passed
  separately. These injected daemon failures are contract proof, not live OS refusal.
- Installed initial wheel: 128 passed in each Windows/Linux Python 3.11/3.12 cell.
  A later Linux 3.12 run raced its harness refresh and still ran 128 while the other
  cells ran 133; that intermediate campaign is not accepted as the final matrix.
  Evidence remains in `.tmp/bt4-fixture-matrix/report.json`, including prior runs.
  Final refresh completed before execution. The final wheel passed **133 tests in
  every cell**, with no failures, errors or skips. All **634** observed runtime/SDK
  origins per cell were inside the isolated installation; harness source hashes
  matched before and after pytest. Final JUnit times: Windows 3.11 **42.136 s**,
  Windows 3.12 **42.204 s**, Linux 3.11 **29.297 s**, Linux 3.12 **29.478 s**.
  Final wheel SHA-256: `996ab94d41aa4d293fea26f6d048c38ab88ae69a4edbdc5071e383d8bab081b6`;
  sdist: `844beefd083e2c9fb5dbad21284f396da6f4a98d4399623285bf81280b80b4a2`.
  All **927** packaged runtime Python files match source bytes.
- Live Docker: all six source cases and all six cases per installed Windows
  3.11/3.12 environment passed against Docker Desktop's Linux daemon: success,
  mismatch, leader exit, timeout, cancellation and repeated cancellation.
  Independent daemon observers saw descendants before interruption and absence
  afterward. The proof driver removed no leftovers. Initial evidence:
  `.tmp/bt4-fixture-container/report.json` and
  `.tmp/bt4-fixture-container-installed/<cell>/report.json`.
  The final installed wheel also passed all six Docker cases per Windows
  interpreter, with installed service origins recorded and zero proof-driver
  removals. This establishes live primary-path success for those observed cases.
- The intermediate full source campaign passed **5,252 tests**, with **78 skips**
  and **two warnings**, in **1068.44 s**. It began before the final adapter-error
  guard and import-ordering repairs and is not final-source proof. The clean
  campaign checks runtime/test/script source hashes before and after execution;
  the final frozen-source run passed **5,257 tests**, with the same **78 skips**
  and **two warnings**, in **1042.30 s**. No runtime/test/script source file changed
  during execution. Evidence: `.tmp/bt4-fixture-final-full-source.xml`, `.log`,
  and `-report.json`. All verification jobs are terminal.

The explicit rerunnable Docker acceptance script is
`scripts/acceptance/verify_fixture_container_lifetime.py`, with canonical output
`benchmarks/results/acceptance/fixture_container_lifetime.json` and the shared
diff ledger. Routine pytest creates no Docker containers.

The final structural baseline reports `collection_ok=true`, `release_ready=false`
(`2026-09-13T09:30:53.710887Z`): **110** existing runtime Ruff findings,
**3,407** missing test layers across **4,532** test functions, **74** oversized
runtime files and **235** runtime functions over 70 lines. No structural release
claim follows from the passing runtime checks.

Structural review: touched runtime and test Ruff passes. New Python files remain
below 400 lines and new functions below 70. The pre-existing oversized
`orchestrator_ops.py` does not grow; `schema.py` remains below 400 lines.
AC-01 through AC-06 and AC-08 pass for this scope. AC-07 and AC-09 remain partial:
uncertain lifetimes still need epic admission/terminal propagation and durable
host-death recovery. AC-10 is updated in the contract, current authority, runbook
and event taxonomy. Project hygiene passes. Final audit confirms **20** scoped
paths and **405** total worktree changes, all **18** original H2 headings, all six
sealed hashes, **927** packaged runtime Python files, clean original `main`, empty
index and clean `git diff --check`. Windows/Linux owned-process inventories are
empty; Docker retains only the pre-existing `vibe-rail-gitea` container. Audit:
`.tmp/bt4-fixture-audit.json`. Changes remain uncommitted in the requested worktree.

Not verified and remaining blockers or drift: WSL Docker execution is blocked;
the observed command reports that Docker Desktop WSL integration is disabled.
Windows clients talking to a Linux daemon are not Linux-client proof. No global
Docker setting was changed. Lost create/remove acknowledgements, malformed daemon
observations, daemon refusal and unavailable cleanup have contract fault-injection
proof only; in-flight Docker creation was not interrupted in live acceptance.
Host death and OS refusal are not live-confirmed cleanup paths.
Broader application shutdown ownership, durable unresolved-effect recovery,
epic terminal propagation, typed CLI outcomes and measured connector telemetry
remain BT-4 work. Existing BT-3 recovery, BT-5 relative database authority, C/D,
E1/E2, CAP-1/2/3 and the eleven findings remain active. No release is claimed.

Exact files touched in this checkpoint (20):

- `CURRENT_AUTHORITY.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_FIXTURE_LIFETIME_BT4_2026-09-13.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`
- `orket/adapters/execution/fixture_docker.py`
- `orket/application/services/fixture_container_owner.py`
- `orket/application/services/fixture_verification_service.py`
- `orket/application/workflows/orchestrator_ops.py`
- `orket/core/contracts/owned_container.py`
- `orket/core/domain/fixture_verifier.py`
- `orket/core/domain/verification.py`
- `orket/schema.py`
- `scripts/acceptance/verify_fixture_container_lifetime.py`
- `tests/adapters/test_verification_subprocess.py`
- `tests/application/test_orchestrator_verification_async.py`
- `tests/contract/test_fixture_container_ownership.py`

### BT-4 CLI outcome counterexample: 2026-09-13

Status: reproduced; implementation remains open.

A real installed Windows Python 3.11 CLI run with llama.cpp completed its single
requirements card and retained accepted card evidence, then correctly recorded
session `b8c48630` as `terminal_failure` because required source attribution was
missing. Nevertheless `orket runtime --card attribution_epic` returned **0**.
The owned CLI process tree was confirmed stopped. This is a live primary-path
failure, separate from the passing fixture-lifetime repair. Evidence:
`.tmp/bt4-cli-outcome-reproduction/report.json`; retained foreign workspace:
`C:/Users/jonmc/AppData/Local/Temp/orket-bt4-attribution-epic-d714mj6y`.
Actual provider/model observations remain in its model receipts.

The same live installed failure also reproduces through both compatibility
surfaces. All three used llama.cpp with
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`, retained two model receipts, and
confirmed the CLI process tree stopped:

| CLI option | Session | Retained state | Exit | Narration |
| --- | --- | --- | --- | --- |
| `--card` | `b8c48630` | `terminal_failure` | 0 | Starting card only |
| `--epic` | `8de65ef6` | `terminal_failure` | 0 | `Orket EOS Run Complete` |
| `--rock` | `e09bed28` | `terminal_failure` | 0 | `Card attribution_epic Complete` |


Earlier probes are retained without upgrading their claims: an empty epic was
rejected during admission; the initial blocked configuration was reset and
completed with accepted evidence; a dependency cycle and contradictory acceptance
criteria raised failures with exit 1. Only the required-source-attribution case
establishes the false zero exit. The next repair must carry typed authoritative
outcomes from `EpicRunFinalizer` through card dispatch to the CLI. It must reuse
canonical control-plane result/evidence vocabulary and preserve pending or
uncertain states; interpreting transcript text or rereading a latest-path report
is not an adequate result authority. No CLI repair is claimed by this checkpoint.

### BT-4 typed runtime outcome cutover: 2026-09-13

Status: implemented; scoped source and installed verification complete. BT-4 and
the architectural-truth lane remain active.

Starting source snapshot: `.tmp/bt4-result-start.json` (4,304 Git-visible files).
Contract: `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`. Contract delta:
`docs/architecture/CONTRACT_DELTA_RUNTIME_RESULTS_BT4_2026-09-13.md`.

`RuntimeExecutionResult` carries the canonical retained run/final-truth records,
a publication digest reference, evidence references, diagnostic reason and an
explicit transcript. Publication returns it only after verifying required
publication effects; finalization, recovery and public dispatch preserve it.
Accepted cards alone cannot establish successful epic completion. Failed workload
and denied approval recovery return the retained typed failure without redispatch.
Approval waits have no invented final truth. Interrupted execution/publication
retains an unresolved observation and does not release uncertain admission.
Cancellation retains `CancelledError` semantics and an observation after owned
cleanup, without claiming the durable run was cancelled.

Parallel dispatch drains the batch before selecting an outcome. Cancellation and
unresolved infrastructure/cleanup effects take precedence over a business failure
or approval pause. A concurrent failed card cannot hide another card's uncertain
effects, publish terminal failure, or release the unfinished admission.

The CLI aliases share the same application result projection. They print success
only after required engine cleanup and exit 0 only for verified success. Other
returned outcomes exit 1, interruption exits 130, and usage errors remain 2.
Collections use ordered `-member-<1-based index>` child session/build identities,
retain the declared member set, close each child, and stop before subsequent
members or the bug-fix phase on non-success. Extension actions and Gitea worker
continuations require successful typed results; approval decision responses expose
a nested runtime outcome. Probe serializers and native recovery workers consume
the changed result rather than converting a normal return into success.

Observed workload path: primary. The live CLI also reports the existing degraded
startup structural-reconciliation path. Observed result: success in the scoped
proof below. Proof kinds are separated:

- Real-filesystem/SQLite integration: 37 focused completion, approval and
  publication recovery tests pass. Actual SQLite aborts, missing/corrupt evidence,
  and retained failure recovery preserve the earlier no-redispatch/no-republication
  checks under the new result contract.
- Native process/collection integration: repeated cancellation observes child
  cleanup while leaving unfinished admission active; actual two-member collections
  retain distinct run identities and stop correctly on first/second-member failure.
- The final failure-priority/approval selection passes 20 tests in 29.96 seconds.
  It includes mixed business/uncertain-cleanup failures in either order against
  actual SQLite/admission, and two ASGI approval decision requests through the
  actual router/engine/stores. Approval resolution status remains distinct from
  the resumed runtime's success/failure. These use deterministic models and
  explicit infrastructure fault injection; they are not live daemon-refusal or
  authenticated external HTTP/provider proof.
- Contract proof: strict typed result validation and cleanup/narration guards.
  The final focused selection passes 26 tests in 5.79 seconds. Synthetic records
  are explicitly test fixtures, not retained runtime evidence. The former isolated
  orchestrator test used invalid placeholder control-plane records; it now checks
  that those cannot establish a published result. The obsolete dict-return AST
  assertion is replaced by real collection behavior and typed-contract checks.
- The caller migration survey first reported 59 failures, 404 passes and 17 skips;
  most failures were obsolete return/exception expectations. Its later run had
  481 passes, 2 failures and 17 skips; both remaining webhook doubles lacked the
  required close method and pass in the final focused selection. No failing survey
  is presented as acceptance.
- Live source llama.cpp: all eight fresh success/failure runs through `--card`,
  `--epic`, `--rock` and `python main.py --card` match retained SQLite truth. Required missing attribution
  gives `terminal_failure`/exit 1; accepted successful runs give `done`/exit 0.
  Each run has actual model receipts and confirmed native CLI process cleanup.
  Evidence: `.tmp/bt4-result-cli-source/report.json`, with prior runs retained.
- The first broad source run had 5,279 passes, one failure, 78 skips and two
  warnings; Python source also changed while it ran. Its routing-only structural
  assertion had not followed the new child-owner helper. The corrected structural
  selection passes all 32 tests and retains the forbidden-authority checks.
  The earlier campaign remains under `.tmp/bt4-result-before-batch-priority-source/`
  and does not count as final acceptance.
- Final full source: 5,287 passed, 78 skipped and two warnings in 1,126.72 seconds.
  `.tmp/bt4-result-final-full-source-report.json` records pytest exit 0 and matching
  before/after Python source hashes; the final audit also matches those hashes
  against the current checkout. The warnings retain the existing deprecated
  `orket.domain` import and deliberately small `GenerateRequest.max_tokens` case.
- The final installed matrix passes the 185-case result, approval, publication,
  recovery and native/fixture ownership envelope on all four cells. `pip check`
  passes; harness hashes match before and after execution; all 646 observed
  runtime/SDK origins per cell are inside that cell's isolated installation.
  The earlier 178-case wheel/matrix is preserved under `before-batch-priority`
  and does not substitute for this final build.
- Final-wheel live llama.cpp: all twelve runs through `--card`, `--epic` and
  `--rock` on Windows Python 3.11/3.12 match exit, narration, session ledger,
  control-plane run, final truth and completed publication. Every run retains
  two actual model receipts and confirmed native CLI cleanup. Failure exits 1;
  verified success exits 0. Installed package metadata and origin are checked
  against the final wheel before each run. Evidence:
  `.tmp/bt4-result-cli-installed/report.json`, schema-2 observations.
  The first expanded proof-reader incorrectly scanned only `.db` files and missed
  `.sqlite3` authority stores; its failed observation remains historical. All
  twelve final observations scan both formats and retain the actual records.
- An additional installed empty-workload probe exits 1 before admission because
  `WorkloadContractV1.units` requires at least one unit. It produces no run record
  and cannot establish incomplete-run CLI proof. Its failed expected-incomplete
  oracle remains at `.tmp/bt4-result-cli-incomplete/report.json`. Actual incomplete
  result behavior passes the installed SQLite integration envelope; pending and
  incomplete public-CLI flows remain an explicit proof limit.

Final artifacts, unreleased core version 0.6.2:

| Cell | Passed | Skipped | Seconds |
| --- | ---: | ---: | ---: |
| Windows Python 3.11.14 | 185 | 0 | 167.060 |
| Windows Python 3.12.2 | 185 | 0 | 162.266 |
| Linux Python 3.11.16 | 185 | 0 | 301.432 |
| Linux Python 3.12.3 | 185 | 0 | 294.652 |

Wheel SHA-256:
`d934f24b7d868895266ebd4508831295e048b1fa5d299be24c9934e5446d953f`.
Sdist SHA-256:
`b1b98830080afdf289adf81cae2d4c69077de9e919d20b01589d21c5ec2e4194`.
All 933 packaged runtime Python files in both archives match current source.
Matrix details: `.tmp/bt4-result-matrix/report.json`; static audit:
`.tmp/bt4-result-static-audit.json`. No new Ruff diagnostics or missing labels on
changed tests are observed. New Python modules/functions meet size limits; the
renamed pre-existing isolated orchestrator test remains oversized (93 to 94 lines).
Three existing oversized runtime modules require narrow correctness changes:
webhook cleanup/result handling (433 to 444 lines), engine result annotation
(457 to 458), and approval result serialization (480 to 483).

The refreshed canonical baseline reports `collection_ok=true`,
`release_ready=false`: 110 runtime Ruff diagnostics, 3,387 unlabeled test functions
out of 4,545, 74 oversized runtime modules and 235 long runtime functions remain.
These observations are not a release gate pass.

Final audit: `.tmp/bt4-result-final-audit.json` passes. The canonical plan's 443
Git-visible changed paths and this checkpoint's 74-file scope match Git and the
starting snapshot. All 18 original H2 headings and all six sealed fixture digests
are preserved; no resealing occurred. Original main remains clean, the worktree
index is empty, `git diff --check` and docs project hygiene pass. No owned native
verification worker remains on Windows or Linux; Docker lists only the existing
operator-owned `vibe-rail-gitea` container. This cutover creates no sandbox resources.

Scoped architecture checklist:

| Check | Disposition and evidence |
| --- | --- |
| AC-01 | partial: `orket/adapters/vcs/gitea_webhook_handlers.py` retains its pre-existing orchestration dependency and consumes that engine's typed return without adding an application import. That coupling is not widened. BT-5/C owns the remaining boundary. |
| AC-02/AC-03 | pass: no decision-node behavior or decision input contract changes. |
| AC-04 | pass: retained caller/runtime identities and deterministic ordered member suffixes; no new identity/timing source for deterministic decisions. |
| AC-05 | partial: new application result/cleanup owners preserve admission and publication authority; webhook/background lifecycle and collection bug-fix phase ownership remain BT-4/BT-5 work in the paths named above. |
| AC-06 | partial: the existing webhook adapter lacks complete side-effect classification; this checkpoint does not widen its effect set. BT-5/C owns classification and ingress ownership. |
| AC-07 | pass within the proved outcome envelope: publication is verified, non-success blocks callers, cleanup precedes success output, and the installed live success/failure paths match retained truth. The public-CLI pending/incomplete proof limit remains explicit. |
| AC-08 | pass: collection phase and webhook outcome payloads are documented in `docs/architecture/event_taxonomy.md`; nested result schemas are versioned. |
| AC-09 | pass within retained recovery scope: run/final-truth identity, publication digest and unfinished admission/preparation/outcome/pause references are preserved; installed recovery tests retain no-redispatch/no-republication assertions. Wider host-death and owner recovery remain open. |
| AC-10 | pass: the result spec, contract delta, authority snapshot, runbook and approval/API/event contracts change together. |

Remaining blockers or drift: app-wide shutdown/host-death recovery and measured
connector telemetry remain BT-4 work. Existing collection bug-fix phase ownership
and the wider authority/relative-database discrepancies remain BT-5 work. The
webhook adapter still has pre-existing orchestration coupling and incomplete
adapter classification; this change observes returned failure and closes its
engine without claiming to resolve that broader ownership design. Existing
oversized files require small signature, serializer, outcome or cleanup changes;
all newly added Python modules/functions remain within the size limits. No new
capability, release, commit or tag is admitted by this checkpoint.
The live CLI's structural startup warning remains a degraded observation owned
by the broader authority/startup work; successful workload truth does not claim
that startup reconciliation or host-wide lifecycle is healthy. No Linux live
provider or WSL Docker proof is claimed by this cutover.

Exact files touched in this checkpoint (74):

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_RUNTIME_RESULTS_BT4_2026-09-13.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`
- `orket/adapters/vcs/gitea_webhook_handlers.py`
- `orket/application/services/epic_dispatch_batch.py`
- `orket/application/services/epic_publication_service.py`
- `orket/application/services/runtime_execution_observation.py`
- `orket/application/services/runtime_execution_result_service.py`
- `orket/application/services/runtime_result_lifetime.py`
- `orket/application/services/runtime_result_projection.py`
- `orket/cli.py`
- `orket/core/contracts/runtime_execution_result.py`
- `orket/exceptions.py`
- `orket/extensions/runtime.py`
- `orket/interfaces/cli.py`
- `orket/orchestration/engine.py`
- `orket/orchestration/engine_approvals.py`
- `orket/organization_loop.py`
- `orket/runtime/execution/__init__.py`
- `orket/runtime/execution/epic_run_finalize.py`
- `orket/runtime/execution/epic_run_orchestrator.py`
- `orket/runtime/execution/epic_run_result_boundary.py`
- `orket/runtime/execution/execution_pipeline.py`
- `orket/runtime/execution/execution_pipeline_card_dispatch.py`
- `orket/runtime/execution/execution_pipeline_resume.py`
- `orket/runtime/execution/gitea_state_loop.py`
- `scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py`
- `scripts/governance/record_truthful_runtime_packet1_live_proof.py`
- `scripts/governance/record_truthful_runtime_packet2_repair_live_proof.py`
- `scripts/probes/probe_support.py`
- `scripts/productflow/run_governed_write_file_flow.py`
- `scripts/run_provider_codegen_matrix.py`
- `scripts/security/build_tool_gate_audit.py`
- `tests/adapters/test_gitea_webhook.py`
- `tests/adapters/test_model_invocation.py`
- `tests/application/test_control_plane_workload_authority_governance.py`
- `tests/application/test_engine_approvals.py`
- `tests/application/test_execution_pipeline_gitea_state_loop.py`
- `tests/application/test_execution_pipeline_issue_entrypoints.py`
- `tests/application/test_execution_pipeline_protocol_run_ledger.py`
- `tests/application/test_execution_pipeline_run_ledger.py`
- `tests/application/test_execution_pipeline_session_status.py`
- `tests/application/test_organization_loop.py`
- `tests/application/test_tool_gate_enforcement_closure.py`
- `tests/contract/test_epic_batch_result_priority.py`
- `tests/contract/test_runtime_result_cleanup.py`
- `tests/contract/test_runtime_result_projection.py`
- `tests/helpers/epic_publication_recovery_worker.py`
- `tests/helpers/epic_publication_worker.py`
- `tests/helpers/runtime_result.py`
- `tests/integration/policy_enforcement/test_runtime_policy_enforcement.py`
- `tests/integration/test_card_completion_epic_outcomes.py`
- `tests/integration/test_empirical_verification.py`
- `tests/integration/test_engine_boundaries.py`
- `tests/integration/test_epic_admission_recovery.py`
- `tests/integration/test_epic_approval_continuation.py`
- `tests/integration/test_epic_completion_publication.py`
- `tests/integration/test_epic_outcome_recovery.py`
- `tests/integration/test_epic_preparation_recovery.py`
- `tests/integration/test_epic_publication_recovery.py`
- `tests/integration/test_epic_run_admission.py`
- `tests/integration/test_idesign_enforcement.py`
- `tests/integration/test_runtime_execution_results.py`
- `tests/integration/test_system_acceptance_flow.py`
- `tests/interfaces/test_cli_startup_semantics.py`
- `tests/live/test_system_acceptance_pipeline.py`
- `tests/runtime/test_epic_run_orchestrator.py`
- `tests/runtime/test_extension_components.py`

### BT-4 CLI unfinished-outcome proof: 2026-09-13

Status: cancellation observation repair implemented; scoped source and installed
acceptance passes. The previous goal turn made implementation and
verification progress. BT-3/BT-4 and the complete lane remain active.

Starting source snapshot: `.tmp/bt4-cli-lifecycle-start.json` (4,317 Git-visible
files). The preceding outcome checkpoint and its final artifacts remain unchanged
historical evidence; this checkpoint builds a separate wheel and proof matrix.

The generic CLI interruption handler discarded `RuntimeExecutionCancelled.result`.
All six native cancellation cases reproduced exit 130 with `[HALT]` but without
the retained session identity or evidence. The CLI now catches the typed
cancellation first, joins engine cleanup and renders the existing application
result before returning 130. An interrupted collection also keeps 130 rather
than inheriting its ordinary non-success projection of 1. Pre-observation generic
interruption retains its generic handler without inventing durable records.

New native integration proof calls the actual `orket.cli.main` runtime entry in
an independent interpreter, with real engine, admission, cards/control-plane
SQLite, finalizer, publication and cleanup owners. No fixture supplies a runtime
result or replaces finalization/publication. Boundaries are explicit:

- Approval wait uses a fixture model and custom loop policy requiring `write_file`
  approval. No protected file is written; the run/admission remain open, final
  truth and terminal publication remain absent, and the CLI exits 1 with references.
- Incomplete execution injects loss of real build membership before dispatch.
  The actual runtime publishes `incomplete` / `waiting_on_observation`, with no
  final truth, and exits 1. This supplies the missing admitted-incomplete proof;
  the earlier empty-input refusal remains a separate pre-admission observation.
- Cancellation starts a real child/grandchild tree with independently observed
  heartbeat writes. A real SIGINT or repeated task cancellation occurs only after
  all three processes are observed. SIGINT is raised inside the CLI interpreter
  after the independent parent requests it; this is not external terminal
  control-event or forced-kill acceptance. The parent checks exit 130, retained unfinished
  run/admission, no fabricated final truth/publication, and no surviving fixture
  process or later heartbeat writes after cleanup.

Each case runs through `--card`, `--epic` and `--rock`. These are native public
entry-function fixtures, not claims that the stock CLI exposes custom-policy or
fault-injection flags, or that cancellation proves remote-provider termination.
The child removes inherited `PYTEST_CURRENT_TEST` so normal isolated CLI settings
bootstrap executes; the first harness run's 12 bootstrap failures are retained
at `.tmp/bt4-cli-lifecycle-before.log`. Corrected reproduction:
`.tmp/bt4-cli-lifecycle-reproduction.log` (six passed, six cancellation failures).
After repair: `.tmp/bt4-cli-lifecycle-after.log` (42 passed in 25.93 seconds),
including all twelve native cases and the existing result/cleanup/CLI contracts.

Observed path: primary for the explicit lifecycle fixtures. Observed result:
success in the scoped source and installed proof. Final matrix:
`.tmp/bt4-cli-lifecycle-matrix/report.json`. The changed runtime and new test
files pass Ruff. The CLI's existing oversized module grows by three lines for
the typed interruption handler/import; no new runtime owner or result schema is
introduced. New test modules/functions satisfy size and layer-label rules.
The refreshed baseline remains `collection_ok=true`, `release_ready=false` with
110 runtime Ruff diagnostics and 3,387 unlabeled functions out of 4,546 tests.

The final installed envelope contains the earlier 185-case result/ownership
selection, all twelve native CLI lifecycle cases and ten CLI startup/result
checks. Each cell passes `pip check`, verifies harness hashes before/after, and
loads all 647 observed runtime/SDK modules from its isolated installation. Every
new CLI child separately checks its runtime origin against the parent's installed
origin. Both archives' 933 runtime Python files match current source; the CLI
module is the only runtime file changed from the preceding verified wheel.

| Cell | Passed | Skipped | Seconds |
| --- | ---: | ---: | ---: |
| Windows Python 3.11.14 | 207 | 0 | 179.258 |
| Windows Python 3.12.2 | 207 | 0 | 179.343 |
| Linux Python 3.11.16 | 207 | 0 | 259.864 |
| Linux Python 3.12.3 | 207 | 0 | 249.271 |

Each cell reports two dependency deprecation warnings: Starlette's current
`httpx` test-client integration and the `anyio.abc.BlockingPortal` alias. These
are reported without changing dependency policy in this CLI repair.
Wheel SHA-256:
`d86a1d267768a3fdc3c0761cdb0b001857742a0dee8d38d596d617df8e16738a`.
Sdist SHA-256:
`84f5a1f92820a561121d26b0f433f00c93a83b76bc1c9c58edc96a7801d21958`.

Four additional stock installed `orket runtime --card` controls use actual
llama.cpp on Windows Python 3.11/3.12: accepted success exits 0; missing required
attribution retains failure and exits 1. All four compare narration/exit with
session, control-plane, final-truth and publication records, retain two model
receipts each, and confirm CLI process cleanup. Evidence:
`.tmp/bt4-cli-lifecycle-cli-installed/report.json`. Their existing startup
structural-reconciliation warning remains an explicit degraded observation;
this is primary workload execution, not a healthy-startup claim.

Final audit `.tmp/bt4-cli-lifecycle-audit.json` passes exact 10-file checkpoint
scope and 445-path worktree inventory, all 18 original H2 headings, six unchanged
sealed fixture digests, archive/source parity, source and installed results,
clean original main, empty index, Ruff, `git diff --check` and docs hygiene.
No owned verification/CLI worker remains on either OS; Docker lists only the
existing operator-owned `vibe-rail-gitea`. Routine proof creates no sandbox.
Scoped AC-01 through AC-10 pass: the only new runtime edge is interface-to-
application, existing result/evidence authority and event schema are reused,
cleanup precedes projection, and the authority/runbook/spec/delta change together.
This scoped review does not close earlier architecture exceptions.

Remaining blockers or drift: the preceding 5,287-pass full source run is historical;
it was not repeated for this scoped CLI change. The unmodified stock CLI cannot
select the custom approval policy used in the boundary fixture. Broader application
shutdown, host death, remote-provider lifetime, measured connector telemetry and
the remaining BT-3/BT-5/C/D/E/CAP gates remain open. This proof does not widen
supported workloads or admit a new runtime policy/configuration option.

Exact files touched in this checkpoint (10):

- `CURRENT_AUTHORITY.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_RUNTIME_RESULTS_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`
- `orket/interfaces/cli.py`
- `tests/helpers/runtime_cli_lifecycle_worker.py`
- `tests/integration/test_runtime_cli_lifecycle.py`

### BT-4 connector timing proof: 2026-09-13

Status: measured connector timing implemented and scoped proof complete; BT-4
and the architectural-truth lane remain open.

The opening native command slept for 300 ms. Independent observation measured
342.4682 ms while the connector reported `duration_ms: 0` with success. Evidence:
`.tmp/bt4-connector-timing-reproduction.json`. This is an observed SD-05
counterexample, not a synthetic timing stub.

The application now measures each awaited invocation with an injected monotonic
callable. Default `RuntimeInputService.monotonic_ns` uses `time.perf_counter_ns`;
the typed `invocation_timing.v1` contract retains actual clock, scope, measured or
unavailable status and reason. Null means unavailable; fractions survive. A
measured zero requires equal actual clock samples. Validation/approval and
receipt publication are outside the interval. Cleanup is included only when the
adapter actually awaits it; timing does not establish effect lifetime.

Cancellation and unknown execution errors retain their original exception and
emit supporting `outward_connector_interrupted` workspace telemetry. They do
not manufacture a result or `tool_invoked` receipt and leave dispatch intent
unresolved. Success, declared failure and timeout retain their outcome meanings.
The timer does not enter authorization/fencing/input hashes or outcome decisions.
An observed receipt commits its original timing and digest, and republication
after a real SQLite abort reuses it without another effect or clock sample.

Normalized logging envelopes are explicitly v2 because duration can now be null
or fractional. Connector provenance survives projection. API/CLI documentation,
event taxonomy and acceptance reports change together; reports count v1 and v2
separately without relabeling historical coverage. Two unused execution-plan
failure helpers that invented zero are removed; repository searches found no
callers. Legacy provenance-free connector fields are read as unavailable, without
rewriting raw events, v1 hashes, sealed fixtures or retained receipts.

Counterexamples and corrected proof:

- The first 44-case reader/recovery campaign found two incomplete reporting test
  fixtures (`model` missing), with 42 cases passing. The completed fixtures pass
  all 44 cases; both logs remain retained. No production fallback was introduced.
- The first installed wheel passed 358 checks on each Linux version, while both
  Windows versions passed 357 and failed the independent clock comparison.
  `monotonic_ns` reported 344 ms against 331.6253/331.1818 ms external observations.
  Actual interpreter probes report `GetTickCount64`, resolution 15.625 ms, for
  Windows Python 3.11/3.12. The corrected source uses monotonic
  `QueryPerformanceCounter` through `perf_counter_ns`; the original 1 ms overrun
  and 50 ms outer-overhead bounds remain unchanged. Probe:
  `.tmp/bt4-connector-timing-clocks.json`.
- The superseded first source campaign was stopped with all three observed
  owned processes confirmed exited. It is incomplete proof. Its log, stop record,
  wheel, sdist and manifest are retained under
  `.tmp/bt4-connector-timing-before-perf-counter/`. The old matrix is retained as
  `before-perf-counter`, including the two failures.
- Corrected-clock focused source checks pass 34 cases. The final frozen canonical
  source campaign passes **5,325 tests**, with **78 skipped** and two warnings
  (the legacy `orket.domain` import and a fixture's low generation token cap).
  JUnit duration is **1144.907s**; pytest reports **1145.24s** overall.
  Its before/after Git-visible Python hashes match:
  `.tmp/bt4-connector-timing-final-full-source-report.json`. This replaces the
  prior checkpoint's historical source-suite limit for the current worktree.

Final installed acceptance:

| Cell | Passed | Skipped | Seconds |
| --- | ---: | ---: | ---: |
| win-py311 | 358 | 0 | 233.467 |
| win-py312 | 358 | 0 | 244.986 |
| linux-py311 | 358 | 0 | 343.683 |
| linux-py312 | 358 | 0 | 335.195 |

The 358-case envelope includes timing, logging/reporting, outward authorization
and actual effect recovery, sealed witness/corruption checks, typed runtime
outcomes and native verification/CLI lifetime. Every cell checks external harness
hashes before/after and loads all 854 observed runtime/SDK modules from its
isolated installation. All 935 runtime Python files in both archives match source.
Each cell retains two dependency deprecation warnings (Starlette/httpx and
`anyio.abc.BlockingPortal`); none is suppressed. Matrix:
`.tmp/bt4-connector-timing-matrix/report.json`.

Wheel SHA-256: `5d6af3cc773022efcfa8ac555a898ac6464b05ac44c5274377b311a55c6a5fe1`.
Sdist SHA-256: `4e1a2f24a4d3fae306781c6469422a6218d8e9b5f28c2fe3ba682b650079dc77`.

Separate installed Windows Python 3.11 live observations:

| Case | Reported ms | Independent elapsed ms |
| --- | ---: | ---: |
| success | 355.8955 | 356.2407 |
| failed | 354.0229 | 354.4708 |
| timeout | 208.3901 | 208.6134 |
| cancelled | 153.1593 | 154.3768 |

Every observed workload PID has a separately confirmed exit after the return
probe. Timing stops before that independent probe; this does not assert that
the connector owns the marker process or that all effects stopped before return.
The first standalone attempt failed a process-presence assertion, followed by
`NoSuchProcess` during cleanup. Its log and driver remain retained. The refined
probe records the marker's parent PID, zero-timeout exit signal and any bounded
post-return wait, separately from the timing comparison.
The timeout marker was not exit-signalled at its first post-return probe;
the bounded probe confirmed exit after 0.6790 ms.
All marker processes reported a parent different from the proof driver. This
is a concrete remaining command-lifetime gap, recorded as partial success for
the separate lifetime observation, while the four timing comparisons pass.
The cancelled attempt emits supporting timing and re-raises cancellation without
a returned effect. An actual
llama.cpp approved-write flow through installed application services, real HTTP,
SQLite and filesystem passes witness, artifact and corruption verification.
Its retained tool event reports 2.2202 ms
with measured performance-counter provenance. The produced file contains exactly
`outward proof live content`. Model: `orcarouter_qwen3.8-27b-uncensored-q4_k_l`;
endpoint `http://127.0.0.1:8080/v1`. The proof driver supplies an explicit fixture
wall clock for governance; connector monotonic timing and provider execution are
real. This is service-level provider proof, not a newly deployed authenticated
API listener. Evidence: `.tmp/bt4-connector-timing-live.json`; all observed runtime
origins are installed and the wheel hash matches this matrix.

Structural review: AC-01 through AC-10 pass within this timing boundary. The core
contract is the shared definition, applications measure and own publication,
adapters retain effect execution, and timing is supporting observation. Existing
oversized files receive only required projection/counter/assertion changes:
`orket/logging.py` (477 to 479 lines), acceptance report (440 to 445), acceptance
loop (959 to 960), and the existing connector CLI test. New modules stay below
400 lines and new functions below 70. The scoped Ruff comparison reports zero
introduced diagnostics and 128 pre-existing diagnostics: 59 in the acceptance
report, 68 in the loop, and one in the connector service test. These remain debt,
not a clean whole-scope Ruff claim. Baseline collection succeeds while release
readiness remains false. Final inventory/package/process audit is retained at
`.tmp/bt4-connector-timing-audit.json`; original main stays clean, the index stays
empty, all 18 original H2 headings and six sealed fixture hashes remain intact.
Routine proof creates no sandbox; final Docker inventory contains only the
operator-owned `vibe-rail-gitea`.

Remaining blockers or drift: built-in `run_command` still owns only its direct
child, with unbounded output capture and incomplete repeated-cancellation
supervision. Remote HTTP effect lifetime, host death and broader app shutdown
are not proven by this timer. The validator-duration default in
`turn_tool_dispatcher.py`, raw turn defaults in probes P01/P03 and duration defaults
in benchmark scoring/determinism reports are separate producers/readers, not
outward receipt measurement; they still need audit before capacity claims. ODR
canonicalization and run-summary duration use different scopes and do not consume
this connector receipt as timing authority. Fabricated numbers in corruption and
sealed proof fixtures remain historical/adversarial data, never live measurement
proof. Broader BT-3/BT-4/BT-5/C/D/E/CAP gates remain active.

Exact files touched in this checkpoint (25):

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_CONNECTOR_TIMING_BT4_2026-09-13.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CONNECTOR_INVOCATION_TIMING.md`
- `orket/application/services/connector_invocation_timing.py`
- `orket/application/services/outward_connector_service.py`
- `orket/application/services/outward_run_execution_plan.py`
- `orket/application/services/runtime_input_service.py`
- `orket/core/contracts/invocation_timing.py`
- `orket/logging.py`
- `scripts/acceptance/report_live_acceptance_patterns.py`
- `scripts/acceptance/run_live_acceptance_loop.py`
- `tests/application/test_outward_connector_service.py`
- `tests/application/test_outward_run_execution_service.py`
- `tests/contract/test_connector_invocation_timing.py`
- `tests/core/test_runtime_event_logging.py`
- `tests/integration/test_outward_connector_timing.py`
- `tests/integration/test_outward_effect_recovery.py`
- `tests/integration/test_runtime_event_schema_reporting.py`
- `tests/interfaces/test_orket_bundle_cli.py`

### BT-4 outward command lifetime checkpoint: 2026-09-13

Observed path: `primary`. Scoped result: `success`. BT-4 and the umbrella plan
remain active. This supersedes the preceding timing checkpoint's direct-child
limitation for the built-in outward `run_command` connector.

The command adapter now receives the core `CommandRunner` port from application
composition and shares `CommandProcessSupervisor` with native verification and
fixture callers. The old verification-specific supervisor module is removed,
without an alias or duplicate executor. Both Windows Job and Linux subreaper
backends establish ownership before command execution. The existing bounded
cleanup protocol handles ordinary/detached children and grandchildren through
completion, failure, timeout, cancellation, repeated cancellation and ordinary
`asyncio.run` shutdown. Application deadlines remain in the owning task so bound
filesystem cancellation semantics are preserved.

Results retain `owned_command.v1` lifetime and actual nullable return codes.
Capture is capped at 4 MiB per raw stream; output limits fail with incomplete
capture. Counts now describe retained bytes before replacement decoding, while
previews remain limited to 256 characters. Missing cleanup acknowledgement or
failed capture raises uncertainty. Cancellation/uncertainty leaves the durable
effect dispatching without a receipt; API reentry refuses repeat dispatch.
Supporting lifetime logs are diagnostic and do not become a recovery journal.
Cleanup establishes process termination, not reversal of external effects.

Counterexamples and corrected proof:

1. `.tmp/bt4-outward-command-before.log/.xml`: ten initial failures, partly
   receipt-shape assertions. The revised behavioral-first reproduction in
   `.tmp/bt4-outward-command-before-behavior.log/.xml` independently observed
   surviving ordinary trees after cancellation/repeated cancellation and timeout
   exceeding its five-second outer bound: three failed, seven deselected.
2. `.tmp/bt4-outward-command-raw-bytes-before.log/.xml`: both raw stream probes
   wrote three invalid UTF-8 bytes but received a count of nine. Both fail before
   the correction. The final capture tests require three raw bytes and three
   replacement characters, and separately exercise actual 5 MiB writes and
   missing executable launch.
3. The first supervisor candidate passed 38 native/connector cases. A later
   campaign passed 26 command/recovery cases and two interpreter-shutdown cases.
   These Python 3.13 source observations did not establish Python 3.11/3.12 parity.
4. The first installed matrix used wheel
   `1fd14ab34c938db4cc2855fe01f952c210ed897424a1d70c8151cf5458e1c6d1` and failed five deadline cases in
   every cell. Windows 3.11 additionally hit a temporary marker-file read denial
   (six failures; other cells five). Python 3.11/3.12's timeout context matches
   the exact `CancelledError` type. The boundary now normalizes that type while
   retaining the original typed cleanup observation; external cancellation during
   deadline cleanup still wins. The marker observer retries only read denial
   within its original bounded wait and still requires all three real identities.
   Failed logs/JUnit/reports remain under
   `.tmp/bt4-outward-command-matrix/before-timeout-type-fix/`.
5. A source campaign passed 380 tests but was excluded from frozen-candidate proof
   because exception-chaining lint fixes changed two files during execution.
   Its report, hashes, log and JUnit remain in
   `.tmp/bt4-outward-command-before-source-freeze/`. The corrected intermediate
   installed matrix is also retained before the last verifier import-order fix;
   it is not substituted for the final candidate's matrix. That intermediate
   matrix passed 380 cases in both Windows cells and Linux 3.11; Linux 3.12
   passed 379 and failed one verification-shutdown fixture startup bound. Its
   cause was not established. The next candidate again passed 380 in Windows
   and Linux 3.11, but Linux 3.12 missed fixture-tree readiness in the signal/epic
   CLI case (379 passed, one failed), before interruption was requested. Both
   failures used one five-second wait for interpreter/import/store setup plus
   command startup. The fixture workers now explicitly signal completed setup:
   setup gets a separate 30-second budget, followed by the existing five-second
   command-tree wait. This changes the fixture initialization budget; it does not
   establish a five-second CLI cold-start guarantee. Command execution deadlines,
   post-cancellation exit bounds and independent no-later-write checks remain
   unchanged. Logs/JUnit for both attempts remain in the matrix history.
   A stable 380-pass source campaign before the fixture-boundary change is also
   retained in `.tmp/bt4-outward-command-before-fixture-bootstrap-source/`;
   the following final campaign includes the readiness handshake.
6. Final selected source regression: **380 passed, zero skipped**, with unchanged
   Python hashes before/after execution in
   `.tmp/bt4-outward-command-final-source-report.json` and sibling log/JUnit.
   Selection covers command capture/lifetime, verifier/fixture callers, typed
   runtime/CLI outcomes, outward authorization, durable receipt republication and
   sealed witnesses. The full canonical suite was not rerun for this slice;
   the preceding 5,325-pass timing run is historical proof of that candidate.

Final installed package matrix, outside the checkout:

| Cell | Passed | JUnit seconds | Runtime/SDK origins checked |
| --- | ---: | ---: | ---: |
| win-py311 | 380 | 246.607 | 854 |
| win-py312 | 380 | 256.458 | 854 |
| linux-py311 | 380 | 403.661 | 854 |
| linux-py312 | 380 | 365.928 | 854 |

Every cell has zero failures/errors/skips; the two warnings are existing
Starlette/httpx and AnyIO deprecations. Installation and `pip check` pass in each
owned environment. All 854 observed runtime/SDK origins are installed paths;
test/script hashes match before and after execution. The wheel and sdist contain
the same 935 runtime Python files as the worktree, including the generic owner
and excluding the removed module. Final archives in
`.tmp/bt4-outward-command-verified-dist/`:

- Wheel SHA256: `5e57a3ac4e0eb4a3b42257f164918dc200657e98353c3b30ec7764342649081b`.
- sdist SHA256: `ee74bd0fbcba62074b5854f0e5aa88f50113861c6608a488d68c6376e9626db6`.

Separate live proof uses the stock installed Windows 3.11 `orket connectors test
run_command` CLI with real detached, TERM-resistant fixture trees. Successful
leader exit returns CLI 0 and actual command 0; leader failure returns CLI 1 and
actual command 7. Independent retained process identities and heartbeat bytes
confirm all three fixture processes stopped with no later writes. The supporting
transport/supervisor PIDs are absent. Exact arguments, outputs, lifetime and
wheel origin are retained in `.tmp/bt4-outward-command-live.json` and its external
harness. This is the local connector harness; it does not invoke a provider or
exercise approval. The authenticated ASGI/SQLite integration uses an explicit
model-output fixture and actual commands to prove uncertainty/reentry fencing.
Killing the real supervisor produces HTTP 409 `E_COMMAND_EXECUTION_UNCERTAIN`;
later approval returns `E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN`, preserving the
intent/journal and emitting no `tool_invoked`. Linux lost-ack fixture descendants
are cleaned by the test controller; that is not application-confirmed cleanup.

Structural review: AC-01/02/03/04/05/06/07/08/10 pass for this scope: explicit core
port, application effect ownership, no new decision-node context/effect reach,
unchanged timing authority, conservative result projection and same-change
contract/taxonomy updates. AC-09 is partial: existing durable dispatch/receipt
integrity and no-reexecution recovery are exercised, but diagnostics are not
durable reconciliation and host-death recovery remains owned by BT-4. The touched
`runtime_verifier.py` remains 636 lines, unchanged from the preceding packaged
candidate; only imports and explicit supervisor construction migrate. Its size
debt remains E2 work. Other touched Python files are under 400 lines; new functions
remain under 70 lines and new/modified tests retain layer labels. Scoped Ruff is
clean, including the verifier import block; no pre-existing lint is hidden by a
comparison against HEAD. The baseline remains `collection_ok=true`,
`release_ready=false`, with 110 runtime Ruff findings,
3386 prose-taxonomy missing labels
among 4565 functions, 74 oversized runtime files
and 235 long functions. These are existing broader E1/E2 gates, not runtime proof.

The final audit binds these claims to archive/source hashes, exact inventories,
all 18 original plan H2 headings, six unchanged sealed fixture hashes, clean
original main, empty index, `git diff --check`, docs hygiene and no remaining
fixture/supervisor processes on Windows/Linux. Routine proof is sandbox-disabled;
Docker inventory contains only operator-owned `vibe-rail-gitea`. No commit, tag,
push, release, global install or provider-setting change occurs in this checkpoint.

Supplemental installed Python 3.11 filesystem integration passes ten cases each
on Windows and Linux, with 801 installed runtime/SDK origins verified per cell.
These real approval/handle paths cover target replacement, repeated cancellation,
timeout cleanup and retained uncertain intent through the same deadline helper.
Reports and JUnit are retained under `.tmp/bt4-outward-command-filesystem/` and
bind the same final wheel; they are additional to the 380-case main selection.

Remaining blockers or drift: abrupt host death, actual OS termination refusal,
remote HTTP effect lifetime, other command helpers and broader app shutdown
ownership remain unproved. Native supervision is not hostile-code containment.
Other timing producers/readers still need the declared SD-05 audit before
capacity claims. Broader BT-3/BT-4/BT-5/C/D/E/CAP gates remain active. The durable
contract and migration delta are `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`
and `docs/architecture/CONTRACT_DELTA_OUTWARD_COMMAND_LIFETIME_BT4_2026-09-13.md`.

Exact files touched in this checkpoint (30):

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_OUTWARD_COMMAND_LIFETIME_BT4_2026-09-13.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/CONNECTOR_INVOCATION_TIMING.md`
- `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`
- `orket/adapters/tools/builtin_connectors.py`
- `orket/application/services/command_process_supervisor.py`
- `orket/application/services/fixture_container_owner.py`
- `orket/application/services/fixture_verification_service.py`
- `orket/application/services/outward_connector_service.py`
- `orket/application/services/runtime_verifier.py`
- `orket/application/services/verification_process_supervisor.py`
- `orket/core/contracts/owned_command.py`
- `tests/application/test_orchestrator_verification_async.py`
- `tests/contract/test_outward_command_deadline_observation.py`
- `tests/helpers/runtime_cli_lifecycle_worker.py`
- `tests/integration/test_outward_command_capture.py`
- `tests/integration/test_outward_command_lifetime.py`
- `tests/integration/test_outward_command_uncertainty.py`
- `tests/integration/test_runtime_cli_lifecycle.py`
- `tests/integration/test_runtime_execution_results.py`
- `tests/integration/test_verification_process_lifetime.py`
- `tests/integration/test_verification_shutdown.py`
- `tests/integration/test_verification_supervisor_receipts.py`
- `tests/integration/verification_shutdown_worker.py`

The old `verification_process_supervisor.py` entry above is a deletion of the
preceding uncommitted module; the generic owner replaces it.

### BT-4 API shutdown ownership checkpoint: 2026-09-13

Status: registered-owner teardown repair and scoped proof complete; BT-4 remains open.

One API container now retains one teardown operation. Close initiation stops
admission, concurrent callers await the same work, and repeated caller cancellation
waits for cleanup before propagating. `closed` becomes true only after successful
registered-owner teardown. Failed close remains failed on reentry; peer resources
and the engine still receive close attempts. Explicitly unconfirmed native command
cancellation prevents a successful teardown claim. The lifespan delegates its
tracked broadcaster to the same owner. Recursive self-close is rejected.

Authority: `docs/specs/API_RUNTIME_LIFECYCLE.md`; delta:
`docs/architecture/CONTRACT_DELTA_API_SHUTDOWN_BT4_2026-09-13.md`.

Observed path: `primary`. Scoped result: `success`. Proof includes live TCP/HTTP,
actual detached native process trees with independent identity/heartbeat checks,
real SQLite integration, and separately labelled synthetic failure contracts.
The end-to-end HTTP test runs Uvicorn with the public `CompositionConfig` factory,
performs `/health`, requests graceful server exit and observes the closed socket,
completed app teardown and zero active registered tasks. This uses a real server
in the test process, not `server.py`, a terminal signal or a live provider call.
The boundary fixture supplies isolated environment/storage; its fake model is
unused. The command cases explicitly register the real composed connector task;
they do not establish ownership of every ordinary HTTP invocation.

Evidence and corrections retained in the worktree:

- `.tmp/bt4-api-shutdown-before.log/.xml`: five fixture setup failures from an
  incorrect public factory argument. These are not behavioral counterexamples.
- `.tmp/bt4-api-shutdown-before-behavior.log/.xml`: cancellation and concurrent
  return left a real listener accepting connections. The normal case also hit
  the probe's one-second Windows connection-refusal timeout.
- `.tmp/bt4-api-shutdown-before-corrected-probe.log/.xml`: one normal pass and
  four actual teardown failures. The probe now allows five seconds for explicit
  connection refusal; timeout remains failure, never evidence of closure. The
  cancellation/cleanup bounds were not widened by this probe correction.
- `.tmp/bt4-api-shutdown-initial.log/.xml`: 25 checks passed. The subsequent
  live-HTTP selection passed 13 in `.tmp/bt4-api-shutdown-tcp.log/.xml`.
- Initial frozen source: 87 passed in 90.46 seconds, retained in
  `.tmp/bt4-api-shutdown-before-renewal-fixture/`. Initial installed Windows cells
  each passed 87. Linux cells each passed 86 and failed the existing 80 ms
  wake-lease renewal fixture, with stale claim/renewal observations. These are
  retained under `.tmp/bt4-api-shutdown-matrix/initial/`, not replaced with green.
  All new shutdown cases passed in all four initial cells.
- A standalone prior-wheel Linux 3.11 control passed the original renewal case
  in 0.31 seconds: `.tmp/bt4-api-shutdown-prior-renewal/`. It does not reproduce
  the concurrent campaign conditions or establish the exact source of delay.
  The supervisor and repository implementation used by that case are unchanged.
- The renewal fixture now uses the existing injected clock seam, waits for an
  actual SQLite renewal, then advances beyond the original lease before allowing
  dispatch completion. It checks persisted renewal and final state without an
  80 ms filesystem/scheduler SLA. The first edit incorrectly compared timestamp
  spellings and timed out; the retained failure is
  `.tmp/bt4-api-shutdown-renewal-followup.log/.xml`. Comparing parsed timestamps
  passes all six supervisor cases in 0.44 seconds in the `-corrected` follow-up.
  Runtime lease policy and native shutdown bounds are unchanged.
- Final frozen source: **87 passed, zero failed/skipped, 91.68 seconds**;
  `.tmp/bt4-api-shutdown-final-source-report.json/.log/.xml`. Git-visible Python
  hashes match before/after. The complete canonical suite was not rerun here;
  earlier full-suite counts remain historical.
- Final installed proof below uses the same runtime wheel with the corrected
  external test fixture. Each cell removes `PYTHONPATH`, validates installed
  origins, checks harness hashes before/after and passes isolated `pip check`.
  The wheel/sdist contain no test Python files; the fixture edit does not change
  runtime archive bytes. Initial Linux refresh overlapped test launch; before/
  after harness hashes still matched. Final refresh completed before test launch.

| Installed cell | Passed | Failed / skipped | Seconds | Installed module origins |
| --- | ---: | ---: | ---: | ---: |
| win-py311 | 87 | 0 / 0 | 81.960 | 801 |
| win-py312 | 87 | 0 / 0 | 95.393 | 801 |
| linux-py311 | 87 | 0 / 0 | 63.878 | 801 |
| linux-py312 | 87 | 0 / 0 | 63.782 | 801 |

Installed reports include dependency warnings (Starlette/httpx and AnyIO;
some cells also report existing Pydantic field-metadata warnings). They are not
presented as warning-free runs. Exact warnings remain in each `pytest.log`.

Archives: `.tmp/bt4-api-shutdown-dist/`.

- Wheel SHA-256: `d985faa6a0d5cbf5179202493a8e9a07510ba9a2590f4c8a0e6037a9c8d38674`.
- Sdist SHA-256: `03221bfa8d5374c45844c46c571a1ca4bb30f898507e4d49576204f7c53881e4`.

The final audit binds 935 runtime Python files to source, wheel and sdist, checks
all six original fixture seals, the unchanged 18 H2 plan headings, exact global
and checkpoint inventories, clean original main, empty index, scoped lint and
native worker cleanup: `.tmp/bt4-api-shutdown-audit.json`. This checkpoint creates
no commit, tag, release, push, sandbox or global package install. Earlier Gitea
push proof remains historical and is not erased by that checkpoint statement.

Architecture checklist: AC-01/02/03/04/06/07/08/10 pass for this scoped change;
AC-05 and AC-09 are partial because untracked in-flight work and durable recovery
are not covered by the local container. Their remediation remains this plan's
BT-4/BT-3 work. The pre-existing oversized `orket/interfaces/api.py` shrinks by
five lines from the preceding candidate; new/changed functions stay within 70
lines. Five current scoped Python files are Ruff-clean. The repository baseline
collects successfully and retains `release_ready=false`; broader structural debt
is not cleared by these scoped checks.

Not verified / remaining blockers or drift: whole-app ownership of active HTTP
requests and connector calls, remote effect termination, arbitrary blocking or
non-settling resource close, event-loop-wide or abrupt host termination with all
owners active, and durable workload/export reconciliation. Cancellation of a
teardown owner is a retained failure, not proof its interrupted resource closed.
Generic task cancellation is local task completion, not effect-completion truth.
No global API shutdown deadline is claimed. No fresh llama.cpp workload, live
Gitea flow, full canonical suite or complete BT-3/BT-4/BT-5/C/D/E/CAP gate was run.

The existing prose taxonomy collector in
`scripts/governance/enforce_test_taxonomy.py` recognizes `live_truth` but not the
policy-approved `end-to-end` label. It therefore reports the new live HTTP test
in `tests/integration/test_api_shutdown_ownership.py` as unlabeled despite its
explicit comment and `pytest.mark.end_to_end`. The current baseline reports
3,387 missing labels among 4,574 test functions, including that collector mismatch;
this is not a clean taxonomy gate. Governance alignment remains owned by the
plan's structural proof work. The test is not relabelled to conceal the mismatch.

Exact files touched in this checkpoint (13):

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_API_SHUTDOWN_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `orket/application/services/api_runtime_container.py`
- `orket/interfaces/api.py`
- `tests/contract/test_api_shutdown_outcomes.py`
- `tests/integration/test_api_shutdown_ownership.py`
- `tests/integration/test_governed_agent_supervisor.py`

### BT-4 active ASGI request ownership checkpoint: 2026-09-13

Status: active HTTP/WebSocket invocation ownership implemented with scoped proof;
BT-4, BT-3 and the umbrella lane remain open. This is an allowed immediate BT-4
lifetime prerequisite, not completion of the broader recovery envelope. Work
remains in `C:/Source/Orket-architectural-truth` on `codex/architectural-truth-bt0`.

The opening real TCP counterexample submitted an authenticated outward run,
approved a native command and observed its child/grandchild identities. Container
close returned while that process tree still ran. The failing requirement is
retained in `.tmp/bt4-request-ownership-before.log/.xml`; fixture cleanup killed
and awaited its observed processes after the assertion. That cleanup is not
application proof.

The app container now admits each HTTP/WebSocket ASGI invocation before dispatch
and retains its task through response streaming and awaited connector execution.
Close cancels active invocations once and awaits cleanup before resources and
engine. Cancellation of the request waiter also waits for its invocation; typed
cleanup uncertainty is retained for both request and close observers. Request
descendants cannot await their own teardown. Pure ASGI middleware replaces the
version-header BaseHTTPMiddleware layer and preserves normal version headers and
transport cancellation identity. Event sockets release their runtime registration
in `finally`; interaction sockets capture the stream bus before shutdown so their
cleanup does not request new runtime admission.

Stopped admission yields HTTP 503, including health, or a pre-accept WebSocket
close. Established WebSockets close with 1001. Cancellation after HTTP headers
truncates the response; a successful header cannot establish body completion.
`docs/specs/API_RUNTIME_LIFECYCLE.md` and the contract delta describe these bounds.
The ASGI scope distinction follows the
[HTTP/WebSocket protocol specification](https://asgi.readthedocs.io/en/stable/specs/www.html).

Verification and retained attempts:

- Initial active-request/registered-shutdown/task regression passed 22 in 17.54s
  (`.tmp/bt4-request-ownership-initial.log/.xml`). The nine new cancellation,
  uncertainty, streaming and WebSocket edge cases passed in 1.31s (`-edges`).
- The first broader source run passed 184 and failed three existing interaction
  WebSocket disconnect tests (`.tmp/bt4-request-ownership-source.log/.xml`, with
  frozen hashes in `-source-report.json`). The boundary had replaced the client's
  cancellation-scope exception. Preserving it after cleanup fixed the regression;
  the affected 23 cases passed in 2.85s (`-disconnect.log/.xml`).
- Corrected source selection passed all 187 in 64.98s with no skips or failures:
  `.tmp/bt4-request-ownership-final-source.log/.xml` and `-source-report.json`.
  After that run only the metrics test assertion changed, replacing a Windows-only
  separator suffix with three platform-native path components. Its focused source
  check passed (`.tmp/bt4-request-ownership-metrics-fixture.xml`). The 187-case
  source selection was not repeated after this fixture-only correction.
- The first installed corrected-runtime matrix passed 187 on each Windows cell,
  and 186 with one failure on each Linux cell. Both Linux failures were the same
  pre-existing metrics separator assertion. All four old harnesses and their
  results are retained in `.tmp/bt4-request-ownership-final-matrix/report.json`
  (`phase=initial`). No runtime workaround was added.
- Fresh harnesses with the corrected assertion pass 187 each on Windows 3.11.14,
  Windows 3.12.2, Linux 3.11.16 and Linux 3.12.3, with zero failures/errors/skips:
  `.tmp/bt4-request-ownership-verified-matrix/report.json`. They run outside the
  checkout without `PYTHONPATH`, check dependencies, verify harness bytes before
  and after, and inspect 811 loaded core/SDK origins per cell; none load source
  runtime modules. The two matrices use the identical corrected runtime wheel.
  Existing dependency deprecation/schema warnings are retained in the logs.
- Native process-tree cancellation uses the existing authenticated approval route
  over Uvicorn TCP, including repeated cancellation of the close waiter. Independent
  observers require no living fixture processes and no later heartbeat writes
  before accepting close. Streaming HTTP is also real TCP. Both WebSocket routes
  use TestClient's real ASGI transport, not TCP WebSocket transport. Synthetic
  failure contracts establish observer semantics, not external-effect proof.
- Fresh installed Windows llama.cpp proof uses the real TCP API, operator approval
  and an actual local file effect. `.tmp/bt4-request-ownership-live/report.json`
  binds the installed wheel, retained model invocation and output digest. The
  model is `orcarouter_qwen3.8-27b-uncensored-q4_k_l`; its receipt records 386 prompt and 28 completion tokens.
  The stored run is completed, the output equals `outward proof live content`,
  application close leaves zero active request/background tasks, post-close health
  is 503, and the server task settles. This is a successful provider path; provider
  cancellation/remote termination is not inferred from it. The first driver failed
  before app construction because it omitted `load_env()` before entering asyncio;
  `.tmp/bt4-request-ownership-live.log` retains that failure. The corrected driver
  follows the existing bootstrap contract (`-live-followup.log`).

Archive authority: `.tmp/bt4-request-ownership-final-dist/` contains matching
runtime source/wheel/sdist Python files. Wheel SHA-256:
`12f2fb8d8d6b0429cd4dacbf98af2e3df4d986dafb755aeeb088652e14625bfd`.
Sdist SHA-256: `9d2e00ad5982f75376a2ddc23064e9d0ecba0caa7fb76b1a10e19970d933b63f`.
The earlier pre-disconnect-fix archives remain in `-ownership-dist/` and are not
the accepted candidate. Final audit: `.tmp/bt4-request-ownership-audit.json`.
It binds the scoped proof and inventory, checks all six original seals, original
main cleanliness, empty index and unchanged 18 H2 plan headings. No commit, tag,
release, push, sandbox creation or global package installation occurred here.

Structural verification finds no introduced Ruff diagnostics in eight changed
Python files. One pre-existing diagnostic remains in `orket/interfaces/api.py`;
the portable metrics assertion removes one existing test diagnostic. The API file
shrinks 20 lines from the preceding candidate and the oversized test file does
not grow. New files/functions stay below 400/70 lines. The existing streaming
registration function grows from 69 to 72 lines to keep both route cleanups in
their established owner; this bounded correctness change is not a new function
or a new oversized file. Its later extraction remains part of interface debt.
The refreshed repository baseline reports `collection_ok=true`,
`release_ready=false`, 109 Ruff diagnostics,
3387 missing layer labels among
4605 functions, and
74 oversized runtime files /
236 oversized functions. The
existing taxonomy collector's `end-to-end` mismatch remains unresolved.

Architecture checklist: AC-01/02/03/04/06/07/08/10 pass for the changed scope.
AC-05/09 remain partial outside admitted local ASGI work: detached/direct connector
ownership and durable interrupted-effect recovery remain BT-4/BT-3 responsibilities.
No new durable schema, replay mutation, approval authority or retry permission is
introduced. Cancellation never establishes successful durable effect outcome.

Not verified / Remaining blockers or drift: unregistered detached tasks, direct
connector invocations outside owned tasks, arbitrary blocking threads/resources,
general shutdown deadlines, event-loop/host death, remote provider/effect
termination and durable workload reconciliation remain open. TCP WebSocket proof,
fresh Linux provider proof, full source/installed repository suites and Gitea proof
were not run in this checkpoint. Earlier full-suite and Gitea records remain
historical; these 187-case envelopes do not close BT-3/BT-4 or the later BT-5/C/D/E/CAP
gates. Continue the required recovery/fencing and lifetime work from this plan.

Exact files touched in this checkpoint (17):

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_API_REQUEST_OWNERSHIP_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `orket/application/services/api_runtime_container.py`
- `orket/interfaces/api.py`
- `orket/interfaces/api_app_context_middleware.py`
- `orket/interfaces/routers/streaming.py`
- `tests/contract/test_api_request_lifecycle.py`
- `tests/integration/test_api_active_request_ownership.py`
- `tests/integration/test_api_stream_request_ownership.py`
- `tests/interfaces/test_api.py`

### BT-4 gate audit and direct filesystem ownership: 2026-09-13

Status: direct filesystem repair implemented and scoped verification passed.
BT-4 remains open for the remaining telemetry/conformance audit. The four numbered BT-4 requirements remain the gate authority. Earlier
native, fixture, result, timing and API checkpoints retain their original proof
ceilings and failures. Work remains in the isolated dirty worktree on the existing
branch; no commit, tag, release or push is included.

| Requirement | Current implementation and acceptance evidence |
|---|---|
| Public verification cleanup | Application `CommandProcessSupervisor`, native Job/subreaper backends; real child/grandchild cancellation, timeout, failure, repeated cancellation and shutdown tests |
| OS descendants and offloaded work | Native ownership plus bound filesystem/card mutation drains; this audit repairs direct builtin filesystem calls and exercises application request shutdown |
| Typed terminal truth and exits | Runtime result service, finalization/publication and CLI projection; native CLI fixtures compare running/incomplete/cancelled observations, storage and nonzero exits; live stock CLI controls remain separately required |
| Measured connector timing | Injected monotonic timing/provenance, nullable log projection, interrupted telemetry and retained receipt publication; independent slow-command/timeout comparisons and absent-clock file effects |

The initial union of eight previous BT-4 installed selections contains 58 files
and 607 cases. Against the accepted BT-3 wheel
`62e766b64b8bf9ec9ba611315176d470d9957f0b844bcf3b823ab48f237c992d`,
Linux 3.11 and 3.12 each pass 607; Windows 3.11 and 3.12 each pass 605 and fail two
public-verifier timeout fixtures. Every cell checks 866 installed core/SDK import
origins with no checkout imports. Initial failed reports remain at
`.tmp/bt4-gate-matrix/initial/`; none are rewritten as a successful full run.

Both Windows failures occur while the test constructs psutil identities from
ready markers: the one-second timeout has already stopped a process. The test
must independently observe all three running processes before claiming the
descendant timeout proof. The fixture now admits a five-second command interval,
retaining the separate five-second cleanup allowance. An exited process is
omitted from cleanup discovery but cannot satisfy the three-process startup
assertion. The first fixture adjustment mistakenly retained a five-second outer
wait for the entire five-second timeout plus cleanup; Linux exposed that error.
The corrected outer wait includes both budgets. No production deadline or OS
termination policy changed. The initial and follow-up logs retain this sequence.

The direct-filesystem audit found an actual runtime defect. Unbound builtin
delete invocation returned cancellation or timeout before its executor thread
finished; the held thread then deleted the real target after that return. All
three source controls failed in `.tmp/bt4-gate-direct-filesystem-before.log/.xml`.
The existing bound filesystem path already drained its worker. One adapter
`owned_io.run_owned_io` now supplies that drain to both bound and direct builtin
filesystem calls. Direct read/write/mkdir/delete operations retain ownership
through their complete await, including thread work and handle close. Repeated
caller cancellation cannot abandon the task. Errors remain errors; a failure
while cancellation drains is logged with context. Existing authorization, target
binding, command ownership, HTTP behavior and durable effect recovery are unchanged.

The new integration file holds real unlink/mkdir operations to independently
observe unfinished work. It covers delete, write and mkdir under cancellation,
repeated cancellation and timeout; the application-created API request owner
also stays open while a direct delete worker is held. That API check exercises
the actual application owner but does not claim a TCP request. The earlier API
checkpoint retains real TCP/native-command shutdown proof. Source follow-ups pass
22 cases, then 31 expanded cases; the first ten verifier-fixture cases pass
separately. Logs: `-direct-filesystem-after`, `-filesystem-expanded` and
`-verification-fixture-followup` stems under `.tmp/bt4-gate`.

The new wheel is
`eda343c66e27b25f70e4e60ecd2d9b98de23bafc950b2878413b5a32f96030c2`;
sdist is `97dae6c2f4f469c706355c18aa2e7727ecefbec12117cce8662b2a44bf48588a`.
Both live under `.tmp/bt4-gate-filesystem-dist/`. The affected 77-case installed
selection passes on Windows 3.11/3.12. Linux 3.11/3.12 each pass 75 and fail the
two verifier cases because of the outer-wait fixture error described above;
the filesystem cases pass. These initial reports remain at
`.tmp/bt4-gate-filesystem-matrix/initial/`, with 814 installed origins per cell.
The final corrected verifier file passes all ten cases on each Windows/Linux
3.11/3.12 cell, with 472 installed origins and unchanged runtime wheel bytes:
`.tmp/bt4-gate-verifier-fixture-matrix/report.json`. The final frozen source
selection passes 77 cases in 53.50s with unchanged source hashes throughout;
`.tmp/bt4-gate-filesystem-final-source-report.json` retains those bindings.

Fresh stock installed Windows 3.11 `orket runtime --card` controls use llama.cpp
`orcarouter_qwen3.8-27b-uncensored-q4_k_l` from an external working directory,
JSON-object/enforced local prompting, no prompt patch and disabled sandbox
creation. A one-card canonical workload with required missing source attribution
exits 1 and retains terminal_failure; its successful control exits 0 and retains
done. Each has two actual model receipts. Output, final-truth identity/lifecycle,
publication phase 4 and released admission agree with the SQLite stores. The
installed native supervisor confirms cleanup in both runs. Both CLI starts
report degraded structural reconciliation: "Structural reconciliation failed;
continuing in degraded mode." The underlying startup cause was not isolated in
this checkpoint. These are degraded-startup proofs with the selected llama.cpp
provider, not primary-startup acceptance or a provider fallback. Evidence:
`.tmp/bt4-gate-cli-installed/report.json` and failure-followup/success logs. The
first copied proof driver failed before execution because its adapted supervisor
constructor omitted the required cancellation-event argument; its original
`-cli-failure.log` and external driver remain preserved. The corrected proof
supplies that argument; no runtime code changed for it.

The structural audit at `.tmp/bt4-gate-filesystem-audit.json` binds the 12 changed
paths, 948 runtime Python files byte-identical across source/wheel/sdist, initial
failures, affected follow-ups and live CLI observations. Six sealed outward
fixtures and all 18 plan headings remain unchanged; the original main worktree is
clean and the index remains empty. The full 607-case selection and
repository suite are not repeated for this bounded adapter change.

Claim ceiling and remaining blockers or drift:

- An awaited filesystem operation settling does not undo its effects. A stuck
  filesystem worker can keep cancellation, timeout or API close pending; Python
  threads have no supported forced-stop guarantee. Ownership of detached tasks,
  arbitrary registered resources, remote effects and abrupt host death remains
  subject to the explicit later recovery/convergence contracts.
- The connector event/log/receipt projections do not invent missing measurement.
  Separate existing zeros remain in governed-agent model latency observation
  (`governed_agent_model_provider.py`) and validator-duration receipt input
  (`turn_tool_dispatcher.py`). They are not connector measurement evidence and
  remain required telemetry/conformance work; no whole-runtime timing or capacity
  claim follows from the connector gate.
- Retained original BT-3 timestamp reversal remains unexplained C/D clock drift.
  Broad custom writer/journal/host recovery and the remaining architecture,
  quality, authority, containment and capacity gates remain active.
- Scoped Ruff and the current transition dependency checker pass. This is not
  enforcement of the future C allowed-edge policy. The canonical baseline still
  reports collection_ok=true and release_ready=false; no release acceptance is
  inferred from the installed integration results.

Exact files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_CONNECTOR_FILESYSTEM_LIFETIME_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `docs/specs/CONNECTOR_INVOCATION_TIMING.md`
- `orket/adapters/execution/owned_io.py`
- `orket/adapters/storage/bound_filesystem.py`
- `orket/adapters/tools/builtin_connectors.py`
- `tests/integration/test_outward_filesystem_lifetime.py`
- `tests/integration/test_verification_process_lifetime.py`

### BT-4 validator timing receipts: 2026-09-13

Status: scoped repair implemented and verified. BT-4 remains open, including the
governed-agent model latency/SDK migration and remaining conformance work.

The dispatcher now explicitly emits `protocol_receipt.v2`. Its typed timing
contract preserves fractional/zero numeric context input as `reported`, with
`source: runtime_context`. Missing/null input is `unavailable` with reason
`missing`; invalid input is unavailable with reason `invalid`. Neither state is
claimed as an instrumented measurement. There is no runtime producer of measured
validator duration. Invalid telemetry no longer raises integer-conversion errors
after an otherwise successful tool read. Receipt field authority and migration
rules live in `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`, with the delta in
`docs/architecture/CONTRACT_DELTA_VALIDATOR_TIMING_BT4_2026-09-13.md`.

Verification (observed runtime path `primary`, scoped result `success`):

- Before repair, the new integration selection failed 11 cases and passed two.
  Missing input became zero, fractional input was truncated, and NaN/infinity
  could fail after the real file read. The original and focused assertion-order
  counterexamples remain in `.tmp/bt4-validator-timing-before.log` and
  `.tmp/bt4-validator-timing-counterexample.log`, with matching JUnit artifacts.
- Final source passes **99 tests**, no skips, on Windows Python 3.13.11. Real
  ToolBox/dispatcher reads, JSON receipt hashes, durable receipt append/reuse,
  v1/v2 replay and materialization are exercised. Typed negative cases are
  contract proof, not live timing measurements. Source/runtime hashes are frozen
  before and after in `.tmp/bt4-validator-timing-final-source-report.json`.
- Initial installed checks pass 99 on each Windows cell; both Linux cells pass
  83 and fail 16. Thirteen new cases and three existing writer tests assumed
  uppercase issue directories, while the existing writer uses lowercase names.
  Those assertions were corrected without changing runtime path behavior. The
  red matrix remains `.tmp/bt4-validator-timing-matrix/report.json`.
- Final installed checks pass **99 each** on Windows Python 3.11/3.12 and Linux
  Python 3.11/3.12, with no failures or skips. All 653 loaded runtime/SDK origins
  belong to the respective installation; `pip check` passes. External harness
  hashes are checked before/after. Evidence:
  `.tmp/bt4-validator-timing-labelled-matrix/report.json`. The preceding all-green
  path-correction and test-metadata matrices remain retained; this matrix includes
  per-test taxonomy labels and the existing writer test's import-order repair.
- Built wheel SHA-256:
  `9a245618d69d9dc7d28901d2efe32c6153c4966efbda42f6935d7789f21f3d5b`.
  Sdist SHA-256:
  `1ece9f02c5277778818164683ea5ea4c2ba89cc85a3c33c4bbc66f0f87a3ba02`.
  All **949 runtime Python files** match source/wheel/sdist exactly. These are
  uncommitted worktree artifacts, not released core/SDK versions.
- Stock installed Windows 3.11 `orket runtime --card attribution_epic` succeeds
  outside the checkout, with two actual llama.cpp responses, four valid v2
  receipts containing unavailable timing, retained `done`/completed final truth,
  publication phase 4, released admission and confirmed Windows Job cleanup.
  Model: `orcarouter_qwen3.8-27b-uncensored-q4_k_l`; sandbox disabled. Evidence:
  `.tmp/bt4-validator-timing-cli/report.json`. Startup is explicitly **degraded**
  by structural reconciliation; this is not primary-startup acceptance or a
  provider fallback. The underlying startup failure remains unisolated.

Structural checks and remaining blockers or drift:

- All six changed Python files pass scoped Ruff. The touched writer test's
  pre-existing import-order diagnostic and missing layer label are repaired;
  new tests also carry individual layer labels recognized by the taxonomy gate.
  The transition dependency checker passes
  with legacy-edge enforcement enabled. This does not close C's allowed-edge gate.
- The refreshed baseline reports `collection_ok=true`, `release_ready=false`,
  109 Ruff diagnostics, 3,386 missing labels among 4,615 test functions, 74 runtime
  files over 400 lines and 236 functions over 70 lines. The final checkpoint audit
  is `.tmp/bt4-validator-timing-audit.json`; it binds the exact twelve changed
  files to the proof, preserved plan headings and sealed fixture hashes.
- AC-01/04/07/08/09/10 pass for this slice: pure typed inputs, explicit unavailable
  state, versioned receipt fields, replay preservation and same-change authority.
  AC-02/03/05/06 preserve existing decision and tool authorization boundaries.
  The oversized dispatcher shrinks; its protocol helper does not grow. The new
  contract and test files remain within size limits. Broader structural exceptions
  retain their existing C/D/E owners.
- No fresh full suite, measured validator latency, model-receipt SDK migration,
  whole-runtime telemetry/capacity proof, or whole BT-4 acceptance is claimed.
  At this checkpoint, governed-agent missing latency still became zero under its strict v1 SDK
  receipt; migration must preserve historical wire records and prove matched SDK
  and host artifacts. Previously recorded clock reversal and broader lifetime,
  authority, recovery, containment and capacity work remain active.

Exact files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_VALIDATOR_TIMING_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`
- `orket/application/workflows/turn_tool_dispatcher.py`
- `orket/application/workflows/turn_tool_dispatcher_protocol.py`
- `orket/core/contracts/protocol_receipt_timing.py`
- `tests/application/test_turn_artifact_writer.py`
- `tests/contract/test_protocol_receipt_timing.py`
- `tests/integration/test_protocol_validator_timing.py`

### BT-4 governed-model receipt migration: 2026-09-13

Status: scoped migration implemented and verified; BT-4 and the umbrella remain open.

Missing/invalid governed-model latency now stays unavailable. New
`agent_model_use_receipt.v2` receipts carry nullable integer `latency_ms` and
`reported`/`unavailable` posture. Actual zero remains a reported zero; booleans,
negative numbers and non-integer metadata do not become measurements. Failed JSON
responses preserve the same timing distinction. Partial/invalid token metadata
follows the existing unknown-usage contract: both counts null, with issued maxima
charged. This fixes the reproduced contradiction between partial counts and
unknown usage without altering the response status or reserving extra budget.

The independently versioned receipt travels inside the existing call, iteration
and IPC envelopes. SDK 0.7.0a1 and the reference/starter 0.3.0a1 are development
candidates paired with this host. Published core 0.6.0/0.6.2 retain their SDK 0.6.0
pins. New declarations require `agent_model_use_receipt.v2`; the child ready
handshake must advertise that feature before the host reserves budget or infers.
Canonical historical v1 receipt and nested envelope reads retain their original
fields. Durable restart returns the original receipt without repeat inference,
charges or record mutation. Old history and installed declarations are not rewritten.
Authority and rollback: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`,
`docs/requirements/sdk/VERSIONING.md`, and
`docs/architecture/CONTRACT_DELTA_MODEL_RECEIPT_TIMING_BT4_2026-09-13.md`.

Proof and retained failures:

- Source receipt/schema/admission checks pass 138. The final composed source
  envelope passes **224**, including actual child processes and SQLite restart.
  Synthetic providers prove unavailable timing; they are not live model proof.
- Initial counterexamples retain 16 latency failures, one missing-feature failure
  and four partial-token failures. The first broker run also records one fixture
  digest mismatch (raw integer temperature versus normalized float) and six
  mixed-SDK child failures. Normalizing the test request fixes the former.
  Matched installation fixes the latter; the old-ready negative proves early
  refusal before any model call or reservation. The old peer is a real subprocess
  emitting historical frames, not an installed historical SDK binary.
- Initial installed Python 3.11 cells pass 223 with one source-CWD structural-test
  failure each. Python 3.12 collection fails because setuptools was undeclared
  for an existing package-build test. The structural assertion now inspects the
  imported runtime, and the root dev extra declares setuptools. These failures
  remain in `.tmp/bt4-model-timing-matrix/report.json`.
- The first corrected installed core/SDK/reference tests pass **224 per cell**, no failures,
  errors or skips. All **859** observed package origins are under each environment's
  site-packages, dependencies pass `pip check`, and copied harness hashes match
  before/after. Report: `.tmp/bt4-model-timing-matrix-final/report.json`.
  Windows 3.11/3.12 JUnit times: 25.635/27.802 seconds; Linux: 24.307/24.602.
  The subsequent import-format-only test correction passes its **four** affected
  integration cases per cell, with **532** installed origins checked, in
  `.tmp/bt4-model-timing-matrix-imports/report.json`. No runtime artifact changed.
- The size audit initially omitted the SDK fixture file from its oversized-file
  check. The corrected audit retains that failure: one new field grew the file
  from 400 to 401 lines. Combining the paired latency fields restores 400 lines
  with identical Python AST. The replacement SDK is verified in
  `.tmp/bt4-model-timing-matrix-fixture-format/report.json`: **224 passed per cell**,
  no failures/errors/skips, 859 installed origins and passing dependency checks.
  Windows 3.11/3.12 JUnit times are 25.067/27.221 seconds; Linux 52.382/50.888.
  Final artifact parity covers all 949 core Python files, 30 SDK Python/schema
  files, two reference modules and the starter module. All 19 changed Python
  files pass Ruff; source fixtures, the plan's 18 H2 headings and both main
  checkouts remain intact. Documentation hygiene and the transition dependency
  checker pass. The baseline remains truthful: 109 Ruff diagnostics, 3,379 missing
  labels among 4,624 test functions, 74 runtime files over 400 lines and 236
  functions over 70 lines; `collection_ok=true`, `release_ready=false`.
- The reference release script verifies the extracted sdist, strict SDK/import
  validation and its test: one passed. Its `--tag v0.3.0a1` checks version equality;
  it did not create a tag or publish. The starter wheel and sdist also build.
- **Live, primary, success:** native installed Windows Python 3.11
  `orket agent submit governed-agent-loop` uses the extracted reference sdist,
  llama.cpp at `http://127.0.0.1:8080/v1`, and inventoried exact model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`. Two iterations produce continue/complete,
  six actual v2 receipts and completed final truth. Reported latencies are
  2135, 820, 2667, 2290, 1100 and 2477 ms. Independent canonical hashing matches
  retained call/iteration digests; CLI receipts equal database receipts. Exit is
  zero, capture is complete and Windows Job cleanup is confirmed. Evidence:
  `.tmp/bt4-model-timing-cli/report.json`; retained workspace:
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-model-timing-cli-geqbmfp8`.
  The first successful CLI run against the earlier SDK remains in `prior_runs`;
  the final run uses the replacement SDK below. Reference sdist validation also
  passes again with the replacement SDK.

Candidate wheel SHA-256 values (sdist hashes remain in the reports):

- Core 0.6.2: `2e885b28668fe557ef9c1c9432bea8c3b4144a65c62ab015369f3bc3addc4a56`.
- SDK 0.7.0a1: `ab76f47700064934e8bdd01c431d029b19f5693e632f279aecc182aad7ac82a6`.
- Reference 0.3.0a1: `04e58e22c4f2a951e5fef3df754f3e1fa2b6cec5c667e9b4564694a26e39031a`.
- Starter 0.3.0a1: `8f2b377bf947029f0acdb2afa4d5837e75c55cbcdedc4eea8225533bcf1fff25`.

The reference counterpart is in `.tmp/governed-agent-model-timing`, branch
`codex/model-receipt-v2`, based on `9e8281b5c7cd48073094ed4ab657e291c75e1604`.
Its canonical main checkout remains unchanged. No package, release or tag is
published by this checkpoint. The scoped audit is `.tmp/bt4-model-timing-audit.json`.
AC-01/04/07/08/09/10: pass for this slice, through typed metadata, versioned
schemas, history retention and same-change authority. AC-02/03/05/06: pass for the
unchanged decision, authorization and adapter-classification boundaries.
Existing architectural exceptions retain C/D/E
owners. A fresh full suite, independent model timing scope, whole-runtime telemetry,
broader live API/provider acceptance and whole BT-4 closure are not claimed.

Exact core-worktree files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_MODEL_RECEIPT_TIMING_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/requirements/sdk/VERSIONING.md`
- `docs/specs/GOVERNED_AGENT_LOOP_V1.md`
- `docs/templates/governed_agent_external/README.md`
- `docs/templates/governed_agent_external/extension.yaml`
- `docs/templates/governed_agent_external/pyproject.toml`
- `orket/application/services/governed_agent_admission.py`
- `orket/application/services/governed_agent_broker_service.py`
- `orket/application/services/governed_agent_fixture.py`
- `orket/application/services/governed_agent_model_provider.py`
- `orket/extensions/governed_agent_invoker.py`
- `orket_extension_sdk/CHANGELOG.md`
- `orket_extension_sdk/README.md`
- `orket_extension_sdk/__version__.py`
- `orket_extension_sdk/agent_broker.py`
- `orket_extension_sdk/agent_fixtures.py`
- `orket_extension_sdk/agent_types.py`
- `orket_extension_sdk/agent_validation.py`
- `orket_extension_sdk/manifest.py`
- `orket_extension_sdk/schemas/governed_agent_loop_v1.json`
- `pyproject.toml`
- `tests/contract/test_governed_model_latency.py`
- `tests/fixtures/governed_agent/legacy_ready_child.py`
- `tests/fixtures/governed_agent/model_receipt_v1.json`
- `tests/integration/test_governed_model_receipt_migration.py`
- `tests/runtime/test_extension_components.py`
- `tests/runtime/test_governed_agent_admission.py`
- `tests/sdk/test_manifest.py`
- `tests/sdk/test_model_receipt_versions.py`
- `tests/sdk/test_validate_module.py`

Exact reference-worktree files: `CHANGELOG.md`, `README.md`, `extension.yaml`,
`pyproject.toml`. Ignored build/proof files are retained at the evidence paths above.

### BT-4 provider timing availability: 2026-09-13

Status: scoped repair implemented and verified; BT-4 and the umbrella remain active.

Backend prompt, generation and total durations now stay null when unavailable.
`model_provider_timing.v1` identifies new provider observations; client elapsed
time remains separate with its existing successful-attempt measurement scope.
No missing phase is synthesized by subtraction, zero or client latency. Actual
zero and fractional durations remain valid. Turn projections disclose reported,
partial, unavailable or legacy-unverified timing without rewriting history.
Benchmark aggregates require complete, versioned phase coverage across every
included turn and complete token coverage for throughput. Disjoint observations
cannot become a complete measurement.

SDK `GenerateResponse` and the generic extension API retain nullable integer
latency, `model_generate_response.v1` and a frozen reported/unavailable posture.
Serialization preserves both fields. Null/static providers claim no model timing.
Shared strict integer observation handling also serves governed v2 receipts,
without changing their wire format, budget policy or historical read contract.
This remains the unpublished SDK 0.7.0a1/core candidate pair. Durable authority:
`docs/specs/MODEL_PROVIDER_TIMING.md`; migration/rollback:
`docs/architecture/CONTRACT_DELTA_PROVIDER_TIMING_BT4_2026-09-13.md`.

Proof and retained failures:

- Initial source counterexamples retain 43 failures for provider/SDK timing and
  six failures plus one pass for aggregate coverage. Two existing adapter tests
  asserted fabricated phases; their 2-failure/171-pass run is preserved before
  correcting those expectations. The first Ruff pass also disclosed three
  pre-existing runner findings. Equivalent expression cleanup and contextual
  stderr reporting replace its silent temporary-epic cleanup failure.
- The final frozen source envelope passes **332**, no failures/errors/skips:
  `.tmp/bt4-provider-timing-source-report.json` and
  `.tmp/bt4-provider-timing-final-source.xml`. It covers real retained log files,
  host routing, actual child processes and SQLite alongside synthetic provider
  controls. MockTransport, static providers and TestClient are not live inference.
- Four installed Windows/Linux Python 3.11/3.12 cells pass **332 each**, no
  failures/errors/skips, with **860** observed package origins under each owned
  site-packages, passing `pip check` and unchanged copied harness hashes.
  Windows JUnit times: 27.457/33.070 seconds; Linux: 26.598/26.451 seconds.
  `.tmp/bt4-provider-timing-matrix/report.json` retains exact artifacts and paths.
  Reference sdist verification passes its one test again against the new SDK;
  `--tag v0.3.0a1` checks version equality without creating or publishing a tag.
- **Live CLI, degraded startup, success:** native installed Windows Python 3.11
  `orket runtime --card attribution_epic` uses inventoried llama.cpp model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l` at `http://127.0.0.1:8080/v1`.
  Two original responses report prompt/generation phases of
  467.32/2996.237 ms and 472.945/2139.116 ms. Backend total remains null despite
  measured client latency of 3735/2812 ms. Retained turn phases match the original
  backend payloads; aggregate prefill/decode is 0.940/5.135 seconds within the
  declared three-decimal rounding tolerance. Exit zero, persisted done/completed
  truth, publication phase 4, released admission and Windows Job cleanup agree.
  The pre-existing structural reconciliation warning remains unisolated.
  Evidence: `.tmp/bt4-provider-timing-cli/report.json`; workspace:
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-provider-timing-cli-tp3v7bz3`.
- **Live TCP API, primary, success:** an authenticated request through the real
  installed application and uvicorn returns HTTP 200, text `ready`, the exact
  llama.cpp model, the versioned response and reported client latency **641 ms**.
  Application close completes with zero tracked background tasks; exit zero,
  complete capture and Windows Job cleanup are confirmed. The first two attempts
  failed before API startup: the proof worker used an unsupported factory keyword,
  then constructed the app inside the running loop instead of before bootstrap.
  Both errors and cleanup results remain in `prior_runs`; failed workers are
  preserved in their original proof directories. Correcting the worker changes
  no runtime code. Evidence: `.tmp/bt4-provider-timing-api/report.json`; successful
  workspace: `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-provider-timing-api-965ekr8l`.

Candidate wheel SHA-256 values:

- Core 0.6.2: `589157da3909e215c5a697797927b55bde33d0d1c7a5a74bd005796cc9b530df`.
- SDK 0.7.0a1: `4ab3b8cfafc02853b93367ac2adbe034242f2cbda9ec7aa636150e35d0f31c90`.
- Reference 0.3.0a1: `04e58e22c4f2a951e5fef3df754f3e1fa2b6cec5c667e9b4564694a26e39031a`.
- Starter 0.3.0a1: `8f2b377bf947029f0acdb2afa4d5837e75c55cbcdedc4eea8225533bcf1fff25`.

Core/SDK sdists are respectively
`c1357975eeb9123655d21ef6c1bfd00b70c30aeac4ab1a82dc2e84a2135d98f7`
and `9902fa3840da0e9d03600317150bfb1066f5d497e281611ca96d61924821b1d8`.
The audit at `.tmp/bt4-provider-timing-audit.json` checks source/wheel/sdist byte
parity for all 950 runtime Python files, 30 SDK Python/schema files, two unchanged
reference modules and the unchanged starter. It also checks frozen source and
installed harnesses, exact scope, test labels, sizes, Ruff, dependency transition,
documentation hygiene, sealed fixtures, all 18 original H2 headings and clean
original main checkouts. An initial diagnostic read used the platform's default
text encoding and misread one archived filename in the UTF-8 start snapshot.
The first audit incorrectly expected a filename alias and failed that assertion;
its other checks passed. The corrected audit reads UTF-8 explicitly without any
path remapping. The original snapshot and archived file are unchanged; the failed
audit remains at `.tmp/bt4-provider-timing-audit-initial.json`.

The refreshed baseline at `2026-09-13T21:34:52.832882Z` remains structural evidence:
109 Ruff findings, 3,377 missing labels among 4,636 tests, 74 runtime files above
400 lines and 236 functions above 70 lines. `collection_ok=true` and
`release_ready=false`. No full-suite rerun, independent backend/GPU measurement,
capacity proof, live LM Studio/Ollama or full BT-4 acceptance is claimed.

Remaining blockers or drift: structural inspection of
`orket/application/services/extension_runtime_support.py::generate_response`
shows a worker thread without cancellation drain, temporary global provider
environment mutation across awaits, and an override client without explicit
close. These are not reproduced live by this successful request; BT-4/BT-5/C/D
retain ownership of counterexamples and repair. Existing generic request option
forwarding also needs conformance review. Benchmark coverage applies to included
parseable turns; corrupted-log completeness and extreme numeric robustness remain
outside this proof. Detached work, force-stopping stuck threads, remote effects,
host-death recovery, the unexplained earlier clock reversal, wider telemetry and
the BT-5/C/D/E/CAP gates remain required. No reference-worktree files changed in
this checkpoint and no commit, tag or release was made.

AC-01/02/03/04/07/08/09/10 pass for the scoped dependency, explicit observation,
versioned projection and authority changes. AC-05/06 remain partial for the
pre-existing generic generation lifetime/client boundary and incomplete adapter
side-effect classification; the timing change does not widen those effects.
The paths and remediation owners are named above.

Exact worktree files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/architecture/CONTRACT_DELTA_PROVIDER_TIMING_BT4_2026-09-13.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/requirements/sdk/VERSIONING.md`
- `docs/specs/MODEL_PROVIDER_TIMING.md`
- `orket/adapters/llm/local_model_provider.py`
- `orket/adapters/llm/openai_compat_runtime.py`
- `orket/adapters/llm/provider_extractors.py`
- `orket/application/services/extension_runtime_service.py`
- `orket/application/services/governed_agent_model_provider.py`
- `orket/application/workflows/turn_executor_runtime.py`
- `orket/capabilities/sdk_llm_provider.py`
- `orket/capabilities/sdk_static_provider.py`
- `orket/core/contracts/model_timing.py`
- `orket_extension_sdk/CHANGELOG.md`
- `orket_extension_sdk/README.md`
- `orket_extension_sdk/llm.py`
- `scripts/benchmarks/live_card_benchmark_runner.py`
- `scripts/benchmarks/live_card_timing_metrics.py`
- `tests/adapters/test_local_model_provider_telemetry.py`
- `tests/adapters/test_provider_extractors.py`
- `tests/contract/test_provider_timing_availability.py`
- `tests/contract/test_sdk_generate_timing.py`
- `tests/integration/test_extension_generate_timing.py`
- `tests/scripts/test_live_card_timing_availability.py`

### BT-4 extension generation lifetime: 2026-09-13

Status: scoped repair implemented and verified; full BT-4 and later gates remain active.

Generic extension generation now drains its synchronous worker through repeated
cancellation. Request-created builtin clients close in that worker on the same
bridge loop used by generation. Explicit provider arguments replace temporary
process-wide environment mutation. The API registers its extension runtime service
for teardown and closes the default model client after admitted requests settle.
Injected providers remain embedding-owned. Worker or cleanup failures take
precedence over cancellation on this seam; failed cleanup cannot become a clean
application close. No inference interrupt, force-stop deadline or per-application
bridge-thread shutdown is claimed.

Authority: `docs/specs/API_RUNTIME_LIFECYCLE.md`; migration and rollback:
`docs/architecture/CONTRACT_DELTA_EXTENSION_GENERATION_LIFETIME_BT4_2026-09-13.md`.
The synchronous SDK protocol and timing schemas are unchanged. This is another
unreleased core candidate paired with the existing SDK 0.7.0a1.

Proof and retained counterexamples:

- Five initial integration failures in `.tmp/bt4-generation-lifetime-before.xml`
  show cancellation settling while a real executor worker could still write,
  override generation mutating both global provider variables, and absent client
  cleanup. Before the repair, tests always released and awaited their controlled
  workers; they do not leave detached effects behind.
- The repaired worker/SDK/service selection passes 27 checks. Five additional API
  checks pass: actual authenticated TCP request shutdown with default and override
  clients, normal lifespan cleanup, embedding ownership and synthetic cleanup
  failure. Controlled model output and gated failure are not live model proof.
  The seven changed Python files pass Ruff. Removing unused support imports also
  makes `validate_extension_id` consume its canonical module directly.
- Final frozen source selection: **372 passed**, no failures/errors/skips,
  31.31 seconds, with unchanged source hashes during execution. Evidence:
  `.tmp/bt4-generation-lifetime-source-report.json` and
  `.tmp/bt4-generation-lifetime-final-source.xml`.
- Four installed Windows/Linux Python 3.11/3.12 cells each pass **372**, no
  failures/errors/skips. **860** observed package origins per cell stay under their
  owned site-packages; `pip check` and before/after copied-harness hashes pass.
  Windows JUnit times: 31.823/41.755 seconds; Linux: 34.833/35.523 seconds.
  `.tmp/bt4-generation-lifetime-matrix/report.json` records the final matrix.
  The selection includes earlier provider/governed timing, SDK, child-process,
  SQLite, API composition/request teardown and filesystem drain regression proof.
- **Live, primary, success:** native installed Windows Python 3.11 serves the
  canonical app through uvicorn on an owned local TCP socket. Exact inventoried
  llama.cpp model `orcarouter_qwen3.8-27b-uncensored-q4_k_l` at
  `http://127.0.0.1:8080/v1` returns normal default and override responses, both
  HTTP 200, with measured client latency 398/131 ms. A third real generation is
  active when application shutdown starts. It finishes after shutdown begins,
  then the default client closes, then application close completes. The pending
  HTTP request receives **503**, not the late generated text. Observed close wait
  is approximately **15.396 seconds**; this is one observation, not a deadline.
  Both clients close on `orket-sync-bridge-loop`; active request/background counts
  are zero. Exit zero, complete capture and Windows Job cleanup are confirmed.
  Passive wrappers observe original provider calls and closes without replacing
  inference. Each retained raw call equals the worker's final observation.
  Report: `.tmp/bt4-generation-lifetime-api/report.json`; workspace:
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-generation-lifetime-api-2e4s8brr`.

The live run also confirms a distinct conformance defect: the third HTTP request
specified `max_tokens: 512`, but the actual backend response reports **593 output
tokens**. Generic SDK request options are not yet forwarded through the provider
policy/transport path. The current lifetime repair does not certify token limits,
temperature or stop sequences; request-option enforcement is the next required
generic-generation repair under BT-4/BT-5/C/D. Preserve this counterexample rather
than relabeling the successful cleanup as full request conformance.

Candidate core 0.6.2 wheel SHA-256:
`b196bf091e482126fbec5c892cbdf271cb73c08ef9e499afebb611bf3e0966d8`;
sdist: `aadbaf1958c64caf36e339aaca841d96bfa882defecc57835076eb9e7ad76ea4`.
The SDK, reference and starter artifacts are unchanged from the preceding timing
checkpoint. The audit at `.tmp/bt4-generation-lifetime-audit.json` binds all 950
runtime Python files, 30 SDK Python/schema files, two reference modules and the
starter to source/wheel/sdist byte parity; it also checks retained live call bytes,
shutdown ordering, test/source hashes, exact scope, test labels, file/function
sizes, dependency transition, docs hygiene, sealed fixtures and 18 original H2
headings. Both original main checkouts remain clean. No commit, tag or publication.

The structural baseline at `2026-09-13T21:53:06.219763Z` reports 106 Ruff findings,
3,377 missing labels among 4,643 test functions, 74 runtime files over 400 lines
and 236 functions over 70 lines. Collection succeeds; release readiness is false.
No new function exceeds 70 lines; all seven touched Python files are below 400.

Remaining blockers or drift: the live token-limit contradiction above, other
generation request options, non-model extension offloads/resources, stuck-thread
termination, remote computation/effect termination, process-owned bridge-thread
lifetime, direct embedding admission coordination and broader recovery remain
unverified or incomplete. The prior unexplained timestamp reversal, degraded
standard-CLI startup and later BT-5/C/D/E/CAP obligations remain open. A fresh full
suite, native live Linux inference, LM Studio/Ollama live acceptance and whole
BT-4 closure are not claimed by this 372-case envelope.

AC-01/02/03/04/05/06/07/08/09/10 pass for this scoped drain, explicit selection,
model-resource ownership and failure-observation repair. Existing request-option
drift and other resource boundaries retain the named active owners above; no
general conformance or target-architecture exception closure follows from it.

Exact worktree files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/architecture/CONTRACT_DELTA_EXTENSION_GENERATION_LIFETIME_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `orket/adapters/execution/owned_io.py`
- `orket/application/services/api_runtime_composition.py`
- `orket/application/services/extension_runtime_service.py`
- `orket/application/services/extension_runtime_support.py`
- `orket/capabilities/sdk_llm_provider.py`
- `tests/integration/test_extension_generation_api_lifetime.py`
- `tests/integration/test_extension_generation_lifetime.py`

### BT-4 generation request options: 2026-09-13

Status: scoped request/profile repair implemented and verified; full BT-4 and later gates remain active.

The preceding live 512-request/593-output-token contradiction is repaired on the
builtin SDK/API path. `GenerateRequest` now supplies its token limit, temperature
and stop sequences to the canonical local prompting policy. The effective limit
is the smaller of request and profile ceilings. Explicit temperature applies to
the call without mutating provider defaults. Stops preserve exact whitespace,
deduplicate only identical strings, and precede profile stops. Empty/non-string
stops and malformed numeric options fail before inference. Existing API numeric
parsing/bounds and strict-profile refusal are retained.

Unresolved profiles in already admitted shadow/compat paths keep explicit options
instead of discarding them. Partial sampling bundles map only present fields.
Final review also reproduced trimming and invalid-element coercion in custom
profile files; profile loading and binding now use the same pure core stop
validator. The former profile token-normalization helper is no longer stop
authority. The oversized policy and profile modules shrink to 558 and 434 lines.
Authority: `docs/specs/MODEL_GENERATION_OPTIONS.md` and
`docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`; delta:
`docs/architecture/CONTRACT_DELTA_GENERATION_OPTIONS_BT4_2026-09-13.md`.

Proof and retained counterexamples:

- Initial transport/policy controls retain **22 failures and four passes** in
  `.tmp/bt4-generation-options-before.xml`. They cover missing SDK forwarding,
  unresolved-profile option loss, malformed limits and stop strings. The first
  repaired SDK/policy/service selection passes 49; expanded API/profile-ceiling
  checks pass 52. MockTransport and the controlled Ollama client are contract
  evidence, not live provider acceptance.
- The first frozen source and four installed cells pass **424** each, with 861
  installed origins per cell. Reports remain at
  `.tmp/bt4-generation-options-source-report.json` and
  `.tmp/bt4-generation-options-matrix/report.json`. Their core wheel is
  `7d07f0eba387b6409b86a09b54646210e46f41a94d713352ab4737d1e4e647cc`.
  These are historical proof before the custom-profile stop correction.
- The later real profile-file counterexamples retain **three failures** in
  `.tmp/bt4-generation-options-profile-before.xml`: trimmed whitespace, a silently
  removed empty string and a stringified integer. The repaired focused selection
  passes 68. Profile parsing/binding and request options now import one core
  contract rather than parallel validators.
- Final frozen source passes **440**, no failures/errors/skips, 41.16 seconds:
  `.tmp/bt4-generation-options-profile-source-report.json` and
  `.tmp/bt4-generation-options-profile-source.xml`. Input hashes remain unchanged
  during execution; the subsequent baseline refresh is separately identified.
- Final installed Windows/Linux Python 3.11/3.12 cells pass **440 each**, no
  failures/errors/skips, with **861** observed package origins under owned
  site-packages, passing dependency checks and unchanged copied harness hashes.
  Windows JUnit times: 51.270/68.669 seconds; Linux: 34.196/34.306 seconds.
  `.tmp/bt4-generation-options-matrix-profile/report.json` binds the replacement
  core artifact. The selection retains prior SDK, governed receipts, child-process,
  SQLite, provider telemetry, API lifetime and filesystem drain regression proof.
- **Live, primary, success:** native installed Windows Python 3.11 serves the
  canonical application via authenticated TCP/uvicorn. The inventoried llama.cpp
  model is `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, at
  `http://127.0.0.1:8080/v1`. A requested 32-token limit reaches the actual provider
  payload; the response reports exactly **32** output tokens and
  `finish_reason=length`. A paired copy control returns `alpha ENDSTOP omega`
  without the caller stop and `alpha` with the exact stop string ` ENDSTOP `.
  All three HTTP responses are 200. Captured outbound payloads retain temperature
  0.0 and the stop string's surrounding spaces; retained original responses
  distinguish length and stop termination. Passive wrappers observe original
  HTTP send, model completion and client close without replacing inference.
  Both builtin clients close on their bridge loop, active request/background
  counts become zero, exit is zero and native Windows Job cleanup is confirmed.
  Evidence: `.tmp/bt4-generation-options-api/report.json`; final workspace:
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-generation-options-api-bbm0q8_i`.
  The earlier successful run against the first core remains in `prior_runs`.

Final core 0.6.2 wheel SHA-256:
`923dbbc4cde6b7cd1bb29754e042ee1cfa158b2adccb2f247571737589772ed8`;
sdist: `13b3f01dbb8cdadabd83662828d8843dbce200098a81b2c3d280625fe760364b`.
SDK 0.7.0a1, reference/starter 0.3.0a1 artifacts are unchanged from the preceding
checkpoints. No SDK wire/schema, commit, tag or publication change occurs here.
The audit at `.tmp/bt4-generation-options-audit.json` binds all 951 core Python
files, the packaged profile registry, 30 SDK Python/schema files, two reference
modules and the starter to source/wheel/sdist bytes. It checks actual request and
response records, current artifact identity, frozen source/harnesses, exact scope,
test labels, sizes, Ruff, dependency transition, docs hygiene, sealed fixtures,
18 original H2 headings and both clean original main checkouts.

The structural baseline at `2026-09-13T22:18:39.209064Z` reports 106 Ruff findings,
3,377 missing labels among 4,649 test functions, 74 oversized runtime files and
236 functions above 70 lines. Collection succeeds; `release_ready=false`.
The seven changed Python files pass Ruff; new files/functions satisfy size bounds,
and both touched oversized modules shrink.

Remaining blockers or drift: forwarding and this backend's reported token/stop
behavior do not independently certify temperature's statistical effect, all
provider implementations, arbitrary native payload overrides or every runtime
context producer. Custom profile-file whitespace has composed contract proof,
not separate live custom-profile inference. A length-limited text response is
transport success, not proof of the larger requested writing objective. No fresh
full suite, live LM Studio/Ollama, native live Linux inference or whole BT-4 closure
is claimed. Non-model capability offloads/resources, stuck-thread and remote
termination, broader recovery, the earlier timestamp reversal/degraded CLI
startup, BT-5/C/D/E and CAP requirements remain active.

AC-01/02/03/04/05/06/07/08/09/10 pass for this scoped explicit-option, pure
validation, profile-ceiling and exact-stop repair. Existing architecture exceptions
and wider authority/resource boundaries keep their active owners; this checkpoint
does not close them.

Exact worktree files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/architecture/CONTRACT_DELTA_GENERATION_OPTIONS_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `docs/specs/MODEL_GENERATION_OPTIONS.md`
- `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
- `orket/adapters/llm/local_prompting_policy.py`
- `orket/application/services/extension_runtime_service.py`
- `orket/capabilities/sdk_llm_provider.py`
- `orket/core/contracts/model_generation_options.py`
- `orket/runtime/config/local_prompt_profiles.py`
- `tests/contract/test_generation_request_options.py`
- `tests/integration/test_extension_generation_options_api.py`

### BT-4 extension capability workers: 2026-09-13

Status: scoped worker lifetime repair implemented and verified; full BT-4 and later gates remain active.

The six remaining synchronous offloads in `ExtensionRuntimeService` now use
`run_owned_thread`: model availability, transcription/status probes, voice
discovery, speech synthesis and voice control. The helper delegates to the existing
owned-I/O drain with failure precedence. Model generation and default-model
cleanup share the helper. Cancellation, repeated cancellation and elapsed asyncio
deadlines wait for the current worker; successful late results are discarded.
Worker exceptions retain existing API error mapping, and unhandled failures remain
observable to shutdown. No provider close protocol or forced termination is added.
Authority: `docs/specs/API_RUNTIME_LIFECYCLE.md`; delta:
`docs/architecture/CONTRACT_DELTA_EXTENSION_WORKERS_BT4_2026-09-13.md`.

Proof and retained counterexamples:

- The initial actual-executor controls reproduce **18 failures and six passes**:
  `.tmp/bt4-extension-offloads-before.xml`. Cancellation and timeout returned while
  workers could still write. The repaired focused generation/capability envelope
  passes **34**; a further **12** real TCP cases retain delayed effects and worker
  failures through repeated close cancellation, stop new admission, and confirm
  model-client cleanup. These use controlled provider delays/results, not live
  STT/TTS inference. Failed teardown repeats the same retained error.
- Frozen source passes **476**, no failures/errors/skips, 49.38 seconds:
  `.tmp/bt4-extension-offloads-source-report.json` and
  `.tmp/bt4-extension-offloads-source.xml`. The subsequent baseline refresh is
  separately identified; inputs did not change during the run.
- Final installed Windows/Linux Python 3.11/3.12 cells pass **476 each**, no
  failures/errors/skips. All **861** observed package origins per cell are in owned
  site-packages; dependencies and copied harness hashes pass. Windows JUnit times
  are 51.700/72.430 seconds, Linux 42.301/42.952 seconds. Evidence:
  `.tmp/bt4-extension-offloads-matrix-selection/report.json`. The first campaign
  stopped before collection because the copied harness renamed one existing test
  path incorrectly; its zero-test failures remain at
  `.tmp/bt4-extension-offloads-matrix/report.json`. Only the harness selection was
  corrected. An initial build invocation also used an interpreter without the
  build frontend; the successful build used the existing build-capable interpreter.
- **Live, primary, success:** native installed Windows Python 3.11 serves the
  canonical application over authenticated TCP/uvicorn from a foreign directory.
  Actual Piper 1.8.0 / ONNX Runtime 1.30.0 uses the existing
  `C:/Source/Orket/data/voices/en_US-lessac-medium.onnx`. A normal synthesis returns
  **78,848** PCM bytes at 22,050 Hz, mono, `pcm_s16le`. Shutdown starts while a second
  Piper child is active, waits **10.699 seconds** through repeated close-caller
  cancellation, and returns HTTP **503** for that request. The original synchronous
  call produces **14,505,984** bytes before settling; those cancelled bytes are not
  returned as a successful response. Both actual Piper children exit **0**.
  Active request/background counts become zero, the default model client closes,
  the worker exits zero, and Windows Job cleanup/capture are confirmed. Passive
  observers call original synthesis and subprocess operations without delays or
  substitute inference. Voice start/state/stop return listening/listening/idle;
  unconfigured STT explicitly returns `stt_unavailable`. Report:
  `.tmp/bt4-extension-offloads-api/report.json`; retained workspace:
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-extension-offloads-api-wurap8ak`.
  Piper was installed only into the owned Win311 proof environment, with a passing
  dependency check; no global package or production dependency changed.

Core 0.6.2 wheel SHA-256:
`13939c23f09dab5830f80511d465a81063c3c3c183d71a09b284de80fbe377e3`;
sdist: `b0e1ca677cb0d71362dfb8ab4fc4fbeb985f6ea9f093ca21e55af85243e61ab4`.
SDK 0.7.0a1 and reference/starter 0.3.0a1 artifacts remain unchanged. No release,
commit, tag or publication is performed. The audit at
`.tmp/bt4-extension-offloads-audit.json` binds 951 core Python files, the profile
registry, 30 SDK Python/schema files, reference and starter modules to their
source/wheel/sdist bytes. It checks source/harness stability, live records, exact
scope, sizes, labels, Ruff, dependency transition, docs hygiene, sealed fixtures,
the original 18 H2 headings, and both clean original main checkouts.

The refreshed structural baseline at `2026-09-13T22:40:24.642001Z` records 106 Ruff
findings, 3,377 missing labels among 4,651 test functions, 74 oversized runtime
files and 236 functions above 70 lines. Collection succeeds; release readiness
remains false. All five changed Python files pass Ruff and remain under 400 lines;
the service shrinks from 395 to 394 lines. New functions satisfy the 70-line bound.

Remaining blockers or drift: the existing null voice catalog makes
`tts_available=true` even though synthesis reports `tts_unavailable`. Piper still
uses unsupervised synchronous subprocess execution and probing; this worker drain
does not supply bounded native descendant termination. Those paths require further
BT-4 remediation. No speech-provider close protocol, stuck-thread termination,
detached-provider work or abrupt-host-death recovery is proved. No live STT model
is configured; the observed STT path is degraded/unavailable, not successful speech
recognition. This run does not assess perceived audio quality, live Linux Piper,
fresh full-suite acceptance or fresh llama.cpp inference. Wider lifetime/outcome
obligations, the earlier timestamp reversal/degraded CLI startup, BT-5/C/D/E and
CAP requirements remain active.

AC-01/02/03/04/05/06/08/09/10 pass for this scoped worker drain. AC-07 is partial:
worker settlement is now truthful, while the pre-existing null-voice availability
mismatch remains owned by Orket Core in this plan and is not widened here.

Exact worktree files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/architecture/CONTRACT_DELTA_EXTENSION_WORKERS_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `orket/adapters/execution/owned_io.py`
- `orket/application/services/extension_runtime_service.py`
- `orket/application/services/extension_runtime_support.py`
- `tests/integration/test_extension_capability_api_lifetime.py`
- `tests/integration/test_extension_capability_lifetime.py`

### BT-4 host Piper native supervision: 2026-09-13

Status: native host-Piper ownership and generic null availability repaired; full BT-4 and later gates remain active.

Host `PiperTTSProvider` now requires the application's `CommandRunner` and
workspace. API and SDK workload composition supply the existing native supervisor;
there is no parallel native owner. The generic API directly awaits the exact builtin
Piper class's async implementation so cancellation reaches native ownership. Injected
subclasses retain their synchronous overrides and voice catalogs. The synchronous SDK
method bridges to that same implementation. A configurable finite positive native
deadline defaults to 120 seconds. Discovery is offloaded/drained and launches no
`--help` process. Explicit invalid backend/model-owner selection fails instead of
silently changing to null TTS.

The shared command port admits an optional integer capture bound from 1 byte
through 64 MiB, validated by both transport and isolated worker from one definition.
Piper uses 64 MiB for PCM; verifier/outward defaults remain 4 MiB. Only completed
exit zero with complete capture and confirmed cleanup can yield a clip. Native
failures retain their result on `PiperSynthesisError`; missing cleanup confirmation
remains `CommandExecutionUncertain`. The TTS API adds nullable `process_lifetime`.
Empty configured-provider output reports `tts_empty_audio`; the generic null
backend has no available catalog and consistently reports `tts_unavailable`.
Authority: `docs/specs/PIPER_RUNTIME_CONTRACT.md`, native/API lifetime specs and
event taxonomy. Delta:
`docs/architecture/CONTRACT_DELTA_PIPER_SUPERVISION_BT4_2026-09-13.md`.

Proof and observed results:

- The first affected regression selection passes **58** checks. The new selection
  initially reports **two failures and 29 passes** because two assertions compared
  an entire log payload with an unenriched lifetime dictionary. The logger's
  standard runtime-event envelope was correctly present. Assertions now compare
  all lifetime fields while allowing that envelope; the corrected new selection
  passes **31**. Both attempts remain in `.tmp/bt4-piper-supervision-new.xml` and
  `.tmp/bt4-piper-supervision-new-final.xml`. No runtime change was made for that
  assertion repair.
- Final review reproduced **three failures** against the first installed wheel:
  the async fast path bypassed an injected Piper subclass's synchronous override,
  and builtin-null classification discarded a custom subclass's declared voices.
  Exact builtin-class checks preserve those embedding implementations. The
  counterexamples remain in `.tmp/bt4-piper-supervision-subclasses-before.xml`
  with artifact/test identity at the matching `.json`; the repaired focused
  envelope passes **54**. A first metadata probe encountered source egg-info and
  was corrected to read the owned installed distribution explicitly.
- Actual native fixture trees exercise the builtin Piper adapter and authenticated
  TCP route with detached, TERM-resistant children/grandchildren. Cancellation,
  repeated cancellation, timeout, leader success/failure, retained cleanup and no
  later heartbeat writes are verified independently. Native 5/7 MiB stdout/stderr
  controls prove admitted 6 MiB capture and refusal above it; malformed bounds
  refuse before dispatch. Existing verifier/outward 4 MiB refusal remains covered.
  These use controlled commands/models and do not prove speech inference.
- Final frozen source passes **538**, no failures/errors/skips, 69.44 seconds:
  `.tmp/bt4-piper-supervision-final-source-report.json` and
  `.tmp/bt4-piper-supervision-final-source.xml`. Inputs are unchanged during execution;
  the later baseline refresh is separately identified.
- Final installed Windows/Linux Python 3.11/3.12 cells pass **538 each**, no
  failures/errors/skips, with **862** observed package origins per cell under owned
  site-packages. Dependencies and copied harness hashes pass. Windows JUnit times
  are 73.702/89.389 seconds; Linux 66.404/67.311 seconds. Evidence:
  `.tmp/bt4-piper-supervision-matrix-final/report.json`. The selection also retains the
  preceding SDK/governed receipt, provider, API, SQLite and filesystem envelopes.
  First-candidate source/installed **535**-check proof remains at
  `.tmp/bt4-piper-supervision-source-report.json` and
  `.tmp/bt4-piper-supervision-matrix/report.json`, bound to wheel
  `8449b31e564ca4003c2f0e8fd421a6ad31a3bee1f238767ffab7336988cb7d85`.
- **Live, primary, success:** native installed Windows Python 3.11 serves the
  canonical application over authenticated TCP from a foreign directory. Actual
  Piper 1.8.0 / ONNX Runtime 1.30.0 uses the unchanged local
  `en_US-lessac-medium.onnx` and configuration. Normal requests return **73,216**
  and **14,564,864** PCM bytes with HTTP 200, confirming actual speech output beyond
  the verifier's 4 MiB default. API lifetime fields match the original native
  observations: completed exit zero, complete capture and confirmed Windows Job
  cleanup. A third request is cancelled after an independent process observer
  sees the real Piper command alive. Shutdown completes in **0.080662 seconds**,
  that retained process identity is no longer running, and the HTTP response is
  **503**. The native result is `cancelled`, actual exit **1**, zero captured audio,
  complete capture and confirmed cleanup. This proves native cancellation after
  process launch; it does not claim that model inference had already started.
  Active request/background counts become zero, the default model client closes,
  the application process exits zero, and outer Windows Job cleanup is confirmed.
  Passive observers invoke the original owner/provider without delays or substitute
  inference. Report: `.tmp/bt4-piper-supervision-api/report.json`; workspace:
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-piper-supervision-api-012es85c`.
  The first successful live run against the prior wheel remains in `prior_runs`.
  The observed shutdown duration is not a general service-level guarantee.

Core 0.6.2 wheel SHA-256:
`dd2c140ab1a7632031de6e1ccaa4f1f909bb3bca7afe57817b1471a2e408ec4a`;
sdist: `60321e46a68ec26aa88cffc0ee8fba50f9023665a72293a520587858d6186ff3`.
SDK 0.7.0a1 and reference/starter 0.3.0a1 artifacts remain unchanged. No release,
commit, tag or publication occurs. The audit at `.tmp/bt4-piper-supervision-audit.json`
binds 952 core Python files, the profile registry, 30 SDK Python/schema files,
reference and starter modules to source/wheel/sdist bytes. It verifies source and
harness stability, live records, exact scope, sizes/labels/Ruff, dependency
transition, docs hygiene, sealed fixtures, the 18 original H2 headings and both
clean original main checkouts.

The baseline at `2026-09-13T23:19:25.916308Z` records 106 Ruff findings, 3,372 missing
labels among 4,663 test functions, 74 oversized runtime files and 236 functions
above 70 lines. Collection succeeds; release readiness remains false. All 15
changed Python files pass Ruff and stay below 400 lines; the runtime service is
398 lines. New functions meet the 70-line bound. Five previously missing labels
are repaired in the touched audio contract tests.

Remaining blockers or drift: host Piper's existing unknown-voice fallback can
disagree with the API's echoed requested voice ID, and its configured sample-rate
tag does not establish agreement with every model's metadata. Those asset/response
truth paths remain owned by Orket Core here. The SDK's separate in-process Piper
provider, generic speech-provider close protocols, arbitrary stuck threads,
detached remote effects and abrupt-host-death/workload recovery are outside this
native CLI acceptance. No fresh full suite, live Linux Piper, live STT model,
perceived-audio-quality acceptance or fresh llama.cpp inference is claimed. The
full BT-4 lifetime/outcome gates, earlier timestamp reversal/degraded CLI startup,
BT-5/C/D/E and CAP requirements remain active.

AC-01/02/03/04/05/06/08/09/10 pass for this scoped native ownership repair. AC-07
remains partial: native/availability outcomes now match their observations, while
the pre-existing voice identity/sample-rate metadata obligations above remain
explicit and are not widened by this change.

Exact worktree files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/architecture/CONTRACT_DELTA_PIPER_SUPERVISION_BT4_2026-09-13.md`
- `docs/architecture/event_taxonomy.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/API_RUNTIME_LIFECYCLE.md`
- `docs/specs/PIPER_RUNTIME_CONTRACT.md`
- `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`
- `orket/adapters/execution/owned_command_limits.py`
- `orket/adapters/execution/owned_command_process.py`
- `orket/adapters/execution/owned_command_worker.py`
- `orket/application/services/command_process_supervisor.py`
- `orket/application/services/extension_runtime_service.py`
- `orket/application/services/extension_runtime_support.py`
- `orket/capabilities/tts_piper.py`
- `orket/core/contracts/owned_command.py`
- `orket/extensions/workload_artifacts.py`
- `tests/contract/test_piper_command_contract.py`
- `tests/integration/test_extension_capability_lifetime.py`
- `tests/integration/test_extension_tts_availability.py`
- `tests/integration/test_owned_command_output_limits.py`
- `tests/integration/test_piper_process_lifetime.py`
- `tests/runtime/test_sdk_audio_capabilities.py`

### BT-4 host Piper voice identity and sample-rate truth: 2026-09-13

Status: scoped asset/response repair implemented and verified; full BT-4 and later gates remain active.

The preceding checkpoint's unknown-voice substitution and configured-rate
relabeling are repaired. The configured default must exist and leads the catalog;
an empty request selects it. Explicit IDs resolve case-insensitively to a canonical
ID. Unknown IDs and collisions between different model/config pairs fail before
native admission. Equivalent physical model/config paths do not create a false
collision. Relative asset paths use the owning workspace.

Adjacent model metadata must contain a positive integer `audio.sample_rate`.
That value labels the PCM clip. A configured rate is now an optional expectation;
disagreement cannot produce audio. The host passes the exact validated metadata
bytes through `--config` in a private workspace directory. Creation and cleanup
remain owned through cancellation, including cancellation before acquisition
returns and during removal. Cleanup errors remain errors. The API returns
canonical voice identity plus `piper_voice.v1` metadata with rate, provenance and
config SHA-256. The synchronous SDK AudioClip stays unchanged; host async callers
consume `PiperSynthesisResult(clip, voice, command)`. Contract and migration authority:
`docs/specs/PIPER_RUNTIME_CONTRACT.md` and
`docs/architecture/CONTRACT_DELTA_PIPER_VOICE_TRUTH_BT4_2026-09-13.md`.

Evidence:

- Before repair, all **15** controlled asset/API cases failed in 0.69 seconds:
  `.tmp/bt4-piper-voice-truth-before.xml/.log`. The initial corrected selection
  passes 15, the broader regression passes 81, and the expanded asset/snapshot/
  native lifetime selection passes 26. Contract controls use actual filesystem
  assets with controlled command results, including 24,000-Hz metadata and an
  original sidecar changed after selection. They are not real model inference.
  Snapshot lifetime integration controls hold actual writes/removal and preserve
  cancellation and cleanup failure. Native lifetime tests launch real processes.
- Frozen source passes **558**, with zero failures, errors or skips, in 82.99
  seconds. Report: `.tmp/bt4-piper-voice-truth-final-source-report.json`; JUnit:
  `.tmp/bt4-piper-voice-truth-final-source.xml`. Input hashes remain unchanged
  during execution; the canonical baseline is refreshed afterward.
- The same **558** cases pass in each installed Windows/Linux Python 3.11/3.12
  cell, with zero failures, errors or skips. Every cell passes `pip check`, checks
  **863** package origins under owned site-packages, and verifies copied harness
  hashes before and after execution. Report:
  `.tmp/bt4-piper-voice-truth-matrix-final/report.json`.

| Installed cell | Passed | Seconds (JUnit) |
|---|---:|---:|
| Windows Python 3.11 | 558 | 76.982 |
| Windows Python 3.12 | 558 | 93.404 |
| Linux Python 3.11 | 558 | 67.796 |
| Linux Python 3.12 | 558 | 68.979 |

- Live installed authenticated TCP/API proof uses Piper **1.8.0**, ONNX Runtime
  **1.30.0**, and existing read-only Lessac/Alan medium models on Windows Python
  3.11. An empty voice request returns canonical `en_US-lessac-medium` and
  **91,136** PCM bytes; case-variant explicit Alan returns canonical
  `en_GB-alan-medium` and **126,464** bytes. Both use **22,050 Hz**. A passive
  observer reads the actual `--config` before the original supervisor runs;
  supplied metadata digests, model argv, response rates/IDs, native receipts and
  captured/returned audio hashes agree. Unknown voice returns 400 without another
  native invocation. A third admitted request is cancelled only after independent
  psutil observation of the actual Piper command. It returns 503, its retained
  process identity stops, and native cleanup/capture are confirmed. Local context
  close takes **0.093967 seconds**; active requests/background tasks become zero,
  the default model client closes, all three private config directories are absent,
  and the application process exits zero with outer Windows Job cleanup confirmed.
  This proves launched-command cancellation, not that inference had already begun.
  Path **primary**, result **success**. Report:
  `.tmp/bt4-piper-voice-truth-api/report.json`; workspace:
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-piper-voice-truth-api-sfn32qdu`.

Core wheel SHA-256:
`208409495b4ae79d68e9d92472c3b2c9e0227157a22924c0f8deaf299af81479`;
sdist:
`1aba28a8a8fae66927ca74f38fa318a8f3339ec78032a128aaea2e6fee4a7ef3`.
Artifacts live under `.tmp/bt4-piper-voice-truth-final-dist/core/`. SDK 0.7.0a1,
reference/starter 0.3.0a1 and their earlier artifact identities are unchanged.
The first PowerShell build wrapper returned 1 although its log ended with successful
wheel/sdist construction. The retained build report records those initial hashes
and log; a subsequent direct frontend subprocess reports exit zero and binds the
final artifacts above. No runtime change or global install was made for that
observation. Build report: `.tmp/bt4-piper-voice-truth-build-report.json`.

Structural audit: `.tmp/bt4-piper-voice-truth-audit.json` binds the exact scope,
source/wheel/sdist parity, live files, initial failures, source/installed checks,
test labels, file/function limits, sealed fixtures, clean original checkouts and
the unchanged 18 top-level plan sections. Documentation hygiene, dependency
transition enforcement and changed-file Ruff pass. The canonical baseline remains
`collection_ok=true`, `release_ready=false`; wider red/noisy gates are not cleared
by this checkpoint. No commit, release, tag or push occurs.

Not verified: fresh full repository suite, live Linux Piper, live non-22,050-Hz
models, STT inference (unconfigured), audio playback or perceived quality, arbitrary
model-weight/schema agreement, hostile filesystem isolation, stuck-thread
termination, detached work or the separately shipped SDK in-process Piper backend.

Remaining blockers or drift: complete the BT-4 conformance audit against its four
numbered obligations and rerun its combined final gate envelope. This checkpoint
closes the demonstrated host voice-ID/rate contradictions; it does not make model
weights immutable or certify arbitrary assets. BT-5, C/D, E1/E2 and CAP gates remain
required. Return to those gate obligations before adding optional voice features.

The subsequent gate reentry inspection reproduces a separate required summary
defect without changing its implementation. Actual `score_benchmark_run.py`,
`report_benchmark_trends.py` and `render_benchmark_dashboard.py` subprocesses use
controlled input artifacts. Two measured runs of 25/75 ms correctly report 50 ms.
Two runs without durations report **0 ms** in scored task/overall output, trends
and the dashboard; one absent duration plus a 50-ms run reports **25 ms**. All
nine CLI processes exit zero, although the two incomplete-timing cases do not
establish those averages. Proof is live CLI aggregation with fixture inputs, not
model inference. Path **primary**, result **failure**, retained at
`.tmp/bt4-summary-timing-counterexample/report.json`, with script hashes and raw
inputs/results under `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-summary-timing-i2u49bbf`.
Repair unavailable/partial duration aggregation and its projections before
accepting the BT-4 summary audit. This counterexample does not reopen the proven
connector measurement or native process-lifetime repairs. Whole-plan reentry also
retains the 35 numbered obligations across BT-5, C/D, E1/E2 and CAP-1/2/3; the
installed scoped counts above are not evidence that those obligations are complete.

Exact worktree files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/architecture/CONTRACT_DELTA_PIPER_VOICE_TRUTH_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/PIPER_RUNTIME_CONTRACT.md`
- `orket/application/services/extension_runtime_service.py`
- `orket/application/services/extension_runtime_support.py`
- `orket/capabilities/piper_voice_assets.py`
- `orket/capabilities/tts_piper.py`
- `tests/contract/test_piper_command_contract.py`
- `tests/contract/test_piper_voice_truth.py`
- `tests/integration/test_piper_config_snapshot_lifetime.py`
- `tests/integration/test_piper_process_lifetime.py`
- `tests/runtime/test_sdk_audio_capabilities.py`

### BT-4 benchmark scored-report timing: 2026-09-13

Status: scored/trend/dashboard repair verified; raw summary/selector conformance and full BT-4 remain open.

The preceding command-level false averages are repaired. Scored-report schema
v2 provides nullable task/overall latency and `benchmark_latency.v1` coverage.
An average requires a nonempty population with a finite nonnegative numeric
duration for every run. Missing, malformed or partial observations cannot
contribute zeros or lower the population count. Explicit zero survives; finite
large values do not overflow an intermediate sum. Malformed task/run collections
fail rather than disappearing from coverage. The common helper reuses the core
duration normalizer. `reported` is input provenance, not independently measured
clock or workload equivalence proof.

Trend and dashboard readers share coverage validation. Contradictory current
metadata fails, partial/absent averages and deltas remain unavailable, and legacy
numbers are retained separately as unverified history. Existing cost, score and
determinism meanings are unchanged. The scored schema changes from v1 to v2;
JSON reruns retain the existing diff ledger. Authorities:
`docs/specs/BENCHMARK_LATENCY_SUMMARY.md` and
`docs/architecture/CONTRACT_DELTA_BENCHMARK_LATENCY_BT4_2026-09-13.md`.

Evidence:

- **21** new contract controls fail on the previous implementation/schema in
  `.tmp/bt4-summary-timing-before.xml/.log`. They cover missing/partial, invalid,
  reported-zero and large finite durations, legacy projection, metadata
  contradictions and malformed run records. The first repair passes 21; expanded
  coverage and existing scoring/reporting/dashboard regressions pass **35**.
- Frozen source passes **35** with zero failures, errors or skips in **18.69 s**:
  `.tmp/bt4-summary-timing-final-source-report.json` and
  `.tmp/bt4-summary-timing-final-source.xml`. Runtime/script/test
  hashes remain unchanged during execution; the baseline is refreshed afterward.
- Four foreign script/test harnesses pass the same **35** checks, each checking
  **469** core/SDK/reference package origins under installed site-packages, frozen
  copied inputs and `pip check`. These are copied repository scripts using the
  unchanged installed packages; no claim is made that benchmark scripts ship in
  the core wheel. Report: `.tmp/bt4-summary-timing-matrix-final/report.json`.

| Cell | Passed | Seconds (JUnit) |
|---|---:|---:|
| Windows Python 3.11 | 35 | 18.545 |
| Windows Python 3.12 | 35 | 18.713 |
| Linux Python 3.11 | 35 | 11.095 |
| Linux Python 3.12 | 35 | 11.518 |

- The public CLI tests invoke actual score/trend/dashboard processes from foreign
  working directories with controlled artifact inputs. They prove complete,
  absent, partial and zero-duration projection, then rerun the same paths and
  check the retained JSON diff ledger. This is end-to-end aggregation proof,
  not provider inference or capacity measurement.
- The original nine-command reproducer now passes: 25/75-ms inputs retain a
  50-ms average, while absent/partial inputs produce null task/overall/trend
  averages and `unavailable` dashboard cells. Path **primary**, result **success**.
  `.tmp/bt4-summary-timing-counterexample/report.json` retains the preceding failed
  run and raw files under `.../orket-bt4-summary-timing-i2u49bbf`; current files are
  under `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-summary-timing-4v_7v97n`.

Core wheel `208409495b4ae79d68e9d92472c3b2c9e0227157a22924c0f8deaf299af81479`,
SDK 0.7.0a1 and reference/starter 0.3.0a1 artifacts remain unchanged. No rebuild,
reinstall, global package change, release, tag, commit or push is needed for this
script-only repair. The audit `.tmp/bt4-summary-timing-audit.json` binds the 13-file
scope, original/repaired controls, frozen source/harnesses, unchanged runtime
artifacts, valid test-layer comments, size limits, original clean checkouts and
the 18 preserved top-level plan sections. Changed-file Ruff, documentation hygiene
and dependency transition checks pass. The refreshed baseline still reports
`collection_ok=true`, `release_ready=false`.

Not verified: fresh full repository or combined BT-4 gate suite, provider/capacity
measurements, raw harness timing/selection correctness, complete cost/score metric
truth, or E1/E2 quality/authority completion.

Remaining blockers or drift:

- Real raw-harness commands with an empty task bank or `--runs 0` both exit zero
  and report **0 ms** despite zero runs. The actual prototype selector admits a
  controlled candidate with no latency as **0 seconds** under a 0.01-second limit.
  These three counterexamples use controlled inputs and no model invocation;
  path **primary**, result **failure**. Evidence:
  `.tmp/bt4-summary-timing-remaining/report.json`, with raw files under
  `C:/Users/jonmc/AppData/Local/Temp/orket-bt4-summary-remaining-a9zvid87`.
  Repair their admitted missing-duration behavior before final summary acceptance;
  this checkpoint does not claim all benchmark producers have migrated.
- The public CLI test is correctly labeled `Layer: end-to-end`. The existing
  taxonomy regex recognizes only unit/contract/integration/live_truth and therefore
  reports that test as unlabeled. This is the already-owned E1 checker defect;
  the audit validates actual layer comments without claiming the legacy strict
  checker passes. The modified reporting tests now carry contract labels.
- BT-4's final combined gate envelope and the 35 later numbered obligations remain
  active. Preserve proven connector timing, process ownership, outcome and voice
  repairs while resolving the demonstrated remaining summary cases.

Exact worktree files touched by this checkpoint:

- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_BENCHMARK_LATENCY_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/BENCHMARK_LATENCY_SUMMARY.md`
- `scripts/benchmarks/benchmark_latency.py`
- `scripts/benchmarks/render_benchmark_dashboard.py`
- `scripts/benchmarks/report_benchmark_trends.py`
- `scripts/benchmarks/score_benchmark_run.py`
- `tests/application/test_benchmark_reporting_phase6.py`
- `tests/contract/test_benchmark_latency_truth.py`
- `tests/integration/test_benchmark_timing_pipeline.py`

### BT-4 benchmark command admission: 2026-09-13

The raw harness now requires an explicit runner template, positive run count and
nonempty validated task selection before child launch or report replacement.
The old implicit `orket run --task ...` shape is unsupported by the installed CLI.
Valid raw reports retain schema 1.1.3 and now retain a shared rerun diff ledger.
Prototype selector v2 refuses missing/invalid latency and invalid thresholds,
explains rejected candidates, and marks input metrics `reported_unverified`.
Explicit reported zero remains distinct from unavailable timing. Internal
quant/canary/context Python handoffs retain `sys.executable`; operator runner and
sidecar templates retain their chosen commands.

Authority: `docs/specs/BENCHMARK_LATENCY_SUMMARY.md` and
`docs/architecture/CONTRACT_DELTA_BENCHMARK_ADMISSION_BT4_2026-09-13.md`.

Proof: primary / success for the bounded native CLI and workflow paths, with
structural source/artifact checks. Source and four foreign installed-package
Windows/Linux Python 3.11/3.12 harnesses each pass 126 checks without skips.
Selection includes all 21 files in the Gitea quant-sweep coverage step plus
scoring/admission regressions: 28 files total. The final frozen campaign is
`.tmp/bt4-benchmark-admission-matrix-handoff/manifest.json` and `report.json`;
source evidence is `.tmp/bt4-benchmark-admission-handoff-source-report.json`
and its XML/log. Each installed cell checks 469 package origins, declared wheel
identities, pip dependencies and copied input hashes before/after execution.
These benchmark scripts are copied repository inputs, not wheel-owned scripts.
Core/SDK/reference/starter artifacts remain those in the preceding checkpoint;
no rebuild, reinstall, commit, tag, release or push occurred here.

The initial 20 admission controls failed before production changes. A subsequent
29-case run had two interpreter-selection failures; the corrected focused run
passed 45. The first wider Windows runs had 13 failures out of 126 while Linux
passed. `.tmp/bt4-benchmark-admission-interpreter.json` independently observes
bare `python` selecting the Windows base interpreter without psutil while the
explicit active interpreter has it. Internal handoffs and integration tests now
use the active interpreter. Initial failures remain under the `before`, `focused`
and `matrix-final` / `final-source` names. The subsequent `matrix-verified`
campaign passed; the handoff campaign repeats the final bytes after keeping the
oversized quant test at its original 925 lines. The raw harness shrank from 557
to 449 lines; its remaining size debt is explicit.

`.tmp/bt4-benchmark-admission-live/report.json` binds real copied CLI observations
to script hashes and retained files. Empty tasks and zero runs exit 2, launch no
runner and preserve previous report bytes. A valid native runner launches and
returns one measured duration. Missing selector latency produces no candidate,
with reason `latency_unavailable`. Original false-success evidence remains
unchanged in `.tmp/bt4-summary-timing-remaining/report.json` and its raw files.

`.tmp/bt4-benchmark-admission-workflow-live.json` records local execution of the
actual YAML dry-run and controlled native runner smoke commands on Linux, both
exit zero. Hosted Gitea execution and real model performance are not proven by
these commands. The workflow includes the affected helper/test paths and corrects
the stale runbook filter to its actual `docs/process/` location.

The checkpoint audit `.tmp/bt4-benchmark-admission-audit.json` binds exact scope,
artifact/source identity, original failure retention, test layers, sealed
fixtures, package-source nonmutation and the canonical baseline. Collection is
not release readiness. The roadmap remains on this lane and all 18 canonical
plan H2 headings remain unchanged.

Remaining blockers or drift:

- Generic runner supervision, quoted arbitrary runner commands, sidecar executable
  selection, cost/quality authenticity and real model/capacity acceptance are not
  established by these admission controls. Do not infer them from CLI exit zero.
- The prior E1 taxonomy regex defect remains: it does not recognize the correctly
  labeled end-to-end scoring CLI test. This checkpoint's modified tests have
  integration labels; no repository-wide taxonomy green is claimed.
- A fresh whole-repository suite, hosted CI, current combined BT-4 acceptance and
  the later BT-5/C/D/E/CAP gates remain open.

Exact worktree files touched by this checkpoint:

- `.gitea/workflows/quant-sweep-smoke.yml`
- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_BENCHMARK_ADMISSION_BT4_2026-09-13.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json`
- `docs/specs/BENCHMARK_LATENCY_SUMMARY.md`
- `scripts/benchmarks/determinism_cli.py`
- `scripts/benchmarks/prototype_model_selector.py`
- `scripts/benchmarks/run_determinism_harness.py`
- `scripts/context/run_context_sweep.py`
- `scripts/quant_sweep/canary.py`
- `scripts/quant_sweep/workflow.py`
- `tests/application/test_prototype_model_selector.py`
- `tests/application/test_quant_sweep_runner.py`
- `tests/application/test_run_context_sweep.py`
- `tests/integration/test_benchmark_command_admission.py`

### Goal reassessment and session boundary: 2026-09-13

Historical handoff boundary; the current resumed BT-4 acceptance is recorded in
the requirement-to-evidence reconciliation above.

The user requested reassessment and a handoff to another session. Implementation
expansion stops at the benchmark admission checkpoint. The whole-plan goal is
not complete; the goal service reports paused. Scoped BT-1/BT-2/BT-3 acceptance
does not establish BT-4 or later acceptance. There are 35 numbered obligations
after BT-4 across BT-5, C/D, E1/E2 and CAP-1/2/3. A percentage-complete claim or
firm whole-project ETA is unsupported. The earlier 5–10 working day estimate
was low confidence and must not be treated as a completion commitment.

The next session should first map BT-4's four numbered requirements and acceptance
paragraph to current artifacts in this canonical plan. For each, name proven
behavior, exact evidence/artifact identity and the remaining falsifiable
acceptance condition. Reuse the existing local/native/installed proofs. Older
gate helpers bind older wheels and must be updated before reuse; historical
passing counts cannot stand in for the current combined gate. Fix only a concrete
gap that prevents one of those acceptance conditions, then run the resulting
combined envelope and separate installed llama.cpp success/unsuccessful flows.
Do not keep adding adjacent features merely because another local checkpoint
can be made green. Preserve the named unsupported scopes and later gate ownership.

The requested session handoff is an ignored local transfer artifact at
`.tmp/ARCHITECTURAL_TRUTH_SESSION_HANDOFF.md`; this canonical plan and
`docs/ROADMAP.md` remain the execution authorities. Preserve the worktree and its
local evidence because the handoff is not a portable replacement for those files.

## BT-5 — Converge authority without replacing every executor

Status: scoped acceptance, 2026-09-14. The current five-requirement disposition
below supersedes earlier open-gate checkpoint notes without changing their proof
scopes. C/D, E1/E2, capability and whole-lane acceptance remain active.

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

### BT-5 opening authority and project-root audit: 2026-09-13

Status: project-root/ingress repair accepted within BT-5; the gate remains open.
The retained BT-4 closeout scope, audit and evidence hashes matched disk before
edits. The start-path matrix now names executor, authorization, effect, terminal,
replay and objective ceilings for cards, outward, governed agents, SDK/legacy,
quickstart, review and ODR. Inspection confirms implemented authenticated schedule
evaluation and webhook delivery routes; the old unadmitted statement was stale.
Fresh scoped conformance below establishes these routes and root selection;
inventory alone does not establish the remaining shared family guarantees.

| BT-5 requirement | Current disposition and next predicate |
|---|---|
| 1. Family authority inventory | Inspected owner chains and ceilings are in `CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`; validate against real composed family paths. |
| 2. Reconcile contradictions | Schedule/webhook wording corrected and actual API/queue/executor controls pass. Discovery and driver now select the caller project and pass it to the existing loader; real installed CLI startup is primary. Core declares the missing timezone-data dependency exposed by Windows schedule admission. |
| 3. Common immutable authority | Outward catalog/snapshot cutover, cards admission rollback, immutable run admission, turn recovery/dispatch ownership, Gitea closeout and approval-denial retain scoped acceptance. Explicit run/attempt/step revisions refuse stale and ABA writes. SDK/legacy/review terminal transactions and retained evidence now pass 1,854 identical source/four-installed cases, copied actual history and actual llama.cpp/Gitea proof in `bt5-remaining-family/repair/gate/audit.json`. Prior native revision/kernel proof and failed candidates remain preserved. This does not grant these families transactional admission, automatic recovery or remote fencing. |
| 4. Migrate consumers | Project-root, runtime/control-plane binding and outward current-input adoption retain scoped acceptance. Cards control-plane admission now rolls back its complete record set on failure/cancellation before epic dispatch, with source/installed and native CLI proof below. Other card/common-family convergence and historical recovery remain required. |
| 5. Family conformance | The retained 2,309-case gate exposed source child-observer teardown and Linux issue-dispatch partial closeout. The repaired 82-case selection passes source/four-installed, but the complete 2,319-case union fails one native timeout in each Linux cell; source and both Windows cells pass. Original failures remain preserved. Trace native clock/deadline inputs, then complete the family disposition. Counts do not establish live agent-model quality or whole-family convergence. |

Project-root delta: `docs/architecture/CONTRACT_DELTA_PROJECT_ROOTS_BT5_2026-09-13.md`.
Initial source inventory: `.tmp/bt5-project-authority/start.json`. The original
BT-4 artifacts and evidence remain retained. Current scoped audit:
`.tmp/bt5-project-authority/verified/audit.json`.

| Current envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 102 | 34.956 |
| Installed Windows Python 3.11 | 102 | 36.901 |
| Installed Windows Python 3.12 | 102 | 44.175 |
| Installed Linux Python 3.11 | 102 | 23.498 |
| Installed Linux Python 3.12 | 102 | 24.149 |

All five runs have zero failures, errors or skips and the same unique test
identities. Each installed cell checks 874 loaded package origins, wheel identity,
dependencies and 1,648 copied input hashes before/after. Source-only workload
authority governance passes 32 structural cases. The source-build registry case
passed in the first source envelope; source/wheel/sdist parity also covers all
953 core and 29 SDK Python files. Structural proof is not independent runtime
verification. Core 0.6.2 candidate wheel SHA-256:
`a157f117b94138b371d459d40a0f4d6de1805cc22b22046ccbf1a0f9ba52ede4`;
sdist: `afc28e5003b28e53d5da326d32d79e7feddc4210b8009a95abbc38282d69c9da`.
SDK/reference/starter artifacts retain their BT-4 identities.

Separate actual installed Windows Python 3.11 llama.cpp flows are **primary /
success**: success exits 0 with retained `done`, and deliberately required missing
source attribution exits 1 with retained `terminal_failure`. Both expose the
staged epic in the startup manifest, agree with retained final truth/publication,
release admission, confirm Windows Job cleanup and preserve actual package bytes
(generated Python caches excluded). Each retains two actual model receipts for
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`, build `b10809-5266f24da`, profile
`llama_cpp.qwen3.8.chatml.v1`; no provider switch occurred. The existing configured
runtime-verifier disablement in this attribution fixture limits the claim to
startup, retained card outcome and publication, not new objective-verifier proof.

Retained counterexamples include `before-complete.xml` (four real root/config
failures, explicit-root control passing) and `regression.xml` (missing `tzdata`
plus stale driver fixtures). `after.xml` retains a Windows error-string assertion
mistake. The first matrix/source observations remain in the parent proof root:
six corrected fixtures omitted their model directories; the installed selection
also incorrectly included a source-build-only case. Those failures are preserved,
not counted as runtime defects. The repaired matrix lives only under `verified/`.
The initial build environment lacked the build frontend; its failure is retained,
and the existing base build frontend produced the candidate without a new install.

Baseline `2026-09-14T02:36:45.523345Z` collects successfully and retains
`release_ready=false`. Scoped Ruff, transition dependency policy and docs hygiene
pass. Core reconciliation side effects, driver blocking reads and broader replay
remain pre-existing D/BT-5 debt; this root repair does not widen their mechanisms.
No fresh full-suite, hosted CI, OS-containment or whole-lane acceptance is claimed.

### BT-5 runtime-store binding and copied-history migration: 2026-09-13

Status: store-binding and migration slice accepted; BT-5 remains open.
Requirement 4 requires this cutover: a real paused card lost its pending approval
after CWD changed, and a second workspace selected an empty control-plane store.
Those counterexamples are retained in `.tmp/bt5-store-authority/before-owned.xml`.
Runtime composition now resolves the runtime DB and workspace once; engine, epic
and turn share the runtime database's sibling control-plane authority.

`docs/specs/RUNTIME_STORE_BINDING.md` and its contract delta govern explicit
offline migration. Original runtime/journal/artifact/native-lock paths stay fixed;
only the checked old control-plane store is copied. An identical durable binding
in both stores preserves each legacy session's original request reference without
granting approval or rewriting authorization. Incomplete binding refuses runtime
admission. Migration checks native owners, SQLite writers, source-session inventory,
configuration digests, pending targets and exclusive publication. It does not merge
mixed histories or fence arbitrary old executables; old owners must be stopped.

Current audit: `.tmp/bt5-store-authority/gate/audit.json`, **primary / success**,
33 repository-visible files in the declared slice. It separately names real local
integration/native-process proof, actual provider proof and structural checks.

| Envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 359 | 274.628 |
| Installed Windows Python 3.11 | 359 | 280.503 |
| Installed Windows Python 3.12 | 359 | 281.864 |
| Installed Linux Python 3.11 | 359 | 606.306 |
| Installed Linux Python 3.12 | 359 | 579.735 |

Every run has the same unique cases and no failures, errors or skips. Each
installed cell confirms 887 loaded package origins, installed artifact identity,
dependency consistency and 1,654 copied input hashes before/after. Package parity
covers 959 core and 29 SDK Python files. The current core 0.6.2 candidate wheel is
`.tmp/bt5-store-authority/dist/core-verified/orket-0.6.2-py3-none-any.whl`, SHA-256
`75077dad77534a07bd4e3079ce6ca7eb4d75247803901891585fd19e39ee59f0`;
sdist SHA-256 `4342199eed0efd6ce86a31f632a10aec1934074959cdf4268139f69304dc83c2`.
SDK/reference/starter retain the prior declared identities.

`installed-legacy-seed.json` retains approval and denial histories generated by
the previous installed core wheel, with real SQLite backups restored at their
original paths. `gate/installed-migration.json` proves the new installed migration
CLI and restarted application preserve those requests, old control-plane history
and backups. Approval writes the expected file and publishes success; denial
writes none and retains blocked child/failed parent truth. Repeated decisions and
migration are idempotent. Missing offline attestation exits 1; migration and retry
exit 0, with native cleanup confirmed. The model is a controlled fixture here.

Separate actual installed Windows Python 3.11 llama.cpp CLI success/failure flows
use relative `ORKET_DURABLE_ROOT=.orket/durable`, primary startup and retained
caller assets. Exit 0 agrees with `done`; deliberate missing required source
attribution exits 1 with `terminal_failure`. Both agree with final truth,
publication phase 4 and released admission; Windows Job cleanup is confirmed and
package bytes remain unchanged, excluding generated Python caches. Each retains
two actual model receipts for `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, server
`b10809-5266f24da`, profile `llama_cpp.qwen3.8.chatml.v1`. The existing disabled
runtime verifier in that attribution fixture does not establish new objective
verification or model-quality acceptance.

Retained observations include the original valid store-ownership counterexamples,
earlier fixture-directory/method mistakes, the 355-case initial broad regression,
and `integrity-before.xml` (one unrelated-session-copy failure and three passing
controls). The repaired focused envelope passes 25 cases. Initial engine unit
fixtures needed their composed-owner marker and updated builder signature.
The first built candidate predates import formatting and remains preserved; only
`core-verified` is accepted. A native helper's omitted supervisor argument failed
before migration; its log remains. The earlier source trial used a pre-final
binding shape and is historical, not current migration proof.

Scoped Ruff, docs hygiene, transition dependency policy, diff whitespace and new
file/function limits pass. Three initialization guards grow the existing engine
by three lines because all public approval reads/decisions must validate storage
before accessing retained authority; this is a correctness exception, not general
permission to grow that hotspot. Baseline collection succeeds and release remains
false. The audit preserves previous checkpoint evidence. Full-suite, hosted CI,
generic recovery, hostile containment and whole-lane acceptance are not established.
Native-lock relocation, mixed-history partition and arbitrary old-writer fencing
remain unadmitted; migration grants no takeover or redispatch of uncertain work.

Next within BT-5: migrate outward consumers to the existing workload catalog and
shared terminal authority, preserving their atomic event/effect transaction,
immutable bindings, quarantine and recovery fences. Then prove each family's
claimed shared guarantees through its real composed path. This accepted storage
cutover does not complete those common-authority or family-conformance predicates.

### BT-5 atomic outward admission prerequisite: 2026-09-13

Status: admission boundary accepted; common workload/terminal migration remains
open. This is required by BT-5.3/4: attaching shared authority to the old admission
would retain two namespace owners or a run committed without its initial event.
Six counterexamples fail against the previous installed core wheel, including
event/head insertion failure, orphan reentry, distinct-ID and same-ID contention,
and native process death before event publication. Their original failed results
remain in `.tmp/bt5-outward-authority/admission-installed-before.*`.

`OutwardRunService` now uses the existing approval/effect unit of work. Namespace
checks run under its writer lock; run/event/head commit together. Same-ID retries
retain the accepted submission. Old missing admission history refuses reentry
without backfill, and generation-zero quarantine remains. The run store declares
its side effects and supports the same borrowed connection. No schema or stored
authorization changes. Contract: `docs/specs/OUTWARD_RUN_ADMISSION.md`; delta:
`docs/architecture/CONTRACT_DELTA_OUTWARD_ADMISSION_BT5_2026-09-13.md`.

Current evidence: `.tmp/bt5-outward-authority/gate/`, **primary / success** for
live local authenticated ASGI, SQLite and native-process boundaries. Controlled
model regressions preserve approval, effect/model recovery and ledger behavior.
Source Windows 3.11 and installed Windows/Linux 3.11/3.12 each pass the same 122
cases, with no failures, errors or skips. Each installed cell checks 826 package
origins, artifact identity, dependencies and 1,657 copied input hashes before and
after. Source hashes remain unchanged during execution; package parity covers
959 core and 29 SDK Python files. Current core wheel SHA-256:
`d570f0cd5d17635647198d40027b4653641813123cdf95bf49c59efe7c0b0b54`;
sdist: `963710a2bd256e9626c5217e5622871651ba5d81b409a0bf11c20bcfcd2ac5c7`.
SDK/reference/starter identities remain unchanged. Structural checks and evidence
retention are recorded in `gate/audit.json`; baseline collection succeeds and
release readiness remains false. No fresh actual-model, full-suite, hosted-CI,
hostile-containment or whole-BT-5 acceptance is claimed.

The next cutover must replace the actual outward result owner. Inspected paths
still needing that change are `outward_model_publication.publish_terminal`,
`outward_effect_publication.publish_effect_projection`, approval denial/expiry,
`OutwardRunExecutionService.continue_after_denial`, and
`TrustHandoffAdmissionService._reject`. The latter two still publish terminal
state/events separately. Protocol `completed` can mean policy rejection, denial
or handoff rejection; mapping it directly to shared success would be false.
Use existing catalog resolution and control-plane repositories on the same
transaction, derive final truth from retained decision/effect evidence, and make
public result projection consume that truth. Preserve the existing outward
attempt/effect IDs, immutable bindings, quarantine and recovery fences. Provide
an explicit copied-history migration/refusal disposition before enabling reentry;
do not silently adopt old rows or dual-dispatch effects. Then execute the shared
adversarial conformance cases through each admitted family. This admission repair
does not substitute for those BT-5.3-5 obligations.

### BT-5 shared outward terminal counterexamples: 2026-09-13

The next migration has a retained installed baseline in
`.tmp/bt5-shared-outward-authority/before-retained.json`, **primary / failure** against
the required shared-run/final-truth predicate. Actual authenticated application
composition, SQLite and file effects ran under the accepted admission wheel
`d570f0cd5d17635647198d40027b4653641813123cdf95bf49c59efe7c0b0b54`.
Model output and time were controlled inputs; this is not actual-provider proof.
All application owners closed with no active background tasks.

| Observed path | Public protocol status | Terminal event | Shared run / attempt / final truth | Observed file effect |
|---|---|---|---|---|
| Approved write | `completed` | `run_completed`, outcome `success` | All absent; four shared effect-journal entries exist | Exactly the approved content |
| Operator denial | `completed` | `run_completed`, outcome `denied` | All absent | None |
| Approval expiry | `failed` | Absent | All absent | None |
| Out-of-workspace policy rejection | `completed` | `run_completed`, outcome `policy_rejected` | All absent | None, including the refused target |

Retained databases, model artifacts and hashes permit a copied-history migration
test against real pre-cutover execution. Do not replace these originals with new
fixtures or infer success from protocol status. The initial helper failed before
application construction because environment bootstrap must precede the event
loop; that traceback remains in `before.log`. The corrected native invocation
uses the existing bootstrap entrypoint. Its first report (`before.json` and
`before-native.log`) included transient SQLite sidecar hashes and is not retained
evidence authority. `before-retained.json` and `before-retained.log` repeat all four
cases after explicitly closing the inspection connection; all 21 retained file
hashes verify after native process exit. Both initial helper failures remain.
This demonstrated gap requires one evidence-derived terminal publisher, shared
catalog/run identity and an explicit history cutover across the paths identified
above. It does not justify accepting another family-specific terminal authority.

### BT-5 shared outward authority implementation and migration: 2026-09-13

Current implementation authority is `docs/specs/OUTWARD_RUN_AUTHORITY.md`, with
delta `docs/architecture/CONTRACT_DELTA_OUTWARD_AUTHORITY_BT5_2026-09-13.md`.
This is progress toward BT-5 requirements 3–5, not cutover acceptance. The original
admission wheel and its scoped audit remain historical evidence. Shared-authority
builds are retained under `.tmp/bt5-shared-outward-authority/dist/`; their current
identity is in `gate/build.json`. Installed acceptance has not yet been collected.

Outward admission resolves the existing catalog and retains common run/attempt
snapshots in the existing writer transaction. Model/effect/approval paths require
that frozen authority. One terminal publisher validates retained decision,
rejection, model or effect evidence and publishes shared final truth, terminal
step, run/attempt closure, native projection and event together. Success requires
the entire admitted tool sequence's approved bindings and observed receipts.
Denial and expiry close in the decision transaction. Their former separate
terminal writes are removed; protocol status is explicitly distinct from result.

The source migration command adopts one reviewed current-state digest after an
explicit stopped-owner attestation. It validates retained ledger history and
bindings, names current-input adoption as the snapshot source, and appends shared
authority without rewriting old native records or claiming original instruction
authenticity. Existing generation/attempt/effect IDs and recovery fences remain.
The same terminal publisher handles adopted terminal history with a distinct
adoption event, preserving an old missing expiry terminal event as historical fact.

Observed evidence, **primary / success** within the declared scopes:

- `migration-terminal-probe.json` under `.tmp/bt5-shared-outward-authority/`:
  source native CLI migration and identical repeat on copied old installed
  success, denied, expired and policy-rejected histories. Native run/proposal,
  model/effect and effect-journal rows stay unchanged; second invocations preserve
  database bytes. All 21 original retained files still match their hashes.
- `old-active-histories.json`: the old admission wheel actually composed seven
  isolated application histories: pending approval; ready/claimed/observed model
  admission; claimed/observed/dispatching effects. Controlled model/clock inputs,
  explicit interruption points and completed application cleanup are recorded.
- `migration-active-probe.json`: source native CLI migration and repeat on copies
  of those seven histories preserve native ownership/fences and retain unfinished
  shared authority. All 29 original files remain unchanged. These invocations do
  not dispatch workload continuation.
- `migration-source-first.xml/.log`: 19 source integration cases pass, covering
  fresh terminal authority, projection contradictions, append-failure rollback
  and retry, reviewed-state/owner/quarantine refusal, migration rollback and
  idempotence. Terminal effect publication retries reuse the observed receipt;
  the non-idempotent command writes one line.
- `migration-continuation.json`: seven fresh old-wheel histories pass source
  composed continuation/recovery. Pending approvals execute one effect; ready
  models run once; observed model results are reused; claimed model/effect work
  requires explicit recovery and retains the prior fence; observed effects
  publish with zero connector calls; uncertain dispatch stays unfinished and
  refuses both ordinary retry and pre-intent recovery. Before-execution database
  and artifact snapshots are retained separately with 29 verified file hashes.
  These are controlled model/clock cases, not actual llama.cpp calls.
- `outward-source-wide.xml/.json/.log`: 405 passed and four failures in a legacy
  fixture that invoked new admission before attempting to seed the removed v1
  model table. Python source hashes remained unchanged during the run. The fixture
  now seeds historical native admission without current schema initialization
  and explicitly adopts shared authority after model migration.
  `legacy-model-migration-repaired.xml/.log` passes all four cases, preserving
  copied rollback/retry, old model evidence and fenced continuation. This is a
  targeted repair follow-up, not a second fresh all-green 409-case run.
- `migration-kill-probe.json`: native process death at uncommitted admission and
  uncommitted final-truth event publication on copied old success/expiry histories
  rolls back both boundaries. All four cases preserve old rows/ledger and succeed
  on explicit retry. `migration-process-owned-snapshot.xml/.log` passes 15 source
  migration/process/ledger cases. Initial `migration-process-source.xml/.log` and
  `migration-kill-probe.log` failed on the first post-crash read; the instrumented
  `migration-kill-probe-v2.log` records SQLite 3.50.4 `SQLITE_IOERR_TRUNCATE` (1546).
  Migration now borrows the existing writer connection for ledger validation,
  replacing its second read connection. The corrected native cases pass; this
  does not diagnose every Windows SQLite or filesystem I/O failure.
- `outward-source-owned-snapshot.xml/.json/.log`: the fresh broad source envelope
  passes 410 cases with no failures, errors or skips, with Python hashes unchanged
  during execution. It includes the repaired legacy fixtures and native migration
  process test. A subsequent import-order-only lint repair is included in the
  reviewed candidate build; the initial build remains retained separately.

Retained failures are not replaced: `authority-resume.xml/.log` records 83 passed
and one stale inspection fixture that fabricated completion without shared truth;
the fixture now inspects a valid unfinished run. `terminal-integrity-before.xml`
records five missed shared-record contradictions and two passing rollback cases.
`terminal-integrity-repaired.xml` records a test fixture that created an invalid
common attempt rather than the intended valid-but-conflicting state; the corrected
case is included in the 19 passing tests. The first migration probe failed because
its inspector named the retired approval table; its log remains retained and the
corrected probe reads `outward_approval_proposals_v2`.

At this implementation checkpoint, combined current-artifact acceptance, installed
migration/continuation and fresh actual llama.cpp flows remained open. The following
acceptance supersedes those proof gaps; shared family conformance remains open. Unknown or conflicting historical evidence remains refused;
this is not a claim that every legacy terminal shape has been accepted. No
provider, release, whole-family or full-plan acceptance follows from these counts.

### BT-5 shared outward cutover acceptance: 2026-09-14

Status: shared outward admission, terminal projection and explicit history cutover
accepted within BT-5. The five BT-5 obligations and whole lane remain open.
Current scoped audit: `.tmp/bt5-shared-outward-authority/gate-package-roots/audit.json`.
Observed path/result: **primary / success**. The audit separates live local
API/SQLite/process proof, actual provider proof, and structural inspection.

| Envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 410 | 244.167 |
| Installed Windows Python 3.11 | 410 | 244.165 |
| Installed Windows Python 3.12 | 410 | 290.925 |
| Installed Linux Python 3.11 | 410 | 286.594 |
| Installed Linux Python 3.12 | 410 | 284.805 |

All five envelopes contain the same 410 unique test identities and no failures,
errors or skips. Each installed cell verifies 834 loaded package origins, wheel
identities, dependencies and 1,663 copied inputs before/after. Source hashes remained
unchanged during execution. Package parity covers 966 core and 29 SDK Python
files. Current core wheel is `dist/reviewed-core/orket-0.6.2-py3-none-any.whl` under
the shared-outward proof root, SHA-256
`7afb066132c3a3007855c5594c65643ceed94182e0d189e0a17e3f7149b88468`;
sdist SHA-256 `819909fc7b40417890210ab9352a3f45fcc246331e4ad5378d2c2c160283445d`.
SDK/reference/starter retain their prior identities.

The first installed campaign (`gate/report.json`) retains 21 structural failures
and 389 passes per cell: governance looked for source beside copied tests. The
corrected checker reads the actual imported package and copied repository tooling;
no source package shadows the wheel. Immediate layers identify structural
contracts. After the broad run, a five-line formatting reduction leaves its AST
identical and shrinks the existing hotspot to 892 lines. A fresh 32-case structural
run covers that exact file and updated matrix documentation. The audit records
these post-proof changes separately; runtime and test semantics are unchanged.

Installed migration uses fresh executions of the retained old admission wheel in
an isolated pip target with the selected interpreter's existing dependencies.
This proves the old-core/new-core boundary, not every historical dependency stack.
Each Windows/Linux Python 3.11/3.12 cell proves:

- Four terminal and seven unfinished native-CLI migrations preserve reviewed
  inputs, five native tables and repeated-invocation database bytes.
- Seven composed application continuations preserve model/effect claims and
  fences. Ready model work executes once; observed work is reused. Claimed work
  requires explicit recovery. Observed effects publish without invocation.
  Uncertain dispatch remains unfinished and refuses redispatch. Repeated decisions
  cause no extra model/connector calls.
- Exact file content, application cleanup and retained before-continuation copies
  are verified. Terminal originals remain unchanged.

Current reports are `migration-win-py311.json`, `migration-win-py312.json`,
`migration-retained-linux-py311.json` and `migration-retained-linux-py312.json` in
the gate directory. The first Linux commands passed, but every reported `/tmp`
file was missing during later verification. Their reports, logs and
`retention-linux-initial.json` remain failed retained-evidence observations.
Fresh Linux campaigns use persistent `/home/jon/.cache/` proof roots. Separate
native-host checks now verify retained files on both platforms. This storage
location repair does not diagnose why the earlier files vanished. The original
Windows/source counterexamples and migration snapshots also verify.

Separate actual installed Windows Python 3.11 llama.cpp proof is retained in
`live-provider.json`: approved write publishes shared success and the exact file;
denial, expiry and policy rejection publish shared blocked truth without their
refused effect. Actual model output is checked against the approval binding.
The authenticated composed API, database, terminal event and public result agree,
and every application closes. Model:
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`; no provider switch occurred. This is
composed API proof, not new native TCP-server, general objective-quality or
hostile-containment acceptance.

Scoped Ruff, docs hygiene, transition dependency policy, immediate test layers,
file/function limits and whitespace checks pass. Baseline collection succeeds;
release readiness remains false. Unknown legacy terminal shapes and arbitrary
old-writer fencing remain unadmitted. Native interruption evidence retains the
Windows SQLite error and the shared-connection repair's stated ceiling. No full
repository suite, hosted CI, release or whole-family acceptance is inferred.

Next required gate: parameterize shared guarantees across outward, cards and
governed agents through real composed entrypoints. Reconcile immutable-input drift,
repeated/concurrent decisions, interrupted observed-result publication, unsupported
takeover and final-result agreement against each family's contract and proof.
SDK/legacy, quickstart, review and ODR retain distinct executors and explicit
ceilings; validate their named authority chains without granting unclaimed
guarantees. Repair demonstrated conformance gaps. This accepted outward slice
does not substitute for BT-5.4/5 or the later C/D/E/CAP obligations.

### BT-5 common terminal transaction counterexample and source repair: 2026-09-14

Status: scoped terminal/API cancellation repair accepted below; common conformance
and whole-family acceptance remain open.
`.tmp/bt5-family-conformance/start.json` binds the preceding accepted outward
audit. Its 47 scoped file hashes, 143 retained proof hashes and 23 checks matched
disk before the family work began.

`tests/integration/test_family_terminal_authority.py` applies the same terminal
write failure to real outward API, canonical card `run_card` and bounded
governed-agent paths. Models/workload output are controlled; the agent executes
real child processes and every family uses SQLite. With complete input fixtures,
five controls passed and one agent case failed: a saved final-truth `success`
survived a failed attempt-completion write while run and attempt stayed unfinished.
`terminal-complete-inputs-before.xml/.log` and 11 copied fixture files in
`terminal-before-evidence/` preserve that observation. The earlier
`terminal-before.xml/.log` used an incomplete negative agent fixture; its two
failures did not exercise the terminal boundary and are not runtime counterexamples.

The bounded loop now uses the existing shared control-plane transaction factory,
compares retained run/attempt state under its writer, refuses existing conflicting
truth, and retains guard checks through publication. Truth, attempt and run commit
together. Runtime composition binds one configured store; inspection/operator
typing consumes the core record contract. Contract delta:
`docs/architecture/CONTRACT_DELTA_AGENT_TERMINAL_TRANSACTION_BT5_2026-09-14.md`.

The initial source repair passes 15 cases. The broader
`agent-regression-source.xml/.json/.log` contains **178 passed, 17 skipped**, no
failures/errors, and unchanged repository-visible hashes during execution. All
nine common cases pass: complete, interrupted attempt write and interrupted run
write for each family. The skipped tests are explicitly gated provider proof:
six llama.cpp, nine Ollama and two native process-recovery cases. This regression
does not establish those live paths. The intermediate collection error after
removing a still-imported local protocol is retained in `terminal-transaction.*`;
inspection/operator consumers now import the existing core repository contract.

The later source llama.cpp run, `live-source-current-extension.*`, passed all
eight CLI/API/effect-restart/native-process-recovery cases in 130.738 seconds.
All 41 retained evidence hashes match. Its current extension selection is the
preserved 0.3.0a1 worktree; the first `live-source.*` run selected the original
0.2 extension and correctly refused the missing model-receipt-v2 feature before
inference. That failed observation remains retained. The eight passing cases
precede the following expanded terminal changes and are not current-candidate
provider acceptance.

`test_governed_agent_terminal_controls.py` then demonstrated four additional
failures with two passing controls: effect denial and operator cancellation both
retained truth after an interrupted attempt/run write. `terminal-controls-before.*`
and the copied databases in `terminal-controls-before-evidence/` preserve them.
Denial now includes pending-status CAS, exact operator evidence, reservation
release, checkpoint rejection and terminal records in the existing control-plane
transaction. Cancellation retains its intent and child observation separately,
then compares retained run/attempt and publishes terminal records together.
The pending-gate implementation is extracted from `async_repositories.py`, which
shrinks below 400 lines. Every consumer imports the single implementation; core
owns its shared port and the transaction supplies a borrowed connection.

Retry testing additionally found that a cancelled invocation was skipped after
failed terminal publication, promoting unknown child state to confirmed shutdown.
`terminal-retry-uncertainty-corrected-before.*` retains two failures/seven controls.
The earlier nine-failure uncertainty run compared incorrect literal enum tokens
and is not the runtime counterexample. Retry now reuses the cancelled invocation
and observes teardown again. Bounded-loop final truth uses the shared validator;
operator stop requires actual retained actions bound to its accepted decision.

The expanded focused source run, `terminal-controls-current.*`, passes **23 cases**
in 19.29 seconds: family success interruptions, denial/cancellation rollback and
retry, unknown-child uncertainty, API pause/stop and real native child teardown.
Observed path/result: **primary / success**, live local SQLite/process behavior
with controlled model/workload output. Expanded current-source and installed
candidate regression, actual llama.cpp, native terminal-write interruption and
older split terminal history disposition remain required. This is continued
BT-5 conformance work, not whole-family or whole-gate acceptance.

The expanded candidate core wheel is
`b14e762db8f82e95b3179b603a5a96a971240387964b3bdd4df7cdd3df3e3815`
(sdist `e593967c08510601fe81817e0c93c2859245f3e1afd56db64f6deee7a95933d9`).
The 97-file source selection passes **642 tests**, no failures/errors/skips, with
unchanged repository-visible hashes. Installed Windows 3.11, Linux 3.11 and Linux
3.12 each pass the same 642 cases. Windows 3.12 reached 506 completed cases and
stalled in `test_api_owned_supervisor_dispatches_real_child_and_exposes_composed_inspection`
while `TestClient` awaited API shutdown. Two read-only native stack observations
in `win312-stall-stack*.txt` establish that boundary; no child subprocess remained
under the observed pytest process. The original run remains unaccepted. One
isolated run and 30 instrumented repetitions pass; they do not explain or replace
the stalled full-envelope observation. The full diagnostic also passed, without
reproducing the stall. An attached bounded coroutine observation of the original
process then found teardown awaiting a still-running supervisor with cancellation
count zero. An additional cancellation released it. The captured state and
`gate/win312-stalled/intervention.json` preserve that intervention; the original
run remains degraded, instrumented evidence even if its test report is green.

The defect is the use of `task.cancelling()` as proof of API-owned cancellation.
An internal timeout can consume its own cancellation and continue after teardown
skips its request. The original transient cancellation source was not captured;
the deterministic regression establishes that mechanism independently. The three
background-close/request-close/request-disconnect controls in
`test_api_shutdown_timeout_race.py` failed before repair. The container now tracks
its own cancellation requests separately, shared across disconnect and teardown.
A first unconditional-cancel repair passed the new races but broke three existing
cleanup-outcome controls; those failures remain in `shutdown-timeout-race-current.*`.
The final owner-request repair passes all **22 focused cases** in 24.79 seconds,
including real composed resources and preserved cleanup failures, recorded in
`shutdown-owned-cancellation-current.*`. This source change requires a fresh
artifact campaign before installed acceptance; the b14e7 wheel predates it.

Fresh installed Windows 3.11 llama.cpp proof passes **eight cases** in 137.3
seconds, with 870 checked package origins, no source-package alias, and 42 checked
retained files. The extension comes from the bound 0.3.0a1 sdist in the foreign
harness. All four installed environments separately pass **four native process
death/retry cases each**: denial and unobserved cancellation, after attempt or run
write but before commit. No terminal truth survives death; denial stays pending;
retry closes from the retained database without fixture reinitialization, refused
write or fabricated child-stop confirmation. Their 96 retained file hashes match.
These are native SQLite/application paths; the distinct actual-provider envelope
does not claim provider execution at each injected terminal fault.

Evidence lives in `.tmp/bt5-family-conformance/gate/`: `source-report.json`, copied
per-cell reports, `family-live-win-py311.json`, `native-terminal-*.json`, and native
retention reports. Dependency-transition and documentation hygiene checks pass;
the regenerated baseline collects successfully and remains `release_ready=false`.
That candidate remained unaccepted because of the Windows 3.12 intervention.
Its three passing installed envelopes do not establish a complete four-cell gate.

Fresh scoped acceptance uses `.tmp/bt5-family-conformance/gate-after-shutdown/`
and core wheel SHA-256
`7558b9c757c5762d33f688fc748b2269c62251ddfdb38b4e708843c3fd794539`
(sdist `c15d5ac49a43f4d09e52712ae9667d6f45830be1dd5f95e47c50551f450c26a9`).
All source and installed runs pass the same **664 unique cases**, without
failures, errors, skips or intervention. Source inputs remained unchanged during
execution; each installed environment checks 882 package origins, dependencies,
exact wheel identities and unchanged copied inputs.

| Current envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 664 | 387.112 |
| Installed Windows Python 3.11 | 664 | 387.497 |
| Installed Windows Python 3.12 | 664 | 446.950 |
| Installed Linux Python 3.11 | 664 | 521.661 |
| Installed Linux Python 3.12 | 664 | 519.542 |

The source regression initially contained a test-only sleep polling loop rejected
by Ruff. After the frozen source run completed, it became one scheduler yield and
an explicit admission-closed assertion. The following yield and all behavioral
assertions remain. The three final cases pass separately in source and all four
installed environments, using new supplemental files while preserving the frozen
harness. `timeout-test-delta.json` binds the before/after test hashes; the audit
permits only that specifically verified test delta and subsequent documentation.
No runtime byte changed after the build.

Fresh installed llama.cpp proof passes **eight cases** in 148.370 seconds, with
870 checked package origins and 42 retained evidence files. Each installed
environment passes **four native process-death/retry cases**, with 96 total
retained files checked against their hashes. No refused write or invented
child-stop confirmation occurs in these controls. The scoped audit verifies
original counterexamples, source/wheel parity, common identities, final test
follow-ups, native/provider evidence, Ruff, labels, sizes and docs hygiene.
Observed proof: **live local application/SQLite/process and actual llama.cpp**;
path/result: **primary / success**. Structural checks are recorded separately.
The baseline collects successfully and remains `release_ready=false`; hosted
Gitea, a fresh full repository suite and whole-BT-5 acceptance are not established.

Remaining blockers or drift: the installed Windows 3.11 `agent inspect` and
`agent replay` commands both exit zero against a copy of the original split
terminal database. Inspection exposes shared success alongside executing run
and attempt records; replay reports its decision comparison, not terminal
consistency. `.tmp/bt5-family-conformance/historical-inspection/report.json`
retains this observation and verifies the original evidence remained unchanged.
Resolve the historical inspection/reentry disposition, common immutable
admission and remaining family adversarial cases before accepting BT-5.

### BT-5 retained terminal consistency candidate: 2026-09-14

Status: source repair verified in focused scopes; fresh installed acceptance is
pending. This addresses BT-5.3–5 and the split-history observation above. It does
not close common immutable admission or the remaining family conformance gate.

The shared SQLite final-truth repository now accepts one immutable truth per run,
with identical retry under a writer transaction. Multiple historical truths and
indexed/payload identity disagreements refuse reads. One pure domain validator
checks run/reference/truth and current terminal-attempt agreement. Outward
projection, cards epic closeout and governed-agent inspection/reentry consume it;
stronger family evidence checks remain. Agent inspection/replay read the join in
one retained-history transaction, including unreferenced truth. Conflicting
inspection returns HTTP 409 or nonzero CLI status; replay cannot report matched.
Agent parent run/attempt admission now commits together. No historical outcome is
rewritten and no conflicting history authorizes redispatch.

Durable authority is `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`; the contract
delta is `docs/architecture/CONTRACT_DELTA_TERMINAL_HISTORY_BT5_2026-09-14.md`.
The previous terminal/API audit and its retained proof remain unchanged. This
candidate uses `.tmp/bt5-family-history/` and preserves original damaged stores.

| Required predicate | Observed evidence | Remaining acceptance |
|---|---|---|
| Reject split terminal joins before projection/reentry | Corrected pre-repair source: 17 failed, five passed; first repair: 69 passed | Fresh built-wheel parity and installed public CLI on preserved history |
| One immutable truth across independent writers | Previous installed 7558b9c7 wheel accepts both native writers; repaired source rejects the second identity | Final installed Windows/Linux Python 3.11/3.12 conformance |
| Atomic parent admission and truthful authenticated inspection | Previous installed wheel leaves parent after attempt-write failure and returns HTTP 200 for inconsistent history; expanded source: 58 passed | Final installed envelope and retained negative evidence audit |
| Shared terminal contradiction refusal without mutation | Outward/cards/agent and related publication source envelope: 55 passed | Final candidate rerun after test composition cleanup; installed family parity |

The source selections overlap and must not be added into a unique-case total.
The earliest test version incorrectly required two particular replay diagnostic
strings; those two failures were assertions, not runtime defects. Corrected
counterexamples and the installed three-failure report retain exact causes.
Source proof uses real SQLite, composed ASGI applications and native children,
with controlled inference. It is not actual-provider or native TCP acceptance.
Observed source path/result: **primary / success** in those scopes. Before
controls record **primary / failure**. Package acceptance was absent at this
source-only opening; the subsequent built-candidate disposition follows.

The first built candidate, wheel `12a376ab37b6fb964f19fb5f426f75305a23e3894f4d922ff9b940c96b9803c7`
and sdist `88476265e508ac3ee57e1c2f3d0017645acdd1f414b22d6dbc2aec5580d22e73`,
is **unaccepted**. Source passes 1,041 cases in 567.49 seconds; installed Windows
3.11/3.12 pass the same count in 568.204/640.475 seconds. Linux 3.11/3.12 each
retain seven failures and 1,034 passes. Seven assertions used uppercase `ISSUE-1`
for an artifact directory the writer consistently normalizes to `issue-1`.
A persistent Linux rerun confirms those seven failures and nine controls with
the lowercase files present. The test paths are corrected without changing
runtime paths. The first follow-up failed during fixture setup because its
parent directory was absent; those 16 setup errors are not runtime defects.

All four installed CLI cells refuse the original split history twice each for
inspection and replay, preserving database bytes/logical state. However, the
installed byte-limit counterexample reports matched despite more than 64 MiB of
final-truth values. Separate actual llama.cpp proof has seven passes and one
failure: wake renewal encounters `database is locked` and its queue never reaches
the required terminal state. A deterministic source transaction/renewal control
reproduces a lock cycle only when reader and renewal share a repository; the
independent reader control passes. The first control version omitted a required
authority field and is retained as a fixture mistake, not runtime evidence.

The subsequent repair keeps the existing replay byte limit in the shared truth
reader and validates wake claims through a separate read-only connection without
the renewal lock. It preserves the same committed owner/fence/lease predicate.
The 70-case focused source envelope passes; the canonical plan's final installed
candidate still needs proof. Initial reports and artifacts live under `gate/`;
the fresh corrected campaign is `gate-bounded/`. Neither test-count totals nor
the successful CLI observations override the failed provider/resource predicates.

Current corrected candidate: wheel
`d77cd7e3006a28faf6955cf1f6ff7325a9fd4e9ad11f2295ed2f55bbbfc0c170`,
sdist `18084ecbba59104656f58c877af4739a1bb1d193d48678843ae7e19b1903752a`.
It is installed in all four owned environments. The source remained unchanged
during the 1,044-case run. All installed cells check 886 package origins, package
identities, dependencies and unchanged copied inputs.

| Corrected envelope | Passed | Failed | JUnit seconds |
|---|---:|---:|---:|
| Source Windows Python 3.11 | 1044 | 0 | 570.627 |
| Installed Windows Python 3.11 | 1044 | 0 | 572.660 |
| Installed Windows Python 3.12 | 1044 | 0 | 642.422 |
| Installed Linux Python 3.11 | 1043 | 1 | 821.478 |
| Installed Linux Python 3.12 | 1044 | 0 | 810.509 |

No errors or skips occur in these envelopes. Actual installed Windows 3.11
llama.cpp proof passes all eight cases in 139.11 seconds, including the previously
failed wake flow; its 42 retained files verify. Every platform passes four native
terminal interruption/retry cases and four repeated historical CLI refusals,
with 96 and 44 retained files respectively. Read-only native retention checks
also verify 435 files from the rejected candidate and its follow-ups. Transition
dependency checks and baseline collection pass; `release_ready` remains false.

**The corrected candidate remains unaccepted.** Linux 3.11's
`test_effect_approval_pauses_then_resumes_with_verified_receipts` returns
`recovery_pending` with `E_SDK_AGENT_FRAME_READ_TIMEOUT` instead of completed.
The retained JUnit duration is 5.761 seconds. This fixture explicitly configures a
two-second child handshake, eight-second request deadline and seven-second lease;
the production invoker defaults to ten seconds for handshake. The report does
not identify which frame timed out. The initial `/tmp` database is no longer
available during subsequent inspection, so no unobserved child timing or resource
cause is inferred. The other passing cells do not explain or override this failure.
Recent progress-log tails omitted its earlier `F`; the completed report is the
authority. Raw logs, JUnit, manifests and the failed gate disposition are retained
under `gate-bounded/`.

A persistent, instrumented installed Linux 3.11 repeat preserves the original
test bytes, assertions, handshake and request limits. It passes in 2.06 seconds;
the two ready frames take 0.411 and 0.393 seconds, and both exchanges begin with
more than six seconds of request time remaining. `frame-probe-installed.json`,
`frame-probe.xml` and `frame-probe-retention.json` retain frame-stage observations,
checked origins and fixture hashes. This repeat does not reproduce or explain the
original failure and does not replace the failed matrix cell.

### BT-5 startup control and remaining composed-family defects: 2026-09-14

Status: historical-consistency candidate remains unaccepted. A controlled native
2.25-second pause before the resumed child's ready frame reproduces the original
positive fixture's two-second timeout on the unchanged installed d77cd7e3 wheel.
The first child returns; the second times out and is reaped. This establishes a
fixture boundary, not the cause of the earlier uninstrumented Linux failure.

The positive effect/resume fixture now uses the production handshake default.
Its eight-second request deadline and seven-second lease are unchanged. Three
explicit cases cover normal completion, completion after the controlled startup
pause, and recovery-pending/no-final-truth after the same pause with a two-second
handshake limit. All retain child teardown and verified effect receipts. Focused
source proof passes all three. No production source or package artifact changed
for this test correction.

The fresh `gate-startup/` campaign retains the same 157-file selection with 1,046
unique cases. Source and installed Linux 3.11 pass all 1,046. Windows 3.11/3.12
each have 1,045 passes and one fixture Git failure (602.067/671.784 seconds).
Linux 3.11 takes 573.752 seconds. Linux 3.12 has 1,045 passes and one unreleased
lease failure in 566.734 seconds. All cells have zero errors/skips and verify
886 installed package origins, exact wheel identities and copied input hashes.

The Windows failures are proof-runner errors. Unquoted backslashes in
`PYTEST_ADDOPTS` produced a malformed, overlong fixture path. A copy at the same
path length reproduces Git's `Filename too long`; the same input at a short path
stages successfully. Original fixtures and the pre-fix runner remain retained.
The runner now quotes its option, and both Windows cells pass all seven unchanged
admission tests with a direct absolute fixture argument (0.60/0.75 seconds).
These follow-ups do not rewrite the failed wide matrix. The malformed source
fixture directory was moved intact under `gate-startup/source-fixtures-retained/`.

Linux 3.12's original turn fixture is retained. It records start time
`2026-09-14T09:32:48.524400+00:00` and end time
`2026-09-14T09:32:47.101688+00:00`; its ordered log also reverses time between
tool-call start and result. Lease release raises `ControlPlaneLeaseError` because
publication time decreased, after successful run/attempt/truth were committed.
The host-clock reversal's cause remains unknown. The observable runtime defect
is non-atomic terminal/resource closeout, not a reason to weaken lease ordering.
`gate-startup/linux-turn-failure.json` binds the retained fixture and log. Initial
SQLite read-only inspection created auxiliary sidecars; subsequent immutable
inspection requires an empty WAL and verifies retained file hashes unchanged.

Separate installed admission controls exercise outward, cards and governed-agent
paths with the same attempt-write interruption. The corrected six-case probe has
five passes and one runtime failure: cards retains a parent without its attempt.
Outward and governed-agent admission roll back. Two earlier probe versions used
success-only helpers or expected HTTP 500 instead of the actual 409; those are
fixture errors, not additional runtime defects. `.tmp/bt5-family-admission/before.json`
binds all three observations and 448 retained files.

The actual llama.cpp and native terminal/history proof from `gate-bounded/` was
rechecked against the unchanged wheel; it was not rerun or broadened. Baseline
collection remains successful with `release_ready=false`. Current failed campaign
audit: `.tmp/bt5-family-history/gate-startup/audit.json`.

### BT-5 turn terminal and preflight transaction proof: 2026-09-14

The demonstrated turn closeout repair passes its scoped gate. This does not accept
the earlier failed wide campaigns or close historical/common-family convergence.
Finalization reads run/attempt/truth under the existing transaction factory and
commits terminal records with lease/resource release. Preflight owns the same
transaction boundary, including its recovery decision and admission when needed.
Both paths validate retained terminal consistency instead of adding missing truth
references. No timestamp clamp, relaxed lease ordering or redispatch is introduced.

Ordinary and protocol composed turns reproduce clock reversal, run-write and
lease-release interruption: the original source has six failures and four
controls. The test toolbox performs a real file write, and the retained observed
effect survives closeout rollback. Moving six preflight tests from in-memory
repositories to SQLite exposed two further failures: abandoned attempt records
carried failed/interrupted-only fields and could not be read back. Preflight now
retains a schema-valid abandoned attempt; classification and attempt reference
remain on its recovery decision. Existing invalid history is not rewritten.
The expanded earlier-wheel probe has ten failures and four passes, including the
preflight round-trip failure and interrupted preflight writes. The probe did not
independently capture package origins; its failure is supporting evidence alongside
the source counterexample and previously checked installed environment.

The first repair envelope has 42 passes and the two preflight schema failures;
the subsequent source envelopes pass 44 and 48 cases. An expanded 71-case source
run passes, while all four copied harnesses stop with two collection errors
because an imported test helper was omitted. These are harness errors. The
corrected harness includes the missing input, retains the initial reports, and
uses the same built artifacts. Ordinary turn tests supply explicit ordered clock
inputs; separate reversal cases retain the original observed timestamps. Runtime
clock behavior is unchanged and its broader ownership remains C/D work.

Current artifacts: core wheel
`46e8f6f6f0b92e10f8cab87d433747108834cf2b41673aedeefdc9cecc01a33f`,
sdist `9a2a2c32393e122ff71469466ffebf9bac467599e4ef4014903bfaa173f3301c`.
All four owned environments now contain that wheel. SDK/reference/starter
identities remain unchanged. Current audit:
`.tmp/bt5-turn-terminal/gate-complete/audit.json`.

| Scoped envelope | Passed | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 99 | 109.836 |
| Installed Windows Python 3.11 | 99 | 111.930 |
| Installed Windows Python 3.12 | 99 | 124.275 |
| Installed Linux Python 3.11 | 99 | 113.182 |
| Installed Linux Python 3.12 | 99 | 113.528 |

The same 99 unique cases run with zero failures/errors/skips; installed cells
verify 876 package origins, artifact identities, dependencies and unchanged
copied inputs. Twenty cases cover terminal write/clock boundaries, preflight
rollback and conflicting historical closeout. These are scoped counts, not a
fresh full-repository or 1,046-case matrix claim for the new wheel.

Separate installed Windows 3.11 card CLI flows use actual llama.cpp. Success
exits 0 with `done`; required-attribution failure exits 1 with `terminal_failure`.
Both match retained epic/publication truth and confirm process cleanup. Each
contains two completed governed tool turns with released latest leases. The
native audit rechecks all 274 retained files. The unsuccessful flow is an epic
attribution failure, not a claim of live-model preflight rejection. The first
helper launch failed before execution because its copied script dependencies
were not on the import path; the unchanged helper was then run from its foreign
harness. A native audit initially matched lease holders to attempt IDs instead
of the canonical holder; correcting the verifier required no runtime change.

Observed scoped path/result: **primary / success**, with live native subprocess,
SQLite, filesystem and actual-provider proof plus structural checks. Ruff, docs
hygiene, whitespace and dependency transition checks pass; baseline collection
is successful and `release_ready` remains false. AC-01/02/03/05–10 pass for the
changed boundary. AC-04 remains partial: the pre-existing runtime `utc_now`
inputs in turn service/closeout still depend on wall time; explicit clock
authority is retained under C/D. The change does not widen that dependency.

Next: repair the demonstrated cards parent-admission gap from
`.tmp/bt5-family-admission/before.json`, then complete immutable authorization and
remaining family predicates. Turn reconciliation/recovery closeout is not covered
by the new transaction claim. The full historical/family gate, C/D/E/CAP and
whole-lane acceptance remain open; no release, commit, tag or push.

### BT-5 cards admission transaction and current family regression proof: 2026-09-14

Status: cards control-plane admission rollback accepted within this scope; whole
BT-5 remains open. Before edits, all 14 scope hashes and 60 proof hashes from the
turn-terminal audit matched disk. The original installed admission counterexample
and all 448 external evidence files remain unchanged. Current source reproduces
its six-case result: five pass, and interrupted cards admission retains an orphan
parent. Outward and governed-agent admission roll back.

`CardsEpicControlPlaneService` now uses its existing transaction factory for the
complete control-plane admission: policy/configuration snapshots, parent/attempt,
start step/effect, checkpoint and acceptance. Failure or cancellation rolls back
these records before epic dispatch. The same scoped service construction serves
admission and closeout. The service is 333 lines; new functions are at most 50.
The independent runtime/publication journals retain their existing preparation
and recovery semantics. No cross-store transaction, timestamp clamp, historical
backfill or new workload identity is introduced.

Twenty-two integration controls exercise the three composed families and all
eight cards write boundaries. Eight exception cases and eight actual task
cancellations prove no partial admission records or dispatched epic work. A
healthy cards control requires all eight record groups, guarding the observer
against a vacuous empty-table check. The first expansion had 14 passes and eight
fixture failures: the runtime correctly translated cancellation after cleanup,
while the test expected the original exception message. The corrected control
cancels the live task at the held write boundary and checks durable rollback.

Current audit: `.tmp/bt5-cards-admission/gate/audit.json`. Core wheel SHA-256:
`6c48ea05fde235632e7eea99f830ab433d7b92fa6e1f9a8234e0cccb45273c70`;
sdist: `6b5ff04c8556dfd4e548e0275a7c6140c4d5ec2c1dc2b1e58ed8874f29e6d5c8`.
SDK/reference/starter identities remain unchanged. All owned environments now
contain this candidate. The 160-input selection includes the earlier full family
envelope, turn transaction controls and the new admission controls.

| Current envelope | Passed | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 1,088 | 589.473 |
| Installed Windows Python 3.11 | 1,088 | 592.153 |
| Installed Windows Python 3.12 | 1,088 | 657.996 |
| Installed Linux Python 3.11 | 1,088 | 525.920 |
| Installed Linux Python 3.12 | 1,088 | 520.682 |

All five runs execute the same unique cases with zero failures/errors/skips.
Installed cells verify 886 package origins, wheel identity, dependency health and
unchanged copied inputs. The audit retains 389 admission-fixture files per cell.
This is current regression proof, not a fresh full-repository or hosted-CI result,
and it does not erase earlier failed campaigns.

Separate actual installed Windows 3.11 llama.cpp CLI flows pass: success exits 0
with `done`; required-attribution failure exits 1 with `terminal_failure`. Both
match retained epic/publication truth and confirm native cleanup. Independent
inspection verifies complete cards admission joins and digests, plus all four
governed tool turns' released latest leases. All 274 native files match their
recorded hashes. The unsuccessful case is an attribution failure, not a claim
of provider failure. An initial helper launch used the wrong copy-source cwd
and stopped before execution; correcting its absolute source path required no
runtime change. An initial dependency-check command used the wrong option name;
the supported `--out` command subsequently passed.

The next immutable-authority predicate is contradicted by a separate installed
six-case control: identical writes pass for all three families, but the shared
repository accepts a changed namespace after healthy composed admission in all
three. `.tmp/bt5-cards-admission/authority-mutation.json` binds actual package
origin, wheel identity, six retained run records and 215 evidence files. This is
a shared-persistence invariant gap, not evidence of a public API authorization
bypass. It stays outside the passing admission-rollback claim.

Observed repair path/result: **primary / success**, with live composed SQLite,
filesystem, cancellation, native process and actual-provider proof. Ruff, docs
hygiene, whitespace and dependency transition checks pass. Baseline collection
is successful with `release_ready=false`. AC-01/02/03/05–10 pass for the changed
boundary. AC-04 remains partial: the existing cards `_utc_now` inputs still use
wall time; C/D owns explicit clocks and identity. This dependency was not widened.

Next: enforce immutable run authority through the common persistence contract and
family consumers, then finish remaining historical/recovery and family predicates.
The turn reconciliation path, broader native family acceptance, C/D/E/CAP and
whole-lane acceptance remain open. No release, commit, tag or push was performed.

### BT-5 shared run immutability acceptance: 2026-09-14

Status: scoped source, installed and native acceptance passes. The cards
admission audit and its retained evidence were verified before this change. The
six-case installed namespace control above supplies the counterexample.

The common core comparison treats every run field except lifecycle state,
current-attempt reference and final-truth reference as immutable admission.
SQLite compares and writes under one writer transaction; borrowed transaction
ownership remains with its caller. Identical retries and ordinary state updates
remain supported. Governed-agent reentry reuses this comparison, retaining the
original creation time. Kernel admission now refuses historical missing namespace
instead of silently choosing a replacement. This is not new state CAS or effect
fencing authority.

Focused source proof passes 36 family/repository/history cases plus 24 field,
transaction, native two-process race and historical kernel-refusal cases. Current
candidate proof root: `.tmp/bt5-run-immutability/`. The full family campaign passes
source and all four installed environments, exact artifact/origin checks,
separate actual llama.cpp CLI flows and retained-history controls below.
Broader shared authority, recovery, C/D/E/CAP and whole-lane acceptance remain open.

Before installation, two additional lock-wait controls exposed a mismatch between
the serialized incoming payload and the caller's later mutable object. The writer
now captures and validates one input before its first await and compares/persists
that same snapshot. The first build and prepared harnesses remain retained and
unaccepted. Current candidate artifacts/proof use `dist-snapshot/` and
`gate-snapshot/` under that root. Invalid contract-version inputs are schema errors;
the first updated fixture incorrectly expected the repository conflict type in
two cases, while 30 controls passed. Those expected error types are now explicit.

The first 1,120-case snapshot campaign remains failed and retained: source and
both Windows cells have 1,117 passes/three failures; Linux cells have 1,116
passes/four failures each. The three shared failures precede cancellation: its
fixture called a second parent-admission helper over an already admitted run,
changing immutable metadata. It now prepares the pending invocation with the
existing parent and updates only legitimate state/step fields. Source cancellation
and immutability follow-up passes all 41 cases.

The additional Linux failures are original recorded clock reversals: card
completion's log goes from `10:49:50.474189` to `10:49:48.621403` UTC, and skill
contract closeout from `10:58:33.776962` to `10:58:32.257866` UTC. Both retain active
leases and nonterminal records without final truth after atomic closeout rollback.
`gate-snapshot/clock-refusals.json` binds 35 unchanged fixture files; the host-clock
cause remains unknown. These two ordinary positive test modules now use the
existing explicit ordered clock fixture, while separate reversal controls remain.
The three corrected fixture modules pass all 38 source cases. Runtime time handling
and the candidate wheel are unchanged. The accepted complete campaign is
`gate-verified/`; `gate-snapshot/audit.json` remains failed.

The final audit is **primary / success**, with all 12 checks passing. This is
live local application/SQLite/native-process proof, separate from structural
source/package parity and governance checks. The three-family mutation cases
exercise the shared persistence port after healthy composed completion; they
do not establish a public API bypass. Separate real kernel ASGI/application/SQLite
controls pass healthy repeated admission and missing/changed historical scope
refusal (three cases); they do not claim TCP server coverage.

| Accepted envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 1,120 | 629.989 |
| Installed Windows Python 3.11 | 1,120 | 604.974 |
| Installed Windows Python 3.12 | 1,120 | 672.328 |
| Installed Linux Python 3.11 | 1,120 | 588.276 |
| Installed Linux Python 3.12 | 1,120 | 585.510 |

All five envelopes have zero failures, errors or skips and identical unique case
identities. The 162-file selection includes 32 immutable-admission controls. Each
installed cell verifies 887 loaded origins, artifact identities, dependencies and
copied input hashes. Core wheel SHA-256:
`dfbce5b750383aa742ce97dd936a71747311ca67e60bdfcfa5a67d2099e9b009`;
sdist: `d4700ddbb3b0ed0ec4f1796141147e13d338d1087c03965edf55fa0833f780ff`.
SDK/reference/starter artifacts retain their prior identities.

Actual installed Windows Python 3.11 llama.cpp flows retain success (exit 0,
`done`, session `0c3f1e1b`) and required-attribution failure (exit 1,
`terminal_failure`, session `ed158c8d`). Both use
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`, retain two governed turns with released
leases, and confirm child cleanup. The audit revalidates 274 native files, six
kernel API evidence files and the original 215-file namespace counterexample.
Each installed cell retains 239 files for its 32 admission cases. Earlier cards
admission fixtures and all 35 original clock-refusal files remain unchanged.
Baseline collection passes while `release_ready=false`. Scoped Ruff, dependency
transition, docs hygiene, size/layer and whitespace checks pass. These results
close the immutable-admission predicate, not general state CAS, recovery fencing,
all turn reconciliation, hosted CI, a fresh full repository suite or whole BT-5.

### BT-5 turn recovery transaction acceptance: 2026-09-14

Status: scoped source, installed and native acceptance passes. The immutable
admission audit's 16 scope hashes, 107 proof hashes and 241 source fixture hashes
were verified before this change. New proof root: `.tmp/bt5-turn-recovery-atomic/`.

The next BT-5.3/BT-5.5 predicate was contradicted by real service/checkpoint/SQLite
execution: exceptions and task cancellation after each of six recovery writes
fail rollback. Read-only inspection records ten partial authority states and two
completed closures whose callers receive the final write's error/cancellation.
`before-observations.json` binds those retained states without changing files.
`before-checked.xml` retains 12 failures and one healthy
closure control. The initial `before.xml` also preserves a fixture error that
compared the uncertainty enum with an incorrect string; it is not a runtime defect.

Service and workflow recovery now use one existing control-plane transaction,
compare captured run/attempt and applicable checkpoint inputs under its writer,
and retain a completed reconciliation refusal until commit. Other exceptions or
cancellation roll back the staged recovery; previously observed files/effects
remain. The retained recovery algorithms and family policy still own the outcome.
The first repaired envelope passes 43 cases; the expanded source envelope passes
66, including orphan-artifact rollback and committed refusal, stale run/attempt
refusal, pre-effect decision interruption and real executor resume regressions.
These overlapping counts are not cumulative. Contract delta:
`docs/architecture/CONTRACT_DELTA_TURN_RECOVERY_BT5_2026-09-14.md`.

The accepted full family envelope uses `gate/` and rebuilt artifacts under `dist/`.
Audit `gate/audit.json` is **primary / success** with all 13 checks passing.

| Accepted envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 1,150 | 608.952 |
| Installed Windows Python 3.11 | 1,150 | 613.380 |
| Installed Windows Python 3.12 | 1,150 | 678.382 |
| Installed Linux Python 3.11 | 1,150 | 542.692 |
| Installed Linux Python 3.12 | 1,150 | 538.939 |

All five runs have identical unique case identities and zero failures, errors or
skips. The 163-file selection includes 30 new recovery controls; each installed
cell verifies 888 loaded package origins, artifact/dependency identity and copied
input hashes. Core wheel SHA-256:
`6109e4a21c9ca7b07029a1a7b635e19dcffb25baaef00aa45504d8ff7f432829`;
sdist: `0ab65d8461e9b7a6d9570bf405122f82a0e66bd0bd7419210f88832081f50117`.
SDK/reference/starter identities remain unchanged.

Separate actual installed Windows Python 3.11 llama.cpp CLI regression passes:
session `3c9016a2` exits 0 with `done`; required-attribution refusal `ee32b4a8`
exits 1 with `terminal_failure`. Both use
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`, retain two completed governed turns with
released leases, and confirm child cleanup. The audit verifies all 274 native
files. These are ordinary CLI regression flows; changed recovery is exercised
through the real service/workflow/SQLite/physical-file controls with controlled
model/tool boundaries, not a claim of provider-backed recovery or TCP API proof.

Each installed cell retains 120 files for its 30 recovery cases; the prior
immutable-admission fixture files and sealed proof hashes remain unchanged.
The first retention collector missed two pytest-shortened directory names on
each inspected host. Its failed observation is retained in
`retention-prefix-failure.json`; correcting only the collector required no test
rerun or runtime change. Structural Ruff, docs hygiene, size/layer, whitespace and
dependency transition checks pass. Baseline collection passes with
`release_ready=false`. AC-04 remains partial for pre-existing runtime clocks under
D; this repair introduces no clock or schema authority.
All owned proof command handles were reaped. The final readable-process inventory
finds no remaining executables in the four owned proof environments, excluding
the inspector and its launching ancestry. Inaccessible unrelated process state
remains outside that inventory's claim.

This transaction does not provide a fence across physical tool/model work,
universal mutable-state CAS, historical repair, fresh whole-repository/hosted-CI
proof or whole BT-5/C/D/E/CAP acceptance.

### BT-5 governed turn ownership acceptance: 2026-09-14

Status: scoped source, installed and native acceptance passes. Proof
root: `.tmp/bt5-turn-ownership/`. This directly addresses BT-5.3/5. The existing
start snapshot binds the previous recovery audit and pre-edit source inventory.

The retained `before.xml` has four failed competing reentry/resume controls and
one passing completed-reentry control. After native ownership wiring, `locked.xml`
passes all 12 turn/epic lock cases. `uncertain-before.xml` then records eight failed
post-write exception/cancellation controls. Cancellation permits another dispatch;
exceptions instead close with false pre-effect classification. A further direct
preflight control fails in `preflight-before.xml`, confirming that abandonment
also needs the uncertainty guard.

Canonical governed turn execution now reuses the extracted native epic lock
mechanism before model work. The application commits a dispatch marker before
toolbox invocation, publishes its observed replacement and effect journal in one
transaction, and preserves unknown outcomes through reentry/recovery/closeout.
Source `dispatch.xml` passes 80 focused cases; `native.xml` passes 35 additional
and overlapping ownership/transaction controls including actual child-process
death and confirmed wait/cleanup. The final envelope includes the repaired
preflight refusal. These overlapping focused counts are not cumulative.
Contract delta: `docs/architecture/CONTRACT_DELTA_TURN_OWNERSHIP_BT5_2026-09-14.md`.

Audit `gate/audit.json` is **primary / success** with all 15 scoped checks passing.
It binds current source/package inputs, earlier retained evidence and the new
physical counterexamples. Read-only `counterexample-observations.json` confirms
eight duplicate physical writes and four false pre-effect failure classifications.

| Accepted envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 1,186 | 610.920 |
| Installed Windows Python 3.11 | 1,186 | 624.423 |
| Installed Windows Python 3.12 | 1,186 | 693.318 |
| Installed Linux Python 3.11 | 1,186 | 604.543 |
| Installed Linux Python 3.12 | 1,186 | 596.904 |

All five runs have the same unique case identities and zero failures, errors or
skips. The selection has 165 test files plus clock and native-worker helpers;
each installed cell verifies 892 package origins, wheel/dependency identity and
copied inputs before/after execution. Core wheel SHA-256:
`6eae5187641f915b67ee7fd9eb5fd081b18b8acc66e8f8048ca64273e5cba8e6`;
sdist: `03f708115ece7335484b5ca5a49a956cce2836b4f1f8de76611b05297e5c6024`.
SDK/reference/starter identities remain unchanged.

Actual installed Windows Python 3.11 llama.cpp CLI session `dbe2ff58` exits 0
with `done`; attribution-refusal session `8e2a276d` exits 1 with
`terminal_failure`. Both use `orcarouter_qwen3.8-27b-uncensored-q4_k_l`, retain
two completed governed turns, observed step/effect joins and released leases,
and confirm native child cleanup. All 278 native files are hash-verified.
These ordinary CLI regressions do not claim provider-backed interruption.

Retention binds 277 files per installed cell for the 29 new turn controls plus
one existing outward native admission control whose shortened fixture prefix
overlaps. The initial collector's 29-directory expectation failed on that extra
fixture; `retention-selection-observation.json` preserves the correction. No
runtime/test input changed. Prior recovery evidence and installed fixture hashes
remain intact. All owned command handles were reaped; the final readable-process
inventory finds no remaining executables in the four proof environments, excluding
the inspector and its ancestry. Inaccessible unrelated processes remain outside
that claim.

Ruff, test-layer/size checks, docs hygiene and whitespace pass; baseline collection
passes with `release_ready=false`. AC-01/02/03/05/06/07/08/09/10 pass within this
scope. AC-04 remains partial for pre-existing turn clocks under D. These fixtures
and flows do not establish clock ordering across all model/tool observations.

The next ordinary-admission predicate is now contradicted, not merely untested:
`.tmp/test_bt5_turn_admission_interruption.py` exercises seven actual admission
writes with error/cancellation. `admission-before.xml` retains 14 failures and one
healthy control; `admission-observations.json` binds their retained partial stores.
Repair that admission transaction before broader family convergence acceptance.

These are live local SQLite/filesystem/process paths with controlled model/tool
boundaries, not provider-backed interruption proof. Historical unmarked attempt
migration, ordinary admission atomicity, general mutable-state CAS, other family
conformance, full repository/hosted CI, C/D/E/CAP and whole-lane acceptance remain
open. Native lock release does not establish remote-effect termination.

### BT-5 ordinary turn admission candidate: 2026-09-14

Status: admission controls pass; combined installed acceptance remains open. New proof
root: `.tmp/bt5-turn-admission/`. Before edits, the prior ownership audit's 26
scope hashes, 65 proof hashes and 531 source fixture hashes matched disk. Its
`admission-before.xml` retains 14 failures and one healthy control; the associated
physical SQLite states remain unchanged.

The service now borrows explicit repository ports from one existing transaction
for admission snapshots, run/attempt, reservation, lease/resource, promotion and
executing-state writes. Resume calls its existing algorithm inside that writer,
and the shared transaction context preserves commit-before-refusal for completed
reconciliation. No new schema, executor or transaction across other stores is
introduced. Contract delta:
`docs/architecture/CONTRACT_DELTA_TURN_ADMISSION_BT5_2026-09-14.md`.

`focused.xml` passes 69 cases. `expanded.xml` passes 90 overlapping cases,
including every one of 11 admission write positions under error/cancellation,
native process death before/after commit, identical reentry, recovery rollback
and committed refusal, and dispatch ownership/terminal regressions. The native
controls use the existing command supervisor and confirm process cleanup. Proof
is live local SQLite/process behavior with controlled interruption; it does not
establish provider-backed admission interruption or whole-family convergence.

The first 1,211-case source/four-installed campaign retains one failure per cell:
the old promotion test patched an unborrowed publication instance and expected
pre-transaction compensation. Its replacement interrupts after real promotion
on the borrowed service and requires complete restoration of the pre-existing
SQLite state. `promotion.xml` passes all 31 admission/preflight cases. Fresh
`gate-verified` harnesses retain the same core artifact; no package rebuild or
provider rerun was needed for that test-only correction.

| Combined candidate envelope | Passing | Failing | JUnit seconds |
|---|---:|---:|---:|
| Source Windows Python 3.11 | 1,211 | 0 | 638.395 |
| Installed Windows Python 3.11 | 1,211 | 0 | 630.539 |
| Installed Windows Python 3.12 | 1,211 | 0 | 701.740 |
| Installed Linux Python 3.11 | 1,211 | 0 | 541.268 |
| Installed Linux Python 3.12 | 1,210 | 1 | 539.637 |

All runs contain the same 1,211 unique cases, with no errors or skips. The 170
selected inputs comprise 167 test files and three helpers. Each installed cell
checks 892 package origins, artifact/dependency identities and unchanged copied
inputs. Source hashes remain unchanged during execution. Core wheel SHA-256:
`834ae2c12e903411726fc21df4e2ff8865699e8255abc367f8c53dc0a4e2e3ab`;
sdist: `8f33da8c08a4fa2c43dc9486cc2186dac72db3d9c2e3bc026e15bd6c7adc28ab`.
SDK/reference/starter artifacts remain unchanged. The original failed campaign
and its fixtures remain retained; neither campaign was overwritten.

The Linux 3.12 failure is
`test_gitea_state_worker_publishes_non_sandbox_lease_history_on_success`.
Its original database retains completed run/attempt records and active leases
after release rejects a non-monotonic timestamp. `gitea-failure-retention.json`
binds the untouched database and its copy. `gitea-clock.xml` then records 15 passing
and one failing instrumented repetition. `gitea-clock-observation.json` records
UTC moving backward **2.721249 seconds** while `perf_counter_ns` advances
**0.865363017 seconds** in that reproduction. The original failure has no such
clock samples, so its exact cause remains unproven. Runtime clocks, validators
and the Gitea test remain unchanged; this is an unresolved clock-input and
terminal/resource consistency predicate, not accepted runtime behavior.

Separate actual installed Windows 3.11 llama.cpp sessions `f5a45df7` and
`80e32a1c` use `orcarouter_qwen3.8-27b-uncensored-q4_k_l`. Success exits 0 with
`done`; attribution refusal exits 1 with `terminal_failure`. Each retains two
completed governed turns, four observed tool-step/effect joins, released turn
leases and confirmed child cleanup. All 278 retained native files match their
hashes. These flows do not establish provider-backed admission interruption.

An actual old-wheel interruption followed by current-wheel copied-history resume
reproduces the historical migration defect in `historical-unmarked.json`: one
physical write precedes cancellation with no step/effect record, then resume
dispatches again without another model call and reports success. The original
16-file history and 20-file resumed copy remain retained. This controlled-model,
real filesystem/SQLite counterexample is not provider or migration acceptance.

Admission rollback/reentry has live local SQLite/process proof; the complete
combined candidate remains **primary / failure**. The baseline collects with
`release_ready=false`. Earlier ownership proof and source/installed fixtures
remain preserved. No whole-family, whole-plan, hosted CI or release acceptance
is claimed. AC-04 remains partial under D; the new clock observation makes its
remaining input problem concrete.

Ruff, immediate test-layer/size checks, docs hygiene and whitespace pass. Each
installed cell retains 33 admission fixture files; prior ownership and first
campaign fixture hashes still match. All owned command handles are reaped, and
readable-process inventories find no remaining executables in the four proof
environments after excluding the inspector and its ancestry. The first audit
collector encountered Linux pytest's `current` symlink from Windows; its traceback
is retained in `gate-verified/audit-before-symlink.log`. Collection now hashes the
16 explicit clock fixture directories and leaves that alias unchanged.
`gate-verified/audit.json` retains the failed combined disposition; exact current
scope is listed in `gate-verified/current-turn-files.json`.

Historical partial/unmarked attempt migration, general mutable-state CAS,
remaining family conformance and later C/D/E/CAP gates remain active.

### Gitea terminal/resource transaction candidate: 2026-09-14

Status: repaired with scoped proof; combined family acceptance remains open.
This addresses the retained ordinary-admission candidate's Gitea terminal/lease
predicate under BT-5 obligations 3 and 5. Preserve the original failed Linux
database, measured UTC reversal and 17 controlled pre-repair failures.

The worker settles owned renewal before one selected remote closeout. Only work
failure selects the failure state; remote-closeout/local-publication failures do
not authorize another remote final mutation. The execution publisher borrows the
existing SQLite transaction for final step/effect, required recovery decision,
attempt/run/truth and lease/resource closure. Retained identities and the common
terminal join govern reuse. Execution/lease UTC inputs use `RuntimeInputService`
by default; controlled fixtures supply ordered clocks. No host-clock repair or
timestamp clamping is claimed. Initial claim atomicity, general remote fencing,
restart recovery and historical repair remain outside this closeout boundary.
Contract: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`; delta:
`docs/architecture/CONTRACT_DELTA_GITEA_TERMINAL_BT5_2026-09-14.md`.

The first immutable candidate's 42 new Gitea controls pass in source and each
installed environment. Its combined results are:

| Envelope | Passed | Failed | JUnit seconds |
|---|---:|---:|---:|
| Source Windows Python 3.11 | 1,253 | 0 | 640.033 |
| Installed Windows Python 3.11 | 1,253 | 0 | 652.747 |
| Installed Windows Python 3.12 | 1,252 | 1 | 723.547 |
| Installed Linux Python 3.11 | 1,252 | 1 | 587.382 |
| Installed Linux Python 3.12 | 1,253 | 0 | 582.917 |

All five have the same 1,253 unique cases and no errors/skips. Each installed
cell checks 893 loaded package origins, wheel identities, dependencies and copied
inputs. Forty-two Gitea fixture directories/92 files per installed cell are
retained. Core wheel SHA-256:
`7346f7141f48740df42243eeec4d87320c5291e78be7cd5c0c284216b991e734`;
sdist: `7e09a2b6a023da52803e27e457ebf4fdb2c22d350c61781020d590c73db8f62e`.
This wheel predates the empty-expiry correction below; it is not the final source
candidate. SDK/reference/starter artifacts retain their previous identities.

Separate actual installed llama.cpp sessions `45675939` and `3d25738f` agree
with their expected successful/unsuccessful CLI exit and retained authority,
with confirmed child cleanup. Three actual installed Gitea 1.25.4 cases pass:
success, failed physical work and local-publication interruption after remote
closeout. The corrected live collector verifies 762 loaded origins, 977 installed
core Python files and all three owned container removals. Its initial failed
collection is preserved: it counted a pytest directory alias as a fourth server
and checked source-tree package bytes. The fresh corrected collection uses the
interpreter's installed package directory and excludes that alias.

The initial audit `.tmp/bt5-gitea-terminal/gate/audit.json` remains **primary /
failure**, with two false predicates: four installed cells passing, and the
empty-expiry contract. The latter was a new regression: empty `LeaseExpiredError`
lost its existing `E_LEASE_EXPIRED` classification. Its retained probe reports
`failed` instead of `blocked`. Restoring that explicit exception branch now
passes **61 focused source cases**, including native process interruption, and
**four actual source Gitea cases** with same-path teardown. The added real Gitea
case verifies the restored blocked outcome and resource closeout. These final
source changes have not yet received a rebuilt installed/combined envelope.

Remaining combined failures are retained with copied originals:

- Windows 3.12 model-owner recovery observed one provider-fixture invocation
  where `test_model_recovery_record_failure_rolls_back_replacement` expected zero
  for `outward_model_attempts_v2`. Its exact cause remains unproven.
- Linux 3.11 approval denial returned HTTP 422. Its copied database retains a
  failed-terminal turn and active lease; the attempt starts at
  `2026-09-14T14:19:25.326374+00:00` and ends earlier at
  `2026-09-14T14:19:23.134941+00:00`. Parent/issue runs remain executing. This proves
  the retained inconsistency, not the original exception detail or a host-clock
  cause. Preserve both approval cases and their 229 files; Windows retention
  preserves five files across the three recovery cases.

Current correction/source hashes and exact files:
`.tmp/bt5-gitea-terminal/correction-audit.json` and
`.tmp/bt5-gitea-terminal/current-turn-files.json`. Preserve the initial audit and
its artifact/input binding. Resolve these two demonstrated predicates, restore
current installed/combined proof, then continue historical unmarked migration
and the remaining family obligations. BT-5 and the whole lane remain open.

### Approval denial transaction and native fixture continuation: 2026-09-14

Status: scoped source/installed acceptance; the whole BT-5 gate remains open.
This addresses the two demonstrated predicates from the preceding Gitea candidate,
not the whole BT-5 gate. Its original 18 source, seven proof, 126 fixture and six
helper hashes still matched disk before edits; the initial failed gate's 65 proof
and 227 fixture hashes also matched. The original handoff is older execution
history. Current roadmap/plan authority remains BT-5.

The immediate denial helper bypassed `finalize_turn_execution_atomic`, leaving
partial terminal writes when resource release failed. Both immediate decision and
retained epic-pause consumers now receive the same-store transaction factory and
reuse that wrapper. The writer rereads the child and counts actual retained tool
steps before closure. Operator decisions and their separate holds/actions remain
retained; they are not rolled back with child closure. Both consumers validate
the terminal join and namespace resource closure before accepting finished-child
reuse. Contract delta: `CONTRACT_DELTA_APPROVAL_TERMINAL_BT5_2026-09-14.md` under
`docs/architecture/`; durable rules live in `CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

Retained source counterexamples in `.tmp/bt5-approval-terminal/`:

- `before.xml`: 15 failed / one passed. All 12 post-write exception/cancellation
  controls and the reversed-clock denial retained partial control-plane state.
  Native model-claim EOF and invalid-token controls each advanced the provider;
  explicit continuation was the passing positive control.
- `atomic.xml`: all 16 pass after transaction/fixture repair.
- `reentry-before.xml`: missing final truth and an active lease still admitted
  terminal-child continuation; two other contradictory-history controls refused.
- `focused.xml`: all 65 cases pass after terminal reuse validation, including
  existing turn-terminal, approval continuation and model-owner recovery cases.
- `restart.xml`: 12 controls initially asserted raw exceptions instead of the
  public runtime's `unresolved` result or `RuntimeExecutionCancelled` contract.
  These are retained test-assertion failures. Corrected restart controls pass in
  `restart-regression.xml`; that run also exposes stale in-memory composition and
  old projection fixtures accepting contradictory terminal continuation.

Native fixture interruption now requires exactly `continue` followed by a newline;
EOF or another token cancels the owned request without advancing the provider.
The controlled EOF reproduction explains a real fixture weakness. It does not
prove the exact event order of the original uninstrumented Windows failure.
Likewise, rejected backward-clock controls do not identify the original Linux
host-clock cause. No clock configuration or provider selection changed.

The next acceptance requirement was a rebuilt candidate covering this source
repair and the prior Gitea empty-expiry correction, with combined Windows/Linux
Python 3.11/3.12 and actual installed service/provider proof. The results follow.
Historical unmarked redispatch, general mutable
state CAS, other family conformance, C/D/E/CAP and whole-lane acceptance remain.

The first rebuilt envelope is retained in `gate/audit.json`: source, Windows
3.11/3.12 and Linux 3.12 pass all 1,286 cases; Linux 3.11 passes 1,285 and fails
the new `cancel-publish_resource` denial control because its expected cancellation
is not raised. All identities match, with zero errors/skips and 893 checked
package origins per installed cell. `failed-cancellation-linux.json` binds the
original and copied 105-file fixture: the child and attempt remain executing,
end time is absent, truth is absent and both leases remain active. The original
response/closing clock were not captured, so its exact cause remains unproven.
The initial audit is **primary / failure**, with only `four_installed` false.

The interruption fixtures now supply an explicit ordered UTC clock to turn
admission/closure. A separate reversed-clock control requires the actual lease
timestamp rejection, unchanged control-plane state and no resource-write entry.
This isolates a later write-interruption predicate from earlier clock refusal;
it does not claim to repair or explain host UTC. No runtime or artifact bytes
changed after the first combined run. Fresh harnesses use `gate-verified/`;
do not overwrite the first failure. Actual installed Gitea's four cases and
separate llama.cpp success/failure flows already pass on this same wheel, with
retained state agreement and owned container/process cleanup.

Current scoped acceptance: `.tmp/bt5-approval-terminal/gate-verified/audit.json`.
The separate fixture clocks pass 29 focused cases, including explicit reversed
time refusal before resource publication. Fresh combined results:

| Envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 1,286 | 661.265 |
| Installed Windows Python 3.11 | 1,286 | 656.893 |
| Installed Windows Python 3.12 | 1,286 | 727.134 |
| Installed Linux Python 3.11 | 1,286 | 599.148 |
| Installed Linux Python 3.12 | 1,286 | 597.281 |

Every envelope contains the same unique cases, with zero failures, errors or
skips. The 32 new approval/restart/native-barrier controls and 43 Gitea controls
are included. Each installed cell checks 893 loaded origins, artifact/dependency
identity and 1,690 copied input hashes; 179 selected inputs include test helpers.
Only the two approval test files differ between the failed and fresh harnesses.
Source hashes were unchanged during execution. Core wheel SHA-256:
`92684a0fd4f348334a84b81c61b691530276b19b1a75ac919d02b53312605b94`;
sdist: `d65175c0b586441327d5088ba88a0463e156209b782d581dd1e10dc9f81e8923`.
SDK/reference/starter artifacts are unchanged. No second package install or
provider rerun was needed for the test-only clock correction.

Actual installed Windows 3.11 Gitea proof passes four cases in 24.067 seconds,
checks 762 origins and all 977 core Python files against the wheel, and confirms
removal of all four owned Gitea 1.25.4 containers. Separate actual llama.cpp
sessions `82ce8c61` and `baed89d1` use `orcarouter_qwen3.8-27b-uncensored-q4_k_l`:
the first exits 0 with `done`; deliberately missing attribution exits 1 with
`terminal_failure`. Both agree with retained truth/publication and confirm native
process cleanup. These flows establish their declared runtime paths, not new
model-quality, capacity or approval-interruption performance guarantees.

Proof is **primary / success** for this scoped repair. Live local ASGI/SQLite and
native-process controls remain distinct from the older in-memory projection
fixtures, which supply transaction composition but prove no persistence or
rollback. Ruff, dependency transition checks, test-layer/size checks, docs hygiene
and whitespace pass. Baseline collection succeeds with `release_ready=false`.
The initial failed gate, original Linux copied fixture, and preceding Gitea audit
remain preserved. The initial start snapshot has one CP1252-decoded UTF-8 PDF
filename; its actual bytes match. The audit normalizes that comparison key only
and preserves the original snapshot and PDF. All launched command handles are
reaped. The original main checkout remains clean; no commit, tag, push or release
was performed. Exact files: `gate-verified/current-turn-files.json` under this
proof root. Historical unmarked redispatch and remaining BT-5/C/D/E/CAP,
repository-wide/hosted CI, clock attribution and whole-lane acceptance remain.

### BT-5 versioned turn dispatch admission: 2026-09-14

Status: scoped dispatch-admission and historical-refusal gate accepted; BT-5 remains open.

The preceding approval-terminal audit was revalidated before changes: 22 scope,
201 proof and 16,485 source-fixture hashes matched. The current installed wheel
`92684a0fd4f348334a84b81c61b691530276b19b1a75ac919d02b53312605b94`
still redispatched a physical write on a byte-identical copy of the old producer's
16-file history: model calls 0, tool calls 1, reported success. The original and
current-wheel failures remain retained in `.tmp/bt5-turn-contract/` and the
unchanged `.tmp/bt5-turn-admission/` history.

New admission binds `turn_tool.dispatch_intent.v1` in the existing configuration
snapshot/run digest. Unfinished history requires that declaration and its exact
payload binding before continuation or new closure/publication. Runtime code does
not backfill old declarations. Coherent completed histories retain verified reuse;
conflicting truth references now refuse instead of being rewritten by reentry.
Durable semantics and rollback are in `CONTROL_PLANE_TERMINAL_AUTHORITY.md` and
`CONTRACT_DELTA_TURN_DISPATCH_ADMISSION_BT5_2026-09-14.md`.

The initial 19 controls failed before repair. Focused runtime proof passed 88;
a subsequent 43-case unit/transport/new-contract run initially failed five stale
in-memory admission fixtures, then passed after explicit fixture composition was
updated. The oversized approval test file shrank by extracting that setup.
Twenty-one new integration cases cover mutation refusal, payload binding,
pre-effect recovery and coherent/corrupt terminal reuse. Separate source runs on
four copies of actual old-wheel history refuse ordinary execution, resume,
denial closure and recovery with zero model/tool calls and unchanged logical
control-plane state. This is real SQLite/filesystem proof with controlled external
boundaries, not provider proof or completed family acceptance.

The final gate now passes the same 1,307 unique cases without failures, errors
or skips: source Windows 3.11 (653.767 s), installed Windows 3.11 (665.528 s),
Windows 3.12 (737.078 s), Linux 3.11 (610.955 s) and Linux 3.12 (606.064 s).
Each installed cell checks 893 package origins and 1,691 copied inputs. All 977
current core Python file bytes match the wheel. The source snapshot remained
unchanged during execution; final authority-summary edits are recorded separately.
The candidate core wheel is
`26ae911b54b58604c3d609185f3a8f8f4f4fcbd349ba6bf850426b29b9468cd4`;
the sdist is `8fc8d16d37f8e84fbffe280bcb758c0e00b89f162febff530de893865d34e1cb`.
SDK/reference/starter artifacts retain their prior identities.

Each of four installed environments also passes all four copied actual old-wheel
history controls with zero model/tool calls and unchanged logical control-plane
state. The old producer's 972 Python files still match its wheel; its original
16 files and all failed observations remain preserved. Actual installed llama.cpp
success session `cd7d00b9` exits 0 with `done`; expected attribution-failure session
`e9aaba85` exits 1 with `terminal_failure`. Both use
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`, match retained authority and confirm
child cleanup. Four installed Gitea 1.25.4 cases pass in 28.114 s with removal of
all four owned containers. The first CLI helper launch lacked the source-driver
`scripts` import path and started no runtime; its error log remains retained,
followed by the correctly composed installed proof.

Current evidence: `.tmp/bt5-turn-contract/gate/audit.json`, the matching manifest,
source/XML and installed reports, `installed-<cell>.json`, `source-history.json`,
and `live-success.json`, `live-failure.json`, `live-gitea.json`. Dependency transition,
Ruff, new-function/test-layer/size checks, docs hygiene and whitespace pass.
Baseline collection is true; release readiness remains false. Existing closeout's
125-line function gains its one declaration guard; no new function exceeds 70.
The approval test file shrinks to 846 lines; its remaining large tests are existing
debt. No repository-wide fresh suite, hosted CI or release acceptance is claimed.

The next required predicate has a concrete retained failure at
`.tmp/bt5-turn-contract/mutable-cas.json`: a real completed TurnExecutor run and
physical write are followed by a separate repository writer saving its stale
executing snapshot. Completed state is overwritten while terminal truth remains.
Public reentry refuses without another model/tool call; this is a demonstrated
mutable-state storage defect, not a demonstrated second public dispatch. Repair
shared CAS through the admitted family writers and prove their composed paths.
No historical replacement/reconciliation endpoint or remote fence is added by
this gate. The larger BT-5/C/D/E/CAP obligations remain active.

### BT-5 mutable execution revisions acceptance: 2026-09-14

Status: **primary / success** for the revision cutover's declared source,
installed, native and live-service scope. BT-5 remains open.

The preceding dispatch-admission audit was revalidated against all 17 scope,
66 proof, 12,321 non-cache source-fixture and 337 failed-fixture hashes. Its
independent stale-run overwrite counterexample remains intact. A second real
TurnExecutor/physical-write probe then showed a completed step being overwritten
by its original dispatch marker. Evidence is retained at
`.tmp/bt5-mutable-cas/step-before.json`.

The candidate introduces explicit revisions for run, attempt and step records.
Creation uses null and requires an absent identity. Reads return a nonnegative
revision; changed writes compare it inside the existing SQLite writer transaction
and return its successor. Identical current saves are no-ops; a stale revision
cannot regain authority when state returns to an earlier value. Historical rows
without a revision expose zero without backfill; this does not grant execution
or repair inconsistent history. Immutable attempt/step admission is also checked.
The durable delta is `CONTRACT_DELTA_EXECUTION_STATE_REVISION_BT5_2026-09-14.md`.

Application writers now retain returned records. Unit execution repositories
share one explicit test helper using the common rules; it claims no durability
or isolation proof. Initial 14 run/attempt revision controls failed before repair.
Seven step controls failed before step repair. The first source envelope then
passed 37 cases, including real composed outward/cards/governed-agent flows.
The broader source run retained 41 failures, 823 passes and four explicit live-Gitea
skips in `expanded.xml`. Its rerun cleared all 41 failures: `resume.xml` records
869 passes, four skips and one new test's incorrect repository keyword, since
corrected. Fixture repairs retain returned revisions or inject corruption directly
when a legitimate write now refuses it. Kernel initial execution may establish
its start timestamp; subsequent mutation remains forbidden. Kernel pre-effect
rejection/error now retains valid abandonment and projects failure evidence from
the bound recovery decision, with conflict controls against real SQLite.

Native independent writers and process death before commit pass for all three
record types. Boundary controls exposed Boolean revisions serialized as integers;
all six before-repair controls failed in `boolean-before.xml`. Persistence now
validates a Python value snapshot before JSON serialization. The corrected
`boundaries-fixed.xml` passes 76 cases, including malformed revisions, immutable
admission, caller mutation during await, SQLite kernel recovery and native races.
This is source proof, not installed or whole-family acceptance. Preserve the
current proof root and start snapshots; do not rerun sealed earlier auditors over
this changed code.

The seven source cases in `family.xml` also pass: outward, cards and governed-agent
closeout refuse their earlier run/attempt admissions; a real TurnExecutor writes
one physical file and refuses stale run, attempt and dispatch-step observations
after completion. The controlled family fixtures do not establish new provider
or remote-service coverage. An actual retained pre-revision TurnExecutor database
from the preceding audited source gate was copied, then all three record types
read as revision zero and saved as no-ops without changing any raw payload.
Its original SHA stayed unchanged; proof is at `history/source/report.json`.
The first combined gate (`gate/audit.json`) is retained as **primary / failure**.
All five envelopes executed the same 1,635 cases with zero errors/skips: source
passed 1,618 with 17 failures; each installed Windows cell passed 1,615 with 20
failures; each installed Linux cell passed 1,611 with 24 failures. All 84 new
revision/family/kernel cases passed in each envelope. Source hashes stayed fixed;
each installed cell checked 904 origins and its copied inputs/artifact identities.
The failure audit SHA is
`eb022baf8e2101c44121395a298c0c0614af8b9ec946242216b628f42079996d`.

The 17 source failures came from test setup: repeated parent admission did not
carry the observed revision, a fixture copied a revision into a fresh store, and
tests rebound immutable step inputs. Parent fixtures now read revisions, initial
agent step inputs bind the request digest, and deliberate corruption uses direct
fault injection. Four extra Linux failures used uppercase artifact directories;
the retained runtime paths are lowercase. Three extra installed failures lacked
the archived replay schema in the foreign harness. The repaired fixture modules
pass 63 source cases. The `repaired/gate` source run passes all 1,635 cases with
zero failures/errors/skips in 673.196 seconds. Each installed host passes 1,632
and fails the same three API schema checks: the harness included the root replay
schema but omitted `kernel-issue.schema.json` from the test registry. This failed
gate is sealed at SHA-256
`94a24b4f580bc1af976383a387a7ed66250c1f8b1b9b28c91f80cd09d1561bad`.
The fresh `complete/gate` includes both registry schemas. The three affected
cases pass independently on all four installed hosts before its broad rerun.
Source inputs remain byte-identical, so this campaign explicitly reuses the
1,635-pass source report/XML/log and binds the original source-fixture directory;
it does not claim another source execution.

The runtime wheel is unchanged by those fixture repairs: SHA-256
`82f83d5b68b182c7c2f98e958f66ff2ff8374259dfcb43cd17d1df5025fde251`;
sdist `adc0c470ba3f605b91ec2d55db6e1c927fbc5b321d5a3c644fb411a751abdd07`.
Separate actual installed Gitea passes four cases with all owned containers
removed. Actual llama.cpp success (`224878db`, exit 0, `done`) and deliberately
unsuccessful (`97bf5d76`, exit 1, `terminal_failure`) flows agree with retained
authority and confirm cleanup. The same wheel passes the actual copied historical
database read/no-op proof on all four installed hosts. These scoped live proofs
remain valid for this unchanged artifact; they do not override failed regression
acceptance. Reports and original failed fixtures remain under `bt5-mutable-cas`.

Actual installed kernel API admission, policy rejection and replay also pass on
this wheel through the real application and SQLite. The abandoned attempt keeps
null failure fields; the bound recovery decision supplies the projected failure
evidence. Replay leaves logical database state unchanged, reservations are
released, and application/background-task cleanup completes. Evidence:
`repaired/kernel-api.json`. The first local helper failed before app construction
because environment bootstrap ran inside the event loop; its retained
`kernel-api-before.log` precedes the corrected outside-loop bootstrap.

Final acceptance is `.tmp/bt5-mutable-cas/complete/gate/audit.json`. The four
fresh installed envelopes pass the same 1,635 cases as the explicitly reused
source observation, with zero failures/errors/skips:

| Envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11, unchanged retained execution | 1,635 | 673.196 |
| Installed Windows Python 3.11 | 1,635 | 661.496 |
| Installed Windows Python 3.12 | 1,635 | 734.782 |
| Installed Linux Python 3.11 | 1,635 | 656.496 |
| Installed Linux Python 3.12 | 1,635 | 645.253 |

Each installed cell verifies 904 actual package origins, wheel identities,
dependency consistency and its copied inputs before/after execution. The gate
includes all 84 new revision/family/kernel cases; their 305 retained fixture
files per installed cell and the original source fixtures are bound by hash.
The audit preserves both failed combined gates, binds the unchanged wheel's
actual llama.cpp/Gitea/kernel API and copied-history evidence, and records source
reuse explicitly. All launched proof sessions finished. Fresh docs hygiene and
whitespace checks pass; unchanged Python retains its preceding scoped Ruff and
transition-policy proof. Baseline collection remains true, release readiness false.
Local CAS does not fence remote effects or close BT-5/C/D/E/CAP. The independently
retained SDK/legacy/review failures below remain open, rather than being counted
as successes in this revision gate.

### BT-5 remaining family terminal counterexamples: 2026-09-14

Status: **primary / failure**, live local composition; no repair acceptance.
This is a demonstrated BT-5.3/5 gap in the named SDK, legacy and manual-review
families, whose executors remain distinct. Their narrower objective/recovery
ceilings do not permit contradictory durable terminal authority.

The existing revision-family controls cover outward, cards and governed agents.
The additional retained probe exercises `ReviewRunService.run_diff` with a real
local Git repository, and `ExtensionManager.run_workload` with installed local
SDK and legacy fixtures. Healthy controls pass. Injecting failure at the final
completed-run persistence call produces the same contradiction in all three:
the attempt is completed and success final truth is durable, but the run remains
executing with no final-truth reference. SDK/legacy propagate the injected error;
review's failure handler instead raises an illegal completed-to-failed attempt
transition. No returned public success is claimed by this observation.

Evidence: `.tmp/bt5-remaining-family/report.json` and `audit.json`; six composed
observations, retained raw databases/artifacts and unchanged source hashes.
The independent audit reopens each SQLite database read-only and verifies its
rows and original digest. Its initial local inventory read used the Windows
default encoding, corrupting a Unicode filename; explicit UTF-8 repaired the
audit helper only. `audit-bootstrap.json` retains that failed audit observation.

A separate source regression envelope for extension manager/components, review,
quickstart and arbiter paths passes 127 of 128 cases. The remaining extension
baseline test launches unqualified `python`, whose selected interpreter lacks
`pydantic`; putting the owned interpreter directory first on PATH still fails.
Both observations and fixtures are retained at `source.xml/.log` and
`baseline-path.xml/.log`. These are source tests with declared fixtures, not
installed-family or new provider/remote-service acceptance.

Next required predicates:

| Family | Required next evidence |
|---|---|
| SDK and legacy extensions | One transaction for the terminal record set; fault/cancellation controls retain no partial terminal truth. Coherent retained reuse is read-only; conflicting run/attempt/truth/step/effect identities refuse. Exercise both real `ExtensionManager` paths and inspect actual SDK output. |
| Manual review | The same terminal consistency and retained-history controls through real Git review. Failure handling must preserve a coherent state without masking the originating persistence failure. Offline review replay keeps its existing, separately stated scope. |
| Shared regression boundary | Retain outward/cards/governed-agent conformance and all failed fixtures; repair the explicit-interpreter test prerequisite, then run source and installed affected-family coverage on the resulting artifact. Do not grant SDK/legacy hostile containment or independent objective verification. |

### BT-5 remaining family terminal repair acceptance: 2026-09-14

Status: **primary / success** for this terminal transaction and retained-history
gate; whole BT-5 remains open. The preceding six
actual observations and audit remain unchanged (audit SHA-256
`18f71a0e9cf7e8b27e72b5c7481fd09dacbc4821f507b2847fb9e9ceb41f80b6`).

SDK and legacy extension closeout now borrow the shared control-plane transaction.
Manual review uses that transaction for closeout and terminal summary reads.
Common retained-evidence validation binds run/attempt/truth and exact family
closeout step/effect/result authority. Identical reuse is read-only; conflicting
outcomes and incomplete histories refuse. Review's error boundary logs a secondary
closeout error and preserves the originating exception. The extension baseline
test uses `sys.executable`, resolving the demonstrated interpreter mismatch.
Contract and migration disposition live in
`docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md` and
`docs/architecture/CONTRACT_DELTA_REMAINING_FAMILY_TERMINAL_BT5_2026-09-14.md`.

The new integration envelope exercises real local extension installation/workload
execution and local Git review: 30 post-write exception/cancellation controls,
healthy physical-result checks, original-error preservation, retained corruption,
no-op reuse and independent concurrent closeout owners. Copied actual old-wheel
healthy histories remain byte-identical; the three partial histories refuse
without mutation in the source probe at
`.tmp/bt5-remaining-family/repair/history/source/report.json`.

Retain all failed observations under `.tmp/bt5-remaining-family/repair/`.
`before.xml` has 30 failures and three passes, but ten failures are test-fixture
defects and cannot be counted as runtime counterexamples. `terminal.xml` passes
151 with ten fixture failures. After correcting journal callback arguments and
cancellation-message assumptions, `history.xml` passes 72. The expanded
`history-complete.xml` passes 90 with two review race-fixture failures: a cancelled
sync bridge legitimately invoked failure compensation before the intended race.
An explicit test-only stop before closeout corrects that fixture; `competing.xml`
passes all six race cases. That test boundary is not native process-death proof.

The fresh combined gate at `.tmp/bt5-remaining-family/repair/gate/audit.json`
passes all 22 checks. All five envelopes contain the same 1,854 unique cases,
including all 91 new family controls, with zero failures, errors or skips:

| Envelope | Cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 1,854 | 770.336 |
| Installed Windows Python 3.11 | 1,854 | 782.972 |
| Installed Windows Python 3.12 | 1,854 | 866.175 |
| Installed Linux Python 3.11 | 1,854 | 715.509 |
| Installed Linux Python 3.12 | 1,854 | 707.035 |

Each installed cell verifies 912 package origins, dependencies, exact wheel
identities and copied inputs before/after execution. Package parity covers 981
core and 29 SDK Python files. Current core wheel SHA-256 is
`cbd75c3cbaf597f5c99f04ccfd885eabda51e790e90f72e805ea8d0123d531db`;
sdist SHA-256 is
`b209d4cc7321204a8a037f8cc73021c464bfb21774e7df4edaa02de9cd28f14a`.
Both live in `repair/dist/`; SDK/reference/starter identities are unchanged.

Each source/installed host retains all 91 new case directories and 3,191 fixture
files. On copies of the six actual preceding-wheel databases, three coherent
histories are reused and three inconsistent histories refuse; logical state and
raw database bytes remain unchanged on every host. Earlier acceptance retains
its 54 proof files and 13,264 source-fixture files with matching hashes.

Separate actual installed Windows Python 3.11 llama.cpp flows return success
exit 0 / retained `done` and unsuccessful exit 1 / retained `terminal_failure`.
Both agree with retained final truth and publication and confirm process cleanup.
The attribution fixture's existing runtime-verifier disablement remains explicit;
this is provider/result regression proof, not new objective-verifier acceptance.
Four actual Gitea 1.25.4 cases pass with owned-container removal verified. All live
observations bind this same wheel. The source run's inputs remained unchanged;
later acceptance-document edits are recorded separately and checked by the
start-path governance envelope. No runtime or test semantics changed after proof.

Scoped Ruff, dependency transition policy, docs hygiene, whitespace, size and
immediate test-layer checks pass. The baseline generated
`2026-09-14T18:39:29.041332Z` has `collection_ok=true`, `release_ready=false`.
AC-01/02/03/05/06/07/08/09/10 pass for the affected boundary. AC-04 remains partial:
the existing service clocks are unchanged and owned by D's explicit-input work.
Pre-existing synchronous builder directory creation in the two family services
also remains D debt; the new terminal transaction path adds no blocking I/O.
The extension service shrinks from 623 to 543 lines, review control-plane service
from 420 to 370, and review run service from 516 to 511. New functions remain
within 70 lines; oversized pre-existing admission methods do not grow.

Admission atomicity,
remote fencing, hostile containment and independent workload objective verification
are not granted by this terminal repair. BT-5 and the later full-plan gates stay open.

### BT-5 remaining ODR native conformance observation: 2026-09-14

Status: **blocked / failure**, live local native preflight under a controlled
missing-tool condition; no repair or provider inference is claimed. The native
`scripts/odr/run_odr_quant_sweep.py` invocation uses an explicit owned interpreter,
a local one-round configuration and `ORKET_LLM_PROVIDER=llama_cpp`. Its child PATH
deliberately lacks Ollama. The arbiter writes its plan, then calls `ollama list`
despite its missing-tool check. It exits 1 with `FileNotFoundError`; the declared
preflight error artifact and result index are absent. The observation changes no
operator installation and invokes no provider inference.

Evidence and exact source/retained-file hashes:
`.tmp/bt5-odr-conformance/report.json` and `audit.json`. Existing arbiter catalog
tests compile a plan; the quant-sweep tests replace tool/model discovery and child
execution. Those controls cannot establish native preflight or execution truth.
Next required predicates are the declared refusal artifact under missing/unavailable
dependencies, explicit provider selection through preflight and execution, and
native bounded success/unsuccessful proof for the admitted ODR path. Reuse canonical
provider selection; installing Ollama is not a prerequisite for llama.cpp admission.
Do not count this scoped failure as an environment blocker for the entire goal.

### BT-5 ODR provider convergence acceptance: 2026-09-14

Status: **primary / success** for the scoped ODR gate; whole BT-5 remains open.
Plan v2 captures the selected provider/endpoint, shared provider inventory replaces
the independent Ollama CLI discovery, and native execution receives that selection
with automatic model replacement/loading disabled. Output validation binds provider
configuration and both role receipts. The runner closes its two provider clients;
the existing artifact validators are extracted once from the oversized arbiter.
Plan/error/raw outputs use the common rerun ledger. Contract and historical-plan
disposition: `docs/specs/ODR_PROVIDER_ADMISSION.md` and
`docs/architecture/CONTRACT_DELTA_ODR_PROVIDER_ADMISSION_BT5_2026-09-14.md`.

Initial native/contract controls pass 11 cases at
`.tmp/bt5-odr-conformance/repair/focused.xml`. Expanded controls pass 19 at
`controls.xml`, including actual local HTTP, subprocess/files, retained receipt
corruption and real provider-client cleanup. HTTP responses are explicit fixtures;
these runs do not prove actual model inference. The retained original missing-tool
failure is unchanged. Those initial controls preceded the expanded gate below.
The accepted core artifact is unchanged; current proof binds the copied script
inputs separately from the installed package.

The first wider campaign retained 184 source passes and 183 passes/one failure
in each installed cell: the foreign harness omitted `tools/repro_odr_gate.py`.
That is a harness defect, not a runtime pass. The preceding Linux preparation
error came from reading this Windows worktree's Git pointer through Linux Git;
the harness now consumes the checked Windows inventory. Missing/malformed base
specs also reproduced two native failures in `repair/base-before.xml`. They now
enter the single preflight error publisher, with invalid model-list/leak-policy
inputs refused before discovery.

The first actual llama.cpp invocation in `repair/live-success.json` obtained two
HTTP-200 model receipts but exited 2 under `E_ARB_VALIDATOR_LEAK`. It copied fenced
constraint metadata and reached the existing token ceiling. That failed positive
observation remains retained. Role prompts now reuse the canonical kernel builders,
retain scenario/seed constraints and request concise prose. Validators and token
ceilings are unchanged. The repaired native/contract selection passes 26 cases in
`repair/input-fixed.xml`. The separate `repair/verified/` campaign now passes:

| Current ODR envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 189 | 46.826 |
| Installed Windows Python 3.11 | 189 | 47.964 |
| Installed Windows Python 3.12 | 189 | 57.669 |
| Installed Linux Python 3.11 | 189 | 34.039 |
| Installed Linux Python 3.12 | 189 | 34.643 |

Every envelope has the same unique cases with zero failures, errors or skips.
They include 22 native/provider/retained-evidence controls; the local HTTP server
supplies explicit fixture responses. Each installed cell verifies 551 loaded
package origins, dependency consistency, wheel identity and copied inputs before
and after execution. The unchanged core wheel is
`cbd75c3cbaf597f5c99f04ccfd885eabda51e790e90f72e805ea8d0123d531db`;
core/SDK source-to-wheel/sdist parity passes. Scripts remain repository tooling,
not newly packaged core entrypoints.

Separate native invocations from foreign workspaces use installed Windows Python
3.11 and actual llama.cpp with Ollama absent from the child PATH. Success exits 0
and produces a validated index. Deliberate strict-policy refusal exits 2 with
`E_ARB_VALIDATOR_LEAK` and no index. Both retain two actual HTTP-200 receipts for
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`, matching the planned selection; both
native invocations return. This is not a general descendant-supervision proof.
Raw files and hashes live in `repair/verified/live-success.json` and
`live-failure.json`. The 18-check audit is
`.tmp/bt5-odr-conformance/repair/verified/gate/audit.json`; the prior terminal gate,
original counterexample and failed candidate observations remain unchanged.

Ruff, immediate test-layer labels, file/function limits, dependency transition,
docs hygiene and whitespace checks pass. The arbiter shrinks from 419 to 328
lines; sweep orchestration shrinks from 106 to 78 lines, and its pre-existing
oversized function remains explicitly visible. Baseline collection succeeds while
release readiness remains false. This gate does not admit independent requirement
quality, automatic restart, hostile containment or remote effect fencing. Next
reconcile all five BT-5 obligations against current family evidence, rather than
selecting another adjacent fix without a demonstrated acceptance gap.

### BT-5 current family evidence reconciliation: 2026-09-14

Status: **primary / partial success**; the current omitted-controls gate fails
one Linux 3.12 case. ODR's demonstrated failure is repaired. Comparing actual
manifest selections shows that the later 227-module,
1,854-case terminal gate omits nine modules from project-root acceptance and 36
from store-binding acceptance; the nine are included in those 36. These include
caller project selection, runtime/store CLI, historical binding/integrity migration
and earlier card/epic boundary regressions. Their old success used older wheels,
so it does not establish current composed behavior. The exact missing selection
was first executed in `.tmp/bt5-current-family-gaps/gate/` with the unchanged current
core artifact; it also includes the 32 start-path governance checks.

The original source envelope finished with 290 passes and one failure: the
composition unit fixture omitted the already-required `control_plane_transactions`
owner. Its fake now supplies that owner and asserts that the engine retains it.
This test change is structural proof only; production composition is unchanged.
The first installed harnesses failed collection because they omitted the current
`control_plane_execution_memory` helper. The repaired harness then disclosed its
second missing dependency, `control_plane_unit_transaction`. Both sets of failed
collection logs are retained. The complete harness includes both inspected
helpers and retains dedicated pytest fixture roots; completed current runs are at
`.tmp/bt5-current-family-gaps/complete/gate/`. ODR acceptance stays separately
sealed at audit SHA-256
`cb8d945f20e6cc215427b8e5a868c08258dfe9ceda7a32e85f094e6925239ed3`.

| Current missing-module envelope | Pass / fail | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 291 / 0 | 150.526 |
| Installed Windows Python 3.11 | 291 / 0 | 152.493 |
| Installed Windows Python 3.12 | 291 / 0 | 148.930 |
| Installed Linux Python 3.11 | 291 / 0 | 164.211 |
| Installed Linux Python 3.12 | 290 / 1 | 158.011 |

All five executions have the same 291 unique cases and zero errors/skips. Each
installed cell verifies 690 package origins, dependencies and copied inputs.
Package sources still match the accepted artifacts. The audit at
`.tmp/bt5-current-family-gaps/complete/gate/audit.json` correctly reports failure;
it retains 10,312 fixture files per passing cell and 10,313 for Linux 3.12, plus
the original unit failure and both failed installed collection campaigns. The
retained terminal and ODR audits remain unchanged. Their combined 2,268 distinct
case identities are an inventory, not a new all-green combined execution.

Exact remaining failure:
`tests/application/test_execution_pipeline_run_ledger.py::test_run_ledger_blocks_done_run_when_required_source_attribution_is_missing`.
The retained `packet1_emission_failure` event reports a generation-stage
`ValueError: run_summary_duration_negative`. The runtime preserves
`terminal_failure` and `source_attribution_receipt_missing`, but emits a degraded
summary without `truthful_runtime_packet2`; that missing packet fails the test.
`complete/summary-failure.json` binds the event, summary and JUnit hashes. This
observation does not independently establish host-clock reversal or its cause.
Before another broad run, inspect the retained time inputs and the existing
clock/summary authority, repair the demonstrated timing or fixture defect without
weakening source-attribution assertions, and verify the applicable current
envelope. This is a BT-5 acceptance predicate touching the already-open D clock
obligation, not an environment blocker or permission to close BT-5.

| Obligation | Current evidence and precise remaining acceptance predicate |
|---|---|
| 1. Named family chains | The durable matrix names all eight required families, public entrypoints, owners and ceilings. Its ODR surface now points to the executable quant-sweep CLI. Structural catalog checks cover 32 cases; behavioral acceptance must bind the family proofs below. |
| 2. Reconciled contradictions | Authenticated scheduled/webhook admission is exercised in the terminal gate. Native ODR now uses the selected provider and produces typed refusal. The omitted current-artifact envelope is executed; its Linux 3.12 negative-duration summary failure needs the precise disposition above. |
| 3. Shared minimum contracts | `test_family_admission_authority`, `test_family_run_authority` and `test_family_terminal_authority` exercise the same interruption/immutable-input/terminal predicates through composed outward/cards/governed-agent paths. The terminal gate also covers shared revisions, dispatch uncertainty and SDK/legacy/review retained joins. Verify their unchanged source/artifact lineage when assembling the final disposition; no new general recovery or remote-fencing guarantee is inferred. |
| 4. Consumer cutover and migration | Outward catalog adoption and actual copied-history migration are retained, with no dual effect dispatch. Current root/store/card controls execute in all five cells; one summary predicate remains failed. Other family executors keep the matrix's explicit semantics. |
| 5. Family conformance | Retain the current 1,854-case terminal gate and 189-case ODR gate with their actual native/service proof and limitations. Resolve the failed 291-case gate, then bind exact identities, artifacts and input deltas into one complete family disposition. Full-suite, hosted CI, C/D/E and CAP remain separate required gates. |

### BT-5 prerequisite: epic bootstrap clock input candidate, 2026-09-14

Status: **primary / partial success**; the explicit-clock controls pass current
installed proof, while the combined family gate exposes separate defects below.
The retained failed run's identity starts at `2026-09-14T19:52:47.324154+00:00`,
but its workload outcome and preparation use `2026-09-14T19:52:41.500020+00:00`.
Publication later records `2026-09-14T19:52:48.051612+00:00`. These exact values
explain the negative summary interval; they do not attribute its clock's cause.
The original failed gate and all fixture hashes remain preserved.

Inspection found an independent input-authority defect: epic bootstrap omitted
the already-supported `now` argument, so a supplied `RuntimeInputService` clock
controlled outcome/publication but not run identity. The existing protocol clock
fixture worked around this by starting one day after wall time. It now supplies
a fixed synthetic epoch, and four composed cases failed before the runtime repair
in `.tmp/bt5-summary-clock/before.xml`. Bootstrap now passes one captured UTC
input through the existing service. Ten focused cases pass in `after.xml`.

The source-attribution test moved from the oversized run-ledger test module into
`tests/integration/test_epic_summary_clock_authority.py`, retaining its original
failure/packet assertions for ordered input and adding deliberate negative-summary
input. Both paths use actual files, protocol ledger, publication and card state;
the workload callback is controlled and is not model-quality proof. The negative
case requires explicit generation-error evidence, nullable degraded duration and
the unchanged source-attribution failure. No clock clamping or success fallback
was added. Existing non-monotonic publication refusal also remains covered.

Contract and migration ceiling: `docs/specs/EPIC_RUNTIME_TIME_INPUTS.md` and
`docs/architecture/CONTRACT_DELTA_EPIC_TIME_INPUT_BT5_2026-09-14.md`. One production
input argument changes, so current package rebuild and installed/native acceptance
are required before accepting the candidate. D still owns the broader time-input
inventory and historical clock attribution. Preserve the complete BT-5 family
obligations while proving this demonstrated prerequisite.

### BT-5 issue-dispatch closeout counterexample and transaction candidate, 2026-09-14

The complete family selection finished on rebuilt core wheel
`c050bf9d0901fb064328c05080dbbe07d244d220bd563d3c5feb6833f436cd93`.
Its retained audit is `.tmp/bt5-summary-clock/gate/audit.json`, SHA-256
`3210333ebf14e38848bb2478e00bb1b1440140c172d549a3e1d5e60e606b4e19`.
This is **primary / failure**, not BT-5 acceptance:

| Current combined envelope | Observed result | JUnit seconds |
|---|---|---:|
| Source Windows Python 3.11 | 2,309 passed; one teardown error | 987.588 |
| Installed Windows Python 3.11 | 2,309 passed | 995.860 |
| Installed Windows Python 3.12 | 2,309 passed | 1,078.390 |
| Installed Linux Python 3.11 | 2,309 passed | 892.791 |
| Installed Linux Python 3.12 | 2,308 passed; one failure | 884.215 |

All cells retain their 2,309 case identities, with no skips. Installed cells check
926 package origins and copied inputs. The separate
`.tmp/bt5-summary-clock/clock-controls/gate/` includes the two existing publication
clock cases omitted by the combined selection: ten clock controls pass in source
and each installed cell, with 669 origins checked per installed cell. These prove
explicit ordered/reversed inputs and summary/ledger refusal, not clock-cause
attribution. Current installed card success/failure, ODR success/refusal and four
actual Gitea cases also pass with retained cleanup evidence. All earlier sealed
audits remain intact; the failure audit binds these distinct scopes and artifacts.

The source teardown error occurs in the real-child handshake-expiry fixture:
`psutil` observes that the child no longer exists before asyncio populates its
return code. The fixture now awaits the existing process handle, with a five-second
bound, rather than asserting synchronous callback completion.

The Linux failure is more than an uncontrolled positive-test clock. In
`test_approval_http_response_distinguishes_decision_from_runtime_outcome[approve]`,
the retained issue attempt starts at `2026-09-14T20:18:47.040593+00:00` and ends at
`2026-09-14T20:18:44.613316+00:00`. The run, attempt and final truth already say
completed/success when lease release rejects reversed time. Its lease remains
active and the parent API reports unresolved. Read-only inspection is retained at
`.tmp/bt5-summary-clock/approval-failure.json`; the original database SHA-256 is
`1881115b39813bdd45612f6fbdc31805b1f54e6ffa2be8ec68cb50a7ebe95791`.
These observations prove split publication, without independently attributing the
host-clock cause. Merely stabilizing that positive test would leave the defect.

Four controlled pre-repair cases in `.tmp/bt5-issue-terminal/before-verified.xml`
reproduce partial publication after a lease write, resource write, cancellation or
reversed time. The initial `before.xml` also retains a wrong fixture method name;
it establishes three runtime counterexamples and one setup error. Closeout now
uses the existing explicit transaction factory, with its publication body extracted
into `orchestrator_issue_closeout.py`. Both public service callers use that owner.
Terminal/recovery/step/effect and lease/resource writes commit together; reentry
validates the shared terminal join and released resource authority. Dispatch
admission and prior physical effects remain outside this transaction.

Source focused proof passes 34 cases, including all seven new rollback/retry,
contention and historical-refusal cases, existing issue controls, real ASGI approval
continuation and native child expiry/cleanup. Contract:
`docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`; delta:
`docs/architecture/CONTRACT_DELTA_ISSUE_CLOSEOUT_BT5_2026-09-14.md`.
This is a new package candidate. Complete current installed/native proof and the
whole family disposition before accepting BT-5. Preserve both failed combined
observations; broader time-input authority remains under D.

Current candidate proof is now **primary / partial success** on core wheel
`5d0f6a4058ecadfd7be26c50b70680c5d174b8107bcf51f231ac321f71c3b9d9`
and sdist `16838437801276365db4395c075de5274012b966bb5f7d4712e1de876eb5133a`.
The audit at `.tmp/bt5-issue-terminal/gate/audit.json` correctly remains failed:

| Issue closeout / approval / clock / child envelope | Pass / fail | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 44 / 0 | 50.614 |
| Installed Windows Python 3.11 | 44 / 0 | 51.123 |
| Installed Windows Python 3.12 | 44 / 0 | 50.888 |
| Installed Linux Python 3.11 | 42 / 2 | 92.618 |
| Installed Linux Python 3.12 | 43 / 1 | 90.288 |

All cells have identical cases, zero errors/skips and 696 checked installed
origins per installed cell. The seven new transaction/refusal cases pass in every
cell. Source JUnit/report authority is `gate/source-final/`, captured after all
package installs finished. The inherited wrapper reused `gate/source-fixtures/`;
these fixtures belong to the final source run. The earlier source run's log/JUnit
remain, but its fixture directory was replaced and cannot support a separate
retained-fixture claim. Its startup had overlapped installation. Both actual installed llama.cpp card outcomes
pass, with success exit 0 and terminal failure exit 1 and confirmed process cleanup.
`copied-history.json` records installed refusal of a byte-identical copy of the
actual failed Linux database, preserving its logical contents and the original
database hash. This is closeout refusal, not automatic history reconciliation.

Both Linux cells fail the native effect/resume fixture's `normal` case with
`E_SDK_AGENT_FRAME_READ_TIMEOUT`, retaining recovery-pending state and no final
truth. Their resumed invocations preserve their original request deadlines:
`2026-09-14T20:52:54.045885+00:00` on Python 3.11 and
`2026-09-14T20:52:53.109466+00:00` on Python 3.12. Existing records do not identify
the exact read phase or prove the cause of the deadline failure. Python 3.11 also
fails the positive approval HTTP case after the already-atomic turn closeout
rejects reversed lease time; its log moves from `20:53:15.596746` to `20:53:13.844495`
UTC and the parent publishes an unsuccessful result. This differs from the
repaired issue-dispatch split publication. Exact read-only observations and hashes
are in `.tmp/bt5-issue-terminal/linux-observations.json`.

### BT-5 native deadline diagnosis and separated controls, 2026-09-14

Fresh installed Linux observations at `.tmp/bt5-native-deadline-probe/` preserve
the previous wheel and every production timeout argument. Python 3.11 passes all
44 cases; Python 3.12 passes 43 and fails `delayed-startup`. That resumed child
starts its ready read with 3.071609 seconds remaining of the original eight-second
deadline, including the deliberate 2.25-second suspension. Ready arrives after
2.659 seconds; subsequent capability calls exhaust the remaining budget. The last
read receives 0.001 seconds and returns `E_SDK_AGENT_FRAME_READ_TIMEOUT`, with the
child confirmed stopped and recovery-pending state. This is post-handshake deadline
exhaustion. The same trace records UTC moving backward while monotonic time advances;
it does not independently attribute the host-clock cause or the earlier uninstrumented
normal-case failures. Raw events, reports and hashes remain retained, with a selected
observation copy at `.tmp/bt5-native-resume-controls/deadline-observations.json`.

The native effect/resume test previously performed tampered-request and stale-guard
rejection controls between its two children in all three startup variants. Those
controls now have a separate real-native/SQLite case: both refusals preserve the
blocked run, valid authority then activates it, and no second invocation exists.
The successful resume retains its actual approval, file effects, checkpoint,
receipts and both native children, plus an explicit unchanged-deadline assertion.
The three startup variants, eight-second request, seven-second lease and two-second
explicit handshake-expiry boundary are unchanged. All functions in the modified
327-line native test module are at most 38 lines. The positive approval HTTP test
uses the existing explicit ordered turn clock; deliberate reversed-time transaction
controls remain in the same acceptance selection. Runtime code is unchanged.

Current scoped audit is **primary / success** at
`.tmp/bt5-native-resume-controls/gate/audit.json`, SHA-256
`9b23663cc2af5ca32ac60a18255540875dfe7919ca5ea8849accbaa09e46565c`:
82 identical cases pass in source (67.162 seconds), Windows Python 3.11/3.12
(68.545/67.591 seconds), and Linux Python 3.11/3.12 (99.770/95.045 seconds).
There are no failures, errors or skips; each installed cell checks 890 origins,
dependencies and copied input hashes. Fresh fixture roots are retained for all
five cells. All original 44 cases remain selected, alongside separate rejection
and approval/turn transaction controls. An initial audit check searched for the
wrong parameter name (`clock` instead of `reversed-time`); its failed structural
observation remains in `audit-check-before.json`. No test rerun hid that error.
Ruff, dependency transition, docs hygiene and whitespace checks pass.

Core wheel remains `5d0f6a4058ecadfd7be26c50b70680c5d174b8107bcf51f231ac321f71c3b9d9`.
The same-artifact actual installed llama.cpp card success/failure and copied failed
history refusal from the issue candidate are hash-verified and reused; no new
provider execution is claimed. This establishes the recorded affected controls and issue-closeout
repair scope, not the combined BT-5 gate. Next: execute the union of the prior complete
family selection and these controls against current artifacts, then reconcile BT-5's
five numbered obligations. Full BT-5/C/D/E/CAP, fresh full-suite, hosted CI and release
acceptance remain open.

### BT-5 complete current union: retained native failures, 2026-09-14

The current union contains 278 selected modules and exactly 2,319 case identities:
the prior complete selection plus all 82 current controls, with no missing or added
identities outside that union. Its audit at
`.tmp/bt5-family-current-acceptance/gate/audit.json` is **primary / failure**:

| Envelope | Pass / fail | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 2,319 / 0 | 992.516 |
| Installed Windows Python 3.11 | 2,319 / 0 | 999.080 |
| Installed Windows Python 3.12 | 2,319 / 0 | 1,084.534 |
| Installed Linux Python 3.11 | 2,318 / 1 | 1,144.141 |
| Installed Linux Python 3.12 | 2,318 / 1 | 1,094.995 |

All cells have zero errors/skips. Installed cells check 927 origins, package
identities, dependencies and copied inputs. Source was unchanged during execution;
later documentation disposition is listed separately by the audit. Fresh fixture
roots retain 30,031 source files and 30,033/30,014/30,032/30,018 files in the four
installed cells. The wheel remains `5d0f6a4058ecadfd7be26c50b70680c5d174b8107bcf51f231ac321f71c3b9d9`.
Fresh actual installed llama.cpp ODR success and deliberate validator refusal pass,
each with two HTTP-200 role receipts. Four actual Gitea cases pass with all four
owned containers removed in the same paths; 982 installed core Python files are
verified against the wheel. Same-artifact actual card outcomes and copied failed
history refusal remain explicitly reused from the issue candidate. All predecessor
audits and their original failed observations remain intact.

Linux 3.11 fails `test_effect_approval_pauses_then_resumes_with_verified_receipts[delayed-startup]`
after 3.347 seconds. Its second invocation is interrupted with
`E_SDK_AGENT_FRAME_READ_TIMEOUT`; the run is recovery-pending with no final truth.
The original deadline remains `2026-09-14T21:27:36.526698+00:00`. Retained database:
`test_effect_approval_pauses_th1/agent-effect-loop.sqlite3`, SHA-256
`bb732ff393caf45403e8e421acdef203be55ee56c309af5d7f28e59d1a40258c`.
Linux 3.12 fails `test_family_terminal_projection_refuses_inconsistent_history[coherent-governed_agent]`
after 2.087 seconds, before a successful terminal fixture exists. Its first invocation
is interrupted by the same timeout; the run is recovery-pending, preserving deadline
`2026-09-14T21:33:03.842686+00:00`. Retained database:
`test_family_terminal_projectio2/agent.sqlite3`, SHA-256
`4190b8f6feb1d0d5109105c869067b47dd92148df9db90bbe1fbb1a6a4197a74`.
Both databases were read locally on Linux with read-only SQLite connections and
unchanged raw hashes. Full selected observations are retained in
`.tmp/bt5-family-current-acceptance/linux-failures.json`; deliberately corrupted
neighboring history fixtures are distinct from the failed coherent case.

The 82-case pass did not resolve native timing across the combined run. These
failures occur well before eight elapsed seconds; do not explain them solely by
test workload duration or infer a host-clock cause from retained timestamps.
The earlier observational trace proved a UTC reversal in that separate run, not
these cases' exact read phase. Progress-log tails missed the earlier failure
markers; final JUnit is the verdict authority, not a tail containing only dots.
Next predicate: trace admission clock inputs, remaining-time calculations and
monotonic elapsed time in both native paths. Preserve original budgets and failed
stores; do not accept timeout as successful conformance. Keep BT-5 open and avoid
another complete rerun until the focused predicate is resolved.

### BT-5 shared native fixture clocks: 2026-09-14

Status: **primary / success** for 96 scoped cases; combined BT-5 remains open.
The subsequent observational native selection passed 16 cases on both installed
Linux versions while still measuring realtime discontinuities. Independent
sampling outside pytest also observed them. Direct kernel clock calls then
bracketed every Python time sample without disagreement in two 4,500-sample runs.
Both kernel traces contain approximately +8.163, -5.615 and +6.541 second realtime
offset changes relative to monotonic time, including the disposable process pinned
to CPU 0. Evidence: `.tmp/bt5-elapsed-clock-controls/clock-observations.json` and
its hashed raw reports. This establishes observed kernel realtime discontinuity,
not its underlying cause or attribution of the earlier uninstrumented failures.
No global clock setting changed.

The selected effect-resume and family-history fixtures now use one explicit UTC
epoch advancing with real monotonic elapsed time. Their helper supplies that same
input to request creation, the host invoker and the SDK broker in the native child.
A test-only bootstrap sets the SDK clock before running the canonical child module;
the executable, workload arguments, pipes, native waits and teardown stay real.
Production clocks, package sources and the `5d0f6a...` wheel are unchanged. The first
parent-only fixture failed because the child broker independently reads UTC;
its `focused.xml`, log and fixture databases remain preserved. The paired-clock
focused run passes all 18 cases.

Two new native controls jump the parent UTC input nine seconds before the first
invocation's read or the resumed invocation's read. Both finish before eight real
elapsed seconds, retain recovery-pending uncertainty with no final truth, preserve
the original deadline and confirm every child stopped. Successful and delayed
resume retain eight/seven-second request/lease limits; the two-second handshake
expiry and previous reversed-time transaction controls remain selected.

The complete affected selection passes 96 identical cases in source and installed
Windows/Linux Python 3.11/3.12, with zero failures/errors/skips and 890 verified
package origins per installed cell. Source takes 86.992 seconds; installed cells
take 87.792, 89.956, 117.706 and 113.157 seconds. Gate evidence is retained under
`.tmp/bt5-elapsed-clock-controls/gate/`. Same-artifact actual card/ODR/Gitea flows
and copied failed-history refusal are retained, not rerun for this test-only change.
This proves conformance with controlled UTC inputs and real elapsed lifetime;
it does not establish unrestricted host-clock behavior or close D's clock authority.
Next: execute the complete 2,321-case family union, preserve the failed 2,319-case
audit, and reconcile all five BT-5 obligations before accepting the gate.

### BT-5 complete elapsed-clock union and remaining fixture inputs: 2026-09-14

The complete 2,321-case union is **primary / failure**. Source and installed
Windows 3.11/3.12 and Linux 3.11 pass all cases; Linux 3.12 has 2,319 passes and
two failures, with no errors/skips. Durations are respectively 974.231, 976.175,
1,064.409, 1,042.771 and 1,028.765 seconds. Every installed cell checks 927 origins;
the exact case union, source/artifact parity, dependencies and governance checks
pass. Failed audit: `.tmp/bt5-family-elapsed-clock/gate/audit.json`, SHA-256
`89ed4954bf396596ad32defdfdf8054916762e7efff1bfbba7ea5046493fd083`.
All five sessions are terminal; original fixture files remain retained.

`test_epic_approval_survives_restart_with_parent_truth[False-approve]` fails after
3.138 seconds. The guard closeout reports `lease publication timestamps must
increase monotonically`; retained logs move from `22:25:29` to `22:25:25` UTC.
The parent is failed, the completed builder/issue joins retain success with released
leases, and the guard remains executing without final truth. The run/attempt/truth
joins are consistent; this is distinct from the earlier partial issue closeout.
`test_retained_terminal_consistency_precedes_result_or_reentry[unfinished-attempt-reentry]`
fails after 1.457 seconds while creating its native history fixture. Its second
invocation is interrupted with `E_SDK_AGENT_FRAME_READ_TIMEOUT`, preserving deadline
`2026-09-14T22:29:55.330538+00:00` and recovery-pending uncertainty without final truth.
Native read-only inspection and original database hashes are retained in
`.tmp/bt5-family-elapsed-clock/linux-failures.json`. Exact original clock-read phase
and underlying host cause remain unproven.

The subsequent fixture change applies the existing shared native clock to all
eight discovered test-module consumers of the composed native fixture, and ordered
turn time to the complete approval-continuation module. Its 17-module selection
passes 171 identical cases in source and each installed Windows/Linux Python
3.11/3.12 environment, with zero failures/errors/skips and 890 checked package
origins per installed cell. Source takes 196.509 seconds; installed cells take
197.247, 211.437, 195.463 and 192.969 seconds. Source inputs are unchanged during
execution. Audit and fixture retention: `.tmp/bt5-shared-fixture-clocks/gate/`.
The audit discovers native-fixture consumers from imports, requires each to declare
the clock and includes every consumer in the executed selection. Earlier explicit
expiry/reversal controls remain present. No production clock, artifact, deadline,
assertion or failure outcome changes. The fresh complete 2,321-case union and
five-obligation BT-5 disposition remain required; this scoped pass does not accept
the failed full union or establish host-clock repair.

### BT-5 complete shared-fixture union: issue-clock refusal, 2026-09-14

The next complete 2,321-case run remains **primary / failure**. Source, installed
Windows 3.11/3.12 and Linux 3.11 pass all cases; Linux 3.12 has 2,320 passes and
one failure, with no errors/skips. JUnit durations are respectively 973.085,
981.240, 1,066.892, 1,136.836 and 1,120.585 seconds. The five environments execute
the same unique case identities; installed cells check 927 package origins each.
Repository inputs remain unchanged throughout source execution. Evidence and
retained fixtures: `.tmp/bt5-family-shared-clock/`.

`test_concurrent_continuation_consumes_pause_once` fails after 1.786 seconds because
the run ledger remains `running` instead of `done`. The captured native traceback
reports `lease publication timestamps must increase monotonically` in the enclosing
issue-dispatch closeout. The selected fixture controls turn time but leaves the
issue service's UTC input independent. Native read-only inspection retains the
completed turn with released lease and successful final truth; the issue and epic
remain executing without final truth, and the issue lease remains active. All
three run/attempt/truth joins are consistent. The original database bytes are
unchanged; this is an atomic refusal, not the earlier partial-success closeout.

The failed full audit is sealed at
`.tmp/bt5-family-shared-clock/gate/audit.json`, SHA-256
`f6e51b1551aad3e7bbbaa4bb01349f0aaf5943c73e8b2c258272a5a669f03586`.
The fixture now supplies the same explicit ordered clock to the turn and its
enclosing issue-dispatch service. All 12 discovered turn-clock consumer modules
are selected with the preceding native/deadline controls: 325 identical cases
across 27 files pass in source and all four installed environments, without
failures/errors/skips. JUnit times are 228.443, 230.503, 244.565, 336.246 and
330.943 seconds; each installed cell checks 890 origins. Source inputs remain
unchanged during execution. Scoped proof and retained fixtures:
`.tmp/bt5-composed-turn-clocks/gate/`.

The independently supplied reversed issue timestamp still requires full rollback.
No production clock, package, validation rule, assertion or deadline changes.
Original clock-read phase and host cause remain unproven; production clock-input
ownership remains D work. Next: rerun the complete 2,321-case family union and
reconcile all five BT-5 requirements. This scoped pass does not accept the preceding
failed full run or close later structural/capability gates.

### BT-5 complete family disposition: 2026-09-14

Status: **primary / success** for the eight families' declared contracts. The
complete current union and the five requirements below now have scoped acceptance.
This does not accept later structural, quality, capability or whole-lane gates.

Sealed audit: `.tmp/bt5-family-composed-clock/gate/audit.json`, SHA-256
`4177e6150883aa61b7ba1b0b10ecde6418601f0bf16e79cdd8b02b12a5d0405c`.
Core wheel remains `5d0f6a4058ecadfd7be26c50b70680c5d174b8107bcf51f231ac321f71c3b9d9`;
SDK/reference/starter identities are unchanged and bound by the audit. No runtime
or test input changed during this complete execution.

| Envelope | Pass / fail / error / skip | JUnit seconds |
|---|---:|---:|
| Source Windows Python 3.11 | 2321 / 0 / 0 / 0 | 988.273 |
| Installed Windows Python 3.11 | 2321 / 0 / 0 / 0 | 992.463 |
| Installed Windows Python 3.12 | 2321 / 0 / 0 / 0 | 1082.034 |
| Installed Linux Python 3.11 | 2321 / 0 / 0 / 0 | 1060.982 |
| Installed Linux Python 3.12 | 2321 / 0 / 0 / 0 | 1049.401 |

All five have the same 2,321 unique identities from 278 selected files, including
the previously omitted root/store/card controls. Each installed cell verifies
927 package origins, dependencies and unchanged copied inputs. Native fixture
retention covers 30,037 source, 30,038 Windows 3.11, 30,036 Windows 3.12, 30,022
Linux 3.11 and 30,023 Linux 3.12 files. All test and fixture processes returned.

| Requirement | Acceptance evidence and retained limit |
|---|---|
| 1. One named family chain | `CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md` names executor, authorization/effect/terminal owners, public paths, replay, objectives and unsupported cases for cards, outward, governed agents, SDK, legacy, quickstart, review and ODR. Catalog governance and each family's actual public/composed paths are selected in the complete gate. Catalog identity alone is not effect or completion authority. |
| 2. Reconcile code/proof contradictions | Authenticated schedule evaluation and HMAC webhook delivery queue through the governed-agent authority; they are caller-driven ingress. Current root/store/card and ODR provider-selection controls pass. Same-artifact actual llama.cpp card success/failure, ODR success/validator-refusal and four actual Gitea flows are reverified by retained hashes, with their original provider and teardown observations. No new provider run is claimed. |
| 3. Shared minimum contracts | The `test_family_admission_authority`, `test_family_run_authority`, `test_family_terminal_authority`, `test_family_terminal_history` and `test_family_execution_revisions` modules apply common rollback, immutability, stale/ABA-write and retained terminal predicates to real composed outward/cards/governed-agent paths. Shared transaction/revision/terminal contracts retain each family's evidence requirements, observed-effect publication, local fencing and one catalog workload identity. SDK/legacy/review terminal interruption and retained-history controls also pass. Local fencing is not remote-effect termination; generic extension success is not independent objective verification. |
| 4. Consumer cutover and migration | Current root/store/card controls include copied offline binding, WAL/interruption/conflict and eligible pre-effect continuation/refusal. Fresh actual old-wheel outward histories prove 11 native CLI migrations and seven authenticated composed continuations in each installed cell; originals/snapshots and exact output bytes are retained. Fresh current-artifact history proof also covers four unmarked-turn refusal paths, six SDK/legacy/review histories and pre-revision read/no-op per cell. Distinct family executors keep their documented limits. |
| 5. Conformance by admitted guarantee | Exact full-union identities bind the parameterized common-family tests, native contention/death, dispatch uncertainty, corruption, repeated-decision and result-agreement controls. Outward shared truth replaces its former parallel terminal authority; card completion uses evidence acceptance and common terminal/resource transactions. Migration performs read-only comparisons and one admitted continuation; observed effects reuse publication, uncertain dispatch refuses redispatch. Quickstart and ODR retain their distinct guarantees; neither acquires general recovery or card objective verification from this gate. |

Fresh installed history audit: `history-audit.json` under the same parent,
SHA-256 `9647bb20b3818684a4edfdf71c6bd73198848382c227041b8126a83d85273f64`.
Each cell checks 791 package origins; unmarked histories refuse without model/tool
calls, healthy terminal histories reuse, interrupted histories refuse, and old
revision-free payloads remain unchanged after read/no-op. The initial Windows
launcher containment failure happened before creation/child launch; the unchanged
launcher passed after independent path revalidation. Its cause remains unknown.
The auditor's WSL `/mnt/c` transport error was corrected by reading the same
Windows bytes through native paths, without changing expected hashes.

Fresh outward audit: `outward-history-audit.json`, SHA-256
`b912f76a54c61b69de8a0431ac3c917221dfda06e2258cdc24e6b65f5aa301fa`.
It checks 820 current package origins per cell and actual old-core wheel
`d570f0cd5d17635647198d40027b4653641813123cdf95bf49c59efe7c0b0b54` in isolated
local pip targets. Eleven copied migrations preserve native rows and repeat bytes.
Seven continuations at their original admitted roots preserve approval/recovery
and model/effect-call counts; observed effects invoke nothing, uncertain dispatch
remains unfinished, and application cleanup completes. This is live native CLI,
SQLite/filesystem and composed API proof with controlled model/time, not provider
or every historical dependency-stack proof. Retained failed attempts include a
helper calling bootstrap after loop start and approval refusal after relocating a
copied root (`E_OUTWARD_AUTHORIZATION_POLICY_DRIFT`). The final proof corrects its
setup; it does not weaken policy binding or admit arbitrary relocation.

Positive native and turn/issue fixtures use explicit time; independent request
expiry, lease expiry and reversed-time rollback remain selected. Production clocks
and artifacts are unchanged. Prior failed complete unions and their original
stores remain sealed. Host-clock cause and stock-clock success are unproven; D
owns explicit production inputs. The baseline remains collection-true and
release-ready-false; the dependency check still enforces only transition policy.

This disposition updates current authority, architecture's migration reference,
the family matrix, project registry and roadmap execution note after the sealed
run. Original checkpoint history stays here. The next work is C/D, followed by the
remaining E/CAP prerequisites and whole-lane user acceptance. No commit, tag, push
or release is performed.

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
Policy v2 now implements the cutover; the current repository verdict fails.
The historical v1 transition-policy green is not C conformance evidence.

#### C counterexample preflight: 2026-09-14

The unchanged checker and policy were copied into ten isolated local fixtures,
with source hashes verified before and after actual native checker commands.
The allowed application-to-core control passes and the already-forbidden
core-to-application control exits 1. Eight other fixtures incorrectly exit 0 and
report `ok: true`: adapters-to-application, interfaces-to-adapters,
core-to-services, core-to-platform, runtime-to-interfaces, relative
core-to-application import, dynamic core-to-application import, and unparseable
core source. Evidence: `.tmp/c-dependency-observation/report.json`; helper:
`.tmp/c_dependency_counterexamples.py`. Each fixture retains its copied inputs,
checker JSON and process log. These are structural policy counterexamples through
the real checker command, not runtime conformance or a policy cutover. C remains
open. The replacement must refuse these cases, retain the valid control and fail
closed on discovery/read/parse errors while implementing the three requirements
above; a stronger denylist alone will not satisfy the allowed-edge requirement.

The subsequent read-only Git-visible AST inventory is retained at
`.tmp/c-dependency-observation/layer-boundaries.json`, including hashes of 982
Python modules and the policy/checker/architecture inputs. It records 2,865 local
import observations and 457 modules whose existing labels are outside the five
normative layers. Among the already named layers, 31 imports need explicit
disposition: nine adapters-to-application, 14 interfaces-to-adapters, six
interfaces-to-core and two decision-nodes-to-adapters. The last two require the
architecture's side-effect-classification check; this inventory grants no exception.
Its 126 dynamic-call spelling candidates are not alias-complete enforcement.
Python-encoding-aware parsing also discovers that the old checker's UTF-8-only
AST read silently skips the valid BOM-prefixed `orket/core/domain/reconciler.py`,
including its `orket.logging` and `orket.project_paths` imports. The replacement
must respect Python source encodings and distinguish parse errors from empty
dependency sets. These observations prepare C's cutover; they do not implement it.

#### C allowed-edge implementation and current disposition: 2026-09-14

The v2 policy classifies all 982 Git-visible package Python files among the five
normative layers. It declares allowed edges, exact decision-node contract and
side-effect-free adapter targets, and exact exception metadata. No dependency
exceptions were added. Runtime/orchestration/kernel/services/platform map to
application; module ownership remains distinct from D's purity/effect proof.

The checker, exporter and baseline share inventory, Python-encoding-aware import
analysis and one policy verdict. Source read/parse/discovery or in-scan mutation
failures cannot pass. Relative/member imports, recognized importer aliases,
literal module forwarders and concrete importer namespaces remain visible;
unresolved routes fail explicitly. This is a declared-import graph with
conservative recognized dynamic routes, not an executed call graph or a complete
proof against arbitrary Python reflection. Implicit package-initializer execution
is not modeled as an edge for every absolute import; D still owns import-time
effects and runtime composition proof.

Both `.gitea/workflows/quality.yml` dependency commands use the v2 checker, preceded
by its contract tests. The legacy budget/enforcement options are retired with
their callers. The canonical JSON check result and generated architecture graph
keep observation separate from verdict; successful export or baseline collection
cannot establish conformance. The contract delta is
`docs/architecture/CONTRACT_DELTA_DEPENDENCY_POLICY_C_2026-09-14.md`.

Retained implementation failures include an omitted orchestration classification,
alias assignment mistaken for importer escape, and missing export/parent identity
resolution for existing literal module forwarders. Repairs retained dependency
edges and did not add exemptions. The first four-cell native gate passed 54
contract cases per cell and audited identical observations, verdicts, input hashes
and retained evidence at `.tmp/c-dependency-cutover/audit.json`. Its SHA-256 is
`348024228e8fb0c42bb99b6ee69d49b7dbdd1db829c2fbe863aca91f595493d3`.
That snapshot predates the supplemental importer-namespace controls and is not
the final implementation's source binding.

Follow-up controls exposed nine unreported negative import/reflection routes and
one allowed dependency missing from observation when the importer namespace itself
was loaded dynamically or obtained through `sys.modules`. The original ten test
failures are retained in `.tmp/c-dependency-cutover/namespace-before.xml/.log`.
Namespace identity now survives these concrete routes. The allowed control must
both pass and retain its dependency edge. The revised source gate passes 64
contract cases in `.tmp/c-dependency-cutover/namespace-after.xml/.log`; the fresh
native campaign is `.tmp/c-dependency-namespace/`, with an immutable 1,003-file
harness manifest. All 64 cases pass without failures/errors/skips in each native
Windows/Linux Python 3.11/3.12 cell. Each cell runs real Git, checker and exporter
commands in a fresh copied repository, retains fixture/report hashes and proves
its source inputs unchanged. The same case identities, observations and verdicts
match across all four cells. The audit is `.tmp/c-dependency-namespace/audit.json`,
SHA-256 `c2814ddc333844b3e982f6bac329bc3e55047592d6e05635836b06b3735f071c`.
Every native process returned and all four parent sessions were reaped. These
repository-tool harnesses intentionally omit the repository-wide conftest and
parse package sources; they do not import an installed core runtime as proof.

The repository observation remains 3,101 import sites, zero unclassified modules,
90 forbidden source/target pairs, one cross-layer strongly connected component,
and 11 analysis errors. Five unresolved dynamic imports occur in the legacy
domain alias registration and extension workload loaders; four escaped importer
references occur in extension subprocess guards; two unresolved reflection sites
occur in settings. These need concrete boundary repairs or a proved bounded
resolution, not broad exemptions. The checker exits 1; export exits 0 with an
explicit failed verdict. The actual Quality dependency command remains failed.

Observed path: primary. Result: partial success. Native repository-tool execution
proves its stated fixture contracts; the dependency evidence is structural.
No core/SDK source behavior or package artifact changed during this cutover, and
the sealed scoped BT-5 acceptance audit remains unchanged. C acceptance, D,
E1/E2, CAP-1/2/3, a fresh whole-repository suite, hosted CI, release readiness and
whole-lane user acceptance remain open. Next work must repair the reported
cross-layer dependencies and unresolved boundaries alongside D's pure-core and
explicit-input obligations while preserving the accepted BT artifacts.

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

#### D1 core/effect separation and current proof: 2026-09-14

The three named D1 boundaries are implemented. `FailureReporter.build_report`
constructs explicit-time core values; the application publisher owns the closed
file write and subsequent saved event. Core reconciliation consumes immutable
asset strings and returns proposed writes/adoptions/problems; application owns
collection, application of writes and events, with an explicitly side-effecting
storage adapter. Core ToolGate consumes explicit file facts; application gathers
path, AST and iDesign facts through an owned worker. Governed file adapters receive
the core async validation contract instead of constructing application authority.
Existing concrete runtime consumers now import the application gate.

The contract delta is
`docs/architecture/CONTRACT_DELTA_CORE_EFFECT_BOUNDARIES_D_2026-09-14.md`.
There is no core-to-application forwarding shim for the removed effect APIs.
Board and CLI startup retain admitted workers through cancellation. The failure
clock is supplied at orchestrator composition; this does not migrate every
production clock or complete immutable decision-context collection.

Retained pre-change observation at `.tmp/d-core-boundaries/before-report.json`
shows ambient failure timestamps and a malformed orphan issue reported adopted
without the corresponding target update. Invalid snapshots now fail before plan
application. Per-target replacement compares captured text and verifies persisted
bytes before adoption events. This is not a transaction across two targets or
fencing against concurrent external editors. Filename/payload identity mismatch
in legacy issue assets remains outside the demonstrated idempotence scope.

A parity control also exposed duplicate same-named epic adoption introduced by
the split. Its failing test is retained at `duplicate-before.xml/.log` under that
proof root. The repaired planner retains the prior global-name rule and selects
the first sorted department deterministically across snapshot permutations.
Two epic test constructors also shared a relative database path; both now use
their own temporary roots. The original generated databases and earlier source
results are retained. The corrected run creates no root control-plane database.

| D requirement | Current evidence | Still required |
|---|---|---|
| 1. Three named splits | Pure value/plan/fact contracts; actual application file, adoption and gate effects; changed concrete consumers | Broader installed gate remains open on one Linux 3.11 lease-clock refusal. |
| 2. Explicit inputs and adapter classification | Required report timestamp, immutable asset strings/file facts, classified board storage, injected gate port | Remaining core/application clocks, identity/randomness, environment/provider and decision-context paths; complete adapter classification enforcement. |
| 3. Async reachability and ownership | Board/startup, report publication, reconciliation and AST/iDesign use owned operations | Complete async inventory including extension install/integrity and runtime policy reads. |
| 4. Determinism, real effects and bounded responsiveness | 439 source cases across 39 affected modules; installed effects/refusals and held real workers; responsiveness bound fixed at 0.5 seconds | Resolve the retained installed clock failure; complete concurrent request/timeout/shutdown envelope and remaining core/runtime parity. |

Current source Windows Python 3.11: 439 passed, zero failures/errors/skips,
102.68 seconds after the portable trace-path correction below.
`source-report.json` binds exact identities and unchanged pre-run inputs;
`source-portable.xml/.log` retain execution. The wheel is built from its sdist;
all 986 current package Python files match both archives, and all 999 wheel
package files match source. Wheel SHA-256:
`199da5972e9bae6fbb6fd9bc32860b69cb013b05211428e23d841d50d473dc8c`;
sdist SHA-256:
`5cc2919d92e53145a3036db290d2ef3739f7f4f5b907e8e3cc4042dc55d1500e`.
SDK/reference/starter artifacts are unchanged. Earlier builds remain historical.

The frozen native harness has 1,721 support files and excludes core/SDK source.
Each fresh private environment installs the four declared wheels and explicitly
reuses dependencies from an existing owned environment; seed packages are not
modified. Verification requires actual imported core origins under the fresh
environment, wheel identities, dependency checks and unchanged copied inputs.
The public flow runs actual `orket runtime extensions list` against valid and
malformed boards and checks persisted adoptions plus the existing degraded warning.
The ToolGate audit covers controlled dispatch denial, not provider-backed work.
Both affected Quality jobs include the value/effect tests before dependency
enforcement. Hosted execution and whole Quality acceptance remain unverified.

The first native matrix is retained at `.tmp/d-core-boundaries/audit.json`.
Windows passed 439 cases per cell; Linux passed 436 and failed three per cell.
The actual writer correctly created normalized `issue-1` paths while three trace
tests expected `ISSUE-1`; Windows case-insensitivity masked those test errors.
Their expected paths now match the existing contract. All four original cells
passed actual CLI primary/degraded flows, verified 870 package origins and
retained unchanged fixtures. The fresh `portable/` campaign uses corrected tests
with the same package artifacts; no runtime change was required for that repair.

The refreshed dependency observation is 986 modules, 3,120 import sites,
85 forbidden pairs, one cross-layer SCC and 11 analysis errors, with no unknown
modules. The three splits remove five forbidden pairs from C's dated snapshot;
the checker still exits 1 and no exception was added. D1 does not close C.

The corrected installed matrix completes with 439/0/0/0 pass/fail/error/skip in
Windows 3.11, Windows 3.12 and Linux 3.12; Linux 3.11 records 438/1/0/0.
Its failure is
`tests/application/test_orchestrator_epic.py::test_execute_issue_turn_uses_prompt_compiler_when_resolver_disabled`:
issue closeout refuses a lease publication at
`2026-09-15T02:08:45.146818+00:00` because publication timestamps must increase
monotonically. The actual fixture, SQLite store and traceback remain under that
cell's `harness/results/`. The cause is not established; an unexplained passing
rerun would not establish a repair. All four cells retain 870 matching package
origins, identical case identities, unchanged inputs, actual CLI primary/degraded
flows, strict controlled ToolGate audit success, and no surviving child processes.
Every parent execution returned and its tool session was reaped.

Current partial audit: `.tmp/d-core-boundaries/portable/audit.json`, SHA-256
`36754b245f86f162e184bfa131ee97729e4497a73378f5d0f14aa6e3e5acca09`.
It rechecks retained bytes and exact current package/support inputs. Native JUnit
seconds are 122.942 / 124.987 / 101.964 / 99.701 for Windows 3.11 / Windows 3.12 /
Linux 3.11 / Linux 3.12 respectively. Ruff on the changed Python, docs project
hygiene, new-file/function size checks and diff whitespace pass. Exact checkpoint
files and structural check outputs are in `.tmp/d-core-boundaries/closeout.json`.

Observed path: primary. Result: partial success; current installed gate remains
open. Proof is native installed CLI/filesystem/controlled dispatch and source
integration plus structural contracts/package parity; no new live provider proof
is claimed. The baseline collected successfully with release-ready false. C/D,
E1/E2 and all capability obligations remain open.
Historical C and BT audits bind their original source/artifact snapshots and are
not regenerated to imply acceptance of this new runtime wheel.

At the user's request that session stopped after wrap-up and handoff. The
September 16 continuation below investigates its retained lease-clock refusal
alongside D2's explicit inputs. The historical failed predicate remains retained.

#### D2 issue-dispatch clock input and retained failure diagnosis: 2026-09-16

The original snapshot verified unchanged before edits: working/original/reference
Git heads, status and file bytes; handoff, helpers and proof artifacts all matched.
Snapshot SHA-256: `d6241a53308f0a5b1d29454b6b8a47995ea1385fa05685b45303e3f768bd9642`.
The work continues on `codex/architectural-truth-bt0`, preserving accumulated work.

Read-only inspection of the retained Linux 3.11 SQLite fixture matched its sealed
hash `5bca96bd816b0edc340b4d7f28901cd5d58b30f6c76d5b76ad572b7b65ba372b`.
Admission/active lease time is `2026-09-15T02:08:51.880580+00:00`; refused closeout
time is `2026-09-15T02:08:45.146818+00:00`, 6.733762 seconds earlier. The retained
run/attempt remain executing, the lease active and terminal truth absent.
Independent WSL journal realtime/monotonic observations show an approximately
7.111950-second backward offset change and a 7.186467-second forward change in
that interval. The refused value follows the backward-change event by 0.102338
seconds. Host clock discontinuity is corroborated; the process responsible for
each adjustment remains unidentified. This is not an unexplained passing rerun,
a repaired host clock, or permission to classify all failures as environmental.
Evidence: `.tmp/d-clock-inputs/diagnosis.json` and `host-journal.jsonl`.

A new real-SQLite pipeline counterexample exposed independent D2 drift: supplying
a 2041 runtime clock still admitted issue dispatch using host time. Its failure
and two missing-constructor-input failures remain at `before.xml/.log` in that
proof root. Issue services now require an explicit UTC callable; pipeline wiring
passes the selected runtime clock through the orchestrator. Admission captures
one input; closeout captures one after the writer lock and shares it across the
effect, attempt end and released lease. Closeout effect publication moved into
the existing transaction helper, reducing the oversized service. Explicit
ordered fixtures remain separate from exact historical reversed-input controls.
Contract: `docs/architecture/CONTRACT_DELTA_ISSUE_CLOCK_INPUT_D_2026-09-16.md`.

The source gate covers 570 cases across 54 affected modules, including the prior
439-case D1 selection, pipeline callers, shared turn-clock consumers and new
clock/transaction controls. All pass without failures/errors/skips; changed-Python
Ruff passes and captured Git-visible inputs remain unchanged. It creates no root
test database. Evidence: `.tmp/d-clock-inputs/source-report.json`, `source-3.xml/.log`.
Earlier missing-call and import-lint failures remain retained. Both Quality jobs
include the clock and transaction controls before dependency enforcement.

The new wheel was built from its sdist; all 986 core Python files and all 999
wheel package files match source. The frozen 1,722-file support harness includes
no core/SDK source. Four fresh private installed Windows/Linux Python 3.11/3.12
environments pass the same 570-case selection without failures/errors/skips.
Their JUnit durations are 220.736 / 217.529 / 200.893 / 194.395 seconds respectively;
these are test durations, not capacity measurements. Each cell verifies 870 actual
core import origins, unchanged copied inputs, exact wheel identities, declared
dependencies, retained artifact hashes, actual installed CLI primary/degraded
startup effects and the controlled ToolGate audit. All children and parent proof
processes returned and their tool sessions were reaped.

The independent audit passes at `.tmp/d-clock-inputs/audit.json`, SHA-256
`f5375aaef8d63103ea19e0536ad207457094258a2be494a4b0637517e772c059`.
Core wheel SHA-256: `61273d55e03330c82e38637df80a62f222a79e8474bc09a6a536418745b16fa4`;
sdist: `89a8b6c1631202811a29853d7f4643daf323e99861a45737c24f6aa2ed3b74e5`.
SDK/reference/starter artifacts remain unchanged. This accepts the D1 installed
boundary envelope and scoped D2 issue-clock propagation with its explicit fixture
inputs and separate historical-reversal controls. It does not establish monotonic
host time, automatic clock recovery, whole D2, or new live-provider behavior.
No old audit is reinterpreted as proof of this wheel.

Observed path: primary. Result: success within this scope. Proof is source and
installed local integration, native public CLI startup and retained host evidence,
plus structural package parity. Docs hygiene and whitespace checks pass. The
canonical baseline refresh reports `collection_ok=true`, `release_ready=false`. Dependency
enforcement still reports 85 forbidden pairs, one authority cycle and 11 analysis
errors across 986 files/3,120 import sites, with no unknown modules. C/D, E1/E2,
CAP-1/2/3, full-suite/hosted Quality and whole-lane acceptance remain open.
Next: continue the numbered C/D dependency, remaining explicit-input/decision,
adapter-classification, async-reachability and responsiveness obligations.
The intended delta and retained proof bindings are recorded in
`.tmp/d-clock-inputs/checkpoint.json`; `.tmp/d_clock_checkpoint.py verify` checks
that checkpoint without regenerating the original September 14 snapshot.
During final preservation checks, the reference repository's parent was found
at `C:/Source/Orket-Extensions/` instead of `C:/Source/OrketExtensions/`.
Its branch/hash, administrative entry and all ten recorded source files matched.
`git worktree repair` corrected the stale reference-worktree `.git` pointer;
its four pre-existing edits remain intact. The old pointer is retained at
`.tmp/d-clock-inputs/reference-gitfile-before.txt`. No source was moved or reset.


#### C/D bug-fix phase values and application ownership: 2026-09-16

The September 16 issue-clock checkpoint verified unchanged before this repair.
The next remaining core outward dependency was `bug_fix_phase -> orket.logging`:
its application manager lived in core, read ambient time, saved state and emitted
events. Four retained counterexamples in `.tmp/d-bug-fix-inputs/before.xml/.log`
show implicit model time, missing explicit extension inputs and actual
pipeline persistence using host time instead of its supplied 2041 input clock.

Core now contains only bug-fix values and deterministic rules. Creation requires
`started_at`; extension and expiry require `now`; the initial end derives from
the one supplied start. Application owns the manager, copied candidate state,
configured store read-back and event publication. Pipeline wiring passes both
workspace and runtime clock. Database refusal or mismatched read-back cannot
publish the candidate cache or a success event. The manager serializes its own
transitions; waiting callers remain cancellable and admitted persistence/event
work drains through cancellation or timeout. Existing module aliases now use
explicit module imports, preserving canonical identity. The manager is no longer
exported from core or the deprecated domain package. Migration, enum string
conversion, in-memory mode and concurrency limits are documented in
`docs/architecture/CONTRACT_DELTA_BUG_FIX_PHASE_D_2026-09-16.md`.

The source envelope passes 608 cases from 60 modules with zero failures/errors/
skips (157.478s in JUnit). It retains the prior 570-case issue-clock envelope and
adds core values, legacy module identity, real SQLite lifecycle/reopen, persisted
value/event parity, SQL write refusal and acknowledged-but-missing writes. Real
publication workers remain held through cancellation and timeout while a separate
SQLite read and event-loop turn meet the predeclared 0.5-second bound. A caller
cancelled before manager ownership produces no phase. These are local runtime
and structural contracts with controlled clocks/providers, not new provider proof.
Ruff on changed Python passes; Git-visible inputs remain unchanged during that
source run and no repository-root test database was created.

New wheel/sdist artifacts are under `.tmp/d-bug-fix-inputs/dist/`. The wheel is
built from the sdist; all 987 package Python files and 1,000 wheel package files
match source. Core wheel SHA-256:
`ad61bd4fb3f689169cdbca7c9ed748a0e7a4f846bce12e30727693e29f83afc8`.
Core sdist SHA-256:
`55f8c6ba54b86c78db298f826004118dc370c04061a3419f527a08f6c462b6f1`.
The unchanged SDK/reference/starter artifacts retain their previous digests.
The frozen manifest and 1,725-file support harness exclude core/SDK source.
Source, packaging and verification orchestration reuse the sealed D helpers via
`.tmp/d_bug_fix_gate.py`; results stay under `.tmp/d-bug-fix-inputs/`.

All four fresh native environments pass the same 608 cases without failures,
errors or skips: Windows 3.11 215.488s, Windows 3.12 212.400s, Linux 3.11 205.574s,
and Linux 3.12 198.712s. Each verifies 884 imported core origins in its own installed
environment, exact wheel identities, unchanged support inputs and retained
artifact hashes. The environments explicitly reuse dependencies from the prior
owned seeds through a `.pth`; core and the three companion wheels are freshly
installed. Native roots are `d-core-boundaries-bug-fix-win-py311|win-py312` under
`C:/Users/jonmc/.cache/orket-architectural-truth/` and
`d-core-boundaries-bug-fix-linux-py311|linux-py312` under
`/home/jon/.cache/orket-architectural-truth/`.

Actual installed CLI startup on valid and malformed boards retains D1's expected
primary/degraded observations and persisted adoption effects; the strict ToolGate
audit passes its controlled dispatch flows. All proof parents/children returned,
and the four parent sessions were reaped. The independent read-back audit passes
all source/package/case/evidence bindings at `.tmp/d-bug-fix-inputs/audit.json`,
SHA-256 `49475e8d2c4656a86f62ba0bbca7c6412fdaeac10f7bfcdfa489bbc14960554d`.
Observed path: primary; result: success for this bounded bug-fix/alias repair.
This accepts its scoped value/effect and installed envelope, not all C/D or a
new live-provider guarantee.

The regenerated dependency graph and canonical check observe 987 files/3,132
import sites, 84 forbidden pairs, one authority cycle, 10 analysis errors and
zero unknown modules. One forbidden pair and the unresolved legacy domain
import route were removed without adding an exception. No `orket.core.*` source
has a reported forbidden pair; ambient time and other core effects still exist,
so this is not whole-core purity. Settings reflection and extension import routes
remain unresolved. The checker exits 1; export succeeds with an explicit failed
verdict. Baseline collection succeeds with `release_ready=false`.

Scope limits: a manager lock and read-back are not cross-process fencing or a
transaction joining SQLite to events. A post-commit read-back failure may leave
durable state changed. The shared logger's broader subscriber/secondary-artifact
contract, all remaining D2/D3/D4 requirements, C conformance, E1/E2, CAP-1/2/3,
fresh full-suite/hosted Quality, release readiness and whole-lane acceptance
remain open. Docs hygiene and diff whitespace pass. The original issue-clock
checkpoint and earlier sealed proof remain unchanged; the new intended delta and
evidence are at `.tmp/d-bug-fix-inputs/checkpoint.json`, verified without resealing
by `.tmp/d_bug_fix_gate.py verify`. No commit, tag, push or release was performed.
Next C/D work should address the remaining application-owned port/
record contracts imported by storage adapters and the unresolved settings/import
routes, while retaining the numbered purity, explicit-input and async obligations.

#### C/D governed-agent shared contracts and manual wake commands: 2026-09-16

The previous bug-fix checkpoint's evidence remains byte-identical. Its current
source mismatch is the intended contract relocation below; the original snapshot
and historical handoff were not regenerated. Before continuing installed proof,
all 4,564 recorded source inputs and the three portable source result files still
matched their captured hashes.

Governed-agent invocation/broker ports and wake, schedule and webhook records now
live in `orket/core/contracts/`. The four retired application modules provide no
forwarding shim. All 36 class definitions retain structural AST parity; concrete
authority-guard invocation stays in application. Manual wake commands now enter
the application-owned `GovernedAgentWakeCommands` for repository composition,
ingress, controls and state views. The CLI retains parsing/request decoding, while
receipt time comes from the selected runtime-input owner. Public arguments, JSON
fields, timestamp encoding and persisted schemas retain their existing contracts.
Migration and remaining limits:
`docs/architecture/CONTRACT_DELTA_AGENT_CONTRACTS_C_2026-09-16.md`.

The portable source gate passes 804 unique cases from 90 modules, with no failures,
errors or skips, changed-Python Ruff passing and no root test database. It includes
the prior 608-case regression selection plus governed-agent contracts, repositories,
loops, wake/schedule/webhook flows and a new native wake lifecycle/restart check.
That public CLI check verifies idempotency, wrong-epoch refusal, valid cancellation,
retained action history and independently read SQLite state. A separate integration
check proves application-composed receipt time persists the supplied 2041 clock.

Retained initial failures include incomplete native test arguments, a duplicate
test-module basename, and a test incorrectly expecting the public wake view to
expose receipt creation time. The latter now checks the reopened stored record;
no public schema field was added to satisfy the test. The first broad selection
passed 804 cases with 17 deliberate provider opt-in skips. Its original report
and XML/log remain preserved separately. The 90-module portable selection excludes
those five opt-in modules explicitly; eight llama.cpp cases are assigned separate
serial installed proof, while nine Ollama cases remain unrun nondefault-provider
coverage. These skips are not counted as portable passes.

The source archive and wheel built from it match all 989 core Python files and
1,002 wheel package files. The frozen harness contains 1,727 support files without
core/SDK sources. Current wheel SHA-256:
`10155404e5cb5cd450406362d73b30d95324180c33b7726b4bc78b36ccebb0ff`;
sdist: `1738229b72e4a91e7bce197442020c371f81985af9c1d4f093ef8f226c2a409e`.
SDK/reference/starter artifacts retain their prior hashes. Source, package and
selection evidence is under `.tmp/c-agent-contracts/`.

Four fresh installed Windows/Linux Python 3.11/3.12 cells pass the identical
804-case selection, with no failures/errors/skips. Their JUnit durations are
454.247 / 469.328 / 431.845 / 423.693 seconds respectively; source took 387.048
seconds. These are test durations, not capacity measurements. Each installed
environment verifies 886 actual core import origins, exact wheel identities,
unchanged copied inputs and retained evidence, native CLI primary/degraded
startup effects and the controlled ToolGate audit. The environments install four
exact wheels and explicitly reuse declared dependencies from their owned seeds
through a `.pth`; this is not a claim of four independent dependency resolutions.
Every native parent process returned, tool sessions were reaped, and their
retained reports show no remaining proof children or root test database.

Separate serial proof on the installed Windows 3.11 candidate passes eight actual
llama.cpp cases in 148.386 seconds. Three CLI continuation scenarios, API-owned
wake/memory/replay, approved and denied effects across restart, and two abrupt API
exit/recovery windows retain the exact model identity
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`. This reuses the unchanged sealed family
live driver with newly copied, hash-bound support and reference source artifacts.
The launcher observed 50 native process identities, returned successfully without
timeout and found none still running afterward. Its process observation is
bounded to that proof tree; it is not OS containment or a machine-wide teardown
claim. The documented native llama.cpp operator service remains available at
loopback port 8080 (PID 12704) for ongoing goal work. Startup inventory and its
immutable log snapshot are retained; ongoing server stdout/stderr are explicitly
mutable operator logs excluded from checkpoint hashes.

The independent audit passes at `.tmp/c-agent-contracts/audit.json`, SHA-256
`083b0f650867c0451e3a110060b212211e531b09d338978ec5a6579ed8ff360c`.
It verifies identical source/installed case identities, the tested package and
harness bytes, original artifact hashes, all four native retained-file audits and
the new live-provider proof. The latter's exact scope/bindings are recorded in
`live-provider.json` (SHA-256
`d28bae4e32d006055146dd97c266cd594d7adb9b3f0d48d59bf86c2fbf82b32e`).
Observed path: primary; malformed-board startup is the expected degraded path.
Result: success within this envelope. Proof includes actual installed local
integration/public commands and live provider behavior, plus structural contract
and package parity. It does not reinterpret earlier wheels as current proof.
The subsequent final whitespace gate found two extra newline bytes at the end of
`orket/interfaces/governed_agent_wake_cli.py`. The failed checkpoint remains
unchanged at `.tmp/c-agent-contracts/checkpoint.json`, SHA-256
`6d81672a1a306be330c884db3549d12737e2878504497fa07d180f352f19e89e`;
its preservation/neighbor and docs checks pass, but its whitespace check fails.
The two bytes were removed in a separately recorded correction. The prior wheel's
module equals the retained pre-correction bytes; the corrected module differs
only by that suffix and has an identical location-independent AST. Every other
package source still matches the tested manifest. Seven current-source CLI and
receipt-clock cases pass after the correction, including actual native wake
commands. The 804-case installed matrix and eight provider cases remain evidence
for the original wheel; no replacement package was built after this formatting
change. This explicit distinction avoids claiming byte-identical installed proof
for the corrected source. The next semantic candidate must build its own artifacts.

Current reentry checkpoint: `.tmp/c-agent-contracts-format/checkpoint.json`;
verify with `.tmp/c_agent_contract_format.py verify`. It binds the correction,
current source proof, refreshed canonical observations and all original evidence
without replacing the failed checkpoint. The 66-file relocation delta is listed
in the original checkpoint; the corrective checkpoint records current file bytes.

The refreshed dependency verdict remains failed: 989 files, 3,139 import sites,
74 forbidden pairs, one authority cycle, 10 analysis errors and no unknown modules.
Ten forbidden pairs were removed without an exception. Export succeeds with the
failed verdict; baseline collection succeeds with `release_ready=false`.
The whole C/D, quality, capability, full-suite/hosted CI, release and explicit
whole-lane user-acceptance obligations remain active. Frozen fields still permit
nested mutable mappings, adapter classification is incomplete, and the remaining
governed-agent CLI commands still own concrete repository composition.

#### C/D governed-agent CLI ownership and Git checkpoint: 2026-09-16

The user requested committing the accumulated remediation and pushing
`codex/architectural-truth-bt0` to GitHub, with subsequent verified checkpoints
committed on that branch. Core 0.6.3 and its matching annotated tag follow the
existing contributor policy. This checkpoint includes the accumulated BT and C/D
work; it does not close the lane, merge main or claim release readiness.

Governed-agent CLI now delegates submit, inspect/replay, pause/stop and cancel to
application services. The submission contract copies role pairs and timestamp
sequences; application retains catalog/request workers and provider cleanup,
including a composition failure after provider selection. The public parser,
wire schemas, exit statuses and cancellation uncertainty are preserved. Contract:
`docs/architecture/CONTRACT_DELTA_AGENT_COMMANDS_C_2026-09-16.md`.

The initial 22 focused cases pass, including native submit/reentry/replay,
malformed/missing input refusal, idempotent controls, cancellation uncertainty,
held preparation cancellation/timeout and real HTTP-client cleanup on injected
composition failure. This is actual CLI/filesystem/SQLite proof with deterministic
model fixtures plus controlled integration faults and unit immutability checks;
it is not live model proof. The subsequent source and fresh installed core 0.6.3
envelope passes 811 identical cases from 93 modules, without failures/errors/skips:

| Envelope | Cases | Seconds |
| --- | ---: | ---: |
| Source Windows Python 3.11 | 811 | 372.209 |
| Installed Windows Python 3.11 | 811 | 416.608 |
| Installed Windows Python 3.12 | 811 | 437.227 |
| Installed Linux Python 3.11 | 811 | 365.361 |
| Installed Linux Python 3.12 | 811 | 364.032 |

Each installed cell checks 888 actual core origins, dependencies, exact case
identities, retained inputs, native primary/degraded CLI startup and ToolGate
behavior. Source/package parity covers 991 Python modules and 1,004 package files.
Eight actual installed Windows 3.11 llama.cpp cases also pass in 211.109 seconds:
CLI continuation, API memory/replay, effect restart and abrupt API process
recovery. The observer records 49 process identities and no survivors. The
operator-owned llama.cpp server remains running; its lifetime is separate from
proof children. No provider fallback or new model/containment promotion is claimed.

Evidence lives under `.tmp/c-agent-cli/`: `source-report.json`, `manifest.json`,
`audit.json` and `live-provider.json`. The tested core wheel SHA-256 is
`47807caf0c02181186d8a2034a65281852f13dcacc4824368a759d2302eb6e9b`;
the source archive SHA-256 is
`16ab3a9be7d67448d5468f409f56cb6649342a18706636b3641a49329c31732a`.
Prior manifests, failed observations and neighboring worktrees remain unchanged.
The immutable pre-format checkpoint is `.tmp/c-agent-cli/checkpoint.json`, SHA-256
`9aef645f362fa951a93f4bed06d21b26813b487557cb4dd5a0e162d069bb7aa3`.

Staging all accumulated files exposed trailing-space/EOF findings that an
unstaged tracked-file-only check had missed. The failed staged check remains in
`staged-whitespace.log`. Final cleanup removes only extra EOF newline bytes from
eight Python files and trailing horizontal whitespace from three Markdown files.
All eight Python ASTs are identical; exactly six Python package files and one
packaged Markdown asset change, while all other package bytes match the tested
wheel. Original bytes are retained under `formatting/`. Structural delta proof:
`formatting.json`, SHA-256
`aa54f048c2a691aa6e65b97e650de2179d8a4b618d96b727dbcfefc9476b5d47`.
The 811-case and live results above bind the pre-format wheel; they are not a
claim of live execution of a rebuilt final-format wheel. Git text normalization
is checked separately against the staged index; the publication receipt binds
that result and the exact pushed commit/tag without rewriting old checkpoints.

New command code/tests, the CLI delegation, terminal-control consumer, shared
native helper and wake tests are recorded by the checkpoint inventory. Metadata
changes include the Quality steps, version/changelog, architecture/current
authority, SDK versioning note, command contract and these project documents.
The exact additional formatting files are in `formatting.json`; the Git commit
diff is the complete accumulated file inventory. Observed path: primary, with
expected degraded refusal controls. Result: scoped success with the final
formatting delta verified structurally; whole-plan result remains partial success.

Final staged whitespace and docs project hygiene pass. Ruff passes for the CLI
change. A separate explicit-file check over all 749 staged Python files reports
223 findings (retained in `final-ruff-batches.log`), including older application,
script and test debt. This wider selection differs from the baseline collector's
102-finding scope; neither is green. Its first single-command attempt exceeded
the Windows command-line length limit; bounded batches completed the check.
E1 owns the remaining lint debt. Publishing the authorized checkpoint does not
waive it or the other open acceptance gates.

Dependency collection reports 991 modules, 3,147 import sites, 66 forbidden pairs,
one cross-layer authority cycle, 10 analysis errors and zero unknown modules.
The eight CLI violations are removed without exemptions. Whole C/D conformance
remains red; E1/E2, CAP-1/2/3, fresh full-suite/hosted CI and whole-lane acceptance
remain active. AC-01 is partial for those remaining sites; the touched interface
imports only application contracts. AC-02/03/04/05/07/08/09/10 preserve the named
boundary with the scoped proof above; AC-06 remains partial for the wider adapter
classification work and adds no new adapter or decision-node caller.

### Protocol contracts and ledger ownership checkpoint (2026-09-17)

Core 0.6.3 is published on `codex/architectural-truth-bt0` at
`08a5ae05e7a33f560386acfa1f48baa8e5b6d078` with annotated tag `v0.6.3`.
Its immutable publication checkpoint is `.tmp/c-agent-cli/published-checkpoint.json`
(SHA-256 `9a5ffc4d190ae552bb7923eb8dc5dfe7e836dda81d59c71ee738f7327bd626e7`).
The current 0.6.4 candidate preserves that evidence and continues the full goal.

Protocol hash/invocation/error/result contracts move to core, and operation-commit
persistence moves to storage. All affected callers use canonical definitions.
Registry reads and writes reload under native local ownership; failed persistence
cannot publish an in-memory winner, corrupt rows refuse mutation, and positive
integer sequences are required. Protocol workers retain ownership through
cancellation/timeout, and nested receipt/event/start/finalize input values are
captured before awaiting. Receipt file I/O has a dedicated storage owner.
Migration and scope limits:
`docs/architecture/CONTRACT_DELTA_PROTOCOL_LEDGER_CD_2026-09-17.md`.

The retained initial eight counterexamples fail before repairs (worker lifetime,
receipt capture, stale writer, persistence failure and malformed history). Three
additional event/summary input counterexamples fail before capture is repaired.
Four invalid-sequence counterexamples fail before strict integer validation.
The final focused regression is 76 passed, without failures/errors/skips, in
6.65 seconds. These include actual local files and independent Python processes;
held-worker/failure controls do not claim live model or hostile-host containment.
Observed path: **primary**; result: **success within this checkpoint**.
The user requires local commits only during 10 AM-6 PM America/Denver work hours.
This checkpoint's commit and annotated tag are retained locally; GitHub push is
deferred under that instruction. Core 0.6.3 remains the last published checkpoint.

The source and four installed proof unions cover the same 1,156 unique cases
from 136 modules, with no unresolved failure, error or
unexecuted selected case. Each installed union combines a retained full selected
run with a fresh 19-case follow-up after two clock-fixture corrections, using the
identical runtime wheel. These are scoped regression unions, not new single
full-suite executions:

| Envelope | Passing cases | JUnit seconds |
|---|---:|---:|
| Source Windows 3.11 union | 1156 | 353.711 + 0.217 + 40.077 + 3.565 |
| Installed win-py311 union | 1156 | 320.611 + 3.761 |
| Installed win-py312 union | 1156 | 339.503 + 3.704 |
| Installed linux-py311 union | 1156 | 394.440 + 5.759 |
| Installed linux-py312 union | 1156 | 391.177 + 5.609 |

The initial source execution passed 1,148 cases and skipped eight script
cases because their existing one-shot opt-in was disabled. Its original report
and JUnit remain retained. A focused follow-up executes exactly those eight with
`ORKET_INCLUDE_ONE_SHOT_SCRIPT_TESTS=1`, preserving all frozen source bytes.
A 75-case source run covers all three modified fixture modules and the
existing deadline/expiry controls. Only these three test modules and one new
fixture helper differ from the initial source observation; all other inputs
remain bound to it at that intermediate observation. A final 19-case source run
covers both subsequently corrected protocol clock-fixture modules. The source
row combines these observations with explicit rerun overlap. All installed full
selected runs use the one-shot opt-in from the start. Three pass all 1,156;
Linux 3.11 passes 1,154 and retains two timestamp failures described below.
The 19-case follow-up passes on all four fresh installed environments. Its
manifest differs from the full selected run in exactly the two test files;
runtime, package artifacts and every other harness input are unchanged.
These script fixtures are controlled contract evidence, not operator sign-off.

Each full installed cell checks 901 core origins (647 in each focused
follow-up), identical case identities,
wheel/dependency identities, unchanged copied inputs, actual valid/malformed-board
CLI flows, ToolGate denial and absence of surviving child processes. Independent
native registry processes exercise contention, owner release and same/different
operation retries on both hosts. Package parity covers
993 Python and 1006
packaged files with no missing/stale sources. The three unchanged pure contracts
also have AST parity after canonical import mapping; the additive registry error
family is exercised by the negative paths.

The original candidate's actual installed Windows 3.11 llama.cpp proof passes all eight cases in
159.165 seconds, covering CLI continuation, API memory/replay, effect
restart and abrupt API recovery. Its 48 observed
process identities have no survivors. This does not establish additional provider
promotion, all-host model proof, containment or machine-wide process teardown. The corrected harness reuses this unmodified
wheel/provider proof; it is not a second model execution.

Initial installed observations remain retained: Windows 3.11/3.12 and Linux 3.11
each failed three governance cases; Linux 3.12 also failed two native subprocess
cases. Actual gate diagnostics identify missing repository boundary files and
two documents in the harness. Those tests now consume isolated copies of actual
installed boundary files and explicit repository documents/root wrappers; copied
core files are never added to the import path. Negative checks remain enabled.
The two subprocess cases retained eight-second UTC deadlines while the host
journal records +12.099067-second and +10.719453-second offset changes in their
failure interval. They now select the existing elapsed-clock fixture for parent
and child, retaining native waits and unchanged budgets. Independent expiry and
clock-jump refusal cases remain in the union. The clock-adjusting process and
stock-clock success are not established. Exact evidence: `native-diagnosis.json`.

The corrected full Linux 3.11 run then retained two
`E_LEDGER_TIMESTAMP_NON_MONOTONIC` failures: pipeline terminal-failure finalization
and projected receipt materialization. The pipeline fixtures now share one
explicit `ProtocolLedgerClock` between pipeline runtime inputs and the ledger;
the projected ledger also receives an explicit clock. The final 19-case runs
exercise both affected modules without changing runtime refusal semantics or
the wheel. The failed run remains sealed in `corrected/`; its remaining 1,154
passing cases are bound by identity, input hashes and artifact hashes. Derived
summary/graph publication before a refused final ledger event remains a known
multi-file atomicity limit; this checkpoint does not claim to repair it.

Evidence under `.tmp/c-protocol-ledger/` (full corrected matrix under `corrected/`,
focused follow-up and union audit under `final/`)
includes source reports/JUnit, opt-in
supplement, package manifest, native audits and live-provider proof. Core wheel
SHA-256: `f332b235e06c227ec983ff7b3b956599c4716c71514df5f7a0f1845f569b895e`;
sdist: `ab820750568450238f8ef0cc43487dd50e9103e38febc41bc81a63f7ce8b44c0`.
Union audit SHA-256: `96352cbd4b345be5dad1e7e7182ab8de211a325884588becc5e47ab5e1289b09`;
19-case audit: `89d5f26e71f401cfa0edfdf67b4a7e4d6fccc3fe319a431f456ac729705bb72c`;
manifest: `a6e4436b340b2c782d3cb2596a8750f4dad7652b137db87c4475bf0edc64031e`;
live-provider report: `994f7250cb9a69f9f444eef4c33d269b95cc3622974dcd17950c0b2a3b8860a5`.
`final/union-audit.json` binds the retained full runs, current follow-ups and
unchanged sealed evidence to this scope. The reused generic auditor's earlier
relocation prose is not a broader scope claim. The eight-case provider execution
belongs to the original candidate and is explicitly reused on the identical wheel.

After execution, one missing `Layer: integration` comment was added to the
pipeline receipt-materialization test. `final/annotation.json` binds its exact
before/after hashes to the frozen harness and verifies identical Python ASTs.
This final annotation has structural proof only; executable test statements and
assertions are unchanged. The runtime and installed artifacts remain identical.

Architecture checklist: AC-01 remains **partial** because repository dependency
conformance is red (58 forbidden pairs, one cross-layer cycle and ten unresolved
import/reflection errors across 993 modules and 3,155 import sites; no unknown
modules). This removes eight forbidden pairs without adding an exception.
AC-02/03/04 pass for the unchanged pure contract computations and captured inputs,
while broader decision-node/clock purity remains D work. AC-05/06 pass for the
new declared storage owners and retained worker calls. AC-07/08/09 pass for the
scoped first-winner, preserved schema/hash and replay regressions; multi-file
atomicity and hostile-writer guarantees are not claimed. AC-10 passes with the
same-change contract/authority pointers and both Quality commands updated.

Changed-file Ruff passes. The broader baseline still reports 94 findings in its
canonical lint scope, 70 oversized Python files, 225 oversized functions and
3,296 missing layer labels under the existing noisy taxonomy checker. These are
remaining E1/E2 work, not green quality evidence. The protocol repository shrinks
to 705 lines but remains oversized. Full C/D, E1/E2, CAP-1/2/3, fresh full-suite,
hosted CI, release readiness and explicit whole-lane acceptance remain open.

### Dual-ledger application authority and recovery candidate (2026-09-17)

The preceding protocol checkpoint is retained locally at commit
`d338d48c4505431feca1824792ec347668e3f70f`, annotated tag `v0.6.4`.
Its current reentry snapshot is `.tmp/c-protocol-ledger/final/local-checkpoint.json`
(SHA-256 `16fe68cc2bb2fee5322110463a628a9ec235297045675a0134cce6796351d06e`).
The snapshot and retained evidence were verified before this candidate changed
source. Nothing from that sealed proof is rewritten or relabeled as this candidate.

Read-only review of the remaining adapter-to-runtime parity dependency exposed
dual-ledger recovery defects. Ten real-filesystem/SQLite/protocol counterexamples
fail against the committed implementation: empty or invalid journals disappear,
databases share a parent journal, acknowledgement bits and row existence hide
content drift, conflicting starts overwrite SQLite, nested caller inputs change
after admission, and cancellation abandons the lifecycle. Original tests, runtime
source, JUnit and log are retained in `.tmp/c-dual-ledger/before.json` and its
hashed evidence. No mocked successful write is used as proof of durable effects.

The candidate moves lifecycle/recovery authority into application services and
separates pure intent validation from a bound storage journal. Every invocation
rechecks durable pending state under cooperating native ownership of both the
database journal and protocol root. Backend content must match before recovery
clears intent; conflicting content and success-shaped returns without effect
refuse. Nested inputs and admitted task lifetime remain owned through interruption.
Migration, explicit degraded behavior, legacy refusal and claim limits are in
`docs/architecture/CONTRACT_DELTA_DUAL_LEDGER_CD_2026-09-17.md`.

Observed path: **primary**; result: **partial success; installed gate open**.
The corrected source Windows 3.11 gate passes 1,193 selected cases from 141 modules
in 306.88 seconds. Its fresh private environment installs the corrected candidate
so sanitized subprocesses use that same wheel while their parent runs source.
Changed-file Ruff and unchanged-input binding pass. All 997 core Python files and
1,010 package files match the wheel built from its sdist. The corrected wheel is
`3cadea5b6917374fed14387cfbaf3852066ca62c9810f9d7766d4017611e4eba`;
sdist `bc33db9a0759a37c06674cc86f19dfd77e90ca410aeb7216462c1fd315715859`.
Eight fresh actual installed llama.cpp cases pass on this corrected wheel with
observed teardown; the operator's llama.cpp service remains running.

Four corrected native envelopes check installed origins, unchanged support,
real valid/malformed public CLI paths, strict ToolGate audit and process cleanup:

| Envelope | Pass / fail / error / skip | Seconds |
|---|---:|---:|
| Installed Windows 3.11 | 1,185 / 0 / 0 / 8 | 335.512 |
| Installed Windows 3.12 | 1,185 / 0 / 0 / 8 | 354.090 |
| Installed Linux 3.11 | 1,184 / 1 / 0 / 8 | 486.167 |
| Installed Linux 3.12 | 1,184 / 1 / 1 / 8 | 473.403 |

The eight skipped script cases were an invocation error: the native commands
omitted `ORKET_INCLUDE_ONE_SHOT_SCRIPT_TESTS=1`. A fresh eight-case supplement now
passes on every OS/Python cell with that flag, identical package/support bytes,
real CLI checks and retained native teardown. Source proof for those eight cases
is explicitly reused from the successful 1,193-case run; provider proof is reused
from the identical corrected wheel. This is not a new complete native rerun.
The resulting Windows unions cover all 1,193 unique cases. Linux retains one
unresolved normal approval/resume case per cell; Python 3.12 also records its
teardown assertion because only the first of two expected children was reached.
All observed children nevertheless stopped, as checked by the independent driver.

Retained SQLite state records `E_SDK_AGENT_FRAME_READ_TIMEOUT`: Linux 3.11's
second invocation and Linux 3.12's first invocation became recovery pending.
Their exact JUnit case times are 9.711 and 8.260 seconds. A separate installed
Linux 3.11 normal-case probe passes, and an instrumented six-case Linux 3.12
module rerun passes normal resume, delayed startup, handshake expiry and explicit
UTC-jump controls. Six further instrumented normal-case repetitions pass on each
Linux Python version. Those passing reruns do not establish the original cause or
close this failure. The retained host journal contains clock-change events, but
these fixtures already use elapsed monotonic inputs; correlation does not prove
causation. Do not widen the eight-second request budget or relabel this as an
explained environment failure. Investigate the retained deadline/stdio paths
before accepting the installed candidate.

Current disposition: `.tmp/c-dual-ledger/current-disposition.json`, SHA-256
`1466b431a21b450886add67fc4c894c1c4cf8dbef870aad82c9a34a2ed5be176`.
Full native/source/provider evidence is under `corrected/`; the eight-case
supplement is under `scripts/`. Actual native report files retain physical
fixtures, logs, JUnit, imported origins and hashes. Every proof process returned
and its execution session was reaped. Proof includes real filesystem, SQLite,
subprocess, CLI and provider behavior plus structural contracts, not full-suite,
hosted CI or whole-lane acceptance.

Initial candidate evidence remains sealed at `initial-candidate.json` in that
proof root (SHA-256 `fc2a3e8903f959ba578d5e23b8275e2afdc88424ab39b4284c121c08efc54207`).
Its four installed cells failed the new worker tests because foreign-cwd workers
could not import copied test support. They now load that support explicitly and
check that child and parent select the same core origin. Its Linux 3.11 summary
retained `run_summary_duration_negative`; that positive fixture now supplies one
explicit clock to ledger and pipeline, preserving negative-clock refusals.
An initial Windows crashing-child timeout prompted eight diagnostic probes;
all separately exposed fatal buffered-stdin shutdown lock aborts. A new regression
fails on the original installed wheel. The corrected child reads its raw input
descriptor on the existing dedicated thread, and the regression requires exit 1,
retained workload diagnostics and no fatal interpreter abort. This crash/teardown
case passes in source and all four corrected installed cells. The original Windows
timeout lacked retained child stderr, so its exact attribution remains unproven.
The first source crash follow-up still launched an older installed child through
its sanitized environment and failed; those logs remain, and the corrected source
gate explicitly binds a fresh child environment instead.

The ten original recovery counterexamples were also independently reproduced on
installed 0.6.4, retaining physical files/SQLite under `before-retained-fixtures/`.
`before-retained-validation.json` verifies original runtime/test bytes and case
identities. This is a separate reproduction, not a claim that the first run's
default temporary directories were preserved. Earlier 55/31/4-case source reports
bind intermediate implementations only. No failed envelope is overwritten.

The regenerated graph now has 997 modules, 57 forbidden pairs, one cross-layer
cycle and ten unresolved analysis errors; collection succeeds, conformance fails.
Removing the dual-ledger adapter-to-application edge does not close C or prove
whole-core purity. D's remaining inputs/async inventory, strict legacy migration,
quality/capability gates, fresh full-suite, hosted CI and whole-lane acceptance
remain open. Core `0.6.5` is retained as a local candidate checkpoint; its installed
gate is not accepted. Work-hours
commits/tags remain local; no GitHub push is authorized during 10 AM-6 PM Denver.

Remaining authority drift found during this review: the `dual_write` settings
label in `orket/application/services/runtime_policy.py` claims protocol primary,
while `orket/runtime/config/runtime_context.py` defaults to SQLite primary and
no caller overrides that default. The constructor's existing default is retained
in this candidate. `.tmp/c-dual-ledger/observed-authority-drift.json` binds the
observation to source hashes. This display/authority disagreement remains C/D
work; it is not accepted as accurate operator guidance.

### Governed native invocation lifetime candidate (2026-09-17)

The prior local 0.6.5 checkpoint remains preserved: commit
`c399d7523c59faff610188029b5098359cb2a96d` and local snapshot SHA-256
`23ee3a44cb67707f206115aaf13268771f9703d313d6b866ab0d2718e12a3ed9`.
The initial working inventory and retained evidence matched that snapshot before
this candidate changed anything. Work-hours commits and tags stay local.

Three real-child counterexamples retained in `.tmp/d-agent-lifetime/before.json`
showed abandoned native ownership during registration, interrupted launch and
repeated teardown cancellation. A separate operator test observed a false stopped
acknowledgement while launch was pending. Intermediate admission checks additionally
observed a duplicate reporting the existing child as stopped and a child receiving
a caller-mutated cancellation reason. Those failed observations remain retained;
the extra operator observation lacks a full contemporaneous test-file byte copy.

Application now registers a process owner before native launch, retains launch
until its handle is captured, and drains teardown through repeated cancellation.
Duplicate and pending-launch observations do not assert unverified teardown;
operator payloads are captured before awaiting; failed cleanup retains the owner
and propagates its error. An invoker binds to its first event loop and refuses
foreign-loop control. Migration and limits live in
`docs/architecture/CONTRACT_DELTA_AGENT_INVOCATION_LIFETIME_D_2026-09-17.md`.

Current candidate: core 0.6.6 with unchanged SDK 0.7.0a1. The latest targeted run
passed eight native lifetime cases and six protocol-vocabulary cases. An earlier
intermediate repair passed 20 related subprocess, loop, failure and approval/resume
cases. Fresh source, wheel, installed and provider proof are recorded below.
The generated graph observes 998 modules, 3,177 import sites, 57 forbidden pairs,
one authority cycle, ten analysis errors and zero unknown modules. Collection
succeeds; the dependency verdict and release readiness remain false.

Current candidate verification covers the same **1,201 selected cases** in
source and all four installed Windows/Linux Python 3.11/3.12 environments through
retained full runs plus a 28-case clock-fixture follow-up. This is an explicit
proof union, not a new single all-green full execution. The one-shot script flag
is enabled in every native command; no skipped case is counted as passing.

| Environment | Retained full pass / fail / error / skip | Full seconds | Follow-up pass / fail / error / skip | Follow-up seconds |
| --- | --- | --- | --- | --- |
| Source Windows 3.11 | 1201 / 0 / 0 / 0 | 308.748 | 28 / 0 / 0 / 0 | 17.462 |
| Installed win-py311 | 1201 / 0 / 0 / 0 | 340.025 | 28 / 0 / 0 / 0 | 19.679 |
| Installed win-py312 | 1201 / 0 / 0 / 0 | 359.342 | 28 / 0 / 0 / 0 | 18.339 |
| Installed linux-py311 | 1200 / 1 / 0 / 0 | 340.877 | 28 / 0 / 0 / 0 | 28.05 |
| Installed linux-py312 | 1201 / 0 / 0 / 0 | 339.151 | 28 / 0 / 0 / 0 | 27.248 |

The current union audit is `.tmp/d-agent-lifetime/clock-final/union-audit.json`,
SHA-256 `870273da1c3b04f40a830e5710277fd6e05dab91020169f7cee3756c10eb737b`. It proves only the provenance fixture
module changed, the packages and input inventory are identical, all previous
failures fall within the rerun module, and every retained native artifact matches.
Fresh installed environments verify actual package
origins, identical support/case inventories, public CLI success and malformed-board
semantics, strict controlled ToolGate behavior, retained artifact hashes and no
remaining child processes. Source includes real filesystem, SQLite and native child
execution with controlled provider/clock fixtures; it is not provider proof.

The retained Linux 3.11 full run failed
`test_run_ledger_records_artifact_provenance_for_generated_files`: the ledger
refused receipt materialization with `E_LEDGER_TIMESTAMP_NON_MONOTONIC` after a
10.220880-second backward timestamp observation. It retained only three ledger
events and no finalized summary. `.tmp/d-agent-lifetime/clock-diagnosis.json`
binds the actual log, failed report and pre-change test bytes; the native report
binds the framed ledger bytes. Correcting only that one test subsequently exposed
the same refusal in Linux 3.12's missing-source-receipt narration test: session-start
log time `2026-09-17T18:44:10.683156+00:00` preceded failure log time
`2026-09-17T18:43:59.997010+00:00`. That intermediate 28-case run and its retained
native artifacts stay bound by `clock-fixture/retained.json` and the final
`clock-final/intermediate-retention.json`.

The module's 23 pipeline constructions now use one explicit test builder sharing
`ProtocolLedgerClock` with each pipeline and its selected protocol repository.
SQLite selections remain SQLite. Existing assertion ASTs are unchanged; runtime
code and the timestamp invariant are unchanged. The existing oversized test file
shrinks from 1,967 to 1,848 lines. Host-clock stability
remains unproven. This fixture repair does not explain the older elapsed-clock
Linux approval/resume deadline failures.

The wheel is built from the sdist with parity for all 998 core Python files and
1,011 wheel package files. Wheel SHA-256:
`ff5d81ca3a7dfe725826afe65a0d8227c2bdcfdb00a6374d8dce129d35fb60e7`; sdist SHA-256:
`b6b49f115bb0cee58bb18b980a97844b78d87b50cea9547632e4c0b6a0e44496`. The harness has 1,747 support files without core/SDK
sources. SDK 0.7.0a1, reference 0.3.0a1 and starter 0.3.0a1 artifacts are unchanged.

A separate serial run on the installed candidate passes eight actual llama.cpp
cases in 141.125 seconds: CLI continuation, API memory/replay, effect
restart and abrupt API-process recovery. The live report binds served model,
candidate wheel, actual installed origins, support and artifact bytes. All observed
proof parents/children are terminal and reaped; the operator provider stays running.
This is one Windows 3.11 provider envelope, not provider/host promotion.

Changed-file Ruff, staged whitespace, documentation hygiene and release metadata
checks pass at the local checkpoint. Structural compliance review is retained in
`.tmp/d-agent-lifetime/review.json`; existing D2 clock/environment and wider adapter
classification/recovery obligations stay partial. This candidate adds no forbidden
dependency pair. Full-suite, hosted CI, release and whole-lane acceptance remain open.

The preceding 0.6.5 Linux approval/resume deadline failures remain unexplained.
These independently reproduced ownership repairs do not establish their cause or
close their acceptance gate. Constructor path resolution, ambient runtime clocks,
environment capture, dynamic extension loading, stronger containment, complete
D3/D4 coverage, C conformance and later full-plan gates remain active obligations.

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
python scripts/governance/check_dependency_direction.py
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
Follow contributor version/changelog/tag policy when committing. The user has
requested a versioned GitHub checkpoint and continued commits on the existing
branch; its proof and publication disposition are recorded in the C/D checkpoint.
The later user instruction restricts 10 AM-6 PM America/Denver work hours to
local commits only. Retain commits and matching annotated tags locally during
that window; do not push to GitHub. The 0.6.4, 0.6.5 and 0.6.6 local checkpoints follow this
restriction; remote publication remains deferred.

Remaining blockers or drift after scoped BT-1 through BT-5 acceptance:

- SR-01 through SR-09 and SD-02/SD-05 pass their scoped behavioral gates. The
  other four self-deception findings and the two capability findings
  remain open.
  Architecture, async, quality and authority debt remains; exploration-safe
  limitations keep their current claim ceilings.
- Original SR-01 through SR-04 regressions now pass, including authenticated
  endpoints, independent processes, drift refusal and effect crash boundaries.
  Explicit pre-intent recovery now passes its process/migration envelope.
  Durable ready/observed admission and explicit fenced model-owner recovery now
  pass their local process/migration envelope. Prior provider cost/execution stays
  unknown. The fixture byte-conversion defect is repaired against the retained
  digests without resealing. The primary llama.cpp approved-write proof now passes;
  the canonical full suite passes after the portable-suite failures were repaired.
  The independent decision races, physical target replacement, cancellation and
  a fresh Linux editable install now pass their bounded envelopes. Wheel builds
  and the complete 194-case BT-1/BT-2 installed API/process/migration envelope now
  pass on Windows and Linux with Python 3.11/3.12. A repaired installed Windows
  Python 3.11 wheel also passes the live llama.cpp application proof and a separate
  authenticated TCP/API proof with confirmed shutdown. Wider provider, host and
  external-effect guarantees remain unverified. See the closure audit for scope.
- The worktree now includes main 0.6.2 and preserves its completed provider lane.
  Legacy history is quarantined from reentry, denial continuation and expiry;
  quarantine is the selected migration disposition and old-run replacement is
  unsupported. Paused cloud
  work, formal-proof extensions and other lanes are not reopened here.
- OS isolation feasibility, remote idempotency, supported-host acceptance and
  performance thresholds remain work in their named slices.
- Native BT-2 corruption/completeness repairs and copied legacy migration now
  pass their bounded Windows/Linux envelopes, including corruption refusal,
  process interruption/restart and actual resource-limit extremes. The retained
  live-provider proof database also imports successfully without redispatch.
  Scoped installed-build/host acceptance now passes; this does not close the
  full plan or imply generic exactly-once effects or historical authenticity.

Next action: investigate the retained Linux approval/resume deadline failures in
the dual-ledger candidate before accepting its installed gate; then continue C/D
from their numbered requirements and retained dependency counterexamples. Scoped BT-5 acceptance is recorded in the five-requirement
disposition above; preserve its exact artifacts, original failures and family
ceilings. C now has one allowed-edge policy, complete classification and exact
exception enforcement; its current repository verdict is red. Repair its 57
forbidden pairs, cross-layer cycle and 10 unresolved import/reflection sites,
retaining adversarial positive and negative proof. D owns remaining clock/core/async work. Thirty later numbered obligations,
full-suite/hosted quality proof and whole-lane user acceptance remain active.

The final BT-3 audit accepts builtin evidence-based completion and scoped replay.
It preserves the initial installed failures, corrected external fixture coverage,
controlled publication-clock refusal and the live guard report's event-scope
error. The original Linux timestamp reversal remains unexplained under C/D clock
drift. Full source passed 5,429/81 skipped before three nonbehavioral cleanup edits
and the later test-only clock correction; focused source and all affected
installed follow-ups cover those deltas. This does not claim a fresh all-green
702-case installed rerun or repository-wide release readiness.

Unknown post-initialization workload ownership, post-effect/unmarked approval
reconciliation, old custom/global stores, separate journals and custom-writer
authority remain required recovery/convergence work under BT-4/BT-5 and the
capability gates. Their current disposition is refusal of unsupported takeover
or success. Retained guarded pre-effect and exact-commit export recovery remain
bounded by their existing contracts; they do not authorize arbitrary redispatch.

Preserve BT-1's atomic event/publication boundary, accepted BT-1/BT-2/BT-3 behavior,
all original failure evidence and legacy quarantine. Wider outward autonomy still
requires the ordered workload, containment and capacity gates. The whole lane
remains active. Branch checkpoint publication does not imply lane or release acceptance.
