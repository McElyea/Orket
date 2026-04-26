from __future__ import annotations

import json

import httpx

import orket.interfaces.orket_bundle_cli as cli_module


def test_ledger_cli_exports_summarizes_and_verifies_offline(monkeypatch, capsys, tmp_path) -> None:
    """Layer: contract. Verifies outward ledger CLI export/summary use API and verify is offline."""
    requests: list[dict] = []
    monkeypatch.delenv("ORKET_API_KEY", raising=False)
    export_path = tmp_path / "ledger.json"
    offline_path = tmp_path / "offline-ledger.json"
    offline_path.write_text(
        json.dumps(
            {
                "schema_version": "ledger_export.v1",
                "export_scope": "all",
                "run_id": "run-1",
                "canonical": {"genesis": "GENESIS", "event_count": 0, "ledger_hash": "GENESIS"},
                "events": [],
                "omitted_spans": [],
            }
        ),
        encoding="utf-8",
    )

    class _FakeClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb) -> None:
            return None

        def request(self, method: str, path: str, **kwargs):
            requests.append({"method": method, "path": path, **kwargs})
            request = httpx.Request(method, f"http://127.0.0.1:8082{path}")
            if path.endswith("/ledger/verify"):
                return httpx.Response(200, json={"result": "valid", "path": path}, request=request)
            return httpx.Response(200, json={"schema_version": "ledger_export.v1", "path": path}, request=request)

    monkeypatch.setattr(cli_module.httpx, "Client", _FakeClient)

    assert cli_module.main(["ledger", "export", "run-1", "--types", "proposals,decisions", "--out", str(export_path)]) == 0
    _ = json.loads(capsys.readouterr().out)
    assert cli_module.main(["ledger", "summary", "run-1"]) == 0
    _ = json.loads(capsys.readouterr().out)
    assert cli_module.main(["ledger", "verify", str(offline_path)]) == 0
    verified = json.loads(capsys.readouterr().out)

    assert export_path.exists()
    assert verified["result"] == "valid"
    assert requests == [
        {
            "method": "GET",
            "path": "/v1/runs/run-1/ledger",
            "headers": {},
            "json": None,
            "params": {"types": "proposals,decisions", "include_pii": False},
        },
        {
            "method": "GET",
            "path": "/v1/runs/run-1/ledger/verify",
            "headers": {},
            "json": None,
            "params": None,
        },
    ]
