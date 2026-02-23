# OS Implementation Plan

Last updated: 2026-02-23
Status: Active
Owner: Orket Core

## Purpose
This plan executes the sealed kernel requirements in `docs/projects/OS/KERNEL_REQUIREMENTS_EXIT.md` and establishes the gate to move OS work from Kernel Requirements to Capability and Replay hardening.

## Requirement Health
The core requirements are strong enough to execute.

Confirmed strengths:
1. Normative contract index and schema set are present.
2. Lifecycle, tombstone, visibility, and digest rules are documented.
3. Error-code registry exists and is linked.
4. Kernel exit criteria are explicit.

## External Inputs Needed From Owner
The following inputs are still required because they are product decisions, not implementation guesses:
1. Sovereign test home selection:
Choose one canonical path for kernel-law tests and CI gate.
Options:
- `tests/kernel/v1/` (recommended, aligns with policy/docs)
- `tests/lsi/` (current active law test location)
2. Deletion representation in committed state:
Choose one behavior for deleted stems:
- hard delete committed index record
- tombstone-marked committed index record
3. Created-set identity mapping contract:
Confirm whether staged creation identity is always `body.dto_type + body.id` for all DTO families, or provide per-dto mapping rules.
4. Determinism numeric failure vocabulary:
`docs/projects/OS/State/digest-spec-v1.md` references number failures; confirm canonical code names to add to `docs/projects/OS/contracts/error-codes-v1.json` (e.g., `E_NON_INTEGER_NUMBER`, `E_INTEGER_OUT_OF_RANGE`).
5. Cross-language digest conformance runtime:
Confirm second runtime for vector parity checks (Rust preferred, TS acceptable) for CI-grade multi-implementation validation.

## Implementation Scope
This plan covers Cards 001-005 closure and the kernel exit gate.

Out of scope for this plan:
1. Capability policy language expansion.
2. Replay UX/reporting enhancements beyond contract minimum.
3. Distributed/mesh runtime.

## Work Plan

### Phase A: Contract and Packaging Alignment
Deliverables:
1. Add any missing package markers required by gate policy:
- `tests/kernel/__init__.py`
- `tests/kernel/v1/__init__.py`
2. Normalize references so one sovereign test home is used everywhere.
3. Ensure all runtime-emitted codes are registry-backed or aliased during migration.

Exit criteria:
1. Test-policy path and actual test home match.
2. Packaging hygiene rules in `KERNEL_REQUIREMENTS_EXIT.md` are true in repo.

### Phase B: Promotion Ledger and NO-OP Law
Deliverables:
1. Implement ledger load/save with atomic write at `committed/index/run_ledger.json`.
2. Enforce ordering preflight:
- `E_PROMOTION_ALREADY_APPLIED`
- `E_PROMOTION_OUT_OF_ORDER`
3. Implement NO-OP classification after preflight with `I_NOOP_PROMOTION` and zero committed mutations.
4. Ensure promotion failures and ledger/tombstone failures emit stage `promotion`.

Exit criteria:
1. `test_law_2_process_model_sequential_promotion_enforced` passes.
2. No-op behavior tests pass with ledger advancement.

### Phase C: Tombstone Runtime Enforcement
Deliverables:
1. Parse and validate `<stem>.tombstone.json` payloads using `contracts/tombstone-v1.schema.json`.
2. Enforce filename-derived stem match.
3. Emit:
- `E_TOMBSTONE_INVALID`
- `E_TOMBSTONE_STEM_MISMATCH`
4. Apply delete behavior in promotion:
- include tombstoned stems in promoted set
- prune ref sources for deleted stems
- skip ref injection for tombstoned stems

Exit criteria:
1. Tombstone vectors pass.
2. Deletion/no-op law tests pass.

### Phase D: LSI Visibility Wall (No Self-Authorization)
Deliverables:
1. Rework orphan validation visibility to:
`visible = committed_index OR staged_created_set`.
2. Build staged-created-set only from staged creations (bodies/manifests), not links.
3. Keep `validate()` read-only (no staged/committed writes).
4. Emit `E_LSI_ORPHAN_TARGET` at pointer-rooted link locations under stage `lsi`.

Exit criteria:
1. `test_link_integrity_orphan_fails_with_pointer` passes.
2. No missing-target resolution via staging refs.

### Phase E: Validator Boundary Wiring
Deliverables:
1. Replace placeholder `orket/kernel/v1/validator.py` with thin real handlers:
- `start_run_v1`
- `execute_turn_v1`
- `finish_run_v1`
2. Handlers perform base-shape checks and route through kernel runtime laws.
3. I/O payloads conform to `contracts/kernel-api-v1.schema.json` and `contracts/turn-result.schema.json`.

Exit criteria:
1. JSON round-trip contract tests pass (valid request -> valid response).
2. Stage attribution matches closure spec.

### Phase F: Mechanical Guardrails and CI Gate
Deliverables:
1. Add registry enforcement test:
fail if emitted `KernelIssue.code` not in `contracts/error-codes-v1.json`.
2. Add digest vector tests with `State/digest-spec-v1.md` canonicalization and integer-only constraints.
3. Add tombstone wire-format vector tests.
4. Set/confirm sovereign gate command for CI.
5. Add `scripts/audit_registry.py` to enforce registry/spec sync.
6. Add `scripts/gen_digest_vectors.py` for maintainer-only vector generation.
7. Add TypeScript parity gate under `conformance/ts`.

Exit criteria:
1. Kernel gate command is deterministic and green.
2. Kernel exit condition in `KERNEL_REQUIREMENTS_EXIT.md` is fully satisfied.
3. CI consumes committed vectors only (no write-back).

## Acceptance Gate (Kernel Requirements Exit)
Kernel Requirements phase is closed only when all are true:
1. Spec-002 law suite green for ledger ordering, no-op classification, and orphan wall.
2. Tombstone semantics enforced in runtime and covered by vectors.
3. Registry guardrail test is active and green.
4. `validator.py` boundary is truthful and schema-safe.

## Execution Order
1. Phase A
2. Phase B
3. Phase C
4. Phase D
5. Phase E
6. Phase F

## Risks and Controls
1. Risk: Stage/code drift during migration.
Control: Registry enforcement test and stage assertions in scenario tests.
2. Risk: Path-policy drift between docs and tests.
Control: Single sovereign gate path and roadmap linkage.
3. Risk: Hidden deletion edge cases.
Control: Tombstone positive/negative vectors and deletion-only promotion tests.

## Immediate Next Task
Start Phase A and Phase B in one slice:
1. finalize sovereign test home choice,
2. land ledger preflight + NO-OP promotion,
3. rerun kernel law suite to prove the first failing law flips.
