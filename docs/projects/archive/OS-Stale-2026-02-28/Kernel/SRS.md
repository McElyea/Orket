Here is the complete Orket Kernel v1 Requirements Pack — integrated, consistent, and aligned with everything we locked: LSI, pruning, atomic promotion, canonical identity, deny-by-default capability, and deterministic replay.

This is publication-ready and Codex-proof.

1️⃣ docs/kernel/kernel-api-v1.md
Orket Kernel API v1

Status: Normative
Version: kernel_api/v1
Identity: Deterministic Local-First Substrate

1. Purpose

The Orket Kernel v1 defines the minimal, stable substrate for deterministic agentic execution.

It governs:

Run lifecycle control

Deterministic event logging

Contract-safe state transitions

Capability and permission enforcement

State-backed link integrity

Replay and structural equivalence

Everything else is a subsystem or plugin.

2. Kernel API Surface
2.1 Run Control
start_run(request) -> run_handle

Creates a run envelope containing:

run_id

workflow identity

policy profile reference

model profile reference

visibility mode

MUST NOT modify committed state.

execute_turn(run_handle, turn_input) -> TurnResult

Executes exactly one deterministic turn.

Properties:

Reads from committed/

Writes only to staging/

Applies fixed stage pipeline

Emits deterministic events

Produces TurnResult (see Spec-003)

Fortress Invariant:
execute_turn MUST NOT modify committed/ under any condition.

finish_run(run_handle, outcome) -> run_summary

If outcome is PASS and commit signal is present:

Triggers atomic promotion of staging → committed

If FAIL:

Staging MUST be discarded (unless policy retains evidence)

2.2 Event and Trace
emit_event(event)

Single-line

Deterministic

Pipe-delimited

Machine-parseable

Not digested

write_trace_artifacts(run_handle, trace_bundle)

Writes canonical JSON artifacts

Includes schema + version metadata

Deterministic ordering

2.3 State and Integrity
validate_triplet(triplet)

Applies fixed stage order:

base_shape
→ dto_links
→ relationship_vocabulary
→ policy
→ determinism

Fail-closed. Unknown state = failure.

validate_links_against_index(triplet, sovereign_index)

Uses Local Sovereign Index (Spec-002).

Visibility order:

Self → Staging → Committed

Missing reference:

FAIL: E_LSI_ORPHAN_REFERENCE
2.4 Capability and Permissions
authorize_tool_call(context, tool_request)

If capability module enabled:

Deny-by-default

Any undeclared action = FAIL (E_CAPABILITY_DENIED)

Every decision produces audit record

If capability module disabled:

Emit I_CAPABILITY_SKIPPED

resolve_capability(role, task)

Produces deterministic capability plan.

2.5 Replay and Equivalence
replay_run(run_descriptor)

Replays deterministic turn sequence using local artifacts.

Must produce identical structural digests and issue ordering.

compare_runs(run_a, run_b)

Structural equivalence only.

Ignores non-pinned metadata (e.g., local filesystem paths).

3. Kernel Invariants

Fixed 5-stage pipeline

Fail-closed state evolution

Deterministic sorting of lists and issues

No partial promotion

Explicit version fields required

Plugin behavior allowlisted

Run/Turn ordering strictly sequential

2️⃣ docs/kernel/kernel-v1-law.md
Orket Kernel v1 Law

Status: Constitutional / Non-Negotiable

Law 1 — The Fortress Invariant

execute_turn is:

Read: committed/
Write: staging/

It MUST NOT modify committed state.

Law 2 — Turn Atomicity

A Turn is the smallest state mutation.

Turn IDs must be unique within a run.

Turns are strictly sequential.

Promotion of turn-N requires turn-(N-1) committed.

Law 3 — Canonical vs Narrative Boundary

Two streams:

State Stream

Canonical JSON

Structural Digest

Persisted

Narrative Stream

Deterministic string events

Not digested

Logs are never digested.

Law 4 — Identity Physics
StructuralDigest = SHA256(UTF8(json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)))

Computed over raw UTF-8 bytes.

Law 5 — Immutable Record Shapes

Triplet Record:

[stem, body_digest, links_digest, manifest_digest, updated_at_turn, lsi_version]

Ref Source Record:

[stem, location, relationship, artifact_digest]

sources[] sorted by:

(stem, location, relationship)
Law 6 — Deletion as Staged Mutation (Option A)

Deletion is explicit.

stage_deletions(stems)

Promotion prunes refs for deleted stems

Content-addressed objects are NOT removed

Law 7 — Stable Code Registry

Errors:

E_LSI_ORPHAN_REFERENCE

E_LSI_PROMOTION_FAILED

E_LSI_CORRUPT_RECORD

E_CAPABILITY_DENIED

Information:

I_REF_MULTISOURCE

I_PROMOTION_PASS

I_CAPABILITY_SKIPPED

Law 8 — Capability Jail

If capability module active:

Any undeclared action = FAIL

Every decision logged

3️⃣ docs/kernel/spec-002-local-sovereign-index-v1.md
Spec-002: Local Sovereign Index (LSI) v1

Status: Normative

1. Purpose

LSI provides:

Link integrity

Deterministic replay

Batch visibility

Atomic promotion

Local-only. No network dependency.

2. Canonical Identity

Canonical form:

UTF-8

Sorted keys

No whitespace

Structural Digest:

64-char hex SHA256 over canonical bytes.

3. Disk Layout
<ORKET_HOME>/
  index/
    committed/
      objects/
      triplets/
      refs/by_id/
    staging/<run>/<turn>/
4. Visibility

Lookup order:

1. Self
2. Staging
3. Committed

Staging shadows committed.

5. Pruning Law (Stem-Scoped)

During promotion:

Remove all refs where source.stem == promoted_stem

Insert new refs from triplet

Do NOT remove refs for other stems

Collisions allowed

6. Collision Law

If len(sources) > 1:

Emit I_REF_MULTISOURCE

Do NOT fail

7. Atomic Promotion

Promotion must:

Build new committed tree

Write committed.__new

os.replace(committed.__new, committed)

No partial states permitted.

8. Determinism

All arrays sorted before write.

Failure ordering sorted by:

(stage, pointer, code)
4️⃣ docs/kernel/spec-003-turn-result-and-issues-v1.md
Spec-003: TurnResult & Issue Contract v1

Status: Normative

KernelIssue

Fields:

level: FAIL | INFO
stage: base_shape | dto_links | rel_vocab | policy | determinism
code: stable error code
location: RFC6901 pointer
message: deterministic string
details: canonical JSON

Issues sorted deterministically.

TurnResult
contract_version
run_id
turn_id
outcome: PASS | FAIL
stage
issues[]
transition_evidence
events[]

Events:

Single-line

Pipe-delimited

Deterministic

5️⃣ docs/kernel/error-codes-v1.md
Kernel Error Codes v1

Status: Normative Registry

Fail Codes
Code	Meaning
E_LSI_ORPHAN_REFERENCE	Missing reference
E_LSI_PROMOTION_FAILED	Atomic promotion failure
E_LSI_CORRUPT_RECORD	Invalid LSI record
E_CAPABILITY_DENIED	Unauthorized action
Info Codes
Code	Meaning
I_REF_MULTISOURCE	Multiple stems reference same ID
I_PROMOTION_PASS	Successful atomic promotion
I_CAPABILITY_SKIPPED	Capability module disabled
Registry Rule

Codes cannot change meaning within v1.

New codes require minor version bump.

Renaming requires major version bump.

🔒 Kernel v1 Is Now Requirements-Complete

This pack defines:

API surface

Machine laws

LSI physics

DTO shapes

Code registry

There are no remaining ambiguous areas.