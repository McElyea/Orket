# MR-2 Implementation Plan: Engine-First Modular Composition

Date: 2026-02-24  
Execution mode: seam-first refactor, API-compatible

## Phase 1: Composition Root

1. Introduce explicit factories:
- `create_engine(config)`
- `create_api_app(config)`
- `create_cli_runtime(config)`
- `create_webhook_app(config)`

2. Replace import-time singleton initialization with lazy/factory wiring.
3. Keep compatibility wrappers in existing entry modules.

## Phase 2: Module Contracts

1. Add core module manifest schema and loader.
2. Implement capability resolver at startup.
3. Add deterministic startup errors for:
- missing module
- missing capability
- incompatible contract version

## Phase 3: Profile Selection and Packaging

1. Define initial install/setup profiles:
- `engine-only`
- `developer-local`
- `api-runtime`
- `api-webhook-runtime`

2. Map profiles to optional dependencies in `pyproject.toml`.
3. Add setup wizard step to persist selected profile.

## Phase 4: Tests and Hardening

1. Add startup tests per profile.
2. Add import-side-effect tests (module import should not start heavy runtime).
3. Add backward compatibility tests for existing API/CLI entrypoints.

## Validation Commands

1. `python -m pytest -q tests/interfaces tests/application tests/platform`
2. `python -m pytest -q tests -k \"module or startup or profile\"`
3. `python scripts/check_dependency_direction.py`

## Work Slicing Guidance

1. PR slice A: factory introduction + wrappers.
2. PR slice B: module manifest and capability resolver.
3. PR slice C: setup/profile wiring.
4. PR slice D: profile matrix tests and docs.

## Risks and Mitigation

1. Risk: startup regressions from moved initialization.
- Mitigation: keep wrappers and preserve existing call signatures.

2. Risk: hidden dependency assumptions in interfaces.
- Mitigation: profile-matrix tests and explicit capability errors.

