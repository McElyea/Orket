from __future__ import annotations

import base64
from pathlib import Path
from urllib import parse

from orket.adapters.vcs.gitea_artifact_exporter import GiteaArtifactExporter


def test_build_repo_url_does_not_embed_credentials(tmp_path: Path) -> None:
    exporter = GiteaArtifactExporter(workspace=tmp_path)

    repo_url = exporter._build_repo_url("https://gitea.example.com", "owner", "repo")
    assert repo_url == "https://gitea.example.com/owner/repo.git"
    parsed = parse.urlparse(repo_url)
    assert parsed.username is None
    assert parsed.password is None


def test_build_repo_url_preserves_base_path(tmp_path: Path) -> None:
    exporter = GiteaArtifactExporter(workspace=tmp_path)

    repo_url = exporter._build_repo_url("https://gitea.example.com/git", "owner", "repo")
    assert repo_url == "https://gitea.example.com/git/owner/repo.git"


def test_git_auth_env_appends_http_header_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "color.ui")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "auto")

    exporter = GiteaArtifactExporter(workspace=tmp_path)
    env = exporter._git_auth_env("alice", "s3cr3t")

    assert env["GIT_CONFIG_COUNT"] == "2"
    assert env["GIT_CONFIG_KEY_1"] == "http.extraHeader"
    header = env["GIT_CONFIG_VALUE_1"]
    assert header.startswith("Authorization: Basic ")

    token = header.split(" ", 2)[-1]
    assert base64.b64decode(token.encode("ascii")).decode("utf-8") == "alice:s3cr3t"
