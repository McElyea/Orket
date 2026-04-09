# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.extensions.build_extension_capability_audit import main


def test_build_extension_capability_audit_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "extension_capability_audit.json"

    exit_code = main(["--out", str(out_path), "--strict"])

    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "extension_capability_audit.v1"
    assert isinstance(payload.get("rows"), list)
    assert any(row["test_case"] == "memory_query_allowed" for row in payload["rows"])
    assert any(row["test_case"] == "child_drift_memory_write" for row in payload["rows"])
    assert isinstance(payload.get("diff_ledger"), list)
