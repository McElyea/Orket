# OS Implementation Plan

Last updated: 2026-02-23
Status: Active
Owner: Orket Core

## Purpose
This plan executes the sealed kernel requirements in `docs/projects/OS/KERNEL_REQUIREMENTS_EXIT.md` and establishes the gate to move OS work from Kernel Requirements to Capability and Replay hardening.

## Strategic Impact
Tombstones plus typed identity (`{dto_type}:{id}`) make the kernel a deterministic conflict-resolution engine instead of a file watcher. This is the foundation for local-first convergence, replay parity, and stable cross-runtime validation.

## Requirement Health
The core requirements are strong enough to execute.

Confirmed strengths:
1. Normative contract index and schema set are present.
2. Lifecycle, tombstone, visibility, and digest rules are documented.
3. Error-code registry exists and is linked.
4. Kernel exit criteria are explicit.

## Locked Decisions (Authoritative)
1. Canonical kernel-law test home is `tests/kernel/v1/`.
2. Registry authority is `docs/projects/OS/contracts/error-codes-v1.json`; all emitted issue and log `[CODE:X]` tokens must resolve to this list.
3. Identity basis is typed identity: `{dto_type}:{id}` derived from staged body payloads.
4. Tombstones are required deletion evidence; visibility subtraction is identity-based (not stem-only).
5. Cross-language digest parity runtime is TypeScript under `conformance/ts`.
6. Digest failures must use specific `E_DIGEST_*` codes, not umbrella promotion failures.

## PR-Ready Integration Checklist
1. Registry lock:
- no duplicate codes in registry
- no dynamic code variants/suffixes
- deterministic registry ordering
2. LSI identity wall:
- derive visible identities from staged bodies (`body.dto_type`, `body.id`)
- validate against committed visibility plus staged creations only
3. TypeScript parity harness:
- committed vector consumption only
- CI may regenerate and diff but must not overwrite vectors
4. Canonicalization and digest law:
- one trailing LF
- no CR and no padding drift
- UTF-8 validity gate before canonicalization and hashing
- integer-only numeric policy for v1

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
5. Ensure tombstone payload identity (`dto_type`, `id`) is used for visibility subtraction.

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
1. Add registry enforcement test (`tests/kernel/v1/test_registry.py`):
fail if emitted `KernelIssue.code` not in `contracts/error-codes-v1.json`.
2. Add digest vector tests with `State/digest-spec-v1.md` canonicalization and integer-only constraints.
3. Add tombstone wire-format vector tests.
4. Set/confirm sovereign gate command for CI.
5. Add `scripts/audit_registry.py` to enforce registry/spec sync.
6. Add `scripts/gen_digest_vectors.py` for maintainer-only vector generation.
7. Add TypeScript parity gate under `conformance/ts`.
8. Add CI diff-only vector verification:
`python scripts/gen_digest_vectors.py --out /tmp/digest-v1.json`
`diff -u tests/kernel/v1/vectors/digest-v1.json /tmp/digest-v1.json`

Exit criteria:
1. Kernel gate command is deterministic and green.
2. Kernel exit condition in `KERNEL_REQUIREMENTS_EXIT.md` is fully satisfied.
3. CI consumes committed vectors only (no write-back).
4. Registry audit is green (`scripts/audit_registry.py`).

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

## Gitea Validation Experiments
1. Truth triangle gate (`audit_registry.py` + kernel pytest + TS parity):
open a PR with an intentional fake code in registry only; verify audit fails deterministically.
2. Golden-vector immutability:
mutate a committed vector value and confirm parity fails; then run regen+diff and confirm CI does not overwrite vector files.
3. One-law-per-PR ergonomics:
run two small PRs (registry-only and base-shape-only) to validate review clarity and deterministic check attachment.

## Immediate Next Task
Start Phase A and Phase B in one slice:
1. land ledger preflight + NO-OP promotion,
2. rerun kernel law suite to prove the first failing law flips,
3. land registry and digest guardrails in parallel (`test_registry.py`, vectors, TS parity harness).

Immediate parallel hardening:
1. land `test_registry.py` as a mechanical guardrail,
2. land `gen_digest_vectors.py` + committed vectors,
3. land `conformance/ts` parity runner wired to committed vectors.
