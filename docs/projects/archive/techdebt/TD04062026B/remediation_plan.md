# Orket Remediation Plan

Last updated: 2026-04-06
Status: Completed
Archive: `docs/projects/archive/techdebt/TD04062026B/`

**Ordering:** Critical safety fixes first, then structural refactors, then process improvements. Each item includes an effort estimate and a success condition.

**Status as of 2026-04-06**
- Completed in the repo: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4
- Remaining active blockers for lane completion: none
- Closeout proof: `python -m mypy --strict orket` exits with zero errors across 571 source files.

---

## Phase 1 — Critical Safety Fixes (Do These Now)

### 1.1 Narrow the Exception Handler in `_run_epic_entry`

**Problem:** `TypeError`, `OSError`, and `RuntimeError` are caught alongside domain exceptions and silently recorded as run failures, hiding bugs and infrastructure issues.

**Fix:**
1. Create a distinct exception class `OrketInfrastructureError` (subclass of `RuntimeError`) for infrastructure-level failures that *should* be recorded as run failures (e.g., ledger write errors, workspace I/O during normal operation).
2. Remove `TypeError` from the catch block entirely — it should never be caught; it indicates a programming error.
3. Remove bare `OSError` — replace with targeted catches at specific I/O call sites that need to degrade gracefully.
4. The final catch block should handle: `CardNotFound`, `ComplexityViolation`, `ExecutionFailed`, `OrketInfrastructureError`.

**Effort:** 1–2 days
**Success condition:** A `TypeError` raised inside `_run_epic_entry` propagates to the caller as an unhandled exception and shows up in logs as a crash, not a failed run record.

---

### 1.2 Fix the Dual-Write Ledger's Partial-Write Gap

**Problem:** A process kill between the SQLite write and the protocol file write (or vice versa) leaves the ledger in a divergent state that is only detected by a retroactive parity campaign.

**Fix:**
1. Add an atomic "write intent" record at the start of any dual-write operation — a lightweight marker that both backends must acknowledge.
2. At startup, scan for uncommitted write intents and either complete or roll them back before accepting new writes.
3. Alternatively (simpler): make the protocol file the authoritative source and make SQLite a derived read model rebuilt on startup from the protocol file. This eliminates the dual-write entirely.

**Effort:** 3–5 days (atomic intent approach); 1–2 weeks (SQLite-as-projection approach)
**Success condition:** A simulated process kill at the write midpoint is detected and handled on next startup without manual intervention.

---

### 1.3 Fix `FilesystemPolicy` Launch Directory Bypass

**Problem:** `can_read` unconditionally allows reads from the launch directory, bypassing configured `read_scope`.

**Fix:**
1. Remove the unconditional `return True` for `resolved == self.launch_dir`.
2. If the launch directory genuinely needs to be readable for config loading, add it explicitly to `reference_spaces` during policy construction rather than hardcoding it as a bypass.
3. Document the security model: write a one-paragraph comment on `FilesystemPolicy` explaining the three scopes and what `launch_dir` is for.

**Effort:** Half a day
**Success condition:** A test verifying that a path in the launch directory is not readable when `read_scope` excludes `domain` passes.

---

### 1.4 Decouple `spec_debt_queue` From Run Start

**Problem:** Every run validates that the spec debt queue is non-empty and contains all three debt types. Closing debt breaks the runtime.

**Fix:**
1. Remove `spec_debt_queue_snapshot()` from the set of artifacts written and validated by `capture_run_start_artifacts`. It is observability metadata, not a runtime invariant.
2. Change `validate_spec_debt_queue` to allow an empty queue (remove `E_SPEC_DEBT_QUEUE_EMPTY`).
3. Remove the `debt_types != _EXPECTED_DEBT_TYPES` set equality check. Validate only structure (each entry has `debt_id`, `debt_type`, `status`, `owner`), not a specific required set.
4. Move debt queue governance to a CI-only check, not a runtime gate.

**Effort:** Half a day
**Success condition:** An empty spec debt queue does not prevent a run from starting.

---

## Phase 2 — Structural Refactors (Next Sprint)

### 2.1 Extract `_run_epic_entry` Into a Dedicated `EpicRunOrchestrator`

**Problem:** `_run_epic_entry` is 300+ lines in a class with 12+ constructor-wired dependencies. It is untestable in isolation.

**Fix:**
1. Create `orket/runtime/epic_run_orchestrator.py` with a class `EpicRunOrchestrator`.
2. Its constructor receives only the dependencies it actually uses: `cards_repo`, `sessions_repo`, `run_ledger`, `cards_epic_control_plane`, `loader`, `orchestrator`, `workload_shell`, `workspace`.
3. Move `_run_epic_entry` body into `EpicRunOrchestrator.run(epic_name, ...)`.
4. `ExecutionPipeline` becomes a factory/coordinator that builds `EpicRunOrchestrator` and delegates to it.

**Effort:** 3–5 days
**Success condition:** `EpicRunOrchestrator` can be unit-tested with mock dependencies without constructing a full `ExecutionPipeline`.

---

### 2.2 Abstract the Snapshot/Validate Pattern

**Problem:** 40+ files implement the same `snapshot() / validate()` idiom with copy-pasted duplicate-detection and row-checking logic.

**Fix:**
1. Create `orket/runtime/contract_schema.py` with a generic `ContractRegistry` class:
   ```python
   class ContractRegistry:
       def __init__(self, schema_version: str, rows: list[dict], required_ids: set[str] | None = None):
           ...
       def validate(self, payload: dict | None = None) -> tuple[str, ...]:
           ...  # shared: non-empty, no duplicates, required set, field presence
   ```
2. Migrate the simplest contracts first (ones with only `check_id` / `example_id` fields).
3. Leave the complex contracts (ones with cross-validation against other snapshots, like `capability_fallback_hierarchy`) as custom implementations, but document why.

**Effort:** 1 week for base class + migration of 20 contracts; 2 weeks for full migration
**Success condition:** Adding a new contract requires writing only a `_snapshot()` function and a config dict, not a 60-line validate function.

---

### 2.3 Fix Type Annotations Throughout

**Problem:** `build_id: str = None`, `Any | None` for typed repos, `**kwargs` swallowing typos, `references: list[str] = None`.

**Fix:**
1. Run `mypy --strict` or `pyright` on `orket/` and fix all errors. The codebase already uses `from __future__ import annotations` universally — type checking is possible with minimal friction.
2. Define `Protocol` interfaces for `RunLedger`, `CardRepository`, `SessionRepository`, etc. so injection points are contractually typed.
3. Replace `**kwargs` pass-through in `run_card` / `run_epic` / `run_issue` / `run_rock` with explicit parameter forwarding. These methods are public API — their signatures should be explicit.

**Effort:** 1 week
**Success condition:** `mypy --strict orket/` exits with zero errors.

---

### 2.4 Make `capture_run_start_artifacts` Transactional

**Problem:** The function writes 5+ JSON files to disk with no rollback if it is interrupted mid-way. An interrupted write leaves the run in a partial-artifact state.

**Fix:**
1. Write all artifacts to a staging directory (`runtime_contracts_staging/`) first.
2. After all writes succeed, atomically rename/move the staging directory to the final location.
3. On load, detect a staging directory (without a corresponding finalized directory) and treat it as an incomplete run start — either clean it up or fail loudly.

**Effort:** 2–3 days
**Success condition:** Simulating a write interruption (e.g., raising after the second JSON file write) does not leave a partially-initialized runtime contracts directory.

---

### 2.5 Replace `type()` Mock in `preview.py`

**Problem:** `type("MockProvider", (), {"model": selected_model})` creates an anonymous class to satisfy `Agent`'s constructor. This breaks silently on interface changes.

**Fix:**
1. Define a `PreviewModelProvider` dataclass or named class in `preview.py`:
   ```python
   @dataclass
   class PreviewModelProvider:
       model: str
   ```
2. Alternatively, define a `ModelProvider` Protocol with `model: str` and have `Agent` accept `ModelProvider`.

**Effort:** Half a day
**Success condition:** `Agent` can be constructed in preview mode using a named, typed class.

---

### 2.6 Document and Fence the Threading in `worker_client.py`

**Problem:** `Worker.run_claimed_work` spawns a `threading.Thread` for lease renewal inside what is otherwise an async codebase. The interaction model is undocumented.

**Fix:**
1. If the worker is only ever called from sync contexts: add a `# NOTE:` comment explaining it is sync-only and why.
2. If it should be async: refactor `_renew_loop` to use `asyncio.create_task` and `asyncio.sleep`, eliminating the thread.
3. Remove the hardcoded `renew_thread.join(timeout=2.0)` — if the renew thread doesn't join in 2 seconds, the join silently times out and the thread may still be running.

**Effort:** 1 day
**Success condition:** Either the thread is gone (async refactor) or the method has a docstring saying "must be called from a non-async context."

---

## Phase 3 — Process Improvements (This Quarter)

### 3.1 Distinguish Living vs. Archaeological Governance Scripts

**Problem:** 80+ test scripts in `tests/scripts/` with no indication of which are run regularly vs. which captured a one-time state.

**Fix:**
1. Add a marker comment at the top of each script: `# LIFECYCLE: live | archived | one-shot`
2. Add a `conftest.py` fixture that reads this marker and skips `one-shot` scripts in regular CI, running them only in a dedicated audit job.
3. Move archived scripts to `tests/scripts/archive/`.

**Effort:** 2–3 days
**Success condition:** Running `pytest tests/scripts/` in CI only executes `live` scripts; `one-shot` scripts are skipped automatically.

---

### 3.2 Add End-to-End Enforcement Tests for Governance Policies

**Problem:** Governance scripts validate that policy snapshots have the right shape, but do not test that violations are actually blocked by the runtime.

**Fix:**
1. For the 5 highest-stakes policies (workspace hygiene, source attribution, trust language, nervous system, tool gate), write integration tests that:
   - Start a real (or near-real) run with a workspace that violates the policy
   - Assert the run is blocked before the model is called
2. These tests should live in `tests/integration/policy_enforcement/`, not `tests/scripts/`.

**Effort:** 1 week
**Success condition:** Breaking a policy in the test workspace causes the integration test to block the run and the unit test for the script to still pass.

---

### 3.3 Add `is_degraded` to Run Summary Schema

**Problem:** Degraded run summaries are structurally indistinguishable from complete ones.

**Fix:**
1. Add `"is_degraded": false` to the standard run summary schema.
2. Set it to `true` in `build_degraded_run_summary_payload`.
3. Update downstream consumers (companion matrix scorer, ODR gate, CI gate) to reject or flag summaries where `is_degraded == true`.

**Effort:** 1–2 days
**Success condition:** A scoring pipeline that receives a degraded summary raises a visible warning and does not produce a normal score.

---

### 3.4 ODR Loop: Expose Convergence Status in Output

**Problem:** A round-cap-terminated ODR run produces output indistinguishable from a converged run.

**Fix:**
1. Add `"termination_reason": "convergence" | "round_cap"` to the ODR result artifact.
2. Add `"final_auditor_verdict": "approved" | "rejected" | "timeout"`.
3. The downstream coding agent should receive — and log — this signal. Optionally, block epic execution if the ODR result is `round_cap` with `final_auditor_verdict: rejected`.

**Effort:** 2 days
**Success condition:** An ODR run that hits the round cap is identifiable in the run summary without reading the raw ODR log.

---

## Summary Roadmap

| Phase | Items | Estimated Total Effort |
|---|---|---|
| Phase 1 (Critical fixes) | 1.1 – 1.4 | 1–2 weeks |
| Phase 2 (Structural refactors) | 2.1 – 2.6 | 4–6 weeks |
| Phase 3 (Process improvements) | 3.1 – 3.4 | 2–3 weeks |
| **Total** | | **7–11 weeks** |

These estimates assume one engineer working on remediation while the rest of the team continues feature work. Phase 1 items are suitable for parallel execution. Phase 2 items should be sequenced: 2.1 (extract `EpicRunOrchestrator`) before 2.2 (abstract snapshot pattern), 2.3 (fix types) last since it may surface new issues once the refactors are in place.
