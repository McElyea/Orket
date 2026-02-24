# Orket Modularity Roadmap (Engine-First, Optional Modules)

Date: 2026-02-24  
Constraint: preserve existing contracts where feasible; break only when clearly justified.

## Target Outcome

Engine is always included.  
Other capabilities are install/setup-selectable modules (API, CLI, webhook/Gitea, sandboxing, benchmark/kernels, etc.) with explicit contracts.

## What Remains To Make Orket Modular

1. Stabilize correctness in core runtime paths (currently blocking).
2. Establish a single enforceable dependency policy (docs + scripts + tests aligned).
3. Separate composition from implementation (no heavy import-time singletons).
4. Formalize module contracts and capability registry.
5. Map install profiles/modules to packaging artifacts (`extras` first, package split later if needed).
6. Add module-aware test lanes and gating.

## Recommended Module Model

### Base (always installed)
- `orket-engine-core`
- Includes: state machine, contracts/types, execution pipeline core, decision-node contracts, logging/event schema, persistence contracts.

### Optional modules (install/setup selectable)
- `orket-module-api` (FastAPI surface)
- `orket-module-cli` (interactive/operator CLI)
- `orket-module-gitea` (webhook server + state adapter + exporter)
- `orket-module-sandbox` (sandbox orchestration/deployment hooks)
- `orket-module-kernel` (kernel v1 lifecycle/contracts/fire-drill assets)
- `orket-module-benchmarks` (benchmark tooling/check scripts)

Each module should declare:
1. Required capabilities.
2. Optional dependencies.
3. Exported services (entrypoints).
4. Contract version compatibility range.

## Phased Plan

### Phase 0: Critical Fixes (No Contract Break)
1. Fix logging isolation/handler lifecycle.
2. Fix `get_member_metrics` missing return.
3. Fix webhook status type call (`CardStatus.CODE_REVIEW`).
4. Fix architecture test root path bugs and add non-empty-scan assertions.
5. Align architecture policy source-of-truth (doc vs test vs script).

Exit criteria:
1. New tests exist for each defect class.
2. Quality gates fail on intentional regression in each area.

### Phase 1: Composition Root + Lazy Wiring (No External API Break)
1. Move interface startup to explicit factories (`create_api_app(config)`, `create_webhook_app(config)`).
2. Remove import-time heavyweight singletons from API/webhook modules.
3. Keep existing endpoints/CLI commands unchanged via thin compatibility wrappers.

Exit criteria:
1. Modules import cleanly without side effects.
2. Engine can run without API/webhook dependencies loaded.

### Phase 2: Module Contracts and Capability Registry
1. Define `ModuleManifest` schema (`id`, `version`, `capabilities`, `deps`, `entrypoints`).
2. Add runtime `CapabilityResolver` used by engine and setup flows.
3. Migrate decision-node registry from static builtins-only to registry + entrypoint discovery.

Exit criteria:
1. Module can be added/removed without touching engine core code.
2. Missing capability errors are deterministic and contract-based.

### Phase 3: Packaging and Setup Selection
1. Short-term: map modules to `pyproject.toml` optional-dependency groups.
2. Setup wizard: prompt for module profile selection; persist to durable config.
3. Runtime boot checks selected module/capability availability before launch.

Exit criteria:
1. Clean install profile for engine-only.
2. API/CLI/webhook profiles install and run independently.

### Phase 4: Boundary Hardening
1. Expand dependency checker to include all package top-levels (eliminate `root` blind spot).
2. Add hard rules for module boundaries and anti-cycle checks.
3. Add architecture diff report in CI (new edge types, new cross-module imports).

Exit criteria:
1. New forbidden edge fails CI reliably.
2. Layer/module graph is measurable and stable between releases.

### Phase 5: Optional Contract-Breaking Cleanup (High Cost)
1. Remove legacy root shims after migration window.
2. Enforce strict port/adapters separation if chosen (`application` depends on contracts only).
3. Version and publish explicit breaking-change migration guide.

Exit criteria:
1. Zero legacy-shim imports.
2. Module boundaries enforced without exceptions.

## Priority Backlog (Concrete Next 10)

1. Fix logger workspace isolation and add multi-workspace test.
2. Add missing `return metrics` and integration test for real metrics reader.
3. Fix webhook `update_status` enum usage and add PR-open webhook test.
4. Repair path roots in platform architecture tests.
5. Add assertions that architecture scan roots exist and include files.
6. Pick one boundary policy for `application -> adapters` and align all enforcers.
7. Refactor API startup to factory-based composition root.
8. Refactor webhook startup to factory-based composition root.
9. Introduce initial module manifest schema in core contracts.
10. Add setup-time module selection + persisted module profile.

## OS-Idea Decision Guidance

Given current state, the practical path is:
1. Pause broad "OS" surface expansion.
2. Stabilize engine and modular seams first.
3. Re-introduce OS-level capabilities only as optional modules with clear use-case ownership.

This keeps progress compounding while minimizing expensive rework.

