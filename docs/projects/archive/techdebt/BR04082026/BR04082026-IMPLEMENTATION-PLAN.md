# BR04082026 Architectural Truth and False-Green Hardening Implementation Plan

Last updated: 2026-04-08
Status: Completed implementation plan
Owner: Orket Core
Lane type: Techdebt architecture truth and verification hardening

Requirements authority:

1. [docs/projects/archive/techdebt/BR04082026/BR04082026-REQUIREMENTS.md](docs/projects/archive/techdebt/BR04082026/BR04082026-REQUIREMENTS.md)

## Purpose

Turn the BR04082026 review and requirements lane into one bounded execution plan.

This plan exists to reduce three kinds of drift without collapsing into a broad rewrite:

1. authority drift between target architecture and live runtime behavior
2. evidence drift between runtime claims and what the verifier actually proves
3. proof drift between green tests and real integrated behavior

## Planning Posture

This lane will not be executed as one giant refactor.

The work is intentionally split into bounded packets so each slice can:

1. reduce one authority inversion at a time
2. produce truthful proof at the highest practical layer
3. avoid introducing new shims, duplicate authority, or narrative-only compliance

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/ARCHITECTURE.md`
6. [docs/projects/archive/techdebt/BR04082026/BR04082026-REQUIREMENTS.md](docs/projects/archive/techdebt/BR04082026/BR04082026-REQUIREMENTS.md)
7. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md)
8. [docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md)
9. [orket/decision_nodes/contracts.py](orket/decision_nodes/contracts.py)
10. [orket/decision_nodes/api_runtime_strategy_node.py](orket/decision_nodes/api_runtime_strategy_node.py)
11. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py)
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
22. cited proof surfaces under `tests/`

## Goal

Close BR04082026 by making the live codebase materially closer to the target architecture and materially harder to verify falsely.

The plan is complete only when:

1. the decision-node layer is advisory rather than authoritative
2. API and engine runtime hosts use explicit ownership instead of hidden shared state
3. orchestration and issue-dispatch behavior have one clear authority path each
4. runtime verification artifacts say exactly what they prove
5. green tests no longer overstate live behavior

## Decision Lock

This plan is locked to seven execution packets.

Lock rules:

1. no packet may introduce a new compatibility shim without explicit user approval
2. no packet may create a new module-global runtime singleton as a shortcut
3. no packet may claim live-proof recovery through compile-only, import-only, or monkeypatch-only evidence
4. each packet must update same-change docs if it changes runtime entrypoints, authority boundaries, or proof semantics
5. if a packet expands into a broad runtime rewrite, stop and split the packet instead of widening the lane silently

## Recommended Direction

### Architecture Choice

1. Recommended:
   1. freeze authority boundaries first
   2. move construction/bootstrap/identity concerns into explicit services
   3. keep decision nodes as structured choice functions
2. Not recommended:
   1. deleting decision nodes first and rebuilding later
   2. relying on documentation-only compliance while contracts still bless the opposite behavior

### Proof Choice

1. Recommended:
   1. upgrade proof surfaces as the code changes land
   2. make support artifacts visibly weaker than authored outputs
   3. prefer real integrated execution paths over patched success
2. Not recommended:
   1. preserving current green tests and calling the lane verified
   2. treating `runtime_verification.json` as authoritative product output by default

### Packaging Choice

1. Recommended:
   1. isolate API runtime ownership
   2. narrow engine and orchestrator surfaces
   3. keep future packaging and process isolation options open
2. Not recommended:
   1. anchoring the implementation in more global mutable state
   2. binding the lane to current import-order side effects

## Packet 1: Freeze Runtime Authority Boundaries

Objective:

1. remove runtime construction, bootstrap, and identity authority from decision-node contracts

Primary surfaces:

1. [orket/decision_nodes/contracts.py](orket/decision_nodes/contracts.py)
2. [orket/decision_nodes/api_runtime_strategy_node.py](orket/decision_nodes/api_runtime_strategy_node.py)
3. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py)
4. [orket/orchestration/engine.py](orket/orchestration/engine.py)
5. new explicit runtime input or wiring services under `orket/application/` or `orket/runtime/`
6. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

Actions:

1. Define explicit ownership for:
   1. runtime clock inputs
   2. run or session identity generation
   3. environment bootstrap
   4. runtime object construction
2. Shrink decision-node contracts so they select strategy from explicit inputs instead of constructing runtime objects.
3. Remove factory and bootstrap responsibilities from live decision-node implementations on touched paths.
4. Remove the `orket.orket` compatibility shim from live API runtime construction.
5. Add contract checks that fail if the touched decision-node contracts regain runtime-authority methods.

Acceptance:

1. touched decision-node contracts no longer define runtime object construction or bootstrap as normal behavior
2. touched live paths no longer mint IDs or timestamps inside decision nodes
3. touched live paths no longer import `ExecutionPipeline` through `orket.orket`

Proof target:

1. contract
2. integration

## Packet 2: Harden Config And Adapter Boundaries

Objective:

1. fail closed on configuration drift and remove adapter imports from the application layer on cited ledger paths

Primary surfaces:

1. [orket/schema.py](orket/schema.py)
2. [orket/adapters/storage/async_protocol_run_ledger.py](orket/adapters/storage/async_protocol_run_ledger.py)
3. [orket/adapters/storage/protocol_append_only_ledger.py](orket/adapters/storage/protocol_append_only_ledger.py)
4. [tests/application/test_schema_environment_config.py](tests/application/test_schema_environment_config.py)
5. [tests/integration/policy_enforcement/test_runtime_policy_enforcement.py](tests/integration/policy_enforcement/test_runtime_policy_enforcement.py)
6. any extracted lower-layer hashing or contract helpers needed by both application and adapters

Actions:

1. Replace silent unknown-environment-key acceptance with one fail-closed or explicitly degraded path.
2. Extract shared hashing or tool-contract helpers into an allowed lower layer.
3. Remove direct adapter imports of application workflow modules on the cited ledger paths.
4. Move timestamp creation on touched adapter paths behind explicit inputs or shared authority helpers.
5. Add structural checks that keep these boundary regressions from returning silently.

Acceptance:

1. unknown environment keys on the touched runtime path are not silently ignored as normal success
2. the cited adapter files no longer import application workflow modules
3. policy-enforcement proof reflects the real config behavior truthfully

Proof target:

1. contract
2. integration

## Packet 3: Isolate API Runtime Ownership

Objective:

1. replace module-global API runtime authority with app-scoped explicit ownership

Primary surfaces:

1. [orket/interfaces/api.py](orket/interfaces/api.py)
2. routers or helpers reached through that module
3. API tests that currently depend on module-global reset behavior

Actions:

1. Introduce an explicit per-app service container or app-runtime context.
2. Move engine, stream bus, interaction manager, extension manager, and extension runtime service ownership onto that app-scoped context.
3. Keep any remaining module-level indirection minimal and explicitly documented.
4. Pull avoidable catalog discovery or filesystem parsing out of the API transport module where a service boundary is clearer.
5. Add proof that repeated app creation or isolated app instances do not share hidden runtime state.

Acceptance:

1. `create_api_app()` no longer relies on shared mutable module-global runtime objects as the authoritative host
2. lifecycle initialization and teardown are explainable from app state alone
3. app isolation proof exists at the integration level

Proof target:

1. contract
2. integration

## Packet 4: Decompose Orchestrator Authority

Objective:

1. turn the current facade-plus-ops split into real bounded orchestration units

Primary surfaces:

1. [orket/application/workflows/orchestrator.py](orket/application/workflows/orchestrator.py)
2. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py)
3. extracted orchestration services or helpers under `orket/application/`
4. representative orchestrator tests in [tests/application/test_orchestrator_epic.py](tests/application/test_orchestrator_epic.py)

Actions:

1. Extract `_execute_issue_turn()` into smaller owned services or helpers.
2. Extract `_build_turn_context()` into a bounded context builder with explicit inputs and outputs.
3. Extract failure handling and pending-gate creation from the monolith where it clarifies authority.
4. Remove `_PATCHABLE_NAMES` and `_sync_patchable_symbols()` from the main authority path.
5. Convert monkeypatch-era test seams into service-boundary or contract-boundary seams where possible.

Acceptance:

1. the touched orchestrator path no longer depends on monkeypatch sync glue for normal execution
2. issue-turn and turn-context authority are no longer hidden inside giant undifferentiated functions
3. touched orchestration files become materially smaller and easier to review

Proof target:

1. contract
2. integration

## Packet 5: Narrow Engine And Issue-Dispatch Authority

Objective:

1. reduce `OrchestrationEngine` scope and define one clear owner for issue-dispatch control-plane truth

Primary surfaces:

1. [orket/orchestration/engine.py](orket/orchestration/engine.py)
2. [orket/orchestration/engine_services.py](orket/orchestration/engine_services.py)
3. [orket/application/services/orchestrator_issue_control_plane_service.py](orket/application/services/orchestrator_issue_control_plane_service.py)
4. [docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md) if touched

Actions:

1. Remove non-essential engine responsibilities from the main runtime facade.
2. Relocate or explicitly downgrade `replay_turn()` so it is not mistaken for a canonical replay verdict path.
3. Define a single-owner contract for issue-dispatch lifecycle truth between orchestration and control-plane publication.
4. If broader ControlPlane convergence becomes necessary, reopen only a bounded issue-dispatch slice and sync both lane docs in the same change.
5. Keep engine service composition explicit rather than constructing broad control-plane behavior inline.

Acceptance:

1. the touched engine path is materially narrower than the current authority bag
2. issue-dispatch truth is no longer effectively owned by two workflow engines
3. any remaining cross-lane dependency with ControlPlane is explicit and documented

Proof target:

1. integration
2. structural

## Packet 6: Rebuild Verifier Truth And Artifact Provenance

Objective:

1. make runtime verification and artifact provenance say exactly what they prove

Primary surfaces:

1. [orket/application/services/runtime_verifier.py](orket/application/services/runtime_verifier.py)
2. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py)
3. [orket/core/cards_runtime_contract.py](orket/core/cards_runtime_contract.py)
4. [orket/runtime/execution/execution_pipeline_runtime_artifacts.py](orket/runtime/execution/execution_pipeline_runtime_artifacts.py)
5. [tests/runtime/test_run_summary_packet1.py](tests/runtime/test_run_summary_packet1.py)
6. [tests/live/test_system_acceptance_pipeline.py](tests/live/test_system_acceptance_pipeline.py)
7. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md)

Actions:

1. Classify verifier evidence explicitly:
   1. syntax-only
   2. command execution
   3. behavioral verification
   4. not evaluated
2. Preserve run, turn, issue, and retry provenance on verifier outputs.
3. Replace the current lossy single-path overwrite behavior with a truthful index or materially richer artifact layout.
4. Stop promoting `runtime_verification.json` as primary authored output by default.
5. Update MAR-facing docs and packet1 or artifact-provenance logic to match the strengthened semantics.
6. Strengthen acceptance assertions so verifier proof quality is tested, not just file existence and field types.

Acceptance:

1. the verifier artifact cannot be mistaken for stronger proof than it provides
2. support verification artifacts and authored outputs are clearly separated
3. MAR and runtime-summary behavior align with the actual evidence surface

Proof target:

1. contract
2. integration
3. live

## Packet 7: Rebuild Proof Honesty On The Cited Test Surfaces

Objective:

1. ensure the green suite stops overstating the paths it actually exercises

Primary surfaces:

1. [tests/integration/policy_enforcement/test_runtime_policy_enforcement.py](tests/integration/policy_enforcement/test_runtime_policy_enforcement.py)
2. [tests/application/test_review_run_service.py](tests/application/test_review_run_service.py)
3. [tests/application/test_orchestrator_epic.py](tests/application/test_orchestrator_epic.py)
4. [tests/runtime/test_runtime_subpackage_boundaries.py](tests/runtime/test_runtime_subpackage_boundaries.py)
5. [tests/live/test_system_acceptance_pipeline.py](tests/live/test_system_acceptance_pipeline.py)
6. any new higher-layer proof tests required by the earlier packets

Actions:

1. Relabel patched or structural tests so their layer claims are honest.
2. Add real integration-path tests where patched tests currently stand in for runtime truth.
3. Keep structural hygiene tests, but present them as structural proof only.
4. Add one or more real-path end-to-end or live proofs for the touched verifier and orchestration flows.
5. Update doc authority if the canonical proof commands or proof taxonomy change.

Acceptance:

1. patched or structural tests are no longer the primary proof for the cited behaviors
2. each cited false-green area has at least one truthful higher-layer proof path or an explicit blocker
3. lane closeout cannot rely on mislabeled green tests

Proof target:

1. integration
2. live
3. structural

## Execution Sequence

1. Packet 1 first, because contract and authority shrinkage must happen before higher-layer cleanup can be trusted.
2. Packet 2 second, because config and adapter boundary hardening reduce low-level drift early.
3. Packet 3 third, so API packaging and lifecycle ownership stop depending on hidden globals.
4. Packet 4 fourth, once authority boundaries are clearer and the orchestrator can be decomposed without preserving monkeypatch-era structure.
5. Packet 5 fifth, after orchestration responsibilities are clearer enough to narrow engine and issue-dispatch ownership honestly.
6. Packet 6 sixth, after the authority surfaces that emit verification artifacts have been made clearer.
7. Packet 7 last as the explicit proof-surface sweep, while still requiring each earlier packet to improve its own tests in the same change.

## Verification Plan

Structural gates:

1. `python scripts/governance/check_docs_project_hygiene.py`
2. architecture or AST checks added for decision-node, adapter, and artifact-provenance boundaries
3. targeted contract tests for packet-local boundary rules

Canonical regression gates:

1. `python -m pytest -q tests/runtime/test_runtime_subpackage_boundaries.py`
2. `python -m pytest -q tests/integration/policy_enforcement/test_runtime_policy_enforcement.py`
3. `python -m pytest -q tests/application/test_review_run_service.py`
4. `python -m pytest -q tests/application/test_orchestrator_epic.py`
5. `python -m pytest -q tests/live/test_system_acceptance_pipeline.py`

Live or higher-layer gates:

1. non-sandbox runs must set `ORKET_DISABLE_SANDBOX=1`
2. any verifier truth-claim packet must include at least one real-path verification flow
3. any end-to-end claim must state whether the observed path was `primary`, `fallback`, `degraded`, or `blocked`

## Blocker Handling

1. If decision-node contract shrinkage requires a new durable contract, extract that contract into `docs/specs/` before continuing the packet.
2. If issue-dispatch convergence requires reopening the full paused ControlPlane lane instead of a bounded slice, stop and document the blocker rather than smuggling that work into BR04082026.
3. If verifier truth cannot be repaired without changing MAR semantics materially, stop and update the spec first rather than silently changing code-only behavior.
4. If a cited false-green area cannot be replaced with truthful higher-layer proof because of environment limits, record the exact blocker and do not leave the old test mislabeled as if it were sufficient proof.

## Stop Conditions

1. Stop and split the packet if a change would widen the repo's active compatibility surface.
2. Stop if a packet begins to couple unrelated authority seams only because they are both large.
3. Stop if the only available proof for a packet is mock-heavy and a higher practical layer has not been attempted.
4. Stop if doc truth and code truth diverge and the packet cannot reconcile them in the same change.

## Completion Gate

This plan closed on 2026-04-08 after the conclusive gate in [docs/projects/archive/techdebt/BR04082026/BR04082026-REQUIREMENTS.md](docs/projects/archive/techdebt/BR04082026/BR04082026-REQUIREMENTS.md) was satisfied and archive closeout was completed in the same change.

## Execution Status

Current truthful status:

1. Packet 1 completed on 2026-04-08.
2. Packet 1 moved API/engine/pipeline construction, env bootstrap, and session-id or timestamp minting on the touched live paths into explicit services:
   1. `orket/application/services/api_runtime_host_service.py`
   2. `orket/application/services/runtime_input_service.py`
   3. `orket/runtime/config/runtime_bootstrap.py`
   4. `orket/runtime/execution/pipeline_wiring_service.py`
3. Packet 1 proof ran with `ORKET_DISABLE_SANDBOX=1` and passed on the targeted contract or integration slice:
   1. `tests/application/test_runtime_authority_contracts.py`
   2. `tests/application/test_decision_node_override_matrix.py`
   3. `tests/application/test_decision_nodes_planner.py`
   4. `tests/runtime/test_epic_run_orchestrator.py`
   5. `tests/runtime/test_route_decision_artifact.py`
   6. `tests/application/test_execution_pipeline_issue_entrypoints.py`
   7. `tests/interfaces/test_api.py`
   8. `tests/interfaces/test_api_task_lifecycle.py`
   9. `tests/interfaces/test_api_composition_isolation.py`
   10. `tests/application/test_engine_refactor.py`
   11. `tests/runtime/test_runtime_context.py`
   12. `tests/runtime/test_runtime_subpackage_boundaries.py`
4. Packet 2 completed on 2026-04-08.
5. Packet 2 hardened the cited config and adapter boundaries on the touched live paths:
   1. authoritative runtime environment loading now fails closed on undeclared keys via `orket/schema.py` and `orket/runtime/config/config_loader.py`
   2. shared protocol hashing and tool-invocation contract helpers now live under `orket/runtime/registry/`
   3. the cited ledger adapters no longer import `orket.application.workflows.*`
   4. the touched async protocol ledger path now accepts an explicit timestamp factory instead of minting timestamps inline only
6. Packet 2 proof ran with `ORKET_DISABLE_SANDBOX=1` and passed on the targeted contract or integration slice:
   1. `tests/application/test_schema_environment_config.py`
   2. `tests/application/test_adapter_boundary_contracts.py`
   3. `tests/application/test_protocol_hashing.py`
   4. `tests/application/test_async_protocol_run_ledger.py`
   5. `tests/application/test_turn_artifact_writer.py`
   6. `tests/application/test_turn_tool_dispatcher_replay_isolation.py`
   7. `tests/application/test_execution_pipeline_protocol_run_ledger.py`
   8. `tests/application/test_execution_pipeline_run_ledger.py`
   9. `tests/contracts/test_run_evidence_graph_projection_validation.py`
   10. `tests/runtime/test_protocol_receipt_materializer.py`
   11. `tests/runtime/test_run_graph_reconstruction.py`
   12. `tests/runtime/test_run_summary.py`
   13. `tests/runtime/test_runtime_subpackage_boundaries.py`
   14. `tests/runtime/test_epic_run_orchestrator.py`
   15. `tests/integration/policy_enforcement/test_runtime_policy_enforcement.py`
   16. `tests/integration/test_turn_executor_control_plane_evidence.py`
   17. `tests/scripts/test_publish_protocol_rollout_artifacts.py`
7. Packet 3 completed on 2026-04-08.
8. Packet 3 moved authoritative API runtime ownership onto the FastAPI app-scoped context on the touched live path:
   1. `orket/interfaces/api.py` now owns runtime members through `app.state.api_runtime_context`
   2. `orket/interfaces/api_runtime_context.py` defines the explicit app-runtime context contract
   3. `create_api_app()` now replaces the app-scoped context for the active project root instead of treating module globals as the authoritative owner
   4. env-sensitive API runtime owners such as `StreamBus` and `InteractionManager` remain lazy, while module-level runtime symbols survive only as documented compatibility aliases for the drained test surface
9. Packet 3 proof ran with `ORKET_DISABLE_SANDBOX=1` and passed on the targeted contract or integration slice:
   1. `tests/interfaces/test_api.py`
   2. `tests/interfaces/test_api_add_transaction_cli.py`
   3. `tests/interfaces/test_api_approvals.py`
   4. `tests/interfaces/test_api_approval_projection_fail_closed.py`
   5. `tests/interfaces/test_api_composition_isolation.py`
   6. `tests/interfaces/test_api_expansion_gate.py`
   7. `tests/interfaces/test_api_interactions.py`
   8. `tests/interfaces/test_api_kernel_lifecycle.py`
   9. `tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py`
   10. `tests/interfaces/test_api_lifecycle_subscribers.py`
   11. `tests/interfaces/test_api_nervous_system_operator_surfaces.py`
   12. `tests/interfaces/test_api_task_lifecycle.py`
   13. `tests/interfaces/test_extension_runtime_api_routes.py`
   14. `tests/interfaces/test_sandbox_lifecycle_operator_api.py`
   15. `tests/interfaces/test_settings_protocol_determinism_controls.py`
10. Packet 4 completed on 2026-04-08.
11. Packet 4 decomposed the touched orchestrator authority into explicit bounded services:
   1. support-service construction remains on `Orchestrator.support_services` via `orket/application/services/orchestrator_support_services.py`
   2. review preflight now lives in `orket/application/services/orchestrator_review_preflight_service.py`
   3. turn preparation and prompt/context assembly now live in `orket/application/services/orchestrator_turn_preparation_service.py` and `orket/application/services/orchestrator_prompt_preparation_service.py`
   4. turn-context construction now lives in `orket/application/services/orchestrator_turn_context_builder.py` with the gate and policy helpers split into `orket/application/services/orchestrator_turn_context_gate_service.py` and `orket/application/services/orchestrator_turn_context_policy.py`
   5. post-dispatch success handling now lives in `orket/application/services/orchestrator_turn_success_handler.py`
   6. failure-path authority now lives in `orket/application/services/orchestrator_failure_handler.py`
   7. `_PATCHABLE_NAMES` plus `_sync_patchable_symbols()` remain removed from the touched live path, `_build_turn_context()` is now a thin delegator, `_handle_failure()` is now a thin delegator, and `_execute_issue_turn()` is materially smaller and sequencing-focused
12. Packet 4 proof ran with `ORKET_DISABLE_SANDBOX=1` and passed on the targeted contract or integration slice:
   1. `tests/application/test_orchestrator_epic.py`
   2. `tests/integration/test_orchestrator_scheduler_control_plane.py`
13. Packet 5 completed on 2026-04-08.
14. Packet 5 narrowed engine and issue-dispatch authority on the touched live path:
   1. `OrchestrationEngine` now composes its control-plane dependencies through `orket/orchestration/engine_services.py::build_engine_control_plane_services(...)` instead of constructing the full control-plane group inline
   2. async kernel control-plane publication and response augmentation now live in `orket/orchestration/engine_kernel_async_service.py::KernelAsyncControlPlaneService`
   3. replay diagnostics now live in `orket/orchestration/engine_services.py::ReplayDiagnosticsService`, the canonical engine replay surface is `replay_turn_diagnostics(...)`, and `replay_turn(...)` now survives only as a diagnostics-only compatibility wrapper
   4. the touched API and CLI replay paths now call `replay_turn_diagnostics(...)` explicitly
   5. the default orchestrator issue-dispatch lifecycle truth remains owned by `orket/application/services/orchestrator_issue_control_plane_service.py`, so no broader ControlPlane lane reopen was required for this packet
15. Packet 5 proof ran with `ORKET_DISABLE_SANDBOX=1` and passed on the targeted structural or integration slice:
   1. `tests/application/test_engine_refactor.py`
   2. `tests/application/test_orchestration_engine_kernel_async.py`
   3. `tests/application/test_orchestrator_issue_control_plane_service.py`
   4. `tests/integration/test_orchestrator_issue_control_plane.py`
   5. `tests/interfaces/test_api.py` replay slice
   6. `tests/interfaces/test_cli_startup_semantics.py`
   7. `tests/interfaces/test_cli_protocol_replay.py`
16. Packet 6 completed on 2026-04-08.
17. Packet 6 rebuilt runtime-verifier truth and verifier artifact provenance on the touched live paths:
   1. `orket/application/services/runtime_verifier.py` now emits explicit verifier evidence classes and summaries over `syntax_only`, `command_execution`, `behavioral_verification`, and `not_evaluated`
   2. `orket/application/services/runtime_verification_artifact_service.py` now preserves stable verifier history through `runtime_verification.json`, `runtime_verification_index.json`, and per-record artifacts under `runtime_verifier_records/`
   3. the touched runtime-summary and execution-pipeline paths no longer promote the verifier artifact to the primary authored output by default
   4. MAR and audit logic now treat `runtime_verification.json` as support verification evidence rather than authored output authority
18. Packet 6 proof ran with `ORKET_DISABLE_SANDBOX=1` and passed on the targeted contract, integration, and end-to-end slice:
   1. `tests/application/test_runtime_verifier_service.py`
   2. `tests/application/test_runtime_verification_artifact_service.py`
   3. `tests/application/test_orchestrator_epic.py` runtime-verifier slice
   4. `tests/runtime/test_run_summary_packet1.py`
   5. `tests/application/test_execution_pipeline_run_ledger.py` packet-6 slice
   6. `tests/scripts/test_audit_phase2.py`
   7. `tests/live/test_system_acceptance_pipeline.py`
19. Packet 7 completed on 2026-04-08.
20. Packet 7 rebuilt proof honesty on the cited test surfaces:
   1. the cited patched run-start policy tests now self-label as contract proof instead of integration proof
   2. the cited patched review-run projection drift tests now self-label as contract proof instead of integration proof
   3. the cited runtime-subpackage boundary suite now self-identifies as structural-only contract proof
   4. the cited orchestrator runtime-verifier gate tests now self-label as patched contract proof
   5. the live acceptance proof now exercises a real local model path and asserts truthful success-or-failure outcome semantics instead of treating volatile model success as the only admissible green shape
21. Packet 7 proof ran with `ORKET_DISABLE_SANDBOX=1` and passed on the cited proof-honesty slice:
   1. `tests/integration/policy_enforcement/test_runtime_policy_enforcement.py`
   2. `tests/application/test_review_run_service.py`
   3. `tests/application/test_orchestrator_epic.py` runtime-verifier and support-service slice
   4. `tests/runtime/test_runtime_subpackage_boundaries.py`
   5. `tests/live/test_system_acceptance_pipeline.py`
22. The seven-packet BR04082026 implementation plan is complete and archived after same-change roadmap closeout.
