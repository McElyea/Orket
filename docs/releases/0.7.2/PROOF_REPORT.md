# Release 0.7.2 proof report

Date: 2026-10-04 (America/Denver)
Owner: Orket Core
Queue: PRR-v1; required goals PRR-01/02/03. PRR-S1 not admitted.
Base: `2ccbd9aa26a71ba0347096800b8acbd8f4804070` on `main`.
Matching annotated tags `v0.7.2` and `sdk-v0.7.2` identify the published increment.

## Changed behavior

Two installed-path defects were reproduced and repaired: missing default
WebSocket transport returned 404 during upgrade, and a disconnected interaction
socket stayed blocked on its event queue and prevented graceful shutdown. The
existing route now owns event forwarding and disconnect observation together,
settling both before subscription cleanup. Disconnection does not cancel the
separately owned workload.

ResponseParser deleted whitespace from non-JSON residue, making `Maybe this...`
escape an existing whole-word grounding rule. It now preserves whitespace and
separates excluded JSON spans. Policy vocabulary, JSON exclusions, tool admission
and corrective refusal remain authoritative. The regression observes two model
attempts and zero tool dispatch after persistent speculative prose.

The matched SDK 0.7.2 increment is packaging-only. Compatibility and migration
classification: [release notes](RELEASE_NOTES.md). Operator commands and startup
diagnosis: [walkthrough](OPERATOR_WALKTHROUGH.md). The unchanged operator override
is excluded from packages and Git; the canonical index blob supplies snapshots.

## Verification

Machine-readable evidence: [verification.json](../../../benchmarks/results/releases/0.7.2/verification.json).
Raw receipts are losslessly compressed as `batches/<batch>/state.json.gz`; command
logs, XML and project artifacts retain their captured bytes. Absolute paths in
receipts identify original local observations; retained project copies preserve
relative paths. [Package hashes](../../../benchmarks/results/releases/0.7.2/SHA256SUMS.txt).

| Observation | Proof | Path / result |
| --- | --- | --- |
| 569 affected parser, turn, streaming, startup, package, SDK and authority controls; zero failures/skips | Mixed marked test layers; native cases identified by tests | primary / success |
| Three additional installed SDK console cases on Python 3.12 | end-to-end | primary / success |
| 56 affected tests after test-only Ruff corrections | integration | primary / success |
| Final canonical paired wheels, fresh default installs and dependency consistency on both Windows interpreters | live package integration | primary / success |
| Public authenticated HTTP/WebSocket actual llama.cpp completion, separate in-flight cancellation and status/snapshot/replay | live | primary / success |
| Durable commit digest inspection after graceful close, zero runtime request/background counts and native command cleanup | live local lifecycle | primary / success |
| Actual stream output passed unchanged into installed parser/validator, with published parser artifacts, both interpreters | live stream plus parser integration | primary / success |
| Refreshed installed TurnExecutor with actual profiled inference and real ToolBox file write; additional actual speculative response rejected, provider client closed, both interpreters | live, template-aligned server | primary / success |
| Native CLI from absent board; explicit warning retained and process settled | live negative control | degraded / success of expected warning observation |
| Native CLI from valid initialized epic/team/rock; actual adoption and no warning/metadata error | live startup | primary / success |
| Final installed SDK version text/JSON, both template scaffolds and strict host validation, both interpreters; SDK-only namespace isolation | live | primary / success |
| Ruff, Mypy, dependency direction, strict taxonomy and critical no-op | structural | primary / success |

Final base installations use the recorded
[dependency constraints](../../../benchmarks/results/releases/0.7.2/dependency-constraints-0.7.2.txt).
Resolved distributions are retained for
[Python 3.11](../../../benchmarks/results/releases/0.7.2/batches/final-packages-r02/py311-dependencies.stdout.log)
and [Python 3.12](../../../benchmarks/results/releases/0.7.2/batches/final-packages-r02/py312-dependencies.stdout.log).
No unconstrained future dependency-resolution claim is made.

Mypy found no issues in 1,223 source files; its untyped-body notes remain in the
log. Taxonomy found 13,101 tests with zero missing/conflicting layers. The main
selection retains 46 warnings, primarily JUnit property compatibility and the
Starlette/httpx transition. An initial Ruff run failed on import ordering and the
native count poll; the corrected run passes. The poll has a narrow explanation:
the public runtime exposes a count, not a settlement notification. Its original
three-second deadline and settlement assertion remain unchanged.

Final source is built from the staged canonical Git index through sdist-to-wheel
builds. All 1,278 source members in the two sdists match indexed Git blobs, and
wheel namespace members match that snapshot. Fifteen core and five SDK namespace
files differ from the earlier candidate only by canonical CRLF-to-LF conversion;
the exact final wheels received fresh live acceptance. The initial index export
hit Windows path length on an existing tracked historical artifact; the successful
export uses command-local `core.longpaths=true`, with no global Git setting change.

## Counterexamples and evidence limits

All failed attempts remain available, including the 0.7.1 upgrade failure,
11 pre-fix parser/dispatch failures, two pre-fix native disconnect failures,
the first candidate's shutdown timeout, and probe errors. R02's durable assertion
incorrectly rejected the application's cancel lifecycle finalize intent. R03's
initial startup fixture lacked required epic/team fields and expected the wrong
adoption shape. R04 misconstructed ContractValidator; R06 wrongly expected one
tool occurrence when the model repeated JSON. Those are failed probes, not new
product defects or passing evidence. R05 records a real fail-closed provider error;
later bounded runs succeeded, without a general reliability guarantee.

The selected provider was initially operator-owned llama.cpp PID 33276 at
`http://127.0.0.1:8080/v1`, exact model
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`. No task command restarted or stopped
it. Before publication, process inspection observed an independently replaced
PID 45556, started at 2026-10-04T19:24:07Z, serving the same model/provider with
the declared text template. The replacement's cause is not asserted. Both public
journeys were refreshed successfully against that process. An additional unrelated
`Orket-paperclips-foundation` worktree appeared and was preserved.
The native stream exposes actual token output, including model reasoning when
provided by that server. The parser proof uses those bytes without substituting
a fabricated response. No tool is dispatched by this additional parser probe.

The initial separate direct profiled card/TurnExecutor attempt was **blocked** by
`E_LLAMA_CPP_TEMPLATE_IDENTITY`: the embedded server template does not match its
declared packaged text template. That failure is retained; no profile override
or guard bypass was introduced. The later `/props` observation matches the final
candidate's template bytes and model alias. A refreshed installed TurnExecutor
then performed actual inference and a real file write on both interpreters;
another actual response, `Maybe this should work.`, triggered the repaired rule.
Both provider clients closed. The first refreshed probe incorrectly expected LF
bytes from the existing Windows text-mode writer; its failed capture remains.
The corrected probe verifies exact CRLF bytes and digest. This bounded success
does not certify arbitrary card workflows or model output.

Durable commits bind lifecycle intents, not transcripts. A model completion
intent references `model_stream_v1`; an interrupted lifecycle finalize intent
references its turn ID. `commit_outcome=ok` does not turn interruption into model
success. Session inspection before shutdown and direct file inspection afterward
do not establish restartable sessions. Local transport/task/process settlement
does not establish remote model termination. The probe uses the canonical app
and cooperative Uvicorn shutdown; console signal delivery is not claimed.

## Acceptance and publication witness

Orket Core records scoped AC-01 through AC-10 acceptance: dependency direction
is preserved; parser policy and inputs remain explicit; no new clock/randomness,
adapter authority, schema or replay authority is added. The interface owns only
its transport children, while existing application owners retain workload and
durable effects. Required facts and refusal cases have retained evidence, and
contracts, generated authority and operator docs change together. Existing wider
architectural exceptions are not widened or certified by this patch.

PRR-01/02 meet their bounded gates. PRR-S1 is **not admitted: time reserved for
required goals**. PRR-03 completion requires the stable final-gate and publication
witnesses under `.tmp/post-release-reliability/`, including docs hygiene, authority
render/source checks, install convergence and release policies; annotated tags;
atomic main/tag push; remote identities; downloaded distribution and receipt
hashes; and a clean worktree. The public `publication.json` attached to both
GitHub releases records those actual identities and final checks without asking
this source file to attest to its own future commit hash.

Remaining blockers or drift: the intentionally degraded missing-board path,
general current-authority runtime proof gap, earlier
coverage capture/discovery limits, and broader marshaller/plugin debt remain.
The full coverage campaign was not rerun for this bounded patch; its 89-percent
floor and branch measurement remain unchanged. No fresh Linux/Mac, hosted CI,
Docker, remote Gitea or remote inference-stop claim is made. Old release evidence
retains its original versions and scope. [Exact files touched](FILES_TOUCHED.md).
