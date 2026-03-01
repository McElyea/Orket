# Orket Extension SDK v0

Last updated: 2026-02-28

## Purpose

Define one clear public extension seam for deterministic workloads with explicit capability injection.

## North Star

Orket is a rule laboratory. The SDK is how workloads (games, simulations, rule auditors) plug into it. The SDK must be workload-agnostic -- it doesn't care whether the workload is a mystery game, a TCG meta breaker, or a policy simulator.

## Public Seam (Locked)

```
Workload.run(ctx, input) -> WorkloadResult
```

Engine-internal types (including `TurnResult`) are private and may change without compatibility guarantees.

## Documents

| File | Purpose |
|---|---|
| `01-REQUIREMENTS.md` | Unified requirements and SDK module contracts |
| `02-PLAN.md` | Implementation phases, status, and remaining work |
| `03-MIGRATION-AND-COMPAT.md` | Migration policy, compatibility guarantees, deprecation criteria |
| `04-TEXTMYSTERY-LAYER0.md` | TextMystery-specific gameplay decisions and checkpoint (reference workload) |

## SDK Modules (v0)

1. `orket_extension_sdk.manifest` -- extension declaration and validation
2. `orket_extension_sdk.capabilities` -- capability injection contracts
3. `orket_extension_sdk.workload` -- execution context and workload protocol
4. `orket_extension_sdk.result` -- structured outcomes and artifacts
5. `orket_extension_sdk.testing` -- determinism harness and test helpers

## SDK Location (Locked)

- Standalone repo: `c:\Source\OrketSDK`
- Package name: `orket-extension-sdk`
- Version policy: `0.y.z` during layer-0 stabilization
- Local dev: `pip install -e c:\Source\OrketSDK`
- Publish: deferred until layer-0 exit criteria met
