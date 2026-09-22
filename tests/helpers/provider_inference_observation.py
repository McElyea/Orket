"""Layer: integration support. Real clients with explicitly pinned fixture admission."""
import asyncio

from orket.application.services.local_model_factory import create_local_model_provider_async
from orket.core.contracts.provider_runtime import ProviderRuntimeTarget
from tests.integration.test_provider_inference_http_inputs import MODEL


async def create_observed_provider(provider, address, **options):
    url = address + ('/v1' if provider == 'openai_compat' else '')
    target = ProviderRuntimeTarget(provider, provider, MODEL, MODEL, url, 'pinned', 'controlled-fixture',
                                   (MODEL,), (), (), False, False, 'OK')
    return await create_local_model_provider_async(MODEL, provider=provider, base_url=url,
        timeout=2, connect_timeout_seconds=1, runtime_target=target, **options)


async def observe_completion(client):
    return await asyncio.wait_for(client.complete(
        [{'role': 'user', 'content': 'Observe captured network routing.'}],
        runtime_context={'local_prompting_mode': 'shadow', 'local_prompt_task_class': 'concise_text'}), 5)


def http_transport(client):
    # Test-only SDK inspection observes actual closure; production uses its public close().
    return client.client if client.provider_backend == 'openai_compat' else client.client._client
