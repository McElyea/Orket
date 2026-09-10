# Governed Agent Loop Slice 6D Proof

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-07
Status: Implemented wake-control checkpoint; lane remains active
Observed path: `primary`
Observed result: `success`
Proof classification: integration and end-to-end local control paths; durable
SQLite, authenticated API, CLI, restart, capacity, and inspection proof

## Outcome

Slice 6D adds supported wake-level cancellation and recovery without weakening
the conservative uncertainty barrier. Every state-evaluated control publishes
its canonical `OperatorActionRecord`, wake-transition receipt, and resulting
wake in one SQLite transaction. Recovery can
requeue an expired claim or confirm a cancelled claim only after the caller
supplies the matching fence, confirms child termination and effect
reconciliation, and records nonempty evidence references.

This is wake-level queue control. It does not replace the existing run-level
`orket agent cancel` authority or authorize a new run continuation, model call,
effect, approval, or final-truth transition.

## Observed Behaviors

1. Cancelling a queued wake closes it without uncertainty; cancelling a claimed
   wake fences its owner and retains uncertainty and capacity.
2. `confirm_cancelled` clears a cancelled claim's uncertainty without
   requeueing it; `requeue` applies only to `recovery_required` work.
3. Both recovery resolutions require matching fencing generation, confirmed
   child stop, cleared effect uncertainty, and evidence references.
4. A missing precondition or stale epoch leaves the wake unchanged and writes a
   durable conflict or stale receipt plus its canonical operator-action result.
5. Repeating the exact action id and request is idempotent; contradictory reuse
   conflicts and preserves the original receipt.
6. Action payloads, digests, actor, time, result status, resulting wake
   authority, and canonical operator-action linkage are inspectable through
   CLI, API, and composed run inspection.
7. API controls retain the existing `/v1` authentication boundary and survive
   app restart.

## Verification

Focused command:

```text
ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_governed_agent_cli.py tests/interfaces/test_governed_agent_api.py tests/integration/test_async_governed_agent_wake_repository.py tests/integration/test_governed_agent_wake_controls.py tests/integration/test_governed_agent_wake_dispatcher.py tests/integration/test_governed_agent_supervisor.py tests/integration/test_governed_agent_effect_service.py tests/runtime/test_governed_agent_loop.py tests/interfaces/test_api_composition_isolation.py tests/application/test_control_plane_workload_authority_governance.py
```

Observed result: `72 passed in 35.88s`.

Structural gates:

1. touched-path Ruff: pass;
2. focused mypy with skipped external imports: 8 control/runtime/interface
   source files passed;
3. dependency direction with legacy-edge enforcement set to fail: pass;
4. docs project hygiene: pass;
5. strict governed-agent docs lint: 13 files, 0 violations;
6. strict architectural-truth docs lint: 6 files, 0 violations;
7. all new Python files remain at or below 400 lines, no touched function
   exceeds 70 lines, and runtime/control classes expose at most 10 public
   methods;
8. canonical repository suite: `4519 passed, 56 skipped, 2 warnings in
   453.01s`; the warnings remain the known deprecated `orket.domain` import and
   low governed-output token warning;
9. architectural-truth baseline: `collection_ok=true`,
   `release_ready=false` because active architectural exceptions and red/noisy
   proof gates remain.

## Not Verified

1. Scheduled timezone, missed-trigger, or coalescing behavior.
2. Webhook authentication, delivery deduplication, or replay protection for
   governed-agent wakes.
3. Generalized effect approval/resolution dispatch from a wake.
4. Live Ollama inference through the continuously running supervisor was not
   part of the 6D checkpoint; Slice 6E subsequently proves it.

## Remaining Blockers or Drift

1. Slice 6F subsequently closes scheduled ingress and Slice 6G closes HMAC
   webhook ingress. Generalized wake-driven effect handling remains open in
   Slice 6.
2. Live Ollama supervisor proof was subsequently completed in Slice 6E.
3. `AT-EX-003` and the wider architectural-truth release-readiness debt remain.
4. Slice 7 release proof and explicit user acceptance remain open.
