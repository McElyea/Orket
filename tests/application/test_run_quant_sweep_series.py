from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_script_module(module_name: str, script_path: str) -> ModuleType:
    path = Path(script_path)
    scripts_dir = str(path.parent.resolve())
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_quant_sweep_series_executes_models_in_order(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module("run_quant_sweep_series_order", "scripts/quant/run_quant_sweep_series.py")
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "models": ["qwen3.5-0.8b", "qwen3.5-2b", "qwen3.5-4b"],
                "quants": ["Q8_0"],
                "runs_per_quant": 1,
                "task_limit": 1,
            }
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(
        matrix_config=str(matrix_path),
        models="",
        summary_root=str(tmp_path / "series"),
        continue_on_error=False,
        dry_run=False,
        sanitize_model_cache=False,
        lmstudio_base_url="http://127.0.0.1:1234",
        lmstudio_timeout_sec=5,
    )
    call_order: list[str] = []

    def _fake_run(cmd: list[str]) -> tuple[int, str, str]:
        matrix_file = Path(cmd[cmd.index("--matrix-config") + 1])
        payload = json.loads(matrix_file.read_text(encoding="utf-8"))
        call_order.append(str(payload["models"][0]))
        summary_out = Path(cmd[cmd.index("--summary-out") + 1])
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(json.dumps({"ok": True}), encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(module, "_parse_args", lambda: args)
    monkeypatch.setattr(module, "_run", _fake_run)

    rc = module.main()
    assert rc == 0
    assert call_order == ["qwen3.5-0.8b", "qwen3.5-2b", "qwen3.5-4b"]

    manifest_path = tmp_path / "series" / "series_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "OK"
    assert [row["model_id"] for row in manifest["results"]] == call_order
    assert manifest["model_cache_sanitation"]["enabled"] is False


def test_run_quant_sweep_series_uses_shared_model_cache_clear(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module("run_quant_sweep_series_shared_clear", "scripts/quant/run_quant_sweep_series.py")
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "models": ["qwen3.5-0.8b"],
                "quants": ["Q8_0"],
                "runs_per_quant": 1,
                "task_limit": 1,
            }
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        matrix_config=str(matrix_path),
        models="",
        summary_root=str(tmp_path / "series"),
        continue_on_error=False,
        dry_run=False,
        sanitize_model_cache=True,
        lmstudio_base_url="http://127.0.0.1:1234",
        lmstudio_timeout_sec=5,
    )
    seen_stages: list[str] = []

    def _fake_clear_loaded_models(*, stage: str, base_url: str, timeout_sec: int, strict: bool):  # noqa: ANN001
        del base_url, timeout_sec, strict
        seen_stages.append(stage)
        return {"stage": stage, "status": "OK"}

    monkeypatch.setattr(module, "_parse_args", lambda: args)
    monkeypatch.setattr(module, "_run", lambda cmd: (0, "", ""))  # noqa: ARG005
    monkeypatch.setattr(module, "clear_loaded_models", _fake_clear_loaded_models)

    rc = module.main()
    assert rc == 0
    assert seen_stages == ["pre_run", "post_run"]
