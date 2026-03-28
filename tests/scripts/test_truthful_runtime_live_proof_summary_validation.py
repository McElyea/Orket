# Layer: contract
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


@pytest.mark.contract
@pytest.mark.parametrize(
    ("script_path", "proof_builder_name"),
    [
        (
            Path("scripts/governance/record_truthful_runtime_packet1_live_proof.py"),
            "_build_success_payload",
        ),
        (
            Path("scripts/governance/record_truthful_runtime_packet2_repair_live_proof.py"),
            "_build_success_payload",
        ),
        (
            Path("scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py"),
            "_build_success_payload",
        ),
    ],
)
def test_live_proof_builders_reject_untrusted_run_summary_projection(
    tmp_path: Path,
    script_path: Path,
    proof_builder_name: str,
) -> None:
    module = _load_module(script_path)
    run_root = tmp_path / "workspace" / "runs" / "sess-live-proof"
    run_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_root / "run_summary.json",
        {
            "run_id": "sess-live-proof",
            "status": "done",
            "tools_used": [],
            "artifact_ids": [],
            "failure_reason": None,
            "truthful_runtime_packet1": {
                "projection_source": "legacy_packet1_surface",
                "projection_only": True,
            },
        },
    )

    builder = getattr(module, proof_builder_name)
    kwargs = {
        "model": "local-model",
        "provider": "ollama",
        "epic_id": "epic-live-proof",
        "workspace": tmp_path / "workspace",
    }
    if "repair_injection_applied" in builder.__code__.co_varnames:
        kwargs["repair_injection_applied"] = False

    with pytest.raises(ValueError, match="run_summary_truthful_runtime_packet1_projection_source_invalid"):
        builder(**kwargs)
