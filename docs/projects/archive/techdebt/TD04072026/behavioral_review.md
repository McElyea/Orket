# Orket — Behavioral Review

**Focus:** Does Orket actually behave the way it claims to? Does the runtime deliver on traceability, replayability, approval-gated actions, fail-closed execution, explicit side-effect records, loop healing, and truthful outcome classification?

**Method:** Trace each claimed behavioral property through the visible execution path. Where the path cannot be closed, mark it explicitly.

---

## 1. Claimed Property: Fail-Closed Execution

### What should happen
Any execution path that cannot verify governance should refuse to proceed, not produce a degraded result.

### What actually happens

**Gap 1 — Governance interceptors are fail-open (CRITICAL)**
`TurnLifecycleInterceptors.apply_before_tool()` catches all exceptions from interceptors and continues to the next one. If every interceptor crashes, the method returns `None` (no block). The tool executes as if no governance was applied. The system is fail-open on interceptor crashes, which is the exact opposite of the claimed property.

**Gap 2 — Skill/dialect load failure is fail-open**
When an agent fails to load its `SkillConfig` or `DialectConfig`, it falls back to `self.description` as the system prompt. This means an agent runs without its governance constraints and hallucination guard. The run proceeds, tools get executed, side effects are written. No circuit-breaker fires. The failure is logged but not surface-breaking.

**Gap 3 — Approval gate is missing from the standard execution path**
The `ToolGate.validate()` is the only pre-execution check visible in `Agent.run()`. The ToolGate can block execution, but it cannot *pause* execution and wait for human approval. There is no human-in-the-loop approval surface in the agent turn path. The comment in `agent.py` calls it "Pre-execution validation" — validation only, not approval. True approval-gated actions would require the ToolGate to be able to emit a "pending" state, suspend the agent, and resume after an external approval event. This mechanism does not exist in the current architecture.

**Verdict:** Fail-closed is partially implemented. Execution cannot proceed if `ToolGate` blocks, but governance rules that crash are silently bypassed, and skill/dialect loading degradation is not circuit-broken. The system is not reliably fail-closed.

---

## 2. Claimed Property: Approval-Gated Actions

### What should happen
High-risk or explicitly governed actions should require human or policy approval before side effects are executed.

### What actually happens

The architecture has the *vocabulary* of approval gating (`OperatorCommandClass`, `OperatorActionRecord`, `CheckpointAcceptanceRecord`, `validate_checkpoint_acceptance`) in `ControlPlaneAuthorityService`. These are rich domain objects with well-defined lifecycle.

However, the **execution path** — `Agent.run()` calling `ToolGate.validate()` calling `tool_fn()` — has no callback into these objects before executing a side effect. The `ControlPlane` records appear to be written *after* execution as attestation, not *before* execution as a gate.

**What this means:** The approval record infrastructure exists, but it is operating as a post-facto audit trail, not a pre-execution approval gate. You can prove what happened after the fact, but you cannot block it before the fact using the current seam.

**The companion flow may be different.** `CompanionConfig` and `ConfigPrecedenceResolver` suggest a separate execution surface where mode/memory/voice are configurable. Whether this surface has synchronous approval gating is not determinable from the visible code.

**Verdict:** Approval-gated actions exist as a data model but are not wired as a pre-execution gate in the standard agent path. This is a future contract expansion, not a current capability.

---

## 3. Claimed Property: Traceability

### What should happen
Every executed action, its inputs, outputs, and outcome should be verifiable after the fact.

### What actually happens

**Strong:** `EffectJournalEntryRecord` (append-only, chained, with `previous_entry` reference) is a solid foundation for side-effect traceability. `FinalTruthRecord` provides outcome classification. `ControlPlanePublicationService.publish_run_snapshots()` writes policy and configuration snapshots at run start.

**Weak:** `Session.transcript` is `list[dict[str, Any]]` with no schema enforcement. This is the primary transcript of what happened during a session. It is unvalidated, unversioned, and not cross-referenced to the effect journal. An agent that executes 5 tool calls writes them to `turn.tool_calls`, but the relationship between `turn.tool_calls` and `EffectJournalEntryRecord`s is not visible in the code.

**Missing seam:** `OpenClawJsonlSubprocessAdapter.run_requests()` returns responses from a subprocess, but there is no visible code that writes those responses to the effect journal. Tool executions via the OpenClaw adapter may be completely absent from the effect journal.

**The ODR gap:** The `odr_canonical_json_bytes()` and `odr_raw_signature()` functions are used in benchmark reproducibility checks, not in the production traceability path. A production run's transcript does not carry an ODR signature.

**Verdict:** Traceability is strong for the control-plane record layer and weak for the agent-turn transcript layer. The two layers are not durably linked. Tool calls via subprocess adapters may not appear in the effect journal at all.

---

## 4. Claimed Property: Replayability

### What should happen
Any run should be reproducible from its recorded inputs, producing the same outputs.

### What actually happens

The ODR (`kernel/v1/`) achieves determinism for the *Reactor* component specifically. The benchmark suite verifies that permuting graph node ordering doesn't change the canonical hash. This is real and well-tested.

For the broader agent execution path, replayability requires:
1. The same model at the same version
2. The same tool implementations
3. The same transcript inputs
4. Deterministic tool results (or mocked tool results on replay)

Point (3) fails because `Session.transcript` has no schema. Point (4) fails because there is no "replay mode" where tool calls are answered from a recorded journal rather than executed live. The retry policy in `IssueConfig.max_retries` would cause retries to re-execute tools against live systems on replay.

The `DeterminismHarness` in the extension SDK tests that a workload produces the same output for the same input — but this is CI-time testing, not production replay.

**Verdict:** Replayability is implemented for the ODR/kernel component. It is not implemented for the full agent execution path. Replaying a session from transcript would re-execute all tool side effects against live systems.

---

## 5. Claimed Property: Explicit Side-Effect Records

### What should happen
Every side effect (write, mutation, API call) should produce a durable record before or after execution.

### What actually happens

`EffectJournalEntryRecord` is the mechanism. It has:
- `effect_id`, `run_id`, `attempt_id`, `step_id`
- `authorization_basis_ref` (what authorized this)
- `intended_target_ref` and `observed_result_ref`
- `uncertainty_classification` (important!)
- `previous_entry` (chain integrity)

This is an excellent design if used. The question is whether it is used. The `ControlPlaneAuthorityService.append_effect_journal_entry()` is the write path. The execution path in `Agent.run()` calls `log_event("tool_call", ...)` — this is a logging call, not a journal write. It is not the same as `append_effect_journal_entry()`.

Unless the `TurnLifecycleInterceptors.apply_after_tool()` hook is wiring journal writes (which would depend on the specific interceptors registered), tool call side effects are being logged but not journaled.

**Verdict:** The side-effect journal infrastructure is excellent. It is not clearly wired to the agent execution path. Tool executions emit log events, not journal entries, unless an interceptor is registered to bridge them.

---

## 6. Claimed Property: Loop Healing

### What should happen
When a workflow gets stuck or fails, the system should detect it and either self-heal or escalate with structured information.

### What actually happens

The code has:
- `IssueConfig.max_retries` and `retry_count` on the card
- `retry_classification_policy.py` in the runtime
- `RecoveryDecisionRecord`, `RecoveryActionClass` in the control plane domain
- `reconciler.py` in `core/domain/`

But the *triggering mechanism* is not visible. Who increments `retry_count`? Who calls the retry classifier? Who creates a `RecoveryDecisionRecord`? The card model has the counters. The domain has the vocabulary. The wiring between a failed agent turn and the retry/escalation path is not visible in the code dump.

The `stop_reason` in `ReactorState` is used in the ODR benchmark path to detect when to stop. Whether a `stop_reason` from a failed agent turn propagates to the retry path is not determinable.

**Verdict:** Loop healing infrastructure exists but the behavioral trigger path is not closed. The system may or may not retry failed turns depending on what the invisible caller of `Agent.run()` does with the returned `ExecutionTurn`.

---

## 7. Claimed Property: Truthful Outcome Classification

### What should happen
Every run should be classified as `accepted / completed / failed / unknown` with an honest basis.

### What actually happens

`FinalTruthRecord` with `ResultClass`, `CompletionClassification`, `EvidenceSufficiencyClassification`, and `ResidualUncertaintyClassification` is a strong vocabulary. `ClosureBasisClassification` and `AuthoritySourceClass` give the basis for the classification.

The gap is in `ControllerRunSummary`:
- Validates that `status="blocked"` can't have successful children ✓
- Does NOT validate that `status="success"` can't have failed children ✗

This means a controller workload can self-report success while its children failed. The `FinalTruthRecord` derived from this summary inherits the lie.

The `EvidenceSufficiencyClassification` suggests the system can report `insufficient_evidence` — but only if the caller correctly computes this field. If the caller defaults to `sufficient`, the claim is unchecked.

**Verdict:** Outcome classification vocabulary is honest and rich. The validation invariants that enforce truthfulness are incomplete. A summary can pass validation while claiming false success.

---

## 8. Behavioral Summary Matrix

| Property | Infrastructure | Wired in Exec Path | Enforced | Verdict |
|---|---|---|---|---|
| Fail-closed | ToolGate | Yes | Partial (interceptors fail-open) | ⚠️ Partial |
| Approval-gated | ControlPlane records | No — post-facto only | No | ❌ Not current |
| Traceability | EffectJournal, ODR | Partial — transcript unlinked | No journal write in turn | ⚠️ Partial |
| Replayability | ODR (kernel only) | ODR: yes; full path: no | Benchmarks only | ⚠️ Kernel only |
| Side-effect records | EffectJournal | Not wired to agent.run | Not enforced | ⚠️ Plumbing exists |
| Loop healing | Retry counters, RecoveryDecision | Trigger path invisible | Unclear | ❓ Unknown |
| Truthful outcomes | FinalTruthRecord, ResultClass | Partial — validator gap | Partial | ⚠️ Partial |

---

## 9. Behavioral Risks for Adapter Targets

Any external system building on Orket's current architecture should assume:

1. **Tools will execute without human approval.** The approval gate in the current agent path is policy validation only. Do not build workflows that require human confirmation before execution using only the current ToolGate.

2. **Interceptor-based governance can silently fail.** Any governance rule implemented as a `TurnLifecycleInterceptor` can be bypassed by a runtime exception. Critical rules must have a fallback that fails the turn hard.

3. **The effect journal may not contain all effects.** Log events and journal entries are different. Tool calls are logged, not journaled, unless a specific interceptor bridges them. An external system's side effects may not appear in Orket's durable record.

4. **Transcripts cannot be trusted for replay.** `Session.transcript` is unschematized. Any downstream system that processes or replays Orket transcripts must implement defensive parsing.

5. **Outcome classifications are unverified for success claims.** A workload reporting `success` is not validated against child results. Verify outcome classifications independently if correctness matters.
