from __future__ import annotations

import json
from pathlib import Path

import orket.interfaces.api as api_module

client = None


def _projection_epic_path(root: Path) -> Path:
    return root / "config" / "epics" / "orket_ui_authored_cards.json"


def _card_draft(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Authoring Demo Card",
        "purpose": "Capture a truthful authoring slice",
        "card_kind": "requirement",
        "prompt": "Summarize the constraints and acceptance criteria.",
        "inputs": ["requirements.md"],
        "expected_outputs": ["summary.md"],
        "expected_output_type": "markdown",
        "display_category": "Definition",
        "notes": "Created from the OrketUI authoring route tests.",
        "constraints": ["fail closed on unknown fields"],
        "approval_expectation": "operator_review",
        "artifact_expectation": "summary.md",
    }
    payload.update(overrides)
    return payload


def test_card_authoring_validate_route_accepts_valid_payload(monkeypatch, tmp_path) -> None:
    """Layer: contract."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    api_module.create_api_app(project_root=Path(tmp_path).resolve())

    response = client.post(
        "/v1/cards/validate",
        headers={"X-API-Key": "test-key"},
        json={"draft": _card_draft()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_valid"] is True
    assert payload["errors"] == []
    assert payload["reason_codes"] == ["card_authoring.valid"]


def test_card_authoring_create_and_save_round_trip(monkeypatch, tmp_path) -> None:
    """Layer: integration."""
    root = Path(tmp_path).resolve()
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    api_module.create_api_app(project_root=root)

    create_response = client.post(
        "/v1/cards",
        headers={"X-API-Key": "test-key"},
        json={"draft": _card_draft()},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["card_id"].startswith("CARD-")
    assert created["revision_id"].startswith("crv_")
    assert created["validation"]["is_valid"] is True

    raw_response = client.get(
        f"/v1/cards/{created['card_id']}",
        headers={"X-API-Key": "test-key"},
    )
    assert raw_response.status_code == 200
    raw_payload = raw_response.json()
    assert raw_payload["summary"] == "Authoring Demo Card"
    assert raw_payload["seat"] == "requirements_analyst"
    assert raw_payload["params"]["authoring_revision_id"] == created["revision_id"]
    assert raw_payload["params"]["display_category"] == "Definition"
    assert raw_payload["params"]["original_card_kind"] == "requirement"

    projection_payload = json.loads(_projection_epic_path(root).read_text(encoding="utf-8"))
    projected_issue = next(item for item in projection_payload["issues"] if item["id"] == created["card_id"])
    assert projected_issue["seat"] == "requirements_analyst"
    assert projected_issue["requirements"] == "Summarize the constraints and acceptance criteria."
    assert projected_issue["params"]["authoring_revision_id"] == created["revision_id"]

    save_response = client.put(
        f"/v1/cards/{created['card_id']}",
        headers={"X-API-Key": "test-key"},
        json={
            "draft": _card_draft(name="Authoring Demo Card v2", notes="Updated through the save route."),
            "expected_revision_id": created["revision_id"],
        },
    )
    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["card_id"] == created["card_id"]
    assert saved["revision_id"] != created["revision_id"]

    updated_raw = client.get(
        f"/v1/cards/{created['card_id']}",
        headers={"X-API-Key": "test-key"},
    )
    assert updated_raw.status_code == 200
    updated_payload = updated_raw.json()
    assert updated_payload["summary"] == "Authoring Demo Card v2"
    assert updated_payload["params"]["authoring_revision_id"] == saved["revision_id"]

    updated_projection = json.loads(_projection_epic_path(root).read_text(encoding="utf-8"))
    updated_issue = next(item for item in updated_projection["issues"] if item["id"] == created["card_id"])
    assert updated_issue["summary"] == "Authoring Demo Card v2"
    assert updated_issue["note"] == "Updated through the save route."
    assert updated_issue["params"]["authoring_revision_id"] == saved["revision_id"]


def test_card_authoring_save_conflict_fails_closed(monkeypatch, tmp_path) -> None:
    """Layer: contract."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    api_module.create_api_app(project_root=Path(tmp_path).resolve())

    create_response = client.post(
        "/v1/cards",
        headers={"X-API-Key": "test-key"},
        json={"draft": _card_draft()},
    )
    created = create_response.json()

    response = client.put(
        f"/v1/cards/{created['card_id']}",
        headers={"X-API-Key": "test-key"},
        json={
            "draft": _card_draft(name="Conflict Card"),
            "expected_revision_id": "crv_stale",
        },
    )

    assert response.status_code == 409
    assert "revision_conflict" in response.json()["detail"]
