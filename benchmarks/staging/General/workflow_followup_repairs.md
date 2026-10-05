# Workflow follow-up repairs (Windows)

Recorded: 2026-10-04, America/Denver. Candidate core 0.7.6; staging only.
Machine-readable evidence: [workflow_followup_repairs.json](workflow_followup_repairs.json).
Source baseline: `1bc8231908743c84bd197355293b12c9b8ad2b2c` (0.7.5).

## Changes and scope

The adapter admits frozen multifile CLI programs with explicit stdout, stderr and
exit-code examples. All ten CLI tasks now have revision 2 identities and explicit
`main.py`/`implementation.py` inventories. Nine tasks' accidentally escaped newline
expectations are corrected in authored data; runtime comparison remains exact.
CLI support verification uses an actual declared argument case. Full completion
acceptance still checks every example, including error cases.

Prepared projects now write the modular configuration that the runtime actually
loads. The sanity recipe captures the canonical organization name and accepts only
its declared file-write receipt. Run history/detail disclose retained repair and
nonconformance warnings without changing acceptance or historical packet facts.

## Live model results

All inference used the operator's existing Windows llama.cpp server and
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`. No provider switch, reload, sandbox or
paid API was used. Benchmark support verification was explicitly enabled.

| Task | Original result | Duration (seconds) | Scope / failure |
| --- | --- | ---: | --- |
| 001 | passed | 30.091 | CLI card |
| 002 | passed | 26.704 | CLI collection member |
| 003 | passed | 28.485 | CLI card |
| 004 | passed | 25.582 | CLI card |
| 005 | passed | 27.173 | CLI card |
| 019 | failed | 37.170 | Correct behavior; quote-sensitive main-guard check |
| 021 | passed | 30.665 | CLI card |
| 025 | failed | 36.172 | Argument error text differed from declared output |
| 026 | passed | 38.827 | CLI card |
| 030 | passed | 42.309 | CLI card |
| 008 | passed | 18.360 | Function card |
| 010 | passed | 18.622 | Function card |
| 040 | failed | 23.295 | Sudoku example returned false instead of true |
| 060 | failed | 23.857 | Collision example returned `[5,10,-5]` instead of `[5,10]` |
| 080 | passed | 18.746 | Function card |

The original matrix remains **11/15 passed** (8/10 CLI, 3/5 function). Task 019's
main-guard check now inspects top-level Python equality, accepting either quote
style and rejecting comments/string literals. Nine contract cases passed. A
**separate fresh task 019 run passed in 30.272 seconds**. The original report and
source bytes remain unchanged; applying the corrected source-feature check to
the original file is structural rescoring only. Task 025's replay check also
reports failure because output mismatches the oracle; this alone does not prove
the two executions were nondeterministic.

Durations are observed task wall times, not controlled comparisons. Missing
experimental controls and orchestration overhead remain `POLLUTED`; CPU/build work
overlapped parts of the matrix. No speedup or cross-model ranking is inferred.

## Installed candidate and API

The first core wheel reused a pre-existing build cache that included an obsolete
SDK namespace. Installation metadata checks passed, but actual import failed on
`AgentIterationRequest`. That wheel, failed environment and all 1,334 cache files
remain retained. The cache was moved within the workspace after containment checks.
The accepted public 0.7.2 core wheel does not contain that SDK namespace.

A fresh 1,246-file package source export produced a clean core 0.7.6 wheel:
`5da31a2cffddab95197dc5acd026c5db230dfdbfd9a61ff767dd38525a87165b`.
It was installed alongside the checksum-verified accepted SDK 0.7.2 wheel in a
new environment outside the checkout. Package origins resolve to site-packages;
dependency checks and `orket sdk --version` passed. The candidate's modified
runtime/view files match the inspected wheel bytes. Repository-only benchmark
and documentation edits after that build do not change its package payload.

**Installed CLI sanity passed live**, session `72b8c85f`, runtime summary 7.491
seconds, one durable completion commit, direct/conformant truth packet. This proves
only the declared organization receipt, not general operational health.

**Installed API QA failed twice**, sessions `3859e76b` and `e83fc889`, at the
hallucination-scope guard after corrective reprompt. Both actual TCP detail views
display `Runtime output required repair.` and preserve unaccepted completion.
These are live failure/disclosure proof, not accepted API QA proof. Accepted
nonconformant history/detail disclosure is covered by contract tests only.
The unchanged QA recipe's earlier 0.7.5 accepted runs remain historical evidence;
they do not cancel these failures. Both associated transport-load runs and service
teardown have separate retained reports: each observed 1,040 samples and zero
failures, including 40 expected missing-target refusals. HTTP admission is not
work completion.

## Streaming, regression and structural proof

The **100-loop streaming run passed**, with 600/600 scenario verdicts and no
law-checker failures, in 830.368 seconds. The s7/s9 cases each observed one real
model delta per loop; s8 cancellation observed no token delta. The other scenarios
exercise controlled backpressure, cancellation/finalization and unknown-workload
refusal. Real streaming retained the existing ten-second read cap and 30-second
scenario limit. The operator server was not cold-reloaded despite the s9 scenario
name. This extends bounded endurance evidence; it does not establish 1,000-loop
acceptance or explain the historical loop-6 failure.

The final targeted native/contract selection passed **222 tests**, zero failures
or skips, with one existing Starlette deprecation warning. Changed-Python Ruff
passed. Native tests exercise frozen multifile acceptance, missing modules, wrong
outputs, replay and effective prepared configuration. Contract tests exercise
warning projections and source syntax. These are not substitutes for model proof.

Structural preflight: 26 nonempty epics, three ready (`standard`,
`qa_completion_test`, `sanity_test`), 23 blocked; six empty assets. V2 admission is
80/80 (70 function, ten CLI); v1's 100 metadata-only tasks remain unsupported.
Admission does not prove a model can finish a task. The raw inventory preserves
each exact blocker. Readiness shapes remain unchanged by the later source-quality
check, so the retained inventory is reused within that scope.

## Failed attempts and evidence ownership

Early CLI probes retained quality-token failures, no-argument support-verifier
failures and real model output failures. The initial test fixture omitted a
required completion field; that test failed, was corrected and rerun. No earlier
results were overwritten or counted as successful final proof. Per-batch receipts
retain source hashes, argv, environment posture, timings, native ownership and
stdout/stderr hashes under `.tmp/workflow-followup/`. Isolated model outputs live
under `C:/Source/Orket-followup076/`; ignored raw evidence is local, not a public
release asset. The JSON records exact receipt/report hashes.

Prior recovered-fixture 1,000-repeat deterministic review evidence from 0.7.5 is
reused only for its unchanged review inputs and policy. It is historical native
deterministic evidence, not a new model run. No broad campaign is repeated here.

## Remaining limitations

The three model output failures and repeated API QA grounding failure remain.
Twenty-three epics need authored semantics; six assets are empty. No full suite,
coverage campaign, hosted CI, non-Windows run, alternate provider/model, full bank
model run, cold reload or 1,000-loop streaming acceptance is added. The previous
loop-6 streaming failure remains historical and its root cause unresolved.
Runtime warning disclosure does not repair the producer of historical
`silent_repaired_success` packets or expand acceptance beyond declared examples.

PRR remains closed with no executable work; PRR-S1 and broader architectural debt
remain deferred under the active architectural-truth umbrella. Operator override,
provider, model server, other worktrees and published releases are preserved.
