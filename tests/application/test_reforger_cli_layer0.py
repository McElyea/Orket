from __future__ import annotations

import json
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main


def _seed_base_pack(base_pack: Path) -> None:
    base_pack.mkdir(parents=True, exist_ok=True)
    (base_pack / "pack.json").write_text(
        json.dumps({"id": "base_truth", "version": "1.0.0"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (base_pack / "system.txt").write_text("Follow hard rules.\n", encoding="utf-8")
    (base_pack / "constraints.yaml").write_text("rules: []\n", encoding="utf-8")


def _seed_mode_and_suite(root: Path, mode_id: str) -> None:
    modes = root / "modes"
    suites = root / "suites" / mode_id
    modes.mkdir(parents=True, exist_ok=True)
    suites.mkdir(parents=True, exist_ok=True)
    (modes / f"{mode_id}.yaml").write_text(
        "\n".join(
            [
                f"mode_id: {mode_id}",
                "description: test mode",
                "hard_rules:",
                "  - never fabricate",
                "soft_rules:",
                "  - stay concise",
                "rubric:",
                "  quality: 1.0",
                "required_outputs:",
                "  - refusal_reason",
                f"suite_ref: suites/{mode_id}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (suites / "cases.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "case_id": "C1",
                        "prompt": "test",
                        "expectations": {"hard": ["must_include:Follow"], "soft": ["prefer_include:concise"]},
                    }
                ),
                json.dumps({"case_id": "C2", "prompt": "test2", "expectations": {"hard": [], "soft": []}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (suites / "rubric.yaml").write_text("quality: 1.0\n", encoding="utf-8")


def test_reforge_init_run_and_determinism(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    reforge_root = tmp_path / "reforge"
    mode_id = "truth_or_refuse"
    model_id = "qwen2.5"
    _seed_mode_and_suite(reforge_root, mode_id)
    base_pack = reforge_root / "packs" / "base" / mode_id
    _seed_base_pack(base_pack)

    rc = main(
        [
            "reforge",
            "init",
            "--mode",
            mode_id,
            "--model",
            model_id,
            "--from",
            str(base_pack),
        ]
    )
    assert rc == 0

    run_args = [
        "reforge",
        "run",
        "--mode",
        mode_id,
        "--model",
        model_id,
        "--seed",
        "7",
        "--budget",
        "3",
        "--baseline",
        str(reforge_root / "packs" / "model" / model_id / mode_id),
        "--save-best",
        "false",
    ]
    rc1 = main(run_args)
    rc2 = main(run_args)
    assert rc1 in (0, 1)
    assert rc2 in (0, 1)

    run_root = reforge_root / "runs"
    bundles = sorted([item for item in run_root.iterdir() if item.is_dir()], key=lambda path: path.name)
    assert len(bundles) == 1
    bundle = bundles[0]
    summary = (bundle / "summary.txt").read_text(encoding="utf-8")
    scoreboard = (bundle / "eval" / "scoreboard.csv").read_text(encoding="utf-8")
    diff = (bundle / "diff" / "best_vs_baseline.md").read_text(encoding="utf-8")
    assert "Orket Reforge Summary" in summary
    assert "candidate_id,score,hard_fail_count,soft_fail_count" in scoreboard
    assert "# Best vs Baseline" in diff

    # Re-run with same inputs should keep deterministic artifact content.
    rc3 = main(run_args)
    assert rc3 in (0, 1)
    summary2 = (bundle / "summary.txt").read_text(encoding="utf-8")
    scoreboard2 = (bundle / "eval" / "scoreboard.csv").read_text(encoding="utf-8")
    diff2 = (bundle / "diff" / "best_vs_baseline.md").read_text(encoding="utf-8")
    assert summary == summary2
    assert scoreboard == scoreboard2
    assert diff == diff2


def test_reforge_open_last_best_effort(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reforge" / "runs").mkdir(parents=True, exist_ok=True)
    rc = main(["reforge", "open", "last"])
    assert rc == 0


def test_reforge_run_exit_code_hard_fail_and_artifact_completeness(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    reforge_root = tmp_path / "reforge"
    mode_id = "lies_only"
    model_id = "gemma3"
    _seed_mode_and_suite(reforge_root, mode_id)
    base_pack = reforge_root / "packs" / "base" / mode_id
    _seed_base_pack(base_pack)

    # Force deterministic hard failure by requiring a missing token.
    suites = reforge_root / "suites" / mode_id
    (suites / "cases.jsonl").write_text(
        json.dumps(
            {
                "case_id": "HF1",
                "prompt": "force hard fail",
                "expectations": {"hard": ["must_include:NON_EXISTENT_TOKEN"], "soft": []},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "reforge",
                "init",
                "--mode",
                mode_id,
                "--model",
                model_id,
                "--from",
                str(base_pack),
            ]
        )
        == 0
    )

    rc = main(
        [
            "reforge",
            "run",
            "--mode",
            mode_id,
            "--model",
            model_id,
            "--seed",
            "11",
            "--budget",
            "2",
            "--baseline",
            str(reforge_root / "packs" / "model" / model_id / mode_id),
            "--save-best",
            "false",
        ]
    )
    assert rc == 1

    runs = sorted([item for item in (reforge_root / "runs").iterdir() if item.is_dir()], key=lambda p: p.name)
    assert runs
    bundle = runs[-1]
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "summary.txt").is_file()
    assert (bundle / "eval" / "scoreboard.csv").is_file()
    assert (bundle / "diff" / "best_vs_baseline.md").is_file()
    assert (bundle / "candidates" / "0001_pack_resolved" / "mutation.json").is_file()
    assert (bundle / "candidates" / "0002_pack_resolved" / "mutation.json").is_file()
