# Orket — Brutal Code Review

**Date:** 2026-04-06
**Reviewer:** Claude (Sonnet 4.6)
**Scope:** Full repository dump — architecture, core kernel, application services, adapters, scripts, CI, tests
**Note:** An archived behavioral review already exists at `docs/projects/archive/techdebt/BR03172026/orket_behavioral_review.md` (dated 2026-03-17). That cycle is marked closed. This review treats the current codebase as the baseline and calls out all issues regardless of whether a previous cycle touched them.

---

## Severity Legend

| Level | Meaning |
|---|---|
| 🔴 **Critical** | Silent data loss, crash path, or fundamental semantic lie in hot path |
| 🟠 **High** | Wrong state visible to callers, likely to cause real bugs under normal use |
| 🟡 **Medium** | Fragile, misleading, or time-bomb behavior |
| 🔵 **Low** | Inconsistency, style drift, or minor spec deviation |

---

## 🔴 CRITICAL

---

### C-1. `lsi.py` — The class body `stage_triplet` is permanently broken; a module-level monkey-patch is the only thing that prevents every call from crashing

**File:** `orket/kernel/v1/state/lsi.py`
**Functions:** `LocalSovereignIndex.stage_triplet`, `_update_refs_by_id`, `_stage_triplet_grouped_update`

The `stage_triplet` method defined in the class body calls `self._update_refs_by_id(sources)`. That method unconditionally raises `RuntimeError` on its first iteration — it exists only as a contract-enforcement stub that says "call the grouped version instead." At the bottom of the module, the class method is silently replaced:

```python
LocalSovereignIndex.stage_triplet = _stage_triplet_grouped_update  # type: ignore[attr-defined]
```

The class definition is a lie. This is effectively dead-code-with-landmines. Any subclass calling `super().stage_triplet(...)` will crash. Any test that imports the class before the module finishes loading (e.g., via `importlib` tricks, circular imports, or mocking internals) gets the crash version. The class is unreadable — every reader must track a module-level side-effect that fires at import time to understand what `stage_triplet` actually does.

**Fix:** Delete the stub body and `_update_refs_by_id`. Put the correct grouped implementation directly in the class body.

---

### C-2. Two canonicalization systems are simultaneously active and cannot verify each other

**Files:** `orket/kernel/v1/canon.py`, `orket/kernel/v1/canonical.py`

| Property | `canon.py` | `canonical.py` |
|---|---|---|
| RFC 8785 compliant | ❌ `json.dumps(sort_keys=True)` | ✅ uses `rfc8785`/`jcs` |
| Strips temporal/path keys | ✅ Yes | ❌ No |
| Sorts unordered list keys | ✅ Yes | ❌ No |
| Float handling | Silent pass-through | Raises `CanonicalizationError` |
| JS safe int check | No | Yes |

The ODR determinism gate and its pinned `EXPECTED_TORTURE_SHA256` hashes use `canon.py`. The LSI storage layer uses `canonical.py`. These produce structurally different digests for identical inputs. Any attempt to cross-validate stored LSI digests against the determinism gate's expected hashes will always fail, silently, because the hash values are technically well-formed — they just mean different things. This is a correctness time-bomb for any future integration between the kernel's determinism proof and the LSI's content-addressing.

**Fix:** Pick one canonicalization system for the whole kernel. Document which keys are non-semantic at the policy level, not inside the serializer.

---

### C-3. `run_round` in `odr/core.py` mutates state in-place while presenting a pure-functional API

**File:** `orket/kernel/v1/odr/core.py`
**Function:** `run_round(state: ReactorState, ...) -> ReactorState`

The function signature says "give me a state, I'll return a new state." `ReactorState` is a plain mutable dataclass. `run_round` mutates it directly (`state.history_v.append(...)`, `state.stable_count += 1`) and then returns the same object. Callers that snapshot the state before calling `run_round` to implement rollback, replay, or comparison will be surprised to find that their "old" snapshot has changed. This is especially dangerous given that the ODR's entire value proposition is deterministic, replayable execution.

**Fix:** Freeze `ReactorState` (`@dataclass(frozen=True)`) or explicitly return a new copy. If mutation is intentional for performance, document it and rename the function to reflect it (`advance_round`, `mutate_round`).

---

### C-4. `replay_spool` silently discards all information about which records failed and why

**File:** `orket/application/services/sandbox_lifecycle_event_service.py`
**Function:** `replay_spool`

```python
try:
    await self.repository.append_event(record)
    replayed += 1
except Exception:
    remaining.append(line)
```

A bare `except Exception` with no logging means that if the repository raises anything — connection error, schema validation failure, a bug in `append_event` — the record goes back into the spool with zero diagnostic information. If the same error recurs, the spool will grow indefinitely. There is no counter, no error category, no way to distinguish a transient network failure from a permanent schema rejection. A permanently broken record will block spool drain forever.

**Fix:** Log the exception at minimum. Distinguish transient from permanent failures. Cap retry attempts per record.

---

### C-5. `_rewrite_spool` has a TOCTOU window that can permanently lose events

**File:** `orket/application/services/sandbox_lifecycle_event_service.py`
**Functions:** `replay_spool`, `_rewrite_spool`

The flow is: read all lines → replay → compute `remaining` → rewrite spool file. If the process crashes between reading and rewriting, the successfully replayed events are gone from the spool but also already written to the repository, while the remaining events are also gone from the spool (since the file was partially truncated or never rewritten). Events are permanently lost.

**Fix:** Write to a `.tmp` file and atomically rename. Or use a proper WAL/offset pattern. At minimum, truncate the file only after confirming the write of remaining lines succeeded.

---

## 🟠 HIGH

---

### H-1. `SandboxLifecycleMutationService.transition_state` fetches the record twice — introducing a TOCTOU gap and an extra DB round-trip

**File:** `orket/application/services/sandbox_lifecycle_mutation_service.py`

The method fetches the record at the start (`current = await self._require_record(sandbox_id)`), applies the mutation through the repository, and then fetches it again to return the result (`record = await self._require_record(sandbox_id)`). This means there is a window between the mutation commit and the second fetch where another writer could modify the record, returning state that does not correspond to the mutation just applied. The return value from `apply_record_mutation` almost certainly contains the updated record already — it is being discarded.

**Fix:** Return the record from `apply_record_mutation` directly. Eliminate the second fetch.

---

### H-2. `execution_repository: Any | None = None` in `ToolApprovalControlPlaneOperatorService` is untyped and silently no-ops

**File:** `orket/application/services/tool_approval_control_plane_operator_service.py`

The `execution_repository` parameter is typed `Any | None` and defaults to `None`. There is no guard or assertion at construction time. Any code path that expects this repository to be present will silently skip operations rather than fail loudly. The `Any` type annotation defeats all static analysis. This is a silent correctness failure disguised as optional behavior.

**Fix:** Remove the parameter if it is genuinely unused. If it is used on code paths not visible in this file, type it with a Protocol and assert it is not `None` before use.

---

### H-3. `_select_case_id` falls back to the first known case instead of erroring on an empty or unknown case ID

**File:** `tools/torture_server.py`
**Function:** `_select_case_id`

```python
if not known_case_ids:
    return ""
return known_case_ids[0]
```

When a caller provides no `case_id`, the server silently picks the first available case. This turns misconfigured or incomplete requests into quietly-wrong behavior rather than a clear error. A client that forgets to set `case_id` will receive results for an arbitrary case with no indication that anything went wrong.

**Fix:** Return an error if `case_id` is absent and there is more than one case available. The single-case convenience path can stay, but it should be explicit.

---

### H-4. Hardcoded absolute Windows path in a Python CI script

**File:** `scripts/extensions/run_textmystery_policy_conformance.py`

```python
parser.add_argument("--textmystery-root", default="C:/Source/Orket-Extensions/TextMystery")
```

This is a hardcoded path to a specific developer's machine. On any CI runner, any other developer's machine, or any Linux/macOS environment, this default will silently resolve to a nonexistent path. The script will fail with `FileNotFoundError` rather than a meaningful configuration error.

**Fix:** Remove the default. Require the argument or read from an environment variable. Fail fast if neither is present.

---

### H-5. `_snapshot_version` swallows bad version data silently

**File:** `orket/application/services/state_audit_service.py` (and similar utility functions)

```python
def _snapshot_version(snapshot: dict[str, Any] | None) -> int | None:
    ...
    try:
        return int(snapshot.get("version"))
    except (TypeError, ValueError):
        return None
```

A malformed or missing version field silently returns `None`. Any comparison or fencing logic downstream that expects a real integer gets `None` without any log or warning. This silently degrades conflict detection.

---

## 🟡 MEDIUM

---

### M-1. Benchmark result artifacts with real SHA256 hashes are committed to the repository

Dozens of JSON files under `benchmarks/results/` contain run-specific SHA256 hashes, timing data, and output previews. These are runtime artifacts, not source code. Committing them bloats git history, causes spurious merge conflicts, and makes the "golden hash" check in `test_odr_determinism_gate.py` brittle — the pinned hash is valid only for the specific canonicalization implementation and input data used when the file was last generated.

**Fix:** Add `benchmarks/results/` to `.gitignore`. Regenerate locally or in CI. Store expected hashes in a dedicated, version-controlled policy file, not in run output.

---

### M-2. `backup_gitea.sh` uses `$?` after `tar` but does not use `set -e`

**File:** `scripts/gitea/backup_gitea.sh`

The script checks `$?` after the `tar` command, but there is no `set -e` at the top (only implicit in the `if [ $? -eq 0 ]` check). If any command before `tar` fails silently, the backup will run against a potentially corrupt or incomplete state. The `cd "$BACKUP_DIR"` before the cleanup loop is also dangerous — if `BACKUP_DIR` is empty, `cd` will succeed but leave the cleanup loop running in the wrong directory.

**Fix:** Add `set -euo pipefail`. Use absolute paths in cleanup loops.

---

### M-3. Mixed old-style and new-style type annotations across the codebase

Multiple files use `from typing import Dict, List` with `Dict[str, Any]` annotations while others use `dict[str, Any]`. Python 3.11 is the target; the old-style forms are unnecessary and create confusion about which style is authoritative. Examples: `tools/repro_odr_gate.py`, `scripts/gitea/check_gitea_state_hardening.py`.

**Fix:** Standardize on built-in generics (`dict`, `list`, `tuple`). Add a ruff rule to enforce this.

---

### M-4. `ORKET_ALLOW_INSECURE_NO_API_KEY` is a commented-out env var with no enforcement

**File:** `.env.example`

The comment says "not for CI/prod" but there is no mechanism to prevent it from being set in CI/prod. There is no CI check that asserts this variable is absent in deployment configs. Documentation-only security controls are not controls.

**Fix:** Add a CI step or startup assertion that exits non-zero if `ORKET_ALLOW_INSECURE_NO_API_KEY=true` is detected in non-local environments.

---

### M-5. `detect_changed_packages.py` is invoked with `--base-ref origin/main` which will fail on first-ever push to main

**File:** `.gitea/workflows/monorepo-packages-ci.yml`

On a fresh branch that has never merged to `main`, or in a shallow clone without `origin/main` fetched, `origin/main` may not exist. The `fetch-depth: 0` mitigates this in most cases but does not handle the first-ever push scenario cleanly.

**Fix:** Add a fallback that treats all packages as changed when `origin/main` does not exist.

---

### M-6. `_validated_or_default` builds an intermediate set inside the function on every call with an O(n) rebuild

**File:** `scripts/companion/run_companion_provider_runtime_matrix.py`

```python
allowed = {token for token in defaults}
```

This is a set comprehension over a tuple that is passed in every call. It should be a frozenset constant or computed once at module level. Minor, but this function is called in a hot matrix-expansion loop.

---

## 🔵 LOW

---

### L-1. `from __future__ import annotations` is used inconsistently

Some files have it, many do not. This has real behavior implications for runtime annotation evaluation (particularly with Pydantic models and `get_type_hints()`). Either commit to it uniformly or commit to not using it.

---

### L-2. `ci_failure_policy.json` has `stale_threshold_runs: 3` with no documentation of what "stale" means

**File:** `.ci/ci_failure_policy.json`

The field exists, but there is no documentation in the file, the schema, or the consuming script about what "stale" means operationally — how many consecutive failures, over what time window, before what action is taken.

---

### L-3. `packages.template.json` exists alongside `packages.json` with no explanation

**File:** `.ci/packages.template.json`

The template uses `packages/core` and `packages/sdk` paths that do not match the actual repo layout (`orket/`, `orket_extension_sdk/`). It is unclear if this is dead scaffolding or an intended future layout. It creates confusion about the canonical CI config.

**Fix:** Delete it or add a comment explaining its purpose.

---

### L-4. `execution_repository` duplication — same pattern repeated in multiple operator services

Multiple operator service classes accept `execution_repository: Any | None = None`. This is a copy-paste pattern that should be a shared base class or injection container entry, not a repeated loose parameter.

---

### L-5. Test files use `type("Org", (), {...})` anonymous class factories for fakes

**Files:** `tests/application/test_runtime_verifier.py`

```python
org = type("Org", (), {"process_rules": {"runtime_verifier_commands": [...]}})
```

This is harder to read than a named fixture class, harder to refactor, and bypasses type checking entirely. These should be proper `@dataclass` or `Protocol`-implementing stub classes.

---

## Summary Table

| ID | Severity | File / Area | Issue |
|---|---|---|---|
| C-1 | 🔴 Critical | `kernel/v1/state/lsi.py` | Monkey-patched method; class body always crashes |
| C-2 | 🔴 Critical | `kernel/v1/canon.py` + `canonical.py` | Two incompatible canonicalization systems |
| C-3 | 🔴 Critical | `kernel/v1/odr/core.py` | Functional API mutates state in-place |
| C-4 | 🔴 Critical | `services/sandbox_lifecycle_event_service.py` | Spool replay swallows all exceptions silently |
| C-5 | 🔴 Critical | `services/sandbox_lifecycle_event_service.py` | TOCTOU data loss in spool rewrite |
| H-1 | 🟠 High | `services/sandbox_lifecycle_mutation_service.py` | Double-fetch TOCTOU + extra DB round-trip |
| H-2 | 🟠 High | `services/tool_approval_control_plane_operator_service.py` | `Any`-typed optional repository silently no-ops |
| H-3 | 🟠 High | `tools/torture_server.py` | Silent wrong-case fallback |
| H-4 | 🟠 High | `scripts/extensions/run_textmystery_policy_conformance.py` | Hardcoded Windows developer path in CI script |
| H-5 | 🟠 High | `services/state_audit_service.py` | Silent version coercion hides data quality issues |
| M-1 | 🟡 Medium | `benchmarks/results/` | Runtime artifacts committed to git |
| M-2 | 🟡 Medium | `scripts/gitea/backup_gitea.sh` | Missing `set -e`, unsafe `cd` in cleanup |
| M-3 | 🟡 Medium | Multiple files | Mixed old/new-style type annotations |
| M-4 | 🟡 Medium | `.env.example` | No enforcement for insecure key override |
| M-5 | 🟡 Medium | `monorepo-packages-ci.yml` | `origin/main` absent on first push |
| M-6 | 🟡 Medium | `run_companion_provider_runtime_matrix.py` | Repeated set rebuild in hot loop |
| L-1 | 🔵 Low | Multiple files | Inconsistent `from __future__ import annotations` |
| L-2 | 🔵 Low | `.ci/ci_failure_policy.json` | Undocumented `stale_threshold_runs` semantics |
| L-3 | 🔵 Low | `.ci/packages.template.json` | Stale template with wrong paths |
| L-4 | 🔵 Low | Multiple operator services | Copy-paste `execution_repository: Any \| None` |
| L-5 | 🔵 Low | Test files | Anonymous class factories for fakes |
