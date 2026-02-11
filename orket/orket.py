# orket/orket.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, UTC
from functools import lru_cache

from orket.llm import LocalModelProvider
from orket.logging import log_event
from orket.state import runtime_state
from orket.policy import create_session_policy
from orket.tools import ToolBox, get_tool_map
from orket.schema import EpicConfig, TeamConfig, EnvironmentConfig, RockConfig, IssueConfig, CardStatus, SkillConfig, DialectConfig, RoleConfig, CardType
from orket.utils import get_eos_sprint, sanitize_name
from orket.exceptions import CardNotFound, ComplexityViolation
from orket.infrastructure.async_repositories import AsyncSessionRepository, AsyncSnapshotRepository, AsyncSuccessRepository
from orket.infrastructure.async_card_repository import AsyncCardRepository
from orket.infrastructure.async_file_tools import AsyncFileTools
from orket.orchestration.turn_executor import TurnExecutor
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.domain.sandbox import SandboxRegistry, SandboxStatus
from orket.services.prompt_compiler import PromptCompiler
from pydantic import BaseModel, ValidationError

# ---------------------------------------------------------------------------
# 1. Configuration & Asset Loading (Application Service)
# ---------------------------------------------------------------------------

class ConfigLoader:
    """
    Unified Configuration and Asset Loader.
    Priority: 1. config/ (Unified) 2. model/{dept}/ (Legacy) 3. model/core/ (Fallback)
    """
    def __init__(
        self,
        root: Path,
        department: str = "core",
        organization: Optional[Any] = None,
        decision_nodes: Optional[DecisionNodeRegistry] = None,
    ):
        self.root = root
        self.config_dir = root / "config"
        self.model_dir = root / "model"
        self.department = department
        self.organization = organization
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.loader_strategy_node = self.decision_nodes.resolve_loader_strategy(self.organization)
        self.file_tools = AsyncFileTools(self.root)

    def _run_async(self, coro):
        """Run async file ops from sync callers without nested-loop failures."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()

    async def _read_text(self, p: Path) -> str:
        try:
            relative_path = p.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            relative_path = str(p)
        return await self.file_tools.read_file(relative_path)

    def load_organization(self) -> Optional[OrganizationConfig]:
        return self._run_async(self.load_organization_async())

    async def load_organization_async(self) -> Optional[OrganizationConfig]:
        from orket.schema import OrganizationConfig
        from orket.settings import get_setting
        
        org_data = {}
        
        # 1. Try Modular Configs (New Standard)
        info_path, arch_path = self.loader_strategy_node.organization_modular_paths(self.config_dir)
        
        if info_path.exists() and arch_path.exists():
            try:
                info = json.loads(await self._read_text(info_path))
                arch = json.loads(await self._read_text(arch_path))
                org_data = {**info, **arch}
            except (json.JSONDecodeError, OSError, TypeError, ValueError) as e:
                log_event("config_error", {"error": f"Failed to load modular config: {e}"})

        # 2. Key Fallback: Monolith (Legacy)
        if not org_data:
            paths = self.loader_strategy_node.organization_fallback_paths(self.config_dir, self.model_dir)
            for p in paths:
                if p.exists():
                    try:
                        org_data = json.loads(await self._read_text(p))
                        break
                    except (json.JSONDecodeError, OSError, TypeError, ValueError):
                        continue
        
        if not org_data:
            return None

        # Validate
        try:
            org = OrganizationConfig.model_validate(org_data)
        except (ValidationError, ValueError, TypeError) as e:
            # Fallback or strict fail? Strict fail for now but log it.
            print(f"[CONFIG] Validation failed: {e}")
            return None
        
        # Overrides
        return self.loader_strategy_node.apply_organization_overrides(org, get_setting)

    def load_department(self, name: str) -> Optional[DepartmentConfig]:
        return self._run_async(self.load_department_async(name))

    async def load_department_async(self, name: str) -> Optional[DepartmentConfig]:
        from orket.schema import DepartmentConfig
        paths = self.loader_strategy_node.department_paths(self.config_dir, self.model_dir, name)
        for p in paths:
            if p.exists():
                raw = await self._read_text(p)
                return DepartmentConfig.model_validate_json(raw)
        return None

    def load_asset(self, category: str, name: str, model_type: Type[BaseModel]) -> Any:
        return self._run_async(self.load_asset_async(category, name, model_type))

    async def load_asset_async(self, category: str, name: str, model_type: Type[BaseModel]) -> Any:
        raw = await self._load_asset_raw_async(category, name, self.department)
        return model_type.model_validate_json(raw)

    @lru_cache(maxsize=256)
    def _load_asset_raw(self, category: str, name: str, dept: str) -> str:
        return self._run_async(self._load_asset_raw_async(category, name, dept))

    async def _load_asset_raw_async(self, category: str, name: str, dept: str) -> str:
        paths = self.loader_strategy_node.asset_paths(
            self.config_dir,
            self.model_dir,
            dept,
            category,
            name,
        )
        
        for p in paths:
            if p.exists():
                return await self._read_text(p)
        
        raise CardNotFound(f"Asset '{name}' not found in category '{category}' for department '{dept}'.")

    def list_assets(self, category: str) -> List[str]:
        return self._run_async(self.list_assets_async(category))

    async def list_assets_async(self, category: str) -> List[str]:
        def _collect_assets() -> List[str]:
            assets = set()
            search_paths = self.loader_strategy_node.list_asset_search_paths(
                self.config_dir,
                self.model_dir,
                self.department,
                category,
            )
            for p in search_paths:
                if p.exists():
                    for f in p.glob("*.json"):
                        assets.add(f.stem)
            return sorted(list(assets))

        return await asyncio.to_thread(_collect_assets)

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
                 sessions_repo: Optional[AsyncSessionRepository] = None,
                 snapshots_repo: Optional[AsyncSnapshotRepository] = None,
                 success_repo: Optional[AsyncSuccessRepository] = None,
                 decision_nodes: Optional[DecisionNodeRegistry] = None):
        self.workspace = workspace
        self.department = department
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.config_root = config_root or Path(".").resolve()
        self.loader = ConfigLoader(self.config_root, department, decision_nodes=self.decision_nodes)
        self.db_path = db_path
        
        # Load Organization
        self.org = self.loader.load_organization()
        self.execution_runtime_node = self.decision_nodes.resolve_execution_runtime(self.org)
        self.pipeline_wiring_node = self.decision_nodes.resolve_pipeline_wiring(self.org)
        
        # Injected or default repositories
        self.async_cards = cards_repo or AsyncCardRepository(self.db_path)
        self.sessions = sessions_repo or AsyncSessionRepository(self.db_path)
        self.snapshots = snapshots_repo or AsyncSnapshotRepository(self.db_path)
        self.success = success_repo or AsyncSuccessRepository(self.db_path)
        
        self.notes = NoteStore()
        self.transcript = []
        self.sandbox_orchestrator = self.pipeline_wiring_node.create_sandbox_orchestrator(
            workspace=self.workspace,
            organization=self.org,
        )
        self.webhook_db = self.pipeline_wiring_node.create_webhook_database()
        self.bug_fix_manager = self.pipeline_wiring_node.create_bug_fix_manager(
            organization=self.org,
            webhook_db=self.webhook_db,
        )
        self.orchestrator = self.pipeline_wiring_node.create_orchestrator(
            workspace=self.workspace,
            async_cards=self.async_cards,
            snapshots=self.snapshots,
            org=self.org,
            config_root=self.config_root,
            db_path=self.db_path,
            loader=self.loader,
            sandbox_orchestrator=self.sandbox_orchestrator,
        )

    async def run_card(self, card_id: str, **kwargs) -> Any:
        epics = await self.loader.list_assets_async("epics")
        if card_id in epics:
            return await self.run_epic(card_id, **kwargs)
        
        rocks = await self.loader.list_assets_async("rocks")
        if card_id in rocks:
            return await self.run_rock(card_id, **kwargs)

        parent_epic, parent_ename, target_issue = await self._find_parent_epic(card_id)
        if not parent_epic: raise CardNotFound(f"Card {card_id} not found.")
        print(f"  [PIPELINE] Executing Atomic Issue: {card_id} (Parent: {parent_epic.name})")
        return await self.run_epic(parent_ename, target_issue_id=card_id, **kwargs)

    async def run_epic(self, epic_name: str, build_id: str = None, session_id: str = None, driver_steered: bool = False, target_issue_id: str = None, **kwargs) -> List[Dict]:
        epic = await self.loader.load_asset_async("epics", epic_name, EpicConfig)
        team = await self.loader.load_asset_async("teams", epic.team, TeamConfig)
        env = await self.loader.load_asset_async("environments", epic.environment, EnvironmentConfig)
        
        # --- COMPLEXITY GATE (iDesign Enforcement) ---
        threshold = 7
        if self.org and self.org.architecture:
            threshold = self.org.architecture.idesign_threshold
            
        if len(epic.issues) > threshold and not epic.architecture_governance.idesign:
            raise ComplexityViolation(
                f"Complexity Gate Violation: Epic '{epic.name}' has {len(epic.issues)} issues "
                f"which exceeds the threshold of {threshold}. iDesign structure is REQUIRED."
            )


        run_id = self.execution_runtime_node.select_run_id(session_id)
        active_build = self.execution_runtime_node.select_epic_build_id(build_id, epic_name, sanitize_name)
        
        if not await self.sessions.get_session(run_id):
            await self.sessions.start_session(run_id, {"type": "epic", "name": epic.name, "department": self.department, "task_input": epic.description})
        
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
        await self.sessions.complete_session(run_id, "done", legacy_transcript)
        log_event("session_end", {"run_id": run_id}, workspace=self.workspace)
        await self.snapshots.record(run_id, {"epic": epic.model_dump(), "team": team.model_dump(), "env": env.model_dump(), "build_id": active_build}, legacy_transcript)

        # --- IRREVERSIBLE SUCCESS CRITERION ---
        backlog = await self.async_cards.get_by_build(active_build)
        is_truly_done = all(i.status in [CardStatus.DONE, CardStatus.CANCELED] for i in backlog)
        if is_truly_done:
            # We record a WIN
            await self.success.record_success(
                session_id=run_id,
                success_type="EPIC_COMPLETED",
                artifact_ref=f"build:{active_build}",
                human_ack=None # Pending judge approval
            )
            log_event("success_recorded", {"run_id": run_id, "type": "EPIC_COMPLETED"}, workspace=self.workspace)

        # Clear active log for UI cleanliness
        root_log = Path("workspace/default/orket.log")
        if root_log.exists():
            await self.loader.file_tools.write_file("workspace/default/orket.log", "")

        return legacy_transcript

    async def run_rock(self, rock_name: str, build_id: str = None, session_id: str = None, driver_steered: bool = False, **kwargs) -> Dict:
        rock = await self.loader.load_asset_async("rocks", rock_name, RockConfig)
        sid = self.execution_runtime_node.select_rock_session_id(session_id)
        active_build = self.execution_runtime_node.select_rock_build_id(build_id, rock_name, sanitize_name)
        results = []
        for entry in rock.epics:
            epic_ws = self.workspace / entry["epic"]
            sub_pipeline = self.pipeline_wiring_node.create_sub_pipeline(
                parent_pipeline=self,
                epic_workspace=epic_ws,
                department=entry["department"],
            )
            res = await sub_pipeline.run_epic(entry["epic"], build_id=active_build, session_id=sid, driver_steered=driver_steered)
            results.append({"epic": entry["epic"], "transcript": res})
        
        # --- TRIGGER BUG FIX PHASE ---
        print(f"  [PHASE] Rock '{rock.name}' complete. Starting Bug Fix Phase...")
        await self.bug_fix_manager.start_phase(rock.id)
        
        return {"rock": rock.name, "results": results}

    async def _find_parent_epic(self, issue_id: str) -> tuple[EpicConfig | None, str | None, IssueConfig | None]:
        for ename in await self.loader.list_assets_async("epics"):
            try:
                epic = await self.loader.load_asset_async("epics", ename, EpicConfig)
                for i in epic.issues:
                    if i.id == issue_id: return epic, ename, i
            except (FileNotFoundError, ValueError, CardNotFound): continue
        return None, None, None

    async def verify_issue(self, issue_id: str) -> Any:
        """Runs empirical verification via the Orchestrator."""
        return await self.orchestrator.verify_issue(issue_id)

# Shims
async def orchestrate_card(card_id: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(card_id, **kwargs)

async def orchestrate(epic_name: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_epic(epic_name, **kwargs)

async def orchestrate_rock(rock_name: str, workspace: Path, **kwargs) -> Dict[str, Any]:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_rock(rock_name, **kwargs)
