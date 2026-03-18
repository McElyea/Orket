from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

E_LOCAL_PROMPT_PROFILE_SCHEMA = "E_LOCAL_PROMPT_PROFILE_SCHEMA"
E_LOCAL_PROMPT_PROFILE_LOAD = "E_LOCAL_PROMPT_PROFILE_LOAD"
E_LOCAL_PROMPT_PROFILE_NOT_FOUND = "E_LOCAL_PROMPT_PROFILE_NOT_FOUND"
E_LOCAL_PROMPT_PROFILE_AMBIGUOUS = "E_LOCAL_PROMPT_PROFILE_AMBIGUOUS"
E_LOCAL_PROMPT_PROFILE_OVERRIDE_MISSING = "E_LOCAL_PROMPT_PROFILE_OVERRIDE_MISSING"
E_LOCAL_PROMPT_PROFILE_FALLBACK_MISSING = "E_LOCAL_PROMPT_PROFILE_FALLBACK_MISSING"
DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH = Path("model/core/contracts/local_prompt_profiles.json")
_TASK_CLASSES = ("strict_json", "tool_call", "concise_text", "reasoning")


def normalize_provider_for_local_prompt_profile(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"openai_compat", "lmstudio"}:
        return "openai_compat"
    return "ollama"


def _normalize_token(value: Any) -> str:
    return str(value or "").strip()


def _normalize_token_list(values: list[Any], *, lowercase: bool = True) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for raw in values:
        token = _normalize_token(raw)
        if lowercase:
            token = token.lower()
        if not token or token in seen:
            continue
        seen.add(token)
        rows.append(token)
    return rows


class LocalPromptToolContract(BaseModel):
    tool_manifest_injection: str
    tool_call_schema: str
    tool_result_role: str

    @field_validator("tool_manifest_injection", mode="before")
    @classmethod
    def _validate_manifest_injection(cls, value: Any) -> str:
        token = _normalize_token(value).lower().replace("-", "_")
        aliases = {
            "system": "system",
            "user": "user",
            "none": "none",
        }
        resolved = aliases.get(token)
        if not resolved:
            raise ValueError("tool_manifest_injection must be one of: system,user,none")
        return resolved

    @field_validator("tool_call_schema", mode="before")
    @classmethod
    def _validate_schema(cls, value: Any) -> str:
        token = _normalize_token(value)
        if not token:
            raise ValueError("tool_call_schema is required")
        return token

    @field_validator("tool_result_role", mode="before")
    @classmethod
    def _validate_tool_result_role(cls, value: Any) -> str:
        token = _normalize_token(value).lower()
        aliases = {"tool": "tool", "user": "user", "assistant": "assistant"}
        resolved = aliases.get(token)
        if not resolved:
            raise ValueError("tool_result_role must be one of: tool,user,assistant")
        return resolved


class LocalPromptSamplingBundle(BaseModel):
    temperature: float
    top_p: float
    top_k: int
    repeat_penalty: float
    max_output_tokens: int
    seed_policy: str
    seed_value: int | None = None

    @field_validator("max_output_tokens")
    @classmethod
    def _validate_max_output_tokens(cls, value: int) -> int:
        if int(value) <= 0:
            raise ValueError("max_output_tokens must be > 0")
        return int(value)

    @field_validator("top_k")
    @classmethod
    def _validate_top_k(cls, value: int) -> int:
        if int(value) <= 0:
            raise ValueError("top_k must be > 0")
        return int(value)

    @field_validator("seed_policy", mode="before")
    @classmethod
    def _validate_seed_policy(cls, value: Any) -> str:
        token = _normalize_token(value).lower().replace("-", "_")
        aliases = {
            "fixed": "fixed",
            "none": "none",
            "provider_default": "provider_default",
        }
        resolved = aliases.get(token)
        if not resolved:
            raise ValueError("seed_policy must be one of: fixed,none,provider_default")
        return resolved

    @model_validator(mode="after")
    def _validate_seed_value(self) -> "LocalPromptSamplingBundle":
        if self.seed_policy == "fixed" and self.seed_value is None:
            raise ValueError("seed_value is required when seed_policy=fixed")
        if self.seed_policy != "fixed" and self.seed_value is not None:
            raise ValueError("seed_value is only allowed when seed_policy=fixed")
        return self


class LocalPromptProfile(BaseModel):
    profile_id: str
    template_family: str
    template_variant: str
    template_source: str
    template_version: str
    allowed_roles: list[str]
    system_prompt_mode: str
    context_budget_tokens: int
    history_policy: str
    stop_sequences_by_task_class: dict[str, list[str]]
    supports_assistant_prefill: bool
    prefill_strategy: str
    tool_call_mode: str
    tool_contract: LocalPromptToolContract
    allows_thinking_blocks: bool
    thinking_block_format: str
    intro_phrase_denylist: list[str] = Field(default_factory=list)
    sampling_bundles: dict[str, LocalPromptSamplingBundle]

    @field_validator("profile_id", "template_variant", "template_version", "history_policy", mode="before")
    @classmethod
    def _validate_required_text(cls, value: Any) -> str:
        token = _normalize_token(value)
        if not token:
            raise ValueError("field is required")
        return token

    @field_validator("template_family", mode="before")
    @classmethod
    def _validate_template_family(cls, value: Any) -> str:
        token = _normalize_token(value).lower().replace("-", "_")
        allowed = {"openai_messages", "chatml", "inst", "custom"}
        if token not in allowed:
            raise ValueError("template_family must be one of: openai_messages,chatml,inst,custom")
        return token

    @field_validator("template_source", mode="before")
    @classmethod
    def _validate_template_source(cls, value: Any) -> str:
        token = _normalize_token(value).lower().replace("-", "_")
        allowed = {"runtime_metadata", "profile_override", "provider_builtin", "unknown"}
        if token not in allowed:
            raise ValueError(
                "template_source must be one of: runtime_metadata,profile_override,provider_builtin,unknown"
            )
        return token

    @field_validator("system_prompt_mode", mode="before")
    @classmethod
    def _validate_system_prompt_mode(cls, value: Any) -> str:
        token = _normalize_token(value).lower().replace("-", "_")
        allowed = {"native", "user_injection"}
        if token not in allowed:
            raise ValueError("system_prompt_mode must be one of: native,user_injection")
        return token

    @field_validator("context_budget_tokens")
    @classmethod
    def _validate_context_budget_tokens(cls, value: int) -> int:
        if int(value) <= 0:
            raise ValueError("context_budget_tokens must be > 0")
        return int(value)

    @field_validator("allowed_roles", mode="before")
    @classmethod
    def _validate_allowed_roles(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("allowed_roles must be a list")
        roles = _normalize_token_list(value, lowercase=True)
        if not roles:
            raise ValueError("allowed_roles must include at least one role")
        return roles

    @field_validator("prefill_strategy", mode="before")
    @classmethod
    def _validate_prefill_strategy(cls, value: Any) -> str:
        token = _normalize_token(value).lower().replace("-", "_")
        allowed = {"none", "assistant_prefix", "forced_token", "provider_specific"}
        if token not in allowed:
            raise ValueError("prefill_strategy must be one of: none,assistant_prefix,forced_token,provider_specific")
        return token

    @field_validator("tool_call_mode", mode="before")
    @classmethod
    def _validate_tool_call_mode(cls, value: Any) -> str:
        token = _normalize_token(value).lower().replace("-", "_")
        allowed = {"native", "json_wrapper"}
        if token not in allowed:
            raise ValueError("tool_call_mode must be one of: native,json_wrapper")
        return token

    @field_validator("thinking_block_format", mode="before")
    @classmethod
    def _validate_thinking_block_format(cls, value: Any) -> str:
        token = _normalize_token(value).lower().replace("-", "_")
        allowed = {"none", "xml_think_tags", "provider_native"}
        if token not in allowed:
            raise ValueError("thinking_block_format must be one of: none,xml_think_tags,provider_native")
        return token

    @field_validator("intro_phrase_denylist", mode="before")
    @classmethod
    def _validate_intro_phrase_denylist(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("intro_phrase_denylist must be a list")
        return _normalize_token_list(value, lowercase=True)

    @field_validator("stop_sequences_by_task_class", mode="before")
    @classmethod
    def _validate_stop_sequences(cls, value: Any) -> dict[str, list[str]]:
        if not isinstance(value, dict):
            raise ValueError("stop_sequences_by_task_class must be a map")
        normalized: dict[str, list[str]] = {}
        for task_class, stops in value.items():
            task = _normalize_token(task_class).lower()
            if task not in _TASK_CLASSES:
                raise ValueError(f"unsupported task class '{task}' in stop_sequences_by_task_class")
            if not isinstance(stops, list):
                raise ValueError(f"stop_sequences_by_task_class.{task} must be a list")
            normalized[task] = _normalize_token_list(stops, lowercase=False)
        return normalized

    @field_validator("sampling_bundles", mode="before")
    @classmethod
    def _validate_sampling_bundles(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("sampling_bundles must be a map")
        normalized: dict[str, Any] = {}
        for task_class, bundle in value.items():
            task = _normalize_token(task_class).lower()
            if task not in _TASK_CLASSES:
                raise ValueError(f"unsupported task class '{task}' in sampling_bundles")
            normalized[task] = bundle
        return normalized

    @model_validator(mode="after")
    def _validate_required_task_classes(self) -> "LocalPromptProfile":
        missing_stop = [task for task in _TASK_CLASSES if task not in self.stop_sequences_by_task_class]
        if missing_stop:
            raise ValueError(f"stop_sequences_by_task_class missing required task classes: {','.join(missing_stop)}")
        missing_sampling = [task for task in _TASK_CLASSES if task not in self.sampling_bundles]
        if missing_sampling:
            raise ValueError(f"sampling_bundles missing required task classes: {','.join(missing_sampling)}")
        return self


class LocalPromptProfileMatch(BaseModel):
    model_equals: list[str] = Field(default_factory=list)
    model_prefixes: list[str] = Field(default_factory=list)
    model_contains: list[str] = Field(default_factory=list)

    @field_validator("model_equals", "model_prefixes", "model_contains", mode="before")
    @classmethod
    def _validate_match_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("match fields must be lists")
        return _normalize_token_list(value, lowercase=True)

    @model_validator(mode="after")
    def _validate_has_match_rules(self) -> "LocalPromptProfileMatch":
        if not self.model_equals and not self.model_prefixes and not self.model_contains:
            raise ValueError("at least one of model_equals/model_prefixes/model_contains is required")
        return self

    def matches(self, model: str) -> bool:
        model_token = _normalize_token(model).lower()
        if not model_token:
            return False
        if model_token in self.model_equals:
            return True
        if any(model_token.startswith(prefix) for prefix in self.model_prefixes):
            return True
        if any(fragment in model_token for fragment in self.model_contains):
            return True
        return False


class LocalPromptProfileEntry(BaseModel):
    provider: str
    match: LocalPromptProfileMatch
    profile: LocalPromptProfile

    @field_validator("provider", mode="before")
    @classmethod
    def _validate_provider(cls, value: Any) -> str:
        return normalize_provider_for_local_prompt_profile(value)


@dataclass(frozen=True)
class ResolvedLocalPromptProfile:
    provider: str
    model: str
    profile: LocalPromptProfile
    resolution_path: str


class LocalPromptProfileRegistry(BaseModel):
    schema_version: str
    profiles: list[LocalPromptProfileEntry]

    @field_validator("schema_version", mode="before")
    @classmethod
    def _validate_schema_version(cls, value: Any) -> str:
        token = _normalize_token(value)
        if token != "local_prompt_profiles.v1":
            raise ValueError("schema_version must be 'local_prompt_profiles.v1'")
        return token

    @model_validator(mode="after")
    def _validate_unique_profile_ids(self) -> "LocalPromptProfileRegistry":
        seen: set[str] = set()
        duplicates: list[str] = []
        for entry in self.profiles:
            profile_id = entry.profile.profile_id
            if profile_id in seen:
                duplicates.append(profile_id)
            seen.add(profile_id)
        if duplicates:
            unique = ",".join(sorted(set(duplicates)))
            raise ValueError(f"duplicate profile_id values detected: {unique}")
        return self

    def resolve_profile(
        self,
        *,
        provider: str,
        model: str,
        override_profile_id: str | None = None,
        allow_fallback: bool = False,
        fallback_profile_id: str | None = None,
    ) -> ResolvedLocalPromptProfile:
        normalized_provider = normalize_provider_for_local_prompt_profile(provider)
        normalized_model = _normalize_token(model).lower()
        if not normalized_model:
            raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_NOT_FOUND}:{normalized_provider}:<empty_model>")
        if _normalize_token(override_profile_id):
            requested = _normalize_token(override_profile_id)
            override = next((entry for entry in self.profiles if entry.profile.profile_id == requested), None)
            if override is None:
                raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_OVERRIDE_MISSING}:{requested}")
            return ResolvedLocalPromptProfile(
                provider=normalized_provider,
                model=normalized_model,
                profile=override.profile,
                resolution_path="override",
            )
        matches = [
            entry
            for entry in self.profiles
            if entry.provider == normalized_provider and entry.match.matches(normalized_model)
        ]
        if len(matches) == 1:
            return ResolvedLocalPromptProfile(
                provider=normalized_provider,
                model=normalized_model,
                profile=matches[0].profile,
                resolution_path="matched",
            )
        if len(matches) > 1:
            profile_ids = ",".join(sorted(entry.profile.profile_id for entry in matches))
            raise ValueError(
                f"{E_LOCAL_PROMPT_PROFILE_AMBIGUOUS}:{normalized_provider}:{normalized_model}:{profile_ids}"
            )
        if allow_fallback and _normalize_token(fallback_profile_id):
            fallback_id = _normalize_token(fallback_profile_id)
            fallback = next((entry for entry in self.profiles if entry.profile.profile_id == fallback_id), None)
            if fallback is None:
                raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_FALLBACK_MISSING}:{fallback_id}")
            return ResolvedLocalPromptProfile(
                provider=normalized_provider,
                model=normalized_model,
                profile=fallback.profile,
                resolution_path="fallback",
            )
        raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_NOT_FOUND}:{normalized_provider}:{normalized_model}")


def load_local_prompt_profile_registry_payload(payload: dict[str, Any]) -> LocalPromptProfileRegistry:
    try:
        return LocalPromptProfileRegistry.model_validate(payload)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(part) for part in err.get('loc', ()))}:{err.get('msg')}" for err in exc.errors()
        )
        raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_SCHEMA}:{errors}") from exc


def load_local_prompt_profile_registry_file(
    path: Path | str = DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH,
) -> LocalPromptProfileRegistry:
    registry_path = Path(path)
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_LOAD}:{registry_path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{E_LOCAL_PROMPT_PROFILE_LOAD}:{registry_path}:root payload must be an object")
    return load_local_prompt_profile_registry_payload(payload)
