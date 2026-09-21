"""Real configuration/file/SQLite observations; controlled provider and admission fixtures."""
import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from orket import utils
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.agents.agent import Agent
from orket.application.services.control_plane_authority_service import ControlPlaneAuthorityService
from orket.core.domain import ResidualUncertaintyClassification
from orket.runtime.config.config_loader import ConfigLoader
from tests.integration.test_execution_policy_input_capture import hold_asset, pipeline_at

pytestmark=[pytest.mark.integration,pytest.mark.asyncio]


class Provider:
    model='probe-model'

    async def complete(self,messages):
        return SimpleNamespace(content='{"tool":"write_file","args":{"path":"result.txt","content":"observed"}}',raw={})


async def write_assets(root):
    files=AsyncFileTools(root)
    await files.write_file('model/core/roles/probe.json',json.dumps(dict(name='probe',intent='observe',responsibilities=[])))
    for family in ('generic','admitted','replacement'):
        await files.write_file('model/core/dialects/'+family+'.json',json.dumps(dict(
            model_family=family,dsl_format='JSON',constraints=[],hallucination_guard='None')))
    return files


async def journal_agent(root, clock, provider=None):
    files = await write_assets(root)

    async def write(args, context):
        await files.write_file(args['path'], args['content'])
        return {'ok': True}

    class Allowed:
        async def validate(self, *args):
            return None

    return files, Agent('probe', 'observe', {'write_file': write}, provider if provider is not None else Provider(),
        config_root=root, tool_gate=Allowed(), journal=ControlPlaneAuthorityService(), turn_clock=clock, environment={})


async def test_model_family_selection_precedes_held_actual_role_read(tmp_path,monkeypatch):
    await write_assets(tmp_path)
    monkeypatch.setenv('ORKET_MODEL_FAMILY_PATTERNS','{"probe":"admitted"}')
    agent=Agent('probe','observe',{},Provider(),config_root=tmp_path)
    entered,release=threading.Event(),threading.Event()
    original=ConfigLoader.load_asset

    def held(loader,category,*args):
        result=original(loader,category,*args)
        if category=='roles':
            entered.set()
            assert release.wait(5),'held role read was not released'
        return result

    monkeypatch.setattr(ConfigLoader,'load_asset',held)
    operation=asyncio.create_task(agent._ensure_configs_loaded_async())
    try:
        assert await asyncio.to_thread(entered.wait,5),'role read did not occur'
        monkeypatch.setenv('ORKET_MODEL_FAMILY_PATTERNS','{"probe":"replacement"}')
        release.set()
        await asyncio.wait_for(operation,5)
        assert agent.dialect.model_family=='admitted'
    finally:
        release.set()
        await asyncio.gather(operation,return_exceptions=True)


async def test_effect_journal_uses_selected_clock_after_actual_file_write(tmp_path,monkeypatch):
    monkeypatch.delenv('ORKET_MODEL_FAMILY_PATTERNS',raising=False)
    observed=datetime(2026,9,20,12,tzinfo=UTC)
    calls=[]

    def clock():
        value=observed+timedelta(seconds=len(calls))
        calls.append(value)
        return value

    files, agent = await journal_agent(tmp_path, clock)
    turn=await agent.run({'description':'write'}, {'issue_id':'PROBE','run_id':'probe-run'},tmp_path)
    assert await files.read_file('result.txt')=='observed'
    entry=turn.raw['effect_journal_entries'][0]
    assert entry['publication_timestamp']==(observed+timedelta(seconds=1)).isoformat()
    assert calls==[observed,observed+timedelta(seconds=1)]


async def test_epic_sprint_is_captured_before_asset_reads_and_sqlite_writes(tmp_path,monkeypatch):
    monkeypatch.setenv('ORKET_EOS_SPRINT_BASE_DATE','2026-02-02')
    monkeypatch.setenv('ORKET_EOS_SPRINT_BASE_QUARTER','1')
    monkeypatch.setenv('ORKET_EOS_SPRINT_BASE_SPRINT','6')
    utils._eos_sprint_base_settings.cache_clear()
    pipeline=await pipeline_at(tmp_path)
    monkeypatch.setattr(pipeline.runtime_inputs,'utc_now',lambda:datetime(2026,2,2,12,tzinfo=UTC))
    owner=pipeline._build_epic_run_orchestrator()
    entered,release=hold_asset(pipeline.loader,monkeypatch)
    operation=asyncio.create_task(owner._load_setup(epic_name='publication_epic',build_id='sprint-build',
        session_id='sprint-session',target_issue_id=None,model_override=''))
    try:
        await asyncio.wait_for(entered.wait(),5)
        monkeypatch.setenv('ORKET_EOS_SPRINT_BASE_QUARTER','80')
        monkeypatch.setattr(pipeline.runtime_inputs,'utc_now',lambda:datetime(2026,2,9,12,tzinfo=UTC))
        release.set()
        setup=await asyncio.wait_for(operation,5)
        await owner._ensure_session_and_cards(setup)
        assert (await pipeline.async_cards.get_by_id('ISSUE-1')).sprint=='Q1 S6'
    finally:
        release.set()
        await asyncio.gather(operation,return_exceptions=True)
        await pipeline.close()
        utils._eos_sprint_base_settings.cache_clear()


async def test_journal_timestamp_override_is_retained_through_provider_wait(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()
    observed = datetime(2026, 9, 20, 12, tzinfo=UTC)
    calls = []

    def clock():
        calls.append(observed)
        return observed

    class HeldProvider(Provider):
        async def complete(self, messages):
            entered.set()
            await release.wait()
            return await super().complete(messages)

    files, agent = await journal_agent(tmp_path, clock, HeldProvider())
    context = {'run_id': 'retained-run', 'journal_publication_timestamp': observed.isoformat()}
    operation = asyncio.create_task(agent.run({'description': 'write'}, context, tmp_path))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        context['journal_publication_timestamp'] = datetime.max.replace(tzinfo=UTC).isoformat()
        agent.turn_clock = lambda: datetime.max.replace(tzinfo=UTC)
        release.set()
        turn = await asyncio.wait_for(operation, 5)
        assert await files.read_file('result.txt') == 'observed'
        assert turn.raw['effect_journal_entries'][0]['publication_timestamp'] == observed.isoformat()
        assert calls == [observed]
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)


async def test_publication_clock_failure_preserves_effect_without_fabricated_record(tmp_path):
    calls = []

    def clock():
        calls.append('observation')
        if len(calls) > 1:
            raise ValueError('clock-unavailable')
        return datetime(2026, 9, 20, 12, tzinfo=UTC)

    files, agent = await journal_agent(tmp_path, clock)
    with pytest.raises(ValueError, match='clock-unavailable'):
        await agent.run({'description': 'write'}, {'run_id': 'failed-clock'}, tmp_path)
    assert await files.read_file('result.txt') == 'observed'
    assert len(calls) == 2


async def test_explicit_empty_agent_environment_keeps_generic_dialect(tmp_path, monkeypatch):
    await write_assets(tmp_path)
    monkeypatch.setenv('ORKET_MODEL_FAMILY_PATTERNS', '{"probe":"admitted"}')
    provider = Provider()
    agent = Agent('probe', 'observe', {}, provider, config_root=tmp_path, environment={})
    provider.model = 'qwen'
    await agent._ensure_configs_loaded_async()
    assert agent.dialect.model_family == 'generic'


async def test_failed_tool_journal_uses_selected_clock_and_retains_uncertainty(tmp_path):
    observed = datetime(2026, 9, 20, 12, tzinfo=UTC)
    calls = []

    def clock():
        value = observed + timedelta(seconds=len(calls))
        calls.append(value)
        return value

    files, agent = await journal_agent(tmp_path, clock)
    original = agent.tools['write_file']

    async def write_then_fail(args, context):
        await original(args, context)
        raise OSError('post-write failure')

    agent.tools['write_file'] = write_then_fail
    turn = await agent.run({'description': 'write'}, {'run_id': 'failed-tool'}, tmp_path)
    assert await files.read_file('result.txt') == 'observed'
    assert turn.tool_calls[0].error == 'post-write failure'
    entry = turn.raw['effect_journal_entries'][0]
    assert entry['uncertainty_classification'] == ResidualUncertaintyClassification.UNRESOLVED.value
    assert entry['publication_timestamp'] == (observed + timedelta(seconds=1)).isoformat()
    assert calls == [observed, observed + timedelta(seconds=1)]
