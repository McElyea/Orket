# Async file operation contract delta

Status: active scoped D implementation; whole-lane acceptance remains open.

`AsyncFileTools` read, write, directory creation and listing now own their complete
admitted operation through the shared owned-I/O supervisor. Native path traversal,
existence checks and directory work run in owned workers. `aiofiles` retains its
existing UTF-8 read/write implementation inside the owned operation, so caller
cancellation cannot return while its admitted native open/read/write/close work
is still running. Native failure remains visible during cancellation drain.
No operation timeout or existing caller deadline is extended or removed.

Each invocation captures its workspace/reference path values and serializes write
content before the first await. Nested caller mutation cannot change that write's
content. Relative roots bind to the current invocation directory. Drive-qualified
relative roots such as `C:workspace` are refused with
`E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED`; callers must supply an absolute root
or an ordinary relative root. Serialization failure now occurs before directory
creation or file truncation. Standard JSON formatting remains unchanged.

`capture()` returns a shallow instance copy with independently bound standard
workspace/reference fields. Additional injected capability identities remain
unchanged; this does not freeze arbitrary subclass state or custom copy hooks.
`resolve_path_async()` supplies an owned path-observation entrypoint. The existing
synchronous resolver remains available for explicitly synchronous/worker consumers.
Pre-loop synchronous file methods retain their existing bridge and return shapes.

Filesystem tools capture their mutation-authority capability before path
observation or lock waits. Write/create retain the existing per-path lock and
`CardWorkspaceMutationAuthority.run` boundary. Removing the original object's
authority while path work waits cannot bypass the admitted completion guard.
The legacy unbound connector delete path captures its permissions and owns path
validation, existence/type checks and unlink in one worker. Authorized connector
dispatch still selects the existing bound-filesystem executor before legacy paths;
its authorization, evidence, deadline and result authority are unchanged.

Proof uses real files, SQLite requests, native path/open/directory ports and the
actual card completion writer guard. Held-port responsiveness remains bounded at
0.5 seconds, timeout starts 50ms after native admission, native release remains
0.8 seconds, and joins retain five-second limits. Controlled injected faults and
native resource observations are distinguished from successful provider workloads.

The affected live Gitea review success fixture drains its owned server's setup
queues and verifies an open, unmerged, mergeable PR before submitting the review.
It retains the original 30-second delivery deadline and remote merge assertions.
An earlier actual HTTP 405 refusal and truthful runtime error remain retained;
the intervening server-state transition was not captured. Fixture readiness does
not change runtime retry/deduplication policy or prove general merge availability.

This is resolved-path containment, with the prior read-only reference policy.
It is not a filesystem snapshot, atomic publication, hard-link protection,
TOCTOU prevention or CAP-2 OS containment. The existing path-lock cache policy is
unchanged. Relative-root capture still observes `Path.cwd()` before the first
await; this checkpoint does not establish a latency bound for that platform
current-directory syscall or arbitrary injected callbacks. Broader invocation
input/async review, including raw-worker authorization-context collection, remains
open. Constructor/helper ownership, adapter enforcement, Linux/provider gaps,
whole-suite Quality, E1/E2/CAP and explicit acceptance remain separate obligations.

Predecessor: `CONTRACT_DELTA_RUNTIME_RESOURCE_CLEANUP_D_2026-09-21.md`.
