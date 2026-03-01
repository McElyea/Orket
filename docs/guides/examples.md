# Orket Examples (Transitional)

Last reviewed: 2026-02-27

This file is intentionally minimal. Canonical operational examples live in:
1. `docs/RUNBOOK.md`
2. `docs/API_FRONTEND_CONTRACT.md`
3. `docs/process/QUANT_SWEEP_RUNBOOK.md`

## Useful Quick Examples

### CLI help
```bash
python main.py --help
```

### API health
```bash
curl http://localhost:8082/health
```

### Webhook health
```bash
curl http://localhost:8080/health
```

### Kernel ODR determinism gate
```bash
python -m pytest tests/kernel/v1/test_odr_determinism_gate.py -k gate_pr -q
```

### Live ODR role matrix (model-in-loop)
```bash
python scripts/run_odr_live_role_matrix.py --out benchmarks/results/odr_live_role_matrix.json
```
