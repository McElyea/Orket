# Direct extension construction ownership

## Summary

- Owner: Orket Core.
- Date: 2026-09-20.
- Affected contracts: extension manager construction, extension control-plane
  composition and `CONTROLLER_WORKLOAD_V1.md`.
- Effective version: 0.6.40 (patch candidate; acceptance remains in the canonical plan).

## Delta

`ExtensionManager(...)` previously performed native path resolution and constructed
its control-plane storage directories even when called from an event-loop thread.
The synchronous control-plane builder likewise created directories directly.
The CLI, controller and API already own their preparation workers; direct
embeddings and several standalone async script bodies still entered the blocking
constructors. Retained pre-change probes show both constructors admitting this
event-loop path and their worker-based positive controls reaching actual SQLite.

Direct synchronous manager construction now refuses a running event loop with
`E_EXT_MANAGER_CONSTRUCTION_REQUIRES_WORKER`, before observing native paths or
creating directories. Callers on an event loop await the existing application
`prepare_extension_manager(...)`, which captures the invocation root and
environment before scheduling its retained worker. Synchronous CLI and worker
callers retain the constructor. This checks the current thread's running loop;
it does not certify arbitrary executors or prevent other synchronous operations.

Control-plane composition moves from `extension_workload_control_plane_service`
to `extension_workload_composition`. Its synchronous
`build_extension_workload_control_plane_service(...)` refuses a running loop with
`E_EXT_CONTROL_PLANE_CONSTRUCTION_REQUIRES_WORKER` before directory effects.
Async embeddings await `prepare_extension_workload_control_plane_service(...)`.
That surface binds relative project/database paths to the captured absolute
invocation root before scheduling the construction worker. The default database
remains `<project>/.orket/durable/db/control_plane_records.sqlite3`; an explicit
database still selects its own location. The composition change does not migrate
stores or change workload admission, effect, checkpoint or terminal semantics.
The synchronous builder also binds a relative database to its construction-time
working directory. The pre-change first database access could instead create a
schema in an existing database after a working-directory change. Regression proof
requires the selected database to be created and that competing store's bytes and
schema to remain unchanged.

Preparation retains its worker through repeated cancellation and caller timeout.
A native worker failure remains observable and takes precedence over interruption.
Created directories may remain after interruption or failure; no database schema
or workload is created merely by construction. The existing storage calls still
own schema creation. Threads have no hard-stop guarantee.

## Migration Plan

1. Replace direct event-loop `ExtensionManager(...)` calls with
   `await prepare_extension_manager(...)` from application
   `extension_catalog_commands`. Retain synchronous calls only outside a running
   loop. Direct `WorkloadExecutor` construction also reaches the guarded
   control-plane builder and must run outside the loop.
2. Import the control-plane builder from `extension_workload_composition`, or
   await its preparation surface. The retired internal builder import has no
   compatibility forwarding alias.
3. Preserve caller environment/root selection and all existing store/native lock
   identities. Migrate repository scripts and real SDK/legacy test callers in the
   same change; no deadline or accepted BT behavior changes are authorized here.
4. Require direct refusal controls, real SQLite positive controls, native directory
   refusal, captured relative paths, retained cancellation/timeout and the
   predeclared 0.5-second responsiveness bound under controlled filesystem holds.
   Exercise actual SDK/legacy/controller/CLI paths and affected source/installed
   package gates; retain earlier failures and platform blockers. Both Quality
   selections keep these regressions.

## Rollback Plan

Drain owned preparation before rolling back code and callers together under a new
patch version. Preserve created directories, catalogs, databases and native lock
identities. A return to unguarded event-loop construction reopens the blocking
boundary; it must not be described as an equivalent async-safe implementation.

## Versioning Decision

Patch checkpoint for a scoped internal construction boundary. Async direct
embeddings require the migration above. Catalog inspection, broader captured
submission/provider inputs, C/D purity/reachability, E quality/authority and CAP
acceptance remain separately open. This contract grants no hostile-code
containment, rollback of native effects or whole-lane acceptance.

Legacy action engine construction and required close now follow
`CONTRACT_DELTA_LEGACY_ACTION_ENGINE_D_2026-09-21.md`. The synchronous ConfigLoader
bridge and direct engine/pipeline/runtime-context construction now follow
`CONTRACT_DELTA_CONFIG_SYNC_BRIDGE_D_2026-09-21.md`; broader constructor and
caller reachability remains open.
