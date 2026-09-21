"""Real asset/SQLite capture checks; controlled providers and no inference claim."""
import asyncio
import json

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.decision_nodes.builtins import DefaultExecutionRuntimeStrategyNode
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline

pytestmark=[pytest.mark.integration,pytest.mark.asyncio]


class Inputs(RuntimeInputService):
    label='admitted'

    def create_session_id(self):
        return self.label+'-session'


class Policy(DefaultExecutionRuntimeStrategyNode):
    label='admitted'

    def select_epic_build_id(self,build_id,name,sanitized):
        return self.label+'-build'


async def pipeline_at(root):
    fs=AsyncFileTools(root)
    await fs.write_file('model/core/environments/standard.json',json.dumps(dict(name='standard',model='dummy-model')))
    await fs.write_file('model/core/rocks/empty.json',json.dumps(dict(id='empty',name='empty',epics=[])))
    pipeline=await publication_pipeline(root,root/'workspace',str(root/'records.sqlite3'))
    await pipeline.initialize()
    pipeline.runtime_inputs=Inputs()
    return pipeline


def hold_asset(loader,monkeypatch):
    entered,release=asyncio.Event(),asyncio.Event()
    read=loader.load_asset_async
    first=True
    async def held(*args,**kwargs):
        nonlocal first
        result=await read(*args,**kwargs)
        if first:
            first=False
            entered.set()
            await release.wait()
        return result
    monkeypatch.setattr(loader,'load_asset_async',held)
    return entered,release


async def test_epic_identity_is_captured_before_held_asset_read(tmp_path,monkeypatch):
    pipeline=await pipeline_at(tmp_path)
    policy=Policy()
    pipeline.execution_runtime_node=policy
    owner=pipeline._build_epic_run_orchestrator()
    entered,release=hold_asset(pipeline.loader,monkeypatch)
    operation=asyncio.create_task(owner._load_setup(epic_name='publication_epic',build_id=None,session_id=None,
        target_issue_id=None,model_override=''))
    try:
        await asyncio.wait_for(entered.wait(),5)
        pipeline.runtime_inputs.label='replacement'
        policy.label='replacement'
        release.set()
        result=await asyncio.wait_for(operation,5)
        assert (result.run_id,result.build_id)==('admitted-session','admitted-build')
    finally:
        release.set()
        await asyncio.gather(operation,return_exceptions=True)
        await pipeline.close()


async def test_collection_retains_selected_policy_and_identity_before_read(tmp_path,monkeypatch):
    pipeline=await pipeline_at(tmp_path)
    entered,release=hold_asset(pipeline.loader,monkeypatch)
    class Replacement(DefaultExecutionRuntimeStrategyNode):
        def select_epic_collection_session_id(self,session_id):
            return 'replacement-session'
        def select_epic_collection_build_id(self,*args):
            return 'replacement-build'
    operation=asyncio.create_task(pipeline._run_epic_collection_entry('empty'))
    try:
        await asyncio.wait_for(entered.wait(),5)
        pipeline.execution_runtime_node=Replacement()
        pipeline.runtime_inputs.label='replacement'
        release.set()
        result=await asyncio.wait_for(operation,5)
        assert (result.session_id,result.build_id)==('admitted-session','epic-collection-build-empty')
        assert not result.succeeded
    finally:
        release.set()
        await asyncio.gather(operation,return_exceptions=True)
        await pipeline.close()


async def test_epic_strategy_receives_sanitized_value_without_callable(tmp_path):
    pipeline=await pipeline_at(tmp_path)
    class ScalarOnly(DefaultExecutionRuntimeStrategyNode):
        def select_epic_build_id(self,build_id,name,sanitized):
            assert type(sanitized) is str,'strategy received a callable instead of a value'
            return 'build-'+sanitized
    pipeline.execution_runtime_node=ScalarOnly()
    try:
        result=await pipeline._build_epic_run_orchestrator()._load_setup(epic_name='publication_epic',build_id=None,
            session_id='admitted-session',target_issue_id=None,model_override='')
        assert result.build_id=='build-publication_epic'
    finally:
        await pipeline.close()


@pytest.mark.parametrize('collection', [False, True])
@pytest.mark.parametrize('field', ['session_id', 'build_id'])
async def test_invalid_identity_refuses_before_asset_read_or_publication(tmp_path, monkeypatch, collection, field):
    pipeline = await pipeline_at(tmp_path)
    method = ('select_epic_collection_session_id' if collection else 'select_run_id') if field == 'session_id' else (
        'select_epic_collection_build_id' if collection else 'select_epic_build_id')
    monkeypatch.setattr(pipeline.execution_runtime_node, method, lambda *args: None)
    reads = []
    original = pipeline.loader.load_asset_async

    async def observed_read(*args, **kwargs):
        reads.append(args)
        return await original(*args, **kwargs)

    monkeypatch.setattr(pipeline.loader, 'load_asset_async', observed_read)
    try:
        with pytest.raises(ValueError, match='E_EXECUTION_POLICY_INVALID_' + field.upper()):
            if collection:
                await pipeline._run_epic_collection_entry('empty', session_id='refused-session')
            else:
                await pipeline._build_epic_run_orchestrator()._load_setup(epic_name='publication_epic', build_id=None,
                    session_id='refused-session', target_issue_id=None, model_override='')
        assert reads == []
        assert await pipeline.sessions.get_session('refused-session') is None
        assert await pipeline.run_ledger.get_run('refused-session') is None
    finally:
        await pipeline.close()


async def test_captured_identity_reaches_verified_sqlite_publication(tmp_path, monkeypatch):
    pipeline = await pipeline_at(tmp_path)
    policy = Policy()
    pipeline.execution_runtime_node = policy
    entered, release = hold_asset(pipeline.loader, monkeypatch)

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, tmp_path / 'workspace')

    monkeypatch.setattr(pipeline.orchestrator, 'execute_epic', execute_fixture)
    operation = asyncio.create_task(pipeline.run_epic('publication_epic'))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        pipeline.runtime_inputs.label = 'replacement'
        policy.label = 'replacement'
        release.set()
        result = await asyncio.wait_for(operation, 10)
        assert result.succeeded
        assert (result.session_id, result.build_id) == ('admitted-session', 'admitted-build')
        assert (await pipeline.sessions.get_session('admitted-session'))['status'] == 'done'
        ledger = await pipeline.run_ledger.get_run('admitted-session')
        assert ledger['status'] == 'done'
        run_id = ledger['artifact_json']['control_plane_run_record']['run_id']
        truth = await pipeline.orchestrator.control_plane_repository.get_final_truth(run_id=run_id)
        assert truth.result_class.value == 'success'
        assert await pipeline.sessions.get_session('replacement-session') is None
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        await pipeline.close()
