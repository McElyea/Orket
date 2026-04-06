from __future__ import annotations

import contextlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.orchestration.engine import OrchestrationEngine
from scripts.common.run_summary_support import load_validated_run_summary

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE_ROOT = REPO_ROOT / "workspace" / "productflow"
DEFAULT_OPERATOR_ACTOR_REF = "productflow:operator"
PRODUCTFLOW_EPIC_ID = "productflow_governed_write_file"
PRODUCTFLOW_ISSUE_ID = "PF-WRITE-1"
PRODUCTFLOW_BUILDER_SEAT = "lead_architect"
PRODUCTFLOW_REVIEWER_SEAT = "reviewer_seat"
PRODUCTFLOW_OUTPUT_PATH = "agent_output/productflow/approved.txt"
PRODUCTFLOW_OUTPUT_CONTENT = "approved"

_EXECUTION_CONTEXT_MARKER = "Execution Context JSON:\n"
_TURN_PACKET_PREFIX = "TURN PACKET:\n"
_IDENTITY_PREFIX = "IDENTITY: "


@dataclass(frozen=True)
class ProductFlowPaths:
    workspace_root: Path
    config_root: Path
    durable_root: Path
    runtime_db_path: Path
    control_plane_db_path: Path
    runs_root: Path
    results_root: Path


@dataclass(frozen=True)
class ResolvedProductFlowRun:
    run_id: str
    session_id: str
    artifact_root: Path
    run_summary_path: Path
    run_summary: dict[str, Any]
    resolution_basis: dict[str, Any]


def resolve_productflow_paths(workspace_root: Path | None = None) -> ProductFlowPaths:
    workspace = (workspace_root or DEFAULT_WORKSPACE_ROOT).resolve()
    durable_root_raw = str(os.getenv("ORKET_DURABLE_ROOT") or "").strip()
    durable_root = Path(durable_root_raw).resolve() if durable_root_raw else (workspace / ".orket" / "durable")
    return ProductFlowPaths(
        workspace_root=workspace,
        config_root=workspace / ".productflow_assets",
        durable_root=durable_root,
        runtime_db_path=durable_root / "db" / "orket_persistence.db",
        control_plane_db_path=durable_root / "db" / "control_plane_records.sqlite3",
        runs_root=workspace / "runs",
        results_root=REPO_ROOT / "benchmarks" / "results" / "productflow",
    )


def ensure_productflow_environment(paths: ProductFlowPaths) -> None:
    os.environ.setdefault("ORKET_DURABLE_ROOT", str(paths.durable_root))
    os.environ.setdefault("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    paths.workspace_root.mkdir(parents=True, exist_ok=True)
    (paths.workspace_root / "agent_output" / "productflow").mkdir(parents=True, exist_ok=True)
    (paths.workspace_root / "verification").mkdir(parents=True, exist_ok=True)
    paths.results_root.mkdir(parents=True, exist_ok=True)
    _write_productflow_assets(paths.config_root)


def reset_productflow_runtime_state(paths: ProductFlowPaths) -> None:
    for target in (
        paths.workspace_root / "agent_output",
        paths.workspace_root / "verification",
        paths.workspace_root / "observability",
        paths.workspace_root / "runs",
    ):
        if target.exists():
            shutil.rmtree(target)
    if paths.durable_root.exists() and paths.durable_root.resolve().is_relative_to(paths.workspace_root.resolve()):
        shutil.rmtree(paths.durable_root)


def _write_productflow_assets(config_root: Path) -> None:
    (config_root / "config").mkdir(parents=True, exist_ok=True)
    for folder in ("epics", "roles", "dialects", "teams", "environments"):
        (config_root / "model" / "core" / folder).mkdir(parents=True, exist_ok=True)

    _write_json(
        config_root / "config" / "organization.json",
        {
            "name": "ProductFlow Org",
            "vision": "Governed ProductFlow proof",
            "ethos": "Truthful runtime evidence first",
            "branding": {"design_dos": []},
            "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
            "process_rules": {"small_project_builder_variant": "architect"},
            "departments": ["core"],
        },
    )
    for dialect_name in ("qwen", "llama3", "deepseek-r1", "phi", "generic"):
        _write_json(
            config_root / "model" / "core" / "dialects" / f"{dialect_name}.json",
            {
                "model_family": dialect_name,
                "dsl_format": "JSON",
                "constraints": [],
                "hallucination_guard": "None",
            },
        )
    _write_json(
        config_root / "model" / "core" / "roles" / "lead_architect.json",
        {
            "id": "ARCH",
            "summary": "lead_architect",
            "type": "utility",
            "description": "ProductFlow builder",
            "tools": ["write_file", "update_issue_status"],
        },
    )
    _write_json(
        config_root / "model" / "core" / "roles" / "code_reviewer.json",
        {
            "id": "REV",
            "summary": "code_reviewer",
            "type": "utility",
            "description": "ProductFlow reviewer",
            "tools": ["read_file", "update_issue_status"],
        },
    )
    _write_json(
        config_root / "model" / "core" / "roles" / "integrity_guard.json",
        {
            "id": "VERI",
            "summary": "integrity_guard",
            "type": "utility",
            "description": "ProductFlow review verifier",
            "tools": ["read_file", "update_issue_status"],
        },
    )
    _write_json(
        config_root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                PRODUCTFLOW_BUILDER_SEAT: {"name": "Lead", "roles": ["lead_architect"]},
                PRODUCTFLOW_REVIEWER_SEAT: {"name": "Reviewer", "roles": ["code_reviewer"]},
            },
        },
    )
    _write_json(
        config_root / "model" / "core" / "environments" / "standard.json",
        {"name": "standard", "model": "dummy", "temperature": 0.0, "timeout": 300},
    )
    _write_json(
        config_root / "model" / "core" / "epics" / f"{PRODUCTFLOW_EPIC_ID}.json",
        {
            "id": PRODUCTFLOW_EPIC_ID,
            "name": "ProductFlow Governed Write File",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Canonical ProductFlow governed write_file approval flow.",
            "architecture_governance": {"idesign": False, "pattern": "Tactical"},
            "issues": [
                {
                    "id": PRODUCTFLOW_ISSUE_ID,
                    "summary": "Write the governed ProductFlow output and move to review",
                    "seat": PRODUCTFLOW_BUILDER_SEAT,
                    "priority": "High",
                }
            ],
        },
    )


def build_productflow_engine(paths: ProductFlowPaths) -> OrchestrationEngine:
    ensure_productflow_environment(paths)
    engine = OrchestrationEngine(
        paths.workspace_root,
        department="core",
        db_path=str(paths.runtime_db_path),
        config_root=paths.config_root,
    )
    loop_policy = engine._pipeline.orchestrator.loop_policy_node

    def _approval_required_tools_for_seat(seat_name: str, issue: Any = None, turn_status: Any = None) -> list[str]:
        del issue, turn_status
        if str(seat_name or "").strip().lower() == PRODUCTFLOW_BUILDER_SEAT:
            return ["write_file"]
        return []

    setattr(loop_policy, "approval_required_tools_for_seat", _approval_required_tools_for_seat)
    return engine


def relative_to_workspace(path: Path, workspace_root: Path) -> str:
    return path.resolve().relative_to(workspace_root.resolve()).as_posix()


async def resolve_productflow_run_with_engine(
    *,
    run_id: str,
    engine: Any,
    workspace_root: Path | None = None,
) -> ResolvedProductFlowRun:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        raise ValueError("productflow_run_id_required")
    paths = resolve_productflow_paths(workspace_root)
    if not paths.runs_root.exists():
        raise ValueError("productflow_runs_root_missing")
    candidates: list[ResolvedProductFlowRun] = []
    # ProductFlow authority freezes approval.control_plane_target_ref + validated
    # run_summary.json as the only admitted run_id -> session_id witness.
    for session_root in sorted(paths.runs_root.iterdir(), key=lambda item: item.name):
        if not session_root.is_dir():
            continue
        run_summary_path = session_root / "run_summary.json"
        if not run_summary_path.exists():
            continue
        try:
            summary = load_validated_run_summary(run_summary_path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        approvals = await engine.list_approvals(session_id=session_root.name, limit=1000)
        matches = [
            item
            for item in approvals
            if str(item.get("control_plane_target_ref") or "").strip() == normalized_run_id
            and str(item.get("reason") or "").strip() == "approval_required_tool:write_file"
        ]
        if len(matches) != 1:
            continue
        candidates.append(
            ResolvedProductFlowRun(
                run_id=normalized_run_id,
                session_id=session_root.name,
                artifact_root=session_root,
                run_summary_path=run_summary_path,
                run_summary=summary,
                resolution_basis={
                    "witness": "approval.control_plane_target_ref + run_summary",
                    "approval_id": str(matches[0].get("approval_id") or ""),
                    "run_summary_path": relative_to_workspace(run_summary_path, paths.workspace_root),
                },
            )
        )
    if not candidates:
        raise ValueError(f"productflow_run_id_not_found:{normalized_run_id}")
    if len(candidates) != 1:
        raise ValueError(f"productflow_run_id_ambiguous:{normalized_run_id}")
    return candidates[0]


@contextlib.contextmanager
def patched_productflow_provider() -> Iterator[None]:
    original_init = LocalModelProvider.__init__
    original_complete = LocalModelProvider.complete

    def _patched_init(self: LocalModelProvider, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        self.model = "dummy"
        self.timeout = 300

    async def _patched_complete(self: LocalModelProvider, messages: list[dict[str, Any]], **kwargs: Any) -> ModelResponse:
        del self, kwargs
        context = _extract_turn_prompt_context(messages)
        active_role = str(context.get("role") or "").strip().lower()
        current_status = str(context.get("current_status") or "").strip().lower()
        if current_status == "code_review" or active_role in {PRODUCTFLOW_REVIEWER_SEAT, "code_reviewer"}:
            return ModelResponse(
                content='```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```',
                raw={"model": "dummy", "total_tokens": 40},
            )
        return ModelResponse(
            content=(
                '```json\n{"tool": "write_file", "args": {"path": "'
                + PRODUCTFLOW_OUTPUT_PATH
                + '", "content": "'
                + PRODUCTFLOW_OUTPUT_CONTENT
                + '"}}\n```\n'
                '```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```'
            ),
            raw={"model": "dummy", "total_tokens": 80},
        )

    LocalModelProvider.__init__ = _patched_init
    LocalModelProvider.complete = _patched_complete
    try:
        yield
    finally:
        LocalModelProvider.__init__ = original_init
        LocalModelProvider.complete = original_complete


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _extract_turn_prompt_context(messages: list[dict[str, Any]]) -> dict[str, Any]:
    context = {"role": "", "current_status": ""}
    decoder = json.JSONDecoder()
    for message in messages:
        content = str((message or {}).get("content") or "")
        if not context["role"]:
            for line in content.splitlines():
                if line.startswith(_IDENTITY_PREFIX):
                    context["role"] = line[len(_IDENTITY_PREFIX) :].strip().lower()
                    break
        if _EXECUTION_CONTEXT_MARKER in content:
            payload_text = content.split(_EXECUTION_CONTEXT_MARKER, 1)[1]
            try:
                parsed, _ = decoder.raw_decode(payload_text.lstrip())
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                if not context["role"]:
                    context["role"] = str(parsed.get("role") or parsed.get("seat") or "").strip().lower()
                if not context["current_status"]:
                    context["current_status"] = str(parsed.get("current_status") or "").strip().lower()
                continue
        if not content.startswith(_TURN_PACKET_PREFIX):
            continue
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("- role: "):
                context["role"] = stripped[len("- role: ") :].strip().lower()
            elif stripped.startswith("- current_status: "):
                context["current_status"] = stripped[len("- current_status: ") :].strip().lower()
    return context


__all__ = [
    "DEFAULT_OPERATOR_ACTOR_REF",
    "PRODUCTFLOW_BUILDER_SEAT",
    "PRODUCTFLOW_EPIC_ID",
    "PRODUCTFLOW_ISSUE_ID",
    "PRODUCTFLOW_OUTPUT_CONTENT",
    "PRODUCTFLOW_OUTPUT_PATH",
    "ProductFlowPaths",
    "ResolvedProductFlowRun",
    "build_productflow_engine",
    "ensure_productflow_environment",
    "patched_productflow_provider",
    "relative_to_workspace",
    "reset_productflow_runtime_state",
    "resolve_productflow_paths",
    "resolve_productflow_run_with_engine",
]
