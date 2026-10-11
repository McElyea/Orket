# Orket Testing Policy

Last reviewed: 2026-10-10

## Test Philosophy
1. Live provider-backed proof has the highest authority for model, provider, orchestration, replay, runtime, and operator-surface behavior.
2. Prefer real system behavior over heavy mocking.
3. Favor deterministic assertions and machine-readable artifacts.
4. Unit tests have the lowest authority and should cover the bare minimum deterministic logic needed to protect refactors.
5. Prefer one truthful live test over many structural tests that do not exercise the real path.
6. Structural tests do not replace live proof.
7. Keep policy/mechanics split clear:
   - Kernel tests validate deterministic mechanics.
   - Live tests validate model-in-loop behavior and quality trends.
8. The default pytest suite must fail closed on real Docker sandbox creation. Only explicit live sandbox acceptance work may create `orket-sandbox-*` resources.

## Live Definition

In this repo, a run may be labeled `live` only when all of the following are true:
1. it uses a real model through a real provider/runtime path (llama.cpp by default; LM Studio or Ollama when explicitly selected)
2. it executes shipped Orket runtime code against a real filesystem workspace
3. it produces fresh runtime artifacts or operator-visible outputs from that run

These do not qualify as `live`:
1. mocks
2. fakes
3. shims
4. provider-bypassed, monkeypatched, replayed, or fixture-simulated model paths
5. provider-free runs
6. dry-run, import-only, compile-only, or structural checks without a live model path
7. unit, contract, integration, or end-to-end tests that do not satisfy the conditions above

Non-live tests still count for their own lane. They must not be described as live proof.
Real CLI, HTTP, storage and installation checks can establish integration behavior
without model inference; label that scope explicitly. A controlled provider's
response does not become live model proof because the HTTP transport is real.

## Mocking Rules
Mocks are never proof of live behavior.

Mocks are allowed only when one of these applies:
1. External service failure injection (`timeout`, `500`, connection drop).
2. Cost/safety boundaries (no real billing/email side effects).
3. Clock control for deterministic time-window testing.

Use real local storage/filesystem where practical:
1. `tmp_path` for filesystem tests.
2. `sqlite` temp DB for repository behavior.

## Required Test Lanes

Each new or modified test must carry exactly one collected layer marker:
`unit`, `contract`, `integration` or `end_to_end`. Directory names do not assign
layers: for example, `tests/interfaces` contains contract and integration cases.
The marker definitions are in `pyproject.toml`; enforce them with
`python scripts/governance/enforce_test_taxonomy.py --strict`.

Run the relevant layer or a narrower path selection appropriate to the change:

1. Unit:
```bash
python -m pytest tests -m unit -q
```
2. Contract:
```bash
python -m pytest tests -m contract -q
```
3. Integration:
```bash
python -m pytest tests -m integration -q
```
4. End-to-end:
```bash
python -m pytest tests -m end_to_end -q
```

`tests/acceptance` and `tests/live` remain useful path selections; their names do
not replace collected layer markers or the live-proof requirements above. Some
provider-specific cases require explicit opt-in/environment inputs; inspect their
requirements and record skips as unverified work, not passing live acceptance.
The default full command remains `python -m pytest -q`. CI's exact selected
commands and 89-percent coverage floor live in `.gitea/workflows/quality.yml`.
Coverage data defaults to `.tmp/quality/.coverage`; the tracked root `.coverage`
is historical data, not a current result.

## Docker Sandbox Guard
1. `tests/conftest.py` sets `ORKET_DISABLE_SANDBOX=1` for the general pytest suite.
2. Tests that intentionally exercise live sandbox lifecycle must opt in explicitly and must prove cleanup against actual Docker containers, networks, and volumes, not only `docker-compose ls`.

## Determinism Gates
1. ODR determinism gate (required for kernel ODR changes):
```bash
python -m pytest tests/kernel/v1/test_odr_determinism_gate.py -k gate_pr -q
```
2. Nightly tier:
```bash
python -m pytest tests/kernel/v1/test_odr_determinism_gate.py -k gate_nightly -q
```

## CLI and Security Smoke
1. CLI regression smoke:
```bash
python scripts/governance/run_cli_regression_smoke.py --out benchmarks/results/governance/cli_regression_smoke.json
```
2. Current API authentication and webhook controls:
```bash
python -m pytest -q tests/interfaces/test_api.py -k "health_check or version or insecure or websocket_events"
python -m pytest -q tests/interfaces/test_webhook_factory.py
```
These are contract/integration controls, not live model proof. The legacy
`scripts/security/security_canary.py` still references removed module-level app
singletons; `scripts/governance/release_smoke.py` invokes that broken path by
default. Do not report either as passing acceptance. Their migration remains
tooling debt; these scoped controls do not establish whole-release readiness.
3. Model-streaming scenario gate:
```bash
python scripts/streaming/run_model_streaming_gate.py --provider-mode stub --timeout 20
```

## Completion Standard
A change is test-complete when:
1. Changes touching model, provider, orchestration, replay, runtime, or operator-surface behavior have relevant live proof or an explicit live blocker classification.
2. Relevant lane tests pass.
3. Determinism gates pass for affected deterministic subsystems.
4. Any new behavior has direct assertions (not only log inspection).
5. Structural lane passes are not presented as a substitute for missing live proof.
