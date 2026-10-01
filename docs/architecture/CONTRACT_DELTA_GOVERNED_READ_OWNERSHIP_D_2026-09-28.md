# Governed wake fence and replay read ownership

## Summary

- Owner: Orket Core.
- Date: 2026-09-28.
- Affected contracts: `GOVERNED_AGENT_LOOP_V1.md`, `SHARED_IO_CANCELLATION.md`.
- Status: implemented; bounded Windows source closing passed.
- Effective version: uncommitted candidate after core 0.6.114; no version bump.

## Delta

Current wake validation and replay evidence readers submit native path resolution
and existence checks before read-only SQLite admission without retaining those
workers through caller cancellation. Their current lexical connection contexts
also lack protection against repeated interruption of acquisition/close. The
supervisor and application request owner wait for the coroutine they cancel;
that does not itself join an abandoned executor operation.

Each reader uses the existing file-root capture policy before the first await,
then admits its complete current preflight/read/close coroutine through the
existing shared I/O owner. The first caller interruption waits for settlement;
successful read values do not escape that interruption. Uncaught operation
failures retain their identity and precedence through `preserve_failure=True`.
No new owner, retry, close loop or worker is introduced in product code.

Replay's preflight errors still propagate. Its existing SQL/read exceptions still
become bounded diagnostic evidence inside the owned operation. On interruption
the diagnostic return is discarded under shared cancellation policy. Outer
application owners retain their documented transport/cancellation selection.
Missing database absence, stale wake refusal, no repair, one-transaction replay,
resource bounds, query ordering and existing read-only URIs stay unchanged.

## Migration Plan

1. Public signatures and response/wire schemas stay unchanged. Supported standard
   relative paths bind at invocation, before any native wait. Drive-relative paths
   now refuse explicitly through the existing shared file-root policy instead of
   observing per-drive current directories later in a worker.
2. Direct async callers keep awaiting interruption until read and close settle.
   No forced native termination or new deadline is promised.
3. Apply opening controls first to the unchanged product. Exercise actual native
   metadata, connection acquisition, query and close holds, timeout interruption,
   repeated cancellation, sibling SQLite responsiveness, root rotation, actual
   SQLite refusal, retained rows and supervisor shutdown. Then apply product and
   rerun those controls with existing wake/replay authority and public API/CLI
   guards. Keep failing openings and cleanup observations.
4. Both Quality jobs retain the opening module with wake/replay and public
   command/API guards. Source inspection and static checks are not live acceptance;
   installed supported-platform proof remains pending.

## Opening evidence

The unchanged-product opening returned **25 failed, 9 passed** in 6.01s. One
failure was a fixture expectation missing the existing `terminal_authority_conflict`
diagnostic for unreadable replay. Correcting only that expected diagnostic produced
**24 failed, 10 passed** in 4.91s. Both runs retained all 5,537 Git-visible inputs
unchanged during execution, with one upstream Starlette/httpx warning.
The 24 failures comprise 22 lifetime/path-capture observations and two new
drive-relative path-refusal requirements. The latter document intentional admission
narrowing, not a claim that this refusal already existed. Original and corrected
reports remain at `.tmp/goal-20260928-governed-read-opening-v{1,2}-*`.

The Python 3.11.14 source closing passed **179 tests** in 105.04s, exit 0, with
all 5,538 Git-visible inputs unchanged and one upstream warning. The selection
includes every opening case, real public wake/replay/supervisor paths, missing
stores, retained evidence integrity, public API/CLI and shared-owner controls.
Observed path: primary; result: success. The native temporary-files/SQLite work
is live local integration; supplied dispatcher/model and structural workflow
checks retain those narrower claims. Canonical scoped Ruff passes. Evidence:
`.tmp/goal-20260928-governed-read-closing-v1-{inputs,readback}.json` and sibling
log/XML. No provider, installed package, Linux or external-effect proof is inferred.

Windows Python 3.12.2 also passes all **34** new source cases in 4.97s, with
5,539 unchanged inputs and one upstream warning. The two reader files and focused
case identities match the 3.11 closing. Current source is imported; the historical
interpreter does not turn this into installed proof. Evidence:
`.tmp/goal-20260928-governed-read-closing-py312-v1-*` and
`.tmp/goal-20260928-recent-ownership-parity.json`; 4,956 historical bindings remain.

## Rollback Plan

Drain admitted reads before rolling code, fixtures and contracts back together.
Retain databases and failed observations. There is no migration or repair to undo;
rollback reopens premature-return and late path-selection counterexamples.

## Versioning Decision

Patch scope after 0.6.114. Existing public contracts remain; the path-capture and
interruption requirements are explicit. Broader wake mutation, manual wake CLI
input loading, provider execution and repository-wide D acceptance are outside
this correction.
