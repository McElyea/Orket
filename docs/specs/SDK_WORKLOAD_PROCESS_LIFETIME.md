# SDK workload process lifetime

Last updated: 2026-09-28
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
remaining exchange files if execution or cleanup is uncertain. Removal can
partly or completely apply before a failed acknowledgement; `exchange_path` is
then a reference, not a guarantee that the directory or all files still exist.
No rollback, recreation, destructor, TTL or automatic removal retry repairs that
state. Operators must establish process termination before removal; retained
inputs may contain workload data and are not public diagnostics.

The host child retains its existing synchronous and coroutine workload handling.
For a coroutine result, native child composition prepares logging once from the
existing captured native logging-input authority and binds it inside the asyncio
task that awaits that coroutine. Preparation failure closes the not-yet-admitted
coroutine; the existing capability ExitStack still owns acquired resources and
the existing child error envelope remains authoritative. Synchronous workloads
keep native publication. Non-coroutine awaitables retain asyncio's existing
refusal. This does not change the synchronous SDK Workload helper/Protocol or
capability method signatures, and does not permit native-only provider bridges
on the event loop. Optional logging remains admission-only, without a new child
shutdown frontier. Contract: `docs/specs/LOG_WRITE_SETTLEMENT.md`.

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
Required observed-event publication retains its existing native owner. Actual
native publication failure, including native `CancelledError`, `SystemExit`,
`KeyboardInterrupt` or another `BaseException`, selects typed
`lifetime-observation` uncertainty with the original failure as cause. It retains
the unadopted exchange and prevents result reading/adoption, even if the physical
append preceded failure. Caller-only interruption after successful publication
keeps the existing confirmed-cancellation and exchange-removal behavior.
The event's workspace and built-in lifetime projection are selected before native
admission; the public caller's workspace was already captured before dispatch.
`sdk_workload_process_uncertain` records phase, retained exchange path and the
native observation when available through another owned worker. Publication
failure or interruption remains attached to the typed uncertainty; it cannot
convert unknown execution into an ordinary terminal failure or clean cancellation.

The uncertainty diagnostic contains native `BaseException` failures after settlement,
including fatal and native cancellation outcomes. It retains the exact secondary
as `diagnostic_error` and adds `Uncertainty diagnostic failed: <type>` to the
selected uncertainty. Caller interruption after a successful publication retains
that original cancellation as the secondary. Existing cause/context, prior notes
and remaining private exchange state remain. Its event capture occurs inside
that same protected diagnostic attempt. Required observation migration:
`docs/architecture/CONTRACT_DELTA_SDK_OBSERVATION_PUBLICATION_D_2026-09-28.md`.
Migration: `docs/architecture/CONTRACT_DELTA_SUPPORTING_DIAGNOSTIC_POLICY_D_2026-09-28.md`.

Exchange removal retains the existing native worker and identity checks. Native
removal failure, including cancellation or fatal exceptions, selects typed
`exchange-remove` uncertainty with the exact original failure as cause. This
policy applies even if deletion already changed the filesystem. It cannot return
success or permit generic no-effect terminal closeout. Supporting diagnostic
failure retains the existing exact secondary and typed note.

If the runner body already selected an error or cancellation, successful removal
preserves that outcome against later caller interruption through the shared
finalizer owner. Actual native removal failure still takes precedence as cleanup
uncertainty; native cancellation is not suppressed as later caller cancellation.
If the body completed normally, caller-only interruption during successful
removal keeps the existing cancellation/timeout behavior. An unrelated exception
handled by an awaiting caller cannot change which of these policies applies.
Executor admission raising cancellation before the native callback remains
outside the callback's native-failure observation. Migration and proof limits:
`docs/architecture/CONTRACT_DELTA_SDK_EXCHANGE_REMOVAL_D_2026-09-28.md`.

Artifact/provenance worker lifetime and confirmed-outcome preservation are owned
by `docs/architecture/CONTRACT_DELTA_WORKLOAD_PUBLICATION_D_2026-09-19.md`.
Cross-store atomicity, arbitrary workload recovery, transitive import provenance,
independent objective verification and capability acceptance remain separate work.
