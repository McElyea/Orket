"""Layer: integration. Real Git snapshots catch whole-file patterns without widening diff scope."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from orket.application.review.models import SnapshotBounds
from orket.application.review.run_service import ReviewRunService
from scripts.reviewrun.run_30page_consistency import fixture

pytestmark = pytest.mark.integration


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def repository(root):
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.name", "Review test")
    git(root, "config", "user.email", "review@example.invalid")
    (root / "code.py").write_text("# TODO: retain an explicit review finding\nvalue = 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-m", "baseline")
    base = git(root, "rev-parse", "HEAD")
    (root / "code.py").write_text("# TODO: retain an explicit review finding\nvalue = 2\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-m", "change")
    return base, git(root, "rev-parse", "HEAD")


def test_files_lane_sees_existing_pattern_but_diff_lane_only_sees_added_lines(tmp_path):
    repo = tmp_path / "repo"
    base, head = repository(repo)
    policy = {"deterministic": {"checks": {"forbidden_patterns": [{"pattern": "TODO", "severity": "high"}]}}}
    service = ReviewRunService(workspace=tmp_path / "reviews")
    common = {"repo_root": repo, "bounds": SnapshotBounds(), "cli_policy_overrides": policy}
    files = service.run_files(ref=head, paths=["code.py"], **common).to_dict()
    diff = service.run_diff(base_ref=base, head_ref=head, **common).to_dict()
    finding = json.loads((Path(files["artifact_dir"]) / "deterministic_decision.json").read_text())
    assert finding["decision"] == "changes_requested"
    assert finding["findings"][0]["path"] == "code.py" and finding["findings"][0]["span"]["start"] == 1
    decision = json.loads((Path(diff["artifact_dir"]) / "deterministic_decision.json").read_text())
    assert decision["decision"] == "pass" and not decision["findings"]


def test_recover_missing_head_then_restore_using_only_the_hashed_bundle(tmp_path):
    original = tmp_path / "original"
    base, head = repository(original)
    (original / ".git/HEAD").unlink()
    requested = {"repo_dir": str(original), "base_ref": base, "head_ref": head}
    retained = tmp_path / "retained"
    result = fixture(retained, requested)
    assert result["head_ref"] == head and not (original / ".git/HEAD").exists()
    restored = tmp_path / "restored"
    restored.mkdir()
    for name in ("fixture.json", "fixture.bundle"):
        shutil.copyfile(retained / name, restored / name)
    assert fixture(restored)["head_ref"] == head
    assert git(restored / "fixture", "rev-parse", "HEAD") == head
    (restored / "fixture.bundle").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum mismatch"):
        fixture(restored)
