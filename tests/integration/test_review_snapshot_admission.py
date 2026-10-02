"""Native review input/refusal and bounded snapshot proof; loopback is not hosted Gitea."""
import asyncio
import json
import os
from functools import partial
from pathlib import Path

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.review.errors import ReviewError
from orket.application.review.models import SnapshotBounds
from orket.application.review.run_service import ReviewRunService
from orket.application.review.snapshot_loader import load_from_files, load_from_pr
from tests.application.test_review_snapshot_loader import _git, _init_repo
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_short_http_ownership import clean_network

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _native(operation, *args, **options):
    return await run_owned_thread(partial(operation, *args, **options), label="review-admission-fixture")


async def _repo(root, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    repo = root / "repo"
    await _native(_init_repo, repo)
    return repo


def _service(root):
    return ReviewRunService(workspace=root / "workspace", control_plane_db_path=root / "control.sqlite3")


@pytest.mark.parametrize("remote,configured,message", [
    ("ftp://fixture.invalid", None, "http.s.*base URL"),
    ("http:///", None, "hostname"),
    ("http://fixture.invalid", None, "no configured git remote"),
    ("http://fixture.invalid", "", "no configured git remote"),
    ("http://fixture.invalid", "local-path", "no configured git remote"),
    ("http://fixture.invalid", "https://other.invalid/unrelated.git", "no configured git remote"),
    ("http://fixture.invalid", "https:///org/repo.git", "no configured git remote"),
    ("http://fixture.invalid", "git@other.invalid:org/repo.git", "not bound"),
    ("http://fixture.invalid", "https://fixture.invalid/prefix/org/repo.git", "not bound"),
])
async def test_pr_remote_refusal_precedes_http_and_bundle(tmp_path, monkeypatch, remote, configured, message):
    repo = await _repo(tmp_path, monkeypatch)
    if configured is not None:
        await _native(_git, repo, "config", "remote.fixture.url", configured)
    with pytest.raises(ValueError, match=message):
        await _native(_service(tmp_path).run_pr, repo_root=repo, remote=remote, repo="org/repo",
                      pr=1, bounds=SnapshotBounds())
    assert not await asyncio.to_thread((tmp_path / "workspace/review_runs").exists)
    assert not await asyncio.to_thread((tmp_path / "control.sqlite3").exists)


async def test_actual_git_reference_and_missing_executable_failures_keep_identity(tmp_path, monkeypatch):
    repo = await _repo(tmp_path, monkeypatch)
    await _native((repo / "kept.py").write_text, "pass\n", encoding="utf-8")
    await _native(_git, repo, "add", ".")
    await _native(_git, repo, "commit", "-m", "fixture")
    service = _service(tmp_path)
    with pytest.raises(ReviewError) as failed:
        await _native(service.run_diff, repo_root=repo, base_ref="missing-ref", head_ref="HEAD", bounds=SnapshotBounds())
    assert failed.value.command == ["git", "diff", "--name-only", "missing-ref", "HEAD"]
    assert failed.value.returncode != 0 and failed.value.stderr
    with pytest.raises(ReviewError) as failed:
        await _native(load_from_files, repo_root=repo, ref="missing-ref", paths=["kept.py"], bounds=SnapshotBounds())
    assert failed.value.command == ["git", "show", "missing-ref:kept.py"] and failed.value.stderr
    with pytest.raises(FileNotFoundError, match="absent.py"):
        await _native(load_from_files, repo_root=repo, ref="HEAD", paths=["absent.py"], bounds=SnapshotBounds())
    with monkeypatch.context() as missing_git:
        missing_git.setenv("PATH", str(tmp_path / "no-executables"))
        for operation, options in [(service.run_diff, dict(base_ref="HEAD", head_ref="HEAD")),
                                   (load_from_files, dict(ref="HEAD", paths=["kept.py"]))]:
            with pytest.raises(ReviewError, match="git executable was not found") as failed:
                await _native(operation, repo_root=repo, bounds=SnapshotBounds(), **options)
            assert failed.value.command[0] == "git" and failed.value.returncode is None
    assert not await asyncio.to_thread((tmp_path / "workspace/review_runs").exists)


async def test_file_selection_and_aggregate_blob_bounds_are_explicit(tmp_path, monkeypatch):
    repo = await _repo(tmp_path, monkeypatch)
    for name, text in [("a.py", "abcd"), ("b.py", "efghij"), ("c.py", "discarded")]:
        await _native((repo / name).write_text, text, encoding="utf-8")
    await _native(_git, repo, "add", ".")
    await _native(_git, repo, "commit", "-m", "fixture")
    paths = ["c.py", "b.py", "a.py", "a.py", ""]
    snapshot = await _native(load_from_files, repo_root=repo, ref="HEAD", paths=paths,
        include_paths={"", "a.py", "b.py"},
        bounds=SnapshotBounds(max_files=1, max_diff_bytes=10, max_blob_bytes=7, max_file_bytes=100))
    assert [row.path for row in snapshot.changed_files] == ["a.py"]
    assert [(row.path, row.content, row.truncated, row.omitted_bytes) for row in snapshot.context_blobs] == [
        ("a.py", "abcd", False, 0), ("b.py", "efg", True, 3)]
    assert snapshot.truncation.files_truncated == 1 and snapshot.truncation.diff_truncated
    assert snapshot.truncation.blob_bytes_original == 10 and snapshot.truncation.blob_bytes_kept == 7
    assert snapshot.truncation.blob_truncated and len(snapshot.diff_unified.encode()) == 10
    assert paths == ["c.py", "b.py", "a.py", "a.py", ""]
    assert await _native((repo / "b.py").read_text, encoding="utf-8") == "efghij"


async def test_loopback_pr_filter_handles_empty_rows_and_explicit_empty_selection(monkeypatch):
    clean_network(monkeypatch)
    diff = b"diff --git a/keep.py b/keep.py\n+++ b/keep.py\n+pass\ndiff --git a/omit.txt b/omit.txt\n+++ b/omit.txt\n+text\n"

    async def respond(request):
        path = request[0].split()[1]
        if path.endswith(".diff"):
            return 200, diff
        if path.endswith("/files"):
            return 200, [{}, {"new_filename": "keep.py"}, {"previous_filename": "omit.txt"}]
        return 200, {"base": {"ref": "base"}, "head": {"ref": "head"}}

    async with observed_http_server(respond) as (url, requests):
        for selection, expected in [({"keep.py"}, ["keep.py"]), (set(), [])]:
            result = await _native(load_from_pr, remote=url, repo="org/repo", pr_number=1,
                                  bounds=SnapshotBounds(), include_paths=selection)
            assert [row.path for row in result.changed_files] == expected
            assert ("keep.py" in result.diff_unified) == bool(expected)
            assert "omit.txt" not in result.diff_unified
            assert result.base_ref == "base" and result.head_ref == "head"
        assert len(requests) == 6


@pytest.mark.parametrize("extensions,expected", [(["", "PY"], ["keep.py"]), ([], ["keep.py", "omit.txt"])])
async def test_bound_loopback_review_publishes_selected_snapshot(tmp_path, monkeypatch, extensions, expected):
    clean_network(monkeypatch)
    repo = await _repo(tmp_path, monkeypatch)

    async def respond(request):
        path = request[0].split()[1]
        if path.endswith(".diff"):
            return 200, b"diff --git a/keep.py b/keep.py\n+++ b/keep.py\n+pass\n"
        if path.endswith("/files"):
            return 200, [{"filename": "keep.py"}, {"filename": "omit.txt"}]
        return 200, {"base": {"sha": "a" * 40}, "head": {"sha": "b" * 40}}

    headers = []
    async with observed_http_server(respond, request_headers=headers) as (url, requests):
        await _native(_git, repo, "remote", "add", "origin", url + "/prefix/org/repo.git")
        result = await _native(_service(tmp_path).run_pr, repo_root=repo, remote=url + "/prefix", repo="org/repo", pr=1,
            bounds=SnapshotBounds(), token="public-fixture-token", cli_policy_overrides={
                "input_scope": {"mode": "code_only", "code_extensions": extensions},
                "model_assisted": {"enabled": False}})
        assert result.ok and result.exit_code == 0 and result.model_assisted_enabled is False
        assert len(requests) == 3 and all(h["authorization"] == "token public-fixture-token" for h in headers)
    snapshot = json.loads(await _native((Path(result.artifact_dir) / "snapshot.json").read_text, encoding="utf-8"))
    assert [row["path"] for row in snapshot["changed_files"]] == expected
    assert result.manifest["auth_source"] == "token_flag"
    assert result.control_plane["run_state"] == "completed"
    assert result.control_plane["projection_only"] is True
