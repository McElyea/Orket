# Native command and verification process lifetime

Status: Active durable contract
Last updated: 2026-09-13
Owner: architectural-truth BT-4

## Scope and authority

`RuntimeVerifier` admits configured commands through the application service
`CommandProcessSupervisor`. `OutwardConnectorService` supplies the same owner to
the built-in command adapter through the core `CommandRunner` port. Builtin host
Piper receives the same application owner; its speech-specific configuration and
response boundary live in `PIPER_RUNTIME_CONTRACT.md`. The execution adapter starts a dedicated,
package-owned supervisor using the active interpreter with `-I -S`. Its OS
backend establishes descendant ownership before releasing command execution.
The result type is `orket/core/contracts/owned_command.py`.

This contract covers native commands reached through `RuntimeVerifier`, including
its card acceptance caller, and native/Docker fixtures through the async
`FixtureVerificationService` used by `Orchestrator.verify_issue`, and the outward
`run_command` connector, and builtin host Piper CLI synthesis. Other process
helpers, epic terminal-state propagation, host-death recovery and hostile-code
containment remain separate BT-4/CAP-2 obligations. A passing command does not
establish card completion.

## Admission and termination

1. Commands retain argv-only admission, workspace-contained working directories,
   caller-selected environment and the existing command timeout. The application
   stops admitting later verifier commands after the first command failure.
2. Windows execution creates a suspended process, assigns it to a retained Job
   Object without breakaway flags, then resumes its initial thread. The job uses
   kill-on-close. Cleanup queries active job processes; sending termination alone
   is not confirmation. Assignment failure never releases the suspended command.
3. Linux execution establishes a child subreaper and readable direct-child
   inventory before dispatch. A single supervisor thread signals and reaps its
   children, including adopted descendants that changed session or process group.
   Cleanup confirms `waitpid` reports no children; an empty `/proc` listing alone
   does not establish exit.
4. Command completion, failure, timeout and owner cancellation all stop remaining
   descendants. Linux sends TERM then escalates to KILL after 250 ms. Windows
   terminates the job. The OS cleanup budget is three seconds, followed by bounded
   stream-thread joins. Repeated cancellation cannot skip the application's
   cleanup wait. Cancellation propagates after that wait, with a lifetime event.
5. The transport allows six seconds for an explicit stop acknowledgement. On
   expiry it attempts to terminate the supervisor and allows one further second
   for exit/capture. Missing acknowledgement remains unconfirmed even if the
   supervisor exits. In particular, killing a Linux subreaper does not prove its
   descendants stopped. No timeout path waits indefinitely for inherited pipes.
6. Shutdown that cancels the caller and collector must retain collected bytes and
   await the bounded cleanup owner. Abrupt host death, OS refusal and external
   process brokers are not confirmed-cleanup claims. The containing runtime must
   retain uncertainty rather than equate an exception with safe terminal state;
   convergence of those epic consumers remains required work.

## Observation and output

`process_lifetime` has schema `owned_command.v1`: `reason`, `cleanup_confirmed`,
`capture_complete`, `backend`, `transport_pid`, nullable `supervisor_pid`, nullable `command_pid`, and
diagnostics. Backend is `windows_job`, `linux_subreaper`, `unavailable`, or
`unconfirmed` when the transport cannot validate the report. PIDs are diagnostic
observations, not durable authority to signal a later process with the same PID.

Reasons are `completed`, `timeout`, `cancelled`, `launch_failed`,
`cleanup_unconfirmed`, `output_limit`, or `capture_incomplete`. Completed commands
retain their actual return code. Timeout maps to verifier exit 124, launch failure
to 127, and other non-completed reasons to 125. Only completed, fully captured,
confirmed-cleanup execution can produce a passing command receipt.

Each raw stream defaults to a 4 MiB retention bound. Application command owners
can explicitly admit an integer `output_limit_bytes` from 1 byte through 64 MiB;
the transport and isolated worker share validation before dispatch. Piper uses
64 MiB for PCM; verifier and outward callers retain the 4 MiB default. Crossing
the admitted limit stops execution and
fails with `output_limit`; clipped bytes cannot satisfy acceptance. Existing
2,000-character diagnostic projections remain in force. Their byte count/hash
describe retained raw bytes, not an uncaptured suffix. A false
`capture_complete` forbids interpreting them as a complete stream. For dispatched
commands, timeout and supervision diagnostics are structured fields, never
fabricated process stderr. Pre-dispatch admission/launcher errors retain the
existing diagnostic projection without captured-stream metadata.
The supervisor protocol is separate from command stdout/stderr. It validates its
schema, a fresh request correlation nonce, and successful transport-process exit
before trusting cleanup confirmation. Windows virtual-environment launchers can
have a different PID from the executing interpreter; `transport_pid` records the
launched process and `supervisor_pid` records the actual supervisor. Unknown
supervisor identity is null. The nonce binds this private transport, not a
deterministic decision or authority to signal arbitrary PIDs.

`verification_process_cancelled` (verification callers) or
`outward_command_cancelled` (outward callers), or `piper_process_cancelled`
(host Piper callers) records the lifetime observation
before caller cancellation propagates. `CommandProcessCancelled` remains an
`asyncio.CancelledError` and carries the observed `OwnedCommandResult` in
`lifetime`, including unconfirmed cleanup. Event delivery is diagnostic, not a durable recovery
journal or proof of completed epic publication.

## Outward command execution

The built-in executor requires an explicit `CommandRunner`; application
composition selects the shared supervisor. It retains argv-only command parsing
and the workspace working directory. The old verification-specific supervisor
module and exception names are removed; there is one native owner implementation.

Admitted `run_command` execution results and event `result_summary` include the
`process_lifetime` observation. Success requires completed execution, actual exit
code zero, complete capture and confirmed cleanup. Nonzero exit, launch failure,
output limit and confirmed timeout remain failed/timeout observations. Return
codes are actual nullable process return codes; verifier-specific 124/125/127
projections do not apply to connector results.
Pre-dispatch command parsing failures retain their existing error result without
inventing process lifetime evidence.

Each stream retains at most 4 MiB raw bytes. Counts describe captured bytes before
UTF-8 replacement decoding; previews retain at most 256 characters. An output
limit stops the tree and returns failure with `capture_complete=false`; the count
does not describe an uncaptured suffix. Capture failure or missing cleanup
confirmation raises `CommandExecutionUncertain` with its original lifetime.
Cancellation carries `CommandProcessCancelled.lifetime`. When the application
deadline translates cancellation into timeout, it preserves that observation;
unconfirmed cleanup remains uncertain rather than a normal timeout receipt.
The deadline boundary normalizes the exception type for Python 3.11/3.12's exact
`CancelledError` match, retains the typed observation separately, and restores it
for external cancellation. Additional caller cancellation during cleanup takes
precedence over deadline translation.

Supporting `outward_connector_interrupted` telemetry includes the lifetime when
available, but is not recovery authority. The durable effect owner retains
dispatch intent without a fabricated receipt on cancellation or uncertainty.
The authenticated API maps command uncertainty to HTTP 409
`E_COMMAND_EXECUTION_UNCERTAIN`; later approval of that same dispatch remains
HTTP 409 `E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN`. Cleanup confirmation describes
process termination, not reversal or absence of command side effects.
Receipt publication retry reuses the original complete receipt, lifetime and
timing. Historical receipts lacking lifetime stay unchanged and establish no
descendant cleanup guarantee. See
`docs/architecture/CONTRACT_DELTA_OUTWARD_COMMAND_LIFETIME_BT4_2026-09-13.md`.

## Fixture execution cutover

The fixture cutover follows
`docs/architecture/CONTRACT_DELTA_FIXTURE_LIFETIME_BT4_2026-09-13.md`; its current
proof state remains in the canonical architectural-truth plan.

1. `FixtureVerificationService.verify` owns asynchronous fixture execution for
   `Orchestrator.verify_issue`. It supplies explicit environment/time inputs and
   filesystem observations to one deterministic fixture policy/result authority.
   It applies scenario changes only after the observed execution outcome.
2. Synchronous `FixtureVerifier.verify` and `VerificationEngine.verify` refuse
   before any effect with an explicit migration error. They are temporary
   tombstones under `BT4-FIXTURE-SYNC-RETIRE`, not functioning fallback executors.
3. Native fixtures reuse owned command execution, including bounded raw capture.
   The existing fixture runner remains support evidence; a passing fixture is not
   sufficient card completion authority. Invalid modes fail closed. Production
   native execution still requires the explicit unsafe override.
4. Docker mode retains its unique name and owner before `create`, verifies the
   immutable container ID and owner labels, and attaches only to that ID. It
   inspects actual container state and exit status rather than equating a Docker
   client exit with a fixture result. Removal targets the retained ID, never an
   unverified name or a foreign resource discovered after a lost response.
5. Every Docker path, including failed creation, timeout and cancellation, inspects
   for an owned resource and attempts bounded cleanup. Confirmed cleanup requires
   successful daemon observation of absence. CLI failure, daemon unavailability,
   foreign ownership and missing acknowledgement remain explicit uncertainty.
   Repeated cancellation cannot bypass the cleanup owner.
6. `VerificationResult.process_lifetime` retains native or container lifetime
   observations. Cancellation propagates with its observation and does not publish
   new verification status. Historical results without this field remain
   historical, with no invented cleanup evidence. Durable epic fencing for unknown
   effects remains a separate required BT-4 gate.

Container observations use `owned_container.v1`: name, owner ID, nullable immutable
container ID and actual exit code, reason, cleanup/capture confirmation, diagnostics,
and each native Docker command's lifetime with operation and CLI return code.
`completed` requires observed terminal container state and agreement with the
attached client's exit code. Other reasons include `launch_failed`, `timeout`,
`cancelled`, `observation_failed`, `cleanup_unconfirmed`, and native capture failures.
Cleanup commands each have a three-second execution budget plus the native
supervision cleanup bounds; the finite cleanup sequence is independent of the
fixture execution timeout. A missing create acknowledgement with an empty name
listing remains uncertain because the daemon may still have an in-flight create.

`FixtureContainerCancelled` carries `OwnedContainerResult`. The application emits
`fixture_verification_cancelled` after cleanup and propagates cancellation.
`FixtureVerificationUncertain` carries an unconfirmed lifetime and emits
`fixture_verification_uncertain`; neither path publishes scenario changes or
`last_run`. These events are diagnostic observations, not a durable recovery owner.
Historical stored results are not migrated to fabricate the additive nullable field.

HTTP verification has its own captured-input and client-lifetime contract in
`docs/specs/SANDBOX_HTTP_VERIFICATION.md`. The shared fixture executable payload
lives in `orket/adapters/execution/fixture_runner.py`; its process/container policy
and native teardown obligations above are unchanged.

## OS references

The Windows backend follows [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[job assignment](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject),
and [ResumeThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread).
The Linux backend follows [child subreapers](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html),
[waitpid](https://man7.org/linux/man-pages/man2/waitpid.2.html), and the documented
limitations of [proc children](https://man7.org/linux/man-pages/man5/proc_tid_children.5.html).
These mechanisms supervise native descendants; they are not a hostile-code sandbox.
Python documents its Windows redirectors in [venv](https://docs.python.org/3.11/library/venv.html).
Docker documents [container creation](https://docs.docker.com/reference/cli/docker/container/create/),
[inspection](https://docs.docker.com/reference/cli/docker/container/inspect/), and
[forced removal](https://docs.docker.com/reference/cli/docker/container/rm/).
