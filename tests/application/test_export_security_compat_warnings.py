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


def test_export_security_compat_warnings_empty():
    mod = _load_script_module("export_security_compat_warnings_a", "scripts/MidTier/export_security_compat_warnings.py")
    payload = {"extensions": [{"extension_id": "x", "compat_fallbacks": []}]}
    result = mod.build_security_compat_warnings(catalog_payload=payload)
    assert result["ok"] is True
    assert result["warning_count"] == 0
    assert result["warnings"] == []


def test_export_security_compat_warnings_collects_fallbacks():
    mod = _load_script_module("export_security_compat_warnings_b", "scripts/MidTier/export_security_compat_warnings.py")
    payload = {
        "extensions": [
            {
                "extension_id": "alpha.ext",
                "source_ref": "main",
                "security_mode": "compat",
                "security_profile": "production",
                "compat_fallbacks": ["EXT_LOCAL_PATH_COMPAT", "EXT_HOST_COMPAT"],
            }
        ]
    }
    result = mod.build_security_compat_warnings(catalog_payload=payload)
    assert result["ok"] is False
    assert result["warning_count"] == 2
    assert [row["fallback_code"] for row in result["warnings"]] == ["EXT_HOST_COMPAT", "EXT_LOCAL_PATH_COMPAT"]

