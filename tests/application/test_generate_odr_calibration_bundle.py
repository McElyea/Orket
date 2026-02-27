from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_script_module(module_name: str, script_path: str) -> ModuleType:
    path = Path(script_path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_odr_calibration_bundle_outputs_expected_distribution(tmp_path: Path) -> None:
    module = _load_script_module("generate_odr_calibration_bundle_test", "scripts/generate_odr_calibration_bundle.py")
    out_dir = tmp_path / "odr_calibration"
    args = [
        "--out-dir",
        str(out_dir),
        "--bundle-out",
        "bundle.json",
        "--labels-out",
        "labels.json",
    ]
    # Execute through subprocess-compatible path by patching argv behavior.
    import sys

    old_argv = sys.argv
    try:
        sys.argv = ["generate_odr_calibration_bundle.py", *args]
        assert module.main() == 0
    finally:
        sys.argv = old_argv

    bundle = json.loads((out_dir / "bundle.json").read_text(encoding="utf-8"))
    labels = json.loads((out_dir / "labels.json").read_text(encoding="utf-8"))

    assert bundle["schema_version"] == "odr.calibration.bundle.v1"
    assert bundle["distribution"] == {"good_resolved": 5, "stable_unresolved": 5, "bad": 5}
    assert len(bundle["runs"]) == 15

    assert labels["schema_version"] == "odr.gold_labels.v1"
    assert len(labels["runs"]) == 15
    first_round = labels["runs"][0]["rounds"][0]
    assert "delta_type_round" in first_round
    assert "delta_type_by_section" in first_round
    assert "final_outcome_gold" in labels["runs"][0]
