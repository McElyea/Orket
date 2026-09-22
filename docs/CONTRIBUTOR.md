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

## Canonical Commands

Provider HTTP catalogs use captured proxy, certificate and optional TLS key-log
inputs with verified TLS and disabled redirects. Native client construction and
all acquired resources remain owned through interruption and cleanup failure.
Explicit empty mappings have no ambient or OS proxy-registry fallback. Non-finite
HTTP budgets and unsupported NO_PROXY CIDR fail explicitly. Inference-client
composition and TLS-library internals remain separate obligations. Contract:
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
readiness criteria, response schemas and conditional settings-write conflicts intact.
Run the runtime-policy input/request/lifetime controls in both Quality jobs when
changing this boundary. Contract: `docs/specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`.

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
affected caller regressions. Scoped source/installed proof and the remaining
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
`python main.py [runtime arguments]` remains supported through `0.6.x`. The hidden
`--rock <rock_name>` alias remains accepted by that wrapper and `orket runtime`, but
new callers must use `--card`; removal requires an explicit `0.7.0` contract delta.

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
