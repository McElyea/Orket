# Layer: contract

from __future__ import annotations

from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.application.services.sandbox_restart_policy_service import (
    SandboxRestartPolicyService,
    SandboxServiceRuntimeSnapshot,
)


def _snapshot(
    observed_at: str,
    *,
    restart_count: int,
    health_status: str | None,
    state: str = "running",
) -> SandboxServiceRuntimeSnapshot:
    return SandboxServiceRuntimeSnapshot(
        observed_at=observed_at,
        service_name="api",
        container_name="sb-1-api-1",
        state=state,
        health_status=health_status,
        restart_count=restart_count,
    )


def test_restart_policy_classifies_restart_loop_when_window_restart_delta_exceeds_threshold() -> None:
    assessment = SandboxRestartPolicyService.assess_runtime_health(
        policy=SandboxLifecyclePolicy(restart_threshold_count=1, restart_window_seconds=60, unhealthy_duration_seconds=600),
        current_snapshots=[_snapshot("2026-03-11T00:00:10+00:00", restart_count=2, health_status="healthy")],
        prior_snapshots=[_snapshot("2026-03-11T00:00:00+00:00", restart_count=0, health_status="healthy")],
    )

    assert assessment.should_terminalize is True
    assert assessment.payload["terminal_reason"] == "restart_loop"
    assert assessment.payload["restart_summary"]["services"][0]["window_restart_delta"] == 2


def test_restart_policy_classifies_restart_loop_when_unhealthy_duration_exceeds_threshold() -> None:
    assessment = SandboxRestartPolicyService.assess_runtime_health(
        policy=SandboxLifecyclePolicy(restart_threshold_count=5, restart_window_seconds=300, unhealthy_duration_seconds=1),
        current_snapshots=[_snapshot("2026-03-11T00:00:02+00:00", restart_count=0, health_status="unhealthy")],
        prior_snapshots=[_snapshot("2026-03-11T00:00:00+00:00", restart_count=0, health_status="unhealthy")],
    )

    assert assessment.should_terminalize is True
    assert assessment.payload["terminal_reason"] == "restart_loop"
    assert assessment.payload["health_summary"]["services"][0]["continuous_unhealthy_seconds"] == 2


def test_restart_policy_does_not_terminalize_before_thresholds_are_crossed() -> None:
    assessment = SandboxRestartPolicyService.assess_runtime_health(
        policy=SandboxLifecyclePolicy(restart_threshold_count=2, restart_window_seconds=60, unhealthy_duration_seconds=10),
        current_snapshots=[_snapshot("2026-03-11T00:00:03+00:00", restart_count=1, health_status="healthy")],
        prior_snapshots=[_snapshot("2026-03-11T00:00:00+00:00", restart_count=0, health_status="healthy")],
    )

    assert assessment.should_terminalize is False
    assert assessment.payload["terminal_reason"] is None
