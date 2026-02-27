# Orket Docs Index

Last reviewed: 2026-02-27

This index is the canonical map for `docs/*.md` (excluding `docs/projects/**`).

## Primary Documents
1. `docs/ROADMAP.md`
   - Active execution priority and project index.
2. `docs/ARCHITECTURE.md`
   - Runtime layers, dependency direction, and decision-node boundaries.
3. `docs/RUNBOOK.md`
   - Operator startup, health checks, and incident response.
4. `docs/SECURITY.md`
   - API/webhook trust boundary and required posture.
5. `docs/TESTING_POLICY.md`
   - Test lanes and required command set.
6. `docs/API_FRONTEND_CONTRACT.md`
   - Implemented API and websocket surface expected by UI clients.

## Operational Extensions
1. `docs/GITEA_WEBHOOK_SETUP.md`
2. `docs/GITEA_STATE_OPERATIONAL_GUIDE.md`
3. `docs/GITEA_BACKUP_STRATEGY.md`
4. `docs/QUANT_SWEEP_RUNBOOK.md`
5. `docs/PRODUCT_PUBLISHING.md`
6. `docs/LOCAL_CLEANUP_POLICY.md`

## Governance and Process
1. `docs/CONTRIBUTOR.md` is the process source of truth.
2. `docs/PR_REVIEW_POLICY.md` defines PR review cycle policy.
3. Active project plans live under `docs/projects/<project>/` and must be indexed in `docs/ROADMAP.md`.
4. `docs/PUBLISHED_ARTIFACTS_POLICY.md` defines the canonical publish workflow for `benchmarks/published/`.

## Historical / Context
1. `docs/PROJECT.md`
2. `docs/VOLATILITY_BASELINE.md`
3. `docs/BENCHMARK_DETERMINISM.md`
4. `docs/BENCHMARK_FAILURE_LEDGER.md`
5. `docs/architecture/` snapshots and ADR materials.

## Deprecated or Transitional Docs
These files are retained for context but are not execution sources:
1. `docs/PROGRAM_LEVEL_TASK_001_PROMPT_AND_RUBRIC.md`
2. `docs/examples.md`
3. `docs/bottleneck_thresholds.md`

When content is promoted into a canonical doc, remove duplication from transitional files.
