from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import orket.interfaces.api as api_module

client = None


def _simple_flow_definition(card_id: str) -> dict[str, object]:
    return {
        "name": "Single card flow",
        "description": "Bounded flow run slice for one assigned card.",
        "nodes": [
            {"node_id": "start", "kind": "start", "label": "Start", "assigned_card_id": None, "notes": ""},
            {"node_id": "card-1", "kind": "card", "label": "Card", "assigned_card_id": card_id, "notes": ""},
            {"node_id": "final", "kind": "final", "label": "Final", "assigned_card_id": None, "notes": ""},
        ],
        "edges": [
            {"edge_id": "edge-1", "from_node_id": "start", "to_node_id": "card-1", "condition_label": ""},
            {"edge_id": "edge-2", "from_node_id": "card-1", "to_node_id": "final", "condition_label": ""},
        ],
    }


def _seed_runnable_issue_model(root: Path, card_id: str) -> None:
    for directory in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / directory).mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "organization.json").write_text(
        json.dumps(
            {
                "name": "Test Org",
                "vision": "Test Vision",
                "ethos": "Test Ethos",
                "branding": {"design_dos": [], "colorscheme": {}},
                "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
                "departments": ["core"],
                "contact": {"email": "test@example.com"},
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(
        json.dumps(
            {
                "id": "ARCH",
                "summary": "lead_architect",
                "type": "utility",
                "description": "D",
                "tools": ["write_file", "update_issue_status"],
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "dialects" / "generic.json").write_text(
        json.dumps(
            {
                "model_family": "generic",
                "dsl_format": "JSON",
                "constraints": [],
                "hallucination_guard": "None",
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "teams" / "standard.json").write_text(
        json.dumps(
            {
                "name": "standard",
                "seats": {
                    "lead_architect": {"name": "Lead", "roles": ["lead_architect"]},
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "environments" / "standard.json").write_text(
        json.dumps({"name": "standard", "model": "gpt-4", "temperature": 0.1}),
        encoding="utf-8",
    )
    (root / "model" / "core" / "epics" / "flow_runtime_epic.json").write_text(
        json.dumps(
            {
                "id": "flow_runtime_epic",
                "name": "flow_runtime_epic",
                "type": "epic",
                "team": "standard",
                "environment": "standard",
                "description": "Flow runtime test epic",
                "architecture_governance": {"idesign": False, "pattern": "Standard"},
                "issues": [
                    {
                        "id": card_id,
                        "summary": "Existing runnable card",
                        "seat": "lead_architect",
                        "priority": "Medium",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _seed_runtime_model_for_authored_projection(root: Path) -> None:
    for directory in ["roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / directory).mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "organization.json").write_text(
        json.dumps(
            {
                "name": "Test Org",
                "vision": "Test Vision",
                "ethos": "Test Ethos",
                "branding": {"design_dos": [], "colorscheme": {}},
                "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
                "departments": ["core"],
                "contact": {"email": "test@example.com"},
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(
        json.dumps(
            {
                "id": "ARCH",
                "summary": "lead_architect",
                "type": "utility",
                "description": "D",
                "tools": ["write_file", "update_issue_status"],
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "dialects" / "generic.json").write_text(
        json.dumps(
            {
                "model_family": "generic",
                "dsl_format": "JSON",
                "constraints": [],
                "hallucination_guard": "None",
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "teams" / "standard.json").write_text(
        json.dumps(
            {
                "name": "standard",
                "seats": {
                    "requirements_analyst": {"name": "Requirements Analyst", "roles": ["lead_architect"]},
                    "coder": {"name": "Coder", "roles": ["lead_architect"]},
                    "quality_assurance": {"name": "QA", "roles": ["lead_architect"]},
                    "code_reviewer": {"name": "Reviewer", "roles": ["lead_architect"]},
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "environments" / "standard.json").write_text(
        json.dumps({"name": "standard", "model": "gpt-4", "temperature": 0.1}),
        encoding="utf-8",
    )


def test_flow_authoring_validate_and_persist_round_trip(monkeypatch, tmp_path) -> None:
    """Layer: integration."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    api_module.create_api_app(project_root=Path(tmp_path).resolve())

    validate_response = client.post(
        "/v1/flows/validate",
        headers={"X-API-Key": "test-key"},
        json={"definition": _simple_flow_definition("CARD-1")},
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["is_valid"] is True

    create_response = client.post(
        "/v1/flows",
        headers={"X-API-Key": "test-key"},
        json={"definition": _simple_flow_definition("CARD-1")},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["flow_id"].startswith("FLOW-")
    assert created["revision_id"].startswith("frv_")

    list_response = client.get("/v1/flows", headers={"X-API-Key": "test-key"})
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert list_payload["items"][0]["flow_id"] == created["flow_id"]

    detail_response = client.get(f"/v1/flows/{created['flow_id']}", headers={"X-API-Key": "test-key"})
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["flow_id"] == created["flow_id"]
    assert len(detail_payload["nodes"]) == 3
    assert len(detail_payload["edges"]) == 2


def test_flow_run_route_accepts_single_card_slice(monkeypatch, tmp_path) -> None:
    """Layer: integration."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    _seed_runnable_issue_model(Path(tmp_path).resolve(), "CARD-RUN-1")
    api_module.create_api_app(project_root=Path(tmp_path).resolve())
    engine = api_module._get_engine()

    asyncio.run(
        engine.cards.save(
            {
                "id": "CARD-RUN-1",
                "session_id": "FLOW-SEED",
                "build_id": "FLOW-BUILD",
                "seat": "coder",
                "summary": "Existing runnable card",
                "priority": 2.0,
                "depends_on": [],
            }
        )
    )

    captured: dict[str, object] = {}

    async def fake_run_issue(issue_id: str, *, session_id: str | None = None, **_kwargs: object) -> dict[str, object]:
        captured["issue_id"] = issue_id
        captured["session_id"] = session_id
        return {"ok": True}

    monkeypatch.setattr(engine, "run_issue", fake_run_issue)

    create_response = client.post(
        "/v1/flows",
        headers={"X-API-Key": "test-key"},
        json={"definition": _simple_flow_definition("CARD-RUN-1")},
    )
    created = create_response.json()

    run_response = client.post(
        f"/v1/flows/{created['flow_id']}/runs",
        headers={"X-API-Key": "test-key"},
        json={"expected_revision_id": created["revision_id"]},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["flow_id"] == created["flow_id"]
    assert payload["revision_id"] == created["revision_id"]
    assert payload["session_id"]

    time.sleep(0.05)
    assert captured["issue_id"] == "CARD-RUN-1"
    assert captured["session_id"] == payload["session_id"]


def test_flow_run_route_blocks_branching_topology(monkeypatch, tmp_path) -> None:
    """Layer: contract."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    api_module.create_api_app(project_root=Path(tmp_path).resolve())

    definition = _simple_flow_definition("CARD-1")
    nodes = list(definition["nodes"])  # type: ignore[index]
    nodes.insert(2, {"node_id": "branch-1", "kind": "branch", "label": "Branch", "assigned_card_id": None, "notes": ""})
    definition["nodes"] = nodes

    create_response = client.post(
        "/v1/flows",
        headers={"X-API-Key": "test-key"},
        json={"definition": definition},
    )
    created = create_response.json()

    run_response = client.post(
        f"/v1/flows/{created['flow_id']}/runs",
        headers={"X-API-Key": "test-key"},
        json={"expected_revision_id": created["revision_id"]},
    )
    assert run_response.status_code == 409
    assert "current_flow_run_slice" in run_response.json()["detail"]


def test_flow_run_route_accepts_authored_card_projection(monkeypatch, tmp_path) -> None:
    """Layer: integration."""
    root = Path(tmp_path).resolve()
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    _seed_runtime_model_for_authored_projection(root)
    api_module.create_api_app(project_root=root)
    engine = api_module._get_engine()

    captured: dict[str, object] = {}

    async def fake_run_issue(issue_id: str, *, session_id: str | None = None, **_kwargs: object) -> dict[str, object]:
        captured["issue_id"] = issue_id
        captured["session_id"] = session_id
        return {"ok": True}

    monkeypatch.setattr(engine, "run_issue", fake_run_issue)

    create_card_response = client.post(
        "/v1/cards",
        headers={"X-API-Key": "test-key"},
        json={
            "draft": {
                "name": "Projected authored card",
                "purpose": "Ensure authored cards compose with flow runs.",
                "card_kind": "requirement",
                "prompt": "Summarize the work.",
                "inputs": ["requirements.md"],
                "expected_outputs": ["summary.md"],
                "expected_output_type": "markdown",
                "display_category": "Definition",
                "notes": "Authored through the host API.",
                "constraints": ["stay truthful"],
                "approval_expectation": "operator_review",
                "artifact_expectation": "summary.md",
            }
        },
    )
    assert create_card_response.status_code == 200
    created_card = create_card_response.json()

    create_flow_response = client.post(
        "/v1/flows",
        headers={"X-API-Key": "test-key"},
        json={"definition": _simple_flow_definition(created_card["card_id"])},
    )
    assert create_flow_response.status_code == 200
    created_flow = create_flow_response.json()

    run_response = client.post(
        f"/v1/flows/{created_flow['flow_id']}/runs",
        headers={"X-API-Key": "test-key"},
        json={"expected_revision_id": created_flow["revision_id"]},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["flow_id"] == created_flow["flow_id"]
    assert payload["session_id"]

    time.sleep(0.05)
    assert captured["issue_id"] == created_card["card_id"]
    assert captured["session_id"] == payload["session_id"]
