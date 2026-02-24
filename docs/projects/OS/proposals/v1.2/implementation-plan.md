# v1.2 Implementation Plan (Proposal)

Last updated: 2026-02-24
Status: Draft proposal (non-authoritative)

## Goal
Convert the v1.2 idea dump into enforceable contracts and deterministic runtime behavior with explicit compatibility handling.

## Phase 0: Decision Freeze
1. Resolve items in `open-decisions.md`.
2. Decide whether v1.2 is:
- `kernel_api/v1` tightening, or
- `kernel_api/v2` breaking set.
3. Freeze digest-scope and ordering rules.

Exit criteria:
1. Open decisions are closed.
2. Versioning classification is explicitly documented.

## Phase 1: Additive Contracts First
1. Add `stage-order-v1.json`.
2. Add `replay-bundle.schema.json`.
3. Add additive error codes only.

Exit criteria:
1. Contract schema tests for new artifacts are green.
2. Registry audit remains green.

## Phase 2: Law Wiring and Comparator Tightening
1. Implement strict canonical parity laws in comparator.
2. Implement report-id derivation invariant.
3. Implement registry-lock check (`E_REGISTRY_DIGEST_MISMATCH`).
4. Implement deterministic path selection and mismatch ordering.

Exit criteria:
1. Replay vectors cover pass/fail/multi-mismatch ordering.
2. 100-iteration replay stability remains green.

## Phase 3: Capability Decision Record Integration
1. Implement decision-record emission law (one record per tool attempt).
2. Enforce deny precedence law.
3. Enforce correspondence law between denied/unresolved decision and capability issue.

Exit criteria:
1. Capability deny/skip/unresolved tests pass.
2. API replay/compare tests remain deterministic.

## Phase 4: TurnResult and Schema Integration
1. If replacing decisions shape, migrate `turn-result.schema.json`.
2. If coexistence model, keep old shape and add parallel record location.
3. Update schema contracts and interface tests.

Exit criteria:
1. Schema contracts pass for all API paths.
2. Any migration shims are documented and tested.

## Phase 5: Authority Promotion
1. Promote accepted contracts into `docs/projects/OS/contracts/`.
2. Update `contract-index.md`.
3. Update test-policy and gate policy text as needed.

Exit criteria:
1. All authoritative docs reference final promoted artifacts only.
2. CI gates are green and deterministic.

## Suggested PR Slicing
1. PR1 Decision freeze + proposal approval docs.
2. PR2 Additive contracts + tests.
3. PR3 Comparator/law tightening + vectors.
4. PR4 Capability decision-record wiring.
5. PR5 Turn-result/schema integration.
6. PR6 Authority promotion and cleanup.
