# Kernel runtime state and lifetime ownership

## Summary
- Change title: Explicit per-runtime Kernel state, observations and shutdown
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-21
- Affected contracts: Kernel action state, direct embeddings and engine lifetime
- Status: implementation contract; scoped acceptance governed by the canonical plan
- Durable authority: `docs/specs/KERNEL_PUBLICATION_INPUTS.md`

## Delta
- Before: independent API applications share process-global Kernel ledger,
  admission, approval, credential and canonical-state maps. A second application
  can observe or resolve the first application's approval and commit against its
  admission. Closed engines admit new mutations; direct engine close can finish
  before an admitted Kernel mutation's required SQLite publication.
- After: each standard engine owns distinct Kernel state, lock and selected input
  sources. Direct embeddings explicitly create and bind a runtime owner; unbound
  or closed owners refuse. No module-default mutable runtime or proxy maps remain.
  Immutable observation values reach low-level event publication; ordinary Kernel
  state remains volatile, with no new durable store or restart reconstruction.
- The existing application lifetime supervisor owns async Kernel publications,
  including approval resolution, before engine resources close. Nested work from
  an admitted invocation remains part of that invocation; unrelated new work
  refuses after close admission. Native work uses the existing owned worker.
- Standard composition passes its selected runtime input sources. Credential
  consumption still samples default expiry time after acquiring its runtime lock.
  Environment capture, exact approval binding, successful same-key reuse and
  partial-publication failure behavior from .75/.76 remain authoritative.
- Independent state owners may use equal session/proposal identifiers without
  sharing authority. This is in-process ownership, not hostile Python isolation,
  OS containment, durable Kernel recovery or per-user API authorization.

## Migration Plan
1. Direct action-path callers create one runtime owner and bind it around their
   related calls; retain and close it explicitly. Closed owners cannot reopen.
2. Standard engine/API callers use their composed gateway and async methods;
   bypassing that gateway does not select the engine's state. Custom gateway
   owners must participate in required cleanup.
3. Replace private global-map/lock test access with the explicitly selected owner.
   Tests and CLI evidence scripts must declare their owner; no test-only implicit
   production fallback or deprecated global alias is introduced.
4. Keep admitted publication owned during cancellation, timeout and close; inspect
   partial state after failure. Shutdown is not proof of transaction rollback.
   Native gateway invocation and close refuse a running event loop; use the
   engine's async methods or an owned native worker.
5. Correct the previous checkpoint's historical planner/router attribution:
   frozen planner/router inputs were introduced in .46, evaluator in .47 and
   loop-policy expansion in .48. Preserve previous sealed proof unchanged.

## Rollback Plan
1. Revert owner, callers, tests and contract together if independent isolation,
   admitted lifetime, selected-input semantics or accepted BT behavior regresses.
2. Preserve failure evidence and existing durable stores. Do not erase uncertainty
   or invent recovered in-memory state after process/application replacement.

## Versioning Decision
- Version bump type: patch remediation with breaking direct-embedding migration.
- Effective version/date: 0.6.77 / 2026-09-21; acceptance evidence is scoped by the canonical plan.
- Downstream impact: explicit direct owner binding and closed-admission refusal;
  existing public Kernel wire shapes and durable control-plane authority retained.
