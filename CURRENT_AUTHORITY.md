# CURRENT_AUTHORITY.md

Last updated: 2026-04-19

This file is the current canonical authority snapshot for high-impact runtime and governance paths.

It is intentionally narrow:
1. Agent behavior rules remain in `AGENTS.md`.
2. Contributor workflow rules remain in `docs/CONTRIBUTOR.md`.
3. This file tracks what is authoritative right now.
4. ControlPlane implementation sequencing and project closeout history remain archived under `docs/projects/archive/ControlPlane/`, while the durable governed workload start-path matrix now lives at `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`; this file should name the live authority seams, not reproduce slice-by-slice closeout detail.

The ControlPlane project closeout completed on 2026-04-09 and is archived at `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/`. Durable ControlPlane contract authority now lives under `docs/specs/` via `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`, the durable governed workload start-path matrix now lives at `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`, and no non-archive `docs/projects/ControlPlane/` folder remains. Future ControlPlane implementation work must reopen explicitly through `docs/ROADMAP.md`.

This file does not define:
1. all supported features,
2. all experimental surfaces,
3. all repository conventions.

It defines only the currently authoritative paths that agents and contributors must treat as canonical unless explicitly directed otherwise.
Legacy CLI `--rock` remains accepted as a hidden compatibility alias to the named card runtime, but it is not part of the canonical runtime path list below.

## Current Canonical Paths

1. Install/bootstrap: `python -m pip install -e ".[dev]"`
2. Default runtime: `python main.py`
3. Named card runtime: `python main.py --card <card_id>`
4. API runtime: `python server.py`
5. Canonical test command: `python -m pytest -q`
6. Active docs index: `docs/README.md`
7. Active roadmap: `docs/ROADMAP.md`
8. Active contributor workflow: `docs/CONTRIBUTOR.md`
9. Long-lived specs root: `docs/specs/`
10. Staged artifact candidate index: `benchmarks/staging/index.json`
11. Published artifact index: `benchmarks/published/index.json`
12. Canonical provider runtime target selection implementation: `orket/runtime/config/provider_runtime_target.py`; `orket/runtime/provider_runtime_target.py` is a one-release compatibility alias.
13. Core release/versioning policy: `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`
14. Core release gate checklist: `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`
15. Core release proof report template: `docs/specs/CORE_RELEASE_PROOF_REPORT.md`
16. Core release proof report storage: `docs/releases/<version>/PROOF_REPORT.md`
17. Core release evidence storage: `benchmarks/results/releases/<version>/`
18. Core release automation workflow: `.gitea/workflows/core-release-policy.yml`
19. Core release automation script: `scripts/governance/check_core_release_policy.py`
20. Core release prep script for release-only worktrees: `scripts/governance/prepare_core_release.py`
21. Canonical core release tag rule: every post-`0.4.0` versioned commit on pushed `main` must carry the matching annotated `v<major>.<minor>.<patch>` tag on that exact commit.
22. Pytest sandbox fail-closed fixture: `tests/conftest.py`
23. Determinism claim/gate policy: `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
24. Canonical runtime event artifact path: `agent_output/observability/runtime_events.jsonl`
25. Terraform plan reviewer durable spec: `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`
26. Terraform plan reviewer live smoke output path: `.orket/durable/observability/terraform_plan_review_live_smoke.json`
27. Canonical external extension package, publish, and validation authority now live in `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`, `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md`, and `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`; Packet 1 admits one external extension repo rooted at `pyproject.toml`, one manifest at the extension root, `src/`, `tests/`, and `scripts/`, keeps `project.version` aligned with manifest `extension_version`, requires explicit SDK bootstrap through `ORKET_SDK_INSTALL_SPEC`, requires the host CLI `orket` or an explicit `ORKET_HOST_INSTALL_SPEC`, keeps the canonical host-validation path fixed at `orket ext validate <extension_root> --strict --json`, scopes host import scanning to `src/` when that tree exists, admits only `manifest_version: v0`, preserves manifest-declared `config_sections`, preserves manifest-declared `allowed_stdlib_modules`, makes SDK workload loading and subprocess execution reject undeclared standard-library imports while the existing internal Orket import block remains active, keeps legacy workload stdlib allowlist enforcement compatibility-scoped to manifests that declare a non-empty list, now hardens one authoritative published artifact family as the source distribution `dist/<normalized_project_name>-<version>.tar.gz`, uses `v<extension_version>` as the canonical release tag, requires the authoritative source distribution to preserve the root manifest plus `src/`, `tests/`, and `scripts/`, uses `./scripts/build-release.sh` / `./scripts/build-release.ps1` plus `./scripts/verify-release.sh v<extension_version>` / `./scripts/verify-release.ps1 v<extension_version>` as the canonical maintainer build-and-verify path, uses `.gitea/workflows/release.yml` as the canonical tagged automation path that preserves the source distribution artifact, and requires operator intake to extract that tagged source distribution and return to `orket ext validate <extracted_root> --strict --json`; publish or validation success remains admissibility evidence only and does not grant runtime authority
28. Canonical control-plane durable store path: `.orket/durable/db/control_plane_records.sqlite3` via `orket/runtime_paths.py`; the same store now durably persists first-class `ResolvedPolicySnapshot` and `ResolvedConfigurationSnapshot` objects for top-level cards epic invocation admission, manual review-run admission, sandbox execution initialization, governed kernel-action admission, governed turn-tool admission, default orchestrator issue dispatch admission, scheduler-owned namespace mutation admission, and Gitea state-worker claimed-run admission via `orket/application/services/control_plane_snapshot_publication.py`, `orket/application/services/cards_epic_control_plane_service.py`, `orket/application/services/review_run_control_plane_service.py`, `orket/application/review/run_service.py`, `orket/application/services/sandbox_control_plane_execution_service.py`, `orket/application/services/kernel_action_control_plane_service.py`, `orket/application/services/turn_tool_control_plane_service.py`, `orket/application/services/orchestrator_issue_control_plane_service.py`, `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`, and `orket/application/services/gitea_state_control_plane_execution_service.py`; manual review deterministic-decision and model-assisted-critique artifacts now also mark `execution_state_authority=control_plane_records`, `lane_output_execution_state_authoritative=false`, and carry canonical review-run `control_plane_run_id`/`control_plane_attempt_id`/`control_plane_step_id` refs when that durable publication exists, so lane JSON no longer looks like standalone execution-state authority, and review replay, answer-key scoring, and consistency extraction now consume shared validated review-bundle payload or artifact loaders, including truncation-bounds snapshot inputs, instead of validating bundle markers and then rereading snapshot or lane JSON ad hoc
28. Canonical governed turn-tool path defaults to `issue:<issue_id>` namespace scope and must fail closed on broader scope declarations, now publishes a first-class namespace `ReservationRecord` on governed admission, explicitly promotes that reservation to an active `LeaseRecord` on execution start with fail-closed activation rollback that invalidates unpromoted reservation truth and releases any just-published active execution lease when promotion fails, mirrors that namespace authority through shared `ResourceRecord` snapshots on activation, closeout release, and activation rollback, and now fails closed when existing executing or completed governed runs try to continue or reuse success while the latest namespace `ResourceRecord` no longer agrees with the active or completed lease authority, carries those reservation/lease refs as checkpoint-acceptance dependencies on the pre-effect `resume_same_attempt` checkpoint boundary for each new governed attempt, now also records the canonical governed run, attempt, step, reservation, lease, and namespace-resource ids directly inside governed turn-tool protocol receipt invocation manifests when that durable authority exists, protocol run-graph reconstruction now preserves those canonical control-plane refs on reconstructed governed tool-call nodes when manifest evidence exists, receipt-derived artifact provenance entries plus packet-1 provenance, packet-2 source-attribution, narration/effect-audit, and idempotency summaries now preserve canonical governed run, attempt, and step ids when authoritative receipt-manifest provenance exists for the generated artifact or narrated effect, those legacy run-summary packet-1, packet-2, and artifact-provenance blocks now also self-identify as `projection_only` with explicit fact-backed `projection_source` markers and fail closed if that framing drifts instead of reading like native effect authority, and legacy protocol receipt materialization into run-ledger `tool_call` / `operation_result` rows now marks those rows `projection_only` with explicit `observability.protocol_receipts.log` source plus projected effect-journal refs for governed turn-tool results instead of letting receipt replay look like native effect authority, publishes terminal `terminate_run` recovery decisions for pre-effect blocked and post-effect failed governed execution with checkpoint or effect preconditions and blocked continuation actions, makes preflight terminal closeout fail closed by materializing an initial attempt when missing, abandoning any existing non-terminal current attempt with explicit `pre_effect_failure` taxonomy plus terminal recovery-decision authority before run terminal state publication, and releasing promoted execution authority when that closeout occurs after execution start, and on `resume_mode` now performs supervisor-owned checkpoint-backed same-attempt recovery for unfinished pre-effect runs on the current attempt; that safe pre-effect path consumes the accepted checkpoint snapshot before prompt or model work and continues on the current attempt instead of bootstrapping attempt 2, fails closed if immutable checkpoint snapshot identity drifts from the current run or namespace request, closes immediately into reconciliation-closed terminal truth if durable operation artifacts already exist without matching step/effect authority, while the recovery and replay helpers still consume older `resume_new_attempt_from_checkpoint` governed lineage truthfully when those records already exist, unfinished post-effect or effect-boundary-uncertain attempts still publish explicit reconciliation records plus `require_reconciliation_then_decide` recovery authority and then close immediately into terminal `reconciliation_closed` truth with a second reconciliation-rationalized `terminate_run` decision, and already-dirty same-attempt or replacement-attempt resumes now fail closed before model invocation instead of being treated as clean retries; completed successful governed turn re-entry still requires accepted checkpoint authority, an immutable checkpoint snapshot artifact, matching snapshot identity, aligned durable step plus effect plus operation truth, no unexpected operation artifacts, and matching durable namespace resource-versus-lease authority before reusing artifacts ahead of prompt or model execution and ahead of checkpoint artifact rewrite rather than rerunning the model and only reusing finalized truth later, and governed runs already in terminal or recovery-blocked states now fail closed before model invocation and before checkpoint artifact rewrite instead of drifting into new tool execution via `orket/application/workflows/turn_tool_dispatcher_support.py`, `orket/runtime/registry/tool_invocation_contracts.py`, `orket/application/workflows/turn_tool_dispatcher_protocol.py`, `orket/application/workflows/turn_executor_control_plane_evidence.py`, `orket/application/workflows/turn_executor_completed_replay.py`, `orket/application/workflows/turn_executor_resume_replay.py`, `orket/application/workflows/turn_executor_model_flow.py`, `orket/application/workflows/turn_executor_model_artifacts.py`, `orket/application/workflows/turn_executor_control_plane.py`, `orket/application/services/turn_tool_control_plane_service.py`, `orket/application/services/turn_tool_control_plane_state_gate.py`, `orket/application/services/turn_tool_control_plane_resource_lifecycle.py`, `orket/application/services/control_plane_resource_authority_checks.py`, `orket/application/services/turn_tool_control_plane_recovery.py`, `orket/application/services/turn_tool_control_plane_reconciliation.py`, `orket/application/services/turn_tool_control_plane_closeout.py`, `orket/runtime/execution_pipeline.py`, `orket/runtime/phase_c_runtime_truth.py`, `orket/runtime/protocol_receipt_materializer.py`, `orket/runtime/run_graph_reconstruction.py`, `orket/runtime/run_summary.py`, `orket/runtime/run_summary_artifact_provenance.py`, and `orket/runtime/run_summary_packet2.py`
29. Canonical Gitea state worker path now publishes one lease-backed control-plane run per claimed card and lease epoch, a durable resolved policy snapshot plus resolved configuration snapshot for that claimed-run admission, a first-class claim reservation before the initial claim mutation, explicit reservation-to-lease linkage on the claimed lease, promotion of that reservation only after the `ready -> in_progress` claim transition succeeds with fail-closed promotion rollback that invalidates unpromoted reservation truth and releases just-published active lease authority when promotion fails, shared `ResourceRecord` history on claim, renew, expiry, release, claim-failure uncertainty, and promotion rollback, now fails closed before backend renew when the latest shared active resource snapshot no longer agrees with the active lease authority, re-publishes terminal expiry/release lease authority when the latest shared resource snapshot drifted away from already-terminal lease truth instead of silently trusting lease-only terminal history, a pre-effect `resume_forbidden` checkpoint from the claimed-card observation, worker-owned claim/finalize steps, effect-journal entries for observed state transitions, terminal recovery decisions on failure including blocked closeout for active control-plane resource drift, and pre-effect claim-failure closeout with reservation invalidation, `lease_uncertain`, a reconciliation record, and reconciliation-closed final truth when the initial claim transition fails via `orket/application/services/gitea_state_control_plane_execution_service.py`, `orket/application/services/gitea_state_control_plane_checkpoint_service.py`, `orket/application/services/gitea_state_control_plane_claim_failure_service.py`, `orket/application/services/gitea_state_control_plane_lease_service.py`, `orket/application/services/gitea_state_control_plane_reservation_service.py`, `orket/application/services/gitea_state_worker.py`, and `orket/application/services/control_plane_resource_authority_checks.py`
30. Canonical approval-gated admission paths now publish a first-class `operator_hold_reservation` on request creation or admission, resolve that reservation on approval decision, and publish first-class guard-review operator commands on the pending-gate surface for supported non-tool resolutions; the active SupervisorRuntime approval-checkpoint contract now admits three shipped bounded approve-to-continue slices only: governed kernel `NEEDS_APPROVAL` on the default `session:<session_id>` namespace scope, plus governed turn-tool `write_file` and `create_issue` approval-required continuation on the default `issue:<issue_id>` namespace scope using the existing `tool_approval` plus `approval_required_tool:<tool_name>` request shape and the already-selected `control_plane_target_ref`. Packet 1 still admits `approve` and `deny` only, while optional `notes` and `edited_proposal` payload members remain bounded operator metadata and do not create a general resume authority. Governed kernel `NEEDS_APPROVAL` admit now publishes that approval-hold reservation from the async orchestration-engine path before response shaping instead of leaving that reservation seam router-local, while the bounded turn-tool `write_file` and `create_issue` slices now fail-close on target or namespace drift, keep checkpoint authority runtime-owned, use the accepted pre-effect same-attempt checkpoint to continue the same governed turn-tool run on approval, and terminal-stop that same governed turn-tool run on denial without widening into a broader approval-required tool family or a manual resume API. Approval list and detail views continue to surface the latest reservation and approval-surface operator-command summary, plus `control_plane_target_ref`, the latest target-side run and attempt summary when durable execution truth exists including namespace scope, admission decision receipt, policy snapshot id, configuration snapshot id, creation timestamp, and attempt count, the latest target-side resource summary for supported governed target runs now including default orchestrator issue-dispatch runs plus scheduler-owned namespace mutation and child-workload composition runs alongside governed turn-tool and kernel-action runs, the latest target-side step summary including namespace scope, capability used, output ref, resources touched, and receipt refs, the latest target-side checkpoint summary including creation timestamp, invalidation and dependency detail, policy digest, integrity verification ref, required reobservation class, acceptance decision timestamp, acceptance supervisor authority, evaluated policy digest, dependent effect or reservation or lease refs, and rejection reasons, the latest target-side effect-journal summary including step id, publication sequence, intended target, observed result ref, authorization-basis ref, publication timestamp, integrity verification ref, prior-entry linkage, contradiction or supersession refs, entry digest, and uncertainty, the latest target-side operator action summary including `input_class`, `command_class`, `risk_acceptance_scope`, `attestation_scope`, `attestation_payload`, `precondition_basis_ref`, receipt refs, affected transition refs, and affected resource refs, approval-resolution operator actions for supported governed turn-tool, kernel-action, orchestrator issue-dispatch, and scheduler-owned namespace mutation/child-workload targets now also carrying the canonical shared target `resource_id` in those `affected_resource_refs` when durable execution truth exists, the latest target-side reservation summary including reservation kind, reservation invalidation basis, supervisor authority, and promotion linkage, and the latest target-side final-truth summary including fuller classifications, authoritative result ref, and authority sources when the approval payload names a governed target or when authoritative approval-reservation truth names that governed target on the kernel approval path; that Packet 1 operator inspection surface now also fails closed on unsupported legacy approval lifecycle statuses and on payload-versus-reservation or operator-action projection drift instead of normalizing contradictory approval truth via `orket/application/services/tool_approval_control_plane_reservation_service.py`, `orket/application/services/kernel_action_pending_approval_reservation.py`, `orket/application/services/tool_approval_control_plane_operator_service.py`, `orket/application/services/control_plane_target_resource_refs.py`, `orket/application/services/pending_gate_control_plane_operator_service.py`, `orket/application/services/governed_turn_tool_approval_continuation_service.py`, `orket/application/workflows/orchestrator_ops.py`, `orket/interfaces/routers/kernel.py`, `orket/interfaces/routers/approvals.py`, `orket/orchestration/engine.py`, `orket/orchestration/engine_approvals.py`, `orket/orchestration/approval_control_plane_read_model.py`, and `orket/application/workflows/orchestrator.py`
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
45. Canonical `run_start_artifacts` bootstrap evidence remains immutable and session-scoped, and fresh `run_identity.json` payloads now explicitly mark that surface as `identity_scope=session_bootstrap`, `projection_source=session_bootstrap_artifacts`, and `projection_only=true`; bootstrap reuse plus legacy run-summary builders, finalize helpers, reconstruction, and summary-contract validators now also fail closed if that framing drifts or if `run_identity.run_id` mismatches the enclosing summary `run_id`, and finalize-time bootstrap validation now degrades cleanly instead of aborting closeout while excluding transient invalid bootstrap identity from degraded summary output, so session-bootstrap evidence does not masquerade as invocation-scoped control-plane run authority via `orket/runtime/run_start_artifacts.py`, `orket/runtime/run_summary.py`, and `orket/runtime/execution_pipeline.py`
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
65. Canonical Prompt Reforger Phase 0 generic service authority now lives in `docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md`, `orket/reforger/service_contracts.py`, `orket/reforger/proof_slices.py`, and `orket/reforger/service.py`; the frozen structural proof artifacts for the bounded LocalClaw-style textmystery slice now live at `benchmarks/staging/General/reforger_service_run_phase0-baseline-run-0001.json`, `benchmarks/staging/General/reforger_service_run_phase0-baseline-run-0001_scoreboard.json`, `benchmarks/staging/General/reforger_service_run_phase0-adapt-run-0007.json`, and `benchmarks/staging/General/reforger_service_run_phase0-adapt-run-0007_scoreboard.json`, and both service-run artifacts explicitly record `proof_type=structural` with blocked live-runtime bookkeeping instead of claiming live-proof success
66. Canonical Prompt Reforger Gemma tool-use lane authority now lives in `docs/projects/PromptReforgerToolCompatibility/PROMPT_REFORGER_GEMMA_TOOL_USE_IMPLEMENTATION_PLAN.md`, `docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json`, `docs/projects/PromptReforgerToolCompatibility/FUNCTIONGEMMA_TOOL_CALL_JUDGE_PROTOCOL.md`, `scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_inventory.py`, `scripts/prompt_lab/run_functiongemma_tool_call_judge.py`, `scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_cycle.py`, and `scripts/prompt_lab/run_prompt_reforger_guide_model_comparison.py`; the live checkpoint artifacts now live at `benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json`, `benchmarks/staging/General/prompt_reforger_gemma_tool_use_judge.json`, `benchmarks/staging/General/prompt_reforger_gemma_tool_use_cycle.json`, and `benchmarks/staging/General/prompt_reforger_guide_model_comparison.json`, the judge path now runs through the admitted `emit_judgment` native-tool contract with truthful LM Studio fallback when Ollama `functiongemma:latest` stays all-inconclusive, the new guide-model comparison surface keeps the Gemma target lane fixed and ranks guide models from generated prompt-candidate scoreboards rather than outer challenge pass/fail, and the lane is currently paused only because `gemma-3-4b-it-qat` did not clear the frozen portability corpus
65. Canonical run-evidence graph contract spec: `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`; admitted view tokens are `full_lineage`, `failure_path`, `authority`, `decision`, `resource_authority_path`, and `closure_path`, while the default operator emission without `--view` remains `full_lineage`, `failure_path`, `resource_authority_path`, and `closure_path`
66. Canonical host-owned session continuity boundary keeps `session_id` as the continuity identifier across `POST /v1/interactions/sessions`, `POST /v1/interactions/{session_id}/turns`, `GET /v1/sessions/{session_id}`, `GET /v1/sessions/{session_id}/status`, `GET /v1/sessions/{session_id}/replay`, and `GET /v1/sessions/{session_id}/snapshot`; the admitted interaction-session path now uses one canonical inspection-only Packet 1 session-context envelope `context_version=packet1_session_context_v1` with ordered provider lineage of host continuity, host-validated turn request, and host-resolved extension-manifest `required_capabilities` metadata when present, and `GET /v1/sessions/{session_id}/snapshot` now exposes that latest session-context lineage while `GET /v1/sessions/{session_id}/replay` without targeted selectors now returns the interaction-turn timeline view; bounded Packet 1 context-provider inputs remain limited to `session_params`, `input_config`, `turn_params`, `workload_id`, `department`, `workspace`, and host-resolved extension-manifest `required_capabilities` on extension turn paths; targeted replay with `issue_id` plus `turn_index` remains run-session-only and fails closed on interaction sessions; authenticated `POST /v1/sessions/{session_id}/halt` and `POST /v1/interactions/{session_id}/cancel` remain the only admitted cleanup-adjacent operator commands on this lane and do not imply deletion or workspace cleanup; protocol replay, replay-compare, replay-campaign, ledger-parity, and ledger-parity-campaign surfaces under `orket/interfaces/routers/sessions.py` remain inspection-only reconstruction or comparison views and fail closed on workspace-containment drift via `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`, `orket/interfaces/routers/sessions.py`, `orket/interfaces/api.py`, `orket/streaming/manager.py`, `orket/streaming/session_context.py`, `tests/interfaces/test_api_interactions.py`, `tests/interfaces/test_sessions_router_protocol_replay.py`, `tests/streaming/test_manager.py`, and `tests/interfaces/test_api.py`
67. Canonical Companion boundary is now BFF-owned: Companion product routes live only in the external Companion gateway under `/api/*`, Orket core no longer mounts Companion-named host routes, and the gateway reaches the host only through `/v1/extensions/{extension_id}/runtime/*` using the same `ORKET_API_KEY` posture as other core routes via `docs/specs/COMPANION_UI_MVP_CONTRACT.md`, `docs/API_FRONTEND_CONTRACT.md`, `orket/interfaces/routers/extension_runtime.py`, and `docs/templates/external_extension/src/companion_app/server.py`
68. Canonical governed local-model tool-turn prompt shape now compacts at source in `orket/application/workflows/turn_message_builder.py` through shared `orket/runtime/compact_turn_packet.py`, producing one minimal model-facing `system` prompt plus one bounded `TURN PACKET` `user` prompt and eliminating the old stacked block labels such as `Execution Context JSON`, `Artifact Contract JSON`, `Artifact Semantic Contract`, `Scenario Truth Contract`, `Turn Success Contract`, `Write Path Contract`, `Read Path Contract`, `Hallucination Verification Scope`, `Guard Decision Contract`, `Guard Rejection Contract`, and `Protocol Response Contract`; the LM Studio Gemma 4 OpenAI-compatible lane preserves the native `system` role, reuses that shared compact packet, collapses any remaining adjacent governed `user` prompt blocks into one merged `user` turn only as a safety net if upstream legacy messages still arrive, records outbound request-shape telemetry as `openai_request_message_count`, `openai_request_role_sequence`, and `openai_request_role_counts` in model raw artifacts, records compacted-packet telemetry through `local_prompting_warnings`, keeps bounded native declared-path `read_file` and `write_file` schemas on admitted turns with `reasoning_effort=none`, falls back guard/native declared-path `read_file` exposure from explicit turn requirements to artifact-contract review or required read surfaces plus verification-scope active or provided context when those explicit lists are empty, applies a tighter deterministic effective context cap on Gemma multi-write tool turns, and treats recorded provider telemetry `openai_native_tool_names` as the authoritative native-tool allowlist for parser-side undeclared or exact-duplicate call filtering before execution via `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`, `docs/architecture/CONTRACT_DELTA_GEMMA_OPENAI_MESSAGE_SHAPE_2026-04-03.md`, `docs/architecture/CONTRACT_DELTA_GEMMA_OPENAI_TOOL_TURN_CONFORMANCE_2026-04-03.md`, `docs/architecture/CONTRACT_DELTA_GEMMA_OPENAI_COMPACT_TURN_PACKET_2026-04-04.md`, `orket/application/workflows/turn_message_builder.py`, `orket/runtime/compact_turn_packet.py`, `orket/adapters/llm/local_prompting_policy.py`, `orket/adapters/llm/local_model_provider.py`, `orket/adapters/llm/openai_native_tools.py`, and `orket/application/workflows/turn_response_parser.py`
69. Canonical local-model coding challenge benchmark harness path is `python scripts/benchmarks/run_local_model_coding_challenge.py --provider <provider> --model <model_id> --epic challenge_workflow_runtime`, and its stable staged report path is `benchmarks/staging/General/local_model_coding_challenge_report.json`; reruns append `diff_ledger` history instead of creating timestamp-only report files
70. Canonical ProductFlow governed `write_file` proof authority now lives in `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md` and `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`; the canonical commands are `ORKET_DISABLE_SANDBOX=1 python scripts/productflow/run_governed_write_file_flow.py`, `python scripts/productflow/build_operator_review_package.py --run-id <run_id>`, and `python scripts/productflow/run_replay_review.py --run-id <run_id>`, the stable proof artifact family lives at `benchmarks/results/productflow/governed_write_file_live_run.json`, `runs/<session_id>/productflow_review_index.json`, `benchmarks/results/productflow/operator_review_proof.json`, and `benchmarks/results/productflow/replay_review.json`, ProductFlow `run_id` resolution now fails closed unless exactly one approval row carries `control_plane_target_ref == <run_id>` for the bounded `approval_required_tool:write_file` seam and the matching `runs/<session_id>/run_summary.json` validates, operator review proof is expected to succeed on that same governed run, and replay review is expected to report a same-run truthful blocker with `replay_ready=false`, `stability_status=not_evaluable`, and explicit `missing_evidence` rather than a stable replay claim via `scripts/productflow/run_governed_write_file_flow.py`, `scripts/productflow/build_operator_review_package.py`, `scripts/productflow/run_replay_review.py`, `scripts/productflow/productflow_support.py`, `scripts/observability/emit_run_evidence_graph.py`, `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`, and `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`
71. Canonical Trusted Run Witness v1 proof authority now lives in `docs/specs/TRUSTED_RUN_WITNESS_V1.md`, `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`, `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`, `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`, `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`, `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, `docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md`, `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`, `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`, and `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md`; admitted compare scopes are ProductFlow governed `write_file` as `trusted_run_productflow_write_file_v1`, the First Useful Workflow Slice as `trusted_repo_config_change_v1`, and Terraform plan decision as `trusted_terraform_plan_decision_v1`, all using operator surface `trusted_run_witness_report.v1`, invariant model surface `trusted_run_invariant_model.v1`, substrate model surface `control_plane_witness_substrate.v1`, witness bundle schema `trusted_run.witness_bundle.v1`, canonical offline claim command `python scripts/proof/verify_offline_trusted_run_claim.py --input <evidence_path>`, and canonical proof-foundation command `python scripts/proof/verify_trusted_run_proof_foundation.py`; ProductFlow keeps canonical campaign output `benchmarks/results/proof/trusted_run_witness_verification.json`, offline output `benchmarks/results/proof/offline_trusted_run_verifier.json`, and proof-foundation output `benchmarks/results/proof/trusted_run_proof_foundation.json`; the useful workflow slice uses `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py`, `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py`, live output `benchmarks/results/proof/trusted_repo_change_live_run.json`, validator output `benchmarks/results/proof/trusted_repo_change_validator.json`, campaign output `benchmarks/results/proof/trusted_repo_change_witness_verification.json`, offline output `benchmarks/results/proof/trusted_repo_change_offline_verifier.json`, witness bundle root `workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json`, governed packet command `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_governed_repo_change_packet.py`, governed packet verifier command `python scripts/proof/verify_governed_change_packet.py --input benchmarks/results/proof/governed_repo_change_packet.json --output benchmarks/results/proof/governed_repo_change_packet_verifier.json`, trusted-kernel model command `python scripts/proof/verify_governed_change_packet_trusted_kernel.py --output benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json`, governed packet output `benchmarks/results/proof/governed_repo_change_packet.json`, governed packet verifier output `benchmarks/results/proof/governed_repo_change_packet_verifier.json`, trusted-kernel model output `benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json`, and staged adversarial benchmark candidate `benchmarks/staging/General/governed_repo_change_packet_adversarial_benchmark_2026-04-19.json`; the Terraform plan decision slice uses `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision.py`, `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py`, provider-backed governed proof command `python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json`, no-spend live setup preflight `python scripts/proof/check_trusted_terraform_live_setup_preflight.py`, publication readiness gate `python scripts/proof/check_trusted_terraform_publication_readiness.py`, publication gate sequence `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py`, live output `benchmarks/results/proof/trusted_terraform_plan_decision_live_run.json`, provider-backed governed proof output `benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json`, live setup preflight output `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_preflight.json`, publication readiness output `benchmarks/results/proof/trusted_terraform_plan_decision_publication_readiness.json`, publication gate output `benchmarks/results/proof/trusted_terraform_plan_decision_publication_gate.json`, validator output `benchmarks/results/proof/trusted_terraform_plan_decision_validator.json`, campaign output `benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json`, offline output `benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json`, and witness bundle root `workspace/trusted_terraform_plan_decision/runs/<session_id>/trusted_run_witness_bundle.json`; `TRI-INV-031` and all admitted witness verifier surfaces now derive `side_effect_free_verification` from the structural proof-foundation artifact rather than from an asserted constant; `trusted_terraform_plan_decision_v1` is now admitted internally under `docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md` and `docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md`, but it is not yet externally publishable and not yet part of the current public trust slice because successful provider-backed governed-proof evidence is not yet admitted public evidence and the publication readiness/gate commands must fail closed until that evidence exists; a single bundle remains `non_deterministic_lab_only`, while a campaign may claim `verdict_deterministic` only when at least two equivalent runs verify with stable contract-verdict signature, stable invariant-model signature, stable substrate signature, stable must-catch outcomes, and for `trusted_repo_config_change_v1` plus `trusted_terraform_plan_decision_v1` a stable validator signature; public proof-backed trust wording remains governed by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`, currently applies only to `trusted_repo_config_change_v1`, must stop at `verdict_deterministic`, and must explicitly say replay and text determinism are not yet proven and that the slice is proof-only and fixture-bounded; the offline verifier may only preserve or downgrade claims from existing evidence via `scripts/proof/trusted_run_witness_contract.py`, `scripts/proof/trusted_run_invariant_model.py`, `scripts/proof/control_plane_witness_substrate.py`, `scripts/proof/offline_trusted_run_verifier.py`, `scripts/proof/trusted_run_proof_foundation.py`, `scripts/proof/trusted_run_non_interference.py`, `scripts/proof/trusted_run_witness_support.py`, `scripts/proof/trusted_scope_family_support.py`, `scripts/proof/trusted_scope_family_claims.py`, `scripts/proof/trusted_scope_family_common.py`, `scripts/proof/trusted_repo_change_contract.py`, `scripts/proof/trusted_repo_change_verifier.py`, `scripts/proof/trusted_repo_change_workflow.py`, `scripts/proof/trusted_repo_change_offline.py`, `scripts/proof/governed_change_packet_contract.py`, `scripts/proof/governed_change_packet_trusted_kernel.py`, `scripts/proof/governed_change_packet_workflow.py`, `scripts/proof/governed_change_packet_verifier.py`, `scripts/proof/run_governed_repo_change_packet.py`, `scripts/proof/verify_governed_change_packet.py`, `scripts/proof/verify_governed_change_packet_trusted_kernel.py`, `scripts/proof/run_governed_change_packet_adversarial_benchmark.py`, `scripts/proof/trusted_terraform_plan_decision_contract.py`, `scripts/proof/trusted_terraform_plan_decision_verifier.py`, `scripts/proof/trusted_terraform_plan_decision_workflow.py`, `scripts/proof/trusted_terraform_plan_decision_bundle_support.py`, `scripts/proof/trusted_terraform_plan_decision_offline.py`, `scripts/proof/terraform_plan_review_live_support.py`, `scripts/proof/build_trusted_run_witness_bundle.py`, `scripts/proof/verify_trusted_run_witness_bundle.py`, `scripts/proof/verify_offline_trusted_run_claim.py`, `scripts/proof/verify_trusted_run_proof_foundation.py`, `scripts/proof/run_trusted_run_witness_campaign.py`, `scripts/proof/run_trusted_repo_change.py`, `scripts/proof/run_trusted_repo_change_campaign.py`, `scripts/proof/run_trusted_terraform_plan_decision.py`, `scripts/proof/run_trusted_terraform_plan_decision_campaign.py`, `scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py`, `scripts/proof/check_trusted_terraform_live_setup_preflight.py`, `scripts/proof/check_trusted_terraform_publication_readiness.py`, and `scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py`
Trusted Terraform live setup packet addition: `python scripts/proof/prepare_trusted_terraform_live_setup_packet.py` is the canonical no-spend setup packet generator for the provider-backed governed-proof attempt. It writes `benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_packet.json` and local ignored packet files under `workspace/trusted_terraform_live_setup/`, executes zero provider calls, writes no credential values, defaults the advisory summary model id to the portable Nova inference-profile id `us.amazon.nova-lite-v1:0`, and does not constitute publication evidence.
Trusted Terraform Bedrock summary-model admission: `scripts/proof/terraform_plan_review_live_support.py` now admits direct `anthropic.*` model ids plus Anthropic inference-profile ids (`us.anthropic.*`, `global.anthropic.*`, or matching inference-profile ARNs) through Bedrock `InvokeModel`, and direct `amazon.nova-*` model ids plus Nova inference-profile ids (`us.amazon.nova-*`, `global.amazon.nova-*`, or matching inference-profile ARNs) through Bedrock `Converse` for the bounded advisory summary seam; no-spend preflight and setup-packet readiness must fail closed on unsupported model ids before provider calls are attempted.

72. Canonical API runtime ownership now lives on the FastAPI app-scoped context `app.state.api_runtime_context` in `orket/interfaces/api.py` with the context contract defined in `orket/interfaces/api_runtime_context.py`; `create_api_app()` replaces that app-scoped context for the active project root, while module-level `engine`, `api_runtime_host`, `stream_bus`, `interaction_manager`, `extension_manager`, and `extension_runtime_service` remain minimal compatibility aliases that mirror or are adopted into that context and are not the authoritative owner, and the env-sensitive `StreamBus` plus `InteractionManager` remain lazy so request-time runtime flags still control their live behavior truthfully
73. Canonical engine control-plane composition now builds through `orket/orchestration/engine_services.py::build_engine_control_plane_services(...)`, async kernel control-plane publication and response augmentation now live in `orket/orchestration/engine_kernel_async_service.py::KernelAsyncControlPlaneService`, the default orchestrator issue-dispatch lifecycle truth remains owned by `orket/application/services/orchestrator_issue_control_plane_service.py` rather than `orket/orchestration/engine.py`, and engine-targeted replay is now explicitly diagnostics-only through `OrchestrationEngine.replay_turn_diagnostics(...)` while `replay_turn(...)` remains only as a compatibility wrapper over the same artifact-backed diagnostics surface; the touched API and CLI replay entrypoints now call `replay_turn_diagnostics(...)` explicitly
74. Canonical runtime-verification support artifacts now use `agent_output/verification/runtime_verification.json` as the latest support-only verifier record, `agent_output/verification/runtime_verification_index.json` as the stable history index, and `agent_output/verification/runtime_verifier_records/<run_id>/<issue_id>/turn_<turn_index>_retry_<retry_count>.json` as the preserved per-record family; those artifacts must record `artifact_role=support_verification_evidence`, `artifact_authority=support_only`, `authored_output=false`, `overall_evidence_class`, and `evidence_summary` over `syntax_only`, `command_execution`, `behavioral_verification`, and `not_evaluated` together with run, issue, turn, and retry provenance, and runtime-summary or MAR paths must not promote the verifier artifact to the primary authored output by default
75. Canonical Tool Execution Gate authority now lives in `docs/specs/TOOL_EXECUTION_GATE_V1.md`; the shipped first slice closes the supported `run_card(...) -> TurnExecutor -> ToolDispatcher` path plus normalized extension actions that re-enter `run_card(...)`, requires construction-time `tool_gate` authority on that supported path, keeps direct `ToolDispatcher.execute_tools(...)`, direct `ToolBox.execute(...)`, and direct card-family method invocation inventory-only internal seams, keeps direct `Agent.run(...)` as retained legacy compatibility that now fail-closes before any direct tool call when `tool_gate` authority is missing, keeps SDK capability registry invocation out of scope under `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`, and fixes the canonical audit command and stable output path at `python scripts/security/build_tool_gate_audit.py --strict` and `benchmarks/results/security/tool_gate_audit.json`
76. Canonical Card Viewer/Runner operator surface now lives in `docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md`; the first truthful operator slice reads through `GET /v1/cards/view`, `GET /v1/cards/{card_id}/view`, `GET /v1/runs/view`, `GET /v1/runs/{session_id}/view`, `GET /v1/system/provider-status`, and `GET /v1/system/health-view`, uses `POST /v1/system/run-active` as the canonical run/rerun action, admits lifecycle categories `prebuild_blocked`, `artifact_run_failed`, `artifact_run_completed_unverified`, `artifact_run_verified`, and `degraded_completed`, and admits card filter buckets `open`, `running`, `blocked`, `review`, `terminal_failure`, and `completed` via `docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md`, `docs/API_FRONTEND_CONTRACT.md`, `orket/interfaces/operator_view_models.py`, `orket/interfaces/operator_view_support.py`, `orket/interfaces/routers/cards.py`, `orket/interfaces/routers/runs.py`, `orket/interfaces/routers/system.py`, and `orket/interfaces/api.py`
77. Canonical Card Authoring surface now lives in `docs/specs/CARD_AUTHORING_SURFACE_V1.md`; the current shipped host slice admits `POST /v1/cards`, `PUT /v1/cards/{card_id}`, and `POST /v1/cards/validate`, mints canonical host `card_id` plus card authoring `revision_id`, persists host authoring payload and revision markers on the canonical card surface, upserts issue-target authored cards into the bounded runtime projection `config/epics/orket_ui_authored_cards.json` for canonical run-card resolution, and fail-closes stale saves with `409 revision_conflict` via `docs/specs/CARD_AUTHORING_SURFACE_V1.md`, `docs/API_FRONTEND_CONTRACT.md`, `orket/interfaces/routers/card_authoring.py`, `orket/application/services/card_authoring_service.py`, `orket/application/services/card_authoring_runtime_projection_service.py`, and `orket/interfaces/api.py`
78. Canonical Flow Authoring surface now lives in `docs/specs/FLOW_AUTHORING_SURFACE_V1.md`; the current shipped host slice admits `GET /v1/flows`, `GET /v1/flows/{flow_id}`, `POST /v1/flows`, `PUT /v1/flows/{flow_id}`, `POST /v1/flows/validate`, and bounded `POST /v1/flows/{flow_id}/runs`, persists flow truth at `.orket/durable/db/orket_ui_flows.sqlite3` via `orket/runtime_paths.py::resolve_flow_authoring_db_path`, admits neutral node kinds `start`, `card`, `branch`, `merge`, and `final`, composes with the authored-card runtime projection for current run-card resolution, bounds current run initiation to exactly one `card` node that resolves to the canonical `issue` runtime target, and treats `200` plus returned `session_id` as authoritative acceptance only while downstream run completion remains governed by the existing runtime policy via `docs/specs/FLOW_AUTHORING_SURFACE_V1.md`, `docs/API_FRONTEND_CONTRACT.md`, `orket/interfaces/routers/flows.py`, `orket/application/services/flow_authoring_service.py`, `orket/adapters/storage/async_flow_repository.py`, `orket/runtime_paths.py`, and `orket/interfaces/api.py`

## Machine-Readable Authority Map (v1)

```json
{
  "version": 1,
  "last_updated": "2026-04-19",
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
      "cli_legacy_named_rock_alias": "python main.py --rock <rock_name>",
      "cli_legacy_named_rock_alias_status": "hidden_compatibility_alias_to_run_card",
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
      "supervisor_runtime_contract_sources": [
        "docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md",
        "docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md",
        "docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md",
        "docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md",
        "docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md",
        "docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PUBLISH_SURFACE_V1.md"
      ],
        "operating_principles_source": "docs/specs/ORKET_OPERATING_PRINCIPLES.md",
        "determinism_gate_policy_source": "docs/specs/ORKET_DETERMINISM_GATE_POLICY.md",
        "card_viewer_runner_surface_contract_source": "docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md",
        "card_authoring_surface_contract_source": "docs/specs/CARD_AUTHORING_SURFACE_V1.md",
        "flow_authoring_surface_contract_source": "docs/specs/FLOW_AUTHORING_SURFACE_V1.md",
        "terraform_plan_reviewer_v1_contract_source": "docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md",
        "local_prompting_contract_source": "docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md",
        "run_evidence_graph_contract_source": "docs/specs/RUN_EVIDENCE_GRAPH_V1.md",
        "sources": [
          "docs/README.md",
          "docs/ROADMAP.md",
          "docs/CONTRIBUTOR.md",
          "docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md",
          "docs/specs/CARD_AUTHORING_SURFACE_V1.md",
          "docs/specs/FLOW_AUTHORING_SURFACE_V1.md"
        ]
      },
      "card_viewer_runner_surface": {
        "contract_source": "docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md",
        "cards_list_route": "GET /v1/cards/view",
        "card_detail_route": "GET /v1/cards/{card_id}/view",
        "runs_list_route": "GET /v1/runs/view",
        "run_detail_route": "GET /v1/runs/{session_id}/view",
        "provider_status_route": "GET /v1/system/provider-status",
        "system_health_route": "GET /v1/system/health-view",
        "run_action_route": "POST /v1/system/run-active",
        "lifecycle_categories": [
          "prebuild_blocked",
          "artifact_run_failed",
          "artifact_run_completed_unverified",
          "artifact_run_verified",
          "degraded_completed"
        ],
        "card_filter_tokens": [
          "open",
          "running",
          "blocked",
          "review",
          "terminal_failure",
          "completed"
        ],
        "sources": [
          "CURRENT_AUTHORITY.md",
          "docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md",
          "docs/API_FRONTEND_CONTRACT.md",
          "orket/interfaces/operator_view_models.py",
          "orket/interfaces/operator_view_support.py",
          "orket/interfaces/routers/cards.py",
          "orket/interfaces/routers/runs.py",
          "orket/interfaces/routers/system.py",
          "orket/interfaces/api.py"
        ]
      },
      "card_authoring_surface": {
        "contract_source": "docs/specs/CARD_AUTHORING_SURFACE_V1.md",
        "create_route": "POST /v1/cards",
        "update_route": "PUT /v1/cards/{card_id}",
        "validate_route": "POST /v1/cards/validate",
        "request_wrapper": "draft",
        "stale_save_guard": "expected_revision_id",
        "host_persistence_shape": "IssueRecord.params.authoring_payload + authoring_revision_id + authoring_saved_at",
        "runtime_projection_epic_id": "orket_ui_authored_cards",
        "runtime_projection_path": "config/epics/orket_ui_authored_cards.json",
        "runtime_projection_runtime_target": "issue",
        "not_found_status_code": 404,
        "conflict_status_code": 409,
        "sources": [
          "CURRENT_AUTHORITY.md",
          "docs/specs/CARD_AUTHORING_SURFACE_V1.md",
          "docs/API_FRONTEND_CONTRACT.md",
          "orket/interfaces/routers/card_authoring.py",
          "orket/application/services/card_authoring_service.py",
          "orket/application/services/card_authoring_runtime_projection_service.py",
          "orket/interfaces/api.py"
        ]
      },
      "flow_authoring_surface": {
        "contract_source": "docs/specs/FLOW_AUTHORING_SURFACE_V1.md",
        "list_route": "GET /v1/flows",
        "detail_route": "GET /v1/flows/{flow_id}",
        "create_route": "POST /v1/flows",
        "update_route": "PUT /v1/flows/{flow_id}",
        "validate_route": "POST /v1/flows/validate",
        "run_route": "POST /v1/flows/{flow_id}/runs",
        "stale_save_guard": "expected_revision_id",
        "storage_path": ".orket/durable/db/orket_ui_flows.sqlite3",
        "storage_resolver": "orket/runtime_paths.py::resolve_flow_authoring_db_path",
        "run_card_resolution_support": "config/epics/orket_ui_authored_cards.json via card authoring runtime projection",
        "admitted_node_kinds": [
          "start",
          "card",
          "branch",
          "merge",
          "final"
        ],
        "bounded_run_slice": [
          "exactly_one_card_node",
          "branch_and_merge_forbidden_on_run_initiation",
          "assigned_card_present_on_host_card_surface",
          "assigned_card_resolves_on_canonical_run_card_surface",
          "assigned_card_resolves_to_issue_runtime_target"
        ],
        "run_success_scope": "accepted_session_id_only",
        "downstream_completion_authority": "existing_runtime_policy_after_handoff",
        "sources": [
          "CURRENT_AUTHORITY.md",
          "docs/specs/FLOW_AUTHORING_SURFACE_V1.md",
          "docs/API_FRONTEND_CONTRACT.md",
          "orket/interfaces/routers/flows.py",
          "orket/application/services/flow_authoring_service.py",
          "orket/adapters/storage/async_flow_repository.py",
          "orket/runtime_paths.py",
          "orket/interfaces/api.py"
        ]
      },
      "supervisor_runtime_session_boundary": {
        "continuity_identifier": "session_id",
        "session_start_route": "POST /v1/interactions/sessions",
      "turn_attachment_route": "POST /v1/interactions/{session_id}/turns",
      "inspection_routes": [
        "GET /v1/sessions/{session_id}",
        "GET /v1/sessions/{session_id}/status",
        "GET /v1/sessions/{session_id}/replay",
        "GET /v1/sessions/{session_id}/snapshot"
      ],
      "cleanup_adjacent_routes": [
        "POST /v1/sessions/{session_id}/halt",
        "POST /v1/interactions/{session_id}/cancel"
      ],
      "protocol_inspection_routes": [
        "GET /v1/protocol/runs/{run_id}/replay",
        "GET /v1/protocol/replay/compare",
        "GET /v1/protocol/replay/campaign",
        "GET /v1/protocol/runs/{run_id}/ledger-parity",
        "GET /v1/protocol/ledger-parity/campaign"
      ],
      "bounded_context_inputs": [
        "session_params",
        "input_config",
        "turn_params",
        "workload_id",
        "department",
        "workspace",
        "required_capabilities"
      ],
      "context_version": "packet1_session_context_v1",
      "provider_order": [
        "host_continuity",
        "turn_request",
        "extension_manifest_required_capabilities"
      ],
      "interaction_snapshot_surface": {
        "route": "GET /v1/sessions/{session_id}/snapshot",
        "fields": [
          "context_version",
          "provider_lineage",
          "latest_context_envelope"
        ],
        "authority": "inspection_only"
      },
      "interaction_replay_timeline_surface": {
        "route": "GET /v1/sessions/{session_id}/replay",
        "mode": "timeline_without_issue_id_or_turn_index",
        "authority": "inspection_only"
      },
      "interaction_targeted_replay_rule": "fail_closed_run_session_only",
      "workspace_containment_rule": "fail_closed",
      "replay_authority": "inspection_only",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md",
        "orket/interfaces/routers/sessions.py",
        "orket/interfaces/api.py",
        "orket/streaming/manager.py",
        "orket/streaming/session_context.py",
        "tests/interfaces/test_api_interactions.py",
        "tests/streaming/test_manager.py",
        "tests/interfaces/test_sessions_router_protocol_replay.py",
        "tests/interfaces/test_api.py"
      ]
    },
    "api_runtime_ownership": {
      "authoritative_owner": "app.state.api_runtime_context",
      "factory": "orket/interfaces/api.py::create_api_app",
      "context_contract_module": "orket/interfaces/api_runtime_context.py",
      "transport_module": "orket/interfaces/api.py",
      "compatibility_aliases": [
        "engine",
        "api_runtime_host",
        "stream_bus",
        "interaction_manager",
        "extension_manager",
        "extension_runtime_service"
      ],
      "env_sensitive_lazy_owners": [
        "stream_bus",
        "interaction_manager"
      ],
      "sources": [
        "CURRENT_AUTHORITY.md",
        "orket/interfaces/api.py",
        "orket/interfaces/api_runtime_context.py",
        "tests/interfaces/test_api_composition_isolation.py",
        "tests/interfaces/conftest.py"
      ]
    },
    "engine_control_plane_composition": {
      "composition_builder": "orket/orchestration/engine_services.py::build_engine_control_plane_services",
      "async_kernel_control_plane_service": "orket/orchestration/engine_kernel_async_service.py::KernelAsyncControlPlaneService",
      "canonical_replay_surface": "orket/orchestration/engine.py::replay_turn_diagnostics",
      "compatibility_replay_surface": "orket/orchestration/engine.py::replay_turn",
      "replay_authority_class": "artifact_observability_only",
      "issue_dispatch_truth_owner": "orket/application/services/orchestrator_issue_control_plane_service.py",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "orket/orchestration/engine.py",
        "orket/orchestration/engine_services.py",
        "orket/orchestration/engine_kernel_async_service.py",
        "orket/application/services/orchestrator_issue_control_plane_service.py",
        "orket/interfaces/api.py",
        "orket/interfaces/cli.py",
        "tests/application/test_engine_refactor.py",
        "tests/application/test_orchestration_engine_kernel_async.py",
        "tests/application/test_orchestrator_issue_control_plane_service.py",
        "tests/integration/test_orchestrator_issue_control_plane.py"
      ]
    },
    "tool_execution_gate_surface": {
      "contract_source": "docs/specs/TOOL_EXECUTION_GATE_V1.md",
      "supported_path": [
        "orket/runtime/execution/execution_pipeline_card_dispatch.py::ExecutionPipelineCardDispatchMixin.run_card",
        "orket/application/workflows/turn_executor.py::TurnExecutor.execute_turn",
        "orket/application/workflows/turn_tool_dispatcher.py::ToolDispatcher.execute_tools"
      ],
      "normalized_primary_path": "orket/extensions/runtime.py::ExtensionEngineAdapter.execute_action",
      "construction_time_gate_requirement": true,
      "legacy_fail_closed_surface": "orket/agents/agent.py::Agent.run",
      "legacy_fail_closed_rule": "block_before_any_direct_tool_call_without_tool_gate",
      "internal_only_inventory": [
        "orket/application/workflows/turn_tool_dispatcher.py::ToolDispatcher.execute_tools",
        "orket/tools.py::ToolBox.execute",
        "orket/runtime/execution/execution_pipeline_card_dispatch.py::ExecutionPipelineCardDispatchMixin._run_issue_entry"
      ],
      "out_of_scope_lane": "docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md",
      "audit_operator_path": "python scripts/security/build_tool_gate_audit.py --strict",
      "audit_output_path": "benchmarks/results/security/tool_gate_audit.json",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/specs/TOOL_EXECUTION_GATE_V1.md",
        "docs/architecture/event_taxonomy.md",
        "scripts/security/build_tool_gate_audit.py",
        "tests/application/test_tool_gate_enforcement_closure.py",
        "tests/scripts/test_build_tool_gate_audit.py"
      ]
    },
    "runtime_verification_support_artifacts": {
      "latest_path": "agent_output/verification/runtime_verification.json",
      "history_index_path": "agent_output/verification/runtime_verification_index.json",
      "history_records_root": "agent_output/verification/runtime_verifier_records/",
      "artifact_role": "support_verification_evidence",
      "artifact_authority": "support_only",
      "authored_output": false,
      "required_evidence_classes": [
        "syntax_only",
        "command_execution",
        "behavioral_verification",
        "not_evaluated"
      ],
      "primary_output_promotion_rule": "forbidden_by_default",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md",
        "orket/application/services/runtime_verifier.py",
        "orket/application/services/runtime_verification_artifact_service.py",
        "orket/runtime/summary/run_summary.py",
        "scripts/audit/audit_support.py",
        "tests/application/test_runtime_verifier_service.py",
        "tests/live/test_system_acceptance_pipeline.py"
      ]
    },
    "companion_bff_boundary": {
      "product_route_owner": "external_companion_bff",
      "gateway_route_family": "/api/*",
      "host_route_family": "/v1/extensions/{extension_id}/runtime/*",
      "legacy_companion_host_routes_present": false,
      "host_auth_source": "ORKET_API_KEY",
      "gateway_host_credential_envs": [
        "COMPANION_API_KEY",
        "ORKET_API_KEY"
      ],
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/specs/COMPANION_UI_MVP_CONTRACT.md",
        "docs/API_FRONTEND_CONTRACT.md",
        "orket/interfaces/routers/extension_runtime.py",
        "docs/templates/external_extension/src/companion_app/server.py"
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
      "productflow_live_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/productflow/run_governed_write_file_flow.py",
      "productflow_review_operator_path": "python scripts/productflow/build_operator_review_package.py --run-id <run_id>",
      "productflow_replay_operator_path": "python scripts/productflow/run_replay_review.py --run-id <run_id>",
      "productflow_live_proof_output_path": "benchmarks/results/productflow/governed_write_file_live_run.json",
      "productflow_review_index_path": "runs/<session_id>/productflow_review_index.json",
      "productflow_operator_review_proof_output_path": "benchmarks/results/productflow/operator_review_proof.json",
      "productflow_replay_review_output_path": "benchmarks/results/productflow/replay_review.json",
      "trusted_run_witness_campaign_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_run_witness_campaign.py",
      "trusted_run_witness_builder_operator_path": "python scripts/proof/build_trusted_run_witness_bundle.py --run-id <run_id>",
      "trusted_run_witness_verifier_operator_path": "python scripts/proof/verify_trusted_run_witness_bundle.py --bundle <bundle_path>",
      "offline_trusted_run_verifier_operator_path": "python scripts/proof/verify_offline_trusted_run_claim.py --input <evidence_path>",
      "trusted_run_witness_bundle_path": "runs/<session_id>/trusted_run_witness_bundle.json",
      "trusted_run_witness_verification_output_path": "benchmarks/results/proof/trusted_run_witness_verification.json",
      "offline_trusted_run_verifier_output_path": "benchmarks/results/proof/offline_trusted_run_verifier.json",
      "trusted_repo_change_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py",
      "trusted_repo_change_campaign_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py",
      "trusted_repo_change_live_run_output_path": "benchmarks/results/proof/trusted_repo_change_live_run.json",
      "trusted_repo_change_validator_output_path": "benchmarks/results/proof/trusted_repo_change_validator.json",
      "trusted_repo_change_witness_verification_output_path": "benchmarks/results/proof/trusted_repo_change_witness_verification.json",
      "trusted_repo_change_offline_verifier_output_path": "benchmarks/results/proof/trusted_repo_change_offline_verifier.json",
      "trusted_repo_change_bundle_path": "workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json",
      "run_evidence_graph_default_views": [
        "full_lineage",
        "failure_path",
        "resource_authority_path",
        "closure_path"
      ],
      "run_evidence_graph_admitted_view_tokens": [
        "full_lineage",
        "failure_path",
        "authority",
        "decision",
        "resource_authority_path",
        "closure_path"
      ],
      "terraform_plan_review_live_smoke_output_path": ".orket/durable/observability/terraform_plan_review_live_smoke.json",
      "local_model_coding_challenge_operator_path": "python scripts/benchmarks/run_local_model_coding_challenge.py --provider <provider> --model <model_id> --epic challenge_workflow_runtime",
      "local_model_coding_challenge_output_path": "benchmarks/staging/General/local_model_coding_challenge_report.json",
      "tool_gate_audit_operator_path": "python scripts/security/build_tool_gate_audit.py --strict",
      "tool_gate_audit_output_path": "benchmarks/results/security/tool_gate_audit.json",
      "prompt_reforger_gemma_inventory_operator_path": "python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_inventory.py",
      "prompt_reforger_gemma_inventory_output_path": "benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json",
      "prompt_reforger_gemma_score_operator_path": "python scripts/prompt_lab/score_prompt_reforger_gemma_tool_use_corpus.py --run-summary <run_summary> --observability-root <observability_root>",
      "prompt_reforger_gemma_score_output_path": "benchmarks/staging/General/prompt_reforger_gemma_tool_use_score.json",
      "prompt_reforger_gemma_judge_operator_path": "python scripts/prompt_lab/run_functiongemma_tool_call_judge.py --score-report <score_report> --inventory benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json",
      "prompt_reforger_gemma_judge_output_path": "benchmarks/staging/General/prompt_reforger_gemma_tool_use_judge.json",
      "prompt_reforger_gemma_cycle_operator_path": "python scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_cycle.py --targets both --runs 1",
      "prompt_reforger_gemma_cycle_output_path": "benchmarks/staging/General/prompt_reforger_gemma_tool_use_cycle.json",
      "artifact_review_policy": "docs/process/PUBLISHED_ARTIFACTS_POLICY.md",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/CONTRIBUTOR.md",
        "docs/projects/PromptReforgerToolCompatibility/PROMPT_REFORGER_GEMMA_TOOL_USE_IMPLEMENTATION_PLAN.md",
        "docs/specs/RUN_EVIDENCE_GRAPH_V1.md",
        "docs/specs/TOOL_EXECUTION_GATE_V1.md",
        "docs/architecture/event_taxonomy.md",
        "docs/process/PUBLISHED_ARTIFACTS_POLICY.md",
        "scripts/observability/emit_run_evidence_graph.py",
        "scripts/security/build_tool_gate_audit.py",
        "scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_inventory.py",
        "scripts/prompt_lab/run_functiongemma_tool_call_judge.py",
        "scripts/prompt_lab/run_prompt_reforger_gemma_tool_use_cycle.py",
        "scripts/prompt_lab/README.md",
        "docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md",
        "docs/specs/TRUSTED_RUN_WITNESS_V1.md",
        "docs/specs/TRUSTED_RUN_INVARIANTS_V1.md",
        "docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md",
        "docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md",
        "docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md",
        "scripts/proof/trusted_run_invariant_model.py",
        "scripts/proof/control_plane_witness_substrate.py",
        "scripts/proof/offline_trusted_run_verifier.py",
        "scripts/proof/verify_offline_trusted_run_claim.py",
        "scripts/proof/run_trusted_run_witness_campaign.py",
        "scripts/proof/trusted_repo_change_contract.py",
        "scripts/proof/trusted_repo_change_verifier.py",
        "scripts/proof/trusted_repo_change_workflow.py",
        "scripts/proof/trusted_repo_change_offline.py",
        "scripts/proof/run_trusted_repo_change.py",
        "scripts/proof/run_trusted_repo_change_campaign.py"
      ]
    },
    "productflow_governed_write_file_review_surface": {
      "live_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/productflow/run_governed_write_file_flow.py",
      "review_operator_path": "python scripts/productflow/build_operator_review_package.py --run-id <run_id>",
      "replay_operator_path": "python scripts/productflow/run_replay_review.py --run-id <run_id>",
      "stable_artifacts": [
        "benchmarks/results/productflow/governed_write_file_live_run.json",
        "runs/<session_id>/productflow_review_index.json",
        "runs/<session_id>/run_evidence_graph.json",
        "runs/<session_id>/run_evidence_graph.mmd",
        "runs/<session_id>/run_evidence_graph.html",
        "benchmarks/results/productflow/operator_review_proof.json",
        "benchmarks/results/productflow/replay_review.json"
      ],
      "resolver_witness": "unique approval.control_plane_target_ref == run_id for approval_required_tool:write_file + validated runs/<session_id>/run_summary.json",
      "run_summary_identity_note": "For the canonical ProductFlow fixture, run_summary.run_id is the session_id and run_summary.control_plane.run_id is the cards-epic run id; neither replaces the governed turn-tool run_id.",
      "review_package_expected_result": "success",
      "replay_surface_expected_result": "same-run truthful blocker",
      "replay_ready": false,
      "stability_status": "not_evaluable",
      "claim_tier": "non_deterministic_lab_only",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md",
        "docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md",
        "scripts/productflow/productflow_support.py",
        "scripts/productflow/run_governed_write_file_flow.py",
        "scripts/productflow/build_operator_review_package.py",
        "scripts/productflow/run_replay_review.py",
        "scripts/observability/emit_run_evidence_graph.py"
      ]
    },
    "trusted_run_witness_v1": {
      "spec": "docs/specs/TRUSTED_RUN_WITNESS_V1.md",
      "invariant_spec": "docs/specs/TRUSTED_RUN_INVARIANTS_V1.md",
      "substrate_spec": "docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md",
      "offline_verifier_spec": "docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md",
      "useful_workflow_spec": "docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md",
      "trust_reason_spec": "docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md",
      "governed_change_packet_kernel_spec": "docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md",
      "governed_change_packet_spec": "docs/specs/GOVERNED_CHANGE_PACKET_V1.md",
      "governed_change_packet_standalone_verifier_spec": "docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md",
      "terraform_plan_decision_scope_spec": "docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md",
      "governed_repo_change_packet_guide": "docs/guides/GOVERNED_REPO_CHANGE_PACKET_GUIDE.md",
      "terraform_plan_decision_scope_guide": "docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md",
      "scope_admission_standard_spec": "docs/specs/TRUSTED_CHANGE_SCOPE_ADMISSION_STANDARD_V1.md",
      "scope_catalog_spec": "docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md",
      "compare_scope": "trusted_run_productflow_write_file_v1",
      "admitted_compare_scopes": [
        "trusted_run_productflow_write_file_v1",
        "trusted_repo_config_change_v1",
        "trusted_terraform_plan_decision_v1"
      ],
      "current_public_trust_slice_compare_scope": "trusted_repo_config_change_v1",
      "terraform_plan_decision_publication_status": "internal_admitted_only_not_public",
      "terraform_plan_decision_publication_blocker": "successful provider-backed governed-proof evidence is not yet admitted public evidence; current admitted campaign evidence still comes from the bounded local harness over Terraform reviewer v1",
      "terraform_plan_decision_runtime_smoke_operator_path": "python scripts/reviewrun/run_terraform_plan_review_live_smoke.py --out benchmarks/results/proof/terraform_plan_review_live_smoke.json",
      "terraform_plan_decision_governed_runtime_operator_path": "python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json",
      "terraform_plan_decision_live_setup_packet_operator_path": "python scripts/proof/prepare_trusted_terraform_live_setup_packet.py",
      "terraform_plan_decision_live_setup_packet_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_packet.json",
      "terraform_plan_decision_live_setup_packet_root": "workspace/trusted_terraform_live_setup/",
      "terraform_plan_decision_live_setup_preflight_operator_path": "python scripts/proof/check_trusted_terraform_live_setup_preflight.py",
      "terraform_plan_decision_live_setup_preflight_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_preflight.json",
      "terraform_plan_decision_publication_readiness_operator_path": "python scripts/proof/check_trusted_terraform_publication_readiness.py",
      "terraform_plan_decision_publication_readiness_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_publication_readiness.json",
      "terraform_plan_decision_publication_gate_operator_path": "python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py",
      "terraform_plan_decision_publication_gate_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_publication_gate.json",
      "operator_surface": "trusted_run_witness_report.v1",
      "offline_verifier_schema": "offline_trusted_run_verifier.v1",
      "proof_foundation_schema": "trusted_run_proof_foundation.v1",
      "contract_verdict_surface": "trusted_run_contract_verdict.v1",
      "invariant_model_surface": "trusted_run_invariant_model.v1",
      "substrate_model_surface": "control_plane_witness_substrate.v1",
      "witness_bundle_schema": "trusted_run.witness_bundle.v1",
      "bundle_path": "runs/<session_id>/trusted_run_witness_bundle.json",
      "verification_output_path": "benchmarks/results/proof/trusted_run_witness_verification.json",
      "offline_verifier_output_path": "benchmarks/results/proof/offline_trusted_run_verifier.json",
      "proof_foundation_output_path": "benchmarks/results/proof/trusted_run_proof_foundation.json",
      "campaign_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_run_witness_campaign.py",
      "offline_verifier_operator_path": "python scripts/proof/verify_offline_trusted_run_claim.py --input <evidence_path>",
      "proof_foundation_operator_path": "python scripts/proof/verify_trusted_run_proof_foundation.py",
      "validator_backed_scope_family_helper": "scripts/proof/trusted_scope_family_support.py",
      "validator_backed_scope_family_support_modules": [
        "scripts/proof/trusted_scope_family_support.py",
        "scripts/proof/trusted_scope_family_claims.py",
        "scripts/proof/trusted_scope_family_common.py"
      ],
      "trusted_repo_change": {
        "compare_scope": "trusted_repo_config_change_v1",
        "contract_verdict_surface": "trusted_repo_change_contract_verdict.v1",
        "validator_surface": "trusted_repo_config_validator.v1",
        "workflow_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py",
        "campaign_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py",
        "governed_packet_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_governed_repo_change_packet.py",
        "governed_packet_verifier_operator_path": "python scripts/proof/verify_governed_change_packet.py --input benchmarks/results/proof/governed_repo_change_packet.json --output benchmarks/results/proof/governed_repo_change_packet_verifier.json",
        "governed_packet_trusted_kernel_operator_path": "python scripts/proof/verify_governed_change_packet_trusted_kernel.py --output benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json",
        "live_run_output_path": "benchmarks/results/proof/trusted_repo_change_live_run.json",
        "validator_output_path": "benchmarks/results/proof/trusted_repo_change_validator.json",
        "verification_output_path": "benchmarks/results/proof/trusted_repo_change_witness_verification.json",
        "offline_verifier_output_path": "benchmarks/results/proof/trusted_repo_change_offline_verifier.json",
        "bundle_path": "workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json",
        "governed_packet_output_path": "benchmarks/results/proof/governed_repo_change_packet.json",
        "governed_packet_verifier_output_path": "benchmarks/results/proof/governed_repo_change_packet_verifier.json",
        "governed_packet_trusted_kernel_output_path": "benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json",
        "governed_packet_adversarial_benchmark_candidate": "benchmarks/staging/General/governed_repo_change_packet_adversarial_benchmark_2026-04-19.json"
      },
      "trusted_terraform_plan_decision": {
        "compare_scope": "trusted_terraform_plan_decision_v1",
        "contract_verdict_surface": "trusted_terraform_plan_decision_contract_verdict.v1",
        "validator_surface": "trusted_terraform_plan_decision_validator.v1",
        "workflow_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision.py",
        "campaign_operator_path": "ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_terraform_plan_decision_campaign.py",
        "governed_runtime_operator_path": "python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json",
        "live_setup_packet_operator_path": "python scripts/proof/prepare_trusted_terraform_live_setup_packet.py",
        "live_setup_preflight_operator_path": "python scripts/proof/check_trusted_terraform_live_setup_preflight.py",
        "publication_readiness_operator_path": "python scripts/proof/check_trusted_terraform_publication_readiness.py",
        "publication_gate_operator_path": "python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py",
        "live_run_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_live_run.json",
        "governed_runtime_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json",
        "live_setup_packet_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_packet.json",
        "live_setup_packet_root": "workspace/trusted_terraform_live_setup/",
        "live_setup_preflight_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_live_setup_preflight.json",
        "publication_readiness_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_publication_readiness.json",
        "publication_gate_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_publication_gate.json",
        "validator_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_validator.json",
        "verification_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_witness_verification.json",
        "offline_verifier_output_path": "benchmarks/results/proof/trusted_terraform_plan_decision_offline_verifier.json",
        "bundle_path": "workspace/trusted_terraform_plan_decision/runs/<session_id>/trusted_run_witness_bundle.json",
        "runtime_smoke_operator_path": "python scripts/reviewrun/run_terraform_plan_review_live_smoke.py --out benchmarks/results/proof/terraform_plan_review_live_smoke.json"
      },
      "single_run_claim_tier": "non_deterministic_lab_only",
      "campaign_target_claim_tier": "verdict_deterministic",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/specs/TRUSTED_RUN_WITNESS_V1.md",
        "docs/specs/TRUSTED_RUN_INVARIANTS_V1.md",
        "docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md",
        "docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md",
        "docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md",
        "docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md",
        "docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md",
        "docs/specs/GOVERNED_CHANGE_PACKET_V1.md",
        "docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md",
        "docs/specs/TRUSTED_TERRAFORM_PLAN_DECISION_V1.md",
        "docs/specs/TRUSTED_CHANGE_SCOPE_ADMISSION_STANDARD_V1.md",
        "docs/specs/TRUSTED_CHANGE_SCOPE_CATALOG_V1.md",
        "docs/guides/GOVERNED_REPO_CHANGE_PACKET_GUIDE.md",
        "docs/guides/TRUSTED_TERRAFORM_PLAN_DECISION_SCOPE_GUIDE.md",
        "scripts/proof/trusted_run_invariant_model.py",
        "scripts/proof/control_plane_witness_substrate.py",
        "scripts/proof/trusted_run_witness_contract.py",
        "scripts/proof/offline_trusted_run_verifier.py",
        "scripts/proof/trusted_run_proof_foundation.py",
        "scripts/proof/trusted_run_non_interference.py",
        "scripts/proof/trusted_run_witness_support.py",
        "scripts/proof/trusted_scope_family_support.py",
        "scripts/proof/trusted_scope_family_claims.py",
        "scripts/proof/trusted_scope_family_common.py",
        "scripts/proof/trusted_repo_change_contract.py",
        "scripts/proof/trusted_repo_change_verifier.py",
        "scripts/proof/trusted_repo_change_workflow.py",
        "scripts/proof/trusted_repo_change_offline.py",
        "scripts/proof/governed_change_packet_contract.py",
        "scripts/proof/governed_change_packet_trusted_kernel.py",
        "scripts/proof/governed_change_packet_workflow.py",
        "scripts/proof/governed_change_packet_verifier.py",
        "scripts/proof/run_governed_repo_change_packet.py",
        "scripts/proof/verify_governed_change_packet.py",
        "scripts/proof/verify_governed_change_packet_trusted_kernel.py",
        "scripts/proof/run_governed_change_packet_adversarial_benchmark.py",
        "scripts/proof/trusted_terraform_plan_decision_contract.py",
        "scripts/proof/trusted_terraform_plan_decision_verifier.py",
        "scripts/proof/trusted_terraform_plan_decision_workflow.py",
        "scripts/proof/trusted_terraform_plan_decision_bundle_support.py",
        "scripts/proof/trusted_terraform_plan_decision_offline.py",
        "scripts/proof/terraform_plan_review_live_support.py",
        "scripts/proof/build_trusted_run_witness_bundle.py",
        "scripts/proof/verify_trusted_run_witness_bundle.py",
        "scripts/proof/verify_offline_trusted_run_claim.py",
        "scripts/proof/verify_trusted_run_proof_foundation.py",
        "scripts/proof/run_trusted_run_witness_campaign.py",
        "scripts/proof/run_trusted_repo_change.py",
        "scripts/proof/run_trusted_repo_change_campaign.py",
        "scripts/proof/run_trusted_terraform_plan_decision.py",
        "scripts/proof/run_trusted_terraform_plan_decision_campaign.py",
        "scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py",
        "scripts/proof/prepare_trusted_terraform_live_setup_packet.py",
        "scripts/proof/check_trusted_terraform_live_setup_preflight.py",
        "scripts/proof/check_trusted_terraform_publication_readiness.py",
        "scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py",
        "scripts/reviewrun/run_terraform_plan_review_live_smoke.py"
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
        "orket/runtime/registry/tool_invocation_contracts.py",
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
      "matrix_gate_doc": "docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md",
      "authority_inputs": [
        "catalog_workload",
        "workload_contract_v1",
        "extension_manifest_workload"
      ],
      "internal_helpers_not_authority": [
        "orket/application/services/control_plane_workload_catalog.py::build_cards_workload_contract"
      ],
      "compatibility_adapters": [],
      "status": "partial",
      "governance_tests": [
        "tests/application/test_control_plane_workload_authority_governance.py",
        "tests/runtime/test_cards_workload_adapter.py"
      ],
      "note": "Only resolve_control_plane_workload(...) is an externally blessed workload-authority seam. The governed start-path matrix in the durable matrix companion is a closure gate, so governance fails if a non-test module consumes workload authority from the catalog without explicit matrix coverage, if touched catalog-resolved publishers reintroduce local workload_id/workload_version aliases, if non-CLI runtime callsites drift back onto run_epic(...), run_issue(...), or run_rock(...) compatibility wrappers, if public wrappers stop collapsing to run_card(...), if the canonical run_card(...) dispatcher starts minting workload authority directly instead of routing into internal entrypoints, or if governed turn-tool runtime entrypoints drift away from the exact adapter-only routing helpers in orket/application/workflows/turn_executor_control_plane.py and orket/application/workflows/turn_tool_dispatcher_control_plane.py that invoke TurnToolControlPlaneService without minting workload authority locally. The canonical public runtime execution surface is run_card(...); run_issue(...), run_epic(...), and run_rock(...) survive only as thin convenience wrappers, with the legacy CLI --rock alias kept hidden and routed directly to run_card(...) as compatibility-only CLI input. Cards, ODR, and extension workload execution resolve through the catalog seam, the cards, ODR, and extension start paths use catalog-local helper resolution instead of assembling WorkloadAuthorityInput(...) in runtime entrypoints, controller dispatch checks extension child eligibility through the manager-owned boolean probes has_manifest_entry(...) and uses_sdk_contract(...) instead of resolving private manifest-entry tuples directly, and internal rock routing remains routing-only debt through the generic epic-collection path.",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "orket/application/services/control_plane_workload_catalog.py",
        "orket/application/services/kernel_action_control_plane_service.py",
        "orket/application/services/review_run_control_plane_service.py",
        "orket/application/services/turn_tool_control_plane_service.py",
        "orket/application/workflows/turn_executor_control_plane.py",
        "orket/application/workflows/turn_tool_dispatcher_control_plane.py",
        "orket/application/services/orchestrator_issue_control_plane_service.py",
        "orket/application/services/orchestrator_scheduler_control_plane_service.py",
        "orket/application/services/orchestrator_scheduler_control_plane_mutation.py",
        "orket/application/services/gitea_state_control_plane_execution_service.py",
        "orket/extensions/manager.py",
        "orket/extensions/artifact_provenance.py",
        "orket/runtime/execution_pipeline.py",
        "orket/runtime/epic_run_orchestrator.py",
        "scripts/odr/run_arbiter.py",
        "tests/application/test_control_plane_workload_authority_governance.py",
        "docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md"
      ]
    },
    "governed_turn_tool_namespace_policy": {
      "default_namespace_scope": "issue:<issue_id>",
      "policy_enforcer": "orket/application/workflows/turn_tool_dispatcher_support.py::tool_policy_violation",
      "manifest_contract": "orket/runtime/registry/tool_invocation_contracts.py::build_tool_invocation_manifest",
      "binding_source": "orket/application/services/skill_adapter.py",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "orket/application/workflows/turn_tool_dispatcher.py",
        "orket/application/workflows/turn_tool_dispatcher_protocol.py",
        "orket/application/workflows/turn_tool_dispatcher_support.py",
        "orket/runtime/registry/tool_invocation_contracts.py",
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
      "loop_runner": "orket/runtime/gitea_state_loop.py::run_gitea_state_loop",
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
        "orket/runtime/execution_pipeline.py",
        "orket/runtime/gitea_state_loop.py"
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
      "primary": "orket/runtime/config/provider_runtime_target.py",
      "compatibility_alias": "orket/runtime/provider_runtime_target.py",
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

## Runtime Behavior Notes

Turn tool-call recovery is fail-closed when truncated recovery is partial: `ToolParser` records `recovery_complete=false`, `ResponseParser` and the legacy `Agent` path emit `tool_recovery_partial`, mark the turn with `partial_parse_failure=True` and `ToolCallErrorClass.PARSE_PARTIAL`, and do not execute recovered, skipped, or hardcoded recovery tool calls.

Truncated tool-call recovery consults `orket/adapters/tools/registry.py::DEFAULT_TOOL_REGISTRY` for recoverable tool argument schemas. The default registry only enables recovery for `read_file`, `write_file`, and `update_issue_status`; additional tools require explicit recoverable registration instead of parser code changes.

Tool execution through `ToolRuntimeExecutor` has a default per-tool timeout of 60 seconds, with runtime context overrides flowing through `tool_timeout_seconds`, skill `tool_runtime_limits.max_execution_time`, or organization-derived `max_tool_execution_time`.

Async-reachable structured log writes use a bounded queue sized by `ORKET_LOG_QUEUE_MAX` with default `10000`; when the queue is full, Orket drops the log record, increments `dropped_log_entry_count()`, and emits sparse stdlib-only `log_write_queue_full` warnings instead of blocking the event loop or recursing through `log_event`.

Runtime log-level resolution in `orket/utils.py` is call-time via `get_current_level()` with `reset_current_level_cache()` for test isolation; there is no import-time `CURRENT_LEVEL` authority.

Agent model-family resolution uses `orket/agents/model_family_registry.py`, defaulting to DeepSeek/Llama/Phi/Qwen pattern mappings and accepting operator extension through `ORKET_MODEL_FAMILY_PATTERNS`; unrecognized models fall back to `generic` and emit `model_family_unrecognized`.

Legacy `Agent.run()` has an opt-in `ControlPlaneAuthorityService` journal seam. Without `journal`, tool effects are log-only; with `journal`, successful and failed tool executions publish `EffectJournalEntryRecord` payloads using `ToolCallErrorClass` and context-provided run authority, and journal publication failures are not silently swallowed.

The canonical supported runtime tool-execution gate story currently centers on the `run_card(...)` family collapsing into `TurnExecutor` and the governed `ToolDispatcher.execute_tools(...)` seam. On that path, pre-execution admission is composed inside the dispatcher from `ToolGate.validate(...)`, dispatcher policy checks in `orket/application/workflows/turn_tool_dispatcher_support.py::tool_policy_violation(...)`, and bounded approval gating; direct `ToolDispatcher` use is internal-only.

Legacy `Agent.run()` direct tool execution remains noncanonical compatibility debt rather than a co-equal supported runtime gate surface because it still accepts an optional `tool_gate` and only gates when one is present.

Extension engine actions that normalize onto `run_card(...)` inherit that canonical governed runtime path, while SDK capability registry invocations inside extension workloads remain a separate authorization problem rather than part of the canonical tool-dispatch authority story.

`EnvironmentConfig` still warns and drops unknown keys at the compatibility Pydantic boundary, but authoritative runtime environment loading now fails closed with `E_ENVIRONMENT_CONFIG_UNKNOWN_KEYS:<keys>` before model work when a touched runtime path supplies undeclared keys.

Session transcripts are schema-bound through `TranscriptTurn` / `ToolCallRecord` at `orket/session.py`; legacy dict rows are defensively migrated on `Session` construction and serialized back as versioned transcript turns.

`OpenClawJsonlSubprocessAdapter.run_requests()` returns `PartialAdapterResult`, preserving `responses`, `completed_count`, and `failed_at` on subprocess failure so callers can avoid unsafe full replay of already-completed adapter requests.

Runtime implementation modules are physically grouped under bounded `orket/runtime/config/`, `orket/runtime/evidence/`, `orket/runtime/execution/`, `orket/runtime/policy/`, `orket/runtime/registry/`, and `orket/runtime/summary/` subpackages with explicit package `__all__` surfaces. The old flat `orket.runtime.<module>` imports are one-release alias shims that preserve compatibility while resolving to the migrated implementation modules; new direct cross-domain imports must go through package public surfaces and are guarded by `tests/runtime/test_runtime_subpackage_boundaries.py`.

The canonical API runtime entrypoint `python server.py` bootstraps environment values from the repo-root `.env` before FastAPI app construction. This preserves the normal `load_env()` precedence rule: explicit process environment variables remain authoritative over `.env` values.

SDK extension workloads run in a child interpreter through `orket/extensions/sdk_workload_runner.py` and `orket/extensions/sdk_workload_subprocess.py`. SDK workload loading statically rejects undeclared standard-library imports, and subprocess execution installs both a manifest-declared stdlib `sys.meta_path` finder and scoped `__import__` guard so dynamic undeclared imports fail before extension code can reuse already-loaded host modules. Legacy workloads retain compatibility behavior: internal Orket imports remain blocked, and stdlib allowlist enforcement applies only when the legacy manifest declares allowed modules.

The shipped SDK capability-authorization first slice is host-owned through `host_authorized_capability_registry_v1` at `orket/extensions/workload_executor.py`, `orket/extensions/sdk_capability_authorization.py`, `orket/extensions/workload_artifacts.py`, `orket/extensions/sdk_capability_runtime.py`, `orket/extensions/sdk_workload_runner.py`, and `orket/extensions/sdk_workload_subprocess.py`; the parent now emits a host-issued authorization envelope, the child revalidates that envelope before workload code executes, and the governed runtime seam fail-closes `model.generate`, `memory.query`, and `memory.write` with distinct `undeclared_use`, `denied`, `admitted_unavailable`, and `authorization_drift` truth while preserving `declared_capabilities`, `admitted_capabilities`, `instantiated_capabilities`, and `used_capabilities` distinctly in provenance and the canonical audit artifact at `benchmarks/results/extensions/extension_capability_audit.json` generated by `python scripts/extensions/build_extension_capability_audit.py --strict`.

Factory-built agents from `orket/agents/agent_factory.py` fail closed to the union of tools declared by the seat's configured roles. Seats without roles or with missing role configs raise `AgentConfigurationError` and emit error events instead of inheriting the full toolbox.

SQLite/Gitea card-state reconciliation is inspection-only and halt-and-alert by default: `StateReconciliationService` compares requested card ids across `AsyncCardRepository` and `GiteaStateAdapter.fetch_card_snapshot`, emits `state_reconciliation_conflict` on divergence, and the on-demand `scripts/gitea/reconcile_state_backends.py` command writes stable diff-ledger JSON at `benchmarks/results/gitea/state_reconciliation.json`.

iDesign source-category enforcement defaults to `iDesignValidator.ALLOWED_CATEGORIES`, but `OrganizationConfig.allowed_idesign_categories` can replace that category set for organization-scoped `ToolGate` validation.

`BaseCardConfig.priority` is now authoritative as a `float`; legacy persisted string priorities are accepted only through the Pydantic construction boundary where `convert_priority` migrates `High`/`Medium`/`Low` and numeric strings, while unknown strings fail validation and must be cleaned before persistence.

Synchronous settings bridge calls that would cross an active event loop fail with `SettingsBridgeError`, not `AssertionError`.

`orket.orket` is a deprecated compatibility shim over `orket.runtime`; new imports must use `orket.runtime` directly, and shim removal is tracked on the roadmap.

Gitea webhook PR review/opened/merged handling validates consumed payload fields through Pydantic boundary models and returns `status=error`, `error=webhook_payload_validation_failed` on invalid payloads instead of propagating nested-key access errors.

Gitea webhook authenticated API calls require `https://` `GITEA_URL` by default. Plaintext `http://` is admitted only when `ORKET_GITEA_ALLOW_INSECURE=true` or `allow_insecure=True` is explicitly set for local development, and that degraded transport posture emits `gitea_webhook_insecure_url_allowed`.

Gitea webhook ingress validates `X-Gitea-Signature` against the canonical `sha256=<hex>` HMAC form, and the lazy webhook handler proxy now uses async-lock-guarded initialization so concurrent deliveries do not construct duplicate handler instances.

JWT access tokens issued through `orket/services/auth_service.py` now default to a 60-minute lifetime unless `ORKET_AUTH_TOKEN_EXPIRE_MINUTES` overrides it, include a `jti` claim on every token, and verify revocation against the SQLite token blocklist at `.orket/durable/db/auth_token_blocklist.sqlite3` resolved through `orket/runtime_paths.py`.

Gitea webhook sandbox handling accepts an injected `SandboxOrchestrator` and explicit `lifecycle_db_path`; default construction routes sandbox state through the repository-backed `SandboxOrchestrator.lifecycle_repository` rather than treating the handler-local `SandboxRegistry` as durable authority.

Gitea webhook review-cycle state now uses a workspace-derived durable DB path at `.orket/durable/db/webhook.db`, records webhook delivery ids as idempotency keys when present, skips duplicate PR review deliveries before side effects, escalates at `MAX_PR_REVIEW_CYCLES=3`, and auto-rejects at the following cycle.

Manual review deterministic defaults treat broad `TODO|FIXME` forbidden-pattern matches as `info` severity and keep `password\s*=` at `high`; operators can override the resolved policy if they want TODO/FIXME matches to block PRs.

Project memory retrieval now uses SQLite FTS5-backed search with SQL-level filtering and BM25 ordering, while `MemoryStore.remember()` deduplicates exact repeated content by SHA-256 content hash before insert so the project-memory surface no longer over-fetches recent rows or accumulate duplicate entries for the same content.

Interaction streaming now admits per-turn `stream_budget` overrides on the shared `StreamBus`, gives `model_stream_v1` a default best-effort budget of 2048 token deltas when no explicit override is supplied, and bounds retained `_turn_states` bookkeeping through TTL/LRU eviction instead of leaving per-turn stream state unbounded.

Interaction session ownership is now explicitly split: `orket/state.py` keeps transport/runtime coordination only (event broadcast queue, websocket fanout, classic runtime task tracking, and interaction-session surface presence), while `orket/streaming/manager.py` remains the sole authority for interaction session and turn state; the API wires those surfaces together through explicit interaction-session start/close registration hooks.

Webhook operator posture now exposes ingress rate limiting as a per-process surface, with `/health` returning `rate_limit_scope=per_process`, `webhook_rate_limit_per_minute`, and `worker_count_hint`, while `.env.example` documents sizing `ORKET_RATE_LIMIT` against the configured worker count when no shared limiter backend is present.

Review-bundle replay validation now raises `ReviewBundleError` carrying explicit `error_code` and `field` metadata instead of untyped string-only `ValueError` failures, and the CLI replay surface preserves those structured bundle error codes in replay failure output.

Streaming turn state is purged after authoritative commit publication while preserving already-queued terminal subscriber events; subscriber queues are bounded by the configured best-effort plus bounded producer budgets, duplicate `COMMIT_FINAL` publication fails closed, and best-effort producer budget exhaustion emits one `STREAM_TRUNCATED` advisory event carrying dropped sequence ranges.

LPJ-C32 append-only run-ledger framing remains `uint32_be payload_len | payload_bytes | uint32_be crc32c(payload_bytes)` with Castagnoli CRC-32C as specified in `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`; runtime checksum calculation uses the declared `google-crc32c` dependency instead of a local hand-rolled table, and IEEE `binascii.crc32` is intentionally not compatible with existing ledger frames.

Dual-write run-ledger recovery now exposes a one-time `AsyncDualModeLedgerRepository.initialize()` seam guarded by `_recovery_run_once`; primary runtime startup/entry surfaces call that initializer before using the repository, and recovery no longer reruns its pending-intent replay loop on every repository operation.

`ExecutionPipeline` now keeps construction, state-mode helpers, the epic-orchestrator builder, and module entrypoints in `orket/runtime/execution/execution_pipeline.py`; public card dispatch, compatibility wrappers, Gitea loop entry wrapping, resume/collection helpers, run-summary materialization, runtime artifact collection, artifact provenance, and ledger/protocol event helpers live in `orket/runtime/execution/execution_pipeline_card_dispatch.py`, `orket/runtime/execution/execution_pipeline_resume.py`, `orket/runtime/execution/execution_pipeline_run_summary.py`, `orket/runtime/execution/execution_pipeline_runtime_artifacts.py`, `orket/runtime/execution/execution_pipeline_artifact_provenance.py`, and `orket/runtime/execution/execution_pipeline_ledger_events.py`, with flat `orket/runtime/*.py` paths preserved only as compatibility aliases.

## Drift Rule

If any command, path, or source in this file changes, the corresponding source documents and implementation entrypoints must be updated in the same change unless the user explicitly directs otherwise.
