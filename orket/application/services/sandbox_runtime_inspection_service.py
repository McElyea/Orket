from __future__ import annotations

import json
from typing import Any

from orket.adapters.storage.command_runner import CommandRunner


OPTIONAL_SANDBOX_HEALTH_SERVICES = frozenset({"pgadmin", "mongo-express"})


class SandboxRuntimeInspectionService:
    """Reads live Docker runtime state without depending on a compose file."""

    def __init__(self, *, command_runner: CommandRunner) -> None:
        self.command_runner = command_runner

    async def list_project_container_rows(self, *, compose_project: str) -> list[dict[str, Any]]:
        result = await self.command_runner.run_async(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )
        if result.returncode != 0:
            return []
        rows: list[dict[str, Any]] = []
        for row in self._parse_rows(result.stdout):
            name = str(row.get("Names") or "").strip()
            if not name:
                continue
            labels = self._parse_label_blob(row.get("Labels"))
            rows.append(
                {
                    "Name": name,
                    "Service": str(labels.get("com.docker.compose.service") or "").strip(),
                    "State": str(row.get("State") or "").strip(),
                    "Status": str(row.get("Status") or "").strip(),
                }
            )
        return sorted(rows, key=lambda item: str(item.get("Name") or ""))

    @staticmethod
    def tracked_container_rows(container_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        labeled_rows = [row for row in container_rows if str(row.get("Service") or "").strip()]
        core_rows = [
            row for row in labeled_rows if str(row.get("Service") or "").strip() not in OPTIONAL_SANDBOX_HEALTH_SERVICES
        ]
        if labeled_rows:
            return core_rows
        return container_rows

    @classmethod
    def all_core_services_running(cls, container_rows: list[dict[str, Any]]) -> bool:
        tracked_rows = cls.tracked_container_rows(container_rows)
        return bool(tracked_rows) and all(str(row.get("State") or "").strip() == "running" for row in tracked_rows)

    @staticmethod
    def _parse_rows(raw: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in str(raw or "").splitlines():
            token = line.strip()
            if not token:
                continue
            parsed = json.loads(token)
            if isinstance(parsed, dict):
                rows.append(parsed)
        return rows

    @staticmethod
    def _parse_label_blob(raw: object) -> dict[str, str]:
        labels: dict[str, str] = {}
        for entry in str(raw or "").split(","):
            key, _, value = entry.partition("=")
            if key:
                labels[key.strip()] = value.strip()
        return labels
