# Governed Agent Loop Slice 6E Proof

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-07
Status: Live supervisor proof complete; lane remains active
Observed path: `primary`
Observed result: `success`
Proof classification: live end-to-end local-model execution through the
authenticated API, durable queue, API-owned supervisor, external child, broker,
and verifier

## Outcome

The continuously owned production composition now has live local-provider
proof. An authenticated API wake was durably admitted, claimed by the API-owned
supervisor, and dispatched through the separately located
`GovernedLocalAgent` package. Planner and critic used exact installed
`qwen2.5:7b`; actor used exact installed `qwen2.5-coder:7b`. Two bounded
iterations produced `continue` then `complete`, and Orket published
verifier-backed final truth.

The proof also observed measured provider receipts and zero tracked background
tasks after API lifespan shutdown. `ORKET_DISABLE_SANDBOX=1` was set; no sandbox
or cloud resource was created.

## Verification

Command:

```powershell
$env:ORKET_DISABLE_SANDBOX='1'
$env:ORKET_RUN_LIVE_AGENT_OLLAMA='1'
$env:ORKET_GOVERNED_AGENT_EXTENSION_ROOT='C:\Source\Orket-Extensions\GovernedLocalAgent'
$env:ORKET_GOVERNED_AGENT_PLANNER_MODEL='qwen2.5:7b'
$env:ORKET_GOVERNED_AGENT_ACTOR_MODEL='qwen2.5-coder:7b'
$env:ORKET_GOVERNED_AGENT_CRITIC_MODEL='qwen2.5:7b'
python -m pytest -q tests/e2e/test_governed_agent_supervisor_ollama.py
```

Observed result: `1 passed in 10.92s`.

The canonical non-live suite subsequently passed with `4519 passed, 56 skipped,
2 warnings in 453.01s`. Its 56 skips include this deliberately opt-in live
test; the result above is the separate live execution proof.

## Claim Limits

1. This proves the local Ollama supervisor integration and truthful receipts,
   not comparative model quality or production readiness.
2. It uses the local external package checkout, not a newly built or published
   release artifact. Prior Slices 3-5 separately prove built-package behavior.
3. Exact unavailable models still fail closed; silent substitution is not
   admitted.

## Remaining Blockers or Drift

1. Slice 6F subsequently closes scheduled ingress with explicit timezone,
   missed/coalesced occurrence policy, durable deduplication, and replay
   protection. Webhook authentication and delivery replay remain open.
2. Generalized wake-driven effect handling requires atomic effect authorization
   against wake fencing; the current issue-scoped effect path remains narrower.
3. `AT-EX-003`, Slice 7 release proof, release actions, and explicit user
   acceptance remain open.
