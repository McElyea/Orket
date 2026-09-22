"""Layer: integration. Actual provider/SQLite effects through application handoff failures."""
import asyncio
import threading
from types import SimpleNamespace

import pytest

from orket.application.services import governed_agent_model_provider as governed
from orket.application.services import model_client_factory as clients
from orket.application.services.model_selection_service import ModelSelectionService
from orket.application.services.orchestrator_prompt_preparation_service import OrchestratorPromptPreparationService
from orket.decision_nodes.builtins import DefaultRouterNode
from orket.schema import CardStatus, EnvironmentConfig
from orket_extension_sdk import AgentIterationRequest
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.provider_inference_observation import http_transport, observe_completion
from tests.integration.test_dispatch_input_admission import _dispatch_context
from tests.integration.test_provider_http_tls_inputs import FIXTURES, server_context
from tests.integration.test_provider_inference_http_inputs import MODEL, response_for
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('interruption', ['failure', 'cancel', 'repeated', 'timeout'])
async def test_governed_multi_client_preparation_owns_partial_and_unadopted_clients(
    tmp_path, monkeypatch, record_property, interruption,
):
    entered, release = threading.Event(), threading.Event()
    created, workers = [], []
    original = governed.create_local_model_provider

    def construct(*args, **options):
        workers.append(threading.get_ident())
        if created:
            entered.set()
            assert release.wait(5), 'second native provider did not remain owned'
            if interruption == 'failure':
                raise ValueError('controlled second provider refusal')
        client = original(*args, **options)
        created.append(client)
        return client

    monkeypatch.setattr(governed, 'create_local_model_provider', construct)

    async def response(request):
        if request[0].startswith('GET '):
            return 200, {'data': [{'id': MODEL}, {'id': 'second-fixture'}]}
        return await response_for('openai_compat', 'observed')(request)

    async with observed_http_server(response) as server:
        request = AgentIterationRequest.from_wire(agent_request())
        models = {profile.role: MODEL if index == 0 else 'second-fixture'
                  for index, profile in enumerate(request.model_profiles)}
        timeout = asyncio.timeout(None)

        async def invoke():
            async with timeout:
                return await governed.prepare_governed_agent_local_runtime(request=request, model_by_role=models,
                    provider='openai_compat', base_url=server[0] + '/v1', environment={})

        task = asyncio.create_task(invoke())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            assert all(worker != threading.get_ident() for worker in workers)
            await responsive_sqlite(tmp_path / 'responsive.sqlite3', record_property)
            assert (await observe_completion(created[0])).content == 'observed'
            if interruption == 'timeout':
                timeout.reschedule(asyncio.get_running_loop().time() + .01)
            elif interruption != 'failure':
                task.cancel()
            await asyncio.sleep(.03)
            if interruption == 'repeated':
                task.cancel()
                await asyncio.sleep(.01)
            assert not task.done() and not http_transport(created[0]).is_closed
            release.set()
            expected = ValueError if interruption == 'failure' else (
                TimeoutError if interruption == 'timeout' else asyncio.CancelledError)
            with pytest.raises(expected):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert len(created) == (1 if interruption == 'failure' else 2)
        assert all(client._closed and http_transport(client).is_closed for client in created)
        assert sum(line.startswith('POST ') for line, _ in server[1]) == 1


@pytest.mark.parametrize('stage', ['native', 'prompt'])
@pytest.mark.parametrize('interruption', ['cancel', 'repeated'])
async def test_card_preparation_retains_provider_until_handoff(tmp_path, monkeypatch, record_property, stage, interruption):
    repo, issue, team, orchestrator = await _dispatch_context(tmp_path, DefaultRouterNode())
    entered, release = threading.Event(), threading.Event()
    arrived, resume = asyncio.Event(), asyncio.Event()
    created = []
    original = clients.ModelClientFactory.create_provider

    def construct(factory, *args):
        client = original(factory, *args)
        created.append(client)
        if stage == 'native':
            entered.set()
            assert release.wait(5)
        return client

    async def load(*args):
        return SimpleNamespace(name='coder')

    async def prompt(*args, **options):
        arrived.set()
        await asyncio.wait_for(resume.wait(), 5)
        raise ValueError('controlled prompt refusal')

    monkeypatch.setattr(clients.ModelClientFactory, 'create_provider', construct)
    monkeypatch.setattr(OrchestratorPromptPreparationService, 'build', prompt)
    orchestrator.loader = SimpleNamespace(load_asset_async=load)
    selection = await ModelSelectionService(environment={'ORKET_MODEL_CODER': MODEL}).prepare(
        preferences={}, user_settings={})

    async def response(request):
        if request[0].startswith('GET '):
            return 200, {'data': [{'id': MODEL}]}
        return await response_for('openai_compat', 'observed')(request)

    async with observed_http_server(response) as server:
        orchestrator.model_clients = clients.ModelClientFactory({'ORKET_LLM_PROVIDER': 'openai_compat',
            'ORKET_LLM_OPENAI_BASE_URL': server[0] + '/v1', 'ORKET_LOCAL_PROMPTING_MODE': 'shadow',
            'ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL': 'false', 'ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL': 'false'})
        task = asyncio.create_task(orchestrator._execute_issue_turn(issue, SimpleNamespace(params={}), team,
            EnvironmentConfig(name='test', model=MODEL), 'run', 'build', selection, None, None))
        try:
            if stage == 'native':
                assert await asyncio.to_thread(entered.wait, 5)
            else:
                await asyncio.wait_for(arrived.wait(), 5)
            await responsive_sqlite(tmp_path / 'responsive.sqlite3', record_property)
            assert len(created) == 1
            assert (await observe_completion(created[0])).content == 'observed'
            task.cancel()
            await asyncio.sleep(.01)
            if interruption == 'repeated':
                task.cancel()
            if stage == 'native':
                assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            resume.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert created[0]._closed and http_transport(created[0]).is_closed
        assert (await repo.get_by_id(issue.id)).status == CardStatus.IN_PROGRESS
        assert sum(line.startswith('POST ') for line, _ in server[1]) == 1


async def test_unpinned_provider_preparation_reuses_captured_trust_directory(tmp_path, monkeypatch):
    context = await asyncio.to_thread(server_context)
    async def response(request):
        if request[0].startswith('GET '):
            return 200, {'data': [{'id': MODEL}]}
        return await response_for('openai_compat', 'admitted')(request)

    async with observed_http_server(response, ssl_context=context) as server:
        environment = {'ORKET_LLM_PROVIDER': 'openai_compat', 'ORKET_LLM_OPENAI_BASE_URL': server[0] + '/v1',
            'SSL_CERT_FILE': 'ca.pem', 'ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL': 'false',
            'ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL': 'false'}
        factory = clients.ModelClientFactory(environment, cwd=FIXTURES)
        monkeypatch.chdir(tmp_path)
        from orket.application.services.runtime_result_lifetime import create_runtime_owner
        from orket.core.contracts.decision_inputs import ModelClientOptions
        client = await create_runtime_owner(lambda: factory.create_provider(MODEL, ModelClientOptions(0, 30)),
                                            label='fixture-model-construction')
        try:
            assert (await observe_completion(client)).content == 'admitted'
            assert client._runtime_target.inventory_source == 'http_models'
            assert [line.split()[0] for line, _ in server[1]] == ['GET', 'POST']
        finally:
            await client.close()
            assert http_transport(client).is_closed


@pytest.mark.parametrize('additional_cancellations', [1, 3])
async def test_card_preparation_retains_successful_close_through_repeated_cancellation(
    tmp_path, monkeypatch, record_property, additional_cancellations,
):
    repo, issue, team, orchestrator = await _dispatch_context(tmp_path, DefaultRouterNode())
    prompt_entered, close_entered, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    created, original = [], clients.ModelClientFactory.create_provider

    def construct(factory, *args):
        client = original(factory, *args)
        close = client._http_client_owner._resources._close
        async def held_close():
            close_entered.set()
            await asyncio.wait_for(release.wait(), 5)
            await close()
        client._http_client_owner._resources._close = held_close
        created.append(client)
        return client

    async def load(*args):
        return SimpleNamespace(name='coder')

    async def prompt(*args, **options):
        prompt_entered.set()
        await asyncio.wait_for(asyncio.Event().wait(), 5)

    async def response(request):
        if request[0].startswith('GET '):
            return 200, {'data': [{'id': MODEL}]}
        return await response_for('openai_compat', 'observed')(request)

    monkeypatch.setattr(clients.ModelClientFactory, 'create_provider', construct)
    monkeypatch.setattr(OrchestratorPromptPreparationService, 'build', prompt)
    orchestrator.loader = SimpleNamespace(load_asset_async=load)
    selection = await ModelSelectionService(environment={'ORKET_MODEL_CODER': MODEL}).prepare(
        preferences={}, user_settings={})
    async with observed_http_server(response) as server:
        orchestrator.model_clients = clients.ModelClientFactory({'ORKET_LLM_PROVIDER': 'openai_compat',
            'ORKET_LLM_OPENAI_BASE_URL': server[0] + '/v1', 'ORKET_LOCAL_PROMPTING_MODE': 'shadow',
            'ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL': 'false', 'ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL': 'false'})
        task = asyncio.create_task(orchestrator._execute_issue_turn(issue, SimpleNamespace(params={}), team,
            EnvironmentConfig(name='test', model=MODEL), 'run', 'build', selection, None, None))
        try:
            await asyncio.wait_for(prompt_entered.wait(), 5)
            assert len(created) == 1 and (await observe_completion(created[0])).content == 'observed'
            task.cancel()
            await asyncio.wait_for(close_entered.wait(), 5)
            await responsive_sqlite(tmp_path / 'responsive.sqlite3', record_property)
            for _ in range(additional_cancellations):
                task.cancel()
                await asyncio.sleep(0)
            assert not task.done() and not http_transport(created[0]).is_closed
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        record_property('physical_http_client_closed', http_transport(created[0]).is_closed)
        record_property('provider_close_result_adopted', created[0]._closed)
        assert created[0]._closed and http_transport(created[0]).is_closed
        assert (await repo.get_by_id(issue.id)).status == CardStatus.IN_PROGRESS
        assert sum(line.startswith('POST ') for line, _ in server[1]) == 1
