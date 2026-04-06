# LIFECYCLE: live
# Layer: contract

from __future__ import annotations

import json
from pathlib import Path

from scripts.gitea.inspect_local_runner_containers import classify_runner_container, main


def _inspect_payload(
    *,
    name: str,
    auto_remove: bool,
    restart_policy: str,
    cmd: list[str],
    env: list[str] | None = None,
) -> dict:
    return {
        "Name": f"/{name}",
        "Created": "2026-03-12T00:00:00Z",
        "State": {"Status": "running"},
        "Config": {
            "Image": "gitea/act_runner:latest",
            "Cmd": cmd,
            "Entrypoint": ["/sbin/tini", "--", "run.sh"],
            "Env": list(env or []),
        },
        "HostConfig": {
            "AutoRemove": auto_remove,
            "RestartPolicy": {"Name": restart_policy},
        },
    }


def test_classify_runner_container_marks_registered_runner_as_persistent() -> None:
    payload = _inspect_payload(
        name="orket-act-runner-1",
        auto_remove=False,
        restart_policy="unless-stopped",
        cmd=[],
        env=["GITEA_RUNNER_NAME=orket-ci-runner-1"],
    )

    assessment = classify_runner_container(payload, registered_runner_names={"orket-ci-runner-1"})

    assert assessment["classification"] == "persistent_containerized_runner_policy_violation"
    assert assessment["cleanup_candidate"] is False
    assert assessment["policy_compliant"] is False
    assert assessment["intended_disposal"] == "not allowed as steady-state infrastructure under teardown policy"
    assert assessment["runner_registration_name"] == "orket-ci-runner-1"


def test_classify_runner_container_marks_version_probe_loop_as_cleanup_candidate() -> None:
    payload = _inspect_payload(
        name="brave_wright",
        auto_remove=True,
        restart_policy="no",
        cmd=["--version"],
    )

    assessment = classify_runner_container(
        payload,
        registered_runner_names=set(),
        log_tail="Error: instance address is empty",
    )

    assert assessment["classification"] == "stray_runner_version_probe_loop"
    assert assessment["cleanup_candidate"] is True
    assert assessment["policy_compliant"] is False
    assert assessment["observed_failure_signature"] == "instance address is empty"


def test_classify_runner_container_marks_exec_loop_as_cleanup_candidate() -> None:
    payload = _inspect_payload(
        name="silly_curie",
        auto_remove=True,
        restart_policy="no",
        cmd=["act_runner", "exec", "workflow_dispatch"],
    )

    assessment = classify_runner_container(payload, registered_runner_names=set())

    assert assessment["classification"] == "stray_runner_exec_loop"
    assert assessment["cleanup_candidate"] is True
    assert assessment["policy_compliant"] is False


def test_inspection_main_writes_diff_ledger_report(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    db_path = repo_root / "infrastructure" / "gitea" / "gitea"
    db_path.mkdir(parents=True, exist_ok=True)
    import sqlite3

    connection = sqlite3.connect(db_path / "gitea.db")
    try:
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE action_runner (name TEXT, deleted INTEGER)")
        cursor.execute("INSERT INTO action_runner (name, deleted) VALUES (?, ?)", ("orket-ci-runner-1", None))
        connection.commit()
    finally:
        connection.close()

    async def fake_list_runner_container_names():
        return ["orket-ci-runner-1", "brave_wright"], []

    async def fake_inspect_runner_containers(_names: list[str]):
        return [
            _inspect_payload(
                name="orket-act-runner-1",
                auto_remove=False,
                restart_policy="unless-stopped",
                cmd=[],
                env=["GITEA_RUNNER_NAME=orket-ci-runner-1"],
            ),
            _inspect_payload(
                name="brave_wright",
                auto_remove=True,
                restart_policy="no",
                cmd=["--version"],
            ),
        ]

    async def fake_collect_logs(name: str, *, skip_logs: bool):
        if name == "brave_wright":
            return "Error: instance address is empty"
        return ""

    monkeypatch.setattr(
        "scripts.gitea.inspect_local_runner_containers._list_runner_container_names",
        fake_list_runner_container_names,
    )
    monkeypatch.setattr(
        "scripts.gitea.inspect_local_runner_containers._inspect_runner_containers",
        fake_inspect_runner_containers,
    )
    monkeypatch.setattr(
        "scripts.gitea.inspect_local_runner_containers._collect_logs",
        fake_collect_logs,
    )

    out_path = tmp_path / "benchmarks" / "runner_report.json"
    exit_code = main(["--repo-root", str(repo_root), "--out", str(out_path)])

    assert exit_code == 1
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert payload["summary"]["cleanup_candidates"] == 1
    assert payload["summary"]["persistent_runner_policy_violations"] == 1
    assert payload["summary"]["policy_violations"] == 2
    assert payload["summary"]["stale_registration_policy_violations"] == 0
    assert payload["containers"][0]["runner_registration_name"] == "orket-ci-runner-1"
    assert "diff_ledger" in payload


def test_inspection_main_fails_when_registration_remains_without_container(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    db_path = repo_root / "infrastructure" / "gitea" / "gitea"
    db_path.mkdir(parents=True, exist_ok=True)
    import sqlite3

    connection = sqlite3.connect(db_path / "gitea.db")
    try:
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE action_runner (name TEXT, deleted INTEGER)")
        cursor.execute("INSERT INTO action_runner (name, deleted) VALUES (?, ?)", ("orket-ci-runner-1", None))
        connection.commit()
    finally:
        connection.close()

    async def fake_list_runner_container_names():
        return [], []

    async def fake_inspect_runner_containers(_names: list[str]):
        return []

    monkeypatch.setattr(
        "scripts.gitea.inspect_local_runner_containers._list_runner_container_names",
        fake_list_runner_container_names,
    )
    monkeypatch.setattr(
        "scripts.gitea.inspect_local_runner_containers._inspect_runner_containers",
        fake_inspect_runner_containers,
    )

    out_path = tmp_path / "benchmarks" / "runner_report_registration_only.json"
    exit_code = main(["--repo-root", str(repo_root), "--out", str(out_path), "--skip-logs"])

    assert exit_code == 1
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert payload["stale_registrations"] == ["orket-ci-runner-1"]
    assert payload["summary"]["containers_total"] == 0
    assert payload["summary"]["stale_registration_policy_violations"] == 1


def test_inspection_main_treats_container_name_as_live_registration_when_env_name_is_absent(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path
    db_path = repo_root / "infrastructure" / "gitea" / "gitea"
    db_path.mkdir(parents=True, exist_ok=True)
    import sqlite3

    connection = sqlite3.connect(db_path / "gitea.db")
    try:
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE action_runner (name TEXT, deleted INTEGER)")
        cursor.execute("INSERT INTO action_runner (name, deleted) VALUES (?, ?)", ("codex-ephemeral", None))
        connection.commit()
    finally:
        connection.close()

    async def fake_list_runner_container_names():
        return ["codex-ephemeral"], []

    async def fake_inspect_runner_containers(_names: list[str]):
        return [
            _inspect_payload(
                name="codex-ephemeral",
                auto_remove=False,
                restart_policy="no",
                cmd=[],
                env=[],
            )
        ]

    async def fake_collect_logs(_name: str, *, skip_logs: bool):
        return ""

    monkeypatch.setattr(
        "scripts.gitea.inspect_local_runner_containers._list_runner_container_names",
        fake_list_runner_container_names,
    )
    monkeypatch.setattr(
        "scripts.gitea.inspect_local_runner_containers._inspect_runner_containers",
        fake_inspect_runner_containers,
    )
    monkeypatch.setattr(
        "scripts.gitea.inspect_local_runner_containers._collect_logs",
        fake_collect_logs,
    )

    out_path = tmp_path / "benchmarks" / "runner_report_container_name_match.json"
    exit_code = main(["--repo-root", str(repo_root), "--out", str(out_path), "--skip-logs"])

    assert exit_code == 1
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert payload["stale_registrations"] == []
    assert payload["containers"][0]["observed_registration_name"] == "codex-ephemeral"
