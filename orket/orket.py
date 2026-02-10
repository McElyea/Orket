# orket/orket.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import json
import uuid
import asyncio
from datetime import datetime, UTC

from orket.llm import LocalModelProvider
from orket.logging import log_event
from orket.state import runtime_state
from orket.agents.agent import Agent
from orket.policy import create_session_policy
from orket.tools import ToolBox, get_tool_map
from orket.schema import EpicConfig, TeamConfig, EnvironmentConfig, RockConfig, IssueConfig, CardStatus, SkillConfig, DialectConfig, RoleConfig, CardType
from orket.utils import get_eos_sprint, sanitize_name
from orket.exceptions import CardNotFound, ExecutionFailed, StateConflict
from orket.infrastructure.sqlite_repositories import SQLiteSessionRepository, SQLiteSnapshotRepository
from orket.infrastructure.async_card_repository import AsyncCardRepository
from orket.orchestration.turn_executor import TurnExecutor
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from orket.domain.bug_fix_phase import BugFixPhaseManager
from orket.services.webhook_db import WebhookDatabase
from orket.domain.sandbox import SandboxRegistry, SandboxStatus
from orket.domain.execution import ExecutionTurn
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
        paths = [
            self.config_dir / "organization.json",
            self.model_dir / "organization.json"
        ]
        for p in paths:
            if p.exists():
                return OrganizationConfig.model_validate_json(p.read_text(encoding="utf-8"))
        return None

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
        # 1. Unified Config
        paths = [
            self.config_dir / category / f"{name}.json",
            self.model_dir / self.department / category / f"{name}.json",
            self.model_dir / "core" / category / f"{name}.json"
        ]
        
        for p in paths:
            if p.exists():
                return model_type.model_validate_json(p.read_text(encoding="utf-8"))
        
        raise CardNotFound(f"Asset '{name}' not found in category '{category}' for department '{self.department}'.")

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
    def __init__(self, workspace: Path, department: str = "core", db_path: str = "orket_persistence.db", config_root: Optional[Path] = None):
        self.workspace = workspace
        self.department = department
        self.config_root = config_root or Path(".").resolve()
        self.loader = ConfigLoader(self.config_root, department)
        self.db_path = db_path
        
        # Load Organization
        self.org = self.loader.load_organization()
        
        # Async-native repository
        self.async_cards = AsyncCardRepository(self.db_path)
        
        self.sessions = SQLiteSessionRepository(self.db_path)
        self.snapshots = SQLiteSnapshotRepository(self.db_path)
        
        self.notes = NoteStore()
        self.transcript = []
        self.sandbox_orchestrator = SandboxOrchestrator(self.workspace)
        self.webhook_db = WebhookDatabase()
        self.bug_fix_manager = BugFixPhaseManager(
            organization_config=self.org.process_rules if self.org else {},
            db=self.webhook_db
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
            raise ExecutionFailed(
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
                if any(ex["id"] == target_issue_id for ex in existing):
                    await self.async_cards.update_status(target_issue_id, CardStatus.READY)
            else:
                await self.async_cards.reset_build(active_build)
        
        for i in epic.issues:
            if not any(ex["id"] == i.id for ex in existing):
                card_data = i.model_dump()
                card_data.update({"session_id": run_id, "build_id": active_build, "sprint": get_eos_sprint(), "status": CardStatus.READY})
                await self.async_cards.save(card_data)

        log_event("session_start", {"epic": epic.name, "run_id": run_id, "build_id": active_build}, workspace=self.workspace)
        await self._traction_loop(active_build, run_id, epic, team, env, driver_steered, target_issue_id)
        
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

    async def verify_issue(self, issue_id: str) -> VerificationResult:
        """
        Runs empirical verification for a specific issue.
        Loads the configuration, executes the 'FIT' fixtures, and updates persistence.
        """
        # 1. Load the latest IssueConfig from DB
        issue_data = await self.async_cards.get_by_id(issue_id)
        if not issue_data:
            raise CardNotFound(f"Cannot verify non-existent issue {issue_id}")
            
        # Re-hydrate into IssueConfig object
        from orket.schema import IssueConfig
        from orket.domain.verification import VerificationResult
        issue = IssueConfig.model_validate(issue_data)
        
        # 2. Execute Verification (Fixtures)
        from orket.domain.verification import VerificationEngine
        print(f"  [VERIFIER] Running empirical tests for {issue_id}...")
        result = VerificationEngine.verify(issue.verification, self.workspace)
        
        # 3. Optional: Execute Sandbox Verification (HTTP)
        rock_id = issue.build_id # Simplification for mapping
        sandbox = self.sandbox_orchestrator.registry.get(f"sandbox-{rock_id}")
        if sandbox and sandbox.status == SandboxStatus.RUNNING:
            print(f"  [VERIFIER] Running sandbox HTTP tests for {issue_id}...")
            sb_result = await VerificationEngine.verify_sandbox(sandbox, issue.verification)
            # Merge results
            result.passed += sb_result.passed
            result.failed += sb_result.failed
            result.total_scenarios += sb_result.total_scenarios
            result.logs.extend(sb_result.logs)

        # 4. Update the Issue with the new verification state
        issue.verification.last_run = result
        
        # Save back to database
        await self.async_cards.save(issue.model_dump())
        
        return result

    async def _traction_loop(self, active_build: str, run_id: str, epic: EpicConfig, team: TeamConfig, env: EnvironmentConfig, driver_steered: bool, target_issue_id: str = None):
        policy = create_session_policy(str(self.workspace), epic.references)
        toolbox = ToolBox(policy, str(self.workspace), epic.references, db_path=self.db_path)
        tool_map = get_tool_map(toolbox)
        
        from orket.orchestration.models import ModelSelector
        from orket.domain.state_machine import StateMachine, StateMachineError
        from orket.settings import load_user_settings
        from orket.schema import RoleConfig, CardType, CardStatus
        
        # Load settings relative to config_root for tests
        settings_path = self.config_root / "user_settings.json"
        user_settings = {}
        if settings_path.exists():
            user_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        else:
            user_settings = load_user_settings()

        model_selector = ModelSelector(organization=self.org, user_settings=user_settings)

        print(f"  [ANTICIPATOR] Scanning Epic '{epic.name}' for critical path risks...")

        while True:
            backlog = await self.async_cards.get_by_build(active_build)
            
            # Prioritize Code Review over Ready work
            in_review = [i for i in backlog if i["status"] == CardStatus.CODE_REVIEW]
            ready = [i for i in backlog if i["status"] == CardStatus.READY]
            
            if target_issue_id:
                target = next((i for i in backlog if i["id"] == target_issue_id), None)
                if target and target["status"] in [CardStatus.READY, CardStatus.CODE_REVIEW]:
                    candidates = [target]
                else: candidates = []
            else:
                candidates = in_review + ready

            if not candidates: break
            
            issue = candidates[0]
            issue_id = issue["id"]
            original_seat = issue["seat"]
            is_review_turn = issue["status"] == CardStatus.CODE_REVIEW
            
            # 1. Determine the active seat for this turn
            seat_name = original_seat
            if is_review_turn:
                # RUN EMPIRICAL VERIFICATION (FIT)
                verification_result = await self.verify_issue(issue_id)
                
                # Inject verification result as a note from the system
                v_msg = f"EMPIRICAL VERIFICATION RESULT: {verification_result.passed}/{verification_result.total_scenarios} Passed."
                if verification_result.failed > 0:
                    v_msg += f" Failures: {verification_result.failed}."
                self.notes.add(Note(from_role="system", content=v_msg, step_index=len(self.transcript)))
                
                # Find a seat with the 'integrity_guard' role
                verifier_seat = next((name for name, s in team.seats.items() if "integrity_guard" in s.roles), None)
                if verifier_seat:
                    seat_name = verifier_seat
                else:
                    # Fallback: original seat but we will force the role later
                    print(f"  [WARN] No explicit verifier seat in team. Falling back to {seat_name} for review.")

            governance_retries = 0
            all_hands_on_deck = False

            seat_obj = team.seats.get(sanitize_name(seat_name))
            if not seat_obj:
                await self.async_cards.update_status(issue_id, CardStatus.CANCELED)
                continue

            # 2. Determine and record the status for this turn
            current_status = issue["status"]
            if not is_review_turn:
                # Execution turns MUST be in_progress
                await self.async_cards.update_status(issue_id, CardStatus.IN_PROGRESS, assignee=seat_name)
                current_status = CardStatus.IN_PROGRESS
            else:
                # Review turns stay in code_review
                await self.async_cards.update_status(issue_id, CardStatus.CODE_REVIEW, assignee=seat_name)
                current_status = CardStatus.CODE_REVIEW

            success = False
            last_violation = None

            while governance_retries < 2:
                # Action B: Summon all roles if first retry failed
                roles_to_load = list(seat_obj.roles) if not all_hands_on_deck else list(team.roles.keys())
                
                # Force integrity_guard role if it's a review turn and not already there
                if is_review_turn and "integrity_guard" not in roles_to_load:
                    roles_to_load = ["integrity_guard"] + list(roles_to_load)

                role_configs = []
                for r_name in roles_to_load:
                    try: role_configs.append(self.loader.load_asset("roles", r_name, RoleConfig))
                    except (FileNotFoundError, ValueError, CardNotFound): pass

                selected_model = model_selector.select(role=roles_to_load[0], asset_config=epic)
                dialect_name = model_selector.get_dialect_name(selected_model)
                dialect = self.loader.load_asset("dialects", dialect_name, DialectConfig)
                provider = LocalModelProvider(model=selected_model, temperature=env.temperature, timeout=env.timeout)

                # Convert primary Role to Skill for compiler
                primary_role = role_configs[0]
                skill = SkillConfig(
                    name=primary_role.name or primary_role.summary or seat_name,
                    intent=primary_role.description,
                    responsibilities=[ro.description for ro in role_configs],
                    idesign_constraints=self.org.architecture.cicd_rules if self.org else [],
                    tools=primary_role.tools
                )

                patch = ""
                if is_review_turn:
                    patch += "\n[PROTOCOL: CODE REVIEW] This card is currently in CODE_REVIEW. Evaluate the work and finalize to 'DONE' if satisfied.\n"
                if all_hands_on_deck:
                    patch += "\n[CRITICAL] ALL HANDS ON DECK: Previous turns failed governance. All team personas are now active.\n"
                
                relevant_notes = self.notes.get_for_role(seat_name, len(self.transcript))
                if relevant_notes:
                    patch += "\n[INTER-AGENT NOTES]\n" + "\n".join([f"- From {n.from_role}: {n.content}" for n in relevant_notes])

                if self.org:
                    patch += f"\n[ORGANIZATION: {self.org.name}]\nEthos: {self.org.ethos}\n"

                system_desc = PromptCompiler.compile(skill, dialect, patch=patch)

                # Aggregate tools
                tools = {}
                for ro in role_configs:
                    for tn in ro.tools:
                        if tn in tool_map:
                            tools[tn] = tool_map[tn]

                print(f"  [ORKESTRATE] {seat_name} -> {issue_id} ({'REVIEW' if is_review_turn else 'EXECUTE'}) (Model: {selected_model})")

                # --- TOOL GATE: Mechanical Enforcement at tool level ---
                from orket.services.tool_gate import ToolGate
                tool_gate = ToolGate(organization=self.org, workspace_root=self.workspace)

                agent = Agent(seat_name, system_desc, tools, provider, config_root=self.config_root, tool_gate=tool_gate)
                turn: ExecutionTurn = await agent.run(
                    task={"description": f"{epic.description}\n\nTask: {issue['summary']}"},
                    context={
                        "session_id": run_id,
                        "issue_id": issue_id,
                        "workspace": str(self.workspace),
                        "role": seat_name,
                        "roles": roles_to_load,
                        "current_status": current_status.value
                    },
                    workspace=self.workspace,
                    transcript=[{"role": t.role, "summary": t.content} for t in self.transcript]
                )

                # --- MECHANICAL ENFORCEMENT (Teeth) ---
                violation = None
                
                # 1. State Machine Validation
                for call in turn.tool_calls:
                    if call.tool == "update_issue_status":
                        try:
                            req_status = CardStatus(call.args.get("status"))
                            # Apply StateMachine check with active roles
                            if not self.org or not self.org.bypass_governance:
                                StateMachine.validate_transition(CardType.ISSUE, current_status, req_status, roles=roles_to_load)
                        except Exception as e:
                            violation = str(e)
                            break
                
                # 2. iDesign Structural Validation
                if not violation and epic.architecture_governance.idesign:
                    from orket.services.idesign_validator import iDesignValidator
                    violation = iDesignValidator.validate_turn(turn, self.workspace)

                if violation:
                    governance_retries += 1
                    last_violation = violation
                    print(f"  [GOVERNANCE] Turn failed: {violation} (Retry {governance_retries}/2)")
                    
                    if governance_retries == 1:
                        self.notes.add(Note(from_role="system", content=f"GOVERNANCE ERROR: {violation}. Re-attempting task with strict adherence to policy.", step_index=len(self.transcript)))
                        continue
                    else:
                        all_hands_on_deck = True
                        self.notes.add(Note(from_role="system", content=f"CRITICAL BLOCK: {violation}. All team personas are now active to resolve this block.", step_index=len(self.transcript)))
                        continue

                # Success!
                self.transcript.append(turn)
                success = True
                break

            # --- HANDLE RESULTS ---
            if not success:
                # Retries exhausted
                from orket.domain.failure_reporter import FailureReporter
                await FailureReporter.generate_report(self.workspace, run_id, issue_id, last_violation or "Unknown failure", self.transcript)
                await self.async_cards.update_status(issue_id, CardStatus.BLOCKED)
                self.sessions.complete_session(run_id, "failed", self.transcript)
                raise ExecutionFailed(f"Governance Policy Violation: {last_violation}. Card {issue_id} is now BLOCKED.")

            # Turn succeeded, check if we need a final status update
            current_db_issue = await self.async_cards.get_by_id(issue_id)
            if current_db_issue["status"] == CardStatus.IN_PROGRESS:
                if not is_review_turn:
                    # Auto-move to review if execution turn didn't update status
                    await self.async_cards.update_status(issue_id, CardStatus.CODE_REVIEW)

    async def _save_checkpoint(self, run_id: str, epic: EpicConfig, team: TeamConfig, env: EnvironmentConfig, active_build: str):
        """Saves current state snapshot for crash recovery."""
        snapshot_data = {
            "epic": epic.model_dump(),
            "team": team.model_dump(),
            "env": env.model_dump(),
            "build_id": active_build,
            "timestamp": datetime.now(UTC).isoformat()
        }
        legacy_transcript = [
            {"role": t.role, "issue": t.issue_id, "content": t.content}
            for t in self.transcript
        ]
        self.snapshots.record(run_id, snapshot_data, legacy_transcript)

    async def _trigger_sandbox(self, epic: EpicConfig):
        """Helper to trigger sandbox deployment."""
        from orket.domain.sandbox import TechStack, SandboxStatus
        rock_id = epic.parent_id or epic.id
        
        # Check if already running to avoid spam
        existing = self.sandbox_orchestrator.registry.get(f"sandbox-{rock_id}")
        if existing and existing.status == SandboxStatus.RUNNING:
            return

        print(f"  [SANDBOX] Deploying environment for {rock_id}...")
        try:
            await self.sandbox_orchestrator.create_sandbox(
                rock_id=rock_id,
                project_name=epic.name,
                tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
                workspace_path=str(self.workspace)
            )
        except Exception as e:
            print(f"  [SANDBOX] WARN: Deployment failed: {e}")

    async def _traction_loop(self, active_build: str, run_id: str, epic: EpicConfig, team: TeamConfig, env: EnvironmentConfig, driver_steered: bool, target_issue_id: str = None):
        """
        The reconstructed Traction Loop.
        Uses TurnExecutor and handles loop logic with proper async patterns.
        """
        from orket.orchestration.models import ModelSelector
        from orket.domain.state_machine import StateMachine
        from orket.settings import load_user_settings
        from orket.services.tool_gate import ToolGate
        
        # 1. Setup Environment
        settings_path = self.config_root / "user_settings.json"
        user_settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else load_user_settings()
        model_selector = ModelSelector(organization=self.org, user_settings=user_settings)
        
        tool_gate = ToolGate(organization=self.org, workspace_root=self.workspace)
        executor = TurnExecutor(StateMachine(), tool_gate, self.workspace)
        
        # Aggregated ToolBox
        policy = create_session_policy(str(self.workspace), epic.references)
        toolbox = ToolBox(policy, str(self.workspace), epic.references, db_path=self.db_path)
        tool_map = get_tool_map(toolbox)

        # Mock ModelClient for now (to be replaced with real async provider integration)
        class AsyncModelClient:
            def __init__(self, provider): self.provider = provider
            async def complete(self, messages): return await self.provider.complete(messages)

        print(f"  [RECONSTRUCTION] Entering Traction Loop for '{epic.name}'")
        iteration_count = 0
        max_iterations = 10

        while iteration_count < max_iterations:
            iteration_count += 1
            backlog = await self.async_cards.get_by_build(active_build)
            
            # Prioritize Code Review over Ready work
            in_review = [i for i in backlog if i["status"] == CardStatus.CODE_REVIEW]
            ready = [i for i in backlog if i["status"] == CardStatus.READY]
            
            if target_issue_id:
                target = next((i for i in backlog if i["id"] == target_issue_id), None)
                candidates = [target] if target and target["status"] in [CardStatus.READY, CardStatus.CODE_REVIEW] else []
            else:
                candidates = in_review + ready

            if not candidates: break
            
            issue_data = candidates[0]
            issue = IssueConfig.model_validate(issue_data)
            is_review_turn = issue.status == CardStatus.CODE_REVIEW
            
            # Select Seat & Role
            seat_name = issue.seat
            if is_review_turn:
                # RUN EMPIRICAL VERIFICATION (FIT)
                verification_result = await self.verify_issue(issue.id)
                v_msg = f"EMPIRICAL VERIFICATION RESULT: {verification_result.passed}/{verification_result.total_scenarios} Passed."
                self.notes.add(Note(from_role="system", content=v_msg, step_index=len(self.transcript)))
                
                verifier_seat = next((name for name, s in team.seats.items() if "integrity_guard" in s.roles), None)
                if verifier_seat: seat_name = verifier_seat

            seat_obj = team.seats.get(sanitize_name(seat_name))
            if not seat_obj:
                await self.async_cards.update_status(issue.id, CardStatus.CANCELED)
                continue

            # Determine target status for this turn
            turn_status = CardStatus.IN_PROGRESS if not is_review_turn else CardStatus.CODE_REVIEW
            
            # Update status to reflect active work
            await self.async_cards.update_status(issue.id, turn_status, assignee=seat_name)

            # Prepare Role
            roles_to_load = list(seat_obj.roles)
            if is_review_turn and "integrity_guard" not in roles_to_load:
                roles_to_load = ["integrity_guard"] + roles_to_load

            role_config = self.loader.load_asset("roles", roles_to_load[0], RoleConfig)
            
            # Select Model
            selected_model = model_selector.select(role=roles_to_load[0], asset_config=epic)
            dialect_name = model_selector.get_dialect_name(selected_model)
            dialect = self.loader.load_asset("dialects", dialect_name, DialectConfig)
            provider = LocalModelProvider(model=selected_model, temperature=env.temperature, timeout=env.timeout)
            client = AsyncModelClient(provider)

            # Compile Prompt
            skill = SkillConfig(
                name=role_config.name or seat_name,
                intent=role_config.description,
                responsibilities=[ro.description for ro in [role_config]],
                tools=role_config.tools
            )
            system_desc = PromptCompiler.compile(skill, dialect)

            context = {
                "session_id": run_id,
                "issue_id": issue.id,
                "workspace": str(self.workspace),
                "role": seat_name,
                "roles": roles_to_load,
                "current_status": turn_status.value,
                "history": [{"role": t.role, "content": t.content} for t in self.transcript[-5:]] # Windowed history
            }

            print(f"  [ORKESTRATE] {seat_name} -> {issue.id} ({issue.status.value})")

            # EXECUTE TURN
            result = await executor.execute_turn(issue, role_config, client, toolbox, context, system_prompt=system_desc)

            if result.success:
                print(f"    [DEBUG] Turn succeeded. Tool calls: {[tc.tool for tc in result.turn.tool_calls]}")
                self.transcript.append(result.turn)
                # Check for CODE_REVIEW transition
                updated_issue = await self.async_cards.get_by_id(issue.id)
                if updated_issue["status"] == CardStatus.CODE_REVIEW:
                    await self._trigger_sandbox(epic)
                
                # Auto-transition if not already updated by tool calls and not already in review
                if updated_issue["status"] == issue.status and not is_review_turn:
                    await self.async_cards.update_status(issue.id, CardStatus.CODE_REVIEW)
                    await self._trigger_sandbox(epic)
                
                # --- MEMORY HYGIENE ---
                await provider.clear_context()
                
                # --- CHECKPOINT ---
                await self._save_checkpoint(run_id, epic, team, env, active_build)
            else:
                print(f"  [FAILURE] Turn failed: {result.error}")
                # --- GENERATE POLICY REPORT ---
                from orket.domain.failure_reporter import FailureReporter
                await FailureReporter.generate_report(
                    workspace=self.workspace,
                    session_id=run_id,
                    card_id=issue.id,
                    violation=result.error or "Unknown failure",
                    transcript=self.transcript,
                    roles=roles_to_load
                )
                await self.async_cards.update_status(issue.id, CardStatus.BLOCKED)
                break

        if iteration_count >= max_iterations:
            raise ExecutionFailed(f"Traction Loop exhausted iterations ({max_iterations}) without completion.")

# Shims
async def orchestrate_card(card_id: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(card_id, **kwargs)

async def orchestrate(epic_name: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_epic(epic_name, **kwargs)

async def orchestrate_rock(rock_name: str, workspace: Path, **kwargs) -> Dict[str, Any]:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_rock(rock_name, **kwargs)