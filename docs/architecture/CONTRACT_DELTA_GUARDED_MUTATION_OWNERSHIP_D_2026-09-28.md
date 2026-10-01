# Guarded tool and card mutation lifetime

Date: 2026-09-28
Status: Implemented bounded D3 correction; scoped source proof recorded; broader acceptance open

## Boundary and observed source defect

`CardWorkspaceMutationService.run` owns a supported workspace operation inside
`CardRepository.completion_write_guard`. Its manual raw Task/gather loop discards
an operation failure after caller cancellation and logs that discarded failure on
the event loop. A raised SystemExit or KeyboardInterrupt can escape its internal
Task instead of reaching the public awaiting caller after resource settlement.
`ToolRuntimeExecutor._invoke_guarded` independently cancels the supplied authority
once but ignores its settled failure on the interruption path. These are source
findings from the opening source, before the correction described below.

## Selected policy

The mutation service retains its exact async-with body, operation invocation and
repository selection timing. The shared `run_owned_io` owns that whole body with
failure preservation and no forwarded interruption. A successful drain propagates
caller cancellation; the operation/guard's actual settled failure takes precedence,
including its own CancelledError. Supporting failure diagnostics use the shared
native diagnostic owner, cannot replace the selected failure, and may attach the
existing `E_OWNED_DIAGNOSTIC_FAILED` marker. The guard still releases before that
supporting diagnostic. There is no rollback promise for an already-written file.

ToolRuntime uses its existing timeout and shared-owner helper for both routes. The
bounded coroutine awaits the supplied authority for the guarded route, retaining
one forwarded interruption to that authority and settling it through later caller
cancellation. Its existing native synchronous failure slot retains the actual
synchronous callable's failure, including native CancelledError, after settlement
and timeout normalization. The native slot is consulted on the guarded route only when the authority's
actual raised failure is that same native object; a later authoritative cleanup
failure or suppressed body error is not overwritten. Ordinary existing exception families still become their
existing tool-error envelopes; native fatal/base failures remain catchable by the
public caller. Successful deadline drain still returns tool_timeout; later caller
cancellation still propagates interruption. Timeout remains a cancellation request,
not a bound on unkillable native work.

The established value policies are preserved: unguarded exception objects can be
ordinary tool return values; the guarded route and mutation service treat a
returned BaseException object as a failure. Dictionary and scalar shaping, timeout
parsing and optional timeout logging are unchanged. Guard selection still follows
the actual builtin callable. No new owner, cancellation loop, authority proxy,
protocol method, input-copy policy or alternate task factory is introduced. The
local guarded boundary retains coroutine-only admission for the authority's
returned operation. A malformed synchronous override returning an existing
Task/Future is refused with TypeError (then the existing public error envelope),
without adopting, awaiting, cancelling or closing that caller-owned object. Exact
CPython exception text and custom task-factory input object identity are not a
contract. Conforming async authority return values remain ordinary values until
the established guarded failure-value check.

The operation, repository and arbitrary callback inputs remain trusted/borrowed.
This does not close their separate input-capture obligations. Custom authorities
still receive one cancellation, and must perform their own cleanup. The runtime
cannot distinguish an arbitrary authority's independently raised async
CancelledError from its response to that forwarded cancellation. The shared
cancel-on-interrupt policy remains authoritative there; this delta does not claim
native failure provenance for arbitrary async authority or guard-close cancellation
at the outer runtime boundary. Direct mutation-service ownership preserves its
actual child's cancellation failure because it does not forward interruption.

## Concrete callers

- ToolBox's filesystem write/create operations use FileSystemTools, which calls
  the mutation authority around already-captured file work.
- ToolBox selects the guarded runtime route for actual image_generate,
  archive_eval, promote_prompt, reforger_inspect and reforger_run callables,
  including selected aliases. Selection code is unchanged.
- `execution_graph_service.persist_execution_graph_snapshot` uses the mutation service for
  its real graph snapshot; its existing publication/refusal policy is unchanged.
- Public ToolRuntime.invoke also accepts explicitly supplied mutation authorities;
  that protocol and the one-forwarded-interruption behavior are preserved.

## Proof design and ceilings

The 32 isolated-child integration cases include actual native file writes,
real SQLite BEGIN IMMEDIATE exclusion, a competing independently constructed card
repository, previously sufficient literal artifact acceptance, and rejection of
that same completion request after the held mutation changes the file. Controls
observe the actual deadline cancellation count before releasing the worker, exact
failure identity/cause/context where publicly exposed, existing tool envelopes,
returned-exception refusal, one invocation and a healthy subsequent guarded write.
Real standard FileHandler controls retain supporting diagnostics, check event-loop
SQLite progress, preserve the native primary and contain a fatal handler failure.
Three cleanup-precedence controls delegate the actual selected SQLite connection
close before an injected native acknowledgement failure; that failure must
supersede the earlier body failure and retain it as context. Two malformed-authority controls retain pre-existing caller-owned native work
after Task/Future admission refusal. Two custom-authority controls prove one forwarded cancellation and retained async
cleanup that writes a real file. Those custom controls claim no database guard.

The existing owned-command harness supervises each child, checks selected package,
shared-owner and product source hashes, actual terminal exit and independent reap.
Fixture emergency release/join runs after product state is recorded. A native hold
has a finite ten-second watchdog; the outer harness retains its 25-second limit.
Old synchronous diagnostic handling may reach the native watchdog and fail; that
must be attributed as an opening counterexample, not a successful native path.

The September 28 opening retains 146 passes and 20 failures in 166 source cases;
all failures are guarded-mutation counterexamples. After correction, all 133
cases in the guarded mutation and shared-owner selection pass on Windows Python
3.11, with 5,644 unchanged Git-visible inputs. Those inputs still matched at the
September 30 checkpoint opening. Both Quality jobs now declare the guarded tests.
The checkpoint records fresh verification and remaining failures:
`docs/projects/archive/architectural-truth/AT09302026-WIP-CHECKPOINT/CHECKPOINT.md`.
This is live bounded local file/SQLite/process proof plus contract controls,
path primary, result success for the scoped historical closing. Fresh installed
guarded-mutation, Python 3.12 and Linux acceptance remain unverified.
No provider, network, sandbox, hostile authority, arbitrary async failure
provenance, process-crash or infinite-native-operation claim is made.
Canonical shared policy remains `docs/specs/SHARED_IO_CANCELLATION.md`.
