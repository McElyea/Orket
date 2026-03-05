# Script Index

_Generated: 2026-03-05T16:16:15.068075Z_

This index maps script scores to purpose and recent artifact evidence.
Scores come from `script_tier_scores.csv` (1-10 scale) and are grouped by functional family.

## arbiter (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/odr/run_arbiter.py` | `odr` | 4/10 | run arbiter | [`benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json)<br>[`benchmarks/published/ODR/arbiter_plan.json`](../../benchmarks/published/ODR/arbiter_plan.json) |

## architecture_pilot (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/acceptance/run_architecture_pilot_matrix.py` | `acceptance` | 4/10 | Run or plan architecture pilot matrix (architecture x builder x project profile). | [`benchmarks/results/acceptance/architecture_pilot_matrix.json`](../../benchmarks/results/acceptance/architecture_pilot_matrix.json)<br>[`benchmarks/results/acceptance/architecture_pilot_matrix_prev.json`](../../benchmarks/results/acceptance/architecture_pilot_matrix_prev.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot_pair2/odr_live_role_matrix.qwen2_5_14b_gemma3_27b.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/odr_live_role_matrix.qwen2_5_14b_gemma3_27b.json) |

## baselines (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/manage_baselines.py` | `benchmarks` | 9/10 | Manage Orket baseline artifacts. | - |

## benchmark_dashboard (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/render_benchmark_dashboard.py` | `benchmarks` | 4/10 | Render a markdown benchmark dashboard. | [`benchmarks/results/benchmarks/phase6_benchmark_dashboard.md`](../../benchmarks/results/benchmarks/phase6_benchmark_dashboard.md) |

## benchmark_leaderboard (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/build_benchmark_leaderboard.py` | `benchmarks` | 4/10 | Build benchmark leaderboard grouped by version/policy. | [`benchmarks/results/tiering/live_100_leaderboard.json`](../../benchmarks/results/tiering/live_100_leaderboard.json)<br>[`benchmarks/results/benchmarks/phase6_benchmark_leaderboard.json`](../../benchmarks/results/benchmarks/phase6_benchmark_leaderboard.json) |

## benchmark_manifest (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/update_benchmark_manifest.py` | `benchmarks` | 2/10 | Regenerate manifest checksums for a benchmark task bank. | [`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/tuning_manifest.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/tuning_manifest.json)<br>[`benchmarks/results/quant/quant_sweep/tuning/live_verify_convergence_20260304_1913/tuning_manifest.json`](../../benchmarks/results/quant/quant_sweep/tuning/live_verify_convergence_20260304_1913/tuning_manifest.json)<br>[`benchmarks/results/quant/quant_sweep/tuning/live_verify_convergence_20260304_1909/tuning_manifest.json`](../../benchmarks/results/quant/quant_sweep/tuning/live_verify_convergence_20260304_1909/tuning_manifest.json) |

## benchmark_run (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/score_benchmark_run.py` | `benchmarks` | 5/10 | Score benchmark determinism runs using tier-aware policy. | [`benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json)<br>[`benchmarks/published/README.md`](../../benchmarks/published/README.md) |

## benchmark_scoring (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/check_benchmark_scoring_gate.py` | `benchmarks` | 6/10 | Validate benchmark scoring metadata and threshold gates. | [`benchmarks/results/benchmarks/benchmark_scoring_gate.json`](../../benchmarks/results/benchmarks/benchmark_scoring_gate.json)<br>[`benchmarks/results/gitea/gitea_state_rollout_gates.json`](../../benchmarks/results/gitea/gitea_state_rollout_gates.json)<br>[`benchmarks/results/security/security_enforcement_flip_gate.json`](../../benchmarks/results/security/security_enforcement_flip_gate.json) |

## benchmark_suite (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/run_benchmark_suite.py` | `benchmarks` | 6/10 | Run benchmark determinism harness and scoring in one command. | - |

## benchmark_task (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/validate_benchmark_task_bank.py` | `benchmarks` | 2/10 | Validate a versioned Orket benchmark task bank. | [`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8_summary.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8_summary.json)<br>[`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8/qwen3.5-4b/Q8_0_determinism_report.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8/qwen3.5-4b/Q8_0_determinism_report.json)<br>[`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8/_canary_report.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8/_canary_report.json) |

## benchmark_trends (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/report_benchmark_trends.py` | `benchmarks` | 5/10 | Build trend report from benchmark scored reports. | [`benchmarks/results/tiering/live_100_trends.json`](../../benchmarks/results/tiering/live_100_trends.json)<br>[`benchmarks/results/benchmarks/phase6_benchmark_trends.json`](../../benchmarks/results/benchmarks/phase6_benchmark_trends.json) |

## churn_report (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/ops/churn_report.py` | `ops` | 3/10 | Generate Orket code churn evidence. | [`benchmarks/results/tiering/2026-02-11_phaseR_churn.json`](../../benchmarks/results/tiering/2026-02-11_phaseR_churn.json)<br>[`benchmarks/results/tiering/2026-02-11_phaseH_churn.json`](../../benchmarks/results/tiering/2026-02-11_phaseH_churn.json) |

## cli_regression (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/run_cli_regression_smoke.py` | `governance` | 4/10 | Run deterministic CLI regression smoke for init/api/refactor. | [`benchmarks/results/governance/cli_regression_smoke.json`](../../benchmarks/results/governance/cli_regression_smoke.json) |

## compat_fallback (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/security/check_compat_fallback_expiry.py` | `security` | 6/10 | Fail CI when expired compatibility fallbacks remain active. | [`benchmarks/results/security/security_compat_expiry_check.json`](../../benchmarks/results/security/security_compat_expiry_check.json)<br>[`benchmarks/results/security/security_compat_expiry_check.md`](../../benchmarks/results/security/security_compat_expiry_check.md) |
| `scripts/security/execute_compat_fallback_removal.py` | `security` | 6/10 | Execute compatibility fallback removal for expired fallbacks. | [`benchmarks/results/security/security_compat_removal_execution.json`](../../benchmarks/results/security/security_compat_removal_execution.json) |

## context_ceiling (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/context/context_ceiling_finder.py` | `context` | 6/10 | Build context ceiling recommendation artifact from context sweep summaries. | - |

## context_profile (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/context/check_context_profile_policy.py` | `context` | 6/10 | Validate context profile policy defaults and matrix references. | - |

## context_rollup (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/context/check_context_rollup_contract.py` | `context` | 6/10 | Validate context rollup consistency against context ceiling artifact. | - |

## context_sweep (4)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/context/build_context_sweep_rollup.py` | `context` | 6/10 | Build compact rollup from context ceiling artifact. | - |
| `scripts/context/check_context_sweep_outputs.py` | `context` | 6/10 | Validate context sweep output coverage. | - |
| `scripts/context/cleanup_context_sweep_artifacts.py` | `context` | 6/10 | Cleanup ephemeral context sweep artifacts. | - |
| `scripts/context/run_context_sweep.py` | `context` | 6/10 | Run multi-context sweep and emit linked context ceiling artifact. | - |

## dependency_direction (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/check_dependency_direction.py` | `governance` | 6/10 | Enforce dependency direction policy. | [`benchmarks/results/governance/dependency_direction_check.json`](../../benchmarks/results/governance/dependency_direction_check.json) |

## dependency_graph (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/export_dependency_graph.py` | `governance` | 6/10 | Export dependency graph snapshot. | - |

## dependency_policy (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/dependency_policy.py` | `governance` | 6/10 | dependency policy | - |

## determinism_control (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/determinism_control_runner.py` | `benchmarks` | 7/10 | Deterministic control runner for harness validation. | [`benchmarks/results/benchmarks/determinism_control_report.json`](../../benchmarks/results/benchmarks/determinism_control_report.json)<br>[`benchmarks/results/benchmarks/benchmark_determinism_report.json`](../../benchmarks/results/benchmarks/benchmark_determinism_report.json) |

## determinism_harness (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/run_determinism_harness.py` | `benchmarks` | 7/10 | Run benchmark tasks repeatedly and report output drift. | - |

## digest_vectors (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/gen_digest_vectors.py` | `governance` | 6/10 | Generate committed digest vectors. | - |

## evaluate_odr (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/odr/evaluate_odr_calibration_bundle.py` | `odr` | 4/10 | Evaluate ODR calibration bundle with telemetry-first convergence diagnostics. | [`benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot_summary.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_summary.json) |

## explorer_artifact (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/explorer/build_explorer_artifact_index.py` | `explorer` | 5/10 | Build explorer artifact index for downstream ingestion. | - |

## explorer_check (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/explorer/build_explorer_check_summary.py` | `explorer` | 6/10 | Build compact summary of explorer check outputs. | - |
| `scripts/explorer/render_explorer_check_digest.py` | `explorer` | 6/10 | Render markdown digest for explorer checks. | - |

## explorer_ingestion (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/explorer/check_explorer_ingestion.py` | `explorer` | 7/10 | Validate explorer artifact index for ingestion readiness. | - |

## explorer_schema (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/explorer/check_explorer_schema_contracts.py` | `explorer` | 6/10 | Validate explorer artifact schema contracts. | - |

## extension_workload (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/extensions/run_extension_workload_baseline.py` | `extensions` | 4/10 | Run an extension workload repeatedly and emit latency baseline artifacts. | - |

## failure_modes (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/replay/report_failure_modes.py` | `replay` | 4/10 | Summarize Orket failure and non-progress modes from logs. | [`benchmarks/results/replay/failure_modes.json`](../../benchmarks/results/replay/failure_modes.json) |

## find_run (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/ops/find_run.py` | `ops` | 2/10 | Find benchmark run records from workspace/run_manifest.jsonl. | - |

## gitea (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/gitea/backup_gitea.sh` | `gitea` | 3/10 | backup gitea | [`benchmarks/results/gitea/gitea_state_rollout_gates.json`](../../benchmarks/results/gitea/gitea_state_rollout_gates.json)<br>[`benchmarks/results/gitea/gitea_state_phase3_readiness.json`](../../benchmarks/results/gitea/gitea_state_phase3_readiness.json)<br>[`benchmarks/results/gitea/gitea_state_hardening_check.json`](../../benchmarks/results/gitea/gitea_state_hardening_check.json) |
| `scripts/gitea/restore_gitea.sh` | `gitea` | 3/10 | restore gitea | [`benchmarks/results/gitea/gitea_state_rollout_gates.json`](../../benchmarks/results/gitea/gitea_state_rollout_gates.json)<br>[`benchmarks/results/gitea/gitea_state_phase3_readiness.json`](../../benchmarks/results/gitea/gitea_state_phase3_readiness.json)<br>[`benchmarks/results/gitea/gitea_state_hardening_check.json`](../../benchmarks/results/gitea/gitea_state_hardening_check.json) |

## gitea_privacy (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/gitea/configure_gitea_privacy.sh` | `gitea` | 2/10 | configure gitea privacy | - |

## gitea_state (5)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/gitea/check_gitea_state_hardening.py` | `gitea` | 4/10 | Evaluate gitea state backend hardening gate using contention/failure-injection test targets. | [`benchmarks/results/gitea/gitea_state_rollout_gates.json`](../../benchmarks/results/gitea/gitea_state_rollout_gates.json)<br>[`benchmarks/results/gitea/gitea_state_hardening_check.json`](../../benchmarks/results/gitea/gitea_state_hardening_check.json)<br>[`benchmarks/results/gitea/gitea_state_phase3_readiness.json`](../../benchmarks/results/gitea/gitea_state_phase3_readiness.json) |
| `scripts/gitea/check_gitea_state_phase3_readiness.py` | `gitea` | 4/10 | Evaluate phase-3 readiness for gitea state backend multi-runner rollout. | [`benchmarks/results/gitea/gitea_state_rollout_gates.json`](../../benchmarks/results/gitea/gitea_state_rollout_gates.json)<br>[`benchmarks/results/gitea/gitea_state_phase3_readiness.json`](../../benchmarks/results/gitea/gitea_state_phase3_readiness.json)<br>[`benchmarks/results/gitea/gitea_state_pilot_readiness.json`](../../benchmarks/results/gitea/gitea_state_pilot_readiness.json) |
| `scripts/gitea/check_gitea_state_pilot_readiness.py` | `gitea` | 4/10 | Check whether gitea state backend pilot prerequisites are satisfied. | [`benchmarks/results/gitea/gitea_state_rollout_gates.json`](../../benchmarks/results/gitea/gitea_state_rollout_gates.json)<br>[`benchmarks/results/gitea/gitea_state_pilot_readiness.json`](../../benchmarks/results/gitea/gitea_state_pilot_readiness.json)<br>[`benchmarks/results/gitea/gitea_state_phase3_readiness.json`](../../benchmarks/results/gitea/gitea_state_phase3_readiness.json) |
| `scripts/gitea/run_gitea_state_rollout_gates.py` | `gitea` | 4/10 | Run gitea state rollout gates (pilot, hardening, phase3) and emit a bundle summary. | [`benchmarks/results/gitea/gitea_state_rollout_gates.json`](../../benchmarks/results/gitea/gitea_state_rollout_gates.json)<br>[`benchmarks/results/gitea/gitea_state_phase3_readiness.json`](../../benchmarks/results/gitea/gitea_state_phase3_readiness.json)<br>[`benchmarks/results/gitea/gitea_state_hardening_check.json`](../../benchmarks/results/gitea/gitea_state_hardening_check.json) |
| `scripts/gitea/run_gitea_state_worker_coordinator.py` | `gitea` | 4/10 | Run the experimental gitea state worker coordinator loop. | [`benchmarks/results/gitea/gitea_state_rollout_gates.json`](../../benchmarks/results/gitea/gitea_state_rollout_gates.json)<br>[`benchmarks/results/gitea/gitea_state_phase3_readiness.json`](../../benchmarks/results/gitea/gitea_state_phase3_readiness.json)<br>[`benchmarks/results/gitea/gitea_state_hardening_check.json`](../../benchmarks/results/gitea/gitea_state_hardening_check.json) |

## kernel_compare (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/gen_kernel_compare_fixture.py` | `governance` | 5/10 | Generate a kernel compare API fixture payload. | - |

## kernel_fire (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/run_kernel_fire_drill.py` | `governance` | 7/10 | run kernel fire drill | - |

## lab_guards (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/check_lab_guards.py` | `benchmarks` | 7/10 | Check cooldown and VRAM preflight guard diagnostics from sweep summary. | - |

## lie_detector (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/extensions/play_lie_detector.py` | `extensions` | 4/10 | Launch The Lie Detector game mode. | - |

## lint (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/docs_lint.py` | `governance` | 9/10 | Deterministic docs gate lint checks. | - |

## live_1000 (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/streaming/check_live_1000_consistency.py` | `streaming` | 3/10 | Validate live_1000_consistency run report. | [`benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model_post_refactor.json`](../../benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model_post_refactor.json)<br>[`benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model.json`](../../benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model.json)<br>[`benchmarks/results/streaming/non_quant_live/live_1000_consistency_stress1_check.json`](../../benchmarks/results/streaming/non_quant_live/live_1000_consistency_stress1_check.json) |
| `scripts/streaming/run_live_1000_consistency.py` | `streaming` | 3/10 | Run live consistency loops for model-streaming gate and real-service stress. | [`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json)<br>[`benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model_post_refactor.json`](../../benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model_post_refactor.json) |

## live_acceptance (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/acceptance/report_live_acceptance_patterns.py` | `acceptance` | 6/10 | Summarize repeatable live-acceptance failure patterns from SQLite results. | [`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json)<br>[`benchmarks/results/streaming/non_quant_live/live_acceptance_patterns.json`](../../benchmarks/results/streaming/non_quant_live/live_acceptance_patterns.json) |
| `scripts/acceptance/run_live_acceptance_loop.py` | `acceptance` | 6/10 | Run live acceptance pytest in a loop and emit per-run metrics + DB summaries. | [`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json)<br>[`benchmarks/results/streaming/non_quant_live/live_acceptance_loop_smoke_qwen25c7b.json`](../../benchmarks/results/streaming/non_quant_live/live_acceptance_loop_smoke_qwen25c7b.json) |

## live_card (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/live_card_benchmark_runner.py` | `benchmarks` | 5/10 | Run one benchmark task through the live Orket card pipeline. | [`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/long_run_recommended_matrix.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/long_run_recommended_matrix.json)<br>[`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8/qwen3.5-4b/Q8_0_determinism_report.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8/qwen3.5-4b/Q8_0_determinism_report.json)<br>[`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8/_canary_report.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/probe_task_8/_canary_report.json) |
| `scripts/benchmarks/run_live_card_benchmark_suite.py` | `benchmarks` | 5/10 | Run benchmark tasks 001-100 through live Orket card execution. | [`benchmarks/results/streaming/non_quant_live/card_run_001/agent_output/observability/runtime_events.jsonl`](../../benchmarks/results/streaming/non_quant_live/card_run_001/agent_output/observability/runtime_events.jsonl)<br>[`benchmarks/results/streaming/non_quant_live/card_run_001/benchmark_task_001_output.md`](../../benchmarks/results/streaming/non_quant_live/card_run_001/benchmark_task_001_output.md)<br>[`benchmarks/results/streaming/non_quant_live/card_run_001/report.json`](../../benchmarks/results/streaming/non_quant_live/card_run_001/report.json) |

## live_consistency (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/streaming/live_consistency_common.py` | `streaming` | 3/10 | live consistency common | [`benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model_post_refactor.json`](../../benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model_post_refactor.json)<br>[`benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model.json`](../../benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model.json)<br>[`benchmarks/results/streaming/non_quant_live/live_1000_consistency_stress1_check.json`](../../benchmarks/results/streaming/non_quant_live/live_1000_consistency_stress1_check.json) |

## live_rock (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/live_rock_benchmark_runner.py` | `benchmarks` | 5/10 | Run one benchmark task through live Orket rock execution. | [`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json)<br>[`benchmarks/results/benchmarks/live_rock_v2_080_determinism_report.json`](../../benchmarks/results/benchmarks/live_rock_v2_080_determinism_report.json) |
| `scripts/benchmarks/run_live_rock_benchmark_suite.py` | `benchmarks` | 5/10 | Run benchmark tasks through live Orket rock execution and score the results. | [`benchmarks/results/streaming/non_quant_live/rock_run_002/benchmark_live_002_8c782f1c/agent_output/observability/runtime_events.jsonl`](../../benchmarks/results/streaming/non_quant_live/rock_run_002/benchmark_live_002_8c782f1c/agent_output/observability/runtime_events.jsonl)<br>[`benchmarks/results/streaming/non_quant_live/rock_run_002/benchmark_live_002_8c782f1c/report.json`](../../benchmarks/results/streaming/non_quant_live/rock_run_002/benchmark_live_002_8c782f1c/report.json)<br>[`benchmarks/results/streaming/non_quant_live/rock_run_002/benchmark_live_002_8c782f1c/run.log`](../../benchmarks/results/streaming/non_quant_live/rock_run_002/benchmark_live_002_8c782f1c/run.log) |

## lmstudio_model (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/providers/lmstudio_model_cache.py` | `providers` | 6/10 | lmstudio model cache | - |

## memory_determinism (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/check_memory_determinism.py` | `benchmarks` | 8/10 | Validate memory determinism trace contracts. | - |
| `scripts/benchmarks/compare_memory_determinism.py` | `benchmarks` | 8/10 | Compare two memory determinism traces for equivalence. | - |

## meta_breaker (3)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/extensions/register_meta_breaker_extension.py` | `extensions` | 4/10 | register meta breaker extension | - |
| `scripts/extensions/run_meta_breaker_scenarios.py` | `extensions` | 4/10 | Run predefined Meta Breaker scenario pack. | - |
| `scripts/extensions/run_meta_breaker_workload.py` | `extensions` | 4/10 | Run Meta Breaker workload through ExtensionManager. | - |

## microservices_pilot (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/acceptance/check_microservices_pilot_stability.py` | `acceptance` | 3/10 | Check if microservices pilot is stable across consecutive architecture pilot artifacts. | [`benchmarks/results/acceptance/microservices_pilot_stability_check.json`](../../benchmarks/results/acceptance/microservices_pilot_stability_check.json)<br>[`benchmarks/results/acceptance/microservices_pilot_decision.json`](../../benchmarks/results/acceptance/microservices_pilot_decision.json) |
| `scripts/acceptance/decide_microservices_pilot.py` | `acceptance` | 3/10 | Decide whether microservices pilot mode should be enabled from unlock-check output. | [`benchmarks/results/acceptance/microservices_pilot_stability_check.json`](../../benchmarks/results/acceptance/microservices_pilot_stability_check.json)<br>[`benchmarks/results/acceptance/microservices_pilot_decision.json`](../../benchmarks/results/acceptance/microservices_pilot_decision.json) |

## microservices_unlock (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/acceptance/check_microservices_unlock.py` | `acceptance` | 4/10 | Evaluate whether microservices mode can be unlocked from objective gates. | [`benchmarks/results/acceptance/microservices_unlock_check.json`](../../benchmarks/results/acceptance/microservices_unlock_check.json) |
| `scripts/acceptance/run_microservices_unlock_evidence.py` | `acceptance` | 4/10 | Run unlock evidence pipeline: matrix execute + live report + unlock checker. | [`benchmarks/results/acceptance/microservices_unlock_check.json`](../../benchmarks/results/acceptance/microservices_unlock_check.json) |

## migration_dry (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/workitem_migration_dry_run.py` | `governance` | 4/10 | Generate deterministic dry-run mapping report for WorkItem migration. | - |

## migrations (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/run_migrations.py` | `governance` | 5/10 | Run Orket SQLite schema migrations. | - |

## model_provider (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/providers/check_model_provider_preflight.py` | `providers` | 4/10 | Preflight checks for real model streaming providers. | - |

## model_selector (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/prototype_model_selector.py` | `benchmarks` | 6/10 | Prototype model/quant selector from quant sweep summary artifacts. | - |

## model_streaming (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/streaming/run_model_streaming_gate.py` | `streaming` | 6/10 | Run model-streaming acceptance gate scenarios. | [`benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model_post_refactor.json`](../../benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model_post_refactor.json)<br>[`benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model.json`](../../benchmarks/results/streaming/non_quant_live/live_1000_consistency_auto_model.json)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md) |

## monolith_readiness (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/acceptance/check_monolith_readiness_gate.py` | `acceptance` | 4/10 | Check monolith readiness gate against matrix artifact thresholds. | - |

## monolith_variant (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/acceptance/run_monolith_variant_matrix.py` | `acceptance` | 5/10 | Run or plan the monolith variant matrix (builder variant x project profile). | [`benchmarks/results/acceptance/monolith_variant_matrix.json`](../../benchmarks/results/acceptance/monolith_variant_matrix.json) |

## nervous_system (3)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/nervous_system/run_nervous_system_attack_torture_pack.py` | `nervous_system` | 4/10 | Run the nervous-system attack torture corpus. | [`benchmarks/results/nervous_system/nervous_system_attack_torture_evidence.json`](../../benchmarks/results/nervous_system/nervous_system_attack_torture_evidence.json)<br>[`benchmarks/results/nervous_system/nervous_system_live_evidence.json`](../../benchmarks/results/nervous_system/nervous_system_live_evidence.json) |
| `scripts/nervous_system/run_nervous_system_live_evidence.py` | `nervous_system` | 4/10 | run nervous system live evidence | [`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json)<br>[`benchmarks/results/nervous_system/nervous_system_live_evidence.json`](../../benchmarks/results/nervous_system/nervous_system_live_evidence.json) |
| `scripts/nervous_system/update_nervous_system_policy_digest_snapshot.py` | `nervous_system` | 4/10 | Refresh the nervous-system policy digest snapshot fixture. | [`benchmarks/results/nervous_system/nervous_system_live_evidence.json`](../../benchmarks/results/nervous_system/nervous_system_live_evidence.json)<br>[`benchmarks/results/nervous_system/nervous_system_attack_torture_evidence.json`](../../benchmarks/results/nervous_system/nervous_system_attack_torture_evidence.json) |

## odr_calibration (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/odr/generate_odr_calibration_bundle.py` | `odr` | 3/10 | Generate ODR calibration candidate run bundle and gold labels scaffold. | [`benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot_summary.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_summary.json) |
| `scripts/odr/score_odr_calibration.py` | `odr` | 3/10 | Score ODR calibration evaluation against gold labels. | [`benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot_summary.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_summary.json) |

## odr_live (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/odr/run_odr_live_role_matrix.py` | `odr` | 7/10 | Run live model-in-loop ODR role matrix and emit round-level IO report. | [`benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json)<br>[`benchmarks/published/ODR/arbiter_plan.json`](../../benchmarks/published/ODR/arbiter_plan.json) |

## odr_provenance (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/odr/generate_odr_provenance.py` | `odr` | 6/10 | Generate ODR provenance sidecar for published ODR runs. | [`benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json)<br>[`benchmarks/published/ODR/arbiter_plan.json`](../../benchmarks/published/ODR/arbiter_plan.json) |

## odr_quant (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/odr/run_odr_quant_sweep.py` | `odr` | 4/10 | Run ODR live role-matrix quant/model sweep and regenerate ODR index. | [`benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json)<br>[`benchmarks/published/ODR/arbiter_plan.json`](../../benchmarks/published/ODR/arbiter_plan.json) |

## odr_role (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/odr/generate_odr_role_matrix_index.py` | `odr` | 4/10 | Generate ODR live role-matrix summary index. | [`benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/arbiter_plan.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/arbiter_plan.json)<br>[`benchmarks/published/ODR/arbiter_plan.json`](../../benchmarks/published/ODR/arbiter_plan.json) |
| `scripts/odr/run_odr_role_matrix.py` | `odr` | 4/10 | Run architect/auditor model role matrix against ODR suites. | [`benchmarks/results/streaming/non_quant_live/odr_live_role_matrix_smoke.json`](../../benchmarks/results/streaming/non_quant_live/odr_live_role_matrix_smoke.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot_pair2/odr_live_role_matrix.qwen2_5_14b_gemma3_27b.json`](../../benchmarks/results/odr/odr_calibration/live_pilot_pair2/odr_live_role_matrix.qwen2_5_14b_gemma3_27b.json)<br>[`benchmarks/results/odr/odr_calibration/live_pilot/odr_live_role_matrix.qwen2_5_14b_deepseek_r1_32b.json`](../../benchmarks/results/odr/odr_calibration/live_pilot/odr_live_role_matrix.qwen2_5_14b_deepseek_r1_32b.json) |

## offline_matrix (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/check_offline_matrix.py` | `benchmarks` | 7/10 | Validate offline capability matrix contract. | [`benchmarks/results/benchmarks/offline_matrix_check_test.json`](../../benchmarks/results/benchmarks/offline_matrix_check_test.json)<br>[`benchmarks/results/benchmarks/offline_matrix_check.json`](../../benchmarks/results/benchmarks/offline_matrix_check.json)<br>[`benchmarks/results/benchmarks/offline_matrix_check.local.json`](../../benchmarks/results/benchmarks/offline_matrix_check.local.json) |

## operator_canary (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/ops/run_operator_canary.py` | `ops` | 2/10 | run operator canary | - |

## orchestration_overhead (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/check_orchestration_overhead_consistency.py` | `benchmarks` | 6/10 | Validate orchestration-overhead telemetry consistency. | [`benchmarks/results/benchmarks/orchestration_overhead_consistency.local.json`](../../benchmarks/results/benchmarks/orchestration_overhead_consistency.local.json) |

## orchestration_runner (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/orchestration_runner.py` | `benchmarks` | 6/10 | Phase 5 orchestration runner with compliance artifacts. | [`benchmarks/published/General/live_100_determinism_report.json`](../../benchmarks/published/General/live_100_determinism_report.json)<br>[`benchmarks/results/benchmarks/phase5_determinism_report.json`](../../benchmarks/results/benchmarks/phase5_determinism_report.json)<br>[`benchmarks/results/benchmarks/phase4_determinism_report.json`](../../benchmarks/results/benchmarks/phase4_determinism_report.json) |

## phase4_benchmark (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/run_phase4_benchmark.py` | `benchmarks` | 3/10 | Run Phase 4 benchmark tasks (001-060) in one command. | [`benchmarks/results/benchmarks/phase4_determinism_report.json`](../../benchmarks/results/benchmarks/phase4_determinism_report.json)<br>[`benchmarks/results/benchmarks/phase4_scored_report.json`](../../benchmarks/results/benchmarks/phase4_scored_report.json) |

## policy_release (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/security/check_policy_release_gate.py` | `security` | 5/10 | Release gate: policy churn must show measurable reliability improvement. | - |

## products_to (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/gitea/publish_products_to_gitea.py` | `gitea` | 6/10 | Publish <source-dir>/* projects to Gitea as separate repositories via git subtree. | - |

## project_hygiene (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/check_docs_project_hygiene.py` | `governance` | 4/10 | check docs project hygiene | - |

## provider_scenario (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/streaming/run_provider_scenario_direct.py` | `streaming` | 3/10 | Run provider scenario directly against runtime (no API transport). | - |

## published_index (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/sync_published_index.py` | `governance` | 6/10 | Validate and render benchmarks/published README from index.json | [`benchmarks/published/README.md`](../../benchmarks/published/README.md)<br>[`benchmarks/published/ODR/index.json`](../../benchmarks/published/ODR/index.json)<br>[`benchmarks/published/index.json`](../../benchmarks/published/index.json) |

## published_projects (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/cleanup_published_projects.py` | `governance` | 5/10 | Auto-cleanup policy for parity-verified published projects. | - |

## quant_frontier (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/quant/quant_frontier_explorer.py` | `quant` | 6/10 | Build quant frontier explorer artifact from sweep summary. | - |

## quant_sweep (5)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/quant/check_quant_sweep_kpis.py` | `quant` | 6/10 | Validate quant sweep KPI thresholds. | [`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json)<br>[`benchmarks/results/quant/quant_sweep/qwen3.5-0.8b/Q8_0_determinism_report.json`](../../benchmarks/results/quant/quant_sweep/qwen3.5-0.8b/Q8_0_determinism_report.json) |
| `scripts/quant/quant_sweep_kpi_report.py` | `quant` | 6/10 | Extract stability KPI block from quant sweep summary. | [`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json)<br>[`benchmarks/results/quant/quant_sweep/qwen3.5-0.8b/Q8_0_determinism_report.json`](../../benchmarks/results/quant/quant_sweep/qwen3.5-0.8b/Q8_0_determinism_report.json) |
| `scripts/quant/render_quant_sweep_report.py` | `quant` | 6/10 | Render quant sweep operator report artifacts. | [`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json)<br>[`benchmarks/results/quant/quant_sweep/qwen3.5-0.8b/Q8_0_determinism_report.json`](../../benchmarks/results/quant/quant_sweep/qwen3.5-0.8b/Q8_0_determinism_report.json) |
| `scripts/quant/run_quant_sweep.py` | `quant` | 6/10 | run quant sweep | [`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.md)<br>[`benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json`](../../benchmarks/results/streaming/non_quant_live/non_quant_live_sweep_audit.json)<br>[`benchmarks/results/quant/quant_sweep/qwen3.5-0.8b/Q8_0_determinism_report.json`](../../benchmarks/results/quant/quant_sweep/qwen3.5-0.8b/Q8_0_determinism_report.json) |
| `scripts/quant/run_quant_sweep_series.py` | `quant` | 6/10 | Run quant sweep matrix one model at a time (serial), preserving shared instructions. | [`benchmarks/results/quant/quant_sweep/series/qwen35_logic_sentry_35b_loadedctx_var50_20260304_202000/qwen3.5-35b-a3b_summary.json`](../../benchmarks/results/quant/quant_sweep/series/qwen35_logic_sentry_35b_loadedctx_var50_20260304_202000/qwen3.5-35b-a3b_summary.json)<br>[`benchmarks/results/quant/quant_sweep/series/qwen35_logic_sentry_35b_loadedctx_var50_20260304_202000/qwen3.5-35b-a3b/qwen3.5-35b-a3b/Q4_K_M_determinism_report.json`](../../benchmarks/results/quant/quant_sweep/series/qwen35_logic_sentry_35b_loadedctx_var50_20260304_202000/qwen3.5-35b-a3b/qwen3.5-35b-a3b/Q4_K_M_determinism_report.json)<br>[`benchmarks/results/quant/quant_sweep/series/qwen35_logic_sentry_35b_loadedctx_var50_20260304_202000/qwen3.5-35b-a3b/qwen3.5-35b-a3b/Q6_K_determinism_report.json`](../../benchmarks/results/quant/quant_sweep/series/qwen35_logic_sentry_35b_loadedctx_var50_20260304_202000/qwen3.5-35b-a3b/qwen3.5-35b-a3b/Q6_K_determinism_report.json) |

## real_provider (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/providers/list_real_provider_models.py` | `providers` | 2/10 | List model IDs available from configured real provider endpoints. | - |

## real_service (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/streaming/real_service_stress.py` | `streaming` | 3/10 | Run real-service stress load against Orket API + webhook. | [`benchmarks/results/streaming/real_service_stress_heavy_authfixed.json`](../../benchmarks/results/streaming/real_service_stress_heavy_authfixed.json)<br>[`benchmarks/results/streaming/real_service_stress_baseline_authfixed.json`](../../benchmarks/results/streaming/real_service_stress_baseline_authfixed.json)<br>[`benchmarks/results/streaming/real_service_stress_heavy_retry.json`](../../benchmarks/results/streaming/real_service_stress_heavy_retry.json) |

## regenerate_canonical (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/ops/regenerate_canonical_roles.py` | `ops` | 2/10 | Regenerate canonical role structure templates. | - |

## registry (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/audit_registry.py` | `governance` | 7/10 | audit registry | - |

## replay_artifacts (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/replay/compare_replay_artifacts.py` | `replay` | 6/10 | Compare two replay artifacts for deterministic drift. | - |

## replay_comparator (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/replay/replay_comparator.py` | `replay` | 4/10 | Compare replay payloads and emit deterministic ReplayReport JSON. | - |

## retention_plan (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/retention_plan.py` | `governance` | 7/10 | Generate retention dry-run plan for artifacts/checks/smoke namespaces. | [`benchmarks/results/streaming/non_quant_live/retention_plan_snapshot.json`](../../benchmarks/results/streaming/non_quant_live/retention_plan_snapshot.json)<br>[`benchmarks/results/governance/retention_plan.json`](../../benchmarks/results/governance/retention_plan.json) |

## retention_policy (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/check_retention_policy.py` | `governance` | 7/10 | Validate retention plan safety invariants. | [`benchmarks/results/governance/retention_policy_check.json`](../../benchmarks/results/governance/retention_policy_check.json) |

## roadmap_metrics (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/check_roadmap_metrics.py` | `governance` | 5/10 | Check ROADMAP pytest metrics against live pytest output. | - |

## security_canary (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/security/security_canary.py` | `security` | 5/10 | security canary | - |

## security_compat (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/security/export_security_compat_warnings.py` | `security` | 5/10 | Export compatibility fallback warning artifacts for CI. | [`benchmarks/results/security/security_compat_warnings.json`](../../benchmarks/results/security/security_compat_warnings.json)<br>[`benchmarks/results/security/security_compat_warnings.md`](../../benchmarks/results/security/security_compat_warnings.md)<br>[`benchmarks/results/security/security_compat_expiry_check.json`](../../benchmarks/results/security/security_compat_expiry_check.json) |

## security_enforcement (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/security/check_security_enforcement_flip_gate.py` | `security` | 5/10 | Validate security enforcement flip gates. | [`benchmarks/results/security/security_enforcement_flip_gate.json`](../../benchmarks/results/security/security_enforcement_flip_gate.json)<br>[`benchmarks/results/security/security_enforcement_flip_gate.md`](../../benchmarks/results/security/security_enforcement_flip_gate.md) |

## security_regression (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/security/run_security_regression_suite.py` | `security` | 4/10 | Run security regression suite and emit status artifact. | [`benchmarks/results/security/security_regression_status.json`](../../benchmarks/results/security/security_regression_status.json) |

## sidecar_parse (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/quant/check_sidecar_parse_policy.py` | `quant` | 6/10 | Validate quant sidecar parse policy contract. | - |

## sidecar_probe (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/quant/sidecar_probe.py` | `quant` | 5/10 | Emit normalized sidecar probe payload. | - |

## skill_contracts (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/check_skill_contracts.py` | `governance` | 5/10 | Validate Skill manifest contract compliance. | - |

## smoke (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/governance/release_smoke.py` | `governance` | 4/10 | One-command local release smoke | [`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/tuning_manifest.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/tuning_manifest.json)<br>[`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/convergence_report.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/convergence_report.json)<br>[`benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/long_run_recommended_matrix.json`](../../benchmarks/results/streaming/non_quant_live/tuner_provider_ready_smoke/qwen3.5-4b/long_run_recommended_matrix.json) |

## stream_scenario (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/streaming/run_stream_scenario.py` | `streaming` | 4/10 | Run a live stream scenario with law assertions. | - |

## telemetry_artifact (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/security/check_telemetry_artifact_fields.py` | `security` | 6/10 | Validate telemetry artifact lane/profile and canonical token states. | - |

## textmystery (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/extensions/play_textmystery.py` | `extensions` | 3/10 | Launch TextMystery interactive play mode. | - |

## textmystery_bridge (2)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/extensions/register_textmystery_bridge_extension.py` | `extensions` | 4/10 | register textmystery bridge extension | - |
| `scripts/extensions/run_textmystery_bridge_workload.py` | `extensions` | 4/10 | Run TextMystery bridge extension workload. | - |

## textmystery_easy (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/extensions/run_textmystery_easy_smoke.py` | `extensions` | 4/10 | One-command TextMystery bridge smoke run (direct SDK/local contract). | - |

## textmystery_policy (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/extensions/run_textmystery_policy_conformance.py` | `extensions` | 5/10 | Run TextMystery policy conformance tests (hint/disambiguation gates). | - |

## thermal_stability (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/quant/thermal_stability_profiler.py` | `quant` | 6/10 | Build thermal stability artifact from quant/context sweep summaries. | - |

## valid_run (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/quant/check_valid_run_policy.py` | `quant` | 6/10 | Validate default valid-run frontier/recommendation policy from quant summary. | - |

## volatility_boundaries (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/benchmarks/check_volatility_boundaries.py` | `benchmarks` | 8/10 | check volatility boundaries | - |

## vram_fragmentation (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/quant/analyze_vram_fragmentation.py` | `quant` | 6/10 | Experimental VRAM fragmentation analyzer for quant sweep summaries. | - |

## windows_backup (1)

| Script | Domain | Rating | Purpose | Recent Artifact Links |
|---|---|---:|---|---|
| `scripts/ops/setup_windows_backup.ps1` | `ops` | 2/10 | setup windows backup | - |

