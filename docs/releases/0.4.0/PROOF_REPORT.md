# Release `0.4.0` Proof Report

Date: `2026-03-13`
Owner: `Orket Core`
Git tag: `v0.4.0`
Completed major project: [docs/projects/archive/techdebt/RP03122026/Closeout.md](docs/projects/archive/techdebt/RP03122026/Closeout.md)
Release policy authority: [docs/specs/CORE_RELEASE_VERSIONING_POLICY.md](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md)
Release gate checklist: [docs/specs/CORE_RELEASE_GATE_CHECKLIST.md](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md)

## Summary of Change

`0.4.0` starts the governed semantic-release era for the core engine. This release makes the core release/versioning policy, release gate checklist, proof report template, release policy CI workflow, and release preparation tooling canonical, and carries forward the currently active runtime-stability closeout planning work without claiming those closeout lanes are already complete.

## Stability Statement

The stable surfaces for this release are the canonical install/bootstrap command, the documented default runtime entrypoint, the documented API runtime entrypoint, the canonical pytest command, and the release/versioning governance path itself. Runtime-stability closeout work remains active and is intentionally tracked as post-`0.4.0` implementation work rather than treated as a prerequisite for starting semantic versioning.

## Compatibility Classification

- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

## Required Operator or Extension-Author Action

None.

## Proof Record Index

| Surface | Surface Type | Proof Mode | Proof Result | Reason | Evidence |
| --- | --- | --- | --- | --- | --- |
| `python main.py` | `default_runtime_entrypoint` | `live` | `success` | `none` | `benchmarks/results/releases/0.4.0/main_help.txt` |
| `python server.py` | `api_runtime_entrypoint` | `live` | `success` | `none` | `benchmarks/results/releases/0.4.0/server_help.txt` |
| `execution pipeline run ledger workflow` | `workflow_path` | `live` | `success` | `none` | `benchmarks/results/releases/0.4.0/workflow_pytest.txt` |
| `protocol run ledger + run graph integration routes` | `integration_route` | `live` | `success` | `none` | `benchmarks/results/releases/0.4.0/integration_pytest.txt` |
| `core release policy guard` | `integration_route` | `live` | `success` | `none` | `benchmarks/results/releases/0.4.0/core_release_policy_check.txt`, `benchmarks/results/releases/0.4.0/core_release_policy_check.json` |

## Detailed Proof Records

### `python main.py`

- `surface_type`: `default_runtime_entrypoint`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.4.0/main_help.txt`
- `notes`: Release proof used the CLI help surface to exercise the entrypoint non-interactively in this environment.

### `python server.py`

- `surface_type`: `api_runtime_entrypoint`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.4.0/server_help.txt`
- `notes`: Release proof used the server help surface to exercise the API entrypoint non-interactively in this environment.

### `execution pipeline run ledger workflow`

- `surface_type`: `workflow_path`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.4.0/workflow_pytest.txt`
- `notes`: Covered the execution-pipeline run-ledger workflow on incomplete, failed, terminal-failure, and bootstrap-artifact paths.

### `protocol run ledger + run graph integration routes`

- `surface_type`: `integration_route`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.4.0/integration_pytest.txt`
- `notes`: Covered protocol run-ledger finalize behavior and deterministic run-graph reconstruction.

### `core release policy guard`

- `surface_type`: `integration_route`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.4.0/core_release_policy_check.txt`, `benchmarks/results/releases/0.4.0/core_release_policy_check.json`
- `notes`: Verified that the repo state for this release aligns with core release policy expectations before tagging.

## Final Proof-Gate Acceptance

Accepted by `Orket Core` on `2026-03-13` as the first process-backed semantic release milestone. This acceptance explicitly does not claim that active runtime-stability closeout lanes are already complete; those remain tracked post-release execution work.
