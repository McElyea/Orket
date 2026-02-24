# MR-2 Requirements: Engine-First Modular Composition

Date: 2026-02-24  
Type: modularization foundation (contract-preserving where possible)

## Objective

Establish a composition model where `engine` is always included and other capabilities are optional/selectable at install/setup time.

## In Scope

1. Composition root/factory model for API, CLI, webhook surfaces.
2. Removal of heavyweight import-time side effects from interface modules.
3. Capability and module manifest contracts.
4. Setup-time module selection persisted in durable config.
5. Optional dependency groups mapped to module profiles.

## Out of Scope

1. Full monorepo-to-multi-repo split.
2. Breaking external endpoint contracts.
3. Kernel/OS feature expansion unrelated to modularity seams.

## Functional Requirements

1. Engine core boots without API/webhook modules installed.
2. API module can be enabled independently of webhook module.
3. Webhook module must fail fast with explicit capability/config errors when selected but misconfigured.
4. Module selection must support at least:
- `engine-only`
- `engine+cli`
- `engine+api`
- `engine+api+webhook`

5. Decision node registry must support module-provided implementations through explicit registration contracts.

## Contract Requirements

1. Define `ModuleManifest` contract with:
- `module_id`
- `module_version`
- `capabilities`
- `required_modules`
- `entrypoints`
- `contract_version_range`

2. Define deterministic error payload for unresolved capability/module.
3. Preserve existing engine invocation contracts.

## Quality Requirements

1. Startup behavior deterministic for each module profile.
2. No import-time network calls or mandatory env validation in modules not selected.
3. Test matrix exists for at least 4 module profiles.

## Acceptance Criteria

1. Engine-only profile runs without importing API/webhook heavy paths.
2. Setup flow writes selected module profile and boot logic honors it.
3. Module manifest/capability checks are enforced at startup.
4. Existing API/CLI contracts remain backward compatible.

