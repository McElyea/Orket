from __future__ import annotations

REQUIRED_SIDECAR_FIELDS = [
    "vram_total_mb",
    "vram_used_mb",
    "ttft_ms",
    "prefill_tps",
    "decode_tps",
    "thermal_start_c",
    "thermal_end_c",
    "kernel_launch_ms",
    "model_load_ms",
]

OPTIONAL_SIDECAR_FIELDS = [
    "pcie_throughput_gbps",
    "cuda_graph_warmup_ms",
    "gpu_clock_mhz",
    "power_draw_watts",
    "fan_speed_percent",
]

VALID_SIDECAR_PARSE_STATUSES = {"OK", "OPTIONAL_FIELD_MISSING", "NOT_APPLICABLE"}

ROLE_MODEL_ENV_KEYS = [
    "ORKET_MODEL_REQUIREMENTS_ANALYST",
    "ORKET_MODEL_ARCHITECT",
    "ORKET_MODEL_LEAD_ARCHITECT",
    "ORKET_MODEL_CODER",
    "ORKET_MODEL_DEVELOPER",
    "ORKET_MODEL_REVIEWER",
    "ORKET_MODEL_CODE_REVIEWER",
    "ORKET_MODEL_INTEGRITY_GUARD",
    "ORKET_MODEL_OPERATIONS_LEAD",
]

