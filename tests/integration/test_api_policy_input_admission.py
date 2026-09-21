"""Real SQLite/ASGI input admission; no provider or Docker effects."""
import asyncio

import httpx
import pytest
from fastapi import FastAPI

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.core.domain.records import IssueRecord
from orket.decision_nodes.api_runtime_strategy_node import DefaultApiRuntimeStrategyNode
from orket.interfaces.routers.cards import ArchiveCardsRequest, build_cards_router
from orket.orchestration.engine_services import CardArchiver

pytestmark=[pytest.mark.integration,pytest.mark.asyncio]


async def owner(tmp_path,node):
    repo=AsyncCardRepository(tmp_path/'cards.sqlite3')
    for name in ('requested','protected'):
        await repo.save(IssueRecord(id=name,summary=name,seat='developer'))
    engine=CardArchiver(repo)
    router=build_cards_router(lambda:engine,lambda:node)
    app=FastAPI()
    app.include_router(router)
    return repo,engine,router,app


async def test_strategy_cannot_add_archive_targets(tmp_path):
    class Mutation(DefaultApiRuntimeStrategyNode):
        def has_archive_selector(self,card_ids,build_id,related_tokens):
            card_ids.append('protected')
            return True
    repo,_,_,app=await owner(tmp_path,Mutation())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as client:
        with pytest.raises(AttributeError, match="append"):
            await client.post('/cards/archive',json={'card_ids':['requested']})
    assert (await repo.get_by_id('protected')).status.value=='ready'
    assert (await repo.get_by_id('requested')).status.value=='ready'


async def test_request_selector_rotation_cannot_extend_later_effect(tmp_path):
    repo,engine,router,_=await owner(tmp_path,DefaultApiRuntimeStrategyNode())
    entry=next(route.endpoint for route in router.routes if route.path=='/cards/archive')
    request=ArchiveCardsRequest(card_ids=['requested'],related_tokens=[])
    entered,release=asyncio.Event(),asyncio.Event()
    archive=engine.archive_cards
    async def held(*args,**kwargs):
        result=await archive(*args,**kwargs)
        entered.set()
        await release.wait()
        return result
    engine.archive_cards=held
    operation=asyncio.create_task(entry(request))
    try:
        await asyncio.wait_for(entered.wait(),5)
        request.related_tokens.append('protected')
        release.set()
        await asyncio.wait_for(operation,5)
    finally:
        release.set()
        await asyncio.gather(operation,return_exceptions=True)
    assert (await repo.get_by_id('protected')).status.value=='ready'


async def test_response_cannot_claim_unobserved_archive_count(tmp_path):
    class FalseCount(DefaultApiRuntimeStrategyNode):
        def normalize_archive_response(self,**kwargs):
            return dict(super().normalize_archive_response(**kwargs),archived_count=999)
    repo,_,_,app=await owner(tmp_path,FalseCount())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as client:
        with pytest.raises(ValueError,match='E_API_ARCHIVE_RESULT_CONTRADICTION'):
            await client.post('/cards/archive',json={'card_ids':['requested']})
    assert (await repo.get_by_id('requested')).status.value=='archived'
