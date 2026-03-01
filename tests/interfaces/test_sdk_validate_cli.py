from __future__ import annotations

import json
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main


def _write_sdk_extension(
    root: Path,
    *,
    entrypoint: str = "demo_workload:run",
    required_capabilities: list[str] | None = None,
) -> None:
    required = list(required_capabilities or [])
    (root / "demo_workload.py").write_text(
        "def run(ctx, payload):\n    return payload\n",
        encoding="utf-8",
    )
    (root / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: demo",
                "extension_version: 1.0.0",
                "workloads:",
                "  - workload_id: w1",
                f"    entrypoint: {entrypoint}",
                *(
                    ["    required_capabilities: []"]
                    if not required
                    else ["    required_capabilities:", *[f"      - {cap}" for cap in required]]
                ),
            ]
        ),
        encoding="utf-8",
    )


def test_sdk_validate_unknown_capability_warns_by_default(tmp_path: Path, capsys) -> None:
    _write_sdk_extension(tmp_path, required_capabilities=["future.capability"])
    code = main(["sdk", "validate", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["warning_count"] == 1
    assert payload["error_count"] == 0
    assert "E_SDK_CAPABILITY_UNKNOWN" in captured.err


def test_sdk_validate_unknown_capability_fails_in_strict_mode(tmp_path: Path, capsys) -> None:
    _write_sdk_extension(tmp_path, required_capabilities=["future.capability"])
    code = main(["sdk", "validate", str(tmp_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 2
    assert payload["ok"] is False
    assert payload["warning_count"] == 0
    assert payload["error_count"] == 1
    assert payload["errors"][0]["code"] == "E_SDK_CAPABILITY_UNKNOWN"


def test_sdk_validate_entrypoint_resolution_error(tmp_path: Path, capsys) -> None:
    _write_sdk_extension(tmp_path, entrypoint="missing_module:run", required_capabilities=[])
    code = main(["sdk", "validate", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "E_SDK_ENTRYPOINT_MISSING"
