# techdebt Requirements Map

Last updated: 2026-03-02
Source audit: `docs/projects/techdebt/Orket_Brutal_Production_Audit.pdf`

## Severity Model
1. `P0` critical
2. `P1` high
3. `P2` medium/low

`critical == P0`

## Requirements
| ID | Requirement | Severity | Owner | Target Module | Status | Evidence |
|---|---|---|---|---|---|---|
| TD-001 | Semantic artifact containment checks (`resolve()+relative_to()`) | P0 | Orket Core | `orket/extensions/workload_artifacts.py` | complete | deterministic containment tests in `tests/runtime/test_extension_components.py` |
| TD-002 | Symlink refusal for artifact validation/manifest generation | P0 | Orket Core | `orket/extensions/workload_artifacts.py` | complete | symlink rejection tests in `tests/runtime/test_extension_components.py` |
| TD-003 | Streaming SHA-256 hashing and size caps | P1 | Orket Core | `orket/extensions/workload_artifacts.py` | complete | file/total size cap tests in `tests/runtime/test_extension_components.py` |
| TD-004 | Deterministic containment failure ordering and stable payload shape | P1 | Orket Core | `orket/extensions/workload_artifacts.py` | complete | ordered payload test in `tests/runtime/test_extension_components.py` |
| TD-005 | Install ref pinning to immutable commit SHA (detached checkout) | P0 | Orket Core | `orket/extensions/manager.py` | complete | install metadata tests in `tests/runtime/test_extension_manager.py` |
| TD-006 | Persist and verify manifest digest at run | P0 | Orket Core | `orket/extensions/manager.py` | complete | tamper rejection test in `tests/runtime/test_extension_manager.py` |
| TD-007 | Trust policy matrix (mode/profile/host/protocol) | P1 | Orket Core | `orket/extensions/manager.py` | in-progress | host/protocol matrix tests in `tests/runtime/test_extension_manager.py` |
| TD-008 | Compatibility fallback metadata and provenance security snapshot | P1 | Orket Core | `orket/extensions/*` | complete | provenance assertions in `tests/runtime/test_extension_manager.py` |
| TD-009 | Compatibility fallback expiry CI gate | P1 | Orket Core | `scripts/check_compat_fallback_expiry.py` | complete | `tests/application/test_check_compat_fallback_expiry.py` |
| TD-010 | Compatibility warning CI artifacts | P1 | Orket Core | `scripts/export_security_compat_warnings.py` | complete | `tests/application/test_export_security_compat_warnings.py` |
| TD-011 | Enforcement flip gate script (`P0==0`, regressions green, warnings zero, expiry green) | P1 | Orket Core | `scripts/check_security_enforcement_flip_gate.py` | complete | `tests/application/test_check_security_enforcement_flip_gate.py` |
| TD-012 | Provenance redaction-by-default | P1 | Orket Core | `orket/extensions/workload_artifacts.py` | complete | redaction/verbose provenance tests in `tests/runtime/test_extension_manager.py` |
| TD-013 | API auth hardening (query token compat warning -> enforce deny) | P0 | Orket Core | `orket/interfaces/api.py`, `orket/decision_nodes/api_runtime_strategy_node.py` | complete | websocket auth tests in `tests/interfaces/test_api.py` |
| TD-014 | Production lockout for insecure bypass | P0 | Orket Core | API/runtime strategy | complete | profile lockout tests in `tests/interfaces/test_api.py` |
| TD-015 | Compatibility fallback expiry removal execution | P1 | Orket Core | extension trust path | open | pending Phase 5 completion |

## Gate Snapshot
1. `P0_open`: 0
2. Enforcement flip readiness: gate script green on current artifacts (`benchmarks/results/security_enforcement_flip_gate.json`).
