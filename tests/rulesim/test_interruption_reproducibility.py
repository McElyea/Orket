from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _run_live_process(config_path: Path, workspace: Path, result_out: Path) -> subprocess.Popen[str]:
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.Popen(
        [
            sys.executable,
            "scripts/rulesim/run_live_rulesim.py",
            "--config",
            str(config_path),
            "--workspace",
            str(workspace),
            "--result-out",
            str(result_out),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _checkpoint_files(path: Path) -> list[Path]:
    return sorted(path.glob("episode_*.json"))


def test_graceful_interruption_reproducible_completed_episodes(tmp_path: Path) -> None:
    stop_file = tmp_path / "stop.signal"
    checkpoint_a = tmp_path / "ckpt_a"
    checkpoint_b = tmp_path / "ckpt_b"
    workspace_a = tmp_path / "workspace_a"
    workspace_b = tmp_path / "workspace_b"
    config_graceful = {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "loop",
        "run_seed": 1234,
        "episodes": 200,
        "max_steps": 6,
        "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
        "scenario": {"turn_order": ["agent_0"]},
        "artifact_policy": "none",
        "checkpoint_dir": str(checkpoint_a),
        "graceful_cancel_file": str(stop_file),
        "episode_delay_ms": 20,
    }
    cfg_a = tmp_path / "graceful.json"
    cfg_a.write_text(json.dumps(config_graceful), encoding="utf-8")
    result_a = tmp_path / "result_a.json"
    proc = _run_live_process(cfg_a, workspace_a, result_a)
    time.sleep(1.2)
    stop_file.write_text("stop\n", encoding="utf-8")
    stdout, stderr = proc.communicate(timeout=60)
    assert proc.returncode == 0, f"stdout={stdout}\nstderr={stderr}"
    partial = _checkpoint_files(checkpoint_a)
    assert 1 <= len(partial) < 200
    payload_a = json.loads(result_a.read_text(encoding="utf-8"))
    assert payload_a["interrupted"] is True

    config_full = dict(config_graceful)
    config_full.pop("graceful_cancel_file")
    config_full["checkpoint_dir"] = str(checkpoint_b)
    config_full["episode_delay_ms"] = 0
    cfg_b = tmp_path / "full.json"
    cfg_b.write_text(json.dumps(config_full), encoding="utf-8")
    result_b = tmp_path / "result_b.json"
    proc2 = _run_live_process(cfg_b, workspace_b, result_b)
    stdout2, stderr2 = proc2.communicate(timeout=60)
    assert proc2.returncode == 0, f"stdout={stdout2}\nstderr={stderr2}"
    full = _checkpoint_files(checkpoint_b)
    assert len(full) == 200
    for left, right in zip(partial, full[: len(partial)], strict=True):
        assert left.read_text(encoding="utf-8") == right.read_text(encoding="utf-8")


def test_hard_kill_reproducible_completed_episodes(tmp_path: Path) -> None:
    checkpoint_a = tmp_path / "kill_ckpt_a"
    checkpoint_b = tmp_path / "kill_ckpt_b"
    workspace_a = tmp_path / "kill_workspace_a"
    workspace_b = tmp_path / "kill_workspace_b"
    config = {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "loop",
        "run_seed": 777,
        "episodes": 300,
        "max_steps": 6,
        "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
        "scenario": {"turn_order": ["agent_0"]},
        "artifact_policy": "none",
        "checkpoint_dir": str(checkpoint_a),
        "episode_delay_ms": 20,
    }
    cfg_a = tmp_path / "kill_a.json"
    cfg_a.write_text(json.dumps(config), encoding="utf-8")
    result_a = tmp_path / "kill_result_a.json"
    proc = _run_live_process(cfg_a, workspace_a, result_a)
    time.sleep(1.2)
    proc.kill()
    proc.communicate(timeout=60)
    partial = _checkpoint_files(checkpoint_a)
    assert 1 <= len(partial) < 300

    config_b = dict(config)
    config_b["checkpoint_dir"] = str(checkpoint_b)
    config_b["episode_delay_ms"] = 0
    cfg_b = tmp_path / "kill_b.json"
    cfg_b.write_text(json.dumps(config_b), encoding="utf-8")
    result_b = tmp_path / "kill_result_b.json"
    proc2 = _run_live_process(cfg_b, workspace_b, result_b)
    stdout2, stderr2 = proc2.communicate(timeout=60)
    assert proc2.returncode == 0, f"stdout={stdout2}\nstderr={stderr2}"
    full = _checkpoint_files(checkpoint_b)
    assert len(full) == 300
    for left, right in zip(partial, full[: len(partial)], strict=True):
        assert left.read_text(encoding="utf-8") == right.read_text(encoding="utf-8")
