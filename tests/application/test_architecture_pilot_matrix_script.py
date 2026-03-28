from __future__ import annotations

from scripts.acceptance.run_architecture_pilot_matrix import (
    PilotCombo,
    _aggregate_by_architecture,
    _build_comparison,
    _build_env,
    build_combos,
    rotate_previous_artifact,
)


def test_build_combos_cartesian_product() -> None:
    combos = build_combos(
        ["force_monolith", "force_microservices"],
        ["coder", "architect"],
        ["backend_only"],
    )
    assert len(combos) == 4
    assert combos[0] == PilotCombo(
        architecture_mode="force_monolith",
        builder_variant="coder",
        project_surface_profile="backend_only",
    )
    assert combos[-1] == PilotCombo(
        architecture_mode="force_microservices",
        builder_variant="architect",
        project_surface_profile="backend_only",
    )


def test_build_env_sets_microservices_toggle_from_architecture_mode() -> None:
    mono_env = _build_env(
        PilotCombo(
            architecture_mode="force_monolith",
            builder_variant="coder",
            project_surface_profile="backend_only",
        )
    )
    micro_env = _build_env(
        PilotCombo(
            architecture_mode="force_microservices",
            builder_variant="coder",
            project_surface_profile="backend_only",
        )
    )
    assert mono_env["ORKET_ARCHITECTURE_MODE"] == "force_monolith"
    assert mono_env["ORKET_ENABLE_MICROSERVICES"] == "false"
    assert micro_env["ORKET_ARCHITECTURE_MODE"] == "force_microservices"
    assert micro_env["ORKET_ENABLE_MICROSERVICES"] == "true"


# Layer: contract
def test_aggregate_and_comparison_metrics() -> None:
    entries = [
        {
            "architecture_mode": "force_monolith",
            "executed": True,
            "summary": {
                "run_count": 2,
                "passed": 2,
                "failed": 0,
                "pass_rate": 1.0,
                "runtime_failure_rate": 0.0,
                "reviewer_rejection_rate": 0.0,
                "invalid_payload_signals": {"metrics_json": 0, "db_summary_json": 0},
            },
        },
        {
            "architecture_mode": "force_microservices",
            "executed": True,
            "summary": {
                "run_count": 2,
                "passed": 1,
                "failed": 1,
                "pass_rate": 0.5,
                "runtime_failure_rate": 0.0,
                "reviewer_rejection_rate": 0.25,
                "invalid_payload_signals": {"metrics_json": 0, "db_summary_json": 0},
            },
        },
    ]
    aggregate = _aggregate_by_architecture(entries)
    assert aggregate["force_monolith"]["pass_rate"] == 1.0
    assert aggregate["force_microservices"]["pass_rate"] == 0.5
    assert aggregate["force_monolith"]["invalid_payload_signals"] == {"db_summary_json": 0, "metrics_json": 0}
    assert aggregate["force_monolith"]["invalid_payload_failures"] == []
    comparison = _build_comparison(entries)
    assert comparison["available"] is True
    assert comparison["pass_rate_delta_microservices_minus_monolith"] == -0.5
    assert comparison["reviewer_rejection_rate_delta_microservices_minus_monolith"] == 0.25
    assert comparison["invalid_payload_signals_by_architecture"] == {
        "force_microservices": {"db_summary_json": 0, "metrics_json": 0},
        "force_monolith": {"db_summary_json": 0, "metrics_json": 0},
    }
    assert comparison["invalid_payload_signal_totals_by_architecture"] == {
        "force_microservices": 0,
        "force_monolith": 0,
    }
    assert comparison["invalid_payload_failures"] == []


# Layer: contract
def test_aggregate_and_comparison_preserve_invalid_payload_drift() -> None:
    entries = [
        {
            "architecture_mode": "force_monolith",
            "executed": True,
            "summary": {
                "run_count": 1,
                "passed": 1,
                "failed": 0,
                "pass_rate": 1.0,
                "runtime_failure_rate": 0.0,
                "reviewer_rejection_rate": 0.0,
                "invalid_payload_signals": {"metrics_json": 1, "db_summary_json": 0},
            },
        },
        {
            "architecture_mode": "force_microservices",
            "executed": True,
            "summary": {
                "run_count": 1,
                "passed": 1,
                "failed": 0,
                "pass_rate": 1.0,
                "runtime_failure_rate": 0.0,
                "reviewer_rejection_rate": 0.0,
            },
        },
    ]
    aggregate = _aggregate_by_architecture(entries)
    assert aggregate["force_monolith"]["invalid_payload_signals"] == {"db_summary_json": 0, "metrics_json": 1}
    assert aggregate["force_microservices"]["invalid_payload_failures"] == [
        "invalid_payload_signals missing or invalid for unknown-builder/unknown-profile"
    ]
    comparison = _build_comparison(entries)
    assert comparison["invalid_payload_signals_by_architecture"] == {
        "force_microservices": {},
        "force_monolith": {"db_summary_json": 0, "metrics_json": 1},
    }
    assert comparison["invalid_payload_signal_totals_by_architecture"] == {
        "force_microservices": 0,
        "force_monolith": 1,
    }
    assert comparison["invalid_payload_failures"] == [
        "force_microservices: invalid_payload_signals missing or invalid for unknown-builder/unknown-profile"
    ]


def test_rotate_previous_artifact_copies_existing_output(tmp_path) -> None:
    current = tmp_path / "current.json"
    previous = tmp_path / "history" / "previous.json"
    current.write_text('{"ok": true}', encoding="utf-8")

    rotate_previous_artifact(current, previous)

    assert previous.exists()
    assert previous.read_text(encoding="utf-8") == '{"ok": true}'


def test_rotate_previous_artifact_noop_when_missing_current(tmp_path) -> None:
    current = tmp_path / "missing.json"
    previous = tmp_path / "previous.json"

    rotate_previous_artifact(current, previous)

    assert not previous.exists()
