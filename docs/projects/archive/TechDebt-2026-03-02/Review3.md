# Orket Code Review #3 -- Claude Opus 4.6

**Date**: 2026-03-02
**Reviewer**: Claude Opus 4.6 (6-agent deep review)
**Codebase Version**: v0.4.5+ (commit af3db7c)
**Scope**: Full codebase -- 285 Python files, ~42K lines, 1295 tests

---

## Verdict

| Dimension | Score | Notes |
|-----------|-------|-------|
| Conceptual Architecture | 8/10 | Sound. FSM, domain models, decision nodes, extension isolation -- all good ideas. |
| Implementation Quality | 5/10 | Pervasive async contamination, DRY violations, god classes, incomplete migrations. |
| Security | 4/10 | Path traversal mostly fixed, but subprocess RCE, credential handling, and SSRF remain. |
| Test Coverage | 7/10 | 1295 tests, 3 failures. Good coverage of happy paths. Weak on edge cases and security. |
| Dead Code / YAGNI | 4/10 | Compatibility shims everywhere, stub methods, duplicate definitions across packages. |
| Production Readiness | 3/10 | Cannot ship. Blocking I/O in async, god-class API (2020 lines), credential leaks in logs. |

**Overall: 5/10** -- Same as Review #2. Architecture remains strong. Implementation debt accumulating faster than it's being paid down.

---

## CRITICAL: Fix This Week or Don't Deploy

### C1. Duplicate `ModelTimeoutError` Definition

**orket/exceptions.py:25** defines `ModelTimeoutError(ModelProviderError)`.
**orket/application/workflows/turn_executor.py** redefines `ModelTimeoutError(Exception)`.

Different inheritance chains. Code that catches one misses the other. This is a **silent error handling failure**. Any timeout during a turn may not propagate correctly depending on which import is used.

**Fix**: Delete the turn_executor.py version. Import from exceptions.py.

### C2. 20 Blocking `subprocess.run()` Calls in Async Code

Found in:
- `orket/discovery.py:13` -- `subprocess.run(["ollama", "list"])`
- `orket/orchestration/models.py:272` -- same call, duplicated
- `orket/adapters/vcs/gitea_artifact_exporter.py:250`
- `orket/application/review/run_service.py:45`
- `orket/application/review/snapshot_loader.py:19`
- `orket/application/services/runtime_verifier.py:250`
- `orket/capabilities/tts_piper.py:69`
- `orket/extensions/manager.py:201, 210`
- `orket/hardware.py:28, 85`
- `orket/interfaces/api_generation.py:38, 43`
- `orket/interfaces/refactor_transaction.py:33, 38`
- `orket/interfaces/scaffold_init.py:57`
- `orket/reforger/cli.py:282`

Each one blocks the entire asyncio event loop. If ollama takes 2 seconds, all websockets, webhooks, and API requests stall.

**Fix**: Replace with `asyncio.create_subprocess_exec()` or wrap in `await asyncio.to_thread(subprocess.run, ...)`.

### C3. 114 Blocking `.read_text()` / `.write_text()` Calls

The `AsyncFileTools` class exists but most of the codebase still uses synchronous `Path.read_text()` and `Path.write_text()`. Found 114 instances across orket/ package. These block the event loop on every file read/write.

**Fix**: Migrate to `AsyncFileTools` or `await asyncio.to_thread()` wrappers. Priority targets:
- `orket/application/services/memory_commit_buffer.py:171, 201`
- `orket/application/workflows/turn_artifact_writer.py:199, 284, 307`
- `orket/domain/reconciler.py:35, 54, 76, 107, 114, 135`
- `orket/runtime/config_loader.py` (all asset loading)

### C4. `api.py` is a 2020-Line God File with 93 Functions

`orket/interfaces/api.py`: 93 functions, 60 async endpoints, mixed concerns:
- System endpoints (health, metrics, calendar, explorer, file read/write)
- Session management (start, turn, finalize, cancel)
- Card CRUD (create, list, archive, status update)
- Kernel gateway (lifecycle, compare, replay)
- Settings management (get, update, reset)
- Runtime policy (options, current, update)
- Streaming/WebSocket
- Team topology discovery

This is unmaintainable. Every change risks regressions across unrelated endpoints.

**Fix**: Split into routers:
- `routers/system.py` -- health, metrics, calendar, explorer, file I/O
- `routers/cards.py` -- CRUD, archive, status
- `routers/sessions.py` -- start, turn, finalize, cancel
- `routers/kernel.py` -- lifecycle, compare, replay
- `routers/settings.py` -- get, update, reset
- `routers/streaming.py` -- WebSocket, event bus

### C5. Credential Exposure in Git Push URLs

`orket/adapters/vcs/gitea_artifact_exporter.py:245-247`:
```python
return f"{scheme}://{user}:{pw}@{host}/{owner}/{repo}.git"
```

Password embedded in URL string. This URL gets:
- Logged in error messages
- Stored in .git/config
- Exposed in stack traces
- Captured by process inspection tools

**Fix**: Use Git credential helpers or SSH keys. Never embed passwords in URLs.

### C6. `lru_cache` on Sync-Async Bridge

`orket/runtime/config_loader.py:115-117`:
```python
@lru_cache(maxsize=256)
def _load_asset_raw(self, category, name, dept):
    return self._run_async(self._load_asset_raw_async(category, name, dept))
```

`lru_cache` on a bound method doesn't work correctly -- `self` is part of the cache key, and the async bridge creates new thread pools per cache miss. Stale results when configs change. Memory leak from `self` reference retention.

**Fix**: Cache at the async layer, not the sync bridge. Or remove caching entirely.

---

## HIGH: Fix This Sprint

### H1. Race Condition in FileSystemTools Path Locks

`orket/adapters/tools/families/filesystem.py:11`:
```python
_path_locks: dict[str, asyncio.Lock] = {}  # Class-level mutable!
```

Class-level mutable dict shared across ALL instances. The `_get_path_lock()` check-then-create is not atomic -- two coroutines can create two different locks for the same path.

**Fix**: Use a module-level lock to protect lock creation, or use `asyncio.Lock` in `__init__` per instance.

### H2. OrchestrationEngine is a God Class (17 Public Methods)

`orket/orchestration/engine.py`: Mixes:
1. Execution (run_card, run_epic, run_rock, run_issue)
2. Sandboxing (get_sandboxes, stop_sandbox)
3. Session lifecycle (halt_session)
4. Card archival (archive_card, archive_cards, archive_build, archive_related_cards)
5. Kernel gateway proxying (kernel_* methods)
6. Observability (replay_turn)

**Fix**: Extract into focused services: `CardExecutor`, `SandboxManager`, `SessionController`, `CardArchiver`.

### H3. Subprocess RCE in Verification

`orket/domain/verification_runner.py:47-49`:
```python
spec = importlib.util.spec_from_file_location("verification_fixture_subprocess", fixture_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
```

Executes arbitrary Python with full interpreter privileges. The "sandbox" is:
- `socket.socket` monkey-patched (bypassed by spawning subprocess)
- `resource.setrlimit` (unavailable on Windows, bypassed by fork)
- No filesystem isolation
- No process isolation

The directory containment check (fixture must be in verification/) is the real security boundary, and it's implemented correctly with `relative_to()`. But if an attacker can write to the verification/ directory, it's game over.

**Fix**: Run fixtures in a Docker container with `--network none --read-only --tmpfs /tmp:size=10m --memory=256m --cpus=0.5`.

### H4. SSRF in Gitea Vendor

`orket/vendors/gitea.py:58`: User-controlled `epic_id` passed as label parameter to Gitea API. While httpx parameterizes the request, the Gitea API may interpret label values differently.

**Fix**: Validate `epic_id` against a whitelist of known milestone IDs. Use `int()` conversion with error handling.

### H5. Duplicate State Transition Definitions

Three independent transition matrices that can silently diverge:
- `orket/core/domain/state_machine.py:16` (primary, comprehensive)
- `orket/core/domain/workflow_profiles.py:93` (secondary, subset)
- `orket/interfaces/prompts_cli.py:16` (tertiary, outdated)

**Fix**: Single source of truth in state_machine.py. Other files import and derive from it.

### H6. `_WebhookHandlerProxy.__getattr__` and Similar Magic

Found in 4+ places: `_WebhookHandlerProxy`, `_ApiRuntimeNodeProxy`, `_EngineProxy`, `AsyncCardRepository.__getattr__`, `GiteaWebhookHandler.__getattr__`.

`__getattr__` delegation:
- Invisible to IDEs and type checkers
- Impossible to trace call chains
- Breaks autocomplete
- Makes grep/search unreliable

**Fix**: Explicitly define forwarding properties or use composition with explicit method wrapping.

### H7. Unvalidated Service Parameter in Sandbox Logs

`orket/services/sandbox_orchestrator.py:248-249`:
```python
if service:
    cmd.append(service)
```

`service` from user input appended to docker-compose command without validation.

**Fix**: Whitelist: `if service not in {"api", "frontend", "database"}: raise ValueError()`

---

## MEDIUM: Fix This Month

### M1. Compatibility Shim Proliferation

Files that exist solely to re-export from new locations:
- `orket/domain/state_machine.py` -> `orket.core.domain.state_machine`
- `orket/domain/records.py` -> `orket.core.domain.records`
- `orket/domain/critical_path.py` -> `orket.core.critical_path`
- `orket/services/tool_gate.py` -> `orket.core.policies.tool_gate`
- `orket/services/webhook_db.py` -> `orket.adapters.vcs.webhook_db`

These add import confusion and maintenance burden. If there are no external consumers, delete the shims and update imports.

**Fix**: `grep -r "from orket.domain.state_machine" orket/` -- if all imports use the new path, delete the shim.

### M2. `schema.py` is a God File (270+ Lines, 14 Models)

EnvironmentConfig, SkillConfig, DialectConfig, BaseCardConfig, IssueConfig, EpicConfig, RockConfig, RoleConfig, TeamConfig, DepartmentConfig, BrandingConfig, ArchitecturePrescription, ContactInfo, OrganizationConfig -- all in one file.

**Fix**: Split into `schema/cards.py`, `schema/organization.py`, `schema/environment.py`.

### M3. Pydantic `extra` Config Inconsistency

- `EnvironmentConfig`: `extra='allow'` (silently accepts unknown fields)
- `BaseCardConfig`: `extra='ignore'` (silently drops unknown fields)
- Most other models: no explicit `extra` setting (default `extra='ignore'`)

Both `allow` and `ignore` mask configuration typos.

**Fix**: Use `extra='forbid'` everywhere. Forces validation errors on typos.

### M4. Circular Import Avoidance via Late Imports

`orket/core/policies/tool_gate.py:76`:
```python
def _validate_file_write(self, ...):
    from orket.services.idesign_validator import iDesignValidator
    from orket.services.ast_validator import ASTValidator
    from orket.domain.execution import ExecutionTurn, ToolCall
```

Late imports inside methods indicate circular dependency. This defeats static analysis and adds per-call import overhead.

**Fix**: Inject validators as constructor dependencies.

### M5. Over-Engineered `build_verification_scope()` -- 15 Parameters

`orket/core/domain/verification_scope.py`: A function with 15 keyword-only parameters to build a single dict.

**Fix**: Replace with a `VerificationScope` Pydantic model. Validation and defaults come free.

### M6. CriticalPathEngine Naming and Bug

`orket/core/critical_path.py:44-72`:
1. **Misleading name**: Uses SUM not MAX. This calculates "impact weight", not "critical path".
2. **Shared visited set**: Bug when diamond dependencies exist. Node counted only once globally, not per-branch.
3. **Comments contradict code**: Line 68 says "max path of children", code does `weight += 1 + recursive`.

**Fix**: Rename to `ImpactWeightCalculator`. Fix visited-set sharing. Add tests for diamond graphs.

### M7. Agent.__init__ Does Blocking I/O

`orket/agents/agent.py:24-66`: Constructor calls `_load_configs()` which does synchronous file reads. In async context, this blocks the event loop.

**Fix**: Make config loading async with a separate `await agent.initialize()` method.

### M8. Stub Methods in Production Code

- `orket/adapters/tools/families/vision.py:16-20` -- `image_analyze()` always returns error
- `orket/vendors/local.py:66` -- `add_card()` raises `NotImplementedError`
- `orket/orchestration/governance_auditor.py` -- audit results logged but never enforced

**Fix**: Remove stubs or implement. Don't ship `NotImplementedError` to production.

### M9. `_resolve_async_method` and `_resolve_sync_method` are Identical

`orket/interfaces/api.py:78-97`: Two functions with identical logic, different names. Pure DRY violation.

```python
def _resolve_async_method(target, invocation, error_prefix):
    method_name = invocation["method_name"]
    method = getattr(target, method_name, None)
    ...

def _resolve_sync_method(target, invocation, error_prefix):
    method_name = invocation["method_name"]
    method = getattr(target, method_name, None)
    ...
```

**Fix**: One function: `_resolve_method(target, invocation, error_prefix)`.

### M10. Truncated UUID as Card ID

`orket/schema.py:51`:
```python
id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
```

8 hex chars = 2^32 possible IDs. Collision probability crosses 50% at ~77K cards (birthday paradox). For a project management tool that generates cards per build, this is reachable.

**Fix**: Use full UUID or `secrets.token_urlsafe(12)` for 96-bit IDs.

---

## LOW: Nice to Have

### L1. Missing `Optional` Import in `session.py`

Line 25 uses `Optional[str]` but `Optional` is not imported. May work at runtime due to `__future__` annotations or may crash on instantiation.

### L2. EventStream Class (events.py) is Just a List Wrapper

`EventStream` wraps `list` with `push()`, `all()`, `last()`. No persistence, no pub-sub, no filtering. YAGNI.

**Fix**: Delete or replace with `asyncio.Queue` if actual event streaming is needed.

### L3. `print()` Instead of `logging` in Mesh Orchestration

`mesh_orchestration/worker.py` uses `print()` for error output. Not captured by log aggregation.

### L4. Duplicate `ollama list` Call

`orket/discovery.py:13` and `orket/orchestration/models.py:272` both call `subprocess.run(["ollama", "list"])` with identical parsing logic.

**Fix**: Consolidate into one function in `discovery.py` or `hardware.py`.

### L5. `_build_stream_bus_from_env()` Duplicates Inline Construction

`orket/interfaces/api.py:486-493` defines `_build_stream_bus_from_env()` which is identical to the inline construction on lines 471-477. One is never called.

### L6. Test Quality: Missing Assertion Messages

Many tests use bare `assert x == y` without failure context. Add messages: `assert count == 0, f"Expected 0 cycles, got {count}"`.

### L7. Demo Data in Production Code

`mesh_orchestration/coordinator.py:47-52` has hardcoded "demo-card-1" in `InMemoryCardStore`.

---

## Security Findings Summary

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| S1 | CRITICAL | Subprocess RCE in verification (exec_module) | domain/verification_runner.py:47 |
| S2 | CRITICAL | Credentials embedded in git push URLs | adapters/vcs/gitea_artifact_exporter.py:245 |
| S3 | HIGH | Unvalidated service param in docker-compose cmd | services/sandbox_orchestrator.py:248 |
| S4 | HIGH | SSRF via user-controlled epic_id in Gitea API | vendors/gitea.py:58 |
| S5 | HIGH | Subprocess verification sandbox bypassed on Windows | domain/verification_runner.py:26 |
| S6 | MEDIUM | `__getattr__` proxies hide security-critical call chains | webhook_server.py:53, api.py:74 |
| S7 | MEDIUM | Race condition in path lock creation | adapters/tools/families/filesystem.py:20 |
| S8 | LOW | Symlink attacks not mitigated in path validation | core/policies/tool_gate.py:72 |
| S9 | INFO | .env has real credentials (correctly gitignored, not tracked) | .env |

---

## Architecture: What's Good

These modules are well-designed and should be left alone:

1. **StateMachine** (`core/domain/state_machine.py`) -- Correct FSM with role-based guards. Clean, declarative, well-tested.

2. **ToolGate** (`core/policies/tool_gate.py`) -- Solid permission enforcement. Uses `is_relative_to()` for path checks. Well-tested (20/20).

3. **AsyncCardRepository** (`adapters/storage/async_card_repository.py`) -- Clean async interface, proper aiosqlite usage, good separation of ops.

4. **SlidingWindowRateLimiter** (`webhook_server.py:102-120`) -- Correct sliding window implementation with asyncio.Lock.

5. **Extension Import Isolation** (`extensions/workload_loader.py:107-145`) -- AST-based import validation prevents extensions from accessing core internals. Smart design.

6. **Webhook HMAC Validation** (`webhook_server.py:131-157`) -- Uses `hmac.compare_digest()` for constant-time comparison. Correct.

7. **GlobalState with Locks** (`state.py`) -- Previous review flagged missing locks. Now fixed with proper `asyncio.Lock` on all mutable state. Good.

8. **Decision Nodes Pattern** -- Delegates policy decisions to pluggable nodes. Clean extension point.

---

## Test Health

```
1295 tests collected
1283 passed, 3 failed, 9 skipped (76.52s)
```

**Failing tests**:
- `test_default_api_runtime_strategy_parity` -- Decision node contract drift
- `test_dependency_policy_maps_all_top_level_namespaces` -- New namespace not in policy
- `test_dependency_direction_and_snapshot_use_canonical_policy` -- Same

**Coverage gaps** (no tests found for):
- `orket/core/critical_path.py` -- Diamond dependency bug untested
- `orket/domain/bug_fix_phase.py` -- No tests at all
- `orket/domain/failure_reporter.py` -- No tests at all
- `orket/domain/reconciler.py` -- No tests at all
- `orket/interfaces/api.py` -- Only 1 lifecycle test for 93 functions
- `orket/extensions/workload_loader.py` -- Import isolation not integration-tested
- Security: No tests for symlink attacks, path traversal via race conditions

---

## Metrics Snapshot

| Metric | Value |
|--------|-------|
| Python files | 285 |
| Lines of code (orket/) | 41,842 |
| Test files | 306 |
| Tests collected | 1,295 |
| Tests passing | 1,283 (99.1%) |
| Tests failing | 3 |
| Tests skipped | 9 |
| `except Exception` catches | 27 across codebase |
| Blocking `subprocess.run()` in orket/ | 20 |
| Blocking `.read_text()`/`.write_text()` in orket/ | 114 |
| Compatibility shims | 5+ re-export files |
| `__getattr__` proxy classes | 5+ |
| Lines in api.py | 2,020 |
| Functions in api.py | 93 |

---

## Priority Action Plan

### This Week (Blocking Deployment)
1. Delete duplicate `ModelTimeoutError` in turn_executor.py
2. Convert top 5 blocking subprocess calls to async (discovery.py, models.py, hardware.py)
3. Remove credential embedding in git push URLs
4. Validate `service` parameter in sandbox_orchestrator.py
5. Fix the 3 failing tests

### This Sprint (High Impact)
6. Split api.py into 6 router modules
7. Split OrchestrationEngine into focused services
8. Fix FileSystemTools race condition in path locks
9. Replace `lru_cache` on config_loader sync bridge
10. Remove or implement stub methods (vision, local vendor)

### Next Sprint (Structural)
11. Migrate top 20 `.read_text()`/`.write_text()` calls to async
12. Delete compatibility shims (verify no external consumers)
13. Split schema.py into 3 files
14. Fix CriticalPathEngine naming and diamond bug
15. Add tests for: critical_path, bug_fix_phase, failure_reporter, reconciler

### Ongoing
16. Set Pydantic `extra='forbid'` across all models
17. Replace `__getattr__` proxies with explicit forwarding
18. Narrow remaining `except Exception` catches
19. Run `mypy --strict` in CI
20. Harden verification subprocess with Docker sandbox

---

## Comparison with Previous Reviews

| Finding | Review #1 (Feb 9) | Review #2 (Feb 10) | Review #3 (Mar 2) |
|---------|-------------------|--------------------|--------------------|
| Implementation Score | 3/10 | 5/10 | 5/10 |
| Tests passing | 52/56 | 67 | 1283/1295 |
| `datetime.now()` without UTC | 16 instances | 16 instances | 0 (FIXED) |
| Hardcoded sandbox passwords | Yes | Yes | No (FIXED) |
| GITEA_ADMIN_PASSWORD enforcement | Missing | Missing | RuntimeError (FIXED) |
| GlobalState race conditions | No locks | No locks | Locks added (FIXED) |
| Dead code (filesystem.py, conductor.py) | Present | Present | Cannot confirm deletion |
| Blocking subprocess calls | Not counted | Not counted | 20 in orket/ |
| Blocking file I/O calls | Not counted | Not counted | 114 in orket/ |
| api.py size | Not measured | Not measured | 2020 lines, 93 functions |
| Test count | 56 | 67 | 1295 |

**Progress**: UTC datetimes fixed. Sandbox passwords fixed. GlobalState locks added. Test suite grew from 67 to 1295. But new code introduces new debt at the same rate the old debt is paid. The implementation score hasn't moved.

---

## Bottom Line

The codebase has grown 5x since the last review (67 tests to 1295, massive new subsystems). The architecture remains sound -- decision nodes, extension isolation, and the FSM are genuinely well-designed. But the implementation continues to accumulate blocking I/O, god classes, and security shortcuts faster than they're being resolved.

The most urgent issue is not any single bug. It's the **systemic pattern of sync-in-async contamination** (134 blocking calls in an async codebase). Until this is addressed, the entire event loop is a house of cards -- any slow disk read or subprocess stalls everything.

Ship nothing until C1-C6 are resolved. The 3 failing tests indicate active contract drift that needs immediate attention.
