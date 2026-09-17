# Captured API authority and system observations

## Summary
- Owner: Orket Core.
- Date: 2026-09-17.
- Status: corrected full selected source suite, four complete installed gates and
  fresh llama.cpp regression pass. Whole-plan acceptance and historical failures remain open.
- Affected contracts: API authentication, startup security, CORS, calendar inputs,
  explorer containment, board roots and filesystem worker ownership.

## Delta
- Application composition captures an immutable environment mapping for API key,
  security profile/mode, insecure bypass, startup checks and CORS. HTTP and both
  WebSocket routes use `ApiAuthenticationService`; a replaceable decision node
  cannot accept a wrong key or override authentication failure responses.
- The interface factory accepts an explicit `environment` mapping; omission
  captures process settings after environment bootstrap. Caller mutation and later
  process changes cannot rotate an existing app's key or change those policies.
  A new application is required to adopt changed settings. Other runtime/provider,
  streaming and store settings remain separate composition inputs.
- `ApiSystemQueryService` owns board, explorer, metrics and calendar queries.
  Its calendar captures the EOS baseline and timezone; system timestamps use the
  app's injected runtime clock. Pure EOS calculation lives in
  `orket/core/contracts/eos_calendar.py`. The legacy utility delegates to that
  calculation and retains its historical ambient settings/cache contract.
- Storage resolves explorer and metrics paths in retained workers. Explorer
  traversal outside the app root returns 403. Missing directories retain the
  ordinary empty response; filesystem failures are not reported as empty success.
  Metrics traversal returns 400; default-workspace fallback stays within the app root.
- Board loading uses the selected project root for config/model assets and
  artifacts, including cross-department assets. The engine passes its config root.
  Synchronous callers may supply `project_root`; omission uses the invocation
  directory. Explicit-root auto-fix reconciles that root's model/workspace.
- Filesystem observation workers remain owned through caller cancellation and
  timeout. API shutdown waits for admitted workers; worker failure takes precedence
  over cancellation. No thread termination deadline or OS fencing is added.

## Migration
1. Configure authentication at app construction, then replace the app to rotate
   credentials or adopt changed security settings. Keep supplied credentials private.
2. Remove custom API decision-node authentication, query-key, board/filesystem,
   sprint and obsolete CORS methods. Those methods are retired, with no delegation
   shim. Presentation recommendations remain strategy-owned.
3. Use the application query service for observations. Supply environment and
   runtime inputs when constructing it directly. Direct synchronous board callers
   needing a different project must provide `project_root` explicitly.
4. Do not treat an elapsed caller timeout as proof that a filesystem worker stopped.

## Proof and limits
- Retained pre-change ASGI counterexamples show cross-app key drift, a strategy
  accepting an invalid key and a strategy bypassing explorer containment. A separate
  real-file counterexample shows two explicit-root boards returning empty inventories.
- Selected checks exercise real ASGI HTTP/WebSocket routes, real files and actual
  TCP HTTP startup/shutdown. Controlled barriers cover cancellation, timeout and
  worker failures; heartbeat responsiveness is bounded at 0.5 seconds using an
  independent elapsed-time observation. WebSocket checks are ASGI, not TCP proof.
- Composition/bootstrap, other system I/O, registry mutability, arbitrary strategy
  invocation recommendations and the complete concurrency matrix remain C/D work.
  Resolved-path containment is not an OS sandbox or fencing against concurrent
  external path replacement. No provider/capability guarantee is expanded here.
- Existing security telemetry drift remains: enabling the insecure-bypass flag logs
  that authentication is disabled even when a configured key still requires authentication.
  This moved warning retains its prior semantics; C/D owns correcting that claim.
- Exact current results and remaining gates belong in the architectural-truth plan.

## Versioning
- Candidate core `0.6.9`; SDK remains `0.7.0a1`.
- Retired internal strategy methods and captured settings require migration.
  Local work-hours commits do not establish publication or release readiness.
