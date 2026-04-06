# Orket Behavioral Review

**Focus:** Runtime behavior, system-level guarantees, observable failure modes, and whether the system does what it says it does.

Last updated: 2026-04-06
Status: Archived source review
Archive: `docs/projects/archive/techdebt/TD04062026B/`

---

## 1. The Determinism Story Is Philosophically Coherent but Practically Fragile

Orket's central promise is reproducible AI agent runs. It achieves this through:
- `run_determinism_class` (`pure` / `workspace` / `external`)
- `execution_capsule` records (network mode, clock mode, timezone, locale, env allowlist hash)
- Protocol append-only ledger with receipt digests
- Determinism campaign tests
- ODR gate with provenance hashing

This is a thoughtful model. The problem is it assumes the **model** is deterministic. Local LLMs via Ollama or LMStudio are not deterministic unless `temperature=0` and `seed` is fixed — and even then, parallel inference and quantization can introduce variance. The entire determinism apparatus is built on top of a component that cannot actually guarantee determinism. The benchmark data (`live_100_determinism_report.json`) shows this awareness — it measures determinism rather than assuming it — but the runtime architecture treats determinism as something that can be *enforced by policy* rather than *measured and accepted*.

If a run is non-deterministic because the model gave a different answer, the ledger records the actual output faithfully. The determinism class in the artifact says `workspace`. Nothing breaks. The system is behaviorally consistent with non-determinism — which is to say the "determinism" controls do not prevent non-deterministic behavior; they only *classify* and *document* it.

This is fine as observability tooling. It is misleading as a "control."

---

## 2. The Spec Debt Queue Cannot Drain

The `spec_debt_queue.py` module requires that:
- The queue is non-empty (`E_SPEC_DEBT_QUEUE_EMPTY` on empty list)
- All three debt types (`doc_runtime_drift`, `schema_gap`, `test_taxonomy_gap`) are represented

This is a governance contract that is snapshotted and validated at run start via `capture_run_start_artifacts`. Every run of Orket loads and validates this snapshot. If any debt item is closed and removed, the next run fails with a contract validation error.

**Observed behavioral consequence:** The debt queue is not a tracker. It is a runtime invariant. Paying off technical debt — all of it — is a breaking change to the runtime. This is likely unintentional but is a real constraint on operations.

---

## 3. The Exception Handling Model Conflates "Run Failed" With "Runtime Crashed"

From `execution_pipeline.py`, the exception handler in `_run_epic_entry` catches:

```
CardNotFound, ComplexityViolation, ExecutionFailed, RuntimeError,
ValueError, TypeError, OSError, asyncio.TimeoutError
```

All of these are handled by writing a `"failed"` run record to the ledger and attempting a degraded run summary. This means:

- A `TypeError` caused by a bug in any of the dozens of functions called during an epic run will be recorded as a failed run, not a crash. The caller gets a structured failure artifact. The bug goes unnoticed unless someone diffs the failure reason field.
- An `OSError` from disk full or permissions on the workspace will also produce a `"failed"` run. The operator may not realize the issue is environmental.
- `RuntimeError` is so broad it could catch errors thrown intentionally by internal protocol enforcement (e.g., the ledger raising `RuntimeError("bounded event queue capacity exceeded")`). These will be silently absorbed as run failures.

The system's observability depends on log events and the run summary to surface the actual cause. If those writes fail (which can happen during an `OSError` scenario), the failure is lost entirely.

---

## 4. The Dual-Write Ledger Has a Behavioral Race Window

The `async_dual_write_run_ledger` writes to SQLite first, then to the append-only protocol file (or vice versa — the ordering is not confirmed without reading the implementation, but dual-write implies serial writes). Between the two writes there is a window where:

- A process kill (SIGKILL, OOM) will leave one backend updated and the other not
- A disk full error on the protocol file leaves SQLite with a record the protocol file lacks

The parity campaign (`test_run_protocol_ledger_parity_campaign.py`) detects this divergence — but only when run explicitly. There is no runtime assertion that both writes have succeeded before the caller proceeds. The behavioral promise "the ledger is consistent" is not enforced at the point of write; it is tested retroactively.

---

## 5. Card State Transitions Are Validated by Registry, But the Registry Is Loaded at Boot

`validate_state_token(domain="session", state=session_status)` is called in `_run_epic_entry` to validate that the computed `session_status` is a known state token. The `state_transition_registry.py` module presumably defines the allowed values. This is correct defensive programming.

The behavioral gap: if the registry file or its snapshot changes between the time the runtime boots and the time a run finalizes, the in-memory registry used for validation may not match the on-disk snapshot used for auditing. Runs that started under registry version N might finalize under registry version N+1. The snapshot written at run start captures the registry version — but validation during the run uses the live in-memory registry from boot time. These can diverge during a long-running process with hot-reload capability or between restarts.

---

## 6. ODR Loop Termination Is Probabilistic

The On-Demand Refinement loop runs an architect model and an auditor model in iteration until a stop condition is met. From `docs/odr/stoplogic.md` and test files, the stop logic involves:
- Round caps (`test_round_cap_probe.py`)
- Auditor verdict assessment
- Convergence scoring

If the architect and auditor disagree indefinitely (two capable models taking opposing positions), the loop terminates by round cap — not by convergence. The result is delivered as "refined" even though no agreement was reached. The downstream system (the coding agent) receives a requirement that the auditor never approved. The behavioral consequence is that the ODR loop's output quality guarantee is "tried N times," not "reached consensus."

---

## 7. The Governance Script Ecosystem Has Behavioral Drift Risk

The 80+ governance scripts under `tests/scripts/` test policies, contracts, and process rules. Many of these tests assert on the *shape* of artifacts (key presence, schema version) rather than on *behavior* (does the system do the right thing when a policy is violated).

Concretely: a test like `test_check_workspace_hygiene_rules.py` verifies that the hygiene rules module produces a snapshot with the expected keys. It does not verify that a workspace that violates those rules is actually rejected by the runtime. The check is static — the behavioral enforcement chain (hygiene rule defined → loaded at run start → violation detected → run blocked) is not tested end-to-end.

This means the governance layer can drift: a rule can exist in the snapshot, pass all tests, and not actually be enforced at runtime if the enforcement path has a bug.

---

## 8. The `FilesystemPolicy` Allows Launch Directory Reads Unconditionally

```python
def can_read(self, path: str) -> bool:
    resolved = Path(path).resolve()
    if resolved == self.launch_dir:
        return True
    ...
```

`self.launch_dir = Path.cwd().resolve()` is set at construction time. Any path that resolves to the directory from which Orket was launched is unconditionally readable — regardless of the configured `read_scope`. If Orket is launched from a sensitive directory (e.g., a home directory or a directory containing credentials), any agent tool call that targets that directory will be permitted by the policy check even if the policy should deny it.

Meanwhile, `can_write` returns `False` for the launch dir unconditionally. The asymmetry is undocumented and the rationale is not in comments.

---

## 9. The Streaming Law Checker Enforces Post-Terminal Rules, But Commit_Final Is Exempt

From `streaming/bus.py`:

```python
if state.terminal_emitted and event_type != StreamEventType.COMMIT_FINAL:
    raise ValueError("Post-terminal events are forbidden except commit_final")
```

`COMMIT_FINAL` can be published after any terminal event. It is the mechanism for flushing final state. The behavioral guarantee is: after `TURN_INTERRUPTED` or `TURN_FINAL`, only `COMMIT_FINAL` is allowed. This is correct.

The gap: `clear_turn` removes the turn state entirely. If `clear_turn` is called between `TURN_FINAL` and `COMMIT_FINAL`, the next `COMMIT_FINAL` will be processed against a fresh state (no `terminal_emitted` flag), and will succeed silently. The protection against post-terminal events is gone. Whether `clear_turn` can be called in this window depends on the call sites — if the session management layer calls `clear_turn` on session end before the streaming layer has flushed `COMMIT_FINAL`, this race is reachable.

---

## 10. Run Summary Materialization Can Silently Use a Degraded Payload

From `run_summary.py` (implied by the `build_degraded_run_summary_payload` function and the `PACKET1_MISSING_TOKEN`), if the run summary cannot be fully materialized (e.g., missing control plane records, ledger read failure), a degraded summary is written. This degraded summary:
- Still passes as a valid summary artifact
- Is written to the same location as a full summary
- Has no `is_degraded: true` field visible in the standard schema (or if it does, consumers must check for it)

Downstream consumers of the run summary (CI gates, the ODR scorer, the companion matrix evaluator) receive the degraded payload and may compute wrong scores or verdicts without any indication that the data they scored was incomplete.

---

## Behavioral Risk Matrix

| Behavior | Risk | Trigger |
|---|---|---|
| `TypeError`/`OSError` silently recorded as run failure | High | Any code bug or infra issue during epic execution |
| Spec debt queue blocks runs if all debt is resolved | High | Closing all SDQ entries |
| Dual-write ledger divergence undetected until campaign | Medium–High | Process kill or disk full during write |
| FilesystemPolicy allows launch-dir reads unconditionally | Medium | Launching from a sensitive path |
| ODR loop delivers non-converged output as "refined" | Medium | Model disagreement beyond round cap |
| Governance scripts don't test enforcement chain end-to-end | Medium | Policy added but enforcement path broken |
| Degraded run summaries scored as complete by consumers | Medium | Control plane unavailability during finalize |
| Streaming race: clear_turn before COMMIT_FINAL | Low–Medium | Session teardown timing |
| Determinism class label doesn't prevent non-determinism | Low | All runs using non-zero temperature |
