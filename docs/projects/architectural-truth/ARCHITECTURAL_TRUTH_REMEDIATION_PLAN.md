# Architectural Truth: Executable Goal Queue

Last updated: 2026-10-02 (America/Denver)
Status: Active implementation; eight goals complete, ATG-09 local acceptance complete and hosted Quality blocked
Queue: ATG-v1 — ten fixed goals for the existing revamp
Owner: Orket Core
Worktree: `C:/Source/Orket-architectural-truth`
Branch: `codex/architectural-truth-bt0`
Next goal: **ATG-09**

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

- The goal IDs, outcomes and exclusions below are fixed for ATG-v1. ATG-01 resolves
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
| ATG-09 | Complete applicable Linux, provider and hosted Quality proof | ATG-08; required environments available | blocked: local installed/provider proof accepted; existing hosted runners unavailable |
| ATG-10 | Reconcile and publish the bounded revamp result | ATG-01 through ATG-09 | waiting |

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

### ATG-09 — Complete applicable Linux, provider and hosted Quality proof

**Start:** ATG-08 passes. Existing Linux Python 3.11/3.12 cells, llama.cpp
model/endpoint and hosted Gitea access are available. Record missing inputs rather than swapping
providers, provisioning cloud resources or weakening deadlines.

**Work:** Run the existing applicable Linux installed selections and `.gitea`
Quality matrix against the identified commit. Exercise the changed provider-backed
public flow with actual llama.cpp inference and observed cleanup. Routine proof
keeps sandbox disabled. Intentional sandbox acceptance must be separately in the
frozen existing obligations and prove teardown in the same path.

**Exit:** Required cells/jobs and live provider proof pass with commit, environment,
artifact and outcome identity. Old Linux clock observations must be reproduced or
cleared on the current host; controlled clocks do not prove host-clock reliability.
An unavailable cell remains blocked, never passed or silently made optional.

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

## Resume record

- Current card/batch: **ATG-09 / ATG09-P01**. **8 of 10 goals complete**.
  Available local installed/provider acceptance is complete; required hosted Gitea
  Quality remains blocked. ATG-10 stays dependent. User authorized resumption and
  repair/update of both existing local blockers. The later one-hour infrastructure
  exception expires **2026-10-03 05:53:22 UTC**; no provider switch or main merge.
- Checkpoint: **v0.6.130**, based on `20ac9de9` / `v0.6.129`, updates the Gitea
  deployment image and records the finite infrastructure exception. Receipts are
  `.tmp/atg09-infra-checks.json` and `.tmp/atg09-infra-publication.json`; verify their
  terminal status, annotated tag and remote identities. `platform_worksets.infrastructure_repair`
  binds this checkpoint. Accepted local fixture/provider/installed evidence remains
  bound by `platform_worksets.local_acceptance` and its v0.6.129 receipts.
- Local software: official llama.cpp **b11146 / 7fe450e19**, CUDA 12.4, is installed
  at `D:/llama.cpp-releases/b11146`; older copies remain. The existing GGUF serves
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l` at `http://127.0.0.1:8080/v1`.
  Manual launcher: `D:/llama.cpp-releases/Start-Orket-Llama.ps1`; logs are under
  `D:/llama.cpp-releases/orket-server/`. Server PID 33276 is operator owned and was
  intentionally left running. Update/readiness receipts are `.tmp/atg09-llama-update.json`
  and `.tmp/atg09-llama-repair-proof.json`; inspect live process/health before reuse.
- Clock repair: Windows Time was started and synchronized to its existing
  `time.windows.com` source, with backed-up network-start/stop service policy.
  Ubuntu's duplicate `systemd-timesyncd` is now **disabled and inactive**, while
  existing WSL PHC synchronization and genuine `NTPSynchronized=yes` remain.
  `.tmp/atg09-clock-service-persistent.json` retains the exact change and reversal
  (`systemctl enable --now systemd-timesyncd.service` inside Ubuntu).
  Persistence through an actual Ubuntu restart is verified; Windows reboot and
  network-transition behavior remain unverified. WSL 2.6.3 is retained; a newer
  package was not required for the passing local proof, and the known moved-distro
  startup concern remains relevant to this Ubuntu installation on `V:`.
- Clock evidence: A03's earlier 60-second pass did not prove sustained stability;
  full Linux 3.11 later recorded 39 steps above 10ms. A04 failed after the temporary
  service stop was undone by an Ubuntu restart; its journal preserves that fact.
  After the persistent change, **A05 passes**: 60.009528 synchronized quiet seconds
  within 100.174335s, with qualified-window steps from -55.29us to +6.370654ms.
  The earlier 20.090341ms step and two unsynchronized reads remain in its raw result.
  Original 60s quiet / 240s ceiling / 10ms step / 280s outer limits are unchanged.
  `.tmp/atg09-persistent-clock.json`, `.tmp/atg09-clock-A05-audit.json` and
  `.tmp/atg09-clock-lifecycle-audit.json` retain observations and process identities.
  Another qualification requires a demonstrated environment change. Long-term
  stability and the exact adjustment caller are not established by this gate.
- Installed evidence uses unchanged **v0.6.125 / b7ab34bb** core and SDK artifacts.
  Linux A02 full runs retain Python 3.11 **6,225 passes / nine skips** and Python 3.12
  **6,224 passes / one failure / nine skips**. The sole failure is the existing
  exact-content assertion reading an empty interpreter-finalization marker.
  The fixture now writes/closes a staging file and atomically publishes the marker;
  all assertions, deadlines, signal behavior and skip rules remain unchanged.
- R01 independently rechecks both affected reload files in Linux/Windows Python
  3.11/3.12: **16 passes per cell, 64 total, no failures/skips**, with frozen source,
  installed origins and all 1,242 core / 31 SDK namespace bytes unchanged. New
  separate harnesses overlay only the repaired helper. All commands settle normally;
  each cell completes below its 600s admission/completion limit. Native command
  waits enforce the remaining budget; the launcher has no independent hard outer
  watchdog. The original failed run is retained, not relabeled as passing.
  Composite totals replace all 16 prior scoped outcomes: each Linux cell has
  **6,225 passes / nine declared skips**; each Windows cell has **6,231 passes /
  three retained Gitea opt-in skips**. Thirty-four source-only controls remain separate.
  Receipts: `.tmp/atg09-linux-{freeze,cells,proof,launch}.json`,
  `.tmp/atg09-reload-{freeze,proof,launch}.json` and
  `.tmp/atg09-local-acceptance-audit.json`. Raw timing samples remain observations
  for readback, not a new campaign-wide gate or long-term clock guarantee.
  Linux pytest monitors cover 30.719s/32.371s, with maximum absolute sampled steps
  1.209951ms/1.110825ms; admission/readback gaps were not continuously monitored.
  Windows raw flags remain: both pinned interpreters report 15.625ms wall/monotonic
  resolution, consistent with the observed 10-13.7125ms residuals. Those flags do
  not establish actual Windows host steps. The locked A02 artifact audit passes;
  an earlier audit whose helper changed mid-readback is retained as invalidated.
- Provider proof is **primary / success** for three actual llama.cpp SSE cases
  through public `run_builtin_workload(model_stream_v1)`: completion, interaction
  cancellation and caller cancellation. Original iterator/client/response/transport
  owners settle, interaction state is empty and no pending tasks remain. Caller
  cancellation stays cancellation; session close retains its fail-closed result.
  Process 8404 exited 0 and was absent. Receipts are `.tmp/atg09_provider_inputs.json`,
  `.tmp/atg09_provider_result.json` and `.tmp/atg09-provider-launch.json`. Existing
  12s/60s/90s/10s limits and the 300s process ceiling remain. Scope is the public
  library flow; API HTTP transport, installed-provider execution and remote inference
  teardown are not established by this proof. Reuse it while relevant inputs match.
- Gitea repair: existing `vibe-rail-gitea` now serves **28.0.0** at
  `http://localhost:3000/Orket/Orket`. Live health, repository/main identity and all
  452 workflow records are preserved. A stopped-container backup at
  `D:/Orket-Gitea-Backups/pre-28.0.0-ATG09` matches all 564 source file hashes and
  passes SQLite integrity checking. `.tmp/atg09-gitea-upgrade.json` retains proof.
  Compose now pins 28.0.0 and preserves Actions run history (`RUN_RETENTION_DAYS=0`).
  The effective compose file is this branch's `infrastructure/docker-compose.gitea.yml`,
  with project `infrastructure` and project directory `C:/Source/Orket/infrastructure`
  so the existing data mount remains authoritative. The separate main checkout's
  older compose file is unchanged and must not replace the new deployment file.
  Rollback requires the saved data/config plus saved old image, not merely an image downgrade.
- Existing Ubuntu Docker Desktop integration was enabled and its native daemon
  access verified; settings backup and exact observation are in
  `.tmp/atg09-docker-integration.json`. Windows and Linux runner tooling is being
  prepared in `D:/Orket-Gitea-Runners/windows` and `/home/jon/orket-gitea-runner`.
  Preparation/native tool checks do not establish hosted execution. Historical
  runner absence follows the archived March 12 temporary-runner teardown; server
  upgrade alone does not supply runners. Existing runs 451/452 were still queued
  immediately after upgrade; retain their evidence before scoped job admission.
- Next exact action: within the one-hour authorization, finish runner admission,
  publish the identified candidate to existing Gitea and execute the unchanged
  required Quality workflow. Its eleven jobs include Ubuntu/Windows Python 3.11/3.12
  determinism cells, Linux gates and intentional Docker acceptance. Link/freeze the
  candidate and helpers in `.tmp/atg09-hosted-run.json` before launch; retain hosted
  job/log/commit/environment identity and native teardown. Stop temporary runners
  before the authorization expires. Provisioning after expiry requires new authorization.
  Close ATG-09 only when every required job passes, then continue ATG-10. Reuse
  unchanged accepted local campaigns; missing or failed hosted jobs remain incomplete.
- Remaining blockers or drift: hosted Gitea Quality is absent; ATG-09/10 and whole
  campaign completion are not claimed. ATG-07's 12,964 passes / 93 skips / 89.213132%
  combined coverage remain bound to unchanged production inputs, with affected
  fixture behavior refreshed by R01. Historical source/harness maps contain one
  unrelated PDF path-label encoding discrepancy; the retained correct build snapshot
  and content hash match. Preserve those receipts. The earlier API timing outlier
  remains unexplained; its unchanged assertion passed the accepted final source run.
  Deferred findings remain outside the fixed queue, and current-authority structural
  checks do not establish general current-runtime proof.

## Reusable goal prompt

```text
Complete ATG-v1 in docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md
on codex/architectural-truth-bt0 in C:\Source\Orket-architectural-truth.
Resume the recorded card/batch, then continue through eligible goals without
asking me to replace the task between them. Follow the fixed worksets, start/exit
criteria and contributor checkpoint rules. Preserve the revamp scope and all
existing behavioral contracts. Record unrelated findings without expanding the
queue. Honor the active run's budget and checkpoint unfinished work accurately.
Finish only when all ten goals and their required evidence/publication are
complete; report external blockers honestly and never merge into main.
```

## Historical reference anchors

<a id="c-one-enforceable-dependency-model"></a>
The original C policy record is retained in the
[historical plan](../archive/architectural-truth/AT10012026-GOAL-QUEUE/REMEDIATION_PLAN_HISTORY.md#c-one-enforceable-dependency-model).

<a id="d1-coreeffect-separation-and-current-proof-2026-09-14"></a>
The original D1 record is retained in the
[historical plan](../archive/architectural-truth/AT10012026-GOAL-QUEUE/REMEDIATION_PLAN_HISTORY.md#d1-coreeffect-separation-and-current-proof-2026-09-14).
