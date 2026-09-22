"""Application-owned Gitea transport construction over captured process inputs."""
from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.application.services.captured_http_client_service import CapturedHttpClientService
from orket.application.services.native_resource_construction import construct_with_owned_cleanup
from orket.application.services.process_input_service import capture_process_context
from orket.application.services.runtime_result_lifetime import create_runtime_owner
from orket.decision_nodes.gitea_lease_policy import gitea_issue_body_limit


def create_gitea_state_adapter(*, environment: Mapping[str, str] | None = None,
                               cwd: Path | None = None, **options: Any) -> GiteaStateAdapter:
    require_sync_context(code="E_GITEA_FACTORY_REQUIRES_ASYNC_OWNER")
    directory, captured = capture_process_context(cwd=cwd, environment=environment)
    owner = CapturedHttpClientService(environment=captured, cwd=directory)
    return construct_with_owned_cleanup(partial(GiteaStateAdapter, http_client_owner=owner,
                                        issue_body_max_bytes=gitea_issue_body_limit(captured), **options),
                                        owner=owner, label="Gitea state adapter construction")


async def create_gitea_state_adapter_async(*, environment: Mapping[str, str] | None = None,
                                         cwd: Path | None = None, **options: Any) -> GiteaStateAdapter:
    directory, captured = capture_process_context(cwd=cwd, environment=environment)
    return await create_runtime_owner(partial(create_gitea_state_adapter, environment=captured,
        cwd=directory, **options), label="gitea-adapter-construction")
