# v1.2 Sovereign Laws (Proposal)

Last updated: 2026-02-24
Status: Draft proposal (non-authoritative)

These laws are proposed as machine laws for v1.2 normalization.

## 1. Deny Precedence Law
If multiple deny conditions apply, emitted `deny_code` precedence is:
1. `E_SIDE_EFFECT_UNDECLARED`
2. else `E_CAPABILITY_DENIED`
3. else `E_PERMISSION_DENIED`

## 2. Single-Emission Decision Record Law
Every tool attempt emits exactly one `CapabilityDecisionRecord` with outcome in:
1. `allowed`
2. `denied`
3. `skipped`
4. `unresolved`

## 3. Strict Canonical Parity Law
Replay equivalence is defined by canonical UTF-8 bytes (or their digests) of canonical parity surfaces.

## 4. Float Ban Law
Floats, NaN, Infinity, and negative zero are forbidden on canonical surfaces.
1. Violation emits `E_CANONICALIZATION_ERROR`.
2. Fractional values must be string-encoded or fixed-point integers.

## 5. Safe Boundary Law
The following are diagnostic-only and ignored for parity:
1. `TurnResult.events`
2. `KernelIssue.message`
3. `ReplayReport.mismatches[].diagnostic`

## 6. Issue Detail Parity Law
For v1.2, all keys under `KernelIssue.details` are parity-relevant.

## 7. Registry Lock Law
If local error-registry digest differs from bundle `registry_digest`, replay fails closed with:
1. `E_REGISTRY_DIGEST_MISMATCH`

## 8. Deterministic Path Selection Law
`turn_results[*].paths` are sorted lexicographically by Unicode codepoint.
1. Comparator loads first readable path.
2. If none are readable: `ERROR` + `E_REPLAY_INPUT_MISSING`.

## 9. Report Ordering Law
`ReplayReport.mismatches[]` sort order:
1. `turn_id`
2. `stage_name` (using stage-order contract)
3. `ordinal`
4. `surface`
5. `path`

## 10. Surface List Law
Parity-included surfaces:
1. Registry and manifest digests
2. Transition digests
3. Canonical decision-record bytes
4. Canonical issue bytes (message excluded)

Parity-excluded surfaces:
1. `TurnResult.events`
2. `KernelIssue.message`
3. `ReplayReport.mismatches[].diagnostic`

## 11. Correspondence Law
For each decision with outcome in `{denied, unresolved}`, a matching capability-stage issue must exist:
1. Same `(run_id, turn_id)`
2. `issue.stage == "capability"`
3. `issue.code == decision.deny_code`
4. `issue.location` points to decision ordinal (e.g. `/capabilities/decisions/<ordinal>`)

## 12. Report Identity Law
`report_id` is SHA-256 of canonical report bytes with:
1. `report_id = null`
2. `mismatches[*].diagnostic = null`

## 13. IssueKey Multiplicity Law
Issue comparison uses multimap buckets (`IssueKey -> list`) rather than set semantics.
1. Comparator must compare bucket cardinality.
2. Within each bucket, normalized issues are sorted by digest before comparison.

## 14. Issue Normalization Scope Law
Issue normalization for parity removes only `message`.
1. `contract_version`, `level`, `stage`, `code`, `location`, and `details` remain parity-relevant.

## 15. Nullification-over-Omission Law
For any canonical surface hashed for identity/digest:
1. Use nullification for excluded fields, not key removal.
2. This applies to `turn_result_digest` projections and report-id projections.
