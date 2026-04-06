from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path("scripts/nervous_system/update_nervous_system_policy_digest_snapshot.py")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_mode_reports_drift_on_missing_snapshot(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snapshot.json"
    result = _run("--snapshot", str(snapshot_path), "--check")
    assert result.returncode == 1
    assert "Snapshot changes" in result.stdout
    assert snapshot_path.exists() is False


def test_write_mode_writes_snapshot_with_schema_version(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snapshot.json"
    result = _run("--snapshot", str(snapshot_path), "--write")
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["snapshot_version"] == 1
    assert payload["digest_algorithm"] == "sha256"
    assert str(payload["canonicalizer"]).startswith("orket/kernel/v1/canonical.py@")


def test_explain_mode_prints_contributor_paths_and_rules(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snapshot.json"
    write = _run("--snapshot", str(snapshot_path), "--write")
    assert write.returncode == 0, write.stdout + "\n" + write.stderr

    result = _run("--snapshot", str(snapshot_path), "--check", "--explain")
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "[EXPLAIN] Digest contributors" in result.stdout
    assert "policy_contexts:" in result.stdout
    assert "deny_rules:" in result.stdout
    assert "tool_profiles:" in result.stdout
    assert "source_path: orket/kernel/v1/nervous_system_policy_snapshot.py" in result.stdout
    assert "source_path: orket/kernel/v1/nervous_system_resolver.py" in result.stdout
    assert "rule_name: deny_ssh_private_key_read" in result.stdout
