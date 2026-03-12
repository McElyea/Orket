# Gitea Runner Container Lifecycle Implementation Plan

Last updated: 2026-03-12
Status: Completed
Owner: Orket Core
Lane type: Priority investigation and remediation

Acceptance standard:
1. start clean
2. run the real route
3. end clean
4. no non-infrastructure containers remain
5. no stale runner registrations remain
6. partial proof does not count

## Objective

Eliminate unexplained lingering local `gitea/act_runner` containers by making runner-container lifecycle:
1. explicit
2. inspectable
3. safe to clean
4. truthfully scoped relative to Docker sandbox cleanup
5. compliant with the rule that any containerized route must have a proven done-to-teardown path or lose container privileges

## Delivered Work

1. Truthful scope correction:
   - [docs/ROADMAP.md](docs/ROADMAP.md) reopened the runner-lifecycle lane when live local evidence showed the archived Docker sandbox lane never governed local Gitea runner host containers.
   - [docs/projects/archive/Docker/03-CLOSEOUT.md](docs/projects/archive/Docker/03-CLOSEOUT.md) was corrected so it no longer overclaims sandbox cleanup scope.
2. Local inspection authority:
   - [scripts/gitea/inspect_local_runner_containers.py](scripts/gitea/inspect_local_runner_containers.py) now classifies persistent runner hosts, safe stray cleanup candidates, and stale runner registrations.
   - [tests/scripts/test_inspect_local_runner_containers.py](tests/scripts/test_inspect_local_runner_containers.py) locks the classifier and stale-registration contract.
3. Real-route teardown proof:
   - [scripts/gitea/run_local_runner_lifecycle_proof.py](scripts/gitea/run_local_runner_lifecycle_proof.py) dispatches a real local Gitea workflow, drives repo-scoped ephemeral runners until the workflow completes, removes any leftover non-infrastructure containers, and deletes temporary API tokens from local Gitea state.
   - [scripts/gitea/local_runner_lifecycle_support.py](scripts/gitea/local_runner_lifecycle_support.py) holds the Docker/Gitea support logic used by the proof route.
   - [tests/scripts/test_run_local_runner_lifecycle_proof.py](tests/scripts/test_run_local_runner_lifecycle_proof.py) locks the proof-script contract surface.

## Live Proof Summary

1. Real Gitea workflow route:
   - `python scripts/gitea/run_local_runner_lifecycle_proof.py`
   - observed workflow: `monorepo-packages-ci.yml`
   - observed run: `15`
   - observed result: `success`
   - observed runner attempts: `3`
   - post-run state:
     - `docker ps -a` showed only `vibe-rail-gitea`
     - `python scripts/gitea/inspect_local_runner_containers.py` returned `PASS`
     - repo runner list for `Orket/Orket` was empty
     - local Gitea `access_token` cleanup removed the temporary proof token
   - canonical evidence path: `benchmarks/results/gitea/local_runner_lifecycle_proof.json`
2. Docker sandbox route revalidation in the same session:
   - `$env:ORKET_RUN_SANDBOX_ACCEPTANCE='1'; python -m pytest -q tests/acceptance/test_sandbox_orchestrator_live_docker.py tests/acceptance/test_sandbox_runtime_recovery_live_docker.py tests/acceptance/test_sandbox_orphan_reconciliation_live_docker.py tests/acceptance/test_sandbox_restart_reclaim_live_docker.py tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py tests/acceptance/test_sandbox_cleanup_leak_gate.py tests/acceptance/test_sandbox_cleanup_claim_race.py tests/acceptance/test_sandbox_store_outage_fail_closed.py`
   - observed result: `13 passed`
   - post-run state:
     - `docker ps -a` showed only `vibe-rail-gitea`
     - `python scripts/gitea/inspect_local_runner_containers.py` returned `PASS`

## Definition of Done

Met on 2026-03-12.

1. The roadmap and Docker closeout no longer overclaim sandbox scope.
2. The local Gitea workflow route has live start-clean -> run-real-route -> end-clean proof.
3. No non-infrastructure containers remain after the proved route.
4. No stale runner registrations remain after the proved route.
5. Persistent containerized runner hosts are no longer treated as acceptable infrastructure in process guidance.
