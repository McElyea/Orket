# Orket — Action Plan
_Based on code review (CR) and behavioral review (BR) findings, April 2026_

Items are ordered by impact-to-effort ratio. Each item references its source finding.

---

## Sprint 1 — Correctness & Safety (Do These First)

### P1-01 — Fix stderr contaminating determinism hash `[CR-01]`
**File:** `scripts/benchmarks/run_benchmark_suite.py` → `_run_once`

Split the combined output. Hash only stdout. Keep the combined string only for the `normalized_output_preview` debug field.

```python
# Before
raw_output = (result.stdout or "") + "\n" + (result.stderr or "")

# After
stdout_only = result.stdout or ""
debug_output = stdout_only + "\n--- stderr ---\n" + (result.stderr or "")
normalized = _normalize_text(json.dumps({
    "exit_code": int(result.returncode),
    "stdout_stderr": stdout_only,      # ← hash input: stdout only
    "artifacts": artifact_payload,
}, sort_keys=True), ...)
...
"normalized_output_preview": debug_output[:300],  # ← debug only
```

**Verification:** Run a task twice. Confirm hashes match when only stderr differs (e.g., add a `sys.stderr.write("noise\n")` to a runner). Confirm hashes still diverge when stdout actually differs.

---

### P1-02 — Fix `dsl_blocks[i + 1]` IndexError `[CR-02]`
**File:** `orket/application/services/tool_parser.py`

One-line fix inside the legacy DSL fallback loop:

```python
for i in range(1, len(dsl_blocks), 2):
    if i + 1 >= len(dsl_blocks):
        break          # ← add this guard
    tool_name = dsl_blocks[i]
    block_content = dsl_blocks[i + 1]
```

**Verification:** Add a unit test that passes a string ending with `[write_file]` (no trailing content) and asserts the result is an empty list, not an exception.

---

### P1-03 — Fix path traversal guard uses unresolved `workspace_root` `[CR-03]`
**File:** Wherever `_resolve_command_cwd` is defined (execution pipeline / runtime verifier)

```python
@staticmethod
def _resolve_command_cwd(raw_cwd: str, workspace_root: Path) -> Path | None:
    workspace_root = workspace_root.resolve()   # ← add this line
    token = str(raw_cwd or ".").strip() or "."
    ...
    if not resolved.is_relative_to(workspace_root):
        return None
    return resolved
```

**Verification:** Add a test that passes `workspace_root=Path(".")` and `raw_cwd="../../../etc"` and asserts the return is `None`.

---

### P1-04 — Fix `process.returncode or 0` maps None to success `[CR-05]`
**File:** `scripts/gitea/inspect_local_runner_containers.py` → `run_command`

```python
# Before
returncode=int(process.returncode or 0),

# After
rc = process.returncode
returncode=int(rc) if rc is not None else -1,
```

**Verification:** Confirm existing tests pass. Add a test that mocks `process.returncode = None` and asserts the result returncode is `-1`.

---

### P1-05 — Add OOM/SIGKILL failure class `[CR-11]`
**File:** `_failure_class_from_returncode`

```python
if returncode == 137:
    return "oom_killed"
```

**Verification:** Add a unit test. Update the `failure_breakdown` key aggregation wherever this is consumed to include `oom_killed`.

---

### P1-06 — Make `ORKET_ALLOW_INSECURE_NO_API_KEY` loud on startup `[BR-04]`
**File:** `orket/interfaces/api.py` or settings startup

```python
if os.getenv("ORKET_ALLOW_INSECURE_NO_API_KEY", "").lower() == "true":
    LOGGER.critical(
        "orket_insecure_no_api_key_enabled",
        extra={"warning": "API authentication is disabled. Never set this in non-local environments."}
    )
```

Also add a check: if `ORKET_ENV` is set to `production` or `staging`, refuse to start when this flag is set (exit 1 with a clear message).

---

## Sprint 2 — Reliability & Observability

### P2-01 — Surface all guard errors, not just the first `[CR-06]`
**File:** `build_runtime_guard_contract`

```python
violations = [
    GuardViolation(
        rule_id=f"RUNTIME_VERIFIER.FAIL.{i}",
        code="RUNTIME_VERIFIER_FAILED",
        message=error[:480],
        location="output",
        severity="strict",
        evidence=(error[:240] + "...[truncated]" if len(error) > 240 else error),
    )
    for i, error in enumerate(errors)
]
```

Or, if the schema requires exactly one violation, concatenate all errors:

```python
combined = " | ".join(e[:120] for e in errors[:5])
if len(errors) > 5:
    combined += f" | (+{len(errors) - 5} more)"
evidence = combined
```

**Verification:** Write a test that triggers two guard failures and asserts both appear in the response.

---

### P2-02 — Raise on unknown assertion op `[CR-07]`
**File:** `_json_assertion_matches`

```python
KNOWN_OPS = {"eq", "ne", "contains", "len_gte", "gt", "gte", "lt", "lte"}
if op not in KNOWN_OPS:
    raise ValueError(f"unknown assertion op: {op!r}. Known ops: {sorted(KNOWN_OPS)}")
```

Call site in `_json_assertion_failures` should catch `ValueError` and append it as an explicit failure message.

---

### P2-03 — Replace JSON deep-copy in `_permute_fixture` `[CR-08]`
**File:** `tools/repro_odr_gate.py`

```python
import copy
payload = copy.deepcopy(fixture)   # replaces json.loads(json.dumps(fixture))
```

---

### P2-04 — Add sqlite timeout to `_load_registered_runners` `[CR-09]`
**File:** `scripts/gitea/inspect_local_runner_containers.py`

```python
try:
    connection = sqlite3.connect(path, timeout=10)
    ...
except sqlite3.OperationalError as exc:
    LOGGER.warning("gitea_db_locked", extra={"path": str(path), "error": str(exc)})
    return set()
```

---

### P2-05 — Extract CI heredoc Python blocks into named scripts `[CR-10, BR-05]`
**Priority within sprint:** highest effort, highest correctness impact

Extract each `python - <<'PY'` block into a file in `scripts/ci/`:

- `sandbox_leak_gate.py` (from quality.yml sandbox acceptance job)
- `migration_smoke_validator.py` (from quality.yml migration smoke job)
- `memory_fixture_smoke.py` (from nightly-benchmark.yml)

Each extracted script should:
- Be callable as `python scripts/ci/<name>.py [args]`
- Have a `main() -> int` entry point
- Be covered by at least one unit test
- Pass ruff lint

The workflow steps become single-line calls: `python scripts/ci/sandbox_leak_gate.py`.

---

### P2-06 — Add `extraction_strategy` field to run summary `[BR-08]`
**File:** Turn artifact writer / run summary builder

The strategy string returned from `ToolParser.parse_tool_calls` (`"stack_json"`, `"legacy_dsl"`, `"truncated_json_recovery"`) should be recorded in the per-turn run summary artifact. This enables:
- Dashboard queries: "what % of turns this week used legacy_dsl?"
- Alerting: "legacy_dsl rate increased 10% in last 24h"

No behavior change — pure observability addition.

---

### P2-07 — Fix `normalize_json_stringify` O(n²) scan `[CR-12]`
**File:** `orket/application/services/tool_parser.py`

Add a max-expression-length guard in the paren-matching loop:

```python
MAX_STRINGIFY_EXPR = 8192
while pos < len(blob):
    if pos - expr_start > MAX_STRINGIFY_EXPR:
        # Expression too large — not a JSON.stringify we can safely normalize
        out.append(blob[marker_idx:])
        idx = pos
        break
    ...
```

---

## Sprint 3 — Test Coverage & Benchmark Validity

### P3-01 — Fix benchmark determinism measurement `[CR-04, BR-02]`
**File:** `scripts/benchmarks/run_benchmark_suite.py` + nightly workflow

Change default `--runs` for determinism-tagged tasks to `2`. Update the nightly workflow:

```yaml
--runs 2
```

Update the published determinism report schema to reject `runs_per_task: 1` as a valid determinism measurement (emit a warning in the report generation script: `"WARNING: runs_per_task=1 cannot prove determinism"`).

The report field `determinism_rate` should document its validity condition: `"valid only when runs_per_task >= 2"`.

---

### P3-02 — Add raw-JSON acceptance test path `[CR-17]`
**File:** `tests/integration/test_system_acceptance_flow.py`

Add a second mock provider variant that returns raw JSON without backtick fences:

```python
class RawJsonProvider:
    async def complete(self, messages):
        return ModelResponse(
            content='{"tool": "write_file", "args": {"path": "agent_output/raw.txt", "content": "ok"}}',
            raw={"model": "dummy", "total_tokens": 50},
        )
```

Run the same acceptance flow with this provider and assert it produces the same result. This exercises the stack-based JSON extractor path in a real integration test.

---

### P3-03 — Add JSON path bracket notation or document limitation `[CR-15]`
**File:** `_resolve_json_path` + task fixture documentation

Option A (minimal): Add a docstring and a clear error message explaining dot-notation-only support. Update the task fixture authoring guide.

Option B (proper): Extend the resolver to support `[N]` array subscripts:

```python
for token in re.split(r'[.\[\]]', path):
    if not token:
        continue
    ...
```

Option A is one commit. Option B is ~20 lines plus tests.

---

### P3-04 — Fix module-level `TestClient` env capture `[CR-19]`
**File:** `tests/interfaces/test_api*.py`

Create a pytest fixture that yields a fresh `TestClient` per test:

```python
@pytest.fixture
def api_client():
    from orket.interfaces.api import app
    with TestClient(app) as client:
        yield client
```

Replace module-level `client = TestClient(app)` in all API test files. This is a mechanical refactor — the test logic doesn't change, only where `client` comes from.

---

### P3-05 — Make companion key strict mode the default when companion key is set `[CR-20, BR-04]`
**File:** Auth middleware / settings

```python
companion_key = os.getenv("ORKET_COMPANION_API_KEY", "")
strict_default = bool(companion_key)   # if key is set, default to strict
companion_strict = os.getenv("ORKET_COMPANION_KEY_STRICT", str(strict_default)).lower() == "true"
```

Update `.env.example` comment to reflect the new behavior.

---

## Sprint 4 — Operational Hygiene

### P4-01 — Enable actual baseline pruning in retention workflow `[BR-07]`
**File:** `.gitea/workflows/baseline-retention-weekly.yml`

Change the `Baseline Prune Plan (Dry Run)` step to actually apply after a dry-run summary is uploaded:

```yaml
- name: Baseline Prune (Apply)
  if: ${{ github.event_name == 'schedule' }}   # only on scheduled runs, not dispatch
  run: |
    python scripts/benchmarks/manage_baselines.py prune \
      --storage-root "..." \
      --keep-last "10"
      # no --dry-run
```

Keep the dispatch path as dry-run-only for manual inspection.

---

### P4-02 — Add log separator to `_collect_logs` `[CR-13]`
**File:** `scripts/gitea/inspect_local_runner_containers.py`

```python
return (result.stdout or "") + "\n--- stderr ---\n" + (result.stderr or "")
```

---

### P4-03 — Add `evidence_truncated` flag to `GuardViolation` `[CR-14]`

```python
raw_evidence = errors[0] if errors else None
evidence = (raw_evidence[:240] if raw_evidence and len(raw_evidence) > 240 else raw_evidence)
evidence_truncated = raw_evidence is not None and len(raw_evidence) > 240
```

Include `evidence_truncated` in the API response and in the GuardViolation dataclass.

---

### P4-04 — Make `--log-tail` configurable in container inspector `[CR-16]`

Add to `_build_parser`:
```python
parser.add_argument("--log-tail", type=int, default=40)
```

Pass `str(args.log_tail)` to the `docker logs` call.

---

### P4-05 — Document or fix `FIXTURE_SECONDARY` in acceptance tests `[BR-09]`
**File:** `tests/integration/test_system_acceptance_flow.py`

Either:
- Remove the constant if it has no effect
- Add a comment explaining exactly what plugin/runner reads it and what it does
- Add a test in the CI configuration that verifies this test file runs in the main test pass (not just in a secondary or optional pass)

---

## Ongoing / Architectural

### A-01 — Promote critical contract invariants to runtime assertions `[BR-01]`

For each invariant in the top 10 contracts listed in `CURRENT_AUTHORITY.md`, write a unit test that asserts the invariant directly from the code, not from a campaign artifact. Start with:
- Receipt schema version field presence
- run_id format (prefix + separator + structure)
- Ledger event monotonicity

These tests should live next to the schema definitions and run in the standard `pytest` suite, not as part of the parity campaign.

---

### A-02 — Add determinism campaign to PR gate (not just nightly) `[BR-02]`

The ODR determinism gate (`repro_odr_gate.py`) currently runs as a tool, not as a CI step on every PR. Add a lightweight 2-run subset (e.g., tasks 1–10) as a required PR check. This catches regressions before they reach main.

---

### A-03 — Add self-signed attestation warning to cutover readiness `[BR-03]`

In `check_protocol_enforce_cutover_readiness.py`, detect when all approvers are the self-signed value (`"Orket Core (local quality workspace)"`) and emit a `"self_attested_only": true` field in the readiness output. This becomes the hook for a future human-review requirement.

---

_End of action plan. 20 items across 4 sprints + 3 architectural items._
_Suggested sprint order: Sprint 1 → Sprint 3-01 → Sprint 2 → Sprint 3 (remainder) → Sprint 4 → Architectural (ongoing)._
