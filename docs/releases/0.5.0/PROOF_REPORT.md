# Release `0.5.0` Proof Report

Date: `2026-04-26`
Owner: `Orket Core`
Git tag: `v0.5.0`
Completed major project: [docs/projects/archive/NorthstarRefocus/2026-04-25-OUTWARD-PIPELINE-CLOSEOUT/closeout.md](docs/projects/archive/NorthstarRefocus/2026-04-25-OUTWARD-PIPELINE-CLOSEOUT/closeout.md)
Release policy authority: [docs/specs/CORE_RELEASE_VERSIONING_POLICY.md](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md)
Release gate checklist: [docs/specs/CORE_RELEASE_GATE_CHECKLIST.md](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md)

## Summary of Change

`0.5.0` closes the NorthstarRefocus outward-facing pipeline lane. The release adds the local governed runtime loop for outward work submission, approval-gated connector execution, denial and timeout handling, persisted run inspection, operator-facing ledger export, and offline `ledger_export.v1` verification.

## Stability Statement

The stable surfaces for this release are the local outward API/CLI governed-run loop, approval decision surfaces, persisted outward run inspection, `ledger_export.v1`, and offline ledger verification. Graphical UI, third-party connector discovery, durable SSE pub/sub, legacy artifact import, and paused provider-backed AWS/Bedrock proof lanes remain outside this release.

## Compatibility Classification

- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`

## Required Operator or Extension-Author Action

No immediate action required. Operators running the outward API must configure `ORKET_API_KEY`; browser clients must explicitly configure trusted CORS origins through `ORKET_ALLOWED_ORIGINS`.

## Proof Record Index

| Surface | Surface Type | Proof Mode | Proof Result | Reason | Evidence |
| --- | --- | --- | --- | --- | --- |
| `python main.py` | `default_runtime_entrypoint` | `live` | `success` | `none` | `benchmarks/results/releases/0.5.0/main_help.txt` |
| `python server.py` | `api_runtime_entrypoint` | `live` | `success` | `none` | `benchmarks/results/releases/0.5.0/server_help.txt` |
| `NorthstarRefocus outward acceptance paths` | `workflow_path` | `live` | `success` | `none` | `benchmarks/results/releases/0.5.0/northstar_e2e_acceptance.txt` |
| `outward API, approval, connector, policy, ledger integration routes` | `integration_route` | `live` | `success` | `none` | `benchmarks/results/releases/0.5.0/outward_targeted_pytest.txt` |
| `docs project hygiene` | `integration_route` | `live` | `success` | `none` | `benchmarks/results/releases/0.5.0/docs_project_hygiene.txt` |
| `canonical pytest suite` | `integration_route` | `live` | `success` | `none` | `benchmarks/results/releases/0.5.0/full_pytest.txt` |

## Detailed Proof Records

### `python main.py`

- `surface_type`: `default_runtime_entrypoint`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.5.0/main_help.txt`
- `notes`: Release proof uses the CLI help surface to exercise the default runtime entrypoint non-interactively.

### `python server.py`

- `surface_type`: `api_runtime_entrypoint`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.5.0/server_help.txt`
- `notes`: Release proof uses the server help surface to exercise the API runtime entrypoint non-interactively.

### `NorthstarRefocus outward acceptance paths`

- `surface_type`: `workflow_path`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.5.0/northstar_e2e_acceptance.txt`
- `notes`: Covers approval, denial, and timeout through the outward API with real SQLite persistence, workspace file effect or effect absence, run inspection, ledger export, and offline verification.

### `outward API, approval, connector, policy, ledger integration routes`

- `surface_type`: `integration_route`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.5.0/outward_targeted_pytest.txt`
- `notes`: Covers targeted outward pipeline API, CLI, approval, connector, policy-gate, storage, and ledger tests.

### `docs project hygiene`

- `surface_type`: `integration_route`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.5.0/docs_project_hygiene.txt`
- `notes`: Verifies roadmap and docs project index hygiene after archiving NorthstarRefocus.

### `canonical pytest suite`

- `surface_type`: `integration_route`
- `proof_mode`: `live`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `benchmarks/results/releases/0.5.0/full_pytest.txt`
- `notes`: Exercises the canonical test command from [docs/CONTRIBUTOR.md](docs/CONTRIBUTOR.md).

## Final Proof-Gate Acceptance

Accepted by `Orket Core` on `2026-04-26` as the minor release for the completed NorthstarRefocus outward-facing pipeline lane.
