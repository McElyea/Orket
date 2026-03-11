# Layer: contract

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


def test_sandbox_lifecycle_record_schema_exposes_required_fields() -> None:
    required = set(SandboxLifecycleRecord.model_json_schema().get("required", []))
    assert {
        "sandbox_id",
        "compose_project",
        "workspace_path",
        "lease_epoch",
        "state",
        "cleanup_state",
        "record_version",
        "created_at",
        "managed_resource_inventory",
        "requires_reconciliation",
        "docker_context",
        "docker_host_id",
    }.issubset(required)


def test_sandbox_lifecycle_record_requires_run_or_session_identity() -> None:
    with pytest.raises(ValidationError, match="run_id or session_id"):
        SandboxLifecycleRecord(
            sandbox_id="sb-1",
            compose_project="orket-sandbox-sb-1",
            workspace_path="workspace/sb-1",
            lease_epoch=0,
            state=SandboxState.CREATING,
            cleanup_state=CleanupState.NONE,
            record_version=1,
            created_at="2026-03-11T00:00:00+00:00",
            cleanup_attempts=0,
            managed_resource_inventory={"containers": [], "networks": [], "managed_volumes": []},
            requires_reconciliation=False,
            docker_context="default",
            docker_host_id="host-a",
        )


def test_sandbox_lifecycle_record_requires_terminal_reason_for_terminal_states() -> None:
    with pytest.raises(ValidationError, match="terminal_reason"):
        SandboxLifecycleRecord(
            sandbox_id="sb-2",
            compose_project="orket-sandbox-sb-2",
            workspace_path="workspace/sb-2",
            run_id="run-2",
            lease_epoch=0,
            state=SandboxState.TERMINAL,
            cleanup_state=CleanupState.NONE,
            record_version=1,
            created_at="2026-03-11T00:00:00+00:00",
            cleanup_attempts=0,
            managed_resource_inventory={"containers": [], "networks": [], "managed_volumes": []},
            requires_reconciliation=False,
            docker_context="default",
            docker_host_id="host-a",
        )


def test_sandbox_lifecycle_record_accepts_phase_one_required_fields() -> None:
    record = SandboxLifecycleRecord(
        sandbox_id="sb-3",
        compose_project="orket-sandbox-sb-3",
        workspace_path="workspace/sb-3",
        run_id="run-3",
        lease_epoch=0,
        state=SandboxState.CLEANED,
        cleanup_state=CleanupState.COMPLETED,
        record_version=1,
        created_at="2026-03-11T00:00:00+00:00",
        terminal_reason=TerminalReason.CLEANED_EXTERNALLY,
        cleanup_attempts=0,
        managed_resource_inventory={"containers": [], "networks": [], "managed_volumes": []},
        docker_host_id="host-a",
        requires_reconciliation=True,
        cleanup_failure_reason="docker-down-timeout",
        docker_context="default",
    )

    assert record.requires_reconciliation is True
    assert record.cleanup_failure_reason == "docker-down-timeout"
