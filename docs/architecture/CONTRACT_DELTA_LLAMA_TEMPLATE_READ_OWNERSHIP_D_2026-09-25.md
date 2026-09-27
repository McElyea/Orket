# Retained llama.cpp template read

## Summary
- Change title: Retain the admitted template-file read before provider HTTP work.
- Owner: Orket Core.
- Date: 2026-09-25.
- Affected contract: `PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`, LP-15.
- Status: implementation contract for the 0.6.106 development candidate.
  Acceptance and publication remain owned by the architectural-truth plan.

## Delta
- Published behavior: matching text-template verification uses a bare
  `asyncio.to_thread` read. Caller cancellation can return while its file worker
  continues, and can mask the admitted worker's later native failure.
- Required behavior: use the existing `run_owned_thread` owner for that same
  bound `read_bytes` call. One or repeated cancellations retain the read until
  settlement. Successful native completion restores cancellation; native failure
  retains precedence and exact exception identity.
- An interrupted read does not continue to provider HTTP work. The verifier's
  nonmatching-version return still performs no template-file or HTTP observation.
- Template bytes, profile identity, independent render comparison, canonical
  hashes, native token accounting and context-budget checks are unchanged.
- No second file implementation, executor, thread lifetime, HTTP client owner,
  provider fallback, forced thread stop or new read deadline is introduced.

## Migration Plan
1. Compatibility window: existing verifier callers and result schemas remain.
2. Migration steps: replace only the unretained native-read await with the shared
   owner. Keep HTTP ordering, selected file and all render checks unchanged.
3. Validation gates: preserve matching/mismatching template/model/render/budget
   and unsupported-message controls; hold a real file read, issue single/repeated
   cancellation, require real SQLite responsiveness below 0.5 seconds, remove
   the admitted file for native failure, join the physical read and close its
   client, and prove no HTTP admission on the interrupted paths.
   Source and installed proof remain required. A forbidden HTTP fixture and
   local template read are not live server, model, tokenizer or inference proof.

## Rollback Plan
1. Rollback trigger: changed template/render behavior or unowned admitted reads.
2. Rollback steps: stop candidate publication and correct the shared ownership
   binding; do not bypass template verification or silently select another provider.
3. Data/state recovery notes: preserve every failed/passing observation. This
   read performs no product file write and does not roll back external file changes.

## Versioning Decision
- Version bump type: patch correction of native-read lifetime and error precedence.
- Effective version/date: 0.6.106 development candidate / 2026-09-25.
- Downstream impact: interrupted callers may wait for the admitted read; a native
  read failure remains visible. No successful result or persisted schema changes.
