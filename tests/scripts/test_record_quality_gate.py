"""Integration controls for real command exits and fail-closed gate evidence."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci import record_quality_gate as recorder
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

pytestmark = pytest.mark.integration


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    root.mkdir()
    (root / "source.py").write_text("value = 1\n", encoding="utf-8")
    for argv in (["git", "init", str(root)], ["git", "-C", str(root), "add", "source.py"],
                 ["git", "-C", str(root), "-c", "user.name=Gate Control", "-c", "user.email=gate@example.invalid",
                  "commit", "-m", "control"]):
        subprocess.run(argv, check=True, capture_output=True)
    return root


def child(exit_code: int) -> list[str]:
    return ["python", "-c", f"import sys; print('actual stdout'); print('actual stderr', file=sys.stderr); sys.exit({exit_code})"]


async def seed_result(repository: Path, output: Path, commands: list[list[str]]) -> tuple[Path, dict]:
    path = output / "quality_gates" / "g4" / "result.json"
    records = await recorder.execute_commands(commands, repo_root=repository, log_root=path.parent, timeout_seconds=5)
    source = recorder.source_identity(repository)
    payload = {"schema_version": "td03052026.quality_command_result.v1", "gate_id": "G4", "status": "PASS",
               "source": source, "run_id": "native-control", "planned_commands": commands, "commands": records}
    write_payload_with_diff_ledger(path, payload)
    return path, source


async def test_actual_zero_exit_retains_logs_and_native_settlement(repository: Path, tmp_path: Path) -> None:
    command = child(0)
    path, source = await seed_result(repository, tmp_path / "evidence", [command])
    assert recorder.validate_result(path, gate_id="G4", source=source, run_id="native-control",
                                    expected_commands=[command])[0]
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["commands"][0]["argv"][0] == sys.executable
    assert result["commands"][0]["lifetime"]["command_pid"] > 0
    assert result["commands"][0]["lifetime"]["cleanup_confirmed"] is True
    assert (path.parent / "command-1.stdout.log").read_bytes().strip() == b"actual stdout"
    assert (path.parent / "command-1.stderr.log").read_bytes().strip() == b"actual stderr"
    assert "diff_ledger" in result


async def test_nonzero_second_child_cannot_make_group_green(repository: Path, tmp_path: Path) -> None:
    commands = [child(0), child(37)]
    path, source = await seed_result(repository, tmp_path / "evidence", commands)
    result = json.loads(path.read_text(encoding="utf-8"))
    assert [record["returncode"] for record in result["commands"]] == [0, 37]
    assert all(record["lifetime"]["cleanup_confirmed"] for record in result["commands"])
    assert not recorder.validate_result(path, gate_id="G4", source=source, run_id="native-control",
                                        expected_commands=commands)[0]


@pytest.mark.parametrize("exit_code", [0, 37])
async def test_recorder_publishes_actual_exit_and_replaces_prior_green(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int,
) -> None:
    output = tmp_path / "evidence"
    commands = [child(0)]
    # Supply controlled argv, while the native child, logs, source capture and publication remain real.
    monkeypatch.setattr(recorder, "gate_commands", lambda _: commands)
    assert await recorder.record_gate("G1", repo_root=repository, output_root=output,
                                      run_id="control", timeout_seconds=5) == 0
    commands[:] = [child(exit_code)]
    assert await recorder.record_gate("G1", repo_root=repository, output_root=output,
                                      run_id="control", timeout_seconds=5) == (0 if exit_code == 0 else 1)
    result = json.loads((output / "quality_gates" / "g1" / "result.json").read_text(encoding="utf-8"))
    dashboard = json.loads((output / "hardening_dashboard.json").read_text(encoding="utf-8"))
    assert result["status"] == ("PASS" if exit_code == 0 else "FAIL")
    assert result["commands"][0]["returncode"] == exit_code
    assert result["source_unchanged"] is True
    assert dashboard["gates"]["G1"]["state"] == ("green" if exit_code == 0 else "red")
    assert dashboard["gates"]["G6"]["state"] == dashboard["gates"]["G7"]["state"] == "red"
    assert len(result["diff_ledger"]) >= 3


@pytest.mark.parametrize("damage", ["missing", "log", "source", "run", "command", "incomplete", "failed"])
async def test_rejects_missing_stale_or_corrupt_evidence(repository: Path, tmp_path: Path, damage: str) -> None:
    commands = [child(0)]
    path, source = await seed_result(repository, tmp_path / "evidence", commands)
    payload = json.loads(path.read_text(encoding="utf-8"))
    run_id = "native-control"
    if damage == "missing":
        path.unlink()
    elif damage == "log":
        (path.parent / "command-1.stdout.log").write_bytes(b"changed")
    elif damage == "source":
        (repository / "source.py").write_text("value = 2\n", encoding="utf-8")
        source = recorder.source_identity(repository)
    elif damage == "run":
        run_id = "different-ci-run"
    else:
        if damage == "command":
            payload["commands"][0]["command"] = child(9)
        elif damage == "incomplete":
            payload["commands"][0]["lifetime"]["capture_complete"] = False
        else:
            payload["status"] = "FAIL"
        path.write_text(json.dumps(payload), encoding="utf-8")
    assert not recorder.validate_result(path, gate_id="G4", source=source, run_id=run_id,
                                        expected_commands=commands)[0]


def test_source_binding_includes_new_untracked_inputs(repository: Path) -> None:
    before = recorder.source_identity(repository)
    (repository / "new_recorder.py").write_text("value = 2\n", encoding="utf-8")
    after = recorder.source_identity(repository)
    assert before["commit"] == after["commit"]
    assert before["source_sha256"] != after["source_sha256"]
    assert after["source_paths_count"] == before["source_paths_count"] + 1


def test_missing_current_proof_keeps_every_gate_red(repository: Path, tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    dashboard = recorder.refresh_dashboard(output, recorder.source_identity(repository), "current-run")
    assert all(entry["state"] == "red" and entry["evidence"] == [] for entry in dashboard["gates"].values())
    assert "diff_ledger" in json.loads((output / "hardening_dashboard.json").read_text(encoding="utf-8"))


def test_provider_gate_requires_both_existing_commands() -> None:
    assert recorder.gate_commands("G4") == [
        recorder.shlex.split(recorder.REQUIRED_CI_SNIPPETS["G4"]), recorder.shlex.split(recorder.PROVIDER_CLOSE_EXTRA)]


def test_cli_refuses_noncanonical_command_before_launch() -> None:
    with pytest.raises(SystemExit) as failure:
        recorder.main(["--gate", "G1", "--run-id", "control", "--", *child(0)])
    assert failure.value.code == 2


async def test_timeout_cannot_pass_even_if_caller_labels_result_pass(repository: Path, tmp_path: Path) -> None:
    commands = [["python", "-c", "import time; time.sleep(30)"]]
    path = tmp_path / "evidence" / "quality_gates" / "g4" / "result.json"
    records = await recorder.execute_commands(commands, repo_root=repository, log_root=path.parent, timeout_seconds=0.1)
    assert records[0]["lifetime"]["reason"] == "timeout"
    assert records[0]["lifetime"]["cleanup_confirmed"] is True
    source = recorder.source_identity(repository)
    write_payload_with_diff_ledger(path, {"schema_version": "td03052026.quality_command_result.v1",
        "gate_id": "G4", "status": "PASS", "source": source, "run_id": "control",
        "planned_commands": commands, "commands": records})
    assert not recorder.validate_result(path, gate_id="G4", source=source, run_id="control",
                                        expected_commands=commands)[0]
