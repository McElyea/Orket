# Outward Bound Filesystem Execution Delta

Owner: Orket Core. Date: 2026-09-12. Scope: BT-1 target binding.

A real worker paused after committed dispatch intent allowed an operator to
replace a directory symlink. The connector re-resolved the unchanged model path,
wrote a second directory, and returned success under an approval bound to the
first directory. Before-claim, before-intent and unchanged-link controls passed;
the after-intent case failed. Existing authorization and effect bytes are retained.

The application passes the complete immutable binding to filesystem execution.
The adapter validates the original path against the bound root/target, retains
parent handles, refuses newly introduced links and uses the opened file handle
for I/O. Windows uses reparse-point opens and parent handles without delete
sharing; POSIX uses descriptor-relative no-follow operations. A missing required
primitive refuses execution. Cancellation waits for the owning filesystem thread
before acknowledging teardown. This does not admit hostile code, constrain an
arbitrary command, prevent privileged filesystem changes, or guarantee that a
postcondition remains unchanged after the operation returns.

The binding schema is unchanged: v1 already commits root, target and arguments.
No backfill or permission reconstruction is needed. Failed target validation
after intent retains uncertainty and prohibits automatic redispatch. Rollback
disables bound filesystem dispatch while preserving intent/receipt/journal data;
it must not restore path re-resolution as execution authority.

Validation must cover both sides of intent, actual target changes at the opened
handle boundary, normal read/write/create/delete behavior, cancellation ownership,
retained argument/result hashes and the live llama.cpp approved-write proof.
Record Windows and POSIX evidence separately; code presence is not host proof.

Installed-wheel acceptance exposed a Python 3.11 failure on both Windows and
Linux: request cancellation returned while the held filesystem operation could
still write. The same original tests passed under Python 3.12. The connector's
`asyncio.wait_for` wrapper is replaced by an `asyncio.timeout` scope that keeps
execution in the owning task. The existing bound executor still drains the
thread and closes its handles before propagating cancellation. Acceptance now
also includes repeated cancellation and an elapsed deadline while the worker is
held. A timeout is not evidence of an absent effect and does not admit redispatch.
The canonical architectural-truth plan retains the failed wheel/test reports and
records final source and installed-wheel outcomes separately.

Implementation references: [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
documents reparse-point handling and sharing rules; [Python os](https://docs.python.org/3/library/os.html#os.open)
documents descriptor-relative operations. These API contracts support the design;
the repository's real filesystem tests must establish observed behavior.
