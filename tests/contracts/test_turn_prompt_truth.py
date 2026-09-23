"""Prompt claims follow application verifier settings and command selection."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.async_repositories import AsyncSnapshotRepository
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot
from orket.application.workflows.orchestrator import Orchestrator
from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.schema import CardStatus, IssueConfig, RoleConfig

pytestmark = pytest.mark.contract


def _orchestrator(tmp_path, rules):
    db_path = str(tmp_path / "cards.db")
    return Orchestrator(
        workspace=tmp_path, async_cards=AsyncCardRepository(db_path), snapshots=AsyncSnapshotRepository(db_path),
        org=SimpleNamespace(process_rules=rules), config_root=tmp_path, db_path=db_path,
        loader=None, sandbox_orchestrator=None,
        architecture_policy=ArchitecturePolicySnapshot(False),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("setting", ["default", "policy_disabled", "env_disabled", "env_enabled_overrides_policy"])
# Layer: contract
async def test_verifier_prompt_uses_application_setting(tmp_path, monkeypatch, compact, setting):
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.delenv("ORKET_DISABLE_RUNTIME_VERIFIER", raising=False)
    disabled = setting in {"policy_disabled", "env_disabled"}
    rules = {"disable_runtime_verifier": setting in {"policy_disabled", "env_enabled_overrides_policy"}}
    if setting.startswith("env_"):
        monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true" if disabled else "false")
    orchestrator = _orchestrator(tmp_path, rules)
    issue = IssueConfig(id="COD-1", summary="Sum", seat="coder")
    context = await orchestrator._build_turn_context(
        run_id="prompt-contract", issue=issue, seat_name="coder", roles_to_load=["coder"],
        turn_status=CardStatus.IN_PROGRESS, selected_model="unused-model",
    )
    assert context["runtime_verifier_enabled"] is not disabled
    context["compact_turn_packet_enabled"] = compact
    role = RoleConfig(id="COD", summary="coder", description="Implement", tools=["write_file"])
    messages = await MessageBuilder(tmp_path).prepare_messages(issue=issue, role=role, context=context)
    rendered = "\n".join(message["content"] for message in messages)
    assert ("no positional arguments" in rendered) is not disabled
    if disabled:
        assert "Runtime Verifier Contract:" not in rendered and "Runtime Verification:" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize("compact", [False, True])
# Layer: contract
async def test_explicit_verifier_command_does_not_advertise_inferred_no_argument_command(tmp_path, compact):
    issue = IssueConfig(id="COD-1", summary="Sum", seat="coder")
    role = RoleConfig(id="COD", summary="coder", description="Implement", tools=["write_file"])
    context = {
        "compact_turn_packet_enabled": compact, "runtime_verifier_enabled": True,
        "artifact_contract": {"kind": "app", "entrypoint_path": "agent_output/main.py"},
        "runtime_verifier_contract": {"commands": [["python", "agent_output/main.py", "2", "3"]]},
    }
    messages = await MessageBuilder(tmp_path).prepare_messages(issue=issue, role=role, context=context)
    rendered = "\n".join(message["content"] for message in messages)
    assert rendered.count("python agent_output/main.py 2 3") == 1
    assert "no positional arguments" not in rendered
    assert "will execute exactly: python agent_output/main.py" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
# Layer: contract
async def test_verifier_setting_filters_only_inferred_support_reads(tmp_path, monkeypatch, disabled, explicit):
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", str(disabled).lower())
    orchestrator = _orchestrator(tmp_path, {})
    support_path = "agent_output/verification/runtime_verification.json"
    params = {"turn_contract": {"required_read_paths": [support_path]}} if explicit else {}
    issue = IssueConfig(id="REV-1", summary="Review", seat="integrity_guard" if explicit else "code_reviewer",
                        params=params)
    context = await orchestrator._build_turn_context(
        run_id="prompt-contract", issue=issue, seat_name="integrity_guard", roles_to_load=["integrity_guard"],
        turn_status=CardStatus.AWAITING_GUARD_REVIEW, selected_model="unused-model",
    )
    assert (support_path in context["required_read_paths"]) == (explicit or not disabled)
