# ATG-02 scoped model-stream lifetime closeout

Date: 2026-10-01 (America/Denver)
Status: Source exit criteria passed; annotated v0.6.119 publication gate pending
Owner: Orket Core

## What changed

The builtin explicitly closes its invocation iterator before requesting a commit
and owns iteration/cancellation-watcher settlement. Repeated caller interruption,
turn timeout and public API shutdown retain cleanup. An iterator-close TimeoutError
is not relabeled as a turn deadline. Borrowed provider objects remain borrowed.

Application composition supplies the explicit HTTP lifetime port to real adapters.
The existing captured network builder and HTTP resource owner retain native
construction, partial acquisition, nested iterators, responses, clients and
transports. Non-streaming and zero-token fallback now use asynchronous HTTP;
there is no unowned synchronous request worker. Native construction and explicit
cleanup failures escape after settlement. Existing provider body errors produce
failed decision intents; successful event/commit schemas and target admission stay.

The raw real-adapter constructor migration is breaking for internal callers:
provide `http_client_owner` using `ModelStreamHttpService`. The abstract provider
iteration/cancel interface, Stub construction and builtin entry signature stay.
No shim, new TLS/proxy authority, dependency exemption or cancellation supervisor
was added. The oversized provider module shrank from 574 to 417 lines.

## What was verified

Live controlled Windows Python 3.11 source proof: primary path, success. Final
selection **150 passed, zero failed**, with one upstream Starlette deprecation
warning. Real loopback HTTP exercises streaming, non-streaming and the explicitly
observed zero-token fallback. It covers held native construction, captured
proxy/authentication/environment values, repeated cancellation, turn deadlines,
partial response bodies, peer EOF, actual client/transport close and public HTTP
API shutdown. Durable interaction decisions/finalization and unchanged target
admission/input controls are included. These fixture replies are not model inference.

Opening controls reproduced five original iterator failures and three additional
cleanup-timeout failures. The valid B02 transport opening recorded seven failures
and two passes. Two earlier transport-observer campaigns did not observe HTTPX
context-exit ports and are retained as incomplete instrumentation, not full
counterexamples. The corrected controls observed lost native completion/failure,
Ollama client escape and event-loop construction before repair.

Structural proof: Ruff, canonical dependency checker (1,214 sources; 4,179 edges;
zero violations/cycles/analysis errors), strict pytest taxonomy (11,735 collected;
zero missing/conflicting layers), critical no-op, docs hygiene, authority structure,
generated equality and release alignment all pass. Gitea workflow declarations
include all new controls in both jobs; no hosted job was run.

`VERIFICATION.json` binds commands, logs, hashes, unchanged-source observations,
proof limits and exact touched files. Local full receipts are
`.tmp/atg02-proof.json` and `.tmp/atg02-structural.json`. A prior intermediate native
dependency check correctly rejected two reverse imports; explicit port composition
removed them without modifying the policy. Publication must verify the annotated
tag, remote branch/peeled tag and clean worktree before moving to ATG-03.

## What was not verified

No new complete suite/coverage or canonical Mypy run, fresh installed Windows/Linux
cell, actual llama.cpp inference or hosted Gitea Quality acceptance. The earlier
complete suite is historical evidence; it is not current proof for changed runtime
files. ATG-06/07 own the typing and unchanged 89-percent coverage gates, and ATG-08/09
own installed/platform/provider/hosted proof. Closing local HTTP connections does
not prove remote inference termination or arbitrary borrowed capability behavior.

## Remaining blockers or drift

Typing and coverage remain red. The default llama.cpp catalog was unavailable;
Gitea endpoint/access is not established. Current Linux clock acceptance remains
unverified. These later prerequisites do not block eligible ATG-03/04/05 work.
Current-authority verification is structural and has no general runtime-proof
adapter. The lane remains active; no main merge or new capability admission.

## Exact files touched

The complete checkpoint list is in `VERIFICATION.json`. Four production files
were changed: the workload, provider module, application HTTP service and existing
core HTTP port contract. Tests, active contracts/index/authority, workflow guards,
queue/worksets, previous publication readback, and version metadata accompany them.
