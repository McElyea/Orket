# Published Benchmark Index

Last updated: 2026-03-14

This directory is the curated, share-safe benchmark lane.

## Folder Layout
1. `General/`
2. `ODR/`
3. `index.json`
   - Machine-readable catalog for automation and dashboards.

## Latest Highlight
1. `General/live_runtime_stability_claim_e_closure_qwen2_5_coder_7b_2026-03-14.json` (`PUB-GEN-006`)
   - Curated closure packet for the remaining deterministic-drift gap in runtime-stability Claim E, including pre-resolution drift, final governed compare scope, three-run strict-compare success, replay success, and provenance.

## Artifact Directory

| ID | Category | File | Title | What it proves | Key signals |
|---|---|---|---|---|---|
| PUB-ODR-001 | ODR | `ODR/odr_live_io.json` | ODR Live IO Core Evidence | Compact ODR live test artifact with explicit input/output and stop reason traces. | `DIFF_FLOOR`, `SHAPE_VIOLATION`, `trace_record_examples` |
| PUB-ODR-002 | ODR | `ODR/odr_experiment_role_matrix_v1_pilot.json` | ODR Role Matrix Pilot Scoring | Pilot role-matrix experiment report with scoring and hard-fail visibility. | `score_total`, `anti_hallucination_hits`, `hard_fail` |
| PUB-ODR-003 | ODR | `ODR/odr_live_role_matrix.qwen14b_r1_32b.json` | Live Role Matrix Trace (Qwen14b + R1-32b) | Full round-level live run for architect/auditor pairing A. | `round_level_io`, `odr_trace`, `live_model_pairing` |
| PUB-ODR-004 | ODR | `ODR/odr_live_role_matrix.qwen14b_gemma27b.json` | Live Role Matrix Trace (Qwen14b + Gemma27b) | Full round-level live run for architect/auditor pairing B. | `round_level_io`, `odr_trace`, `live_model_pairing` |
| PUB-GEN-001 | General | `General/live_card_100_scored_report.json` | Live Card 100 Scored Report | Quality scoring summary across 100 live-card tasks. | `overall_avg_score`, `per_task_score_bands`, `pass_rate` |
| PUB-GEN-002 | General | `General/live_100_determinism_report.json` | Live 100 Determinism Report | Determinism evidence across 100 tasks using hash-based repeatability checks. | `determinism_rate`, `deterministic_tasks`, `unique_hashes` |
| PUB-GEN-005 | General | `General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13.json` | Live Runtime Stability Proof (Qwen2.5 Coder 7B) | Curated live proof package for runtime-stability closeout: acceptance success, replay success, fail-closed boundary evidence, fresh strict-compare drift, and governed-runtime manifest success. | `provider_preflight_pass`, `protocol_replay_ok`, `deterministic_match_false`, `governed_manifest_success`, `live_output_drift` |
| PUB-GEN-006 | General | `General/live_runtime_stability_claim_e_closure_qwen2_5_coder_7b_2026-03-14.json` | Live Runtime Stability Claim E Closure (Qwen2.5 Coder 7B) | Curated closure packet for the remaining deterministic-drift gap in runtime-stability Claim E, including pre-resolution drift, final governed compare scope, three-run strict-compare success, replay success, and provenance. | `claim_e_closure`, `deterministic_match_true`, `three_run_pairwise_success`, `protocol_replay_ok`, `compare_scope_delta` |

## Reading Paths
1. Product walkthrough: `PUB-ODR-001` -> `PUB-GEN-001` -> `PUB-GEN-002`
2. Model-role science: `PUB-ODR-002` -> `PUB-ODR-003` -> `PUB-ODR-004`

## Publish Workflow
1. Copy curated artifact(s) into the correct category folder.
2. Add/update artifact rows in `index.json`.
3. Regenerate this README:
```bash
python scripts/governance/sync_published_index.py --write
```
4. Validate before commit:
```bash
python scripts/governance/sync_published_index.py --check
```
5. Only add artifacts here after explicit user approval and manual review.
6. Do not overwrite prior published artifacts; add versioned files instead.

