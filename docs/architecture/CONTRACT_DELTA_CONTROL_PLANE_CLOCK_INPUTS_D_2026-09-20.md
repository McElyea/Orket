# Selected clocks for remaining control-plane families

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.54 candidate, 2026-09-20.
- Durable contract: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

## Delta
Cards-epic, extension-workload and manual-review control-plane owners previously
observed UTC through local static methods. Their transaction-scoped service
construction could not retain an injected clock. Constructors now select an
explicit `utc_now` callable and carry it into borrowed transaction owners.
Execution-pipeline wiring supplies its selected runtime clock to the cards owner.
Review and extension composition expose the same input.

The extension manager's existing selected clock also reaches workload execution,
creation identity and control-plane publication. Async manager preparation exposes
that optional clock. Helper callers can pass a clock explicitly; supplied creation
time/run IDs retain their existing meaning. Defaults preserve host UTC behavior.

Clock selection is retained; observations remain fresh at the existing creation,
journal and closeout publication points. Clock failure uses the existing refusal,
rollback and failure-reporting paths. Terminal retries preserve their original
times and authority. No timeline normalization or historical record rewrite is
authorized, and no transaction or native execution lifetime guarantee is expanded.

## Verification and rollback
Verify actual SQLite creation, effect-journal and terminal records through cards,
manual review and both trusted extension families. Prove clock propagation across
transaction ownership, clock failure without fabricated terminal success, and
identical retry without new timestamps. Compare default identity formatting with
the published behavior and retain installed source/caller/package bindings.
Controlled providers and clocks do not establish fresh model inference, elapsed
performance or Linux wall-clock stability.

Rollback must preserve stored records and disclose restored host-clock selection;
it must not repair historical timestamps or weaken terminal consistency checks.

## Versioning decision
- Compatible patch input ports; existing default callers remain supported.
- Custom hosts select `utc_now` at construction; a new owner adopts a new selection.
- Remaining D/E/CAP and explicit lane acceptance remain active.
