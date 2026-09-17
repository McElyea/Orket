"""Pure generation-option contracts shared by profile loading and provider binding."""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def request_sampling_options(context: Mapping[str, Any]) -> dict[str, Any]:
    options = {}
    maximum = context.get("local_prompt_max_output_tokens")
    if maximum is not None:
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            raise ValueError("local_prompt_max_output_tokens must be a positive integer")
        options["max_output_tokens"] = maximum
    temperature = context.get("local_prompt_temperature")
    if temperature is not None:
        if (not isinstance(temperature, (int, float)) or isinstance(temperature, bool)
                or not 0 <= temperature <= 2 or not math.isfinite(temperature)):
            raise ValueError("local_prompt_temperature must be a finite number between 0 and 2")
        options["temperature"] = float(temperature)
    return options


def request_stop_sequences(context: Mapping[str, Any]) -> list[str]:
    stops = context.get("local_prompt_stop_sequences")
    if stops is None:
        return []
    return exact_stop_sequences(stops, label="local_prompt_stop_sequences")


def exact_stop_sequences(stops: Any, *, label: str) -> list[str]:
    if not isinstance(stops, list) or not all(isinstance(item, str) and item != "" for item in stops):
        raise ValueError(f"{label} must be a list of nonempty strings")
    # Whitespace is part of a stop token. Only byte-identical duplicates collapse.
    return list(dict.fromkeys(stops))


def cap_sampling_bundle(bundle: Mapping[str, Any], requested: Mapping[str, Any]) -> dict[str, Any]:
    effective = {**bundle, **requested}
    if "max_output_tokens" in bundle and "max_output_tokens" in requested:
        effective["max_output_tokens"] = min(bundle["max_output_tokens"], requested["max_output_tokens"])
    return effective


def sampling_payload(bundle: Mapping[str, Any], *, ollama: bool, extended: bool) -> dict[str, Any]:
    fields = [("temperature", "temperature", float), ("top_p", "top_p", float),
              ("max_output_tokens", "num_predict" if ollama else "max_tokens", int)]
    if extended:
        fields += [("top_k", "top_k", int), ("repeat_penalty", "repeat_penalty", float)]
    payload = {target: convert(bundle[source]) for source, target, convert in fields if source in bundle}
    if bundle.get("seed_policy") == "fixed" and bundle.get("seed_value") is not None:
        payload["seed"] = int(bundle["seed_value"])
    return payload
