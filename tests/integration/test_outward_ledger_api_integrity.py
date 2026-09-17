from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_authorization import outward_api
from tests.helpers.outward_ledger import allow_at_rest_corruption, event_count, logical_contents, seed_ledger


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Real API middleware and SQLite verify both local and externally anchored history.
async def test_authenticated_verification_rejects_corruption_without_writing(tmp_path, boundary) -> None:
    db_path, inputs, _ = boundary
    await seed_ledger(db_path, 3)
    async with outward_api(tmp_path, inputs) as (client, _context):
        export = await client.get("/v1/runs/bt2/ledger")
        assert export.status_code == 200, export.text
        anchor = export.json()["retained"]["anchor"]
        body = {"external_anchor": anchor}
        verified = await client.post("/v1/runs/bt2/ledger/verify", json=body)
        assert verified.status_code == 200 and verified.json()["external_anchor"] == "matched_prefix"
        unauthorized = await client.post("/v1/runs/bt2/ledger/verify", json=body, headers={"X-API-Key": "wrong"})
        assert unauthorized.status_code == 403
        async with aiosqlite.connect(db_path) as connection:
            await allow_at_rest_corruption(connection)
            await connection.execute("UPDATE run_events SET payload_json='{}' WHERE event_id='bt2:000002'")
            await connection.commit()
        before = await asyncio.to_thread(logical_contents, db_path)
        for _ in range(2):
            invalid = await client.get("/v1/runs/bt2/ledger/verify")
            assert invalid.status_code == 200 and invalid.json()["result"] == "invalid"
            refused = await client.get("/v1/runs/bt2/ledger", params={"include_pii": True})
            assert refused.status_code == 422
        assert await asyncio.to_thread(logical_contents, db_path) == before


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Concurrent HTTP requests at a frozen clock allocate distinct durable audit identities.
async def test_concurrent_pii_exports_retain_distinct_authenticated_audits(tmp_path, boundary) -> None:
    db_path, inputs, _ = boundary
    service = await seed_ledger(db_path, 3)
    async with outward_api(tmp_path, inputs) as (client, _context):
        responses = await asyncio.gather(*(
            client.get("/v1/runs/bt2/ledger", params={"include_pii": True}) for _ in range(4)
        ))
        assert all(response.status_code == 200 for response in responses), [response.text for response in responses]
        for response in responses:
            payload = response.json()
            assert payload["canonical"]["event_count"] == payload["retained"]["anchor"]["event_count"]
            assert payload["canonical"]["event_count"] == len(payload["events"])
    assert await event_count(db_path) == 7
    audits = [event for event in await service.event_store.list_for_run("bt2") if event.event_type == "ledger_export_requested"]
    assert len(audits) == len({event.event_id for event in audits}) == 4
    assert all(event.payload["operator_ref"] not in {"operator:unknown", "operator:api"} for event in audits)
    assert (await service.verify_run("bt2"))["result"] == "valid"
