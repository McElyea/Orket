from __future__ import annotations

from pathlib import Path


def test_quant_sweep_full_workflow_enforces_policy_gates() -> None:
    workflow = Path(".gitea/workflows/quant-sweep-full-selfhosted.yml").read_text(encoding="utf-8")
    required_commands = [
        "python scripts/MidTier/check_quant_sweep_kpis.py",
        "python scripts/HighTier/check_lab_guards.py",
        "python scripts/MidTier/check_sidecar_parse_policy.py",
        "python scripts/MidTier/check_valid_run_policy.py",
        "python scripts/MidTier/analyze_vram_fragmentation.py",
        "python scripts/MidTier/prototype_model_selector.py",
    ]
    missing = [cmd for cmd in required_commands if cmd not in workflow]
    assert not missing, "quant-sweep full workflow missing required policy gates: " + ", ".join(missing)
