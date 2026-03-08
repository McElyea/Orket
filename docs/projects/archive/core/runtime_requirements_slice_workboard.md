# Core Runtime Requirements Slice Workboard

Last updated: 2026-03-06  
Status: Completed (closeout tracker)  
Owner: Orket Core

## Purpose

Track execution status, dependencies, and proof obligations for implementation slices defined in:
1. `runtime_requirements_implementation_plan.md`

## Slice Tracker

| Slice ID | Name | Status | Priority | Depends On | Primary Proof | Proof Artifact | Evidence Location | Notes |
|---|---|---|---|---|---|---|---|---|
| CORE-IMP-00 | Contract Bootstrap | done | P0 | none | Contract tests for registry/map validation | `contract_bootstrap_validation_report.json` | `tests/reports/contract_bootstrap_validation_report.json` | Canonical contract sources/loader and runtime snapshot capture are implemented (`core/artifacts/schema_registry.yaml`, `core/tools/*`, `orket/runtime/contract_bootstrap.py`) and verified via targeted contract+integration suite (`19 passed`) with docs hygiene check. |
| CORE-IMP-01 | Deterministic Run Spine | done | P0 | CORE-IMP-00 | Integration proof of ledger ordering + required invocation manifests | `ledger_ordering_test_report.json` | `tests/reports/ledger_ordering_test_report.json` | Run-start artifacts and immutable contract snapshots are enforced; protocol ledger now enforces strict `tool_call -> result` sequence contracts with `call_sequence_number`, rejects orphaned open calls on finalize, requires explicit per-invocation manifests and `tool_call_hash` on runtime receipt + ledger paths, and enforces artifact emission only after matching results. |
| CORE-IMP-02 | Golden Replay Integrity | done | P0 | CORE-IMP-00, CORE-IMP-01 | Integration replay tests + compatibility rejection tests | `replay_integrity_test_report.json` | `tests/reports/replay_integrity_test_report.json` | Replay now enforces capability-manifest source compatibility and workspace snapshot compatibility for workspace/external runs, fails closed on incompatible/mixed `ledger_schema_version`, enforces operation-record-only replay execution (`E_REPLAY_OPERATION_MISSING` on gaps), and applies replay isolation guardrails that skip runtime persistence writes during replay-mode dispatcher execution; deterministic drift classification (`drift_schema_version` `1.0`) remains in place across compare/campaign outputs. |
| CORE-IMP-03 | Ring Policy Enforcement | done | P1 | CORE-IMP-00 | Static import boundary tests + dispatch rejection integration tests | `ring_policy_enforcement_report.json` | `tests/reports/ring_policy_enforcement_report.json` | Runtime dispatch preflight rejects ring/capability/determinism-policy/tool-invocation-boundary violations before execution, role/skill tool bindings carry explicit ring/determinism/capability/tool-contract metadata defaults, turn contexts inherit run-scoped determinism/capability policy from run-start artifacts, and runtime emits explicit `determinism_violation` telemetry plus `E_DETERMINISM_VIOLATION` when declared-`pure` tools show side-effect signals. |
| CORE-IMP-04 | Compatibility Mapping Governance | done | P1 | CORE-IMP-00, CORE-IMP-03 | Mapping contract tests + translation artifact integration tests | `compat_mapping_governance_report.json` | `tests/reports/compat_mapping_governance_report.json` | Compatibility map validation enforces no-chaining + determinism propagation (least-deterministic mapped core tool class), dispatcher enforces mapping presence and policy preflight for compatibility tools, run-start artifacts include immutable `compatibility_map_snapshot`, and compatibility dispatch writes `compat_translation.json` artifacts with mapping version/determinism + translation hash. |
| CORE-IMP-05 | Prompt Budget and Tokenizer Truth | done | P1 | CORE-IMP-01, CORE-IMP-02 | Budget enforcement contract tests + backend-tokenizer integration tests | `prompt_budget_tokenizer_truth_report.json` | `tests/reports/prompt_budget_tokenizer_truth_report.json` | Stage-scoped prompt budgets now load from canonical `core/policies/prompt_budget.yaml`, turn execution enforces fail-closed budget checks with explicit `E_PROMPT_BUDGET_EXCEEDED` semantics, backend tokenizer accounting is integrated via model/provider `count_tokens` paths (with explicit tokenizer-accounting failure code when strict backend binding is required), and turn artifacts now emit `prompt_budget_usage.json`, `prompt_structure.json`, and structural `prompt_diff.txt` when prompt structure changes between adjacent turns. |
| CORE-IMP-06 | Reliability Scoreboard and Promotion Gates | done | P1 | CORE-IMP-01, CORE-IMP-02, CORE-IMP-04 | Ledger-only reproducibility tests + promotion gate integration tests | `scoreboard_promotion_gate_report.json` | `tests/reports/scoreboard_promotion_gate_report.json` | Ledger-only scoreboard computation now fails closed on incomplete tool call/result coverage, promotion-gate evaluator emits deterministic pass/fail reasons (reliability threshold, replay parity, unresolved drift), governance script now emits rerunnable `tool_scoreboard.json` artifacts from append-only ledger events, and canonical retention policy tiers are defined in `core/policies/artifact_retention_tiers.yaml`. |
| CORE-IMP-07 | Compatibility Pilot Vertical Slice | done | P2 | CORE-IMP-02, CORE-IMP-04, CORE-IMP-06 | Live+replay golden parity on pilot mappings | `compat_pilot_parity_report.json` | `tests/reports/compat_pilot_parity_report.json` | Pilot compatibility set (`openclaw.file_read`, `openclaw.workspace_list`, `openclaw.file_edit`) now has deterministic live+replay parity coverage through dispatcher integration, compatibility translation artifacts now include latency (`compat_latency_profile.json`) plus mapping metadata, and replay-mode compatibility calls prove operation-record parity without re-executing mapped core tools. |
| CORE-IMP-08 | Run Graph Reconstruction | done | P3 | CORE-IMP-01, CORE-IMP-02, CORE-IMP-04, CORE-IMP-07 | Deterministic graph reconstruction + replay parity integration tests | `run_graph_reconstruction_report.json` | `tests/reports/run_graph_reconstruction_report.json` | Runtime protocol finalize now emits deterministic `run_graph.json` derived from ledger+artifact metadata only, graph schema is pinned in `core/artifacts/run_graph_schema.json`, and contract/integration tests prove reproducibility, artifact-lineage integrity, compatibility-expansion edge correctness, golden reconstruction, and deterministic live-vs-replay parity. |

## Status Definitions

1. `queued`: not started.
2. `in_progress`: actively implementing.
3. `blocked`: cannot proceed due to explicit blocker.
4. `done`: implemented, verified, and closeout evidence recorded.
5. `future`: intentionally deferred until prerequisites are complete.

## Closeout Requirements Per Slice

1. Code changes merged for claimed behavior.
2. Required proof artifacts/tests executed and recorded.
3. Any unproven seams documented explicitly as residual risk.
4. Tracker row status moved to `done` only after proof is attached.

## Blocker Logging Format

Use this format when a slice becomes blocked:

```text
Slice: CORE-IMP-XX
Blocker: <short blocker title>
Type: environment | dependency | design | test-gap
Impact: <what cannot proceed>
Next action: <smallest unblock step>
```
