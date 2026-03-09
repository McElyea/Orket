from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_external_extension_template_server_serves_static_ui() -> None:
    """Layer: contract. Verifies external extension template web server boots and serves static UI assets."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        from companion_app.server import app

        client = TestClient(app)
        home = client.get("/")
        assert home.status_code == 200
        assert "Companion MVP Template" in home.text
        assert client.get("/healthz").json() == {"ok": True}
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/styles.css").status_code == 200
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)
