# Governed Agent Loop Slice 6G Proof

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-07
Status: Implemented webhook-ingress checkpoint; lane remains active
Observed path: `primary`
Observed result: `success`
Proof classification: integration and end-to-end webhook control path; durable
SQLite, API key, HMAC, freshness, replay/conflict, rollback, restart,
inspection, real child, and supervisor teardown proof

## Outcome

Slice 6G adds one supported webhook ingress without creating another execution
owner. The endpoint retains the canonical `/v1` API-key boundary and adds a
configured issuer/key-bound HMAC-SHA256 check. One durable delivery receipt and
its selected webhook wake commit before the existing supervisor can claim work.

## Observed Behaviors

1. The signature covers the contract domain, route issuer, route delivery id,
   canonical UTC delivery timestamp, and raw-body SHA-256 digest.
2. Missing or invalid API credentials, issuer/key mismatch, malformed
   signatures, noncanonical UTC timestamps, stale deliveries, and excessively
   future deliveries and bodies over 1 MiB fail closed.
3. HMAC and freshness checks precede JSON interpretation. Authenticated bodies
   still pass the existing strict wake dispatch and iteration validators.
4. The webhook delivery receipt and selected `source=webhook` wake commit in
   one SQLite transaction. An injected receipt-write failure rolls back the
   wake insertion.
5. Exact signed raw-content retry is idempotent. Changed content under a
   retained issuer/delivery identity conflicts and preserves prior truth.
6. Direct publication of webhook provenance through the general queue adapter
   fails closed; only the webhook repository admits it.
7. Delivery records and wake trigger metadata retain issuer, delivery, key,
   delivered/received timestamps, and content digest across API restart.
   Signing secrets and raw signatures are absent from durable and API views.
8. Run inspection resolves the durable webhook delivery associated with its
   wake.
9. An authenticated webhook wake reaches the existing real external-child loop
   and terminal verifier truth under API-owned supervision, with zero tracked
   tasks after lifespan shutdown.

## Verification

Focused command:

```text
ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_governed_agent_cli.py tests/interfaces/test_governed_agent_api.py tests/interfaces/test_governed_agent_webhook_api.py tests/integration/test_async_governed_agent_wake_repository.py tests/integration/test_governed_agent_scheduled_wakes.py tests/integration/test_governed_agent_webhook_ingress.py tests/integration/test_governed_agent_wake_controls.py tests/integration/test_governed_agent_wake_dispatcher.py tests/integration/test_governed_agent_supervisor.py tests/integration/test_governed_agent_effect_service.py tests/runtime/test_governed_agent_loop.py tests/interfaces/test_api_composition_isolation.py tests/application/test_control_plane_workload_authority_governance.py
```

Observed result after final body-limit hardening: `85 passed in 43.35s`.

Structural and canonical gates:

1. changed-path Ruff: pass;
2. focused mypy with skipped external imports: 13
   webhook/queue/runtime/interface source files passed;
3. canonical repository suite after final body-limit hardening: `4532 passed,
   56 skipped, 2 warnings in 599.39s`; the warnings remain the known deprecated `orket.domain` import and
   low governed-output token warning;
4. dependency direction with legacy-edge enforcement set to fail: pass;
5. docs project hygiene: pass;
6. strict governed-agent docs lint: 15 files, zero violations; strict
   architectural-truth docs lint: 6 files, zero violations;
7. new webhook production files remain at or below 400 lines and their
   functions remain at or below 70 lines;
8. `git diff --check`: pass apart from existing line-ending notices;
9. regenerated architectural-truth baseline: `collection_ok=true`,
   `release_ready=false`; its focused tests pass (`2 passed`).

## Not Verified

1. Multi-issuer or overlapping-key rotation; Slice 6G configures one active
   issuer/key pair and documents a bounded cutover.
2. Provider-specific webhook formats; callers submit the canonical Orket wake
   body after signing the exact raw bytes.
3. Generalized effect approval/resolution dispatch from a wake.
4. Live Ollama inference specifically from webhook ingress; Slice 6E already
   proves the unchanged supervisor/provider path with live fixed roles.

## Remaining Blockers or Drift

1. Generalized wake-driven effect handling and atomic wake-fence composition
   for that path remain a separate checked Slice 6 increment.
2. Scheduler callers still supply stable, non-overlapping evaluation windows;
   Orket does not own timer discovery.
3. `AT-EX-003` and wider architectural-truth release-readiness debt remain.
4. Slice 7 release proof and explicit user acceptance remain open.
