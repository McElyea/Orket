# SDK workload process lifetime

Last updated: 2026-09-19
Status: Active contract; scoped source/installed proof recorded in the canonical plan
Owner: Orket Core

`WorkloadExecutor.run_sdk_workload` owns each admitted SDK invocation through
`run_sdk_workload_in_subprocess`. Request values are serialized before its first
await. Application supplies the native execution deadline; the default reuses
`DEFAULT_CHILD_TIMEOUT_SECONDS` (900 seconds). Direct host embeddings may pass a
finite positive `timeout_seconds`; workload input cannot change that limit.
Controller deadlines can interrupt the invocation earlier.

The runner uses `CommandProcessSupervisor` and the existing Windows Job or Linux
subreaper adapter. Unsupported native supervision fails closed. Cancellation,
repeated cancellation and caller timeout retain the admitted native owner until
its cleanup observation settles. Descendant cleanup precedes result adoption,
including when the workload leader returns while its children continue running.
The shared native capture limit remains 4 MiB across stdout and stderr. Native
deadline, output-limit and incomplete capture results do not authorize SDK success.
This is trusted execution lifetime ownership, not hostile-code containment or a
claim that remote effects can be terminated.

An owned storage worker creates and writes the private request/result exchange;
owned workers also read it and remove it. Cancellation waits for admitted workers.
The resource owner records its directory before writing, so cancellation during
creation cannot discard the only cleanup handle. Application preserves the
exchange if execution or cleanup is uncertain. No destructor or TTL removes a
retained exchange. Operators must establish process termination before removal;
retained inputs may contain workload data and are not public diagnostics.

SDK result adoption requires completed native execution, confirmed cleanup,
complete capture and a well-formed child result consistent with its exit code.
A valid child-reported workload error preserves the existing
`SdkSubprocessRunError` path. Missing, malformed or inconsistent results, native
timeout and output-limit failures preserve unresolved execution even when native
cleanup is confirmed: absence of an SDK report does not prove absence of effects.

`SdkSubprocessExecutionUncertain` carries the observed lifetime when available,
the failing phase, and the retained exchange path. The executor must propagate it
without manufacturing terminal failure or `side_effect_observed=False`. Existing
pre-effect `resume_forbidden` checkpoint and nonterminal control-plane records
remain authoritative. Confirmed cancellation also propagates without terminal
closeout. Neither outcome authorizes automatic replay or redispatch.
Confirmed SDK cancellation propagates the ordinary `asyncio.CancelledError` type,
retaining the native observation as its cause/event. This preserves caller timeout
conversion on Python 3.11 and 3.12. Controller deadlines return their existing
failed-child summary after cleanup while the child's control-plane run remains
unresolved; that summary is not a terminal child-run receipt.

`sdk_workload_process_cancelled` retains the existing `owned_command.v1` native
observation before cancellation propagates. Normal native returns emit
`sdk_workload_process_observed` with that same schema before result adoption.
These are lifetime observations, not workload success or durable effect receipts.
Failures to publish/read/clean up after dispatch preserve uncertainty.
`sdk_workload_process_uncertain` records phase, retained exchange path and the
native observation when available through another owned worker. Publication
failure or interruption remains attached to the typed uncertainty; it cannot
convert unknown execution into an ordinary terminal failure or clean cancellation.

Artifact/provenance worker lifetime and confirmed-outcome preservation are owned
by `docs/architecture/CONTRACT_DELTA_WORKLOAD_PUBLICATION_D_2026-09-19.md`.
Cross-store atomicity, arbitrary workload recovery, transitive import provenance,
independent objective verification and capability acceptance remain separate work.
