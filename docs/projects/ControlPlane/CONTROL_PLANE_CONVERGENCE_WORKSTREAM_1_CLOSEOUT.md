# Control-Plane Convergence Workstream 1 Closeout
Last updated: 2026-03-26
Status: Partial closeout artifact
Owner: Orket Core
Workstream: 1 - Canonical workload, run, and attempt promotion

## Objective

Record the slices already landed under Workstream 1 without over-claiming workstream completion.

Closed or narrowed slices captured here:
1. canonical workload projection family for cards, ODR, and extension workloads
2. shared governed workload catalog for the main control-plane publishers
3. canonical sandbox workload publication on the default runtime path
4. invocation-scoped top-level cards epic run, attempt, and start-step publication
5. manual review-run run, attempt, and start-step publication plus control-plane-backed read projection
6. cards `run_summary.json` read projection of durable cards-epic run, attempt, and start-step truth
7. fresh `run_start_artifacts` `run_identity.json` demotion to explicit session-bootstrap projection-only evidence
8. fresh `retry_classification_policy` demotion to explicit non-authoritative attempt-history guidance
9. fresh review-run manifests now explicitly point execution-state authority at durable control-plane records while marking lane outputs non-authoritative for run/attempt state

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `Workload` | `conflicting` | `conflicting` | Added one canonical projection family plus a shared governed workload catalog covering cards, ODR, extensions, sandbox, top-level cards epic execution, and manual review-run execution. Universal start-path authority still does not exist. |
| `Run` | `partial` | `partial` | Added first-class top-level cards epic run publication and first-class manual review-run publication, with review manifests, results, and CLI projection now reading or pointing at durable control-plane state, cards `run_summary.json` now projecting persisted cards-epic run or attempt or step truth instead of inventing a separate cards-summary run state, and fresh `run_start_artifacts` now explicitly mark `run_identity` as session-bootstrap `projection_only` evidence. Legacy observability and broader summary surfaces still remain. |
| `Attempt` | `partial` | `partial` | Added first-class top-level cards epic attempt publication and manual review-run attempt publication, and fresh retry-classification snapshots now explicitly declare `attempt_history_authoritative=false` so retry policy stops looking like hidden attempt truth. Broader retry and resume behavior still remains service-local in some runtime paths. |
| `Step` | `partial` | `partial` | Added top-level cards epic invocation-start step publication and manual review-run `review_run_start` step publication. Broader runtime execution still lacks one shared step surface. |

## Code, entrypoints, tests, and docs changed

Code and entrypoints changed across the recorded Workstream 1 slices:
1. `orket/core/contracts/workload_identity.py`
2. `orket/application/services/control_plane_workload_catalog.py`
3. `orket/application/services/cards_epic_control_plane_service.py`
4. `orket/application/services/review_run_control_plane_service.py`
5. `orket/application/review/run_service.py`
6. `orket/runtime/workload_adapters.py`
7. `orket/runtime/execution_pipeline.py`
8. `orket/services/sandbox_orchestrator.py`
9. `orket/application/services/sandbox_control_plane_execution_service.py`
10. `scripts/odr/run_arbiter.py`
11. extension workload and provenance surfaces under `orket/extensions/`
12. governed workload consumers under `orket/application/services/` for kernel action, orchestrator issue, orchestrator scheduler, turn-tool, and Gitea worker execution
13. review CLI projection path in `orket/interfaces/orket_bundle_cli.py`
14. cards run-summary control-plane projection path in `orket/runtime/run_summary.py` and `orket/runtime/run_summary_control_plane.py`
15. run-start bootstrap identity demotion path in `orket/runtime/run_start_artifacts.py`
16. retry classification demotion path in `orket/runtime/retry_classification_policy.py`
17. review manifest execution-authority demotion path in `orket/application/review/models.py` and `orket/application/review/run_service.py`

Representative tests changed or added:
1. `tests/core/test_workload_contract_models.py`
2. `tests/runtime/test_cards_workload_adapter.py`
3. `tests/runtime/test_extension_components.py`
4. `tests/runtime/test_extension_manager.py`
5. `tests/application/test_control_plane_workload_catalog.py`
6. `tests/application/test_execution_pipeline_workload_shell.py`
7. `tests/application/test_execution_pipeline_cards_epic_control_plane.py`
8. `tests/application/test_review_run_service.py`
9. `tests/integration/test_review_run_live_paths.py`
10. `tests/interfaces/test_review_cli.py`
11. existing integration coverage for turn executor, Gitea worker, orchestrator issue, orchestrator scheduler, and sandbox lifecycle paths

Docs changed:
1. `docs/specs/WORKLOAD_CONTRACT_V1.md`
2. `docs/specs/REVIEW_RUN_V0.md`
3. `docs/guides/REVIEW_RUN_CLI.md`
4. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
5. `CURRENT_AUTHORITY.md`

## Proof executed

Proof type: `structural`
Observed result: `success`

Commands executed for the slices recorded here:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/core/test_workload_contract_models.py tests/runtime/test_cards_workload_adapter.py tests/application/test_execution_pipeline_workload_shell.py tests/application/test_run_arbiter_workload_contract.py tests/runtime/test_extension_components.py tests/runtime/test_extension_manager.py`
   Result: `46 passed`
2. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_workload_catalog.py tests/application/test_kernel_action_control_plane_service.py tests/application/test_orchestrator_issue_control_plane_service.py tests/application/test_orchestrator_scheduler_control_plane_service.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py`
   Result: `41 passed`
3. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_workload_catalog.py tests/application/test_sandbox_control_plane_execution_service.py tests/application/test_sandbox_control_plane_effect_service.py tests/integration/test_sandbox_lifecycle_reconciliation_service.py tests/integration/test_sandbox_orchestrator_lifecycle.py`
   Result: `22 passed`
4. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_execution_pipeline_cards_epic_control_plane.py tests/application/test_execution_pipeline_workload_shell.py tests/application/test_execution_pipeline_session_status.py`
   Result: `8 passed`
5. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "runtime_contract_bootstrap_artifacts or keeps_run_identity_immutable"`
   Result: `2 passed, 12 deselected`
6. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py tests/application/test_control_plane_workload_catalog.py`
   Result: `14 passed`
7. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary.py tests/application/test_execution_pipeline_cards_epic_control_plane.py tests/application/test_execution_pipeline_run_ledger.py -k "control_plane or summary or incomplete or failed or terminal_failure or runtime_contract_bootstrap_artifacts or keeps_run_identity_immutable"`
   Result: `14 passed, 8 deselected`
8. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
9. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_start_artifacts.py tests/application/test_execution_pipeline_run_ledger.py -k "run_identity or runtime_contract_bootstrap_artifacts or keeps_run_identity_immutable"`
   Result: `4 passed, 38 deselected`
10. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_start_artifacts.py tests/application/test_execution_pipeline_cards_epic_control_plane.py tests/application/test_execution_pipeline_run_ledger.py -k "control_plane or summary or run_identity or incomplete or failed or terminal_failure or runtime_contract_bootstrap_artifacts or keeps_run_identity_immutable"`
    Result: `16 passed, 34 deselected`
11. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_retry_classification_policy.py tests/runtime/test_run_start_artifacts.py tests/application/test_execution_pipeline_run_ledger.py -k "retry_classification_policy or run_identity or runtime_contract_bootstrap_artifacts"`
    Result: `8 passed, 38 deselected`
12. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py`
    Result: `11 passed`

## Compatibility exits

Workstream 1 compatibility exits affected by the slices recorded here:
1. `CE-01` narrowed, not closed
   Reason: a canonical projection family and shared governed workload catalog now exist, but the `Workload` row remains `conflicting` because start-path authority is not yet universal.
2. `CE-02` narrowed, not closed
   Reason: manual review runs now publish first-class run, attempt, and step truth, fresh review manifests now explicitly point execution-state authority at durable control-plane records while marking lane outputs non-authoritative for run or attempt state, the review result or CLI path now reads durable control-plane state, cards `run_summary.json` now projects durable cards-epic run or attempt or step state from persisted control-plane records, fresh `run_start_artifacts` now explicitly mark `run_identity` as session-bootstrap projection-only evidence, and fresh retry-classification snapshots now explicitly declare `attempt_history_authoritative=false`. Broader `run_summary.py` closure projections, legacy retry or lane behavior, and broader observability surfaces still survive.

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. `orket/runtime/run_start_artifacts.py`
   Reason: immutable session-scoped runtime bootstrap evidence is still valid as a projection and evidence package. Fresh `run_identity` payloads now explicitly mark that surface as session-bootstrap projection-only evidence, but it still cannot truthfully hold invocation-scoped cards epic run ids.
2. `orket/runtime/run_summary.py`
   Reason: legacy runtime summary output remains an active projection surface for cards runs and other runtime proof paths. Cards summaries now project durable cards-epic run or attempt or step state from persisted records, but the broader summary surface is not yet demoted lane-wide to projection-only closure behavior.
3. `orket/application/review/lanes/`
   Reason: deterministic and model-assisted review lanes remain valid evidence-producing review components. Fresh review manifests now explicitly mark those lane outputs non-authoritative for run or attempt state, but not all touched read paths or replay surfaces are fully framed that way yet.
4. `orket/runtime/retry_classification_policy.py`
   Reason: retry policy still exists outside one universal append-only attempt history model for all runtime paths. Fresh snapshots now explicitly declare that policy surface non-authoritative for attempt history, but service-local retry behavior still survives.

## Remaining gaps and blockers

Workstream 1 is not complete.

Remaining gaps:
1. `Workload` still lacks one universal governed start-path authority across every runtime start path.
2. `Run` still has legacy read surfaces under `run_start_artifacts.py`, `run_summary.py`, and observability trees that can still look authoritative.
3. `Attempt` still is not universal across broader retry and recovery behavior.
4. `Step` still is not universal across broader runtime execution paths.
5. `CE-01` and `CE-02` both remain open.

Current blocker on the next obvious `CE-02` cut:
1. `run_start_artifacts.py` is session-scoped and immutable, while top-level cards epic control-plane run ids are invocation-scoped. Forcing invocation-scoped identity into that surface would create stale or dishonest authority on same-session reentry.

## Authority-story updates landed with these slices

The following authority docs were updated in the same slices recorded here:
1. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/WORKLOAD_CONTRACT_V1.md`
4. `docs/specs/REVIEW_RUN_V0.md`
5. `docs/guides/REVIEW_RUN_CLI.md`

## Verdict

Workstream 1 has materially narrowed `CE-01` and `CE-02`, but it is still open.

The next truthful Workstream 1 work should focus on demoting remaining legacy run and attempt read surfaces without pushing invocation-scoped control-plane identity into immutable session-scoped artifacts.
