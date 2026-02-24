# OS Implementation Plan

Last updated: 2026-02-24
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
Completed in current execution slice:
1. Phase B ledger/order/no-op law behavior is implemented and green in kernel-law tests.
2. Baseline Phase F guardrails are landed:
- `test_registry.py`
- `test_digest_vectors.py`
- `scripts/audit_registry.py`
- `scripts/gen_digest_vectors.py`
- `conformance/ts` parity harness
3. `.gitea/workflows/quality.yml` enforces:
- registry audit
- kernel sovereign test gate (`tests/kernel/v1`)
- TS digest parity
- digest vector regenerate+diff fail-closed check
4. Legacy Spec-002 law tests are physically consolidated into `tests/kernel/v1`; `tests/lsi` mirror files are removed.
5. `scripts/audit_registry.py` is now strict-mode fail-closed for registry extras, with complete OS doc coverage enforced.
6. Deprecated `jsonschema.RefResolver` is replaced by `referencing.Registry` wiring in kernel schema-contract tests.
7. Validator boundary now includes thin capability/replay handlers:
- `resolve_capability_v1`
- `authorize_tool_call_v1`
- `replay_run_v1`
- `compare_runs_v1`
8. Kernel-v1 tests now enforce capability/replay closure codes and schema conformance for new response shapes.
9. Capability allow/deny decisions now include deterministic policy source/version metadata in decision evidence.
10. Replay parity now compares contract-scoped surfaces (turn digests, stage outcomes, issue/event codes, schema/contract versions), not whole-object equality.
11. Multi-turn replay vectors are committed at `tests/kernel/v1/vectors/replay-v1.json` and enforced by `tests/kernel/v1/test_replay_vectors.py`.
12. Capability metadata is now wired to concrete runtime artifact `model/core/contracts/kernel_capability_policy_v1.json` (with context override support), and capability resolution can derive permissions from role/task policy mapping.
13. Replay vectors now include deterministic mismatch-field assertions (`details.mismatch_fields`) for stage/schema/issue-pointer drift.
14. Policy artifact contract test is active at `tests/kernel/v1/test_capability_policy_contract.py`.
15. Explicit kernel API module surface is now available at `orket/kernel/v1/api.py` with stable exported handlers for run lifecycle, capability, and replay.
16. Policy artifact schema is now normative at `docs/projects/OS/contracts/kernel-capability-policy-v1.schema.json` and enforced by kernel-v1 tests.
17. Non-test adoption of the explicit API surface is active via `orket/application/services/kernel_v1_gateway.py`.
18. Replay vectors now include event-code multiset drift and mixed turn-count edge cases.
19. Orchestration integration path is active: `orket/orchestration/engine.py` now routes kernel v1 calls through `KernelV1Gateway`.
20. Replay vectors include mixed issue-order normalization proof (`pass-mixed-issue-order-normalized`).
21. Application workflow path supports minimal kernel lifecycle execution through `KernelV1Gateway.run_lifecycle(...)`.
22. Orchestration-facing replay/compare boundary coverage is active in `tests/application/test_engine_refactor.py`.
23. Production API path adoption is active at `POST /v1/kernel/lifecycle` (`orket/interfaces/api.py`) and routes to `OrchestrationEngine.kernel_run_lifecycle(...)`.
24. Replay vectors include combined mismatch-case asserting deterministic `mismatch_fields` ordering.
25. Orchestration-facing replay compare API boundary is active at `POST /v1/kernel/compare` and routes to `OrchestrationEngine.kernel_compare_runs(...)`.
26. Orchestration-facing replay-run API boundary is active at `POST /v1/kernel/replay` and covered for `E_REPLAY_INPUT_MISSING`/`E_REPLAY_VERSION_MISMATCH` propagation.
27. Replay vectors now include additional pass-normalization case for randomized issue/event input order.
28. API-boundary replay compare assertions are active (real engine path) for pointer-drift failure and mixed-order pass normalization in `tests/interfaces/test_api_kernel_lifecycle.py`.
29. `/v1/kernel/compare` response schema contract is enforced against `replay-report.schema.json` at API boundary.
30. Realistic artifact-derived API compare fixture is active at `tests/interfaces/fixtures/kernel_compare_realistic_fixture.json`.
31. `/v1/kernel/replay` success path is covered with full descriptor payload (profiles + refs) and schema validation at API boundary.
32. API-boundary compare parity version drift is covered with deterministic mismatch-field assertion (`["contract_version"]`).

Next task:
1. Add replay comparator tests for staged pointer/code ordering guarantees under mixed issue sets.
2. Add kernel compare vector and API test that combine pointer drift + stage drift in one case and assert deterministic mismatch-field ordering.
3. Add API-level schema contract test for `/v1/kernel/replay` responses (replay-report schema) under both PASS and FAIL payloads.
