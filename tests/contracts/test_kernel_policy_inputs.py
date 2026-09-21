"""Contract: independent published outcomes, immutable input and trusted-input admission."""
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from orket.kernel.v1 import api
from orket.kernel.v1.nervous_system_policy import NervousSystemPolicyInputs, capture_nervous_system_policy_inputs
from orket.kernel.v1.nervous_system_runtime_state import list_events_for_session, reset_runtime_state_for_tests

pytestmark = pytest.mark.contract
REFERENCE = json.loads((Path(__file__).parents[1] / 'fixtures/kernel_policy_inputs_v055.json').read_text(encoding='utf-8'))


@pytest.fixture(autouse=True)
def isolated_kernel_ledger():
    reset_runtime_state_for_tests()
    yield
    reset_runtime_state_for_tests()


@pytest.mark.parametrize('case', REFERENCE['cases'], ids=lambda case: case['id'])
def test_published_admission_outcomes(case):
    selected = capture_nervous_system_policy_inputs(environment=case['environment'])
    expected = case['observed']
    if 'error' in expected:
        with pytest.raises({'ValueError': ValueError, 'TypeError': TypeError}[expected['error']]) as error:
            api.admit_proposal(case['request'], policy_inputs=selected)
        assert str(error.value) == expected['message']
        assert list_events_for_session('parity-session') == []
    else:
        result = api.admit_proposal(case['request'], policy_inputs=selected)
        assert {key: result[key] for key in expected['result']} == expected['result']


@pytest.mark.parametrize('field', ['enabled', 'allow_pre_resolved_flags', 'use_profile_resolver'])
@pytest.mark.parametrize('invalid', [None, 0, 1, 'true', 'false', [], {}])
def test_policy_fields_require_plain_booleans(field, invalid):
    values = dict(enabled=True, allow_pre_resolved_flags=False, use_profile_resolver=True)
    values[field] = invalid
    with pytest.raises(TypeError, match='E_KERNEL_POLICY_BOOLEAN_REQUIRED'):
        NervousSystemPolicyInputs(**values)


def test_empty_environment_is_authoritative_and_policy_is_immutable(monkeypatch):
    monkeypatch.setenv('ORKET_ENABLE_NERVOUS_SYSTEM', 'true')
    monkeypatch.setenv('ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS', 'true')
    monkeypatch.setenv('ORKET_USE_TOOL_PROFILE_RESOLVER', 'false')
    selected = capture_nervous_system_policy_inputs(environment={})
    assert selected == NervousSystemPolicyInputs(False, False, True)
    with pytest.raises(FrozenInstanceError):
        selected.enabled = True


def test_request_fields_cannot_override_disabled_operator_policy(monkeypatch):
    monkeypatch.setenv('ORKET_ENABLE_NERVOUS_SYSTEM', 'false')
    request = {'contract_version': 'kernel_api/v1', 'session_id': 'untrusted', 'trace_id': 'untrusted',
        'policy_inputs': {'enabled': True, 'allow_pre_resolved_flags': True, 'use_profile_resolver': False},
        'proposal': {'proposal_type': 'action.tool_call', 'payload': {'tool_name': 'local.echo'}}}
    with pytest.raises(ValueError, match='disabled'):
        api.admit_proposal(request)
    assert list_events_for_session('untrusted') == []


@pytest.mark.parametrize('invalid', [{}, True, 'enabled'])
def test_explicit_policy_requires_typed_input(invalid):
    with pytest.raises(TypeError, match='E_KERNEL_POLICY_INPUT_REQUIRED'):
        api.admit_proposal({}, policy_inputs=invalid)
