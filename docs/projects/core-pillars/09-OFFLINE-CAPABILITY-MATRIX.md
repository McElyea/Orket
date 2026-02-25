# Core Pillars Offline Capability Matrix

Date: 2026-02-24  
Status: active

## Objective
Define deterministic offline behavior for the v1 command surface and enforce that baseline flows do not require network access by default.

## Network Toggle Contract
1. Runtime network mode values:
- `offline` (default)
- `online_opt_in` (explicit)

2. Source of truth:
- `orket.runtime.offline_mode.resolve_network_mode`

3. Baseline guarantee:
- If network mode is unset, Orket resolves to `offline`.

## Command Matrix (v1)

| Command | Offline Supported | Requires Network By Default | Degradation Behavior | Notes |
|---|---|---|---|---|
| `init` | yes | no | none | Local blueprint/template hydration only. |
| `api_add` | yes | no | none | Local project mutation + local verify profile. |
| `refactor` | yes | no | none | Local repo mutation + local verify profile. |

## Enforcement
1. Contract checker:
- `python scripts/check_offline_matrix.py --require-default-offline`

2. Required checks:
- matrix doc exists and contains v1 commands
- runtime matrix includes v1 commands
- default network mode resolves to `offline`
- v1 commands do not require network by default

3. CI policy:
- Offline matrix check runs in quality workflow.

## Non-Goals (v1)
1. Forcing all optional integrations (for example gitea exporter) to operate offline.
2. Simulating network failure behavior for every adapter.
3. Replacing adapter-specific readiness gates.
