"""Public catalog requests retain real native files and preserve existing tolerant discovery."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from orket.interfaces.api import create_api_app
from tests.helpers.api_observation_lifetime import exercise_owned_api_read
from tests.helpers.model_selection import ModelSelectionFixture
from tests.integration.test_api_run_observation_ownership import hold_native_read

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROUTES = {
    "active_roles": "/v1/system/model-assignments",
    "team_catalog": "/v1/system/teams",
    "team_file": "/v1/system/teams",
}
TEAM = "model/core/teams/fixture.json"
ROLE = "model/core/roles/coder.json"


def write_catalog_file(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest_asyncio.fixture
async def catalog_client(tmp_path):
    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "fixture"})
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://fixture", headers={"X-API-Key": "fixture"},
    ) as client:
        app.state.api_runtime_context.model_selection = ModelSelectionFixture()
        # Seed after startup: these files exercise the catalog, not engine configuration loading.
        await asyncio.to_thread(write_catalog_file, tmp_path, TEAM, {"seats": {"one": {"roles": ["Coder"]}}})
        await asyncio.to_thread(write_catalog_file, tmp_path, ROLE, {"name": "Coder", "tools": ["read_file"]})
        yield app, client


@pytest.mark.parametrize("kind", list(ROUTES))
@pytest.mark.parametrize("stop", ["cancel", "timeout", "shutdown", "shutdown_cancel"])
async def test_api_catalog_reads_remain_owned(tmp_path, monkeypatch, record_property, catalog_client, kind, stop):
    app, client = catalog_client
    selected = tmp_path / (ROLE if kind == "team_catalog" else TEAM)
    state = hold_native_read(monkeypatch, selected, False)
    await exercise_owned_api_read(app, client, ROUTES[kind], state, tmp_path, record_property, stop)


@pytest.mark.parametrize("kind", list(ROUTES))
@pytest.mark.parametrize("problem", ["os_error", "invalid_json", "non_object"])
async def test_api_catalog_preserves_tolerant_files(tmp_path, monkeypatch, catalog_client, kind, problem):
    _, client = catalog_client
    selected = tmp_path / (ROLE if kind == "team_catalog" else TEAM)
    observed = []
    if problem == "os_error":
        read_text = Path.read_text

        def failed_ack(path, *args, **kwargs):
            result = read_text(path, *args, **kwargs)
            if path == selected:
                observed.append(path)
                raise OSError("Injected catalog acknowledgement failure after actual read")
            return result

        monkeypatch.setattr(Path, "read_text", failed_ack)
    else:
        payload = "{invalid" if problem == "invalid_json" else "[]"
        await asyncio.to_thread(selected.write_text, payload, encoding="utf-8")
    response = await client.get(ROUTES[kind])
    assert response.status_code == 200
    items = response.json()["items"]
    if kind == "active_roles":
        assert [item["role"] for item in items] == ["coder"]
    elif kind == "team_catalog":
        assert items[0]["roles"] == [{"role": "coder", "name": "coder", "description": None,
                                      "tools": [], "source": "seat_reference"}]
    else:
        assert items == []
    if problem == "os_error":
        assert observed == [selected]


async def test_api_role_filter_keeps_order_and_bypasses_discovery(tmp_path, monkeypatch, catalog_client):
    _, client = catalog_client
    read_text = Path.read_text

    def reject_catalog_read(path, *args, **kwargs):
        assert path not in {tmp_path / TEAM, tmp_path / ROLE}, "Filtered query unexpectedly read the catalog"
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_catalog_read)
    response = await client.get(ROUTES["active_roles"], params={"roles": " Lead Reviewer, QA-Role, ,CODER,lead reviewer "})
    assert response.status_code == 200
    assert response.json()["filters"] == {"roles": ["lead_reviewer", "qa-role", "coder"]}
    assert [item["role"] for item in response.json()["items"]] == ["lead_reviewer", "qa-role", "coder"]


async def test_api_filename_fallback_keeps_normalized_duplicates(tmp_path, catalog_client):
    _, client = catalog_client
    await asyncio.to_thread((tmp_path / TEAM).write_text, "{}", encoding="utf-8")
    for name in ("A Role", "a_role"):
        path = tmp_path / f"model/core/roles/{name}.json"
        await asyncio.to_thread(path.write_text, "{invalid role content", encoding="utf-8")
    response = await client.get(ROUTES["active_roles"])
    assert response.status_code == 200
    assert [item["role"] for item in response.json()["items"]] == ["a_role", "a_role", "coder"]


async def test_api_topology_keeps_catalog_precedence_raw_overlay_and_sorting(tmp_path, catalog_client):
    _, client = catalog_client
    await asyncio.to_thread(write_catalog_file, tmp_path, "model/qa/roles/coder.json",
                            {"name": "Coder", "description": "later catalog", "tools": ["later_tool"]})
    team = {"name": "Team", "roles": {"coder": {"description": "team coder", "tools": []},
                                      " Lead Reviewer ": {"name": "unmatched raw-key overlay"}},
            "seats": {"z": {"roles": ["Coder", " QA-Role "]}, "a": "not a mapping"}}
    await asyncio.to_thread(write_catalog_file, tmp_path, TEAM, team)
    await asyncio.to_thread(write_catalog_file, tmp_path, "model/qa/teams/second.json", {"roles": {"coder": {}}})
    response = await client.get(ROUTES["team_file"])
    assert response.status_code == 200
    items = response.json()["items"]
    assert [(item["department"], item["team_id"]) for item in items] == [("core", "fixture"), ("qa", "second")]
    assert items[0]["seats"] == [{"seat_id": "a", "name": None, "roles": []},
                                  {"seat_id": "z", "name": None, "roles": ["coder", "qa-role"]}]
    assert items[0]["roles"] == [
        {"role": "coder", "name": "Coder", "description": "team coder", "tools": ["later_tool"], "source": "team"},
        {"role": "lead_reviewer", "name": "lead_reviewer", "description": None, "tools": [], "source": "seat_reference"},
        {"role": "qa-role", "name": "qa-role", "description": None, "tools": [], "source": "seat_reference"},
    ]
    filtered = await client.get(ROUTES["team_file"], params={"department": " QA "})
    assert filtered.json()["items"] == [items[1]]
    assert filtered.json()["filters"] == {"department": " QA "}
