from __future__ import annotations

import asyncio
import json
import sqlite3
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiofiles
import httpx

try:
    from scripts.gitea.inspect_local_runner_containers import build_runner_container_report, run_command
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from gitea.inspect_local_runner_containers import build_runner_container_report, run_command


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def workflow_path_matches(run_payload: dict[str, Any], workflow_id: str) -> bool:
    return str(run_payload.get("path") or "").startswith(f"{workflow_id}@")


async def write_runner_config(config_path: Path) -> None:
    await asyncio.to_thread(config_path.parent.mkdir, parents=True, exist_ok=True)
    config_payload = "\n".join(
        [
            "log:",
            "  level: info",
            "runner:",
            "  file: /data/.runner",
            "  capacity: 1",
            "  fetch_timeout: 5s",
            "  fetch_interval: 2s",
            "container:",
            "  options: --add-host=host.docker.internal:host-gateway",
            "",
        ]
    )
    async with aiofiles.open(config_path, "w", encoding="utf-8", newline="\n") as handle:
        await handle.write(config_payload)


async def list_docker_rows() -> list[dict[str, str]]:
    result = await run_command("docker", "ps", "-a", "--format", "{{json .}}")
    if result.returncode != 0:
        failure = result.stderr.strip() or result.stdout.strip() or "docker ps -a failed"
        raise RuntimeError(f"Unable to list Docker containers: {failure}")
    rows: list[dict[str, str]] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


async def list_non_allowlisted_containers(allowlist: set[str]) -> list[dict[str, str]]:
    return [
        {
            "name": str(row.get("Names") or "").strip(),
            "image": str(row.get("Image") or "").strip(),
            "status": str(row.get("Status") or "").strip(),
        }
        for row in await list_docker_rows()
        if str(row.get("Names") or "").strip() and str(row.get("Names") or "").strip() not in allowlist
    ]


async def remove_containers(names: list[str]) -> list[dict[str, Any]]:
    cleanup: list[dict[str, Any]] = []
    for name in names:
        result = await run_command("docker", "rm", "-f", "-v", name)
        cleanup.append(
            {
                "name": name,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        )
    return cleanup


async def create_temp_access_token(gitea_container: str, username: str, token_name: str) -> str:
    result = await run_command(
        "docker",
        "exec",
        "-u",
        "git",
        gitea_container,
        "/usr/local/bin/gitea",
        "admin",
        "user",
        "generate-access-token",
        "--username",
        username,
        "--token-name",
        token_name,
        "--scopes",
        "all",
        "--raw",
    )
    token = result.stdout.strip()
    if result.returncode != 0 or not token:
        failure = result.stderr.strip() or result.stdout.strip() or "unable to create temp access token"
        raise RuntimeError(f"Unable to create temp Gitea token: {failure}")
    return token


async def delete_user_token(client: httpx.AsyncClient, username: str, token_name: str) -> dict[str, Any]:
    response = await client.delete(f"/api/v1/users/{username}/tokens/{token_name}")
    return {
        "status_code": response.status_code,
        "deleted": response.status_code in {204, 404},
        "response_text": response.text.strip(),
    }


def _delete_access_tokens_sync(gitea_db: Path, token_names: list[str]) -> int:
    if not token_names:
        return 0
    connection = sqlite3.connect(gitea_db)
    try:
        cursor = connection.cursor()
        cursor.executemany("DELETE FROM access_token WHERE name = ?", [(name,) for name in token_names])
        deleted = int(cursor.rowcount)
        connection.commit()
        return deleted
    finally:
        connection.close()


async def delete_access_tokens(gitea_db: Path, token_names: list[str]) -> int:
    return await asyncio.to_thread(_delete_access_tokens_sync, gitea_db, token_names)


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
) -> Any:
    response = await client.request(method, path, json=payload)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed with {response.status_code}: {response.text.strip()}")
    if not response.text.strip():
        return None
    return response.json()


async def list_repo_runners(client: httpx.AsyncClient, owner: str, repo: str) -> list[dict[str, Any]]:
    payload = await request_json(client, "GET", f"/api/v1/repos/{owner}/{repo}/actions/runners")
    return list(payload.get("runners") or [])


async def list_workflow_runs(client: httpx.AsyncClient, owner: str, repo: str) -> list[dict[str, Any]]:
    payload = await request_json(client, "GET", f"/api/v1/repos/{owner}/{repo}/actions/runs?limit=25")
    return list(payload.get("workflow_runs") or [])


async def get_workflow_run(client: httpx.AsyncClient, owner: str, repo: str, run_id: int) -> dict[str, Any]:
    return dict(await request_json(client, "GET", f"/api/v1/repos/{owner}/{repo}/actions/runs/{run_id}"))


async def list_run_jobs(client: httpx.AsyncClient, owner: str, repo: str, run_id: int) -> list[dict[str, Any]]:
    payload = await request_json(client, "GET", f"/api/v1/repos/{owner}/{repo}/actions/runs/{run_id}/jobs")
    return list(payload.get("jobs") or [])


async def dispatch_workflow(client: httpx.AsyncClient, owner: str, repo: str, workflow_id: str, ref: str) -> None:
    response = await client.post(
        f"/api/v1/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
        json={"ref": ref},
    )
    if response.status_code != 204:
        body = response.text.strip() or "no response body"
        raise RuntimeError(f"Workflow dispatch failed with {response.status_code}: {body}")


def completed_job_count(jobs: list[dict[str, Any]]) -> int:
    return sum(1 for job in jobs if str(job.get("status") or "") == "completed")


async def find_new_run_id(
    client: httpx.AsyncClient,
    *,
    owner: str,
    repo: str,
    workflow_id: str,
    previous_max_run_id: int,
    deadline: float,
    poll_interval_seconds: float,
) -> int:
    loop = asyncio.get_running_loop()
    while loop.time() < deadline:
        matches = [
            run
            for run in await list_workflow_runs(client, owner, repo)
            if workflow_path_matches(run, workflow_id) and int(run.get("id") or 0) > previous_max_run_id
        ]
        if matches:
            return max(int(run.get("id") or 0) for run in matches)
        await asyncio.sleep(poll_interval_seconds)
    raise RuntimeError("Timed out waiting for dispatched workflow run to appear.")


async def delete_repo_runners_by_prefix(
    client: httpx.AsyncClient,
    *,
    owner: str,
    repo: str,
    name_prefix: str,
) -> list[dict[str, Any]]:
    cleanup: list[dict[str, Any]] = []
    for runner in await list_repo_runners(client, owner, repo):
        runner_id = str(runner.get("id") or "")
        runner_name = str(runner.get("name") or "")
        if not runner_id or not runner_name.startswith(name_prefix):
            continue
        response = await client.delete(f"/api/v1/repos/{owner}/{repo}/actions/runners/{runner_id}")
        cleanup.append(
            {
                "runner_id": runner_id,
                "runner_name": runner_name,
                "status_code": response.status_code,
                "deleted": response.status_code in {204, 404},
            }
        )
    return cleanup


async def wait_for_container_exit(container_name: str, timeout_seconds: int, poll_interval_seconds: float) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        result = await run_command("docker", "inspect", "-f", "{{.State.Status}}", container_name)
        status = result.stdout.strip().lower()
        if result.returncode != 0 or status in {"exited", "dead"}:
            return
        await asyncio.sleep(poll_interval_seconds)
    raise RuntimeError(f"Timed out waiting for runner container {container_name} to finish.")


async def run_ephemeral_attempt(
    *,
    repo_root: Path,
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    gitea_url: str,
    runner_image: str,
    runner_labels: str,
    prefix: str,
    attempt_number: int,
    attempt_timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    runner_name = f"{prefix}-{attempt_number}"
    attempt_root = repo_root / ".tmp" / "gitea_runner_lifecycle_proof" / runner_name
    await write_runner_config(attempt_root / "config.yaml")
    registration = await request_json(
        client,
        "POST",
        f"/api/v1/repos/{owner}/{repo}/actions/runners/registration-token",
    )
    registration_token = str(registration.get("token") or "").strip()
    if not registration_token:
        raise RuntimeError("Gitea returned an empty runner registration token.")

    register_result = await run_command(
        "docker",
        "run",
        "--rm",
        "--add-host=host.docker.internal:host-gateway",
        "-v",
        f"{attempt_root.resolve()}:/data",
        "-w",
        "/data",
        "--entrypoint",
        "act_runner",
        runner_image,
        "register",
        "--config",
        "/data/config.yaml",
        "--instance",
        gitea_url.replace("localhost", "host.docker.internal"),
        "--token",
        registration_token,
        "--name",
        runner_name,
        "--labels",
        runner_labels,
        "--no-interactive",
        "--ephemeral",
    )
    if register_result.returncode != 0:
        failure = register_result.stderr.strip() or register_result.stdout.strip() or "runner registration failed"
        raise RuntimeError(f"Runner registration failed for {runner_name}: {failure}")

    daemon_result = await run_command(
        "docker",
        "run",
        "-d",
        "--name",
        runner_name,
        "--add-host=host.docker.internal:host-gateway",
        "-v",
        f"{attempt_root.resolve()}:/data",
        "-w",
        "/data",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "--entrypoint",
        "act_runner",
        runner_image,
        "daemon",
        "--config",
        "/data/config.yaml",
    )
    if daemon_result.returncode != 0:
        failure = daemon_result.stderr.strip() or daemon_result.stdout.strip() or "runner daemon failed to start"
        raise RuntimeError(f"Runner daemon failed for {runner_name}: {failure}")

    await wait_for_container_exit(runner_name, attempt_timeout_seconds, poll_interval_seconds)
    log_result = await run_command("docker", "logs", runner_name)
    remove_result = await run_command("docker", "rm", "-f", runner_name)
    deleted_runners = await delete_repo_runners_by_prefix(client, owner=owner, repo=repo, name_prefix=runner_name)
    await asyncio.to_thread(shutil.rmtree, attempt_root, True)
    return {
        "attempt_number": attempt_number,
        "runner_name": runner_name,
        "register_stdout": register_result.stdout.strip(),
        "register_stderr": register_result.stderr.strip(),
        "daemon_container_id": daemon_result.stdout.strip(),
        "daemon_logs": ((log_result.stdout or "") + (log_result.stderr or "")).strip(),
        "container_remove": {
            "returncode": remove_result.returncode,
            "stdout": remove_result.stdout.strip(),
            "stderr": remove_result.stderr.strip(),
        },
        "deleted_repo_runners": deleted_runners,
    }


async def collect_state(
    *,
    repo_root: Path,
    gitea_db: Path,
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    workflow_id: str,
    allowlist: set[str],
) -> dict[str, Any]:
    runner_report = await build_runner_container_report(
        repo_root=repo_root,
        gitea_db=gitea_db,
        execute_stray_cleanup=False,
        skip_logs=True,
    )
    return {
        "runner_report": runner_report,
        "repo_runners": await list_repo_runners(client, owner, repo),
        "non_infrastructure_containers": await list_non_allowlisted_containers(allowlist),
        "active_workflow_runs": [
            {
                "id": int(run.get("id") or 0),
                "status": str(run.get("status") or ""),
                "conclusion": str(run.get("conclusion") or ""),
                "path": str(run.get("path") or ""),
            }
            for run in await list_workflow_runs(client, owner, repo)
            if workflow_path_matches(run, workflow_id) and str(run.get("status") or "") != "completed"
        ],
    }
