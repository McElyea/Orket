from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import stat
from collections.abc import Mapping
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib import parse

import httpx

from orket.adapters.vcs.gitea_export_git import GiteaExportGit
from orket.core.contracts.gitea_export import GiteaExportIntent
from orket.core.domain.outward_authorization import canonical_json
from orket.runtime_paths import resolve_gitea_artifact_cache_root


def _env_enabled(name: str, default: str = "0", *, environment: Mapping[str, str]) -> bool:
    return environment.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _safe_slug(value: str, fallback: str = "value") -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-").lower()
    return normalized if normalized and normalized not in {".", ".."} else fallback


class GiteaArtifactExporter:
    """Prepare exact commits, execute admitted pushes and reconcile through reads."""

    side_effecting = True

    def __init__(self, workspace: Path, *, environment: Mapping[str, str] | None = None,
                 invocation_root: Path | None = None):
        observed, root = dict(os.environ if environment is None else environment), invocation_root or Path.cwd()
        self.workspace = (root / workspace).resolve()
        self._username = observed.get("GITEA_ADMIN_USER", "").strip()
        self._password = observed.get("GITEA_ADMIN_PASSWORD", "").strip()
        self._binding = {
            "enabled": _env_enabled("ORKET_GITEA_ARTIFACT_EXPORT", "0", environment=observed),
            "workspace": str(self.workspace),
            "gitea_url": observed.get("GITEA_URL", "").strip(),
            "owner": (observed.get("ORKET_GITEA_ARTIFACT_OWNER", "").strip()
                      or observed.get("GITEA_PRODUCT_OWNER", "").strip() or self._username),
            "repo_name": observed.get("ORKET_GITEA_ARTIFACT_REPO", "orket-run-artifacts").strip(),
            "branch": observed.get("ORKET_GITEA_ARTIFACT_BRANCH", "main").strip(),
            "prefix": observed.get("ORKET_GITEA_ARTIFACT_PATH_PREFIX", "runs").strip().strip("/"),
            "private_repo": _env_enabled("ORKET_GITEA_ARTIFACT_PRIVATE", "1", environment=observed),
            "cache_root": str(resolve_gitea_artifact_cache_root(observed.get("ORKET_GITEA_ARTIFACT_CACHE_ROOT", "").strip(),
                invocation_root=root, environment=observed)),
            "author_name": observed.get("ORKET_GITEA_ARTIFACT_AUTHOR_NAME", "Orket Artifact Bot"),
            "author_email": observed.get("ORKET_GITEA_ARTIFACT_AUTHOR_EMAIL", "orket@local"),
        }
        target = parse.urlsplit(self._binding["gitea_url"])
        if target.username is not None or target.password is not None:
            raise ValueError("E_GITEA_EXPORT_CREDENTIAL_URL")

    def binding(self) -> dict[str, Any]:
        return dict(self._binding)

    async def prepare_export(self, **run: Any) -> GiteaExportIntent:
        self._validate_settings()
        run_id = str(run["run_id"])
        run_day = date.fromisoformat(run["export_day"]).isoformat()
        suffix = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        run_path = self._binding["prefix"] + "/" + run_day + "/" + _safe_slug(run_id, "run") + "-" + suffix[:12]
        payload_dir = Path(self._binding["cache_root"]) / "payload" / suffix
        await asyncio.to_thread(
            self._build_payload, payload_dir, run_path, run_id, run["run_type"], run["run_name"], run["build_id"],
            run["session_status"], run["summary"], run.get("failure_class"), run.get("failure_reason"), run["export_time"])
        git = self._transport(run_id, run["export_time"])
        await git.initialize()
        base = await git.fetch_head(self._binding["branch"]) if await self._repo_exists() else None
        commit, tree = await git.prepare(payload_dir, run_path, base)
        return GiteaExportIntent(binding=self.binding(), run_id=run_id, commit=commit, tree=tree,
                                 base_commit=base, run_path=run_path)

    async def export_run(self, *, export_intent: GiteaExportIntent | None = None, **run: Any) -> dict[str, Any] | None:
        if not self._binding["enabled"]:
            return None
        intent = self._validate_intent(export_intent)
        if intent.run_id != run["run_id"]:
            raise ValueError("E_GITEA_EXPORT_RUN_CONFLICT")
        await self._ensure_repo()
        git = self._transport(intent.run_id)
        await git.push(intent.commit, intent.tree, intent.run_path, self._binding["branch"])
        receipt = await self.reconcile_export(intent)
        if receipt is None:
            raise ValueError("E_GITEA_EXPORT_PUSH_UNCONFIRMED")
        return receipt

    async def reconcile_export(self, export_intent: GiteaExportIntent) -> dict[str, Any] | None:
        intent = self._validate_intent(export_intent)
        if not await self._repo_exists():
            return None
        git = self._transport(intent.run_id)
        await git.initialize()
        if not await git.confirms(intent.commit, intent.tree, intent.run_path, self._binding["branch"]):
            return None
        manifest = json.loads((await git.command("show", intent.commit + ":" + intent.run_path + "/manifest.json"))[1])
        if manifest.get("run_id") != intent.run_id or manifest.get("export_path") != intent.run_path:
            raise ValueError("E_GITEA_EXPORT_MANIFEST_CONFLICT")
        binding = self._binding
        return {"provider": "gitea", "owner": binding["owner"], "repo": binding["repo_name"],
                "branch": binding["branch"], "path": intent.run_path, "commit": intent.commit, "tree": intent.tree,
                "url": binding["gitea_url"].rstrip("/") + "/" + binding["owner"] + "/" + binding["repo_name"]
                       + "/src/commit/" + intent.commit + "/" + intent.run_path}

    def _validate_settings(self) -> None:
        if not self._binding["enabled"]:
            raise ValueError("E_GITEA_EXPORT_DISABLED")
        target = parse.urlsplit(self._binding["gitea_url"])
        if target.scheme not in {"http", "https"} or not target.netloc or target.query or target.fragment:
            raise ValueError("E_GITEA_EXPORT_TARGET")
        if not self._username or not self._password:
            raise ValueError("E_GITEA_EXPORT_CREDENTIALS_MISSING")
        for field in ("owner", "repo_name", "branch"):
            token = self._binding[field]
            pattern = r"[A-Za-z0-9][A-Za-z0-9._/-]*" if field == "branch" else r"[A-Za-z0-9][A-Za-z0-9._-]*"
            if not re.fullmatch(pattern, token) or ".." in token or token.endswith(("/", ".", ".lock")):
                raise ValueError("E_GITEA_EXPORT_COMPONENT:" + field)
        prefix = self._binding["prefix"]
        if not prefix or "\\" in prefix or ":" in prefix or any(part in {".", ".."} for part in prefix.split("/")):
            raise ValueError("E_GITEA_EXPORT_PREFIX")
        for field in ("author_name", "author_email"):
            if not self._binding[field] or re.search(r"[\r\n<>]", self._binding[field]):
                raise ValueError("E_GITEA_EXPORT_AUTHOR")

    def _validate_intent(self, intent: GiteaExportIntent | None) -> GiteaExportIntent:
        self._validate_settings()
        if intent is None or intent.binding != self.binding():
            raise ValueError("E_GITEA_EXPORT_INTENT_REQUIRED")
        path = PurePosixPath(intent.run_path)
        if path.is_absolute() or ".." in path.parts or "\\" in intent.run_path or ":" in intent.run_path:
            raise ValueError("E_GITEA_EXPORT_PATH_ESCAPE")
        return intent

    def _transport(self, run_id: str, captured_at: str | None = None) -> GiteaExportGit:
        binding = self._binding
        key = hashlib.sha256(canonical_json({"binding": binding, "run_id": run_id}).encode("utf-8")).hexdigest()
        repo_dir = Path(binding["cache_root"]) / "repo_cache" / key
        allowed = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP")
        environment = {key: os.environ[key] for key in allowed if key in os.environ}
        environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                            "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never",
                            "GIT_AUTHOR_NAME": binding["author_name"], "GIT_COMMITTER_NAME": binding["author_name"],
                            "GIT_AUTHOR_EMAIL": binding["author_email"], "GIT_COMMITTER_EMAIL": binding["author_email"]})
        if captured_at:
            environment.update(GIT_AUTHOR_DATE=captured_at, GIT_COMMITTER_DATE=captured_at)
        return GiteaExportGit(repo_dir, self._build_repo_url(binding["gitea_url"], binding["owner"], binding["repo_name"]),
                              self._git_auth_env(self._username, self._password, environment))

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> int:
        async with httpx.AsyncClient(timeout=30, auth=(self._username, self._password)) as client:
            try:
                response = await client.request(method, self._binding["gitea_url"].rstrip("/") + path, json=payload)
            except httpx.HTTPError as exc:
                raise RuntimeError("E_GITEA_EXPORT_HTTP_UNAVAILABLE") from exc
        if response.status_code not in {200, 201, 404, 409}:
            raise RuntimeError("E_GITEA_EXPORT_HTTP_STATUS:" + str(response.status_code))
        return response.status_code

    async def _repo_exists(self) -> bool:
        binding = self._binding
        return await self._request("GET", "/api/v1/repos/" + binding["owner"] + "/" + binding["repo_name"]) == 200

    async def _ensure_repo(self) -> None:
        if await self._repo_exists():
            return
        binding = self._binding
        path = "/api/v1/user/repos" if binding["owner"] == self._username else "/api/v1/orgs/" + binding["owner"] + "/repos"
        await self._request("POST", path, {"name": binding["repo_name"], "private": binding["private_repo"], "auto_init": False})
        if not await self._repo_exists():
            raise RuntimeError("E_GITEA_EXPORT_REPOSITORY_UNCONFIRMED")

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
        captured_at: str,
    ) -> None:
        cache_root = Path(self._binding["cache_root"]).resolve()
        if not payload_dir.resolve().is_relative_to(cache_root) or payload_dir.resolve() == cache_root:
            raise ValueError("E_GITEA_EXPORT_PATH_ESCAPE")
        if payload_dir.exists():
            shutil.rmtree(payload_dir)
        payload_dir.mkdir(parents=True, exist_ok=True)

        observability_dir = self.workspace / "observability" / _safe_slug(run_id, fallback="run")
        agent_output_dir = self.workspace / "agent_output"
        run_log = self.workspace / "orket.log"

        for source in (observability_dir, agent_output_dir, run_log):
            reparse_point = source.exists() and (
                getattr(source.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
            if not source.resolve().is_relative_to(self.workspace) or source.is_symlink() or reparse_point:
                raise ValueError("E_GITEA_EXPORT_SOURCE_ESCAPE")
            if source.is_dir() and any(path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0)
                                       & stat.FILE_ATTRIBUTE_REPARSE_POINT for path in source.rglob("*")):
                raise ValueError("E_GITEA_EXPORT_SOURCE_SYMLINK")

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
            "captured_at": captured_at,
            "source_workspace": str(self.workspace),
            "export_path": run_path,
            "failure_class": failure_class,
            "failure_reason": failure_reason,
            "summary": summary,
        }
        (payload_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _build_repo_url(self, base_url: str, owner: str, repo: str) -> str:
        parsed = parse.urlparse(base_url)
        scheme = parsed.scheme or "http"
        if parsed.netloc:
            host = parsed.netloc
            base_path = parsed.path
        else:
            host = parsed.path
            base_path = ""
        normalized_path = base_path.strip("/")
        if normalized_path:
            normalized_path = f"/{normalized_path}"
        return f"{scheme}://{host}{normalized_path}/{owner}/{repo}.git"

    def _git_auth_env(self, username: str, password: str, environment: dict[str, str] | None = None) -> dict[str, str]:
        auth_value = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        env = dict(os.environ if environment is None else environment)
        try:
            config_count = max(0, int(str(env.get("GIT_CONFIG_COUNT", "0"))))
        except ValueError:
            config_count = 0
        env[f"GIT_CONFIG_KEY_{config_count}"] = "http.extraHeader"
        env[f"GIT_CONFIG_VALUE_{config_count}"] = f"Authorization: Basic {auth_value}"
        env["GIT_CONFIG_COUNT"] = str(config_count + 1)
        return env
