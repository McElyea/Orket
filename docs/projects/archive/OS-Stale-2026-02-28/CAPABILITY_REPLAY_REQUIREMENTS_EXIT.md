# CAPABILITY_REPLAY_REQUIREMENTS_EXIT.md

Sovereign Capability + Replay - Normative Closure Specification (v1)

Last updated: 2026-02-23
Status: Draft

This document defines the sealed, mechanically enforceable requirements for the post-kernel OS phase: Capability Security + Replay/Equivalence. Once implemented and the sovereign test suite is green, this phase is closed.

Strategic impact:
Capability deny-by-default plus deterministic replay equivalence converts the kernel from "state correct now" to "state and decision process reproducible later", which is required for safe policy rollout and audit-grade incident analysis.

## 1. Capability Sovereignty (Resolution Law)

Purpose: Capability decisions are contract data, not runtime intuition.

1.1 Resolution Order:
Capability resolution MUST execute before any tool execution attempt.

1.2 Fail-Closed:
If capability resolution fails, runtime MUST emit `E_CAPABILITY_NOT_RESOLVED` and block execution.

1.3 Stage Attribution:
Capability resolution failures MUST emit `stage="capability"`.

1.4 Deterministic Decision Surface:
Allow/deny decisions MUST be serializable through `contracts/capability-decision.schema.json` with deterministic field ordering.

## 2. Permission Gate (Deny-By-Default Law)

2.1 Default:
Any undeclared tool action MUST be denied when capability enforcement is enabled.

2.2 Failure Codes:
Denied actions MUST emit one of:
- `E_PERMISSION_DENIED`
- `E_CAPABILITY_DENIED`
- `E_SIDE_EFFECT_UNDECLARED`

2.3 Success Metadata:
Allowed actions MUST carry deterministic provenance metadata in decision details (policy source and contract version).

2.4 Stage Attribution:
Permission denials MUST emit `stage="capability"`.

## 3. Capability Module-Off Behavior (Explicit Skip Law)

3.1 Informational Signal:
When capability enforcement is disabled by policy/module configuration, runtime MUST emit `I_CAPABILITY_SKIPPED`.

3.2 Non-Ambiguity:
`I_CAPABILITY_SKIPPED` MUST NOT be emitted together with deny codes for the same decision path.

3.3 Registry Rule:
All emitted capability codes and info tokens MUST resolve in `contracts/error-codes-v1.json`.

## 4. Replay Input Contract (Completeness Law)

4.1 Required Inputs:
Replay MUST require:
- run envelope identity (`run_id`, `workflow_id`, version fields)
- policy/model/runtime profile references
- trace artifacts and validation issues
- deterministic state references

4.2 Missing Inputs:
Missing required replay inputs MUST emit `E_REPLAY_INPUT_MISSING` under `stage="replay"`.

4.3 Version Guard:
Contract version mismatches MUST emit `E_REPLAY_VERSION_MISMATCH` under `stage="replay"`.

## 5. Replay Equivalence (Deterministic Parity Law)

5.1 Must-Match Surface:
Replay equivalence MUST compare:
- stage order and stage outcomes
- error/info codes with pointers and stages
- contract digests and schema versions

5.2 Allowed Divergence:
Replay equivalence MAY ignore:
- host-local absolute paths
- non-contract diagnostic text not used for policy decisions

5.3 Failure Code:
Parity failures MUST emit `E_REPLAY_EQUIVALENCE_FAILED` under `stage="replay"`.

## 6. Comparator Output (Report Law)

6.1 Schema:
Replay comparison output MUST conform to `contracts/replay-report.schema.json`.

6.2 Determinism:
Comparator output ordering MUST be deterministic across repeated runs for identical inputs.

6.3 CI Behavior:
CI MUST fail closed on replay comparator or report-shape failure.

## 7. Gate Integration (Sovereign Test Home Law)

Canonical gate remains:
`tests/kernel/v1/`

Required scenario coverage additions:
1. capability unresolved -> `E_CAPABILITY_NOT_RESOLVED`
2. undeclared tool call denied -> deterministic deny code under `stage="capability"`
3. module-off path -> `I_CAPABILITY_SKIPPED`
4. replay input missing -> `E_REPLAY_INPUT_MISSING`
5. replay version mismatch -> `E_REPLAY_VERSION_MISMATCH`
6. replay equivalence mismatch -> `E_REPLAY_EQUIVALENCE_FAILED`

Required gate commands:
1. `python scripts/audit_registry.py`
2. `python -m pytest -q tests/kernel/v1`
3. `npm test --prefix conformance/ts`

## 8. Capability + Replay Exit Condition

This phase is closed when all are true:
1. capability deny-by-default law is enforced and green in sovereign tests
2. module-off informational behavior is deterministic and registry-backed
3. replay input/version/parity failure paths are enforced and schema-safe
4. replay comparator report output is deterministic and contract-valid
