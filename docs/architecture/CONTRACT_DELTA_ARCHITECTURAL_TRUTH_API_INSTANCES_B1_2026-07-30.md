# Contract Delta: Architectural Truth API Instances B1

Status: Implemented B1 checkpoint

## Summary

- Change title: Per-app API identity and lifecycle ownership
- Owner: Orket Core
- Date: 2026-07-30
- Affected contracts:
  - `CURRENT_AUTHORITY.md` API runtime ownership
  - `docs/ARCHITECTURE.md` interface/application authority
  - `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
  - `orket/interfaces/api.py::create_api_app`
  - `orket/interfaces/api_runtime_context.py`
  - `orket/runtime/policy/composition.py::create_api_app`

## Delta

- Current behavior:
  - `create_api_app(project_root=...)` replaces the context on one module-global
    FastAPI object and returns that same object;
  - module-global aliases can be adopted into whichever context is current;
  - API transport tasks and the engine do not have one app-owned teardown record;
  - two factory callers cannot remain live with distinct project roots.
- Accepted B1 behavior:
  - every `create_api_app(...)` call returns a new FastAPI object;
  - each result owns a distinct app context, runtime state, runtime host, engine,
    outbound policy snapshot, and tracked background-task set;
  - request, websocket, and lifespan execution resolve owners from the current
    ASGI app rather than a replaceable process-global current context;
  - lifespan teardown unsubscribes logging, cancels and awaits tracked background
    tasks, and closes the app-owned engine exactly once;
  - the module-default `app` plus existing test-facing owner aliases remain
    compatibility-only during B1 and may influence only that default app;
  - outward pipeline service/store extraction and complete alias removal are B2
    work and are not claimed by this delta.
- Why this break is required now:
  - a factory that returns the same mutable app cannot provide tenant, test, or
    lifecycle isolation;
  - B1 removes the shared-factory identity defect without combining it with the
    much larger compatibility-test and outward-service extraction.

## Migration Plan

1. Compatibility window:
   - `from orket.interfaces.api import app` remains available through B1;
   - module aliases remain test-facing compatibility for the default app only;
   - callers needing a configured root must retain the object returned by
     `create_api_app(...)`;
   - alias removal requires B2 proof and same-change test migration.
2. Migration steps:
   - add an application-owned API runtime container with idempotent teardown;
   - attach one container to each FastAPI instance;
   - add an ASGI app-context boundary used by HTTP, websocket, and lifespan paths;
   - register health, v1, middleware, and streaming routes on each new app;
   - change test fixtures and direct callers to retain factory results;
   - keep default-app aliases from crossing into non-default app contexts.
3. Validation gates:
   - `create_api_app(A) is not create_api_app(B)`;
   - both apps remain live concurrently with distinct roots, engines, runtime
     states, stream buses, interaction managers, and extension managers;
   - requests to each app observe their own project root under concurrency;
   - closing app A closes its engine/tasks without changing app B;
   - repeated construction and teardown leaves no tracked background tasks;
   - module import does not construct a second non-default app owner;
   - focused integration, canonical pytest, changed-file Ruff, dependency
     enforcement, documentation hygiene, and diff checks pass.

## Rollback Plan

1. Rollback trigger:
   - request/websocket context crosses app boundaries, a created app lacks routes,
     default-server startup regresses, or teardown changes another app.
2. Rollback steps:
   - revert the B1 factory/context middleware and fixture migration together;
   - restore the singleton characterization test and keep `AT-EX-002` active;
   - retain the contract delta as failed-attempt evidence.
3. Data/state recovery notes:
   - B1 changes in-memory ownership only;
   - no durable schema or path migration occurs;
   - engine close is idempotent and must not delete durable state.

## Versioning Decision

- Version bump type: Patch when an implementation commit is prepared
- Effective version/date: Implementation began 2026-07-30 and released in core
  `0.5.10` on 2026-09-07
- Downstream impact: factory callers must use the returned FastAPI object; the
  module-default app remains compatibility-only during B1
