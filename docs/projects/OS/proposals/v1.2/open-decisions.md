# v1.2 Locked Decisions

Last updated: 2026-02-24
Status: Locked

## D1. Version Classification
Decision:
1. `kernel_api/v1` tightening.

Rule:
1. No silent semantic swaps.
2. If existing field meaning changes, introduce a new field or parallel schema.
3. Keep prior meaning stable until removal in a later major.

## D2. Capability Decision Surface
Decision:
1. `CapabilityDecisionRecord` coexists with current capability artifact for one minor cycle.
2. It becomes the sole parity surface in next major or scheduled deprecation window.

Operational rule:
1. During migration, `TurnResult` may carry both.
2. Once both are present, comparator parity uses DecisionRecord.

## D3. `turn_result_digest` Scope
Decision:
1. Contract-only digest scope.

Exclusions:
1. `TurnResult.events`
2. `KernelIssue.message`
3. Any declared narrative/diagnostic-only surfaces.

## D4. Issue Comparison Ordering
Decision:
1. Deterministic IssueKey ordering (not array order).

Order key:
1. `stage_index`
2. `location`
3. `code`
4. `details_digest`

## D5. Registry Digest Input Rule
Decision:
1. Digest full wrapper canonical JSON:
- `{ "contract_version": "...", "codes": { ... } }`

## D6. `report_id` Diagnostic Handling
Decision:
1. Nullify, do not remove:
- `report_id = null`
- `mismatches[*].diagnostic = null`

## D7. IssueKey Multiplicity + Normalization Scope
Decision:
1. Use multimap buckets (`IssueKey -> list`) with cardinality checks.
2. Compare normalized items sorted by digest inside each bucket.

Normalization:
1. Remove only `message`.
2. Keep all parity fields (`contract_version`, `level`, `stage`, `code`, `location`, `details`).

## D8. Nullification-over-Omission Consistency
Decision:
1. For any normalized surface used for hashing, prefer nullification over key removal.

Scope:
1. TurnResult digest projection.
2. Replay report ID input projection.

## D9. Coexistence Field Naming
Decision:
1. Keep existing `capabilities.decisions` semantics unchanged for v1 compatibility.
2. Add `capabilities.decisions_v1_2_1` as the DecisionRecord parity surface during coexistence.
3. Consider rename to `capabilities.decisions` only in the next major after deprecation window.

Why:
1. Avoids semantic swap on an existing field in `kernel_api/v1`.
2. Keeps migration explicit and testable.
