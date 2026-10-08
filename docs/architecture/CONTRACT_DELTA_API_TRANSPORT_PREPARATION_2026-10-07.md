# API transport preparation before readiness

## Summary
- Change title: Own schema and included-route preparation during API startup.
- Owner: Orket Core
- Date: 2026-10-07
- Affected contract: `docs/specs/API_RUNTIME_LIFECYCLE.md`.

## Delta
- Previous behavior: startup validated authentication and initialized the runtime,
  then marked the API ready without preparing the transport schema. FastAPI
  0.142.2 lazily compiled included-router dependencies on the first request.
- Behavior: the interface captures its bound public `app.openapi` callback before
  preparation awaits. The application startup owner executes it in its retained
  native worker after authentication validation, before engine initialization and
  readiness. Cancellation drains admitted preparation; native failure prevents
  readiness and takes precedence over later caller cancellation.
- Reason: the retained full Quality failure measured 0.6115s replay admission
  against the unchanged 0.5s responsiveness assertion. Native profiling found
  354 dependency constructions and 0.1678s included-route compilation on the
  request's event loop; direct native SQLite/path observations were quick.
  This demonstrates avoidable first-request blocking, but does not reconstruct
  the historical scheduler state or prove that every delay has that cause.

The public callback uses FastAPI's own schema/cache and route authorities; no
private route traversal, duplicate compiler or synthetic warm-up request is added.
The inspected upstream [schema builder](https://github.com/fastapi/fastapi/blob/0.142.2/fastapi/openapi/utils.py)
traverses the [included route contexts](https://github.com/fastapi/fastapi/blob/0.142.2/fastapi/routing.py).
Configure routes and schema callbacks before lifespan entry. Dynamic route mutation
and custom callbacks that bypass preparation remain outside this guarantee.

## Migration plan
1. Compatibility window: none for internal `api_runtime_lifespan` callers; its
   transport preparation callback is required. The sole production caller migrates
   in this change; public factory and HTTP/WebSocket schemas remain unchanged.
2. Migration: embeddings still configure and enter one lifespan per app. A partial
   schema after failed startup cannot grant readiness; create another app to retry.
3. Gates: native schema/thread/first-request controls, retained startup cancellation
   and failure controls, original replay responsiveness and ownership assertions,
   real server bootstrap/reload and installed public API flow, canonical typing,
   lint and whole-suite coverage. Keep both existing Quality selections.

## Rollback plan
1. Trigger: route/schema compatibility or owned startup regression.
2. Revert the callback port and its caller together; retain failed proof.
3. Earlier graph preparation may have created directories/databases. This change
   adds no durable schema storage or migration. Cleanup still owns acquired resources.

## Versioning decision
- Patch: core 0.7.8 candidate; publication is a separate action.
- Downstream action: internal lifespan callers supply their captured callback;
  public app users keep the existing construction/lifespan protocol.
- Native Mac/Metal acceptance remains absent and is not inferred from Windows proof.

Native Windows scoped/callback capture, real server bootstrap/reload, fresh installed
API/process controls and canonical whole-suite coverage passed. The latter retained
13,252 passed, 93 skipped and 89.25% with unchanged assertions. Source remained
frozen through settlement. Exact scope and the incomplete worker measurement:
`docs/releases/0.7.8/PROOF_REPORT.md`. No historical scheduler reconstruction is claimed.
