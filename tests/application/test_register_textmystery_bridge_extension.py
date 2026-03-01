from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path("scripts/register_textmystery_bridge_extension.py").resolve()
    spec = importlib.util.spec_from_file_location("register_textmystery_bridge_extension", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load register_textmystery_bridge_extension.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_register_textmystery_bridge_extension_writes_sdk_manifest_and_catalog(tmp_path, monkeypatch):
    module = _load_script_module()
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    durable_root = tmp_path / ".orket_durable"
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(durable_root))

    code = module.main()
    assert code == 0

    extension_dir = tmp_path / "workspace" / "live_ext" / "textmystery_bridge"
    manifest_path = extension_dir / "extension.yaml"
    module_path = extension_dir / "textmystery_bridge_extension.py"
    assert manifest_path.exists()
    assert module_path.exists()
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert "manifest_version: v0" in manifest_text
    assert "entrypoint: textmystery_bridge_extension:run_workload" in manifest_text

    catalog_path = durable_root / "config" / "extensions_catalog.json"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = payload.get("extensions", [])
    assert isinstance(rows, list)
    match = [row for row in rows if str(row.get("extension_id")) == module.EXTENSION_ID]
    assert len(match) == 1
    row = match[0]
    assert row["contract_style"] == "sdk_v0"
    assert row["workloads"][0]["workload_id"] == module.WORKLOAD_ID
    assert row["workloads"][0]["entrypoint"] == "textmystery_bridge_extension:run_workload"
