# Orket — Issue Remediation Plan
*Generated April 25, 2026 · Based on Code Review (58 issues) + Behavioral Review (13 issues)*

---

## Guiding Principles for This Plan

1. **Fix what breaks users first** — security and correctness before architecture purity.
2. **One refactor at a time** — don't interleave structural changes with bug fixes.
3. **Every fix needs a test that would have caught the original bug.**
4. **Don't create a new lane for every fix** — batch related issues into one focused sprint.

---

## Wave 1 — Critical & Security (Do Now, 1–2 weeks)

These issues can cause data loss, security exposure, or silent wrong behavior in production.

### W1-A: Secret Enforcement at Startup (Issues 26, 27, 28, 29)

**What:** Add a startup validation pass that refuses to boot if required secrets are at their default/placeholder values in non-local environments.

**Steps:**
1. Create `orket/runtime/startup_checks.py` with a `validate_required_secrets()` function.
2. Check `ORKET_ENCRYPTION_KEY`, `SESSION_SECRET`, `GITEA_WEBHOOK_SECRET`, `ORKET_API_KEY` against known placeholder strings.
3. Replace `MSSQL_SA_PASSWORD=YourStrong!Passw0rd` in `.env.example` with `MSSQL_SA_PASSWORD=change-me-sql-server-sa`.
4. Use `hmac.compare_digest` for the `X-API-Key` header comparison (Issue 28).
5. Add a CORS configuration module (Issue 30) — start with explicit `allow_origins=[]` (deny all cross-origin) and document how to open it.
6. Add a startup warning if `ORKET_GITEA_ALLOW_INSECURE=true` and `GITEA_URL` starts with `https://` (Issue 29).

**Test:** Write a test that monkeypatches each required env var to its placeholder value and asserts the app refuses to start.

---

### W1-B: Fix Silent Failure at Data Extraction Boundaries (Issues 15, 16, 17, 21, 25)

**What:** The `extract_openai_*` and `_normalized_tools` functions silently swallow structural errors. These are the "fail-closed" gaps identified in the Behavioral Review.

**Steps:**
1. Change `extract_openai_content` to return `Optional[str]` — `None` for structural failure, `""` for legitimate empty model response.
2. Fix `_to_int` to handle negative integers: use `int(value.strip())` with a `try/except ValueError` instead of `isdigit()`.
3. Add a `log.warning` with structured fields to `_normalized_tools` when it falls back to an empty list.
4. Add a null guard before `recover_structured_reasoning_answer("")`.
5. Fix the `str(action.get("kind") or "")` pattern in all rulesim toys to raise `TypeError` on non-string input.

**Test:** Unit tests for each function covering the structural failure paths.

---

### W1-C: SQLite WAL Mode (Issue 34)

**What:** Enable WAL mode on every database connection open to prevent `database is locked` errors under concurrent async access.

**Steps:**
1. Find the `aiosqlite` connection open site in the control plane.
2. Add `await db.execute("PRAGMA journal_mode=WAL;")` immediately after open.
3. Add a connection health check that verifies WAL mode is active.

**Test:** Write a concurrent write test using `asyncio.gather` that would fail under non-WAL mode.

---

### W1-D: Session ID Collision Fix (Issue 7)

**What:** The `build_orket_session_id` hash fallback collides for sessions with the same provider/model/first-two-messages.

**Steps:**
1. Add a monotonically increasing counter or a `uuid.uuid4()` component to the fallback derivation.
2. Audit all call sites to ensure the preferred `session_id` or `run_id` is passed explicitly wherever possible.
3. Remove `"seat_id"` from the fallback key priority list (Issue 18) — it is a role identifier, not a session identifier.

**Test:** Write a test that creates two sessions with identical prompts and asserts they get different IDs.

---

## Wave 2 — Architecture Refactoring (2–4 weeks)

These issues are structural and require more coordinated changes. Do one at a time.

### W2-A: Define a `RuleSystem` Protocol and Enforce It (Issues 4, 5)

**What:** Replace the implicit duck-typed `RuleSystem` interface with a formal `Protocol`.

**Steps:**
1. Create `orket/rulesim/protocol.py`:
   ```python
   from typing import Protocol, runtime_checkable
   
   @runtime_checkable
   class RuleSystem(Protocol):
       def initial_state(self, seed: int, scenario: dict, ruleset: dict, agents: list[str]) -> dict: ...
       def legal_actions(self, state: dict, agent_id: str) -> list[dict]: ...
       def apply_action(self, state: dict, agent_id: str, action: dict) -> TransitionResult: ...
       def is_terminal(self, state: dict) -> TerminalResult | None: ...
       def observe(self, state: dict, agent_id: str) -> dict: ...
       def hash_state(self, state: dict) -> str: ...
       def serialize_state(self, state: dict) -> dict: ...
       def serialize_action(self, action: dict) -> dict: ...
       def action_key(self, action: dict) -> str: ...
   ```
2. Assert `isinstance(rule_system, RuleSystem)` at registry registration time.
3. Delete `State = Any`, `Action = Any`, `Observation = Any` from `rulesim/types.py`.

**Test:** A test that registers a malformed rule system and asserts `isinstance` fails at registration.

---

### W2-B: Collapse `GoldenDeterminismRuleSystem` and Fix Registry Naming (Issues 3, 55)

**Steps:**
1. Delete `orket/rulesim/toys/golden_determinism.py`.
2. In the rule system registry, add `"golden_determinism": LoopRuleSystem` as an alias entry.
3. Update all call sites that import `GoldenDeterminismRuleSystem`.

---

### W2-C: Per-Provider Extractor Registry (Issues 8, 20, 54)

**What:** The triple-fallback chains in `extract_openai_timings` and the Ollama-handling in `extract_openai_*` should be replaced with a per-provider extractor registry.

**Steps:**
1. Define `ProviderExtractor` protocol with `extract_content`, `extract_usage`, `extract_tool_calls`, `extract_timings` methods.
2. Implement `OpenAIExtractor` and `OllamaExtractor` separately.
3. Registry: `{"openai": OpenAIExtractor(), "ollama": OllamaExtractor(), "lm_studio": OllamaExtractor()}`.
4. Delete `openai_native_tools.py` fallback chains.
5. Rename the module to `provider_extractors/`.

---

### W2-D: Extract `_dedupe` to Shared Utility (Issue 22)

**Steps:**
1. Create `orket/utils/collections.py` with `dedupe_ordered(values: Iterable[str]) -> list[str]`.
2. Replace all inline `_dedupe` implementations with the shared function.
3. Add a unit test for `dedupe_ordered`.

---

### W2-E: Replace `deepcopy` in RuleSystem Toys with Typed State Objects (Issue 6)

**What:** Long-term fix for the copy-on-every-step performance issue.

**Steps:**
1. Define a `frozen=True` dataclass for each toy's state:
   ```python
   @dataclass(frozen=True)
   class LoopState:
       tick: int = 0
   ```
2. Since frozen dataclasses are immutable, mutation becomes `replace(state, tick=state.tick + 1)` — which creates a shallow copy only of the changed fields.
3. Update `serialize_state` to output `asdict(state)` and `initial_state` to return `LoopState()`.

---

### W2-F: Fix `_process_rule` and Remove `organization: Any` (Issue 2)

**Steps:**
1. Define an `Organization` Protocol (or dataclass) with `process_rules: dict[str, Any]`.
2. Update `GiteaStateLoopRunner` to accept `organization: Organization | None`.
3. Move the `_process_rule` logic into the `Organization` type itself.
4. Move the `state_backend_mode != "gitea"` guard to `__post_init__` (Issue 10).

---

### W2-G: Add Schema Migration Framework (Issue 36)

**Steps:**
1. Evaluate `yoyo-migrations` (lightweight, SQLite-compatible) or write a minimal internal migration runner.
2. Create `orket/infrastructure/db/migrations/` with numbered migration files.
3. Add a `migrate()` call to the startup sequence before any schema access.
4. Add a test that applies migrations to an empty DB and verifies the schema.

---

## Wave 3 — Testing Hardening (2–3 weeks)

### W3-A: Test Isolation — Remove Shared Global State (Issues 39, 40, 41)

**Steps:**
1. Create a `pytest` fixture `api_key_env` that sets and restores `ORKET_API_KEY` per test.
2. Create a `test_client` fixture that creates a fresh `TestClient(app)` per test (not module-level).
3. Ensure `CardStatus` and all other types used in tests have explicit imports at the top of each test file.
4. Add `asyncio_mode = "auto"` to `pytest.ini` or `pyproject.toml` if not already set.

---

### W3-B: Add Engine Teardown in Integration Tests (Issue 38)

**Steps:**
1. Add an `async_engine` fixture:
   ```python
   @pytest_asyncio.fixture
   async def async_engine(tmp_path):
       engine = OrchestrationEngine(workspace_root=tmp_path / "ws", db_path=str(tmp_path / "rt.db"))
       yield engine
       await engine.close()
   ```
2. Update all tests that create `OrchestrationEngine` directly to use this fixture.

---

### W3-C: Fix Random Stream Separation in ODR Gate (Issue 45)

**Steps:**
1. Replace `random.Random(seed + (perm_index * 7919))` with `random.Random((seed, perm_index))`.
2. Add a test that verifies two different `perm_index` values produce different permutation orders on the same fixture.

---

### W3-D: Add Coverage Threshold (Issue 44)

**Steps:**
1. Add `pytest-cov` to dev dependencies.
2. Add to `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   addopts = "--cov=orket --cov-fail-under=70"
   ```
3. Set the initial threshold at current coverage, then raise it by 5% per sprint.

---

## Wave 4 — CI/CD & Governance (1–2 weeks)

### W4-A: Fix Force Push Base SHA (Issue 47)

**Steps:**
1. In `core-release-policy.yml`, handle the zero-SHA case:
   ```yaml
   BASE_SHA="${{ github.event.before }}"
   if [ "$BASE_SHA" = "0000000000000000000000000000000000000000" ]; then
     BASE_SHA=$(git rev-list --max-parents=0 HEAD)
   fi
   ```

---

### W4-B: Fix CalVer Stamping (Issue 48)

**Steps:**
1. Determine if `--dry-run` is intentional (validation only) or a bug.
2. If intentional, rename the CI step to "Validate CalVer" to avoid confusion.
3. If it should actually stamp, remove `--dry-run` and commit the updated `pyproject.toml` from CI.

---

### W4-C: Separate Retention Workflow Output Directory (Issue 51)

**Steps:**
1. Change the retention workflow output path from `benchmarks/results/quant/quant_sweep/` to `benchmarks/results/retention/weekly/`.
2. Update artifact upload paths accordingly.

---

### W4-D: Rename `openclaw_torture_adapter` (Issue 53)

**Steps:**
1. Rename the file and all references to `challenge_corpus_adapter`.
2. Update CI configuration and import paths.
3. Update changelog.

---

### W4-E: Fix `.env.example` Issues (Issues 27, 31, 32)

**Steps:**
1. Replace `YourStrong!Passw0rd` with `change-me-sql-server-sa`.
2. Replace `admin@viberail.local` with `admin@localhost.invalid`.
3. Rewrite the rate limit comment to explicitly state: "This is a per-worker limit. Total effective limit = ORKET_RATE_LIMIT × ORKET_WEBHOOK_WORKERS."
4. Replace `ORKET_TIMEZONE=MST` default with `ORKET_TIMEZONE=UTC` and add a comment about DST.

---

## Wave 5 — Behavioral Issues (4–6 weeks, requires design decisions)

### W5-A: Implement the Missing Outbound Policy Gate (Behavioral Issue 3)

This is the highest-priority behavioral issue because it is a gap between the stated architecture and the actual implementation.

**Steps:**
1. Audit whether `outbound_policy_gate.py` exists outside this dump.
2. If not, spec and implement the minimal PII scrub gate: configurable field path exclusions + placeholder substitution.
3. Wire it into the projection pack output path.
4. Add a test that proves PII fields are scrubbed from outbound payloads.

---

### W5-B: Widen the Approval Checkpoint Surface (Behavioral Issue 6)

The current approval checkpoint only covers `write_file` in `issue:` namespace. This is a product limitation, not just a code bug.

**Steps:**
1. Define the `tool_approval_family_v1` extension point: a list of governed tools eligible for approval-checkpoint.
2. Start with `write_file` + `create_directory` as the v1 family.
3. Document clearly which tools are and are not in the approval family.

---

### W5-C: Resolve the 4B Model Portability Path (Behavioral Issue 4)

The Gemma 4B portability path is stuck at 2/5 corpus slices. This is a product viability issue for operators without high-end GPUs.

**Options to evaluate:**
1. **Lower the corpus bar** — reduce the frozen 5-slice corpus to a 3-slice minimum-viable corpus for portability tier models.
2. **Add a portability-mode prompt reforger** — lower the constraint complexity in the reforged prompts for smaller models.
3. **Document the hardware minimum clearly** — if 4B is genuinely insufficient, publish the actual minimum VRAM spec and don't claim portability that doesn't exist.
4. **Defer local models below 7B** — accept that the portability target is 7B and reframe the portability claim.

**Decision needed from owner.** Do not leave this paused indefinitely — a paused lane with an unresolved portability claim is a product integrity problem.

---

### W5-D: Resolve Known ODR Nondeterminism (Behavioral Issue 5)

The Claim E nondeterminism is acknowledged. A "staged hardening lane" that stays staged indefinitely is not a resolution.

**Steps:**
1. Time-box the hardening lane: give it a specific completion date (suggest 6 weeks from now).
2. If not resolved by that date, downgrade the determinism claim in the architecture docs to "best-effort deterministic with known variance."
3. Either way, publish the variance range from the existing drift diff summary so operators can set expectations.

---

### W5-E: Define SDK Extension Versioning SLA (Behavioral Issue 12)

**Steps:**
1. Document whether the `orket_extension_sdk` follows the core version or has its own semantic version.
2. Define the compatibility guarantee: "SDK vX.Y is compatible with core vX.Y through vX.(Y+n)."
3. Add this to the SDK's `README.md` and the extension author documentation.

---

## Tracking

### Issue-to-Wave Mapping

| Wave | Issues Addressed |
|------|-----------------|
| W1 (Critical/Security) | 7, 15, 16, 17, 18, 21, 25, 26, 27, 28, 29, 30, 34 |
| W2 (Architecture) | 2, 3, 4, 5, 6, 8, 10, 20, 22, 36, 54, 55 |
| W3 (Testing) | 38, 39, 40, 41, 42, 43, 44, 45, 46 |
| W4 (CI/CD) | 13, 14, 31, 32, 47, 48, 51, 52, 53 |
| W5 (Behavioral) | B3, B4, B5, B6, B12 |
| Deferred/Low | 9, 11, 12, 19, 23, 24, 33, 35, 37, 49, 50, 56, 57, 58 |

### Deferred Items Note

Issues 49 (release cadence) and 50 (docs-to-code ratio) are structural process issues that require a team culture decision, not a code fix. The recommendation is to explicitly discuss them in a retrospective and set a policy (e.g., "no more than 3 releases per week," "every contract doc must have a test path"). They are not items that can be addressed by a single pull request.

---

## Success Criteria

After completing Waves 1–4:
- Zero critical security issues (verified by audit of `.env.example` and startup checks)
- SQLite WAL enabled and verified in integration tests
- `extract_openai_content` returns `Optional[str]` and all callers handle `None`
- `RuleSystem` Protocol exists and all toys pass `isinstance` check at registration
- CI coverage threshold is enforced
- CalVer situation is clarified (either stamping or explicitly documented as validation-only)

After Wave 5:
- Outbound policy gate is implemented and tested
- Approval checkpoint covers at least 2 tools
- The 4B portability situation has a decision (not just a paused lane)
- ODR nondeterminism is either fixed or the architecture docs are truthfully downgraded
- SDK SLA is published

---

*End of Remediation Plan*
