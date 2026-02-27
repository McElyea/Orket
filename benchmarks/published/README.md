# Published Benchmark Highlights

Last updated: 2026-02-27

This folder contains curated benchmark artifacts suitable for sharing.

## Start Here
1. `odr_live_io.json`
   - Best single-file walkthrough of ODR behavior with concrete inputs/outputs.
2. `odr_experiment_role_matrix_v1_pilot.json`
   - Best model-role pairing snapshot with explicit scoring and hard-fail visibility.
3. `live_card_100_scored_report.json`
   - Best quality-at-scale summary.
4. `live_100_determinism_report.json`
   - Best determinism-at-scale summary.

## Highlights

| Artifact | Why it matters | Key signal |
|---|---|---|
| `odr_live_io.json` | Demonstrates real ODR stop logic and parser behavior with trace payloads | Includes `DIFF_FLOOR` and `SHAPE_VIOLATION` examples with full round records |
| `odr_experiment_role_matrix_v1_pilot.json` | Shows role-level model evaluation using objective scoring | Captures both normal runs (`score_total: 70`) and hard-fail case (`score_total: 1100`, `anti_hallucination_hits: 1`) |
| `live_card_100_scored_report.json` | Shows production-style quality scoring across 100 tasks | `overall_avg_score: 4.97`, deterministic per-task scoring bands |
| `live_100_determinism_report.json` | Verifies deterministic behavior across broad task surface | `total_tasks: 100`, `deterministic_tasks: 100`, `determinism_rate: 1.0` |
| `odr_live_role_matrix.qwen14b_r1_32b.json` | Full live role matrix trace for one pairing | Round-level architect/auditor outputs + ODR trace records |
| `odr_live_role_matrix.qwen14b_gemma27b.json` | Full live role matrix trace for alternate auditor pairing | Useful for side-by-side pairing comparisons |

## Suggested Use
1. External demo: start with `odr_live_io.json` then `live_card_100_scored_report.json`.
2. Technical review: start with `odr_experiment_role_matrix_v1_pilot.json` then inspect the two full role-matrix traces.
3. Stability proof: pair `live_100_determinism_report.json` with the ODR artifacts.

## Notes
1. These are curated copies from `benchmarks/results/`.
2. Keep sensitive/local-only paths out of public artifacts when adding new files.
