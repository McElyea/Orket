from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import parse

import httpx
from orket.runtime_paths import resolve_gitea_artifact_cache_root


def _env_enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _safe_slug(value: str, fallback: str = "value") -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-").lower()
    return normalized or fallback


@dataclass
class _GiteaClient:
    base_url: str
    username: str
    password: str
    timeout_sec: int = 30

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, str]:
        url = f"{self.base_url.rstrip('/')}{path}"
        try:
            with httpx.Client(
                timeout=self.timeout_sec,
                auth=(self.username, self.password),
                headers={"Content-Type": "application/json"},
            ) as client:
                resp = client.request(method=method, url=url, json=payload)
                return int(resp.status_code), resp.text
        except httpx.HTTPError as exc:
            return 0, str(exc)

    def repo_exists(self, owner: str, repo: str) -> bool:
        status, _ = self._request("GET", f"/api/v1/repos/{owner}/{repo}")
        return status == 200

    def create_repo(self, owner: str, repo: str, private: bool = True) -> bool:
        status, _ = self._request("POST", f"/api/v1/orgs/{owner}/repos", {"name": repo, "private": private})
        if status in {201, 409}:
            return True
        status, _ = self._request("POST", "/api/v1/user/repos", {"name": repo, "private": private})
        return status in {201, 409}


class GiteaArtifactExporter:
    """
    Best-effort exporter for raw run artifacts to a local Gitea repository.
    """

    _lock = asyncio.Lock()

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)

    async def export_run(
        self,
        *,
        run_id: str,
        run_type: str,
        run_name: str,
        build_id: str,
        session_status: str,
        summary: Dict[str, Any],
        failure_class: str | None = None,
        failure_reason: str | None = None,
    ) -> dict[str, Any] | None:
        if not _env_enabled("ORKET_GITEA_ARTIFACT_EXPORT", "0"):
            return None

        gitea_url = os.getenv("GITEA_URL", "").strip()
        username = os.getenv("GITEA_ADMIN_USER", "").strip()
        password = os.getenv("GITEA_ADMIN_PASSWORD", "").strip()
        owner = (
            os.getenv("ORKET_GITEA_ARTIFACT_OWNER", "").strip()
            or os.getenv("GITEA_PRODUCT_OWNER", "").strip()
            or username
        )
        repo_name = os.getenv("ORKET_GITEA_ARTIFACT_REPO", "orket-run-artifacts").strip()
        branch = os.getenv("ORKET_GITEA_ARTIFACT_BRANCH", "main").strip()
        prefix = os.getenv("ORKET_GITEA_ARTIFACT_PATH_PREFIX", "runs").strip().strip("/")
        private_repo = _env_enabled("ORKET_GITEA_ARTIFACT_PRIVATE", "1")

        required = {"GITEA_URL": gitea_url, "GITEA_ADMIN_USER": username, "GITEA_ADMIN_PASSWORD": password, "OWNER": owner}
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing Gitea artifact export settings: {', '.join(missing)}")

        client = _GiteaClient(base_url=gitea_url, username=username, password=password)
        if not client.repo_exists(owner, repo_name):
            created = client.create_repo(owner, repo_name, private=private_repo)
            if not created:
                raise RuntimeError(f"Failed to create artifacts repo {owner}/{repo_name}")

        run_day = datetime.now(UTC).strftime("%Y-%m-%d")
        run_slug = _safe_slug(run_id, fallback="run")
        run_path = f"{prefix}/{run_day}/{run_slug}"

        cache_root_env = os.getenv("ORKET_GITEA_ARTIFACT_CACHE_ROOT", "").strip()
        export_root = resolve_gitea_artifact_cache_root(cache_root_env)
        payload_dir = export_root / "payload" / run_slug
        repo_dir = export_root / "repo_cache" / f"{_safe_slug(owner)}_{_safe_slug(repo_name)}"

        await asyncio.to_thread(self._build_payload, payload_dir, run_path, run_id, run_type, run_name, build_id, session_status, summary, failure_class, failure_reason)
        async with self._lock:
            commit = await asyncio.to_thread(
                self._commit_payload,
                repo_dir,
                payload_dir,
                gitea_url,
                owner,
                repo_name,
                username,
                password,
                branch,
                run_path,
                run_id,
                session_status,
            )

        web_url = f"{gitea_url.rstrip('/')}/{owner}/{repo_name}/src/branch/{branch}/{run_path}"
        return {
            "provider": "gitea",
            "owner": owner,
            "repo": repo_name,
            "branch": branch,
            "path": run_path,
            "url": web_url,
            "commit": commit,
        }

    def _build_payload(
        self,
        payload_dir: Path,
        run_path: str,
        run_id: str,
        run_type: str,
        run_name: str,
        build_id: str,
        session_status: str,
        summary: dict[str, Any],
        failure_class: str | None,
        failure_reason: str | None,
    ) -> None:
        if payload_dir.exists():
            shutil.rmtree(payload_dir)
        payload_dir.mkdir(parents=True, exist_ok=True)

        observability_dir = self.workspace / "observability" / _safe_slug(run_id, fallback=run_id)
        agent_output_dir = self.workspace / "agent_output"
        run_log = self.workspace / "orket.log"

        if observability_dir.exists():
            shutil.copytree(observability_dir, payload_dir / "observability", dirs_exist_ok=True)
        if agent_output_dir.exists():
            shutil.copytree(agent_output_dir, payload_dir / "agent_output", dirs_exist_ok=True)
        if run_log.exists():
            shutil.copy2(run_log, payload_dir / "orket.log")

        manifest = {
            "run_id": run_id,
            "run_type": run_type,
            "run_name": run_name,
            "build_id": build_id,
            "session_status": session_status,
            "captured_at": datetime.now(UTC).isoformat(),
            "source_workspace": str(self.workspace),
            "export_path": run_path,
            "failure_class": failure_class,
            "failure_reason": failure_reason,
            "summary": summary,
        }
        (payload_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _commit_payload(
        self,
        repo_dir: Path,
        payload_dir: Path,
        gitea_url: str,
        owner: str,
        repo_name: str,
        username: str,
        password: str,
        branch: str,
        run_path: str,
        run_id: str,
        session_status: str,
    ) -> str:
        self._run_cmd(["git", "--version"], cwd=self.workspace)

        if not repo_dir.exists():
            repo_dir.mkdir(parents=True, exist_ok=True)
            self._run_cmd(["git", "init"], cwd=repo_dir)
            self._run_cmd(["git", "config", "user.email", os.getenv("ORKET_GITEA_ARTIFACT_AUTHOR_EMAIL", "orket@local")], cwd=repo_dir)
            self._run_cmd(["git", "config", "user.name", os.getenv("ORKET_GITEA_ARTIFACT_AUTHOR_NAME", "Orket Artifact Bot")], cwd=repo_dir)
        self._run_cmd(["git", "config", "core.longpaths", "true"], cwd=repo_dir, allow_fail=True)

        push_url = self._build_push_url(gitea_url, owner, repo_name, username, password)
        remotes = self._run_cmd(["git", "remote"], cwd=repo_dir, allow_fail=True)
        if "origin" in remotes.split():
            self._run_cmd(["git", "remote", "set-url", "origin", push_url], cwd=repo_dir)
        else:
            self._run_cmd(["git", "remote", "add", "origin", push_url], cwd=repo_dir)

        self._run_cmd(["git", "fetch", "origin", branch], cwd=repo_dir, allow_fail=True)
        remote_head = self._run_cmd(["git", "ls-remote", "--heads", "origin", branch], cwd=repo_dir, allow_fail=True)
        if remote_head.strip():
            self._run_cmd(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=repo_dir)
        else:
            self._run_cmd(["git", "checkout", "-B", branch], cwd=repo_dir)

        target_dir = repo_dir / run_path
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(payload_dir, target_dir, dirs_exist_ok=True)

        self._run_cmd(["git", "add", run_path], cwd=repo_dir)
        commit_msg = f"artifact run {run_id} status {session_status}"
        commit_out = self._run_cmd(["git", "commit", "-m", commit_msg], cwd=repo_dir, allow_fail=True)
        if "nothing to commit" in commit_out.lower():
            return self._run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir).strip()

        self._run_cmd(["git", "push", "origin", branch], cwd=repo_dir)
        return self._run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir).strip()

    def _build_push_url(self, base_url: str, owner: str, repo: str, username: str, password: str) -> str:
        parsed = parse.urlparse(base_url)
        scheme = parsed.scheme or "http"
        host = parsed.netloc or parsed.path
        user = parse.quote(username, safe="")
        pw = parse.quote(password, safe="")
        return f"{scheme}://{user}:{pw}@{host}/{owner}/{repo}.git"

    def _run_cmd(self, cmd: list[str], cwd: Path, allow_fail: bool = False) -> str:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0 and not allow_fail:
            raise RuntimeError(
                f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )
        return "\n".join(part for part in (stdout, stderr) if part).strip()
