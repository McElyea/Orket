"""Real Gitea composition with public fixture credentials and resource observations."""
import asyncio
import os
from pathlib import Path

from orket.application.services.gitea_state_adapter_factory import create_gitea_state_adapter_async
from orket.application.services.gitea_webhook_runtime import build_webhook_runtime
from orket.application.services.provider_http_resources import ProviderHttpResources
from orket.application.services.webhook_configuration import WebhookConfiguration


def webhook_configuration(root, address, environment, cwd):
    return WebhookConfiguration(project_root=root, invocation_root=cwd,
        environment=environment, gitea_url=address, user='fixture-user', password='public-password',
        secret=b'public-secret', test_token='', api_key='', test_enabled=False,
        allow_insecure=address.startswith('http://'), rate_limit=100, worker_count=1)


async def create_gitea_owner(kind, root, address, *, environment=None, cwd=None, **options):
    if kind == 'state':
        return await create_gitea_state_adapter_async(base_url=address, owner='fixture-owner', repo='fixture-repo',
            token='public-token', max_retries=0, environment=environment, cwd=cwd, **options)
    config = webhook_configuration(root, address, dict(os.environ) if environment is None else environment,
                                    Path.cwd() if cwd is None else cwd)
    return await build_webhook_runtime(config)


def http_client(owner):
    return owner.http._client if hasattr(owner, 'http') else owner.client


async def observe_request(owner):
    if hasattr(owner, 'http'):
        return await asyncio.wait_for(owner.fetch_ready_cards(limit=5), 5)
    observations = []

    async def invoke():
        response = await owner.client.get(owner.gitea_url + '/api/v1/version')
        response.raise_for_status()
        observations.append(response.json())

    await asyncio.wait_for(owner.run_request(invoke), 5)
    return observations[0]


def observe_resources(monkeypatch, *, fail_after=None):
    resources, closed = [], []
    original = ProviderHttpResources.retain

    def retain(owner, resource):
        original(owner, resource)
        if any(resource is item for item in resources):
            return
        resources.append(resource)
        close = resource.aclose

        async def observed_close():
            await close()
            closed.append(resource)

        monkeypatch.setattr(resource, 'aclose', observed_close)
        if len(resources) == fail_after:
            raise OSError('controlled failure after actual HTTP resource acquisition')

    monkeypatch.setattr(ProviderHttpResources, 'retain', retain)
    return resources, closed
