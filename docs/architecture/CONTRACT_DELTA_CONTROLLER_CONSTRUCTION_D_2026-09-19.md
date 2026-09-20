# Controller construction and captured manager inputs

Owner: Orket Core. Date: 2026-09-19. Effective version: 0.6.38 (patch).
Status: active scoped contract; verification and checkpoint disposition remain in the
canonical architectural-truth plan. This does not close C/D.

## Delta

Previously, the synchronous controller runtime builder constructed its dispatcher
and extension manager immediately, performing path resolution and directory writes
inside an async workload. Retained native directory holds block the event loop
beyond the declared 0.5-second responsiveness bound. The CLI already used an owned
construction worker, but a queued worker observed later environment/cwd values;
a retained counterexample constructs storage under the rotated invocation root.

`build_controller_workload_runtime` remains synchronous and returns runtime hooks
without constructing a manager, resolving paths or creating directories. It captures
the invocation cwd, controller environment and relevant context/catalog selections.
The async dispatch hook captures its envelope, workspace and department before
awaiting owned manager preparation, then constructs a dispatcher with that explicit
manager. Relative workspaces bind to the captured invocation cwd. Each dispatch
owns a separate manager. Disabled controller invocations
do not prepare a child manager. Controller enablement, department restrictions and
caps use the captured environment; later invocations can capture updated policy.

`ControllerDispatcher` requires an explicit `extension_manager`; omitted or `None`
managers are no longer implicit construction requests. The application surface
`prepare_extension_manager` captures environment/cwd before scheduling its retained
worker. Manager construction and the canonical default catalog resolver accept
those explicit inputs, preventing queued preparation from selecting later roots.

Existing root selection semantics remain: catalog and durable-root environment
paths bind to the invocation cwd; an explicitly supplied project root selects the
workload project independently. Controller context workspace selects the project
when an explicit payload/context catalog is supplied, as before. This delta does
not change global/default store policy or introduce implicit project migrations.

## Migration and validation

Direct dispatcher embeddings must prepare a manager outside the event loop or
await `prepare_extension_manager(...)`, then supply it to the dispatcher. No
synchronous compatibility constructor is retained. Existing controller workload
runtime builders and SDK entrypoints keep their signatures and wire schemas.

Keep real nested controller/CLI paths, queued input rotation, native directory
refusal, retained cancellation/timeout and event-loop responsiveness checks in
the affected source/installed gates and both Quality selections. Synthetic holds
must be identified as controlled latency, not natural filesystem performance.

## Limits and rollback

Owned threads have no hard-stop deadline. Interruption waits for preparation to
settle and can retain created directories. A worker failure takes precedence over
interruption; failed preparation must not dispatch a child. Direct manager and
control-plane construction, wider API composition and other invocation input
boundaries still require D work. No hostile-code, provider or crash-atomicity
guarantee is added.

Drain in-flight preparation before rollback. Restore callers and constructor
contracts together under a new patch version, preserving existing directories and
catalogs. Reverting this delta reopens blocked event loops and late input selection;
do not classify partial directory creation as absence of effects.
