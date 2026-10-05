"""Tool arguments are data; only transport-level fences violate the envelope."""

import json

import pytest

from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.core.domain.execution import ExecutionTurn
from tests.helpers.turn_artifacts import artifact_test_utc_now

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("protocol", [False, True])
@pytest.mark.parametrize("text", ["```python\nprint('ok')\n```", 'A "quoted" \\ path then ```text```'])
def test_markdown_in_json_tool_arguments_is_payload(protocol, text):
    validator = ContractValidator(ResponseParser(utc_now=artifact_test_utc_now))
    payload = json.dumps({"tool": "write_file", "args": {"path": "README.md", "content": text}})
    turn = ExecutionTurn(timestamp=None, role="coder", issue_id="README", content=payload)
    result = validator.local_prompt_anti_meta_diagnostics(
        turn, {"local_prompt_task_class": "tool_call", "protocol_governed_enabled": protocol}
    )
    assert result["violations"] == []


@pytest.mark.parametrize("wrapper", ["```json\n{}\n```", "{}\n```", "```\n{}"])
def test_markdown_outside_json_remains_rejected(wrapper):
    validator = ContractValidator(ResponseParser(utc_now=artifact_test_utc_now))
    payload = json.dumps({"tool": "write_file", "args": {"path": "README.md", "content": "```"}})
    turn = ExecutionTurn(timestamp=None, role="coder", issue_id="README", content=wrapper.format(payload))
    result = validator.local_prompt_anti_meta_diagnostics(turn, {"local_prompt_task_class": "tool_call"})
    assert any(item["rule_id"] == "LOCAL_PROMPT.MARKDOWN_FENCE" for item in result["violations"])
