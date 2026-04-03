from __future__ import annotations

from typing import Any

from orket.domain.execution import ExecutionTurn


def artifact_semantic_contract_diagnostics(
    turn: ExecutionTurn,
    context: dict[str, Any],
) -> dict[str, Any]:
    required_tools = {
        str(tool).strip() for tool in (context.get("required_action_tools") or []) if str(tool).strip()
    }
    if "write_file" not in required_tools:
        return {"ok": True, "violations": []}

    artifact_contract = context.get("artifact_contract")
    if not isinstance(artifact_contract, dict):
        return {"ok": True, "violations": []}

    raw_checks = artifact_contract.get("semantic_checks")
    if not isinstance(raw_checks, list):
        return {"ok": True, "violations": []}

    written_content_by_path: dict[str, str] = {}
    for call in turn.tool_calls or []:
        if call.tool != "write_file":
            continue
        path = str((call.args or {}).get("path") or "").strip()
        content = (call.args or {}).get("content")
        if path and isinstance(content, str):
            written_content_by_path[path] = content

    violations: list[dict[str, Any]] = []
    for raw_check in raw_checks:
        if not isinstance(raw_check, dict):
            continue
        path = str(raw_check.get("path") or "").strip()
        if not path:
            continue
        content = written_content_by_path.get(path)
        if content is None:
            continue

        label = str(raw_check.get("label") or path).strip() or path
        must_contain = [
            str(token).strip()
            for token in (raw_check.get("must_contain") or [])
            if str(token).strip()
        ]
        must_not_contain = [
            str(token).strip()
            for token in (raw_check.get("must_not_contain") or [])
            if str(token).strip()
        ]

        missing_tokens = [token for token in must_contain if token not in content]
        forbidden_tokens = [token for token in must_not_contain if token in content]
        if not missing_tokens and not forbidden_tokens:
            continue

        violations.append(
            {
                "path": path,
                "label": label,
                "missing_tokens": missing_tokens,
                "forbidden_tokens": forbidden_tokens,
            }
        )

    return {"ok": not violations, "violations": violations}
