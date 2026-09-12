# Orket architectural review: behavioral truth

Date: 2026-09-10 (America/Denver)
Status: Review reference; not an approved implementation plan or release sign-off
Source base: `5e0dcd642dabc3a8e0c141473829e4c7228e5f8a`, plus the current dirty working tree
Owner for remediation decisions: Orket Core

## Ship-risk debt

These findings concern observable authority, effects, and evidence. “Behavioral lie” means the system's output or implied guarantee exceeds what it actually enforced; it does not imply intent by its authors. Severity describes consequences within the affected path, not every Orket runtime.

### SR-01 — An old approval authorizes a different, still-unapproved write

**Critical. Reproduced with real SQLite and files, through the composed outward application flow; model responses were deterministic fixtures.**

In a two-turn run using `write_file` twice:

1. Approve the first proposal and let its write complete.
2. The runtime advances and requests approval for the second file.
3. Retry the first approval's continuation.
4. The second file is written and the run becomes `completed`, while the second proposal remains `pending`.

Observed:

```text
before_retry=approval_required
after_retry=completed
second_approval=pending
second_file_written=true
```

[OutwardRunExecutionService.continue_after_approval](../../../orket/application/services/outward_run_execution_service.py#L112) checks that the supplied proposal is approved and its tool name matches the run's current model tool call. It does not bind execution to that proposal's turn, exact arguments, or consumption state. [model_tool_call](../../../orket/application/services/outward_run_execution_plan.py#L55) selects the latest model call. The [approval router](../../../orket/interfaces/routers/approvals.py#L116) invokes continuation on repeated approval requests too.

An approval is effectively reusable permission for a tool name. It must instead authorize one immutable effect identity. The fact that the operator approved one write says nothing about a subsequent write to another target.

The outward proof kernel explicitly limits its admitted formal scope to selected single-turn paths. This finding does not claim to refute that scoped proof; it concerns the executable, tested multi-turn application surface, which accepts this sequence without an equivalent scope restriction.

**Required correction:** bind approval to run, attempt/turn, proposal identity, argument digest, target scope, and policy version; require the current pending proposal to match; atomically consume or claim that exact authorization before execution. An old approval retry must return its original receipt without advancing another turn.

**Acceptance proof:** execute a real two-write sequence, retry approval 1 while approval 2 is pending, and prove the second file remains absent. Repeat after process restart. The existing two-step test uses different tools (`read_file`, then `write_file`), which misses this same-tool identity defect.

### SR-02 — One approval can execute twice while the ledger records one effect

**Critical. Reproduced with real concurrent application calls, SQLite, and two actual Python subprocesses. No model was invoked.**

Two concurrent calls to `continue_after_approval()` for the same approved `run_command` both entered the executor. The command appended one line to a temporary file.

```text
file contents: effect, effect
continuation results: IntegrityError, completed
tool_invoked events: 1
```

The order of the two return values varies. The duplicate effect does not.

[Continuation](../../../orket/application/services/outward_run_execution_service.py#L112) performs a read/check/execute sequence without an execution claim. [_append_once](../../../orket/application/services/outward_run_execution_service.py#L437) deduplicates events after execution, using a separate read and insert. A duplicate event error cannot roll back a command that already ran.

This is worse than a duplicate API response: execution history understates real effects. Sequential idempotency tests and unique event IDs provide false confidence about effect idempotency.

**Required correction:** durably claim the approved effect before dispatch, record dispatch intent, and distinguish confirmed completion from uncertain execution. Use an external idempotency key where the connector supports one; otherwise reconcile before retry. Do not promise generic exactly-once external effects merely because SQLite can serialize local decisions.

**Acceptance proof:** concurrent authenticated approval retries and crash injection before/after dispatch must produce at most one effect or an explicit unresolved boundary. Verify the filesystem/remote effect independently of event counts.

### SR-03 — Conflicting operator decisions both succeed

**High. Reproduced with concurrent real SQLite application calls.**

Concurrent approval and denial of one pending proposal returned `approved` and `denied`. Both `proposal_approved` and `proposal_denied` were recorded. The stored decision was whichever write won last; both winners were observed on repeated probes.

[_decide](../../../orket/application/services/outward_approval_service.py#L161) reads `pending`, constructs a replacement, then calls [OutwardApprovalStore.save](../../../orket/adapters/storage/outward_approval_store.py#L61), which uses `INSERT OR REPLACE`. There is no conditional transition on the original status. Proposal state, run state, and decision event are also committed separately.

This defeats the meaning of a durable operator decision. An acknowledgement of denial cannot be trusted as exclusive closure.

**Required correction:** one database transaction must conditionally transition pending status and publish the decision/run projection or durable outbox entry. The loser must receive the already-authoritative decision or an explicit conflict. Contradictory idempotency reuse must not silently become a successful response.

**Acceptance proof:** approve/deny, approve/expire, and two-operator races using separate connections and processes; one authoritative decision and a consistent run/event projection after restart.

The governed-agent effect path already uses a pending-status compare-and-set in [resolve_write](../../../orket/application/services/governed_agent_effect_service.py#L153). The architectural problem is that a stronger approval substrate exists beside this weaker outward one, under similar product vocabulary.

### SR-04 — Approval expiry is enforced by looking, not by approving

**High. Reproduced through real approval, continuation, and file execution.**

A proposal expired at `12:00:01`. Direct approval at `13:00:00` succeeded; continuation wrote the file and marked the run `completed`.

[list_pending and get](../../../orket/application/services/outward_approval_service.py#L88) call `expire_due()`. [approve and _decide](../../../orket/application/services/outward_approval_service.py#L103) do not validate expiry. Continuation's later `get()` cannot expire it because it is already approved. Whether someone reads the queue changes whether an expired action is allowed.

The [existing execution test](../../../tests/application/test_outward_run_execution_service.py#L138) itself advances the clock beyond its requested 30-second approval timeout before approving successfully. This behavior is not merely untested; a happy-path test accommodates it.

**Required correction:** atomically validate pending status and expiry at the decision boundary using the authoritative clock. Queue reads must not be necessary for safety.

**Acceptance proof:** direct approval after expiry, without any prior list/get, must fail closed and perform no effect. Include the exact boundary and concurrent expiry/approval cases.

### SR-05 — Ledger verification repairs the evidence it is supposed to check

**High. Reproduced against a previously exported real SQLite ledger.**

The probe exported a ledger, changed one stored event payload without updating its stored hashes, then called `verify_run()`:

```text
payload={"tampered": true}
verifier_changed_stored_hash=true
verify_result=valid
```

[verify_run](../../../orket/application/services/outward_ledger_service.py#L100) calls `export()`. Export calls [_ensure_hashes](../../../orket/application/services/outward_ledger_service.py#L144), which recomputes hashes from current database contents and overwrites mismatches through [update_hashes](../../../orket/adapters/storage/outward_run_event_store.py#L89). Verification then validates this newly sealed representation.

This proves that the exported bytes are internally consistent. It does **not** prove that the retained event history remained intact. Calling the online verification endpoint can erase the evidence of a stored hash mismatch.

The [tampering test](../../../tests/application/test_outward_ledger_service.py#L73) modifies an already-exported copy, where offline verification correctly fails. That test does not exercise corruption before the next export. The [export contract](../../../docs/specs/LEDGER_EXPORT_V1.md) defines export hashing, so the narrower offline claim is legitimate; treating this endpoint as retained-history integrity is not.

**Required correction:** distinguish first-time sealing from verification. Verification must be read-only and reject a previously sealed mismatch. Establish append-time integrity and a stable ordering/anchor strategy; external retention or signing is needed for stronger authenticity claims. Export reconstruction must not quietly replace historical commitments.

**Acceptance proof:** mutate/delete/reorder stored evidence after sealing and verify rejection without any database change. Preserve a prior external anchor and demonstrate what it can and cannot detect.

### SR-06 — A truncated ledger is exported as the full canonical ledger

**High. Reproduced with 5,001 correctly hashed SQLite events.**

```text
stored_events=5001
exported_events=5000
export_scope=all
verify_result=valid
```

[_ensure_hashes](../../../orket/application/services/outward_ledger_service.py#L144) requests 5,000 events. [list_for_run](../../../orket/adapters/storage/outward_run_event_store.py#L101) caps results at 5,000. Export derives both canonical count and final hash from that limited list, and [verify_ledger_export](../../../orket/core/domain/outward_ledger.py#L72) can only check the supplied count.

This is an actual completeness lie: omitted tail events are not declared as an omission. The exported view and its self-reported total agree because both were truncated together. The single-turn proof scope limits likely event volume today; it does not make a full-export API truthful at its boundary.

**Required correction:** read all events from a consistent snapshot with pagination, or reject/label bounded exports as partial. Compare against an independent database count and retained final anchor.

**Acceptance proof:** 4,999/5,000/5,001-event cases and a concurrent append during export. An `all` export must include the tail or explicitly fail completeness.

### SR-07 — No verification can become automatic `done` intent

**High. Reproduced at the real verifier-to-status-synthesis boundary; final card persistence was not exercised.**

An empty workspace with no executable verification plan produced:

```text
ok=true
overall_evidence_class=not_evaluated
checked_files=[]
command_results=[]
```

Passing that actual `ok` value into the integrity-guard context caused [synthesize_required_status_tool_call](../../../orket/application/workflows/turn_executor_runtime.py#L80) to append `update_issue_status(status="done")` without a model-supplied status tool call.

[RuntimeVerifier.verify](../../../orket/application/services/runtime_verifier.py#L57) defines `ok` as absence of errors. It correctly preserves the evidence class, but [prompt preparation](../../../orket/application/services/orchestrator_prompt_preparation_service.py#L89) reduces the result to `runtime_verifier_ok`; synthesis consumes that boolean. The real [model flow](../../../orket/application/workflows/turn_executor_model_flow.py#L320) calls the synthesis function.

The evidence writer is more truthful than its consumer. Adding `not_evaluated` to an artifact does not protect an execution gate that ignores it. Syntax-only success has the same architectural weakness when a task requires behavioral proof.

**Required correction:** gate completion on a typed evidence requirement and a satisfied acceptance contract, not a generic `ok`. `not_evaluated`, syntax validation, command execution, and objective satisfaction need distinct authority. Independently enforced artifact/tool preconditions may still block a particular run; this probe does not claim those were bypassed.

**Acceptance proof:** a composed card run requiring behavioral verification must stay incomplete/blocked when checks are absent or only compile syntax. Test a present but behaviorally incorrect implementation too.

### SR-08 — Cancelling verification leaves its subprocess free to mutate files

**High. Reproduced through public RuntimeVerifier.verify with a real child process.**

The verifier launched a command that signalled startup, waited one second, then wrote a file. After startup, the caller cancelled and awaited the verifier task. The child subsequently wrote the file:

```text
task_cancelled=true
child_wrote_after_cancel=true
```

[_run_command](../../../orket/application/services/runtime_verifier.py#L305) kills its child on `TimeoutError` but has no cancellation cleanup. `CancelledError` escapes without terminating and awaiting the process. A completed cancellation of the Python task therefore does not mean verification work has stopped.

**Required correction:** make the application own the child lifetime in cancellation and failure paths. Terminate, escalate if needed, and await confirmed exit. Define process-tree ownership for commands that create descendants. Preserve uncertainty when shutdown cannot be confirmed.

**Acceptance proof:** cancel the real public verifier mid-command and prove no post-cancel effect and no surviving child/descendant. The review probe used a bounded child that exited naturally; no long-running process was left behind.

### SR-09 — Card runtime outcomes are discarded before CLI exit status

**High. Structural call-chain finding; no provider-backed failed epic was run for this finding.**

[EpicRunFinalizer](../../../orket/runtime/execution/epic_run_finalize.py#L106) can record `terminal_failure` or `incomplete` without raising. Its public finalization returns a legacy transcript rather than the resolved outcome. [EpicRunOrchestrator.run](../../../orket/runtime/execution/epic_run_orchestrator.py#L61) returns that transcript normally. The [CLI card and epic branches](../../../orket/interfaces/cli.py#L526) ignore the persisted outcome and return zero; the epic branch also prints `Orket EOS Run Complete`.

The July repair correctly fixed caught fatal exceptions. It did not establish a typed outcome from workload completion to the process boundary. A successful function return still means “the runner returned,” even when its durable result says otherwise.

**Required correction:** return one typed run result containing lifecycle, result class, evidence sufficiency, run ID, and durable evidence references. Define process exit semantics for incomplete, blocked, failed, and successful executions and project them at the CLI boundary.

**Acceptance proof:** run real installed commands for a blocked/incomplete epic and a successful epic, asserting both persisted state and exit status. Do not substitute a mock that simply returns an invented status object.

## Exploration-safe debt

These boundaries can support continued bounded development when stated honestly. They must not be promoted into broader product guarantees.

### ES-01 — There are several execution architectures, not one uniformly governed runtime

**Structural.** Cards orchestration, the outward run service, the governed-agent loop, generic SDK workloads, and the quickstart have different result types, effect owners, and evidence mechanisms. `success`, `done`, `completed`, `matched`, `valid`, `ok`, and `FinalTruthRecord` are not interchangeable assurances.

The governed-agent path has explicit iteration fencing, pending-status CAS for effects, observation/reconciliation, and a continuation policy. Those mechanisms do not automatically protect the outward path demonstrated above. [The control-plane start-path matrix](../../../docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md) and [README](../../../README.md) already qualify selected lanes; preserve that qualification.

Do not rewrite the whole system merely to reduce package count. Extract shared authorization/claim/effect/evidence behavior only after its contracts are executable. Keep transports thin and each lane's claim ceiling explicit during migration. A common label or facade is not convergence.

### ES-02 — The governed-agent verifier remains a ticket-report fixture verifier

**Structural; explicitly admitted by the durable contract.** [Composition](../../../orket/application/services/governed_agent_execution_composition.py#L130) installs `SecondIterationDeterministicVerifier` for both fixture and live-model selection. [The verifier](../../../orket/application/services/governed_agent_fixture.py#L44) checks the known ticket-report corpus and admits satisfaction from iteration two onward. [GOVERNED_AGENT_LOOP_V1](../../../docs/specs/GOVERNED_AGENT_LOOP_V1.md) explicitly describes that admitted verifier.

This is useful live-model orchestration proof when actually run with a provider. It is not a general-purpose objective verifier, broad autonomous-agent completion proof, or proof of arbitrary extension correctness. The fixture provider is also explicitly labelled as non-live. Those are honest limitations, not defects by themselves.

Before generalizing, acceptance/verifier selection must be workload-owned and digest-bound; unsupported objectives must be rejected explicitly. Preserve independent verification of actual output contents rather than replacing it with a model recommendation.

### ES-03 — Trusted extension execution is not hostile-code containment

**Structural; no hostile-code or container escape testing performed.** The governed-agent contract correctly admits operator-trusted extension code and says Python import guards are not OS containment. Generic SDK work uses a subprocess; legacy loading still has in-process import behavior. [Fixture verification](../../../orket/core/domain/fixture_verifier.py#L29) also distinguishes development subprocess mode from required production container mode unless explicitly overridden.

Continue local trusted development under those limits. Do not market AST import filtering, Python socket monkeypatches, a subprocess, or a workspace path check as a security sandbox for arbitrary code. Expansion to untrusted extensions needs a separately enforced OS boundary and adversarial proof. The review did not establish a new containment exploit.

## Self-deception debt

### SD-01 — The architecture gate still certifies a weaker architecture

**High. Structural checker execution and source inspection.**

The dependency checker passed over **834 Python files**, including these observed edge counts under its own classifications:

| Edge | Count |
|---|---:|
| adapters → application | 9 |
| interfaces → adapters | 14 |
| core → services | 2 |
| core → platform | 13 |

The [policy](../../../model/core/contracts/dependency_direction_policy.json) is a denylist over more layer classifications than the normative architecture. It does not forbid `adapters → application`. Core can reach implementation through `services`/`platform` despite [the architecture's purity rules](../../../docs/ARCHITECTURE.md). [core/policies/tool_gate.py](../../../orket/core/policies/tool_gate.py#L15) imports service validators; [core/domain/reconciler.py](../../../orket/core/domain/reconciler.py) writes files and emits events; core models read wall time. Decision-node strategy also reads environment settings.

This is a confirmed continuation of `AT-EX-001`, `004`, `007`, and `008`, not a newly discovered pristine-layer violation. The register is commendably explicit. The green dependency check still does not prove the stated architecture.

**Correction:** one ratified allowed-edge model, exact governed exceptions, and effect/determinism checks that enforce the actual target. Report green as “passes current transition policy” until that cutover. Move effects out of core without losing real execution proof.

### SD-02 — An empty governed-agent replay reports `matched`

**Medium. Reproduced with a real SQLite RunRecord and zero iteration snapshots.**

```text
status=matched
decisions=[]
```

[GovernedAgentInspectionService.replay](../../../orket/application/services/governed_agent_inspection_service.py#L158) uses `all(...)` over the replay list. For an existing run with no iterations, the empty list yields success-shaped `matched`.

For populated runs, [_replay_snapshot](../../../orket/application/services/governed_agent_inspection_service.py#L253) recomputes the continuation decision from retained decision inputs and compares the decision/digest. That is legitimately narrower than rerunning a model or re-observing effects; the contract calls it continuation replay. The output should identify that scope and should not certify absent evidence.

**Correction:** report `not_evaluated` or `insufficient_evidence` for an empty replay and include compared decision count/scope. Keep decision consistency, source-evidence integrity, effect truth, and full execution replay distinct.

Update 2026-09-11: the empty-replay defect is repaired. Existing runs without
iteration snapshots report `no_decisions`; populated continuation comparison
remains unchanged. Real SQLite proof is in
`tests/integration/test_governed_agent_empty_replay.py`. Broader review findings
remain open under the architectural-truth plan.

### SD-03 — The tests pass the intended stories while missing the authority boundaries

**High. Full test execution plus adversarial local probes.**

`python -m pytest -q` returned **4,576 passed, 73 skipped, 2 warnings, exit 0**, in 433.18 seconds. The nine probes in the companion evidence document all reproduced their targeted defects in the same review session.

Specific blind spots:

| Existing proof | Missing counterexample |
|---|---|
| Sequential approval idempotency | Concurrent execution and contradictory decisions |
| Two-step read then write | Two successive calls to the same tool with an old approval |
| Tampering with an exported JSON copy | Mutating stored evidence before online verification |
| Small full-ledger exports | A full export beyond the storage query cap |
| Verifier reports `not_evaluated` | A downstream completion gate consumes only `ok` |
| Timeout handling | Cancellation while a child process remains active |
| Fatal startup exit tests | Nonexceptional terminal failure propagated to CLI status |

These tests are not worthless. Their scope is smaller than the confidence a large green count invites. The problem is proof selection, not a shortage of assertions.

The taxonomy gate also remains misaligned: **4,272 test definitions scanned, 3,479 missing labels, strict exit 1**. [Its regex](../../../scripts/governance/enforce_test_taxonomy.py#L11) recognizes nearby `unit|contract|integration|live_truth` prose, not the canonical pytest markers or `end_to_end`. This is the checker's missing-label count, not proof that all those tests lack valid pytest classification. The difference from 4,576 passes includes parametrization and collection semantics.

**Correction:** make pytest markers authoritative; distinguish test layer from live/provider posture; require adversarial composed-path proof for each authority claim. A test named integration is not automatically live-provider or complete-system evidence.

### SD-04 — Green pytest is not a green quality envelope, and noisy checks need repair

**Medium. Structural tooling executed.**

| Check | Observed result |
|---|---|
| Ruff over `orket` | 128 errors; exit 1 |
| Ruff over canonical Quality workflow scope `orket tests` | 154 errors; exit 1 |
| No-op critical-path inventory | 15 findings across 495 files |
| Python size inventory | 76 files over 400 lines; 241 functions over 70 lines |
| AST parse errors in size inventory | 0 |

The no-op findings include ellipsis signatures inside `TYPE_CHECKING` blocks in [execution_pipeline_card_dispatch.py](../../../orket/runtime/execution/execution_pipeline_card_dispatch.py#L17), not executable no-op implementations. Do not present all 15 as runtime defects. The [checker](../../../scripts/governance/check_noop_critical_paths.py) understands Protocol methods but does not account for this type-only scope.

Size outliers include the API facade at 1,984 lines, `orchestrator_ops.py` at 1,853, and the bundle CLI at 1,607. Size is a change-risk signal, not proof of a behavioral lie. Some large functions are router factories containing nested handlers; the raw function count overstates single-flow complexity.

**Correction:** fix noisy gates and use enforceable baselines; do not clear them with broad ignores. Decompose along authority and lifetime ownership, backed by parity proof. Keep the critical effect/evidence defects ahead of aesthetic file splitting.

### SD-05 — Connector duration telemetry is fabricated

**Medium. Structural, directly on the executed outward connector path.**

[OutwardConnectorService.invoke_with_result](../../../orket/application/services/outward_connector_service.py#L94) emits `duration_ms: 0` for every invocation, including actual subprocess execution and timeout. This is not an observed duration. The duplicate-effect probe's command explicitly slept for 300 ms, yet this path has no elapsed-time measurement.

**Correction:** measure elapsed time with a monotonic clock and record its provenance, or report timing unavailable. A precise zero is a measurement claim; it must not mean “we did not measure.” Audit summary fields for other constant success-shaped defaults before using telemetry to justify capacity or performance claims.

### SD-06 — Authority prose is too large to act as a reliable current snapshot

**Medium. Structural; previously registered as AT-EX-016.**

[CURRENT_AUTHORITY.md](../../../CURRENT_AUTHORITY.md) calls itself intentionally narrow but contains extensive slice and release history. During this review, its September provider-composition paragraph described generic local-provider selection while an older canonical-command bullet still described exactly one of `--deterministic-fixture` or `--ollama-model`. The new provider integration was already dirty user work, and another verification document appeared during review; this is a worktree snapshot, not a claim about a committed release regression.

The resulting risk is that a reader chooses whichever paragraph supports the desired claim. App ownership, control-plane participation, provider support, and proof scope become easy to conflate across lanes.

**Correction:** keep one bounded, validated current authority manifest and move implementation history to durable release/closeout records, as the existing remediation plan already proposes. For every public surface, name the actual executor, authorization owner, terminal-result authority, proof level, and unsupported cases.

## Architectural assessment

**Orket has useful deterministic and governed components, but its outward approval/evidence path is not a trustworthy foundation for wider autonomous side effects yet.** Expanding that surface before repairing SR-01 through SR-06 would amplify authority errors and make the resulting evidence look cleaner than the execution actually was.

The central problems are concrete:

1. **Authorization is detached from effect identity.** A mutable approval row and tool-name check stand in for a consumed authorization for exact arguments.
2. **Evidence is reconstructed from the present.** Rehashing mutable state and self-reporting a truncated count creates internally consistent proof that can conceal what happened.
3. **Consumers erase distinctions producers recorded.** Evidence classes collapse to booleans; workload outcomes collapse to transcripts; no decisions collapse to `matched`.
4. **“Governed” names multiple guarantees.** Stronger fencing/reconciliation in one lane does not transfer to another by sharing a repository or API family.
5. **Tests overrepresent sequential success.** Race, retry, cancellation, missing-evidence, and storage-boundary cases are where authority claims fail.

Adding more truth-named artifacts will not fix these problems. Each boundary needs an invariant that can fail visibly when independently observed execution contradicts it.

### What improved since the July architectural review

The earlier [review](../future/BRUTAL_CODE_REVIEW_ARCHITECTURAL_TRUTH_2026-07-29.md) must not be treated as an unchanged defect list:

- The API factory now returns distinct apps, contexts, engines, and runtime states; the first app retains its root. The isolated subprocess probe confirmed these identities and absence of a module-default `app` owner. This does not by itself prove every lifecycle/cancellation case.
- Fresh runtime onboarding/help and handled fatal exit semantics passed real subprocess probes. The fatal case exited 1.
- Quickstart help works; EOF returns 2 with `E_QUICKSTART_INPUT_REQUIRED`.
- The governed-run packaged default ran outside the checkout and produced its evidence artifact.
- Runtime verification now records evidence classes, and README explicitly limits the quickstart and determinism claims. SR-07 concerns consumption of that evidence, not absence of all truthful metadata.
- The architectural baseline collector itself reported `collection_ok=true`, **`release_ready=false`**. That is an honest collector status, not another false green.

### Coverage and proof ceilings

This was a repository-wide architectural review with targeted behavioral execution, not a line-by-line proof of every implementation. The structural inventory covered 834 Python files. Findings received deeper call-chain inspection; untouched modules did not receive equal scrutiny.

| Area | Review coverage | What remains unproved here |
|---|---|---|
| Entrypoints, bootstrap, API ownership | Contributor/authority/architecture protocol; CLI/factory source; real baseline subprocesses; full suite | Fresh wheel installation, every startup configuration, all shutdown failures |
| Cards orchestration and completion | Dispatch/finalizer/preflight/status synthesis; real verifier probes | Provider-backed failed/incomplete epic through CLI |
| Outward approvals, execution, storage, ledger | Real SQLite races, real files/subprocesses, two-turn fixture-model flow, corruption and truncation | Authenticated network API reproduction and remote connector effects |
| Governed-agent loop, wake/effects, inspection | Continuation/composition/fencing/effect/replay sources; empty replay against SQLite; full suite | Live llama.cpp/LM Studio/Ollama execution, provider cancellation, crash at every publication boundary |
| Provider/streaming/ODR | Canonical target resolution and new governed-provider composition inspected; broad suite | Live provider identity, streaming timing, ODR campaigns; dirty integration work was not certified |
| Kernel, control plane, review/trust handoff | Contract/final-truth/verification boundaries inspected; full suite includes their tests | Universal state/evidence atomicity, new formal proof, cloud acceptance |
| Extensions and verification containment | SDK dispatch/loading and verifier execution-mode boundaries inspected | Hostile-extension containment, container escape resistance, installed external extension matrix |
| Sandbox, Gitea, AWS and remote integrations | Current authority/scoped admission; non-live suite coverage | Live Docker/AWS/Gitea operations and teardown; no such resources were created |
| Architecture/governance | Dependency policy, taxonomy, lint, no-op/size inventory, docs hygiene | Linux/Python 3.11/3.12 matrix and CI coverage thresholds |

### Recommended remediation order

This is review advice, not a second active roadmap or an accepted implementation plan. The [existing plan](ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md) remains the execution authority.

1. **Close outward authorization holes first:** exact approval binding, atomic decisions with expiry, durable effect claims, retry/recovery semantics. Prove against actual effects before layering more features on this path.
2. **Make evidence verification independent:** read-only mismatch detection, complete exports, stable anchors and explicit proof scope. Retain the counterexamples; do not merely update expected hashes.
3. **Repair completion and cancellation contracts:** typed results across CLI/application boundaries, evidence-strength gates, and supervised child lifetime.
4. **Use those contracts to converge the execution families:** reuse the stronger existing primitives where their semantics fit; do not create another parallel approval framework.
5. **Then finish architecture-gate and authority cleanup:** allowed-edge enforcement, core purity, async reachability, taxonomy, lint, and bounded current authority. The active plan's next dependency-gate slice is useful but is not the most urgent behavioral risk uncovered here.

Each remedial slice should identify the violated claim, reproduce it with independent observation, repair the authoritative transition, and rerun the same counterexample. A new receipt whose contents merely repeat the caller's desired outcome is not proof.

## What changed

Added this review and a companion [evidence and reproduction document](BEHAVIORAL_TRUTH_REVIEW_EVIDENCE_2026-09-10.md) under the existing indexed architectural-truth project. No runtime code, test suite, roadmap priority, exception acceptance, release version, or existing user edits were changed by this review. No commit or push was performed.

## What was verified

- **Live local integration:** nine adverse probes, with actual SQLite/files/subprocesses as applicable. The two-turn probe substitutes only model responses. These are bounded application proofs, not full provider/API acceptance.
- **Live local entrypoints:** seven baseline command observations and an isolated API-factory construction/close probe.
- **Mixed test-suite proof:** 4,576 passed, 73 skipped, 2 warnings, exit 0 on Windows/Python 3.13.11 with pytest 9.0.3 and `ORKET_DISABLE_SANDBOX=1`.
- **Structural:** dependency check passed; strict taxonomy failed; Ruff failed in both recorded scopes; no-op/size inventories collected; documentation project hygiene passed.
- The companion records individual path/result classifications, reproduction source, outputs, and source hashes. Probe collection exit 0 means observations were collected; the reproduced contract outcomes are failures.

## What was not verified

No live provider-backed run, remote effect, cloud operation, live Docker sandbox acceptance, fresh distribution install, production load test, or authenticated HTTP reproduction of these newly found defects was performed. Those proofs are absent, not implicitly covered by pytest. No environment failure prevented the local review; external/live paths were deliberately outside its execution envelope, so availability is unknown rather than asserted blocked.

The CLI outcome finding is structural. The verifier-status finding stops at generated `done` intent. The source base was dirty and provider integration work changed during the session; source hashes for the primary counterexamples are retained in the companion. This is not release acceptance for an immutable build.

## Remaining blockers or drift

SR-01 through SR-09 remain unresolved. The new counterexamples are review findings, not accepted architecture exceptions. Existing dependency/core/input/async, taxonomy, lint, no-op, and authority-maintenance drift remains. The review does not close or reorder the architectural-truth lane or reopen paused cloud/provider lanes.

## Exact files touched

- [BEHAVIORAL_TRUTH_ARCHITECTURE_REVIEW_2026-09-10.md](BEHAVIORAL_TRUTH_ARCHITECTURE_REVIEW_2026-09-10.md)
- [BEHAVIORAL_TRUTH_REVIEW_EVIDENCE_2026-09-10.md](BEHAVIORAL_TRUTH_REVIEW_EVIDENCE_2026-09-10.md)
