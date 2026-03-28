# Control-Plane Convergence Workstream 1 Closeout
Last updated: 2026-03-27
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
7. fresh `run_start_artifacts` `run_identity.json` demotion to explicit session-bootstrap projection-only evidence, with bootstrap reuse plus summary consumers now failing closed if that framing drifts
8. fresh `retry_classification_policy` demotion to explicit non-authoritative attempt-history guidance
9. fresh review-run manifests now explicitly point execution-state authority at durable control-plane records while marking lane outputs non-authoritative for run/attempt state
10. governed kernel direct API and async engine responses now surface canonical durable `control_plane_step_id` refs when step truth exists instead of dropping that step identity on the response contract
11. governed turn-tool protocol receipt invocation manifests now surface canonical durable `control_plane_step_id` refs when governed step truth exists instead of leaving step authority only as a bare protocol `step_id`
12. reconstructed protocol run-graph tool-call nodes now preserve canonical durable turn-tool control-plane refs, including `control_plane_step_id`, when manifest evidence exists
13. receipt-derived artifact provenance entries now preserve canonical governed turn-tool `control_plane_run_id`, `control_plane_attempt_id`, and `control_plane_step_id` refs when authoritative receipt-manifest provenance exists for the generated artifact
14. packet-2 source-attribution summaries now preserve those same canonical governed run, attempt, and step refs when the source-attribution receipt artifact already has authoritative artifact-provenance evidence
15. packet-2 narration/effect-audit entries and idempotency summaries now preserve those same canonical governed run, attempt, and step refs when authoritative protocol receipt-manifest evidence exists for the narrated effect
16. packet-1 provenance now preserves those same canonical governed run, attempt, and step refs when the selected primary artifact output is backed by authoritative artifact-provenance evidence
17. persisted review-lane deterministic-decision and model-assisted-critique artifacts now explicitly mark execution-state authority as `control_plane_records`, mark lane outputs non-authoritative for execution state, and carry canonical review-run run, attempt, and step refs when durable review-run publication exists
18. human review CLI output now reads the durable review control-plane summary strongly enough to surface run/attempt state, start-step kind, and canonical run/attempt/step refs instead of compressing that surface to state-only text
19. cards `run_summary.json` `control_plane` block now explicitly fails closed unless it keeps declaring `projection_only=true` with `projection_source=control_plane_records`
20. review-run result and CLI `control_plane` summary now explicitly declares `projection_only=true` with `projection_source=control_plane_records` and fails closed if that framing drifts
21. review-run manifest plus deterministic/model-assisted lane artifacts now fail closed if their `execution_state_authority=control_plane_records` and non-authoritative execution-state markers drift
22. `orket review replay --run-dir` now validates persisted review manifest and lane-artifact execution-authority markers before replay and fails closed if those persisted markers drift
23. review answer-key scoring now validates persisted review manifest and lane-artifact execution-authority markers before treating review bundle JSON as trustworthy evidence and fails closed if those persisted markers drift
24. review consistency-signature extraction now validates persisted review manifest and lane-artifact execution-authority markers before treating review bundle JSON as trustworthy evidence and fails closed if those persisted markers drift
25. embedded review-result `manifest` output now validates persisted execution-authority markers before leaving the process and fails closed if those markers drift
26. legacy cards `run_summary` and finalize consumers now validate reused `run_identity.json` projection framing instead of silently consuming drifted bootstrap run evidence
27. code-review probe artifact bundles now emit review-bundle execution-authority markers plus a bundle manifest so shared answer-key scoring stays aligned with fail-closed review bundle validation
28. shared probe/workload helpers, MAR audit completeness and compare surfaces, and training-data extraction now consume one shared validated legacy `run_summary.json` loader before trusting summary JSON as run evidence
29. review answer-key scoring, review consistency-signature extraction including the truncation-bounds snapshot path, and `orket review replay --run-dir` now consume shared validated review-bundle payload or artifact loaders instead of validating persisted review-bundle authority markers and then rereading lane JSON, snapshot inputs, or replay inputs ad hoc
30. governance dashboard seed metrics now validate persisted `run_ledger.summary_json` payloads against the canonical run-summary contract and sanitize persisted `run_ledger.artifact_json` through the shared validated run-ledger projection seam before deriving session-status or degrade signals, so malformed legacy summary or artifact rows register as invalid-payload signals instead of silently shaping fallback or degrade heuristics
31. API run-detail and session-status surfaces now validate persisted `run_ledger.summary_json` payloads against the canonical run-summary contract before exposing summary blocks, and run detail now also sanitizes the nested `run_ledger.summary_json` projection, so malformed legacy summary payloads fail closed to empty summary projections instead of silently shaping API-visible run state
32. API run-detail and session-status surfaces now also sanitize persisted `run_ledger.artifact_json` through the shared validated run-ledger record seam, so malformed legacy artifact payloads fail closed to empty artifact projections instead of leaking raw invalid run-ledger artifact state through API-visible run surfaces
33. direct `orket review replay --snapshot ... --policy ...` now also reuses the shared validated review-bundle artifact loader when those files target canonical bundle artifacts from one review-run directory, so replay fails closed on drifted persisted review authority markers instead of bypassing bundle validation through raw replay inputs
34. protocol/sqlite run-ledger parity consumers now also consume the shared validated run-ledger projection family, and the SQLite run-ledger adapter now preserves malformed persisted summary/artifact payload text long enough for that seam to detect it, so malformed `summary_json` or `artifact_json` payloads fail closed as explicit parity drift instead of disappearing inside the adapter or being normalized away into false-green parity
35. protocol/sqlite run-ledger parity-campaign rows and campaign telemetry now preserve side-specific invalid projection-field detail instead of collapsing malformed persisted run-ledger projection drift into generic mismatch counts
36. protocol rollout evidence bundle summaries now preserve those side-specific invalid projection-field counts instead of collapsing malformed parity drift back to generic mismatch totals
37. protocol enforce-window signoff payloads and capture manifests now preserve those same side-specific invalid projection-field counts instead of reducing malformed parity drift back to generic signoff or manifest pass-fail summaries
38. protocol cutover-readiness outputs now preserve those same side-specific invalid projection-field counts instead of flattening malformed parity drift back to generic ready or passing-window totals
39. protocol rollout, signoff, and cutover outputs now consume one shared invalid-projection detail helper instead of carrying divergent local parsing logic
40. live-acceptance pattern reporting now validates persisted `metrics_json` and `db_summary_json` row payloads and records explicit invalid-payload signals instead of silently flattening malformed rows into empty state
41. microservices unlock gating now fails closed when the live-acceptance report is missing or malformed on `run_count`, `session_status_counts`, `pattern_counters`, or `invalid_payload_signals`, or reports any non-zero invalid source-row counts instead of allowing stale or malformed live-report payloads to produce false-green unlock decisions
42. monolith variant matrix summaries now preserve normalized live-report `invalid_payload_signals`, and both monolith readiness plus matrix-stability gates now fail closed when those matrix summary counts are missing, malformed, or non-zero instead of trusting rate-only matrix summaries derived from malformed live-report rows
43. architecture pilot matrix comparison now preserves side-specific invalid-payload totals, detailed per-architecture invalid-payload maps, and failures from the underlying pilot summaries, and microservices pilot stability now fails closed when that persisted comparison detail is missing, malformed, non-zero, or internally inconsistent with its own per-architecture invalid-payload maps instead of trusting architecture delta summaries or stored totals alone
44. runtime-policy pilot-stability reads now fail closed when the persisted pilot-stability artifact is structurally malformed instead of trusting a bare `stable` flag
45. microservices pilot decision now fails closed when the persisted unlock artifact is structurally malformed instead of trusting a bare `unlocked` flag
46. runtime-policy microservices unlock reads now fail closed when the persisted unlock artifact is structurally malformed, reuse the same structural unlock-report validator as microservices pilot decision, and default to the canonical acceptance artifact paths instead of stale pre-acceptance output paths
47. runtime-policy pilot-stability reads now also fail closed when the persisted pilot-stability artifact is internally inconsistent, with the shared acceptance-report validator rejecting drift between top-level `stable` / `failures`, per-check stability evidence, and `artifact_count`
48. runtime-policy microservices unlock reads and microservices pilot decision now also fail closed when the persisted unlock artifact is internally inconsistent, with the shared acceptance-report validator rejecting drift between top-level `unlocked` / `failures` and per-criterion `ok` / `failures` detail

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `Workload` | `conflicting` | `conflicting` | Added one canonical projection family plus a shared governed workload catalog covering cards, ODR, extensions, sandbox, top-level cards epic execution, and manual review-run execution. Universal start-path authority still does not exist. |
| `Run` | `partial` | `partial` | Added first-class top-level cards epic run publication and first-class manual review-run publication, with review manifests, results, CLI projection, and persisted review lane decision/critique artifacts now reading from or pointing at durable control-plane state, and human review CLI output now surfacing canonical run refs plus durable run state instead of reducing that surface to state-only text, review-run result and CLI `control_plane` summaries now explicitly declaring `projection_only=true` with source `control_plane_records` and failing closed if that framing drifts, review-run manifests plus deterministic/model-assisted lane artifacts now also fail closed if their `execution_state_authority=control_plane_records` and non-authoritative execution-state markers drift, direct `orket review replay --snapshot ... --policy ...` now also reuses the same shared validated review-bundle artifact loader when those files target canonical bundle artifacts from one review-run directory instead of bypassing bundle validation through raw replay inputs, cards `run_summary.json` now projecting persisted cards-epic run or attempt or step truth instead of inventing a separate cards-summary run state and now failing closed if its `control_plane` block stops declaring `projection_only=true` with source `control_plane_records`, shared probe/workload helpers plus MAR audit completeness and training-data extraction now also validate legacy `run_summary.json` projection framing before trusting summary JSON as evidence, governance dashboard seed metrics now also sanitize persisted `run_ledger.artifact_json` through the shared validated run-ledger projection seam instead of silently trusting malformed artifact rows, live-acceptance pattern reporting now validates persisted `metrics_json` and `db_summary_json` row payloads before deriving counters or issue-status totals and records explicit invalid-payload signals instead of silently flattening malformed rows into empty state, monolith variant matrix summaries now preserve those normalized live-report `invalid_payload_signals`, monolith readiness plus matrix-stability gates now fail closed when those matrix summary counts are missing, malformed, or non-zero instead of trusting rate-only matrix summaries derived from malformed live-report rows, architecture pilot matrix comparison now preserves side-specific invalid-payload totals, detailed per-architecture invalid-payload maps, and failures from the underlying pilot summaries, and microservices pilot stability now fails closed when that persisted comparison detail is missing, malformed, non-zero, or internally inconsistent with its own per-architecture invalid-payload maps instead of trusting architecture delta summaries or stored totals alone, runtime-policy pilot-stability reads now fail closed when the persisted pilot-stability artifact is structurally malformed or internally inconsistent instead of trusting top-level `stable` / `failures` fields, runtime-policy unlock reads and microservices pilot decision now also fail closed when the persisted unlock artifact is structurally malformed or internally inconsistent, with the shared acceptance-report validator rejecting drift between top-level `unlocked` / `failures` and per-criterion `ok` / `failures` detail instead of trusting top-level unlock state alone, microservices unlock gating now fails closed when the live-acceptance report is missing or malformed on `run_count`, `session_status_counts`, `pattern_counters`, or `invalid_payload_signals`, or reports any non-zero invalid source-row counts instead of allowing stale or malformed live-report payloads to produce false-green unlock decisions, API run-detail and session-status surfaces now also sanitize persisted `run_ledger.artifact_json` through the same validated run-ledger record seam that already guards summary projections, protocol/sqlite run-ledger parity consumers now also fail closed on malformed persisted run-ledger summary or artifact projections while the SQLite run-ledger adapter preserves malformed persisted payload text long enough for that validation seam to detect it instead of normalizing the drift away into false-green parity, protocol/sqlite parity-campaign rows plus campaign telemetry now preserve side-specific invalid projection-field detail instead of collapsing malformed persisted projection drift into generic mismatch counts, protocol rollout evidence bundle markdown now preserves those same side-specific invalid projection-field counts instead of reducing malformed parity drift back to generic mismatch totals, protocol enforce-window signoff plus capture-manifest outputs now preserve those same invalid projection-field counts instead of flattening malformed parity drift back to generic signoff or manifest pass-fail summaries, protocol cutover-readiness outputs now preserve those same invalid projection-field counts instead of flattening malformed parity drift back to generic ready or passing-window totals, and rollout/signoff/cutover now consume one shared invalid-projection detail helper instead of carrying divergent local parsers, fresh receipt-derived artifact provenance entries plus packet-1 provenance and packet-2 source-attribution, narration/effect-audit, and idempotency summaries now preserving canonical governed `control_plane_run_id` refs when authoritative receipt-manifest provenance exists, and fresh `run_start_artifacts` now explicitly mark `run_identity` as session-bootstrap `projection_only` evidence while bootstrap reuse plus legacy run-summary/finalize consumers now fail closed if that framing drifts. Legacy observability and broader summary surfaces still remain. |
| `Attempt` | `partial` | `partial` | Added first-class top-level cards epic attempt publication and manual review-run attempt publication, persisted review lane decision/critique artifacts now preserving canonical review-run `control_plane_attempt_id` while explicitly marking execution state non-authoritative, human review CLI output now surfacing canonical attempt refs plus durable attempt state instead of reducing that surface to state-only text, fresh receipt-derived artifact provenance entries plus packet-1 provenance and packet-2 source-attribution, narration/effect-audit, and idempotency summaries now preserving canonical governed `control_plane_attempt_id` refs when authoritative receipt-manifest provenance exists, and fresh retry-classification snapshots now explicitly declare `attempt_history_authoritative=false` so retry policy stops looking like hidden attempt truth. Broader retry and resume behavior still remains service-local in some runtime paths. |
| `Step` | `partial` | `partial` | Added top-level cards epic invocation-start step publication and manual review-run `review_run_start` step publication, governed kernel direct API/async engine responses now surface canonical durable `control_plane_step_id` refs when step truth exists, governed turn-tool protocol receipt invocation manifests now preserve canonical `control_plane_step_id` refs instead of leaving step authority only as a bare protocol-local field, reconstructed protocol run-graph tool-call nodes now preserve those canonical refs during graph projection, persisted review lane decision/critique artifacts now preserve canonical review-run `control_plane_step_id` while explicitly marking execution state non-authoritative, human review CLI output now surfaces canonical step refs plus start-step kind instead of reducing that surface to state-only text, and receipt-derived artifact provenance plus packet-1 provenance and packet-2 source-attribution, narration/effect-audit, and idempotency summaries now preserve canonical governed `control_plane_step_id` refs when authoritative receipt-manifest provenance exists. Broader runtime execution still lacks one shared step surface. |

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
18. governed kernel response-step projection path in `orket/application/services/kernel_action_control_plane_view_service.py`, `orket/interfaces/routers/kernel.py`, and `orket/orchestration/engine.py`
19. governed turn-tool protocol manifest control-plane step projection path in `orket/application/workflows/tool_invocation_contracts.py` and `orket/application/workflows/turn_tool_dispatcher_protocol.py`
20. governed protocol run-graph control-plane ref projection path in `orket/runtime/run_graph_reconstruction.py`
21. receipt-derived artifact provenance control-plane ref projection path in `orket/runtime/execution_pipeline.py` and `orket/runtime/run_summary_artifact_provenance.py`
22. packet-1 provenance control-plane ref projection path in `orket/runtime/execution_pipeline.py` and `orket/runtime/run_summary.py`
23. packet-2 source-attribution, narration/effect-audit, and idempotency control-plane ref projection path in `orket/runtime/phase_c_runtime_truth.py` and `orket/runtime/run_summary_packet2.py`
24. review-lane decision and critique artifact execution-authority demotion path in `orket/application/review/models.py` and `orket/application/review/run_service.py`
25. human review CLI control-plane ref projection path in `orket/interfaces/orket_bundle_cli.py`
26. review-run control-plane summary projection validation helper in `orket/application/review/control_plane_projection.py`
27. review replay bundle authority validation plus shared replay-artifact loader path in `orket/application/review/bundle_validation.py` and `orket/interfaces/orket_bundle_cli.py`, including direct `--snapshot` plus `--policy` replay when those files target canonical bundle artifacts from one run directory
28. review answer-key scoring authority validation plus shared bundle-artifact consumption path in `scripts/reviewrun/score_answer_key.py`
29. review consistency-signature authority validation plus shared replay-artifact consumption path, including truncation-bounds snapshot loading, in `scripts/reviewrun/run_1000_consistency.py`
30. review-result manifest authority validation path in `orket/application/review/models.py`
31. run-identity projection validation path in `orket/runtime/run_start_artifacts.py`, `orket/runtime/run_summary.py`, and `orket/runtime/execution_pipeline.py`
32. code-review probe bundle authority alignment path in `scripts/workloads/code_review_probe.py`, `scripts/workloads/code_review_probe_support.py`, and `scripts/workloads/code_review_probe_reporting.py`
33. shared validated legacy run-summary loader in `scripts/common/run_summary_support.py` plus consumer adoption in `scripts/probes/probe_support.py`, `scripts/audit/audit_support.py`, `scripts/audit/compare_two_runs.py`, and `scripts/training/extract_training_data.py`
34. shared validated review-bundle payload and artifact loaders in `orket/application/review/bundle_validation.py`
35. governance dashboard seed run-ledger summary/artifact validation path in `scripts/governance/build_runtime_truth_dashboard_seed.py`
36. API run-ledger summary validation and nested run-detail run-ledger summary sanitization path in `orket/application/services/run_ledger_summary_projection.py` and `orket/interfaces/api.py`
37. API run-ledger artifact projection sanitization path in `orket/application/services/run_ledger_summary_projection.py` and `orket/interfaces/api.py`
38. direct review replay canonical bundle-path validation reuse in `orket/application/review/bundle_validation.py` and `orket/interfaces/orket_bundle_cli.py`
39. shared runtime run-ledger projection normalization plus fail-closed parity/read path in `orket/runtime/run_ledger_projection.py`, `orket/application/services/run_ledger_summary_projection.py`, `orket/runtime/run_ledger_parity.py`, and `orket/adapters/storage/async_repositories.py`
40. protocol/sqlite run-ledger parity-campaign invalid-projection detail preservation path in `orket/runtime/protocol_ledger_parity_campaign.py`
41. protocol rollout evidence markdown invalid-projection detail preservation path in `scripts/protocol/publish_protocol_rollout_artifacts.py`
42. protocol enforce-window signoff and capture-manifest invalid-projection detail preservation path in `scripts/protocol/record_protocol_enforce_window_signoff.py` and `scripts/protocol/run_protocol_enforce_window_capture.py`
43. protocol cutover-readiness invalid-projection detail preservation path in `scripts/protocol/check_protocol_enforce_cutover_readiness.py`
44. shared protocol invalid-projection detail normalization path in `scripts/protocol/parity_projection_support.py`
45. live-acceptance row payload validation and invalid-signal reporting path in `scripts/acceptance/report_live_acceptance_patterns.py`
46. shared live-acceptance report contract validation plus microservices unlock fail-closed path in `orket/application/services/microservices_acceptance_reports.py` and `scripts/acceptance/check_microservices_unlock.py`
47. monolith variant matrix invalid-signal preservation plus monolith readiness and matrix-stability fail-closed path in `scripts/acceptance/run_monolith_variant_matrix.py`, `scripts/acceptance/check_monolith_readiness_gate.py`, and `scripts/acceptance/check_microservices_unlock.py`
48. architecture pilot matrix comparison invalid-signal preservation plus shared comparison-validation and microservices pilot stability fail-closed path in `scripts/acceptance/run_architecture_pilot_matrix.py`, `scripts/acceptance/check_microservices_pilot_stability.py`, and `orket/application/services/microservices_acceptance_reports.py`
49. runtime-policy pilot-stability report validation path in `orket/application/services/runtime_policy.py`
50. microservices pilot decision unlock-report validation path in `scripts/acceptance/decide_microservices_pilot.py`
51. shared microservices acceptance-report normalization plus runtime-policy unlock-report validation path in `orket/application/services/microservices_acceptance_reports.py`, `orket/application/services/runtime_policy.py`, and `scripts/acceptance/decide_microservices_pilot.py`
52. shared microservices acceptance-report internal-consistency validation plus runtime-policy pilot-stability hardening path in `orket/application/services/microservices_acceptance_reports.py` and `orket/application/services/runtime_policy.py`
53. shared microservices acceptance-report internal-consistency validation plus runtime-policy and pilot-decision unlock-report hardening path in `orket/application/services/microservices_acceptance_reports.py`

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
12. `tests/interfaces/test_api_kernel_lifecycle.py`
13. `tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py`
14. `tests/application/test_orchestration_engine_kernel_async.py`
15. `tests/application/test_turn_artifact_writer.py`
16. `tests/application/test_async_protocol_run_ledger.py`
17. `tests/runtime/test_protocol_receipt_materializer.py`
18. `tests/integration/test_turn_executor_control_plane.py`
19. `tests/runtime/test_run_graph_reconstruction.py`
20. `tests/runtime/test_run_summary_artifact_provenance.py`
21. `tests/runtime/test_run_summary_packet2.py`
22. `tests/application/test_execution_pipeline_run_ledger.py`
23. `tests/runtime/test_run_summary_packet1.py`
24. `tests/application/test_review_run_service.py`
25. `tests/interfaces/test_review_cli.py`
26. `tests/runtime/test_run_summary.py`
27. `tests/runtime/test_run_summary_projection_validation.py`
28. `tests/application/test_reviewrun_answer_key_scoring.py`
29. `tests/application/test_reviewrun_consistency.py`
30. `tests/application/test_review_run_result_contract.py`
31. `tests/runtime/test_run_identity_projection.py`
32. `tests/application/test_code_review_probe.py`
33. `tests/scripts/test_audit_phase2.py`
34. `tests/scripts/test_run_summary_projection_consumers.py`
35. `tests/application/test_review_bundle_validation.py`
36. `tests/scripts/test_common_run_summary_support.py`
37. `tests/scripts/test_build_runtime_truth_dashboard_seed.py`
38. `tests/application/test_reviewrun_consistency.py`
39. `tests/interfaces/test_api.py`
40. `tests/interfaces/test_review_cli.py`
41. `tests/runtime/test_run_ledger_parity.py`
42. `tests/scripts/test_compare_run_ledger_backends.py`
43. `tests/runtime/test_protocol_ledger_parity_campaign.py`
44. `tests/interfaces/test_cli_protocol_parity_campaign.py`
45. `tests/interfaces/test_sessions_router_protocol_replay.py`
46. `tests/scripts/test_run_protocol_ledger_parity_campaign.py`
47. `tests/scripts/test_publish_protocol_rollout_artifacts.py`
48. `tests/scripts/test_record_protocol_enforce_window_signoff.py`
49. `tests/scripts/test_run_protocol_enforce_window_capture.py`
50. `tests/scripts/test_check_protocol_enforce_cutover_readiness.py`
51. `tests/scripts/test_protocol_parity_projection_support.py`
52. `tests/application/test_live_acceptance_reporting.py`
53. `tests/application/test_microservices_unlock_gate.py`
54. `tests/application/test_monolith_matrix_and_gate.py`
55. `tests/application/test_architecture_pilot_matrix_script.py`
56. `tests/application/test_microservices_pilot_stability.py`
57. `tests/application/test_microservices_pilot_decision.py`
58. `tests/application/test_microservices_acceptance_reports.py`
59. `tests/interfaces/test_api.py`

Docs changed:
1. `docs/specs/WORKLOAD_CONTRACT_V1.md`
2. `docs/specs/REVIEW_RUN_V0.md`
3. `docs/guides/REVIEW_RUN_CLI.md`
4. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
5. `CURRENT_AUTHORITY.md`
6. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`
7. `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`
8. `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`
9. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
10. `docs/specs/REVIEW_RUN_V0.md`
11. `docs/guides/REVIEW_RUN_CLI.md`
12. `docs/specs/PROTOCOL_LEDGER_PARITY_CAMPAIGN_SCHEMA.md`

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
    Result: `13 passed`
13. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_kernel_action_control_plane_view_service.py tests/interfaces/test_api_kernel_lifecycle.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py tests/application/test_orchestration_engine_kernel_async.py`
    Result: `34 passed`
14. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_graph_reconstruction.py tests/application/test_turn_artifact_writer.py tests/application/test_async_protocol_run_ledger.py tests/runtime/test_protocol_receipt_materializer.py tests/integration/test_turn_executor_control_plane.py tests/application/test_kernel_action_control_plane_view_service.py tests/interfaces/test_api_kernel_lifecycle.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py tests/application/test_orchestration_engine_kernel_async.py`
    Result: `81 passed`
15. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_artifact_provenance.py tests/runtime/test_run_summary_packet2.py tests/application/test_execution_pipeline_run_ledger.py -k "artifact_provenance or source_attribution or narration_to_effect_audit or idempotency"`
    Result: `8 passed, 16 deselected`
16. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary.py -k "control_plane_projection or control_plane_reconstruction"`
    Result: `2 passed, 4 deselected`
17. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_packet1.py -k "provenance_preserves_control_plane_refs or reconstruction_matches_emitted_summary"`
    Result: `2 passed, 12 deselected`
18. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_packet2.py -k "phase_c_contract_allows_non_repair_sections or source_attribution_preserves_control_plane_refs or reconstruction_matches_emitted_summary_for_phase_c_sections"`
   Result: `3 passed, 3 deselected`
19. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_summary_projection_validation.py -k "control_plane_projection or control_plane_reconstruction or control_plane_projection_source_invalid or control_plane_projection_only_invalid"`
   Result: `4 passed, 10 deselected`
20. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/interfaces/test_review_cli.py tests/integration/test_review_run_live_paths.py -k "control_plane or projection"`
   Result: `3 passed, 11 deselected`
21. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py -k "execution_state_authority or authoritative or control_plane"`
   Result: `6 passed, 4 deselected`
22. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_review_cli.py -k "replay or control_plane"`
   Result: `4 passed, 2 deselected`
23. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_reviewrun_answer_key_scoring.py`
   Result: `4 passed`
24. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_reviewrun_consistency.py`
   Result: `2 passed`
25. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_result_contract.py`
   Result: `1 passed`
26. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_identity_projection.py tests/runtime/test_run_start_artifacts.py tests/runtime/test_run_summary.py tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py tests/runtime/test_run_summary_projection_validation.py tests/application/test_execution_pipeline_run_ledger.py -k "run_identity or summary or packet1 or packet2 or artifact_provenance or projection"`
   Result: `50 passed, 34 deselected`
27. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_code_review_probe.py`
   Result: `8 passed`
28. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_audit_phase2.py tests/scripts/test_run_summary_projection_consumers.py`
   Result: `11 passed`
29. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py`
   Result: `8 passed`
30. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_common_run_summary_support.py tests/scripts/test_run_summary_projection_consumers.py tests/scripts/test_truthful_runtime_live_proof_summary_validation.py tests/live/test_run_summary_support.py`
   Result: `9 passed`
31. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py tests/interfaces/test_review_cli.py tests/application/test_code_review_probe.py`
   Result: `24 passed`
32. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_build_runtime_truth_dashboard_seed.py`
   Result: `4 passed`
33. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_reviewrun_consistency.py`
   Result: `4 passed`
34. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api.py -k "run_detail_and_session_status"`
   Result: `2 passed, 94 deselected`
35. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api.py -k "run_detail_and_session_status"`
   Result: `3 passed, 94 deselected`
36. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_build_runtime_truth_dashboard_seed.py tests/interfaces/test_api.py -k "build_runtime_truth_dashboard_seed or run_detail_and_session_status"`
   Result: `8 passed, 94 deselected`
37. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_review_cli.py -k "replay"`
   Result: `5 passed, 3 deselected`
38. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_ledger_parity.py tests/scripts/test_compare_run_ledger_backends.py tests/scripts/test_build_runtime_truth_dashboard_seed.py tests/interfaces/test_api.py -k "run_ledger_parity or compare_run_ledger_backends or build_runtime_truth_dashboard_seed or run_detail_and_session_status"`
   Result: `21 passed, 94 deselected`
39. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_protocol_ledger_parity_campaign.py tests/interfaces/test_cli_protocol_parity_campaign.py tests/interfaces/test_sessions_router_protocol_replay.py -k "ledger_parity_campaign"`
   Result: `9 passed, 18 deselected`
40. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_run_protocol_ledger_parity_campaign.py tests/scripts/test_publish_protocol_rollout_artifacts.py`
   Result: `7 passed`
41. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_record_protocol_enforce_window_signoff.py tests/scripts/test_run_protocol_enforce_window_capture.py`
   Result: `8 passed`
42. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_record_protocol_enforce_window_signoff.py tests/scripts/test_run_protocol_enforce_window_capture.py tests/scripts/test_check_protocol_enforce_cutover_readiness.py`
   Result: `12 passed`
43. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_protocol_parity_projection_support.py tests/scripts/test_publish_protocol_rollout_artifacts.py tests/scripts/test_record_protocol_enforce_window_signoff.py tests/scripts/test_check_protocol_enforce_cutover_readiness.py`
   Result: `12 passed`
44. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_live_acceptance_reporting.py tests/application/test_microservices_unlock_evidence_script.py`
   Result: `12 passed`
45. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_unlock_gate.py tests/application/test_live_acceptance_reporting.py tests/application/test_microservices_unlock_evidence_script.py`
   Result: `17 passed`
46. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_monolith_matrix_and_gate.py tests/application/test_microservices_unlock_gate.py tests/application/test_microservices_unlock_evidence_script.py`
   Result: `18 passed`
47. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_architecture_pilot_matrix_script.py tests/application/test_microservices_pilot_stability.py tests/application/test_microservices_pilot_decision.py`
   Result: `13 passed`
48. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api.py -k "runtime_policy"`
   Result: `6 passed, 92 deselected`
49. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_pilot_decision.py tests/application/test_microservices_unlock_evidence_script.py tests/application/test_microservices_unlock_gate.py`
   Result: `12 passed`
50. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api.py -k "runtime_policy"`
   Result: `8 passed, 92 deselected`
51. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_pilot_decision.py`
   Result: `4 passed`
52. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_acceptance_reports.py tests/interfaces/test_api.py -k "runtime_policy or pilot_stability_report or microservices_acceptance_reports"`
   Result: `11 passed, 92 deselected`
53. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_acceptance_reports.py tests/application/test_microservices_pilot_decision.py tests/interfaces/test_api.py -k "unlock_report or microservices_acceptance_reports or runtime_policy"`
   Result: `16 passed, 94 deselected`
54. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_acceptance_reports.py tests/application/test_architecture_pilot_matrix_script.py tests/application/test_microservices_pilot_stability.py`
   Result: `18 passed`
55. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_acceptance_reports.py tests/application/test_microservices_unlock_gate.py`
   Result: `16 passed`
56. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_pilot_decision.py tests/interfaces/test_api.py -k "runtime_policy or unlock_report or microservices_acceptance_reports"`
   Result: `12 passed, 94 deselected`

## Compatibility exits

Workstream 1 compatibility exits affected by the slices recorded here:
1. `CE-01` narrowed, not closed
   Reason: a canonical projection family and shared governed workload catalog now exist, but the `Workload` row remains `conflicting` because start-path authority is not yet universal.
2. `CE-02` narrowed, not closed
   Reason: manual review runs now publish first-class run, attempt, and step truth, fresh review manifests plus persisted review lane decision/critique artifacts now explicitly point execution-state authority at durable control-plane records while marking lane outputs non-authoritative for execution state and now fail closed if those review artifact markers drift, the embedded review-result `manifest` surface now also validates those persisted execution-authority markers before leaving the process and fails closed if they drift, `orket review replay --run-dir`, direct `--snapshot` plus `--policy` replay when those files target canonical bundle artifacts from one review-run directory, the review answer-key scoring path, and the review consistency-signature path now also validate those persisted review bundle authority markers before treating bundle artifacts as trustworthy evidence and fail closed if they drift, with replay, scoring, and consistency now also consuming shared validated review-bundle payload or artifact loaders, including truncation-bounds snapshot inputs, instead of validating markers and then rereading lane JSON or replay inputs ad hoc, workload-side code-review probe bundles now emit the same non-authoritative execution-state markers plus a bundle manifest before reusing shared answer-key scoring, the review result and CLI paths now read durable control-plane refs plus lifecycle state from persisted records and now fail closed if that review-summary projection drifts away from explicit `control_plane_records` framing, cards `run_summary.json` now projects durable cards-epic run or attempt or step state from persisted control-plane records and now fails closed if that `control_plane` block drifts away from explicit projection framing, shared probe/workload helpers plus MAR audit completeness and compare surfaces, training-data extraction, governance dashboard seed metrics, live-acceptance pattern reporting, monolith variant matrix summaries, monolith readiness plus matrix-stability gates, architecture pilot matrix comparison, microservices pilot stability, runtime-policy pilot-stability reads, microservices pilot decision, microservices unlock gating, API run-detail/session-status surfaces, protocol/sqlite run-ledger parity consumers, protocol/sqlite parity-campaign reporting surfaces, protocol rollout evidence bundle summaries, protocol enforce-window signoff plus capture-manifest outputs, and protocol cutover-readiness outputs now also consume validated legacy run-summary or run-ledger projection evidence before trusting summary JSON, artifact JSON, persisted `metrics_json` or `db_summary_json` rows, rate-only matrix summaries, architecture delta summaries, bare pilot-stability flags, bare unlock flags, unlock eligibility, parity heuristics, campaign mismatch summaries, rollout-summary shorthand, signoff/manifest pass-fail summaries, or cutover-ready totals, with governance dashboard seed metrics now also sanitizing persisted `run_ledger.artifact_json` through the shared validated run-ledger projection seam, live-acceptance pattern reporting now recording explicit invalid-payload signals when malformed `metrics_json` or `db_summary_json` rows drift instead of flattening them into clean empty state, monolith variant matrix summaries now preserving those normalized live-report invalid-payload counts instead of dropping them, monolith readiness plus matrix-stability gates now failing closed when those matrix summary counts are missing, malformed, or non-zero instead of producing false-green matrix readiness from malformed live-report rows, architecture pilot matrix comparison now preserving side-specific invalid-payload totals and failures from the underlying pilot summaries instead of flattening malformed source-row drift back into plain architecture deltas, microservices pilot stability now failing closed when that comparison detail is missing, malformed, or non-zero instead of producing false-green pilot stability from malformed live-report rows, runtime-policy pilot-stability reads now failing closed when the persisted pilot-stability artifact is structurally malformed instead of trusting a bare `stable` flag, microservices pilot decision now failing closed when the persisted unlock artifact is structurally malformed instead of trusting a bare `unlocked` flag, microservices unlock gating now failing closed when the live report is missing or malformed on `run_count`, `session_status_counts`, `pattern_counters`, or `invalid_payload_signals`, or reports any non-zero invalid source-row counts instead of producing false-green unlock decisions, run detail also sanitizing the nested `run_ledger.summary_json` projection, both API surfaces now sanitizing persisted `run_ledger.artifact_json` through the same validated run-ledger record seam instead of leaking raw invalid summary or artifact payloads, parity now failing closed on malformed persisted summary or artifact projections instead of normalizing them away into false-green equality while the SQLite run-ledger adapter preserves malformed persisted payload text long enough for that detection to happen, parity-campaign rows plus campaign telemetry now preserving side-specific invalid projection-field detail instead of collapsing malformed persisted projection drift into generic mismatch counts, rollout evidence markdown now preserving those same invalid projection-field counts instead of reducing malformed parity drift back to generic mismatch totals, signoff plus capture-manifest outputs now preserving those same invalid projection-field counts instead of flattening malformed parity drift back to generic pass-fail summaries, cutover-readiness outputs now preserving those same invalid projection-field counts instead of flattening malformed parity drift back to generic ready or passing-window totals, and rollout/signoff/cutover now also consume one shared invalid-projection detail helper instead of carrying divergent local parsers, fresh `run_start_artifacts` now explicitly mark `run_identity` as session-bootstrap projection-only evidence, bootstrap reuse plus legacy run-summary/finalize consumers now also fail closed if that framing drifts, and fresh retry-classification snapshots now explicitly declare `attempt_history_authoritative=false`. Broader `run_summary.py` closure projections, legacy retry or lane behavior, and broader observability surfaces still survive.

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. `orket/runtime/run_start_artifacts.py`
   Reason: immutable session-scoped runtime bootstrap evidence is still valid as a projection and evidence package. Fresh `run_identity` payloads now explicitly mark that surface as session-bootstrap projection-only evidence and bootstrap reuse plus summary consumers now reject framing drift, but it still cannot truthfully hold invocation-scoped cards epic run ids.
2. `orket/runtime/run_summary.py`
   Reason: legacy runtime summary output remains an active projection surface for cards runs and other runtime proof paths. Cards summaries now project durable cards-epic run or attempt or step state from persisted records, the dedicated `control_plane` block now fails closed if explicit projection framing drifts, and shared probe/workload, audit, and training consumers now validate the summary contract before trusting it, but the broader summary surface is not yet demoted lane-wide to projection-only closure behavior.
3. `orket/application/review/lanes/`
   Reason: deterministic and model-assisted review lanes remain valid evidence-producing review components. Fresh review manifests plus persisted decision/critique artifacts now explicitly mark those lane outputs non-authoritative for execution state, but not all touched read paths or replay surfaces are fully framed that way yet.
4. `orket/runtime/retry_classification_policy.py`
   Reason: retry policy still exists outside one universal append-only attempt history model for all runtime paths. Fresh snapshots now explicitly declare that policy surface non-authoritative for attempt history, but service-local retry behavior still survives.
5. review-run result and CLI JSON `control_plane` summary
   Reason: this review-facing summary now explicitly declares `control_plane_records` projection framing and rejects malformed summaries, but broader review-lane and replay surfaces still remain around that durable execution truth.
6. review-run manifest and review-lane decision/critique artifacts
   Reason: these review-facing artifact surfaces now fail closed on malformed execution-authority markers, but broader review-lane and replay surfaces still remain around that durable execution truth.
7. review answer-key scoring
   Reason: this scoring surface now validates persisted review-bundle authority markers through one shared review-bundle loader before trusting lane JSON, but other review evidence and analysis consumers still remain around that durable execution truth.
8. review consistency-signature extraction
   Reason: this consistency-analysis surface now validates persisted review-bundle authority markers through one shared review-bundle loader before trusting lane JSON, but other review evidence and analysis consumers still remain around that durable execution truth.

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
6. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`
7. `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`
8. `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`
9. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
10. `docs/specs/REVIEW_RUN_V0.md`
11. `docs/guides/REVIEW_RUN_CLI.md`

## Verdict

Workstream 1 has materially narrowed `CE-01` and `CE-02`, but it is still open.

The next truthful Workstream 1 work should focus on demoting remaining legacy run and attempt read surfaces without pushing invocation-scoped control-plane identity into immutable session-scoped artifacts.
