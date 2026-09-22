"""One non-secret provider selection for ODR discovery, execution and evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from orket.application.services.local_model_factory import (
    create_local_model_provider_async,
)
from orket.core.contracts.provider_runtime import normalize_base_url, normalize_provider
from orket.runtime.config.defaults import configured_provider
from orket.runtime.config.provider_runtime_target import default_base_url, list_provider_models


@dataclass(frozen=True)
class ProviderSelection:
    provider: str
    base_url: str

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not isinstance(self.base_url, str) or not self.base_url:
            raise ValueError("ODR provider selection requires nonempty string fields")
        normalize_provider(self.provider)
        parsed = urlsplit(self.base_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment):
            raise ValueError("ODR provider endpoint must be HTTP(S) without credentials, query or fragment")

    def to_payload(self) -> dict[str, str]:
        return asdict(self)


def resolve_selection(provider: str = "", base_url: str = "") -> ProviderSelection:
    selected = str(provider or configured_provider()).strip().lower()
    endpoint = str(base_url or default_base_url(selected)).strip()
    checked = ProviderSelection(selected, endpoint if "://" in endpoint else "http://" + endpoint)
    return ProviderSelection(selected, normalize_base_url(checked.base_url, default=checked.base_url))


def selection_from_plan(plan: dict) -> ProviderSelection:
    values = plan.get("provider_selection")
    if plan.get("schema_version") != "odr.run_arbiter.plan.v2" or not isinstance(values, dict):
        raise ValueError("ODR plan requires versioned provider selection")
    if set(values) != {"provider", "base_url"}:
        raise ValueError("ODR plan provider selection has invalid fields")
    return ProviderSelection(**values)


async def available_models(selection: ProviderSelection) -> set[str]:
    # The adapter owns API-key interpretation and client cleanup; keys never enter the plan.
    async with (await create_local_model_provider_async(
        model="odr-inventory", provider=selection.provider, base_url=selection.base_url, timeout=30,
    )) as provider:
        inventory = await list_provider_models(
            provider=selection.provider, base_url=selection.base_url,
            api_key=provider.openai_api_key or None, timeout_s=10,
        )
    return set(inventory["models"])


def provider_evidence_failures(payload: dict, selection: ProviderSelection, architect: str, auditor: str) -> list[str]:
    failures = []
    config = payload.get("config", {})
    if not isinstance(config, dict) or config.get("provider_selection") != selection.to_payload():
        failures.append("provider_selection_mismatch")
    for row in payload.get("results", []):
        for scenario in row.get("scenarios", []):
            rounds = scenario.get("rounds", [])
            if not rounds:
                failures.append("provider_round_evidence_missing")
            for round_row in rounds:
                if not isinstance(round_row, dict):
                    failures.append("provider_round_evidence_invalid")
                    continue
                for role, model in (("architect", architect), ("auditor", auditor)):
                    raw = round_row.get(role + "_provider_raw")
                    if not isinstance(raw, dict) or raw.get("provider_name") != selection.provider or raw.get("model") != model:
                        failures.append(role + "_provider_identity_mismatch")
    return sorted(set(failures))
