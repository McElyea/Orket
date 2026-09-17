# Retained Gitea Export Commit and Receipt Recovery

## Summary
- Change title: Confirm lost Gitea export results from retained Git intent.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `GITEA_ARTIFACT_EXPORT_CONTRACT.md`,
  `CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`, preparation schema and export receipts.

## Delta
- Opening behavior: an actual successful push followed by lost local acknowledgement
  leaves preparation permanently uncertain because its journal lacks a commit to
  inspect. The exporter also rebuilds mutable payloads and suppresses some Git errors.
- Required behavior: prepare the exact local commit before remote mutation; retain
  `gitea_export_intent.v1` with the export-started marker in `epic_preparation.v2`.
  Dispatch that commit once. Recovery reads the remote branch and confirms commit
  ancestry, subtree and manifest identity before publishing the receipt.
- Bind effective workspace and author identity alongside existing target settings.
  Retain export time and use a run-ID hash suffix for remote paths. Receipts use
  immutable commit URLs. Unsafe components, source symlinks/reparse points and
  escaping payload paths reject preparation; secrets stay outside bindings/URLs.
- HTTP and Git execution are asynchronous. Git errors and truncated diagnostics
  are failures. The existing process cleanup helpers move to the shared execution
  adapter and their internal caller imports move with them; no forwarding shim is added.
- Remote evidence that is missing or unconfirmed still blocks automatic retry.
  This change does not infer that no effect occurred or grant owner takeover.

## Migration Plan
1. Preparation v1 lacks this intent contract and is rejected. Expanded export
   bindings also reject old insufficient inputs. Preserve old records and digests;
   do not reconstruct an intent from current workspace output.
2. Preserve the journal and local Git objects needed for first dispatch. Confirmed
   remote commits can be fetched for recovery. New paths use the documented run-ID
   hash suffix; old exported paths are not moved or overwritten by migration.
3. Validate actual Gitea pushes, lost acknowledgements, native death after push,
   death before push, unchanged remote commit counts, payload freezing and
   mismatched/absent commit evidence. Reconfirm the shared process helper consumer.
4. Use an explicitly selected disposable localhost instance and prove removal of
   its container/anonymous volumes. Production Gitea is not a proof fixture.

## Rollback Plan
1. Trigger: recovery repeats a push, loses original payload identity, or publishes
   success without confirming the retained remote commit.
2. Stop affected reentry and retain all intent/commit/effect evidence while repairing
   the protocol. Do not restore best-effort error swallowing or clear the journal.
3. Unconfirmed remote attempts need owner recovery; a new session does not repair
   the uncertain old effect.

## Versioning Decision
- Effective date: 2026-09-12; new internal `gitea_export_intent.v1` and
  `epic_preparation.v2` contracts.
- No release/version bump or production migration is performed in this worktree.
- Direct enabled exporters now require retained intent. Runtime callers use the
  application preparation path; external callers must adopt the same admission contract.
