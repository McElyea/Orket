from __future__ import annotations

from pathlib import Path


def test_nightly_workflow_enforces_memory_determinism_contract_gates() -> None:
    """Layer: contract. Verifies the nightly memory comparator step is labeled as an identity smoke check, not runtime enforcement."""
    workflow_path = Path(".gitea/workflows/nightly-benchmark.yml")
    text = workflow_path.read_text(encoding="utf-8")

    required_commands = [
        "python scripts/benchmarks/check_memory_determinism.py",
        "python scripts/benchmarks/compare_memory_determinism.py",
        "benchmarks/results/benchmarks/nightly_memory_determinism_check.json",
        "benchmarks/results/benchmarks/nightly_memory_determinism_compare.json",
    ]
    missing = [cmd for cmd in required_commands if cmd not in text]
    assert not missing, "nightly workflow missing required memory determinism gates: " + ", ".join(missing)
    assert "Smoke: Memory Trace Fixture Contract And Comparator Identity Check" in text
    assert "Enforce Memory Determinism Contract" not in text
    assert "--left benchmarks/results/benchmarks/memory/memory_trace_fixture_left.json" in text
    assert "--right benchmarks/results/benchmarks/memory/memory_trace_fixture_right.json" in text
    assert "--left-retrieval benchmarks/results/benchmarks/memory/memory_retrieval_trace_fixture_left.json" in text
    assert "--right-retrieval benchmarks/results/benchmarks/memory/memory_retrieval_trace_fixture_right.json" in text
