# ATG-01 evidence reconciliation

Date: 2026-10-01 (America/Denver)
Status: Complete; branch publication verified
Owner: Orket Core
Candidate: `7d8daf386b40e3194b46da3e5431c6c3b4bcdb99` / `v0.6.117`, with the
user's four queue-document edits and historical queue archive preserved.
Checkpoint: `20eaba3abe0c7a2e6400e12b9dc31222ff8a6052` / annotated `v0.6.118`;
remote branch and peeled tag match, with a clean worktree observed after push.
Receipt: `.tmp/atg01-publication.json`. No runtime implementation change.

## Changed

The canonical queue now executes the user's fixed ATG-v1 scope. Its
[finite inventory](../../../architectural-truth/GOAL_WORKSETS.json) freezes 67
batches: 2 stream, 4 required-producer, 9 other D, 3 E2 and 49 typing batches.
Each names paths/symbols, existing obligations, contracts, missing proof and
completion checks. Typing groups contain at most five production files.

The 207 previously recorded async rows reconcile to 122 satisfied at their
retained scoped boundaries, 16 non-defects on the recorded routes, and 69 pending
proof/repair rows. This is row accounting, not a whole-runtime purity claim.
All 19 required publication sites are retained: 14 have existing native ownership
and scoped controls; five sites in bug-fix, preview, reconciliation and required-read
producer families need their remaining input/adverse proof. Optional preparation
callers remain outside that workset. No replacement logging backend is proposed.

The three named E2 roots measure 478, 635 and 490 lines. Ops functions already meet
70 lines; the dispatcher execution body is 519 lines and message preparation is
458. Their existing authority and phase timing constrain extraction.

The exception register and architecture no longer describe the applied guarded
tool correction as an unfixed source defect. The logging migration and eight
fixture failures are closed at their recorded scopes. No whole C/D/E exception
or compatibility window is retired; CAP and the six proposal bundles remain excluded.

## Verified

Proof for this goal is **structural**; path **primary**, result **success** for
evidence reconciliation. Canonical Mypy is a separately failing quality gate:
**415 errors in 170 files, 1,213 sources**. It ran once, exit 1, with no input
change. Exact diagnostics are retained in [MYPY_DIAGNOSTICS.txt](MYPY_DIAGNOSTICS.txt).
The source environment is Python 3.11.14, Mypy 2.3.1, pytest 9.1.1 and coverage
7.16.2. Its installed distribution metadata still says 0.6.115; this is source
verification of 0.6.117, not fresh installed-package acceptance.

The remote branch and peeled annotated `v0.6.117` tag both matched the candidate.
The complete-suite XML, log and coverage JSON hashes match their retained readback.
Runtime, SDK and test inputs match the original run. Changed inputs are disclosed
in the inventory: documentation/changelog changes and the archived PDF path that
is not present under the receipt's spelling. That PDF supplies no runtime proof.
Relevant test-source hashes and retained passing case counts accompany reused
ownership evidence. There was no new full-suite execution.

The retained suite remains **11,584 passed, 0 failed, 93 skipped**, exit 1 because
**87.035153%** coverage fails the unchanged **89%** gate. Scoped real file, SQLite,
child-process and controlled HTTP controls remain historical live source evidence;
their hash revalidation is structural, not another live execution.

Both existing Windows interpreters execute (3.11.14/3.12.2). Existing WSL Ubuntu
environments execute Python 3.11.16/3.12.3; the 3.11 environment requires its explicit
retained path, since `python3.11` is absent from PATH. No infrastructure was provisioned.
The default local llama.cpp catalog at `http://127.0.0.1:8080/v1/models` was
unavailable (`URLError`). This is endpoint observation only; inference was not attempted.

Ignored receipts: `.tmp/atg01-inputs.json`, `.tmp/atg01-mypy-receipt.json` and
`.tmp/atg01-mypy.log`. The process receipt records argv, source identity, process
IDs, start/finish time, exit, log hash and unchanged inputs. No command remains running.
Final structural/publication results belong in `VERIFICATION.json` beside this file.

## Not verified

No fresh runtime, installed-wheel, actual-model, Linux behavior, clock-reliability,
Docker or hosted Quality campaign was run. No complete source suite was repeated.
The remaining batches must supply their own opening/closing proof. Reusing existing
source controls does not waive ATG-08/09's installed and platform requirements.

## Remaining blockers or drift

Typing and coverage remain red. The llama.cpp default catalog is currently unavailable;
Gitea endpoint/access is not established by the configured GitHub remote. Earlier
Linux clock failures remain historical and need current-host verification at ATG-09.
These later prerequisites do not block the eligible local ATG-02/03/04/05 work.
Current-authority checks remain structural and explicitly lack general runtime proof.
The whole lane remains active; no main merge or capability admission is authorized.

## Exact files touched

The final checkpoint list is retained in `VERIFICATION.json`. It includes the
user's existing queue/contributor/roadmap/registry edits and three exact history
archive files, plus this closeout, diagnostics, worksets, exception/architecture
reconciliation and version/changelog metadata. The prior historical plan and
registry snapshots retain their bytes.
