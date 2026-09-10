# Governed Agent Loop Slice 6A Proof

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-07
Status: Implemented bounded queue/supervisor substrate; lane remains active
Observed path: `primary`
Observed result: `success`
Proof classification: integration and structural; no live model or public API

## Outcome

Slice 6A implements and proves the first checked Slice 6 increment without
crossing the then-open architectural-truth B2 boundary. The durable queue, claim,
fencing, expiry-recovery, bounded supervisor, container teardown, and wake
inspection primitives work against real SQLite state. Production continuous
operation is not claimed. B2 was subsequently completed in the next bounded
slice, so the production-composition prerequisite is now cleared.

## Observed Behaviors

1. Equivalent enqueue is idempotent across repository reconstruction.
2. Wake-id or deduplication-key reuse with contradictory payload is rejected.
3. Two concurrent repository instances obtain only one claim for one wake.
4. Release and reclaim advance fencing generation and reject stale completion.
5. Capacity limits return explicit backpressure without consuming another wake.
6. Renewal and cancellation compare against retained claim authority.
7. Expired claims become uncertain `recovery_required` state and cannot be
   redispatched until child stop and effect reconciliation are both confirmed.
8. Cancellation during dispatch fences the would-be result publication.
9. Supervisor failure and shutdown preserve recovery truth instead of requeueing
   uncertain work.
10. Application-container shutdown leaves no tracked supervisor task and closes
    the engine.
11. Existing-run inspection reconstructs wake and claim state from SQLite.
12. Scheduled source tokens and malformed targets, timestamps, or payloads fail
    closed.

## Verification

Focused integration and regression command:

```text
python -m pytest -q tests/integration/test_async_governed_agent_wake_repository.py tests/integration/test_governed_agent_supervisor.py tests/runtime/test_governed_agent_loop.py tests/interfaces/test_governed_agent_cli.py tests/interfaces/test_api_composition_isolation.py
```

Observed result: `23 passed in 11.38s`.

Canonical repository command:

```text
ORKET_DISABLE_SANDBOX=1 python -m pytest -q
```

Observed result: `4506 passed, 55 skipped, 2 warnings in 471.03s`.

Observed structural results:

1. touched-path Ruff: pass;
2. focused mypy with external imports skipped: 6 source files, no issues;
3. new-file size gate: no production file over 400 lines;
4. new-function size gate: no function over 70 lines;
5. dependency-direction gate: pass;
6. docs project hygiene: pass;
7. governed-agent strict docs lint: 9 files, 0 violations;
8. architectural-truth baseline regeneration: `collection_ok=true`,
   `release_ready=false` because the recorded pre-existing architecture,
   taxonomy, and repository-wide lint debt remains.

Repository-wide mypy is not a truthful gate in the current tree because
pre-existing compatibility-module errors remain outside this slice.

## Not Verified

1. Public CLI or HTTP wake submission.
2. Production API lifespan startup of the supervisor.
3. Existing agent-loop, broker, provider, or effect dispatch from a wake.
4. Wake-fence validation inside every current broker call and effect dispatch.
5. Provider-specific local-capacity admission.
6. Scheduled timezone/missed-trigger/coalescing behavior.
7. Webhook authentication, deduplication, or replay protection.
8. Live Ollama execution through a continuous supervisor.
9. Full session inspection of approval/effect state through one composed view.

## Remaining Blockers or Drift

1. `AT-EX-002` is resolved by the subsequent B2 checkpoint; Slice 6A itself did
   not activate production supervision.
2. `AT-EX-003` remains active for broader interface composition ownership.
3. The subsequent Slice 6B checkpoint closes production dispatcher, provider
   capacity, authenticated API ingress, inspector composition, and app-lifespan
   teardown; Slice 6C closes public manual transport; Slice 6D closes durable
   wake cancellation/recovery controls; Slice 6E closes live Ollama supervisor
   proof; Slice 6F closes scheduled ingress; and Slice 6G closes HMAC webhook
   ingress. Generalized wake-driven effects/recovery remain.
4. Slice 7 release proof and user acceptance remain open.
