# Frozen native operation and input ownership

## Summary
- Change title: Close frozen ATG-04 native ownership and input gaps.
- Owner: Orket Core.
- Date: 2026-10-01.
- Affected contracts: `docs/specs/SHARED_IO_CANCELLATION.md` and
  `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`,
  `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`, `docs/specs/OUTWARD_RUN_AUTHORITY.md`,
  `docs/specs/RUN_EVIDENCE_GRAPH_V1.md` and `docs/specs/GOVERNED_AGENT_LOOP_V1.md`.

## Delta
- Current behavior: Direct demo and marshaller file calls could abandon admitted
  native work on cancellation, observe later paths/payloads, or miss digest adoption.
- Proposed behavior: Existing shared owners retain native work and close. Governed
  demo paths bind before waits; marshaller writers bind construction roots and capture
  publication inputs. Ledger append retains physical append and successful digest
  adoption together. Returned ledger records are detached JSON values actually stored.
  File commands share the artifact module's read/write implementations and capture
  admission roots, sequences and actor identity. Attempt/workload calls snapshot
  consumed inputs before native work. Native file ownership does not establish the
  separate marshaller process adapter's interruption or descendant-cleanup behavior.
  Quickstart applies shared ownership to ledger create/read/publication, operator
  input/output and file readback. Synchronous callbacks execute in native workers;
  caller interruption can leave prior effects without a terminal event.
  Outward policy validation reuses connector input capture and native settlement.
  Offline migration binds database/unit inputs; SQLite backups own both connections
  through committed-WAL copying and close. Support graphs capture payloads/roots and
  retain file operations without acquiring execution authority. Manual wake requests
  capture namespace inputs before their retained native read. Existing domain error
  envelopes, policy refusal and supplemental degraded observations remain unchanged.
- Why this break is required now: These are frozen ATG-04 defects. Cancellation
  cannot establish completion while required native work remains active.

## Migration Plan
1. Compatibility window: Apply with the v0.6.121 checkpoint. No shim or new
   filesystem authority. Public signatures and serialized output remain unchanged.
2. Migration steps: Retain interrupted calls until settlement. Construct new writers
   to select another relative construction root. Consume ledger records as JSON
   values; tuple payloads return as arrays. Inspect partial output before recovery.
3. Validation gates: Direct public native holds, SQLite responsiveness, input mutation,
   cancellation/deadline, failure/partial-effect and real CLI/Git flows; both Quality
   selections; dependency, Ruff, taxonomy and docs gates. Broader installed/provider
   and whole-queue acceptance remain separate.

## Rollback Plan
1. Rollback trigger: Regression in recorded native failure, serialized output or
   preserved publication ordering.
2. Rollback steps: Revert the affected cohesive batch and its contract/docs together;
   retain the debt as open. Do not remove tests or weaken deadlines to mask failure.
3. Data/state recovery notes: Existing files, commits and ledger bytes can survive a
   failed caller. No whole-bundle rollback or automatic ledger repair is promised.

## Versioning Decision
- Version bump type: Patch; scoped architectural checkpoint.
- Effective version/date: 0.6.121 / 2026-10-01.
- Downstream impact: Internal embeddings now wait for native settlement. Relative
  writer roots bind at construction; ledger result values reflect their JSON encoding.
  CLI names and serialized evidence contracts remain unchanged. Compatibility:
  `breaking / internal_only / required` for those direct embedding timing/value rules.

The unchanged dependency gate rejected six interface-to-adapter imports in the
first combined candidate despite 634 passing source cases. Quickstart now calls
concrete ledger/action operations in `application/services/quickstart_io_service.py`;
manual wake request-file capture/read/validation lives in the existing application
command service. Interfaces retain formatting and caller argument capture. No edge
waiver, layer reclassification, generic re-export or second native owner was added.
