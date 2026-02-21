from __future__ import annotations

import json
from pathlib import Path


def test_quant_sweep_preset_configs_include_required_controls() -> None:
    config_names = [
        "quant_sweep_logic_only.json",
        "quant_sweep_refactor_heavy.json",
        "quant_sweep_mixed.json",
    ]
    required_keys = {
        "models",
        "quants",
        "task_bank",
        "runs_per_quant",
        "seed",
        "threads",
        "affinity_policy",
        "warmup_steps",
        "context_sweep_profile",
        "context_sweep_contexts",
    }
    configs_root = Path("benchmarks/configs")
    for name in config_names:
        path = configs_root / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), name
        assert required_keys.issubset(payload.keys()), name
        assert isinstance(payload["models"], list) and payload["models"], name
        assert isinstance(payload["quants"], list) and payload["quants"], name
        assert isinstance(payload["context_sweep_contexts"], list) and payload["context_sweep_contexts"], name
