from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.proof.run_trust_conformance_pack import (
    CONFORMANCE_SUMMARY_SCHEMA_VERSION,
    main as conformance_main,
)
from scripts.proof.trusted_repo_change_contract import TARGET_CLAIM_TIER, TRUSTED_REPO_COMPARE_SCOPE


def test_conformance_pack_command_generates_positive_and_negative_cases(tmp_path: Path) -> None:
    """Layer: integration. Verifies the canonical conformance command emits a passing skeptical-evaluator summary."""
    paths = _paths(tmp_path)

    exit_code = conformance_main(_generation_args(paths))
    summary = _load(paths["summary"])

    assert exit_code == 0
    assert summary["schema_version"] == CONFORMANCE_SUMMARY_SCHEMA_VERSION
    assert summary["mode"] == "generated_fixture_conformance"
    assert summary["observed_result"] == "success"
    assert summary["adopted_compare_scopes"] == [TRUSTED_REPO_COMPARE_SCOPE]
    assert summary["selected_claim_tier"] == TARGET_CLAIM_TIER
    assert all(item["result"] == "pass" for item in summary["positive_case_results"])
    assert len(summary["negative_case_results"]) == 8
    assert all(item["result"] == "pass" for item in summary["negative_case_results"])
    assert {item["name"] for item in summary["verifier_substeps"]} >= {
        "positive_packet_generation",
        "packet_verifier",
        "finite_model",
    }
    assert isinstance(summary.get("diff_ledger"), list)


def test_supplied_fixture_mode_does_not_mutate_packet(tmp_path: Path) -> None:
    """Layer: integration. Verifies supplied-fixture verification is read-only over authority-bearing input artifacts."""
    paths = _paths(tmp_path)
    assert conformance_main(_generation_args(paths)) == 0
    before = _sha256(paths["packet"])

    supplied_summary = tmp_path / "supplied_summary.json"
    supplied_model = tmp_path / "supplied_finite_model.json"
    exit_code = conformance_main(
        [
            "--verify-fixture",
            "--packet",
            str(paths["packet"]),
            "--output",
            str(supplied_summary),
            "--finite-model-output",
            str(supplied_model),
        ]
    )
    after = _sha256(paths["packet"])
    summary = _load(supplied_summary)

    assert exit_code == 0
    assert before == after
    assert summary["mode"] == "supplied_fixture_verification"
    assert summary["observed_result"] == "success"
    assert any(item["name"] == "supplied_packet_verifier" for item in summary["verifier_substeps"])
    assert all(item["result"] == "pass" for item in summary["negative_case_results"])


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "workspace": tmp_path / "workspace",
        "summary": tmp_path / "summary.json",
        "finite_model": tmp_path / "finite_model.json",
        "packet": tmp_path / "packet.json",
        "packet_verifier": tmp_path / "packet_verifier.json",
    }


def _generation_args(paths: dict[str, Path]) -> list[str]:
    return [
        "--workspace-root",
        str(paths["workspace"]),
        "--output",
        str(paths["summary"]),
        "--finite-model-output",
        str(paths["finite_model"]),
        "--packet-output",
        str(paths["packet"]),
        "--packet-verifier-output",
        str(paths["packet_verifier"]),
    ]


def _load(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
