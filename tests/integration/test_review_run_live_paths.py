# Layer: end-to-end

from __future__ import annotations

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.application.review.models import SnapshotBounds
from orket.application.review.run_service import ReviewRunService
from orket.capabilities.sync_bridge import run_coro_sync
from orket.core.domain import RunState


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")


class _StubGiteaServer:
    def __init__(self) -> None:
        self.requests: list[dict[str, str]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_type())
        host, port = self._server.server_address
        self.base_url = f"http://{host}:{port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def _handler_type(self):
        owner = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return None

            def do_GET(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0]
                owner.requests.append(
                    {
                        "path": path,
                        "authorization": str(self.headers.get("Authorization") or ""),
                        "accept": str(self.headers.get("Accept") or ""),
                    }
                )
                if path == "/api/v1/repos/org/repo/pulls/7":
                    self._send_json(
                        {
                            "title": "Live PR",
                            "base": {"sha": "base-sha", "ref": "main", "repo": {"id": 17}},
                            "head": {"sha": "head-sha", "ref": "feature"},
                            "user": {"login": "tester"},
                            "labels": [{"name": "ship-risk"}],
                        }
                    )
                    return
                if path == "/api/v1/repos/org/repo/pulls/7/files":
                    self._send_json(
                        [
                            {
                                "filename": "orket/demo.py",
                                "status": "modified",
                                "additions": 1,
                                "deletions": 1,
                            }
                        ]
                    )
                    return
                if path == "/api/v1/repos/org/repo/pulls/7.diff":
                    self._send_text(
                        "diff --git a/orket/demo.py b/orket/demo.py\n"
                        "--- a/orket/demo.py\n"
                        "+++ b/orket/demo.py\n"
                        "@@ -1 +1 @@\n"
                        "-print('old')\n"
                        "+print('ok')\n"
                    )
                    return
                self.send_response(404)
                self.end_headers()

            def _send_json(self, payload: object) -> None:
                body = __import__("json").dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_text(self, payload: str) -> None:
                body = payload.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return _Handler

    def __enter__(self) -> _StubGiteaServer:
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)


def test_review_run_pr_sends_token_only_to_bound_live_remote(tmp_path: Path) -> None:
    """Layer: end-to-end. Verifies PR review succeeds against a live local remote only when it is bound to the repo remote."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    workspace = tmp_path / "workspace" / "default"
    control_plane_db = tmp_path / "control_plane.sqlite3"
    service = ReviewRunService(workspace=workspace, control_plane_db_path=control_plane_db)

    with _StubGiteaServer() as server:
        _git(repo, "remote", "add", "origin", f"{server.base_url}/org/repo.git")

        result = service.run_pr(
            remote=server.base_url,
            repo="org/repo",
            pr=7,
            repo_root=repo,
            bounds=SnapshotBounds(),
            token="live-secret",
        )

    assert result.ok is True
    assert result.manifest["auth_source"] == "token_flag"
    assert result.manifest["control_plane_run_id"] == result.run_id
    assert result.control_plane is not None
    assert result.control_plane["projection_source"] == "control_plane_records"
    assert result.control_plane["projection_only"] is True
    assert result.control_plane["run_state"] == "completed"
    assert result.control_plane["attempt_state"] == "attempt_completed"
    snapshot_payload = json.loads((Path(result.artifact_dir) / "snapshot.json").read_text(encoding="utf-8"))
    assert snapshot_payload["repo"]["remote"] == server.base_url
    assert [row["path"] for row in snapshot_payload["changed_files"]] == ["orket/demo.py"]
    assert [request["path"] for request in server.requests] == [
        "/api/v1/repos/org/repo/pulls/7",
        "/api/v1/repos/org/repo/pulls/7/files",
        "/api/v1/repos/org/repo/pulls/7.diff",
    ]
    assert {request["authorization"] for request in server.requests} == {"token live-secret"}
    execution_repo = AsyncControlPlaneExecutionRepository(control_plane_db)
    persisted_run = run_coro_sync(execution_repo.get_run_record(run_id=result.run_id))
    assert persisted_run is not None
    assert persisted_run.lifecycle_state is RunState.COMPLETED


def test_review_run_pr_blocks_unbound_live_remote_before_request(tmp_path: Path) -> None:
    """Layer: end-to-end. Verifies PR review refuses an unbound remote before any live HTTP request is sent."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "remote", "add", "origin", "https://trusted.example/org/repo.git")
    workspace = tmp_path / "workspace" / "default"
    service = ReviewRunService(workspace=workspace, control_plane_db_path=tmp_path / "control_plane.sqlite3")

    with _StubGiteaServer() as server:
        with pytest.raises(ValueError, match="not bound to a configured git remote"):
            service.run_pr(
                remote=server.base_url,
                repo="org/repo",
                pr=7,
                repo_root=repo,
                bounds=SnapshotBounds(),
                token="live-secret",
            )

        assert server.requests == []


def test_review_run_files_missing_ref_path_fails_closed_live(tmp_path: Path) -> None:
    """Layer: end-to-end. Verifies review files fails closed when a requested file cannot be loaded from the requested ref."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "existing.py").write_text("print('ok')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    ref = _git(repo, "rev-parse", "HEAD")

    workspace = tmp_path / "workspace" / "default"
    service = ReviewRunService(workspace=workspace, control_plane_db_path=tmp_path / "control_plane.sqlite3")

    with pytest.raises(FileNotFoundError, match="missing.py"):
        service.run_files(
            repo_root=repo,
            ref=ref,
            paths=["missing.py"],
            bounds=SnapshotBounds(),
        )
