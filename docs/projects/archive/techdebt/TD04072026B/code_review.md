# Orket — Brutal Code Review
_April 2026 — New issues only; W3-series items from prior review excluded._

---

## 🔴 Critical

### CR-01 — Benchmark determinism hash includes stderr — `scripts/benchmarks/run_benchmark_suite.py`

In `_run_once`:

```python
raw_output = (result.stdout or "") + "\n" + (result.stderr or "")
```

This string is then normalized and SHA-256 hashed as the "determinism hash." Any stderr noise — Python deprecation warnings, locale output, pip upgrade hints — will cause a hash mismatch between runs and report false non-determinism (or, worse, mask real non-determinism when the noise happens to be identical). Stdout and stderr should be hashed separately or stderr should be stripped entirely for the canonical hash. The combined string may be kept for debugging preview, but it must not be the hash input.

---

### CR-02 — `dsl_blocks[i + 1]` IndexError on odd split — `orket/application/services/tool_parser.py`

```python
dsl_blocks = re.split(r"(?:\[|TOOL:\s*)(write_file|...)\s*", text)
for i in range(1, len(dsl_blocks), 2):
    tool_name = dsl_blocks[i]
    block_content = dsl_blocks[i + 1]   # ← crash if text ends with a tool marker
```

If model output ends with a bare tool marker and no following content block, `len(dsl_blocks)` is even and `dsl_blocks[i + 1]` raises `IndexError`. This is a latent crash in the legacy DSL fallback that fires on any truncated or malformed model response. Fix: guard with `if i + 1 < len(dsl_blocks)`.

---

### CR-03 — Path traversal guard broken when `workspace_root` is unresolved — `orket/runtime/execution_pipeline.py` / `_resolve_command_cwd`

```python
resolved = candidate.resolve()
if not resolved.is_relative_to(workspace_root):  # workspace_root may contain symlinks or ..
    return None
```

`Path.is_relative_to` compares string prefixes on resolved vs potentially unresolved paths. If the caller passes `workspace_root = Path(".")` or a path with `..` components, `is_relative_to` may return `True` for paths that are actually outside the root (or `False` for paths that are inside it). The fix is one line: `workspace_root = workspace_root.resolve()` before the comparison.

---

### CR-04 — Single run per task means determinism rate is always 1.0 — `benchmarks/published/General/live_100_determinism_report.json`

```json
"runs_per_task": 1,
"determinism_rate": 1.0
```

A single execution always produces exactly one hash. `unique_hashes == 1` when `run_count == 1` is a mathematical guarantee, not a measurement. The published report's `determinism_rate: 1.0` over 100 tasks is therefore meaningless — it proves nothing. Any task run exactly once will be reported as deterministic. Minimum required runs for a valid determinism measurement is 2. This is a silent validity problem with published benchmark artifacts.

---

## 🟠 High

### CR-05 — `process.returncode or 0` silently maps running/None process to success — `scripts/gitea/inspect_local_runner_containers.py`

```python
returncode=int(process.returncode or 0),
```

`asyncio.subprocess.Process.returncode` is `None` when the process has not yet terminated. `None or 0` evaluates to `0`, making an in-flight or never-awaited process look like it exited successfully. This can cause cleanup decisions to be made on stale Docker inspect data. Use `process.returncode if process.returncode is not None else -1`.

---

### CR-06 — `build_runtime_guard_contract` drops all errors beyond the first — `orket/application/guards/`

```python
evidence=(errors[0][:240] if errors else None),
```

The `GuardContract` violations list always contains exactly one `GuardViolation` regardless of how many errors were collected. All errors after `errors[0]` are silently discarded. An agent run that fails multiple guard rules will only ever surface one in the API response and logs. Fix: either emit one violation per error, or concatenate all error messages into the evidence field with a truncation indicator.

---

### CR-07 — `_json_assertion_matches` silently returns False for unknown ops

```python
if op == "lte":
    return actual_num <= expected_num
return False   # ← unknown op silently treated as "never matches"
```

If a task fixture specifies an unknown assertion op (e.g., `"exists"`, `"startswith"`, or a typo like `"gte "` with a trailing space), the assertion silently evaluates to False. This means a misconfigured fixture will always fail its assertions without any diagnostic that the op itself is invalid. A bad fixture will look like a real runtime failure. Fix: raise `ValueError(f"unknown assertion op: {op!r}")` or append an explicit failure message.

---

### CR-08 — `_permute_fixture` deep-copies via JSON round-trip — `tools/repro_odr_gate.py`

```python
payload = json.loads(json.dumps(fixture))
```

For each permutation index this serializes and deserializes the entire fixture, which is O(n) in fixture size and garbage-collects a full copy each time. More critically, any non-JSON-serializable value in the fixture (e.g., a `Path`, `datetime`, or custom type accidentally left in test data) will silently be coerced or raise during the dump, mutating the fixture without warning. Use `copy.deepcopy(fixture)` instead.

---

### CR-09 — `_load_registered_runners` sqlite3 connection has no timeout — `scripts/gitea/inspect_local_runner_containers.py`

```python
connection = sqlite3.connect(path)
```

`sqlite3.connect` defaults to a 5-second timeout, but when Gitea is actively writing (e.g., a runner is registering or a job is finishing), the Gitea SQLite DB may be locked. The cleanup tool will block, potentially blocking the entire CI leak-gate check. Pass `timeout=10` explicitly and wrap with a `try/except OperationalError` to degrade gracefully instead of blocking.

---

### CR-10 — Inline Python heredocs in CI YAML are untestable and bypass linting — Multiple `.gitea/workflows/*.yml`

Several CI jobs (quality gate, sandbox acceptance, migration smoke) run substantial Python logic via:

```yaml
run: |
  python - <<'PY'
  import json, os, subprocess, sys
  ...
  PY
```

These blocks are invisible to `ruff`, cannot be unit-tested, have no type annotations, and can silently break when library APIs change. The sandbox leak gate, migration validator, and memory fixture smoke are all implemented this way. Each should be extracted to a named script in `scripts/ci/` and invoked by the workflow step.

---

### CR-11 — `returncode 137` (OOM/SIGKILL) indistinguishable from command_failed — `orket/runtime/execution_pipeline.py`

```python
def _failure_class_from_returncode(returncode: int) -> str:
    if returncode == 124: return "timeout"
    if returncode in {126, 127}: return "missing_runtime"
    return "command_failed"
```

Exit code 137 is `SIGKILL` (128 + 9), typically indicating OOM termination. In containerized sandbox environments this is a common and distinct failure mode. Classifying it as `command_failed` means operators cannot distinguish "my agent script crashed" from "the sandbox was OOM-killed." Add `if returncode == 137: return "oom_killed"`.

---

### CR-12 — `normalize_json_stringify` is O(n²) on adversarial model output — `orket/application/services/tool_parser.py`

The paren-matching while loop scans character-by-character from each `JSON.stringify(` occurrence to find the closing paren. With no depth limit and no early exit for implausibly large expressions, a model response containing many `JSON.stringify(` without closing parens will scan the remainder of the string for each one. A 10 KB model response with 50 unclosed occurrences triggers 500 KB of scanning. Add a max-expression-length guard (e.g., abort if `pos - expr_start > 4096`).

---

## 🟡 Medium

### CR-13 — `_collect_logs` concatenates stdout and stderr without separator

```python
return (result.stdout or "") + (result.stderr or "")
```

The log tail returned for container classification mixes stdout and stderr with no delimiter. Any code that later analyzes the tail to detect the `KNOWN_RETRY_SIGNATURE` string `"instance address is empty"` may match it in either stream, or fail to match it if it spans the boundary of the concatenation. Use a clear separator: `"\n--- stderr ---\n"`.

---

### CR-14 — `GuardViolation` evidence is silently truncated at 240 chars with no indicator

```python
evidence=(errors[0][:240] if errors else None)
```

240 characters is often insufficient for a meaningful stack trace or JSON diff. The truncation is silent — the API consumer has no way to know they're seeing a partial error. Either increase the limit, expose `evidence_truncated: bool` in the response, or log the full error separately before truncating.

---

### CR-15 — `_resolve_json_path` only supports dot notation; this is undocumented

The JSON path resolver in `_json_assertion_matches` splits on `.` only:

```python
for token in [segment for segment in str(path).split(".") if segment]:
```

Paths like `token_metrics.counts.prompt_tokens` work, but paths with array subscripts (`events[0].role`) or keys containing dots will fail with a `KeyError`. Task fixtures that evolve to need array access will silently fail assertions. This should be documented on the path format, or a proper JSONPath library (or at minimum bracket-notation support) should be used.

---

### CR-16 — `docker logs --tail 40` is hardcoded

```python
result = await run_command("docker", "logs", "--tail", "40", container_name)
```

40 lines is arbitrary. A rapidly restart-looping container may span 3–4 restarts in 40 lines, mixing log contexts from different runs. This should be configurable via a `--log-tail` CLI argument defaulting to 40, so operators can increase it when debugging persistent stray runners.

---

### CR-17 — `AcceptanceProvider` in tests uses only backtick-wrapped JSON, bypassing stack JSON extractor path — `tests/integration/test_system_acceptance_flow.py`

```python
content='```json\n{"tool": "write_file", ...}\n```'
```

All acceptance tests use the markdown code-fence format exclusively. The primary stack-based JSON extractor path (strategy `"stack_json"`) is never exercised by integration tests. A regression in the stack extractor would not be caught by these tests because the backtick format goes through a different (regex-based) extraction path. At least one acceptance test should use raw JSON output from the mock provider.

---

### CR-18 — `ORKET_ALLOW_INSECURE_NO_API_KEY` has no runtime warning when set in non-local envs

The flag is documented in `.env.example` as "Insecure local override ONLY (not for CI/prod)" — but the code has no enforcement of that intent. If this flag is set in a staging or production environment (e.g., via a copied `.env` file), the API silently becomes unauthenticated. The setting should emit a loud `CRITICAL` log warning on startup when set to `true`, and should optionally refuse to start if an `ORKET_ENV=production` flag is also set.

---

### CR-19 — Module-level `TestClient(app)` in API test files captures env at import time — `tests/interfaces/test_api*.py`

```python
client = TestClient(app)  # module-level
```

`TestClient` is instantiated when the module is imported, before `monkeypatch.setenv` calls in individual tests run. The `app` object and its middleware may cache environment variables (e.g., `ORKET_API_KEY`, `ORKET_ENABLE_NERVOUS_SYSTEM`) from import time rather than from per-test monkeypatching. Some tests compensate by re-setting env vars in the test body, but the order-of-operations is fragile. Consider using a pytest fixture that creates the `TestClient` fresh per test.

---

### CR-20 — Companion key strict mode is opt-in (fail-open default)

```env
# ORKET_COMPANION_KEY_STRICT=false
```

The default is `false`, meaning `ORKET_API_KEY` remains valid on companion routes even when `ORKET_COMPANION_API_KEY` is set. This is the opposite of what operators who bother to configure a scoped companion key intend. The secure default should be strict mode once a companion key is configured — i.e., if `ORKET_COMPANION_API_KEY` is set, auto-enable strict mode unless explicitly overridden with `ORKET_COMPANION_KEY_STRICT=false`.

---

## 🔵 Low / Cleanup

### CR-21 — `sorted(names)` in `_list_runner_container_names` provides no useful stability guarantee

Container names with random UUID suffixes (e.g., `gitea-runner-abc123`) sort lexicographically but this ordering is unrelated to creation time or registration order. The sort exists for "determinism" in the output report but provides no actual semantic ordering. Replace with sort-by-creation-time via inspect data, or document that the ordering is arbitrary.

---

### CR-22 — `_run_once` passes `execution_mode` and `runtime_target` redundantly as both positional args and as format kwargs

```python
command = runner_template.format(
    runtime_target=runtime_target,
    execution_mode=execution_mode,
    venue=runtime_target,        # ← duplicate
    flow=execution_mode,         # ← duplicate
    ...
)
```

`venue` and `flow` are aliases for `runtime_target` and `execution_mode`. Both sets of names are kept for backward compat with older runner templates, but this is undocumented. A comment explaining the alias relationship, or a deprecation path for the old names, would reduce confusion.

---

### CR-23 — `stale_threshold_runs: 3` in `.ci/ci_failure_policy.json` has no documented enforcement path

The field exists and is presumably consumed by some CI policy script, but it is not obvious which script reads it or what happens when the threshold is exceeded. If this is enforced via a webhook or a scheduled job, that enforcement path should be linked from the policy file itself (a `"enforcement_script"` field, or a comment in the JSON).

---

### CR-24 — `self-approver` in protocol enforce-window signoff

```
"Approver: Orket Core (local quality workspace)"
```

The system signs off its own rollout windows. For pre-production, this is pragmatic. But the signoff schema has an `approver` field that implies a human or external authority. This should be explicitly documented as "automated self-attestation" in the schema, and the cutover readiness gate should emit a warning (not a hard failure) when all signoffs are self-signed.

---

### CR-25 — `_extract_last_json_object` name implies positional selection; behavior is unclear

The function `_extract_last_json_object` is called on combined `stdout + "\n" + stderr`. The name implies it extracts "the last" object, but if the runner emits diagnostic JSON before the final result JSON, the extraction logic must be verified to actually get the final one. If extraction fails silently (returns `{}`), the telemetry normalization will fall back to defaults and the run will look like it had zero cost and zero latency rather than surfacing an extraction error.

---

_End of code review. 25 issues identified: 4 critical, 8 high, 8 medium, 5 low._
