from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script_module(name: str, relative_path: str):
    path = Path(relative_path).resolve()
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_execute_compat_fallback_removal_noop_before_expiry():
    mod = _load_script_module("execute_compat_fallback_removal_a", "scripts/MidTier/execute_compat_fallback_removal.py")
    payload = {"extensions": [{"extension_id": "x", "compat_fallbacks": ["EXT_LOCAL_PATH_COMPAT"]}]}
    result = mod.execute_removal(catalog_payload=payload, current_version="0.4.9")
    assert result["changed"] is False
    assert result["removed_count"] == 0
    assert result["catalog"]["extensions"][0]["compat_fallbacks"] == ["EXT_LOCAL_PATH_COMPAT"]


def test_execute_compat_fallback_removal_removes_expired_codes():
    mod = _load_script_module("execute_compat_fallback_removal_b", "scripts/MidTier/execute_compat_fallback_removal.py")
    payload = {
        "extensions": [
            {"extension_id": "x", "compat_fallbacks": ["EXT_LOCAL_PATH_COMPAT", "DEV_PROFILE_EXCEPTION_LOCAL_PATH"]}
        ]
    }
    result = mod.execute_removal(catalog_payload=payload, current_version="0.5.0")
    assert result["changed"] is True
    assert result["removed_count"] == 1
    assert result["catalog"]["extensions"][0]["compat_fallbacks"] == ["DEV_PROFILE_EXCEPTION_LOCAL_PATH"]

