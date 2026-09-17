# Card Completion Acceptance Boundary

## Summary
- Change title: Separate declared card acceptance from verifier and turn success.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md` and
  `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` and
  `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`; BT-3/SR-07 remains active.

## Delta
- Opening behavior: an empty workspace returned `RuntimeVerificationResult.ok`
  true, synthesized `done`, and persisted it. Explicit model completion also persisted
  after role/state checks without evidence sufficiency. The composed six-case
  counterexample also reproduced syntax-only and wrong-output completion.
- Required behavior: application-owned acceptance admission and validated evidence
  feed one pure, typed comparison. Evidence binds every declared criterion to its
  verifier, policy, workload, inputs, artifacts and run/attempt. All completion
  paths must enforce that result through final persistence.
- Implementation boundary: core types/comparison now have an application-owned
  CLI verification and retained-evidence service. It captures exact artifacts,
  checks declared cases, and re-reads content-addressed SQLite evidence. A configured
  completion authority now rechecks that evidence and fresh scope inside the final
  card writer transaction. Typed explicit/synthesized requests and file-write
  serialization pass composed proof. Standard runtime composition, turn context,
  receipt-bound final turn publication/reentry and builtin writer ownership are
  wired. Compact prompts retain acceptance and tool-call contracts. Remaining
  outcome consumers, custom writers, regression repair and installed-wheel proof
  keep SR-07 open.
- Build outcome extension: application inspection now holds one card writer guard
  across the full inventory and retained receipt bindings. All expected cards
  must be present and every observed card must have accepted `done` or
  `guard_approved` state. Empty, missing, canceled, archived, receiptless and
  evidence-unreadable work cannot become session `done`. Ledger artifacts retain
  `card_completion_outcome.v1`, as specified in the acceptance contract.
  The runtime-local card protocol is removed in favor of the canonical core port.
- Event correction: loop termination now emits `orchestrator_epic_stopped`.
  `orchestrator_epic_complete` follows accepted control-plane/ledger finalization;
  a strategy-supplied event name cannot authorize that claim. Existing source
  attribution gates remain. This snapshot does not imply atomic publication
  across stores or permanent currency of workspace contents. Historical logs and
  legacy terminal rows do not gain acceptance through this change.
- Shared-verifier repair: JSON checks previously accepted a clipped valid prefix
  hiding invalid trailing output, and replacement-decoded invalid UTF-8. Capture
  metadata now exposes truncation, encoding, raw byte counts and digests; lossy
  stdout cannot pass a JSON contract. Actual argv is retained and string arguments
  preserve whitespace/empties; non-string or NUL-containing argv is rejected.
  An optional explicit environment supports the new service's sanitized child
  execution without changing the default environment for existing callers.
- Artifact family: explicitly declared `card_artifact_acceptance.v1` supports
  strict UTF-8 literal text and selected JSON object values. Application-owned,
  non-executing checks reconstruct `artifact_verification` evidence from captured
  bytes. These use `card_acceptance_package.v2` without command receipts; the
  existing CLI v1 family and digest serialization remain unchanged. Unknown or
  mismatched definition/package families fail closed. Both use the same final
  persistence gate and immutable store; no new database migration is required.
- Canonical workload repair: tiny summation assets now declare their actual
  requirement, selected design fields, implementation/review CLI cases and optional
  attribution JSON. Turn prompts retain the validated criteria definition.
  Empirical support results survive later preparation saves; a passing fixture
  without declared acceptance still cannot authorize completion. These bounded
  checks do not establish general workload quality or CAP-1 acceptance.
- Provider request option: the existing OpenAI-compatible response-format override
  additionally accepts `json_object`, requesting an object without changing
  provider/model selection or relaxing runtime parsing. Request-shape tests are
  structural proof; actual server/model conformance must be recorded separately.
- Reason: verifier success and process termination are weaker claims than
  satisfying the workload's declared acceptance requirements.

## Migration Plan
1. Compatibility window: no new boolean fallback, universal verifier or historical
   evidence promotion. Existing packet-1 projection and support-artifact contracts
   retain their scope.
2. Migration steps: card schema v2 adds persisted attempt generations/contexts,
   completion references and immutable receipts. New successful writes require
   application authority; existing terminal rows retain history without receipts.
   The additive migration is exercised on isolated proof databases only. Standard
   runtime composition now supplies the service and evidence store beside its
   card database, named `<runtime-db-filename>.card_acceptance.sqlite3`. Finish
   remaining outcome consumers and writer coordination, then prove the complete gate.
3. Validation gates: typed contract checks plus composed negative and sufficient
   runtime flows to SQLite; stale/cross-run/mutation, bypass and concurrency proof;
   provider-backed and supported-host proof before the full BT-3 gate closes.

## Rollback Plan
1. Rollback trigger: incorrect binding or evidence admission discovered during
   implementation or proof.
2. Rollback steps: retain the counterexamples and fail closed on the affected
   completion path; repair the acceptance boundary before admitting it. Do not
   restore a verifier-boolean fallback as accepted behavior.
3. Data/state recovery notes: evidence stays in a separate store, selected by the
   caller or the standard runtime default described above;
   schema v2 receipts and attempt bindings reside in card storage. No production
   database has been migrated. Preserve v2 records on rollback; do not remove
   enforcement or rewrite history into acceptance. Isolated databases are proof data.

## Versioning Decision
- Version bump type: no release action in this worktree checkpoint.
- Effective version/date: definitions retain explicit v1 identifiers; artifact
  evidence adds package v2 on 2026-09-12. Runtime enforcement is incomplete.
- Downstream impact: card persistence now rejects unsupported completion and tools
  expose missing acceptance evidence when available. Standard runtime completion
  and reentry require retained receipts; standalone unconfigured repositories
  fail closed. Build consumers must distinguish workflow stop from accepted
  completion, and event consumers must use the corrected semantics above.
  Only the explicitly declared bounded acceptance families above are implemented;
  broader capability admission and whole SR-07 acceptance remain open.
