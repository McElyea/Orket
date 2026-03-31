# CURRENT_AUTHORITY.md

Last updated: 2026-03-30

This file is the current canonical authority snapshot for high-impact runtime and governance paths.

It is intentionally narrow:
1. Agent behavior rules remain in `AGENTS.md`.
2. Contributor workflow rules remain in `docs/CONTRIBUTOR.md`.
3. This file tracks what is authoritative right now.
4. Control-plane convergence checkpoint and any explicit reopen sequencing stay in `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`; this file should name the live authority seams, not reproduce lane closeout detail.

ControlPlane is currently paused after a truthful partial-convergence checkpoint. This file records only live seams and does not imply an active convergence queue.

This file does not define:
1. all supported features,
2. all experimental surfaces,
3. all repository conventions.

It defines only the currently authoritative paths that agents and contributors must treat as canonical unless explicitly directed otherwise.

## Current Canonical Paths

1. Install/bootstrap: `python -m pip install -e ".[dev]"`
2. Default runtime: `python main.py`
3. Named card runtime: `python main.py --card <card_id>`
4. Legacy named rock runtime alias: `python main.py --rock <rock_name>`
5. API runtime: `python server.py`
6. Canonical test command: `python -m pytest -q`
7. Active docs index: `docs/README.md`
8. Active roadmap: `docs/ROADMAP.md`
9. Active contributor workflow: `docs/CONTRIBUTOR.md`
10. Long-lived specs root: `docs/specs/`
11. Staged artifact candidate index: `benchmarks/staging/index.json`
12. Published artifact index: `benchmarks/published/index.json`
13. Canonical provider runtime target selection: `orket/runtime/provider_runtime_target.py`
14. Core release/versioning policy: `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`
15. Core release gate checklist: `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`
16. Core release proof report template: `docs/specs/CORE_RELEASE_PROOF_REPORT.md`
17. Core release proof report storage: `docs/releases/<version>/PROOF_REPORT.md`
18. Core release evidence storage: `benchmarks/results/releases/<version>/`
19. Core release automation workflow: `.gitea/workflows/core-release-policy.yml`
20. Core release automation script: `scripts/governance/check_core_release_policy.py`
21. Core release prep script for release-only worktrees: `scripts/governance/prepare_core_release.py`
22. Canonical core release tag rule: every post-`0.4.0` versioned commit on pushed `main` must carry the matching annotated `v<major>.<minor>.<patch>` tag on that exact commit.
23. Pytest sandbox fail-closed fixture: `tests/conftest.py`
24. Determinism claim/gate policy: `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
25. Canonical runtime event artifact path: `agent_output/observability/runtime_events.jsonl`
26. Terraform plan reviewer durable spec: `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`
27. Terraform plan reviewer live smoke output path: `.orket/durable/observability/terraform_plan_review_live_smoke.json`
28. Canonical control-plane durable store path: `.orket/durable/db/control_plane_records.sqlite3` via `orket/runtime_paths.py`; the same store now durably persists first-class `ResolvedPolicySnapshot` and `ResolvedConfigurationSnapshot` objects for top-level cards epic invocation admission, manual review-run admission, sandbox execution initialization, governed kernel-action admission, governed turn-tool admission, default orchestrator issue dispatch admission, scheduler-owned namespace mutation admission, and Gitea state-worker claimed-run admission via `orket/application/services/control_plane_snapshot_publication.py`, `orket/application/services/cards_epic_control_plane_service.py`, `orket/application/services/review_run_control_plane_service.py`, `orket/application/review/run_service.py`, `orket/application/services/sandbox_control_plane_execution_service.py`, `orket/application/services/kernel_action_control_plane_service.py`, `orket/application/services/turn_tool_control_plane_service.py`, `orket/application/services/orchestrator_issue_control_plane_service.py`, `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`, and `orket/application/services/gitea_state_control_plane_execution_service.py`; manual review deterministic-decision and model-assisted-critique artifacts now also mark `execution_state_authority=control_plane_records`, `lane_output_execution_state_authoritative=false`, and carry canonical review-run `control_plane_run_id`/`control_plane_attempt_id`/`control_plane_step_id` refs when that durable publication exists, so lane JSON no longer looks like standalone execution-state authority, and review replay, answer-key scoring, and consistency extraction now consume shared validated review-bundle payload or artifact loaders, including truncation-bounds snapshot inputs, instead of validating bundle markers and then rereading snapshot or lane JSON ad hoc
28. Canonical governed turn-tool path defaults to `issue:<issue_id>` namespace scope and must fail closed on broader scope declarations, now publishes a first-class namespace `ReservationRecord` on governed admission, explicitly promotes that reservation to an active `LeaseRecord` on execution start with fail-closed activation rollback that invalidates unpromoted reservation truth and releases any just-published active execution lease when promotion fails, mirrors that namespace authority through shared `ResourceRecord` snapshots on activation, closeout release, and activation rollback, and now fails closed when existing executing or completed governed runs try to continue or reuse success while the latest namespace `ResourceRecord` no longer agrees with the active or completed lease authority, carries those reservation/lease refs as checkpoint-acceptance dependencies on the pre-effect `resume_same_attempt` checkpoint boundary for each new governed attempt, now also records the canonical governed run, attempt, step, reservation, lease, and namespace-resource ids directly inside governed turn-tool protocol receipt invocation manifests when that durable authority exists, protocol run-graph reconstruction now preserves those canonical control-plane refs on reconstructed governed tool-call nodes when manifest evidence exists, receipt-derived artifact provenance entries plus packet-1 provenance, packet-2 source-attribution, narration/effect-audit, and idempotency summaries now preserve canonical governed run, attempt, and step ids when authoritative receipt-manifest provenance exists for the generated artifact or narrated effect, those legacy run-summary packet-1, packet-2, and artifact-provenance blocks now also self-identify as `projection_only` with explicit fact-backed `projection_source` markers and fail closed if that framing drifts instead of reading like native effect authority, and legacy protocol receipt materialization into run-ledger `tool_call` / `operation_result` rows now marks those rows `projection_only` with explicit `observability.protocol_receipts.log` source plus projected effect-journal refs for governed turn-tool results instead of letting receipt replay look like native effect authority, publishes terminal `terminate_run` recovery decisions for pre-effect blocked and post-effect failed governed execution with checkpoint or effect preconditions and blocked continuation actions, makes preflight terminal closeout fail closed by materializing an initial attempt when missing, abandoning any existing non-terminal current attempt with explicit `pre_effect_failure` taxonomy plus terminal recovery-decision authority before run terminal state publication, and releasing promoted execution authority when that closeout occurs after execution start, and on `resume_mode` now performs supervisor-owned checkpoint-backed same-attempt recovery for unfinished pre-effect runs on the current attempt; that safe pre-effect path consumes the accepted checkpoint snapshot before prompt or model work and continues on the current attempt instead of bootstrapping attempt 2, fails closed if immutable checkpoint snapshot identity drifts from the current run or namespace request, closes immediately into reconciliation-closed terminal truth if durable operation artifacts already exist without matching step/effect authority, while the recovery and replay helpers still consume older `resume_new_attempt_from_checkpoint` governed lineage truthfully when those records already exist, unfinished post-effect or effect-boundary-uncertain attempts still publish explicit reconciliation records plus `require_reconciliation_then_decide` recovery authority and then close immediately into terminal `reconciliation_closed` truth with a second reconciliation-rationalized `terminate_run` decision, and already-dirty same-attempt or replacement-attempt resumes now fail closed before model invocation instead of being treated as clean retries; completed successful governed turn re-entry still requires accepted checkpoint authority, an immutable checkpoint snapshot artifact, matching snapshot identity, aligned durable step plus effect plus operation truth, no unexpected operation artifacts, and matching durable namespace resource-versus-lease authority before reusing artifacts ahead of prompt or model execution and ahead of checkpoint artifact rewrite rather than rerunning the model and only reusing finalized truth later, and governed runs already in terminal or recovery-blocked states now fail closed before model invocation and before checkpoint artifact rewrite instead of drifting into new tool execution via `orket/application/workflows/turn_tool_dispatcher_support.py`, `orket/application/workflows/tool_invocation_contracts.py`, `orket/application/workflows/turn_tool_dispatcher_protocol.py`, `orket/application/workflows/turn_executor_control_plane_evidence.py`, `orket/application/workflows/turn_executor_completed_replay.py`, `orket/application/workflows/turn_executor_resume_replay.py`, `orket/application/workflows/turn_executor_model_flow.py`, `orket/application/workflows/turn_executor_model_artifacts.py`, `orket/application/workflows/turn_executor_control_plane.py`, `orket/application/services/turn_tool_control_plane_service.py`, `orket/application/services/turn_tool_control_plane_state_gate.py`, `orket/application/services/turn_tool_control_plane_resource_lifecycle.py`, `orket/application/services/control_plane_resource_authority_checks.py`, `orket/application/services/turn_tool_control_plane_recovery.py`, `orket/application/services/turn_tool_control_plane_reconciliation.py`, `orket/application/services/turn_tool_control_plane_closeout.py`, `orket/runtime/execution_pipeline.py`, `orket/runtime/phase_c_runtime_truth.py`, `orket/runtime/protocol_receipt_materializer.py`, `orket/runtime/run_graph_reconstruction.py`, `orket/runtime/run_summary.py`, `orket/runtime/run_summary_artifact_provenance.py`, and `orket/runtime/run_summary_packet2.py`
29. Canonical Gitea state worker path now publishes one lease-backed control-plane run per claimed card and lease epoch, a durable resolved policy snapshot plus resolved configuration snapshot for that claimed-run admission, a first-class claim reservation before the initial claim mutation, explicit reservation-to-lease linkage on the claimed lease, promotion of that reservation only after the `ready -> in_progress` claim transition succeeds with fail-closed promotion rollback that invalidates unpromoted reservation truth and releases just-published active lease authority when promotion fails, shared `ResourceRecord` history on claim, renew, expiry, release, claim-failure uncertainty, and promotion rollback, now fails closed before backend renew when the latest shared active resource snapshot no longer agrees with the active lease authority, re-publishes terminal expiry/release lease authority when the latest shared resource snapshot drifted away from already-terminal lease truth instead of silently trusting lease-only terminal history, a pre-effect `resume_forbidden` checkpoint from the claimed-card observation, worker-owned claim/finalize steps, effect-journal entries for observed state transitions, terminal recovery decisions on failure including blocked closeout for active control-plane resource drift, and pre-effect claim-failure closeout with reservation invalidation, `lease_uncertain`, a reconciliation record, and reconciliation-closed final truth when the initial claim transition fails via `orket/application/services/gitea_state_control_plane_execution_service.py`, `orket/application/services/gitea_state_control_plane_checkpoint_service.py`, `orket/application/services/gitea_state_control_plane_claim_failure_service.py`, `orket/application/services/gitea_state_control_plane_lease_service.py`, `orket/application/services/gitea_state_control_plane_reservation_service.py`, `orket/application/services/gitea_state_worker.py`, and `orket/application/services/control_plane_resource_authority_checks.py`
30. Canonical approval-gated admission paths now publish a first-class `operator_hold_reservation` on request creation or admission, resolve that reservation on approval decision, and publish first-class guard-review operator commands on the pending-gate surface for supported non-tool resolutions, with governed kernel `NEEDS_APPROVAL` admit now publishing that approval-hold reservation from the async orchestration-engine path before response shaping instead of leaving that reservation seam router-local, while approval list and detail views surface the latest reservation and approval-surface operator-command summary, plus `control_plane_target_ref`, the latest target-side run and attempt summary when durable execution truth exists including namespace scope, admission decision receipt, policy snapshot id, configuration snapshot id, creation timestamp, and attempt count, the latest target-side resource summary for supported governed target runs now including default orchestrator issue-dispatch runs plus scheduler-owned namespace mutation and child-workload composition runs alongside governed turn-tool and kernel-action runs, the latest target-side step summary including namespace scope, capability used, output ref, resources touched, and receipt refs, the latest target-side checkpoint summary including creation timestamp, invalidation and dependency detail, policy digest, integrity verification ref, required reobservation class, acceptance decision timestamp, acceptance supervisor authority, evaluated policy digest, dependent effect or reservation or lease refs, and rejection reasons, the latest target-side effect-journal summary including step id, publication sequence, intended target, observed result ref, authorization-basis ref, publication timestamp, integrity verification ref, prior-entry linkage, contradiction or supersession refs, entry digest, and uncertainty, the latest target-side operator action summary including `input_class`, `command_class`, `risk_acceptance_scope`, `attestation_scope`, `attestation_payload`, `precondition_basis_ref`, receipt refs, affected transition refs, and affected resource refs, approval-resolution operator actions for supported governed turn-tool, kernel-action, orchestrator issue-dispatch, and scheduler-owned namespace mutation/child-workload targets now also carrying the canonical shared target `resource_id` in those `affected_resource_refs` when durable execution truth exists, the latest target-side reservation summary including reservation kind, reservation invalidation basis, supervisor authority, and promotion linkage, and the latest target-side final-truth summary including fuller classifications, authoritative result ref, and authority sources when the approval payload names a governed target or when authoritative approval-reservation truth names that governed target on the kernel approval path via `orket/application/services/tool_approval_control_plane_reservation_service.py`, `orket/application/services/kernel_action_pending_approval_reservation.py`, `orket/application/services/tool_approval_control_plane_operator_service.py`, `orket/application/services/control_plane_target_resource_refs.py`, `orket/application/services/pending_gate_control_plane_operator_service.py`, `orket/application/workflows/orchestrator_ops.py`, `orket/interfaces/routers/kernel.py`, `orket/orchestration/engine.py`, `orket/orchestration/engine_approvals.py`, `orket/orchestration/approval_control_plane_read_model.py`, and `orket/application/workflows/orchestrator.py`
31. The standalone coordinator API now publishes first-class non-hedged `ReservationRecord` truth for claim admission, explicitly promotes those reservations to lease authority on successful claim with fail-closed promotion rollback that invalidates unpromoted reservation truth, releases just-published active lease authority when promotion fails, and now mirrors that rollback through the same shared `ResourceRecord` seam, publishes `LeaseRecord` expiry on the open-cards observation path in addition to claim, renew, expiry-before-reclaim, and release transitions, mirrors those same transitions through shared `ResourceRecord` snapshots, now fails closed when renew, expiry, or release would continue while the latest shared coordinator `ResourceRecord` no longer agrees with the active lease authority, preflights stale-expiry publication and active lease/resource authority before open-cards listing plus claim/renew/complete/fail store mutation so coordinator ownership does not change after detected drift, and exposes the latest reservation, lease, and resource summary on list, claim, renew, complete, and fail responses including reservation kind, reservation basis, reservation supervisor authority, promotion rule, lease resource id, lease expiry basis, lease cleanup eligibility rule, granted timestamp, publication timestamp, last confirmed observation, and resource current state via `orket/interfaces/coordinator_api.py`, `orket/application/services/coordinator_control_plane_reservation_service.py`, and `orket/application/services/coordinator_control_plane_lease_service.py`
32. Canonical sandbox operator views now surface the latest reconciliation summary when durable control-plane truth exists, including `control_plane_reconciliation_id`, `control_plane_divergence_class`, and `control_plane_safe_continuation_class`, alongside run, attempt, reservation, lease, latest resource id/kind/state/orphan classification, checkpoint, effect-journal including latest intended target, observed result ref, authorization-basis ref, integrity verification ref, and uncertainty classification, latest operator-action split summary including `input_class`, `command_class`, `risk_acceptance_scope`, `attestation_scope`, `attestation_payload`, `precondition_basis_ref`, receipt refs, and affected transition/resource refs, and fuller final-truth classifications including result, closure basis, terminality basis, evidence sufficiency, residual uncertainty, degradation, authoritative result ref, and authority sources via `orket/application/services/sandbox_lifecycle_view_service.py`
33. Canonical governed kernel-action replay and audit views now surface the latest reservation summary for the run when durable control-plane truth exists, including operator-hold reservations created by approval-required admission and run-owned concurrency reservations created by governed admission with promoted run-owned execution reservations taking precedence over stale terminal hold records, the latest execution-lease summary when present, the latest resource summary when present, current attempt failure boundary plus taxonomy and recovery-decision/action summary when present, the latest step summary including namespace scope, resources touched, and receipt refs, the latest operator action including `input_class`, `command_class`, `risk_acceptance_scope`, `attestation_scope`, `attestation_payload`, `precondition_basis_ref`, receipt refs, and affected transition/resource refs, and fuller final-truth classifications including evidence sufficiency, residual uncertainty, degradation, terminality basis, authoritative result ref, and authority sources via `orket/application/services/kernel_action_control_plane_view_service.py` and `orket/interfaces/routers/kernel.py`
34. Canonical default orchestrator issue-dispatch now publishes one first-class control-plane run and attempt per `session_id + issue_id + seat + turn_index`, a concurrency `ReservationRecord` and promoted `LeaseRecord` for the issue dispatch slot, a shared issue-dispatch-slot `ResourceRecord` on activation, closeout release, and fail-closed dispatch-start rollback, fail-closed dispatch-start authority rollback that invalidates an unpromoted reservation and releases any just-published active lease when reservation-to-lease promotion fails, fail-closed reused-run rejection when dispatch run ids collide with still-active lifecycle truth or with non-terminal attempt drift under terminal run truth, fail-closed namespace-scope drift rejection on reused closed runs and active closeout paths, fail-closed reused-run reservation or lease drift rejection when closed dispatch runs still carry active resource authority or lack promoted-to-lease lineage, fail-closed active-closeout rejection when dispatch runs no longer carry promoted reservation plus active lease authority, fail-closed resource-drift rejection when the latest shared issue-dispatch-slot `ResourceRecord` no longer agrees with the active or closed dispatch lease, a dispatch `StepRecord` plus `EffectJournalEntryRecord` on turn start, a closeout `StepRecord` plus `EffectJournalEntryRecord` for both transition-based and observation-only closeouts, terminal `FinalTruthRecord` plus lease release on later authoritative issue transitions or on successful observed-status closeout when no later issue transition occurs, terminal `RecoveryDecisionRecord` authority for failed or blocked closeouts, and fail-closed closeout rejection when an active dispatch reservation points at terminal attempt drift via `orket/application/services/control_plane_resource_authority_checks.py`, `orket/application/services/orchestrator_issue_control_plane_service.py`, `orket/application/services/orchestrator_issue_control_plane_support.py`, `orket/application/workflows/orchestrator.py`, and `orket/application/workflows/orchestrator_ops.py`
35. Canonical default orchestrator scheduler-owned issue mutation now publishes explicit issue-scoped namespace authority when no active issue-dispatch run exists: dependency-block propagation, pre-dispatch retry or terminal transitions such as runtime-guard or ODR stop paths, missing-seat transitions, execution-pipeline resume requeue of stalled in-progress/code-review/awaiting-guard issues, targeted execution-pipeline issue-resume requeue, and other scheduler-owned issue status mutations now publish one first-class control-plane run and attempt, a namespace `ReservationRecord` plus promoted `LeaseRecord`, shared issue-scoped `ResourceRecord` snapshots on activation, closeout release, and fail-closed namespace-activation rollback, fail-closed namespace-activation rollback that invalidates unpromoted reservations and releases just-published active namespace leases when promotion fails, fail-closed non-terminal reused-run rejection when scheduler mutation run ids collide with still-active lifecycle truth or with non-terminal attempt drift under terminal run truth, fail-closed namespace-scope drift rejection for reused closed mutation runs, fail-closed reused-run reservation or lease drift rejection when closed scheduler mutation runs still carry active resource authority or lack promoted-to-lease lineage, fail-closed resource-drift rejection when the latest shared issue-scoped `ResourceRecord` no longer agrees with the closed namespace lease, a scheduler mutation `StepRecord`, an `EffectJournalEntryRecord`, terminal `FinalTruthRecord`, and terminal `RecoveryDecisionRecord` authority for failed or blocked closeouts; team-replan child issue creation now publishes the same namespace reservation, lease, resource, step, effect, and final-truth family for the child workload-composition mutation via `orket/application/services/control_plane_resource_authority_checks.py`, `orket/application/services/orchestrator_scheduler_control_plane_service.py`, `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`, `orket/application/services/orchestrator_issue_control_plane_support.py`, `orket/application/workflows/orchestrator.py`, `orket/application/workflows/orchestrator_ops.py`, and `orket/runtime/execution_pipeline.py`

36. Canonical control-plane recovery taxonomy resolution now derives `failure_plane` and `failure_classification` from both canonical enum tokens and sanctioned legacy basis aliases before persisting `RecoveryDecisionRecord`, and carries those same canonical fields onto failed or interrupted attempt updates where recovery decisions are published via `orket/core/domain/control_plane_recovery.py`, `orket/application/services/sandbox_control_plane_execution_service.py`, `orket/application/services/turn_tool_control_plane_closeout.py`, and `orket/application/services/gitea_state_control_plane_claim_failure_service.py`
37. Canonical governed kernel-action failure handling now publishes explicit terminal recovery authority for both observed and pre-effect commit failures: observed-execution policy-rejected or error outcomes mark failed attempts with `post_effect_observed` taxonomy and publish terminal `RecoveryDecisionRecord` authority, while non-observed pre-effect policy-rejected or error outcomes keep attempts `abandoned` with `pre_effect_failure` taxonomy and publish terminal `RecoveryDecisionRecord` authority before terminal final-truth closeout via `orket/application/services/kernel_action_control_plane_service.py` and `orket/application/services/kernel_action_control_plane_failure.py`
38. Canonical governed kernel-action lifecycle now publishes a first-class admission `ReservationRecord` per run, promotes that reservation to an active execution `LeaseRecord` on commit-time execution start only when execution truth is committed or observed with fail-closed activation rollback that invalidates unpromoted reservations and releases just-published active execution leases when promotion fails, mirrors that execution authority through shared `ResourceRecord` snapshots on activation, terminal release, and activation rollback, now fails closed when existing run consistency is re-entered while a durable execution lease exists but the matching `ResourceRecord` no longer agrees with it, enforces an explicit default `session:<session_id>` namespace scope on governed kernel runs with fail-closed rejection of broader proposal/request namespace-scope declarations, now records commit-step namespace scope truth and uses that run namespace for kernel-action reservation or lease target scope publication when present, keeps pre-effect terminal policy rejection without observed execution on reservation-only authority (no execution lease promotion), fails closed on unsupported commit status tokens before publishing execution truth, releases execution lease authority on terminal commit closeout, releases unpromoted admission reservations on terminal session-end cancellation and pre-effect terminal closeout, fail-closed terminalizes any non-terminal current attempt as `abandoned` before run cancellation on session-end closure, now publishes optional authenticated run-scoped `operator_attestation` truth on kernel session-end when explicitly requested with bounded scope and payload (without collapsing it into command or risk-acceptance records), with both kernel session-end cancel and bounded attestation now carrying the canonical execution-scope `resource_id` in durable `affected_resource_refs`, governed kernel `NEEDS_APPROVAL` admit now publishes its approval-hold reservation from an application-owned async engine seam before response shaping, and the shared kernel-action control-plane view now owns the async engine admit/commit/end-session response projection contract instead of leaving the full ref set router-local, so authenticated kernel responses and direct async engine responses both return control-plane response references after durable publication (`control_plane_run_id`, `control_plane_attempt_id`, `control_plane_attempt_state`, `control_plane_step_id`, plus reservation and lease and resource and final-truth refs when present, plus recovery decision/action refs and latest operator-action id when present) via `orket/interfaces/routers/kernel.py`, `orket/orchestration/engine.py`, `orket/application/services/kernel_action_pending_approval_reservation.py`, `orket/application/services/kernel_action_control_plane_service.py`, `orket/application/services/kernel_action_control_plane_operator_service.py`, `orket/application/services/kernel_action_control_plane_resource_lifecycle.py`, `orket/application/services/kernel_action_control_plane_view_service.py`, `orket/application/services/control_plane_resource_authority_checks.py`, `orket/application/services/kernel_action_control_plane_support.py`, and `orket/application/services/kernel_action_control_plane_outcome.py`
39. Canonical control-plane contract model authority now fails closed on unsupported `contract_version` for first-class records, keeping enum-backed packet-v2 nouns and record families pinned to `control_plane.contract.v1`, with explicit contract-proof coverage for run, reservation, and final-truth record families plus matrix-proof coverage that all first-class record models pin to one contract-version default via `orket/core/contracts/control_plane_models.py`, `orket/core/domain/control_plane_enums.py`, `tests/contracts/test_control_plane_contract_schema.py`, and `tests/contracts/test_control_plane_contract_version_matrix.py`
40. Canonical sandbox create-record failure handling now fail-closes any partial allocation authority publication by releasing just-published active `LeaseRecord` truth linked to the create-path reservation, publishing a matching shared `ResourceRecord` closeout when durable lifecycle authority never finished initializing, and invalidating the still-unpromoted allocation `ReservationRecord` before surfacing create failure, preventing create-path lease, resource, or reservation drift when lifecycle record creation fails after lease publication via `orket/services/sandbox_orchestrator.py`, `orket/application/services/sandbox_control_plane_resource_service.py`, `orket/application/services/sandbox_runtime_lifecycle_service.py`, and `orket/application/services/sandbox_control_plane_reservation_service.py`
41. Canonical authenticated session halt (`/v1/sessions/{session_id}/halt`) now publishes a durable session-scoped `OperatorActionRecord` command (`cancel_run`) with the authenticated non-secret actor fingerprint and explicit accepted-cancel versus no-active-task result classification on the default API-to-engine path via `orket/interfaces/api.py`, `orket/orchestration/engine.py`, and `orket/orchestration/engine_services.py`
42. Canonical authenticated interaction cancel (`/v1/interactions/{session_id}/cancel`) now publishes durable interaction-scoped `OperatorActionRecord` `cancel_run` commands (session-scope or turn-scope targeting) with authenticated non-secret actor fingerprints on the default API interaction-control path via `orket/interfaces/routers/sessions.py` and `orket/interfaces/api.py`
43. Canonical top-level cards epic execution now publishes one invocation-scoped control-plane `RunRecord`, one initial `AttemptRecord`, and one invocation-start `StepRecord` per `run_epic(...)` call, with durable policy/config snapshots derived from the canonical cards workload contract and terminal or waiting lifecycle transitions reflected back into run-ledger artifacts plus an additive `run_summary.json` `control_plane` projection that reads those durable records instead of inventing separate cards-epic run truth, and that legacy summary block now explicitly self-identifies as `projection_only` with source `control_plane_records` and fails closed if that framing drifts, if lower-level projected control-plane ids survive without the parent ids they depend on, if a projected cards run drops core run metadata while still carrying `run_id`, if projected attempt ids survive without attempt state or a positive attempt ordinal, if projected attempt state or ordinal survives after projected `attempt_id` drops, if projected `current_attempt_id` survives after projected `attempt_id` drops, if projected `current_attempt_id` drifts from projected `attempt_id` when both are present, if projected attempt ids drift outside the projected run lineage, or if projected step ids drift outside the projected run lineage, survive without `step_kind`, or keep projected `step_kind` after projected `step_id` drops via `orket/application/services/cards_epic_control_plane_service.py`, `orket/runtime/execution_pipeline.py`, `orket/runtime/run_summary.py`, and `orket/runtime/run_summary_control_plane.py`
44. Canonical manual review-run execution now publishes one first-class control-plane `RunRecord`, one initial `AttemptRecord`, and one `review_run_start` `StepRecord` per review invocation, with durable policy/config snapshots derived from the canonical review-run workload contract and surfaced back through `run_manifest.json` plus review result and CLI `control_plane` summary projection fields that read from those durable records, now explicitly self-identify as `projection_only` with source `control_plane_records`, and fail closed if that framing drifts, if projected run or attempt or step refs drift from the enclosing review result run identity and manifest control-plane refs, if lower-level projected attempt or step refs survive after parent run or attempt refs drop, if projected attempt state or ordinal survives after projected `attempt_id` drops, if projected `step_kind` survives after projected `step_id` drops, if projected attempt or step refs drift outside the projected run lineage, if the embedded manifest drops control-plane refs still carried by the returned summary, or if that returned summary keeps projected run, attempt, or step ids while dropping projected run metadata, attempt state or ordinal, or step kind; the embedded review-result `manifest` surface now also validates those persisted execution-authority markers before leaving the process and fails closed if they drift, if it omits those returned control-plane refs, if its attempt or step refs drift outside the declared `control_plane_run_id` lineage, or if top-level review-run identity is empty, while `orket review diff`, `orket review pr`, and `orket review files` now surface that serialization failure as structured `E_REVIEW_RUN_FAILED` output instead of an uncaught exception; fresh review manifests plus persisted deterministic-decision and model-assisted-critique artifacts now also declare `execution_state_authority=control_plane_records`, mark lane outputs non-authoritative for execution state, carry canonical review-run run/attempt/step refs, require non-empty manifest and lane-payload `run_id`, reject fresh manifest or lane-payload `control_plane_run_id` that drifts from the artifact `run_id`, reject fresh manifest or lane attempt or step refs that drift outside the declared `control_plane_run_id` lineage, require lane-payload `control_plane_run_id` / `control_plane_attempt_id` / `control_plane_step_id` whenever the manifest declares them, reject lower-level manifest or lane control-plane refs that survive after parent run or attempt refs drop, and fail closed if those execution-authority markers drift; `orket review replay --run-dir`, direct `orket review replay --snapshot ... --policy ...` when those files target canonical bundle artifacts from the same run directory, the review answer-key scoring path, the review consistency-signature path, and the persisted `check_1000_consistency.py` validator now also validate persisted review-bundle authority markers plus required manifest and lane-payload `run_id`, required lane-payload `control_plane_*` refs when the manifest declares them, lower-level manifest or lane control-plane refs that survive without parent run or attempt refs, manifest or lane attempt or step refs that drift outside the declared `control_plane_run_id` lineage, and persisted manifest and lane-payload run or control-plane refs before treating bundle artifacts as trustworthy evidence and fail closed if those markers or refs drift, with replay, scoring, and consistency now consuming shared validated review-bundle payload or artifact loaders instead of validating markers and then rereading lane JSON or replay inputs ad hoc, review answer-key scoring now also emits explicitly versioned `reviewrun_answer_key_score_v1` reports with required top-level `run_id` plus fixture/snapshot/policy provenance fields, required nested deterministic/model-assisted score blocks whose aggregate totals must stay aligned with the per-issue rows they summarize, explicit model reasoning/fix weights needed to prove reasoning and fix subtotals against those same rows, required per-issue row shape, and disabled model blocks that cannot carry derived model activity, and workload-side code-review probe score consumers now fail closed if that score-report contract drifts at the nested block, aggregate, issue-row, or top-level provenance level instead of trusting ad hoc dict shape, workload-side code-review probe bundles that reuse that shared scoring seam now also emit aligned bundle-local `run_id` values on deterministic and model-assisted lane payloads, failing closed before artifact persistence when that bundle-local `run_id` is empty so the same validation rejects missing or drifted bundle run identity instead of silently accepting lane-local omissions, the review consistency report producer now also validates its own report contract before write through the shared consistency-report validator so drifted `contract_version` or other malformed contract framing never persists as review-local JSON while truthful failed outcomes can still persist as failed reports, and the persisted `check_1000_consistency.py` validator now also fails closed before trusting report JSON when `contract_version` drifts, when those default, strict, replay, or baseline report `run_id` values are empty, when required nested baseline/default/strict/replay signature digests, deterministic finding-row code/severity/message/path/span/details shape, deterministic-lane version, executed-check lists, or truncation framing drift, or when scenario-local `truncation_check` digests, byte counts, or boolean flags drift instead of trusting shallow `ok` or counter fields alone; API run-detail/session-status views, governance dashboard seed metrics, protocol/sqlite run-ledger parity consumers, protocol/sqlite run-ledger parity-campaign rows, protocol rollout evidence bundle summaries, protocol enforce-window signoff payloads, protocol enforce-window capture manifests, and protocol cutover-readiness summaries now also consume one shared validated run-ledger projection family, while the SQLite run-ledger adapter preserves malformed persisted `summary_json` or `artifact_json` payloads long enough for that seam to detect them, and rollout/signoff/cutover now also share one protocol invalid-projection detail helper instead of carrying divergent local parsers, so malformed surfaces fail closed instead of leaking raw payloads, disappearing inside the adapter, being normalized into false-green parity, or being collapsed into generic parity-campaign mismatch counts inside campaign rows, rollout summaries, signoff gates, capture manifests, or cutover-readiness outputs; human CLI output now also surfaces durable review run/attempt/step refs and start-step kind from that same control-plane summary instead of collapsing the surface to state-only text, so deterministic/model-assisted lane outputs do not masquerade as standalone run or attempt or step truth via `orket/application/services/review_run_control_plane_service.py`, `orket/application/review/control_plane_projection.py`, `orket/application/review/bundle_validation.py`, `orket/application/review/run_service.py`, `orket/application/review/models.py`, `orket/application/services/run_ledger_summary_projection.py`, `orket/runtime/run_ledger_projection.py`, `orket/runtime/run_ledger_parity.py`, `orket/runtime/protocol_ledger_parity_campaign.py`, `orket/adapters/storage/async_repositories.py`, `orket/interfaces/orket_bundle_cli.py`, `scripts/reviewrun/score_answer_key.py`, `scripts/reviewrun/score_answer_key_contract.py`, `scripts/reviewrun/run_1000_consistency.py`, `scripts/reviewrun/check_1000_consistency.py`, `scripts/workloads/code_review_probe.py`, `scripts/workloads/code_review_probe_support.py`, `scripts/workloads/code_review_probe_reporting.py`, `scripts/protocol/parity_projection_support.py`, `scripts/protocol/publish_protocol_rollout_artifacts.py`, `scripts/protocol/record_protocol_enforce_window_signoff.py`, `scripts/protocol/run_protocol_enforce_window_capture.py`, and `scripts/protocol/check_protocol_enforce_cutover_readiness.py`
45. Canonical `run_start_artifacts` bootstrap evidence remains immutable and session-scoped, and fresh `run_identity.json` payloads now explicitly mark that surface as `identity_scope=session_bootstrap` plus `projection_only=true`; bootstrap reuse plus legacy run-summary builders, finalize helpers, reconstruction, and summary-contract validators now also fail closed if that framing drifts or if `run_identity.run_id` mismatches the enclosing summary `run_id`, and finalize-time bootstrap validation now degrades cleanly instead of aborting closeout while excluding transient invalid bootstrap identity from degraded summary output, so session-bootstrap evidence does not masquerade as invocation-scoped control-plane run authority via `orket/runtime/run_start_artifacts.py`, `orket/runtime/run_summary.py`, and `orket/runtime/execution_pipeline.py`
46. Canonical `retry_classification_policy` now explicitly declares `projection_only=true` with `projection_source=retry_classification_rules` plus `attempt_history_authoritative=false`, run-start contract capture now validates that framing before persisting `retry_classification_policy.json`, the retry-policy checker now normalizes malformed report output into a fail-closed error report before diff-ledger write, rejects report payloads whose embedded snapshot is not itself a valid retry-policy snapshot, falls back to the canonical retry-policy snapshot when malformed producer output omits or drifts that embedded snapshot, and the runtime-truth acceptance gate now validates both the retry-policy report contract and the persisted run-level `retry_classification_policy.json` artifact before trusting top-level `ok`, `signal_count`, or mere file presence while preserving explicit fail-closed error detail from validated retry-policy reports instead of collapsing them into generic false state, making that runtime contract snapshot classification guidance only instead of hidden attempt-history authority via `orket/runtime/retry_classification_policy.py`, `orket/runtime/run_start_contract_artifacts.py`, `scripts/governance/check_retry_classification_policy.py`, and `scripts/governance/run_runtime_truth_acceptance_gate.py`
47. Canonical sandbox lifecycle now publishes first-class shared `ResourceRecord` snapshots on create, create-accepted, active health verification, renew, reacquire, reconciliation, terminal, and cleaned transitions, authenticated sandbox cancel now records a durable operator command carrying the canonical shared sandbox `resource_id` in `affected_resource_refs`, and sandbox operator views now read the latest resource id, kind, current state, and orphan classification from that durable store while also surfacing those latest operator-action affected transition/resource refs via `orket/application/services/sandbox_control_plane_operator_service.py`, `orket/application/services/sandbox_control_plane_resource_service.py`, `orket/application/services/sandbox_runtime_lifecycle_service.py`, `orket/application/services/sandbox_lifecycle_reconciliation_service.py`, `orket/application/services/sandbox_terminal_outcome_service.py`, `orket/application/services/sandbox_runtime_cleanup_service.py`, `orket/application/services/sandbox_lifecycle_view_service.py`, `orket/application/services/control_plane_publication_service.py`, and `orket/adapters/storage/async_control_plane_record_repository.py`
48. Canonical script-side legacy `run_summary.json` consumers now fail closed before trusting malformed projection framing through one shared validated run-summary loader: shared probe/workload helpers, MAR audit completeness and compare surfaces, and training-data extraction all consume that loader and reject summary payloads whose projection-backed blocks drift away from explicit projection semantics via `scripts/common/run_summary_support.py`, `scripts/probes/probe_support.py`, `scripts/audit/audit_support.py`, `scripts/audit/compare_two_runs.py`, and `scripts/training/extract_training_data.py`
49. Canonical governance live-proof recorders for truthful runtime packet-1, packet-2 repair, and artifact provenance now also consume that same shared validated run-summary loader before reading legacy summary blocks during proof recording, and fail closed instead of silently trusting malformed packet or artifact-provenance projection semantics via `scripts/common/run_summary_support.py`, `scripts/governance/record_truthful_runtime_packet1_live_proof.py`, `scripts/governance/record_truthful_runtime_packet2_repair_live_proof.py`, and `scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py`
50. Canonical live truthful-runtime proof readers now also consume that same shared validated run-summary loader before trusting packet-1, packet-2, or artifact-provenance summary blocks during end-to-end verification, and fail closed instead of silently trusting malformed projection semantics via `scripts/common/run_summary_support.py`, `tests/live/run_summary_support.py`, `tests/live/test_truthful_runtime_phase_c_completion_live.py`, `tests/live/test_truthful_runtime_phase_e_completion_live.py`, `tests/live/test_truthful_runtime_packet1_live.py`, `tests/live/test_truthful_runtime_artifact_provenance_live.py`, and `tests/live/test_system_acceptance_pipeline.py`
51. Canonical governance dashboard seed metrics now validate persisted `run_ledger.summary_json` payloads against the authoritative run-summary contract and sanitize persisted `run_ledger.artifact_json` through the shared validated run-ledger projection seam before deriving session-status or degrade signals, so malformed legacy summary or artifact rows register as invalid-payload signals instead of silently shaping fallback/degrade heuristics via `scripts/governance/build_runtime_truth_dashboard_seed.py` and `orket/application/services/run_ledger_summary_projection.py`
52. Canonical API run-detail and session-status read surfaces now validate persisted `run_ledger.summary_json` payloads against the authoritative run-summary contract before exposing summary blocks, and run detail now also sanitizes the nested `run_ledger.summary_json` projection, so malformed legacy summary payloads fail closed to empty summary projections instead of silently shaping API-visible run state via `orket/application/services/run_ledger_summary_projection.py` and `orket/interfaces/api.py`
53. Canonical API run-detail and session-status read surfaces now also sanitize persisted `run_ledger.artifact_json` through the same validated run-ledger projection seam, so malformed legacy artifact payloads fail closed to empty artifact projections instead of leaking raw invalid run-ledger artifact state through API-visible run surfaces via `orket/application/services/run_ledger_summary_projection.py` and `orket/interfaces/api.py`
54. Canonical live-acceptance pattern reporting now validates persisted `live_acceptance_runs.metrics_json` and `live_acceptance_runs.db_summary_json` row payloads before deriving counters or issue-status totals, and records explicit invalid-payload signals instead of silently flattening malformed rows into empty state via `scripts/acceptance/report_live_acceptance_patterns.py`
55. Canonical microservices unlock gating now fails closed when the live-acceptance report is missing or malformed on `run_count`, `session_status_counts`, `pattern_counters`, or `invalid_payload_signals`, or reports any non-zero invalid source-row signals, instead of allowing stale or malformed live-report payloads to produce false-green unlock decisions via `orket/application/services/microservices_acceptance_reports.py` and `scripts/acceptance/check_microservices_unlock.py`
56. Canonical monolith variant matrix summaries now preserve normalized live-acceptance `invalid_payload_signals`, and both monolith readiness plus matrix-stability gates now fail closed when those matrix summary counts are missing, malformed, or non-zero instead of trusting rate-only matrix summaries derived from malformed live-report rows via `scripts/acceptance/run_monolith_variant_matrix.py`, `scripts/acceptance/check_monolith_readiness_gate.py`, and `scripts/acceptance/check_microservices_unlock.py`
57. Canonical architecture pilot matrix comparison now preserves side-specific invalid-payload totals, detailed per-architecture invalid-payload maps, and failures from the underlying pilot summaries, and microservices pilot stability now fails closed when that persisted comparison detail is missing, malformed, non-zero, or internally inconsistent with its own per-architecture invalid-payload maps instead of trusting architecture delta summaries or stored totals alone via `scripts/acceptance/run_architecture_pilot_matrix.py`, `scripts/acceptance/check_microservices_pilot_stability.py`, and `orket/application/services/microservices_acceptance_reports.py`
58. Canonical runtime-policy pilot-stability reads now fail closed on malformed persisted pilot-stability artifacts and require the saved report to match the checkerÃ¢â‚¬â„¢s structural contract instead of trusting a bare `stable` flag via `orket/application/services/runtime_policy.py` and `tests/interfaces/test_api.py`
59. Canonical microservices pilot decision now fails closed on malformed persisted unlock artifacts and requires the saved unlock report to match the checkerÃ¢â‚¬â„¢s structural contract instead of trusting a bare `unlocked` flag via `scripts/acceptance/decide_microservices_pilot.py`
60. Canonical runtime-policy microservices unlock reads now fail closed on malformed persisted unlock artifacts, reuse the same structural unlock-report validator as microservices pilot decision, and default to the canonical acceptance artifact paths instead of stale pre-acceptance output paths via `orket/application/services/microservices_acceptance_reports.py`, `orket/application/services/runtime_policy.py`, and `tests/interfaces/test_api.py`
61. Canonical runtime-policy pilot-stability reads now also fail closed on internally inconsistent persisted pilot-stability artifacts, with the shared acceptance-report validator rejecting drift between `stable`, `failures`, `checks`, and `artifact_count` instead of trusting top-level fields alone via `orket/application/services/microservices_acceptance_reports.py`, `orket/application/services/runtime_policy.py`, `tests/application/test_microservices_acceptance_reports.py`, and `tests/interfaces/test_api.py`
62. Canonical runtime-policy microservices unlock reads and microservices pilot decision now also fail closed on internally inconsistent persisted unlock artifacts, with the shared acceptance-report validator rejecting drift between top-level `unlocked` or `failures` and per-criterion `ok` or `failures` detail instead of trusting top-level unlock state alone via `orket/application/services/microservices_acceptance_reports.py`, `tests/application/test_microservices_acceptance_reports.py`, `tests/application/test_microservices_pilot_decision.py`, and `tests/interfaces/test_api.py`
63. Canonical run-evidence graph operator path: `python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>`
64. Canonical run-evidence graph artifact family: `runs/<session_id>/run_evidence_graph.json`, `runs/<session_id>/run_evidence_graph.mmd`, and `runs/<session_id>/run_evidence_graph.html` emitted by `scripts/observability/emit_run_evidence_graph.py`
65. Canonical run-evidence graph contract spec: `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`

## Machine-Readable Authority Map (v1)

```json
{
  "version": 1,
  "last_updated": "2026-03-30",
  "authority": {
    "dependency_authority": {
      "primary": "pyproject.toml",
      "install_command": "python -m pip install -e \".[dev]\"",
      "sources": [
        "pyproject.toml",
        "docs/CONTRIBUTOR.md",
        "README.md"
      ]
    },
    "install_bootstrap": {
      "commands": [
        "python -m pip install --upgrade pip",
        "python -m pip install -e \".[dev]\""
      ],
      "sources": [
        "docs/CONTRIBUTOR.md",
        "README.md"
      ]
    },
    "runtime_entrypoints": {
      "cli_default": "python main.py",
      "cli_named_card": "python main.py --card <card_id>",
      "cli_named_rock": "python main.py --rock <rock_name>",
      "cli_named_rock_status": "legacy_alias_to_run_card_via_run_rock_wrapper",
      "api": "python server.py",
      "sources": [
        "docs/CONTRIBUTOR.md",
        "README.md"
      ]
    },
    "canonical_test_command": {
      "command": "python -m pytest -q",
      "lane_reference": "docs/TESTING_POLICY.md",
      "sources": [
        "docs/CONTRIBUTOR.md",
        "docs/RUNBOOK.md",
        "docs/TESTING_POLICY.md"
      ]
    },
    "verification_policy": {
      "agent_policy": "AGENTS.md",
      "contributor_policy": "docs/CONTRIBUTOR.md",
      "testing_policy": "docs/TESTING_POLICY.md",
      "pytest_sandbox_default_policy": "tests/conftest.py",
      "sources": [
        "AGENTS.md",
        "docs/CONTRIBUTOR.md",
        "docs/TESTING_POLICY.md",
        "tests/conftest.py"
      ]
    },
    "active_spec_index": {
      "root_docs_index": "docs/README.md",
      "specs_root": "docs/specs/",
      "active_roadmap_source": "docs/ROADMAP.md",
      "process_source": "docs/CONTRIBUTOR.md",
      "core_runtime_contract_sources": [
        "docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md",
        "docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md",
        "docs/specs/RUNTIME_INVARIANTS.md",
        "docs/specs/TOOL_CONTRACT_TEMPLATE.md",
        "docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_REPAIR_LEDGER_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_MEMORY_TRUST_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_CONFORMANCE_GOVERNANCE_CONTRACT.md"
      ],
      "offline_capability_matrix_source": "docs/specs/OFFLINE_CAPABILITY_MATRIX.md",
      "protocol_governed_contract_sources": [
        "docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md",
        "docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md",
        "docs/specs/PROTOCOL_DETERMINISM_CONTROL_SURFACE.md",
        "docs/specs/PROTOCOL_ERROR_CODE_REGISTRY.md",
        "docs/specs/PROTOCOL_REPLAY_CAMPAIGN_SCHEMA.md",
        "docs/specs/PROTOCOL_LEDGER_PARITY_CAMPAIGN_SCHEMA.md"
      ],
      "operating_principles_source": "docs/specs/ORKET_OPERATING_PRINCIPLES.md",
      "determinism_gate_policy_source": "docs/specs/ORKET_DETERMINISM_GATE_POLICY.md",
      "terraform_plan_reviewer_v1_contract_source": "docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md",
      "local_prompting_contract_source": "docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md",
      "run_evidence_graph_contract_source": "docs/specs/RUN_EVIDENCE_GRAPH_V1.md",
      "sources": [
        "docs/README.md",
        "docs/ROADMAP.md",
        "docs/CONTRIBUTOR.md"
      ]
    },
    "canonical_script_output_locations": {
      "staged_artifacts_index": "benchmarks/staging/index.json",
      "staged_artifacts_readme": "benchmarks/staging/README.md",
      "published_artifacts_index": "benchmarks/published/index.json",
      "published_artifacts_readme": "benchmarks/published/README.md",
      "runtime_event_artifact_path": "agent_output/observability/runtime_events.jsonl",
      "run_evidence_graph_operator_path": "python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>",
      "run_evidence_graph_json_path": "runs/<session_id>/run_evidence_graph.json",
      "run_evidence_graph_mermaid_path": "runs/<session_id>/run_evidence_graph.mmd",
      "run_evidence_graph_rendered_path": "runs/<session_id>/run_evidence_graph.html",
      "terraform_plan_review_live_smoke_output_path": ".orket/durable/observability/terraform_plan_review_live_smoke.json",
      "artifact_review_policy": "docs/process/PUBLISHED_ARTIFACTS_POLICY.md",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/CONTRIBUTOR.md",
        "docs/specs/RUN_EVIDENCE_GRAPH_V1.md",
        "docs/architecture/event_taxonomy.md",
        "docs/process/PUBLISHED_ARTIFACTS_POLICY.md",
        "scripts/observability/emit_run_evidence_graph.py",
        "docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md"
      ]
    },
    "control_plane_storage": {
      "default_db_path": ".orket/durable/db/control_plane_records.sqlite3",
      "resolver": "orket/runtime_paths.py::resolve_control_plane_db_path",
      "runtime_consumers": [
        "orket/services/sandbox_orchestrator.py",
        "orket/orchestration/engine.py",
        "orket/application/workflows/orchestrator_ops.py",
        "orket/runtime/execution_pipeline.py",
        "orket/interfaces/coordinator_api.py"
      ],
      "runtime_published_record_families": [
        "resolved_policy_snapshot",
        "resolved_configuration_snapshot",
        "reservation_record",
        "run_record",
        "attempt_record",
        "step_record",
        "effect_journal_entry_record",
        "checkpoint_record",
        "checkpoint_acceptance_record",
        "recovery_decision_record",
        "operator_action_record",
        "final_truth_record",
        "reconciliation_record",
        "lease_record",
        "resource_record"
      ],
      "sources": [
        "CURRENT_AUTHORITY.md",
        "orket/runtime_paths.py",
        "orket/services/sandbox_orchestrator.py",
        "orket/orchestration/engine.py",
        "orket/orchestration/engine_approvals.py",
        "orket/application/workflows/orchestrator_ops.py",
        "orket/application/workflows/turn_executor.py",
        "orket/application/workflows/turn_executor_control_plane.py",
        "orket/application/workflows/turn_executor_control_plane_evidence.py",
        "orket/application/workflows/turn_executor_model_artifacts.py",
        "orket/application/workflows/turn_executor_model_flow.py",
        "orket/application/workflows/tool_invocation_contracts.py",
        "orket/application/workflows/turn_tool_dispatcher.py",
        "orket/application/workflows/turn_tool_dispatcher_control_plane.py",
        "orket/application/workflows/turn_tool_dispatcher_protocol.py",
        "orket/application/workflows/turn_tool_dispatcher_support.py",
        "orket/application/services/cards_epic_control_plane_service.py",
        "orket/application/services/control_plane_publication_service.py",
        "orket/application/services/control_plane_snapshot_publication.py",
        "orket/application/services/coordinator_control_plane_lease_service.py",
        "orket/application/services/coordinator_control_plane_reservation_service.py",
        "orket/application/services/gitea_state_control_plane_checkpoint_service.py",
        "orket/application/services/gitea_state_control_plane_claim_failure_service.py",
        "orket/application/services/gitea_state_control_plane_execution_service.py",
        "orket/application/services/gitea_state_control_plane_lease_service.py",
        "orket/application/services/gitea_state_control_plane_reservation_service.py",
        "orket/application/services/gitea_state_worker.py",
        "orket/application/services/kernel_action_control_plane_failure.py",
        "orket/application/services/kernel_action_control_plane_outcome.py",
        "orket/application/services/kernel_action_control_plane_resource_lifecycle.py",
        "orket/application/services/kernel_action_control_plane_service.py",
        "orket/application/services/kernel_action_control_plane_operator_service.py",
        "orket/application/services/kernel_action_pending_approval_reservation.py",
        "orket/application/services/kernel_action_control_plane_view_service.py",
        "orket/application/services/orchestrator_issue_control_plane_service.py",
        "orket/application/services/orchestrator_issue_control_plane_support.py",
        "orket/application/services/orchestrator_scheduler_control_plane_service.py",
        "orket/application/services/orchestrator_scheduler_control_plane_mutation.py",
        "orket/application/services/pending_gate_control_plane_operator_service.py",
        "orket/application/services/review_run_control_plane_service.py",
        "orket/application/services/sandbox_control_plane_checkpoint_service.py",
        "orket/application/services/sandbox_control_plane_execution_service.py",
        "orket/application/services/sandbox_control_plane_effect_service.py",
        "orket/application/services/sandbox_control_plane_operator_service.py",
        "orket/application/services/sandbox_control_plane_reservation_service.py",
        "orket/application/services/sandbox_control_plane_lease_service.py",
        "orket/application/services/skill_adapter.py",
        "orket/application/services/tool_approval_control_plane_operator_service.py",
        "orket/application/services/tool_approval_control_plane_reservation_service.py",
        "orket/application/services/turn_tool_control_plane_closeout.py",
        "orket/application/services/turn_tool_control_plane_factory.py",
        "orket/application/services/turn_tool_control_plane_resource_lifecycle.py",
        "orket/application/services/turn_tool_control_plane_recovery.py",
        "orket/application/services/turn_tool_control_plane_reconciliation.py",
        "orket/application/services/turn_tool_control_plane_service.py",
        "orket/application/services/turn_tool_control_plane_state_gate.py",
        "orket/application/services/turn_tool_control_plane_support.py",
        "orket/interfaces/api.py",
        "orket/interfaces/routers/sessions.py",
        "orket/interfaces/routers/approvals.py",
        "orket/interfaces/coordinator_api.py",
        "orket/interfaces/routers/kernel.py",
        "orket/kernel/v1/nervous_system_runtime.py",
        "orket/application/review/run_service.py",
        "orket/runtime/execution_pipeline.py",
        "orket/runtime/tool_invocation_policy_contract.py",
        "orket/runtime/protocol_error_codes.py",
        "orket/application/services/sandbox_lifecycle_view_service.py",
        "orket/adapters/storage/async_control_plane_record_repository.py",
        "orket/adapters/storage/async_control_plane_execution_repository.py",
        "orket/core/contracts/control_plane_models.py",
        "orket/core/domain/control_plane_enums.py",
        "docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md"
      ]
    },
    "control_plane_workload_authority": {
      "canonical_catalog": "orket/application/services/control_plane_workload_catalog.py",
      "external_authority_seam": "orket/application/services/control_plane_workload_catalog.py::resolve_control_plane_workload",
      "matrix_gate_doc": "docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md",
      "authority_inputs": [
        "catalog_workload",
        "workload_contract_v1",
        "extension_manifest_workload"
      ],
      "internal_helpers_not_authority": [
        "orket/application/services/control_plane_workload_catalog.py::build_cards_workload_contract"
      ],
      "compatibility_adapters": [
        "orket/runtime/workload_adapters.py"
      ],
      "status": "partial",
      "governance_tests": [
        "tests/application/test_control_plane_workload_authority_governance.py",
        "tests/runtime/test_cards_workload_adapter.py"
      ],
      "note": "Only resolve_control_plane_workload(...) is an externally blessed workload-authority seam. The governed start-path matrix in the Workstream 1 closeout is a closure gate, so governance fails if a non-test module consumes workload authority from the catalog without explicit matrix coverage, if touched catalog-resolved publishers reintroduce local workload_id/workload_version aliases, if non-CLI runtime callsites drift back onto run_epic(...), run_issue(...), or run_rock(...) compatibility wrappers, if public wrappers stop collapsing to run_card(...), or if the canonical run_card(...) dispatcher starts minting workload authority directly instead of routing into internal entrypoints. The canonical public runtime execution surface is run_card(...); run_issue(...), run_epic(...), and run_rock(...) survive only as thin convenience wrappers, with the legacy CLI --rock alias now routing through run_rock(...) as a thin wrapper over run_card(...). Cards, ODR, and extension workload execution now resolve through the catalog seam, the cards, ODR, and extension start paths use catalog-local helper resolution instead of assembling WorkloadAuthorityInput(...) in runtime entrypoints, controller dispatch now checks extension child eligibility through the manager-owned boolean probes has_manifest_entry(...) and uses_sdk_contract(...) instead of resolving private manifest-entry tuples directly, internal rock routing remains routing-only debt through the generic epic-collection path, extension manifest metadata remains private internal metadata under orket/extensions/, and broader runtime start-path workload authority is still not universal.",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "orket/application/services/control_plane_workload_catalog.py",
        "orket/application/services/kernel_action_control_plane_service.py",
        "orket/application/services/review_run_control_plane_service.py",
        "orket/application/services/turn_tool_control_plane_service.py",
        "orket/application/services/orchestrator_issue_control_plane_service.py",
        "orket/application/services/orchestrator_scheduler_control_plane_service.py",
        "orket/application/services/orchestrator_scheduler_control_plane_mutation.py",
        "orket/application/services/gitea_state_control_plane_execution_service.py",
        "orket/runtime/workload_adapters.py",
        "orket/extensions/manager.py",
        "orket/extensions/artifact_provenance.py",
        "orket/runtime/execution_pipeline.py",
        "scripts/odr/run_arbiter.py",
        "tests/application/test_control_plane_workload_authority_governance.py",
        "docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md",
        "docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md"
      ]
    },
    "governed_turn_tool_namespace_policy": {
      "default_namespace_scope": "issue:<issue_id>",
      "policy_enforcer": "orket/application/workflows/turn_tool_dispatcher_support.py::tool_policy_violation",
      "manifest_contract": "orket/application/workflows/tool_invocation_contracts.py::build_tool_invocation_manifest",
      "binding_source": "orket/application/services/skill_adapter.py",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "orket/application/workflows/turn_tool_dispatcher.py",
        "orket/application/workflows/turn_tool_dispatcher_protocol.py",
        "orket/application/workflows/turn_tool_dispatcher_support.py",
        "orket/application/workflows/tool_invocation_contracts.py",
        "orket/application/workflows/turn_executor_control_plane.py",
        "orket/application/services/skill_adapter.py",
        "orket/application/services/turn_tool_control_plane_service.py",
        "orket/runtime/tool_invocation_policy_contract.py",
        "orket/runtime/protocol_error_codes.py"
      ]
    },
    "gitea_state_worker_control_plane_execution": {
      "default_run_shape": "one lease-backed run per claimed card and lease epoch",
      "checkpoint_mode": "pre-effect claimed-card checkpoint with resume_forbidden semantics",
      "claim_reservation_mode": "publish active claim reservation after backend lease acquire, link claimed lease to that reservation, and promote the reservation only after the ready_to_in_progress claim transition succeeds",
      "claim_failure_mode": "pre-effect blocked closeout with failed claim step, reservation invalidation, terminate_run recovery decision, lease_uncertain publication, claim-scope reconciliation record, and reconciliation_closed final truth",
      "execution_service": "orket/application/services/gitea_state_control_plane_execution_service.py",
      "checkpoint_service": "orket/application/services/gitea_state_control_plane_checkpoint_service.py",
      "claim_failure_service": "orket/application/services/gitea_state_control_plane_claim_failure_service.py",
      "worker_runtime": "orket/application/services/gitea_state_worker.py",
      "pipeline_entrypoint": "orket/runtime/execution_pipeline.py::run_gitea_state_loop",
      "published_record_families": [
        "run_record",
        "attempt_record",
        "reservation_record",
        "checkpoint_record",
        "checkpoint_acceptance_record",
        "step_record",
        "effect_journal_entry_record",
        "recovery_decision_record",
        "final_truth_record",
        "lease_record",
        "resource_record"
      ],
      "sources": [
        "CURRENT_AUTHORITY.md",
        "orket/application/services/gitea_state_control_plane_checkpoint_service.py",
        "orket/application/services/gitea_state_control_plane_claim_failure_service.py",
        "orket/application/services/gitea_state_control_plane_execution_service.py",
        "orket/application/services/gitea_state_control_plane_lease_service.py",
        "orket/application/services/gitea_state_control_plane_reservation_service.py",
        "orket/application/services/gitea_state_worker.py",
        "orket/runtime/execution_pipeline.py"
      ]
    },
    "core_release_versioning": {
      "primary": "docs/specs/CORE_RELEASE_VERSIONING_POLICY.md",
      "release_gate_checklist": "docs/specs/CORE_RELEASE_GATE_CHECKLIST.md",
      "release_proof_template": "docs/specs/CORE_RELEASE_PROOF_REPORT.md",
      "release_proof_reports_root": "docs/releases/",
      "release_evidence_root": "benchmarks/results/releases/",
      "automation_workflow": ".gitea/workflows/core-release-policy.yml",
      "automation_script": "scripts/governance/check_core_release_policy.py",
      "release_prep_script": "scripts/governance/prepare_core_release.py",
      "main_commit_tags_required": true,
      "tag_format": "v<major>.<minor>.<patch>",
      "core_version_source": "pyproject.toml",
      "changelog_source": "CHANGELOG.md",
      "workflow_source": "docs/CONTRIBUTOR.md",
      "sdk_versioning_source": "docs/requirements/sdk/VERSIONING.md",
      "sources": [
        "CURRENT_AUTHORITY.md",
        ".gitea/workflows/core-release-policy.yml",
        "scripts/governance/check_core_release_policy.py",
        "scripts/governance/prepare_core_release.py",
        "docs/specs/CORE_RELEASE_VERSIONING_POLICY.md",
        "docs/specs/CORE_RELEASE_GATE_CHECKLIST.md",
        "docs/specs/CORE_RELEASE_PROOF_REPORT.md",
        "docs/CONTRIBUTOR.md",
        "CHANGELOG.md",
        "pyproject.toml"
      ]
    },
    "model_provider_runtime_selection": {
      "primary": "orket/runtime/provider_runtime_target.py",
      "runtime_consumers": [
        "orket/adapters/llm/local_model_provider.py",
        "orket/workloads/model_stream_v1.py"
      ],
      "verification_consumers": [
        "scripts/providers/check_model_provider_preflight.py",
        "scripts/providers/list_real_provider_models.py"
      ],
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/CONTRIBUTOR.md",
        "scripts/README.md"
      ]
    }
  }
}
```

## Drift Rule

If any command, path, or source in this file changes, the corresponding source documents and implementation entrypoints must be updated in the same change unless the user explicitly directs otherwise.
