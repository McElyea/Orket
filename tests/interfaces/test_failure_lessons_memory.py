from __future__ import annotations

import json
import subprocess
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def _write_verify_harness(repo: Path) -> None:
    verify_script = repo / "verify.py"
    verify_script.write_text(
        "from pathlib import Path\n"
        "import os\n"
        "import sys\n"
        "if Path('tests/SHOULD_FAIL').exists():\n"
        "    sys.stderr.write(\"Missing env var API_KEY\\n\")\n"
        "    sys.exit(1)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    config = {
        "verify": {
            "profiles": {
                "default": {
                    "commands": ["python verify.py"],
                }
            }
        }
    }
    (repo / "orket.config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


def _init_refactor_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "orket-test@example.com")
    _git(repo, "config", "user.name", "Orket Test")
    (repo / "src" / "auth").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "auth" / "user.js").write_text("export const User = 'User';\n", encoding="utf-8")
    (repo / "src" / "auth" / "index.js").write_text("import { User } from './user.js';\n", encoding="utf-8")
    (repo / "src" / "other").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "other" / "secret.js").write_text("export const SECRET = 'x';\n", encoding="utf-8")
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    _write_verify_harness(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial fixture")
    return repo


def test_d1_record_on_verify_fail_writes_failure_lesson(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_refactor_repo(tmp_path)
    (repo / "tests" / "SHOULD_FAIL").write_text("force fail\n", encoding="utf-8")
    _git(repo, "add", "tests/SHOULD_FAIL")
    _git(repo, "commit", "-m", "force verify fail marker")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("ORKET_FAILURE_LESSONS", "1")

    code = main(["refactor", "rename User to Member", "--scope", "./src/auth", "--yes", "--json"])
    payload = json.loads(capsys.readouterr().out)

    lessons_path = repo / ".orket" / "memory" / "failure_lessons.jsonl"
    rows = [json.loads(line) for line in lessons_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert code == 1
    assert payload["code"] == "E_VERIFY_FAILED_REVERTED"
    assert payload["failure_lesson_id"]
    assert len(rows) == 1
    assert rows[0]["id"] == payload["failure_lesson_id"]


def test_d2_rerun_surfaces_relevant_failure_lesson_warning(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_refactor_repo(tmp_path)
    (repo / "tests" / "SHOULD_FAIL").write_text("force fail\n", encoding="utf-8")
    _git(repo, "add", "tests/SHOULD_FAIL")
    _git(repo, "commit", "-m", "force verify fail marker")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("ORKET_FAILURE_LESSONS", "1")

    _ = main(["refactor", "rename User to Member", "--scope", "./src/auth", "--yes", "--json"])
    first = json.loads(capsys.readouterr().out)

    _ = _git(repo, "reset", "--hard", "HEAD")
    code = main(["refactor", "rename User to Member", "--scope", "./src/auth", "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["advisories"]
    assert payload["advisories"][0]["lesson_id"] == first["failure_lesson_id"]


def test_d3_advisory_mode_warns_but_does_not_block(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_refactor_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("ORKET_FAILURE_LESSONS", "1")

    lessons_path = repo / ".orket" / "memory" / "failure_lessons.jsonl"
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    lesson = {
        "id": "lesson-1",
        "created_at": "2026-02-24T10:00:00+00:00",
        "command": "refactor",
        "request": {"scope": ["./src/auth"], "verify_profile": "default"},
        "plan": {"touch_set": ["src/auth/user.js"], "touch_count": 1},
        "advice": {
            "summary": "Missing env var API_KEY",
            "preflight_checks": [{"type": "env_var_present", "name": "API_KEY"}],
        },
    }
    lessons_path.write_text(json.dumps(lesson) + "\n", encoding="utf-8")

    code = main(["refactor", "rename User to Member", "--scope", "./src/auth", "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert "env_var_present:API_KEY" in payload["preflight_warnings"]
    assert payload["code"] == "OK"


def test_d4_memory_never_expands_scope_or_barrier_rules(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_refactor_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("ORKET_FAILURE_LESSONS", "1")

    lessons_path = repo / ".orket" / "memory" / "failure_lessons.jsonl"
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    lesson = {
        "id": "lesson-2",
        "created_at": "2026-02-24T10:00:00+00:00",
        "command": "refactor",
        "request": {"scope": ["./src/auth"], "verify_profile": "default"},
        "plan": {"touch_set": ["src/other/secret.js"], "touch_count": 1},
        "advice": {"summary": "Try broader scope", "preflight_checks": []},
    }
    lessons_path.write_text(json.dumps(lesson) + "\n", encoding="utf-8")

    code = main(["refactor", "rename SECRET to LEAK", "--scope", "./src/auth", "--yes", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["code"] == "E_TOUCHSET_EMPTY"
