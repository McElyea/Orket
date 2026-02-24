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
11. Replay comparator law tests (IssueKey multimap, registry lock, report-id invariants)

## Non-negotiable PR gates
A PR MUST fail if any of the following occurs:

### Contract drift
- Any Normative Schema changes without version policy compliance
- Any DTO missing required version fields
- Any additionalProperties introduced in schemas without explicit allowance
- Any emitted `KernelIssue.code` not present in `contracts/error-codes-v1.json`
- Any emitted `[CODE:X]` token not present in `contracts/error-codes-v1.json`
- Registry duplicates or unstable ordering in `contracts/error-codes-v1.json`
- Replay comparator report-id derivation omits excluded keys instead of nullifying them

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
- Digest vectors MUST be committed under `tests/kernel/v1/vectors/digest-v1.json`
- CI MUST NOT overwrite vector files; CI may only compare regenerated output to committed vectors

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
- cross-language parity check (Python and TypeScript) over committed digest vectors
- registry digest mismatch -> `E_REGISTRY_DIGEST_MISMATCH`
- digest/version mismatch across replay digests -> `E_REPLAY_VERSION_MISMATCH`
- issue-key multiplicity mismatch is detected even when IssueKey fields match
- issue `message` drift does not fail replay parity
- replay report mismatch ordering is deterministic by `(turn_id, stage_index, ordinal, surface, path)`
- report-id hash nullifies `report_id` and `mismatches[*].diagnostic`

Packaging and gate hygiene:
- `tests/__init__.py`, `tests/kernel/__init__.py`, and `tests/kernel/v1/__init__.py` must exist for sovereign gate packaging stability.

Conformance commands required by gate policy:
- `python -m pytest -q tests/kernel/v1`
- `npm test --prefix conformance/ts`
