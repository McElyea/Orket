from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx

from orket.application.services.outward_connector_service import (
    OutwardConnectorArgumentError,
    OutwardConnectorNotFoundError,
    OutwardConnectorService,
)
from orket.application.services.outward_ledger_service import verify_ledger_file

ERROR_RUN_API_FAILED = "E_RUN_API_FAILED"
ERROR_CONNECTOR_FAILED = "E_CONNECTOR_FAILED"


def _run_api_base_url() -> str:
    return str(os.getenv("ORKET_API_URL") or "http://127.0.0.1:8082").rstrip("/")


def _run_api_headers() -> dict[str, str]:
    api_key = str(os.getenv("ORKET_API_KEY") or "").strip()
    return {"X-API-Key": api_key} if api_key else {}


def _run_api_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    with httpx.Client(base_url=_run_api_base_url(), timeout=30.0) as client:
        response = client.request(
            method,
            path,
            headers=_run_api_headers(),
            json=payload,
            params=params,
        )
    try:
        body: Any = response.json()
    except json.JSONDecodeError:
        body = {"detail": response.text}
    return response.status_code, body


def _read_instruction(args: argparse.Namespace) -> str:
    inline = str(getattr(args, "instruction", "") or "").strip()
    file_path = str(getattr(args, "instruction_file", "") or "").strip()
    if inline:
        return inline
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    return ""


def handle_run_command(args: argparse.Namespace) -> int:
    command = str(getattr(args, "run_command", "") or "").strip()
    try:
        if command == "submit":
            policy_overrides: dict[str, Any] = {}
            tools = [str(item).strip() for item in list(getattr(args, "approval_required_tools", []) or []) if str(item).strip()]
            if tools:
                policy_overrides["approval_required_tools"] = tools
            if getattr(args, "max_turns", None) is not None:
                policy_overrides["max_turns"] = int(args.max_turns)
            if getattr(args, "approval_timeout_seconds", None) is not None:
                policy_overrides["approval_timeout_seconds"] = int(args.approval_timeout_seconds)
            payload: dict[str, Any] = {
                "task": {
                    "description": str(args.description or ""),
                    "instruction": _read_instruction(args),
                }
            }
            if str(getattr(args, "run_id", "") or "").strip():
                payload["run_id"] = str(args.run_id).strip()
            if str(getattr(args, "namespace", "") or "").strip():
                payload["namespace"] = str(args.namespace).strip()
            if policy_overrides:
                payload["policy_overrides"] = policy_overrides
            status_code, body = _run_api_request("POST", "/v1/runs", payload=payload)
        elif command == "status":
            status_code, body = _run_api_request("GET", f"/v1/runs/{args.run_id}")
        elif command == "list":
            params = {
                key: value
                for key, value in {
                    "status": getattr(args, "status", None),
                    "limit": getattr(args, "limit", None),
                    "offset": getattr(args, "offset", None),
                }.items()
                if value is not None and str(value).strip() != ""
            }
            status_code, body = _run_api_request("GET", "/v1/runs", params=params)
        elif command == "events":
            params = {
                key: value
                for key, value in {
                    "types": getattr(args, "types", None),
                    "from_turn": getattr(args, "from_turn", None),
                    "to_turn": getattr(args, "to_turn", None),
                    "agent_id": getattr(args, "agent_id", None),
                }.items()
                if value is not None and str(value).strip() != ""
            }
            status_code, body = _run_api_request("GET", f"/v1/runs/{args.run_id}/events", params=params)
        elif command == "summary":
            status_code, body = _run_api_request("GET", f"/v1/runs/{args.run_id}/summary")
        elif command == "watch":
            watch_params = {"types": args.types} if str(getattr(args, "types", "") or "").strip() else None
            status_code, body = _run_api_request("GET", f"/v1/runs/{args.run_id}/events/stream", params=watch_params)
        else:
            status_code, body = 2, {"detail": "Unsupported run command"}
    except (OSError, ValueError, httpx.HTTPError) as exc:
        status_code, body = 1, {"code": ERROR_RUN_API_FAILED, "detail": str(exc)}

    print(json.dumps(body, indent=2, ensure_ascii=False))
    return 0 if 200 <= int(status_code) < 300 else 1


def handle_approvals_command(args: argparse.Namespace) -> int:
    command = str(getattr(args, "approvals_command", "") or "").strip()
    try:
        if command in {"list", "watch"}:
            status = str(getattr(args, "status", "") or "pending").strip() or "pending"
            status_code, body = _run_api_request("GET", "/v1/approvals", params={"status": status})
        elif command == "review":
            status_code, body = _run_api_request("GET", f"/v1/approvals/{args.proposal_id}")
        elif command == "approve":
            status_code, body = _run_api_request(
                "POST",
                f"/v1/approvals/{args.proposal_id}/approve",
                payload={"note": str(getattr(args, "note", "") or "") or None},
            )
        elif command == "deny":
            status_code, body = _run_api_request(
                "POST",
                f"/v1/approvals/{args.proposal_id}/deny",
                payload={"reason": str(args.reason or ""), "note": str(getattr(args, "note", "") or "") or None},
            )
        else:
            status_code, body = 2, {"detail": "Unsupported approvals command"}
    except (OSError, ValueError, httpx.HTTPError) as exc:
        status_code, body = 1, {"code": ERROR_RUN_API_FAILED, "detail": str(exc)}

    print(json.dumps(body, indent=2, ensure_ascii=False))
    return 0 if 200 <= int(status_code) < 300 else 1


def handle_ledger_command(args: argparse.Namespace) -> int:
    command = str(getattr(args, "ledger_command", "") or "").strip()
    try:
        if command == "export":
            params = {
                key: value
                for key, value in {
                    "types": getattr(args, "types", None),
                    "include_pii": bool(getattr(args, "include_pii", False)),
                }.items()
                if value is not None and str(value).strip() != ""
            }
            status_code, body = _run_api_request("GET", f"/v1/runs/{args.run_id}/ledger", params=params)
            if 200 <= int(status_code) < 300:
                Path(str(args.out)).write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        elif command == "verify":
            body = asyncio.run(verify_ledger_file(Path(str(args.file))))
            status_code = 200 if body["result"] in {"valid", "partial_valid"} else 1
        elif command == "summary":
            status_code, body = _run_api_request("GET", f"/v1/runs/{args.run_id}/ledger/verify")
        else:
            status_code, body = 2, {"detail": "Unsupported ledger command"}
    except (OSError, ValueError, json.JSONDecodeError, httpx.HTTPError) as exc:
        status_code, body = 1, {"code": ERROR_RUN_API_FAILED, "detail": str(exc)}

    print(json.dumps(body, indent=2, ensure_ascii=False))
    return 0 if 200 <= int(status_code) < 300 else 1


def _connector_http_allowlist() -> tuple[str, ...]:
    raw = str(os.getenv("ORKET_CONNECTOR_HTTP_ALLOWLIST") or "")
    return tuple(host.strip().lower() for host in raw.split(",") if host.strip())


def _connector_service(workspace_root: str) -> OutwardConnectorService:
    return asyncio.run(OutwardConnectorService.for_workspace(
        Path(workspace_root),
        http_allowlist=_connector_http_allowlist(),
    ))


def handle_connectors_command(args: argparse.Namespace) -> int:
    command = str(getattr(args, "connectors_command", "") or "").strip()
    service = _connector_service(str(getattr(args, "workspace", "") or "."))
    try:
        if command == "list":
            status_code, body = 200, service.list_connectors()
        elif command == "show":
            status_code, body = 200, service.show_connector(str(args.name))
        elif command == "test":
            raw_args = json.loads(str(args.args or "{}"))
            body = asyncio.run(service.invoke(str(args.name), raw_args))
            status_code = 200 if body.get("outcome") == "success" else 1
        else:
            status_code, body = 2, {"detail": "Unsupported connectors command"}
    except OutwardConnectorArgumentError as exc:
        status_code, body = 1, {"code": ERROR_CONNECTOR_FAILED, "connector_name": exc.connector_name, "errors": exc.errors}
    except OutwardConnectorNotFoundError as exc:
        status_code, body = 1, {"code": ERROR_CONNECTOR_FAILED, "detail": str(exc)}
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        status_code, body = 1, {"code": ERROR_CONNECTOR_FAILED, "detail": str(exc)}

    print(json.dumps(body, indent=2, ensure_ascii=False))
    return 0 if 200 <= int(status_code) < 300 else 1
