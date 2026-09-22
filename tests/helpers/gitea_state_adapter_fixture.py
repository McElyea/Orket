"""Contract fixtures retain actual transports even when domain collaborators are replaced."""
from contextlib import AsyncExitStack

import pytest_asyncio

from orket.application.services.gitea_state_adapter_factory import create_gitea_state_adapter_async
from orket.application.services.runtime_result_lifetime import close_runtime_owner


@pytest_asyncio.fixture
async def gitea_adapter_factory():
    async with AsyncExitStack() as resources:
        async def create(**options):
            adapter = await create_gitea_state_adapter_async(environment=options.pop('environment', {}), **options)
            resources.push_async_callback(close_runtime_owner, adapter)
            return adapter

        yield create
