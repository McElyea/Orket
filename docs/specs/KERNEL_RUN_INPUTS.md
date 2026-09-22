# Kernel run identity and workspace inputs

Last updated: 2026-09-22
Status: Active implementation contract since 0.6.79; scoped acceptance belongs to the architectural-truth plan

Kernel start uses immutable `KernelRunInputs`: a nonempty plain-string run ID and
an absolute lexical `KernelWorkspaceInputs` value. Pure response construction does
not generate identity or inspect a filesystem. Application capture samples the
explicit owner's selected `create_kernel_run_id` port once after request validation.
The default port preserves the `run-` plus eight UUID hex digits format. Port
failure or invalid identity refuses; there is no second identity source or retry.
The owner binds the selected method at construction. Explicit typed inputs may
replace capture for trusted Python callers; request JSON cannot supply them.

Every Kernel owner captures an invocation root. Standard engines pass their
selected config/project root; direct owners capture their invocation directory
unless given a root. Owner activation binds that immutable root. Relative run
workspace values resolve against it; start handles return absolute lexical paths.
The default remains `.orket_kernel` beneath that root. Absolute caller paths retain
precedence. No file is created by start or by root capture.

Direct ownerless execute-turn resolves its relative handle against the captured
invocation root before policy reads or local effects. Async invocation/publication
captures a root before scheduling workers and carries it through nested calls,
alongside the existing environment snapshot. Owner activation takes precedence
over a surrounding invocation root. Direct gateway requests and whole lifecycle
requests detach before lock acquisition or identity callbacks can wait.

Direct implicit start now requires an explicit active owner and native execution
off the event loop. Pure start with typed inputs needs no owner or worker. Existing
gateway and API lifecycle callers already own their runtime. A relative handle
from an older version must be used with the intended bound invocation root or an
explicit absolute workspace. No workspace migration, copying or merging occurs.

Paths are captured lexically without resolving links. Drive-relative Windows paths
are refused. This prevents later cwd changes from selecting another lexical root;
it does not provide descriptor-based confinement, contain hostile filesystem
replacement, authenticate caller paths, or make concurrent process-wide chdir safe.
LSI/promotion remain local effects with their existing partial-failure semantics.
Cancellation and timeout are not rollback. State remains volatile; run identity
does not establish durable admission, uniqueness enforcement or exactly-once work.
The legacy finish response still echoes the host-supplied PASS/FAIL value and
reports zero turns; it is not an aggregate execution verdict. This input change
does not promote that response into independently verified completion evidence.

The canonical plan owns exact source/installed and live local acceptance, retained
counterexamples, input parity, interruption bounds and remaining D/E/CAP work.
