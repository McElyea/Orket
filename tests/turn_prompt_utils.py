from __future__ import annotations

import json
from typing import Any


_EXECUTION_CONTEXT_MARKER = "Execution Context JSON:\n"
_TURN_PACKET_PREFIX = "TURN PACKET:\n"
_IDENTITY_PREFIX = "IDENTITY: "


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def extract_turn_prompt_context(messages: list[dict[str, Any]]) -> dict[str, Any]:
    context = {
        "role": "",
        "issue_id": "",
        "current_status": "",
        "required_read_paths": [],
        "required_write_paths": [],
        "required_statuses": [],
        "missing_required_read_paths": [],
    }
    decoder = json.JSONDecoder()

    for message in messages:
        content = str((message or {}).get("content") or "")
        if not context["role"]:
            for line in content.splitlines():
                if line.startswith(_IDENTITY_PREFIX):
                    context["role"] = line[len(_IDENTITY_PREFIX) :].strip().lower()
                    break

        if _EXECUTION_CONTEXT_MARKER in content:
            payload_text = content.split(_EXECUTION_CONTEXT_MARKER, 1)[1]
            try:
                parsed, _ = decoder.raw_decode(payload_text.lstrip())
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if not isinstance(parsed, dict):
                continue
            if not context["role"]:
                context["role"] = str(parsed.get("seat") or "").strip().lower()
            if not context["issue_id"]:
                context["issue_id"] = str(parsed.get("issue_id") or "").strip()
            if not context["current_status"]:
                context["current_status"] = str(parsed.get("current_status") or "").strip().lower()
            context["required_read_paths"] = [
                str(path).strip()
                for path in (parsed.get("required_read_paths") or [])
                if str(path).strip()
            ]
            context["required_write_paths"] = [
                str(path).strip()
                for path in (parsed.get("required_write_paths") or [])
                if str(path).strip()
            ]
            context["required_statuses"] = [
                str(status).strip()
                for status in (parsed.get("required_statuses") or [])
                if str(status).strip()
            ]
            context["missing_required_read_paths"] = [
                str(path).strip()
                for path in (parsed.get("missing_required_read_paths") or [])
                if str(path).strip()
            ]
            continue

        if not content.startswith(_TURN_PACKET_PREFIX):
            continue

        in_missing_inputs = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("Issue ") and not context["issue_id"]:
                issue_header = stripped[len("Issue ") :]
                context["issue_id"] = issue_header.split(":", 1)[0].strip()
                continue
            if stripped.startswith("- role: "):
                context["role"] = stripped[len("- role: ") :].strip().lower()
                in_missing_inputs = False
                continue
            if stripped.startswith("- current_status: "):
                context["current_status"] = stripped[len("- current_status: ") :].strip().lower()
                in_missing_inputs = False
                continue
            if stripped.startswith("- required read paths: "):
                context["required_read_paths"] = _split_csv(stripped[len("- required read paths: ") :])
                in_missing_inputs = False
                continue
            if stripped.startswith("- required write paths: "):
                context["required_write_paths"] = _split_csv(stripped[len("- required write paths: ") :])
                in_missing_inputs = False
                continue
            if stripped.startswith("- allowed statuses: "):
                context["required_statuses"] = _split_csv(stripped[len("- allowed statuses: ") :])
                in_missing_inputs = False
                continue
            if stripped == "Missing Inputs:":
                in_missing_inputs = True
                continue
            if in_missing_inputs and stripped.startswith("- "):
                missing_path = stripped[2:].strip()
                if missing_path:
                    context["missing_required_read_paths"].append(missing_path)
                continue
            if stripped.endswith(":") and not stripped.startswith("- "):
                in_missing_inputs = False

    return context
