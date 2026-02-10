# orket/orket.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import json
import uuid
import asyncio
from datetime import datetime, UTC
from functools import lru_cache

from orket.llm import LocalModelProvider
from orket.logging import log_event
from orket.state import runtime_state
from orket.policy import create_session_policy
from orket.tools import ToolBox, get_tool_map
from orket.schema import EpicConfig, TeamConfig, EnvironmentConfig, RockConfig, IssueConfig, CardStatus, SkillConfig, DialectConfig, RoleConfig, CardType
from orket.utils import get_eos_sprint, sanitize_name
from orket.exceptions import CardNotFound, ExecutionFailed, StateConflict, ComplexityViolation
from orket.infrastructure.sqlite_repositories import SQLiteSessionRepository, SQLiteSnapshotRepository
from orket.infrastructure.async_card_repository import AsyncCardRepository
from orket.orchestration.turn_executor import TurnExecutor
from orket.orchestration.orchestrator import Orchestrator
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from orket.domain.bug_fix_phase import BugFixPhaseManager
from orket.services.webhook_db import WebhookDatabase
from orket.domain.sandbox import SandboxRegistry, SandboxStatus
from orket.services.prompt_compiler import PromptCompiler
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# 1. Configuration & Asset Loading (Application Service)
# ---------------------------------------------------------------------------

class ConfigLoader:
    """
    Unified Configuration and Asset Loader.
    Priority: 1. config/ (Unified) 2. model/{dept}/ (Legacy) 3. model/core/ (Fallback)
    """
    def __init__(self, root: Path, department: str = "core"):
        self.root = root
        self.config_dir = root / "config"
        self.model_dir = root / "model"
        self.department = department

    def load_organization(self) -> Optional[OrganizationConfig]:
        from orket.schema import OrganizationConfig
        from orket.settings import get_setting
        
        org_data = {}
        
        # 1. Try Modular Configs (New Standard)
        info_path = self.config_dir / "org_info.json"
        arch_path = self.config_dir / "architecture.json"
        
        if info_path.exists() and arch_path.exists():
            try:
                info = json.loads(info_path.read_text(encoding="utf-8"))
                arch = json.loads(arch_path.read_text(encoding="utf-8"))
                org_data = {**info, **arch}
            except Exception as e:
                log_event("config_error", {"error": f"Failed to load modular config: {e}"})

        # 2. Key Fallback: Monolith (Legacy)
        if not org_data:
            paths = [
                self.config_dir / "organization.json",
                self.model_dir / "organization.json"
            ]
            for p in paths:
                if p.exists():
                    try:
                        org_data = json.loads(p.read_text(encoding="utf-8"))
                        break
                    except Exception:
                        continue
        
        if not org_data:
            return None

        # Validate
        try:
            org = OrganizationConfig.model_validate(org_data)
        except Exception as e:
            # Fallback or strict fail? Strict fail for now but log it.
            print(f"[CONFIG] Validation failed: {e}")
            return None
        
        # Overrides
        env_name = get_setting("ORKET_ORG_NAME")
        if env_name: org.name = env_name
        
        env_vision = get_setting("ORKET_ORG_VISION")
        if env_vision: org.vision = env_vision
            
        return org

    def load_department(self, name: str) -> Optional[DepartmentConfig]:
        from orket.schema import DepartmentConfig
        paths = [
            self.config_dir / "departments" / f"{name}.json",
            self.model_dir / name / "department.json" # Legacy check
        ]
        for p in paths:
            if p.exists():
                return DepartmentConfig.model_validate_json(p.read_text(encoding="utf-8"))
        return None

    def load_asset(self, category: str, name: str, model_type: Type[BaseModel]) -> Any:
        return model_type.model_validate_json(self._load_asset_raw(category, name, self.department))

    @lru_cache(maxsize=256)
    def _load_asset_raw(self, category: str, name: str, dept: str) -> str:
        # 1. Unified Config
        paths = [
            self.config_dir / category / f"{name}.json",
            self.model_dir / dept / category / f"{name}.json",
            self.model_dir / "core" / category / f"{name}.json"
        ]
        
        for p in paths:
            if p.exists():
                return p.read_text(encoding="utf-8")
        
        raise CardNotFound(f"Asset '{name}' not found in category '{category}' for department '{dept}'.")

    def list_assets(self, category: str) -> List[str]:
        assets = set()
        search_paths = [
            self.config_dir / category,
            self.model_dir / self.department / category,
            self.model_dir / "core" / category
        ]
        for p in search_paths:
            if p.exists():
                for f in p.glob("*.json"):
                    assets.add(f.stem)
        return sorted(list(assets))

# ---------------------------------------------------------------------------
# 2. The Execution Pipeline (Explicit Orchestration Flow)
# ---------------------------------------------------------------------------

from orket.orchestration.notes import NoteStore, Note

class ExecutionPipeline:
    """
    The central engine for Orket Unit execution.
    Load → Validate → Plan → Execute → Persist → Report
    """
    def __init__(self, 
                 workspace: Path, 
                 department: str = "core", 
                 db_path: str = "orket_persistence.db", 
                 config_root: Optional[Path] = None,
                 cards_repo: Optional[AsyncCardRepository] = None,
                 sessions_repo: Optional[SQLiteSessionRepository] = None,
                 snapshots_repo: Optional[SQLiteSnapshotRepository] = None):
        self.workspace = workspace
        self.department = department
        self.config_root = config_root or Path(".").resolve()
        self.loader = ConfigLoader(self.config_root, department)
        self.db_path = db_path
        
        # Load Organization
        self.org = self.loader.load_organization()
        
        # Injected or default repositories
        self.async_cards = cards_repo or AsyncCardRepository(self.db_path)
        self.sessions = sessions_repo or SQLiteSessionRepository(self.db_path)
        self.snapshots = snapshots_repo or SQLiteSnapshotRepository(self.db_path)
        
        self.notes = NoteStore()
        self.transcript = []
        self.sandbox_orchestrator = SandboxOrchestrator(self.workspace)
        self.webhook_db = WebhookDatabase()
        self.bug_fix_manager = BugFixPhaseManager(
            organization_config=self.org.process_rules if self.org else {},
            db=self.webhook_db
        )
        self.orchestrator = Orchestrator(
            workspace=self.workspace,
            async_cards=self.async_cards,
            snapshots=self.snapshots,
            org=self.org,
            config_root=self.config_root,
            db_path=self.db_path,
            loader=self.loader,
            sandbox_orchestrator=self.sandbox_orchestrator
        )

    async def run_card(self, card_id: str, **kwargs) -> Any:
        epics = self.loader.list_assets("epics")
        if card_id in epics:
            return await self.run_epic(card_id, **kwargs)
        
        rocks = self.loader.list_assets("rocks")
        if card_id in rocks:
            return await self.run_rock(card_id, **kwargs)

        parent_epic, parent_ename, target_issue = self._find_parent_epic(card_id)
        if not parent_epic: raise CardNotFound(f"Card {card_id} not found.")
        print(f"  [PIPELINE] Executing Atomic Issue: {card_id} (Parent: {parent_epic.name})")
        return await self.run_epic(parent_ename, target_issue_id=card_id, **kwargs)

    async def run_epic(self, epic_name: str, build_id: str = None, session_id: str = None, driver_steered: bool = False, target_issue_id: str = None, **kwargs) -> List[Dict]:
        epic = self.loader.load_asset("epics", epic_name, EpicConfig)
        team = self.loader.load_asset("teams", epic.team, TeamConfig)
        env = self.loader.load_asset("environments", epic.environment, EnvironmentConfig)
        
        # --- COMPLEXITY GATE (iDesign Enforcement) ---
        threshold = 7
        if self.org and self.org.architecture:
            threshold = self.org.architecture.idesign_threshold
            
        if len(epic.issues) > threshold and not epic.architecture_governance.idesign:
            raise ComplexityViolation(
                f"Complexity Gate Violation: Epic '{epic.name}' has {len(epic.issues)} issues "
                f"which exceeds the threshold of {threshold}. iDesign structure is REQUIRED."
            )


        run_id = session_id or str(uuid.uuid4())[:8]
        active_build = build_id or f"build-{sanitize_name(epic_name)}"
        
        if not self.sessions.get_session(run_id):
            self.sessions.start_session(run_id, {"type": "epic", "name": epic.name, "department": self.department, "task_input": epic.description})
        
        existing = await self.async_cards.get_by_build(active_build)
        if existing:
            if target_issue_id:
                # Only reset the target issue if it exists in DB
                if any(ex.id == target_issue_id for ex in existing):
                    await self.async_cards.update_status(target_issue_id, CardStatus.READY)
            else:
                await self.async_cards.reset_build(active_build)
        
        for i in epic.issues:
            if not any(ex.id == i.id for ex in existing):
                card_data = i.model_dump(by_alias=True)
                card_data.update({"session_id": run_id, "build_id": active_build, "sprint": get_eos_sprint(), "status": CardStatus.READY})
                await self.async_cards.save(card_data)

        log_event("session_start", {"epic": epic.name, "run_id": run_id, "build_id": active_build}, workspace=self.workspace)
        
        # Delegate traction loop to the Orchestrator
        await self.orchestrator.execute_epic(
            active_build=active_build,
            run_id=run_id,
            epic=epic,
            team=team,
            env=env,
            target_issue_id=target_issue_id
        )
        
        # Sync the transcript from orchestrator for session reporting
        self.transcript = self.orchestrator.transcript
        
        legacy_transcript = [
            {"step_index": i, "role": t.role, "issue": t.issue_id, "summary": t.content, "note": t.note}
            for i, t in enumerate(self.transcript)
        ]
        self.sessions.complete_session(run_id, "done", legacy_transcript)
        log_event("session_end", {"run_id": run_id}, workspace=self.workspace)
        self.snapshots.record(run_id, {"epic": epic.model_dump(), "team": team.model_dump(), "env": env.model_dump(), "build_id": active_build}, legacy_transcript)

        # Clear active log for UI cleanliness
        root_log = Path("workspace/default/orket.log")
        if root_log.exists():
            root_log.write_text("", encoding="utf-8")

        return legacy_transcript

    async def run_rock(self, rock_name: str, build_id: str = None, session_id: str = None, driver_steered: bool = False, **kwargs) -> Dict:
        rock = self.loader.load_asset("rocks", rock_name, RockConfig)
        sid = session_id or str(uuid.uuid4())[:8]
        active_build = build_id or f"rock-build-{sanitize_name(rock_name)}"
        results = []
        for entry in rock.epics:
            epic_ws = self.workspace / entry["epic"]
            sub_pipeline = ExecutionPipeline(epic_ws, entry["department"], db_path=self.db_path, config_root=self.config_root)
            res = await sub_pipeline.run_epic(entry["epic"], build_id=active_build, session_id=sid, driver_steered=driver_steered)
            results.append({"epic": entry["epic"], "transcript": res})
        
        # --- TRIGGER BUG FIX PHASE ---
        print(f"  [PHASE] Rock '{rock.name}' complete. Starting Bug Fix Phase...")
        await self.bug_fix_manager.start_phase(rock.id)
        
        return {"rock": rock.name, "results": results}

    def _find_parent_epic(self, issue_id: str) -> tuple[EpicConfig | None, str | None, IssueConfig | None]:
        for ename in self.loader.list_assets("epics"):
            try:
                epic = self.loader.load_asset("epics", ename, EpicConfig)
                for i in epic.issues:
                    if i.id == issue_id: return epic, ename, i
            except (FileNotFoundError, ValueError, CardNotFound): continue
        return None, None, None

    async def verify_issue(self, issue_id: str) -> Any:
        """Runs empirical verification via the Orchestrator."""
        return await self.orchestrator.verify_issue(issue_id)



        if iteration_count >= max_iterations:
            raise ExecutionFailed(f"Traction Loop exhausted iterations ({max_iterations}) without completion.")

# Shims
async def orchestrate_card(card_id: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(card_id, **kwargs)

async def orchestrate(epic_name: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_epic(epic_name, **kwargs)

async def orchestrate_rock(rock_name: str, workspace: Path, **kwargs) -> Dict[str, Any]:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_rock(rock_name, **kwargs)