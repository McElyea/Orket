# Architectural Truth: Executable Goal Queue

Last updated: 2026-10-04 (America/Denver)
Status: Active umbrella; bounded Windows ATG-v1, v0.7.1 cleanup and PRR-v1 publication complete
Queue: ATG-v1 — ten goals; Windows-only scope amended by the user on 2026-10-03
Owner: Orket Core
Worktree: `C:/Source/Orket` (release integration; original ATG proof worktree retained)
Branch: `main`; accepted ATG checkpoint remains `codex/architectural-truth-bt0` / `v0.6.144`
Next goal: **None; PRR-v1 is published and complete (3/3), with no executable PRR work**

## Purpose and authority

This file retains the completed ATG-v1 queue, release publication witnesses and
umbrella proof limits. The user invoked PRR-v1 on October 4, 2026. Its completed
publication and historical checkpoints are [archived](../archive/architectural-truth/PRR10042026/POST_RELEASE_RELIABILITY_PLAN.md).
The matched 0.7.2 [release proof](../../releases/0.7.2/PROOF_REPORT.md) supersedes
the earlier grounding and installed native-stream proof gaps only at its stated
scope. Initial card-template refusals remain historical; a later independently
replaced, template-aligned server passed bounded actual turns on both interpreters.
Fresh remote and downloaded-byte reconciliation confirms matched `v0.7.2` and
`sdk-v0.7.2` at `9cb8a89056c46f0c3633e0c20aaac60d80113236`; PRR-01 through
PRR-03 are complete. The [final handoff](../../releases/0.7.3/PROOF_REPORT.md)
records a documentation-only successor, preserving the 0.7.2 install target.
PRR-S1 remains not admitted. Broader limits remain; no new queue is executable.
The ATG goal cards, schedules and next-action text below describe the completed
queue and do not authorize its restart or override the PRR-v1 resume record.
Execution workflow lives in `docs/CONTRIBUTOR.md`, including **Persistent goal
queues**. Runtime contracts and `CURRENT_AUTHORITY.md` keep their existing authority.

The scope is the existing C/D/E revamp: settle already-recorded runtime ownership
debt, finish the named structural cleanup, restore quality gates, and verify the
resulting branch. Preserve accepted BT-1 through BT-5 behavior and A/B guarantees.
This is not permission to replace the architecture, broaden supported capabilities,
or reopen completed work merely because a different design is possible.

The former 28,934-line plan and previous project registry are retained as exact
historical snapshots in the [history archive](../archive/architectural-truth/AT10012026-GOAL-QUEUE/README.md).
Their old next-action instructions, proposed capabilities and stale measurements
are not the current queue. Existing contracts remain binding; archiving the journal
does not retire an obligation or establish whole-lane acceptance.

## User-directed Windows scope amendment

On October 3 the user directed: "Lets remove the blocker from the plan and stop
trying to support linux if this is working in windows". **Windows is the sole
acceptance target for this refactor.** This explicit decision supersedes the
original ATG-09 Linux and hosted-CI requirements and the previous runner requests.
The verification-contract amendment is recorded in
`docs/architecture/CONTRACT_DELTA_WINDOWS_ACCEPTANCE_2026-10-03.md`.

- Remove Linux Python cells, WSL/Linux clock qualification, Linux runner access,
  Docker/Linux hosted jobs and a complete hosted Gitea workflow from this queue's
  required acceptance. No new runner authorization or infrastructure update is
  needed for the Windows path. Do not retry those retired obligations.
- Keep Windows Python 3.11/3.12 installed/public-path proof, actual llama.cpp
  provider proof and current native Windows quality checks. Preserve all remaining
  assertions, test deadlines, declared platform skips and the 89% coverage floor.
- This is a user-approved scope reduction, not successful Linux/hosted verification.
  Existing POSIX code and CI definitions remain unchanged; they grant no Linux or
  Mac support claim and are not ATG-v1 execution prerequisites. No replacement
  Windows CI infrastructure or native Windows Docker target is introduced.
- Preserve earlier successes, failures and missing evidence in the exact
  [pre-amendment plan](../archive/architectural-truth/AT10032026-WINDOWS-SCOPE/PLAN_BEFORE_WINDOWS_SCOPE.md)
  and the workset history. Only this plan's current card and resume record govern
  execution. At amendment time eight goals were complete; the amendment itself
  did not close ATG-09/10. Their later accepted results are recorded below.

## Preserved starting point

| Evidence | Accepted observation and limit |
|---|---|
| Logging caller migration | `3bbb5c0a` / `v0.6.116`, pushed; explicit preparation migration checkpoint |
| Eight fixture repairs | `7d8daf38` / `v0.6.117`, pushed; all eight repaired cases pass; 48 assertions and existing timeouts retained |
| Complete source suite | One Windows Python 3.11 run: **11,584 passed, 0 failed, 93 skipped**; 5,653 inputs unchanged during execution |
| Coverage | **87.035153%**, failing the unchanged **89%** combined statement/branch gate; pytest exit 1 was the coverage verdict |
| Other checks | Ruff, strict taxonomy, critical no-op/dependency controls at their recorded scopes, docs and authority structure pass; structural checks are not runtime proof |
| Typing | Last recorded canonical Mypy result: **415 errors in 170 files**, at the earlier `v0.6.115` checkpoint; refresh before repair |
| Proof limits | No fresh complete Linux/installed/provider/hosted-CI acceptance; current-authority runtime proof remains explicitly unavailable |

The retained full-run evidence is `.tmp/fixture-goal-full-suite-{inputs,readback}.json`,
its XML/log/coverage JSON, and `.tmp/fixture-goal-publication.json`. These are local
artifacts, not guaranteed to exist in another checkout. The archived plan retains
the tracked result summary. Reuse proof only after checking its relevant inputs;
do not repeat the 73-minute suite solely to restate this starting point.

## Frozen scope and progress

- The goal IDs and finite worksets remain fixed; the user-directed Windows scope
  amendment above governs ATG-09 acceptance. ATG-01 resolves
  existing debt into finite worksets; it cannot invent new architecture requirements.
- A workset names concrete paths/symbols, the existing obligation, evidence needed,
  and batch IDs. Freeze it before editing. Add regressions caused by these changes
  to their originating batch; record unrelated discoveries under **Deferred findings**.
- Larger goals advance through cohesive batches, normally at most five production
  files. Record a justified larger ownership boundary before editing; this cannot
  widen the parent goal. Tests and necessary contract/docs updates accompany it.
- Measure progress as completed goals and completed frozen work items. Do not turn
  these unequal goals into an effort percentage or recalculate the old 60%/15%
  estimates. New findings do not silently increase the denominator.
- Completing this queue does not authorize a main merge, whole-lane retirement,
  or a claim that every historical architectural aspiration is implemented.
- Every goal's exit also requires a tracked proof/closeout link, updated queue and
  resume state, and a verified branch checkpoint under the contributor version,
  changelog, annotated-tag and push rules. Publish these checkpoints as goals finish;
  do not accumulate all ten goals into one final commit. Early checkpoints retain
  the still-open later quality gates explicitly; they are not release-readiness claims.

| ID | Goal | Starts after | Status |
|---|---|---|---|
| ATG-01 | Reconcile evidence and freeze the remaining worksets | Published `v0.6.117` inputs identified | complete: `20eaba3a` / `v0.6.118` |
| ATG-02 | Settle model-stream iterator and client lifetime | ATG-01 | complete: `b6a54b3e` / `v0.6.119` |
| ATG-03 | Finish already-inventoried required log producers | ATG-01 | complete: `5e878cc2` / `v0.6.120` |
| ATG-04 | Close the other frozen D ownership/input defects | ATG-01; affected ATG-02/03 work | complete: `9b2e91d9` / `v0.6.121` |
| ATG-05 | Finish the three named E2 hotspots | ATG-01; affected D repairs | complete: `64b39cb9` / `v0.6.122` |
| ATG-06 | Clear canonical typing debt in bounded batches | ATG-02 through ATG-05 | complete: `52b45773` / `v0.6.123` |
| ATG-07 | Restore the unchanged 89% coverage gate | ATG-02 through ATG-06 | complete: `1e5ce56f` / `v0.6.124` |
| ATG-08 | Verify fresh Windows packages and public paths | ATG-07 | complete: `b7ab34bb` / `v0.6.125` |
| ATG-09 | Complete Windows quality and provider proof | ATG-08 | complete: `f0551120` / `v0.6.143` |
| ATG-10 | Reconcile and publish the bounded revamp result | ATG-01 through ATG-09 | complete: `0b33356f` / `v0.6.144` |

## Goal cards

ATG-01's [closeout](../archive/architectural-truth/AT10012026-ATG01/CLOSEOUT.md)
and [frozen worksets](GOAL_WORKSETS.json) retain the original 67-batch inventory
across ATG-02 through ATG-06 and its now-closed dispositions. The original 415
typing diagnostics in 170 files are historical; canonical Mypy now passes. All 207
historical async rows retain their scoped reconciliations. This inventory is not
a second execution plan. The cards preserve the original acceptance contracts.

### ATG-01 — Reconcile evidence and freeze the remaining worksets

**Start:** Correct branch/worktree; identify the checkpoint and preserve any later
user edits. Read the current exception register and the final historical closeouts,
not every earlier journal entry.

**Work:** Reconcile superseded claims, especially the now-fixed logging callers,
guarded-mutation repair and eight fixture failures. Run canonical Mypy once and
reuse other unchanged evidence. Create `GOAL_WORKSETS.json` in this directory with
source fingerprints, finite ATG-02/03/04/05/06 worksets and batch IDs. It is an
evidence inventory, not a second execution plan. Inventory only already-recorded
C/D/E debt; do not conduct a new open-ended repository architecture review.

**Exit:** Every included defect has a named current owner/path, existing contract,
reproduction or explicit missing-proof case, and finite completion check. Already
satisfied items have evidence and are removed from pending work. Type counts are
current; environment prerequisites for ATG-08/09 are recorded without provisioning
new infrastructure. No runtime code or full-suite rerun is needed for this goal.

### ATG-02 — Settle model-stream iterator and client lifetime

**Start:** ATG-01 binds current `orket/workloads/model_stream_v1.py`,
`orket/streaming/model_provider.py` and their directly required owners/callers.

**Work:** Reproduce the remaining iterator/transport lifetime defects before repair.
Retain admitted stream work and cleanup through success, failure, cancellation,
timeout and shutdown. Preserve request/environment capture, target refusal and
existing event/commit semantics. Use the existing lifetime owner and provider
interfaces. Archived scratch candidates remain unapplied.

**Exit:** Real local HTTP streaming and observable close/cleanup controls pass,
including repeated cancellation, mid-stream failure and cleanup failure. No owned
task/client is abandoned; borrowed resources retain caller ownership. Applicable
input/admission and public streaming regressions pass. Controlled HTTP is labeled
as such; actual model inference remains ATG-09 proof.

ATG-02 scoped source proof: [closeout](../archive/architectural-truth/AT10012026-ATG02/CLOSEOUT.md)
and [receipt](../archive/architectural-truth/AT10012026-ATG02/VERIFICATION.json).
The final selection passes 150 cases; native structural gates and publication
pass. Later quality and installed/provider gates were open at that checkpoint;
ATG-09 now supplies the accepted current Windows scopes.

### ATG-03 — Finish already-inventoried required log producers

**Start:** ATG-01 identifies the remaining required producers after `v0.6.116`;
already-migrated optional callers are excluded.

**Work:** Migrate one frozen producer family per batch using the existing native
I/O owner and `docs/specs/LOG_WRITE_SETTLEMENT.md`. Preserve required versus optional
semantics, selected workspace/inputs, error precedence and completion authority.
Do not redesign the process-global writer or add another logging backend.

**Exit:** Each frozen producer has real append/publication, held-write cancellation,
native failure and partial-effect proof. Required failures cannot publish false
completion; required work settles before its owner returns. Existing preparation,
subscriber, overflow and fatal-writer controls remain green. A zero-item workset
closes by evidence, not by manufacturing replacement work.

ATG-03 scoped source proof: [closeout](../archive/architectural-truth/AT10012026-ATG03/CLOSEOUT.md)
and [receipt](../archive/architectural-truth/AT10012026-ATG03/VERIFICATION.json).
All five frozen sites pass the 251-case combined selection and native structural
gates. Annotated checkpoint publication passes; the later Windows gates are
now accepted by ATG-09 at their stated scopes.

### ATG-04 — Close the other frozen D ownership/input defects

**Start:** ATG-01 identifies concrete remaining application/storage/provider paths
and their existing obligations; wait for ATG-02/03 only where they are dependencies.

**Work:** Repair one owner family per batch: explicit invocation inputs, native
operation ownership, responsiveness and truthful cleanup/publication. Exclude
ATG-02/03 families and already-accepted boundaries. Existing marshaller runtime
defects may be included only if already recorded; its held requirements lane stays
closed. No arbitrary plugin purity proof, new effect system or global runtime rewrite.

**Exit:** Every frozen item passes its healthy and adverse public-path checks, with
actual file/SQLite/process/HTTP observations where applicable. Input mutation,
repeated cancellation, partial effects and native failures retain the specified
outcome. Dependency/core/decision controls pass at the claimed scope. Unrelated
transitive concerns are retained as findings, not silently added to this goal.

### ATG-05 — Finish the three named E2 hotspots

**Start:** Freeze current sizes and responsibilities for
`orket/application/workflows/orchestrator_ops.py`, `turn_tool_dispatcher.py` and
`turn_message_builder.py`; relevant D behavior is stable.

**Work:** Extract only the still-oversized responsibilities in those three modules
by their existing authority/lifetime boundaries. Retain their public contracts,
phase-selected owners and input timing. Reuse existing modules where possible;
no new coordinator facade, delegation proxy or copied authority.

**Exit:** The three roots meet the existing 400-line/70-line limits, or carry a
specific correctness exception allowed by repository policy; new structures meet
the class limits. Measured ownership/size debt decreases and real phase/effect/
cleanup regressions prove parity. Already-compliant roots require no extraction.
This goal does not expand to every oversized file in the repository.

### ATG-06 — Clear canonical typing debt in bounded batches

**Start:** ATG-02 through ATG-05 are complete; refresh their effect on ATG-01's
diagnostic inventory. Keep removed, remaining and introduced diagnostics separate.

**Work:** Resolve one owning module group per batch, normally at most five product
files. Use canonical definitions and accurate protocols/annotations. Preserve
behavior. No blanket ignores, weakened configuration, new `Any` escapes, suppressed
categories, compatibility shims or architecture rewrite to make Mypy green.

**Exit:** `python -m mypy orket/ --ignore-missing-imports` exits zero with the existing
configuration; touched behavior and import/contract controls pass, and canonical
Ruff remains green. Necessary runtime corrections receive their own real proof;
a contract decision beyond this queue is an explicit blocker, not a typing waiver.

### ATG-07 — Restore the unchanged 89% coverage gate

**Start:** Runtime, extraction and typing batches are closed; bind one candidate.
Use the retained coverage JSON to distinguish unmeasured child execution from
actually untested behavior. Zero-reported native workers are candidates to inspect,
not permission to count unobserved execution.

**Work:** Add meaningful missing behavior/branch tests in bounded owner batches.
Correct a demonstrated measurement defect only with native child counterexamples.
Preserve all canonical coverage configuration, source inclusion, assertions,
timeouts and skips; no threshold reduction, coverage exclusions or structural
tests presented as live behavior.

**Exit:** One complete canonical run on the stabilized candidate has zero failures
and at least **89% combined coverage**. Run
`python -m pytest tests/ --cov=orket --cov-config=pyproject.toml --cov-fail-under=89`
with `ORKET_DISABLE_SANDBOX=1`; retain source fingerprints, full counts, skips,
warnings and measured totals. Use targeted proof while iterating; another complete
run requires a changed candidate or a recorded invalid-run cause, never impatience.

### ATG-08 — Verify fresh Windows packages and public paths

**Start:** ATG-07's candidate and affected regression selection are frozen; Windows
Python 3.11 and 3.12 environments are available. Missing prerequisites are recorded.

**Work:** Build clean wheel/source artifacts without stale build inputs. Verify
package membership, byte/version identity and `pip check`; install outside the
checkout. Run existing affected controls and public CLI, API, demo/quickstart and
owned cleanup flows on the declared supported Windows Python cells.

**Exit:** Each required cell has actual installed origins, matching package content,
public effects/refusals and cleanup evidence. Help/import checks are only structural
proof. Any package/runtime repair invalidates affected earlier proof and receives
a bounded regression rerun before this card closes.

ATG-08 installed proof: [closeout](../archive/architectural-truth/AT10012026-ATG08/CLOSEOUT.md)
and [receipt](../archive/architectural-truth/AT10012026-ATG08/VERIFICATION.json).
Fresh Windows Python 3.11.14 and 3.12.2 cells each pass 6,231 cases with zero failures
and three unchanged Gitea opt-in skips. Exact case identity, installed package bytes,
source and harness inputs were bound to that original checkpoint. Atomic
publication and clean readback are verified at `b7ab34bb` / `v0.6.125`. ATG-09
reconciles the later reload repair as 6,236 passes / 3 skips per interpreter;
original and replacement cases are not added wholesale.

### ATG-09 — Complete Windows quality and provider proof

**Start:** ATG-08 passes. Bind the current Windows candidate and retained proof.
Use native Windows Python 3.11/3.12 evidence; neither a Linux host nor a hosted
runner is an admission requirement. Reuse valid accepted inputs before rerunning.

**Work:** Run the existing full quality selection on native Windows with
`ORKET_DISABLE_SANDBOX=1`. Keep the complete source selection, branch measurement
and canonical command:

```text
python -m pytest tests/ --cov=orket --cov-config=pyproject.toml --cov-fail-under=89
```

Keep the existing canonical local checks:

```text
python -m ruff check orket tests
python -m mypy orket/ --ignore-missing-imports
python scripts/governance/check_dependency_direction.py
python scripts/governance/enforce_test_taxonomy.py --strict
python scripts/governance/check_noop_critical_paths.py
python scripts/governance/check_docs_project_hygiene.py
python scripts/governance/check_current_authority.py
python scripts/governance/render_current_authority.py --check
python scripts/governance/check_install_surface_convergence.py
```

These are existing commands, not a new test framework. Accepted unchanged command
evidence may be reused at its exact relevant inputs. The Windows full-suite result
must cover the reload repair; historical v0.6.124 coverage cannot do so. Bind source,
environment, counts, skips, warnings, coverage data and native process settlement.
Do not change skip declarations or exclude failing Windows cases to pass the gate.

Reuse accepted installed Windows 3.11/3.12 composites and actual llama.cpp
public-library completion/cancellation proof when relevant sources/artifacts match.
If a repair invalidates them, rerun only the affected existing obligations. Keep
the selected provider and observe original owners/cleanup. Docker/Linux sandbox
deployment and hosted-job scheduling are outside this Windows-only acceptance;
their old missing proof remains explicit history, not replacement work.

**Exit:** Required Windows source quality, installed/public paths and provider
evidence pass with exact source/artifact/outcome identity and owned cleanup. The
full Windows suite has zero failures and at least **89% combined coverage**; local
structural checks remain distinct from runtime proof. Publish ATG-09's tracked
closeout and verified versioned branch/tag checkpoint. No hosted green status,
Linux/Mac compatibility or whole-product correctness is inferred.

ATG-09 Windows proof: [closeout](../archive/architectural-truth/AT10032026-ATG09/CLOSEOUT.md)
and [verification](../archive/architectural-truth/AT10032026-ATG09/VERIFICATION.json).
The current full suite passes 12,987 cases with 93 unchanged skips and
89.21575503742372% combined coverage. Local structural gates pass; retained
installed/provider evidence is hash-bound and reusable. The matching v0.6.143
branch/tag readback and clean worktree succeeded; ATG-10 retains that exact witness.

### ATG-10 — Reconcile and publish the bounded revamp result

**Start:** All preceding cards pass. If an external gate is blocked, a partial
status report may be prepared, but this goal and the campaign remain incomplete.

**Work:** Reconcile the finite worksets, exception register, canonical authority,
compatibility obligations and accumulated proof. Run applicable final structural,
docs and release checks. Reuse unchanged complete-suite evidence. Commit, annotate
the matching version tag and push the existing branch under contributor policy;
verify remote identities and a clean worktree. Do not merge `main`.

**Exit:** Every queued outcome has accepted evidence and a tracked closeout, no
required gate is red or missing, and publication is verified. State exactly which
C/D/E obligations were closed and which broader limitations remain. Whole-lane
retirement and new capability admission still require the user's separate decision.

## Exclusions and deferred findings

CAP-1 new workload families, CAP-2 hostile-code containment, CAP-3 new performance
targets, formal-proof expansion, paused cloud lanes, provider switching, 0.7.0
compatibility removals, a main merge and applying the six archived proposal bundles
are outside ATG-v1. Reading history does not activate its proposed decisions.
The authority checker's explicit lack of general current-runtime proof remains a
claim limit; adding a new proof-adapter system is outside this queue.

Deferred finding (structural observation, not live proof):
`orket/marshaller/process.py::run_process` directly awaits subprocess creation and
communication and catches timeout only. Caller cancellation/descendant teardown and
ambient environment capture are not established by the frozen native-file worksets.
No historical row assigns this process owner to ATG-v1. Retain it as separate debt;
B03/B04 native-file and healthy real Git controls do not prove adverse process cleanup.
Do not expand this queue or its denominator without user authorization. Historical
capability/compatibility obligations remain in the archive and active specs.

Historical finding, repaired by PRR-02 in matched 0.7.2 (original B17-closing
observation follows unchanged): the existing
ResponseParser residue normalization removes prose whitespace. The grounding
check consequently misses `Maybe this...` after it becomes `Maybethis...`; a
punctuation-separated marker remains detectable. This coverage batch retains the
counterexample and does not change parser/grounding behavior or add a new goal.

## Two-day completion plan

Use the user's next usage reset/kickoff as T0. Work through ATG-09 then ATG-10;
the ten-goal denominator and accepted predecessor worksets stay unchanged. End by
the earlier of T0+48 hours and the verified downgrade time. Until account timing
is supplied, finish during October 5 using October 6 at 00:00 America/Denver
(06:00 UTC) as a conservative planning cutoff, not a verified billing timestamp.

| Window | Existing work and deliverable |
|---|---|
| Day 1, first hour | Verify branch/publication, current process state and relevant Windows/provider evidence hashes; bind one native Windows source candidate. |
| Day 1 | Run the full Windows quality/coverage command early. During its source freeze, do independent read-only evidence review and prepare the ATG-10 draft. Diagnose and fix demonstrated Windows failures in bounded batches, then refresh affected proof. |
| Day 2 | Finish remaining Windows verification, audit evidence and publish ATG-09. Then reconcile the finite worksets/exception register and publish ATG-10 separately. Advance immediately when prerequisites pass. |
| Final six hours | Reserve time for verification, native process settlement, publication and exact handoff. Admit no campaign whose existing bounds and cleanup cannot fit. |

Use bounded `gpt-6.1-sol` / `xhigh` subagents for substantial independent analysis,
implementation or evidence review; keep edits disjoint. The primary owns source
freezes, integration, final verification, publication and this record. Handle
retrieval and small edits directly. Reuse unchanged accepted proof; repeat a full
campaign only for a changed candidate or an explained invalid run. Preserve failed
receipts and remaining limits. No Linux, WSL, runner or infrastructure work belongs
to this schedule. No new targets, paid credits, API spending or main merge.

ATG-10 still starts only after accepted/published ATG-09. Its existing bounded
reconciliation covers the plan/worksets/README, exception reasons, roadmap,
version/changelog and archived closeout/verification. Refresh the old ignored
readiness proposal against this scope before use; its eleven-job admission is
superseded. Run applicable metadata/release checks and keep current-authority
runtime proof explicitly unavailable. If finished early, report completion;
available time does not reopen other lanes or deferred capabilities.

Official [Pro documentation](https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers)
ties continued access to the current billing period. The [pricing documentation](https://learn.chatgpt.com/docs/pricing)
describes usage limits separately. No extra week or exact account cutoff has been
verified; budget for at most two days. The user's kickoff time remains scheduling
input, not a Linux/runner prerequisite.

## Post-queue release authorization

### Historical release cleanup: 0.7.1 completion checkpoint

The published 0.7.1 result is complete. The original prepublication checkpoint
below retains its scope; it is not outstanding release work.

The user requested completion of remaining release changes after matched core/SDK
0.7.0 were published at `43c3650d1a29822b2091a75474902c726bcb5048`.
The concrete remaining item is `BT4-FIXTURE-SYNC-RETIRE`. Its bounded workset is
the two refusing fixture classes, their deprecated exports, dependent tests,
current contracts and matched core/SDK packaging metadata. Production callers of
the classes are absent; constant/security-error consumers retain their identities.
Other aliases and broader ATG limitations keep their separate contracts.

An actual installed counterexample additionally found `orket sdk --version`
printing `OK: None None (None)` while JSON was correct. The same release workset
fixes the host text renderer and requires exact installed text/JSON output. First
candidate bytes and the failed regression remain under `.tmp/release-0.7.1/`;
the corrected build/run is `.tmp/release-0.7.1/r02/state.json`.

The corrected candidate passes 372 selected cases and three additional installed
SDK CLI cases on Python 3.12. Actual installed async fixtures and CLI/API/workflow
paths pass on Windows 3.11/3.12, with the existing degraded startup warning retained.
Exact version text/JSON, strict template validation, standalone SDK isolation and
canonical structural gates pass. Both fixture classes and their deprecated exports
are absent. Their removal obligation and the SDK text-rendering defect are closed
once final publication readback succeeds; other compatibility duties remain.

Acceptance requires actual native async fixture behavior/cleanup, all removed
class exports absent in source and installed packages, SDK/public-path controls,
canonical structural/docs gates, exact package hashes, and published matching
0.7.1 tags/assets. The 0.7.0 releases remain immutable. Contract:
`docs/architecture/CONTRACT_DELTA_FIXTURE_RETIREMENT_0_7_1_2026-10-03.md`.
Proof: `docs/releases/0.7.1/PROOF_REPORT.md`; stable evidence:
`benchmarks/results/releases/0.7.1/`. Native execution/build/check and publication
receipts: `.tmp/release-0.7.1/r02/state.json`, `.tmp/release-0.7.1/final-checks.json`,
and `.tmp/release-0.7.1/publication.json`. Freeze tracked inputs during each run;
inspect an existing receipt before retrying. Preserve the local skip-worktree
operational override and substitute its Git blob only in packaging snapshots.
The accepted patch is complete when the publication receipt reports `verified`
and the two matching annotated tags/GitHub assets identify the same commit and
verified bytes. Then no release cleanup remains; the ATG queue stays 10/10.

### Published 0.7.0 disposition (historical)

The user accepted the completed Windows queue, then explicitly requested merge
to main and release 0.7.0 on October 3. That instruction supersedes this queue's
earlier no-merge/minor-release exclusion for this release only. Main fast-forwarded
from `112569206211aaa5a009a5e5ef7af43af545c744` to the verified ATG-10 commit
`0b33356f0e666ec67eb7c386dfaff706820960d6`. The local skip-worktree operational rock
was preserved byte-for-byte and is excluded from release artifacts and commits.

Core and SDK 0.7.0 are released together at their matching annotated tags once the
publication witness below succeeds. The SDK implementation is unchanged from
0.7.0a1 except version identity. Existing command aliases remain through 0.7.x;
the accepted delta and migration requirements live in
`docs/architecture/CONTRACT_DELTA_CORE_SDK_0_7_0_2026-10-03.md`.
Release proof/notes: `docs/releases/0.7.0/`. Stable machine evidence:
`benchmarks/results/releases/0.7.0/`; private execution/process record:
`.tmp/release-0.7.0/state.json`. The frozen packaging snapshot excludes the local
operational override. Fresh Windows 3.11/3.12 installed public-surface proof,
SDK isolation, API store/authentication/cleanup, 185 focused cases and canonical
structural gates pass; initial failures and exact artifact hashes are retained.
Final checks freeze current inputs at `.tmp/release-0.7.0/final-checks.json`.
Publication is complete only after `.tmp/release-0.7.0/publication.json` verifies
both annotated tags, atomic main/tag push, remote identities and downloaded GitHub
asset bytes. Its public `publication.json` asset is linked from the v0.7.0 release.
Inspect this receipt before resuming an interrupted publication. Once it succeeds,
no release action remains; do not reopen the completed ATG queue.
This release does not retire the broader umbrella or add Linux/hosted requirements.

Remaining release drift: `BT4-FIXTURE-SYNC-RETIRE` originally targeted the 0.7.0
cutover, but removal is not complete. Orket Core retains the existing refusing
`FixtureVerifier.verify` / `VerificationEngine.verify` tombstones and deprecated
domain exports under the explicit release delta. No new removal version is
assigned. Caller inventory and separate contract acceptance are still required
before retirement; no synchronous execution or hidden forwarding is restored.

## Historical resume record (accepted ATG checkpoint)

This accepted ATG record retains its original evidence and limitations. Later
0.7.0/0.7.1/0.7.2 releases supersede only the scopes identified above, including
fixture retirement, parser grounding and installed Windows provider paths.
Its old next-action and missing-proof statements do not activate work.

- Current checkpoint: **ATG-10 / v0.6.144**. ATG-01 through ATG-09 are
  complete; **10 of 10 complete**. Publication was verified at
  `0b33356f0e666ec67eb7c386dfaff706820960d6`; the publication condition below is satisfied.
  No executable goal remains after that witness. This is the bounded Windows
  queue result, not whole-lane retirement or whole-product conformance.
- ATG-09 is accepted and published: commit
  `f05511206f676b894313e9e39669971de0382aa7`, annotated `v0.6.143` object
  `123fefd8131a2cadbeefbee31f55607217b1063d`. Atomic push, exact remote branch/tag
  and peeled commit identities, and clean worktree were verified before ATG-10.
  Its actual publication and seven final checks (including 17 release passes)
  are retained in the [ATG-10 verification](../archive/architectural-truth/AT10032026-ATG10/VERIFICATION.json).
- Current source proof is the native Windows Python 3.11.14 run bound to
  `a6b99e575682d9b721983381e75f80402c8018d2` / v0.6.142 plus the prelaunch plan link:
  **12,987 passed / 0 failed / 93 unchanged skips**, 3 pytest warnings and one
  coverage merge warning; **89.21575503742372%** combined coverage at floor 89.
  All 5,746 frozen inputs remained unchanged. Owner/pytest settled and all 5,820
  sampled descendants were absent. Raw evidence: `.tmp/atg09-windows-quality.json`
  and `.tmp/atg09-windows-quality/A01/`; tracked scope/hashes:
  [ATG-09 verification](../archive/architectural-truth/AT10032026-ATG09/VERIFICATION.json).
- Coverage limits: one malformed child shard was discarded; six pre-existing
  namespace files remain outside default unexecuted-source discovery. The same
  1,216 files appear in old/current reports. Separate static analysis adds all six
  omitted files (133 statements + 38 branches) with zero hits:
  **89,040 / 99,974 = 89.06315642066937%**. This does not replace measured proof or
  establish complete child capture. The exact paths, hashes and warning remain
  tracked in the ATG-09 audit. No exclusions, deadlines, assertions or skips changed.
- Fresh Ruff, dependency, strict taxonomy (13,080 items) and critical no-op gates
  pass. Canonical Mypy reuse is bound to unchanged relevant inputs. Windows 3.11/
  3.12 installed composites retain **6,236 passes / 3 skips each**; source fixture
  proof retains **119 passes / 0 skips**. Actual llama.cpp library completion,
  interaction cancellation and caller cancellation retain original iterator/
  response/client/transport settlement. Runtime/artifacts remain v0.6.136; fixture
  proof remains v0.6.140. Only release/evidence/status metadata changed afterward.
- Finite reconciliation: all **67** ATG-02/03/04/05/06 batches (**2/4/9/3/49**)
  are closed; all **207** historical rows retain their original scoped dispositions
  (16 not-open, 188 satisfied by retained scoped proof, 3 satisfied by scoped proof).
  All three named hotspots, 27 coverage batches and seven coverage reconciliations
  retain their accepted records. No denominator or new executable goal was added.
- Closed C/D/E scope: canonical dependency/authority/checker and typing gates;
  frozen model-stream, five required-producer and nine other ownership/input
  families; the three named E2 roots; unchanged-floor Windows coverage; scoped
  Windows packages/public paths and actual llama.cpp library flows. The
  [bounded closeout](../archive/architectural-truth/AT10032026-ATG10/CLOSEOUT.md)
  binds predecessor links, compatibility duties and limitations.
- Compatibility stays binding: source `main.py`/hidden `--rock` through 0.6.x
  until an explicit 0.7.0 delta; replay diagnostics wrapper; latest verification
  artifact; flat runtime aliases with unassigned removal version; current event
  taxonomy and ReviewRun/path specifics. No new shim or removal is authorized.
- Remaining blockers or drift: no required Windows behavior gate is red.
  General current-authority runtime proof stays unavailable. Broader transitive
  C/D/E and callback/plugin claims, marshaller subprocess cancellation/descendant/
  environment ownership and ResponseParser whitespace/grounding residue remain
  debt. Linux/Mac, hosted Quality, API/installed-provider execution, live Docker
  sandbox and remote inference/server teardown remain unverified. The selected
  llama.cpp server is operator-owned; no provider switch or infrastructure action
  occurred. Historical failed/missing outcomes remain unchanged.
- Final validation/publication witnesses: `.tmp/atg10-windows-closeout-checks.json`
  and `.tmp/atg10-windows-closeout-publication.json`. Completion requires all final
  docs/authority/install/release checks and 17 existing release cases to pass,
  matching annotated **v0.6.144**, atomic branch/tag push, exact remote identities
  and a clean worktree. The matching tag identifies this checkpoint immutably;
  a future branch may advance. Inspect the stable receipt before retrying any
  interrupted publication. Current metadata is frozen during final validation.
- Next exact action: verify those final witnesses. Once successful, stop this
  queue; do not activate maintenance, deferred findings or new capabilities.
  Reopen only for an explicit scoped user request. The umbrella remains active.
- Session kickoff: 2026-10-03T21:45:57Z; planned cutoff: 2026-10-05T21:45:57Z
  subject to any earlier verified downgrade time. No billing timestamp is inferred.

## Reusable goal prompt

```text
Verify the canonical final ATG-v1 resume record and matching v0.6.144 publication.
If its atomic push, remote identities and clean-worktree witness succeeded, the
bounded Windows queue is 10/10 and has no next executable goal. Preserve its
broader limitations and compatibility duties; do not reopen work without an
explicit scoped request. If publication was interrupted, inspect its exact stable
receipt and current refs before resuming only that unfinished authorized action.
```

## Historical reference anchors

<a id="c-one-enforceable-dependency-model"></a>
The original C policy record is retained in the
[historical plan](../archive/architectural-truth/AT10012026-GOAL-QUEUE/REMEDIATION_PLAN_HISTORY.md#c-one-enforceable-dependency-model).

<a id="d1-coreeffect-separation-and-current-proof-2026-09-14"></a>
The original D1 record is retained in the
[historical plan](../archive/architectural-truth/AT10012026-GOAL-QUEUE/REMEDIATION_PLAN_HISTORY.md#d1-coreeffect-separation-and-current-proof-2026-09-14).
