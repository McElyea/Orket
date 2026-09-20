# Governed wake input and provider lifetime ownership

## Summary

- Owner: Orket Core.
- Date: 2026-09-20.
- Affected contracts: governed wake ingress, dispatch and provider cleanup.
- Effective version: 0.6.42 (patch candidate; acceptance remains in the canonical plan).

## Delta

Validated public wake submissions retain their dispatch JSON using the SDK's
`FrozenJson` value. Constructing a durable request produces a fresh payload and
captures any host-supplied trigger; later caller mutation cannot alter the queued
request. The stored wire shape, identity and canonical payload digest rules do
not change. Schedules serialize the retained value explicitly. This does not
replace repository fencing, deduplication, transactions or wake state authority.

Wake dispatch retains the validated SDK `AgentIterationRequest` and a frozen
continuation plan before its first fence await. It uses those same values through
catalog admission and bounded execution, rather than reparsing a mutable retained
wake payload after suspension. Existing target, capacity, lease, deadline,
continuation, effect and terminal validation still applies. A capture is not
permission to reopen a terminal run or bypass an active fence.

Provider configuration copies its role-model mapping on construction. Dispatchers
capture a private environment snapshot on construction, with an optional explicit
`environment` input. API composition forwards its existing captured environment
to both settings and dispatcher construction. Local runtime preparation retains
the input contract introduced in 0.6.41. No credentials are included in proof or
configuration receipts by this change.

Dispatch retains provider cleanup through caller timeout and repeated cancellation.
The local provider owner attempts every owned client close even if an earlier
close fails, reports the failures, and propagates the first failure after draining
the remaining clients. A close failure takes precedence over caller interruption;
it cannot be converted into successful cleanup. The shared retained-I/O adapter
remains the cancellation authority. There is no hard-stop promise for unresponsive
cleanup or interpreter/process termination.

## Migration Plan

1. Internal envelope consumers use its validated `request` value and explicitly
   thaw `continuation_inputs` when passing wire JSON. There is no mutable
   `request_payload` compatibility alias.
2. Internal submission/schedule consumers explicitly thaw frozen dispatch JSON.
   Public API/CLI/webhook wire fields remain unchanged.
3. Pass an earlier environment snapshot to dispatcher construction when the caller
   owns one. Otherwise construction is the capture boundary.
4. Require native SQLite ingress mutation controls, real governed subprocess
   dispatch under retained-payload mutation, real TCP provider selection controls,
   retained cleanup interruption/failure tests and affected public wake flows.
   Keep the existing 0.5-second controlled-hold responsiveness bound and all product
   deadlines. Separate deterministic/controlled responses from real inference.

## Rollback Plan

Drain dispatch and cleanup owners before rolling code and consumers back together
under a new patch version. Preserve wake rows, payload digests, catalogs, stores,
fences and failed observations. A rollback reopens the documented mutation and
abandoned-cleanup counterexamples and is not equivalent lifetime behavior.

## Versioning Decision

Patch checkpoint for application input and resource ownership. Public wire
contracts remain compatible; internal envelope/value consumers migrate together.
Broader C/D/E/CAP and explicit whole-lane acceptance remain open.
