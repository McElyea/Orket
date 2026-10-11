"""Explicit, non-truncating admission for governed text model requests."""
from collections.abc import Mapping, Sequence

from orket.exceptions import ModelProviderError


class ModelInputBudgetError(ModelProviderError):
    """Refusal before inference; no model tokens have been consumed."""


def admit_model_input(messages: Sequence[Mapping[str, str]], *, requested_input: int,
                      requested_output: int, effective_output: int, context_limit: int,
                      native_counter: bool) -> int:
    if effective_output < requested_output:
        raise ModelInputBudgetError(
            f"E_MODEL_OUTPUT_LIMIT: requested={requested_output}, effective={effective_output}; "
            "lower the request or select an explicit host prompt profile with a larger output ceiling")
    available = min(requested_input, context_limit - effective_output)
    # This intentionally conservative estimate is not a tokenizer measurement.
    # Native llama.cpp admission uses the fully rendered prompt instead.
    estimate = 256 + sum(len(row.get("content", "").encode("utf-8")) + 128 for row in messages)
    if available < 1 or (not native_counter and estimate > available):
        raise ModelInputBudgetError(
            f"E_MODEL_INPUT_BUDGET: utf8_byte_estimate={estimate}, input_limit={requested_input}, "
            f"context_limit={context_limit}, output_limit={effective_output}; reduce evidence or "
            "increase request limits and the selected host profile context_budget_tokens "
            "(ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH), within model capacity; input was not truncated")
    return estimate
