from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_script_module(module_name: str, script_path: str) -> ModuleType:
    path = Path(script_path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_benchmark_suite_invokes_memory_checks_when_paths_are_provided(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module("run_benchmark_suite_memory", "scripts/run_benchmark_suite.py")
    recorded: list[list[str]] = []

    def _fake_run(cmd: list[str]) -> None:
        recorded.append(list(cmd))

    monkeypatch.setattr(module, "_run", _fake_run)
    raw_out = tmp_path / "raw.json"
    scored_out = tmp_path / "scored.json"
    check_out = tmp_path / "memory_check.json"
    compare_out = tmp_path / "memory_compare.json"
    trace = tmp_path / "memory_trace.json"
    retrieval = tmp_path / "memory_retrieval_trace.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_benchmark_suite.py",
            "--runner-template",
            "python scripts/determinism_control_runner.py --task {task_file} --venue {venue} --flow {flow}",
            "--raw-out",
            str(raw_out),
            "--scored-out",
            str(scored_out),
            "--memory-trace",
            str(trace),
            "--memory-retrieval-trace",
            str(retrieval),
            "--memory-check-out",
            str(check_out),
            "--memory-compare-left",
            str(trace),
            "--memory-compare-right",
            str(trace),
            "--memory-compare-left-retrieval",
            str(retrieval),
            "--memory-compare-right-retrieval",
            str(retrieval),
            "--memory-compare-out",
            str(compare_out),
        ],
    )

    rc = module.main()
    assert rc == 0
    assert len(recorded) == 4
    assert recorded[2][0:2] == ["python", "scripts/check_memory_determinism.py"]
    assert "--trace" in recorded[2]
    assert "--retrieval-trace" in recorded[2]
    assert recorded[3][0:2] == ["python", "scripts/compare_memory_determinism.py"]
    assert "--left-retrieval" in recorded[3]
    assert "--right-retrieval" in recorded[3]

