# Current workflow and benchmark recovery

Started: 2026-10-05 (America/Denver)
Last updated: 2026-10-06 (America/Denver)
Status: Completed scoped recovery; model failures and proof limits retained
Owner: Orket Core
Observed path: primary
Observed result: partial success (restored harnesses; retained model failures)

## Scope and disposition

The user requested repairing current tests, scripts, oracles and workflows and
explicitly authorized quarantining workflows lacking repairable inputs. The fixed
WR-01 through WR-05 queue covered inventory, benchmark contracts, stored assets,
demonstrated configuration defects, and Windows/live verification. This is a scoped
source change on `main`, based on `0342a855453a5a36c3096163d74e78e42989e861`
(core 0.7.7 / SDK 0.7.2). No release, commit, push, new provider, ATG/PRR reopening
or whole-umbrella retirement is part of this change.

All 80 current executable tasks were attempted through both live routes. All six
prepared workflow recipes were exercised. No runnable task in those selections
remains unattempted. Six distinct benchmark tasks retain a failure on at least one
route. The 38 quarantined assets and 13 historical model/quant configurations are
separate inventories, not unattempted current-bank tests or passing results.

## What changed

- Both live suites default to the full executable v2 bank, validate selected
  oracles before effects, use the project interpreter/current model selection,
  and fail their process result when workloads fail. Scoring remains separate.
- Task-specific ordering, constraints and source requirements are visible. The
  artifact contract admits all required implementation modules. Every declared
  case now reaches the existing repair verifier, including later CLI error cases.
  Expected answers, retry/deadline limits, verifier ownership and the 89% floor
  remain unchanged. Native positive/negative references verify the failure oracles.
- Standalone roles, actual tool bindings and schema fields replace stale stored
  definitions. Prepared projects seed member workspaces correctly and isolate the
  caller's mutable board. Factorial derives from the canonical task 008 oracle.
- 27 epics and 11 dependent collections move outside runtime discovery. Their
  original paths, reasons and restoration conditions remain in the quarantine
  manifest. First-run guidance now points to available runtime help.
- Coverage writes to the ignored CI location. Native recovery fixtures use a
  private dotenv path. Native worker observations stop at their pytest owner.
  Collection failure evidence uses its authored member path even without main.py.

Durable details: [readiness contract](../../../../specs/WORKFLOW_BENCHMARK_READINESS.md),
[migration delta](../../../../architecture/CONTRACT_DELTA_WORKFLOW_INPUTS_2026-10-05.md),
[quarantine manifest](../../../../quarantine/workflows/manifest.json), and
[prepared recipes](../../../../../examples/stored_workflows/README.md).

## What was verified

Proof is native Windows and live llama.cpp where stated. Runtime runs used
`ORKET_DISABLE_SANDBOX=1`, the existing server and
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`. Its `openai_compat` adapter is the expected
llama.cpp transport, with no provider/model fallback. Native process receipts
retain argv, source identity, output hashes, Windows job cleanup and capture.
Use `.venv/Scripts/python.exe`; the global shell still resolves an older install.

Receipt paths below are relative to `.tmp/workflow-recovery/`; ignored local
receipts are reproducibility evidence in this checkout, not published artifacts.

| Proof | Result | Retained evidence |
|---|---|---|
| Full Windows tests and coverage | 13,121 passed, 93 skipped; 89.24% coverage against unchanged 89% floor | `windows-quality/attempt-5/state.json` and command logs |
| Final scoped native/contract regression | 84 passed; includes all four former gate failures and real early-provider refusal | `final-regression/state.json` |
| Full direct live route | 76/80 workloads passed; exactly IDs 001-080, one run each | `live-card/attempt-3/state.json`, `live-card/full.json`, `live-card/full-scored.json` |
| Full collection live route | 76/80 workloads passed; exactly IDs 001-080, one run each | `live-rock/attempt-2/state.json`, `live-rock/full.json`, `live-rock/full-scored.json` |
| Provider-interrupted collection task retry | Provider reached; behavior passed; model rewrote verifier, so workload failed | `live-collection-retry/state.json`, `live-collection-retry/result.json`, `live-collection-retry/scored.json` |
| Five prepared epics | 19 accepted cards across standard, QA, sanity, challenge and factorial | Successful epic rows in `live-stored/attempt-1/outcomes.json` |
| Prepared two-member collection | Three accepted member cards after corrected seed placement | `live-stored/attempt-2/outcomes.json` |
| Final portable factorial contract | Accepted completion on final serialized verifier contract | `live-factorial-contract/state.json`, `live-stored/outcomes.json` (attempt 4) |
| Scoped repair feedback | 025/043/055/060 passed; 032/040 retained wrong algorithms with exact failure feedback | `live-repair-feedback/state.json` |
| Structural checks | Ruff, strict taxonomy and pre-closeout docs hygiene passed; final closeout checks recorded below | Local command results and retained taxonomy/dependency reports |

The complete live sweeps and first complete quality gate bind source
`09733dc28ecb85ca0b04cd1c574607bc24d5a2060dc90109a88e3a957caa1ec0`.
The final scoped regression, task 004 retry and final quality gate bind
`b90b27290e1e87941fabe2588073cd72b04accc573928dcff12dd4a4b4cf20f0`.
The latter delta is the collection failure-path fix, the parser/worker observation
test corrections, one native regression, and supporting docs. Frozen runs retain
unchanged-source checks. Final closeout documentation is subsequent to execution. The exact
[pre-closeout plan](PLAN_BEFORE_CLOSEOUT.md) is historical input, not an active
queue. Post-closeout checks use `.tmp/workflow-recovery/post-closeout/state.json`.

The first complete gate retained 13,116 passes, 93 skips, four failures and 89.24%
coverage. One structural test expected parser text in a wrapper after extraction;
three native tests counted the proof supervisor above pytest as invocation-owned
workers. Both were corrected without changing runtime behavior or worker assertions.
Earlier provisional runs were stopped for demonstrated candidate corrections and
are not full gates. Original failed receipts remain. Coverage source reconciliation
separates generated measurements from authored source; it does not rewrite the
original source-mismatch verdict. The first native failure-retention test also
retains its draft's mistaken expected CLI exit 1; actual runtime refusal is exit 2.

## Remaining failures and proof limits

| Task | Route | Observed reason |
|---|---|---|
| 001 | Direct | Model rewrote the supplied verifier; completion refused. |
| 002 | Collection | Behavior passed, but generated source omitted required argparse. |
| 004 | Collection | Full sweep: HTTP 503 Loading model. Isolated retry: actual inference and correct behavior, but verifier rewritten. |
| 005 | Direct | Model rewrote the supplied verifier; completion refused. |
| 032 | Both | Wrong meeting-room algorithm: intervals counted without reducing active count. |
| 040 | Both | Wrong Sudoku algorithm: row, column and box keys share the same namespace. |

The retry does not replace the failed full-suite observation. All eight failed
route/task cells remain visible. Correctness failures are not grounds to alter
oracles or repeatedly sample until green. Required source features and explicit
verifier ownership were present in the prompts. The six-task diagnostic confirms
the wrong function outputs reached the existing bounded repair loop.

Each full score report has 63/80 policy passes and 17 policy failures: tasks
001-015 plus 032/040. Tier 1 requires a band that a single run cannot establish.
This is distinct from the 76/80 workload result. Repeated raw runner/log hashes
include runtime identifiers; they are not semantic determinism. No controlled
speed claim is made: these runs lack experimental controls and overlap coverage.
The inherited scorer's `input_report` field contains the task-bank path, not a
raw-report identity. This metadata-label drift is retained; use the wrapper's
`raw_report` path and the source-bound receipt to identify its actual input.

Not verified by this change: declared skips, live Docker acceptance, new installed
wheel/release pairing, Python 3.12 or alternate platforms, 13 historical model/quant
matrices, repeated semantic determinism, or whole-lane ATG/PRR acceptance. Historical
streaming, review and load proof in the 0.7.7 report retains its original scope and
is not relabeled as a fresh run. Current-authority structural validity does not
establish current proof; `current_proof_established` remains false.

Quarantined inputs require real source/assets, requirements and acceptance before
restoration. The operator-owned `run_the_business` skip-worktree override retains
stale references; it was neither rewritten nor dispatched. Successful prepared
workflow summaries still disclose `silent_repaired_success` packet conformance
debt. A malformed historical aggregate manifest record is left intact; use retained
per-run metadata for current observations.

The full gate also retained three pytest warnings (TestClient dependency
deprecation, the intentional legacy-domain import and a low-token request control).
Coverage rejected two incompletely initialized worker databases. Read-only SQLite
inspection found no file/arc data and no populated coverage-schema version in either;
`coverage-worker-warnings.json` retains their hashes and observations. The 89.24%
combined result passed without these measurements. Their missing worker coverage
is disclosed, not repaired by deleting artifacts or rerunning until quiet.

## Final structural closeout

Docs project hygiene, authority validation and renderer equality passed after
archiving. Authority validation remains structural, with current proof false.
Dependency enforcement inspected 1,223 files and 4,318 edges with zero violations,
unknown modules, analysis errors or authority cycles; six resolved dynamic routes
remain visible in `.tmp/dependencies.json`. Strict taxonomy classified all 13,214
tests with zero missing/conflicting layers or collection errors. Ruff and
`git diff --check` passed. Post-closeout authority/documentation regression passed
all five tests with unchanged source and confirmed native capture/cleanup.
Only final evidence wording and link checks followed that regression.

## Exact files touched

See [CHANGED_FILES.md](CHANGED_FILES.md), including every quarantined source and
destination. Ignored local evidence is listed above and is not part of that source
inventory. No commits or publication are implied by this closeout.
