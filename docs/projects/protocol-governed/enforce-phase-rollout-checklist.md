# Protocol Enforce-Phase Rollout Checklist (v1)

Last updated: 2026-03-05  
Status: Active  
Owner: Orket Core

This checklist is the operational gate for moving protocol-governed runtime from compat observation to enforce-by-default.

## Pre-Conditions

1. `docs/projects/protocol-governed/requirements.md` is the active runtime contract.
2. `docs/projects/protocol-governed/implementation-plan.md` active slices are up to date.
3. `docs/projects/protocol-governed/determinism-control-surface.md` matches runtime fields in settings and receipts.

## Campaign Windows

Run and retain evidence for at least two operator windows:

1. Window A (baseline traffic mix)
2. Window B (peak/variance traffic mix)

For each window, capture:

1. replay campaign artifact (`--strict`)
2. ledger parity campaign artifact (`--strict`)
3. rollout bundle publication output
4. error-family summary output

## Required Commands

1. `python scripts/MidTier/run_protocol_determinism_campaign.py --workspace-root <workspace> --runs-root <runs_root> --baseline-run-id <run_id> --strict`
2. `python scripts/MidTier/run_protocol_ledger_parity_campaign.py --workspace-root <workspace> --baseline-run-id <run_id> --strict`
3. `python scripts/MidTier/publish_protocol_rollout_artifacts.py --workspace-root <workspace> --out-dir benchmarks/results/protocol_governed/rollout_artifacts --baseline-run-id <run_id> --strict`
4. `python scripts/MidTier/summarize_protocol_error_codes.py --workspace-root <workspace> --strict`

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

1. deterministic replay mismatch regression in production window
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
