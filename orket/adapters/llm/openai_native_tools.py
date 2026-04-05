from __future__ import annotations

from typing import Any, Mapping


def _dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value or '').strip()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def _scope_map(runtime_context: Mapping[str, Any]) -> Mapping[str, Any]:
    scope = runtime_context.get('verification_scope')
    return scope if isinstance(scope, Mapping) else {}


def _artifact_contract_map(runtime_context: Mapping[str, Any]) -> Mapping[str, Any]:
    artifact_contract = runtime_context.get('artifact_contract')
    return artifact_contract if isinstance(artifact_contract, Mapping) else {}


def _normalized_tools(runtime_context: Mapping[str, Any]) -> list[str]:
    required_action_tools = _dedupe(
        [str(tool).strip() for tool in (runtime_context.get('required_action_tools') or []) if str(tool).strip()]
    )
    if required_action_tools:
        return required_action_tools
    scope = _scope_map(runtime_context)
    return _dedupe(
        [str(tool).strip() for tool in (scope.get('declared_interfaces') or []) if str(tool).strip()]
    )


def _normalized_read_paths(runtime_context: Mapping[str, Any]) -> list[str]:
    required_read_paths = _dedupe(
        [str(path).strip() for path in (runtime_context.get('required_read_paths') or []) if str(path).strip()]
    )
    if required_read_paths:
        return required_read_paths
    artifact_contract = _artifact_contract_map(runtime_context)
    review_read_paths = _dedupe(
        [str(path).strip() for path in (artifact_contract.get('review_read_paths') or []) if str(path).strip()]
    )
    if review_read_paths:
        return review_read_paths
    contract_read_paths = _dedupe(
        [str(path).strip() for path in (artifact_contract.get('required_read_paths') or []) if str(path).strip()]
    )
    if contract_read_paths:
        return contract_read_paths
    scope = _scope_map(runtime_context)
    active_context = _dedupe(
        [str(path).strip() for path in (scope.get('active_context') or []) if str(path).strip()]
    )
    if active_context:
        return active_context
    return _dedupe(
        [str(path).strip() for path in (scope.get('provided_context') or []) if str(path).strip()]
    )


def _normalized_write_paths(runtime_context: Mapping[str, Any]) -> list[str]:
    required_write_paths = _dedupe(
        [str(path).strip() for path in (runtime_context.get('required_write_paths') or []) if str(path).strip()]
    )
    if required_write_paths:
        return required_write_paths
    artifact_contract = _artifact_contract_map(runtime_context)
    return _dedupe(
        [str(path).strip() for path in (artifact_contract.get('required_write_paths') or []) if str(path).strip()]
    )


def _explicit_native_tooling(runtime_context: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    tools = runtime_context.get('native_tools')
    if not isinstance(tools, list):
        return [], None, {}
    normalized_tools = [dict(tool) for tool in tools if isinstance(tool, Mapping)]
    if not normalized_tools:
        return [], None, {}
    raw_choice = runtime_context.get('native_tool_choice')
    tool_choice = str(raw_choice).strip() if raw_choice is not None else None
    if tool_choice == '':
        tool_choice = None
    raw_overrides = runtime_context.get('native_payload_overrides')
    payload_overrides = dict(raw_overrides) if isinstance(raw_overrides, Mapping) else {}
    return normalized_tools, tool_choice, payload_overrides


def build_openai_native_tooling(
    *,
    model: str,
    runtime_context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    explicit_tools, explicit_tool_choice, explicit_payload_overrides = _explicit_native_tooling(runtime_context)
    if explicit_tools:
        return explicit_tools, explicit_tool_choice, explicit_payload_overrides
    model_token = str(model or "").strip().lower()
    required_action_tools = _normalized_tools(runtime_context)
    required_read_paths = _normalized_read_paths(runtime_context)
    required_write_paths = _normalized_write_paths(runtime_context)
    if 'gemma' not in model_token:
        return [], None, {}
    tools: list[dict[str, Any]] = []
    if 'read_file' in required_action_tools and required_read_paths:
        tools.append(
            {
                'type': 'function',
                'function': {
                    'name': 'read_file',
                    'description': (
                        'Read exactly one required workspace-relative file for the current turn.'
                    ),
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'path': {
                                'type': 'string',
                                'enum': _dedupe(required_read_paths),
                                'description': 'Choose exactly one required read path.',
                            },
                        },
                        'required': ['path'],
                        'additionalProperties': False,
                    },
                },
            }
        )
    if 'write_file' in required_action_tools and required_write_paths:
        tools.append(
            {
                'type': 'function',
                'function': {
                    'name': 'write_file',
                    'description': (
                        'Write exactly one required workspace-relative file for the current turn.'
                    ),
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'path': {
                                'type': 'string',
                                'enum': _dedupe(required_write_paths),
                                'description': 'Choose exactly one required write path.',
                            },
                            'content': {
                                'type': 'string',
                                'description': 'Complete file content to write at the selected path.',
                            },
                        },
                        'required': ['path', 'content'],
                        'additionalProperties': False,
                    },
                },
            }
        )
    if not tools:
        return [], None, {}

    # Gemma 4 reliably takes the native tool path on bounded file-action turns, and
    # status updates can still be synthesized downstream when exactly one status is required.
    return (
        tools,
        'required',
        {'reasoning_effort': 'none'},
    )


__all__ = ['build_openai_native_tooling']
