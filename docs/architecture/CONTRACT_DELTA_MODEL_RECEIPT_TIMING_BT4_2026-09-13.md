# Nullable governed-model receipt timing

## Summary
- Owner: Orket Core; date: 2026-09-13.
- Contracts: `docs/specs/GOVERNED_AGENT_LOOP_V1.md` and
  `docs/requirements/sdk/VERSIONING.md`.
- Development pair: host remediation candidate, SDK 0.7.0a1, and reference
  extension/starter 0.3.0a1. These versions are not released or tagged.

## Delta
- Previously missing/invalid model latency became zero, including failed JSON
  responses. Strict v1 receipts had no unavailable representation.
- New host receipts use v2 with nullable integer latency and a separate
  `reported`/`unavailable` posture. Reported latency comes from the model-provider
  observation; no independent clock, timing-scope or capacity claim is added.
- Boolean metadata is not an integer measurement. Incomplete/invalid token
  metadata follows the existing unknown-usage contract: both counts null and
  issued input/output maxima charged. Response status remains independent.
- Canonical historical v1 reads retain their original integer and fields.
  New declarations require the v2 receipt host feature. The existing call,
  iteration and IPC envelope versions carry the independently versioned receipt.
- The child ready handshake must advertise v2 receipt support before any model
  reservation or inference. Historical ready-frame reads allow the absent field;
  live admission rejects it. This also refuses mismatched parent/child SDK installs
  before sending a new receipt to an old decoder.

## Migration Plan
1. SDK 0.7.0a1 is limited to the matched host candidate, overriding its nominal
   compatibility window. Published core 0.6.0/0.6.2 pins remain SDK 0.6.0.
2. Revalidate extension consumers for nullable latency, then explicitly declare
   `agent_model_use_receipt.v2`. Old declarations cannot authorize new execution.
   Historical run/receipt records and installed manifests are not rewritten.
3. The reference extension counterpart is prepared in the separate worktree
   `.tmp/governed-agent-model-timing`, based on the canonical
   `C:/Source/OrketExtensions/GoverenedAgentLoop` repository. Its main checkout and
   released artifacts remain intact. The Orket starter also carries the new
   version, SDK pin and declaration.
4. Gates: typed/schema negative cases; historical v1 nested roundtrips; old-feature
   refusal; durable broker replay without new inference or charges; real child
   receipt retention; matched SDK/core/reference builds and installed origins;
   live llama.cpp provider proof. Results and remaining gaps belong to the plan.

## Rollback Plan
1. If a required consumer cannot retain null/posture, stop new affected admission
   while repairing the consumer. Do not relabel v2 as v1 or fabricate zero.
2. Preserve original stores, payload digests and version markers. Historical
   artifacts need no rewrite; older published packages are not used against newly
   authored v2 history without their own verified migration procedure.

## Versioning Decision
- SDK minor prerelease and explicit receipt feature are required by the changed
  public contract. Core release/version/tag work remains subject to its existing
  release policy; this change does not publish any package.
- Downstream effect: matching SDK/declarations are required. The latency contract
  does not strengthen provider outcome, usage, containment or completion claims.
