# v1.2 Migration Matrix

Last updated: 2026-02-24
Status: Active (authoritative for v1.2 execution)

## Mapping

| Current Artifact | Proposed Artifact | PR | Change Type | Break Risk | Required Tests/Gates | Notes |
|---|---|---|---|---|---|---|
| none | `contracts/stage-order-v1.json` | PR-01 | Additive | Low | schema contract checks, comparator ordering tests | Authoritative stage spine for deterministic ordering. |
| `contracts/error-codes-v1.json` | wrapper-form registry instance | PR-01 | Tighten + migration compatibility | Medium | `scripts/audit_registry.py`, `tests/kernel/v1/test_registry.py` | Digest input uses full wrapper canonical JSON. |
| `contracts/error-codes-v1.schema.json` | coexistence-compatible registry schema | PR-01 | Tighten | Medium | schema contract checks | Migration window must avoid silent semantic swaps. |
| none | `contracts/sovereign-laws.md` | PR-01 | Additive | Low | law-reference checks | Locked laws only; no speculative/unlocked law text. |
| `contracts/capability-decision.schema.json` | `contracts/capability-decision-record.schema.json` (new) | PR-02 | Add in parallel | Medium | validator schema contracts, capability scenario tests | Locked: coexist one minor cycle, then replace. |
| `contracts/turn-result.schema.json` | add `capabilities.decisions_v1_2_1` coexistence field | PR-02 | Additive | Medium | turn-result schema tests, fixture validation tests | Existing `capabilities.decisions` meaning remains stable in v1. |
| none | `contracts/replay-bundle.schema.json` | PR-03 | Additive | Low/Medium | bundle validation tests, comparator input tests | New replay input manifest contract. |
| `contracts/replay-report.schema.json` | tightened replay report schema | PR-03 | Tighten existing (additive where possible) | Medium | schema contracts, replay vectors, API compare tests | Include nullable digest behavior for schema/ERROR states. |
| implicit comparator behavior | explicit canonical comparator implementation | PR-05 | Behavior tightening | Medium | replay comparator tests, replay stability tests, API boundary tests | Locked: IssueKey order + multiplicity + nullification invariant. |
| runtime capability emission | DecisionRecord + correspondence law emission | PR-06 | Behavior tightening | Medium | capability gate tests, validator tests | One record per attempt and issue correspondence required. |
| turn_result digest implementation | contract-only digest surface | PR-07 | Behavior tightening | Medium | replay vectors + digest sensitivity tests | Locked: diagnostics excluded from digest input. |

## Risk Classification Guidance
1. `Low`: additive contract/documentation with no interpretation changes.
2. `Medium`: behavior tightening or schema constraints likely to expose drift.
3. `High`: direct schema or semantic breaks to existing consumers (not planned in this sequence).

## Rollout Strategy
1. Land anchors first (`PR-01`), then parity surface coexistence (`PR-02`, `PR-03`), then byte-law docs (`PR-04`).
2. Implement deterministic gate behavior in comparator (`PR-05`).
3. Wire runtime emissions and digest scope (`PR-06`, `PR-07`).
4. Promote accepted artifacts into authoritative index and policy docs.
