# Outward Approval and Effect Lifecycle V1

Last updated: 2026-09-12
Status: Active implementation contract; complete enforcement remains the BT-1 gate
Owner: Orket Core

## Authority and scope

This contract governs outward proposals and the `/v1/approvals/{id}/approve`,
`/deny` and compatibility `/decision` routes. Implementation/proof status lives in
`docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`.
The scope is the existing outward connector family. This does not extend the
SupervisorRuntime Packet 1 families, single-turn proof-kernel claim ceiling,
untrusted-code admission or provider selection.

The associated delta is
`docs/architecture/CONTRACT_DELTA_OUTWARD_AUTHORIZATION_BT1_2026-09-11.md`.
Existing control-plane effect and checkpoint semantics remain authoritative in
`docs/specs/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md`.

## Proposal and decision

1. The application publishes a proposal, its pending run projection and event in
   one serialized transaction. Proposal numbering is not capped by queue paging.
2. Each executable proposal binds its complete call to run ID, persistent
   execution generation, turn/step, namespace, resolved workspace and target,
   connector contract version, canonical argument digest, resolved policy digest
   and version, submission time and expiry. Preview fields cannot supply authority.
3. The application owns decision policy. A storage unit of work acquires the
   SQLite writer lock before the application samples its injected clock and reads
   the authoritative pending row. The pending-status transition, run projection
   and decision event commit together or roll back together. Independent database
   paths refuse participation; silent cross-database partial publication is invalid.
4. At `now >= expires_at`, a pending decision becomes `expired`, attributed to
   `system:timeout` with `timeout_exceeded`. Approval/denial requested before the
   deadline may win. Queue reads are unnecessary for expiry enforcement, and a
   timeout scan cannot overwrite an already resolved proposal.
5. Resolved decisions are immutable. Repeated and contradictory decisions return
   the original decision, operator and timestamp; they do not acknowledge a second
   successful decision. The original proposal ID is the durable decision key.
   No generic HTTP idempotency-header contract is introduced.
6. Approval expiry bounds admission to approve, not delayed dispatch of already
   approved work. Dispatch still revalidates generation, policy, scope and binding.
   Changed inputs require new admission. A lease deadline does not extend or
   replace approval authority.

## Effect ownership and publication

Bound filesystem dispatch must consume the retained resolved target through an
OS file/directory handle boundary. Re-resolving model path arguments after intent
cannot redirect a write, read, directory creation or deletion. Validate the
original path against the binding, open the bound path without following new
reparse points/symlinks, retain its parent handles through execution and perform
file I/O on the opened handle. Local Windows and descriptor-relative POSIX paths
are the implementation targets; a missing required primitive fails closed. This
is target-binding enforcement, not hostile-process containment, protection from
privileged filesystem modification, or an arbitrary command filesystem sandbox.
Existing v1 bindings already retain the required root/target; their bytes remain
immutable. The binding commits a canonical pathname, not a historical inode/file-ID
or prior file-content digest; the opened object is pinned at dispatch. Cancellation
cannot release a thread-owned operation's handles before that operation has
finished, including repeated cancellation requests. The connector timeout uses
an `asyncio.timeout` scope in the owning task, so an outer task wrapper cannot
return cancellation before the bound executor drains its worker. An elapsed
deadline also waits for that drain before publishing a timeout result. A timeout
does not establish that no filesystem effect occurred; its retained receipt
cannot authorize redispatch. Intent without a recorded result remains uncertain.

1. Each proposal has one durable effect reference, retained after leaving the
   pending queue. Execution uses its protected complete call; latest model output
   and redacted previews cannot authorize dispatch.
2. Before calling a connector, commit a unique claim, monotonic fencing token and
   dispatch intent. Every approval, retry and recovery entrypoint uses this same
   application authority. Missing persistence prevents new dispatch.
3. An old proposal retry returns only that proposal's receipt/state. It cannot
   execute the current turn's call or advance the current turn again.
4. Reuse the existing `EffectJournalEntryRecord`, ordered journal validation,
   uncertainty classes and checkpoint acceptance rules. A claim/intent is not an
   observation. If publication spans databases, commit an outbox with the owning
   transaction, project idempotently, and require durable acknowledgement before
   dispatch. Do not introduce two writable histories of the same effect.
5. Observation/receipt and terminal projection publication are retryable without
   redispatch. Missing or duplicate ledger events are errors, never permission to
   execute again. Existing v1 ledger order/hash semantics remain until BT-2's
   separately versioned change.

## Recovery and migration

1. A prior owner may resume a committed claim with no intent only while its fencing
   authority is valid. Replacement requires evidence that the prior owner cannot
   dispatch; lease expiry alone is insufficient.
2. Intent without a conclusive observation is unresolved even if a crash might
   have happened immediately before invocation. Block automatic retry and retain
   uncertainty until reconciled. Arbitrary commands cannot be assumed idempotent.
3. Matching file content establishes a postcondition, not invocation causality.
   Stable connector keys help only where the connector independently enforces
   them. SQLite cannot guarantee generic exactly-once external effects.
4. Preserve old decisions, events, receipts and uncertain effects. Legacy proposals
   without their original complete binding require quarantine/new admission;
   permission cannot be reconstructed from current model calls or matching output.
5. Inventory/back up stores, stop old writers, rehearse upgrade/restart on copies,
   and enforce a durable writer-version gate before enabling migrated dispatch.
   Rollback disables dispatch while retaining history; it cannot revive reusable
   approvals or erase possible external effects.

Legacy generation 0 is retained history, not execution admission. Run submission
reentry, direct start and denial continuation refuse it with
`E_OUTWARD_LEGACY_RUN_QUARANTINED` before adding events or changing projections,
including when the retained status is terminal. Status inspection remains available.
Unbound pending proposals retain their original status even after their stored
deadline: ordinary queue reads and expiry sweeps skip them; attempted new decisions
return `E_OUTWARD_AUTHORIZATION_REQUIRED`. This quarantine is derived from retained
generation/binding fields and does not relabel historical outcomes or claim that
old effects never happened. A fresh independently submitted run requires its own
admission and approval. Quarantine is the selected disposition for records without
a complete binding and satisfies that migration requirement. Reconciliation or
replacement of the old run remains unsupported; admitting it later requires a
separate contract and proof. A new namespace does not prove physical target isolation.

## Pre-intent claim recovery

`GET /v1/approvals/{id}/effect` exposes the effect state, owner/fencing generation,
binding and receipt digests, without complete arguments or receipt contents.
`POST /v1/approvals/{id}/effect/recover` accepts `request_id`,
`expected_owner_id`, and positive `expected_fencing_generation`. Both routes use
the existing authenticated outward operator surface. A body cannot set its actor.

Recovery may replace only a retained `claimed` effect with no dispatch intent.
It compares the supplied owner/generation and validates the original approval,
binding, scope, policy and journal under the SQLite writer lock. The new owner
gets generation N+1; a shared control-plane recovery decision and operator action
commit with the new claim/journal entry. The old worker must pass the same fenced
intent transaction before calling a connector. Thus replacement prevents that
worker from dispatching even if its process is still alive. If intent committed
first, replacement fails. A lease deadline or an operator's assertion of process
death does not provide alternative authority.

The request key is scoped to proposal, operation and authenticated actor. Identical
retries return/reuse the original recovery decision; changed owner/generation or
actor with the same key conflicts. Repeated recovery cannot increment the fence
again, invoke a recorded effect again, or advance another turn. Normal approval
retries never reassign a claim. Intent without a receipt remains blocked for
observation/reconciliation, including timeout and process-death cases.

Initial effect journal references remain retained; references created after owner
replacement include their fencing generation. Existing shared journal and recovery
record contracts remain authoritative. No new mutable copy of those records is
introduced. This operation does not recover legacy unbound runs or initiate next-turn model
admission. Durable ready/observed model admission uses run reentry as defined below.

## Durable model admission

The outward planner requests `tool_transport_policy=profile`. Its complete
governed connector schema remains in the prompt, and the existing local provider
profile selects native tooling or JSON-wrapper generation. The admitted llama.cpp
profile uses JSON wrappers; native profiles keep their declared native tool
schemas and required choice. This does not select a different provider or relax
proposal validation/approval.

Starting a governed run and advancing a successful effect to another turn must
commit a model-admission record in the same transaction as the run projection
and turn events. Admission binds the run generation, turn, step and immutable
run input snapshot. One owner may claim it before provider invocation; concurrent
requests conflict instead of invoking another producer. A claimed admission with
no retained result is unresolved and cannot be reclaimed by ordinary run retry.
Explicit replacement follows the operator recovery contract below; elapsed time
alone is not replacement authority.

The extracted call and original model-evidence references/digests are retained
before publication. Retrying `POST /v1/runs` for that run may claim a ready
admission or publish a retained result without calling the model again. Proposal,
authorization, run projection, model-proposal event and admission publication
commit together. Errors and policy rejection use the same publication boundary.
Changed inputs, missing admission, corrupt evidence and a competing owner block
publication. Older running rows without admission are not silently backfilled.

Proposal-extraction artifacts describe the immutable extraction observation;
their `extracted_pending_proposal` value is not later overwritten with approval
admission. The retained admission publication, proposal row and ledger events
provide acceptance authority. An old approval retry still cannot start the next
model turn. This contract does not imply exactly-once provider billing or recover
a model response that was lost before durable retention.

## Explicit model-attempt recovery

`GET /v1/runs/{run_id}/model-admission` exposes the current turn's attempt scope,
state, owner, fence, input/result digests and recovery reference, plus retained
attempt summaries. Full inputs, tool arguments and response contents are absent.
`POST /v1/runs/{run_id}/model-admission/recover` requires `request_id`,
`execution_generation`, `turn`, `step_index`, `expected_owner_id` and
`expected_fencing_generation`. Both use the existing authenticated operator
surface; the server supplies actor identity.

The serialized recovery transaction may supersede only the latest claimed
attempt without a retained result, with unchanged run inputs. It retains that
row unchanged and creates fence N+1 in `ready`, with a shared recovery decision
and operator action. Observation and recovery contend on the same lock: if
observation wins, replacement is refused; if replacement wins, the old worker
cannot observe or publish. Repeating an identical recovery request returns its
original attempt without creating another one, calling the provider or advancing
another turn. Conflicting actor/body reuse and superseded recovery return conflict.
Public run reentry then claims the ready attempt through normal model authority.

New attempts use distinct immutable evidence directories derived from their
run/generation/turn/step/fence identity. The ledger references the admitted attempt;
no mutable latest alias can select evidence. Migration retains old rows and
artifact references as legacy layout, retires the old table name against mixed
writers, and never rewrites historical artifacts. Replacement always uses the
new layout. Missing/contradictory recovery records prevent continuation.

Recovery authorizes another volatile model computation. It does not establish
whether the prior provider call ran or was billed, cancel a remote invocation,
or retry a governed connector. Both providers may finish; only the current
attempt can publish an approval, whose own effect still requires authorization.

## Acceptance

BT-1 acceptance requires authenticated separate-connection/process decision and
dispatch races; old approval retries through restart; argument/policy/scope/
generation drift; deadline and lock-wait cases beyond the pending scan cap; each
claim/intent/dispatch/receipt/publication crash point; copied-store migration;
and independently observed files/append effects. A green decision test alone
does not prove durable effect ownership or close the full BT-1 gate.

## Current enforcement checkpoint (2026-09-12)

The source candidate enforces immutable bindings, serialized decisions and
expiry, unique fenced claim/intent, shared journal linkage, uncertain retry
refusal and receipt-based atomic publication. New admitted runs persist generation
1; unbound legacy generation 0 cannot acquire execution authority. Explicit
authenticated recovery may replace a pre-intent claim with fencing generation
N+1 and atomic shared recovery/operator records. Normal approval retry and lease
expiry never reassign ownership. Missing or contradictory recovery records block
both inspection and dispatch. Model-attempt recovery now appends a ready fenced
replacement, retaining the old unresolved row and atomically recording shared
recovery/operator authority. Attempt-scoped files and fenced observation keep late
old output from acquiring proposal authority. Ordinary run retry cannot replace
an owner; provider execution/cost uncertainty remains explicit.

Approval schema v2 retires the old table name and protects original metadata,
binding, decisions and history against replacement/update/deletion. Populated v1
stores require the copied offline upgrade in `docs/RUNBOOK.md`. Legacy statuses
remain historical records; they do not confer current execution authority.

The combined SR-01 through SR-04 behavioral gate passes for the current candidate
on Windows local drives and Linux POSIX filesystems with Python 3.11/3.12.
The 194-case installed-wheel BT-1/BT-2 envelope covers independent decision races,
dispatch/recovery crash boundaries, copied migration, target replacement and
repeated filesystem cancellation/timeout. Runtime source is excluded from the
foreign test harness. The installed Windows Python 3.11 wheel also passes live
llama.cpp approved-write and authenticated TCP/API proof with confirmed shutdown.
Exact evidence and limits are recorded in the canonical architectural-truth plan.
This acceptance is not core release approval or proof of untested hosts/providers.
Connector
receipts and local fixture proof do not extend workload acceptance or formal
single-turn claims.
