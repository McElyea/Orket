# v1.2 PR Workboard (Execution Packet)

Last updated: 2026-02-24
Status: Archived (PR-01..PR-07 complete; closeout complete)

This file is the implementation handoff for PR-01 through PR-07.

## Global Rules (Apply to Every PR)
1. Respect D1-D9 from `open-decisions.md`.
2. Keep all path references under `docs/projects/OS/*` and repo code/tests.
3. When a field is excluded from hashing, set it to `null`; do not remove the key.
4. Do not bundle unrelated refactors into these PRs.

## PR-01: Add Stage Spine + Registry Wrapper (No Kernel Changes)
Status:
1. Complete.

Goal:
1. Land the anchor artifacts required by comparator and replay contracts.

Primary files:
1. `docs/projects/OS/contracts/stage-order-v1.json` (new)
2. `docs/projects/OS/contracts/error-codes-v1.json` (wrapper-form registry instance)
3. `docs/projects/OS/contracts/error-codes-v1.schema.json` (compat shape for migration window)
4. `docs/projects/OS/contracts/sovereign-laws.md` (new; locked laws only)
5. `scripts/audit_registry.py` (read wrapper and compute deterministic digest)

Required acceptance checks:
1. Registry audit reads wrapper and emits deterministic digest over canonical bytes of:
   - `{ "contract_version": "...", "codes": { ... } }`
2. Stage-order contract is referenced from docs used by comparator and replay contracts.
3. No edits to `orket/kernel/v1/*` in this PR.

Suggested checks:
1. `python scripts/audit_registry.py`
2. `python -m pytest -q tests/kernel/v1/test_registry.py`

## PR-02: CapabilityDecisionRecord Schema + Coexistence Wiring
Status:
1. Complete.

Goal:
1. Introduce authoritative decision-record parity shape without breaking existing turn artifacts.

Primary files:
1. `docs/projects/OS/contracts/capability-decision-record.schema.json` (new)
2. `docs/projects/OS/contracts/turn-result.schema.json` (add coexistence field)
3. `docs/projects/OS/contracts/capability-decision.schema.json` (unchanged semantics; keep valid)
4. `tests/kernel/v1/test_validator_schema_contract.py` (extend contract coverage)

Coexistence lock:
1. Use explicit versioned coexistence field in `TurnResult`:
   - keep existing `capabilities.decisions` unchanged
   - add `capabilities.decisions_v1_2_1` for `CapabilityDecisionRecord[]`
2. Comparator parity uses `decisions_v1_2_1` only when both sides provide it.

Required acceptance checks:
1. JSON Schema validates examples for all outcomes:
   - `allowed`
   - `denied`
   - `skipped`
   - `unresolved`
2. Existing TurnResult fixtures still validate.

## PR-03: ReplayBundle + ReplayReport Schemas
Status:
1. Complete.

Goal:
1. Make replay input/output contracts authoritative and deterministic.

Primary files:
1. `docs/projects/OS/contracts/replay-bundle.schema.json` (new)
2. `docs/projects/OS/contracts/replay-report.schema.json` (tightened additively)
3. `docs/projects/OS/Execution/replay-contract.md` (cross-reference updates)

Required acceptance checks:
1. Bundle schema enforces required fields and `paths.minItems >= 1`.
2. Report schema enforces required mismatch keys:
   - `surface`
   - `stage_name`
   - `path`
   - `diagnostic` (nullable for report-id projection)
3. Report schema enforces digest nullability rules for schema/ERROR cases.

Suggested checks:
1. `python -m pytest -q tests/kernel/v1/test_validator_schema_contract.py`
2. `python -m pytest -q tests/interfaces/test_api_kernel_lifecycle.py`

## PR-04: Canonicalization + Digest Rules Documentation
Status:
1. Complete.

Goal:
1. Lock byte-level rules so Python/TypeScript/comparator converge.

Primary files:
1. `docs/projects/OS/contracts/canonicalization-rules.md` (new)
2. `docs/projects/OS/contracts/decision-id-derivation.md` (new)
3. `docs/projects/OS/contracts/digest-surfaces.md` (new; D3 and D8 explicit)

Required acceptance checks:
1. Rules explicitly define:
   - sorted keys
   - deterministic separators
   - UTF-8
   - `ensure_ascii=false`
   - float/NaN/Infinity/-0 ban
   - no Unicode normalization transforms
2. TurnResult digest scope is documented as contract-only.
3. Hash projections specify nullification, not omission.

## PR-05: Comparator Implementation (IssueKey Multimap + report_id Invariant)
Status:
1. Complete.

Goal:
1. Ship the deterministic gate implementation for replay parity.

Primary files:
1. `scripts/replay_comparator.py` (new)
2. `tests/kernel/v1/test_replay_comparator.py` (new)
3. `tests/interfaces/test_api_kernel_lifecycle.py` (API-boundary parity assertions)

Must-have tests:
1. Registry lock mismatch:
   - status `DIVERGENT`
   - `E_REGISTRY_DIGEST_MISMATCH`
2. Version mismatch:
   - status `DIVERGENT`
   - `E_REPLAY_VERSION_MISMATCH`
3. Safe boundary:
   - `KernelIssue.message` drift does not fail parity
4. Issue multiplicity:
   - same IssueKey with different counts fails parity
5. Report ordering:
   - sorted by `(turn_id, stage_index, ordinal, surface, path)`
6. `report_id` derivation:
   - nullify `report_id` and `mismatches[*].diagnostic` before hashing
   - stable hash across equivalent runs

Suggested checks:
1. `python -m pytest -q tests/kernel/v1/test_replay_comparator.py`
2. `python -m pytest -q tests/interfaces/test_api_kernel_lifecycle.py`

## PR-06: Kernel Emission Wiring (DecisionRecords + Correspondence Law)
Status:
1. Complete.

Goal:
1. Ensure runtime emits parity decision records deterministically.

Primary files:
1. `orket/kernel/v1/validator.py`
2. `orket/kernel/v1/contracts.py`
3. `tests/kernel/v1/test_validator_v1.py`
4. `tests/kernel/v1/test_api_surface.py`

Required runtime law:
1. Exactly one `CapabilityDecisionRecord` per tool attempt.
2. For `denied` and `unresolved` outcomes, emit matching `KernelIssue` with:
   - `stage = "capability"`
   - `code == deny_code`
   - `location = /capabilities/decisions_v1_2_1/<ordinal>` during coexistence

Required acceptance checks:
1. Tests enforce one-record-per-attempt invariant.
2. Tests enforce correspondence law.
3. API boundary behavior remains deterministic.

## PR-07: TurnResult Digest Surface Implementation (D3)
Status:
1. Complete.

Goal:
1. Compute `turn_result_digest` from contract-only digest surface.

Primary files:
1. `orket/kernel/v1/canonical.py`
2. `orket/kernel/v1/validator.py`
3. `tests/kernel/v1/test_replay_vectors.py`
4. `tests/kernel/v1/test_replay_stability.py`

Required acceptance checks:
1. Changes to `events` do not change digest.
2. Changes to `KernelIssue.message` do not change digest.
3. Changes to parity-relevant structural fields do change digest.
4. Replay stability remains deterministic over repeated runs.

Suggested checks:
1. `python -m pytest -q tests/kernel/v1/test_replay_vectors.py`
2. `python -m pytest -q tests/kernel/v1/test_replay_stability.py`

## Closeout Step (After PR-07)
Status:
1. Complete.

1. Update `docs/projects/OS/contract-index.md` with completed v1.2 artifacts.
2. Update `docs/projects/OS/test-policy.md` with mandatory comparator checks.
3. Archive this execution packet and keep only enduring normative docs.
