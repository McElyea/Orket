# Orket Master Roadmap v2: The Honest Path

**Author**: Claude Opus 4.6 (consolidated from 4 agent reviews + direct code audit)
**Date**: 2026-02-10
**Version**: v0.4.5 (actual) -- NOT v1.0

This document replaces the previous MASTER_ROADMAP.md which falsely claimed v1.0 milestone completion. Every item below is verified against the actual codebase as of this date.

---

## Reality Check: Where We Actually Are

### What The Old Roadmap Claimed

> "v1.0 MILESTONE REACHED. All roadmap items COMPLETE. 150+ tests. Production-ready."

### What The Code Says

| Dimension | Claimed | Actual | Evidence |
|:---|:---|:---|:---|
| Tests | 150+ | 67 (16 files) | `pytest tests/ -q` returns 67 passed |
| Bare except: | Eliminated | 0 bare, 44 broad `except Exception` | grep confirms bare gone; broad remains |
| datetime.now(UTC) | Complete | 16 occurrences of `datetime.now()` remain | sqlite_repositories.py, api.py, persistence.py, tools.py, utils.py, notes.py |
| Dead code deleted | Complete | filesystem.py, conductor.py, persistence.py still exist | All flagged for deletion, all still present |
| Async-pure | Complete | SQLiteSessionRepository and SQLiteSnapshotRepository are sync sqlite3 | Called from async ExecutionPipeline |
| Orphaned code | None | orket.py:305-306 references undefined variables | `iteration_count` and `max_iterations` never defined in scope |
| API tests | Done | 0 tests for 20+ endpoints | api.py has zero test coverage |

**Honest Score: v0.4.5** -- The architecture is sound. The reconstruction landed about 60%. The remaining 40% is unglamorous cleanup that keeps getting deprioritized for new features.

---

## Completed Work (Verified)

These items are genuinely done and working:

- [x] **TurnExecutor**: Clean async single-turn executor (384 lines, well-designed)
- [x] **Orchestrator**: Extracted from god method, parallel DAG execution with semaphore
- [x] **AsyncCardRepository**: aiosqlite-based, proper locking, IssueRecord types
- [x] **RCE Mitigation**: Verification directory separation, `relative_to()` path check
- [x] **Path Traversal Fix (tools.py)**: `Path.is_relative_to()` used correctly
- [x] **ToolGate**: Best-tested module (20/20 tests). Clean policy enforcement
- [x] **State Machine**: Correct FSM with role-based transition guards
- [x] **Pydantic Schema**: Comprehensive domain models with validation
- [x] **Bare except: Cleanup**: Zero bare `except:` clauses remain
- [x] **requests -> httpx**: gitea_webhook_handler.py now uses `await self.client.post()`
- [x] **Webhook Server**: HMAC signature validation, event dispatcher
- [x] **Sandbox Orchestrator**: Docker Compose generation, port allocation
- [x] **Memory Store**: Persistent per-issue memory with RAG search
- [x] **Agent Coordination Hub**: Sovereign directories, handoff protocols
- [x] **pyproject.toml**: Single source of truth for dependencies
- [x] **Structured Logging**: Rotating file handlers, JSON format, subscriber system
- [x] **Auth Service**: JWT + bcrypt, RuntimeError if SECRET_KEY missing

---

## Phase 0: Architectural Alignment (Week 1 -- PRE-REQUISITE)

**Goal**: Align the codebase with `docs/OrketArchitectureModel.md` and address the "Three Projects in a Trenchcoat" diagnosis.

### 0.1 Decouple the Product Core (The "Diamond")
**Context**: The workflow engine (cards, bottlenecks, priority) is the most valuable part but is coupled to LLM logic.
**Action**:
- Create `orket/core/` directory.
- Move `WaitReason`, `CardStatus`, `BottleneckThresholds`, `CriticalPath` logic here.
- **Strict Rule**: `orket/core/` must NOT import `llm`, `server`, or `cli`. It must be runnable purely with Python standard library (and maybe Pydantic).

### 0.2 Unify Configuration (The "Source of Truth")
**Context**: "Identity Fragmentation" (3 different organization.json files).
**Action**:
- Designate `config/organization.json` as the Single Source of Truth.
- Delete `config/org_info.json` and `model/organization.json`.
- Update `ConfigLoader` to read ONLY from the single source.
- Remove logic that "guesses" which config to use.

### 0.3 Formalize Entry Points (The "Facade")
**Context**: `main.py` (CLI) and `server.py` (API) initialize the system differently.
**Action**:
- Create `orket/system.py` with an `OrketSystem` class (Facade).
- `OrketSystem` handles config loading, DB connection, and Engine initialization.
- Refactor `main.py` and `server.py` to simply call `OrketSystem.boot()`.

### 0.4 Isolate Volatility (The "Decision Nodes")
**Context**: Volatile AI logic (`llm.py`, prompt compilation) is mixed with stable plumbing.
**Action**:
- Create `orket/intelligence/` (or `orket/decisions/`).
- Move `llm.py`, prompt logic, and dialect handling here.
- Define strict interfaces (contracts) between `orket/orchestration` and `orket/intelligence`.

---

## Phase 1: Stop Lying to Ourselves (Week 1 -- IMMEDIATE)

**Goal**: Fix every item the old roadmap falsely marked as done.

### 1.1 Delete Dead Code (Verified Complete)

| File | Lines | Status | Why It Still Exists |
|:---|:---|:---|:---|
| `orket/filesystem.py` | 159 | GONE | Verified deleted. |
| `orket/conductor.py` | 109 | GONE | Verified deleted. |
| `orket/persistence.py` | 176 | GONE | Verified deleted. |
| `orket/orket.py:305-306` | 2 | GONE | Verified deleted. |
| `async_card_repository.py:208-225` | 18 | GONE | Verified deleted. |

### 1.2 Fix datetime.now() (Verified Complete)

16 occurrences across 6 files. Every one gets `UTC`:

**Status**: [x] Verified. All 16+ occurrences now use `datetime.now(UTC)`.

### 1.3 Harden Credential Management (Verified Complete)

| Issue | File | Fix |
|:---|:---|:---|
| Empty GITEA_ADMIN_PASSWORD default | gitea_webhook_handler.py:37 | [x] Raises RuntimeError |
| Hardcoded DB passwords in sandbox templates | sandbox_orchestrator.py:274 | [x] Uses secrets.token_urlsafe |
| WEBHOOK_SECRET silent startup | webhook_server.py:38 | [x] Fails at startup |
| Wildcard CORS methods/headers | api.py:44-45 | [x] Explicit list |

### 1.4 Fix Async Contamination (Day 2, 2 hours)

`SQLiteSessionRepository` and `SQLiteSnapshotRepository` are synchronous `sqlite3` implementations called from async `ExecutionPipeline`. Every call blocks the event loop.

**Option A (Quick)**: Wrap with `asyncio.to_thread()` at call sites
**Option B (Proper)**: Create `AsyncSessionRepository` and `AsyncSnapshotRepository` using aiosqlite

Recommended: **Option B**. The sync repositories are 80 lines each. Port them to aiosqlite.

### 1.5 Add asyncio Locks to GlobalState (Day 2, 30 minutes)

`orket/state.py` has unprotected shared state accessed from multiple async contexts:
```
active_websockets: List[Any]   -- mutated in api.py:215 and api.py:229
active_tasks: Dict[str, Task]  -- mutated in api.py:134
interventions: Dict             -- mutated from multiple contexts
```

Add `asyncio.Lock` for each mutable field.

---

## Phase 2: Close the Test Gap (Week 2)

**Goal**: Get from 67 tests to 120+. Test the things that actually matter.

### 2.1 Critical Module Tests (Must Have)

| Module | Current Tests | Target | Status | Why |
|:---|:---|:---|:---|:---|
| `AsyncCardRepository` | 12 | 15 | [x] DONE | All persistence flows through here |
| `interfaces/api.py` | 8 | 15 | [x] BEGUN | 20+ endpoints, baseline coverage |
| `services/tool_parser.py` | 10 | 10 | [x] DONE | Parses LLM output |
| `ConfigLoader` | 0 | 6 | [ ] TODO | Fallback logic, asset loading |
| `gitea_webhook_handler.py` | 0 | 8 | [ ] TODO | PR lifecycle, cycle tracking |
| `Orchestrator.execute_epic` | 0 | 5 | [ ] TODO | The main execution loop |

### 2.2 Error Path Tests (Should Have)

- [x] Malformed JSON from LLM (tool_parser edge cases)
- [ ] Missing config files (ConfigLoader fallback behavior)
- [ ] Permission denied on file write (FileSystemTools)
- [x] Database locked / corrupted (AsyncCardRepository)
- [ ] Gitea unreachable (webhook handler timeout/retry)
- [ ] Invalid state transitions (StateMachine negative cases)

### 2.3 Test Infrastructure (Build Once)

Create `tests/conftest.py` with shared fixtures:
```
OrgBuilder().with_idesign(threshold=2).write(root)
EpicBuilder("EPIC-01").with_issues(3).write(root)
TeamBuilder.standard().write(root)
```

This addresses ChatGPT's review finding: "Each test reconstructs an entire miniature universe."

---

## Phase 3: Structural Integrity (Week 3-4)

**Goal**: Resolve the remaining DRY violations and architectural debt.

### 3.1 Consolidate File I/O

Three implementations exist: `FileSystemTools` (sync, tools.py), `AsyncFileTools` (async, infrastructure/), and raw `Path.read_text()` calls in api.py, logging.py, orket.py.

**Status**: [> ] IN PROGRESS. `AsyncFileTools` integrated into `tools.py`; `api.py` read/save endpoints and `orket.py` config loading paths now migrated. Remaining direct file I/O cleanup continues in other modules.

### 3.2 Consolidate Status Update Logic

Status validation is duplicated in:
1. `tools.py:CardManagementTools.update_issue_status()`
2. `services/tool_gate.py:_validate_state_change()`
3. `domain/state_machine.py:validate_transition()`

Target: StateMachine is the single authority. ToolGate delegates to StateMachine. CardManagementTools delegates to ToolGate.

**Status**: [> ] PARTIAL. `ToolGate` delegates to `StateMachine`, and `CardManagementTools.update_issue_status()` now validates via `StateMachine` (remaining alignment: explicit ToolGate delegation path).

### 3.3 Complete GovernanceAuditor

`orket/orchestration/governance_auditor.py` exists but has incomplete methods:
- `_audit_destructive_operation()` -- [x] DONE
- `_audit_issue_creation()` -- [x] DONE

**Status**: [x] DONE. Methods implemented and wired into tool-call auditing.

### 3.4 Exception Hierarchy Expansion

Currently 44 `except Exception` catches across the codebase. Each should be narrowed:

| Location | Current | Target | Status |
|:---|:---|:---|:---|
| tools.py (6x) | `except Exception` | `except (FileNotFoundError, PermissionError, json.JSONDecodeError)` | [x] DONE |
| board.py (4x) | `except Exception` | `except (FileNotFoundError, json.JSONDecodeError, CardNotFound)` | [ ] TODO |

### 3.5 Refactor policy.py After filesystem.py Deletion

`policy.py` imports `FilesystemPolicy` from the deleted `filesystem.py`. Options:
- **A**: Inline workspace validation into `policy.py` using `Path.is_relative_to()`
- **B**: Have `policy.py` delegate to `BaseTools._resolve_safe_path()`

Recommended: **A**. Keep it simple.

---

## Phase 4: Parallel Execution Hardening (Week 5-6)

**Goal**: Make the DAG-based parallel execution production-safe.

### 4.1 Race Condition Tests

The Orchestrator runs issues in parallel via `asyncio.gather()` with a semaphore (limit: 3). But:
- No tests verify concurrent execution produces correct results
- No tests for workspace file conflicts between parallel agents
- No tests for database contention under parallel writes

### 4.2 File Locking for Parallel Agents

When two agents write to the same workspace concurrently, file conflicts are possible. Implement:
- Per-issue workspace subdirectories (agents cannot write outside their issue scope)
- Or file-level advisory locking via `filelock`

### 4.3 Context Window Management

The Orchestrator passes a sliding window of 5 turns (`self.transcript[-5:]`). For complex issues requiring 20+ turns, agents lose context.

Options:
- Increase window to 10 (simple, more tokens)
- Implement summarization (compress old turns into a summary)
- Use the Memory Store (already exists) to persist key decisions

---

## Phase 5: Production Readiness (Week 7-10)

**Goal**: Actual production readiness, not claimed.

### 5.1 Verification Engine Hardening

The RCE mitigation (directory separation) is necessary but insufficient. `importlib.exec_module()` still executes with full process privileges.

**Target**: Run verification fixtures in `subprocess` with:
- Timeout (prevent infinite loops)
- No network access
- Read-only filesystem
- Resource limits (memory, CPU)

Long-term: Docker container execution.

### 5.2 CI/CD Pipeline

No CI currently exists. Create:
```yaml
# .github/workflows/quality.yml
- pytest tests/ --cov=orket --cov-fail-under=60
- ruff check orket/
- mypy orket/ --ignore-missing-imports
- grep -rn "datetime.now()" orket/ --include="*.py" | grep -v "now(UTC)" && exit 1
```

### 5.3 Rate Limiting

Webhook endpoint has no rate limiting. Add:
- Token bucket or sliding window rate limiter
- Configurable via `ORKET_RATE_LIMIT` env var

### 5.4 Input Validation

API endpoints accept raw `Dict[str, Any]`. Replace with Pydantic models:
- `RunAssetRequest` for `/system/run-active`
- `GiteaWebhookPayload` for `/webhook/gitea`
- `SaveFileRequest` for `/system/save`

### 5.5 Load Testing

Before claiming production-ready:
- 100 concurrent webhook deliveries
- 10 parallel epic executions
- 50 simultaneous WebSocket connections
- Measure: response time p50/p95/p99, error rate, memory usage

---

## Phase 6: Operational Maturity (v1.0 Actual)

**Goal**: The real v1.0.

### 6.1 Metrics
- 150+ tests with 60%+ code coverage
- Zero CRITICAL/HIGH security findings
- All async functions truly async (no blocking calls)
- Zero bare `except:` or overly broad `except Exception`
- Sub-second API response times under load

### 6.2 Deliverables
- Production Dockerfile with health checks
- Migration scripts for database schema changes
- Runbook for common operational scenarios
- Security audit report (internal or external)

---

## Agent Contribution Tracker

| Agent | Phase | Key Contributions |
|:---|:---|:---|
| GeminiCLI | v0.3.9 | Async migration, security patches, exception cleanup, dependency consolidation |
| GeminiAntigravity | v0.3.10+ | Mandatory governance, engine hardening, parallel DAG, AST enforcement, memory store |
| GeminiPro | Phase 7 | PII scrub, config refactor, CORS/auth, script fixes, code decomposition |
| Claude (Sonnet) | Feb 9 AM | Original code review, BRUTAL_PATH.md, identified 15 critical issues |
| Claude (Opus) | Feb 9 PM | Deep 6-agent review (security, async, architecture, testing, errors, deps) |
| ChatGPT | Feb 9 | Test design critique, DI recommendations, iDesign structured violations |
| Claude (Opus) | Feb 10 | This roadmap. Full audit against all prior claims. Honesty pass. |

---

## Products Built by Orket

The `workspace/default/` directory contains an iDesign-structured project (managers, engines, accessors, controllers, utils). The `product/` directory contains:

| Product | State | Notes |
|:---|:---|:---|
| sneaky_price_watch | Substantial (~20 modules) | iDesign structure (Accessors/Controllers/Engines/Managers). Import paths may need fixing. |
| price_arbitrage | Stub (~50 lines) | Placeholder polling loop. No real logic. |

---

## The Uncomfortable Truth (Updated)

Four separate code reviews by four different AI agents all converged on the same conclusion:

> **Concept: 8/10. Implementation: 3/10.**

The reconstruction raised implementation to approximately **5/10**. The TurnExecutor, AsyncCardRepository, ToolGate, and StateMachine are genuinely well-built. But the last 40% -- the dead code, the datetime bugs, the sync-in-async contamination, the untested API, the false roadmap claims -- erodes trust in everything else.

**The single hardest thing about this project is not building new features. It is finishing what was started.**

This roadmap does not contain a single new feature. Every item is cleanup, hardening, or testing of existing code. That is intentional. The architecture is sound. The domain models are clean. The reconstruction plan was correct. Now we finish the job.

---

## Key References

| Document | Location | Purpose |
|:---|:---|:---|
| This Roadmap | `docs/ROADMAP.md` | Unified source of truth |
| BRUTAL_PATH.md | `docs/BRUTAL_PATH.md` | Original emergency plan (Feb 9) |
| Claude Deep Review | `docs/reviews/Claude_Deep_Review_2026-02-09.md` | 30-finding security/architecture audit |
| ChatGPT Review | `docs/reviews/Code_Review (2-9-2026 10pm0).md` | Test design and DI critique |
| Gemini Brutal Review | `docs/reviews/Gemini_Brutal_Review_2026-02-10.md` | God class and governance theater analysis |
| Claude Feedback | `docs/reviews/Claude_Feedback_2026-02-10.md` | 21 catastrophic design failures |       
| Reconstruction Status | `Agents/Claude/RECONSTRUCTION_STATUS.md` | Session-level progress tracker |
| GLOBAL_ACTIVITY.md | `docs/GLOBAL_ACTIVITY.md` | Who did what, when |
