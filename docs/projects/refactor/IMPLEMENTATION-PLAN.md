# Refactor Implementation Plan: SOLID Cleanup and Structural Decomposition

Date: 2026-02-28
Execution mode: incremental, low blast radius, one phase at a time

## Phase 1: Quick Wins and Test Fixes (Week 1)

Low-risk changes that fix failing tests and establish consistency.

### 1.1 Register new modules in dependency direction policy
- File: `tests/platform/test_dependency_policy_contract.py`
- Action: Add `orket.reforger`, `orket.streaming`, `orket.workloads`, `orket.extensions`, `orket.driver_support_*` to the policy classification map.
- Fixes: 2 test failures.

### 1.2 Resolve reforger print policy violation
- File: `orket/reforger/cli.py`
- Action: Replace `print()` calls with `logging.getLogger("orket.reforger").info()` or whitelist in print policy test.
- Fixes: 1 test failure.

### 1.3 Update kernel v1 test contracts
- Files: `tests/kernel/v1/test_capability_decision_record_schema.py`, `test_registry.py`, `test_replay_comparator.py`, `test_replay_contract_schemas.py`, `test_validator_schema_contract.py`
- Action: Update test fixture schemas to match current kernel v1 code. Do not change production code; tests must reflect reality.
- Fixes: 19 test failures.

### 1.4 Type hint standardization
- Files: All files in `orket/` using `Dict[`, `List[`, `Optional[`, `Tuple[` from typing.
- Action: Replace with lowercase `dict`, `list`, `tuple`, `X | None`. Add missing return type annotations to public methods in `orket/logging.py`, `orket/adapters/storage/async_file_tools.py`, `orket/streaming/manager.py`.
- No behavior change.

### 1.5 Dead code removal
- Delete `orket/services/gitea_webhook_handler.py` (compatibility shim) if no imports reference it.
- Delete `orket/adapters/storage/sqlite_repositories.py` (sync legacy) if fully replaced by async_repositories.py.
- Verify with: `grep -rn "from orket.services.gitea_webhook_handler" orket/` and `grep -rn "sqlite_repositories" orket/`

### Phase 1 validation
```
python -m pytest tests/platform/ -v
python -m pytest tests/kernel/v1/ -v
python -m pytest tests/ -q --tb=line
```

---

## Phase 2: Data Clumps and Value Objects (Week 1-2)

Extract dataclasses to eliminate parameter groups traveling together.

### 2.1 Create RunContext dataclass
- New file: `orket/runtime/run_context.py`
- Fields: `run_id: str`, `active_build: str`, `workspace: Path`, `department: str`, `config_root: Path`, `db_path: Path`
- Update call sites in `orket/runtime/execution_pipeline.py` to pass `RunContext` instead of individual parameters.

### 2.2 Create PullRequestRef dataclass
- New file: `orket/adapters/vcs/models.py` (or add to existing `orket/adapters/storage/gitea_state_models.py`)
- Fields: `owner: str`, `repo_name: str`, `pr_number: int`, `full_name: str` (computed property: `f"{owner}/{repo_name}"`)
- Update call sites in `orket/adapters/vcs/gitea_webhook_handler.py`.

### 2.3 Add Pydantic models for webhook payloads
- File: `orket/adapters/vcs/models.py`
- Models: `WebhookPayload`, `PullRequestPayload`, `ReviewPayload`
- Validate incoming webhook data before field access in `GiteaWebhookHandler.handle_webhook`.

### Phase 2 validation
```
python -m pytest tests/adapters/ -v
python -m pytest tests/ -q --tb=line
```

---

## Phase 3: Dependency Injection Fixes (Week 2)

Replace internal instantiation with constructor injection.

### 3.1 SandboxOrchestrator
- File: `orket/services/sandbox_orchestrator.py`
- Change: Accept `AsyncFileTools` as constructor parameter instead of creating at line 54-55.
- Update all instantiation sites to pass the dependency.

### 3.2 OrketDriver
- File: `orket/driver.py`
- Change: Accept `LocalModelProvider`, `AsyncFileTools`, `ReforgerTools` as constructor parameters.
- Update factory/entry point to wire dependencies.

### 3.3 API runtime node
- File: `orket/interfaces/api.py`
- Change: Replace module-level `api_runtime_node = DecisionNodeRegistry().resolve_api_runtime()` with lazy initialization via `functools.lru_cache` or a provider function.

### Phase 3 validation
```
python -m pytest tests/interfaces/ tests/adapters/ -v
python -m pytest tests/ -q --tb=line
```

---

## Phase 4: God Class Decomposition (Week 2-3)

The highest-risk phase. Each decomposition is an independent PR slice.

### 4.1 ExecutionPipeline decomposition
- Source: `orket/runtime/execution_pipeline.py` (~660 lines)
- Target structure:
  - `orket/runtime/execution_pipeline.py` - Thin coordinator (<200 lines). Wires dependencies, delegates to specialists.
  - `orket/runtime/epic_orchestrator.py` - Epic execution logic extracted from `run_epic`. Receives `RunContext`.
  - `orket/runtime/artifact_manager.py` - Artifact export, transcript writing, run ledger management.
  - `orket/runtime/session_manager.py` - Session state, snapshot management.
- Constructor takes injected dependencies (repositories, orchestrator, artifact manager, session manager).
- Each extracted class gets dedicated unit tests.

### 4.2 GiteaWebhookHandler decomposition
- Source: `orket/adapters/vcs/gitea_webhook_handler.py` (~413 lines)
- Target structure:
  - `orket/adapters/vcs/gitea_webhook_handler.py` - Dispatcher (<100 lines). Routes events to handlers.
  - `orket/adapters/vcs/handlers/pr_review_handler.py` - PR review, cycle tracking, escalation logic.
  - `orket/adapters/vcs/handlers/pr_merge_handler.py` - Merge and rejection logic.
  - `orket/adapters/vcs/handlers/sandbox_handler.py` - Sandbox deployment via PR events.
- Dispatcher uses a handler registry: `dict[str, WebhookEventHandler]`.
- Each handler receives `PullRequestRef` and validated `WebhookPayload`.

### 4.3 VerificationEngine extraction
- Source: `orket/domain/verification.py` (~331 lines, includes 87-line embedded runner)
- Target structure:
  - `orket/domain/verification.py` - Orchestration only (<150 lines). Loads fixtures, delegates execution, collects results.
  - `orket/domain/subprocess_runner.py` - Subprocess lifecycle, network isolation, resource limits, output parsing.
- `VerificationEngine.verify()` calls `SubprocessVerificationRunner.execute()`.

### Phase 4 validation
```
python -m pytest tests/ -v --tb=short
grep -rn "except Exception" orket/
```

---

## Phase 5: Async Cleanup (Week 3)

### 5.1 AsyncFileTools sync/async bridge
- File: `orket/adapters/storage/async_file_tools.py`
- Change: Remove `_run_async()` bridging pattern. All callers must use `await`. If sync callers exist, create a separate `SyncFileTools` wrapper that uses `asyncio.run()` at the boundary, not inside the async class.

### 5.2 Migrate gitea_artifact_exporter to httpx
- File: `orket/adapters/vcs/gitea_artifact_exporter.py`
- Change: Replace `urllib.request` imports with `httpx.AsyncClient`. Make export methods async.
- Update callers to await.

### Phase 5 validation
```
python -m pytest tests/ -v --tb=short
grep -rn "import requests\|from urllib" orket/
```

---

## Phase 6: Test Hardening (Week 3-4)

### 6.1 GlobalState test isolation
- File: `orket/state.py`
- Add: `reset()` classmethod or context manager that clears all mutable state for test isolation.
- Add: Fixture in `conftest.py` that resets GlobalState between tests.

### 6.2 Logging subscriber isolation
- File: `orket/logging.py`
- Add: `clear_subscribers()` function.
- Add: Fixture in `conftest.py` that clears subscribers between tests.

### 6.3 Unit tests for decomposed classes
- Add tests for: `EpicOrchestrator`, `ArtifactManager`, `SessionManager`, `PRReviewHandler`, `PRMergeHandler`, `SandboxHandler`, `SubprocessVerificationRunner`.
- Each class must have at least 3 tests covering happy path, error path, and edge case.

### Phase 6 validation
```
python -m pytest tests/ -v --tb=short
```

---

## Work Slicing Guidance

Each phase is an independent PR slice. Within Phase 4, each god class decomposition (4.1, 4.2, 4.3) is its own PR.

| PR | Phase | Risk | Estimated scope |
|----|-------|------|-----------------|
| A  | 1.1-1.3 | Low | Test fixes only, no production changes |
| B  | 1.4-1.5 | Low | Cosmetic: type hints + dead code |
| C  | 2.1-2.3 | Low | New dataclasses + call site updates |
| D  | 3.1-3.3 | Medium | Constructor signature changes |
| E  | 4.1 | High | ExecutionPipeline decomposition |
| F  | 4.2 | High | GiteaWebhookHandler decomposition |
| G  | 4.3 | Medium | VerificationEngine extraction |
| H  | 5.1-5.2 | Medium | Async interface changes |
| I  | 6.1-6.3 | Low | Test infrastructure + new tests |

## Rollback Strategy

1. Each PR slice is independently revertable.
2. Phase 4 decompositions preserve the original class as a facade during transition. The facade delegates to new classes. Once tests are green, the facade internals are removed.
3. If any decomposition destabilizes runtime, revert that PR only. Other phases remain independent.
4. Phase 1-3 can ship without Phase 4-6. Phase 4-6 can ship incrementally.

## Success Metrics

1. Test suite: 1180+ passing (up from 1148).
2. No class over 200 lines in modified files.
3. No method exceeding 3 nesting levels in modified files.
4. No constructor exceeding 5 parameters in modified files.
5. `grep -rn "except Exception" orket/` returns at most 1 result (project_dumper_small.py).
6. `grep -rn "Dict\[" orket/` returns 0 results.
