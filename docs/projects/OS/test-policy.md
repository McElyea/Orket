# OS Test Policy (Normative)

## Purpose
This policy defines the required test gates for OS v1 pull requests.

## Required test categories
1. Contract shape tests (schemas)
2. Determinism tests (ordering + canonicalization)
3. LSI behavior tests (shadowing, orphan detection, pruning)
4. Promotion atomicity tests (no partial committed state)
5. Capability enforcement tests (deny-by-default when enabled)
6. Replay/equivalence tests (structural parity)
7. Lifecycle ordering tests (out-of-order promotion rejection)
8. Empty-stage/no-op and deletion-only promotion tests
9. Error-code registry conformance tests
10. Digest and tombstone reference vector tests

## Non-negotiable PR gates
A PR MUST fail if any of the following occurs:

### Contract drift
- Any Normative Schema changes without version policy compliance
- Any DTO missing required version fields
- Any additionalProperties introduced in schemas without explicit allowance
- Any emitted `KernelIssue.code` not present in `contracts/error-codes-v1.json`

### Determinism regression
- Issues/events ordering becomes nondeterministic
- Canonicalization output changes without a major bump
- Structural digest rules change without a major bump

### Fortress violation
- Any write occurs under committed/ during execute_turn
- Any partial promotion leaves committed/ in intermediate state

### Fail-closed violations
- Missing diff context (CI) silently passes where policy says fail
- Missing link targets (LSI) do not fail with pointer-rooted error

## Fixture policy (Replay / Equivalence)
- Fixtures MUST be canonical JSON
- Fixtures MUST include expected structural digests (computed from canonical bytes)
- Replay tests MUST run >= 100 iterations without divergence (or deterministic equivalent proof)

## Required test mapping
All normative OS laws MUST map to at least one scenario test in:
`tests/kernel/v1/`

Required scenario coverage includes:
- out-of-order promotion -> `E_PROMOTION_OUT_OF_ORDER`
- duplicate promotion -> `E_PROMOTION_ALREADY_APPLIED`
- orphan target -> `E_LSI_ORPHAN_TARGET`
- no-op promotion on missing/empty staging (when no deletes)
- deletion-only promotion on missing/empty staging (when explicit deletes exist)
- tombstone payload validation and stem mismatch failures
- digest vectors match expected SHA-256 values across at least one independent implementation
- link validation read-only behavior (no staged/committed index mutation during validate)
