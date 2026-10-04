# Post-release reliability: execution handoff

Last updated: 2026-10-04 (America/Denver)
Status: Archived; PRR-v1 publication verified and complete
Queue: PRR-v1
Owner: Orket Core
Workspace: `C:/Source/Orket`
Branch: `main`
Progress: PRR-01 through PRR-03 complete (3/3); PRR-S1 not admitted
Next action: None. Required closeout and publication are verified; do not reopen deferred work.

## Final reconciliation

On October 4, live remote readback and fresh asset downloads confirmed matched
annotated `v0.7.2` and `sdk-v0.7.2` at
`9cb8a89056c46f0c3633e0c20aaac60d80113236`. The public `publication.json`, both
checksum manifests and all distribution bytes match the accepted witnesses.
The original publication and closeout receipts report success and 3/3; no later
main commit existed at reconciliation preflight. Task-owned process cleanup,
the unchanged operator override, selected llama.cpp server and other worktrees
were checked. [Final handoff and exact evidence](../../../../releases/0.7.3/PROOF_REPORT.md)
record the documentation-only successor checkpoint; the tested install target
remains matched core/SDK 0.7.2.

The cards, starting checkpoints and prepublication instructions below retain
their historical scope. They do not reactivate the completed queue. The October 6,
2026 00:00 America/Denver cutoff and final six-hour reserve are retained; required
work finished before the reserve. PRR-S1 remains not admitted, and whole-umbrella
retirement remains outside scope.

## Purpose and authority

Use the remaining Pro/Codex access to make the installed Windows product more
reliable before October 6. Deliver one real-model user journey, repair the recorded
grounding defect, and publish verified changes with an accurate operator handoff.
Marshaller process ownership is a conditional stretch item.

This file is the single canonical plan and resume record for PRR-v1, indexed by
`docs/ROADMAP.md`. It implements the user's request to write the recommended sprint
as a handoff; creating it does not start execution. Contributor workflow remains
in `docs/CONTRIBUTOR.md`. Existing contracts and `CURRENT_AUTHORITY.md` remain
authoritative. Proposed acceptance checks below do not silently change a runtime
contract; record any required contract delta with its implementation.

The completed ATG-v1 queue and release cleanup are retained in
[the umbrella record](../../../architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md).
Their old schedules and next-action instructions do not activate work in this
queue. This handoff does not reopen the marshaller requirements lane or retire
the architectural-truth umbrella.

## Starting checkpoint and proof limits

Expected baseline, to be checked against actual state before execution:

- Core and SDK: `0.7.1`; core pins the standalone SDK exactly.
- Main commit: `2ccbd9aa26a71ba0347096800b8acbd8f4804070`.
- Published tags: `v0.7.1` and `sdk-v0.7.1`, on that same commit.
- Release evidence: `docs/releases/0.7.1/PROOF_REPORT.md`.
- Prior cleanup proof: 372 selected tests plus three additional installed CLI
  cases on Python 3.12; installed native fixture, CLI, HTTP health and deterministic
  workflow observations on Windows Python 3.11/3.12.
- The installed CLI reaches its driver but emits a structural-reconciliation
  warning. Its path remains degraded. HTTP health is not inference or graceful
  shutdown proof; the deterministic workflow performs no model inference.
- Older actual llama.cpp library-flow evidence belongs to its recorded source
  and environment. It does not establish a fresh installed CLI/API user journey.
- General current-authority runtime proof, broader plugin purity, and the retained
  coverage capture/discovery limits remain outside this queue's completion claim.

Preserve later user changes and inspect receipts/process state before relaunching
work. The planning change may be uncommitted when this goal starts; inspect and
retain its three documentation files rather than resetting to the baseline.

The operator's `model/core/rocks/run_the_business.json` is intentionally marked
skip-worktree (`S`). Its expected SHA-256 is
`14724f69f6712ba8c49370855646e55f5f8cf0c06c3e06e07d24dd259b8252ab`.
Preserve its bytes and flag; exclude the override from commits and packages.
Use canonical Git content in an isolated packaging snapshot. Retain other
worktrees and published 0.7.0/0.7.1 tags and assets unchanged.

## Time and usage budget

The user identifies October 6 as the end of the available plan window. The exact
account cutoff and remaining allowance have not been verified. For this queue,
use the conservative working cutoff **2026-10-06 00:00 America/Denver**
(`2026-10-06T06:00:00Z`) unless the user supplies another cutoff. An earlier known
account limit takes precedence. This is a scheduling assumption, not a claim about
subscription expiry.

| Window | Allocation |
|---|---|
| October 4 | Validate inputs; establish the installed real-model journey and diagnose demonstrated failures. |
| October 5, before 18:00 Denver | Complete journey repairs and the grounding fix; consider PRR-S1 only after required behavior is accepted. |
| Final six hours before cutoff | Freeze the candidate, finish affected verification, settle owned processes, publish accepted work, and record the handoff. |

Advance immediately when a goal finishes. Do not spend time merely to exhaust an
allowance. Start no batch whose implementation, proof and cleanup cannot fit before
the verification reserve. If started late, reduce optional work, not acceptance
criteria. At the cutoff, pause with an exact unfinished-work checkpoint; time
expiry is not completion. If all required work is complete earlier, stop.

Plan access is not an API spending budget. Check visible usage/reset information
when available; do not assume a token balance or guaranteed continuous capacity.
Do not purchase credits, switch to API billing, provision infrastructure, or change
the selected llama.cpp provider. Official usage reference, checked October 4:
[OpenAI pricing and usage guidance](https://learn.chatgpt.com/docs/pricing).

## Fixed queue

| ID | Work | Dependency | Status |
|---|---|---|---|
| PRR-01 | Installed Windows real-model user journey | Baseline and ownership preflight | accepted: both installed Windows versions |
| PRR-02 | ResponseParser whitespace/grounding repair | Baseline; may proceed if PRR-01 is blocked | accepted: regressions and live stream/parser proof |
| PRR-03 | Verification, publication and operator handoff | PRR-01 and PRR-02 accepted; any admitted stretch work settled | complete: matched 0.7.2 publication verified |
| PRR-S1 | Marshaller subprocess ownership | Optional admission described below | not admitted |

Required completion is 3/3. PRR-S1 is reported separately and never changes that
denominator. A blocked required goal keeps the overall objective unfinished.
PRR-03 preparation and safe publication of independently verified fixes may
proceed while another goal is blocked; that does not close the queue.

### PRR-01: Installed Windows real-model user journey

**Start:** Follow contributor startup, inspect actual main/dirty state, publication
receipts and owned processes, then bind the candidate and usable Python 3.11/3.12
environments. Discover current supported invocation commands from the contributor
guide, authority snapshot and owning runtime specs; record exact commands before
execution. Confirm the operator-selected llama.cpp endpoint/model without exposing
credentials or taking ownership of its server.

**Work:** In a fresh workspace outside the source checkout, install exact paired
wheels and prove imports resolve to those installed packages. Exercise one
existing public user path through real llama.cpp inference, completion and durable
result inspection, followed by a separate in-flight cancellation and clean exit.
Use the existing CLI or API path that admits the workload; do not invent a new
entrypoint, protocol or provider. State exactly which public surface is proven.
Diagnose the existing startup warning and fix demonstrated defects in this path
in bounded batches. Do not suppress a warning to claim primary-path success.

Primary owners to inspect include `orket/interfaces/`, `orket/workloads/model_stream_v1.py`,
`orket/streaming/model_provider.py`, and their current lifetime contracts. Follow
only the callers needed for the selected path. Use existing inspection/replay
commands where supported; do not add resume/replay behavior to expand this goal.

**Exit:** Both supported Windows Python versions have fresh installed-path proof
for the selected journey, exact model/provider and artifact identities, observable
durable outcomes, and settled client/child resources. The warning's cause and
disposition are recorded truthfully; any retained degraded behavior is explained,
not represented as primary success. A provider/environment blocker is recorded
and leaves this goal open. Health checks, imports and simulated inference do not
satisfy its live gate. Produce a reproducible operator walkthrough.

### PRR-02: ResponseParser whitespace/grounding repair

**Start:** Reproduce the retained counterexample: prose `Maybe this...` loses its
word boundary during residue normalization and escapes strict-grounding detection.
Inspect `orket/application/workflows/turn_response_parser.py`,
`orket/application/workflows/turn_contract_rules.py`, the canonical residue helper,
and the existing turn-contract/parser tests. Confirm the actual owning function
before editing; the earlier finding is evidence to reproduce, not a new test result.

**Work:** Make the smallest change preserving prose word boundaries through
extraction and grounding evaluation. Cover spaces, tabs/newlines, punctuation,
mixed prose/tool JSON, and negative controls for text intentionally excluded by
the existing contract. Preserve parsing, tool admission and error semantics.
Do not broaden the grounding policy or introduce a second parser.

**Exit:** A pre-fix failing contract/integration case and passing repaired cases
exercise the real parser-to-validator path. Relevant turn execution tests and a
real runtime flow pass; a mocked model response is not live-provider proof.
Refresh the installed journey if its relevant code changed. Update the owning
contract and delta if the repair changes an externally observable obligation.

### PRR-S1: Conditional marshaller subprocess repair

**Admission:** PRR-01/02 behavior is accepted, required publication work is reserved,
and a bounded diagnosis, repair and native proof fit before the final six-hour
reserve. Record the admission decision and frozen workset before editing. Otherwise
record `not admitted: time reserved for required goals` and proceed to PRR-03.

The recorded structural concern is `orket/marshaller/process.py::run_process`:
subprocess creation/communication, caller cancellation, descendant cleanup and
ambient environment capture lack established ownership proof. Reproduce the
actual failure first. Limit edits to that owner and directly required callers;
reuse existing process ownership infrastructure. Keep the held marshaller product
requirements, arbitrary plugin execution and new platform support out of scope.

**Exit if admitted:** Real native children/descendants prove completion, timeout,
cancellation, settlement and environment ownership on Windows, with no orphaned
owned processes or false success. Preserve/document existing outcome precedence
and compatibility. If it cannot finish safely, retain an explicit unfinished
checkpoint and keep incomplete changes out of the accepted release; do not erase
user changes or label the attempted repair complete.

### PRR-03: Verify, publish and hand off

Freeze the final candidate and run checks appropriate to changed paths under the
canonical contributor commands: targeted behavioral tests, Ruff, Mypy, dependency
direction, strict taxonomy, critical no-op, docs hygiene, current authority, install
convergence and release metadata as applicable. Reuse unchanged accepted evidence
only with matching relevant inputs. Run the full canonical suite when required by
the affected gate or breadth of changes; retain the existing 89% coverage floor,
branch measurement, assertions, deadlines and declared skips. Do not rerun an
unchanged full campaign merely to consume plan access.

Follow core and SDK release policies, including patch version/changelog advancement,
matching annotated core tags and atomic main/tag pushes for each committed increment.
Choose versions from actual main at execution time; do not reserve 0.7.2 blindly.
Preserve the user's matched-pair release preference for the final published core
and SDK artifacts, with exact dependency metadata and fresh pair validation.
SDK versioning remains independently governed by `docs/requirements/sdk/VERSIONING.md`;
record any packaging-only SDK increment truthfully. Do not claim untested pairings.

Build from canonical frozen sources, verify package contents and fresh installs,
and publish the accepted patch assets to the existing GitHub release destination.
Verify remote commit/tag identities and downloaded asset hashes. Retain stable
publication receipts so interrupted publication can resume without replacing
published bytes. No PyPI upload or new distribution channel is included.

Update the existing quickstart/owning operator documentation with tested commands,
expected results and limitations. Update relevant contracts and authority records
with implementation changes. Archive this completed slice and its evidence under
the contributor closeout rules, remove its execution entry from the roadmap, and
leave the architectural-truth umbrella active. Record remaining findings without
automatically turning them into executable goals.

**Exit:** PRR-01/02 accepted, stretch disposition settled, applicable checks pass,
accepted release publication verified, no owned process left unaccounted for,
and exact files/evidence/remaining limitations handed off. A partial release is
reported as partial success and does not satisfy missing required goals.

## Execution and evidence rules

- Continue through eligible goals without asking for a replacement prompt. When
  blocked, request the exact missing input and continue independent eligible work.
- Use the current session model with effort appropriate to the work. If the invoking
  prompt explicitly authorizes subagents, use bounded independent diagnosis/review
  assignments; the primary owns edits, source freezes, integration and publication.
- Use `ORKET_DISABLE_SANDBOX=1` for these proof runs. Keep provider selection fixed.
  Do not start Linux/WSL, hosted runner, Docker, Bedrock, remote Gitea or infrastructure
  campaigns. Do not stop or replace the operator-owned model server.
- Before long commands, record argv, environment posture, candidate hashes,
  process identity/start time, bounded deadline, logs and result locations in stable
  ignored receipts under `.tmp/post-release-reliability/`. Observe an existing run
  before launching a replacement. Keep tracked inputs frozen while source-bound
  verification runs; checkpoint afterward in this file.
- Keep scoped proof/closeout under the repository's existing artifact conventions.
  Rerunnable JSON producers use the diff-ledger helpers required by `AGENTS.md`.
  Preserve failed attempts and exact evidence bytes; never silently exclude a
  malformed capture or reinterpret absent proof as success.
- Label new/modified tests by layer. Record proof as live, structural or absent,
  path as primary/fallback/degraded/blocked, and result as success/failure/partial
  success/environment blocker. Keep health, fixture, controlled-HTTP and actual
  model evidence distinct.

## Historical resume record (before publication)

This checkpoint is preserved as recorded. The final reconciliation above
supersedes its 2/3 status and next actions; the evidence and failed attempts remain.

- Current goal: PRR-03; required progress 2/3, publication not yet performed.
- Main baseline: `2ccbd9aa26a71ba0347096800b8acbd8f4804070`; candidate matched core/SDK 0.7.2.
- Operator override bytes and skip-worktree flag preserved; operator-owned llama.cpp
  PID 33276 was observed initially at `http://127.0.0.1:8080/v1`, exact model
  `orcarouter_qwen3.8-27b-uncensored-q4_k_l`. Other worktrees/releases preserved.
- PRR-01 accepted: fresh default wheel installs outside checkout, Python 3.11.14
  and 3.12.2, actual public HTTP/WebSocket completion, separate in-flight cancel,
  session inspection, digest-verified durable lifecycle commits, graceful runtime
  close and native command cleanup. Receipt `installed-r03/state.json` retains
  the successful journeys alongside independently failed card/startup probes.
- Startup disposition: missing project `model/` intentionally degrades. Correct
  epic/team fixtures prove real board adoption and warning-free installed CLI;
  `live-remainder-r07/state.json`. Initial fixture lacked required metadata and
  its assertion expected the wrong shape; preserved as failed probe evidence.
- PRR-02 accepted: pre-fix parser/validator and erroneous dispatch counterexamples
  (11 failed / 45 passed), then 186 affected passes. Actual public stream output
  passes unchanged into installed parser/validator on both versions and triggers
  the strict rule; parser artifacts and token bytes retained in R07. No tool is
  dispatched by that additional parser probe. Negative exclusions have contract/
  integration controls, not an asserted live model formatting guarantee.
- Initial separate card-provider flow was blocked by `E_LLAMA_CPP_TEMPLATE_IDENTITY`:
  operator server uses embedded GGUF template, while the declared card profile
  requires its packaged text template. No guard, model or server was changed.
  This does not block the accepted native streaming path and is not card-flow proof.
- Demonstrated runtime fixes: missing default WebSocket dependency; disconnected
  interaction socket retained request during graceful shutdown; grounding residue
  lost word boundaries. Native socket counterexamples failed twice, then 46
  affected controls passed. Independent read-only review found no blocking defect.
- Durable scope: completion intent references `model_stream_v1`; interrupted
  lifecycle intent references turn ID. Durable commits do not persist generated
  transcripts. R02 probe incorrectly disallowed any cancel finalize intent;
  corrected against existing authority, retaining exact failed capture.
- Other failed probes remain: R04 constructor misuse, R05 fail-closed provider
  error, R06 erroneous single-call expectation when actual output repeated JSON.
  R07 validates the unmodified output and its actual calls; no failed result is
  counted as passing. All native command cleanup was confirmed.
- PRR-S1: **not admitted: time reserved for required goals**. No marshaller edits.
- Stable local root: `.tmp/post-release-reliability/`; candidate artifact hashes
  and canonical-source snapshot: `candidate-r02/state.json`. Actual external
  projects: `C:/Users/jonmc/AppData/Local/Temp/orket-prr-v1/`.
- Dirty workset: parser, interaction route, WebSocket packaging, matched versions,
  directly affected tests/Quality selection, contracts/current authority, operator
  documentation and preserved planning files. No unrelated implementation edits.
- Next receipt: `.tmp/post-release-reliability/verification/state.json`; scoped
  source/installed SDK controls and canonical structural gates. Freeze tracked
  inputs throughout that run. Retain release evidence under
  `benchmarks/results/releases/0.7.2/` and narrative under `docs/releases/0.7.2/`.
- No queue-owned process is running at this checkpoint. Exact account allowance is
  unavailable; conservative cutoff and six-hour reserve remain authoritative.

Update this record at cohesive batch boundaries and before interruption. Required
completion still needs verified publication, exact remote identities, asset bytes,
cleanup, final operator handoff and slice archive. No current claim is a fresh
full-coverage, hosted-CI, other-platform or remote-inference-stop claim.

## Historical source closeout and publication boundary

This prepared source checkpoint predates publication. Its conditions were later
satisfied by the verified witnesses linked in the final reconciliation above.

Final canonical wheel receipt: `.tmp/post-release-reliability/final-packages-r02/state.json`
(success on both supported interpreters). Fresh source controls: 569 passes plus
three additional installed SDK cases; 56 affected retests after lint corrections.
Ruff, Mypy, dependency, taxonomy and no-op checks pass at their recorded inputs.
The initial verification receipt retains its Ruff failure; its corrected successor
is `verification-corrected/state.json`. The initial canonical export's Windows
path-length failure remains in `final-packages/state.json`; command-local long-path
Git export succeeded without changing global configuration.

Evidence is sealed under `benchmarks/results/releases/0.7.2/`; narrative and tested
operator commands are under `docs/releases/0.7.2/`. Only this PRR slice is archived.
The architectural-truth umbrella, prior publication evidence, operator override
and other worktrees remain. No required implementation work remains; publication
is complete only when the attached public `publication.json` and local witness
verify matched tags, atomic main push, exact downloaded hashes and final cleanup.
Do not infer success from this prepared source closeout alone. Final checks have
stable receipt `final-checks-r03/state.json`; interrupted publication resumes from
`publication/state.json` after inspecting real refs/assets and owned processes.

Final environment reconciliation: before publication the original PID was absent.
Read-only inspection observed PID 45556, started 2026-10-04T19:24:07Z, serving the
same selected provider/model with the declared text template. No task command
restarted or stopped either server; the cause of replacement is not asserted.
An unrelated `Orket-paperclips-foundation` worktree also appeared and was preserved.
`environment-refresh/state.json` retains both successful refreshed public journeys
and the failed LF-only file assertion. `profiled-refresh-r02/state.json` then proves
actual installed TurnExecutor inference, real ToolBox write with native CRLF bytes,
actual speculative-response grounding refusal and provider-client closure on both
Windows versions. Original template refusals remain failures at their recorded
environment. The current template is byte-matched, without bypass or provider switch.
Required behavior remains accepted; final publication witness is still required.
