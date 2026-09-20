# API construction ownership and captured startup inputs

## Summary

- Change title: own API runtime preparation inside the application lifespan.
- Owner: Orket Core.
- Date: 2026-09-19.
- Affected contracts: `API_RUNTIME_LIFECYCLE.md`, runtime entrypoint composition,
  captured settings, runtime-store binding and API request admission.
- Status: implemented in 0.6.39; scoped verification and remaining limits are recorded in the canonical plan.

## Delta

The retained pre-change synchronous API factory constructed the complete runtime graph, read
configuration and created storage directories before lifespan ownership began.
A retained public-factory observation with a controlled 0.8-second native directory
hold produced a 1.078-second event-loop gap against a 0.5-second bound. The graph
also has constructor inputs that independently observe process environment/cwd.

The synchronous ASGI factory returns the transport application with captured
construction inputs. Runtime graph preparation and outbound-policy file reads
belong to an application-owned worker entered by the lifespan. The public factory
signature and module-profile authorization remain; this is not a second runtime
composition authority or an asynchronous ASGI factory.

Factory inputs capture the invocation cwd, selected project path, environment and
runtime settings/preferences. Existing settings bootstrap rules remain: bootstrap
before starting an event loop or bind runtime settings explicitly. Synchronous
pre-loop settings bootstrap may read persistence; an event-loop caller without
the required bound settings fails rather than synchronously inspecting files.
Construction does not mutate process environment to simulate captured inputs.

The captured inputs select authentication, CORS, outbound policy location, engine
and extension settings, manager roots, subordinate store roots, governed-agent
configuration, exporter configuration and provider/voice construction. Runtime
composition passes these values through the relevant constructors. Filesystem
assets are observed through owned preparation at their selected paths; this does
not freeze an entire external filesystem tree at factory invocation.

HTTP and WebSocket admission remains closed until preparation and initialization
succeed. Pre-start, starting, failed-start and closed applications return HTTP 503
or close WebSockets before acceptance. The published runtime context is available
after preparation, but context availability alone does not authorize requests.
Shutdown closes admission before retaining existing request/background cleanup.
A factory result owns one lifespan; another start requires a new application.

Cancellation and caller timeout retain the preparation worker until settlement.
Fully constructed resources remain owned until transfer to the runtime container
or verified cleanup. A later composition failure closes already acquired graph
resources. Worker and cleanup failures remain failures, with the original error
retained; a timeout is not a hard stop. Directory or migration effects may remain.
Constructors that fail before returning an acquired resource require their own
cleanup; this change cannot infer absence of internal partial effects.

Existing catalog/project/durable-root and persistent-store sharing semantics
remain. No implicit store migration, tenant isolation, provider admission or
hostile-code containment guarantee is added.

Reload requires the ASGI lifespan protocol. Worker startup/teardown failure yields
a nonzero worker result; the parent refuses replacement after failed cleanup and
reports unexpected worker exit instead of remaining idle without a serving worker.
Parent cleanup still joins the worker and releases its listener. Repeated signals
do not bypass an unfinished startup, active request or cooperative cleanup.

## Migration Plan

1. Compatibility window: effective in the versioned checkpoint below; no implicit
   eager-construction or lazy forwarding compatibility path is retained.
2. Embeddings must run the application's lifespan before issuing requests or
   consuming runtime services. Tests that inspect construction or initialization
   must observe the actual preparation/initialization boundary. Synchronous ASGI
   server factories remain supported; canonical server and reload paths have live
   verification with retained cleanup.
   The canonical server now explicitly binds settings and preferences at pre-loop
   bootstrap; a spawned worker's later in-loop `server:app` import consumes those
   snapshots. This fixes the retained `SettingsBridgeError` startup counterexample.
   Canonical reload now uses a process-shared stop event and joins the old worker
   before replacement. Repeated console signals request normal close without
   Uvicorn's lifespan-skipping forced exit. Native Windows source reload passed
   with Uvicorn 0.52.4 and the declared minimum 0.27.0, including both lifespan
   shutdowns and an empty retained native job. Historical normal Windows/Linux
   startup and Linux reload observations predate the new supervisor. The final
   source cohort passes 1,001 cases. Windows Python 3.11/3.12 pass all 1,001;
   Linux 3.11 passes 1,000 with one Windows junction skip. Both Linux 3.12
   attempts retain 999 passes, one failure and one skip due to observed
   wall-clock discontinuities; full four-cell acceptance remains open.
   Real StatReload, active work, startup interruption,
   repeated stop requests and failed cleanup are included. The minimum/current
   Windows observations do not establish every intermediate Uvicorn version
   or optional watcher backend. There is no new startup/shutdown hard-stop
   guarantee. The canonical plan retains all failures and verification limits.
3. Validation gates: captured input rotation across preparation, controlled native
   read/write holds, cancellation/repeated cancellation/timeout, native refusal,
   acquired-resource cleanup, pre-start HTTP/WebSocket refusal, actual request and
   shutdown behavior, distinct applications, module policy and preserved A/B/BT
   guarantees. Test the affected source and fresh installed Windows/Linux Python
   3.11/3.12 paths, package origins/bytes and actual server startup/reload. Report
   structural checks separately from live behavior.

## Rollback Plan

1. Trigger: preparation, request ownership, storage selection or shutdown violates
   the documented contract.
2. Drain startup and runtime owners before restoring factory, lifespan, callers
   and captured-construction interfaces together under a new patch version.
3. Preserve created directories, catalogs, migration artifacts and databases.
   Cleanup of runtime resources does not establish rollback of filesystem effects.
   Restoring eager composition reopens the retained blocking counterexample.

## Versioning Decision

- Version bump type: patch under the active architectural-truth remediation lane.
- Effective version/date: 0.6.39 / 2026-09-20.
- Downstream impact: embeddings and tests must stop relying on constructed runtime
  services before lifespan; SDK/wire schemas and ASGI factory signature are unchanged.
