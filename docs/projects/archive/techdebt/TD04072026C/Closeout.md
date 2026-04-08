# TD04072026C Techdebt Closeout

Last updated: 2026-04-07
Status: Completed
Owner: Orket Core

## Scope

This archive packet closes the finite Priority Now techdebt remediation lane formerly tracked at `docs/projects/techdebt/remediation_plan.md`.

Archived lane files:
1. `remediation_plan.md`
2. `code_review.md`
3. `behavioral_review.md`

## Outcome

Closed all remediation plan action groups:
1. Phase 1 correctness blockers: P1-A through P1-F.
2. Phase 2 security and credential safety: P2-A through P2-C.
3. Phase 3 robustness and error surface: P3-A through P3-K.
4. Phase 4 behavioral and policy correctness: P4-A through P4-G.
5. Phase 5 documentation and observability: P5-A through P5-C.

The active `docs/projects/techdebt/` folder returns to standing-maintenance-only authority.

## Proof Summary

Proof type: unit, contract, integration, focused structural lint, and local workflow structural check.

Observed path: primary.

Observed result: success.

Verified:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/adapters/test_async_card_repository.py tests/adapters/test_async_session_repository.py tests/application/test_review_run_id.py tests/application/test_agent_model_family_registry.py tests/application/test_exception_hierarchy.py tests/integration/test_control_plane_checkpoint_publication.py tests/application/test_control_plane_publication_service.py tests/application/test_review_run_service.py tests/adapters/test_gitea_webhook.py tests/adapters/test_gitea_state_adapter.py tests/interfaces/test_webhook_factory.py tests/application/test_schema_environment_config.py tests/application/test_agent_factory.py tests/adapters/test_openai_compat_runtime.py tests/application/test_review_policy_resolver.py tests/application/test_model_assisted_lane.py tests/application/test_review_git_errors.py tests/adapters/test_local_model_provider_timeout.py tests/streaming/test_bus.py tests/streaming/test_manager.py tests/streaming/test_stream_test_workload.py tests/application/test_cards_odr_stage.py tests/application/test_review_deterministic_lane.py tests/adapters/test_webhook_db.py tests/application/test_async_protocol_run_ledger.py tests/application/test_async_dual_write_run_ledger.py tests/integration/policy_enforcement/test_runtime_policy_enforcement.py::test_tool_gate_violation_blocks_before_tool_execution tests/application/test_turn_tool_dispatcher_policy_enforcement.py` -> 239 passed.
2. `python -m ruff check orket/application/services/cards_odr_stage.py orket/application/review/policy_resolver.py orket/application/review/lanes/deterministic.py orket/adapters/vcs/webhook_db.py orket/adapters/vcs/gitea_webhook_handler.py orket/adapters/vcs/gitea_webhook_handlers.py orket/adapters/storage/async_protocol_run_ledger.py tests/application/test_async_dual_write_run_ledger.py tests/application/test_cards_odr_stage.py tests/application/test_review_deterministic_lane.py tests/application/test_agent_model_family_registry.py tests/adapters/test_gitea_webhook.py tests/adapters/test_webhook_db.py tests/application/test_async_protocol_run_ledger.py` -> passed.
3. `python scripts/governance/check_docs_project_hygiene.py` -> passed.
4. `git diff --check` -> passed with line-ending normalization warnings only.

## Not Verified Here

1. No live external provider was invoked.
2. No intentional live sandbox acceptance flow was run.
3. No live Gitea server or webhook delivery was exercised.
4. Repository-wide `python -m ruff check` remains blocked by pre-existing unrelated violations outside this lane.

## Remaining Drift

The dual-write intent file remains as the recovery coordination mechanism. The duplicate-on-recovery hazard is addressed by backend acknowledgement checks and idempotent lifecycle event writes, with explicit recovery tests covering single SQLite and protocol lifecycle sequences after replay. No unresolved completion-blocking drift remains for this closed lane.
