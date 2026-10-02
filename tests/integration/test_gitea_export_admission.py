"""Exporter admission and native local effects; loopback HTTP is not hosted Gitea."""
import asyncio
import json
import os
from copy import deepcopy
from functools import partial

import pytest

from orket.adapters.execution.owned_command_process import execute_owned_command
from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.gitea_artifact_exporter_factory import create_gitea_artifact_exporter
from orket.core.contracts.gitea_export import GiteaExportIntent
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_gitea_export_native_ownership import run_values
from tests.integration.test_short_http_ownership import clean_network

pytestmark = pytest.mark.asyncio


async def _owner(root, *, url="http://127.0.0.1:1", changes=None):
    environment = dict(os.environ)
    environment.update(ORKET_GITEA_ARTIFACT_EXPORT="1", GITEA_URL=url,
        GITEA_ADMIN_USER="fixture", GITEA_ADMIN_PASSWORD="public-password",
        ORKET_GITEA_ARTIFACT_OWNER="fixture", ORKET_GITEA_ARTIFACT_REPO="fixture",
        ORKET_GITEA_ARTIFACT_BRANCH="main", ORKET_GITEA_ARTIFACT_PATH_PREFIX="runs",
        ORKET_GITEA_ARTIFACT_PRIVATE="1",
        ORKET_GITEA_ARTIFACT_AUTHOR_NAME="Fixture", ORKET_GITEA_ARTIFACT_AUTHOR_EMAIL="fixture@local",
        ORKET_GITEA_ARTIFACT_CACHE_ROOT=str(root / "cache"))
    environment.update(changes or {})
    return await run_owned_thread(partial(create_gitea_artifact_exporter,
        root / "workspace", environment=environment, invocation_root=root), label="export-admission-fixture")


@pytest.mark.contract
@pytest.mark.parametrize("changes,code", [
    ({"ORKET_GITEA_ARTIFACT_EXPORT": "0"}, "E_GITEA_EXPORT_DISABLED"),
    ({"GITEA_URL": "ftp://fixture.invalid"}, "E_GITEA_EXPORT_TARGET"),
    ({"GITEA_URL": "http:///missing"}, "E_GITEA_EXPORT_TARGET"),
    ({"GITEA_URL": "http://fixture.invalid?query=1"}, "E_GITEA_EXPORT_TARGET"),
    ({"GITEA_URL": "http://fixture.invalid#fragment"}, "E_GITEA_EXPORT_TARGET"),
    ({"GITEA_ADMIN_USER": ""}, "E_GITEA_EXPORT_CREDENTIALS_MISSING"),
    ({"GITEA_ADMIN_PASSWORD": ""}, "E_GITEA_EXPORT_CREDENTIALS_MISSING"),
    ({"ORKET_GITEA_ARTIFACT_REPO": ""}, "E_GITEA_EXPORT_COMPONENT:repo_name"),
    ({"ORKET_GITEA_ARTIFACT_BRANCH": "feature/../bad"}, "E_GITEA_EXPORT_COMPONENT:branch"),
    ({"ORKET_GITEA_ARTIFACT_BRANCH": "bad.lock"}, "E_GITEA_EXPORT_COMPONENT:branch"),
    ({"ORKET_GITEA_ARTIFACT_PATH_PREFIX": "/"}, "E_GITEA_EXPORT_PREFIX"),
    ({"ORKET_GITEA_ARTIFACT_PATH_PREFIX": "a\\b"}, "E_GITEA_EXPORT_PREFIX"),
    ({"ORKET_GITEA_ARTIFACT_PATH_PREFIX": "a:b"}, "E_GITEA_EXPORT_PREFIX"),
    ({"ORKET_GITEA_ARTIFACT_AUTHOR_NAME": ""}, "E_GITEA_EXPORT_AUTHOR"),
    ({"ORKET_GITEA_ARTIFACT_AUTHOR_NAME": "line\nbreak"}, "E_GITEA_EXPORT_AUTHOR"),
    ({"ORKET_GITEA_ARTIFACT_AUTHOR_EMAIL": "<address>"}, "E_GITEA_EXPORT_AUTHOR"),
])
async def test_invalid_settings_refuse_before_payload_or_transport(tmp_path, changes, code):
    owner = await _owner(tmp_path, changes=changes)
    with pytest.raises(ValueError, match=code):
        await owner.prepare_export(**run_values({}))
    assert not await asyncio.to_thread((tmp_path / "cache").exists)


def _intent(owner, **changes):
    # These shaped values only exercise pre-transport refusal, never a claimed commit.
    values = dict(binding=owner.binding(), run_id="refusal",
        commit="a" * 40, tree="b" * 40, run_path="runs/refusal")
    return GiteaExportIntent(**{**values, **changes})


@pytest.mark.contract
@pytest.mark.parametrize("path", ["../escape", "/absolute", "windows\\path", "drive:path"])
async def test_public_intent_path_refusal_never_enters_transport(tmp_path, path):
    owner = await _owner(tmp_path)
    intent = _intent(owner, run_path=path)
    with pytest.raises(ValueError, match="E_GITEA_EXPORT_PATH_ESCAPE"):
        await owner.reconcile_export(intent)
    assert not await asyncio.to_thread((tmp_path / "cache").exists)


@pytest.mark.contract
async def test_missing_foreign_and_wrong_run_intents_cannot_authorize_export(tmp_path):
    owner = await _owner(tmp_path)
    with pytest.raises(ValueError, match="E_GITEA_EXPORT_INTENT_REQUIRED"):
        await owner.export_run(run_id="refusal")
    intent = _intent(owner)
    foreign = _intent(owner, binding={**intent.binding, "repo_name": "other"})
    with pytest.raises(ValueError, match="E_GITEA_EXPORT_INTENT_REQUIRED"):
        await owner.export_run(export_intent=foreign, run_id="refusal")
    with pytest.raises(ValueError, match="E_GITEA_EXPORT_RUN_CONFLICT"):
        await owner.export_run(export_intent=intent, run_id="other")
    disabled = await _owner(tmp_path, changes={"ORKET_GITEA_ARTIFACT_EXPORT": "0"})
    assert await disabled.export_run() is None
    assert not await asyncio.to_thread((tmp_path / "cache").exists)


async def _children(path):
    return await asyncio.to_thread(lambda: list(path.iterdir()))


async def _git(repo, *args):
    result = await execute_owned_command(argv=["git", "-C", str(repo), *args], cwd=repo,
        environment=dict(os.environ), timeout_seconds=15, input_data=None, stop=asyncio.Event())
    assert result.cleanup_confirmed and result.capture_complete, result
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


@pytest.mark.integration
async def test_prepare_copies_real_artifacts_and_replaces_only_owned_payload(tmp_path, monkeypatch):
    clean_network(monkeypatch)
    original = {"observability/owned-payload/event.json": b'{"event":"kept"}',
                "agent_output/result.txt": b"result\n", "orket.log": b"native log\n"}
    for name, content in original.items():
        path = tmp_path / "workspace" / name
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)

    async def absent(_request):
        return 404, {"message": "controlled absent repository"}

    async with observed_http_server(absent) as (url, requests):
        owner = await _owner(tmp_path, url=url)
        run = run_values({"result": "first"})
        before = deepcopy(run)
        intent = await owner.prepare_export(**run)
        payload, = await _children(tmp_path / "cache/payload")
        assert await asyncio.to_thread(lambda: payload.resolve().is_relative_to(tmp_path.resolve()))
        for source, destination in [("observability/owned-payload/event.json", "observability/event.json"),
                                    ("agent_output/result.txt", "agent_output/result.txt"), ("orket.log", "orket.log")]:
            assert await asyncio.to_thread((payload / destination).read_bytes) == original[source]
        repo, = await _children(tmp_path / "cache/repo_cache")
        manifest = json.loads(await _git(repo, "show", intent.commit + ":" + intent.run_path + "/manifest.json"))
        assert manifest["summary"] == {"result": "first"} and manifest["export_path"] == intent.run_path
        assert run == before
        stale = payload / "stale.txt"
        await asyncio.to_thread(stale.write_bytes, b"owned old payload")
        run["summary"] = {"result": "second"}
        second = await owner.prepare_export(**run)
        assert second.commit != intent.commit and not await asyncio.to_thread(stale.exists)
        assert len(requests) == 2 and all(request[0].startswith("GET /api/v1/repos/fixture/fixture ")
                                          for request in requests)
    for name, content in original.items():
        assert await asyncio.to_thread((tmp_path / "workspace" / name).read_bytes) == content


@pytest.mark.integration
async def test_http_refusal_does_not_hide_partial_native_payload(tmp_path, monkeypatch):
    clean_network(monkeypatch)

    async def unavailable(_request):
        return 503, {"message": "controlled service failure"}

    async with observed_http_server(unavailable) as (url, requests):
        owner = await _owner(tmp_path, url=url)
        with pytest.raises(RuntimeError, match="E_GITEA_EXPORT_HTTP_STATUS:503"):
            await owner.prepare_export(**run_values({"retained": True}))
        assert len(requests) == 1
    payload, = await _children(tmp_path / "cache/payload")
    manifest = json.loads(await asyncio.to_thread((payload / "manifest.json").read_text, encoding="utf-8"))
    assert manifest["summary"] == {"retained": True}
    repo, = await _children(tmp_path / "cache/repo_cache")
    assert await asyncio.to_thread((repo / ".git").is_dir)


@pytest.mark.integration
@pytest.mark.parametrize("owner_name,creation_path", [
    ("fixture", "/api/v1/user/repos"), ("team", "/api/v1/orgs/team/repos"),
])
async def test_repository_creation_must_be_confirmed_before_push(tmp_path, monkeypatch, owner_name, creation_path):
    clean_network(monkeypatch)

    async def unconfirmed(request):
        return (201, {}) if request[0].startswith("POST ") else (404, {})

    async with observed_http_server(unconfirmed) as (url, requests):
        owner = await _owner(tmp_path, url=url, changes={"ORKET_GITEA_ARTIFACT_OWNER": owner_name})
        intent = await owner.prepare_export(**run_values({}))
        with pytest.raises(RuntimeError, match="E_GITEA_EXPORT_REPOSITORY_UNCONFIRMED"):
            await owner.export_run(export_intent=intent, run_id=intent.run_id)
        assert [request[0].split()[0] for request in requests] == ["GET", "GET", "POST", "GET"]
        assert requests[2][0].split()[1] == creation_path
        assert requests[2][1] == {"name": "fixture", "private": True, "auto_init": False}
