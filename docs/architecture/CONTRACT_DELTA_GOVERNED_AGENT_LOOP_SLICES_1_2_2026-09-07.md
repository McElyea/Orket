# Contract Delta: Governed Agent Loop Slices 1-2

Status: Accepted bounded implementation; deterministic fixture only

## Summary

- Change title: Add the public agent SDK and one host-governed deterministic
  two-iteration path.
- Owner: Orket Core
- Date: 2026-09-07
- Affected contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`.
- Authorization: the user requested implementation of the accepted plan and
  resolution of its outstanding design questions in the same work.

## Delta

- SDK `0.5.0a1` publishes immutable V1 models, canonical serialization and
  semantic validation, a bounded framed-stdio codec, async workload/cancellation
  protocols, child broker proxies, deterministic fixtures, and conformance
  helpers. These bindings import no private `orket.*` implementation.
- The standalone SDK distribution is the installed owner of
  `orket_extension_sdk`. Core depends on `orket-extension-sdk>=0.5.0a1,<0.8.0`
  and no longer packages that namespace.
- The host advertises `governed_agent_loop.v1` and `agent_stdio_ipc.v1` for the
  dedicated governed-agent path. The generic extension executor remains a
  fail-closed non-agent path and returns `E_AGENT_RUNTIME_NOT_ADMITTED` for any
  agent discriminator.
- `ExtensionManager.resolve_governed_agent_workload(...)` validates a persisted
  manifest, integrity and host features, then projects the selected definition
  through the canonical control-plane workload catalog. No second workload
  authority is introduced.
- The application-owned governor creates and retains one parent run and attempt,
  admits exactly two sequential steps in the current fixture, materializes the
  first accepted result into the second request, and records a deterministic
  continuation decision after each accepted result.
- The SQLite repository owns idempotent dispatch preparation, per-call broker
  reservation and completion, atomic compare-and-set result acceptance,
  cancellation epochs, decision records, interrupted-publication uncertainty,
  and final truth. Results must match the host-issued identity and receipt.
- The real child process performs the versioned ready/handshake exchange and
  bounded broker calls over framed stdio. The host owns provider resolution,
  usage receipts, cancellation and process reap. Windows pipe integration uses
  bounded daemon-thread adapters around the blocking stream endpoints.
- Only an admitted host verifier or an operator cancellation publishes
  `FinalTruthRecord`. Extension completion remains advisory.
- `orket agent submit ... --deterministic-fixture`, `inspect`, `replay`, and
  `cancel` are the admitted CLI surfaces. Submit is explicitly labeled
  `deterministic_fixture_not_live_model`.

## Resolved Design Question

Existing control-plane run, attempt and step objects are not sufficient wake
queue truth. Slice 6 will add one bounded `AgentWakeRecord` repository/table for
wake identity, reason, target occurrence, deduplication, claim, lease, fencing,
and missed/coalesced-trigger state. This records a decision, not shipped queue or
supervisor behavior. Architectural-truth Slice B2 remains its lifecycle gate.

## Explicit Non-Admission

This delta does not admit:

1. a live Ollama or other model provider on the agent path;
2. agent effects, approval continuation, or uncertain-effect reconciliation;
3. live fixed multi-model planner/actor/critic execution;
4. an agent HTTP API, background scheduler, wake queue, or continuous supervisor;
5. hostile-extension containment or a final SDK/core compatibility release.

## Migration and Compatibility

1. Existing generic and controller workloads retain their prior execution path.
2. Agent workloads require the complete manifest declaration and both host
   features. Partial or unknown declarations fail before child startup.
3. Agent callers use the dedicated `orket agent` surface; they must not call the
   generic extension executor.
4. The SDK remains a development prerelease until the Slice 7 release matrix is
   complete.

## Rollback

1. Remove the dedicated governed-agent CLI registration and stop advertising
   both agent host features together.
2. Keep strict agent discrimination so rollback cannot route an agent through
   generic execution.
3. Preserve durable run, dispatch, uncertainty, cancellation and final-truth
   records for inspection; do not delete or reinterpret completed evidence.
4. Keep the SDK schema and prior prerelease available to decode retained records.
