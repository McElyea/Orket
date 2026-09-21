import argparse
import asyncio
import io
import json
import sys
from functools import partial
from pathlib import Path
from typing import Any

from orket.application.services.extension_catalog_commands import list_installed_extensions, prepare_extension_manager
from orket.application.services.protocol_command_service import ProtocolCommand, execute_protocol_command
from orket.application.services.runtime_console_service import read_console_line
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_execution_result_service import RuntimeExecutionCancelled
from orket.application.services.runtime_inspection_service import (
    emit_runtime_manifest,
    read_runtime_board,
    read_runtime_replay,
)
from orket.application.services.runtime_inspection_service import (
    resolve_runtime_path as _resolve_path,
)
from orket.application.services.runtime_result_lifetime import (
    close_runtime_owner,
    create_runtime_owner,
    open_runtime_owner,
)
from orket.application.services.runtime_result_projection import runtime_result_exit_code, runtime_result_lines
from orket.discovery import perform_first_run_setup, print_orket_manifest, run_startup_checks
from orket.extensions import ExtensionManager
from orket.interfaces.cli_arguments import parse_args
from orket.orchestration.engine import OrchestrationEngine


async def _finish_named_run(engine, result, *, cancelled=False) -> int:
    if await close_runtime_owner(engine) and not cancelled:
        raise asyncio.CancelledError("Runtime cleanup completed after caller cancellation")
    print("\n".join(runtime_result_lines(result)))
    return 130 if cancelled else runtime_result_exit_code(result)


async def _print_extensions_list(manager: ExtensionManager) -> None:
    extensions = await list_installed_extensions(manager)
    if not extensions:
        print("No extensions installed.")
        return

    print("Installed extensions:")
    for ext in extensions:
        print(f"- {ext.extension_id} ({ext.extension_version}) [{ext.source}]")
        if ext.manifest_entries:
            for workload in ext.manifest_entries:
                print(f"  workload: {workload.workload_id} ({workload.workload_version})")
        else:
            print("  workload: <none>")


async def _install_extension(args: argparse.Namespace, manager: ExtensionManager) -> None:
    repo = str(args.target or "").strip()
    if not repo:
        raise ValueError("extensions install requires a repo path/URL (e.g. 'orket runtime extensions install <repo>').")
    record = await manager.install_from_repo(repo=repo, ref=args.ref)
    print(f"Installed extension: {record.extension_id} ({record.extension_version})")
    if record.manifest_entries:
        print("Registered workloads:")
        for workload in record.manifest_entries:
            print(f"- {workload.workload_id} ({workload.workload_version})")


async def _run_extension_workload(args: argparse.Namespace, manager: ExtensionManager) -> None:
    workload_id = (args.subcommand or "").strip()
    if not workload_id:
        raise ValueError("run command requires a workload id (e.g. 'orket runtime run mystery_v1 --seed 123').")
    workspace = await _resolve_path(args.workspace)
    result = await manager.run_workload(
        workload_id=workload_id,
        input_config={"seed": args.seed},
        workspace=workspace,
        department=args.department,
    )
    print(f"Executed workload: {result.workload_id} ({result.workload_version})")
    print(f"Extension: {result.extension_id} ({result.extension_version})")
    print(f"Plan hash: {result.plan_hash}")
    print(f"Artifact root: {result.artifact_root}")
    print(f"Provenance: {result.provenance_path}")


def print_board(hierarchy: dict[str, Any]) -> None:
    print(f"\n{'=' * 60}\n ORKET PROJECT BOARD (The Card Hierarchy)\n{'=' * 60}")
    for rock in hierarchy["rocks"]:
        print(f"\n[ROCK] {rock['name']} (Status: {rock.get('status', 'on_track')})")
        for epic in rock.get("epics", []):
            if "error" in epic:
                print(f"  - [EPIC] {epic['name']} (Error: {epic['error']})")
                continue
            print(f"  - [EPIC] {epic['name']} (Status: {epic.get('status', 'planning')})")
            for issue in epic.get("issues", []):
                summary = issue.get("summary") or issue.get("name") or "Unnamed Unit"
                priority = issue.get("priority", "Medium")
                status = issue.get("status", "ready")
                print(f"    * [{issue['id']}] {summary} ({issue['seat']}) [Priority: {priority}, Status: {status}]")
    print(f"\n{'=' * 60}\n")


def _emit_startup_status(startup_status: dict[str, str] | None) -> None:
    if not isinstance(startup_status, dict):
        return
    if str(startup_status.get("reconciliation") or "").strip().lower() == "failed":
        print("[STARTUP WARNING] Structural reconciliation failed; continuing in degraded mode.", file=sys.stderr)


async def run_cli(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    engine = None
    try:
        startup_status = await run_startup_checks(perform_first_run_setup)
        _emit_startup_status(startup_status)
        args = parse_args() if argv is None and prog is None else parse_args(argv, prog=prog)
        extension_manager = await prepare_extension_manager()

        if args.command == "extensions":
            if args.subcommand == "list":
                await _print_extensions_list(extension_manager)
                return 0
            if args.subcommand == "install":
                await _install_extension(args, extension_manager)
                return 0
            raise ValueError(
                "Supported extensions commands: 'orket runtime extensions list' and "
                "'orket runtime extensions install <repo> [--ref <ref>]'."
            )

        if args.command == "run":
            await _run_extension_workload(args, extension_manager)
            return 0

        if args.command == "marshaller":
            from orket.marshaller.cli import (
                default_run_id,
                execute_marshaller_from_files,
                inspect_marshaller_attempt,
                list_marshaller_runs,
            )

            workspace_root = await _resolve_path()
            if args.subcommand == "list":
                result = await list_marshaller_runs(workspace_root, limit=max(1, int(args.marshaller_list_limit)))
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.subcommand == "inspect":
                run_id = str(args.target or "").strip()
                if not run_id:
                    raise ValueError(
                        "marshaller inspect requires target run_id "
                        "(e.g. 'orket runtime marshaller inspect <run_id>')."
                    )
                inspect_result = await inspect_marshaller_attempt(
                    workspace_root,
                    run_id=run_id,
                    attempt_index=args.marshaller_inspect_attempt,
                )
                print(json.dumps(inspect_result, indent=2, ensure_ascii=False))
                return 0

            request_raw = str(args.marshaller_request or "").strip()
            if not request_raw:
                raise ValueError("marshaller command requires --marshaller-request <path>.")
            if not args.marshaller_proposal:
                raise ValueError("marshaller command requires at least one --marshaller-proposal <path>.")
            proposal_paths = [await _resolve_path(str(item)) for item in args.marshaller_proposal]
            execution_result = await execute_marshaller_from_files(
                workspace_root=workspace_root,
                run_request_path=await _resolve_path(request_raw),
                proposal_paths=proposal_paths,
                run_id=str(args.marshaller_run_id or default_run_id()).strip(),
                allowed_paths=list(args.marshaller_allow_path or []),
                promote=bool(args.marshaller_promote),
                actor_id=args.marshaller_actor_id,
                actor_source=str(args.marshaller_actor_source or "cli"),
                branch=str(args.marshaller_branch or "main"),
            )
            print(json.dumps(execution_result, indent=2, ensure_ascii=False))
            return 0

        if args.command == "protocol":
            result = await execute_protocol_command(ProtocolCommand(
                action=str(args.subcommand or ""),
                workspace=Path(args.workspace),
                invocation_root=Path.cwd(),
                run_a=str(args.target or "").strip(),
                run_b=str(args.protocol_run_b or "").strip(),
                events_a=args.protocol_events_a,
                events_b=args.protocol_events_b,
                artifacts_a=args.protocol_artifacts_a,
                artifacts_b=args.protocol_artifacts_b,
                runs_root=args.protocol_runs_root,
                campaign_run_ids=tuple(args.protocol_campaign_run_id or ()),
                baseline_run_id=args.protocol_baseline_run_id,
                parity_session_ids=tuple(args.protocol_parity_session_id or ()),
                discover_limit=int(args.protocol_parity_discover_limit),
                sqlite_db=args.protocol_sqlite_db,
                strict=bool(args.protocol_strict),
                max_parity_mismatches=int(args.protocol_max_parity_mismatches),
            ))
            print(json.dumps(result.payload, indent=2, ensure_ascii=False))
            if result.strict_failure:
                raise ValueError(result.strict_failure)
            return 0

        construction_inputs = await RuntimeConstructionInputs.capture_async()
        workspace = await _resolve_path(args.workspace, invocation_root=construction_inputs.invocation_root)
        engine = await create_runtime_owner(
            partial(OrchestrationEngine, workspace, args.department, construction_inputs=construction_inputs),
            label="runtime-cli-construction")

        if args.board:
            print_board(await read_runtime_board(engine))
            return 0

        if args.loop:
            from orket.organization_loop import OrganizationLoop

            await (await OrganizationLoop.create()).run_forever()
            return 0

        if args.archive_card or args.archive_build or args.archive_related:
            archived_ids: list[str] = []
            missing_ids: list[str] = []
            archived_count = 0
            if args.archive_card:
                archive_result = await engine.archive_cards(args.archive_card, archived_by="cli", reason=args.archive_reason)
                archived_ids.extend(archive_result.get("archived", []))
                missing_ids.extend(archive_result.get("missing", []))
            if args.archive_build:
                archived_count += await engine.archive_build(
                    args.archive_build, archived_by="cli", reason=args.archive_reason
                )
            if args.archive_related:
                related_archive_result = await engine.archive_related_cards(
                    args.archive_related, archived_by="cli", reason=args.archive_reason
                )
                archived_ids.extend(related_archive_result.get("archived", []))
                missing_ids.extend(related_archive_result.get("missing", []))

            archived_ids = sorted(set(archived_ids))
            missing_ids = sorted(set(missing_ids))
            archived_count += len(archived_ids)
            print(f"Archived {archived_count} card(s).")
            if archived_ids:
                print(f"Archived IDs: {', '.join(archived_ids)}")
            if missing_ids:
                print(f"Missing IDs: {', '.join(missing_ids)}")
            return 0

        if args.replay_turn:
            parts = args.replay_turn.split(":")
            if len(parts) not in {3, 4}:
                raise ValueError("--replay-turn format must be <session_id>:<issue_id>:<turn_index>[:role]")
            session_id, issue_id, turn_index = parts[0], parts[1], int(parts[2])
            role = parts[3] if len(parts) == 4 else None
            replay = await read_runtime_replay(engine,
                session_id=session_id,
                issue_id=issue_id,
                turn_index=turn_index,
                role=role,
            )
            print(json.dumps(replay, indent=2, ensure_ascii=False))
            return 0

        await emit_runtime_manifest(print_orket_manifest, args.department)

        if args.rock or args.card:
            target = args.rock or args.card
            print(f"Running Orket Card: {target}")
            result = await engine.run_card(target, build_id=args.build_id,
                driver_steered=args.driver_steered, model_override=args.model)
            return await _finish_named_run(engine, result)

        if not args.epic:
            # Interactive Driver Mode
            from orket.driver import OrketDriver

            print(f"\n{'=' * 60}\n ORKET DRIVER (Interactive)\n{'=' * 60}")
            construct = partial(OrketDriver, model=args.model, project_root=construction_inputs.invocation_root,
                                environment=construction_inputs.environment)
            async with open_runtime_owner(construct, label="interactive-driver-construction") as driver:
                while True:
                    user_input = await read_console_line("Driver> ")
                    if user_input is None or user_input.lower() in ["exit", "quit", "q"]:
                        break
                    if not user_input:
                        continue
                    print("Thinking...", end="", flush=True)
                    response = await driver.process_request(user_input)
                    print(f"\r{response}\n")
            return 0

        print(f"Running Orket Epic: {args.epic}")
        result = await engine.run_epic(
            args.epic,
            build_id=args.build_id,
            driver_steered=args.driver_steered,
            target_issue_id=args.resume,
            model_override=args.model,
        )
        return await _finish_named_run(engine, result)

    except RuntimeExecutionCancelled as exc:
        return await _finish_named_run(engine, exc.result, cancelled=True)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[HALT] Interrupted by user.")
        return 130
    except (RuntimeError, ValueError, OSError, TypeError) as e:
        import traceback

        traceback.print_exc()
        print(f"\n[FATAL] {e}")
        return 1
    finally:
        if engine is not None and await close_runtime_owner(engine):
            raise asyncio.CancelledError("Runtime cleanup completed after caller cancellation")
