"""Owned localhost Gitea for explicitly selected integration acceptance."""
from __future__ import annotations

import asyncio
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import httpx


@dataclass(frozen=True)
class LocalGitea:
    url: str
    container_id: str
    username: str = "export-proof"
    password: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)

    def export_environment(self, cache_root: str) -> dict[str, str]:
        return {"ORKET_GITEA_ARTIFACT_EXPORT": "1", "GITEA_URL": self.url,
                "GITEA_ADMIN_USER": self.username, "GITEA_ADMIN_PASSWORD": self.password,
                "ORKET_GITEA_ARTIFACT_OWNER": self.username, "ORKET_GITEA_ARTIFACT_REPO": "artifacts",
                "ORKET_GITEA_ARTIFACT_BRANCH": "main", "ORKET_GITEA_ARTIFACT_PATH_PREFIX": "runs",
                "ORKET_GITEA_ARTIFACT_CACHE_ROOT": cache_root, "ORKET_DISABLE_SANDBOX": "1"}


async def docker(*args: str, allow_failure: bool = False, strip_output: bool = True) -> str:
    child = await asyncio.create_subprocess_exec("docker", *args, stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)
    try:
        stdout, _stderr = await asyncio.wait_for(child.communicate(), timeout=60)
    finally:
        if child.returncode is None:
            child.kill()
            await child.communicate()
    if child.returncode and not allow_failure:
        # Admin creation arguments contain a generated secret; never echo argv/output.
        raise RuntimeError("Local Gitea Docker operation failed")
    output = stdout.decode("utf-8", errors="replace")
    return output.strip() if strip_output else output


async def wait_ready(server: LocalGitea) -> None:
    deadline = time.monotonic() + 60
    async with httpx.AsyncClient(timeout=2) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(server.url + "/api/v1/version")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass  # Expected during this bounded startup poll; timeout remains a failure.
            await asyncio.sleep(0.5)
    raise TimeoutError("Owned localhost Gitea did not become ready")


async def get_visible(server: LocalGitea, path: str, *, params: dict[str, str] | None = None) -> httpx.Response:
    """Wait only for Gitea's post-receive empty-repository projection to catch up."""
    deadline = time.monotonic() + 20
    async with httpx.AsyncClient(auth=(server.username, server.password), timeout=5) as client:
        while True:
            response = await client.get(server.url + path, params=params)
            if response.status_code != 409 or time.monotonic() >= deadline:
                response.raise_for_status()
                return response
            await asyncio.sleep(0.1)


@asynccontextmanager
async def local_gitea(*, webhook_host: str | None = None):
    name = "orket-acceptance-gitea-" + uuid.uuid4().hex
    webhook_options = ["--env", "GITEA__webhook__ALLOWED_HOST_LIST=" + webhook_host] if webhook_host else []
    container_id = await docker(
        "run", "--detach", "--name", name, "--label", "orket.acceptance=epic-export",
        "--publish", "127.0.0.1::3000", "--env", "GITEA__database__DB_TYPE=sqlite3",
        "--env", "GITEA__security__INSTALL_LOCK=true", "--env", "GITEA__service__DISABLE_REGISTRATION=true",
        "--env", "GITEA__actions__ENABLED=false", "--env", "GITEA__server__DISABLE_SSH=true",
        *webhook_options, "gitea/gitea:1.25")
    try:
        port = (await docker("port", container_id, "3000/tcp")).rsplit(":", 1)[-1]
        server = LocalGitea(url="http://127.0.0.1:" + port, container_id=container_id)
        await wait_ready(server)
        await docker("exec", "--user", "git", container_id, "gitea", "admin", "user", "create",
                     "--username", server.username, "--password", server.password,
                     "--email", "export-proof@localhost.invalid", "--admin", "--must-change-password=false")
        yield server
    finally:
        await docker("rm", "--force", "--volumes", container_id)
        assert not await docker("ps", "--all", "--quiet", "--filter", "id=" + container_id)
