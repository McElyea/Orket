# Contract delta: outward command lifetime

## Summary
- Owner: Orket Core, architectural-truth BT-4.
- Date: 2026-09-13.
- Affected contracts: built-in command adapter construction, command results,
  shared native supervision, outward API interruption and receipt recovery.
- Durable contract: `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`.

## Delta
- Prior behavior: `run_command` waited only for its direct subprocess. Cancellation
  left real children/grandchildren running and inherited pipes could delay timeout.
  Decoding invalid UTF-8 before byte counting overstated raw captured bytes.
- New behavior: application composition injects the core `CommandRunner` port.
  `CommandProcessSupervisor` owns the same Windows Job/Linux subreaper execution
  used by verification. Completion, failure, timeout and cancellation await
  bounded descendant cleanup; uncertain observations remain explicit.
- `BuiltInConnectorExecutor` requires `command_runner`. The former
  `verification_process_supervisor` module and `VerificationProcessSupervisor` /
  `VerificationProcessCancelled` names are replaced by
  `command_process_supervisor`, `CommandProcessSupervisor` and
  `CommandProcessCancelled`. All repository callers migrate together, without an alias.
- Results/event summaries retain `owned_command.v1` lifetime and actual nullable
  process exit codes. Raw capture is capped at 4 MiB per stream; excess output
  fails with incomplete capture. Previews remain 256 characters; counts now measure
  retained raw bytes, including invalid UTF-8. Verifier exit projections stay local
  to verification and do not become connector process return codes.
- Cancellation and uncertain cleanup do not fabricate a normal receipt.
  `CommandExecutionUncertain` maps to HTTP 409 `E_COMMAND_EXECUTION_UNCERTAIN`.
  The existing effect journal fences reentry with
  `E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN`. Supporting lifetime logs do not replace
  retained dispatch intent or establish rollback of command effects.
- The installed matrix exposed Python 3.11/3.12's exact cancellation-type match
  in `asyncio.timeout`. The boundary normalizes only the exception presented to
  that context and retains the original typed observation. External cancellation
  during deadline cleanup still propagates with its lifetime; it cannot become
  a normal timeout receipt. Passing Python 3.13 source tests alone did not expose this.

## Migration Plan
1. No compatibility window for these unreleased internal supervisor names. Python
   adapter callers must supply an explicit runner; standard service composition
   supplies the shared owner. Consumers accept additive `process_lifetime` and
   nullable actual return codes, and must not interpret clipped output as complete.
2. Preserve raw ledger history, sealed witness fixtures and receipt hashes.
   Publication retry reuses the original lifetime and timing. No historical
   backfill or synthetic cleanup confirmation is permitted.
3. Verify real ordinary/detached trees under cancellation, repeated cancellation,
   timeout, leader success/failure and interpreter shutdown. Exercise real lost
   supervisor acknowledgement across API reentry, output limits, invalid UTF-8,
   missing executable, verifier regressions and installed Windows/Linux 3.11/3.12.
   Contract-only deadline fault injection is supplementary, not native cleanup proof.

## Rollback Plan
1. Trigger: missing cleanup ownership, incorrect receipt publication, regression in
   verification callers, or packaging that retains a duplicate supervisor.
2. Stop promotion and repair the owner/observation boundary. Do not restore the
   direct-child executor, synthesize successful cleanup, or replay uncertain work.
3. Preserve original receipts, dispatch intents and diagnostic evidence. This
   change does not reconcile historical unknown effects or introduce data migration.

## Versioning Decision
- Lifetime schema remains `owned_command.v1`; connector result projection is additive.
- Core remains unreleased 0.6.2 worktree development. This change creates no release,
  main commit, tag or push; release policy applies at promotion.
- Effective date: 2026-09-13 in the dedicated architectural-truth worktree.
- Downstream impact: required runner injection, internal supervisor rename,
  bounded output, corrected raw counts and explicit interruption uncertainty.
