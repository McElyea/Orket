# Required producer event input capture

## Summary
- Owner: Orket Core
- Date: 2026-10-01
- Contract: `docs/specs/LOG_WRITE_SETTLEMENT.md`; existing shared I/O cancellation and core builtin capture authority.

## Delta
- Bug-fix publication now selects its workspace and detaches event values before persistence/readback waits. Unsupported event values refuse before persistence.
- Preview's two missing-input observations retain their selected destination across loader/read waits. Existing private scalar payloads and degraded preview behavior remain.
- Structural adoption and missing-read events detach event values before native admission. Prior file/SQLite/cache effects remain observable if required logging later fails.
- Existing required native I/O ownership, prepared logging context, failure precedence and optional writer/queue semantics remain unchanged.

## Migration Plan
1. No constructor, schema, compatibility alias or provider migration. Existing accepted builtin values preserve their meaning; unsupported graphs follow the canonical capture refusal.
2. Retain real source controls for healthy output, input/root mutation, native holds, repeated cancellation, timeout and failure before/after physical writes. Public bug-fix, preview and reconciliation paths plus the missing-read boundary and existing public message controls provide scoped proof.
3. Both Quality selections retain these controls with existing preparation, subscriber, overflow and fatal-writer regressions. Hosted, installed and actual-provider acceptance remain later queue gates.

## Rollback Plan
1. Event mismatch or a success returned before required publication blocks the checkpoint.
2. Correct the bounded caller capture while preserving controls and the shared logging/I/O owners. Do not reintroduce borrowed payloads or a second writer.
3. Do not claim rollback of previously committed SQLite/cache/board effects after a log failure.

## Versioning Decision
- Patch checkpoint v0.6.120; compatible internal correctness change.
- No new capability or whole-lane acceptance. Current typing/coverage and external proof gates remain open.
