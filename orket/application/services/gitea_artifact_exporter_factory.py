"""Compose artifact binding and HTTP requests from one captured environment."""
from collections.abc import Mapping
from pathlib import Path

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.vcs.gitea_artifact_exporter import GiteaArtifactExporter
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.application.services.owned_http_request_service import OwnedHttpRequestService
from orket.application.services.process_input_service import capture_process_context


def create_gitea_artifact_exporter(workspace: Path, *, environment: Mapping[str, str] | None = None,
                                  invocation_root: Path | None = None) -> GiteaArtifactExporter:
    require_sync_context(code="E_GITEA_EXPORT_CONSTRUCTION_REQUIRES_ASYNC_OWNER")
    directory, captured = capture_process_context(cwd=invocation_root, environment=environment)
    return GiteaArtifactExporter(workspace, environment=captured, invocation_root=directory,
        command_runner=CommandProcessSupervisor(directory / workspace, cancellation_event="gitea_export_command_cancelled"),
        http_requester=OwnedHttpRequestService(environment=captured, cwd=directory))
