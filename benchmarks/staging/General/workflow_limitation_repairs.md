# Windows workflow limitation repairs

Recorded: 2026-10-04 (America/Denver). Candidate source checkpoint: core 0.7.5.
Status: staging candidate, not promoted benchmark evidence.

The [machine-readable report](workflow_limitation_repairs.json) records exact
command/log hashes, native ownership receipts, durable completion receipts,
preflight failures and original failed attempts. Raw evidence is retained under
`.tmp/workflow-wins/`; isolated projects and recovered bundles are retained under
`C:/Source/Orket-wins075/`. These local references are not public release assets.
The retained manifest identifies exact bytes; Git may normalize source text line
endings. The original 0.7.4 comparisons and their failed evidence remain unchanged.

## Changed and verified

All inference used the operator's existing llama.cpp server and
`orcarouter_qwen3.8-27b-uncensored-q4_k_l` on Windows. Runtime proof used a fresh
editable development environment (core metadata 0.7.4 during execution, SDK 0.7.2),
with sandbox creation disabled. The final version bump changes metadata only.
No paid API, model switch or server restart was used.

| Repair | Observed proof | Result |
| --- | --- | --- |
| Prepared `standard` cards | Live CLI, three accepted cards per run | Two final-recipe runs: 57.386 and 58.335 seconds |
| Prepared QA cards | Live CLI and real TCP API, two accepted cards per run | CLI 29.658 seconds; final API 30.420 seconds (earlier API 30.051 seconds) |
| Isolated benchmark assets and function acceptance | Live v2 task 008 factorial; retained project/board and three expected cases | Card passed (18.445 seconds); two collection runs passed (17.844 and 14.435 seconds) |
| Outcome-aware load and service ports | Two real TCP baselines and saved combined wrapper, three separate runs | 1,040 samples each, zero failures; each includes 40 expected missing-target refusals, not completed jobs |
| Typed streaming errors and idle diagnostics | Controlled native HTTP timeout; three actual idle-server one-token requests | `ReadTimeout` retained; observed first deltas 576.736, 94.888 and 85.530 ms |
| Bounded streaming retry | Ten complete gates, 60 scenario verdicts | All passed in 83.646 seconds; actual model token output in s7/s9 |
| Historical 30-page review recovery and whole-file scanner | Real Git bundle recovery, native deterministic ReviewRun | 1,000/1,000 expected `changes_requested` decisions in 628.736 seconds |
| Targeted regression selection | Integration, contract and unit tests; changed-Python lint | 281 passed, no failures/skips; Ruff passed |

Model runs followed the primary selected-provider path with no recorded fallback.
Their acceptance is bounded to declared cases. The final prepared workflows still
record `truth_classification: repaired` and packet conformance `non_conformant`
(`silent_repaired_success`); this report does not relabel them as pristine runs.
The benchmark experimental-quality label remains `POLLUTED` where controls are
absent. The durations above are observations, not a speedup or model ranking:
some CPU verification and load work overlapped, and task semantics changed.

The review used the exact historical commits
`8f4152650d8d969a10a6e0296038057be39393c9` and
`2c7b660cac993ab26f94dc1f473ddcb9b82e88de`, all 28 selected paths, and historical
policy digest `92ff86ca0041dabf0a78f60e0bad6da9005edf6b373726550d8e1832610bf01b`.
The self-contained bundle SHA-256 is
`492210879e5ccc8c3569a9255afee7c1bb81c7822debd399bdec1327decac91a`.
The original broken temporary repository was not repaired or overwritten.
Recovery changed repository identity, and the corrected finding now identifies
`app/feature_04.py:2`; fresh output is not byte-identical to historical output.
This is native deterministic proof with no model calls.

## Retained failures and limitations

- The first helper used a nonexistent CLI module. The next standard run exposed
  line-ending-sensitive design acceptance; semantic JSON acceptance fixed it.
- The first collection run put the verifier outside its member workspace. Both
  subsequent isolated collection runs passed after correcting that input path.
- Two real API QA attempts failed: a seed in the CLI workspace, then generic role
  instructions requesting an unrelated artifact. The prepared API workspace and
  role scope now match the declared cards. Both terminal failures remain visible.
- The first recovered review repeatedly returned a false pass. It was stopped
  when the files-versus-diff scanner defect was demonstrated. Its checkpoint and
  owned termination receipt remain intact; the corrected run required the expected
  rejection as well as repeatability.
- Earlier successful `workflows-03` records `source_inputs_unchanged: false`
  because documentation changed during execution. Final-recipe CLI/API runs have
  frozen inputs. Each batch retains its own source inventory and scope.
- The first dependency check rejected the router's new legacy-exception import.
  Target observation moved to the application service. The final API QA/load run,
  repeated 281-test selection, lint and dependency check passed. The initial
  failed governance report remains under `governance-01/check_outputs/`.
- Structural preflight inspected 26 nonempty stored epics: only `standard` and
  `qa_completion_test` are ready; 24 need concrete inputs, roles or acceptance.
  Six more assets are empty placeholders. Readiness alone is not live proof.
- v1 has 100 metadata-only tasks. v2 has 70 explicit function-example tasks and
  ten unsupported program tasks. Only task 008 was exercised live in this repair;
  the inventory does not establish success on the other 69 supported tasks.
- Ten streaming loops do not establish 1,000-loop endurance or explain the old
  loop-6 failure. Timeouts were not relaxed. The s8 scenario cancels at model
  loading; the s9 cold-load label does not prove a physical cold model reload.
- No full suite/coverage, new wheel/SDK pairing, hosted CI, other provider/model,
  non-Windows, statistical performance or thermal endurance proof is added.

All recorded task command owners confirmed native cleanup and complete capture.
The operator model server, board override, other worktrees and old published
releases remain outside task ownership. Final source/tag publication and scoped
governance are recorded in the [0.7.5 proof report](../../../docs/releases/0.7.5/PROOF_REPORT.md).
PRR remains closed; PRR-S1 and broader architectural debt remain deferred.
