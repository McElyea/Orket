# Layer: contract

from __future__ import annotations

from orket.application.services.sandbox_cleanup_authority_service import SandboxCleanupAuthorityService
from orket.core.domain.sandbox_cleanup import DockerResourceType, ObservedDockerResource
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


def _record(**overrides) -> SandboxLifecycleRecord:
    payload = {
        "sandbox_id": "sb-1",
        "compose_project": "orket-sandbox-sb-1",
        "workspace_path": "workspace/sb-1",
        "run_id": "run-1",
        "lease_epoch": 0,
        "state": SandboxState.TERMINAL,
        "cleanup_state": CleanupState.SCHEDULED,
        "record_version": 3,
        "created_at": "2026-03-11T00:00:00+00:00",
        "terminal_reason": "failed",
        "cleanup_attempts": 0,
        "managed_resource_inventory": ManagedResourceInventory(
            containers=["sb-1-api"],
            networks=["sb-1-net"],
            managed_volumes=["sb-1-db"],
        ),
        "requires_reconciliation": False,
        "docker_context": "desktop-linux",
        "docker_host_id": "host-a",
    }
    payload.update(overrides)
    return SandboxLifecycleRecord(**payload)


def _resource(name: str, *, labels: dict[str, str] | None = None, context: str = "desktop-linux", host: str = "host-a") -> ObservedDockerResource:
    return ObservedDockerResource(
        resource_type=DockerResourceType.CONTAINER,
        name=name,
        docker_context=context,
        docker_host_id=host,
        labels=labels or {},
    )


def test_compose_cleanup_allowed_with_record_scope_and_matching_host_context() -> None:
    service = SandboxCleanupAuthorityService()
    decision = service.decide(
        record=_record(),
        observed_resources=[
            _resource(
                "sb-1-api",
                labels={"orket.managed": "true", "orket.sandbox_id": "sb-1", "orket.run_id": "run-1"},
            )
        ],
        compose_path_available=True,
    )

    assert decision.compose_cleanup_allowed is True
    assert "compose_project_authority" in decision.reason_codes


def test_fallback_cleanup_rejects_prefix_only_unlabeled_resources() -> None:
    service = SandboxCleanupAuthorityService()
    decision = service.decide(
        record=_record(),
        observed_resources=[_resource("orket-sandbox-sb-1_api_1")],
        compose_path_available=False,
    )

    assert decision.compose_cleanup_allowed is False
    assert decision.fallback_resource_names == []
    assert decision.blocked_resource_names == ["orket-sandbox-sb-1_api_1"]
    assert "missing_positive_authority" in decision.reason_codes


def test_compose_cleanup_is_blocked_when_observed_resources_lack_positive_authority() -> None:
    service = SandboxCleanupAuthorityService()
    decision = service.decide(
        record=_record(),
        observed_resources=[_resource("orket-sandbox-sb-1_api_1")],
        compose_path_available=True,
    )

    assert decision.compose_cleanup_allowed is False
    assert decision.blocked_resource_names == ["orket-sandbox-sb-1_api_1"]
    assert "missing_positive_authority" in decision.reason_codes
    assert "compose_cleanup_blocked" in decision.reason_codes


def test_cleanup_is_blocked_on_cross_daemon_or_context_mismatch() -> None:
    service = SandboxCleanupAuthorityService()
    decision = service.decide(
        record=_record(),
        observed_resources=[
            _resource(
                "sb-1-api",
                labels={"orket.managed": "true", "orket.sandbox_id": "sb-1", "orket.run_id": "run-1"},
                context="other-context",
            )
        ],
        compose_path_available=True,
    )

    assert decision.compose_cleanup_allowed is False
    assert "host_context_mismatch" in decision.reason_codes


def test_cleanup_allows_legacy_pid_scoped_host_ids_on_same_host() -> None:
    service = SandboxCleanupAuthorityService()
    decision = service.decide(
        record=_record(docker_host_id="host-a:4242"),
        observed_resources=[
            _resource(
                "sb-1-api",
                labels={"orket.managed": "true", "orket.sandbox_id": "sb-1", "orket.run_id": "run-1"},
                host="host-a",
            )
        ],
        compose_path_available=True,
    )

    assert decision.compose_cleanup_allowed is True
    assert "host_context_mismatch" not in decision.reason_codes


def test_break_glass_scope_only_allows_explicitly_approved_resources() -> None:
    service = SandboxCleanupAuthorityService()
    decision = service.decide(
        record=_record(),
        observed_resources=[_resource("manual-volume")],
        compose_path_available=False,
        break_glass_approved=True,
        approved_resource_names={"manual-volume"},
    )

    assert decision.fallback_resource_names == ["manual-volume"]
    assert "break_glass_scope_applied" in decision.reason_codes
