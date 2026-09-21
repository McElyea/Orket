# API run observation ownership and paths

Status: active bounded D contract delta; lane acceptance remains open.

`ApiRuntimeContainer.run_queries` owns log listing, token summaries, replay
listing and execution-graph handoff observations through `ApiRunQueryService`.
Its side-effecting `ApiRunLogReader` uses the application's captured absolute
project root and retains each native path/read worker through cancellation,
elapsed deadlines and shutdown. Worker failure remains visible even when
cancellation is pending. A deadline does not stop a native thread or promise an
immediate return; admitted work must settle before request ownership is released.

Pure record projections live in
`orket/core/contracts/run_observation_projection.py`. Default/run file ordering,
the distinct token/replay deduplication keys, model precedence/case, token
fallbacks, log filtering/pagination and handoff ordering retain their existing
semantics. Missing logs are empty observations; blank, invalid-JSON and non-object
lines are skipped. Native read failures are visible. This change does not repair
every malformed record-field behavior or make multiple file reads atomic.
Diagnostic records and handoff edges cannot establish accepted card completion,
graph execution truth or a canonical replay verdict. BT-3 graph inspection and
snapshot publication retain their existing authorities.

Targeted API replay uses the same owned `read_runtime_replay` service as the CLI.
The engine's replay service consumes its captured absolute workspace root;
relative internal service roots are refused. Workspace/observability, session,
issue, selected turn and artifact paths must resolve within their declared roots.
Log readers likewise validate default/runs roots, the requested run and each log
path. Invalid paths raise `PermissionError`, mapped to HTTP 400 by these API
routes. Missing targeted artifacts retain HTTP 404; partial target arguments and
interaction-session targeted replay retain HTTP 422. The UI boundary governance
check now exercises the authenticated log route instead of a removed private
path helper.

Containment checks cover the observed paths, including native directory aliases.
They are not descriptor-bound protection against hostile concurrent path changes,
hard-link provenance, an atomic filesystem snapshot, or CAP-2 isolation. Legitimate
artifacts remain under the captured roots; no new compatibility forwarding helper
is introduced. Sandbox log ownership now follows
`CONTRACT_DELTA_API_SANDBOX_LOGS_D_2026-09-21.md`. Other synchronous bridges,
captured inputs, adapter classification and complete async reachability stay open.

Proof: the canonical architectural-truth plan and `.tmp/d-api-run-observation/`.
Source and installed claims are recorded only after their corresponding checks.
Controlled file/SQLite/HTTP observations are distinct from model inference,
capacity proof, whole-suite coverage and Linux clock acceptance.
