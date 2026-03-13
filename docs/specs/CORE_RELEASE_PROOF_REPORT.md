# Core Release Proof Report Template

Last updated: 2026-03-12
Status: Active
Owner: Orket Core

Canonical template for completed core engine minor-release proof reports beginning with `0.4.0`.

Patch releases may use this template, but it is required only when the release policy or release gate requires proof records.

## 1. Storage Rules

1. Save the completed narrative report as `docs/releases/<version>/PROOF_REPORT.md`.
2. Use the plain release number for `<version>`, not the Git tag form.
3. Store machine-readable or bulky supporting evidence under `benchmarks/results/releases/<version>/`.
4. Keep evidence references stable and repo-relative where practical.
5. Record an explicit `reason` whenever:
   - `proof_mode` is `structural`
   - `proof_result` is `blocked`
   - `proof_result` is `not_applicable`

## 2. Template

```md
# Release `<version>` Proof Report

Date: `YYYY-MM-DD`
Owner: `Orket Core`
Git tag: `v<major>.<minor>.<patch>`
Completed major project: `<roadmap lane or closeout reference>`
Release policy authority: [docs/specs/CORE_RELEASE_VERSIONING_POLICY.md](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md)
Release gate checklist: [docs/specs/CORE_RELEASE_GATE_CHECKLIST.md](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md)

## Summary of Change

<High-level description of what the release introduces or modifies.>

## Stability Statement

<Explicit statement of which system surfaces are considered stable for this release.>

## Compatibility Classification

- `compatibility_status`: `<preserved|breaking|deprecated>`
- `affected_audience`: `<operator_only|extension_author_only|internal_only|all>`
- `migration_requirement`: `<none|required>`

## Required Operator or Extension-Author Action

<Migration or operational steps required after upgrade. Write `None.` if no action is required.>

## Proof Record Index

| Surface | Surface Type | Proof Mode | Proof Result | Reason | Evidence |
| --- | --- | --- | --- | --- | --- |
| `<surface name>` | `<default_runtime_entrypoint|api_runtime_entrypoint|workflow_path|integration_route>` | `<live|structural>` | `<success|blocked|not_applicable>` | `<reason or none>` | `<repo-relative links>` |

## Detailed Proof Records

### `<surface name>`

- `surface_type`: `<default_runtime_entrypoint|api_runtime_entrypoint|workflow_path|integration_route>`
- `proof_mode`: `<live|structural>`
- `proof_result`: `<success|blocked|not_applicable>`
- `reason`: `<required when proof_mode is structural or proof_result is blocked/not_applicable; otherwise none>`
- `evidence`: `<repo-relative links to logs, screenshots, traces, command transcripts, or narrative evidence>`
- `notes`: `<optional>`

### `<next surface name>`

- `surface_type`: `<default_runtime_entrypoint|api_runtime_entrypoint|workflow_path|integration_route>`
- `proof_mode`: `<live|structural>`
- `proof_result`: `<success|blocked|not_applicable>`
- `reason`: `<required when proof_mode is structural or proof_result is blocked/not_applicable; otherwise none>`
- `evidence`: `<repo-relative links to logs, screenshots, traces, command transcripts, or narrative evidence>`
- `notes`: `<optional>`
```

## 3. Minimum Coverage Rules

Every completed minor-release proof report must include records for:

1. the default runtime entrypoint
2. the API runtime entrypoint
3. at least one real workflow path
4. currently material integration routes

If a required surface does not exist or is outside the supported scope of the release, use `proof_result: not_applicable` and record the reason explicitly.
