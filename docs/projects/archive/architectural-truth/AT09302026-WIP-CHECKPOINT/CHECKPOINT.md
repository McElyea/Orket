# Architectural truth WIP checkpoint

Date: 2026-09-30 (America/Denver)
Status: Historical branch checkpoint; whole-lane acceptance remains open
Branch: codex/architectural-truth-bt0
Base: 8f97e0d4252e776093ef4920b04891659a2ba55a (0.6.114)
Checkpoint version: 0.6.115

## Scope

The user requested closeout of interrupted work in progress, without widening the
revamp. This checkpoint retains the 369 modified and 163 new files present at
handoff, adds the missing guarded-mutation CI/documentation closeout, and preserves
six unapplied proposal bundles. It does not merge to main, complete C/D/E or CAP,
admit new workloads/containment, or establish release readiness.

The retained source includes prepared logging and its caller migrations, native
I/O and cleanup ownership, captured roots/settings/stream inputs, checkpoint
lineage checks, API/bundle/orchestrator decomposition, canonical import/type
repairs, strict test classification and the manifest-backed authority view.

## Interrupted work disposition

The final applied guarded-mutation repair was followed by 133 passing source
cases on September 28, but its plan/CI closeout was unfinished. Every Git-visible
input still matched that retained test snapshot at this closeout's opening.
The earlier 166-case opening retained 146 passes and 20 failures; every failure
was in the guarded-mutation counterexamples. Those failures are not relabeled.
The applied three-file application policy/projection import candidate is also
retained. No prepared-only candidate was silently applied.

No other active agent in this session or repository worker process was found at
opening. That observation does not enumerate or close other app conversations.

`unapplied-proposals.zip` preserves the six original scratch directories with
byte-identical files; `proposal-inventory.json` gives every member hash. They are
historical proposals, not active contracts, imported modules or acceptance proof:

- Model-stream iterator lifetime candidate and its later fixture correction.
- Model-stream client/resource-owner design review (no implementation drafted).
- Direct orchestrator composition proposal.
- Four policy-registry import corrections.
- Two metadata/value import corrections.

Reuse requires current-source reconciliation and the specified proof. The original
scratch directories and retained local test artifacts have not been deleted.

## Verification

| Check | Observed result | Proof and limits |
|---|---|---|
| Guarded mutation/shared owners and Quality workflow guards | 163 passed, zero failures/skips; 83.25 seconds; 5,647 unchanged test-time inputs | Windows Python 3.11.14 source; live native file/SQLite/process controls plus structural/unit controls; primary, success |
| Fresh 0.6.115 wheel | Build, install and `pip check` passed | Installed in a separate environment; installed package origins verified |
| Installed public deterministic flows | Governed demo evidence files retained; quickstart approval wrote the expected bytes, denial wrote none; both ledgers verified | Live Windows Python 3.11 from outside the checkout; primary, success; no model inference |
| Installed CLI/runtime help | Passed | Command admission only; not default-runtime execution proof |
| Ruff, dependency direction, strict taxonomy, critical no-op, authority consistency, docs hygiene | Passed | Structural proof; authority checker explicitly does not establish current runtime proof |
| Mypy | 415 errors in 170 files, 1,213 sources checked | Failing canonical structural gate |
| Full source suite with 89-percent coverage gate | Stopped by closeout at 38-percent reported progress after failures | Incomplete diagnostic; no finalized XML or fresh complete-suite coverage; not acceptance proof |

Strict taxonomy collected 11,644 cases with no missing/conflicting classifications
or collection errors. Dependency checking observed 1,213 sources, 4,168 edges and
six resolved dynamic routes, with no violations, unknown routes, analysis errors,
adapter errors or authority cycles. The no-op check covered 717 files.

The broad diagnostic bound 5,644 unchanged inputs. Its pytest process tree was
terminated deliberately to keep this request a bounded WIP checkpoint; all eight
identified process identities were absent afterward. This is operator termination,
not proof of product cleanup. The supervising receipt writer completed, but its
zero parsed cases mean no XML existed, not that zero tests ran. No result or
coverage is inferred for unfinished cases. A separate one-case reproduction failed
at `tests/acceptance/test_sandbox_cleanup_claim_race.py` with
`E_LOGGING_PREPARATION_REQUIRED`, confirming an unmigrated direct caller. Other
failures in the interrupted run are not all diagnosed or attributed to that cause.

The earlier completed full-suite result remains historical: 10,632 passes,
93 skips and 86.7044163-percent coverage against 89, before the latest WIP.
It does not establish current coverage. Required gates and assertions were not
weakened, and no new test skip was introduced for this checkpoint.

The first wheel-builder command was unavailable in the source test environment
(`build.__main__` missing). The separate packaging environment then built the
wheel successfully with `pip wheel`, using the declared build backend.
Content verification then rejected that initial wheel: the old build directory
contributed 32 obsolete package modules, although existing source members matched.
Its successful smoke does not establish final-artifact acceptance. The clean-copy
rebuild contains 1,233 package files, all byte-identical to current source, with no
obsolete members. Reinstallation, dependency consistency and all installed smoke
checks pass again on that final wheel. The rejected wheel and contaminated build
directory are retained under `.tmp/closeout-20260930/`; the old root build directory
has been moved there so later builds do not reuse it. No product implementation
changed for this packaging-environment correction.

[VERIFICATION.json](VERIFICATION.json) retains command results, evidence hashes,
the wheel identity and explicit proof limits. Original logs, input manifests and
test receipts remain in the named local `.tmp` paths; those raw artifacts are not
part of the Git checkpoint. Later checkpoint edits only finalize documentation
and evidence; the tested product/test bytes are checked for equality before commit.
Git's text line-ending normalization is checked separately against the working
files and recorded in the verification record; it is structural equivalence,
not an additional runtime test.

## Remaining blockers or drift

Full-plan D/E obligations, direct logging consumers, typing, fresh full-suite
coverage and broader installed/platform/provider acceptance remain open. The
guarded mutation installed matrix, Windows Python 3.12, Linux, actual model
inference and hosted Gitea CI were not rerun here. The bounded installed smoke
does not replace them. Proposed CAP requirements remain unaccepted for
implementation. See the canonical active plan for accepted BT guarantees and
remaining scope. The branch is a saved partial checkpoint, not merge readiness.

All 540 checkpoint paths are listed in [FILES.txt](FILES.txt). The list includes inherited WIP;
it does not imply that every inherited file was authored during closeout.
