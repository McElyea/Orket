from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class DeploymentSpec:
    required_files: Dict[str, str]


class DeploymentValidationError(Exception):
    """Raised when deployment planning validation fails."""


class DeploymentPlanner:
    """
    Deterministic deployment planning stage.

    Emits baseline deployment assets for generated projects.
    """

    _DEFAULT_FILES: Dict[str, str] = {
        "agent_output/deployment/Dockerfile": (
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY . /app\n"
            "CMD [\"python\", \"agent_output/main.py\"]\n"
        ),
        "agent_output/deployment/docker-compose.yml": (
            "services:\n"
            "  app:\n"
            "    build:\n"
            "      context: ../../\n"
            "      dockerfile: agent_output/deployment/Dockerfile\n"
            "    command: python agent_output/main.py\n"
        ),
        "agent_output/deployment/run_local.sh": (
            "#!/usr/bin/env sh\n"
            "set -e\n"
            "python agent_output/main.py\n"
        ),
    }
    _BACKEND_ONLY_FILES: Dict[str, str] = {
        "agent_output/deployment/Dockerfile": (
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY . /app\n"
            "CMD [\"python\", \"agent_output/main.py\"]\n"
        ),
        "agent_output/deployment/run_local.sh": (
            "#!/usr/bin/env sh\n"
            "set -e\n"
            "python agent_output/main.py\n"
        ),
    }
    _API_VUE_FILES: Dict[str, str] = {
        "agent_output/deployment/Dockerfile": (
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY . /app\n"
            "CMD [\"python\", \"agent_output/main.py\"]\n"
        ),
        "agent_output/deployment/docker-compose.yml": (
            "services:\n"
            "  api:\n"
            "    build:\n"
            "      context: ../../\n"
            "      dockerfile: agent_output/deployment/Dockerfile\n"
            "    command: python agent_output/main.py\n"
            "  frontend:\n"
            "    image: node:20-alpine\n"
            "    working_dir: /app/agent_output/frontend\n"
            "    command: sh -c \"echo frontend placeholder\"\n"
        ),
        "agent_output/deployment/run_local.sh": (
            "#!/usr/bin/env sh\n"
            "set -e\n"
            "python agent_output/main.py\n"
        ),
    }

    def __init__(
        self,
        workspace_root: Path,
        file_tools: Any,
        organization: Any = None,
        project_surface_profile: str | None = None,
    ):
        self.workspace_root = workspace_root
        self.file_tools = file_tools
        self.organization = organization
        self.project_surface_profile = str(project_surface_profile or "").strip().lower()

    async def ensure(self) -> Dict[str, Any]:
        spec = self._resolve_spec()
        created_files = await self._ensure_files(spec.required_files)
        await self._validate_required_files(spec.required_files)
        return {
            "created_files": created_files,
            "required_files": sorted(spec.required_files.keys()),
        }

    def _resolve_spec(self) -> DeploymentSpec:
        rules = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            rules = self.organization.process_rules
        required_files = self._normalize_file_map(
            rules.get("deployment_planner_required_files"),
            self._DEFAULT_FILES,
        )
        profile = self.project_surface_profile or str(
            rules.get("project_surface_profile", "unspecified")
        ).strip().lower()
        if profile in {"backend_only", "cli", "tui"}:
            required_files = dict(self._BACKEND_ONLY_FILES)
        elif profile == "api_vue":
            required_files = dict(self._API_VUE_FILES)
        return DeploymentSpec(required_files=dict(required_files))

    async def _ensure_files(self, required_files: Mapping[str, str]) -> List[str]:
        created: List[str] = []
        for rel_path, content in required_files.items():
            target = self.workspace_root / rel_path
            exists = await asyncio.to_thread(target.exists)
            if exists:
                continue
            await self.file_tools.write_file(rel_path, content)
            created.append(rel_path)
        return created

    async def _validate_required_files(self, required_files: Mapping[str, str]) -> None:
        missing = []
        for rel_path in required_files.keys():
            exists = await asyncio.to_thread((self.workspace_root / rel_path).is_file)
            if not exists:
                missing.append(rel_path)
        if missing:
            raise DeploymentValidationError(
                "missing deployment files: " + ", ".join(sorted(missing))
            )

    @staticmethod
    def _normalize_file_map(raw: Any, default: Mapping[str, str]) -> Dict[str, str]:
        if isinstance(raw, dict):
            normalized = {}
            for key, value in raw.items():
                key_str = str(key).strip()
                if not key_str:
                    continue
                normalized[key_str] = str(value)
            if normalized:
                return normalized
        return dict(default)
