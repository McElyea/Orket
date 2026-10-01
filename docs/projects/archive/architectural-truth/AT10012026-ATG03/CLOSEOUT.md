# ATG-03 required producer closeout

Date: 2026-10-01 (America/Denver)
Status: Source exit passed; annotated v0.6.120 publication gate pending
Owner: Orket Core

## What changed

Finish the five frozen required logging sites in four producer families. Bug-fix
publication captures its event and workspace before persistence/readback waits;
preview captures its two missing-input destinations before read/loader waits;
structural adoption and missing-read events detach builtin payload values before
native admission. Existing native ownership, prepared context, required failure
precedence and prior-effect semantics remain. No logging backend, optional queue
or process-global writer lifecycle changed.

## What was verified

Live Windows Python 3.11 source proof: **251 passed, zero failed**, one upstream
Starlette deprecation warning. Inputs stayed unchanged during both the test and
structural campaigns. Public bug-fix transitions, preview compilation and structural
reconciliation observe real SQLite/files/logs, held native work, repeated caller
cancellation and timeout, root/value mutation, native failure before/after physical
append, and prior effects. Independent SQLite observations complete inside the
predeclared 0.5-second limit during native holds.

The preview missing-input path is deliberately degraded and returns only after its
required observation. Missing-read nested metadata is tested at its publication
boundary; existing public MessageBuilder controls retain directory/write failure,
read ownership and no later compaction after failure. A failed required event may
leave prior SQLite/cache/board/log effects, without returning successful completion.

Opening counts: bug-fix 7 failed/3 passed; preview 2 failed/18 passed; structural
6 failed/3 passed; missing-read 6 failed/3 passed. Existing lifetime controls mostly
passed already: the reproduced gaps were payload/destination capture. Closing
batches passed 22, 25, 41 and 33 cases; the final combined 251-case campaign also
includes unchanged logging preparation, subscriber, overflow, diagnostic/fatal
writer, API handoff and native frontier controls. Timeouts are armed only after
actual native admission to avoid confusing setup latency with interruption proof.

Structural proof passes: Ruff; native dependency direction (1,214 sources, 4,182
edges, zero violations/cycles/analysis errors); strict taxonomy (11,783 collected,
zero missing/conflicting layers); critical no-op; docs hygiene; authority structure
and generated equality; release policy. Both Gitea job selections declare the new
controls. This is workflow declaration proof, not a hosted job result.

The tracked `VERIFICATION.json` binds commands, source/log hashes, exact touched
files, limits and publication gate. Full local receipts are `.tmp/atg03-proof.json`
and `.tmp/atg03-structural.json`. Verify annotated v0.6.120, remote branch/peeled tag
and a clean worktree before moving to ATG-04.

## What was not verified

No new complete suite/coverage or canonical Mypy run; no fresh installed Windows/
Linux cell, live llama.cpp inference or hosted Gitea job. The v0.6.117 full suite
is historical and does not prove these changed callers. ATG-06/07 retain the typing
and unchanged 89-percent coverage gates; ATG-08/09 retain installed/platform/provider
and hosted acceptance. No unbound-native capture or whole-request transaction
claim is added. Whole C/D/E acceptance and main merge remain outside this closeout.

## Remaining blockers or drift

Typing and coverage remain red. The default llama.cpp catalog was unavailable,
Gitea access is unestablished and current Linux clock acceptance is unverified.
These later prerequisites do not block eligible local ATG-04/05 work. The native
authority checker still establishes structure only, without general runtime proof.

## Exact files touched

The full list is in `VERIFICATION.json`. Production scope is four frozen files:
`bug_fix_phase_manager.py`, `preview_service.py`, `structural_reconciliation_service.py`
and `turn_read_context.py`. Four integration modules, Quality selections/guard,
contracts, authority, queue/worksets, ATG-02 publication readback and version metadata
accompany those caller corrections.
