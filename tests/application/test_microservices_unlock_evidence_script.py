from __future__ import annotations

from types import SimpleNamespace

from scripts.run_microservices_unlock_evidence import build_command_plan


def test_build_command_plan_contains_expected_steps() -> None:
    args = SimpleNamespace(
        models=["m1", "m2"],
        iterations=2,
        matrix_out="benchmarks/results/matrix.json",
        live_report_out="benchmarks/results/live.json",
        unlock_out="benchmarks/results/unlock.json",
        require_unlocked=False,
    )
    plan = build_command_plan(args)
    assert len(plan) == 4
    assert plan[0][:3] == ["python", "scripts/run_monolith_variant_matrix.py", "--execute"]
    assert plan[1][:3] == ["python", "-m", "scripts.run_live_acceptance_loop"]
    assert plan[2][:2] == ["python", "scripts/report_live_acceptance_patterns.py"]
    assert plan[3][:2] == ["python", "scripts/check_microservices_unlock.py"]


def test_build_command_plan_appends_require_unlocked_flag() -> None:
    args = SimpleNamespace(
        models=["m1"],
        iterations=1,
        matrix_out="a.json",
        live_report_out="b.json",
        unlock_out="c.json",
        require_unlocked=True,
    )
    plan = build_command_plan(args)
    assert "--require-unlocked" in plan[-1]
