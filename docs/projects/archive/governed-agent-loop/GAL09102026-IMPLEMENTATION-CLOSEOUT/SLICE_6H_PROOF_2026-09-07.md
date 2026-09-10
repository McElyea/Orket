# Governed Agent Loop Slice 6H Proof

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-07
Status: Implemented wake-driven effect checkpoint; lane remains active
Observed path: `primary`
Observed result: `success`
Proof classification: integration and end-to-end effect control path; durable
SQLite, active wake fence, approval/denial, uncertainty, aggregate checkpoint,
operator authorization, restart, real child, and supervisor teardown proof

## Outcome

Slice 6H connects accepted effect proposals from the continuous supervisor to
the existing governed effect authority. The claimed wake prepares proposals,
but cannot execute an approval-required write. Authenticated operator control
accepts continuation only after every proposal has a safe journal observation,
then queues one exact request-bound resume wake. The run does not become
`executing` until that wake is claimed and revalidates the authorization.

## Observed Behaviors

1. A real external child returns issue-scoped read and write proposals; the
   active wake observes and journals the read, publishes the write's
   resume-forbidden checkpoint, pending gate, and reservation, and completes
   with the run operator-blocked before any write.
2. The effect service checks wake authority before each preparation publication
   and after external observation. A stale check after the read prevents the
   journal publication.
3. Authenticated denial publishes existing operator/terminal truth, performs no
   write, and queues no resume wake.
4. Authenticated approval executes through the existing issue-scoped tool gate,
   re-observes the target, journals the result, and accepts the per-write
   checkpoint. Unobserved reads or writes are journaled as unresolved and move
   the run to recovery pending without later proposal preparation or resume.
5. Continuation requires safe receipts for every proposal and one accepted
   aggregate checkpoint covering those exact effect journals. A fully observed
   read-only proposal set uses an explicit continuation endpoint without a
   fabricated write approval.
6. The resume operator action binds the exact next-request digest, checkpoint,
   and receipt set. Tampering fails before activation. A stale claimed worker
   cannot change the blocked run to executing.
7. Approval records authorization and enqueues durable work while leaving the
   run blocked. Exact approval retry returns the same wake idempotently, and a
   later API process claims that retained wake, activates the run, invokes the
   real child, and publishes verifier-backed final truth.
8. Inspection exposes the prepared approval, effect journals, per-effect and
   aggregate checkpoints, operator actions, both wakes, recovery posture when
   applicable, and terminal truth.

## Verification

Focused command:

```text
ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/integration/test_governed_agent_effect_service.py tests/e2e/test_governed_agent_effect_resume.py tests/integration/test_governed_agent_wake_dispatcher.py tests/integration/test_governed_agent_supervisor.py tests/interfaces/test_governed_agent_api.py tests/interfaces/test_governed_agent_webhook_api.py
```

Observed result: `28 passed in 28.65s`.

Canonical repository command:

```text
ORKET_DISABLE_SANDBOX=1 python -m pytest -q
```

Observed result: `4540 passed, 56 skipped, 2 warnings in 484.97s`.
The two warnings are the existing deprecated `orket.domain` import warning and
the governed-output low-token warning; neither is an effect-resume failure.

Architectural-truth baseline regeneration completed with
`collection_ok=true` and `release_ready=false`. Its focused contract suite
reported `2 passed in 1.67s`. This is successful collection, not a claim that
the repository's known architecture debt is release-ready.

Structural gates:

1. changed-path Ruff: pass;
2. focused mypy with skipped external imports: 9 source files, zero issues;
3. dependency direction with legacy-edge enforcement set to fail: pass;
4. docs project hygiene: pass;
5. strict architectural-truth docs lint: 6 files, zero violations;
6. changed runtime files remain at or below 400 lines and changed functions at
   or below 70 lines;
7. `git diff --check`: pass apart from existing line-ending notices.

Architecture checklist result for the changed path:

1. AC-01 dependency direction: pass;
2. AC-02 decision-node purity: pass, no decision node changed;
3. AC-03 explicit inputs: pass, all operator and timing inputs are explicit;
4. AC-04 deterministic inputs: pass, no runtime clock or random identity added;
5. AC-05 side-effect ownership: pass, interface -> application -> existing
   effect adapter;
6. AC-06 adapter classification: pass, the existing issue-scoped executor
   remains application-authorized;
7. AC-07 runtime truth: pass, authorization is distinct from queued and claimed
   execution, and uncertainty enters recovery;
8. AC-08 observability schema: pass, no event taxonomy changed;
9. AC-09 replayability: pass, proposal, receipt, journal, checkpoint, action,
   request digest, and wake refs are durable;
10. AC-10 authority drift: pass, contract, current authority, runbook, roadmap,
    implementation plan, and project registry were updated together.

## Not Verified

1. Live Ollama inference specifically after an effect-resume wake; Slice 6E
   already proves the unchanged supervisor/provider/child path with live fixed
   roles, while this slice proves the new effect flow with a real child and
   deterministic host provider.
2. Non-issue effects or capabilities beyond `read_file` and `write_file`; they
   remain unadmitted.

## Remaining Blockers or Drift

1. Slice 7 clean build/install and external-package compatibility are now
   proven in `SLICE_7_PACKAGING_CHECKPOINT_2026-09-07.md`; final release
   reconciliation, policy-governed release actions, and explicit user
   acceptance remain open.
2. `AT-EX-003` and wider architectural-truth release-readiness debt remain.
3. Stable evaluation-window discovery remains caller-owned by accepted
   contract; it is an intentional boundary rather than unimplemented Orket
   timer authority.
