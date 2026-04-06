# Orket Code Review — Brutal Edition

**Scope:** Full codebase dump — 568 source files, ~480K lines including tests, benchmarks, docs, workflows, and governance tooling.
**Reviewer posture:** Assume production use with real consequences. No grace for nice intentions.

Last updated: 2026-04-06
Status: Archived source review
Archive: `docs/projects/archive/techdebt/TD04062026B/`

---

## 1. `ExecutionPipeline` Is a God Object and Nobody Stopped It

`orket/runtime/execution_pipeline.py` is the worst offender in the codebase. The `__init__` method alone wires together:

- A `DecisionNodeRegistry`
- An `OrketRuntimeContext`
- Five async repository dependencies
- A `GiteaArtifactExporter`
- A `NoteStore`
- A `SandboxOrchestrator`
- A `WebhookDatabase`
- A `BugFixManager`
- An `Orchestrator`
- A `CardsEpicControlPlaneService`
- A `SharedWorkloadShell`

That is twelve conceptually distinct subsystems configured inside a single constructor. The class then has public entry points (`run_card`, `run_epic`, `run_issue`, `run_rock`, `run_gitea_state_loop`) and private helpers numbering into the dozens. `_run_epic_entry` alone is 300+ lines and does session lifecycle, card state management, contract artifact capture, capability manifest parsing, run ledger writes, transcript building, source attribution gating, control plane finalization, summary materialization, and Gitea export — sequentially, in one coroutine, with a six-exception-type bare `except` block at the bottom.

This is not an orchestration pipeline. It is a kitchen sink that learned to `await`.

**Specific bugs and smells inside `_run_epic_entry`:**

- `build_id: str = None` (and similar throughout) is incorrect Python — the annotation says `str`, the default is `None`. Should be `str | None = None`. This is repeated across most public methods.
- The nested closure `_execute_cards_workload` captures `active_build`, `run_id`, `epic`, `team`, `env`, `target_issue_id`, `resume_mode`, and `model_override` from the outer scope. If any of those names are rebound before the closure executes (they aren't here, but the pattern invites future bugs), behavior silently changes.
- The catch block handles `CardNotFound, ComplexityViolation, ExecutionFailed, RuntimeError, ValueError, TypeError, OSError, asyncio.TimeoutError` in one branch. Catching `TypeError` and `OSError` alongside domain exceptions means infrastructure failures (e.g., disk full, a misspelled attribute access) are treated as recoverable run failures and written to the ledger as `"failed"` runs. The distinction between "the run failed" and "the code crashed" is gone.
- `artifacts` is mutated in-place across the happy path and then separately reconstructed under failure — two partially-overlapping assembly paths for the same dict. If a key is added to one path and not the other, the ledger will have inconsistent shapes across runs.

---

## 2. The Contract Snapshot Pattern Is Copy-Pasted 40+ Times

The following structure appears in virtually every file under `orket/runtime/`:

```python
def some_thing_snapshot() -> dict[str, Any]:
    return { "schema_version": "1.0", ... }

def validate_some_thing(payload: dict[str, Any] | None = None) -> ...:
    policy = dict(payload or some_thing_snapshot())
    # validate fields one by one
    return tuple(sorted(observed_ids))
```

Files confirmed to follow this exact pattern include: `artifact_provenance_block_policy.py`, `canonical_examples_library.py`, `capability_fallback_hierarchy.py`, `clock_time_authority_policy.py`, `cold_start_truth_test_contract.py`, `spec_debt_queue.py`, and at least 35 more.

The duplication is not cosmetic. Each implementation re-implements:
- The `dict(payload or snapshot())` fallback idiom
- Iteration over a `list` with `isinstance(row, dict)` row checks
- Duplicate-detection via `len(set(ids)) != len(ids)`
- Set-equality against a hardcoded `_EXPECTED_*` constant

None of this is shared. Any bug in the pattern (e.g., an off-by-one in duplicate detection, a missing strip call) must be fixed 40 times. There is no base class, no generic validator, no shared utility. There is not even a comment acknowledging this is intentional.

---

## 3. `spec_debt_queue.py` Enforces That Debt Must Exist

```python
_EXPECTED_DEBT_TYPES = {"doc_runtime_drift", "schema_gap", "test_taxonomy_gap"}

def validate_spec_debt_queue(payload):
    ...
    if debt_types != _EXPECTED_DEBT_TYPES:
        raise ValueError("E_SPEC_DEBT_QUEUE_DEBT_TYPE_SET_MISMATCH")
```

The validator hardcodes that all three debt types must be present. If `SDQ-001` (doc_runtime_drift) is ever resolved and removed from the queue, validation breaks. You cannot close debt without simultaneously relaxing the validator. This is not a debt queue. It is a debt monument. It guarantees debt is never fully paid.

Additionally, `if not rows: raise ValueError("E_SPEC_DEBT_QUEUE_EMPTY")` — the queue is not allowed to be empty. The system's own governance contract has enshrined the requirement that unresolved technical debt always exist.

---

## 4. `preview.py` Is a Maintenance Liability

```python
mock_provider = type("MockProvider", (), {"model": selected_model})
agent = Agent(seat_name, desc, {}, mock_provider)
```

Creating a class at runtime with `type()` to paper over a missing abstraction is a design smell. If `Agent`'s constructor signature changes, this blows up at runtime, not at import time, not during type checking. The static analyzer sees nothing wrong.

Elsewhere in the same file:
```python
except (ValueError, FileNotFoundError) as e:
    log_event(...)
    pass
```

Swallowing exceptions and continuing with `self.org = None` means preview results are silently wrong when the org config is missing or malformed. Users see a preview; the preview is built without org context; nobody knows.

Also: `references: list[str] = None` in `create_session_policy` (`policy.py`) is a mutable default argument bug. It works only because `None` is not actually mutable — but it signals the author didn't know why the pattern exists, and another developer could easily introduce a truly mutable default nearby.

---

## 5. Loose Typing Is Systematic

`run_ledger_repo: Any | None` in `ExecutionPipeline.__init__` signals that the type of the run ledger is not contractually defined at the call site. Whatever gets passed in is used with duck typing. This is reasonable for dependency injection, except there is no Protocol or ABC defining the interface. There are just calls like `await self.run_ledger.start_run(...)` that will raise `AttributeError` at runtime if the wrong object is passed.

`**kwargs` is used in `run_card`, `run_epic`, `run_issue`, `run_rock`, and `_run_epic_entry`. These kwargs flow through multiple layers before being consumed. The call chain is `run_card → _run_epic_entry` with `**forwarded_kwargs` after popping `target_issue_id`. Any typo in a kwarg name is silently ignored for the entire call depth.

---

## 6. `run_gitea_state_loop` Has an Inline Lambda That Belongs in a Method

```python
process_rules_get = process_rules.get if hasattr(process_rules, "get") else lambda key, default=None: getattr(process_rules, key, default) if process_rules is not None else default
```

This is one logical line. It handles three cases (dict-like, object-like, None) in a ternary-inside-lambda. It is not readable. It is not testable in isolation. It is not named. A three-line method called `_get_process_rule(key, default)` would be clearer, shorter, and independently testable.

---

## 7. Threading Mixed Into an Async Codebase Without Acknowledgment

`worker_client.py` uses `threading.Thread` and `threading.Event` for the lease renewal loop inside `run_claimed_work`. This runs a sync thread alongside async code. The implications (GIL contention, asyncio event loop interaction if `sleep_fn` is ever swapped for an async version, the 2-second hardcoded join timeout) are undocumented. `time.sleep` blocks the OS thread, which is correct here, but the code offers no comment explaining why it's not an `asyncio.Task`.

---

## 8. `capture_run_start_artifacts` Is a Side-Effect Blizzard

This function:
1. Creates directories on disk
2. Loads runtime contract snapshots
3. Writes multiple JSON files (with immutability enforcement)
4. Resolves and writes run identity
5. Generates a capability manifest and writes it
6. Captures workspace state
7. Returns a dict of 20+ keys

It is called from `_run_epic_entry` via `asyncio.to_thread`, meaning its entire execution (multiple file reads/writes) runs in a thread pool executor. If any file write fails mid-way, the run identity file might exist but the capability manifest might not. There is no transaction boundary, no rollback, no partial-write detection. The immutability checks (`_write_immutable_json`) only protect against mutation on a second call — they do not protect against corruption from an interrupted first call.

---

## 9. The Governance Script Test Surface Is Untethered From Source

There are 80+ test files under `tests/scripts/`, each testing an individual governance or CI script. Many of these tests (`test_check_*`) follow a pattern where they:
1. Build a fixture
2. Call `evaluate_X()` on it
3. Assert on the returned structure

The scripts themselves (`check_*`) exist as standalone modules. Many of these scripts appear to exist because a contract changed and needed a one-time validation pass — they are historical snapshots treated as living tests. This creates a maintenance burden where new developers must understand which scripts are "living" (run regularly) and which are "archaeological" (ran once in March 2026 and never again). The naming convention does not distinguish them.

---

## 10. The Dual-Write Ledger Has No Documented Failure Mode for Divergence

`async_dual_write_run_ledger.py` maintains two backends: SQLite and an append-only protocol file. Parity campaigns (`test_run_protocol_ledger_parity_campaign.py`) verify they agree. But the source code for the dual-write adapter almost certainly does not handle the case where the SQLite write succeeds and the protocol file write fails (or vice versa). Partial writes leave the ledger in a divergent state that the parity campaign will detect — but only on the next campaign run, not immediately. The window between a partial write and detection is unbounded.

---

## Summary Severity Table

| Issue | Severity | File(s) |
|---|---|---|
| `ExecutionPipeline` god object / 300-line `_run_epic_entry` | Critical | `runtime/execution_pipeline.py` |
| Broad exception catch merges infra and domain failures | Critical | `runtime/execution_pipeline.py` |
| 40+ copy-pasted snapshot/validate pairs | High | All `runtime/*.py` contract files |
| `spec_debt_queue` makes debt irresolvable | High | `runtime/spec_debt_queue.py` |
| `capture_run_start_artifacts` non-transactional multi-write | High | `runtime/run_start_artifacts.py` |
| Loose `Any` typing on ledger, `**kwargs` silently dropped | High | `runtime/execution_pipeline.py` |
| `type()` mock class in `preview.py` | Medium | `preview.py` |
| Swallowed exceptions in preview org loading | Medium | `preview.py` |
| `process_rules_get` inline lambda | Medium | `runtime/execution_pipeline.py` |
| Threading in async context undocumented | Medium | `adapters/execution/worker_client.py` |
| `build_id: str = None` annotation errors throughout | Low–Medium | Multiple |
| Governance scripts lack living vs. archaeological distinction | Low | `tests/scripts/` |
