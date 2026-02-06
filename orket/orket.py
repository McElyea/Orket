# orket/orket.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from orket.llm import LocalModelProvider
from orket.logging import log_event
from orket.conductor import Conductor, ManualConductor, SessionView
from orket.agents.agent_factory import build_band_agents
from orket.tools import _policy


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TaskContext:
    task: Dict[str, Any]


@dataclass
class Flow:
    name: str
    description: str
    band_name: str
    score_name: str
    task: Dict[str, Any]


@dataclass
class BandRole:
    description: str
    tools: List[str]


@dataclass
class Band:
    name: str
    roles: Dict[str, BandRole]


@dataclass
class Score:
    name: str
    steps: List[Dict[str, Any]]


@dataclass
class OrchestrateResult:
    flow_name: str
    transcript: List[Dict[str, Any]]
    workspace: Path


# ---------------------------------------------------------------------------
# JSON loading helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_flow(flow_path: Path) -> Flow:
    data = _load_json(flow_path)
    return Flow(
        name=data["name"],
        description=data.get("description", ""),
        band_name=data["band"],
        score_name=data["score"],
        task=data["task"],
    )


def load_band(model_root: Path, band_name: str) -> Band:
    path = model_root / "band" / f"{band_name}.json"
    data = _load_json(path)

    roles: Dict[str, BandRole] = {}
    for role_name, role_data in data["roles"].items():
        roles[role_name] = BandRole(
            description=role_data["description"],
            tools=role_data.get("tools", []),
        )

    return Band(
        name=data["name"],
        roles=roles,
    )


def load_score(model_root: Path, score_name: str) -> Score:
    path = model_root / "score" / f"{score_name}.json"
    data = _load_json(path)
    return Score(
        name=data["name"],
        steps=data["steps"],
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def orchestrate(
    flow_path: Path,
    workspace: Path,
    model_name: str,
    temperature: float = 0.2,
    seed: Optional[int] = None,
    interactive_conductor: bool = False,
) -> OrchestrateResult:

    workspace = workspace.resolve()

    # FIXED: correct model root resolution
    # flow_path = model/flow/standard.json
    # flow_path.parent = model/flow
    # flow_path.parent.parent = model
    model_root = flow_path.parent.parent

    # Load flow, band, score, task
    flow = load_flow(flow_path)
    band = load_band(model_root, flow.band_name)
    score = load_score(model_root, flow.score_name)
    ctx = TaskContext(task=flow.task)

    # Register workspace with policy
    _policy().add_workspace(str(workspace))

    # Provider + Conductor
    provider = LocalModelProvider(model=model_name, temperature=temperature, seed=seed)
    conductor: Conductor = ManualConductor() if interactive_conductor else Conductor()

    # Build agents
    agents = build_band_agents(band, provider)

    # Session-level model selection logging
    conductor.log_session_models(
        band=band,
        provider=provider,
        workspace=workspace,
        flow_name=flow.name,
    )

    transcript: List[Dict[str, Any]] = []
    notes: Dict[str, Any] = {}

    log_event(
        "session_start",
        {
            "flow": flow.name,
            "band": band.name,
            "score": score.name,
            "model": provider.model,
            "temperature": provider.temperature,
            "seed": provider.seed,
        },
        workspace=workspace,
    )

    # Main step loop
    for idx, step in enumerate(score.steps):
        role_name = step["role"]

        session_view = SessionView(
            flow_name=flow.name,
            step_index=idx,
            transcript=transcript,
            role=role_name,
            notes=notes,
        )

        adjust = conductor.before_step(step, session_view)

        if adjust.skip_role:
            log_event(
                "step_skipped",
                {
                    "role": role_name,
                    "step_index": idx,
                    "reason": "conductor_skip",
                },
                workspace=workspace,
            )
            continue

        log_event(
            "step_start",
            {
                "role": role_name,
                "step_index": idx,
                "model": provider.model,
                "temperature": provider.temperature,
                "seed": provider.seed,
            },
            workspace=workspace,
        )

        agent = agents[role_name]
        agent.apply_prompt_patch(adjust.prompt_patch)

        response = agent.run(
            task=ctx.task,
            context={
                "step_index": idx,
                "workspace": str(workspace),
                "flow_name": flow.name,
                "notes": notes,
            },
            workspace=workspace,
            transcript=transcript,
        )

        # Handle NOTES_UPDATE in response
        if "NOTES_UPDATE:" in response.content:
            try:
                import json
                parts = response.content.split("NOTES_UPDATE:")
                update_str = parts[1].splitlines()[0].strip()
                update_data = json.loads(update_str)
                notes.update(update_data)
                log_event("notes_updated", {"update": update_data, "current_notes": notes}, workspace=workspace)
            except Exception as e:
                log_event("notes_update_error", {"error": str(e), "content": response.content}, workspace=workspace)

        log_event(
            "step_end",
            {
                "role": role_name,
                "step_index": idx,
                "output_preview": response.content[:200],
                "model": provider.model,
            },
            workspace=workspace,
        )

        transcript.append(
            {
                "step_index": idx,
                "role": role_name,
                "note": response.note,
                "summary": response.content,
            }
        )

        conductor.after_step(step, session_view)

    log_event(
        "session_end",
        {
            "flow": flow.name,
            "steps": len(score.steps),
        },
        workspace=workspace,
    )

    return OrchestrateResult(
        flow_name=flow.name,
        transcript=transcript,
        workspace=workspace,
    )
