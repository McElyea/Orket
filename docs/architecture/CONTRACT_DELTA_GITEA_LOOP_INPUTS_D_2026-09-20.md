# Gitea loop inputs and lifetime

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.55 candidate, 2026-09-20.
- Contracts: `docs/specs/GITEA_LOOP_INPUTS_AND_LIFETIME.md` and
  `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md`.

## Delta
Gitea loop owners capture environment, root and organization limit context before
settings or initialization awaits. Pipeline composition retains its selected
clock and control-plane database. Optional standalone inputs preserve existing
default callers and numeric policy. A reused runner retains its construction
selection; a new runner adopts changed context.

Claim-failure closeout uses the execution owner's selected UTC provider, and
reservations expose that same provider selection. Promotion-failure rollback no
longer substitutes a previous lease timestamp for a reversed observation. The
existing lease guard refuses it; prior effects remain, and the original promotion
failure is retained as exception context. Previously clamped histories are not
rewritten. This is stricter enforcement of the existing monotonicity contract.

Worker construction, acquired HTTP transports and summary writes have explicit
ownership through interruption and teardown. Cleanup failure cannot become clean
success. No remote exactly-once, atomic initial claim, historical repair, hostile
containment or expanded cross-store transaction guarantee is introduced.

## Verification and rollback
Retain pre-change SQLite timestamp, environment-rotation, open-client and reversed
rollback observations, including fixture setup failures. Verify unchanged default
numeric outcomes against the published package, real local effects, cancellation,
timeout, repeated interruption and cleanup failures. Exercise the installed loop
against owned actual Gitea and independently confirm teardown.

Rollback must disclose restored ambient selection and missing ownership. It must
not rewrite retained evidence, silently clamp clocks, or weaken deadlines.

## Versioning decision
- Compatible patch ports and correction of previously required clock refusal.
- Existing default callers retain numeric policy and result shape.
- Remaining D/E/CAP and explicit lane acceptance remain active.
