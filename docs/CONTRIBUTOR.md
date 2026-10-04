# Contributor Guide

## Startup

1. Before substantive work, read in order:
   - `docs/CONTRIBUTOR.md`
   - `docs/ROADMAP.md`
   - `docs/ARCHITECTURE.md`
2. Read `docs/architecture/ARCHITECTURE_COMPLIANCE_CHECKLIST.md` before merge when the change touches runtime, orchestration, adapters, interfaces, or decision nodes.
3. Agents also follow `AGENTS.md`.
4. Do not scan dependency or vendor trees (`node_modules/`, `.venv/`) unless explicitly requested.
5. For `Last updated:` fields, use the local `America/Denver` date.

## Work Selection

1. Default to the highest-priority active roadmap item.
2. If `Priority Now` is empty or contains only a maintenance-only posture marker, take the highest-priority active non-recurring item in `Maintenance (Non-Priority)`.
3. Standing recurring maintenance is fallback work unless the user explicitly asks for it or it is the only active maintenance item.
4. Do not reopen staged, deferred, or paused work without an explicit request.

## Roadmap Discipline

`docs/ROADMAP.md` is the only active roadmap.

1. Keep entries terse, execution-only, and non-journaled.
2. Active lane entries point to the canonical implementation plan path, not requirement docs.
3. Staged / Waiting and Paused / Checkpointed entries include only the canonical lane authority path and the smallest valid reopen trigger.
4. Keep detailed reentry criteria, missing-proof status, and historical execution detail in the canonical lane file, not in separate reentry docs.
5. Do not create parallel active backlog or handoff docs.
6. Update the roadmap at handoff to remove completed or obsolete items.
7. Every non-archive folder in `docs/projects/` must appear in the Project Index.
8. Every active or queued roadmap entry must point to an existing path.
9. When roadmap or `docs/projects/` structure changes, run `python scripts/governance/check_docs_project_hygiene.py` before handoff.
10. Standing recurring maintenance entries stay static and point only to durable authority docs, not volatile evidence.

## Planning and Closeout

1. When creating or revising a staged lane, keep detailed reentry criteria in the lane's canonical plan or authority file.
2. When creating a new active implementation plan, add or update its roadmap entry in the same change.
3. When accepted requirements contain durable contracts or specs, extract them into `docs/specs/` before writing the implementation plan.
4. When a change updates a durable contract, record the contract delta using `docs/architecture/CONTRACT_DELTA_TEMPLATE.md`.
5. When a non-maintenance lane completes, move plan, closeout, and history docs to `docs/projects/archive/<lane>/` in the same change.
6. Move long-lived contracts or specs out of completed lanes into `docs/specs/`.
7. Do not leave `Status: Completed` or `Status: Archived` docs in active `docs/projects/`.
8. When closing a phase or slice in a multi-phase initiative or umbrella lane, archive only phase-scoped or slice-scoped docs. Keep the initiative mini-roadmap, umbrella README, and current canonical plan active while later phases or remaining slices exist. Do not retire the whole lane unless the user explicitly accepts whole-lane retirement.
9. For `docs/projects/techdebt/`, leave only standing maintenance docs and docs for cycle ids still active in the roadmap.

## Persistent goal queues

When the user targets a canonical plan for continuing goal execution:

1. Use that plan's fixed goal IDs, worksets, dependencies and start/exit criteria.
   Creating the queue is planning; begin its implementation when the user invokes
   it for execution. Do not replace the objective or enlarge its scope on resume.
2. Resume the recorded unfinished batch after checking its source and process
   state. Then take the first eligible goal in order. A completed batch or goal
   does not require another user prompt to continue within the authorized queue.
3. Checkpoint at cohesive batch boundaries and before interruption/budget limits:
   record current goal/batch, completed and remaining work, source/dirty-file
   identity, proof/artifact paths, blockers and the next exact action. For running
   commands retain argv, environment posture, process identity/start time, log and
   result paths. Observe that process before considering a replacement run.
4. Keep tracked inputs frozen during source-bound verification. Link a stable
   ignored process receipt before launch and let it retain live process status;
   update the tracked checkpoint after the run. Reuse proof only while its relevant
   inputs remain valid. Full campaigns require their stated gate, a changed
   candidate, or an explained invalid run; scoped proof is preferred between them.
5. Close an item only on its stated evidence and publication conditions. Never
   weaken assertions, limits, mandatory environments or acceptance criteria to
   finish it. Archive completed proof/history under contributor closeout rules;
   keep the active plan a concise queue and resume record, not an execution journal.
6. Record unrelated discoveries without adding executable goals or changing the
   progress denominator. Continue independent eligible goals when one is blocked.
   If none is eligible, report the exact blocker and required input; blocked,
   budget-limited or unverified required work is not completed work. Existing user
   authorization applies to routine choices; scope expansion needs a user decision.
7. Refactoring does not authorize new product, platform, deployment or acceptance
   targets. Obtain explicit user direction before introducing any such target.

The user's October 3 ATG-v1 scope amendment makes Windows the sole acceptance
target for that queue. Follow its canonical plan for native Windows quality,
installed/public-path and llama.cpp proof. Linux/WSL clock work, hosted runners
and the complete cross-platform Gitea workflow are no longer ATG-v1 prerequisites.
Existing workflow definitions and historical results remain intact; this change
does not turn failed or absent hosted/Linux evidence into passing proof. Keep
Windows assertions, deadlines, declared skips and the 89-percent floor unchanged.
Verification-contract delta: `docs/architecture/CONTRACT_DELTA_WINDOWS_ACCEPTANCE_2026-10-03.md`.

## Repository Rules

1. Keep runtime paths in `orket/` async-safe and governance mechanical.
2. Keep permanent decisions in tracked docs or code.
3. Prefer small, reversible changes.
4. Do not commit secrets, `.env`, or local database files.
5. Keep the repo root clean. Put tool-specific metadata under `Agents/` when practical.
6. Do not add small project-subfolder `README.md` files by default.
7. Workflow changes go in `.gitea/workflows/` only unless explicitly approved otherwise.
8. When changing automation, implement and validate the `.gitea` workflow first.
9. Agent-proposed benchmark artifacts must go to `benchmarks/staging/` until the user explicitly approves publication.
10. After any staging artifact change, run:
   - `python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --write`
   - `python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --check`
11. After any published artifact change, run:
   - `python scripts/governance/sync_published_index.py --write`
   - `python scripts/governance/sync_published_index.py --check`
12. Commit staged artifacts, `benchmarks/staging/index.json`, and `benchmarks/staging/README.md` together. Commit published artifacts, `benchmarks/published/index.json`, and `benchmarks/published/README.md` together.

Required bug-fix, preview, structural adoption and missing-read producers retain
captured event values/workspaces before their owned native publication. Both Quality
selections include the five-site controls for actual append, held-write cancellation,
native failure and partial effects, alongside existing logging preparation/subscriber/
overflow/fatal-writer controls. Keep successful completion conditional on required
publication; earlier durable effects need not roll back. Contract:
`docs/specs/LOG_WRITE_SETTLEMENT.md`.

Governed-run demo changes retain the direct async native-operation controls and
public CLI/inspection/replay cases in both Quality selections. Marshaller artifact/
ledger changes retain native holds, input/JSON capture, partial effects and real
runner/promotion controls in both selections. Quickstart retains ledger/adoption,
operator/file ownership and native CLI outcome controls. Outward model policy
validation retains connector-capture, native settlement and transaction-recovery
controls under `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`. Offline migration
retains metadata, committed-WAL copy/close, partial-copy and process-death controls
under `docs/specs/OUTWARD_RUN_AUTHORITY.md`. Support graph changes retain native
read/write/input controls and projection-only semantics from
`docs/specs/RUN_EVIDENCE_GRAPH_V1.md`. Manual wake routes retain request read/close,
argument capture and native command guards under `docs/specs/GOVERNED_AGENT_LOOP_V1.md`.
Preserve captured
paths, native failure precedence and partial bundles under
`docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`.

Named orchestrator/dispatcher/message extractions retain both Quality selections'
phase selection, actual turn effects, replay/receipt ownership, completion and
native read controls. The prompt-input inventory follows every extracted renderer.
Keep module/function limits and original capture/await order; structural size
checks do not replace live phase proof. Delta:
`docs/architecture/CONTRACT_DELTA_NAMED_HOTSPOTS_E2_2026-10-01.md`.

## Current Authority Maintenance

`docs/architecture/current_authority.json` is the bounded authored index;
`CURRENT_AUTHORITY.md` is its generated view. Canonical contracts, implementation,
the dependency policy and start-path matrix remain the owners of their rules.
Update affected sources and current records together, then run
`python scripts/governance/render_current_authority.py` and
`python scripts/governance/check_current_authority.py`. Use
`python scripts/governance/render_current_authority.py --check` for a read-only
generated-view comparison. Do not append execution history to the manifest/view;
retain scoped proof and outstanding work in their canonical plan or release record.

Both Quality truthful-checker steps run the native authority checker and its
contract/native controls. It checks documented argv and declared entrypoints,
source admission, compatibility conditions and exact generated equality. It does
not execute product commands or establish semantic agreement between prose rules.
Current runtime proof remains explicitly unavailable: requesting
`python scripts/governance/check_current_authority.py --require-current-proof`
must refuse. Contract: `docs/specs/CURRENT_AUTHORITY_SOURCE_CONTRACT.md`.

## Canonical Commands

Model-stream builtin calls capture request/provider inputs before discovery and
apply canonical target admission before inference construction. Both Quality jobs
retain real local catalog, blocked-target refusal and input-mutation controls.
Keep turn phase controls with the existing preparation/provider/approval guards
when changing orchestrator composition. Contracts and limits:
`docs/architecture/CONTRACT_DELTA_MODEL_STREAM_INPUTS_D_2026-09-28.md`,
`docs/architecture/CONTRACT_DELTA_MODEL_STREAM_ADMISSION_D_2026-09-28.md`, and
`docs/architecture/CONTRACT_DELTA_ORCHESTRATOR_TURN_PHASES_E2_2026-09-28.md`.

Both Quality selections retain model-stream iterator, transport, input and failure
controls. The builtin explicitly closes its admitted iterator before commit/return
and retains native construction and cleanup through repeated interruption. Raw
real stream adapters require the application HTTP lifetime port. A cleanup
TimeoutError is not a turn-deadline verdict. Controlled HTTP is separate from
actual-provider acceptance under `docs/specs/MODEL_STREAM_LIFETIME.md`.


Tool invocation uses the shared I/O owner through synchronous native work and
async cleanup. The timeout requests interruption; effects and cleanup may finish
later. Both Quality jobs retain isolated tool failure/value/deadline controls and
existing workspace-guard checks. Both jobs also retain guarded native-failure,
SQLite exclusion, cleanup-precedence and authority-admission controls in
`tests/integration/test_guarded_mutation_ownership.py`. Preserve the guarded
route's separate proof limits under `docs/specs/SHARED_IO_CANCELLATION.md`.

Application file validation and reconciliation capture invocation roots before
owned waits; direct stores bind their construction root. Both Quality jobs retain
real two-tree, CWD/attribute rotation, refusal and partial-adoption controls under
`docs/architecture/CONTRACT_DELTA_APPLICATION_ROOT_INPUTS_D_2026-09-28.md`.
Filesystem containment and lock selection share resolved-path identity for Windows
namespace aliases while preserving native I/O paths and reference write refusals.
Both Quality selections retain the native alias and pure identity controls with
the existing file lifetime/input checks; UNC value checks are not live SMB proof.
Contract: `docs/architecture/CONTRACT_DELTA_ASYNC_FILE_OPERATIONS_D_2026-09-21.md`.
Epic extraction must preserve phase-selected owners and approval consumption after
semaphore admission; retain the public phase controls with existing scheduler,
approval and recovery guards under `docs/specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`.

Turn checkpoint continuation must bind its requested run, resumed/source attempts,
recovery decision and accepted checkpoint. Preserve actual retained-state refusal
and no-repair controls, plus turn recovery and approval-continuation guards, in
both Quality jobs. Metadata lineage does not prove artifact replay or effects.
Contract: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

Test-layer authority is exactly one distinct canonical pytest marker per collected
item: `unit`, `contract`, `integration` or `end_to_end`. Prose and directories do
not classify tests. The v2 taxonomy checker retains missing/conflicting items and
collection failures; strict acceptance requires zero of each. Both taxonomy and
critical no-op checks use the shared Git-visible inventory, including nonignored
untracked files. Both `architecture_gates` and `quality` run their regression
tests plus `python scripts/governance/enforce_test_taxonomy.py --strict` and
`python scripts/governance/check_noop_critical_paths.py` in the truthful-checker
step, without narrowed roots or optional failure. Preserve its exact-argv guard
and the canonical Ruff and coverage gates.
Contract: `docs/specs/QUALITY_CHECKER_CONTRACT.md`.
The Quality coverage command is `pytest tests/ --cov=orket --cov-config=pyproject.toml --cov-fail-under=89`.
Keep the explicit configuration path so native children launched from other
directories retain the authored branch measurement. The 89-percent floor remains.
Hosted coverage writes to the absolute ignored `.tmp/quality/.coverage` path so
the unchanged normalization guard does not stage generated coverage data.
Hosted architecture gates use `scripts/ci/record_quality_gate.py` to execute the
existing G1-G5 commands and write current command results, logs and the required
TD03052026 dashboard before its unchanged `--require-ready` audit. Missing, stale
or failed evidence remains red; G6/G7 gain no proof from this recorder. Its native
subprocess controls run before the recorded gates. Outputs stay under the stable
`benchmarks/results/techdebt/td03052026/` root and use the rerun diff ledger.
The architectural baseline's size collector uses that inventory too. Retain its
complete oversized lists and nested-function context for no-growth comparisons;
inclusive parent/child spans overlap and cannot be summed as independent defects.
Turn-tool ownership controls recognize explicit service and captured-binding
imports; both Quality selections retain the exact caller map and adverse scan
controls. These are bounded structural observations, not general alias analysis.

Optional loop logging requires an explicitly prepared application binding, captures
supported built-in inputs and admits independent main/artifact stages to the
existing bounded writer. Canonical owners perform preparation; direct async
embeddings await `prepare_logging(LoggingInputs(...))` and enter `bind_logging(...)`
in the operation's task. Borrowed runtime lifespan yields carry no binding token.
Return is admission only. Both Quality selections retain preparation, native
startup failure, task-context, capture, overflow, fatal-writer and API handoff
controls. The single daemon remains process-owned. ATG-03 closed the five
frozen required-producer input sites; broader logging guarantees remain limited
by `docs/specs/LOG_WRITE_SETTLEMENT.md`.
Keep the public pipeline verification, database bootstrap and standalone provider retry controls in
both Quality selections. These cover real local fixture/HTTP/logging behavior;
controlled HTTP responses do not establish actual model inference or live Docker
acceptance. Direct calls to services borrowed from a runtime still bind explicitly.

Required epic completion logs retain the existing native I/O owner through
interruption. Keep the real append, retained-store and recovery controls in both
Quality selections. A failed acknowledgement can leave store and log effects;
the publication journal remains the progress authority. Contract:
`docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`.

Card metadata, receipt inspection, final artifact authorization and epic journal
transactions retain admitted native work through caller interruption. Both Quality
jobs retain the native ownership controls with card completion, epic admission
and publication recovery cases. A settled interrupted commit can be durable;
inspect retained state and use existing recovery authority before retrying.

Sandbox event publication captures supported built-in values before event identity
and persistence. Append and replay share native ownership; preserve busy refusal,
legacy-sentinel migration and partial effects. Both Quality jobs retain file,
SQLite, process and input controls under `docs/specs/SANDBOX_EVENT_PUBLICATION_OWNERSHIP.md`.
API startup validation uses the existing owned native worker before engine startup;
keep handler/cancellation/security controls under `docs/specs/API_RUNTIME_LIFECYCLE.md`.
Both Quality selections also retain native missing-authentication and missing-
interaction-owner refusal/cleanup controls in `test_api_required_runtime_owners.py`.
The required-value delta is `docs/architecture/CONTRACT_DELTA_TYPING_REQUIRED_VALUES_2026-10-01.md`.

Supporting failure diagnostics retain the existing native I/O owner through
handler settlement. Both Quality jobs retain held/failing-handler, fatal-handler
and executor-refusal controls with existing I/O and API lifecycle/cleanup guards.
Preserve primary/cancellation identity, remaining close attempts and tracked
background failure ownership under `docs/specs/RUNTIME_FAILURE_DIAGNOSTICS.md`.
Affected custom standard handlers must support native worker invocation.

Required native workers retain `SystemExit` and `KeyboardInterrupt` until the
public caller observes their original failure, including through enclosing shared
I/O owners. Both Quality selections retain the isolated API event and nested-owner
controls, coroutine admission/refusal controls and existing cancellation/diagnostic
guards. Custom task factories observe the admitted coroutine adapter; arbitrary
custom/eager task-factory compatibility is not established. Contract:
`docs/specs/SHARED_IO_CANCELLATION.md`.

Shared I/O factories declare `OwnedCoroutine[T]`, matching their existing Task
admission. Preserve interpreter-observed generator refusal and caller ownership
of rejected work when changing annotations; the exact variadic throw forwarding
remains unchecked. Typing success does not replace native settlement controls.

System role/team catalog reads run through the application query service and
existing native worker owner. Preserve tolerant parsing, response ordering and
request/shutdown settlement. Outward model and sandbox terminal evidence retain
one complete admitted publication/read attempt through interruption; partial
files do not acquire completion authority. Both Quality jobs retain these controls
and the active outward HTTP event-stream lifecycle case. Contracts:
`docs/specs/API_RUNTIME_LIFECYCLE.md` and
`docs/specs/EVIDENCE_ARTIFACT_PUBLICATION_OWNERSHIP.md`.

Public enum representation controls run in both Quality selections; declaration-local
exceptions preserve the bounded scope in `docs/specs/PUBLIC_ENUM_REPRESENTATION_CONTRACT.md`.

Direct sandbox cleanup decision builders supply `compose_path_available`; the
application observes it once through the retained native owner. Both Quality
selections retain the cleanup observation and existing recovery/authority cases.
Contract: `docs/specs/SANDBOX_CLEANUP_OBSERVATION.md`.

Direct review preflight construction supplies `utc_now`; direct `Note` values
supply `id` and `created_at`. Standard composition passes the existing turn clock.
Keep support/guard decisions and their completion-authority limits intact under
`docs/specs/EPIC_RUNTIME_TIME_INPUTS.md`.

Verifier input and support-artifact ownership controls run in both Quality jobs,
alongside real verification process lifetime, card acceptance and review-time
cases. Preserve native failure precedence and record/latest/index partial effects
under `docs/specs/RUNTIME_VERIFICATION_OWNERSHIP.md`.
Fixture and sandbox HTTP verifier constructors require the selected aware
`utc_now` port. Fixture invocation detaches supported built-in scenario values,
captures process inputs and retains metadata and required security publication
through interruption. Both Quality jobs include the selected-clock and publication
controls; supplied container observations do not establish live Docker teardown.

Gitea state/webhook HTTP composition uses captured network policy and one native
resource owner. Async callers use owned factories; native constructors refuse
entry on the event loop. Both Gitea CLI paths retain adapters through cleanup,
and coordinator summaries use the shared diff ledger at the existing output path.
Authorization, retries, URL admission, finite deadlines and webhook failure envelopes
remain authoritative. Contract: `docs/specs/GITEA_HTTP_CLIENT_OWNERSHIP.md`;
migration: `docs/architecture/CONTRACT_DELTA_GITEA_HTTP_INPUTS_D_2026-09-22.md`.
Retry operations snapshot borrowed nested request values. Lease acquisition and
renewal use a body-size limit compiled from the captured construction environment.
Raw native embeddings supply that integer; recreate adapters to change policy.
Request-input migration: `docs/architecture/CONTRACT_DELTA_GITEA_REQUEST_INPUTS_D_2026-09-22.md`.

Artifact-export and builtin HTTP use the application short-request owner for captured
network inputs, native construction and complete resource cleanup. Exporters retain
construction configuration; builtin HTTP observes configuration per request. Raw
embeddings supply the request port; async exporter construction retains the native
factory. Contract: `docs/specs/SHORT_HTTP_REQUEST_OWNERSHIP.md`; migration:
`docs/architecture/CONTRACT_DELTA_SHORT_HTTP_OWNERSHIP_D_2026-09-22.md`.

Artifact export captures restricted Git inputs with its construction context,
copies nested payload arguments before dispatch and retains native payload/cache
work through interruption. Application composition supplies the shared command
supervisor; Git keeps its 60s deadline, bounded capture and private failures.
Descendant cleanup precedes command success; uncertainty cannot authorize export.
Raw exporter/Git embeddings supply the command port. Contract and migration:
`docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md` and
`docs/architecture/CONTRACT_DELTA_GITEA_EXPORT_OWNERSHIP_D_2026-09-22.md`.

Interrupted connector telemetry captures its invocation root and retains one
native publication attempt through directory work, writes and logging sinks.
Repeated cancellation and supporting-log failures preserve the original connector
exception. A failed diagnostic sink adds a non-secret note to that exception.
Timing retains its invocation scope; logs grant no effect or recovery authority.
Other log producers keep their current contracts. Migration and scope:
`docs/specs/CONNECTOR_INVOCATION_TIMING.md` and
`docs/architecture/CONTRACT_DELTA_CONNECTOR_LOGGING_D_2026-09-22.md`.

Shared required-read metadata uses explicit application observations and the
existing PathResolver/native owners. Each response attempt shares one observation
with corrective rendering; retries and per-tool preflight observe afresh. Governed
preloads, legacy file classification and exists-only context availability retain
their distinct semantics. Execution uses captured admitted commands and preserves
the original result sinks. Packet-1 intended provider/profile comes from the existing
runtime construction snapshot; actual telemetry keeps its precedence. Native
automatic pipeline capture excludes unused preferences; supplied full inputs and
existing async factories retain full capture. Omitted preference access refuses
explicitly under `docs/specs/SETTINGS_INPUT_OWNERSHIP.md`. Contracts:
`docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md` and
`docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`; migration and proof limits:
`docs/architecture/CONTRACT_DELTA_REQUIRED_INPUT_OWNERSHIP_D_2026-09-22.md`.

Turn-message preparation captures its workspace and prompt-consumed values before
awaiting native work; unrelated execution resources remain untouched. Existing
native/file owners retain path admission, metadata, reads, closure and missing-input
log production through interruption. Required reads use the existing governed
PathResolver policy. Compaction writes to the two originally captured output sinks.
Contract and migration: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
and `docs/architecture/CONTRACT_DELTA_MESSAGE_READ_OWNERSHIP_D_2026-09-22.md`.

Packet-2 collection captures its workspace, normalized policy and detached
provenance before receipt discovery. The existing native owner retains protocol
and legacy discovery/read/close and contained-file audit through interruption.
Protocol-file precedence, sorting, operation identity and tolerant parsing remain;
verified narration audit still means successful receipt plus contained existing
file, not semantic content. Migration and limits:
`docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md` and
`docs/architecture/CONTRACT_DELTA_PACKET2_OWNERSHIP_D_2026-09-22.md`.

Terraform artifact publication captures its workspace and nested payloads; shared
file capabilities own metadata and writes through interruption. Source-attribution
observation captures its receipt path and derived policy/provenance, then owns
existence/read/decode/close as one native operation. Non-object JSON has no claim
or source evidence and cannot verify synthesis. Existing missing/invalid receipt
classifications and partial artifact effects remain explicit. Contracts and migration:
`docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`,
`docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md` and
`docs/architecture/CONTRACT_DELTA_DIRECT_METADATA_D_2026-09-22.md`.

SDK workload parents validate configured capability identifiers before dispatch without
constructing unused providers. The native child owns default model clients through
construction, authorization, execution and cleanup; a cleanup failure cannot publish
success. Configured borrowed providers retain caller ownership.

Card preparation retains primary and ODR-auditor cleanup as owned operations so
repeated cancellation cannot interrupt adoption of a completed provider close.

Inference clients reuse captured catalog proxy, trust and key-log policy. The native
provider factory refuses event-loop entry; async callers use owned construction and
retain partial or unadopted clients through cleanup. Captured Ollama authentication
overrides the SDK's ambient request header. Provider preparation shares the captured
lexical directory. Backend redirects, deadlines, retries, admission and response
lineage remain authoritative. Contract: `docs/specs/PROVIDER_INFERENCE_CLIENT_OWNERSHIP.md`;
migration: `docs/architecture/CONTRACT_DELTA_PROVIDER_INFERENCE_INPUTS_D_2026-09-22.md`.

Provider HTTP catalogs use captured proxy, certificate and optional TLS key-log
inputs with verified TLS and disabled redirects. Native client construction and
all acquired resources remain owned through interruption and cleanup failure.
Explicit empty mappings have no ambient or OS proxy-registry fallback. Non-finite
HTTP budgets and unsupported NO_PROXY CIDR fail explicitly. TLS-library internals
and wider async reachability remain separate obligations. Contract:
`docs/specs/PROVIDER_HTTP_CATALOG_INPUTS.md`; migration:
`docs/architecture/CONTRACT_DELTA_PROVIDER_HTTP_INPUTS_D_2026-09-22.md`.


Provider and shared command input changes require the process-input and relative
GGUF controls alongside existing inventory, model-load and lifetime cases in both
Quality jobs. Observe actual child/private-supervisor context and model-state files;
fixture executables do not establish actual-provider acceptance. Preserve explicit
empty environments, finite deadlines and drive-relative refusal. Contract delta:
`docs/architecture/CONTRACT_DELTA_PROVIDER_PROCESS_INPUTS_D_2026-09-22.md`.

OpenClaw JSONL callers supply the existing application command supervisor through
`JsonlCommandRunner`; adapters do not create a second process-tree owner. Preserve
sequential request admission, accepted partial responses, bounded writes/capture
and cleanup uncertainty. Both Quality jobs exercise real process/pipe controls and
the nervous-system CLIs with explicitly declared fixture adapters. Those runs are
not actual OpenClaw/model acceptance. Contract: `docs/specs/OPENCLAW_PROCESS_OWNERSHIP.md`.

Worker's synchronous adapter refuses event-loop entry. Async callers use the
existing owned native worker and retain the borrowed, finitely bounded HTTP client
until work and renewal settle. Exercise native refusal, actual HTTP/SQLite renewal
lifetime and existing lease/hedging controls in both Quality jobs. Accepted server
effects can survive interruption. Contract: `docs/specs/WORKER_RENEWAL_OWNERSHIP.md`.

Provider inventory native commands and Packet 1 alias commands use the package-owned
OS supervisor. Preserve finite budgets, bounded capture, cleanup uncertainty and native
event-loop refusal when editing these paths. Exercise real descendant trees and output
controls in both Quality jobs. A successful CLI inventory is not model inference, and
process cleanup cannot establish rollback of model or alias effects. Contract:
`docs/specs/PROVIDER_GOVERNANCE_COMMAND_OWNERSHIP.md`.

Architecture policy helpers and direct orchestrator construction require explicit
immutable policy snapshots. Application observation receives a captured environment
and absolute invocation root; async callers await the owned observation service.
Settings capture at each request to retain operator changes between requests. Keep
policy-service construction in `ApiRuntimeContainer`; the router supplies its
captured request inputs through that application owner. Keep
readiness criteria, response schemas and conditional settings-write conflicts intact.
Run the runtime-policy input/request/lifetime controls in both Quality jobs when
changing this boundary. Contract: `docs/specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`.

Orchestrator support construction calls canonical implementations once; internal
type errors cannot trigger reduced-input retries. Both Quality jobs retain those
constructor controls with public verification and ordered card/control-plane
transition guards. Policy/constructor tests target their actual owners after the
facade helper/export retirement; full execution and provider lifetime proof remain
separate from structural decomposition.

Extension scaffold authoring sources live in `docs/templates/external_extension/`
and `docs/templates/governed_agent_external/`. After changing them, run
`python scripts/governance/sync_extension_templates.py --write` followed by
`python scripts/governance/sync_extension_templates.py --check`; commit the source
changes and generated archives together. Runtime reads those packaged archives
only. The compiler normalizes UTF-8 text to LF, preserves binary assets and uses
fixed ZIP metadata. Both Quality jobs enforce source/archive agreement.

- Install: `python -m pip install --upgrade pip && python -m pip install -e "./orket_extension_sdk[testing]" -e ".[dev]"`
- Default runtime: `orket runtime`
- Named card runtime: `orket runtime --card <card_id>`
- API runtime: `python server.py`
- Standalone coordinator: `python -m uvicorn orket.interfaces.coordinator_api:create_coordinator_app --factory`
- Standalone Gitea webhook: `python -m orket.webhook_server` or `python -m uvicorn orket.webhook_server:create_webhook_app --factory`
- Governed-action quickstart: `orket-quickstart` or `orket-quickstart --decision approve|deny`
- Governed-run deterministic demo: `orket demo governed-run`
- Interactive project setup: `python -m orket.interfaces.setup_cli`
- Test command: `python -m pytest -q`

Async Kernel embeddings use engine async mutation/approval methods; the API
routes synchronous Kernel work through application-owned workers. Retain the
caller until required publication settles, including cancellation or timeout.
Cancellation can follow an effect; inspect retained state before retrying.
Owned JSON/environment and partial-publication limits live in
`docs/specs/KERNEL_PUBLICATION_INPUTS.md`. Direct action-path embeddings must
create and bind an explicit `KernelRuntime` and close it after related calls;
async direct embeddings use `KernelRuntime.open()` and retain any workers they
start. Engine callers use the engine-owned gateway/runtime and async methods.
Do not restore global-map or test-reset defaults to migrate a caller.
Legacy capability policy reads and native execute-turn use owned workers. Typed
policy inputs and the package-owned default follow
`docs/specs/KERNEL_CAPABILITY_POLICY_INPUTS.md`; do not restore CWD lookup or
silent empty-policy fallback. Implicit Kernel start also requires an active
owner and native execution; typed run inputs permit pure start. Preserve bound
project/invocation roots across worker waits and use the selected run-ID port:
`docs/specs/KERNEL_RUN_INPUTS.md`. Direct LSI reads/staging/validation, promotion
and ledger repair also require native owned execution. Missing staging is a
no-op, not deletion intent; use explicit tombstones and inspect retained recovery
directories after failures. See `docs/specs/KERNEL_STATE_EFFECTS.md`.
Outbound policy-file loading also requires owned native execution. API policy
is captured during preparation; construct a new app to reconfigure it. Explicit
policy inputs bypass ambient lookup. See `docs/specs/OUTBOUND_POLICY_INPUTS.md`.
Synchronous SDK/bridge, Piper discovery, review and provider-inventory work
requires native execution. Async embeddings use owned workers, retain close,
and explicitly own any loop-bound resources. See `docs/specs/SYNC_COROUTINE_OWNERSHIP.md`.
Script command scopes retain engine and default provider cleanup before returning.
Artifact replay reads use native owned observation without runtime construction.
ProductFlow fixtures and witness history obey current acceptance/lease contracts.
See `docs/specs/SCRIPT_RUNTIME_OWNERSHIP.md`.
The three truthful-runtime governance recorders own their engines on their event loop;
call their native entrypoints outside a running loop. Alias simulation is contract proof,
not Ollama acceptance; preserve existing aliases and surface owned cleanup failures.
Declare an explicit literal module effect bound for each policy-classified adapter.
The canonical dependency gate enforces the declaration and decision-admission contract
in `docs/specs/ADAPTER_EFFECT_CLASSIFICATION.md`; read-only is not deterministic purity.

Prompt commands use `python -m orket.interfaces.prompts_cli --root <project> ...`.
Prompt reads share model-file ownership with writers and can create native lock
identities; tests should copy canonical assets into their own temporary roots.
Setup, prompt and vision command ownership, migration and partial-effect limits
live in `docs/architecture/CONTRACT_DELTA_COMMAND_AUTHORITY_CD_2026-09-19.md`.

Python test/tool launchers must use `sys.executable` for repository-owned child
Python commands so private environments retain their dependencies. Explicit
operator-supplied runner commands keep their selected executable. Scope a
repository-only pytest plugin to the parent pytest arguments when child tools
execute tests in a foreign project; do not export it through `PYTEST_PLUGINS`.

Embedded callers import `create_api_app`, `create_cli_runtime` and
`create_webhook_app` from `orket.interfaces.runtime_entrypoints`. Keep its
module-profile authorization gate; `CompositionConfig` and `create_engine` remain
application exports through `orket.runtime`. The former runtime transport-factory
exports are retired in 0.6.19. `API_RUNTIME_LIFECYCLE.md` documents the distinction
between separate API owners and selected persistent stores.

The 0.6.39 API construction transition requires embeddings and test clients
to enter the application's lifespan before looking up runtime services or making
requests. The synchronous factory captures inputs; owned preparation and startup
acquire the runtime. Bind both settings and preferences for event-loop factory
callers. The canonical `python server.py` command performs that binding before
the loop so spawned reload workers can later import the ASGI app. Canonical reload
uses cooperative worker shutdown and waits for the old worker before replacement;
it has no forced-stop deadline. Worker startup or cleanup failure remains a
launcher failure. Both Quality jobs include the construction, server and
affected caller regressions. Retain the native process-finalization signal controls
alongside the server reload cases: cooperative worker handlers remain installed
through the serving loop, then native signal-ignore handlers remain through
interpreter teardown. The parent still joins the worker, and a failed finalizer
must fail the launcher. Retain both multiprocessing and interpreter-finalization
signal controls. Both Quality selections also retain native signal-under-lock
controls: handlers latch requests without acquiring Event locks, normal watcher
flow consumes them, and a stop during join prevents replacement. Existing reload
assertions, waits and skip rules remain unchanged.
Scoped source/installed proof and the remaining
repository-wide verification limits remain in the architectural-truth plan.

Standalone webhook apps also require their lifespan and retain one owner per
factory result. The module-default app and adapter-owned handler are retired in
0.6.20. Direct embeddings, captured input rotation, native Gitea review translation
and interruption limits live in `docs/specs/WEBHOOK_RUNTIME_LIFECYCLE.md`.

Direct extension-manager construction is synchronous and refuses an event-loop
thread in 0.6.40. Async embeddings and scripts await application
`prepare_extension_manager(...)`; direct control-plane embeddings use
`extension_workload_composition.prepare_extension_workload_control_plane_service(...)`.
The synchronous control-plane builder now lives in that composition module and
binds relative database paths at construction. Both Quality jobs retain the
native construction and competing-store regressions. Migration and partial-effect
limits: `docs/architecture/CONTRACT_DELTA_DIRECT_EXTENSION_CONSTRUCTION_D_2026-09-20.md`.

Governed submissions bind relative project, catalog, request, continuation and
database paths when the async body starts, before scheduling preparation. Callers
with an earlier admission boundary can pass `invocation_root` and `environment`.
Provider preparation copies role-model and environment inputs before inventory
awaits. Both Quality jobs retain the queued-path and provider-input regressions.
Scope and migration: `docs/architecture/CONTRACT_DELTA_GOVERNED_SUBMISSION_CAPTURE_D_2026-09-20.md`.

Wake ingress retains validated JSON before persistence; dispatch retains the SDK
request and continuation inputs before its first fence await. Dispatcher construction
captures provider environment and role-model inputs, including the API factory's
earlier snapshot. Cleanup drains owned clients through interruption and reports
close failures after attempting remaining clients. Internal value consumers migrate
to the existing SDK frozen values; public wake wire fields stay unchanged. Both
Quality jobs retain these regressions. Contract:
`docs/architecture/CONTRACT_DELTA_GOVERNED_WAKE_OWNERSHIP_D_2026-09-20.md`.

Wake claim validation and replay evidence reads retain native metadata, read-only
SQLite acquisition, queries and closure through interruption. Both Quality jobs
keep these controls with supervisor shutdown, stale-fence, replay-integrity and
public command/API guards. Successful read settlement grants no recovery or
external-effect authority. Contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`.

Outward ledger observation captures database/reader/anchor inputs and retains
native preflight, read-only queries and close. Both Quality jobs retain interruption,
paging, concurrent append, integrity and borrowed-transaction controls. A borrowed
reader does not own its caller's commit, rollback or connection closure. Contract:
`docs/specs/OUTWARD_LEDGER_STORAGE_V2.md`.

Outward initializers and transaction resource phases use captured paths and the
existing native owner. Borrowed connections supply their own prepared schema;
interrupted commit may remain durable. Required command/fixture lifetime finalizers
settle after the caller outcome is selected, retaining native failures rather than
confusing them with later caller interruption. Both Quality jobs retain native
identity/effect controls and existing admission/recovery/process guards. Contracts:
`docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md` and
`docs/specs/SHARED_IO_CANCELLATION.md`.

Canonical scaffold, dependency and deployment setup retain complete admitted
stages, including metadata, remaining files and validation. Both Quality jobs
retain their native hold/input controls and original service/epic guards. Earlier
files remain after later failure; interrupted success does not admit the next
stage. Contract: `docs/specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`.

Bootstrap synchronous settings before starting an event loop, or explicitly bind
`set_runtime_settings_context(...)` for synchronous runtime consumers. Async
settings APIs observe persistence through owned workers; they do not refresh a
bound runtime snapshot. Settings paths, strict read failures and resumable
preference migration are specified in `docs/specs/SETTINGS_INPUT_OWNERSHIP.md`.
Tests select temporary settings files and export a temporary `ORKET_DURABLE_ROOT`
for child processes, then bind explicit empty snapshots in their fixture;
production behavior does not inspect `PYTEST_CURRENT_TEST`. CLI startup binds
persisted settings after onboarding before constructing runtime components.

The canonical `orket runtime` command bootstraps environment before its event
loop. Direct async CLI embeddings must do the same before entering the loop;
engine construction captures the post-startup settings and environment, and does
not reload a second ambient `.env` in its worker. CLI engine/read ownership and
inspection scope are documented in
`docs/architecture/CONTRACT_DELTA_CLI_RUNTIME_OWNERSHIP_D_2026-09-21.md`.

Async driver embeddings await `OrketDriver.create(...)` and close the returned
driver; direct synchronous construction is restricted to pre-loop/worker use.
The interactive CLI and API chat own provider cleanup. Admitted console reads
must settle through a line, EOF or input failure before interrupted cleanup can
finish; no forced thread stop or input deadline is promised. Contract:
`docs/architecture/CONTRACT_DELTA_DRIVER_LIFETIME_D_2026-09-21.md`.

Async legacy extension embeddings use
`async with ExtensionEngineAdapter.open(RunContext(...))` to own construction and
required engine cleanup. Pre-loop direct constructors remain available with
caller-owned `await adapter.close()`. Direct loop-thread construction is refused.
Contract: `docs/architecture/CONTRACT_DELTA_LEGACY_ACTION_ENGINE_D_2026-09-21.md`.

Synchronous ConfigLoader methods refuse event-loop calls and close unstarted
coroutines. Async engine/pipeline embeddings use their `.open(...)` contexts
for captured bootstrap/path inputs, worker construction and required cleanup.
Direct engine, pipeline and runtime-context construction is pre-loop/worker
only. Existing action/result authority is retained. Migration and limits:
`docs/architecture/CONTRACT_DELTA_CONFIG_SYNC_BRIDGE_D_2026-09-21.md`.

Runtime cleanup attempts every declared resource after an earlier close failure.
Synchronous close ports use owned workers; admitted cleanup remains owned
through repeated cancellation. Multiple failures remain visible in exception
groups, and failed cleanup cannot set the engine/pipeline closed flag. Port
migration, failure handling and proof limits:
`docs/architecture/CONTRACT_DELTA_RUNTIME_RESOURCE_CLEANUP_D_2026-09-21.md`.

Async file operations own native path/file work through interruption and capture
standard path/reference values and serialized write content. Filesystem tools
retain the admitted mutation authority and existing path locks; authorized
connector dispatch keeps its bound-filesystem authority. Migration, native
current-directory observation and containment limits:
`docs/architecture/CONTRACT_DELTA_ASYNC_FILE_OPERATIONS_D_2026-09-21.md`.

Outward authorization observation owns its native worker and captures standard
metadata, arguments, roots and allowlist values before waiting. Binding retains
its run/argument inputs; dispatch rechecks argument drift after observation.
Canonical target naming, migration and bounded snapshot/ownership limits:
`docs/architecture/CONTRACT_DELTA_AUTHORIZATION_INPUTS_D_2026-09-21.md`.

Approval submission captures caller argument values before transaction acquisition
and direct transaction storage waits. Run policy, numbering and submission time
remain sampled inside the acquired transaction. Contract and migration:
`docs/architecture/CONTRACT_DELTA_APPROVAL_SUBMISSION_INPUTS_D_2026-09-21.md`.

Async sandbox-log embeddings pass a bound `SandboxOrchestrator.get_logs` callable
to `read_runtime_sandbox_logs` and retain ownership of any constructed pipeline.
Direct synchronous log reads refuse an event-loop thread; the API uses
`open_runtime_owner` for construction and required cleanup. Nonzero command exits
are failures. Contract and migration:
`docs/architecture/CONTRACT_DELTA_API_SANDBOX_LOGS_D_2026-09-21.md`.

Direct sandbox command embeddings use `create_sandbox_command_runner(...)` or
provide the core owner port, absolute cwd, full environment and finite budget.
Standard orchestrator environments now bind complete child inputs. Migration,
shared process ownership and unresolved Docker-effect limits:
`docs/architecture/CONTRACT_DELTA_SANDBOX_COMMAND_OWNERSHIP_D_2026-09-21.md`.

Async organization embeddings await `OrganizationLoop.create()` before
`run_forever()`; the canonical `orket runtime --loop` uses that factory. Direct
synchronous construction refuses an event-loop thread before configuration I/O.
The ownership, captured-input and selection contract lives in
`docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`.

Handled fatal outcomes from `orket runtime` must return a nonzero process status. The
governed-run demo default is package-owned and must not depend on the caller's current
working directory.

The standalone coordinator has its own per-application owner and in-memory card
store. Run its lifespan on embedded use and inspect retained state after a
transition failure. Startup migration, storage roots and interruption limits live
in `docs/specs/COORDINATOR_RUNTIME_LIFECYCLE.md`.

Compatibility-only source wrapper:
`python main.py [runtime arguments]` remains deprecated but supported through `0.7.x`. The hidden
`--rock <rock_name>` alias remains accepted by that wrapper and `orket runtime`, but
new callers must use `--card`; removal requires a separate accepted contract delta
and continued installed-root proof. The 0.7.0 release preserves these aliases:
`docs/architecture/CONTRACT_DELTA_CORE_SDK_0_7_0_2026-10-03.md`.

Failure report publication captures its selected root, immutable scalar identity
and rendered content before yielding. Both Quality jobs retain native capture,
file/log settlement, partial publication and refusal controls under
`docs/specs/FAILURE_REPORT_PUBLICATION.md`.

Connector supporting diagnostics preserve the primary through unexpected native
failures; SDK uncertainty retains its exact secondary and typed note. Both Quality
selections retain the isolated native controls and existing lifetime/manager guards.
Do not replace the SDK secondary protocol with the generic diagnostic marker.
Contract delta: `docs/architecture/CONTRACT_DELTA_SUPPORTING_DIAGNOSTIC_POLICY_D_2026-09-28.md`.

Epic cleanup distinguishes actual native cancellation from later caller interruption.
Preserve native rollback/close identity controls in both card/journal selections.
Pipeline composition returns the exact required approval service with its owner;
both public factory selections retain constructor-order and service-identity controls.
Team replan ownership keeps phase-selected effect ports and one count map; both
orchestrator selections retain real partial-effect/count/owner-rebinding controls.
Migration details live in the dated epic composition and scheduler contract deltas.

Gitea reconciliation/coordinator owners and coroutine SDK children prepare and
bind optional logging in the actual operation task. Direct async embeddings
retain the same requirement. Required dual-ledger and webhook events capture
supported values and their selected workspace before worker admission. Direct
dual-ledger constructors supply an absolute workspace; custom sinks keep their
borrowed-input contract. Native SDK lifetime-publication failure, including fatal
or cancellation failure, retains typed uncertainty and the unadopted exchange.
Caller-only interruption after successful publication retains its existing policy.

Native exchange-removal failure also selects typed uncertainty with its exact
cause, including cancellation/fatal failures. Successful removal preserves an
already-selected body error against later caller interruption; successful-body
interruption keeps its prior policy. Deletion may have partly or completely
applied, so the retained reference does not promise intact exchange bytes.
Both Quality selections retain actual-child, loopback HTTP, SQLite, capture,
native failure and startup controls. Contracts: `docs/specs/LOG_WRITE_SETTLEMENT.md`
and `docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md`.

Pipeline and standalone runtime-context/ConfigLoader registry construction pass
their captured settings explicitly. Selection does not rebind caller context or
silently load omitted preferences; supplied registries keep precedence. Both
Quality selections retain selection/refusal and real construction guards under
`docs/specs/SETTINGS_INPUT_OWNERSHIP.md`.

Trust handoff admission captures its package path and retains complete native
verification through interruption; direct synchronous verification refuses loop
entry. Existing package integrity/rejection rules and declared event paths stay
authoritative. Interrupted verification leaves earlier shared EXECUTING admission
without later handoff or terminal publication. Both Quality jobs retain real
package, native interruption, path and CLI controls under
`docs/specs/TRUST_HANDOFF_PACKET1_V1.md`.

Model preparation captures its invocation directory before settings and score
waits. Relative score reports use that root; Windows drive-relative paths refuse.
Every preparation requires observable CWD, including absent/absolute reports.
Existing advisory selection, byte provenance and native ownership remain under
`docs/architecture/CONTRACT_DELTA_MODEL_SCORE_ROOT_D_2026-09-28.md`.
Both Quality selections retain the root controls with existing model policy guards.

## Release and Versioning

1. Core engine release/versioning authority lives in `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
2. Core engine version source of truth is `pyproject.toml`.
3. Starting with `0.4.0`, each commit kept on `main` must advance the core engine version, keep `CHANGELOG.md` aligned, and create and push the matching annotated Git tag `v<version>`. The default release step is a patch bump; minor release steps are allowed only as defined in `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
4. Minor version bumps require closure of a roadmap-tracked major project as defined in `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
5. Do not treat UI work as the default reason for `0.4.0`; follow the active release/versioning policy and roadmap instead.
6. Use `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md` when evaluating core release readiness.
7. Use `docs/specs/CORE_RELEASE_PROOF_REPORT.md` for required minor-release proof records and store completed reports under `docs/releases/<version>/PROOF_REPORT.md`.
8. CI now enforces core version/changelog alignment, commit-range version advancement, commit-range tag alignment for pushed `main`, and tagged core release format through `.gitea/workflows/core-release-policy.yml` and `scripts/governance/check_core_release_policy.py`.
9. Final proof-gate acceptance remains checklist-backed and owned by Orket Core.
10. The canonical operator path for release-only core release prep is `python scripts/governance/prepare_core_release.py --tag v<major>.<minor>.<patch>`.
11. Use `--commit-and-tag` only after the matching changelog entry and any required proof report are complete and no unrelated worktree changes remain.
12. For normal non-release-only work, each versioned commit destined for `main` must carry its matching annotated tag on that exact commit, and the branch tip plus those tags must be pushed together. A core version bump is not complete until its matching tag is pushed.

## Testing

1. Prefer real filesystems, databases, and integration paths over mocks when practical.
   Bootstrap publication proof must retain native access failures and incomplete
   staging, exercise held-handle release/exhaustion and owned interruption, and
   distinguish Windows from POSIX rename behavior. See
   `docs/architecture/CONTRACT_DELTA_RUN_START_PUBLICATION_D_2026-09-19.md`.
2. Keep tests deterministic and isolated.
3. For refactors, prove parity with regression tests.
4. Provider-backed runtime selection and local warmup authority live in `orket/runtime/config/provider_runtime_target.py`; `orket/runtime/provider_runtime_target.py` is a one-release compatibility alias. Pure provider identity and target values live in `orket/core/contracts/provider_runtime.py`. Runtime paths and provider verification scripts must reuse these authorities and supply captured provider settings where available.
5. The general pytest suite fails closed on Docker sandbox creation through `tests/conftest.py`. Only explicit live sandbox acceptance work may create real `orket-sandbox-*` resources.
6. When maintenance work needs live sandbox baseline proof, run `python scripts/techdebt/run_live_maintenance_baseline.py --baseline-id <baseline_id> --strict`.
7. Provider-backed live proof scripts/tests that are not explicit sandbox acceptance work must set `ORKET_DISABLE_SANDBOX=1`.
8. Any flow that intentionally creates real `orket-sandbox-*` resources must prove teardown in the same execution path before temp-workspace cleanup or handoff. Do not rely on delayed TTL cleanup for routine proof runs.
9. Tests that touch the module-level `orket.state.runtime_state` singleton must use the `fresh_runtime_state` pytest fixture from `tests/conftest.py`.
10. Repository checks and review exports share the Git-visible inventory in `scripts/common/git_inventory.py`. Tests must not depend on ignored local utilities. Git discovery failures are errors, not empty inventories or permission to walk ignored trees.
11. Dependency enforcement is `python scripts/governance/check_dependency_direction.py`. Policy v2 uses the five normative layers and exact exceptions; the retired legacy-budget options have no compatibility mode. `python scripts/governance/export_dependency_graph.py` regenerates the observed graph and its separate verdict. A successful export or baseline collection does not mean the dependency verdict passes. Both commands share the same discovery, analysis and policy implementation.
12. Recognized dynamic routes require inspected syntax and unambiguous bindings, not a filename/function-name allowlist or diagnostic waiver. Keep `resolved_dynamic_routes` visible in reports. Import-interception changes require redirected/escaped/rebound controls; external-name changes require plain-string, absolute-name, namespace, builtin-identity and local-scope controls. Both Quality jobs run these checks with extension input/origin regressions. Contract: `docs/architecture/CONTRACT_DELTA_DYNAMIC_IMPORT_ANALYSIS_C_2026-09-20.md`.

Optional repository review copy: `python -m scripts.governance.export_review_packet`.
It writes `Agents/review/project_review_packet.txt` by default (`--output` overrides
the path). This is a filtered source/config copy, not retained runtime evidence or
a claim that every repository file is included. Exit 2 discloses byte/character
limit omissions; exit 1 reports discovery/read/write errors. Review the filter and
output before sharing. The ignored local `project_dump.py` is not repository
tooling or a test prerequisite.

Extension installation is async: await `ExtensionManager.install_from_repo`.
Keep real Git cancellation, failed replacement, native catalog refusal and captured
preflight regressions in both Quality selections. Preserve referenced checkouts
and catalog native lock identities. Interruption/publication limits and synchronous
worker-only catalog surfaces are specified in
`docs/architecture/CONTRACT_DELTA_EXTENSION_INSTALL_D_2026-09-19.md`.

Both Quality selections retain controller construction and queued manager-input
regressions, including real SDK children, native directory refusal and retained
interruption. Controlled directory holds measure event-loop responsiveness under
injected latency; they are not natural filesystem performance benchmarks. See
`docs/architecture/CONTRACT_DELTA_CONTROLLER_CONSTRUCTION_D_2026-09-19.md`.

Both Quality selections also retain Git interruption uncertainty controls, sandbox
deployment publication recovery and rule-simulation interruption reproducibility.
The sandbox regressions use real SQLite with controlled Docker observations;
separate live Docker proof must verify teardown. See
`docs/architecture/CONTRACT_DELTA_SANDBOX_DEPLOY_RECOVERY_D_2026-09-19.md`.
Rule-simulation interruption tests wait for a committed episode checkpoint before
interrupting and retain byte-for-byte comparison with the uninterrupted run.

Extension tests that create independent source roots must use distinct top-level
module names or separate Python processes. A cached module from another root is
an admission error, not a fixture to reuse. Source-origin and load-worker limits
live in `docs/architecture/CONTRACT_DELTA_EXTENSION_ORIGINS_CD_2026-09-19.md`.

SDK lifetime regressions use actual trusted workload children and independent
process/filesystem observations, including returning leaders with descendants.
Keep synthetic native-observation controls labeled contract proof. Uncertain
execution must retain its control-plane state and private exchange; see
`docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md`.
Controller proof also exercises installed nested workloads and the packaged
schema, explicit schema replacement, captured validation inputs and read-worker
interruption. Keep both controller regression modules in the Quality selection.

Workload publication regressions exercise real SDK/legacy paths and the actual
interaction manager, including native write refusals and retained cancellation.
Policy proof also rotates environment between actual workload stages, checks
independent database identities and overlaps runs on the same manager. Preserve
size limits and real Git/material admission controls; see
`docs/architecture/CONTRACT_DELTA_WORKLOAD_POLICY_D_2026-09-19.md`.
Fake contexts alone cannot establish lifecycle authority. Keep publication/input
ownership modules in both Quality selections; contract and proof limits live in
`docs/architecture/CONTRACT_DELTA_WORKLOAD_PUBLICATION_D_2026-09-19.md`.

### Local provider development and testing

1. Develop local provider support in this priority order: **llama.cpp**, **LM Studio**, then **Ollama**. Their runtime selection tokens are `llama_cpp`, `lmstudio`, and `ollama`.
2. Use **llama.cpp by default for future provider-backed live testing**, including governed-agent work. Explicit user selections and tests of a specific provider use that provider; deterministic tests retain their isolated fixtures.
3. If the required llama.cpp integration or environment is unavailable, report the exact blocker and prioritize enabling that path. Any proof through another provider must identify the actual provider and cannot count as llama.cpp proof.
4. llama.cpp is the default for every provider-neutral runtime and tool. Pure provider/model defaults live in `orket/core/contracts/provider_runtime.py`; runtime environment observation lives in `orket/runtime/config/defaults.py`. LM Studio and Ollama require explicit selection; an unavailable llama.cpp server must never trigger a provider switch. Ollama installation or live coverage is not a prerequisite for llama.cpp work. Existing admission gates still apply.
