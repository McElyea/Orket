# Orket Code Review (Brutal but Constructive)

**Reviewer:** ChatGPT  
**Tone:** Honest, uncompromising, rooting for you  
**Overall Verdict:** Strong ideas, real system, but abstractions are leaking and tests are carrying too much weight.

---

## Executive Summary

This codebase is **ambitious and serious**. You are tackling problems most projects never even attempt:

- Deterministic agent orchestration
- Runtime architectural governance (iDesign)
- Tool-gated execution
- Session resumption
- Model-agnostic agent dialects
- Hard execution gates (complexity, verification)

That puts Orket closer to **Temporal / Airflow / LangGraph** than to “LLM wrapper” projects.

However:

> **Your tests are compensating for weak boundaries, and your engine API is trying to be clever instead of boring.**

The result is brittleness, repetition, and unnecessary coupling.

This review focuses on the highest-leverage fixes.

---

## 1. Test Design: Overcoupled and Overbuilt

### Problem

Each test reconstructs an entire miniature universe:

- `organization.json`
- dialects
- roles
- teams
- environments
- epics
- SQLite state
- monkeypatched providers

Symptoms:
- Tests are long but not expressive
- Small schema changes cause widespread breakage
- Test intent is buried under setup noise

This is not clarity — it’s **ceremony**.

### Recommendation

Introduce **test builders or helpers**.

Examples:

```python
OrgBuilder().with_idesign(threshold=2).write(root)
EpicBuilder("EPIC-01").with_issues(3).write(root)
TeamBuilder.standard().write(root)
```

Or at minimum:

```python
write_minimal_org(root)
write_standard_team(root)
write_dummy_dialects(root)
```

Your tests should describe behavior, not infrastructure provisioning.

## 2. Monkeypatching LocalModelProvider Is a Smell

### Problem

Tests globally monkeypatch constructors and methods:

```python
monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
monkeypatch.setattr(LocalModelProvider, "complete", dummy_provider.complete)
```

This causes:

- Hidden coupling between tests
- Order-dependent behavior
- Bypassing dependency injection entirely

This is fragile and will eventually bite you.

### Recommendation

Introduce dependency injection at the engine boundary.

Example:

```python
engine = OrchestrationEngine(
    workspace,
    provider_factory=lambda env: DummyProvider()
)
```

Then tests can inject providers cleanly without monkeypatching global state.

## 3. Tests Assert Internal Choreography Instead of Outcomes

### Problem

Some tests assert execution mechanics instead of results:

```python
assert dummy_provider.turns >= 2
```

This bakes internal implementation details into your test contract.

If you later:

- collapse phases
- merge verifier passes
- change retry logic

…the behavior is still correct, but tests fail.

### Recommendation

Assert effects, not choreography.

**Good:**

```python
assert issue["status"] == "done"
assert sanity_file.exists()
```

**Bad:**

```python
assert turns >= 2
```

Let the engine evolve internally.

## 4. iDesign Validator: Strong Idea, Weak Enforcement Model

This is one of Orket’s best ideas — and also one of its riskiest.

### What Works Well

- Runtime architectural governance is excellent
- Naming rules are explicit and testable
- Violations are human-readable
- Enforcement is automated (huge win)

### Problems

#### 1. Path-Based Heuristics Are Brittle

`"path": "engines/logic.py"`

Assumes:

- directory == responsibility
- naming == intent
- no refactors
- no legacy code

This is acceptable as a heuristic, but not true enforcement.

#### 2. Validator Returns Strings Instead of Structured Data

```python
violation = iDesignValidator.validate_turn(...)
assert "Manager component" in violation
```

This:

- Forces brittle string matching
- Makes evolution painful
- Blends UX with programmatic contracts

### Recommendation

Return structured violations:

```python
Violation(
  code="ENGINE_NAMING",
  severity="error",
  message="Engine component must include 'Engine' in filename",
  path="engines/compute.py"
)
```

Tests then assert on codes, not text.

---

## 5. OrchestrationEngine.run_card() Is Doing Too Much

### Problem

`run_card()` is overloaded with responsibilities:

- config loading
- session resumption
- issue filtering
- governance enforcement
- orchestration
- verification
- persistence

This makes the API unclear and hard to reason about.

### Recommendation

Split intent explicitly:

```python
engine.run_epic("epic_id")
engine.resume_issue("epic_id", "issue_id")
engine.run_issue(issue_id)
```

APIs should communicate intent clearly and honestly.

---

## 6. SQLite Repositories Leak Domain Shape

### Problem

Repositories accept raw dictionaries:

```python
cards.save({"id": "I1", "status": "done", ...})
```

This provides:

- No validation
- No invariants
- No guarantees

Your domain deserves more structure than “hope this dict is correct.”

### Recommendation

Use typed records or domain objects:

```python
IssueRecord(
    id="I1",
    status="done",
    seat="lead_architect"
)
```

This doesn’t require heavy DDD — just guardrails.

---

## 7. Tests Encode Product Decisions Accidentally

### Problem

Tests assert on human-facing strings:

```python
assert "Complexity Gate Violation" in str(exc.value)
```

This freezes UX text as an API contract.

### Recommendation

Raise typed exceptions:

```python
with pytest.raises(ComplexityViolation):
    ...
```

Human-readable messages can evolve. Error contracts should not.

---

## Secondary Review: Critical Issues & Code Smells

### 1. File & Directory Hygiene
- **Empty `debug_schema.py`**: Dead weight that clutters the codebase.
- **Duplicate `__pycache__`**: Appears twice in `project_dumper_small.py`'s `skip_dirs`.
- **Test Scatter**: Tests are scattered across `workspace/default/tests/` and `workspace/default/examples/`. Standardize to a single location.

### 2. Configuration & Settings
- **Hardcoded Paths**: `reload_excludes` in `server.py` is brittle.
- **Claude Settings Mess**: `.claude/settings.local.json` contains hardcoded git commit templates.
- **Config Duplication**: Multiple `environment.json` files with conflicting model definitions.
- **Hardcoded Secrets/Org Data**: Organization details and potentially model preferences are burned into the repo.

### 3. API & Execution
- **Error Handling**: `main.py` and `server.py` lack graceful crash reporting.
- **Brittle APIs**: `run_card` (addressed in Phase 1) and lack of API versioning.
- **Hidden Logic**: Priority calculation is buried in private methods but leaked to demos.

### 4. Code Quality
- **Docstrings**: Widespread lack of documentation for functions like `normalize_price`, `evaluate_alert_conditions`.
- **Naming Inconsistency**: Mix of naming styles across the codebase.
- **God Objects**: Unclear boundaries between "Managers", "Engines", and "Accessors".
- **Complexity**: `export_project_filtered` is doing too much.

### 5. Performance & Security
- **Sync I/O**: `project_dumper` uses synchronous file reads.
- **Pagination**: Memory risks when handling large lists of products/prices.
- **Input Validation**: `normalize_price` is vulnerable to malformed strings or null values.

---

## Updated Recommendations

1. **Purge the Dead Weight**: Delete empty files and fix copy-paste errors.
2. **Canonicalize Config**: Ensure there is only one source of truth for environment settings.
3. **Document Boundaries**: Create `ARCHITECTURE.md` to define the iDesign component roles.
4. **Harden Entry Points**: Add global error handlers to `main.py` and `server.py`.
5. **Standardize Tests**: Move all verification logic into a consistent directory structure.
