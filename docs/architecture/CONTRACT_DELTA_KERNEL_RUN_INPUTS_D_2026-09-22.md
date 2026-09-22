# Kernel run identity and workspace capture

## Summary
- Change title: Explicit selected run identity and stable lexical workspace inputs
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-22
- Affected contracts: Kernel start handles, relative workspace resolution and native invocation
- Status: implementation contract; scoped acceptance governed by the canonical plan
- Durable authority: `docs/specs/KERNEL_RUN_INPUTS.md`

## Delta
- Before: validator mints UUIDs internally; relative handles and queued native
  calls can write beneath a later process cwd. API default workspaces follow server
  cwd instead of the selected application project. Native gateway lifecycle callers
  may mutate borrowed turn lists while earlier work waits.
- After: application captures selected identity and immutable absolute lexical
  workspace values. Engines bind their project root; direct async calls capture
  roots before workers. Start handles retain that root across subsequent calls.
  Pure typed start produces equal handles for equal inputs without hidden reads.
- Existing policy/credential/publication behavior, local staging/promotion outcomes
  and effect ownership remain; no new containment, durable recovery or broker claim.

## Migration
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Direct implicit start callers bind a `KernelRuntime` and use native/owned-worker
  execution, or supply typed immutable run inputs. Custom runtime input providers
  implement `create_kernel_run_id`. Standard engines supply their project root.
- Expect absolute workspace roots in returned handles. Bind older relative handles
  to their intended root explicitly; nothing moves or merges existing workspaces.

## Verification and limits
The canonical plan must record deterministic typed-input parity, actual source and
installed staging/promotion, selected ID failure and capture, queued/held native
root changes, concurrent owners, cancellation/timeout/shutdown and real API effects.
Predeclared responsiveness/deadline bounds remain mandatory. Broader adapter/effect
inventory, Linux verification, E/CAP and user acceptance remain separate gates.
