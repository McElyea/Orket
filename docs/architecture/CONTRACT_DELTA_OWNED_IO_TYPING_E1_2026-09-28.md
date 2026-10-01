# Shared I/O factory declarations

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; scoped Windows source preservation checks pass.
- Contract: `docs/specs/SHARED_IO_CANCELLATION.md`.

## Delta

The shared factory advertised arbitrary `Awaitable[T]` despite relying on
`asyncio.create_task` coroutine admission. Untyped settlement also lost its result
type. `OwnedCoroutine[T]` now names the coroutine/generator family in one place;
the shared factory, Kernel publication and supplied turn-preparation close port
reuse it. The private bug-fix phase factory follows the same declaration.
Generic settlement/adapter annotations retain result and first-cancellation types.
The outward watch handler uses a distinct optional query local instead of reusing
a dictionary-only local. Executable operations remain unchanged.

Exact `throw(*args)` forwarding remains untyped: the current checker cannot express
that overloaded variadic delegation without normalization, argument-type erasure
or suppression. No such workaround is introduced. Generator admission still
depends on the selected interpreter, and rejected values remain caller-owned.

## Migration Plan

1. Describe actual coroutine-producing factories accurately. Futures, Tasks and
   arbitrary awaitables do not acquire new admission or automatic wrappers.
2. The broader Kernel runtime invocation and underlying provider-close awaitables
   remain supported where existing native async wrappers actually await them.
3. Retain the shared-owner admission, identity, fatal, cancellation and resource
   controls, plus real bug-fix/Kernel/provider consumer paths. No tests or fixtures
   change solely to accommodate the annotations.

## Verification

The isolated preserved-source Mypy comparison removes exactly two reported errors:
**700 in 200 files -> 698 in 198 files**, with zero added diagnostics. Both runs
use the same Windows Python 3.11.14/Mypy 2.3.1/config/stubs and 1,237 bound inputs.
That comparison predates later card/epic/wake/orchestrator source changes; it is
not a current whole-tree green gate. Five positive inference assertions pass;
three negative scenarios produce five expected static refusals. Scoped Ruff passes.
Normalized executable ASTs match, excluding annotations and the exact local rename.
Generic-base introspection differs and needs no claim of identity preservation.

The 24-selector closing passes **158 tests** on both Windows Python 3.11.14 and
3.12.2, in 48.78s and 58.04s. Each run retains all Git-visible inputs unchanged
(5,545 and 5,547 respectively), with one upstream Starlette/httpx warning. The
five typed product files and all case identities match between cells. Native
fatal/interruption/admission controls and real bug-fix/Kernel/provider-consumer
paths retain their individual fixture limits; this is live local source proof,
path primary, result success. Neither interpreter run is fresh installed proof.
Evidence: `.tmp/goal-20260928-owner-typing-closing-{v1,py312-v1}-*` and
`.tmp/goal-20260928-recent-ownership-parity.json`. All 4,956 historical installed
bindings remain unchanged. Static receipts and application hashes remain in
`.tmp/e1-owner-typing-candidate-20260928/`; the application explicitly rebases the
two intervening orchestrator caller/test changes to their accepted parity report.
Unchecked throw, custom/eager task factories, installed and platform acceptance,
all other Mypy errors and the repository coverage gate remain open.

## Rollback Plan

A runtime protocol or caller regression blocks acceptance. Preserve evidence and
correct or revert the five paths and declarations together. No storage migration,
cleanup transfer or newly admitted effect requires data rollback.

## Versioning Decision

Unreleased 0.6.114 source correction; no version/release change. Static consumers
see truthful narrower factory types. Runtime admission/refusal and underlying
broader awaitable ports retain their existing behavior.
