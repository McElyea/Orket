"""Public profile admission contracts and native registry-file refusal."""
import json
from copy import deepcopy

import pytest

from orket.runtime.config.local_prompt_profiles import (
    E_LOCAL_PROMPT_PROFILE_NOT_FOUND,
    E_LOCAL_PROMPT_PROFILE_SCHEMA,
    LocalPromptProfileMatch,
    load_local_prompt_profile_registry_file,
    load_local_prompt_profile_registry_payload,
)
from tests.runtime.test_local_prompt_profiles import _base_profile, _payload


def _entry():
    return {"provider": "llama_cpp", "match": {"model_prefixes": ["demo"]},
            "profile": _base_profile("demo.v1")}


def _replace(mapping, dotted, value):
    parts = dotted.split(".")
    for part in parts[:-1]:
        mapping = mapping[part]
    mapping[parts[-1]] = value


@pytest.mark.contract
@pytest.mark.parametrize("field,value", [
    ("profile_id", " "), ("template_variant", ""), ("template_version", ""), ("history_policy", ""),
    ("template_family", "unsupported"), ("template_source", "unsupported"),
    ("system_prompt_mode", "unsupported"), ("context_budget_tokens", 0),
    ("allowed_roles", "user"), ("allowed_roles", [" "]),
    ("prefill_strategy", "unsupported"), ("tool_call_mode", "unsupported"),
    ("thinking_block_format", "unsupported"), ("intro_phrase_denylist", "intro"),
    ("stop_sequences_by_task_class", []), ("stop_sequences_by_task_class", {"unsupported": []}),
    ("stop_sequences_by_task_class", {}), ("sampling_bundles", []),
    ("sampling_bundles", {"unsupported": {}}),
    ("tool_contract.tool_manifest_injection", "unsupported"),
    ("tool_contract.tool_call_schema", " "), ("tool_contract.tool_result_role", "system"),
    ("sampling_bundles.strict_json.max_output_tokens", 0),
    ("sampling_bundles.strict_json.top_k", 0),
    ("sampling_bundles.strict_json.seed_policy", "unsupported"),
    ("sampling_bundles.strict_json.seed_value", None),
    ("sampling_bundles.concise_text.seed_value", 7),
])
def test_invalid_profile_constraints_refuse_without_rewriting_caller_input(field, value):
    entry = _entry()
    _replace(entry["profile"], field, value)
    payload = _payload([entry])
    before = deepcopy(payload)
    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_SCHEMA) as error:
        load_local_prompt_profile_registry_payload(payload)
    assert "profiles.0.profile" in str(error.value)
    assert payload == before


@pytest.mark.contract
@pytest.mark.parametrize("changes", [
    {"provider": "unsupported"},
    {"match": {"model_equals": "demo"}},
    {"match": {"model_prefixes": "demo"}},
    {"match": {"model_contains": "demo"}},
    {"match": {"model_prefixes": None}},
])
def test_invalid_registry_entry_cannot_select_a_profile(changes):
    entry = {**_entry(), **changes}
    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_SCHEMA):
        load_local_prompt_profile_registry_payload(_payload([entry]))


@pytest.mark.contract
def test_schema_version_and_duplicate_profile_identity_are_not_accepted():
    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_SCHEMA):
        load_local_prompt_profile_registry_payload({"schema_version": "foreign/v1", "profiles": []})
    entries = [_entry(), _entry()]
    entries[1]["match"] = {"model_equals": ["other-model"]}
    with pytest.raises(ValueError, match="duplicate profile_id values detected: demo.v1"):
        load_local_prompt_profile_registry_payload(_payload(entries))


@pytest.mark.contract
def test_profile_normalization_and_explicit_override_preserve_selection_truth():
    entry = _entry()
    entry["provider"] = " LLAMA_CPP "
    entry["match"] = {"model_equals": None, "model_prefixes": [" Demo ", "demo", " "]}
    entry["profile"].update(intro_phrase_denylist=None, allowed_roles=[" User ", "user", " "],
                            template_family="OPENAI-MESSAGES")
    original = deepcopy(entry)
    registry = load_local_prompt_profile_registry_payload(_payload([entry]))
    selected = registry.resolve_profile(provider="llama_cpp", model=" Demo-model ")
    assert selected.resolution_path == "matched" and selected.model == "demo-model"
    assert selected.profile.allowed_roles == ["user"] and selected.profile.intro_phrase_denylist == []
    assert selected.profile.template_family == "openai_messages"
    assert registry.profiles[0].match.model_equals == []
    assert registry.profiles[0].match.model_prefixes == ["demo"]
    override = registry.resolve_profile(provider="llama_cpp", model="unmatched", override_profile_id="demo.v1")
    assert override.resolution_path == "override" and override.profile.profile_id == "demo.v1"
    assert entry == original
    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_NOT_FOUND):
        registry.resolve_profile(provider="llama_cpp", model=" ")


@pytest.mark.contract
def test_public_match_value_distinguishes_empty_prefix_and_fragment_models():
    match = LocalPromptProfileMatch(model_prefixes=["demo"], model_contains=["special"])
    assert not match.matches("")
    assert match.matches("DEMO-model") and match.matches("other-special-model")
    assert not match.matches("unmatched")


@pytest.mark.integration
def test_native_invalid_profile_file_keeps_original_bytes(tmp_path):
    path = tmp_path / "profiles.json"
    entry = _entry()
    entry["profile"]["sampling_bundles"]["strict_json"]["max_output_tokens"] = 0
    original = json.dumps(_payload([entry]), indent=3).encode()
    path.write_bytes(original)
    with pytest.raises(ValueError, match=E_LOCAL_PROMPT_PROFILE_SCHEMA):
        load_local_prompt_profile_registry_file(path)
    assert path.read_bytes() == original and list(tmp_path.iterdir()) == [path]
