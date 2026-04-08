# BR04082026 Architectural Truth and False-Green Hardening Requirements

Last updated: 2026-04-08
Status: Completed requirements archive
Owner: Orket Core
Lane type: Techdebt architecture truth and verification hardening

Implementation plan:

1. [docs/projects/archive/techdebt/BR04082026/BR04082026-IMPLEMENTATION-PLAN.md](docs/projects/archive/techdebt/BR04082026/BR04082026-IMPLEMENTATION-PLAN.md)

## Purpose

Convert the 2026-04-08 brutal architectural review into an explicit remediation contract.

This lane exists to do three things without widening into an undisciplined rewrite:

1. retire authority inversions on active runtime paths
2. remove behavioral lies and false-green proof surfaces
3. make future implementation packets easier to verify than the current architecture

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/ARCHITECTURE.md`
6. `docs/projects/techdebt/README.md`
7. `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
8. [orket/decision_nodes/contracts.py](orket/decision_nodes/contracts.py)
9. [orket/decision_nodes/api_runtime_strategy_node.py](orket/decision_nodes/api_runtime_strategy_node.py)
10. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py)
11. [orket/decision_nodes/registry.py](orket/decision_nodes/registry.py)
12. [orket/interfaces/api.py](orket/interfaces/api.py)
13. [orket/orchestration/engine.py](orket/orchestration/engine.py)
14. [orket/application/workflows/orchestrator.py](orket/application/workflows/orchestrator.py)
15. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py)
16. [orket/application/services/runtime_verifier.py](orket/application/services/runtime_verifier.py)
17. [orket/application/services/orchestrator_issue_control_plane_service.py](orket/application/services/orchestrator_issue_control_plane_service.py)
18. [orket/runtime/execution/execution_pipeline_runtime_artifacts.py](orket/runtime/execution/execution_pipeline_runtime_artifacts.py)
19. [orket/core/cards_runtime_contract.py](orket/core/cards_runtime_contract.py)
20. [orket/adapters/storage/async_protocol_run_ledger.py](orket/adapters/storage/async_protocol_run_ledger.py)
21. [orket/adapters/storage/protocol_append_only_ledger.py](orket/adapters/storage/protocol_append_only_ledger.py)
22. [orket/schema.py](orket/schema.py)
23. [tests/integration/policy_enforcement/test_runtime_policy_enforcement.py](tests/integration/policy_enforcement/test_runtime_policy_enforcement.py)
24. [tests/application/test_review_run_service.py](tests/application/test_review_run_service.py)
25. [tests/application/test_orchestrator_epic.py](tests/application/test_orchestrator_epic.py)
26. [tests/runtime/test_runtime_subpackage_boundaries.py](tests/runtime/test_runtime_subpackage_boundaries.py)
27. [tests/runtime/test_run_summary_packet1.py](tests/runtime/test_run_summary_packet1.py)
28. [tests/live/test_system_acceptance_pipeline.py](tests/live/test_system_acceptance_pipeline.py)
29. [tests/application/test_schema_environment_config.py](tests/application/test_schema_environment_config.py)

## Review Claim and Scope

This is not a claim that every file in the repository was read.

It is a claim that every issue found in this review pass is listed here and converted into requirements below.

Scope of this pass:

1. active runtime authority paths
2. orchestration and control-plane seams
3. decision-node authority boundaries
4. API surface ownership
5. runtime-verification truth claims
6. representative integration and end-to-end proof surfaces most likely to hide false green

## Observed Inventory Snapshot

Observed on 2026-04-08 in this workspace:

1. `orket/` Python files: `708`
2. Python files over 400 lines: at least `71`
3. Top oversized files:
   1. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py) `2926`
   2. [orket/interfaces/api.py](orket/interfaces/api.py) `1715`
   3. [orket/interfaces/orket_bundle_cli.py](orket/interfaces/orket_bundle_cli.py) `1158`
   4. [orket/adapters/storage/async_control_plane_record_repository.py](orket/adapters/storage/async_control_plane_record_repository.py) `1026`
   5. [orket/runtime/policy/runtime_truth_drift_checker.py](orket/runtime/policy/runtime_truth_drift_checker.py) `1018`
   6. [orket/kernel/v1/validator.py](orket/kernel/v1/validator.py) `979`
   7. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py) `801`
   8. [orket/adapters/storage/async_protocol_run_ledger.py](orket/adapters/storage/async_protocol_run_ledger.py) `770`
   9. [orket/runtime/summary/run_summary.py](orket/runtime/summary/run_summary.py) `733`
   10. [orket/kernel/v1/state/promotion.py](orket/kernel/v1/state/promotion.py) `699`
4. Classes exposing more than 10 public methods: `26`
5. Largest class surfaces:
   1. `DefaultApiRuntimeStrategyNode` in [orket/decision_nodes/api_runtime_strategy_node.py](orket/decision_nodes/api_runtime_strategy_node.py): `56`
   2. `ApiRuntimeStrategyNode` in [orket/decision_nodes/contracts.py](orket/decision_nodes/contracts.py): `51`
   3. `OrchestrationEngine` in [orket/orchestration/engine.py](orket/orchestration/engine.py): `37`
   4. `DecisionNodeRegistry` in [orket/decision_nodes/registry.py](orket/decision_nodes/registry.py): `27`
6. Representative cross-package import edges from the current codebase:
   1. `runtime -> application`: `33`
   2. `application -> runtime`: `27`
   3. `application -> adapters`: `26`
   4. `orchestration -> application`: `15`
   5. `runtime -> adapters`: `15`
   6. `interfaces -> application`: `14`
   7. `adapters -> runtime`: `11`
   8. `adapters -> application`: `3`
7. Test seam density remains very high:
   1. `monkeypatch` occurrences across `tests/`: `2645`
   2. `patch(` occurrences across `tests/`: `12`
   3. `tmp_path` occurrences across `tests/`: `4666`

These counts are not defects by themselves.

They are evidence that the current architecture is under structural pressure and that verification truth must be held to a higher standard than the current suite often applies.

## Current Truth

### Ship-risk Debt

1. Decision-node contracts are not bounded advisory seams. They explicitly authorize runtime construction, runtime bootstrap, ID generation, invocation selection, and filesystem/runtime helpers on the authority path.
   Evidence:
   1. [orket/decision_nodes/contracts.py](orket/decision_nodes/contracts.py) defines `create_session_id`, `create_preview_builder`, `create_chat_driver`, `create_execution_pipeline`, `create_engine`, `create_file_tools`, `bootstrap_environment`, and `create_orchestrator` as part of the decision-node contract surface.
   2. [orket/decision_nodes/api_runtime_strategy_node.py](orket/decision_nodes/api_runtime_strategy_node.py) reads environment variables, emits live timestamps, mints UUID-backed session ids, creates preview/chat/runtime objects, and resolves active invocations.
   3. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py) bootstraps env via `load_env()`, generates UUID-backed run ids, constructs orchestrators and providers, and reads environment flags directly.
   Why this is bad:
   1. the contract layer itself blesses the inversion, so downstream cleanup cannot enforce the target architecture while the protocol still says this behavior is valid
   2. strategy volatility remains inside execution authority rather than outside it
   3. deterministic replay and authority ownership remain harder to prove than they need to be

2. The API surface is a process-global mutable runtime host, not a thin boundary over explicit application services.
   Evidence:
   1. [orket/interfaces/api.py](orket/interfaces/api.py) resolves its runtime node through `DecisionNodeRegistry()` at import time.
   2. The module owns mutable globals for `engine`, `stream_bus`, `interaction_manager`, `extension_manager`, and `extension_runtime_service`.
   3. `create_api_app()` mutates a shared `app.state.project_root` and resets those shared globals rather than constructing an isolated runtime object graph.
   4. The same module also keeps substantial catalog discovery, file parsing, and runtime policy selection logic inline.
   Why this is bad:
   1. request behavior depends on import order and module-global state
   2. test isolation can pass through monkeypatch/reset habits rather than truthful lifecycle ownership
   3. API behavior is harder to reason about than an explicit app-factory plus injected-service model

3. The orchestrator split is facade-only. Operational complexity still lives in one giant ops file and the public orchestrator class mainly exists to preserve monkeypatch-era seams.
   Evidence:
   1. [orket/application/workflows/orchestrator.py](orket/application/workflows/orchestrator.py) re-exports patchable symbols and syncs them back into `orchestrator_ops`.
   2. `_PATCHABLE_NAMES` and `_sync_patchable_symbols()` exist specifically to keep monkeypatches working across the split.
   3. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py) remains `2926` lines.
   4. `_execute_issue_turn()` is still the dominant behavioral unit.
   5. `_build_turn_context()` is still a giant context-construction authority blob.
   Why this is bad:
   1. the split reduced import surface but not behavioral ownership
   2. tests can keep targeting patch points instead of stable contracts
   3. the largest logic seam remains difficult to review, verify, or safely evolve

4. Runtime verification over-claims truth relative to what the default verifier actually proves.
   Evidence:
   1. [orket/core/cards_runtime_contract.py](orket/core/cards_runtime_contract.py) defines one canonical `runtime_verification.json` path.
   2. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py) writes that artifact on review turns with a single fixed path and fresh timestamp.
   3. [orket/application/services/runtime_verifier.py](orket/application/services/runtime_verifier.py) defaults to `python -m compileall -q agent_output` plus an optional Python entrypoint for Python/polyglot surfaces.
   4. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md) allows the same file to stand in as a cards contract-verdict artifact.
   5. [orket/runtime/execution/execution_pipeline_runtime_artifacts.py](orket/runtime/execution/execution_pipeline_runtime_artifacts.py) can surface this file as the primary artifact output when no work artifact is recorded.
   Why this is bad:
   1. compile-only evidence is weaker than the authority posture implied by the name and by MAR usage
   2. one fixed output path is lossy across repeated turns and repeated runs
   3. the system risks narrating behavioral proof when it only proved syntax or command completion

5. Environment schema drift is intentionally tolerated on active runtime inputs.
   Evidence:
   1. [orket/schema.py](orket/schema.py) declares `EnvironmentConfig` with `extra="ignore"` and only emits a warning for unknown keys.
   2. [tests/application/test_schema_environment_config.py](tests/application/test_schema_environment_config.py) locks this behavior in as contract.
   3. [tests/integration/policy_enforcement/test_runtime_policy_enforcement.py](tests/integration/policy_enforcement/test_runtime_policy_enforcement.py) writes `language`, `runtime`, and `rules` keys into environment JSON; the targeted pytest run passed while warning that those keys were ignored.
   Why this is bad:
   1. config authors can believe a policy or runtime setting is active when it is silently discarded
   2. green tests normalize drift instead of failing closed on it
   3. operator intent is no longer trustworthy from config alone

6. The protocol ledger adapter layer still imports application workflow code and therefore violates the published dependency direction.
   Evidence:
   1. [orket/adapters/storage/async_protocol_run_ledger.py](orket/adapters/storage/async_protocol_run_ledger.py) imports `orket.application.workflows.protocol_hashing` and `tool_invocation_contracts`.
   2. [orket/adapters/storage/protocol_append_only_ledger.py](orket/adapters/storage/protocol_append_only_ledger.py) imports `canonical_json` from the application layer.
   3. The async ledger also mints timestamps directly inside the adapter.
   Why this is bad:
   1. adapters are inheriting application authority instead of translating data
   2. the published five-layer dependency map becomes descriptive fiction instead of a meaningful rule
   3. audit and replay surfaces inherit extra hidden behavior from the wrong layer

7. `OrchestrationEngine` remains too broad to be a credible single-owner runtime facade.
   Evidence:
   1. [orket/orchestration/engine.py](orket/orchestration/engine.py) resolves runtime policy through decision nodes during initialization and bootstraps the environment from there.
   2. The same class constructs control-plane repositories and services directly.
   3. The class exposes `37` public methods in the current tree.
   4. `replay_turn()` remains a sync diagnostic helper reading artifacts directly with `Path.read_text()`.
   Why this is bad:
   1. one class is carrying runtime bootstrap, orchestration, session control, approvals, archiving, kernel control-plane, and replay diagnostics
   2. the engine is not a narrow integration point; it is a broad authority bag
   3. refactoring pressure will continue to spill into tests and compatibility wrappers

8. Control-plane publication for issue dispatch is effectively a second workflow engine living beside the orchestrator.
   Evidence:
   1. [orket/application/services/orchestrator_issue_control_plane_service.py](orket/application/services/orchestrator_issue_control_plane_service.py) owns begin-dispatch, closeout, rollback, resource-authority checks, and effect publication.
   2. The service has substantial state-transition logic rather than a thin projection/publication role.
   3. The paused ControlPlane convergence lane means this duplication is known but not retired.
   Why this is bad:
   1. workflow authority is split between orchestration flow and publication flow
   2. bugs can be fixed in one side while the other keeps stale assumptions
   3. control-plane truth is harder to verify when publication logic also classifies lifecycle behavior

9. Deprecated compatibility paths remain on live authority seams.
   Evidence:
   1. [orket/decision_nodes/api_runtime_strategy_node.py](orket/decision_nodes/api_runtime_strategy_node.py) constructs `ExecutionPipeline` through `from orket.orket import ExecutionPipeline`.
   2. [docs/ROADMAP.md](docs/ROADMAP.md) already carries a future lane for `orket.orket` compatibility-shim removal.
   Why this is bad:
   1. live runtime construction is still routed through the very shim the roadmap says is debt
   2. compatibility paths remain sticky when they stay on primary authority surfaces

10. Deterministic runtime inputs are not yet disciplined enough for the truth claims Orket wants to make.
    Evidence:
    1. [orket/decision_nodes/api_runtime_strategy_node.py](orket/decision_nodes/api_runtime_strategy_node.py) generates UUID-backed session ids and wall-clock timestamps.
    2. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py) generates UUID-backed run/session ids.
    3. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py) mints fresh wall-clock timestamps for runtime verification output and pending-gate records.
    4. [orket/adapters/storage/async_protocol_run_ledger.py](orket/adapters/storage/async_protocol_run_ledger.py) mints fresh timestamps in adapter space.
    Why this is bad:
    1. deterministic replay remains weaker than the architecture narrative
    2. clock and identity generation are still scattered instead of injected and recorded deliberately

### Exploration-safe Debt

11. The target five-layer architecture is not the actual dependency map of the repo.
    Evidence:
    1. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) describes a five-layer model with strict dependency rules.
    2. Current code still shows material `runtime -> application`, `application -> runtime`, `interfaces -> application`, `adapters -> application`, and `runtime -> adapters` coupling.
    Why this matters:
    1. the architecture doc is directionally useful but not yet mechanically true
    2. future refactors can claim "alignment" while still depending on an exception-heavy real graph

12. File size and class-surface counts show that several authority seams are still too broad for reliable future change.
    Evidence:
    1. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py) `2926` lines
    2. [orket/interfaces/api.py](orket/interfaces/api.py) `1715` lines
    3. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py) `801` lines
    4. `DefaultApiRuntimeStrategyNode` exposes `56` public methods
    5. `OrchestrationEngine` exposes `37` public methods
    Why this matters:
    1. authority drift is easier to hide in oversized modules
    2. test coverage can stay broad but shallow because units are too large to isolate truthfully

13. The API module still mixes interface concerns with runtime catalog parsing, security fallback policy, lifecycle management, and object construction.
    Evidence:
    1. [orket/interfaces/api.py](orket/interfaces/api.py) discovers role/team topology, reads JSON files, owns auth fallback policy, and lazily constructs runtime subsystems from the same module.
    Why this matters:
    1. even after removing hidden proxies, the interface boundary is still carrying too much policy and filesystem behavior
    2. the current app module is not a stable seam for future packaging or process isolation

14. `OrchestrationEngine.replay_turn()` remains a diagnostic convenience method, not a canonical replay/audit operator.
    Evidence:
    1. [orket/orchestration/engine.py](orket/orchestration/engine.py) reads persisted artifacts directly and returns them structurally.
    2. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md) already defines dedicated audit operators elsewhere.
    Why this matters:
    1. the repo still exposes a tempting but non-authoritative helper on the main engine surface
    2. future users can misread it as a truthful replay verdict path

### Self-deception Debt

15. The runtime-policy "integration" tests stub out the integrated execution path they claim to exercise.
    Evidence:
    1. [tests/integration/policy_enforcement/test_runtime_policy_enforcement.py](tests/integration/policy_enforcement/test_runtime_policy_enforcement.py) is marked `integration`.
    2. It constructs a real `ExecutionPipeline`, then monkeypatches `pipeline.orchestrator.execute_epic` and the contract snapshot factories before calling the run path.
    Why this matters:
    1. the tests do prove fail-closed gates around run start
    2. they do not prove end-to-end orchestration behavior
    3. labeling them simply as integration evidence can create false confidence

16. Several review-run tests labeled integration validate fail-closed projection behavior by monkeypatching internals rather than exercising the full path.
    Evidence:
    1. [tests/application/test_review_run_service.py](tests/application/test_review_run_service.py) monkeypatches `_generate_ulid`, `run_deterministic_lane`, and `read_execution_summary` in the key drift/failure tests.
    2. The tests then assert the run closes or rejects projection drift.
    Why this matters:
    1. these are useful fail-closed tests
    2. they are not complete integrated proof that the real projection source will drift or close the same way under live conditions

17. The orchestrator runtime-verifier tests patch the verifier and then assert report shaping.
    Evidence:
    1. [tests/application/test_orchestrator_epic.py](tests/application/test_orchestrator_epic.py) replaces `RuntimeVerifier` with local fake classes for the runtime-guard failure paths.
    2. The tests then assert issue status changes and `runtime_verification.json` structure.
    Why this matters:
    1. these tests prove decision handling after a verifier result exists
    2. they do not prove the real verifier produces the claimed signals or artifact semantics

18. The runtime boundary suite is structural-only and can pass while the wider repo keeps inverted dependencies.
    Evidence:
    1. [tests/runtime/test_runtime_subpackage_boundaries.py](tests/runtime/test_runtime_subpackage_boundaries.py) checks shim behavior, `__all__`, and AST import shapes inside `orket.runtime`.
    Why this matters:
    1. the suite is useful hygiene
    2. it is not proof that the overall repo honors the architectural layering described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

19. The primary "end-to-end" acceptance test uses a dummy provider, not a live model path.
    Evidence:
    1. [tests/live/test_system_acceptance_pipeline.py](tests/live/test_system_acceptance_pipeline.py) is marked `end_to_end`.
    2. `test_system_acceptance_role_pipeline_with_guard()` patches `LocalModelProvider` with a dummy multi-role provider.
    3. The true live path is separately gated behind `ORKET_LIVE_ACCEPTANCE`.
    Why this matters:
    1. the canonical acceptance route is still mostly proving orchestration against a controlled fake provider
    2. the test name and mark can be read as stronger proof than is actually present

20. Even the live acceptance verifier assertions are too weak for the authority claimed by `runtime_verification.json`.
    Evidence:
    1. [tests/live/test_system_acceptance_pipeline.py](tests/live/test_system_acceptance_pipeline.py) only checks that the file exists and that `ok` is a bool and `command_results` is a list.
    Why this matters:
    1. a compile-only or structurally shaped artifact can satisfy the test
    2. the suite does not prove that the verifier checked meaningful runtime behavior

21. Runtime summary tests and runtime artifact selection logic encourage the system to treat `runtime_verification.json` as a primary artifact when no real work artifact is recorded.
    Evidence:
    1. [orket/runtime/execution/execution_pipeline_runtime_artifacts.py](orket/runtime/execution/execution_pipeline_runtime_artifacts.py) promotes the verifier artifact to `primary_artifact_output` if no primary work artifact exists.
    2. [tests/runtime/test_run_summary_packet1.py](tests/runtime/test_run_summary_packet1.py) explicitly encodes scenarios where `runtime_verification.json` becomes the preserved artifact output.
    Why this matters:
    1. support evidence can be mistaken for authored work output
    2. downstream audit/reporting layers can over-read verifier presence as product output truth

22. The green test run already demonstrated a standardized false-green tolerance for ignored environment keys.
    Evidence:
    1. The targeted run of [tests/integration/policy_enforcement/test_runtime_policy_enforcement.py](tests/integration/policy_enforcement/test_runtime_policy_enforcement.py) passed while warning that `language`, `runtime`, and `rules` were ignored.
    Why this matters:
    1. this is not just a theoretical schema issue
    2. the current suite is already green while configuration intent is being discarded

## Resolution Goal

This lane is complete only when Orket can truthfully claim all of the following:

1. decision nodes are advisory seams and no longer runtime authority owners
2. the API runtime is constructed through explicit, isolated ownership instead of module-global mutable state
3. orchestration behavior is decomposed into reviewable, testable, bounded application services
4. runtime verification artifacts describe exactly what was checked and are not used as stronger proof than they provide
5. architectural compliance is harder to violate accidentally and easier to verify mechanically
6. tests do not present patched or structural proof as live behavior proof

## Scope

In scope:

1. extracting and enforcing bounded authority rules for decision nodes, API runtime setup, orchestration, and verifier truth
2. shrinking or decomposing oversized authority seams when needed to satisfy those rules
3. correcting false-green or over-claimed tests and relabeling proof honestly
4. updating docs and source-of-truth contracts wherever authority boundaries change

Out of scope:

1. broad product redesign unrelated to these authority and verification defects
2. speculative framework swaps
3. performance tuning not required by the truth and architecture work
4. adding new compatibility shims to preserve the current drift

## Requirements

### R1. Decision nodes must become advisory-only seams

1. The protocol surface in [orket/decision_nodes/contracts.py](orket/decision_nodes/contracts.py) must stop defining runtime object factories, environment bootstrap hooks, and direct identity generation as valid decision-node responsibilities.
2. Runtime construction must move behind deterministic application or runtime services with explicit ownership.
3. Decision nodes may select among supplied options, but they must not:
   1. call `load_env()`
   2. mint UUIDs or timestamps for runtime truth
   3. instantiate orchestrators, pipelines, engines, providers, or file tools
   4. reach into environment state for missing execution context
4. Any remaining exception must be documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) as a temporary boundary violation with a tracked removal target.

### R2. API runtime ownership must be explicit and isolated

1. [orket/interfaces/api.py](orket/interfaces/api.py) must stop relying on module-global mutable runtime objects as the authoritative runtime host.
2. `create_api_app()` must construct an isolated runtime graph for the returned app instead of mutating shared module state.
3. App lifecycle behavior must be resettable without import-order dependence.
4. Interface modules must stop carrying avoidable runtime policy, catalog parsing, and runtime object construction logic inline when an application service can own it more truthfully.

### R3. Orchestrator authority must be decomposed into bounded units

1. [orket/application/workflows/orchestrator.py](orket/application/workflows/orchestrator.py) must stop existing primarily as a monkeypatch bridge into [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py).
2. `_PATCHABLE_NAMES` plus `_sync_patchable_symbols()` compatibility machinery must be removed from the main authority path.
3. `_execute_issue_turn()` and `_build_turn_context()` must be decomposed into bounded application services or helpers with explicit ownership.
4. No new authority unit created by this lane may exceed the repository size rules without clear justification.

### R4. Runtime verification must fail closed on proof quality

1. `runtime_verification.json` must either become a truthful, scoped support artifact or be strengthened until its name and authority use are deserved.
2. The verifier report must explicitly identify:
   1. what was syntax-only
   2. what was command execution
   3. what was behavioral verification
   4. what, if anything, was not evaluated
3. Compile-only or import-only checks must not be presented as authoritative proof that a task contract was satisfied.
4. The runtime-verification path must preserve run/turn/issue provenance and must not silently overwrite materially distinct verifier results.
5. MAR-facing docs and code must remain aligned with the actual evidence quality the verifier can produce.

### R5. Environment schema truth must fail closed

1. Unknown environment keys must no longer be silently ignored on authoritative runtime configuration paths.
2. If backward compatibility requires a transition period, the transition must:
   1. surface explicit degraded or blocked status
   2. make ignored keys visible in a machine-checkable artifact
   3. have a defined removal target
3. Tests must stop encoding "ignored unknown keys with warning" as the desired steady state.

### R6. Adapters must stop importing application workflow authority

1. Adapter modules under [orket/adapters/storage/](orket/adapters/storage/) must not import application workflow modules for canonical hashing, contracts, or event logic.
2. Shared logic needed by both layers must be extracted into an allowed lower layer or a neutral utility with clear ownership.
3. Timestamps, digests, and event framing on adapter boundaries must come from explicit inputs or shared lower-layer contracts rather than adapter-local authority decisions.

### R7. `OrchestrationEngine` must become a narrower runtime facade

1. Engine bootstrap must not route through decision-node runtime-authority hooks.
2. `OrchestrationEngine` must shed non-essential responsibilities until its public surface is materially smaller and easier to verify.
3. Diagnostic helpers such as `replay_turn()` must either:
   1. move to a more truthful audit/debug operator surface, or
   2. remain explicitly documented as non-authoritative helpers that do not produce replay verdicts
4. The engine must depend on explicit service composition rather than constructing broad control-plane and workflow authority inline.

### R8. Control-plane issue-dispatch logic must converge on one authority owner

1. Issue-dispatch lifecycle truth must not remain split across orchestration flow and a second workflow-like publication service.
2. The lane must either:
   1. converge the behavior into the ControlPlane lane authority, or
   2. define a clear single-owner contract between orchestration and publication services
3. Publication services must not silently accumulate policy and classification logic that belongs to the workflow authority.

### R9. Deterministic runtime inputs must be centralized and recorded

1. Wall-clock timestamps and generated IDs used on authority paths must come from explicit injected inputs or a clearly owned runtime-input service.
2. Decision nodes, adapters, and workflow helpers must stop minting fresh identity/time values opportunistically.
3. Any remaining fresh runtime inputs must be recorded in the authoritative artifact path that depends on them.

### R10. Test labels and proof claims must match the real path exercised

1. Mock-heavy or monkeypatch-heavy tests must not be the only proof behind claims about runtime truth, integration truth, or end-to-end behavior.
2. Tests that patch the primary behavior they claim to verify must be relabeled or supplemented with higher-layer proof.
3. `integration` means the actual integration path executes.
4. `end-to-end` means the end-to-end path executes without replacing the primary runtime dependency with a fake while still presenting the test as canonical live proof.
5. Structural hygiene tests must be described as structural proof only.
6. Acceptance tests must prove stronger semantics for runtime verification than "artifact exists and has a few typed fields."

### R11. Support artifacts must not be narrated as authored output

1. Runtime-summary and artifact-provenance logic must distinguish clearly between:
   1. authored work product
   2. support verification artifact
   3. inferred or degraded fallback artifact
2. `runtime_verification.json` must not become the primary output of a successful run unless the governing contract explicitly says the run's primary product is the verification record itself.
3. Packet/reconstruction tests must reinforce this distinction rather than blur it.

### R12. Documentation and code truth must converge in the same change

1. Any implementation packet opened from this requirements lane must update:
   1. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) when dependency or ownership rules materially change
   2. [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md) when canonical runtime entrypoints or proof commands change
   3. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md) when verifier or audit evidence contracts change
2. The lane must not close while architecture docs still describe a cleaner boundary than the code actually implements.

## Testing and Verification Requirements

### Structural Proof

1. Add or update targeted tests for:
   1. decision-node contract shrinkage
   2. API runtime isolation and reset behavior
   3. orchestrator decomposition seams
   4. verifier evidence classification
   5. artifact-provenance separation between work output and support verification
   6. environment schema fail-closed behavior
   7. adapter dependency enforcement
2. Structural tests may prove architecture mechanics, but they must be labeled structural or contract truthfully.

### Integration Proof

1. Integration proof for this lane must exercise real orchestration, runtime-verifier, and control-plane behavior without patching out the very integration under test.
2. If a test replaces a provider, verifier, orchestrator, or projection source, its scope must be described narrowly and truthfully.
3. For non-sandbox proof, set `ORKET_DISABLE_SANDBOX=1`.

### End-to-End or Live Proof

1. Any closure claim about runtime-verifier truth must include at least one path that exercises the real verifier behavior end to end.
2. Any closure claim about test-truth hardening must show that previously false-green proof surfaces now fail closed or are relabeled honestly.
3. If live provider proof is blocked, the blocker must be recorded exactly and the lane must not claim stronger proof than was actually run.

## Conclusive Gate

This lane is conclusive only when all of the following are true:

1. decision-node contracts no longer encode runtime object construction, environment bootstrap, or identity generation as normal runtime strategy behavior
2. the API runtime can be created and reset without relying on shared module-global authority state
3. the main orchestrator authority path is no longer dominated by the current facade-plus-ops split
4. runtime verification artifacts truthfully state what was checked and are not over-read as stronger proof than they provide
5. unknown environment keys fail closed or are surfaced in an explicitly degraded, machine-checkable way
6. adapter dependencies no longer import application workflow modules in the cited ledger paths
7. patched or structural tests are no longer the primary proof offered for the behaviors called out in this review
8. `python scripts/governance/check_docs_project_hygiene.py` passes

## Residual Truth Rule

If this lane cannot retire all defects in one packet without widening scope unsafely:

1. split work into bounded implementation packets by authority seam
2. keep this requirements document as the single remediation contract until the user explicitly accepts or retires it
3. do not claim architectural compliance or live-proof recovery beyond the exact seams actually fixed and reverified
