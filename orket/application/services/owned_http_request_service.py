"""Short requests reuse captured network policy and existing native/runtime owners."""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from orket.application.services.captured_http_client_service import CapturedHttpClientService
from orket.application.services.native_resource_construction import construct_with_owned_cleanup
from orket.application.services.process_input_service import capture_process_context
from orket.application.services.runtime_result_lifetime import open_runtime_owner


@dataclass
class _RequestOwner:
    client: Any
    resources: CapturedHttpClientService

    async def close(self):
        await self.resources.close(self.client)


def _construct(*, environment, cwd, timeout_s, auth):
    resources = CapturedHttpClientService(environment=environment, cwd=cwd)
    return construct_with_owned_cleanup(
        lambda: _RequestOwner(resources.create_client(timeout_s=timeout_s, auth=auth), resources),
        owner=resources, label="Short HTTP request construction")


class OwnedHttpRequestService:
    def __init__(self, *, environment: Mapping[str, str] | None = None, cwd: Path | None = None):
        # None intentionally observes ambient configuration at each operation.
        self._environment = None if environment is None else dict(environment)
        self._cwd = cwd

    async def request(self, method: str, url: str, *, timeout_s: float,
                      auth: tuple[str, str] | None = None, **options: Any) -> Any:
        directory, environment = capture_process_context(cwd=self._cwd, environment=self._environment)
        options = deepcopy(options)
        construct = partial(_construct, environment=environment, cwd=directory, timeout_s=timeout_s, auth=auth)
        async with open_runtime_owner(construct, label="short-http-construction") as owner:
            return await owner.client.request(method, url, **options)
