# Sidecar Parse Schema

Version: `sidecar.parse.v1`  
Last updated: 2026-02-21

## Purpose
Define a stable, backend-agnostic contract for hardware sidecar parse payloads inside quant sweep artifacts.

## Required Canonical Keys
Each `hardware_sidecar` object MUST include these snake_case keys:
1. `vram_total_mb`
2. `vram_used_mb`
3. `ttft_ms`
4. `prefill_tps`
5. `decode_tps`
6. `thermal_start_c`
7. `thermal_end_c`
8. `kernel_launch_ms`
9. `model_load_ms`
10. `sidecar_parse_status`
11. `sidecar_parse_errors`

## Optional Canonical Keys
If present, these fields MUST remain snake_case:
1. `pcie_throughput_gbps`
2. `cuda_graph_warmup_ms`
3. `gpu_clock_mhz`
4. `power_draw_watts`
5. `fan_speed_percent`

Missing optional keys MUST NOT fail execution by themselves.

## Parse Status Contract
Allowed `sidecar_parse_status` values:
1. `OK`
2. `OPTIONAL_FIELD_MISSING`
3. `NOT_APPLICABLE`
4. `REQUIRED_FIELD_MISSING`
5. `PARSE_ERROR`

`sidecar_parse_errors` MUST be a deterministic list of stable reason tokens (for example `missing:ttft_ms`).

## Alias Normalization
Sidecar providers MAY emit aliases, but the persisted summary contract MUST normalize to canonical snake_case keys.

Examples:
1. `prompt_tps` -> `prefill_tps`
2. `generation_tps` -> `decode_tps`
3. `temp_start_c` -> `thermal_start_c`
4. `temp_end_c` -> `thermal_end_c`

## Artifact Embedding
`run_quant_sweep.py` summaries MUST store normalized sidecar payloads under:
1. `sessions[*].per_quant[*].hardware_sidecar`

This contract is enforced by:
1. `scripts/check_sidecar_parse_policy.py`
2. `tests/application/test_check_sidecar_parse_policy.py`

