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

Standalone webhook apps also require their lifespan and retain one owner per
factory result. The module-default app and adapter-owned handler are retired in
0.6.20. Direct embeddings, captured input rotation, native Gitea review translation
and interruption limits live in `docs/specs/WEBHOOK_RUNTIME_LIFECYCLE.md`.

Bootstrap synchronous settings before starting an event loop, or explicitly bind
`set_runtime_settings_context(...)` for synchronous runtime consumers. Async
settings APIs observe persistence through owned workers; they do not refresh a
bound runtime snapshot. Settings paths, strict read failures and resumable
preference migration are specified in `docs/specs/SETTINGS_INPUT_OWNERSHIP.md`.
Tests select temporary settings files and export a temporary `ORKET_DURABLE_ROOT`
for child processes, then bind explicit empty snapshots in their fixture;
production behavior does not inspect `PYTEST_CURRENT_TEST`. CLI startup binds
persisted settings after onboarding before constructing runtime components.

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

Optional repository review copy: `python -m scripts.governance.export_review_packet`.
It writes `Agents/review/project_review_packet.txt` by default (`--output` overrides
the path). This is a filtered source/config copy, not retained runtime evidence or
a claim that every repository file is included. Exit 2 discloses byte/character
limit omissions; exit 1 reports discovery/read/write errors. Review the filter and
output before sharing. The ignored local `project_dump.py` is not repository
tooling or a test prerequisite.

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
Fake contexts alone cannot establish lifecycle authority. Keep publication/input
ownership modules in both Quality selections; contract and proof limits live in
`docs/architecture/CONTRACT_DELTA_WORKLOAD_PUBLICATION_D_2026-09-19.md`.

### Local provider development and testing

1. Develop local provider support in this priority order: **llama.cpp**, **LM Studio**, then **Ollama**. Their runtime selection tokens are `llama_cpp`, `lmstudio`, and `ollama`.
2. Use **llama.cpp by default for future provider-backed live testing**, including governed-agent work. Explicit user selections and tests of a specific provider use that provider; deterministic tests retain their isolated fixtures.
3. If the required llama.cpp integration or environment is unavailable, report the exact blocker and prioritize enabling that path. Any proof through another provider must identify the actual provider and cannot count as llama.cpp proof.
4. llama.cpp is the default for every provider-neutral runtime and tool. Pure provider/model defaults live in `orket/core/contracts/provider_runtime.py`; runtime environment observation lives in `orket/runtime/config/defaults.py`. LM Studio and Ollama require explicit selection; an unavailable llama.cpp server must never trigger a provider switch. Ollama installation or live coverage is not a prerequisite for llama.cpp work. Existing admission gates still apply.
