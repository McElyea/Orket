# Gitea Runner Container Lifecycle Closeout

Last updated: 2026-03-12
Status: Archived
Owner: Orket Core

## Scope Closed

This lane closed the gap between sandbox cleanup proof and local Gitea runner lifecycle truth.

What is now proven:
1. the repo has a truthful local inspector for `gitea/act_runner` containers and stale runner registrations
2. the real local Gitea workflow route can start clean, run, and end clean without leaving non-infrastructure containers behind
3. temporary repo-scoped runners and temporary Gitea API tokens created by the proof route are torn down after use
4. the local Docker sandbox acceptance route still ends clean in the same session

## Live Result

Observed on 2026-03-12:
1. `python scripts/gitea/run_local_runner_lifecycle_proof.py`
   - workflow: `monorepo-packages-ci.yml`
   - run id: `15`
   - result: `success`
   - attempts: `3`
2. post-run verification:
   - `docker ps -a` showed only `vibe-rail-gitea`
   - `python scripts/gitea/inspect_local_runner_containers.py` returned `PASS`
   - repo runner list for `Orket/Orket` returned `total_count=0`
   - local Gitea `access_token` table retained only the pre-existing `Orket` token
3. Docker sandbox revalidation:
   - live acceptance slice returned `13 passed`
   - post-run Docker/Gitea cleanup checks remained clean

## Canonical Evidence

1. `benchmarks/results/gitea/local_runner_lifecycle_proof.json`
2. `tests/acceptance/test_sandbox_orchestrator_live_docker.py`
3. `tests/acceptance/test_sandbox_runtime_recovery_live_docker.py`
4. `tests/acceptance/test_sandbox_orphan_reconciliation_live_docker.py`
5. `tests/acceptance/test_sandbox_restart_reclaim_live_docker.py`
6. `tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py`
7. `tests/acceptance/test_sandbox_cleanup_leak_gate.py`
8. `tests/acceptance/test_sandbox_cleanup_claim_race.py`
9. `tests/acceptance/test_sandbox_store_outage_fail_closed.py`

## Notes

1. No new local Gitea workflow definition was required for closure. During no-push mode, the proof route reused the existing local `monorepo-packages-ci.yml` workflow already present in the local Gitea repo.
2. The active Docker sandbox lane remains archived separately in [docs/projects/archive/Docker/03-CLOSEOUT.md](docs/projects/archive/Docker/03-CLOSEOUT.md). This closeout covers the runner lifecycle gap that sandbox cleanup never governed.
