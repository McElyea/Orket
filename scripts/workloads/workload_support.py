from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.llm.local_model_provider import LocalModelProvider
from scripts.probes.probe_support import applied_probe_env, json_safe

TModel = TypeVar("TModel", bound=BaseModel)


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(load_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def artifact_inventory(root: Path) -> list[str]:
    return [path.relative_to(root).as_posix() for path in sorted(root.rglob("*")) if path.is_file()]


def extract_json_object(text: str) -> dict[str, Any] | None:
    candidate = str(text or "").strip()
    if not candidate:
        return None
    possible_payloads = [candidate]
    if "```" in candidate:
        parts = candidate.split("```")
        possible_payloads.extend(part.strip() for part in parts if part.strip())
    brace_start = candidate.find("{")
    brace_end = candidate.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        possible_payloads.append(candidate[brace_start : brace_end + 1].strip())

    for raw in possible_payloads:
        normalized = raw
        if normalized.startswith("json\n") or normalized.startswith("JSON\n"):
            normalized = normalized[5:].strip()
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def empty_contract_payload(advisory_errors: list[str]) -> dict[str, Any]:
    return {"advisory_errors": list(advisory_errors)}


def validate_json_contract(
    *,
    text: str,
    model_cls: type[TModel],
) -> tuple[dict[str, Any], bool, bool, list[str]]:
    advisory_errors: list[str] = []
    extracted = extract_json_object(text)
    if extracted is None:
        advisory_errors.append("response_json_not_found")
        return empty_contract_payload(advisory_errors), False, False, advisory_errors
    try:
        validated = model_cls.model_validate(extracted)
    except ValidationError as exc:
        advisory_errors.append(f"contract_validation_error:{exc}")
        payload = empty_contract_payload(advisory_errors)
        payload["raw_extracted_json"] = extracted
        return payload, True, False, advisory_errors
    payload = validated.model_dump()
    payload["advisory_errors"] = list(advisory_errors)
    return payload, True, True, advisory_errors


async def run_strict_json_model(
    *,
    model: str,
    provider: str,
    ollama_host: str,
    temperature: float,
    seed: int,
    timeout: int,
    messages: list[dict[str, str]],
    runtime_context: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    with applied_probe_env(
        provider=str(provider),
        ollama_host=str(ollama_host or "").strip() or None,
        disable_sandbox=True,
    ):
        local_provider = LocalModelProvider(
            model=str(model),
            temperature=float(temperature),
            seed=int(seed),
            timeout=int(timeout),
        )
        try:
            response = await local_provider.complete(
                list(messages),
                runtime_context={
                    **dict(runtime_context or {}),
                    "local_prompt_task_class": "strict_json",
                },
            )
        finally:
            await local_provider.close()
    return str(response.content or ""), json_safe(dict(response.raw or {}))


def load_python_symbols(path: Path) -> dict[str, Any]:
    source = load_text(path)
    namespace: dict[str, Any] = {"__name__": "__generated_workload__"}
    code = compile(source, str(path), "exec")
    exec(code, namespace)
    return namespace
