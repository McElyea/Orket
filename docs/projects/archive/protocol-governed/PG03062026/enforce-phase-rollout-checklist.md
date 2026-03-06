# Protocol Enforce-Phase Rollout Checklist (v1)

Last updated: 2026-03-06  
Status: Archived (execution complete; superseded by recurring maintenance)  
Owner: Orket Core

This checklist is the operational gate for moving protocol-governed runtime from compat observation to enforce-by-default.

Recurring execution owner:
1. `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`

## Pre-Conditions

1. `docs/projects/protocol-governed/requirements.md` is the active runtime contract.
2. `docs/projects/archive/protocol-governed/PG03062026/implementation-plan.md` captures the completed execution slices.
3. `docs/projects/protocol-governed/determinism-control-surface.md` matches runtime fields in settings and receipts.

## Campaign Windows

Run and retain evidence for at least two operator windows using staged or replayed pre-production runs:

1. Window A (baseline staged/replayed traffic mix)
2. Window B (peak/variance staged/replayed traffic mix)

For each window, capture:

1. replay campaign artifact (`--strict`)
2. ledger parity campaign artifact (`--strict`)
3. rollout bundle publication output
4. error-family summary output

## Required Commands

1. `python scripts/protocol/run_protocol_determinism_campaign.py --runs-root <runs_root> --baseline-run-id <run_id> --strict --out <replay_out_json>`
2. `python scripts/protocol/run_protocol_ledger_parity_campaign.py --sqlite-db <sqlite_db> --protocol-root <workspace_root> --session-id <session_id> --strict --out <parity_out_json>`
3. `python scripts/protocol/publish_protocol_rollout_artifacts.py --workspace-root <workspace_root> --out-dir <rollout_out_dir> --run-id <run_id> --session-id <session_id> --baseline-run-id <run_id> --strict`
4. `python scripts/protocol/summarize_protocol_error_codes.py --input <replay_out_json> --input <parity_out_json> --out <error_summary_out_json> --strict`
5. `python scripts/protocol/record_protocol_enforce_window_signoff.py --window-id <window_id> --window-date <yyyy-mm-dd> --replay-campaign <replay_out_json> --parity-campaign <parity_out_json> --rollout-bundle <rollout_bundle_json> --error-summary <error_summary_out_json> --retry-spike-status <pass|fail|unknown> --approver <approver_label> --out <signoff_out_json> --strict`

Equivalent module form is also valid (`python -m scripts.protocol.<script_name_without_py>`).

One-command wrapper (runs all five commands in order and emits a capture manifest):
1. `python scripts/protocol/run_protocol_enforce_window_capture.py --window-id <window_id> --window-date <yyyy-mm-dd> --workspace-root <workspace_root> --run-id <run_id> --session-id <session_id_or_blank> --retry-spike-status <pass|fail|unknown> --approver <approver_label> --out-root <window_out_root> --strict`

Cutover readiness gate (consumes captured window manifests):
1. `python scripts/protocol/check_protocol_enforce_cutover_readiness.py --manifest <window_a_manifest_json> --manifest <window_b_manifest_json> --min-pass-windows 2 --out <cutover_readiness_out_json> --strict`

Production-rollout note:
1. Production-window operator sign-off is not required until a production rollout exists.
2. Do not block enforce cutover readiness on unavailable production traffic inputs.

## Hard Gates

All gates must be green in both windows:

1. replay campaign `all_match == true`
2. ledger parity campaign `all_match == true`
3. rollout artifact publication exits zero and updates latest pointers
4. no unresolved P0/P1 protocol error families in summary
5. no sustained retry spike attributable to strict protocol rejections

## Cutover Steps

1. Set runtime default policy to enforce mode in deployment config.
2. Keep rollback switch documented and ready (`compat` mode path).
3. Deploy incrementally (canary then broad rollout).
4. Validate first post-cutover campaign window with strict comparators.

## Rollback Criteria

Rollback to compat mode if any of the following occurs:

1. deterministic replay mismatch regression in any enforced validation window (pre-production or production)
2. parity mismatch regression with unexplained delta signatures
3. sustained protocol validation failure spike causing operational instability
4. unresolved high-severity protocol error family introduced by cutover

## Sign-Off Template

Record sign-off per window:

1. Window ID/date:
2. Replay campaign artifact path:
3. Parity campaign artifact path:
4. Rollout bundle path:
5. Error summary path:
6. Gate status (`PASS`/`FAIL`):
7. Approver:

## Latest Execution (2026-03-05)

Window A:
1. Window ID/date: `window_a / 2026-03-05`
2. Replay campaign artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_a/protocol_replay_campaign.json`
3. Parity campaign artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_a/protocol_ledger_parity_campaign.json`
4. Rollout bundle path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_a/rollout_artifacts/protocol_rollout_bundle.latest.json`
5. Error summary path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_a/protocol_error_code_summary.json`
6. Gate status (`PASS`/`FAIL`): `PASS`
7. Approver: `Orket Core (local quality workspace)`
8. Operator sign-off artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_a/protocol_operator_signoff.json`

Window B:
1. Window ID/date: `window_b / 2026-03-05`
2. Replay campaign artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_b/protocol_replay_campaign.json`
3. Parity campaign artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_b/protocol_ledger_parity_campaign.json`
4. Rollout bundle path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_b/rollout_artifacts/protocol_rollout_bundle.latest.json`
5. Error summary path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_b/protocol_error_code_summary.json`
6. Gate status (`PASS`/`FAIL`): `PASS`
7. Approver: `Orket Core (local quality workspace)`
8. Operator sign-off artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_b/protocol_operator_signoff.json`

Cutover readiness gate:
1. Command: `python scripts/protocol/check_protocol_enforce_cutover_readiness.py --manifest benchmarks/results/protocol/protocol_governed/enforce_phase/window_default/protocol_window_capture_manifest.json --manifest benchmarks/results/protocol/protocol_governed/enforce_phase/window_wrapper_live_2026-03-06/protocol_window_capture_manifest.json --min-pass-windows 2 --out benchmarks/results/protocol/protocol_governed/enforce_phase/cutover_readiness/protocol_enforce_cutover_readiness.json --strict`
2. Output artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/cutover_readiness/protocol_enforce_cutover_readiness.json`
3. Gate status (`PASS`/`FAIL`): `PASS`

Pre-production staged/replayed validation windows:
1. Window ID/date: `window_preprod_stage_a / 2026-03-05`
2. Capture manifest artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_preprod_stage_a/protocol_window_capture_manifest.json`
3. Gate status (`PASS`/`FAIL`): `PASS`
4. Approver: `Orket Core (staged replay)`
5. Window ID/date: `window_preprod_stage_b / 2026-03-05`
6. Capture manifest artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/window_preprod_stage_b/protocol_window_capture_manifest.json`
7. Gate status (`PASS`/`FAIL`): `PASS`
8. Approver: `Orket Core (staged replay)`

Pre-production cutover readiness gate:
1. Command: `python scripts/protocol/check_protocol_enforce_cutover_readiness.py --manifest benchmarks/results/protocol/protocol_governed/enforce_phase/window_preprod_stage_a/protocol_window_capture_manifest.json --manifest benchmarks/results/protocol/protocol_governed/enforce_phase/window_preprod_stage_b/protocol_window_capture_manifest.json --min-pass-windows 2 --out benchmarks/results/protocol/protocol_governed/enforce_phase/cutover_readiness/protocol_enforce_cutover_readiness_preprod.json --strict`
2. Output artifact path: `benchmarks/results/protocol/protocol_governed/enforce_phase/cutover_readiness/protocol_enforce_cutover_readiness_preprod.json`
3. Gate status (`PASS`/`FAIL`): `PASS`
