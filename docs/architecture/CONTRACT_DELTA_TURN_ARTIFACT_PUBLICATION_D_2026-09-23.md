# Turn artifact destination, inputs and publication ownership

## Summary
- Change title: Capture one turn artifact destination and retain admitted publication.
- Owner: Orket Core.
- Date: 2026-09-23.
- Affected contract(s): `docs/specs/TURN_ARTIFACT_PUBLICATION_CONTRACT.md`,
  protocol local prompting, epic runtime time inputs and governed turn recovery.
- Status: 0.6.102 implementation migration. Acceptance, publication and observations
  remain owned by the architectural-truth remediation plan.

## Delta
- Current behavior: published .101 permits an interrupted response caller to finish
  before its native write, reads mutable raw input after the text write, and allows
  lexical artifact workspace escape. Matched source/installed openings retain five
  lifetime/input failures plus two healthy controls, and two path failures plus two
  healthy controls per cell. Broader migration requirements are not yet live proof.
- Proposed behavior: one required frozen destination binds the existing writer,
  absolute workspace and original identity before owner admission. Named prompt,
  response, parser, counter, memory, checkpoint, dispatch and recovery values are
  captured at their documented boundaries. Existing owned I/O drains admitted work.
  Clean cancellation stops subsequent admission; preserved late failures retain
  existing error-handler/failure-publication behavior, including prefix overwrite.
- Intentional changes: path-bearing internal APIs require a destination with explicit
  role ID (or explicit None for retained approval identities); path components reject
  lexical redirection; raw JSON renders before text publication; the existing runtime
  clock callback reaches parser/checkpoint consumers explicitly. New checkpoints use
  one timestamp across local and control-plane records. Existing record time remains.
  A separate invocation binding retains the existing dispatcher/control-plane owner,
  namespace and resume/replay selections across the execution-owner wait. Initial
  model and corrective inputs share the captured prompt sequence used by artifacts.
- Preserved behavior: entry defaults, healthy artifact formats and ordering, parser
  strict/partial/native policies, direct/provider counter precedence and conversion
  scope, only coroutine awaiting, memory normalizations and capped error recovery,
  prompt sinks, .101 command/result capture, BT-1 through BT-5 and resource ownership.
  Snapshot reads retain their missing/malformed/unreadable classification; converted
  read failures inside the owner do not suppress a pending caller cancellation.
- Why required now: D's reached artifact boundaries currently separate caller lifetime,
  mutable input and actual path authority. Centralizing without lifetime/capture and
  composed recovery proof would leave the observed defect class reachable.

## Migration Plan
1. Compatibility window: none for these internal call sites. Migrate all production
   and test callers together; no compatibility fallback or mutable destination cache.
2. Migration steps: introduce the shared destination; move writer, memory, response,
   parser and budget consumers to required captured values; wire the existing clock;
   migrate dispatch, checkpoints, replay and approval recovery; update durable sources.
3. Validation gates: retain both matched openings; real physical failure/interruption
   and capture controls, composed owner/provider identity controls, recovery mismatches,
   unchanged SQLite <0.5s/deadlines, full affected source/installed parity and C checks.
   Freeze all candidate bytes during proof. Structural review alone does not accept it.

## Rollback Plan
1. Rollback trigger: changed accepted behavior, failed ownership/identity recovery,
   source/package drift or missing acceptance evidence.
2. Rollback steps: keep the candidate unpublished and correct under a new proof phase,
   or revert the complete API migration as one scoped change. Preserve every observation.
3. Data/state recovery notes: completed documents and partial prefixes can remain;
   publication is not an atomic bundle. Existing pre-effect recovery/acceptance rules
   govern records. No automatic repair, rollback, reacceptance or evidence deletion.

## Versioning Decision
- Version bump type: patch within the active 0.6 remediation lane.
- Effective version/date: candidate 0.6.102, only after required verification/publication.
- Downstream impact: internal Python callers must supply destination and clock inputs.
  Existing artifact schema and accepted replay identities stay compatible. No new
  provider, Linux, hostile-code, hard-deadline, full-coverage or lane-completion claim.
