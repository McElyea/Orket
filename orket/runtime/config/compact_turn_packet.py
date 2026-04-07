from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PACKET_VERSION = 'compact_turn_packet_v1'
_ISSUE_PREFIX = 'Issue '
_ISSUE_BRIEF_PREFIX = 'Issue Brief:\n'
_ARTIFACT_SEMANTIC_PREFIX = 'Artifact Semantic Contract:\n'
_ARTIFACT_EXACT_SHAPE_PREFIX = 'Artifact Exact-Shape Hints:\n'
_SCENARIO_TRUTH_PREFIX = 'Scenario Truth Contract:\n'
_RUNTIME_VERIFIER_PREFIX = 'Runtime Verifier Contract:\n'
_PROTOCOL_RESPONSE_PREFIX = 'Protocol Response Contract:\n'
_TURN_SUCCESS_PREFIX = 'Turn Success Contract:\n'
_WRITE_PATH_PREFIX = 'Write Path Contract:\n'
_READ_PATH_PREFIX = 'Read Path Contract:\n'
_COMMENT_CONTRACT_PREFIX = 'Comment Contract:\n'
_ARCHITECTURE_CONTRACT_PREFIX = 'Architecture Decision Contract:\n'
_GUARD_DECISION_PREFIX = 'Guard Decision Contract:\n'
_GUARD_REJECTION_PREFIX = 'Guard Rejection Contract:\n'
_ODR_PREBUILD_PREFIX = 'ODR Prebuild Summary JSON:\n'
_ODR_REFINED_REQUIREMENT_PREFIX = 'ODR Refined Requirement:\n'
_PRELOADED_READ_CONTEXT_PREFIX = 'Preloaded Read Context:\n'
_CORRECTIVE_PREFIX = 'Corrective instruction:'
_MISSING_INPUT_PREFIX = 'Missing Input Preflight Notice:\n'
_PRIOR_TRANSCRIPT_PREFIX = 'Prior Transcript JSON:\n'
_PROJECT_CONTEXT_MARKER = 'PROJECT CONTEXT (PAST DECISIONS):\n'
_PATCH_MARKER = 'PATCH:\n'


@dataclass(frozen=True)
class CompactTurnPacketResult:
    messages: list[dict[str, str]]
    applied: bool
    packet_version: str
    source_message_count: int
    compacted_message_count: int


def _normalized_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        token = str(item or '').strip()
        if token:
            items.append(token)
    return items


def _find_message_content(messages: list[dict[str, str]], prefix: str) -> str:
    for message in messages:
        content = str((message or {}).get('content') or '')
        if content.startswith(prefix):
            return content
    return ''


def _message_body(content: str, prefix: str) -> str:
    if not content.startswith(prefix):
        return ''
    return content[len(prefix) :].strip()


def _renamed_section(content: str, prefix: str, title: str) -> str:
    body = _message_body(content, prefix)
    if not body:
        return ''
    return f'{title}:\n{body}'


def _bullet_lines(content: str, prefix: str) -> list[str]:
    body = _message_body(content, prefix)
    if not body:
        return []
    return [line.strip() for line in body.splitlines() if line.strip()]


def _append_unique_lines(target: list[str], candidates: list[str]) -> None:
    seen = set(target)
    for candidate in candidates:
        line = str(candidate or '').strip()
        if not line or line in seen:
            continue
        target.append(line)
        seen.add(line)


def _extract_system_tail(system_content: str, marker: str, title: str) -> str:
    if not system_content:
        return ''
    index = system_content.find(marker)
    if index < 0:
        return ''
    tail = system_content[index + len(marker) :].strip()
    if not tail:
        return ''
    return f'{title}:\n{tail}'


def is_compact_turn_packet(messages: list[dict[str, str]]) -> bool:
    if len(messages) != 2:
        return False
    system_content = str((messages[0] or {}).get('content') or '')
    user_content = str((messages[1] or {}).get('content') or '')
    return 'MODE: compact governed tool turn' in system_content and user_content.startswith('TURN PACKET:\n')


def _render_compact_system_prompt(runtime_context: dict[str, Any]) -> str:
    role_name = str(runtime_context.get('role') or 'worker').strip() or 'worker'
    required_statuses = _normalized_list(runtime_context.get('required_statuses'))
    lines = [
        f'IDENTITY: {role_name}',
        'MODE: compact governed tool turn',
        'RULES:',
        '- Return exactly one JSON object.',
        '- Response envelope: {"content":"","tool_calls":[...]}.',
        '- content must be empty when tool_calls are present.',
        '- No prose, no markdown fences, no labels.',
        '- Use only tools, paths, statuses, and facts from the TURN PACKET.',
        '- Call every required tool in the same response.',
    ]
    if required_statuses:
        lines.append('- Emit update_issue_status using only the allowed statuses from the TURN PACKET.')
    lines.append('GUARDRAIL: Output only the JSON object.')
    return '\n'.join(lines)


def _render_dependency_summary(runtime_context: dict[str, Any]) -> str:
    dependency_context = runtime_context.get('dependency_context')
    if not isinstance(dependency_context, dict) or not dependency_context:
        return ''
    lines = ['Dependency Context:']
    dependency_count = int(dependency_context.get('dependency_count') or 0)
    lines.append(f'- dependency_count: {dependency_count}')
    depends_on = _normalized_list(dependency_context.get('depends_on'))
    if depends_on:
        lines.append('- depends_on: ' + ', '.join(depends_on))
    unresolved = _normalized_list(dependency_context.get('unresolved_dependencies'))
    if unresolved:
        lines.append('- unresolved_dependencies: ' + ', '.join(unresolved))
    dependency_statuses = dependency_context.get('dependency_statuses')
    if isinstance(dependency_statuses, dict) and dependency_statuses:
        rendered = ', '.join(
            f'{str(key).strip()}={str(value).strip()}'
            for key, value in dependency_statuses.items()
            if str(key).strip()
        )
        if rendered:
            lines.append('- dependency_statuses: ' + rendered)
    return '\n'.join(lines)


def _render_artifact_checks(runtime_context: dict[str, Any]) -> str:
    artifact_contract = runtime_context.get('artifact_contract')
    artifact_contract = artifact_contract if isinstance(artifact_contract, dict) else {}
    semantic_checks = artifact_contract.get('semantic_checks')
    if not isinstance(semantic_checks, list) or not semantic_checks:
        return ''
    lines = ['Artifact Checks:']
    for raw_check in semantic_checks:
        if not isinstance(raw_check, dict):
            continue
        path = str(raw_check.get('path') or '').strip()
        label = str(raw_check.get('label') or '').strip()
        header = path or 'artifact'
        if label:
            header = f'{header} ({label})' if path else label
        lines.append(f'- {header}')
        must_contain = _normalized_list(raw_check.get('must_contain'))
        if must_contain:
            lines.append('  must contain: ' + ', '.join(must_contain))
        must_not_contain = _normalized_list(raw_check.get('must_not_contain'))
        if must_not_contain:
            lines.append('  must not contain: ' + ', '.join(must_not_contain))
    return '\n'.join(lines) if len(lines) > 1 else ''


def _render_runtime_verifier(runtime_context: dict[str, Any]) -> str:
    runtime_verifier_ok = runtime_context.get('runtime_verifier_ok')
    runtime_verifier_contract = runtime_context.get('runtime_verifier_contract')
    lines: list[str] = []
    if runtime_verifier_ok is True:
        lines.append('- runtime verifier: passed')
    elif runtime_verifier_ok is False:
        lines.append('- runtime verifier: failed')
    if not isinstance(runtime_verifier_contract, dict) or not runtime_verifier_contract:
        return 'Runtime Verification:\n' + '\n'.join(lines) if lines else ''
    commands = runtime_verifier_contract.get('commands')
    if isinstance(commands, list) and commands:
        lines.append('- verifier commands:')
        for raw_command in commands:
            cwd = '.'
            argv = raw_command
            if isinstance(raw_command, dict):
                cwd = str(raw_command.get('cwd') or '.').strip() or '.'
                argv = raw_command.get('argv')
            if not isinstance(argv, list):
                continue
            rendered = ' '.join(str(token).strip() for token in argv if str(token).strip())
            if rendered:
                lines.append(f'  - cwd={cwd}: {rendered}')
    if bool(runtime_verifier_contract.get('expect_json_stdout', False)):
        lines.append('- stdout must be valid JSON')
    json_assertions = runtime_verifier_contract.get('json_assertions')
    if isinstance(json_assertions, list) and json_assertions:
        lines.append('- stdout assertions:')
        for assertion in json_assertions:
            if not isinstance(assertion, dict):
                continue
            path = str(assertion.get('path') or '').strip()
            op = str(assertion.get('op') or '').strip()
            if not path or not op:
                continue
            lines.append(f"  - {path} {op} {assertion.get('value')!r}")
    return 'Runtime Verification:\n' + '\n'.join(lines) if lines else ''


def _render_scenario_constraints(runtime_context: dict[str, Any]) -> str:
    scenario_truth = runtime_context.get('scenario_truth')
    if not isinstance(scenario_truth, dict) or not scenario_truth:
        return ''
    blocked_issue_policy = scenario_truth.get('blocked_issue_policy')
    blocked_issue_policy = blocked_issue_policy if isinstance(blocked_issue_policy, dict) else {}
    lines = ['Scenario Constraints:']
    scenario_id = str(scenario_truth.get('scenario_id') or '').strip()
    if scenario_id:
        lines.append(f'- scenario_id: {scenario_id}')
    expected_terminal_status = str(scenario_truth.get('expected_terminal_status') or '').strip()
    if expected_terminal_status:
        lines.append(f'- expected_terminal_status: {expected_terminal_status}')
    if bool(blocked_issue_policy.get('blocked_implies_run_failure')):
        lines.append('- blocked implies run failure')
    allowed_issue_ids = _normalized_list(blocked_issue_policy.get('allowed_issue_ids'))
    if allowed_issue_ids:
        lines.append('- blocked allowed only for: ' + ', '.join(allowed_issue_ids))
    return '\n'.join(lines) if len(lines) > 1 else ''


def _render_comment_contract(runtime_context: dict[str, Any]) -> str:
    required_comment_contains = _normalized_list(runtime_context.get('required_comment_contains'))
    required_comment_min_length = runtime_context.get('required_comment_min_length')
    if not required_comment_contains and not required_comment_min_length:
        return ''
    lines = ['Review Comment Rules:']
    if required_comment_min_length:
        lines.append(f'- minimum comment length: {int(required_comment_min_length)}')
    if required_comment_contains:
        lines.append('- required comment tokens: ' + ', '.join(required_comment_contains))
    return '\n'.join(lines)


def _render_architecture_contract(runtime_context: dict[str, Any]) -> str:
    if not bool(runtime_context.get('architecture_decision_required')):
        return ''
    decision_path = str(runtime_context.get('architecture_decision_path') or 'agent_output/design.txt').strip()
    allowed_patterns = _normalized_list(runtime_context.get('architecture_allowed_patterns')) or ['monolith', 'microservices']
    lines = [
        'Architecture Contract:',
        f'- write architecture decision JSON to: {decision_path}',
        '- recommendation must be one of: ' + ', '.join(allowed_patterns),
        '- include keys: recommendation, confidence, evidence',
    ]
    forced_pattern = str(runtime_context.get('architecture_forced_pattern') or '').strip()
    if forced_pattern:
        lines.append(f'- recommendation must equal: {forced_pattern}')
    forced_frontend = str(runtime_context.get('frontend_framework_forced') or '').strip()
    if forced_frontend:
        lines.append(f'- frontend_framework must equal: {forced_frontend}')
    return '\n'.join(lines)


def _runtime_verifier_prompt_enabled(runtime_context: dict[str, Any]) -> bool:
    artifact_contract = runtime_context.get('artifact_contract')
    artifact_contract = artifact_contract if isinstance(artifact_contract, dict) else {}
    profile_traits = runtime_context.get('profile_traits')
    profile_traits = profile_traits if isinstance(profile_traits, dict) else {}
    runtime_verifier_allowed = bool(profile_traits.get('runtime_verifier_allowed', True))
    profile_intent = str(profile_traits.get('intent') or '').strip().lower()
    runtime_verifier_contract = runtime_context.get('runtime_verifier_contract')
    runtime_verifier_contract = runtime_verifier_contract if isinstance(runtime_verifier_contract, dict) else {}
    artifact_kind = str(artifact_contract.get('kind') or '').strip().lower()
    return runtime_verifier_allowed or (
        bool(runtime_verifier_contract)
        and profile_intent in {'write_artifact', 'build_app'}
        and artifact_kind not in {'', 'none'}
    )


def _render_turn_packet(messages: list[dict[str, str]], runtime_context: dict[str, Any]) -> str:
    issue_header = _find_message_content(messages, _ISSUE_PREFIX)
    issue_brief = _find_message_content(messages, _ISSUE_BRIEF_PREFIX)
    artifact_semantic = _find_message_content(messages, _ARTIFACT_SEMANTIC_PREFIX)
    artifact_exact_shape = _find_message_content(messages, _ARTIFACT_EXACT_SHAPE_PREFIX)
    scenario_truth = _find_message_content(messages, _SCENARIO_TRUTH_PREFIX)
    runtime_verifier = _find_message_content(messages, _RUNTIME_VERIFIER_PREFIX)
    turn_success = _find_message_content(messages, _TURN_SUCCESS_PREFIX)
    write_path_contract = _find_message_content(messages, _WRITE_PATH_PREFIX)
    read_path_contract = _find_message_content(messages, _READ_PATH_PREFIX)
    comment_contract = _find_message_content(messages, _COMMENT_CONTRACT_PREFIX)
    architecture_contract = _find_message_content(messages, _ARCHITECTURE_CONTRACT_PREFIX)
    guard_decision = _find_message_content(messages, _GUARD_DECISION_PREFIX)
    guard_rejection = _find_message_content(messages, _GUARD_REJECTION_PREFIX)
    odr_prebuild = _find_message_content(messages, _ODR_PREBUILD_PREFIX)
    odr_requirement = _find_message_content(messages, _ODR_REFINED_REQUIREMENT_PREFIX)
    preloaded_read_context = _find_message_content(messages, _PRELOADED_READ_CONTEXT_PREFIX)
    missing_input_notice = _find_message_content(messages, _MISSING_INPUT_PREFIX)
    prior_transcript = _find_message_content(messages, _PRIOR_TRANSCRIPT_PREFIX)
    corrective = _find_message_content(messages, _CORRECTIVE_PREFIX)
    system_content = str((messages[0] or {}).get('content') or '') if messages else ''

    artifact_contract = runtime_context.get('artifact_contract')
    artifact_contract = artifact_contract if isinstance(artifact_contract, dict) else {}
    required_tools = _normalized_list(runtime_context.get('required_action_tools'))
    required_statuses = _normalized_list(runtime_context.get('required_statuses'))
    required_read_paths = _normalized_list(runtime_context.get('required_read_paths'))
    required_write_paths = _normalized_list(runtime_context.get('required_write_paths'))

    header_lines = ['TURN PACKET:']
    if issue_header:
        header_lines.append(issue_header)
    header_lines.extend(
        [
            f"- role: {str(runtime_context.get('role') or '').strip() or 'unknown'}",
            f"- current_status: {str(runtime_context.get('current_status') or '').strip() or 'unknown'}",
            f"- stage_gate_mode: {str(runtime_context.get('stage_gate_mode') or '').strip() or 'none'}",
        ]
    )
    execution_profile = str(runtime_context.get('execution_profile') or '').strip()
    if execution_profile:
        header_lines.append(f'- execution_profile: {execution_profile}')
    if required_tools:
        header_lines.append('- required tools: ' + ', '.join(required_tools))
    if required_statuses:
        header_lines.append('- allowed statuses: ' + ', '.join(required_statuses))
    if required_read_paths:
        header_lines.append('- required read paths: ' + ', '.join(required_read_paths))
    if required_write_paths:
        header_lines.append('- required write paths: ' + ', '.join(required_write_paths))
    primary_output = str(artifact_contract.get('primary_output') or '').strip()
    if primary_output:
        header_lines.append(f'- primary output: {primary_output}')
    if runtime_context.get('runtime_verifier_ok') is True and required_statuses == ['done']:
        header_lines.append('- runtime verifier passed; blocked is not allowed on this turn')
    header_lines.append('- response shape: {"content":"","tool_calls":[...]}')
    _append_unique_lines(
        header_lines,
        [
            '- You must include all required tool calls in this same response.'
            if line.startswith('- You must include all required tool calls in this same response.')
            else '- A response containing only get_issue_context/add_issue_comment is invalid.'
            if line.startswith('- A response containing only get_issue_context/add_issue_comment is invalid.')
            else '- If you choose status=blocked, include wait_reason: resource|dependency|review|input|system.'
            if line.startswith('- If you choose status=blocked, include wait_reason:') and 'blocked' in required_statuses
            else '- Empty or placeholder content for required write_file paths is invalid.'
            if line.startswith('- Empty or placeholder content for required write_file paths is invalid.')
            else '- When writing Python source through write_file, prefer single-quoted literals to keep the JSON payload valid.'
            if line.startswith('- When writing Python source through write_file, prefer single-quoted literals')
            else ''
            for line in _bullet_lines(turn_success, _TURN_SUCCESS_PREFIX)
        ],
    )
    _append_unique_lines(
        header_lines,
        [
            '- Use workspace-relative write paths exactly as listed.'
            if line.startswith('- Use workspace-relative paths exactly as listed.')
            else ''
            for line in _bullet_lines(write_path_contract, _WRITE_PATH_PREFIX)
        ],
    )
    _append_unique_lines(
        header_lines,
        [
            '- Do not use placeholder or absolute paths outside the workspace.'
            if line.startswith('- Do not use placeholder or absolute paths outside the workspace.')
            else ''
            for line in _bullet_lines(read_path_contract, _READ_PATH_PREFIX)
        ],
    )

    sections = ['\n'.join(header_lines)]
    for candidate in (
        issue_brief,
        _render_dependency_summary(runtime_context),
        _renamed_section(scenario_truth, _SCENARIO_TRUTH_PREFIX, 'Scenario Constraints')
        or _render_scenario_constraints(runtime_context),
        _renamed_section(artifact_semantic, _ARTIFACT_SEMANTIC_PREFIX, 'Artifact Checks')
        or _render_artifact_checks(runtime_context),
        _renamed_section(artifact_exact_shape, _ARTIFACT_EXACT_SHAPE_PREFIX, 'Exact Shape Hints'),
        _renamed_section(runtime_verifier, _RUNTIME_VERIFIER_PREFIX, 'Runtime Verification')
        or (_render_runtime_verifier(runtime_context) if _runtime_verifier_prompt_enabled(runtime_context) else ''),
        _renamed_section(comment_contract, _COMMENT_CONTRACT_PREFIX, 'Review Comment Rules')
        or _render_comment_contract(runtime_context),
        _renamed_section(architecture_contract, _ARCHITECTURE_CONTRACT_PREFIX, 'Architecture Contract')
        or _render_architecture_contract(runtime_context),
        _renamed_section(guard_decision, _GUARD_DECISION_PREFIX, 'Guard Review Rules'),
        _renamed_section(guard_rejection, _GUARD_REJECTION_PREFIX, 'Guard Review Rules'),
        _renamed_section(odr_prebuild, _ODR_PREBUILD_PREFIX, 'ODR Summary'),
        _renamed_section(odr_requirement, _ODR_REFINED_REQUIREMENT_PREFIX, 'ODR Requirement'),
        _extract_system_tail(system_content, _PROJECT_CONTEXT_MARKER, 'Project Context'),
        _extract_system_tail(system_content, _PATCH_MARKER, 'Patch'),
        preloaded_read_context,
        _renamed_section(missing_input_notice, _MISSING_INPUT_PREFIX, 'Missing Inputs'),
        prior_transcript,
        corrective,
    ):
        if candidate:
            sections.append(candidate)
    return '\n\n'.join(section for section in sections if section.strip())


def compact_turn_messages(
    messages: list[dict[str, str]],
    *,
    runtime_context: dict[str, Any],
) -> CompactTurnPacketResult:
    if is_compact_turn_packet(messages):
        return CompactTurnPacketResult(
            messages=list(messages),
            applied=False,
            packet_version=PACKET_VERSION,
            source_message_count=len(messages),
            compacted_message_count=len(messages),
        )
    compacted = [
        {'role': 'system', 'content': _render_compact_system_prompt(runtime_context)},
        {'role': 'user', 'content': _render_turn_packet(messages, runtime_context)},
    ]
    return CompactTurnPacketResult(
        messages=compacted,
        applied=True,
        packet_version=PACKET_VERSION,
        source_message_count=len(messages),
        compacted_message_count=len(compacted),
    )


__all__ = [
    'PACKET_VERSION',
    'CompactTurnPacketResult',
    'compact_turn_messages',
    'is_compact_turn_packet',
]
