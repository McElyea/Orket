# Sovereign Laws (v1.2)

Last updated: 2026-02-24
Status: Normative for v1.2 execution

## Laws
1. Deny precedence: `E_SIDE_EFFECT_UNDECLARED` -> `E_CAPABILITY_DENIED` -> `E_PERMISSION_DENIED`.
2. Single-emission decision record: one capability decision record per tool attempt.
3. Strict canonical parity: parity is based on canonical UTF-8 bytes or digests of parity surfaces.
4. Float ban: floats, NaN, Infinity, and negative zero are forbidden on canonical surfaces.
5. Safe boundary: `TurnResult.events`, `KernelIssue.message`, and replay mismatch diagnostics are parity-excluded.
6. Issue detail parity: all keys in `KernelIssue.details` are parity-relevant.
7. Registry lock: registry digest mismatch fails closed with `E_REGISTRY_DIGEST_MISMATCH`.
8. Deterministic path selection: turn result paths are Unicode codepoint sorted; comparator reads first readable path.
9. Report ordering: mismatches sort by `(turn_id, stage_name, ordinal, surface, path)`.
10. Surface list: parity includes digest/manifests, transition digests, decision-record bytes, and issue bytes (without message).
11. Correspondence: denied/unresolved decisions require a capability-stage issue with matching deny code and ordinal location.
12. Report identity: `report_id` hashes canonical report bytes with `report_id = null` and `mismatches[*].diagnostic = null`.
13. IssueKey multiplicity: compare IssueKey buckets as multimaps with cardinality checks.
14. Issue normalization scope: remove only `message` for issue parity normalization.
15. Nullification-over-omission: excluded hash fields are nullified, not removed.
