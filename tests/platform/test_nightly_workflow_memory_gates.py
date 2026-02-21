from __future__ import annotations

from pathlib import Path


def test_nightly_workflow_enforces_memory_determinism_contract_gates() -> None:
    workflow_path = Path(".gitea/workflows/nightly-benchmark.yml")
    text = workflow_path.read_text(encoding="utf-8")

    required_commands = [
        "python scripts/check_memory_determinism.py",
        "python scripts/compare_memory_determinism.py",
        "benchmarks/results/nightly_memory_determinism_check.json",
        "benchmarks/results/nightly_memory_determinism_compare.json",
    ]
    missing = [cmd for cmd in required_commands if cmd not in text]
    assert not missing, "nightly workflow missing required memory determinism gates: " + ", ".join(missing)

