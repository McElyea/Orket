# Epic execution phase composition

## Summary
- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; Windows source parity passes, installed parity pending.
- Contract: `docs/specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`.

## Delta
`orchestrator_ops.execute_epic` retains settings and model preparation, tool and
executor construction, and composition of phase-specific effects. The focused
`orchestrator_epic_workflow` owns the existing team preflight and dispatch-loop
control flow. Existing public `Orchestrator` imports, execution arguments and
return behavior remain. No compatibility forwarding or additional owner is added.

The loop node is selected before the first settings await. Each limit still
observes the current loop inputs at its original call. Each dispatch tick selects
the current card repository; replan and planner selection follow the completed
read. Replan's nested transition, card, team, publication and event callbacks
retain their existing selection phases. Final exhaustion reads the current card
repository after the last dispatch batch.

Semaphore admission precedes selecting the current turn operation. The original
approval dictionary is retained, and the issue entry is popped inside the turn
call arguments after its method lookup. It is neither copied nor consumed while
waiting for the semaphore. Event fields, optional logging admission, dependency
propagation, stop/stall/exhaustion interpretation and exception boundaries remain.
Loop termination grants no accepted card or build completion authority.

This reduces the oversized execution operation and ops module. The existing
turn operation and module size debt remain under the architectural-truth plan;
this slice does not finish E2 or repair separately inventoried input/lifetime debt.

## Migration Plan
No existing repository consumer requires a changed import or monkeypatch path.
Card snapshot reads and tool/executor construction remain composed by ops.
Moved loop mechanics belong to the focused workflow module; imported incidental
ops names are not retained as compatibility exports. Public import contracts are
unchanged. The focused module depends on existing services and typed contracts,
without a coordinator proxy or duplicated transaction/dispatch algorithms.

Before application, run the three new public execution controls against the
unchanged product, then the declared existing epic, dispatch, scheduler, approval,
recovery, provider-cleanup and supplied-provider engine selectors. After application,
run the identical selection, dependency checks and canonical typing/size inventories.
Retain original observations. The new controls use real card reads and scheduler
effects with controlled turn boundaries; they do not establish inference success.
Full installed and Linux parity remain separate proof obligations.

## Rollback Plan
Revert the ops composition and focused workflow together if ordered effects,
public behavior or phase-selected owner parity fails. Preserve the standalone
phase controls. Inspect retained card/control-plane state before retry; neither
the extraction nor loop interruption promises rollback of earlier effects.

## Versioning Decision
Current source candidate 0.6.114; no version bump or new capability admission.
Public behavior parity is intended and must be observed. Internal responsibility
moves without new facade exports, provider ownership or completion authority.


### Observed source parity, 2026-09-28

The first three opening fixtures used positional arguments against the keyword-only
facade and hid task failures behind event timeouts. They are invalid parity evidence;
the retained 335-case report contains three failures and 332 passes. The fixture now
uses public keywords and observes task failure alongside its event waiter. All 15
original assertions remain. The corrected three cases pass on unchanged product;
all 236 epic cases pass after extraction in the combined closing recorded by the
active plan. Real card/scheduler and supplied-turn checks preserve phase selection,
approval consumption, recovery and actual local pipeline behavior. No live inference
or installed acceptance is claimed. Ops shrinks 728 to 577 lines, execute_epic 213
to 66; the new 151-line module has no function over 49 lines. Remaining ops/turn and
later ordered hotspots remain open. Source evidence is retained under
`.tmp/goal-20260928-roots-remaining-{opening-app-imports-closing,epic-closing}-v1-*`.
