# Governed Agent Loop Slice 6C Proof

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-07
Status: Implemented manual-wake transport checkpoint; lane remains active
Observed path: `primary`
Observed result: `success`
Proof classification: integration and end-to-end; durable CLI ingress consumed
by the API-owned deterministic supervisor and real child/broker path

## Outcome

Slice 6C adds one supported manual transport to the existing durable wake
queue. `orket agent wake enqueue` validates the same dispatch envelope as API
ingress and persists `source=manual`; `list` and `inspect` expose the retained
queue state. The command never starts execution. A separately owned supervisor
claims the row through the Slice 6B path.

## Observed Behaviors

1. Manual enqueue requires exactly one new-workload or existing-run target, a
   caller-stable occurrence id, and a complete bounded dispatch envelope.
2. Repeating identical manual content is idempotent.
3. Manual and API identity include their source, preventing cross-transport
   wake-id and deduplication collisions.
4. CLI list and inspect read the canonical durable repository.
5. A manual wake persists before the API app exists, then is claimed by the
   explicitly enabled API-owned supervisor and reaches verifier-backed final
   truth through the existing child and broker.
6. CLI exit does not own or leak a supervisor, provider, or child task.

## Verification

Focused command:

```text
ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_governed_agent_cli.py tests/interfaces/test_governed_agent_api.py tests/integration/test_async_governed_agent_wake_repository.py tests/integration/test_governed_agent_wake_dispatcher.py tests/integration/test_governed_agent_supervisor.py tests/runtime/test_governed_agent_loop.py tests/interfaces/test_api_composition_isolation.py tests/application/test_control_plane_workload_authority_governance.py
```

Observed result: `65 passed in 33.99s`.

Structural gates:

1. touched-path Ruff: pass;
2. focused mypy with skipped external imports: 2 changed/new source files
   passed;
3. dependency direction with legacy-edge enforcement set to fail: pass;
4. docs project hygiene: pass;
5. strict governed-agent docs lint: 11 files, 0 violations;
6. new-file and changed-function size gate: pass;
7. canonical repository suite: `4515 passed, 55 skipped, 2 warnings in
   452.55s`; the warnings remain the known deprecated `orket.domain` import and
   low governed-output token warning.

## Not Verified

1. Scheduled timezone, missed-trigger, or coalescing behavior.
2. Webhook authentication, delivery deduplication, or replay protection.
3. Public wake cancellation or recovery mutation controls were not part of the
   6C checkpoint; Slice 6D subsequently implements them.
4. Generalized effect approval/resolution dispatch from a wake.
5. Live Ollama inference through the continuously running supervisor was not
   part of the 6C checkpoint; Slice 6E subsequently proves it.

## Remaining Blockers or Drift

1. Recovery controls were subsequently implemented in Slice 6D, live Ollama
   supervisor proof in Slice 6E, and scheduled ingress in Slice 6F. Webhook
   policy and generalized wake-driven effects remain.
2. `AT-EX-003` and the wider architectural-truth release-readiness debt remain.
3. Slice 7 release proof and explicit user acceptance remain open.
