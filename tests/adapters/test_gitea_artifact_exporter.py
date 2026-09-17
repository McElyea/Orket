from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path
from urllib import parse

import pytest

from orket.adapters.vcs.gitea_artifact_exporter import GiteaArtifactExporter


@pytest.mark.unit
# Layer: unit
def test_build_repo_url_does_not_embed_credentials(tmp_path: Path) -> None:
    exporter = GiteaArtifactExporter(workspace=tmp_path)

    repo_url = exporter._build_repo_url("https://gitea.example.com", "owner", "repo")
    assert repo_url == "https://gitea.example.com/owner/repo.git"
    parsed = parse.urlparse(repo_url)
    assert parsed.username is None
    assert parsed.password is None


@pytest.mark.unit
# Layer: unit
def test_build_repo_url_preserves_base_path(tmp_path: Path) -> None:
    exporter = GiteaArtifactExporter(workspace=tmp_path)

    repo_url = exporter._build_repo_url("https://gitea.example.com/git", "owner", "repo")
    assert repo_url == "https://gitea.example.com/git/owner/repo.git"


@pytest.mark.unit
# Layer: unit
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


@pytest.mark.contract
# Layer: contract
def test_export_binding_is_frozen_and_omits_authentication_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "fixture-secret")
    monkeypatch.setenv("ORKET_GITEA_ARTIFACT_REPO", "original")
    exporter = GiteaArtifactExporter(tmp_path)
    before = exporter.binding()
    monkeypatch.setenv("ORKET_GITEA_ARTIFACT_REPO", "changed")
    assert exporter.binding() == before
    assert "fixture-secret" not in str(before)
    before["repo_name"] = "mutated"
    assert exporter.binding()["repo_name"] == "original"


@pytest.mark.contract
# Layer: contract
def test_export_binding_rejects_credential_bearing_target(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_URL", "https://fixture-user:fixture-password@gitea.invalid")
    with pytest.raises(ValueError, match="E_GITEA_EXPORT_CREDENTIAL_URL"):
        GiteaArtifactExporter(tmp_path)


@pytest.mark.asyncio
@pytest.mark.parametrize("setting,value", [("ORKET_GITEA_ARTIFACT_BRANCH", "--upload-pack=bad"),
                                         ("ORKET_GITEA_ARTIFACT_PATH_PREFIX", "../outside"),
                                         ("ORKET_GITEA_ARTIFACT_OWNER", "../owner")])
# Layer: contract
async def test_export_rejects_unsafe_components_before_preparation(monkeypatch, tmp_path, setting, value):
    monkeypatch.setenv("ORKET_GITEA_ARTIFACT_EXPORT", "1")
    monkeypatch.setenv("GITEA_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("GITEA_ADMIN_USER", "fixture-user")
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "fixture-password")
    monkeypatch.setenv(setting, value)
    exporter = GiteaArtifactExporter(tmp_path)
    with pytest.raises(ValueError, match="E_GITEA_EXPORT_COMPONENT|E_GITEA_EXPORT_PREFIX"):
        await exporter.prepare_export(run_id="rejected")


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "nt", reason="Native Windows junction boundary")
# Layer: integration
async def test_export_rejects_top_level_junction_before_remote_access(monkeypatch, tmp_path):
    target, alias = tmp_path / "original", tmp_path / "agent_output"
    await asyncio.to_thread(target.mkdir)
    retained = target / "result.txt"
    await asyncio.to_thread(retained.write_text, "retained", encoding="utf-8")
    environment = {**os.environ, "ORKET_TEST_LINK": str(alias), "ORKET_TEST_TARGET": str(target)}
    child = await asyncio.create_subprocess_exec(
        "powershell", "-NoProfile", "-Command",
        "New-Item -ItemType Junction -Path $env:ORKET_TEST_LINK -Target $env:ORKET_TEST_TARGET | Out-Null",
        env=environment, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, stderr = await asyncio.wait_for(child.communicate(), timeout=15)
        assert child.returncode == 0, stderr.decode(errors="replace")
        settings = {"ORKET_GITEA_ARTIFACT_EXPORT": "1", "GITEA_URL": "http://127.0.0.1:1",
                    "GITEA_ADMIN_USER": "fixture-user", "GITEA_ADMIN_PASSWORD": "fixture-password",
                    "ORKET_GITEA_ARTIFACT_OWNER": "fixture-user", "ORKET_GITEA_ARTIFACT_BRANCH": "main",
                    "ORKET_GITEA_ARTIFACT_PATH_PREFIX": "runs",
                    "ORKET_GITEA_ARTIFACT_CACHE_ROOT": str(tmp_path / "cache")}
        for key, value in settings.items():
            monkeypatch.setenv(key, value)
        with pytest.raises(ValueError, match="E_GITEA_EXPORT_SOURCE_ESCAPE"):
            await GiteaArtifactExporter(tmp_path).prepare_export(
                run_id="junction", run_type="epic", run_name="proof", build_id="build", session_status="done",
                summary={}, export_day="2026-09-12", export_time="2026-09-12T12:00:00+00:00")
    finally:
        if child.returncode is None:
            child.kill()
        await child.communicate()
        if alias.exists():
            await asyncio.to_thread(alias.rmdir)
        assert await asyncio.to_thread(retained.read_text, encoding="utf-8") == "retained"
