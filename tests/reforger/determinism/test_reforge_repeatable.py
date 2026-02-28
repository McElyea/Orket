from __future__ import annotations

import hashlib
import json
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main


def _seed_base_pack(base_pack: Path) -> None:
    base_pack.mkdir(parents=True, exist_ok=True)
    (base_pack / "pack.json").write_text('{"id":"base_truth","version":"1.0.0"}\n', encoding="utf-8")
    (base_pack / "system.txt").write_text("Follow truth constraints.\n", encoding="utf-8")
    (base_pack / "constraints.yaml").write_text("rules: []\n", encoding="utf-8")


def _seed_mode_suite(root: Path, mode_id: str) -> None:
    mode_dir = root / "modes"
    suite_dir = root / "suites" / mode_id
    mode_dir.mkdir(parents=True, exist_ok=True)
    suite_dir.mkdir(parents=True, exist_ok=True)
    (mode_dir / f"{mode_id}.yaml").write_text(
        "\n".join(
            [
                f"mode_id: {mode_id}",
                "description: truth only",
                "hard_rules:",
                "  - output_exactly_one_of:YES|NO",
                "soft_rules:",
                "  - output_prefer_include:YES",
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
    (suite_dir / "cases.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "case_id": "R1",
                        "prompt": "answer",
                        "expectations": {"hard": ["output_exactly_one_of:YES|NO"], "soft": ["output_prefer_include:YES"]},
                    }
                ),
                json.dumps(
                    {
                        "case_id": "R2",
                        "prompt": "unknown",
                        "expectations": {"hard": ["must_refuse_if_unknown"], "soft": ["output_prefer_include:refusal_reason"]},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (suite_dir / "rubric.yaml").write_text("quality: 1.0\n", encoding="utf-8")
    (suite_dir / "fake_outputs.json").write_text(
        json.dumps(
            {
                f"{mode_id}:R1": "YES",
                f"{mode_id}:R2": "REFUSE\nrefusal_reason:unknown",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _tree_digest(path: Path) -> str:
    payload: list[bytes] = []
    files = sorted(item for item in path.rglob("*") if item.is_file())
    for file_path in files:
        rel = str(file_path.relative_to(path)).replace("\\", "/")
        payload.append(rel.encode("utf-8"))
        payload.append(b"\n")
        payload.append(hashlib.sha256(file_path.read_bytes()).hexdigest().encode("utf-8"))
        payload.append(b"\n")
    return hashlib.sha256(b"".join(payload)).hexdigest()


def _manifest_without_timestamps(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = dict(payload)
        payload.pop("timestamps", None)
    return payload


def test_reforge_repeatable_fake_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    reforge = tmp_path / "reforge"
    mode_id = "truth_only"
    model_id = "fake"
    _seed_mode_suite(reforge, mode_id)
    base = reforge / "packs" / "base" / mode_id
    _seed_base_pack(base)

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
                str(base),
            ]
        )
        == 0
    )

    args = [
        "reforge",
        "run",
        "--mode",
        mode_id,
        "--model",
        model_id,
        "--seed",
        "123",
        "--budget",
        "4",
        "--baseline",
        str(reforge / "packs" / "model" / model_id / mode_id),
        "--save-best",
        "false",
    ]
    rc1 = main(args)
    assert rc1 == 0

    runs = sorted((reforge / "runs").iterdir(), key=lambda p: p.name)
    assert len(runs) == 1
    run = runs[0]
    snapshot_summary = (run / "summary.txt").read_text(encoding="utf-8")
    snapshot_scoreboard = (run / "eval" / "scoreboard.csv").read_text(encoding="utf-8")
    snapshot_diff = (run / "diff" / "best_vs_baseline.md").read_text(encoding="utf-8")
    snapshot_candidates = _tree_digest(run / "candidates")
    snapshot_manifest = _manifest_without_timestamps(run / "manifest.json")
    scoreboard_lines = [line.strip() for line in snapshot_scoreboard.splitlines() if line.strip()]
    assert len(scoreboard_lines) >= 2
    assert scoreboard_lines[1].startswith("0001,")

    rc2 = main(args)
    assert rc2 == 0
    assert snapshot_summary == (run / "summary.txt").read_text(encoding="utf-8")
    assert snapshot_scoreboard == (run / "eval" / "scoreboard.csv").read_text(encoding="utf-8")
    assert snapshot_diff == (run / "diff" / "best_vs_baseline.md").read_text(encoding="utf-8")
    assert snapshot_candidates == _tree_digest(run / "candidates")
    assert snapshot_manifest == _manifest_without_timestamps(run / "manifest.json")
