from __future__ import annotations

from orket.interfaces.operator_view_models import build_card_list_item_view, build_run_detail_view
from orket.interfaces.operator_view_support import build_provider_status_view, build_system_health_view


def test_run_detail_view_uses_verified_completion_vocabulary() -> None:
    """Layer: contract. Verifies verified completion is labeled through the canonical operator outcome vocabulary."""
    view = build_run_detail_view(
        session_id="run-verified",
        status="done",
        summary={
            "status": "done",
            "execution_profile": "builder_guard_app_v1",
            "truthful_runtime_packet1": {
                "provenance": {
                    "primary_output_kind": "artifact",
                    "primary_output_id": "agent_output/main.py",
                    "truth_classification": "direct",
                }
            },
            "truthful_runtime_packet2": {
                "source_attribution": {
                    "synthesis_status": "verified",
                }
            },
        },
        artifacts={"runtime_verification_path": "agent_output/verification/runtime_verification.json"},
        issue_count=1,
    )

    assert view["lifecycle_category"] == "artifact_run_verified"
    assert view["primary_status"] == "completed"
    assert view["verification"]["status"] == "verified"
    assert view["summary"] == "Completed with verified evidence."
    assert "run.lifecycle.artifact_run_verified" in view["reason_codes"]


def test_run_detail_view_distinguishes_prebuild_blocked_from_artifact_failure() -> None:
    """Layer: contract. Verifies failed ODR prebuild without a primary output is not presented as an artifact run failure."""
    view = build_run_detail_view(
        session_id="run-prebuild-blocked",
        status="failed",
        summary={
            "status": "failed",
            "execution_profile": "odr_prebuild_builder_guard_v1",
            "odr_active": True,
            "odr_stop_reason": "UNRESOLVED_DECISIONS",
            "truthful_runtime_packet1": {
                "provenance": {
                    "primary_output_kind": "none",
                }
            },
        },
        artifacts={},
        issue_count=1,
    )

    assert view["lifecycle_category"] == "prebuild_blocked"
    assert view["primary_status"] == "blocked"
    assert view["summary"] == "Blocked in prebuild before an artifact-producing run started."


def test_card_list_item_uses_terminal_failure_bucket_when_last_run_failed() -> None:
    """Layer: contract. Verifies card list filtering can distinguish terminal failure from generic blocked status."""
    run_view = {
        "session_id": "run-prebuild-blocked",
        "primary_status": "blocked",
        "degraded": False,
        "summary": "Blocked in prebuild before an artifact-producing run started.",
        "reason_codes": ["run.lifecycle.prebuild_blocked"],
        "next_action": "review_prebuild_findings",
        "lifecycle_category": "prebuild_blocked",
    }
    view = build_card_list_item_view(
        card={
            "id": "CARD-1",
            "session_id": "run-prebuild-blocked",
            "build_id": "build-1",
            "summary": "Blocked card",
            "seat": "coder",
            "status": "blocked",
        },
        run_view=run_view,
    )

    assert view["filter_bucket"] == "terminal_failure"
    assert view["primary_status"] == "failed"
    assert view["next_action"] == "review_prebuild_findings"


def test_provider_status_and_system_health_views_surface_degraded_truth() -> None:
    """Layer: contract. Verifies provider demotion and hot resources stay first-class degraded operator state."""
    provider_view = build_provider_status_view(
        [
            {
                "role": "coder",
                "final_model": "qwen2.5-coder:7b",
                "dialect": "openai",
                "demoted": True,
                "reason": "fallback_profile",
            }
        ]
    )
    system_view = build_system_health_view(
        heartbeat={"status": "online", "active_tasks": 2, "timestamp": "2026-04-08T10:00:00+00:00"},
        metrics={
            "cpu_percent": 95.0,
            "ram_percent": 70.0,
            "vram_gb_used": 0.0,
            "vram_total_gb": 0.0,
            "timestamp": "2026-04-08T10:00:00+00:00",
        },
        provider_status=provider_view,
    )

    assert provider_view["degraded"] is True
    assert provider_view["primary_status"] == "degraded"
    assert provider_view["reason_codes"] == ["provider.assignment_demoted"]
    assert system_view["degraded"] is True
    assert "system.cpu_hot" in system_view["reason_codes"]
    assert "system.provider_degraded" in system_view["reason_codes"]
