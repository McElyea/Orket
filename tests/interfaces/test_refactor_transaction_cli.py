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
        "import sys\n"
        "sys.exit(1 if Path('tests/SHOULD_FAIL').exists() else 0)\n",
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


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "orket-test@example.com")
    _git(repo, "config", "user.name", "Orket Test")

    (repo / "src" / "auth").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "auth" / "user.js").write_text(
        "export const User = 'User';\n",
        encoding="utf-8",
    )
    (repo / "src" / "auth" / "index.js").write_text(
        "import { User } from './user.js';\nexport default User;\n",
        encoding="utf-8",
    )
    (repo / "src" / "other").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "other" / "secret.js").write_text("export const SECRET = 'x';\n", encoding="utf-8")
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    _write_verify_harness(repo)

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial fixture")
    return repo


def test_refactor_verify_failure_reverts_repo_and_preserves_head(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    (repo / "tests" / "SHOULD_FAIL").write_text("force fail\n", encoding="utf-8")
    _git(repo, "add", "tests/SHOULD_FAIL")
    _git(repo, "commit", "-m", "force verify fail marker")
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    content_before = (repo / "src" / "auth" / "user.js").read_text(encoding="utf-8")

    monkeypatch.chdir(repo)
    code = main(["refactor", "rename User to Member", "--scope", "./src/auth", "--yes"])
    out = capsys.readouterr().out

    assert code == 1
    assert "E_VERIFY_FAILED_REVERTED" in out
    assert (repo / "src" / "auth" / "user.js").read_text(encoding="utf-8") == content_before
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


def test_refactor_scope_barrier_returns_touchset_empty_and_keeps_repo_clean(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    code = main(["refactor", "rename SECRET to LEAK", "--scope", "./src/auth", "--yes"])
    out = capsys.readouterr().out

    assert code == 1
    assert "E_TOUCHSET_EMPTY" in out
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


def test_refactor_dry_run_lists_touch_set_and_does_not_modify_repo(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    code = main(["refactor", "rename User to Member", "--scope", "./src/auth", "--dry-run"])
    out = capsys.readouterr().out

    assert code == 0
    assert "FILES TO BE MODIFIED" in out
    assert "src/auth/user.js" in out
    assert "src/auth/index.js" in out
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""
