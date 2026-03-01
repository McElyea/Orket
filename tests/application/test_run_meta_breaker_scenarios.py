from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


def _load_register_module():
    script_path = Path("scripts/register_meta_breaker_extension.py").resolve()
    spec = importlib.util.spec_from_file_location("register_meta_breaker_extension_for_scenarios", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load register_meta_breaker_extension.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_meta_breaker_scenarios_emits_pack_report(tmp_path, monkeypatch):
    register_module = _load_register_module()
    monkeypatch.setattr(register_module, "PROJECT_ROOT", tmp_path)
    durable_root = tmp_path / ".orket_durable"
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(durable_root))
    assert register_module.main() == 0

    output = tmp_path / "meta_breaker_scenarios.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_meta_breaker_scenarios.py",
            "--project-root",
            str(tmp_path),
            "--workspace",
            str(tmp_path / "workspace" / "default"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "meta_breaker.scenario_pack.v1"
    assert payload["workload_id"] == "meta_breaker_v1"
    assert payload["scenario_count"] == 3
    assert len(payload["scenarios"]) == 3
    for row in payload["scenarios"]:
        assert Path(row["artifact_root"]).exists()
        assert Path(row["provenance_path"]).exists()
