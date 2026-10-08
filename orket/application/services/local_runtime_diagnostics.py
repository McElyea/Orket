"""Bounded first-run observations through existing provider, hardware and command owners."""
from __future__ import annotations

import asyncio
import math
import sys
from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import Any

import httpx

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.llm.local_model_provider_runtime_target import (
    ensure_provider_runtime_target,
    provider_runtime_target_payload,
)
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.application.services.local_model_factory import create_local_model_provider_async
from orket.application.services.user_settings_service import SettingsLocation, UserSettingsService
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL, provider_from_environment
from orket.core.contracts.provider_setup import ProviderSetup
from orket.exceptions import ModelConnectionError, ModelProviderError
from orket.hardware import get_metrics_snapshot
from orket.runtime.config.config_loader import ConfigLoader
from orket.runtime.config.gguf_model_inventory import resolve_gguf_model_root
from orket.runtime.config.provider_runtime_target import default_base_url


def _configured_model(root: Path, environment: dict[str, str], explicit: str) -> str:
    if explicit:
        return explicit
    location = SettingsLocation(root, environment.get("ORKET_DURABLE_ROOT", ".orket/durable"))
    settings = UserSettingsService(location).read_settings()
    organization = ConfigLoader(root, environment=environment, user_settings=settings).load_organization()
    if organization is None:
        raise ValueError("E_DIAGNOSTIC_PROJECT_REQUIRED: run orket setup or supply --model-id")
    return str(organization.process_rules.get("default_llm") or DEFAULT_LOCAL_MODEL)


async def _observe_provider(root: Path, environment: dict[str, str], choices: ProviderSetup,
                            *, inference: bool, timeout_seconds: float) -> dict[str, Any]:
    provider = None
    observed: dict[str, Any] = {"catalog_admitted": False, "inference": "not_requested" if not inference else "not_established",
                                "metal": "unverified", "resources_closed": False}
    try:
        provider = await create_local_model_provider_async(
            model=choices.model, provider=choices.provider, base_url=choices.base_url,
            environment=environment, cwd=root, temperature=0, timeout=timeout_seconds)
        async with asyncio.timeout(timeout_seconds):
            await ensure_provider_runtime_target(provider)
            observed.update(catalog_admitted=True, target=provider_runtime_target_payload(provider))
            if inference:
                response = await provider.complete(
                    [{"role": "user", "content": "What is 6 multiplied by 7? Reply with only the number 42."}],
                    runtime_context={"local_prompt_max_output_tokens": 32, "local_prompt_temperature": 0})
                content = response.content.strip()
                observed.update(inference="success" if content == "42" else "failure", response=content)
    except (ModelConnectionError, ModelProviderError, httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
        observed.update(error=f"{type(exc).__name__}: {exc}",
                        inference="failure" if inference and observed["catalog_admitted"] else "not_established")
    finally:
        if provider is not None:
            await run_owned_io(provider.close, label="local-diagnostics-provider-close", preserve_failure=True)
            observed["resources_closed"] = True
    return observed


async def diagnose_local_runtime(
    root: Path, *, environment: Mapping[str, str], provider_name: str = "", model_id: str = "",
    base_url: str = "", inference: bool = False, timeout_seconds: float = 30,
) -> dict[str, Any]:
    if not root.is_absolute():
        raise ValueError("E_DIAGNOSTIC_ROOT_ABSOLUTE_REQUIRED")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("E_DIAGNOSTIC_TIMEOUT_POSITIVE_REQUIRED")
    captured = dict(environment)
    provider_name = provider_name or provider_from_environment(captured)
    # A first-run check must diagnose the requested target, never silently select/load another.
    captured.update(ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL="0", ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL="0")
    model = await run_owned_thread(partial(_configured_model, root, captured, model_id), label="diagnostic-model-input")
    choices = ProviderSetup(provider_name, model, base_url or default_base_url(provider_name, environment=captured),
                            str(resolve_gguf_model_root(environment=captured)) if provider_name == "llama_cpp" else "")
    report: dict[str, Any] = {"project": str(root), "provider": choices.provider, "model": choices.model,
                              "base_url": choices.base_url, "provider_observation": {"catalog_admitted": False},
                              "scope": "requested local diagnostics; not whole-runtime or Metal acceptance"}
    report["hardware"] = await run_owned_thread(get_metrics_snapshot, label="diagnostic-hardware")
    report["provider_observation"] = await _observe_provider(root, captured, choices, inference=inference,
                                                             timeout_seconds=timeout_seconds)
    owner = CommandProcessSupervisor(root, cancellation_event="local-diagnostics-command-interrupted")
    command = await owner.run([sys.executable, "-I", "-c", "print('orket diagnostic command')"], cwd=root,
                               environment=captured, timeout_seconds=min(timeout_seconds, 10), output_limit_bytes=4096)
    command_ok = (command.returncode == 0 and command.reason == "completed" and command.cleanup_confirmed
                  and command.capture_complete and command.stdout.strip() == b"orket diagnostic command")
    report["command_observation"] = {"ok": command_ok, "returncode": command.returncode, **command.lifetime()}
    provider_ok = report["provider_observation"]["catalog_admitted"] and report["provider_observation"]["resources_closed"] and (
        not inference or report["provider_observation"]["inference"] == "success")
    blocked = command.backend == "unavailable" and command.command_pid is None
    report.update(ok=bool(provider_ok and command_ok), observed_path="blocked" if blocked else "primary",
                  observed_result="environment blocker" if blocked else "success" if provider_ok and command_ok else "failure")
    return report
