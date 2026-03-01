from __future__ import annotations

import json
from pathlib import Path

from orket.application.review.policy_resolver import resolve_review_policy
from orket.settings import save_user_settings, set_settings_file


def test_review_policy_precedence_cli_repo_user_defaults(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    policy_dir = repo_root / ".orket"
    policy_dir.mkdir(parents=True)
    (policy_dir / "review_policy.json").write_text(
        json.dumps({"bounds": {"max_files": 50}, "model_assisted": {"enabled": False}}),
        encoding="utf-8",
    )

    settings_path = tmp_path / "user_settings.json"
    set_settings_file(settings_path)
    save_user_settings({"review_policy": {"bounds": {"max_files": 80, "max_diff_bytes": 99}}})

    resolved = resolve_review_policy(
        cli_overrides={"bounds": {"max_files": 10}},
        repo_root=repo_root,
    )
    payload = resolved.payload
    assert payload["bounds"]["max_files"] == 10
    assert payload["bounds"]["max_diff_bytes"] == 99
    assert payload["policy_version"] == "review_policy_v0"
    assert payload["input_scope"]["mode"] == "code_only"
    assert resolved.policy_digest.startswith("sha256:")


def test_review_policy_digest_stable_for_identical_payload(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    first = resolve_review_policy(repo_root=repo_root)
    second = resolve_review_policy(repo_root=repo_root)
    assert first.policy_digest == second.policy_digest


def test_review_policy_scope_override_all_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    resolved = resolve_review_policy(repo_root=repo_root, cli_overrides={"input_scope": {"mode": "all_files"}})
    assert resolved.payload["input_scope"]["mode"] == "all_files"
