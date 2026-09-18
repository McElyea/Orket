# Contract Delta: Architectural Truth API Composition B2

Status: Implemented B2 checkpoint

## Summary

- Change title: Import-pure API transport and application-owned runtime graph
- Owner: Orket Core
- Date: 2026-09-07
- Affected contracts:
  - `CURRENT_AUTHORITY.md` API runtime ownership
  - `docs/ARCHITECTURE.md` interface/application authority
  - `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
  - `orket/interfaces/api.py::create_api_app`
  - `orket/application/services/api_runtime_composition.py`
  - `orket/application/services/api_runtime_container.py`

## Delta

- Previous behavior:
  - importing `orket.interfaces.api` constructed one default FastAPI app,
    decision node, runtime state, runtime host, and engine;
  - mutable module aliases could replace owners for the default app;
  - outward stores/services and `ModelSelector` were constructed in the
    interface module;
  - tests and some scripts consumed the default app or patched owner aliases.
- Accepted B2 behavior:
  - importing `orket.interfaces.api` constructs no FastAPI app or runtime owner;
  - the module exports no default `app` or mutable owner alias;
  - every app is created explicitly and receives one complete
    `ApiRuntimeContainer` from the application composition root;
  - each container owns distinct engine, runtime state/event queue, stream bus,
    interaction manager, extension manager/catalog, extension runtime service,
    outward stores/services, and an app-container-held model-selector factory;
  - route callbacks retrieve existing owners from the active app context;
  - lifespan teardown cancels tracked tasks and closes the app-owned engine once;
  - production startup retains the app returned by `orket.runtime.create_api_app`.
- Compatibility impact:
  - `from orket.interfaces.api import app` and direct owner-alias patching are no
    longer supported;
  - tests and embedders must retain a factory-created app and access its
    `app.state.api_runtime_context`;
  - explicit runtime inputs may be supplied to `create_api_app(...)` for
    deterministic composition.

## Migration Plan

1. Move the full owner graph into
   `orket/application/services/api_runtime_composition.py`.
2. Expand `ApiRuntimeContainer` with the outward and model-selection owners.
3. Make interface getters read only from an explicit or active app context.
4. Remove default app creation, owner adoption, lazy owner construction, and
   interface-owned outward factories.
5. Migrate tests, lifecycle probes, and baseline collection to factory-created
   app contexts.
6. Remove `AT-EX-002` only after import-purity, structural construction,
   two-app isolation, concurrent request, and teardown proof passes.

## Validation Gates

1. A clean subprocess import observes zero FastAPI instances and zero named
   runtime owners in `orket.interfaces.api`.
2. Static inspection finds no protected-layer class construction in that module.
3. Two apps have distinct stores, event queues, engines, extension catalogs,
   services, roots, and outbound-policy snapshots.
4. Concurrent requests retain the correct app root.
5. Closing one app leaves the other app unchanged.
6. Repeated lifespan cycles leave every container closed with zero tracked tasks.
7. Interface tests, canonical pytest, touched Ruff/mypy, dependency direction,
   documentation hygiene, baseline regeneration, and diff checks pass.

## Rollback Plan

1. Rollback trigger:
   - production server startup cannot retain a factory result;
   - request context crosses apps;
   - app teardown leaks or closes another app's owner;
   - an interface route cannot resolve its app-owned dependency.
2. Rollback steps:
   - revert composition, interface, and caller migrations together;
   - restore `AT-EX-002` with the failed proof as evidence;
   - do not restore a default owner without explicitly restoring its ship-risk
     exception and compatibility contract.
3. Data/state recovery:
   - no durable schema or canonical path changes are introduced;
   - outward stores continue to use the configured control-plane database;
   - engine teardown is idempotent and does not delete durable state.

## Versioning Decision

- Version bump type: Patch when an implementation commit is prepared
- Effective date: 2026-09-07
- Downstream impact: code importing `orket.interfaces.api.app` must migrate to
  `orket.runtime.create_api_app(...)` or `orket.interfaces.api.create_api_app(...)`
  and retain the returned FastAPI instance.

## Subsequent factory migration (0.6.19)

The runtime transport-factory import paths above describe the original checkpoint.
Current callers use `orket.interfaces.runtime_entrypoints`, preserving application
capability admission. See
`docs/architecture/CONTRACT_DELTA_INTERFACE_COMPOSITION_C_2026-09-18.md`.
Historical release proof is not reinterpreted as proof of the new package.
