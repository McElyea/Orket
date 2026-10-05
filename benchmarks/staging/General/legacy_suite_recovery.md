# Stored suite execution and workflow recovery (Windows)

Candidate core 0.7.7; staging only, not approved benchmark publication.
Baseline source: `ebd3e6d1f0d38d4391b4175a2b3b7dae7003195b` (0.7.6).
Recorded: 2026-10-05, America/Denver.
Machine-readable evidence: [legacy_suite_recovery.json](legacy_suite_recovery.json).
Detailed change/proof manifest: [0.7.7 proof report](../../../docs/releases/0.7.7/PROOF_REPORT.md).

## Why previously runnable workflows were blocked

The current completion gate requires declared acceptance and retained evidence.
The older programming challenge had runtime checks, but none of its twelve cards
connected those checks to completion acceptance. It refused the first completion
transition with `E_CARD_COMPLETION_EVIDENCE_REQUIRED`. The migration connects its
existing commands and assertions to retained acceptance; model declarations do not
become completion authority.

The QA failure was a runtime contract mismatch: artifact final review acquired an
app-only design path absent from the prepared project. Artifact review now follows
its declared paths. The QA note also no longer asks a read-only reviewer to write.

Three fresh challenge attempts then exposed separate blockers. Windows writers
translated submitted line endings before exact artifact acceptance. Repeated role
history exceeded the selected server's 8K context after five accepted cards.
Finally, the anti-meta validator rejected Markdown fences inside a valid JSON
README argument after eleven accepted cards. Exact text writes, the recipe's
existing one-turn history setting, and a shared lexical fence check address these
demonstrated failures. Required file context and acceptance checks remain intact.
The fourth attempt completed all twelve cards. Earlier attempts remain unchanged.

The normal unactivated shell also resolved global core/SDK 0.7.1. The project
`.venv` now has editable core 0.7.7 and SDK 0.7.2; its activated `orket` entrypoint
completed real QA. Activation is required per shell. The global install is preserved.
Use the [four prepared recipes](../../../examples/stored_workflows/README.md).

## Outcomes and timing

All model calls use the existing Windows llama.cpp server and
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`. No provider switch, reload, paid API
billing, credit purchase or routine sandbox creation was used.

Workflow timings come from retained run summaries; V2 means use the benchmark's
outer attempt latency. API timings measure observed job completion, and review
timings measure native batch execution. These different workloads and clocks do
not establish a cross-family speed ranking. The JSON also retains run-meta timing
distributions separately from outer harness overhead.

| Family | Observed result | Timing / meaning |
| --- | --- | --- |
| Baseline stored epics | 26 nonempty attempted: 2 complete, 24 failed; 6 empty | Sanity 10.907 s; standard 55.790 s |
| Recovered QA | 2 accepted cards | 29.972 s, real model |
| Recovered programming challenge | 12 accepted cards, final five native commands pass | 437.515 s, real model |
| V2 card bank | 74/80 pass | 25.138 s mean across successes and failures |
| V2 default collection | 37/40 pass, tasks 001-040 | 24.469 s mean across outcomes |
| V1 actual card bank | 100 preflight refusals; no inference | 0.696 s mean refusal latency |
| Harness controls | 460 fixture executions pass | No model-quality claim |
| Deterministic review | 4,100 repetitions plus strict replay pass | 839.506 s batch wall time |
| Recovered historical whole-file review | 1,000 repetitions pass with required `changes_requested` | 661.967 s |
| Queued TCP API | Real QA accepted; separate 1,040 transport samples pass | 27.521 s job completion |
| Installed final wheel/API | Real QA accepted; separate 1,040 transport samples pass | 30.703 s job completion |
| Baseline/heavy service load | All 6,040 transport/refusal samples pass | HTTP 404 for missing work is expected refusal |
| Stub soak | 120 turns pass terminal/ordering checks | No long model-conversation claim |
| Live/native streaming endurance | Corrected 1,000 loops / 6,000 scenarios pass | 8,230.711 s; original failure retained |

The V2 card failures were 025, 032, 040, 043, 055 and 060. Task 025 produced the
wrong argparse error text; 032 returned three meeting rooms instead of two; 040
collided Sudoku row/column/box tuple namespaces; 043 failed histogram logic; 060
failed asteroid collision logic. Task 055 passed examples but included explicitly
forbidden main/print code. The collection reproduced 025, 032 and 040 failures.
These are generated-result failures, not reasons to relax the oracles.

The old CLI checker conflated correctness with replay equality. The corrected
checker observes every declared case twice and reports the two facts separately.
Live collection task 025 failed correctness but passed bounded replay equality
with all four cases observed. The task still failed, including its missing completed
guard turn. Matching wrong outputs do not pass acceptance.

The common card/collection range 001-040 averaged 24.839/24.469 seconds with 37
passes each. These are descriptive observations on different candidate snapshots,
not a controlled speedup. One attempt per task cannot establish determinism;
missing timing controls and orchestration overhead retain `POLLUTED` labels.
Historical models, hardware, policies and acceptance differ. Three old Gemma
challenge attempts ended in terminal failure at 63.5-64.6 seconds and are not
successful timing baselines for the recovered challenge.

## Streaming failure and repair

The first requested 1,000-loop attempt completed 121 loops before failing the
controlled `s6_finalize_cancel_noop` at loop 122: 728 of 729 recorded scenario
verdicts passed. All reached real-model s7/s9 scenarios passed (121 each). The
native authority commit and trace existed, but the harness missed `commit_final`.

Each poll previously started a new reader and abandoned it after 0.5 seconds. The
abandoned reader could consume a later event into an unobserved private queue.
The failed native commit took longer than one poll, still within the unchanged
30-second scenario budget. The repair retains one pending receive across polls
and settles it after socket closure. It does not prefetch events or extend limits.

A native API reproduction held commit publication across multiple polls: the old
runner failed despite a native authority commit; the corrected runner passed.
Quiet socket, disconnect, malformed-message, lifespan, provider-identity and
stream-law checks cover cleanup and negative outcomes. An initial expanded test
batch exposed timing dependence in the test's early-finalize coordination; that
failed batch is retained. The final test explicitly admits workload execution
after the early finalize request returns and then holds publication. Original
endurance bytes and assertions remain unchanged.

Corrected gate `gate-3b8a69a10bc0` completed all 1,000 loops in 8,230.711
seconds. All 6,000 verdicts and the separate authoritative checker passed, with
zero stream-law failures. This comprises 2,000 completed real-model s7/s9
streams (one observed token delta each), 1,000 real-provider s8 cancellation
cases before any observed token,
and 3,000 controlled API lifecycle/refusal scenarios. The s8 name does not
prove cancellation after real generation has begun. Source
inputs stayed unchanged; time limits and gate assertions were not relaxed.
The gate repeats independent scenarios on a warm server. It does not establish
a thousand-turn conversation or a real cold model reload.

## Remaining limits

Twenty-two other nonempty stored assets retain authoring blockers: nine legacy
schema failures, nine missing reviewer seats, three missing completion definitions,
and one unavailable `google_web_search` capability. Six additional assets are empty.
Fixing the first refusal alone would not prove those workflows ready. Real task
inputs, reviewer responsibilities and meaningful oracles are needed; generic
success criteria would conceal the missing work. V1 metadata templates also lack
executable function/CLI examples. Thirteen model/quantization matrices require
different selected inputs and remain unrun; their hashes and historical reports
are preserved.

The operator's `run_the_business` override was preserved without dispatch or
migration. Other stored rocks beyond the V2 collection are not individually
certified by the epic inventory.

Accepted workflows still retain repaired/nonconformant `silent_repaired_success`
truth packets. Mechanical acceptance and current operator disclosures do not
repair that producer. The architectural-truth umbrella remains active; PRR stays
closed, with no executable PRR work. PRR-S1 and broader architecture debt remain
deferred. No hosted CI, non-Windows, full coverage or alternate-model claim is made.

## Evidence preservation

Each batch records actual argv, frozen source hashes, native Windows process
lifetimes, output hashes and result artifacts under `.tmp/legacy-suites/`.
Workspaces remain under `C:/Source/Orket-suite077/`. The outer campaign intentionally
spans repairs; individual batch snapshots are the proof boundary. Wrapper success
labels never override native exits or workload verdicts. Historical reports,
failed workspaces and exact accepted artifacts were not rewritten.

Native cleanup and preservation checks passed: task-owned command identities
are absent, task service ports are released, and the operator board/server,
other worktree heads and accepted 0.7.2 public tags are preserved. Source-only
publication uses the annotated `v0.7.7` checkpoint; no replacement release
assets or approved benchmark publication are claimed. The cutoff remains October
6, 2026 00:00 America/Denver, with the final six hours reserved for verification
and publication.
