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


def test_compat_fallback_expiry_check_passes_without_expired_or_unknown_codes():
    mod = _load_script_module("check_compat_fallback_expiry_a", "scripts/check_compat_fallback_expiry.py")
    payload = {"extensions": [{"extension_id": "x", "compat_fallbacks": ["EXT_LOCAL_PATH_COMPAT"]}]}
    result = mod.evaluate_compat_fallback_expiry(current_version="0.4.9", catalog_payload=payload)
    assert result["ok"] is True
    assert result["expired_active"] == []
    assert result["unknown_codes"] == []


def test_compat_fallback_expiry_check_fails_on_expired_active_code():
    mod = _load_script_module("check_compat_fallback_expiry_b", "scripts/check_compat_fallback_expiry.py")
    payload = {"extensions": [{"extension_id": "x", "compat_fallbacks": ["EXT_LOCAL_PATH_COMPAT"]}]}
    result = mod.evaluate_compat_fallback_expiry(current_version="0.5.0", catalog_payload=payload)
    assert result["ok"] is False
    assert any(row["fallback_code"] == "EXT_LOCAL_PATH_COMPAT" for row in result["expired_active"])


def test_compat_fallback_expiry_check_fails_on_unknown_code():
    mod = _load_script_module("check_compat_fallback_expiry_c", "scripts/check_compat_fallback_expiry.py")
    payload = {"extensions": [{"extension_id": "x", "compat_fallbacks": ["EXT_UNKNOWN_COMPAT"]}]}
    result = mod.evaluate_compat_fallback_expiry(current_version="0.4.0", catalog_payload=payload)
    assert result["ok"] is False
    assert result["unknown_codes"] == ["EXT_UNKNOWN_COMPAT"]

