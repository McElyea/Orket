# Orket — Remediation Plan

**Date:** 2026-04-06
**Based on:** Code Review (2026-04-06) + Behavioral Review (2026-04-06)
**Prioritization:** Critical safety first → high behavioral correctness → medium reliability → low hygiene

Issues are grouped into workstreams that can be executed in parallel by different owners. Each item includes an acceptance criterion that a test or structural check can verify.

---

## Workstream 1 — Kernel Correctness (Blocker for any determinism claim)

Owner: Kernel
Priority: Ship nothing that relies on determinism guarantees until W1 is done.

### W1-1. Fix `stage_triplet` monkey-patch (C-1 / BH-2)

**Action:**
1. Delete the stub `stage_triplet` body and `_update_refs_by_id` from the `LocalSovereignIndex` class.
2. Move `_stage_triplet_grouped_update` into the class body as `stage_triplet`.
3. Remove the `LocalSovereignIndex.stage_triplet = ...` line at the bottom of the module.
4. Delete `_update_refs_by_id` entirely.

**Acceptance criteria:**
- `grep -n "LocalSovereignIndex.stage_triplet =" orket/kernel/v1/state/lsi.py` returns no results.
- All existing LSI tests pass.
- A new test confirms `LocalSovereignIndex().stage_triplet(...)` does not raise `RuntimeError`.

---

### W1-2. Unify canonicalization (C-2 / BH-3)

**Action:**
1. Decide on one canonical system. Recommendation: `canonical.py` (RFC 8785 compliant) is the correct long-term choice. `canon.py`'s stripping behavior should be implemented as a pre-processing step on the data, not inside the serializer.
2. Create a `CanonicalPolicy` class or module that documents which keys are non-semantic (temporal, path, run-specific) and strips them before handing off to `canonical.py`.
3. Update `repro_odr_gate.py` and `test_odr_determinism_gate.py` to use the unified path.
4. Update all callers of `canon.py` to use the new path.
5. Delete `canon.py` after all callers are migrated.
6. Regenerate and re-pin all expected SHA256 hashes in test fixtures.

**Acceptance criteria:**
- `canon.py` does not exist.
- All determinism gate tests pass with re-pinned hashes.
- A structural test asserts that no module imports from `canon.py`.

---

### W1-3. Fix `run_round` mutation (C-3 / BH-1)

**Action:**
1. Freeze `ReactorState` (`@dataclass(frozen=True)`) or introduce a `ReactorState.copy_with(...)` method.
2. Update `run_round` to return a new state object, not the mutated input.
3. Update all callers to use the returned value.

**Acceptance criteria:**
- `ReactorState` is frozen or has explicit copy semantics.
- A test calls `run_round` with a captured pre-call snapshot, asserts the snapshot is unchanged after the call, and asserts the returned state reflects the update.

---

## Workstream 2 — Lifecycle Event Durability (Blocker for production use of spool fallback)

Owner: Application Services

### W2-1. Spool replay exception handling (C-4)

**Action:**
1. Add logging in the `except Exception` block in `replay_spool` — log the exception, the record's ID, and a retry count.
2. Introduce a per-record retry counter. After N failures (configurable, default 3), move the record to a dead-letter file rather than re-queuing.
3. Return a structured result from `replay_spool` that includes counts of replayed, re-queued, and dead-lettered records.

**Acceptance criteria:**
- A test injects a repository that always raises and verifies that records are eventually moved to dead-letter, not re-queued indefinitely.
- `replay_spool` logs at least one structured message per failed record.

---

### W2-2. Atomic spool rewrite (C-5)

**Action:**
1. Replace the direct write to `spool_path` in `_rewrite_spool` with a write to `spool_path.with_suffix(".tmp")` followed by an atomic `rename`.
2. Ensure the `.tmp` file is cleaned up if it already exists before writing.

**Acceptance criteria:**
- `_rewrite_spool` uses `rename` for the final commit.
- A test that simulates a crash mid-rewrite (by raising after the tmp write) confirms the original spool file is intact.

---

### W2-3. Concurrency guard for `replay_spool` (BH-7)

**Action:**
1. Add a file lock (e.g., using `fcntl.flock` on Linux or `msvcrt.locking` on Windows, or a cross-platform library like `filelock`) around the read-replay-rewrite cycle in `replay_spool`.
2. If the lock is already held, `replay_spool` should return 0 (another caller is handling it) rather than racing.

**Acceptance criteria:**
- A test launches two concurrent `replay_spool` calls and verifies no record is double-replayed or lost.

---

## Workstream 3 — State Machine and API Correctness

Owner: Application Services + Control Plane

### W3-1. Fix `transition_state` double-fetch (H-1 / BH-6)

**Action:**
1. Update `apply_record_mutation` to return the written record.
2. Remove the second `_require_record` call in `transition_state`.
3. Return the record from the mutation result directly.

**Acceptance criteria:**
- `transition_state` makes exactly one repository read per call (the initial fetch for fencing).
- A test injects a repository that counts calls and asserts exactly one read.

---

### W3-2. Fix `execution_repository: Any | None` (H-2)

**Action:**
1. Define a `Protocol` for `ExecutionRepository` with the methods actually used.
2. Replace `Any | None` with `ExecutionRepository | None`.
3. Add an assertion or guard in the code paths that use it: if it is `None` where it is required, raise `ValueError` explicitly.

**Acceptance criteria:**
- `mypy` or `pyright` no longer suppresses errors on this parameter.
- A test asserts that calling the relevant method with `execution_repository=None` raises a clear error rather than silently no-oping.

---

### W3-3. Fix `_select_case_id` silent wrong-case fallback (H-3)

**Action:**
1. If the request has no `case_id` and there is more than one known case, return an error response instead of silently picking the first.
2. The single-case auto-select convenience can stay but should log a warning.

**Acceptance criteria:**
- A test sends a request with no `case_id` to a server with multiple loaded cases and verifies an error is returned.
- A test with exactly one loaded case verifies the auto-select still works.

---

### W3-4. Fix tool approval action ID collision risk (BH-9)

**Action:**
1. Ensure `decision_token` is explicitly set to `"deny"` on the denial path rather than relying on the `resolution.decision` field which may be absent.
2. Add a structural separator in the action ID format to make denial and approval IDs namespace-distinct (e.g., prefix with `deny:` or `approve:`).

**Acceptance criteria:**
- A test generates an action ID for a denial and an action ID for a grant with otherwise identical inputs and asserts they are not equal.

---

## Workstream 4 — Infrastructure and CI Reliability

Owner: DevOps / CI

### W4-1. Remove hardcoded Windows path from extension script (H-4)

**Action:**
1. Remove the default from `--textmystery-root`.
2. Add logic to read from `TEXTMYSTERY_ROOT` environment variable.
3. Fail with a clear error if neither argument nor env var is set.

**Acceptance criteria:**
- Running the script with no arguments on a system without `TEXTMYSTERY_ROOT` set prints a clear error and exits non-zero.
- The string `C:/Source` does not appear anywhere in the scripts directory.

---

### W4-2. Fix `backup_gitea.sh` shell safety (M-2)

**Action:**
1. Add `set -euo pipefail` at the top.
2. Change the cleanup `cd "$BACKUP_DIR"` + `ls | tail | xargs rm` pattern to use absolute paths: `find "$BACKUP_DIR" -name "gitea_backup_*.tar.gz" | sort -r | tail -n +8 | xargs -r rm`.

**Acceptance criteria:**
- ShellCheck passes on the script with no warnings.

---

### W4-3. Add `benchmarks/results/` to `.gitignore` (M-1)

**Action:**
1. Add `benchmarks/results/` to `.gitignore`.
2. Remove already-committed result files from git history (optional, use `git filter-repo` if desired).
3. Move expected/pinned hashes into a dedicated `benchmarks/contracts/` directory that is version-controlled.

**Acceptance criteria:**
- `git status` after a local benchmark run shows no new untracked files under `benchmarks/results/`.
- CI regenerates result artifacts as non-committed outputs.

---

### W4-4. Fix first-push `origin/main` absent in monorepo CI (M-5)

**Action:**
1. In `detect_changed_packages.py`, handle the case where the base ref does not exist by treating all packages as changed.
2. Add a fallback: `git rev-parse --verify origin/main` before diffing; if it fails, output all packages as changed.

**Acceptance criteria:**
- A dry-run test of the script in a repo with no `origin/main` returns all packages as changed rather than crashing.

---

### W4-5. Add a real execution smoke to the quant sweep CI (BH-10)

**Action:**
1. Add a second step to `quant-sweep-smoke.yml` that runs the sweep against a local stub/mock model rather than `--dry-run`.
2. This step should exercise at least one full sweep round-trip to validate the execution path.

**Acceptance criteria:**
- The CI job fails if the sweep runner cannot complete one execution round.

---

## Workstream 5 — ControlPlane Convergence (Deferred / Explicit Reopen Required)

Owner: Orket Core
**Note:** This workstream is intentionally last and cannot be started without an explicit reopen of the paused convergence lane per the freeze rules in `CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`.

The eight documented gaps (BH-5) should be addressed in the following order when the lane reopens:

1. Attempt history universally first-class (Workstream 2 of the existing convergence plan).
2. Reservation and lease truth universal across admission and scheduling (Workstream 3).
3. Effect truth through normative effect journal on all governed mutation paths (Workstream 4).
4. Checkpoint publication and supervisor-owned acceptance as execution-default (Workstream 5).
5. Operator-action authority unified across all paths (Workstream 6).
6. Namespace and safe-tooling gates universal (Workstream 7).
7. Closure truth unified through `FinalTruthRecord` (Workstream 8, already partially closed).
8. Workload identity conflict resolution (foundational, should be re-assessed when above are done).

**Pre-condition for reopen:** All W1–W4 items above must be closed first. A clean, non-hybrid runtime is required before the convergence lane can make meaningful progress.

---

## Workstream 6 — Code Hygiene (Non-blocking, parallelizable)

Owner: Any contributor

These can be addressed incrementally as files are touched, or in a single hygiene PR.

- **W6-1:** Standardize all type annotations to built-in generics (`dict`, `list`, `tuple`). Add `UP006`, `UP035` ruff rules to enforce.
- **W6-2:** Add `from __future__ import annotations` uniformly, or decide not to use it and remove existing ones. Document the decision in `CONTRIBUTING.md`.
- **W6-3:** Delete `packages.template.json` or add a comment explaining it.
- **W6-4:** Replace anonymous `type("Org", (), {...})` fakes in tests with proper dataclass or Protocol fixtures.
- **W6-5:** Extract `execution_repository` injection pattern into a shared base or container entry.
- **W6-6:** Document `stale_threshold_runs` semantics in the CI failure policy schema or a README.

---

## Completion Gate

This plan is complete when:

1. All W1 items are closed (structural proof: tests pass, `canon.py` deleted, monkey-patch removed).
2. All W2 items are closed (live proof: spool durability tests pass, atomic rewrite verified).
3. All W3 items are closed (structural proof: `Any` removed from service signatures, double-fetch eliminated).
4. All W4 items are closed (CI proof: quant sweep smoke runs execution, backup script passes ShellCheck).
5. W5 remains explicitly deferred until a lane reopen is recorded in `ROADMAP.md`.
6. W6 items are tracked as open hygiene work without blocking the completion gate.

A governance hygiene script run (`python scripts/governance/check_docs_project_hygiene.py`) and a full test suite run must both pass before this plan is considered closed.
