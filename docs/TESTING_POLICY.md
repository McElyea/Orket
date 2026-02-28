# Orket Testing Policy

Last reviewed: 2026-02-27

## Test Philosophy
1. Prefer real system behavior over heavy mocking.
2. Favor deterministic assertions and machine-readable artifacts.
3. Keep policy/mechanics split clear:
   - Kernel tests validate deterministic mechanics.
   - Live tests validate model-in-loop behavior and quality trends.

## Mocking Rules
Mocks are allowed only when one of these applies:
1. External service failure injection (`timeout`, `500`, connection drop).
2. Cost/safety boundaries (no real billing/email side effects).
3. Clock control for deterministic time-window testing.

Use real local storage/filesystem where practical:
1. `tmp_path` for filesystem tests.
2. `sqlite` temp DB for repository behavior.

## Required Test Lanes
1. `unit` lane:
```bash
python -m pytest tests/core tests/application tests/adapters tests/interfaces tests/platform -q
```
2. `integration` lane:
```bash
python -m pytest tests/integration tests/runtime tests/contracts -q
```
3. `acceptance` lane:
```bash
python -m pytest tests/acceptance tests/kernel/v1/test_odr_refinement_behavior.py -q
```
4. `live` lane (opt-in):
```bash
python -m pytest tests/live -q
```

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
python scripts/run_cli_regression_smoke.py --out benchmarks/results/cli_regression_smoke.json
```
2. Security canary:
```bash
python scripts/security_canary.py
```
3. Model-streaming scenario gate:
```bash
python scripts/run_model_streaming_gate.py --provider-mode stub --timeout 20
```

## Completion Standard
A change is test-complete when:
1. Relevant lane tests pass.
2. Determinism gates pass for affected deterministic subsystems.
3. Any new behavior has direct assertions (not only log inspection).
