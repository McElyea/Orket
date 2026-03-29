# Control-Plane Convergence Implementation Plan
Last updated: 2026-03-29
Status: Active implementation authority
Owner: Orket Core
Lane type: Control-plane convergence / implementation plan

## Authority posture

This document is the active implementation authority for the ControlPlane convergence lane opened in `docs/ROADMAP.md`.

The active ControlPlane requirements authority remains the accepted packet under `docs/projects/ControlPlane/orket_control_plane_packet/`.
The last accepted ControlPlane implementation sequencing lane remains archived under `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/`.

The paired requirements companion is `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_HARDENING_REQUIREMENTS.md`.
The packet README, project index, and archived lane material must continue to tell the same authority story as this plan.

## Source authorities

This plan is bounded by:
1. `docs/projects/ControlPlane/orket_control_plane_packet/README.md`
2. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
3. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_HARDENING_REQUIREMENTS.md`
4. `docs/ROADMAP.md`
5. `docs/ARCHITECTURE.md`
6. `CURRENT_AUTHORITY.md`
7. `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md`
8. `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/CLOSEOUT.md`

## Purpose

Converge the runtime from packet-v2 partial adoption into default-path control-plane authority.

This lane exists because the accepted foundation packet is real, but current-state and closeout material still show hybrid behavior:
1. workload identity remains conflicting
2. attempt history is not yet universally first-class
3. reservation and lease truth are not yet universal across admission and scheduling
4. effect truth is still often reconstructed outside the normative effect journal
5. checkpoint publication and supervisor-owned checkpoint acceptance are not execution-default
6. operator-action authority remains fragmented outside selected paths
7. namespace and safe-tooling gates are not yet universal across broader workloads and resource targeting
8. closure truth risks remaining split between new control-plane records and older summary surfaces

## Non-goals

This lane does not:
1. invent a new control-plane vocabulary
2. redesign the OS target
3. broaden into memory, DAG, UX, or distributed-cluster semantics
4. reopen packet-v2 frozen decisions

## Decision lock

The following remain frozen:
1. `Reservation` is first-class
2. `FinalTruthRecord` is first-class
3. `recovering` is control-plane activity
4. resumed or replacement workload execution returns to `executing`
5. operator risk acceptance is never world-state evidence
6. operator attestation is bounded and visibly distinct from observation
7. the effect journal is a normative authority surface
8. slim namespace semantics exist now and are not deferred
9. terminal commands may stop continuation but may not rewrite truth
10. `orket/application/services/control_plane_workload_catalog.py` is the only governed start-path seam that may mint `WorkloadRecord` objects
11. other workload surfaces may only provide raw input data, call that seam, or read/project already-built canonical workload records
12. runtime-local adapters, extension models, and workload-specific entrypoints must not import low-level workload builders directly
13. a negative governance test must fail if non-allowed modules import or call `build_control_plane_workload_record(...)` or `build_control_plane_workload_record_from_workload_contract(...)`
14. the governed start-path matrix in `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md` is a closure gate, not passive inventory; any non-test module that directly consumes workload authority from `control_plane_workload_catalog.py` must be represented there with a truthful classification, and delegated rock entrypoints must fail governance if they stop delegating before `CE-01` closes
15. touched catalog-resolved publishers must carry canonical `WorkloadRecord` objects through run publication and mutation helpers instead of restating workload authority as local `workload_id` / `workload_version` string-pair aliases

## Activation status

This lane is now opened through `docs/ROADMAP.md`.

The opening change must keep all of the following true together:
1. the roadmap points to this plan as the active implementation lane
2. the ControlPlane README and project-index wording match the roadmap and archive
3. the archived `CP03262026-LANE-CLOSEOUT` material stays historical only
4. this plan's workstream-level code bindings, proof commands, crosswalk gates, and compatibility exits remain the active sequencing surface

## Current truthful starting point

The strongest already-converged surfaces are:
1. first-class `RunRecord` and `AttemptRecord` publication is already live on the main sandbox path, governed turn-tool path, governed kernel path, default orchestrator issue-dispatch plus scheduler-owned mutation paths, Gitea worker path, manual review-run path, and cards-epic path
2. reservation, lease, and shared resource truth already cover the main sandbox, coordinator, governed turn-tool, governed kernel, default orchestrator issue-dispatch, default orchestrator scheduler-owned mutation, and Gitea worker ownership paths
3. effect-journal publication already covers sandbox deploy and cleanup, governed kernel commit behavior, default orchestrator issue-dispatch, scheduler-owned mutation and child-workload composition, governed turn-tool execution, and Gitea worker state transitions
4. checkpoint and recovery-decision truth already exist on the sandbox reclaimable path, the governed turn pre-effect same-attempt path, and the Gitea worker pre-effect claimed-card path
5. first-class operator-action, reconciliation, and final-truth publication already exist on selected sandbox, approval, governed turn-tool, governed kernel, and Gitea worker closure paths
6. cards, ODR, and extension workload execution now route through `orket/application/services/control_plane_workload_catalog.py`, with `orket/runtime/workload_adapters.py` reduced to a compatibility shim, extension models reduced to raw manifest data only, extension workload start now resolving one canonical `WorkloadRecord` before execution and then reusing that record in provenance instead of minting it later, the named CLI rock runtime now entering `run_rock(...)` explicitly instead of passing through `run_card(...)` heuristics, touched catalog-resolved publishers now carrying canonical `WorkloadRecord` objects through their run-publication and namespace-mutation helpers instead of restating authority as local string-pair aliases, and the workload-authority governance tests now forbidding direct low-level workload-builder use outside the canonical seam, unclassified direct workload-authority consumers outside the governed start-path matrix, and alias drift on those touched catalog-resolved publishers

The highest-risk open gaps remain:
1. `Workload` still reads `conflicting` in the crosswalk because broader runtime start paths still do not share one universal governed workload authority surface
2. older summary, receipt, bootstrap, snapshot, and retry-local surfaces can still look authoritative unless each surviving projection is explicitly framed and fail-closed
3. checkpoint publication, checkpoint acceptance, and recovery-decision publication are still not execution-default outside the currently covered paths
4. operator-action and reconciliation authority are still fragmented across endpoint-local, log-local, and subsystem-local behavior on broader paths
5. namespace and safe-tooling boundaries are still not universal across broader workloads, scheduling, resource targeting, and child composition
6. terminal closure still risks split-brain behavior while `run_summary.py`, legacy truth contracts, and other projections remain alive beside first-class `FinalTruthRecord` publication

## Execution strategy

This lane should proceed in convergence order, not in fresh-design order.

The rule is:
1. promote missing nouns,
2. universalize publication,
3. eliminate ambient or reconstructed authority,
4. collapse compatibility surfaces into projections,
5. close documentation drift last.

## Slice binding rule

No executable slice under this plan is specific enough unless it names:
1. the exact crosswalk row or rows it changes
2. the exact code surfaces, repositories, services, and runtime entrypoints it will touch
3. the legacy authority surface it is demoting
4. the exact proof commands that must pass
5. the compatibility exit ledger entries it narrows or closes
6. the crosswalk and doc updates that land in the same change

## Compatibility exit ledger

Removal condition means remove the surface as an authority surface.
Projection-only reads may remain only when the packet, crosswalk, and proofs say so explicitly.

| Exit id | Surface kept temporarily | Current authority risk | Owning workstream | Removal or projection-only condition |
| --- | --- | --- | --- | --- |
| `CE-01` | `orket/runtime/workload_adapters.py` and extension-manifest workload adapters | Parallel workload nouns can remain de facto start authority. | Workstream 1 | A canonical workload contract is the only governed start-path surface for runtime workloads, rocks, and extension entrypoints, and the `Workload` crosswalk row no longer reads `conflicting`. |
| `CE-02` | `orket/application/review/run_service.py`, `orket/runtime/run_start_artifacts.py`, and lane-local retry surfaces under `orket/application/review/lanes/` | Review and retry-local state can continue to look like run and attempt truth. | Workstream 1 | Governed start, retry, and replay paths publish `RunRecord` and attempt truth directly, and touched read models consume those records instead of review-local authority. |
| `CE-03` | Sandbox-special-case resource and ownership surfaces under `orket/application/services/sandbox_runtime_*` | Sandbox can remain its own ownership authority family instead of one resource model instance. | Workstream 2 | Reservation, lease, and resource truth share one general model across sandbox, coordinator, turn-tool, orchestrator, and Gitea worker paths. |
| `CE-04` | `workspace/observability/<run_id>/`, `orket/runtime/protocol_receipt_materializer.py`, and legacy receipt-heavy readbacks | Effect truth can still be reconstructed from artifacts after the fact. | Workstream 3 | Governed mutation and closure-relevant writes publish through the effect journal first, and artifact surfaces become projection-only. |
| `CE-05` | `orket/application/review/snapshot_loader.py`, `orket/application/review/models.py`, and saved-state existence checks | Snapshot presence can keep acting like resume authority. | Workstream 4 | Checkpoint acceptance plus recovery decision are required for resume, and saved state or snapshot presence is no longer sufficient. |
| `CE-06` | Endpoint-, log-, and policy-local operator and reconciliation behavior across API and orchestration surfaces | Operator influence and reconciliation can remain implicit or scattered. | Workstream 5 | Commands, risk acceptance, attestation, and reconciliation publish through first-class record families and touched endpoints stop acting as hidden authority. |
| `CE-07` | `orket/runtime/run_summary.py`, `orket/runtime/runtime_truth_contracts.py`, and `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` | Legacy closure surfaces can keep acting like alternate final-truth authorities. | Workstream 6 | Governed terminal paths emit `FinalTruthRecord`, and older summary surfaces are explicitly projection-only or retired. |
| `CE-08` | Ambient namespace assumptions, compatibility tool mappings, and preflight-only gate checks on tool mutation paths | Tooling and broader runtime paths can keep mutating outside one declared namespace and safe-tooling boundary. | Workstream 7 | Governed mutation paths fail closed on undeclared capability, namespace drift, reservation or lease bypass, and missing journal linkage. |

## Convergence status snapshot

Status terms in this snapshot:
1. `partial artifact recorded` means this lane already has a stable partial closeout artifact for the workstream
2. `no convergence closeout artifact yet` means this lane has not yet recorded a slice-bounded closeout artifact for the workstream, and does not imply zero pre-existing packet-v2 coverage on the touched surfaces

| Workstream | Snapshot status | Canonical closeout artifact path | Truthful current note |
| --- | --- | --- | --- |
| 1 | `partial artifact recorded` | `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md` | Canonical workload, run, attempt, and step slices are already recorded, including cards, ODR, and extension workload execution now routing through the shared workload resolver, touched catalog-resolved publishers now carrying canonical `WorkloadRecord` objects instead of local workload string-pair aliases, and governance tests guarding direct low-level builder use, start-path matrix drift, delegated rock-entrypoint drift, and string-alias drift on those touched publishers, but `CE-01` and `CE-02` remain open and the `Workload`, `Run`, `Attempt`, and `Step` rows still need more convergence proof before this workstream can close. |
| 2 | `partial artifact recorded` | `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_2_CLOSEOUT.md` | Reservation, lease, and shared resource slices are already recorded, but `CE-03` remains open and broader read-side adoption plus any still-uncovered ownership paths remain outside the closeout claim. |
| 3 | `partial artifact recorded` | `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_3_CLOSEOUT.md` | Projection-only demotion of legacy receipt and summary-backed effect surfaces is already recorded, but `CE-04` remains open and broader default-path effect-journal publication still needs additional convergence slices. |
| 4 | `partial artifact recorded` | `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_4_CLOSEOUT.md` | Checkpoint and recovery slices are now recorded for the sandbox reclaimable path, the governed turn pre-effect recovery path, and the Gitea worker claimed-card path, but `CE-05` remains open and broader supervisor-owned checkpoint and recovery authority is still not universal. |
| 5 | `partial artifact recorded` | `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_5_CLOSEOUT.md` | Reconciliation and operator-action slices are now recorded for selected sandbox, approval, governed turn, governed kernel, and Gitea paths, but `CE-06` remains open and broader divergence handling plus non-sandbox operator authority still need one universal publication family. |
| 6 | `partial artifact recorded` | `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_6_CLOSEOUT.md` | Partial `FinalTruthRecord` adoption is now recorded on sandbox, governed turn-tool, governed kernel, and Gitea worker terminal paths, but `CE-07` remains open and broader terminal closure still needs fail-closed final-truth universalization. |
| 7 | `partial artifact recorded` | `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_7_CLOSEOUT.md` | Namespace and safe-tooling hardening is now recorded on governed turn-tool and scheduler-owned mutation paths, but `CE-08` remains open and the `Workload` row still reads `conflicting` while broader runtime start and mutation paths remain outside one universal namespace boundary. |
| 8 | `partial artifact recorded` | `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_8_CLOSEOUT.md` | Roadmap, packet README, archive, and this plan now have a recorded partial documentation-convergence artifact, and Workstreams 1 through 8 each have a stable closeout artifact file, but lane-wide documentation convergence stays open until every future crosswalk delta, compatibility-exit update, and final lane-status change remains synchronized. |

## Workstream closeout artifact contract

No workstream may be marked complete without one stable closeout artifact for that workstream.

The closeout artifact must record:
1. workstream id, objective, and the exact slice or slices being closed
2. touched crosswalk rows, including previous status, new status, and migration-note delta
3. exact code surfaces, entrypoints, tests, and docs changed
4. proof commands executed, proof type (`structural`, `live`, or `blocked`), and observed result
5. compatibility exits consumed, narrowed, or closed
6. surviving projection-only surfaces and why they are still allowed to remain non-authoritative
7. explicit remaining gaps, blockers, or deferred follow-on work
8. authority-story updates that landed in the same change

Each workstream section below names its canonical closeout artifact path.
Declaring that path does not itself create proof or completion; the artifact must still exist and satisfy this contract before the workstream may close.

If a workstream closes only partially, the artifact must say exactly what remains open and why the remaining surfaces are still outside the closeout claim.

## Open convergence slice queue

The slices below are the next truthful execution queue for this lane.
They are ordered by the authoritative execution order later in this document.
Because Workstream 7 must execute before Workstream 6, `Slice 7A` intentionally appears before `Slice 6A`.
If a slice expands or splits materially, update this queue in the same change rather than letting code become the hidden plan.

### Slice 1A - Legacy run and attempt read-surface demotion

1. Workstream: 1
2. Crosswalk rows: `Workload`, `Run`, `Attempt`, `Step`
3. Exact code surfaces and entrypoints: `orket/runtime/run_summary.py`; `orket/runtime/run_start_artifacts.py`; `orket/runtime/run_start_contract_artifacts.py`; `orket/application/review/control_plane_projection.py`; `orket/application/review/models.py`; `orket/application/review/run_service.py`; `orket/application/review/bundle_validation.py`; `orket/interfaces/orket_bundle_cli.py`; `scripts/reviewrun/score_answer_key.py`; `scripts/reviewrun/score_answer_key_contract.py`; `scripts/reviewrun/run_1000_consistency.py`; `scripts/reviewrun/check_1000_consistency.py`; `scripts/workloads/code_review_probe.py`; `scripts/workloads/code_review_probe_support.py`; `scripts/workloads/code_review_probe_reporting.py`; `orket/application/review/lanes/`; `orket/runtime/retry_classification_policy.py`; `orket/runtime/execution_pipeline.py`; `scripts/governance/check_retry_classification_policy.py`; `scripts/governance/run_runtime_truth_acceptance_gate.py`
4. Legacy authority to demote: session-bootstrap `run_identity` reuse, review-lane-local execution-state surfaces, fresh or persisted review-bundle JSON that can still look authoritative when manifest or control-plane ids drift, when fresh or persisted review manifests or lane payloads omit required `run_id`, when fresh review manifests or lane payloads carry `control_plane_run_id` that drifts from their `run_id`, when manifest or lane attempt or step refs drift outside the declared `control_plane_run_id` lineage, when lane payloads omit required control-plane refs claimed by the manifest, when lower-level manifest or lane control-plane refs survive after parent run or attempt refs drop before serialization or during persisted bundle validation, when returned review results or CLI payloads drop manifest control-plane refs while still exposing those refs through the `control_plane` summary, when review-side `control_plane` summaries keep lower-level projected attempt or step ids after parent run or attempt ids drop, when review-side `control_plane` summaries let projected attempt state or ordinal survive after projected `attempt_id` drops or let projected `step_kind` survive after projected `step_id` drops, when review-side `control_plane` summaries let projected attempt or step refs drift outside the projected run lineage, when review-side `control_plane` summaries keep projected run, attempt, or step ids while dropping projected run metadata, attempt state or ordinal, or step kind, when legacy cards `run_summary` control-plane projections let lower-level ids survive without parent run or attempt ids, drop core run metadata while still carrying `run_id`, keep projected attempt ids while dropping attempt state or ordinal, let projected attempt state or ordinal survive after projected `attempt_id` drops, let `current_attempt_id` survive after projected `attempt_id` drops, let `current_attempt_id` drift from projected `attempt_id`, let projected attempt ids drift outside the projected run lineage, keep projected step ids while dropping `step_kind`, let projected `step_kind` survive after projected `step_id` drops, let projected step ids drift outside the projected run lineage, when retry-classification snapshots omit explicit projection-only framing or drift away from `retry_classification_rules`, when run-start contract capture writes generated retry-classification snapshots without validating that projection framing before persistence, when the retry-policy checker writes malformed report payloads without validating or normalizing the report contract before diff-ledger persistence, when retry-policy report validation accepts an invalid embedded snapshot or producer normalization persists that invalid embedded snapshot instead of falling back to the canonical retry-policy snapshot, when governance acceptance checks trust malformed retry-policy report payloads through shallow `ok` or `signal_count` fields or collapse valid fail-closed retry-policy reports into generic error-free false state, when run-level acceptance checks trust persisted `retry_classification_policy.json` through file presence or loose JSON shape alone instead of validating the artifact and matching it against the current canonical snapshot, when workload-side bundle emitters omit or producer-serialize empty aligned lane-payload `run_id`, when review answer-key scoring emits loose score-report JSON without explicit contract framing plus top-level `run_id`, fixture/snapshot/policy provenance fields, nested deterministic/model-assisted score blocks whose aggregate totals stay aligned with their per-issue rows, explicit model reasoning/fix weights needed to prove reasoning and fix subtotals against those same rows, required per-issue row shape, and disabled model blocks that do not carry derived model activity, when workload-side score consumers trust that score report at the nested block, aggregate, or issue-row level through ad hoc dict shape alone, retry-local attempt history, and summary-backed run or closure state that still reads like authority, when review consistency reporting serializes empty default, strict, replay, or baseline `run_id` fields into its own report surface, when review consistency reporting writes malformed contract framing before persistence or misclassifies truthful failed outcomes as malformed contract drift, or when persisted review consistency-report validation trusts shallow `ok` or counter fields without validating report contract framing plus default, strict, replay, and baseline run identity, nested signature digests, deterministic finding-row code/severity/message/path/span/details shape, deterministic-lane version, executed-check lists, signature truncation framing, or scenario-local `truncation_check` digests, byte counts, and boolean flags
5. Required proof commands: `python -m pytest -q tests/application/test_control_plane_authority_service.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_async_control_plane_execution_repository.py`; `python -m pytest -q tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`; `python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py`; `python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py tests/application/test_code_review_probe.py`; `python -m pytest -q tests/scripts/test_check_1000_consistency.py tests/application/test_reviewrun_consistency.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py`
6. Compatibility exits narrowed or closed: `CE-01`, `CE-02`
7. Same-change doc updates: `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md`; `CURRENT_AUTHORITY.md`; `docs/specs/REVIEW_RUN_V0.md`; `docs/guides/REVIEW_RUN_CLI.md`; and any contract-delta note required by review bundle, review consistency-report, answer-key score-report, or bootstrap projection hardening
8. Slice exit condition: broader run or attempt read surfaces are projection-only or adapter-only with explicit migration notes, touched review manifest or lane-artifact serializers plus review result, CLI, replay, scoring, consistency, and persisted consistency-report validation consumers reject embedded manifest omission, missing manifest or lane-payload `run_id`, fresh same-run `control_plane_run_id` drift, review attempt-lineage drift, review step-lineage drift, lifecycle-projection incompleteness, review-bundle control-plane id-hierarchy incompleteness, review-summary control-plane id-hierarchy incompleteness, review-summary orphaned attempt or step metadata, persisted manifest or control-plane identifier drift, empty consistency-report run ids, persisted consistency-report contract-version drift, nested signature or finding-row shape drift, or scenario-local truncation-check drift before trusting or serializing review-local JSON, review consistency-report producers validate that contract framing before persistence while still allowing truthful failed outcomes to persist as failed reports, review answer-key scoring emits explicitly versioned score-report payloads with non-empty top-level `run_id`, fixture/snapshot/policy provenance fields, nested score-block aggregates aligned with their issue rows, explicit model reasoning/fix weights, reasoning/fix subtotals aligned with those same issue rows, and disabled model blocks free of derived model activity, workload-side score consumers validate that contract before trusting score JSON, review-run lane payloads preserve required `control_plane_*` refs whenever the manifest declares them, workload-side review-bundle emitters that reuse shared scoring preserve aligned lane-payload `run_id` and fail closed before artifact write when that bundle-local `run_id` is empty, legacy cards `run_summary` control-plane projections fail closed on transient run-projection incompleteness, id-hierarchy incompleteness, current-attempt hierarchy incompleteness, orphaned attempt or step metadata, attempt-metadata incompleteness, attempt-alignment, attempt-lineage, step-metadata incompleteness, or step-lineage drift, and no immutable session-scoped artifact is forced to carry invocation-scoped control-plane identity

### Slice 2A - Shared resource-registry projection and residual ownership convergence

1. Workstream: 2
2. Crosswalk rows: `Reservation`, `Lease`, `Resource`
3. Exact code surfaces and entrypoints: `orket/application/services/control_plane_target_resource_refs.py`; `orket/application/services/sandbox_lifecycle_view_service.py`; `orket/application/services/kernel_action_control_plane_view_service.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/interfaces/coordinator_api.py`; `orket/runtime/execution_pipeline.py`
4. Legacy authority to demote: lease-centric or subsystem-local ownership summaries that still bypass one shared resource-registry projection
5. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_reservation_contract.py tests/contracts/test_control_plane_lease_contract.py`; `python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py tests/integration/test_orchestrator_scheduler_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py`
6. Compatibility exits narrowed or closed: `CE-03`
7. Same-change doc updates: `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_2_CLOSEOUT.md`; `CURRENT_AUTHORITY.md` if any supported operator or approval read models gain new canonical resource projections
8. Slice exit condition: targeted non-sandbox read surfaces consume one shared resource-registry story and no touched ownership path still relies on lease-only or subsystem-local truth where shared resource truth exists

### Slice 3A - Projection-only demotion of remaining legacy effect readbacks

1. Workstream: 3
2. Crosswalk rows: `Effect`, `Run`, `FinalTruthRecord`
3. Exact code surfaces and entrypoints: `orket/runtime/run_summary.py`; `orket/runtime/protocol_receipt_materializer.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/application/services/kernel_action_control_plane_view_service.py`; `orket/application/services/sandbox_lifecycle_view_service.py`; `scripts/common/run_summary_support.py`
4. Legacy authority to demote: artifact-backed, receipt-backed, or summary-backed effect readbacks that still present themselves as primary effect truth
5. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_effect_journal_contract.py tests/application/test_control_plane_publication_service.py`; `python -m pytest -q tests/runtime/test_protocol_receipt_materializer.py tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py`
6. Compatibility exits narrowed or closed: `CE-04`
7. Same-change doc updates: `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_3_CLOSEOUT.md`; `CURRENT_AUTHORITY.md`; any touched legacy truth-contract doc that still frames summary output as authority
8. Slice exit condition: every touched legacy effect read surface self-identifies as projection-only with explicit source framing, and touched read models consume durable effect-journal linkage before receipt or summary evidence

### Slice 4A - Checkpoint policy map and explicit resume enforcement

1. Workstream: 4
2. Crosswalk rows: `Checkpoint`, `RecoveryDecision`, `Attempt`
3. Exact code surfaces and entrypoints: `orket/application/services/sandbox_control_plane_checkpoint_service.py`; `orket/application/services/gitea_state_control_plane_checkpoint_service.py`; `orket/application/workflows/turn_executor_control_plane.py`; `orket/application/workflows/turn_executor_resume_replay.py`; `orket/application/services/sandbox_runtime_recovery_service.py`; `orket/application/services/turn_tool_control_plane_recovery.py`; `orket/application/review/snapshot_loader.py`; `orket/runtime/execution_pipeline.py`
4. Legacy authority to demote: snapshot existence, saved-state presence, and service-local recovery heuristics that can still imply resumability without accepted checkpoint authority
5. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_recovery_contract.py tests/application/test_sandbox_control_plane_checkpoint_service.py`; `python -m pytest -q tests/application/test_kernel_action_control_plane_pre_effect_recovery.py tests/integration/test_sandbox_runtime_recovery_service.py tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py`
6. Compatibility exits narrowed or closed: `CE-05`
7. Same-change doc updates: `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_4_CLOSEOUT.md`; `CURRENT_AUTHORITY.md` if resume or recovery entrypoint contracts change
8. Slice exit condition: touched resume or recovery paths fail closed unless accepted checkpoint plus explicit recovery decision truth exists, and snapshot presence alone no longer authorizes continuation

### Slice 5A - Endpoint-local operator and reconciliation authority collapse

1. Workstream: 5
2. Crosswalk rows: `ReconciliationRecord`, `OperatorAction`, `FinalTruthRecord`
3. Exact code surfaces and entrypoints: `orket/application/services/pending_gate_control_plane_operator_service.py`; `orket/application/services/sandbox_control_plane_operator_service.py`; `orket/application/services/tool_approval_control_plane_operator_service.py`; `orket/application/services/kernel_action_control_plane_operator_service.py`; `orket/application/services/sandbox_lifecycle_reconciliation_service.py`; `orket/interfaces/api.py`; `orket/interfaces/routers/approvals.py`; `orket/interfaces/routers/kernel.py`; `orket/orchestration/approval_control_plane_read_model.py`
4. Legacy authority to demote: endpoint-local, log-local, or policy-local operator and divergence behavior that still acts as hidden control-plane authority
5. Required proof commands: `python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py tests/application/test_tool_approval_control_plane_operator_service.py`; `python -m pytest -q tests/application/test_pending_gate_control_plane_operator_service.py tests/application/test_kernel_action_control_plane_operator_service.py tests/integration/test_sandbox_lifecycle_reconciliation_service.py tests/integration/test_gitea_state_worker_control_plane.py`
6. Compatibility exits narrowed or closed: `CE-06`
7. Same-change doc updates: `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_5_CLOSEOUT.md`; `CURRENT_AUTHORITY.md` if authenticated operator or approval surfaces change their canonical control-plane payloads
8. Slice exit condition: touched operator and reconciliation paths publish through one first-class record family, and read models preserve command versus risk-acceptance versus attestation split explicitly

### Slice 7A - Namespace authority and safe-tooling expansion beyond current governed paths

1. Workstream: 7
2. Crosswalk rows: `Workload`, `Resource`, `Reservation`, `Lease`, `Effect`
3. Exact code surfaces and entrypoints: `orket/application/workflows/turn_tool_dispatcher.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/turn_tool_control_plane_resource_lifecycle.py`; `orket/runtime/workload_adapters.py`; `orket/application/services/orchestrator_issue_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`; `orket/application/workflows/turn_executor_control_plane.py`; `orket/runtime/execution_pipeline.py`
4. Legacy authority to demote: ambient namespace visibility, compatibility-only tool mappings, and mutation paths that can still run without one explicit namespace and safe-tooling contract
5. Required proof commands: `python -m pytest -q tests/application/test_turn_tool_dispatcher_policy_enforcement.py tests/application/test_turn_tool_dispatcher_compatibility.py`; `python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_orchestrator_scheduler_control_plane.py`; `python -m pytest -q tests/platform/test_no_old_namespaces.py`
6. Compatibility exits narrowed or closed: `CE-08`
7. Same-change doc updates: `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_7_CLOSEOUT.md`; `CURRENT_AUTHORITY.md`; `docs/specs/WORKLOAD_CONTRACT_V1.md` if workload or namespace contract framing changes materially
8. Slice exit condition: touched mutation paths fail closed on undeclared namespace or capability scope, and broader workload composition preserves explicit namespace inheritance or override rules instead of ambient access

### Slice 6A - Final-truth closure unification after namespace hardening

1. Workstream: 6
2. Crosswalk rows: `FinalTruthRecord`, `Run`, `Effect`, `OperatorAction`, `ReconciliationRecord`
3. Exact code surfaces and entrypoints: `orket/core/domain/control_plane_final_truth.py`; `orket/application/services/sandbox_control_plane_closure_service.py`; `orket/application/services/sandbox_terminal_outcome_service.py`; `orket/application/services/kernel_action_control_plane_service.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/gitea_state_control_plane_execution_service.py`; `orket/runtime/run_summary.py`; `orket/runtime/runtime_truth_contracts.py`; `orket/runtime/execution_pipeline.py`
4. Legacy authority to demote: run-summary and packet-1 style closure surfaces that can still read like alternate final-truth authorities
5. Required proof commands: `python -m pytest -q tests/contracts/test_control_plane_final_truth_contract.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_packet1.py`; `python -m pytest -q tests/integration/test_sandbox_terminal_outcome_service.py tests/integration/test_turn_tool_control_plane_closeout.py tests/integration/test_gitea_state_worker_control_plane.py tests/integration/test_sandbox_orchestrator_lifecycle.py`
6. Compatibility exits narrowed or closed: `CE-07`
7. Same-change doc updates: `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_6_CLOSEOUT.md`; `CURRENT_AUTHORITY.md`; `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` if any surviving projection contract remains
8. Slice exit condition: every touched terminal path emits `FinalTruthRecord` before successful closeout, and touched legacy summary surfaces are projection-only or retired instead of authoring terminal truth

### Slice 8A - Documentation and authority-story convergence closeout

1. Workstream: 8
2. Crosswalk rows: any row changed by the converged code slices in the same batch
3. Exact doc surfaces: `docs/ROADMAP.md`; `docs/projects/ControlPlane/orket_control_plane_packet/README.md`; `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/CLOSEOUT.md`; this plan; the active workstream closeout artifact touched by the same slice
4. Legacy authority to demote: stale or contradictory lane wording, unstated compatibility exits, or closeout claims that drift away from code and proof
5. Required proof commands: `python scripts/governance/check_docs_project_hygiene.py`; `python -m pytest -q tests/platform/test_no_old_namespaces.py`
6. Compatibility exits narrowed or closed: whichever exit ids the paired code slice truthfully narrows or closes; never claim a close without updating the ledger and the relevant closeout artifact in the same change
7. Same-change doc updates: roadmap, packet README, crosswalk, this plan, and the relevant workstream closeout artifact whenever lane status, crosswalk status, or compatibility-exit posture changes
8. Slice exit condition: touched docs, code, proofs, compatibility exits, and closeout claims tell one authority story with no stale alternate implementation lane

## Workstream 1 - Canonical workload, run, and attempt promotion

Closeout artifact:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md`

Objective:
1. eliminate identity drift across workload, run, and retry history

Crosswalk rows:
1. `Workload`
2. `Run`
3. `Attempt`
4. `Step`

Required deliverables:
1. one canonical governed workload object or contract family used by runtime workloads, rocks, and extension entrypoints
2. one authoritative run object replacing split run identity across review and observability surfaces
3. one durable append-only attempt object family
4. step attribution hooks sufficient to support effect and closure linkage
5. compatibility adapters where old surfaces remain temporarily

Authority map:
1. canonical workload surfaces to converge: `orket/runtime/workload_adapters.py`; extension manifests under `extensions/`; `docs/specs/WORKLOAD_CONTRACT_V1.md`
2. run and attempt publication and storage: `orket/core/contracts/control_plane_models.py`; `orket/adapters/storage/async_control_plane_execution_repository.py`; `orket/application/services/sandbox_control_plane_execution_service.py`; `orket/application/services/kernel_action_control_plane_service.py`; `orket/application/services/orchestrator_issue_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_service.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/gitea_state_control_plane_execution_service.py`
3. legacy authority to demote: `orket/application/review/run_service.py`; `orket/runtime/run_start_artifacts.py`; `orket/application/review/lanes/`; `orket/runtime/retry_classification_policy.py`
4. runtime entrypoints that must stop bypassing canonical identity: `orket/runtime/execution_pipeline.py`; `orket/application/workflows/turn_executor.py`; `orket/application/workflows/turn_tool_dispatcher.py`; `orket/application/workflows/orchestrator_ops.py`; `orket/orchestration/engine.py`; `orket/interfaces/routers/kernel.py`

Acceptance criteria:
1. new governed execution paths cannot start without canonical workload and run identity
2. retries and resumes publish append-only attempt history
3. old loop-shaped retry surfaces no longer act as hidden attempt truth
4. child workload composition can attribute parent/child workload identity explicitly

Representative proof commands:
1. `python -m pytest -q tests/application/test_control_plane_authority_service.py tests/integration/test_turn_executor_control_plane.py`
2. `python -m pytest -q tests/integration/test_orchestrator_issue_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py`
3. `python -m pytest -q tests/integration/test_async_control_plane_execution_repository.py`

Crosswalk update gate:
1. update `Workload`, `Run`, `Attempt`, and `Step` in `00B_CURRENT_STATE_CROSSWALK.md` in the same change as the code and proof
2. keep any touched row `partial` or `conflicting` until the legacy surface is reduced to adapter or projection-only behavior with an explicit migration note

Compatibility exits consumed:
1. `CE-01`
2. `CE-02`

## Workstream 2 - Reservation, lease, and resource universalization

Closeout artifact:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_2_CLOSEOUT.md`

Objective:
1. make reservation and lease truth the default admission and ownership discipline everywhere it matters

Crosswalk rows:
1. `Reservation`
2. `Lease`
3. `Resource`

Required deliverables:
1. reservation publication on every governed admission, scheduling, claim, hold, and exclusivity path
2. lease publication on every governed active ownership or mutation path
3. explicit reservation-to-lease promotion under supervisor control
4. unified resource registry model consuming sandbox as one instance rather than one special authority
5. orphan, stale, release, invalidation, and cleanup paths wired through the general model

Authority map:
1. canonical reservation and lease contracts: `orket/core/contracts/control_plane_models.py`; `orket/core/domain/control_plane_reservations.py`; `orket/core/contracts/state_backend.py`; `orket/core/domain/coordinator_card.py`
2. publication and lifecycle services: `orket/application/services/sandbox_control_plane_reservation_service.py`; `orket/application/services/sandbox_control_plane_lease_service.py`; `orket/application/services/sandbox_control_plane_resource_service.py`; `orket/application/services/tool_approval_control_plane_reservation_service.py`; `orket/application/services/coordinator_control_plane_reservation_service.py`; `orket/application/services/coordinator_control_plane_lease_service.py`; `orket/application/services/orchestrator_issue_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`; `orket/application/services/turn_tool_control_plane_resource_lifecycle.py`; `orket/application/services/gitea_state_control_plane_reservation_service.py`; `orket/application/services/gitea_state_control_plane_lease_service.py`; `orket/application/services/control_plane_publication_service.py`
3. resource-model surfaces to generalize: `orket/core/contracts/control_plane_models.py`; `orket/adapters/storage/async_control_plane_record_repository.py`; `orket/application/services/sandbox_runtime_lifecycle_service.py`; `orket/application/services/sandbox_lifecycle_reconciliation_service.py`; `orket/application/services/sandbox_terminal_outcome_service.py`; `orket/application/services/sandbox_runtime_cleanup_service.py`; `orket/application/services/sandbox_runtime_inspection_service.py`; `orket/application/services/sandbox_lifecycle_view_service.py`
4. runtime entrypoints that must share the same admission and ownership rules: `orket/runtime/execution_pipeline.py`; `orket/interfaces/coordinator_api.py`; `orket/application/workflows/turn_executor_control_plane.py`; `orket/application/workflows/orchestrator_ops.py`; `orket/services/sandbox_orchestrator.py`

Acceptance criteria:
1. no governed admission path still publishes undefined or implicit reservation truth
2. no governed ownership path mutates without lease truth where lease semantics apply
3. scheduler and non-sandbox runtime paths share the same reservation/lease rules
4. orphan and stale ownership handling is reconstructable across runs and attempts

Representative proof commands:
1. `python -m pytest -q tests/contracts/test_control_plane_reservation_contract.py tests/contracts/test_control_plane_lease_contract.py`
2. `python -m pytest -q tests/interfaces/test_coordinator_api_control_plane.py tests/integration/test_orchestrator_scheduler_control_plane.py`
3. `python -m pytest -q tests/integration/test_gitea_state_worker_control_plane.py tests/application/test_sandbox_control_plane_reservation_service.py tests/application/test_sandbox_control_plane_lease_service.py`
4. `python -m pytest -q tests/acceptance/test_sandbox_restart_reclaim_live_docker.py`

Crosswalk update gate:
1. update `Reservation`, `Lease`, and `Resource` in `00B_CURRENT_STATE_CROSSWALK.md` in the same change as the code and proof
2. do not mark the rows aligned while any governed admission or ownership path still relies on sandbox-only or subsystem-local ownership truth

Compatibility exits consumed:
1. `CE-03`

## Workstream 3 - Effect journal default-path convergence

Closeout artifact:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_3_CLOSEOUT.md`

Objective:
1. make the effect journal the universal authoritative write path for governed mutation and closure-relevant events

Crosswalk rows:
1. `Effect`
2. `Run`
3. `FinalTruthRecord`

Required deliverables:
1. one normative effect publication API or service boundary
2. mandatory effect-journal linkage on all governed mutation paths
3. ordered append-only integrity checks across the expanded path set
4. compatibility projections for older receipts or artifact surfaces
5. automated detection of governed mutation paths that bypass journal publication

Authority map:
1. canonical effect models and publication seam: `orket/core/contracts/control_plane_effect_journal_models.py`; `orket/core/domain/control_plane_effect_journal.py`; `orket/application/services/control_plane_publication_service.py`
2. execution services that must publish effect truth first: `orket/application/services/sandbox_control_plane_effect_service.py`; `orket/application/services/kernel_action_control_plane_service.py`; `orket/application/services/orchestrator_issue_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/gitea_state_control_plane_execution_service.py`; `orket/application/services/gitea_state_worker.py`
3. legacy or read-model surfaces to demote to projection-only: `workspace/observability/<run_id>/`; `orket/runtime/protocol_receipt_materializer.py`; `orket/runtime/run_summary.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/application/services/kernel_action_control_plane_view_service.py`; `orket/application/services/sandbox_lifecycle_view_service.py`
4. runtime entrypoints that must not bypass the journal: `orket/runtime/execution_pipeline.py`; `orket/application/workflows/turn_tool_dispatcher.py`; `orket/application/workflows/orchestrator_ops.py`; `orket/orchestration/engine.py`; `orket/kernel/v1/nervous_system_runtime.py`

Acceptance criteria:
1. effect truth is no longer authoritatively reconstructed from scattered artifacts on governed paths
2. legacy receipt and artifact surfaces are projections, not authorities
3. journal ordering and integrity proofs cover the broadened path set
4. final truth can consume published effect history directly

Representative proof commands:
1. `python -m pytest -q tests/contracts/test_control_plane_effect_journal_contract.py tests/application/test_control_plane_publication_service.py`
2. `python -m pytest -q tests/integration/test_turn_executor_control_plane_evidence.py tests/integration/test_turn_tool_control_plane_closeout.py`
3. `python -m pytest -q tests/application/test_kernel_action_control_plane_service.py tests/integration/test_orchestrator_issue_control_plane.py`
4. `python -m pytest -q tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py`

Crosswalk update gate:
1. update `Effect`, and any touched `Run` or `FinalTruthRecord` notes, in `00B_CURRENT_STATE_CROSSWALK.md` in the same change as the code and proof
2. do not mark the row aligned while any governed mutation path still depends on artifact reconstruction for authoritative effect truth

Compatibility exits consumed:
1. `CE-04`

## Workstream 4 - Checkpoint and recovery authority universalization

Closeout artifact:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_4_CLOSEOUT.md`

Objective:
1. stop saved-state existence from acting like recovery authority

Crosswalk rows:
1. `Checkpoint`
2. `RecoveryDecision`
3. `Attempt`

Required deliverables:
1. explicit checkpoint policy map: checkpoint-required, checkpoint-eligible, checkpoint-forbidden
2. supervisor-owned checkpoint publication on required or eligible boundaries
3. checkpoint acceptance records and invalidation logic generalized beyond current limited paths
4. recovery-decision publication for all governed recovery paths
5. runtime enforcement that resumed execution versus new-attempt execution is explicit

Authority map:
1. checkpoint and recovery models: `orket/core/contracts/control_plane_models.py`; `orket/core/contracts/control_plane_effect_journal_models.py`; `orket/core/domain/control_plane_recovery.py`
2. checkpoint publication and replay services: `orket/application/services/sandbox_control_plane_checkpoint_service.py`; `orket/application/services/gitea_state_control_plane_checkpoint_service.py`; `orket/application/workflows/turn_executor_control_plane.py`; `orket/application/workflows/turn_executor_resume_replay.py`; `orket/application/workflows/turn_executor_completed_replay.py`; `orket/application/workflows/turn_executor_control_plane_evidence.py`
3. recovery services and legacy seams to demote: `orket/application/services/sandbox_runtime_recovery_service.py`; `orket/application/services/sandbox_restart_policy_service.py`; `orket/application/services/turn_tool_control_plane_recovery.py`; `orket/application/services/turn_tool_control_plane_closeout.py`; `orket/application/services/gitea_state_control_plane_execution_service.py`; `orket/application/review/snapshot_loader.py`; `orket/application/review/models.py`
4. runtime entrypoints that must enforce explicit recovery mode: `orket/runtime/execution_pipeline.py`; `orket/services/sandbox_orchestrator.py`; `orket/application/services/sandbox_control_plane_execution_service.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/gitea_state_worker.py`

Acceptance criteria:
1. no resume path depends on snapshot existence alone
2. supervisor acceptance is required before checkpoint-backed continuation
3. recovery decisions are first-class and durable across all governed recovery paths
4. replay and reconciliation can consume checkpoint and recovery truth directly

Representative proof commands:
1. `python -m pytest -q tests/contracts/test_control_plane_recovery_contract.py tests/application/test_sandbox_control_plane_checkpoint_service.py`
2. `python -m pytest -q tests/application/test_kernel_action_control_plane_pre_effect_recovery.py tests/integration/test_sandbox_runtime_recovery_service.py`
3. `python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py`
4. `python -m pytest -q tests/acceptance/test_sandbox_runtime_recovery_live_docker.py tests/acceptance/test_sandbox_restart_reclaim_live_docker.py`

Crosswalk update gate:
1. update `Checkpoint`, `RecoveryDecision`, and any touched `Attempt` notes in `00B_CURRENT_STATE_CROSSWALK.md` in the same change as the code and proof
2. do not mark the rows aligned while snapshot or saved-state presence alone can still authorize continuation on any governed path

Compatibility exits consumed:
1. `CE-05`

## Workstream 5 - Reconciliation and operator-action convergence

Closeout artifact:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_5_CLOSEOUT.md`

Objective:
1. replace scattered operator and subsystem-specific reconciliation behavior with one published authority family

Crosswalk rows:
1. `ReconciliationRecord`
2. `OperatorAction`
3. `FinalTruthRecord`

Required deliverables:
1. generalized reconciliation-record publication across non-sandbox as well as sandbox paths
2. one operator-action publication family for commands, risk acceptance, and attestation
3. endpoint and policy refactors that stop operator influence from remaining implicit
4. enforcement that operator action never becomes world-state evidence except policy-bounded attestation, still visibly marked
5. final-truth input wiring from reconciliation and operator-action records

Authority map:
1. reconciliation publication surfaces: `orket/application/services/sandbox_lifecycle_reconciliation_service.py`; `orket/application/services/sandbox_control_plane_reconciliation_service.py`; `orket/application/services/turn_tool_control_plane_reconciliation.py`; `orket/application/services/turn_tool_control_plane_recovery.py`; `orket/application/services/gitea_state_control_plane_claim_failure_service.py`
2. operator-action publication surfaces: `orket/application/services/pending_gate_control_plane_operator_service.py`; `orket/application/services/sandbox_control_plane_operator_service.py`; `orket/application/services/tool_approval_control_plane_operator_service.py`; `orket/application/services/kernel_action_control_plane_operator_service.py`; `orket/application/services/control_plane_publication_service.py`
3. endpoint and read-model surfaces that must stop acting as hidden operator authority: `orket/interfaces/api.py`; `orket/interfaces/routers/sessions.py`; `orket/interfaces/routers/approvals.py`; `orket/interfaces/routers/kernel.py`; `orket/orchestration/approval_control_plane_read_model.py`; `orket/runtime/operator_override_logging_policy.py`; `orket/orchestration/engine.py`; `orket/orchestration/engine_approvals.py`
4. runtime entrypoints that must preserve operator input split explicitly: `orket/application/workflows/orchestrator.py`; `orket/application/workflows/orchestrator_ops.py`; `orket/application/services/sandbox_lifecycle_view_service.py`

Acceptance criteria:
1. operator inputs are no longer scattered across endpoint behavior, policies, and logs
2. reconciliation is no longer subsystem-specific
3. command, risk acceptance, and attestation remain distinct in read models and proofs
4. final truth can explain operator and reconciliation influence without collapsing them

Representative proof commands:
1. `python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py tests/application/test_tool_approval_control_plane_operator_service.py`
2. `python -m pytest -q tests/application/test_pending_gate_control_plane_operator_service.py tests/application/test_kernel_action_control_plane_operator_service.py`
3. `python -m pytest -q tests/integration/test_sandbox_lifecycle_reconciliation_service.py tests/integration/test_gitea_state_worker_control_plane.py`
4. `python -m pytest -q tests/acceptance/test_sandbox_orphan_reconciliation_live_docker.py`

Crosswalk update gate:
1. update `ReconciliationRecord`, `OperatorAction`, and any touched `FinalTruthRecord` notes in `00B_CURRENT_STATE_CROSSWALK.md` in the same change as the code and proof
2. do not mark the rows aligned while any authenticated operator path or divergence-handling path still acts through endpoint-local or log-local authority

Compatibility exits consumed:
1. `CE-06`

## Workstream 6 - Final-truth closure unification

Closeout artifact:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_6_CLOSEOUT.md`

Objective:
1. eliminate split-brain closeout between new control-plane truth and older summary surfaces

Sequencing note:
1. Execute this after Workstream 7 even though the numbering stays stable for reference continuity.
2. Final-truth closure cannot be treated as complete while governed mutation can still bypass namespace or safe-tooling boundaries.

Crosswalk rows:
1. `FinalTruthRecord`
2. `Run`
3. `Effect`
4. `OperatorAction`
5. `ReconciliationRecord`

Required deliverables:
1. one closure service or authority path that emits `FinalTruthRecord`
2. derived compatibility projections for run summary or packet-1 style surfaces where needed
3. closeout gating that forbids terminal governed completion without final-truth publication
4. explicit mapping from authority inputs to closure output fields
5. migration notes and deprecation plan for older closure-writing surfaces

Authority map:
1. canonical closure models and services: `orket/core/contracts/control_plane_models.py`; `orket/core/domain/control_plane_final_truth.py`; `orket/application/services/control_plane_publication_service.py`; `orket/application/services/sandbox_control_plane_closure_service.py`; `orket/application/services/sandbox_terminal_outcome_service.py`; `orket/application/services/kernel_action_control_plane_service.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/application/services/gitea_state_control_plane_execution_service.py`; `orket/application/services/gitea_state_control_plane_claim_failure_service.py`
2. legacy closure and truth surfaces to demote to projection-only: `orket/runtime/run_summary.py`; `orket/runtime/runtime_truth_contracts.py`; `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
3. read-model and operator-facing projections that must consume final truth rather than author it: `orket/application/services/sandbox_lifecycle_view_service.py`; `orket/application/services/kernel_action_control_plane_view_service.py`; `orket/orchestration/approval_control_plane_read_model.py`
4. runtime entrypoints that must fail closed without `FinalTruthRecord`: `orket/services/sandbox_orchestrator.py`; `orket/application/workflows/turn_tool_dispatcher.py`; `orket/application/workflows/orchestrator_ops.py`; `orket/runtime/execution_pipeline.py`; `orket/interfaces/routers/kernel.py`

Acceptance criteria:
1. every governed terminal path emits one `FinalTruthRecord`
2. no old summary surface can act as alternate truth authority
3. false completion claims are rejected from closure
4. degraded, uncertain, or operator-accepted outcomes remain visibly classified

Representative proof commands:
1. `python -m pytest -q tests/contracts/test_control_plane_final_truth_contract.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_packet1.py`
2. `python -m pytest -q tests/integration/test_sandbox_terminal_outcome_service.py tests/integration/test_turn_tool_control_plane_closeout.py`
3. `python -m pytest -q tests/integration/test_gitea_state_worker_control_plane.py tests/integration/test_sandbox_orchestrator_lifecycle.py`
4. `python -m pytest -q tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py tests/acceptance/test_sandbox_orchestrator_live_docker.py`

Crosswalk update gate:
1. update `FinalTruthRecord`, and any touched `Run`, `Effect`, `OperatorAction`, or `ReconciliationRecord` notes, in `00B_CURRENT_STATE_CROSSWALK.md` in the same change as the code and proof
2. do not mark the row aligned while any governed terminal path can still close without published final truth or while `run_summary.py` still writes authority rather than projecting it

Compatibility exits consumed:
1. `CE-07`

## Workstream 7 - Namespace and safe-tooling universalization

Closeout artifact:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_7_CLOSEOUT.md`

Objective:
1. make namespace and safe-tooling rules the default boundary across broader runtime workloads

Sequencing note:
1. Execute this before Workstream 6.
2. Namespace and safe-tooling hardening is a prerequisite to trustworthy closure because uncontrolled mutation paths invalidate closeout authority.

Crosswalk rows:
1. `Workload`
2. `Resource`
3. `Reservation`
4. `Lease`
5. `Effect`

Required deliverables:
1. one explicit namespace authority surface consumed by broader workloads, scheduling, resource targeting, and child composition
2. safe-tooling integration on every governed tool family that can affect state
3. degraded-mode tooling restrictions enforced through the same path
4. namespace inheritance and override rules for composed workloads
5. audit hooks proving undeclared capability or namespace escalation fails closed

Authority map:
1. safe-tooling and namespace enforcement surfaces: `orket/application/workflows/turn_tool_dispatcher.py`; `orket/application/services/turn_tool_control_plane_resource_lifecycle.py`; `orket/application/services/turn_tool_control_plane_service.py`; `orket/runtime/execution_pipeline.py`
2. workload, scheduling, and composition paths that must share namespace authority: `orket/runtime/workload_adapters.py`; `orket/application/services/orchestrator_issue_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_service.py`; `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`; `orket/application/workflows/turn_executor_control_plane.py`
3. supporting contracts and repositories that must participate: `orket/core/contracts/control_plane_models.py`; `orket/adapters/storage/async_control_plane_record_repository.py`; `orket/application/services/control_plane_publication_service.py`
4. runtime entrypoints and public surfaces that must fail closed on undeclared mutation scope: `orket/interfaces/api.py`; `orket/interfaces/routers/kernel.py`; `orket/orchestration/engine.py`

Acceptance criteria:
1. no governed tooling path can mutate without namespace and capability checks
2. broader runtime workloads share explicit namespace targeting instead of ambient access
3. child workload composition preserves supervisor authority and explicit grants
4. operator-gated tools remain distinct from world-state evidence

Representative proof commands:
1. `python -m pytest -q tests/application/test_turn_tool_dispatcher_policy_enforcement.py tests/application/test_turn_tool_dispatcher_compatibility.py`
2. `python -m pytest -q tests/application/test_turn_tool_control_plane_preflight_guards.py tests/integration/test_turn_executor_control_plane.py`
3. `python -m pytest -q tests/platform/test_no_old_namespaces.py tests/integration/test_orchestrator_scheduler_control_plane.py`

Crosswalk update gate:
1. update `Workload`, `Resource`, `Reservation`, `Lease`, and `Effect` in `00B_CURRENT_STATE_CROSSWALK.md` in the same change as the code and proof
2. do not mark touched rows aligned while any governed mutation path still relies on ambient namespace visibility, undeclared capability scope, or journal-free mutation

Compatibility exits consumed:
1. `CE-08`

## Workstream 8 - Documentation, authority-story, and closeout convergence

Closeout artifact:
1. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_8_CLOSEOUT.md`

Objective:
1. ensure code, packet, plan, closeout, and roadmap tell one story

Sequencing note:
1. This workstream closes last at lane scope.
2. Per-slice crosswalk and authority-story updates still land in the same change as each converged code slice; only the lane-wide documentation closeout waits for the other workstreams to converge.

Crosswalk rows:
1. any row changed by the converged code slices recorded in the same change

Required deliverables:
1. active implementation authority remains explicit across roadmap, packet README, project index, and archive wording
2. current-state crosswalk updates land in the same changes as converged code slices
3. README / project index / roadmap wording change together whenever lane status changes again
4. deprecation notes exist for superseded surfaces and compatibility exits
5. explicit statement of what remains open after convergence
6. each workstream has a stable closeout artifact that records crosswalk deltas, compatibility exits, surviving projection-only surfaces, proofs, and remaining gaps

Authority map:
1. authority docs that must agree: `docs/ROADMAP.md`; `docs/projects/ControlPlane/orket_control_plane_packet/README.md`; `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`; `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/CLOSEOUT.md`; this plan; the paired convergence requirements doc
2. governance checks that must pass when roadmap or project wording changes: `python scripts/governance/check_docs_project_hygiene.py`
3. proof and closeout surfaces that must stop claiming a different lane story: closeout docs, README notes, and any future convergence closeout material
4. execution rule: no workstream may be marked complete unless its closeout artifact, crosswalk rows, compatibility exits, and proof commands already tell the same story as the code

Acceptance criteria:
1. no live doc claims a different active implementation authority than the roadmap, packet README, and archive story
2. any future lane-status change updates roadmap, project index, README, and archive wording together in one authority-safe update
3. crosswalk rows move only with explicit code and proof evidence
4. compatibility exit ledger entries close or narrow in the same changes that reduce their authority risk
5. no workstream is marked complete without a closeout artifact that records surviving projection-only surfaces and remaining gaps explicitly

Crosswalk update gate:
1. update every touched row in `00B_CURRENT_STATE_CROSSWALK.md` in the same change as the paired code and proof
2. do not claim documentation convergence for any slice while roadmap, packet README, this plan, the relevant closeout artifact, and the touched crosswalk rows still tell different authority stories

Representative proof commands:
1. `python scripts/governance/check_docs_project_hygiene.py`
2. `python -m pytest -q tests/platform/test_no_old_namespaces.py`
3. `python -m pytest -q`

Compatibility exits consumed:
1. whichever exit ids the paired code slice truthfully narrows or closes in the same change
2. Workstream 8 does not own a separate compatibility surface; it records the documentation-side posture for the exit ids owned by Workstreams 1 through 7

## Verification matrix

Structural:
1. one canonical workload identity
2. one canonical run/attempt history model
3. no reservation-free governed ownership path
4. no resume-by-snapshot-existence path
5. no alternate closure authority path
6. no tool mutation path lacking namespace/capability/effect-journal linkage
7. no operator-input collapse

Integration:
1. admission -> reservation -> lease -> effect -> closure chain
2. pre-effect failure -> checkpoint/recovery decision -> resumed or new-attempt execution
3. effect uncertainty -> reconcile -> safe continuation or stop
4. operator command / risk acceptance / attestation -> final truth projection
5. non-sandbox path parity with sandbox path for core control-plane records

Live:
1. stale lease or orphan claim fails closed
2. degraded operator-approved continuation remains degraded in final truth
3. false success claim does not survive final-truth publication
4. namespace drift or undeclared capability escalation is rejected
5. real closeout path emits one final-truth authority record

## Stop conditions

1. Stop and narrow scope if the lane starts inventing new control-plane nouns instead of converging packet-v2 nouns.
2. Stop and split the lane if workload identity convergence turns into a full extension-platform redesign.
3. Stop and split the lane if namespace work turns into multitenant platform semantics.
4. Stop and split the lane if compatibility projections are being treated as alternate authorities.
5. Stop and narrow scope if a slice cannot name:
   1. the crosswalk row it is fixing,
   2. the old authority it is replacing,
   3. the new first-class record it is publishing.

## Execution order

Execution order is authoritative.
Workstream numbering stays stable to avoid unnecessary reference churn.

1. workload, run, and attempt promotion
2. reservation, lease, and resource universalization
3. effect journal default-path convergence
4. checkpoint and recovery authority universalization
5. reconciliation and operator-action convergence
6. namespace and safe-tooling universalization
7. final-truth closure unification
8. docs and authority-story convergence

## Completion gate

This lane is complete only when:
1. the runtime no longer has a meaningful split between governed control-plane paths and legacy/ambient truth paths for the covered surfaces
2. all covered terminal runs close through one `FinalTruthRecord`
3. effect truth is published, not reconstructed, on governed mutation paths
4. reservation and lease truth are universal across governed admission and ownership paths
5. checkpoint authority is explicit and supervisor-owned
6. operator influence is first-class, distinct, and auditable
7. namespace and safe-tooling rules are default-path behavior
8. every workstream has a closeout artifact that records touched crosswalk rows, compatibility exits, surviving projection-only surfaces, proofs, and remaining gaps truthfully
9. every compatibility exit ledger entry is either closed or explicitly reduced to projection-only status with a surviving non-authority note
10. crosswalk, docs, code, and proofs tell the same story


