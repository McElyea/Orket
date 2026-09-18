"""Application composition binds captured settings and prompt authority to transport."""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.application.services.local_prompting_service import LocalPromptingService
from orket.application.services.provider_preparation_service import ProviderPreparationService
from orket.core.contracts.provider_preparation import ProviderPreparationPort


def create_local_model_provider(*args: Any, environment: Mapping[str, str] | None = None,
                                runtime_preparation: ProviderPreparationPort | None = None,
                                **kwargs: Any) -> LocalModelProvider:
    captured = dict(os.environ if environment is None else environment)
    return LocalModelProvider(*args, environment=captured,
                              prompt_policy=LocalPromptingService(environment=captured),
                              runtime_preparation=(runtime_preparation if runtime_preparation is not None
                                                   else ProviderPreparationService(environment=captured)), **kwargs)
