# Contract Delta: Governed Agent Loop Slice 0 Bindings

Status: Accepted implementation binding; runtime admission remains disabled

## Summary

- Change title: Close governed-agent manifest, schema, broker-definition, and
  reproducible-fixture gaps without admitting runtime execution.
- Owner: Orket Core
- Date: 2026-09-07
- Affected contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`.
- Authorization: the user requested implementation of the accepted plan and
  resolution of its outstanding design questions in the same work.

## Delta

- Any raw workload row that uses the reserved workload id, agent kind, agent
  declaration, iteration capability, iteration input/output contract, or an
  alternate agent-version marker is now agent-like and requires the complete
  strict declaration. Manifest-v0 generic extras remain compatible only when
  they do not claim the agent protocol.
- The current host advertises no executable agent features. Host validation and
  installation refuse otherwise-valid agent extensions with
  `E_AGENT_HOST_FEATURE_UNSUPPORTED`; catalog reload rejects malformed persisted
  rows; generic execution rejects every agent discriminator before run artifact
  creation. Child configuration cannot materialize `agent.iteration.v1`.
- The canonical packaged schema now binds all required budget families,
  materialized context, typed model calls/results, host receipts, effect
  receipts, memory queries/write proposals, handoff narrowing, usage posture,
  and framed broker messages.
- V1 resolves reference delivery through bounded host materialization, not a
  child-accessible resolver. Selection of a model profile is distinct from an
  actual model call.
- Usage is `measured`, `estimated`, or `unknown`; host charges remain separate.
  Unknown counts are null and retain conservative non-negative charges.
- Application-owned ports now define dispatch intent, retained parent binding,
  atomic compare-and-set result acceptance, interrupted-publication truth,
  cancellation/teardown, and broker calls. These ports do not implement or
  admit a governor, repository, child adapter, or provider.
- Shared positive and negative public fixtures are imported by SDK and host
  tests. Source-tree results remain structural/contract proof, not installed or
  live runtime proof.

## Migration Plan

1. Existing non-agent v0 workloads remain valid and retain permissive top-level
   optional metadata behavior.
2. Agent authors must supply the complete typed declaration and all mandatory
   feature markers. They can run SDK author validation, but current host
   validation truthfully reports runtime unavailability.
3. Slice 1 will add public immutable bindings and the minimum codec/proxies,
   assign the first development prerelease, and build clean artifacts.
4. Slice 2 may advertise host features only after the real broker and bounded
   two-iteration child path pass integration proof.

## Rollback Plan

1. If strict discrimination breaks a supported non-agent workload, retain the
   raw fixture, narrow only the false-positive discriminator, and keep explicit
   agent markers fail closed.
2. If a new schema binding conflicts with the durable contract, keep runtime
   admission disabled, revise the single packaged schema, fixtures, SDK/host
   validator, and this delta together.
3. Rollback must not add an agent marker to the generic capability registry or
   allow a malformed persisted row to reach child startup.

## Versioning Decision

- No core or SDK distribution is released by this source checkpoint.
- The Slice 1 development SDK version is selected as `0.5.0a1`, aligning the
  existing `0.Y` compatibility formula with core `0.5.*` without claiming that
  compatibility before clean built-package proof.
- The standalone `orket-extension-sdk` distribution is the target installed
  owner of the public namespace. Core packaging must stop co-owning that
  namespace in Slice 1 without breaking the canonical source install; until
  that packaging transition and clean proof land, mixed installation is not a
  supported compatibility claim.
