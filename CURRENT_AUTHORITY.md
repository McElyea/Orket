# CURRENT_AUTHORITY.md

Last updated: 2026-03-24

This file is the current canonical authority snapshot for high-impact runtime and governance paths.

It is intentionally narrow:
1. Agent behavior rules remain in `AGENTS.md`.
2. Contributor workflow rules remain in `docs/CONTRIBUTOR.md`.
3. This file tracks what is authoritative right now.

This file does not define:
1. all supported features,
2. all experimental surfaces,
3. all repository conventions.

It defines only the currently authoritative paths that agents and contributors must treat as canonical unless explicitly directed otherwise.

## Current Canonical Paths

1. Install/bootstrap: `python -m pip install -e ".[dev]"`
2. Default runtime: `python main.py`
3. Named rock runtime: `python main.py --rock <rock_name>`
4. API runtime: `python server.py`
5. Canonical test command: `python -m pytest -q`
6. Active docs index: `docs/README.md`
7. Active roadmap: `docs/ROADMAP.md`
8. Active contributor workflow: `docs/CONTRIBUTOR.md`
9. Long-lived specs root: `docs/specs/`
10. Staged artifact candidate index: `benchmarks/staging/index.json`
11. Published artifact index: `benchmarks/published/index.json`
12. Canonical provider runtime target selection: `orket/runtime/provider_runtime_target.py`
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
27. Canonical control-plane durable store path: `.orket/durable/db/control_plane_records.sqlite3` via `orket/runtime_paths.py`
28. Canonical governed turn-tool path defaults to `issue:<issue_id>` namespace scope and must fail closed on broader scope declarations, publishes a pre-effect `resume_new_attempt_from_checkpoint` checkpoint boundary for each governed attempt, now publishes terminal `terminate_run` recovery decisions for pre-effect blocked and post-effect failed governed execution with checkpoint/effect preconditions and blocked continuation actions, and on `resume_mode` may only perform supervisor-owned checkpoint-backed new-attempt recovery for unfinished pre-effect runs while unfinished post-effect or effect-boundary-uncertain attempts publish explicit reconciliation records plus `require_reconciliation_then_decide` recovery authority and then close immediately into terminal `reconciliation_closed` truth with a second reconciliation-rationalized `terminate_run` decision; completed successful governed turn re-entry now reuses durable step and operation artifacts before prompt/model execution and before checkpoint artifact rewrite rather than rerunning the model and only reusing finalized truth later, and governed runs already in terminal or recovery-blocked states now fail closed before model invocation and before checkpoint artifact rewrite instead of drifting into new tool execution via `orket/application/workflows/turn_tool_dispatcher_support.py`, `orket/application/workflows/tool_invocation_contracts.py`, `orket/application/workflows/turn_executor_control_plane.py`, `orket/application/services/turn_tool_control_plane_service.py`, `orket/application/services/turn_tool_control_plane_recovery.py`, `orket/application/services/turn_tool_control_plane_reconciliation.py`, and `orket/application/services/turn_tool_control_plane_closeout.py`
29. Canonical Gitea state worker path now publishes one lease-backed control-plane run per claimed card and lease epoch, a first-class claim reservation before the initial claim mutation, explicit reservation-to-lease linkage on the claimed lease, promotion of that reservation only after the `ready -> in_progress` claim transition succeeds, a pre-effect `resume_forbidden` checkpoint from the claimed-card observation, worker-owned claim/finalize steps, effect-journal entries for observed state transitions, terminal recovery decisions on failure, and pre-effect claim-failure closeout with reservation invalidation, `lease_uncertain`, a reconciliation record, and reconciliation-closed final truth when the initial claim transition fails via `orket/application/services/gitea_state_control_plane_execution_service.py`, `orket/application/services/gitea_state_control_plane_checkpoint_service.py`, `orket/application/services/gitea_state_control_plane_claim_failure_service.py`, and `orket/application/services/gitea_state_control_plane_reservation_service.py`
30. Canonical approval-gated admission paths now publish a first-class `operator_hold_reservation` on request creation or admission, resolve that reservation on approval decision, and publish first-class guard-review operator commands on the pending-gate surface for supported non-tool resolutions, while approval list and detail views surface the latest reservation and approval-surface operator-command summary, plus `control_plane_target_ref`, the latest target-side run and attempt summary when durable execution truth exists including namespace scope, admission decision receipt, policy snapshot id, configuration snapshot id, creation timestamp, and attempt count, the latest target-side step summary including namespace scope, capability used, output ref, resources touched, and receipt refs, the latest target-side checkpoint summary including creation timestamp, invalidation and dependency detail, policy digest, integrity verification ref, required reobservation class, acceptance decision timestamp, acceptance supervisor authority, evaluated policy digest, dependent effect or reservation or lease refs, and rejection reasons, the latest target-side effect-journal summary including step id, publication sequence, intended target, observed result ref, authorization-basis ref, publication timestamp, integrity verification ref, prior-entry linkage, contradiction or supersession refs, entry digest, and uncertainty, the latest target-side operator action summary including receipt refs, affected transition refs, and affected resource refs, the latest target-side reservation summary including reservation kind, reservation invalidation basis, supervisor authority, and promotion linkage, and the latest target-side final-truth summary including fuller classifications, authoritative result ref, and authority sources when the approval payload names a governed target or when authoritative approval-reservation truth names that governed target on the kernel approval path via `orket/application/services/tool_approval_control_plane_reservation_service.py`, `orket/application/services/tool_approval_control_plane_operator_service.py`, `orket/application/services/pending_gate_control_plane_operator_service.py`, `orket/application/workflows/orchestrator_ops.py`, `orket/interfaces/routers/kernel.py`, `orket/orchestration/engine_approvals.py`, `orket/orchestration/approval_control_plane_read_model.py`, and `orket/application/workflows/orchestrator.py`
31. The standalone coordinator API now publishes first-class non-hedged `ReservationRecord` truth for claim admission, explicitly promotes those reservations to lease authority on successful claim, publishes `LeaseRecord` expiry on the open-cards observation path in addition to claim, renew, expiry-before-reclaim, and release transitions, and exposes the latest reservation and lease summary on list, claim, renew, complete, and fail responses including reservation kind, reservation basis, reservation supervisor authority, promotion rule, lease resource id, lease expiry basis, lease cleanup eligibility rule, granted timestamp, publication timestamp, and last confirmed observation via `orket/interfaces/coordinator_api.py`, `orket/application/services/coordinator_control_plane_reservation_service.py`, and `orket/application/services/coordinator_control_plane_lease_service.py`
32. Canonical sandbox operator views now surface the latest reconciliation summary when durable control-plane truth exists, including `control_plane_reconciliation_id`, `control_plane_divergence_class`, and `control_plane_safe_continuation_class`, alongside run, attempt, reservation, lease, checkpoint, effect-journal including latest intended target, observed result ref, authorization-basis ref, integrity verification ref, and uncertainty classification, latest operator-command including receipt refs, and fuller final-truth classifications including result, closure basis, terminality basis, evidence sufficiency, residual uncertainty, degradation, authoritative result ref, and authority sources via `orket/application/services/sandbox_lifecycle_view_service.py`
33. Canonical governed kernel-action replay and audit views now surface the latest reservation summary for the run when durable control-plane truth exists, including operator-hold reservations created by approval-required admission, the latest step summary including namespace scope, resources touched, and receipt refs, the latest operator action including receipt refs, and fuller final-truth classifications including evidence sufficiency, residual uncertainty, degradation, terminality basis, authoritative result ref, and authority sources via `orket/application/services/kernel_action_control_plane_view_service.py` and `orket/interfaces/routers/kernel.py`

## Machine-Readable Authority Map (v1)

```json
{
  "version": 1,
  "last_updated": "2026-03-24",
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
      "cli_named_rock": "python main.py --rock <rock_name>",
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
      "terraform_plan_review_live_smoke_output_path": ".orket/durable/observability/terraform_plan_review_live_smoke.json",
      "artifact_review_policy": "docs/process/PUBLISHED_ARTIFACTS_POLICY.md",
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/CONTRIBUTOR.md",
        "docs/architecture/event_taxonomy.md",
        "docs/process/PUBLISHED_ARTIFACTS_POLICY.md",
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
        "lease_record"
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
        "orket/application/workflows/tool_invocation_contracts.py",
        "orket/application/workflows/turn_tool_dispatcher.py",
        "orket/application/workflows/turn_tool_dispatcher_control_plane.py",
        "orket/application/workflows/turn_tool_dispatcher_protocol.py",
        "orket/application/workflows/turn_tool_dispatcher_support.py",
        "orket/application/services/control_plane_publication_service.py",
        "orket/application/services/coordinator_control_plane_lease_service.py",
        "orket/application/services/coordinator_control_plane_reservation_service.py",
        "orket/application/services/gitea_state_control_plane_checkpoint_service.py",
        "orket/application/services/gitea_state_control_plane_claim_failure_service.py",
        "orket/application/services/gitea_state_control_plane_execution_service.py",
        "orket/application/services/gitea_state_control_plane_lease_service.py",
        "orket/application/services/gitea_state_control_plane_reservation_service.py",
        "orket/application/services/gitea_state_worker.py",
        "orket/application/services/kernel_action_control_plane_service.py",
        "orket/application/services/kernel_action_control_plane_operator_service.py",
        "orket/application/services/kernel_action_control_plane_view_service.py",
        "orket/application/services/pending_gate_control_plane_operator_service.py",
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
        "orket/application/services/turn_tool_control_plane_recovery.py",
        "orket/application/services/turn_tool_control_plane_reconciliation.py",
        "orket/application/services/turn_tool_control_plane_service.py",
        "orket/application/services/turn_tool_control_plane_support.py",
        "orket/interfaces/routers/approvals.py",
        "orket/interfaces/coordinator_api.py",
        "orket/interfaces/routers/kernel.py",
        "orket/kernel/v1/nervous_system_runtime.py",
        "orket/runtime/execution_pipeline.py",
        "orket/runtime/tool_invocation_policy_contract.py",
        "orket/runtime/protocol_error_codes.py",
        "orket/application/services/sandbox_lifecycle_view_service.py",
        "orket/adapters/storage/async_control_plane_record_repository.py",
        "orket/adapters/storage/async_control_plane_execution_repository.py",
        "docs/projects/ControlPlane/orket_control_plane_packet/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md"
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
        "lease_record"
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
