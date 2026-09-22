# Approval submission input contract delta

Status: active scoped D implementation; whole-lane acceptance remains open.

`OutwardApprovalService.request_tool_approval` captures argument values before
waiting to acquire its database transaction. `request_in_transaction` captures
argument values before its first storage wait, including when called directly
by application model publication. Nested caller mutation after either boundary
cannot replace the pending proposal preview, authorization digest or the
arguments retained in its atomic proposal/run/event publication.

Run authority, approval policy, proposal numbering and submission time continue
to be read within the acquired transaction. Capturing caller arguments does not
freeze the database before a writer wait or retain an earlier authorization or
expiry timestamp. Existing durable admission, rollback, dispatch drift refusal,
claim/intent/publication and effect recovery owners remain authoritative.

Migration: provide the intended argument values when starting submission and
start a new invocation to submit changed values. Capture covers standard copied
argument values, not arbitrary custom copy callbacks or concurrent external
configuration mutation. Stable inputs retain existing proposal identities,
serialization, digest recipes, policy and expiry behavior.

Required proof: retain current-wheel counterexamples for argument changes during
public writer acquisition and direct transaction run/count reads; preserve a
post-writer timestamp compatibility control; verify actual SQLite proposal,
run and event values plus no file effect. Source and installed acceptance must
also preserve affected rollback, migration, authorization and recovery cases.
Controlled clocks/model output are not provider inference. Broader D, Linux,
provider, E/CAP and lane acceptance remain separate obligations.

Predecessor: `CONTRACT_DELTA_AUTHORIZATION_INPUTS_D_2026-09-21.md`.
