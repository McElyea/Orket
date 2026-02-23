# KERNEL_REQUIREMENTS_EXIT.md

Sovereign Kernel - Normative Closure Specification (v1)

This document defines the sealed, mechanically enforceable requirements for the Orket Kernel. Once implemented and the sovereign test suite is green, the Kernel Requirements phase is closed.

Strategic impact:
Tombstones plus typed identity (`{dto_type}:{id}`) convert kernel behavior from file watching into deterministic conflict resolution. Deletion is preserved as evidence so local-first convergence remains stable.

## 1. State Sovereignty (Ledger Law)

Path: `committed/index/run_ledger.json`

Purpose: The ledger is the single source of truth for turn ordering.

1.1 Creation:
If missing, the ledger MUST be treated as:
`{"last_promoted_turn_id": "turn-0000"}`.

1.2 Atomic Persistence:
Ledger writes MUST use atomic replace (write temp -> `os.replace`).
Partial writes MUST fail closed.

1.3 Ordering Enforcement:
Promotion MUST fail if:
- `turn_id <= last_promoted_turn_id` -> `E_PROMOTION_ALREADY_APPLIED`
- `turn_id != last_promoted_turn_id + 1` -> `E_PROMOTION_OUT_OF_ORDER`

1.4 Turn ID Normalization:
Turn IDs MUST follow the format `turn-` + 4 decimal digits (e.g., `turn-0001`).
Ordering MUST be numeric, not lexical.

## 2. Turn Classification (NO-OP Law)

A turn is a NO-OP if the staging root is missing OR contains zero promoted stems (after considering tombstones).

2.1 Behavior:
Advance ledger to `turn_id`, emit `I_NOOP_PROMOTION`, and perform zero filesystem mutations to committed state.

2.2 Precedence:
NO-OP classification occurs after ledger ordering validation.
You cannot NO-OP `turn-0002` before `turn-0001`.

## 3. Stage Taxonomy (Error Attribution Law)

Every `KernelIssue` MUST be attributed to the correct stage:

| Concern | Required Stage |
|---|---|
| Ordering, ledger, tombstone validation | `promotion` |
| Orphan / link integrity | `lsi` |
| API boundary / request validation | `base_shape` |

Constraint:
`determinism` MUST NOT be used for promotion or LSI failures.

## 4. Tombstone Wire Format (Deletion Law)

Filename: `<stem>.tombstone.json`
Schema: `contracts/tombstone-v1.schema.json`

4.1 Validation:
`payload.stem` MUST match the filename-derived stem byte-for-byte.

4.2 Failure Codes:
Invalid payload -> `E_TOMBSTONE_INVALID`
Stem mismatch -> `E_TOMBSTONE_STEM_MISMATCH`

Both MUST use `stage="promotion"`.

4.3 Promotion:
Tombstoned stems MUST be included in the promoted stems set, cause pruning of existing refs, and skip new ref injection.

4.4 Identity Payload:
Tombstone payload MUST carry `dto_type` and `id` so deletion intent can be projected onto identity keys.

## 5. Visibility Resolution (Self-Authorization Wall)

Visibility MUST be computed as:

`Visible = (Sovereign_Index - Tombstoned_Identities) + Staged_Creations`

5.0 Identity Basis:
All created objects MUST be identified by `{dto_type, id}` pairs derived from the staged body.
This identity pair is the canonical basis for:
- visibility resolution,
- staged creation sets,
- and reference validation.

5.1 Identity Basis:
Computed on `{type, id}` pairs, not just stems.

5.2 Conflict Rule:
If a stem is both tombstoned and re-created in the same turn, Creation wins.

5.3 Orphan Failure:
If a link target is not visible, emit `E_LSI_ORPHAN_TARGET` under `stage="lsi"`.

## 6. Vocabulary Governance (Registry Law)

Path: `contracts/error-codes-v1.json`

6.1 Rule:
Every emitted `KernelIssue.code` (and informational `I_` codes in deterministic output) MUST exist in the registry.

6.2 Scope:
Includes `base_shape` codes (e.g., `E_BASE_SHAPE_MISSING_RUN_ID`).

6.3 Registry Integrity:
Registry MUST contain no duplicate codes.
Registry ordering SHOULD be deterministic (sorted).
Dynamic code suffixing/variants are forbidden.

6.4 Token Coverage:
Every emitted log token of the form `[CODE:X]` MUST also exist in the registry.

6.5 Digest Specificity:
Once digest enforcement is active, digest failures MUST use specific `E_DIGEST_*` codes rather than umbrella failures such as `E_PROMOTION_FAILED`.

6.6 Registry Guardrail Test:
`tests/kernel/v1/test_registry.py` MUST enforce:
1. Registry schema/pattern validity and duplicate rejection.
2. Emitted issue codes belong to `contracts/error-codes-v1.json`.
3. Emitted `[CODE:X]` tokens belong to `contracts/error-codes-v1.json`.
4. Deterministic failure output for missing registrations.

## 7. API Boundary and Packaging

7.1 Boundary:
`validator.py` MUST expose thin, truthful handlers (`execute_turn_v1`, etc.) that perform base-shape checks and use safe serialization.

7.2 Packaging Hygiene:
`tests/__init__.py`, `tests/kernel/__init__.py`, `tests/kernel/v1/__init__.py`, and (until consolidation) `tests/lsi/__init__.py` MUST exist.

## 8. Sovereign Test Home (Gate Law)

Canonical gate lives at: `tests/kernel/v1/`

CI gate command:

```bash
python -m pytest -q tests/kernel/v1
```

Conformance parity gate:

```bash
npm test --prefix conformance/ts
```

Vector handshake rule:
1. Golden vectors are maintainer-generated and committed.
2. CI consumes committed vectors and MUST NOT overwrite vector files.
3. CI MAY regenerate and diff for parity checks, but write-back in CI is forbidden.

Execution gate commands:
1. `python scripts/audit_registry.py`
2. `python -m pytest -q tests/kernel/v1`
3. `npm test --prefix conformance/ts`

## 9. Kernel Requirements Exit Condition

The phase is closed when:
1. Spec-002 is green (ledger, no-op, and orphan laws).
2. Tombstone semantics are enforced.
3. Registry guardrail is live (asserting issue emission).
4. `validator.py` boundary is truthful and base-shape safe.
