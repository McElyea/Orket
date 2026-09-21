# Gitea loop input selection and ownership

Status: Active contract for the 0.6.55 candidate
Last updated: 2026-09-20

The public Gitea loop retains its existing readiness and numeric-limit policy.
Runner construction captures the environment, invocation root and organization
limit tokens. Supplied `RuntimeConstructionInputs` are authoritative, including
an empty environment; their settings snapshot replaces an ambient settings read.
Without that snapshot, the loop collects settings asynchronously after capturing
its other inputs. An existing runner retains its selection; construct a new
runner to adopt changed environment or organization values.

Limit precedence remains explicit argument, captured environment, captured
organization rule, observed settings, then the existing default. Preserve the
numeric resolver's existing lexical behavior, including numeric zero as absent
and the string `"0"` as an admitted token. Relative database and summary paths
remain bound to the captured invocation root through later cwd changes.

Pipeline entry constructs its runner before initialization awaits and supplies
its selected runtime clock, construction snapshot and control-plane database.
Standalone callers may supply those same optional ports. Worker execution,
lease and reservation owners receive the selected UTC provider; the coordinator
receives the selected monotonic provider. Observations remain fresh at their
existing points; no single timestamp replaces an invocation's later observations.
An observed remote lease acquisition timestamp remains the execution creation
timestamp when present; the selected UTC provider remains its fallback.

Worker construction, including path migration and HTTP-client construction,
runs in an owned worker. A successfully constructed HTTP adapter is registered
before subsequent composition can fail. Interruption retains the worker until
it settles, prevents workload admission and closes any acquired adapter. The
loop closes its adapter on normal completion, failure, timeout and cancellation.
Repeated cancellation retains cleanup ownership; cleanup failure is reported,
and an earlier failure remains available when cleanup also fails.

Summary publication captures its target before work awaits. Directory creation
and the existing JSON write run in an owned worker. Interruption waits for that
worker to settle; write failure is not reported as a successful summary. This
does not make the summary atomic with SQLite or remote Gitea effects.
An unresolved typed runtime outcome still refuses successful loop completion.
Cleanup closes the client while retaining unfinished local and remote authority;
it does not invent a terminal failure, release the remote lease or publish a
successful summary for that outcome.

Claim-failure clock selection, reservation rollback refusal, terminal truth and
remaining non-atomic boundaries are governed by
`CONTROL_PLANE_TERMINAL_AUTHORITY.md`. No timestamp is repaired to make a lease
guard pass. Existing terminal histories and unknown remote outcomes are retained.

Acceptance requires actual local SQLite and HTTP-client observations, owned
construction/write cancellation and cleanup-failure checks, and a real owned
Gitea flow through the installed public loop with teardown. Held-worker tests use
the existing predeclared 0.5-second concurrent-response bound. They do not promise
a universal filesystem or network completion deadline. Controlled settings,
remote fixtures and clocks must be identified separately from real Gitea proof.
The canonical plan records measured results and unavailable environments; this
contract alone does not establish acceptance.
