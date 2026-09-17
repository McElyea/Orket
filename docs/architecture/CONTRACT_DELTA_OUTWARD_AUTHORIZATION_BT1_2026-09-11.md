# Outward authorization and effect lifecycle: BT-1 delta

Status: Implemented; scoped BT-1 behavioral acceptance passed on the recorded Windows/Linux matrix

The settled lifecycle contract is `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`.
The decisions below define the implementation target; consult the canonical plan
for which guarantees have actual runtime proof.

## Summary

- Change title: Bind each outward approval to one effect and serialize its decision and dispatch authority.
- Owner: Orket Core; BT-0 preparation by Codex in `codex/architectural-truth-bt0`.
- Date: 2026-09-11 (America/Denver).
- Affected contracts: `docs/API_FRONTEND_CONTRACT.md` outward approval clauses;
  `docs/specs/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md` effect publication;
  `docs/architecture/event_taxonomy.md`; outward proposal/run persistence.
- Related scope limits: `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
  and `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md` remain bounded
  to their admitted families. Reusing their primitives does not extend Packet 1.

## Delta

Pre-repair behavior was reproduced through authenticated ASGI requests, real SQLite
connections, actual file/command effects and a new Python process on 2026-09-11:
an old approval executes a later same-tool call; overlapping retries execute twice;
approve and deny both acknowledge success; direct approval ignores its deadline.
The tests assert the healthy opposite. Atomic proposal/decision publication and
serialized expiry, immutable bindings, durable claims/intent, shared journaling
and receipt-based publication are implemented in the worktree. Pre-intent owner replacement is also implemented through the explicit
recovery contract below. Legacy records are explicitly quarantined; claimed model attempts have the fenced replacement contract below. Durable ready/observed admission follows its decision below. The canonical lane plan owns coverage and
proof ceilings. The scoped combined SR-01 through SR-04 gate now passes the
recorded installed-wheel Windows/Linux Python 3.11/3.12 envelope and live installed
llama.cpp/application/API proof. This is not core release or broader capability
approval; the canonical plan contains the requirement audit and retained failures.

Settled BT-1 implementation decisions:

1. **Binding.** Persist the full JSON call and an immutable binding containing
   proposal ID, run ID, execution generation, turn/step, namespace, resolved
   workspace/target, connector name and contract version, argument digest, resolved
   policy version/digest, submission time and expiry. The application collects
   these inputs before proposal publication. Previews are derived redacted views.
   The latest model call cannot supply dispatch arguments. Reuse the existing
   outward canonical argument hashing rule; extract/import it rather than adding
   another recipe. A generation cannot be inferred on restart.
2. **Decision transaction.** The application owns decision policy; the storage
   adapter owns one SQLite `BEGIN IMMEDIATE` unit of work over co-located proposal,
   run projection and event rows. Sample the injected application clock after the
   writer lock is acquired. Re-read the proposal, apply pending-status CAS, and
   commit the winning decision, projection and event together. Failed persistence
   permits neither successful acknowledgement nor dispatch. Different database
   paths refuse this mode instead of performing three independent commits.
3. **Expiry.** `now >= expires_at` expires a pending decision with system timeout
   attribution, regardless of the requested decision or any prior queue access.
   Before that instant either approval or denial may win. Queue expiry uses the
   same transaction and cannot overwrite a resolved proposal. Expiry bounds
   approval admission, not dispatch of an already approved effect. Delayed first
   dispatch still requires unchanged generation, binding, policy and scope;
   invalidation requires a fresh proposal. Approval TTL and lease ownership are
   separate; this decision adds no implicit second dispatch deadline.
4. **Retries.** Preserve the response envelope and return the original durable
   decision for repeated or contradictory decisions, including its original
   operator and timestamp. A denied/expired result never dispatches. An approved
   retry resolves only its own effect reference/receipt and cannot advance the
   current turn again. The proposal ID is the durable decision key. This slice
   introduces no generic HTTP idempotency-header guarantee. Any later such key
   must bind authenticated actor, operation, proposal and request digest, with
   conflicting reuse returning conflict.
5. **Ownership.** Persist a unique effect reference derived from the immutable
   proposal, with a monotonic fenced owner token and dispatch state, before
   executing the connector. Claim and journal intent must be durable before
   crossing the boundary. Approve, compatibility-decision and recovery entrypoints
   use the same application authority. Lease timeout alone cannot replace an owner
   that may still cause an external effect.
6. **Journal reuse.** Reuse `EffectJournalEntryRecord`, ordered publication and
   uncertainty rules, and supervisor checkpoint acceptance. A claim is admission
   to attempt, not observed effect evidence. `GovernedAgentEffectService` provides
   immutable proposal, CAS and reconciliation patterns; it does not prove a generic
   exactly-once connector primitive. If control-plane publication is in a separate
   database, commit an outbox with the outward transaction, project idempotently
   and require durable acknowledgement before dispatch. Maintain one authoritative
   journal, not independently writable effect histories.
7. **Recovery.** A committed claim without dispatch intent is eligible only for a
   fenced continuation after proving the previous owner cannot dispatch. Intent
   without a conclusive observation is unresolved, including a crash immediately
   before the connector call; block automatic retry. Confirmed observations can
   finish publication without another execution. Arbitrary `run_command` cannot
   retry across uncertainty. Matching file content establishes a postcondition,
   not which invocation caused it. Connector idempotency is usable only when the
   connector independently enforces the stable key. SQLite cannot guarantee
   generic exactly-once external effects.
8. **Ledger compatibility.** Retain current v1 event bytes and ordering semantics
   in the decision transaction. Do not reseal history. BT-2 separately versions
   append-order/hash changes and preserves previous exports. Missing/duplicate
   events are failures, never justification to redispatch an effect.

Reason for the change: SR-01 through SR-04 broke authorization even with
deterministic model fixtures. Their repaired behavioral gate precedes outward expansion.

## Migration Plan

1. Compatibility window: retain endpoint shapes; unsafe legacy unbound dispatch
   gets no compatibility window. Keep `main.py` and `--rock` through 0.6.x under
   their existing separate contract.
2. The active lifecycle spec settles these decisions. `CURRENT_AUTHORITY.md`, the
   API contract, event taxonomy and `docs/RUNBOOK.md` describe the implemented
   transaction/effect boundaries and explicitly retain uncertainty and unsupported
   recovery cases instead of granting implicit redispatch authority.
3. Inventory/back up stores; stop old writers; migrate a copy first. Preserve
   decisions, events and receipts. Quarantine executable legacy proposals lacking
   their original complete binding. Never reconstruct permission from the latest
   model output, redacted previews or matching file content.
4. Require a schema/writer-version gate rejecting mixed dispatch writers. Rehearse
   interrupted migration and restart before enabling dispatch.
5. Validation: all BT-1 races, binding-drift variants, expiry beyond the scan cap,
   process crash points and independently observed effects in the canonical plan.
   The current BT-0 tests are a starting set, not the complete gate.

## Rollback Plan

1. Trigger: binding mismatch, mixed writers, lost journal linkage, duplicate or
   unauthorized effects, inconsistent projections or uncertain migration.
2. Stop dispatch while retaining inspection/evidence. Roll forward using reconciled
   records; never restore reusable approvals to obtain a green result.
3. Preserve claims, intent, observations, outbox acknowledgements and uncertainty.
   A backup restore cannot erase externally possible effects or authorize retry.

## Versioning Decision

- Version bump type: later implementation commits follow the core release policy;
  this proposal makes no version change, commit or tag.
- Effective version/date: binding/effect source candidate on 2026-09-11; no release
  created. The copied migration is implemented and rehearsed; complete BT-1
  recovery and migration-interruption proof remain required before cutover.
- Downstream impact: clients retain response shapes but inspect the returned
  decision. HTTP success does not mean an effect occurred. Legacy unbound work
  requires new admission. No single-turn formal scope, untrusted-execution
  admission or provider-selection contract is expanded here.

## Pre-intent owner replacement decision (2026-09-12)

The current BT-1 source candidate adds authenticated effect inspection and explicit
pre-intent claim recovery, as specified in
`docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`. Replacement CAS competes with
the old owner's intent transaction and increments its fence; it does not depend
on detecting process death. A committed intent prevents replacement. Durable
request identity, shared recovery/operator records and retained journal linkage
make repeats auditable and prevent an old request from acquiring another claim.
The new owner uses the same dispatch/receipt/publication authority as approval.
Post-intent uncertainty, legacy unbound runs and model-admission recovery are not
reclassified by this operation. Live local fencing, recovery-crash, corruption and copied-schema proof is recorded
in the active plan; full BT-1 acceptance remains open.

## Model admission decision (2026-09-12)

Run start and effect-to-next-turn advancement will create durable ready admission
with their existing transactional projection. A unique owner claims immutable
run inputs before invoking the provider; the extracted result and original
evidence commitments are retained before atomic proposal publication. Public run
reentry may resume ready or observed admission. Claimed admission without a
result remains explicitly unresolved; ordinary retry cannot replace its owner.
Missing legacy admission is not synthesized from mutable current output.

The extraction artifact remains an extraction observation and is no longer
rewritten after proposal publication. Acceptance is recorded by the admission,
proposal and ledger transaction. Existing evidence field names remain; this
corrects mutable extraction evidence without changing the v1 ledger hash scheme
or extending the single-turn formal claim ceiling. Crash, competing-owner,
rollback and read-only corruption tests are required before claiming enforcement.

## Explicit model-attempt replacement decision (2026-09-12)

Add authenticated current-admission inspection and explicit recovery of the
latest claimed model attempt. Recovery retains its unresolved row and appends a
ready attempt at the next fence, atomically with shared recovery/operator records.
It does not call the provider; normal run reentry claims ready work. Identical
request retries cannot produce another attempt or advance a different turn.
Fenced observation prevents a late old producer from publishing. New evidence
uses attempt-specific directories and no shared latest aliases. Migrate previous
admission rows without changing their artifacts or input/result commitments;
retire the previous table name so mixed old writers fail closed. Provider
execution/cost uncertainty stays explicit; this is not external-call idempotency.

## Retained fixture byte correction (2026-09-12)

The approved, denied and policy-rejected frozen package manifests commit CRLF
ledger/bundle bytes. Git's blanket LF conversion changed six retained files;
their original CRLF representations exactly match every existing commitment.
Restore those bytes and exempt the sealed fixture directory from text conversion.
No manifest, digest, claim, verifier algorithm or acceptance scope changes. This
repairs the historical trust-handoff fixture failure without resealing evidence.

## Legacy-history quarantine clarification (2026-09-12)

Generation-0 runs cannot reenter submission, start or denial continuation. Refuse
before repairing a missing submission event or projecting a historical denial as
new completion. Unbound pending approvals do not expire through ordinary reads or
sweeps; their original decisions and run/event history remain untouched. New
decision attempts require a binding even if the old deadline has passed. Preserve
read-only status inspection and normal independent generation-1 admission. This
does not reconcile old effects, free an occupied namespace, establish target
isolation, or authorize replacing the old run from its mutable model call.

## Profile-selected outward tool transport (2026-09-12)

Live llama.cpp proof exposed unconditional native-tool requests from the outward
planner, rejected by the admitted JSON-wrapper profile before generation. The
planner now explicitly requests `tool_transport_policy=profile`. The existing
provider adapter passes its already resolved `tool_call_mode` into shared request
construction: native profiles retain schemas/choice; JSON-wrapper profiles omit
native request fields and use the prompt schema. Unknown policy/mode fails closed.
Explicit native callers without this policy retain their current behavior and
unsupported-provider refusal. No profile, provider admission, fallback or connector
authorization scope changes. Validation requires both mode-selection regressions
and a real llama.cpp outward approval/write proof.

## Legacy disposition scope correction (2026-09-12)

The original BT-1 migration requirement permits a new proposal **or explicit
quarantine**. The implemented generation/binding quarantine is the selected
disposition, preserving old history and uncertainty. Earlier implementation notes
incorrectly made a new legacy-run reconciliation/replacement workflow mandatory
for this requirement. Correct that scope drift; do not add another executable
entrypoint to close an obligation already met by quarantine. Reconciliation and
replacement of old work remain unsupported, without inferring absent effects or
free physical targets. Copied-store, incompatible-writer, restart and final host
acceptance obligations remain; this correction does not close the BT-1 release gate.
