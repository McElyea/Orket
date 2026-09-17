# Contract delta: owned native verification processes

## Summary
- Owner: architectural-truth BT-4.
- Date: 2026-09-13.
- Affected contracts: runtime command receipts, card CLI acceptance execution,
  cancellation events; `VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`.

## Delta
- Previous behavior: caller cancellation abandoned a direct subprocess; timeout
  killed only that subprocess and could hang on pipes inherited by descendants.
- Required behavior: establish native OS descendant ownership before execution,
  stop further command admission on failure, and await bounded confirmed cleanup
  or retain explicit uncertainty. Repeated cancellation cannot skip cleanup.
- Receipts add `process_lifetime`. Output retention is bounded at 4 MiB per raw
  stream and excess output fails explicitly. Actual captured stderr is preserved;
  timeout diagnostics use structured metadata. Existing diagnostic clipping and
  card acceptance sufficiency requirements remain authoritative.
- This break is required because returning cancellation or a timeout while owned
  work continues permits later writes after the caller believes execution ended.
- Windows virtual-environment redirectors require distinct transport/supervisor
  PID observations. The private transport uses a fresh correlation nonce and
  requires normal transport exit. A buffered daemon stdin reader was replaced
  with raw descriptor reads to prevent CPython 3.11/3.12 shutdown aborts.

## Migration Plan
1. Replace `RuntimeVerifier` process execution in place. No unsupervised fallback
   or compatibility window is admitted for platforms lacking the required backend.
2. Legacy fixture/thread execution and Docker containers still require their own
   cutover; this change does not silently reinterpret those paths as supervised.
3. Validate children/grandchildren, timeout, repeated cancellation, leader exit,
   session detachment, event-loop shutdown, capture integrity, and failed-command
   admission using real processes. Validate installed Windows/Linux 3.11/3.12
   separately. Record unsupported and unverified paths in the canonical plan.
4. Propagate unconfirmed lifetime through epic terminal/admission authority before
   closing BT-4. A failed command receipt alone does not close that obligation.

## Rollback Plan
1. Trigger: unsupported OS ownership, lost cleanup acknowledgement or incorrect
   command/output classification.
2. Disable affected verifier admission while repairing the supervisor. Do not
   restore direct-child-only cancellation or accept incomplete output as success.
3. Preserve existing receipts and uncertainty. No historical record migration or
   invented cleanup acknowledgement is permitted.

## Versioning Decision
- Effective in the 2026-09-13 worktree checkpoint; no release/version bump yet.
- Additive receipt fields accompany stricter command failure/admission behavior.
  Consumers must use `process_lifetime` before claiming teardown; exit 125 cannot
  be interpreted as confirmed cleanup.
