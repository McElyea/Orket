# Layer: end-to-end

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from orket.interfaces.orket_bundle_cli import main
from orket_extension_sdk.agent_fixtures import prefixed_digest
from tests.runtime.governed_agent_test_support import staged_agent_request, ticket_continuation_inputs

_LIVE_ENABLED = os.getenv("ORKET_RUN_LIVE_AGENT_OLLAMA") == "1"
_EXTENSION_ROOT = Path(
    os.getenv(
        "ORKET_GOVERNED_AGENT_EXTENSION_ROOT",
        r"C:\Source\OrketExtensions\GoverenedAgentLoop",
    )
)


@pytest.mark.end_to_end
@pytest.mark.parametrize("case_id", ["mixed", "all-open", "empty-first"])
@pytest.mark.skipif(not _LIVE_ENABLED, reason="set ORKET_RUN_LIVE_AGENT_OLLAMA=1 for live Ollama proof")
def test_live_single_model_reaches_verified_terminal_truth(tmp_path: Path, capsys, monkeypatch, case_id) -> None:
    """Layer: end-to-end. One exact Ollama model crosses two external child iterations."""
    model = os.getenv("ORKET_GOVERNED_AGENT_OLLAMA_MODEL", "qwen2.5:7b")
    payload = _run_live(tmp_path, capsys, monkeypatch, models={"default": model}, case_id=case_id)

    assert payload["proof_posture"] == "live_local_model"
    assert payload["observed_path"] == "primary"
    assert payload["observed_result"] == "success"
    assert payload["run"]["lifecycle_state"] == "completed"
    assert [decision["disposition"] for decision in payload["decisions"]] == ["continue", "complete"]
    receipts = _receipts(payload)
    assert {receipt["model"] for receipt in receipts} == {model}
    _assert_measured_receipts(receipts)


@pytest.mark.end_to_end
@pytest.mark.parametrize("case_id", ["mixed", "all-open", "empty-first"])
@pytest.mark.skipif(not _LIVE_ENABLED, reason="set ORKET_RUN_LIVE_AGENT_OLLAMA=1 for live Ollama proof")
def test_live_multi_model_preserves_distinct_role_identity(tmp_path: Path, capsys, monkeypatch, case_id) -> None:
    """Layer: end-to-end. Fixed roles use two or more exact local model identities."""
    planner = os.getenv("ORKET_GOVERNED_AGENT_PLANNER_MODEL", "qwen2.5:7b")
    actor = os.getenv("ORKET_GOVERNED_AGENT_ACTOR_MODEL", "qwen2.5-coder:7b")
    critic = os.getenv("ORKET_GOVERNED_AGENT_CRITIC_MODEL", planner)
    payload = _run_live(
        tmp_path,
        capsys,
        monkeypatch,
        models={"default": planner, "planner": planner, "actor": actor, "critic": critic},
        case_id=case_id,
    )

    assert payload["observed_result"] == "success"
    role_models = {
        receipt["role"]: receipt["model"]
        for receipt in _receipts(payload)
        if receipt["status"] == "returned"
    }
    assert role_models == {"planner": planner, "actor": actor, "critic": critic}
    assert len(set(role_models.values())) >= 2
    _assert_measured_receipts(_receipts(payload))


def _run_live(tmp_path: Path, capsys, monkeypatch, *, models: dict[str, str], case_id: str, provider: str | None = "ollama") -> dict:
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    if not _EXTENSION_ROOT.is_dir():
        pytest.fail(f"Live external extension is missing: {_EXTENSION_ROOT}")
    manifest_path = _EXTENSION_ROOT / "extension.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    catalog_path = tmp_path / "extensions.json"
    catalog_path.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": manifest["extension_id"],
                        "extension_version": manifest["extension_version"],
                        "extension_api_version": "1.0.0",
                        "source": "live-external-proof",
                        "path": str(_EXTENSION_ROOT.resolve()),
                        "contract_style": "sdk_v0",
                        "manifest_path": str(manifest_path.resolve()),
                        "allowed_stdlib_modules": manifest["allowed_stdlib_modules"],
                        "manifest_entries": manifest["workloads"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_live_request(case_id)), encoding="utf-8")
    continuation_path = tmp_path / "continuation.json"
    continuation_path.write_text(json.dumps(ticket_continuation_inputs(case_id)), encoding="utf-8")
    now = datetime.now(UTC)
    args = [
        "agent", "submit", "governed-agent-loop",
        "--db", str(tmp_path / "agent.sqlite3"),
        "--catalog", str(catalog_path),
        "--request", str(request_path),
        "--continuation-inputs", str(continuation_path),
        "--creation-timestamp-utc", now.isoformat(),
        "--decision-timestamp-utc", (now + timedelta(seconds=1)).isoformat(),
        "--decision-timestamp-utc", (now + timedelta(seconds=2)).isoformat(),
        "--next-lease-expires-at-utc", (now + timedelta(minutes=9)).isoformat(),
        "--model", models["default"],
    ]
    if provider is not None:
        args.extend(("--provider", provider))
    for role in ("planner", "actor", "critic"):
        if role in models:
            args.extend((f"--{role}-model", models[role]))
    args.append("--json")
    exit_code = main(args)
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert exit_code == 0, payload
    return payload


def _live_request(case_id: str = "mixed") -> dict:
    request = staged_agent_request(case_id)
    now = datetime.now(UTC)
    request["deadline_utc"] = (now + timedelta(minutes=10)).isoformat()
    request["lease_expires_at_utc"] = (now + timedelta(minutes=9)).isoformat()
    for profile in request["model_profiles"]:
        profile["max_output_tokens"] = 512
        profile["timeout_ms"] = 120_000
    _set_budget(request["remaining_iteration_budget"], run_scope=False)
    _set_budget(request["remaining_run_budget"], run_scope=True)
    return request


def _set_budget(budget: dict, *, run_scope: bool) -> None:
    multiplier = 2 if run_scope else 1
    budget["model_calls"] = 4 * multiplier
    budget["per_role_model_calls"] = [
        {"role": role, "count": 2 * multiplier}
        for role in ("planner", "actor", "critic")
    ]
    budget["input_tokens"] = 16_384 * multiplier
    budget["output_tokens"] = 2_048 * multiplier
    budget["repair_attempts"] = multiplier
    budget["wall_time_ms"] = 600_000
    budget["snapshot_digest"] = prefixed_digest(
        {key: value for key, value in budget.items() if key != "snapshot_digest"}
    )


def _receipts(payload: dict) -> list[dict]:
    return [
        call["receipt"]
        for iteration in payload["iterations"]
        for call in iteration["model_calls"]
        if call["receipt"] is not None
    ]


def _assert_measured_receipts(receipts: list[dict]) -> None:
    assert len(receipts) >= 6
    for receipt in receipts:
        assert receipt["status"] == "returned"
        assert receipt["usage_posture"] == "measured"
        assert isinstance(receipt["input_tokens"], int)
        assert isinstance(receipt["output_tokens"], int)
        assert receipt["latency_ms"] >= 0
        assert receipt["finish_reason"]
        assert isinstance(receipt["truncated"], bool)
