# Governed Agent Loop Slice 6F Proof

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-07
Status: Implemented scheduled-ingress checkpoint; lane remains active
Observed path: `primary`
Observed result: `success`
Proof classification: integration and end-to-end scheduled control path;
durable SQLite, authenticated API, DST, misfire, coalescing, rollback, restart,
inspection, and supervisor proof

## Outcome

Slice 6F adds one supported scheduled-ingress path without adding a second
runtime loop. An authenticated caller submits a bounded evaluation window with
explicit schedule and dispatch inputs. The application deterministically
interprets local occurrence times and publishes the evaluation receipt plus at
most one selected wake in one SQLite transaction. The existing API-owned
supervisor remains the sole consumer and execution owner.

## Observed Behaviors

1. IANA timezone conversion uses naive local time plus explicit DST fold and
   retains canonical UTC conversion in the trigger receipt.
2. Nonexistent local times, noncanonical folds, future occurrences, unknown
   fields, invalid grace, and unsupported policy values fail closed.
3. Misfire grace is bounded from 0 through 86400 seconds. `skip` retains a
   durable evaluation without queue work; `fire_once` admits missed work.
4. Fixed `latest` coalescing selects at most one eligible occurrence and records
   every coalesced or skipped occurrence identity.
5. The schedule evaluation receipt and selected `source=scheduled` wake commit
   atomically. An injected receipt-write failure rolls the wake insertion back.
6. Exact evaluation replay is idempotent. Contradictory reuse conflicts and
   preserves the original receipt and wake.
7. Direct publication of scheduled provenance through the general queue adapter
   fails closed; only the schedule repository admits it.
8. API restart preserves evaluation and wake truth. Wake and run inspection
   expose trigger metadata, and composed run inspection resolves the durable
   evaluation receipt.
9. A scheduled wake reaches the existing real external-child loop and terminal
   verifier truth under API-owned supervision, with zero tracked tasks after
   lifespan shutdown.

## Verification

Focused command:

```text
ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_governed_agent_cli.py tests/interfaces/test_governed_agent_api.py tests/integration/test_async_governed_agent_wake_repository.py tests/integration/test_governed_agent_scheduled_wakes.py tests/integration/test_governed_agent_wake_controls.py tests/integration/test_governed_agent_wake_dispatcher.py tests/integration/test_governed_agent_supervisor.py tests/integration/test_governed_agent_effect_service.py tests/runtime/test_governed_agent_loop.py tests/interfaces/test_api_composition_isolation.py tests/application/test_control_plane_workload_authority_governance.py
```

Observed result: `78 passed in 41.70s`.

Structural and canonical gates:

1. changed-path Ruff: pass;
2. focused mypy with skipped external imports: 11
   schedule/queue/runtime/interface source files passed;
3. canonical repository suite: `4525 passed, 56 skipped, 2 warnings in
   547.57s`; the warnings remain the known deprecated `orket.domain` import and
   low governed-output token warning;
4. dependency direction with legacy-edge enforcement set to fail: pass;
5. docs project hygiene: pass;
6. strict governed-agent and architectural-truth docs lint: pass;
7. new-file and touched-function size gates: pass;
8. `git diff --check`: pass apart from existing line-ending notices;
9. architectural-truth baseline: `collection_ok=true`,
   `release_ready=false` because active architectural exceptions and red/noisy
   proof gates remain.

## Not Verified

1. An embedded or external always-on timer that discovers evaluation windows;
   Slice 6F begins at authenticated, fully materialized schedule evaluation.
2. Webhook authentication, delivery deduplication, or replay protection; Slice
   6G subsequently proves those paths.
3. Generalized effect approval/resolution dispatch from a wake.
4. Live Ollama inference specifically from scheduled ingress; Slice 6E already
   proves the unchanged supervisor/provider path with live fixed roles.

## Remaining Blockers or Drift

1. Slice 6G subsequently closes webhook ingress. Generalized wake-driven effect
   handling remains a separate checked Slice 6 increment.
2. Scheduler callers must supply stable, non-overlapping evaluation windows;
   Orket does not yet own timer discovery.
3. `AT-EX-003` and wider architectural-truth release-readiness debt remain.
4. Slice 7 release proof and explicit user acceptance remain open.
