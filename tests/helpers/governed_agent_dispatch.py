"""Real native catalog, wake queue, fences and dispatch services for boundary proof."""
import asyncio
import json
from datetime import datetime, timedelta

from tests.helpers.governed_agent_cli import write_submission_files
from tests.integration import test_governed_agent_wake_dispatcher as fixture


async def configured_dispatcher(tmp_path, *, provider=None, environment=None):
    catalog, request_path, now = await asyncio.to_thread(write_submission_files, tmp_path)
    request = json.loads(await asyncio.to_thread(request_path.read_text, encoding='utf-8'))
    db = tmp_path / 'agent.sqlite3'
    wakes = fixture.AsyncGovernedAgentWakeRepository(db)
    await wakes.enqueue(fixture._wake(request, now))
    claim = await wakes.claim_next(owner_id='input-capture', now_utc=now.isoformat(),
        lease_expires_at_utc=(now + timedelta(seconds=30)).isoformat(), max_active_claims=1)
    assert claim.wake is not None and claim.authority is not None
    execution = fixture.AsyncControlPlaneExecutionRepository(db)
    iterations = fixture.AsyncGovernedAgentRepository(db)
    records = fixture.AsyncControlPlaneRecordRepository(db)
    publication = fixture.ControlPlanePublicationService(repository=records)
    manager = await fixture.prepare_extension_manager(catalog_path=catalog, project_root=tmp_path)
    dispatcher = fixture.GovernedAgentWakeLoopDispatcher(
        execution_repository=execution, iteration_repository=iterations, record_repository=records,
        extension_manager=manager, provider=provider or fixture.GovernedAgentProviderConfiguration(
            mode='deterministic_fixture', default_model='', role_models={}, ollama_base_url='',
            inventory_timeout_seconds=5, capacity_limit=1),
        effect_service=fixture.GovernedAgentEffectService(
            transactions=fixture.SQLiteControlPlaneTransactions(db), execution_repository=execution,
            publication=publication, pending_gates=fixture.AsyncPendingGateRepository(db),
            file_executor=fixture.GovernedAgentFileEffectExecutor(tmp_path, tool_gate=fixture.ToolGate(None, tmp_path))),
        effect_resume_service=fixture.GovernedAgentEffectResumeService(execution_repository=execution,
            iteration_repository=iterations, publication=publication), environment=environment,
    )
    guard = fixture.GovernedAgentWakeClaimGuard(repository=wakes, authority=claim.authority,
                                             now_utc=lambda: datetime.now(now.tzinfo).isoformat())
    return dispatcher, execution, guard, claim.wake, request['identity']['run_id']
