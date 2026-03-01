# Refactor Requirements: SOLID Cleanup and Structural Decomposition

Date: 2026-02-28
Type: structural refactor / design quality improvement
Baseline: v0.4.5 reconstruction complete, 1148/1189 tests passing (96.6%)

## Objective

Decompose god classes, eliminate SOLID violations, and resolve remaining design debt identified in the 2026-02-28 audit. Bring implementation quality from 5/10 toward 7/10 without breaking existing contracts or domain behavior.

## In Scope

1. God class decomposition (ExecutionPipeline, GiteaWebhookHandler, VerificationEngine).
2. Data clump extraction into value objects (RunContext, PullRequestRef).
3. Dependency inversion fixes (inject instead of instantiate).
4. Async/sync contamination cleanup (AsyncFileTools bridging pattern).
5. Type hint standardization (lowercase generics, missing return types).
6. Test contract alignment (kernel v1 schemas, dependency policy, print policy).
7. Dead code removal (legacy shims, urllib holdout).

## Out of Scope

1. New feature development.
2. Domain model changes (schema.py, state_machine.py).
3. Public API contract changes.
4. Infrastructure or deployment changes.
5. Reforger module internals (separate project).

## Functional Requirements

### FR-1: ExecutionPipeline decomposition
- `ExecutionPipeline` (~660 lines) must be split into focused classes each under 200 lines.
- Epic execution logic extracted to a dedicated orchestrator.
- Artifact export logic extracted to a dedicated exporter.
- Session/transcript management extracted to a dedicated manager.
- The coordinator class accepts dependencies via constructor injection, not internal instantiation.
- `run_epic` method nesting depth must not exceed 3 levels.

### FR-2: GiteaWebhookHandler decomposition
- Webhook event dispatch must use a handler registry or polymorphic pattern, not if-elif chains.
- PR review, merge, rejection, and sandbox deployment must be in separate handler classes.
- Webhook payloads must be validated with Pydantic models before field access.
- Data clump `(owner, repo_name, pr_number, repo_full_name)` replaced with `PullRequestRef` value object.

### FR-3: VerificationEngine extraction
- Embedded 87-line subprocess runner code must be extracted to a `SubprocessVerificationRunner` class.
- `VerificationEngine` delegates execution to the runner, retaining only orchestration logic.
- Subprocess lifecycle, network isolation, and resource limits are the runner's responsibility.

### FR-4: Data clump elimination
- `RunContext` dataclass created for `(run_id, active_build, workspace, department, config_root, db_path)`.
- `PullRequestRef` dataclass created for `(owner, repo_name, pr_number, repo_full_name)`.
- All methods currently receiving these as individual parameters must accept the dataclass instead.

### FR-5: Dependency injection fixes
- `SandboxOrchestrator` must accept `AsyncFileTools` via constructor, not instantiate internally.
- `OrketDriver` must accept `LocalModelProvider` and tool instances via constructor.
- Module-level `api_runtime_node` in `api.py` must be lazily initialized or injected.

### FR-6: Async consistency
- `AsyncFileTools._run_async()` sync/async bridging via ThreadPoolExecutor must be replaced with a clean async-only interface or a documented executor service.
- `gitea_artifact_exporter.py` must migrate from `urllib.request` to `httpx`.
- Legacy `sqlite_repositories.py` (sync) must be removed if no longer referenced.

### FR-7: Type hint standardization
- All type hints must use lowercase generics (`dict`, `list`, `tuple`) per Python 3.9+.
- All public methods must have explicit return type annotations.
- Mixed `Optional[X]` / `X | None` syntax must be standardized to `X | None`.

### FR-8: Test contract alignment
- Kernel v1 test schemas must match current code schemas (19 failing tests).
- New modules (`reforger`, `streaming`, `workloads`, `extensions`, `driver_support_*`) must be registered in the dependency direction policy (2 failing tests).
- `reforger/cli.py` print calls must be whitelisted or replaced with logging (1 failing test).

## Quality Requirements

1. No regression in currently passing tests (1148 minimum).
2. All 32 currently failing tests must be resolved or explicitly deferred with justification.
3. No new `except Exception` broad catches introduced.
4. No new global mutable state introduced.
5. Each decomposed class must have at least one direct unit test.

## Verification Requirements

1. Run full test suite: `python -m pytest tests/ -v --tb=short`
2. Run architecture guards:
   - `python -m pytest tests/platform/ -v`
   - `python scripts/check_dependency_direction.py`
3. Verify no broad exception catches added: `grep -rn "except Exception" orket/`
4. Verify no sync HTTP usage added: `grep -rn "import requests" orket/`
5. Verify type hint consistency: `grep -rn "Dict\[" orket/` should return 0 results.

## Acceptance Criteria

1. ExecutionPipeline is under 200 lines; no method exceeds 3 nesting levels.
2. GiteaWebhookHandler uses handler registry; payloads validated with Pydantic.
3. VerificationEngine delegates to SubprocessVerificationRunner.
4. RunContext and PullRequestRef dataclasses exist and are used at all call sites.
5. All dependencies injected via constructor; no internal instantiation of services.
6. Type hints standardized; all public methods annotated.
7. Test suite passes at 1180+ (current 1148 + resolved failures).
8. No new SOLID violations introduced.
