# Authorization observation and input contract delta

Status: active scoped D implementation; whole-lane acceptance remains open.

`OutwardConnectorService.authorization_context` captures its selected registered
metadata, argument values, standard workspace/reference roots and HTTP allowlist
before its first await. Policy validation, native root/target observation and
context construction then run in one owned worker. Caller cancellation or timeout
retains admitted work until it settles; native failure remains visible during
cancellation drain. Existing caller deadlines are unchanged.

The invocation uses a shallow copy of the service and executor with independently
captured standard fields. The selected metadata/schema and arguments are copied
as values. Filesystem permissions reuse `AsyncFileTools.capture`; standard root
binding shares `capture_file_roots`. Additional injected capabilities retain their
identities. Arbitrary custom state, registry behavior beyond the selected metadata,
and custom copy hooks are not frozen by this contract.

The registered connector name selects the target kind after registry lookup.
Whitespace accepted by that lookup now produces the same file or HTTP target as
the canonical name, rather than incorrectly falling through to a workspace target.
Canonical stable inputs retain their existing policy version, context shape,
serialization and digest recipes.

`bind_authorization` snapshots the supplied run and argument values before context
observation. Later nested caller changes cannot replace the binding's arguments,
step, acceptance contract or run policy. `validate_dispatch_authorization` checks
run scope and arguments both before and after observation, and retains its current
policy and target comparisons. A recorded argument change while observation waits
now refuses with `E_OUTWARD_AUTHORIZATION_ARGUMENT_DRIFT`.

Migration: supply the intended values when starting each invocation; use a new
invocation for changed inputs. Standard drive-qualified relative filesystem roots
are refused with `E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED`; supply an absolute
or ordinary relative root. Embeddings with custom registries/executors must honor
the selected metadata and standard captured fields instead of depending on late
mutation of the original objects.

Proof distinguishes actual filesystem observation and concurrent SQLite requests
from command execution or external HTTP requests: constructing a command or URL
authorization context performs neither outward effect. Held observations use the
existing 0.5-second response bound, 50ms admitted timeout, 0.8-second release and
five-second join limits. Bound-filesystem dispatch, command supervision and durable
claim/intent/publication authority remain with their existing owners.

Relative-root capture still calls `Path.cwd()` before the first await; its syscall
latency and custom copy callbacks are outside the measured bound. Capturing path
values is not an atomic filesystem or configuration snapshot, handle-bound
confinement, or CAP-2 admission. Earlier awaits in proposal construction, arbitrary
runtime reconfiguration and other ambient inputs still require their own review.
Adapter enforcement, Linux/provider gaps, whole Quality, E1/E2/CAP and explicit
whole-lane acceptance remain separate obligations.

Predecessor: `CONTRACT_DELTA_ASYNC_FILE_OPERATIONS_D_2026-09-21.md`.
