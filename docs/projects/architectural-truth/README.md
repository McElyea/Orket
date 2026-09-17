# Architectural Truth

Date: 2026-07-29
Last updated: 2026-09-16
Status: Active project registry
Owner: Orket Core

Current gate: scoped BT-1 through BT-5 are accepted. C/D dependency enforcement,
core purity, explicit inputs and async safety are next, followed by E1/E2 and the
gated capability obligations. The whole lane remains active.

C's v2 allowed-edge implementation replaces the transition denylist. The checker,
exporter and baseline share one Git-visible import inventory; repository violations
remain explicit failures. Conformance and the full C/D gate remain open in the
canonical plan. The v1 legacy-budget command is retired.

D1's three named core/effect splits are implemented: failure values, structural
plans and ToolGate facts are pure inputs/outputs; application owns their effects
and validation workers. The September 16 D1/issue-clock envelope passes 570 cases
in source and all four installed Windows/Linux Python 3.11/3.12 cells. The retained
clock refusal is corroborated by the host journal; explicit pipeline clock
propagation now has ordered and exact reversed-input proof. Remaining D2-D4 and
dependency failures keep the full C/D gate open. Exact proof is in the canonical
plan; current core/effect contracts and migration are recorded in
`docs/architecture/CONTRACT_DELTA_CORE_EFFECT_BOUNDARIES_D_2026-09-14.md`.

The subsequent bug-fix phase repair moves its manager into application, makes
core time inputs explicit, verifies configured persistence before events and
retains admitted effects through cancellation. Source and all four installed cells
pass 608 identical cases. Explicit legacy module imports preserve identity;
one forbidden pair and one unresolved import route are removed. Current C
conformance at that checkpoint failed with 84 forbidden pairs, one authority cycle and 10
analysis errors. Migration and limits:
`docs/architecture/CONTRACT_DELTA_BUG_FIX_PHASE_D_2026-09-16.md`.

The subsequent C/D repair moves governed-agent shared contracts into core and manual
wake command ownership into application. Source and four installed environments
pass 804 identical cases with no failures/errors/skips; package parity and eight
separate live llama.cpp cases pass. Current dependency conformance fails with 74
forbidden pairs, one authority cycle and 10 analysis errors. Exact evidence and
limits are recorded in the canonical plan and
`docs/architecture/CONTRACT_DELTA_AGENT_CONTRACTS_C_2026-09-16.md`.
The final two-byte EOF correction has seven passing current-source cases and
structural AST parity; installed/provider evidence retains the original wheel's
exact bytes. The failed whitespace checkpoint is preserved separately.

The next C/D candidate moves remaining governed-agent CLI coordination into
application, removing eight forbidden pairs (66 remain). Source and four fresh
Windows/Linux Python 3.11/3.12 installations pass 811 identical cases; eight
actual installed llama.cpp cases and native cleanup pass. The final accumulated
staged-whitespace cleanup has exact byte-delta and Python AST parity proof;
installed/live evidence retains the pre-format wheel. Exact evidence and limits
are recorded in the canonical plan.
Core 0.6.3 is the user-requested accumulated GitHub branch checkpoint, with
subsequent verified checkpoints committed to `codex/architectural-truth-bt0`.
This preserves the full goal and its remaining acceptance gates.

BT-5's five-requirement disposition is in the canonical plan. The sealed audit at
`.tmp/bt5-family-composed-clock/gate/audit.json` binds 2,321 identical cases across
source and four installed Windows/Linux Python 3.11/3.12 environments, with no
failures, errors or skips. It binds unchanged package sources, retained actual
llama.cpp card/ODR and Gitea proof on the same core wheel, plus fresh installed
historical reuse/refusal and outward upgrade proof. The family chains and their
limits are in `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`.

Selected positive native and turn/issue fixtures use explicit time; independent
expiry and reversal controls remain. This is not a stock-clock guarantee or an
explanation of earlier host-clock observations. Unsupported historical takeover,
arbitrary relocation and remote fencing remain outside the admitted contracts.
Full-suite, hosted CI, quality, capability, release and user whole-lane acceptance
are still required. Original failures and checkpoint scopes remain in the plan;
the older project history below is not the current execution disposition.

Historical execution notes: Slice A and Slice B remain complete. The canonical plan
addresses all 18 September behavioral-review findings. BT-0 counterexample and
contract preparation, followed by BT-1 authorization/effect repair, precedes the
remaining Slice C/D/E work. Broader verified workloads, separately admitted OS
containment, and capacity proof follow their prerequisite gates. This revision
has implemented BT-1 decision transactions, immutable bindings, durable dispatch
claims and journal-backed receipt publication. The original SR-01 through SR-04
regressions pass, including process restart and actual command effects. Explicit
pre-intent owner recovery now fences a live old worker and retains shared
recovery/operator records. Durable model admission now resumes ready or observed
work after restart and publishes a retained result without another provider call.
Explicit model recovery now admits a fenced replacement while retaining the old
attempt and its isolated evidence. The worktree now includes main 0.6.2. Legacy
generation-0 histories refuse reentry and denial continuation; unbound pending
proposals retain their old statuses through queue reads and expiry sweeps.
Quarantine is the selected legacy migration disposition; old-run replacement is
unsupported. The primary llama.cpp approved-write proof now passes after outward
tool transport was aligned with its resolved profile. Repository-owned inventory
and tracked prompt thresholds remove ignored local test prerequisites. The canonical
suite passed at BT-1/BT-2 closure with copied migration and the Python 3.11
cancellation repair (4,827 passed, 74 skipped). Bound filesystem handles now prevent the
reproduced post-intent target redirection, and independent approve/approve,
approve/deny and approve/expire races pass. A fresh Linux editable install passes
the outward regression envelope; the installed matrix is recorded below.
BT-2 now repairs its nine opening storage failures through atomic append
commitments, read-only complete snapshots and serialized audit IDs. Native proof
includes concurrent appends, external prefix anchors, caller payload capture and
Windows/Linux API/CLI paths. Copied legacy migration now retains complete SQLite
backups, validates original hashes, requires explicit unsealed disposition and
preserves legacy quarantine. Real process interruption/restart and the actual
100,000-event/64 MiB boundaries pass on Windows and Linux. The retained database
from the earlier live provider proof also imports into a verified inactive copy
without redispatch. Fresh wheels and Windows Python 3.12 installed demo,
quickstart and copied migration paths pass from a foreign working directory.
The full 194-case outward API/process/migration envelope now passes against
installed wheels on Windows and Linux under Python 3.11/3.12, with runtime source
excluded from the test harness. The repaired wheel also passes live llama.cpp
application and authenticated TCP/API proofs with confirmed teardown. SR-01
through SR-06 pass their scoped behavioral acceptance gates. BT-3 now has a
read-only replay repair with independent step counts and input-digest checks.
The final 44-case installed replay/import envelope passes on Windows/Linux
Python 3.11/3.12 after fixing a reproduced POSIX Python 3.12 import-hook recursion.
The repaired wheel also passes live llama.cpp with two matching decisions and
six measured receipts. Replay resource limits refuse partial comparison.
SD-02 passes scoped acceptance. The final BT-3 audit below now also accepts
builtin card completion; earlier checkpoint limitations remain historical.
The opening card counterexample reproduced unsupported persisted `done` in six
empty-workspace, syntax-only and wrong-output explicit/synthesized cases.
Declared acceptance now feeds final SQLite writes through an application
completion authority. Persisted attempt generations, current inputs/artifacts,
immutable evidence and atomic completion receipts gate new `done` and
`guard_approved` writes. Explicit and synthesized status requests pass a fresh
12-case composed proof; resumed per-tool caches cannot restore unsupported success.
Standard runtime composition now binds declared acceptance to dispatched turns.
Receipt inspection guards final turn publication and completed-turn reentry;
builtin writer ownership survives timeout and repeated cancellation. Compact
prompts retain acceptance and tool-call contracts. Build finalization now requires
every admitted card to be present and every observed card to have retained
acceptance, inspected under one writer guard. Loop termination emits a stop event;
accepted control-plane and ledger finalization emits completion.
The 136-case source matrix and an additional forged-event negative control pass on
Windows Python 3.13/3.11 and Linux Python 3.12. A fresh standard llama.cpp flow also
passes through card and build acceptance; 161 broader regression cases pass.
Unconfigured repositories continue to reject completion.
The remaining nine workload failures are repaired with explicit acceptance for
their actual text, design and sum-program outputs. Artifact criteria compare
captured text/JSON without executing it, and share final receipt enforcement with
CLI acceptance. The empirical verification flow now preserves its persisted
support observations while refusing undeclared completion. The 166-case source
matrix passes across Windows Python 3.13/3.11 and Linux Python 3.12; the final
artifact negatives and retained live CLI receipt inspection also pass.
The package-default repair moves canonical registries, policies, schemas and the
invariant contract into shipped assets. Explicit overrides retain fail-closed
validation; files in CWD cannot silently supply defaults. A wheel rebuilt from
the source archive passes 254 tests on each Windows/Linux Python 3.11/3.12 host,
with all runtime imports from site-packages. The installed live llama.cpp
increment workload also reaches matching card/build acceptance. Earlier missing
asset and invariant-document startup failures remain recorded. The broader
source run passed 5,012 tests with 74 skipped before the final invariant move;
24 focused checks subsequently pass with the documentation index in place.
Canonical summation now passes source live llama.cpp proof with eight model
receipts, four accepted cards and matching build receipts, including a run with
no prompt patch. Compact sections no longer repeat acceptance; disabled verifier
claims and inferred support reads are omitted; stage contracts match their actual
outputs. Explicit llama.cpp JSON-object requests include an enforced object schema.
The 208-case source envelope and deterministic canonical pipeline pass. These
changes are included in the expanded installed candidate audit recorded below. The admission audit
now rejects model-supplied definitions before driver asset or builtin card writes;
ordinary cards without criteria remain unevaluated. A real llama.cpp model proposal
is refused with unchanged asset hashes through the driver's fallback prompting
configuration and strict JSON parser. This is no historical provenance claim.
The failed-read guard retry now requeues through the existing reason-gated system
transition exception, invalidates the old completion request and preserves failed
dispatch truth. Source integration and live composed recovery pass, including a
fresh accepted review. This does not establish automatic resume or effect replay.
Dependency scheduling and turn context now share application-owned retained
acceptance checks and build scope. Strategies select from admitted copies, and
pre-turn rechecks reject changed dependency inputs or revoked prerequisites.
The canonical four-card workload passes again through this path with eight real
llama.cpp responses and matching card/build receipts. The operator execution
graph now shares dispatch's retained acceptance and build-scope checks, exposes
receipt/rejection diagnostics, and guards snapshot writes. Live authenticated
TCP/API reads pass nine prepared acceptance cases and evidence-loss reinspection.
Card/run operator views now require retained acceptance for completed filters and
verified runs; attribution metadata stays separate. Enum-valued card details and
unfiltered pagination are repaired. Missing/substituted run outcomes, changed
receipts and evidence loss are rejected through source integration and nine live
TCP/API cases. Control-plane closeout now commits its related records together;
session/success publication follows run-ledger finalization. SQLite abort,
cancellation and native process interruption/reentry tests pass. Publication
errors preserve accepted work and the original error. A durable prepared
publication plan now supports matching same-session restart across ledger,
session, snapshot and success-store writes without resetting accepted cards or
dispatching the workload again. Native process and live llama.cpp recovery pass.
Retained preparation now also covers closeout, receipts and summary before the
ready publication plan. Native interruption and live llama.cpp summary-write
recovery preserve accepted cards and model receipts. Export settings are frozen;
an enabled attempt without a retained result refuses automatic retry. Gitea
exports now retain exact commit intents and recover lost replies through remote
confirmation without another push. Disposable localhost Gitea, native restart and
combined live llama.cpp/Gitea acceptance pass with teardown. Unconfirmed export
owner recovery, arbitrary custom writers and the full proof envelope remained
open at that checkpoint. The final BT-3 audit below records current acceptance.
Workload termination is now retained before completion inspection and preparation.
Reentry preserves its transcript, effective snapshot and failure identity; native
restart and live first-preparation-write recovery pass. A started invocation with
no retained outcome refuses redispatch and reports uncertainty. Owner recovery for
that uncertain boundary remains required.
Standard entry now retains a resource admission before initialization. Same-session
and shared workspace/build/card races reject before writes; native death before
the ledger exists retains the claim. Verified publication releases the resources.
Explicit owner replacement before initialization now retains a fenced recovery
history. A paused original owner rejects before writes; duplicate requests consume
initialization once. Native process races/death and combined llama.cpp/Gitea proof
pass. Recovery after initialization, separate-journal coordination and arbitrary
writers remain open. Old admission v1 is rejected without inferred recovery rights.
Exact proof and limits are recorded in the canonical plan.
The 2026-09-13 approval repair now preserves a paused epic as unfinished execution.
Restart approval and denial retain the original parent/child identities, and one
journal claim excludes competing continuations. The actual llama.cpp four-card
flow pauses before its first write, restarts and completes with eight model
receipts. Both default and custom absolute runtime database layouts pass; engine, epic and
turn composition share the selected sibling control-plane store. Previously
published failures and split custom/global history are preserved without migration.

The scoped 264-case installed approval envelope passes on Windows/Linux Python
3.11/3.12, with runtime/SDK imports confirmed inside each isolated installation.
The earlier full source and 567-case installed candidate failures remain historical
evidence; scoped approval acceptance does not replace those broader gates.
The earlier Windows throughput failure passed unchanged in isolation, and Linux
Gitea acceptance still requires Docker in WSL. Recovery after a consumed pause,
post-initialization owner takeover, separate journals and custom writers remain
required work. Post-effect checkpoint refusal is preserved. Exact evidence and
current full-suite status live in the canonical plan's approval-repair checkpoint.
BT-4 native verification now establishes OS descendant ownership before command
execution, waits for bounded cleanup through cancellation and event-loop shutdown,
and reports uncertainty separately. Real Windows/Linux process tests cover
children, grandchildren, changed process groups, resistant descendants, leader
exit and timeout. The live llama.cpp four-card flow retained 15 passing native
command lifetime receipts and closed its engine. Installed and broad regression
results are retained in the canonical plan's BT-4 checkpoint. Fixture execution now
uses the async application service, with native descendant cleanup and separately
confirmed Docker removal. The old synchronous fixture entrypoints refuse before
execution; cancellation and uncertainty do not publish a new fixture result.
The fixture checkpoint records native/installed tests and explicit live Docker
acceptance. Broader application shutdown, host-death recovery, the complete CLI
outcome proof envelope and measured connector telemetry remain active work.

The fixture cutover's final source campaign passes **5,257 tests**, with **78
unchanged skips** and **two warnings**. The final installed envelope passes **133
checks per Windows/Linux Python 3.11/3.12 cell**; all 634 observed runtime/SDK
origins per cell are installed, and harness/source hashes remain stable. Both
installed Windows versions pass six live Docker cases with confirmed teardown.
WSL Docker integration remains unavailable. Separate live llama.cpp CLI probes
reproduced zero exits for retained `terminal_failure` through `--card`, `--epic`
and `--rock`. The typed result cutover now carries verified publication outcomes
through finalization, recovery, public dispatch and CLI projection. Fresh source
llama.cpp probes observe failure exits of 1 and a verified successful exit of 0.
The final typed-result wheel passes 185 installed checks per Windows/Linux Python
3.11/3.12 cell, with all 646 observed runtime/SDK origins inside each installation.
Twelve final-wheel llama.cpp runs through the three aliases on both Windows
versions match exit, narration and retained session/control-plane/publication truth.
The existing degraded startup warning remains explicit. The canonical plan records
the passing frozen-source campaign (5,287 passed, 78 skipped, two warnings) and
pending/incomplete public-CLI proof limits. Exact inventories, preserved fixture
digests, package/source parity and owned-process cleanup pass the final audit;
the complete architectural-truth lane remains open.

The following CLI lifecycle checkpoint preserves typed cancellation evidence in
CLI output after cleanup. Its 42-case source selection passes, including native
approval-wait, incomplete-run, SIGINT and repeated-cancellation cases through all
three aliases. Explicit model/policy/storage fixtures exercise real retained
authority and native process cleanup; the canonical plan separates those fixtures
from stock CLI and live-provider proof. The final envelope passes 207 installed
checks per Windows/Linux Python 3.11/3.12 cell, including child import-origin checks.
Four additional stock CLI llama.cpp success/failure controls pass on both Windows
versions. The full source gate remains the preceding checkpoint's historical run;
broader shutdown/recovery, connector timing and later gates remain required.

The preceding native BT-4 source campaign passed: 5,231 passed, 78 skipped and two warnings.
It includes the three earlier BT-3 structural corrections. The scoped installed
native-verifier/card-acceptance envelope passes 94 cases each on Windows/Linux
Python 3.11/3.12, with all 561 observed runtime/SDK origins inside each isolated
installation. Four of the source skips are opt-in localhost Gitea tests.
This is not a release-ready checkpoint. Sealed fixture bytes match
their original retained digests without resealing. The canonical plan records
the closure audit and the remaining 11 findings; no new capability is admitted.

## Objective

Make Orket's runtime behavior, dependency enforcement, tests, authority docs,
and operator entrypoints describe the same executable architecture.

Expand useful autonomy only with independently verified outcomes, reliable
recovery, and explicit capability limits.

## Canonical docs

1. Project registry: `docs/projects/architectural-truth/README.md`
2. Active implementation plan:
   `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
3. Active exception register:
   `docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json`
4. Rerunnable observation baseline:
   `docs/projects/architectural-truth/architectural_truth_baseline.json`
5. Slice A proof:
   `docs/projects/architectural-truth/SLICE_A_PROOF_2026-07-29.md`
6. Command-root proof:
   `docs/projects/architectural-truth/COMMAND_ROOT_PROOF_2026-07-30.md`
7. API B1 proof:
   `docs/projects/architectural-truth/API_INSTANCE_B1_PROOF_2026-07-30.md`
8. API B2 proof:
   `docs/projects/architectural-truth/API_COMPOSITION_B2_PROOF_2026-09-07.md`
9. September review reference:
   `docs/projects/architectural-truth/BEHAVIORAL_TRUTH_ARCHITECTURE_REVIEW_2026-09-10.md`
10. September evidence and reproductions:
    `docs/projects/architectural-truth/BEHAVIORAL_TRUTH_REVIEW_EVIDENCE_2026-09-10.md`

Historical review inputs remain under `docs/projects/future/` until their
own roadmap lifecycle moves or retires them.

The connector timing checkpoint replaces fabricated zeros with measured monotonic
duration and explicit provenance, preserving null/fractional logging in v2
envelopes. Installed Windows clock counterexamples drove a performance-counter
source correction without loosening the independent timing bounds. The final
source suite passes 5,325 tests (78 skipped); all four installed
Windows/Linux Python 3.11/3.12 cells pass 358 cases. Separate installed llama.cpp
approved-write proof and native success/failure/timeout/cancellation timing
comparisons pass. The timeout workload's exit needed a subsequent bounded wait,
so its separate lifetime observation remains partial.
Receipt republication retains the original measurement, historical hashes stay
unchanged, and the plan records failed/aborted attempts and exact proof scope.
At that timing checkpoint, command descendant ownership, other timing summaries
and later gates remained open.

The outward command lifetime checkpoint now shares the native supervisor through
an explicit core runner port, bounds raw capture and retains cleanup uncertainty
across API reentry. Installed Python 3.11/3.12 deadline failures were reproduced
and repaired without discarding typed cancellation evidence. The final selected
source regression and each Windows/Linux 3.11/3.12 installed cell pass 380 cases;
separate stock installed connector CLI success/failure trees confirm teardown.
No provider is invoked by that local CLI proof. The final archives, failed
attempts, exact file inventory and verification limits are in the canonical plan.
The earlier full-suite timing result remains historical; broader shutdown,
host-death recovery, other timing summaries and later architecture gates remain
open. The roadmap lane remains active and release readiness remains false.

The API shutdown checkpoint gives registered tasks/resources one retained teardown
and separates stopped admission from successful closure. Repeated cancellation,
concurrent close, failed-owner observation, a registered native command tree and
live Uvicorn HTTP shutdown pass scoped proof. Final source and four installed
Windows/Linux 3.11/3.12 cells each pass 87 checks. The plan preserves initial Linux
lease-fixture failures and the logical-clock/real-SQLite fixture correction.
That checkpoint left active request ownership open; the later ASGI checkpoint
below closes its bounded local invocation scope. General close deadlines and
host-death recovery remain open alongside BT-3 and later architecture gates.

Explicit retained export recovery now fences the prior local caller and confirms
delivery or grants one retry of the original Git commit. Accepted cards and model
receipts remain unchanged in fresh live llama.cpp/Gitea recovery. Installed proof
passes 95 on each Windows 3.11/3.12 cell (including actual Gitea) and 88 on each
Linux cell (journal/native recovery; no Linux Gitea transport proof). At that checkpoint, the
canonical source run passed 5,379, failed three stale test-double cases and skipped
81; the corrected nine-case file passes source and all four installed cells.
The full suite was not rerun after that fixture correction. The plan preserves
the initial push-counter failure and its fresh corrected run. At that export
checkpoint, unknown workload owner recovery, claimed approval interruption,
old-store and separate-journal recovery, and the later architecture gates remained open.

Interrupted guarded approval recovery now excludes an active native owner and
admits one explicit pre-effect continuation with retained operator history.
Original pause/checkpoint/admission identities survive; denial and post-effect
refusal remain intact. Live llama.cpp recovery after native process death completes
four accepted cards and one actual Gitea push with teardown. Final installed proof
passes 138 on Windows 3.11/3.12 and 131 on Linux 3.11/3.12. The frozen source suite
passes 5,399 with 81 skips; the later Linux path-fixture correction
passes its seven source cases and the final installed matrix. The full source
suite was not repeated after that fixture-only correction. The plan retains all
earlier harness/Linux failures, exact evidence and current file inventory.
Unmarked/post-effect pauses and arbitrary workload ownership still need separate
reconciliation; the architectural-truth lane and later gates remain active.

The active ASGI request checkpoint now owns HTTP/WebSocket invocations through
streaming and awaited connector work. Shutdown stops admission and waits for
request cleanup before resources and engine. Real TCP approval dispatch proves
native child/grandchild teardown, and streaming/ASGI WebSocket checks prove local
transport cleanup. Corrected source selection passes 187; its later portable
metrics assertion passes separately. All four fresh installed Windows/Linux
3.11/3.12 harnesses pass 187. Fresh installed Windows llama.cpp through the actual
TCP API commits its approved file and closes successfully. The plan preserves the
WebSocket cancellation regression, Linux fixture failures, bootstrap-driver error,
exact archives and evidence. Detached work, arbitrary resources/deadlines, remote
effects, host death, BT-3 recovery and later gates remain required; the whole lane
stays active and release readiness remains false.

The final BT-3 audit accepts builtin card completion and governed-agent replay.
Prompts consume typed acceptance, and governed rejection metadata reaches actual
storage and engine events through one envelope. The frozen source suite passed
5,429 with 81 skips; focused source and four installed Python/OS follow-ups cover
the later cleanup and test-fixture deltas. Initial installed failures remain
recorded: a missing copied extension fixture and one unexplained timestamp
reversal. Controlled clock-ordering/refusal checks pass; runtime timestamps are
not clamped. Live installed llama.cpp proves accepted cards and final-review
rejection. A read-only audit corrects the live driver's event-counting scope while
preserving its failed report and unchanged execution evidence. Exact files,
candidate hashes, proof limits and all attempts are in the canonical plan.

SR-01 through SR-07 and SD-02 now pass their scoped gates. Ten findings remain
open. BT-4 is next, followed by BT-5/C/D/E and capability work. Custom writers,
unknown workload ownership, broader recovery and the clock-input drift remain
required. The canonical baseline still reports release_ready=false.

The BT-4 gate audit found and repaired direct filesystem cancellation returning
before an executor thread finished its mutation. A shared adapter drain now owns
bound and direct builtin filesystem I/O; real delete/write/mkdir and API request
owner checks verify the wait. The combined installed regression and affected
follow-ups retain their Windows process-observation and Linux fixture-wait
failures. Final source passes 77 checks; corrected verifier follow-ups pass ten on each
installed Python/OS cell. Stock installed llama.cpp CLI success and failure both
match durable truth and confirm cleanup; both disclose degraded structural
reconciliation at startup. Exact package hashes, initial failures
and proof limits are recorded in the canonical plan. Thread force-stop, arbitrary detached ownership, broader recovery
and non-connector telemetry remain explicit outstanding scope.

Validator timing now has a scoped BT-4 repair: new dispatcher receipts use v2
with nullable duration and explicit reported/unavailable provenance. No validator
measurement is claimed. Final source and four installed Python/OS cells pass 99
checks each, including real file reads, receipt persistence, replay and
materialization. The initial Linux failures from case-sensitive test path
assumptions remain recorded. A stock installed llama.cpp CLI run publishes four
valid v2 receipts and completes with confirmed cleanup; startup still discloses
degraded structural reconciliation. The plan records exact artifacts, hashes and
limits. Governed-agent missing-latency/SDK migration was the next open slice at
that checkpoint; its scoped proof follows. Remaining BT-4/later gates stay active.

Governed-model v2 receipts now retain unavailable latency without fabricating
zero. SDK 0.7.0a1, the host candidate and reference extension/starter 0.3.0a1 form
an unreleased development pair. Admission and the ready handshake require v2
support before inference; canonical v1 history remains unchanged. Source and
four installed Python/OS cells pass 224 selected checks each. A final import-only
test cleanup passes four affected checks in each installed cell. The final SDK
fixture size correction retains identical behavior and passes a new 224-case
matrix and native live run against its rebuilt artifact. The initial
mixed-SDK, fixture-hash, source-path and undeclared setuptools failures remain
recorded in the plan. Native installed llama.cpp CLI proof completes with six
reported-latency receipts matching retained SQLite and final truth, with process
cleanup confirmed. Provider timing remains reported metadata; no independent
model timing scope or capacity claim is added. BT-4 and later gates remain open;
release_ready remains false.

The next scoped BT-4 repair preserves missing provider phases and backend total
as null, versions timing provenance, and requires complete turn coverage for
benchmark timing/throughput. Generic SDK/API generation preserves nullable latency
and its response version/posture. Source and four installed Python/OS cells pass
332 selected checks each. Native installed llama.cpp CLI proof matches original
provider phases and retained aggregates, with degraded reconciliation at startup;
authenticated TCP API proof returns the versioned result and confirms application
and process cleanup. Both API proof-worker startup mistakes remain recorded.
The canonical plan lists exact files, package hashes, failures and outstanding
thread/client ownership, selection and wider timing/recovery obligations. This
checkpoint does not close BT-4 or the later gates; release readiness stays false.

Generic extension generation now retains worker/client lifetime through repeated
cancellation, passes provider overrides explicitly, and closes the API's default
model client after requests settle. Injected clients remain embedding-owned.
Source and four installed Python/OS cells pass 372 selected checks each. Live
installed llama.cpp returns two normal HTTP 200 responses, then completes an
in-flight model call while shutdown waits and returns HTTP 503. Both model clients
close on their bridge loop before application/process cleanup completes. The
canonical plan retains the five initial counterexamples, exact artifacts and
remaining request-option, stuck-thread and wider ownership obligations. Whole
BT-4 acceptance and release readiness remain open.

The request-option counterexample is now repaired on the builtin SDK/API path.
Per-call token limits narrow profile ceilings, temperature is forwarded, and stop
strings retain exact whitespace; unresolved admitted profiles also retain explicit
options. Custom profile stop lists share the core exact-string validator. Source
and four installed Python/OS cells pass 440 checks each. Live
installed llama.cpp reaches an explicit 32-token ceiling with length termination;
a paired stop control returns `alpha ENDSTOP omega` without the caller sentinel
and `alpha` with it. Captured provider requests preserve the supplied temperature
and exact stop bytes. Application/client/native-process cleanup also completes.
The canonical plan records the initial 22 failing controls and three later
profile-stop counterexamples, exact artifacts and
proof limits. Other context producers, wider ownership, full BT-4 and later gates
remain active; no release readiness is claimed.

The remaining generic extension capability offloads now retain their synchronous
workers through cancellation and elapsed asyncio deadlines. Source and four
installed Windows/Linux Python 3.11/3.12 cells pass 476 selected checks each,
including actual executor effects and TCP teardown failures. Native installed
Piper returns real PCM audio; a second synthesis remains owned through about
10.7 seconds of API shutdown, then its cancelled HTTP request receives 503.
Both children exit zero and application/native-process cleanup completes.
The canonical plan retains the initial 18 counterexamples, failed harness
selection, artifact identities and exact files. That checkpoint established the
synchronous worker drain; native Piper and null availability are addressed below.

Builtin host Piper now shares the native command supervisor through an explicitly
supplied application owner. Its API path directly awaits supervised execution;
its synchronous SDK method uses the existing bridge. The native deadline defaults
to 120 seconds and PCM capture is bounded at 64 MiB; existing verifier/outward
defaults remain 4 MiB. Probe subprocesses and silent explicit-backend fallback are
removed. Generic null TTS status, catalog and synthesis now agree on unavailable.
Source and four installed Windows/Linux Python 3.11/3.12 cells pass 538 checks each.
Injected subclasses retain their synchronous overrides and voice catalogs.
Live installed Piper completes short and 14.6 MB audio responses, then a cancelled
request stops its observed native process and returns 503 after about 81 ms of
local shutdown. Native receipts and application/process cleanup are retained.
The canonical plan records exact artifacts, failures and scope. The voice
identity/rate obligations identified there are addressed in the next checkpoint.

Host Piper now refuses unknown or ambiguous voice IDs, preserves the configured
default, and returns the selected canonical ID and model-derived sample rate.
Its optional rate setting checks agreement rather than relabeling PCM. A private
owned config snapshot binds the returned metadata digest to the bytes supplied
to Piper and is removed after native settlement. Source and four installed
Windows/Linux Python 3.11/3.12 cells pass 558 selected checks each. Real installed
Piper verifies default Lessac and explicit Alan responses, unknown-voice rejection
before launch, and cancelled native shutdown with all snapshots removed. The
canonical plan retains 15 initial failing controls, artifacts and exact files.
Arbitrary model-weight/schema validity, other resources, full BT-4 and later gates
remain active; no whole-lane or release acceptance is claimed.

The scored benchmark pipeline now preserves unavailable and partial timing.
Scored schema v2 adds duration coverage; averages require every input run to
provide a finite nonnegative duration. Trends and dashboards share validation,
preserve old numeric averages as unverified history and display missing timing
as unavailable. Source and four foreign Windows/Linux Python 3.11/3.12 harnesses
pass 35 selected checks, including native CLI flows and rerun ledgers. Core/SDK
artifacts are unchanged. The canonical plan retains the original false averages
and the repaired outputs, plus remaining raw-harness/selector counterexamples.
The existing taxonomy checker also misreports the correctly labeled end-to-end
CLI test as missing a layer; E1 owns that checker correction. BT-4 and later
gates remain active.


Raw benchmark admission now rejects empty task/run populations before launch or
report replacement, and requires an explicit runner. Selector v2 rejects missing
latency instead of admitting a zero default, with retained rejection reasons and
rerun history. Internal quant/context handoffs retain the active Python environment.
Source and four installed-package Windows/Linux cells pass 126 checks each; local
YAML smoke commands also pass with controlled runners. The canonical plan retains
initial failures, proof paths, the 17-file inventory and the user's requested
goal reassessment. That handoff was followed by the current combined BT-4
acceptance named above. The whole plan and 35 later numbered obligations remain
open; no reliable whole-project ETA is established.
