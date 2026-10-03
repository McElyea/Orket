# Architectural Truth: Executable Goal Queue

Last updated: 2026-10-03 (America/Denver)
Status: Windows ATG-09 evidence accepted; v0.6.143 publication and ATG-10 remain
Queue: ATG-v1 — ten goals; Windows-only scope amended by the user on 2026-10-03
Owner: Orket Core
Worktree: `C:/Source/Orket-architectural-truth`
Branch: `codex/architectural-truth-bt0`
Next goal: **ATG-10**, after verified ATG-09 publication

## Purpose and authority

Use this file as the target for one continuing goal. Complete the listed goals in
dependency order without requiring a replacement user prompt after each one.
This is the lane's single canonical execution plan, indexed by `docs/ROADMAP.md`.
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
  execution. Eight goals remain complete; the amendment does not close ATG-09/10.

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
| ATG-09 | Complete Windows quality and provider proof | ATG-08 | Windows evidence accepted; completes with v0.6.143 publication |
| ATG-10 | Reconcile and publish the bounded revamp result | ATG-01 through ATG-09 | ready after verified v0.6.143 publication |

## Goal cards

ATG-01's [closeout](../archive/architectural-truth/AT10012026-ATG01/CLOSEOUT.md)
and [frozen worksets](GOAL_WORKSETS.json) bind the current evidence and 67 pending
batches across ATG-02 through ATG-06. These are inventory/evidence, not a second
execution plan. The 207 historical async rows are reconciled individually;
typing remains 415 diagnostics in 170 files. Later goals retain their fixed gates.

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
pass. Later quality and installed/provider gates stay open.

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
gates. Annotated checkpoint publication passes; later queue gates remain open.

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
source and harness inputs remain unchanged. Atomic publication and clean readback
are verified at `b7ab34bb` / `v0.6.125`.

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
installed/provider evidence is hash-bound and reusable. Publication closes
this goal only when its matching v0.6.143 branch/tag readback succeeds.

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

Deferred finding (observed public contract failure, B17-closing): the existing
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

## Resume record

- Current card/batch: **ATG-09 acceptance/publication -> ATG-10**. Eight predecessor
  goals are published. Verified `v0.6.143` publication makes **9 of 10 complete**;
  ATG-10 starts immediately after that witness succeeds.
- Source candidate: `a6b99e575682d9b721983381e75f80402c8018d2` / `v0.6.142`, plus
  the prelaunch plan receipt link. The 5,746-input freeze stayed unchanged.
  `.tmp/atg09-windows-quality.json` records the completed native Python 3.11.14
  run: **12,987 passed, 0 failed, 93 skipped, 3 pytest warnings** plus one retained coverage merge warning, **89.21575503742372%**
  combined statement/branch coverage. Owner/pytest processes settled; all 5,820
  sampled descendant identities were absent at readback. Raw outputs remain in
  `.tmp/atg09-windows-quality/A01/`; this is mixed-layer source execution, not
  whole-product proof. Existing assertions, deadlines, skips and floor are intact.
- Measurement limits: one malformed child coverage shard was discarded; no
  execution from it is credited. Six pre-existing namespace files remain outside
  default unexecuted-source discovery in both old and current reports. The
  configured 1,216-file report selection is unchanged; complete capture of every
  child or Git-visible file is not claimed. Exact paths, warning and shard hash
  remain in `.tmp/atg09-windows-quality-audit.json` and the tracked verification.
  Separate static confidence analysis adds all six omitted files (133 statements
  and 38 branches) with zero execution credit: 89,040 / 99,974 = 89.06315642066937%,
  still above 89%. This does not change or replace the observed coverage report.
- `.tmp/atg09-windows-local-checks.json` records canonical Ruff, dependency,
  strict taxonomy (13,080 items) and critical no-op success. Mypy remains valid
  by the exact input audit in `.tmp/atg10-windows-reconciliation-audit.json`.
  Structural gates do not execute general product behavior.
- `.tmp/atg09-windows-resume-evidence-audit.json` binds reusable Windows 3.11/3.12
  installed composites (**6,236 passes / 3 unchanged skips each**), the **119-case**
  fixture proof and actual llama.cpp completion/interaction-cancellation/caller-
  cancellation with original iterator/client/response/transport settlement.
  Runtime/artifacts remain `v0.6.136`; fixture inputs remain `v0.6.140`. Packaging
  differs only by version metadata. No installed/provider campaign was repeated.
- ATG-09 tracked closeout: `../archive/architectural-truth/AT10032026-ATG09/`.
  Final metadata/release validation: `.tmp/atg09-windows-closeout-checks.json`.
  Publication witness: `.tmp/atg09-windows-closeout-publication.json`, matching
  annotated `v0.6.143`, remote branch/tag identities and clean worktree. The
  receipt is mutable until publication finishes; inspect it before any retry.
- Next exact action: finish/verify the ATG-09 metadata checks and v0.6.143 atomic
  branch/tag publication, then reconcile the finite worksets, exception register,
  proof limits and roadmap under ATG-10; publish its separate patch checkpoint.
  Reuse the accepted full suite while runtime/test/configuration inputs match.
- Remaining blockers or drift: no Windows acceptance blocker is known. ATG-10
  and its publication remain open. Broader transitive C/D/E findings, marshaller
  process ownership, grounding residue normalization and compatibility windows
  remain separate debt. General current-authority runtime proof stays unavailable.
  Linux/Mac, hosted Quality, API/installed-provider and remote-server teardown
  are not established; retired failed/absent evidence remains unchanged history.
- This resumed session began 2026-10-03T21:45:57Z. The two-day planning cutoff is
  2026-10-05T21:45:57Z, subject to an earlier verified downgrade time; no billing
  timestamp is inferred. No Linux/WSL, runner or infrastructure work is admitted.

## Reusable goal prompt

```text
Verify the ATG-09 v0.6.143 branch/tag publication in the canonical resume record,
then complete ATG-10 in C:\Source\Orket-architectural-truth on
codex/architectural-truth-bt0 without another task prompt. Reuse the accepted
Windows source, installed and llama.cpp proof at matching inputs. Reconcile only
the fixed queue, preserve broader debt/compatibility and publish the final bounded
closeout separately. Do not run Linux/WSL/hosted campaigns or merge main.
```

## Historical reference anchors

<a id="c-one-enforceable-dependency-model"></a>
The original C policy record is retained in the
[historical plan](../archive/architectural-truth/AT10012026-GOAL-QUEUE/REMEDIATION_PLAN_HISTORY.md#c-one-enforceable-dependency-model).

<a id="d1-coreeffect-separation-and-current-proof-2026-09-14"></a>
The original D1 record is retained in the
[historical plan](../archive/architectural-truth/AT10012026-GOAL-QUEUE/REMEDIATION_PLAN_HISTORY.md#d1-coreeffect-separation-and-current-proof-2026-09-14).
