"""Real native commands and on-disk submission inputs shared by CLI acceptance tests."""
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from tests.runtime.governed_agent_test_support import TEMPLATE_ROOT, agent_request


def run_agent_cli(tmp_path, *arguments, expected=0, db_name="agent.sqlite3"):
    executable = Path(sys.executable).with_name("orket.exe" if os.name == "nt" else "orket")
    result = subprocess.run(
        [str(executable), "agent", *arguments, "--db", str(tmp_path / db_name), "--json"],
        cwd=tmp_path, env=dict(os.environ, ORKET_DISABLE_SANDBOX="1"),
        text=True, encoding="utf-8", capture_output=True, timeout=60,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return json.loads(result.stdout)


def write_submission_files(tmp_path):
    manifest_path = TEMPLATE_ROOT / "extension.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"extensions": [{
        "extension_id": manifest["extension_id"], "extension_version": manifest["extension_version"],
        "extension_api_version": "1.0.0", "source": "test-fixture", "path": str(TEMPLATE_ROOT),
        "contract_style": "sdk_v0", "manifest_path": str(manifest_path),
        "allowed_stdlib_modules": manifest["allowed_stdlib_modules"], "manifest_entries": manifest["workloads"],
    }]}), encoding="utf-8")
    request = agent_request()
    now = datetime.now(UTC)
    # Allow native process startup; separate existing tests exercise expiry/refusal.
    request["deadline_utc"] = (now + timedelta(minutes=3)).isoformat()
    request["lease_expires_at_utc"] = (now + timedelta(minutes=2)).isoformat()
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    return catalog, request_path, now
