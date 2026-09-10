# Governed Agent Loop Slice 6B Proof

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-07
Status: Implemented production composition checkpoint; lane remains active
Observed path: `primary`
Observed result: `success`
Proof classification: integration, end-to-end, and structural; deterministic
provider with a real child/broker path, not live local-model proof

## Outcome

Slice 6B connects the Slice 6A durable queue to the canonical governed-agent
execution path without restoring module-default API ownership. Each factory app
owns one runtime graph. Authenticated API wake admission persists independently
of supervisor activation, while explicit activation processes one bounded claim
through the existing catalog, loop, child subprocess, broker, verifier, and
final-truth authorities.

## Observed Behaviors

1. API wake admission inherits the `/v1` API-key boundary; unauthenticated
   submission is rejected.
2. Identical API occurrences are idempotent and remain durable across complete
   FastAPI app teardown and reconstruction.
3. Continuous dispatch is disabled by default and reports its exact runtime,
   provider, and capacity posture.
4. Explicit deterministic activation runs the real external child and host
   broker through two sequential iterations and publishes verified final truth.
5. A later existing-run wake consumes terminal state without reopening the run
   or adding another iteration.
6. Active claims renew during a bounded dispatch and application teardown leaves
   no supervisor, renewal, dispatch, or child task owned by the app.
7. The durable active-claim limit is the provider/local capacity reservation;
   requests exceeding the configured inference-concurrency limit are released
   without child or provider work.
8. Cancelling a wake during provider work makes its guard stale before broker
   receipt publication. The durable call remains reserved with no fabricated
   result, and its uncertain wake continues to consume provider capacity until
   explicit recovery.
9. Provider selection and loop construction moved from the CLI interface into
   one application composition authority reused by CLI and API dispatch.
10. New-run wakes remain discoverable from the run inspector by their retained
    request identity even though they did not target a pre-existing run.
11. Inspection now composes wake/claim, run, attempt, iteration, role/model
    receipt, budget, context/evidence, effect, approval, checkpoint, operator
    action, continuation, and final-truth state, plus an operator summary.
12. Replay remains read-only and reconstructs decisions from durable snapshots.

## Verification

Focused production-path command:

```text
ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_governed_agent_api.py tests/integration/test_governed_agent_wake_dispatcher.py tests/integration/test_governed_agent_supervisor.py tests/integration/test_governed_agent_effect_service.py tests/runtime/test_governed_agent_loop.py tests/interfaces/test_governed_agent_cli.py tests/interfaces/test_api_composition_isolation.py
```

Observed result: `32 passed in 17.24s`.

Structural gates:

1. touched-path Ruff: pass;
2. dependency direction with legacy-edge enforcement set to fail: pass;
3. docs project hygiene: pass;
4. focused mypy with skipped external imports: 10 new Slice 6A-6B source files
   passed;
5. new and previously compliant production file-size and changed-function
   gates: pass, with every new Python file at or below 400 lines and no new or
   widened function above 70 lines; the pre-existing oversized API facade
   remains recorded architectural debt;
6. strict governed-agent docs lint: 10 files, 0 violations;
7. strict architectural-truth docs lint: 6 files, 0 violations;
8. canonical repository suite: `4512 passed, 55 skipped, 2 warnings in
   466.70s`; the warnings remain the known deprecated `orket.domain` import and
   low governed-output token warning.

## Not Verified

1. Live Ollama inference through the continuously running supervisor.
2. Scheduled timezone, missed-trigger, or coalescing behavior.
3. Webhook authentication, delivery deduplication, or replay protection.
4. Public manual-wake transport was outside the 6B proof boundary; Slice 6C
   subsequently adds and proves the durable CLI transport.
5. Generalized effect approval/resolution dispatch from a wake; existing
   issue-scoped effect authority is composed into inspection but remains a
   separately invoked application path.
6. Hostile extension isolation; V1 continues to admit operator-trusted code.
7. Cross-database queue and execution authority; the production composition
   deliberately uses one configured SQLite path.

## Remaining Blockers or Drift

1. Slice 6E subsequently closes live Ollama supervisor proof and Slice 6F closes
   scheduled ingress. Webhook policy and generalized wake-driven
   effect/recovery handling remain.
2. `AT-EX-003` remains active for broader interface-facade debt.
3. Slice 7 release proof and explicit user acceptance remain open.

## Exact Files Touched

Recorded in the final task report for the combined uncommitted Slice 6A, B2,
and Slice 6B worktree; this proof file identifies the Slice 6B authority and
verification boundary.
