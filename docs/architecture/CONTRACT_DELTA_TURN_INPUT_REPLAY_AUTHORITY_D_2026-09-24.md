# Turn input, operation replay and checkpoint authority

## Summary
- Change title: Bind Packet-1 construction intent and validate retained turn replay inputs.
- Owner: Orket Core.
- Date: 2026-09-24.
- Affected contracts: `TURN_ARTIFACT_PUBLICATION_CONTRACT.md`,
  `PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`, `CONTROL_PLANE_TERMINAL_AUTHORITY.md`
  and `TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`.
- Status: implementation contract for 0.6.105. Acceptance, packaging and publication
  remain owned by the architectural-truth remediation plan.

## Delta
- Published 0.6.104 behavior: Packet-1 start and closeout can select different
  construction-input objects after a mutable context-slot replacement. Present
  operation records can be accepted, treated as missing or republished without one
  strict identity/argument/result-digest check. Governed cache hits can bypass the
  durable execution gate and step/effect alignment. Checkpoint consumers validate
  filename identity and shape without comparing the full payload to its retained
  integrity reference.
- Required behavior: bind the already selected `RuntimeConstructionInputs` object
  into initial and closeout Packet-1 callbacks. Read an operation slot through the
  existing owned file operation and classify only actual content absence as a miss.
  Apply one strict operation validator to embedded replay, ordinary cache reuse and
  completed replay. Governed hits also require the existing durable run/attempt/
  resource gate and step/effect/call alignment. Validate the full checkpoint digest
  in completed replay, pre-effect resume and approval continuation.
- Cached publication: after-tool hooks receive detached values and must preserve
  canonical arguments/result. Retained operation bytes are not reserialized.
  Governed nonprotocol calls use the strict operation slot before legacy fallback;
  admitted legacy reuse can create an absent operation slot without rewriting the
  legacy file. This is not authorization for public resume over retained effects.
  A subsequent cached determinism violation refuses before result substitution
  or publication, using its existing diagnostic. Live result adaptation remains.
- Terminal truth: a local zero count cannot override a same-attempt effect journal
  read in the existing closeout transaction. Failures retain post-effect/failed
  classification. Empty-attempt and unresolved-dispatch rules remain; step-only
  split authority is not reconciled by this correction.
- Embedded replay boundary: `TurnExecutor` still performs model inference and parsing
  for a fresh proposal, then reuses exact stored operation results without toolbox
  or governed control-plane execution. This does not change the separate
  `orket protocol replay` recorded-run interface, which bypasses model inference,
  prompt construction and validator repair heuristics.
- Preserved authorities: `RuntimeConstructionInputs`, `TurnArtifactDestination`,
  `TurnControlPlaneBinding`, `TurnArtifactWriter`, the existing owned-I/O adapter,
  native run owner, control-plane service/transaction owners, canonical protocol
  JSON/hash functions and checkpoint integrity-reference format. No new writer,
  lock, clock, repository, serializer, result schema or operation identifier.
- Diagnostic contract: present-invalid records use
  `E_OPERATION_ARTIFACT_INVALID` with finite record reasons. Missing/conflicting
  governed anchors use `control_plane_anchor_missing` or
  `control_plane_anchor_mismatch`; named terminal-join errors are converted into
  that anchor family. Checkpoint mismatch uses
  `E_CHECKPOINT_SNAPSHOT_INTEGRITY_MISMATCH`.
  Cached middleware changes use `E_CACHED_RESULT_MIDDLEWARE_AUTHORITY` with
  `args_changed` or `result_changed`.
  Cached determinism refusal uses the existing `E_DETERMINISM_VIOLATION` family.

## Explicit ceilings
- A result plus its canonical digest establishes local operation-record
  self-consistency. Current step/effect schemas do not commit that digest, so a
  coordinated result-plus-digest rewrite remains outside the guarantee.
- Run, attempt, reservation, lease, resource, step and journal observations are not
  one snapshot. The final run reload detects run movement through the gate; other
  authority can move after its own read. New dispatch and step/effect publication
  retain their existing transactions.
- Legacy call-keyed `tool_result_*` files have no content digest. Governed reuse gains
  durable call/anchor authorization, not operation-record content integrity.
- Pre-effect resume can commit its existing recovery prefix before snapshot
  integrity refusal. The change adds no rollback, repair, replacement attempt or
  reordered recovery authority.
- Refusal is per operation. Earlier and later independent calls and final violation
  aggregation retain their existing publication/effect semantics. There is no
  whole-turn rollback or stop-on-first-refusal behavior.
- This contract adds no hostile-filesystem containment, remote provider admission,
  Linux result, full replay determinism, forced native deadline, full-suite result
  or whole-goal completion claim.

## Migration Plan
1. Bind one selected construction-input object when constructing the epic run owner;
   require it through Packet-1 start and summary builders. Migrate direct internal
   callers together; add no optional fallback or forwarding shim.
2. Produce and consume operation records through one builder/validator using the
   existing canonical JSON authority. Preserve operation IDs, filenames and valid
   canonical records. Present noncanonical legacy records refuse rather than use a
   second fallback hash policy.
3. Keep policy/compatibility/workspace/gate/skill/approval order before cache
   selection. Governed operation-record and legacy hits share the current execution
   gate and durable alignment predicate; true misses retain normal dispatch.
4. Use the existing full checkpoint serialization formula and validate the retained
   reference in all three consumers before using tool-plan content. Preserve each
   consumer's established recovery and diagnostic ordering.
5. Update fixtures that hand-build operation records to include exact operation ID,
   tool, canonical arguments and digest. Preserve route-specific descriptive text
   alongside stable reason codes. The plan owns matched opening, source/installed
   execution, package parity and retained physical evidence.
6. Internal middleware callers explicitly supply `replayed`. Cache selection takes
   explicit governed status and returns result, replay provenance and operation-slot
   provenance; both persistence paths require that provenance. Migrate repository
   callers together, without an optional compatibility default. Dispatch admission
   requires explicit replay provenance on both cache and live paths.

## Rollback Plan
1. Trigger: valid canonical records or Packet-1 precedence change, a present-invalid
   record becomes redispatchable, checkpoint authority weakens, or acceptance fails.
2. Repair or revert the implementation and these contract changes as one scoped
   migration. Preserve every opening and candidate observation.
3. Do not delete retained operation files, checkpoints, control-plane rows or
   Packet-1 summaries. Historical noncanonical records require explicit migration
   or refusal; rollback does not grant them execution authority.

## Versioning Decision
- Version bump type: patch in the active architectural-remediation lane.
- Target: 0.6.105, published only after canonical scoped acceptance.
- Compatibility status: required internal migration; no compatibility shim.
- These requirements describe implementation semantics. They are not proof that
  source, installed packages, providers, Linux or the complete D lane passed.
