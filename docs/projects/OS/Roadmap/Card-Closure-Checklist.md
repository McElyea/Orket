# OS v1 Card Closure Checklist

Last updated: 2026-02-24
Status: Active checklist

## Card 006 - Replay Engine

Acceptance:
1. Structural replay parity checks deterministic.
2. Divergences reported with stable codes.
3. 100/100 replay stability.

Evidence:
1. `tests/kernel/v1/test_replay_vectors.py`
2. `tests/interfaces/test_api_kernel_lifecycle.py` (`/v1/kernel/compare` real-engine assertions)
3. `tests/kernel/v1/test_replay_stability.py`

Gate linkage:
1. `.gitea/workflows/quality.yml` -> `python -m pytest -q tests/kernel/v1`
2. `.gitea/workflows/quality.yml` -> `python -m pytest -q tests/interfaces/test_api_kernel_lifecycle.py`

Status:
1. Completed.

## Card 007 - Capability Jail

Acceptance:
1. Undeclared permissions denied deterministically.
2. Audit fields present for allow/deny outcomes.
3. Module-off emits `I_CAPABILITY_SKIPPED`.

Evidence:
1. `tests/kernel/v1/test_validator_v1.py` (`E_PERMISSION_DENIED`, `E_CAPABILITY_DENIED`, `E_SIDE_EFFECT_UNDECLARED`, `E_CAPABILITY_NOT_RESOLVED`)
2. `tests/kernel/v1/test_validator_schema_contract.py` (capability decision schema conformance)
3. `model/core/contracts/kernel_capability_policy_v1.json` + `tests/kernel/v1/test_capability_policy_contract.py`

Gate linkage:
1. `.gitea/workflows/quality.yml` -> `python -m pytest -q tests/kernel/v1`

Status:
1. Completed.

## Card 008 - Contract Tests

Acceptance:
1. Schema validation tests are active.
2. Scenario constitution tests are active.
3. PR gates enforce `docs/projects/OS/test-policy.md`.

Evidence:
1. `tests/kernel/v1/test_validator_schema_contract.py`
2. `tests/kernel/v1/test_registry.py`
3. `tests/kernel/v1/test_digest_vectors.py`
4. `tests/kernel/v1/test_tombstone_promotion.py`
5. `tests/interfaces/test_api_kernel_lifecycle.py`
6. `scripts/audit_registry.py`

Gate linkage:
1. `.gitea/workflows/quality.yml` -> registry audit
2. `.gitea/workflows/quality.yml` -> kernel sovereign suite
3. `.gitea/workflows/quality.yml` -> kernel interface suite
4. `.gitea/workflows/quality.yml` -> TS conformance gate

Status:
1. Completed.
2. Fire-drill suite is now codified as `python scripts/run_kernel_fire_drill.py`.
