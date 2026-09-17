# ControlPlane Governed Start-Path Matrix
Last updated: 2026-09-14
Status: Active durable governance companion
Owner: Orket Core

## Purpose

Preserve the active workload-authority decision lock and governed start-path matrix after ControlPlane project closeout.

## Active authorities

1. [docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md](docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md)
2. [docs/specs/WORKLOAD_CONTRACT_V1.md](docs/specs/WORKLOAD_CONTRACT_V1.md)
3. [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## Workload Authority Decision Lock

The active workload-authority lock is:

1. exactly one repo seam may mint governed `WorkloadRecord` objects for start paths: `orket/application/services/control_plane_workload_catalog.py`
2. all other workload surfaces may only provide raw input data, call that seam, or read/project an already-built canonical workload record
3. runtime-local adapters, extension models, and workload-specific entrypoints may not import or call low-level control-plane workload builders directly
4. the governed start-path matrix below is a closure gate, not passive inventory: any non-test module that directly consumes workload authority from `control_plane_workload_catalog.py` must appear there with a truthful classification, and rock wrappers must remain routing-only retirement debt rather than regaining standalone workload-authority status
5. touched catalog-resolved publishers may not reintroduce local `workload_id` / `workload_version` authority aliases after receiving canonical `WorkloadRecord` objects from the shared catalog
6. `run_card(...)` is the sole public card runtime execution surface, so `run_issue(...)`, `run_epic(...)`, and `run_rock(...)` may survive only as thin compatibility wrappers that normalize inputs and delegate back to it, while rock execution may remain only as routing-only retirement debt rather than a standalone workload-authority surface. Other admitted families retain the explicit entrypoints below; they do not route through the card executor merely to share its name.

## Governed Start-Path Matrix

This matrix is machine-enforced by `tests/application/test_control_plane_workload_authority_governance.py`.

| Start path | Current authority status | Truthful note |
| --- | --- | --- |
| outward governed execution | `catalog-resolved` | `outward_control_plane_service.py` resolves the shared catalog at admission and binds its record into immutable run snapshots on the outward transaction. Terminal publication uses shared final truth. Scoped migration and installed acceptance pass under `OUTWARD_RUN_AUTHORITY.md`; BT-5 family conformance remains open. |
| cards epic execution | `projection-resolved` | `run_card(...)` is the canonical public runtime surface, and its normalized dispatcher resolves cards-epic `workload.contract.v1` payloads plus `WorkloadRecord` projection through `control_plane_workload_catalog.py`. |
| atomic issue execution | `projection-resolved` | `run_card(...)` is the canonical public runtime surface for issue execution too; its normalized dispatcher resolves issue cards onto the cards-epic path and `ExecutionPipeline._run_issue_entry(...)` routes those starts through `_run_epic_entry(..., target_issue_id=...)`, so the cards workload projection still resolves through `control_plane_workload_catalog.py`. |
| ODR / run arbiter | `projection-resolved` | `scripts/odr/run_arbiter.py` emits raw `workload.contract.v1` payload and resolves its `WorkloadRecord` through `_resolve_odr_arbiter_control_plane_workload_from_contract(...)`. |
| manual review-run | `catalog-resolved` | `ReviewRunControlPlaneService` consumes `REVIEW_RUN_WORKLOAD` from the shared catalog and carries that canonical `WorkloadRecord` directly into run publication. |
| sandbox runtime | `catalog-resolved` | sandbox start paths consume `sandbox_runtime_workload_for_tech_stack(...)` from the shared catalog. |
| kernel action | `catalog-resolved` | `KernelActionControlPlaneService` consumes `KERNEL_ACTION_WORKLOAD` and carries that canonical `WorkloadRecord` directly into run publication. |
| governed turn-tool | `catalog-resolved` | `TurnToolControlPlaneService` consumes `TURN_TOOL_WORKLOAD` and carries that canonical `WorkloadRecord` directly into run publication; `orket/application/workflows/turn_executor_control_plane.py` and `orket/application/workflows/turn_tool_dispatcher_control_plane.py` remain adapter-only routing seams that do not mint workload authority locally. |
| orchestrator issue dispatch | `catalog-resolved` | `OrchestratorIssueControlPlaneService` consumes `ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD` and carries that canonical `WorkloadRecord` directly into run publication. |
| orchestrator scheduler mutation | `catalog-resolved` | `OrchestratorSchedulerControlPlaneService` consumes `ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD` and carries that canonical `WorkloadRecord` through namespace-mutation helpers. |
| orchestrator child workload composition | `catalog-resolved` | `OrchestratorSchedulerControlPlaneService` consumes `ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD` and carries that canonical `WorkloadRecord` through namespace-mutation helpers. |
| Gitea state worker | `catalog-resolved` | `GiteaStateControlPlaneExecutionService` consumes `GITEA_STATE_WORKER_EXECUTION_WORKLOAD` and carries that canonical `WorkloadRecord` directly into run publication. |
| extension workload execution | `projection-resolved` | `ExtensionManager.run_workload(...)` resolves one canonical extension `WorkloadRecord` through the shared seam at workload start and carries that same record through the returned extension result and provenance. |
| governed-agent CLI and API wake | `projection-resolved` | Bounded `orket agent submit`, durable `orket agent wake enqueue`, and authenticated `POST /v1/agent-wakes` feed the dedicated governed-agent path. Manual/API wakes persist without resolving workload authority or starting execution; explicit lifespan activation resolves the manifest through `ExtensionManager.resolve_governed_agent_workload(...)`, projects exactly one canonical extension `WorkloadRecord`, and processes new-run or existing-run wakes through the same bounded governor, broker, verifier, and final-truth path. Authenticated `POST /v1/agent-schedules/{schedule_id}/evaluations` and API-key plus HMAC authenticated `POST /v1/agent-webhooks/{issuer_ref}/deliveries/{delivery_id}` also admit durable wakes through their schedule/webhook services and repositories. These are caller-driven evaluations/deliveries, not an automatically installed scheduler or webhook subscription. |
| rock entrypoints that initiate governed execution | `routing-only` | the legacy CLI `--rock` alias routes through `run_rock(...)`, a thin wrapper over `run_card(...)`; internal rock routing remains routing-only retirement debt and does not mint standalone rock `WorkloadRecord` authority. |

## Family authority chains and conformance scope

The chains below are accepted for their declared BT-5 guarantees. Catalog
resolution establishes workload identity; each family's authorization, completion
and recovery guarantees are limited by its named contracts. The canonical plan's
BT-5 five-requirement disposition binds current regression, migration and actual
service evidence. It does not admit additional objectives or takeover paths.

| Family / public surface | Executor and authorization owner | Effect and terminal authority | Replay / supported objectives / remaining ceiling |
|---|---|---|---|
| Cards: `orket runtime --card`, engine `run_card`, card API | `OrchestrationEngine` / `ExecutionPipeline`; turn admission via `TurnToolControlPlaneService`, approval continuation via `EpicApprovalPauseService` | Turn dispatcher and admitted adapters; `CardCompletionService` gates card writes, `CardsEpicControlPlaneService` and `EpicPublicationService` own retained build result; typed runtime result projects it | Declared builtin acceptance and bounded pre-effect resume; artifact diagnostics are not replay-verdict authority. Composition retains one absolute runtime path and its sibling control-plane store. Historical relative scopes require the offline migration in `RUNTIME_STORE_BINDING.md`; unrelated histories are not merged. |
| Outward runs: authenticated run/approval API | `OutwardRunExecutionService`; `OutwardModelAdmissionService` and exact `OutwardApprovalService` bindings; shared catalog/run admission through `outward_control_plane_service.py` | `OutwardEffectService` owns claim/intent/observation/publication through adapters; `outward_terminal_service.py` validates retained evidence and publishes shared final truth in the existing transaction | Protocol status/summary project shared truth. `OUTWARD_RUN_AUTHORITY.md` owns explicit historical current-input adoption. Source and installed copied-history migration/continuation and actual llama.cpp terminal proof pass; current common-family conformance is bound by the BT-5 disposition below. Accepted BT-1/BT-2 and single-turn formal claim ceilings remain. |
| Governed agents: `orket agent submit`, wake CLI/API, schedule evaluation and webhook delivery | `GovernedAgentSupervisor` / `GovernedAgentLoopService`; wake fences, `GovernedAgentBrokerService`, continuation policy and operator/effect-control services | `GovernedAgentEffectService` and admitted host capabilities; `governed_agent_terminal_service.py` and effect-terminal service publish canonical final truth | Admitted governed-agent workload contract, retained iteration replay and explicit wake recovery. Schedules/webhooks queue through the same authority; they do not grant effect approval or new objectives. Trusted extension and provider limits remain. |
| SDK workloads: runtime extension `run` / `ExtensionManager.run_workload` | `WorkloadExecutor.run_sdk_workload`; manifest admission and host-issued capability envelope | SDK child and host capability bridge; `ExtensionWorkloadControlPlaneService` owns control-plane closeout | Manifest-declared capabilities and result/provenance contract. Generic result success is not the card or governed-agent independent objective verifier. Hostile containment and shared recovery are unproven. |
| Legacy workloads: runtime extension `run` / `ExtensionManager.run_workload` | `WorkloadExecutor.run_legacy_workload`; existing trusted manifest/compiled-action policy | Legacy workload loader/action execution; `ExtensionWorkloadControlPlaneService` closeout and `ExtensionRunResult` projection | Existing trusted compatibility behavior; no SDK-equivalent capability, hostile-containment, replay or restart guarantee is inferred. |
| Governed-action quickstart: `orket-quickstart` | `run_governed_action_demo`; one interactive/explicit operator choice over a fixed local proposal | Demo file writer, `QuickstartLedgerWriter`, `DemoResult` | Fixed offline teaching example with ledger verification. No concurrent approval CAS, durable effect claim, general workload admission or replay/resume guarantee. |
| Manual review: review CLI / `application/review/run_service.py` | Snapshot/policy resolution and deterministic review lane; model-assisted lane advisory | Review bundle writer and `ReviewRunControlPlaneService`; deterministic decision is authoritative | Read-only snapshot review and offline artifact replay. It is not an autonomous change executor or webhook-triggered review service. |
| ODR: `python scripts/odr/run_odr_quant_sweep.py` | `RunArbiter` compiles/validates an explicit workload contract and provider-bound script stages | Sweep owns child execution and arbiter artifact checks; retained plan/error/result output defines the invocation outcome | `ODR_PROVIDER_ADMISSION.md` owns the admitted native selection and validation contract. Distinct ODR executor; no card acceptance, independent requirement-quality verdict, outward effect fencing, restart or general native descendant supervision. |

Project roots and runtime-store migration are governed by `RUNTIME_PROJECT_ROOTS.md`
and `RUNTIME_STORE_BINDING.md`. Shared immutable admission, mutable revisions,
terminal/resource transactions, retained consistency and marked dispatch uncertainty
are governed by `CONTROL_PLANE_TERMINAL_AUTHORITY.md`. Family writers use these
contracts; a native local fence is not a remote-effect termination guarantee.

Current BT-5 acceptance: `.tmp/bt5-family-composed-clock/gate/audit.json`, core
wheel SHA-256 `5d0f6a4058ecadfd7be26c50b70680c5d174b8107bcf51f231ac321f71c3b9d9`.
The complete 278-file selection passes 2,321 identical cases in source and each of
four installed Windows/Linux Python 3.11/3.12 environments, including the common
outward/cards/governed-agent adversarial predicates and the distinct family limits.
Fresh installed history proof covers unmarked-turn refusal, retained SDK/legacy/
review closeout, pre-revision read/no-op and outward old-binary upgrade. Original
failed stores remain unchanged. Actual llama.cpp card/ODR and Gitea proof on the
same artifact is explicitly reused; this is not new provider execution.

Positive native and turn/issue fixtures use explicit time alongside independent
expiry/reversal controls. Production clock ownership remains D work. Detailed
requirements, exact proof hashes, original failures and evidence limits are in the
canonical architectural-truth plan. Full-suite, hosted CI, quality, capability,
release and whole-lane acceptance remain separate gates.

Schedule/webhook admission is implemented by the authenticated governed-agent
routes, application composition and durable schedule/webhook repositories. It
queues work through existing authority and does not grant effect approval. Core
declares `tzdata`; invalid/nonexistent local times refuse admission and ambiguous
times require an explicit fold. Historical provider proof retains its named
provider and cannot substitute for another provider's proof.

## Surviving Projection-Only Or Temporary Surfaces

The following projection or compatibility surfaces remain allowed:

1. extension-manifest workload metadata surfaces under `orket/extensions/`
2. `orket/runtime/run_start_artifacts.py`
3. `orket/runtime/run_summary.py`
4. `orket/application/review/lanes/`
5. `orket/runtime/retry_classification_policy.py`, `orket/runtime/run_start_contract_artifacts.py`, `scripts/governance/check_retry_classification_policy.py`, and `scripts/governance/run_runtime_truth_acceptance_gate.py`

These surfaces may emit evidence or metadata, but they do not become co-equal workload authority.

## Historical Record

The ControlPlane project closeout archive lives at [docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CLOSEOUT.md).
