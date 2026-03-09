from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_sdk_import_does_not_load_internal_orket_modules(tmp_path: Path) -> None:
    """Layer: integration. Verifies importing SDK contracts does not transitively import internal `orket.*` modules."""
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    command = [
        sys.executable,
        "-c",
        (
            "import json, sys; "
            "import orket_extension_sdk as sdk; "
            "bad = sorted(name for name in sys.modules if name == 'orket' or name.startswith('orket.')); "
            "print(json.dumps({'version': sdk.__version__, 'bad': bad}))"
        ),
    ]
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["version"]
    assert payload["bad"] == []

