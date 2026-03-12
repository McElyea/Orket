from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


DEFAULT_GITEA_DB = "infrastructure/gitea/gitea/gitea.db"
RUNNER_IMAGE_PREFIX = "gitea/act_runner"
KNOWN_RETRY_SIGNATURE = "instance address is empty"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect local gitea/act_runner containers and classify persistent runners vs stray retry loops.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve default paths.")
    parser.add_argument("--gitea-db", default=DEFAULT_GITEA_DB, help="Path to the local Gitea SQLite database.")
    parser.add_argument("--out", default="", help="Optional JSON output path for a rerunnable report.")
    parser.add_argument(
        "--execute-stray-cleanup",
        action="store_true",
        help="Stop and remove only containers classified as safe stray runner cleanup targets.",
    )
    parser.add_argument(
        "--skip-logs",
        action="store_true",
        help="Skip docker log tail collection when classifying unregistered runner containers.",
    )
    return parser


async def run_command(*cmd: str) -> CommandResult:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    return CommandResult(
        returncode=int(process.returncode or 0),
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
    )


def _load_registered_runners(path: Path) -> set[str]:
    if not path.exists():
        return set()

    connection = sqlite3.connect(path)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM action_runner WHERE deleted IS NULL")
        return {str(row[0]).strip() for row in cursor.fetchall() if row and str(row[0]).strip()}
    finally:
        connection.close()


async def _list_runner_container_names() -> tuple[list[str], list[str]]:
    result = await run_command("docker", "ps", "-a", "--format", "{{json .}}")
    if result.returncode != 0:
        failure = result.stderr.strip() or result.stdout.strip() or "docker ps -a failed"
        raise RuntimeError(f"Unable to list Docker containers: {failure}")

    names: list[str] = []
    warnings: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"Skipped non-JSON docker ps row: {line[:120]}")
            continue
        image = str(row.get("Image") or "")
        name = str(row.get("Names") or "").strip()
        if image.startswith(RUNNER_IMAGE_PREFIX) and name:
            names.append(name)
    return sorted(names), warnings


async def _inspect_runner_containers(names: list[str]) -> list[dict[str, Any]]:
    if not names:
        return []
    result = await run_command("docker", "inspect", *names)
    if result.returncode != 0:
        failure = result.stderr.strip() or result.stdout.strip() or "docker inspect failed"
        raise RuntimeError(f"Unable to inspect Docker containers: {failure}")
    return list(json.loads(result.stdout))


async def _collect_logs(container_name: str, skip_logs: bool) -> str:
    if skip_logs:
        return ""
    result = await run_command("docker", "logs", "--tail", "40", container_name)
    return (result.stdout or "") + (result.stderr or "")


def classify_runner_container(
    inspect_payload: dict[str, Any],
    *,
    registered_runner_names: set[str],
    log_tail: str = "",
) -> dict[str, Any]:
    name = str(inspect_payload.get("Name") or "").lstrip("/")
    config = dict(inspect_payload.get("Config") or {})
    host_config = dict(inspect_payload.get("HostConfig") or {})
    state = dict(inspect_payload.get("State") or {})
    restart_policy = str(dict(host_config.get("RestartPolicy") or {}).get("Name") or "no")
    auto_remove = bool(host_config.get("AutoRemove"))
    cmd = [str(token) for token in list(config.get("Cmd") or [])]
    entrypoint = [str(token) for token in list(config.get("Entrypoint") or [])]
    image = str(config.get("Image") or "")
    env_values = [str(token) for token in list(config.get("Env") or [])]
    runner_registration_name = ""
    for token in env_values:
        if token.startswith("GITEA_RUNNER_NAME="):
            runner_registration_name = token.partition("=")[2].strip()
            break
    matches_registered_runner = name in registered_runner_names or runner_registration_name in registered_runner_names
    observed_registration_name = runner_registration_name or (name if name in registered_runner_names else "")

    assessment = {
        "name": name,
        "image": image,
        "state_status": str(state.get("Status") or ""),
        "created_at": str(inspect_payload.get("Created") or ""),
        "restart_policy": restart_policy,
        "auto_remove": auto_remove,
        "command": cmd,
        "entrypoint": entrypoint,
        "runner_registration_name": runner_registration_name,
        "observed_registration_name": observed_registration_name,
        "registered_runner": matches_registered_runner,
        "classification": "unknown_runner_container",
        "policy_compliant": False,
        "intended_disposal": "manual review required",
        "required_action": "prove teardown path or stop using container privileges",
        "cleanup_candidate": False,
        "reason": "Container does not match a known safe cleanup rule.",
    }

    if matches_registered_runner:
        assessment.update(
            {
                "classification": "persistent_containerized_runner_policy_violation",
                "policy_compliant": False,
                "intended_disposal": "not allowed as steady-state infrastructure under teardown policy",
                "required_action": "move runner host off containers or replace with a teardown-proven ephemeral path",
                "cleanup_candidate": False,
                "reason": (
                    "Container maps to a registered local Gitea action runner, but it is a long-lived "
                    "containerized runner host with no automatic done->teardown path."
                ),
            }
        )
        return assessment

    log_signature = KNOWN_RETRY_SIGNATURE if KNOWN_RETRY_SIGNATURE in log_tail else ""
    if log_signature:
        assessment["observed_failure_signature"] = log_signature

    if auto_remove:
        if cmd == ["--version"]:
            assessment.update(
                {
                    "classification": "stray_runner_version_probe_loop",
                    "policy_compliant": False,
                    "intended_disposal": "container exit should have triggered Docker auto-remove",
                    "required_action": "remove container and block this launch pattern from further use",
                    "cleanup_candidate": True,
                    "reason": (
                        "Container was started with the act_runner image default entrypoint plus '--version'. "
                        "Observed behavior kept the default runner bootstrap loop alive instead of exiting."
                    ),
                }
            )
            return assessment

        if cmd[:2] == ["act_runner", "exec"]:
            assessment.update(
                {
                    "classification": "stray_runner_exec_loop",
                    "policy_compliant": False,
                    "intended_disposal": "container exit should have triggered Docker auto-remove",
                    "required_action": "remove container and stop using this entrypoint pattern for one-shot exec",
                    "cleanup_candidate": True,
                    "reason": (
                        "Container attempted an ad hoc act_runner exec flow through the image default entrypoint. "
                        "Observed behavior left the runner bootstrap loop alive, so auto-remove never fired."
                    ),
                }
            )
            return assessment

        assessment.update(
            {
                "classification": "stray_runner_autoremove_loop",
                "policy_compliant": False,
                "intended_disposal": "container exit should have triggered Docker auto-remove",
                "required_action": "remove container and prove a teardown path before reusing this pattern",
                "cleanup_candidate": True,
                "reason": (
                    "Container is an unregistered act_runner container with Docker auto-remove enabled, but it "
                    "did not exit on its own."
                ),
            }
        )
        return assessment

    return assessment


async def build_runner_container_report(
    *,
    repo_root: Path,
    gitea_db: Path,
    execute_stray_cleanup: bool,
    skip_logs: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    registered_runner_names = _load_registered_runners(gitea_db)
    container_names, ps_warnings = await _list_runner_container_names()
    warnings.extend(ps_warnings)
    inspect_payloads = await _inspect_runner_containers(container_names)

    containers: list[dict[str, Any]] = []
    cleanup_actions: list[dict[str, Any]] = []
    for inspect_payload in inspect_payloads:
        name = str(inspect_payload.get("Name") or "").lstrip("/")
        log_tail = await _collect_logs(name, skip_logs=skip_logs)
        assessment = classify_runner_container(
            inspect_payload,
            registered_runner_names=registered_runner_names,
            log_tail=log_tail,
        )
        containers.append(assessment)

    observed_registration_names = {
        str(item.get("observed_registration_name") or "").strip()
        for item in containers
        if str(item.get("observed_registration_name") or "").strip()
    }
    stale_registrations = sorted(name for name in registered_runner_names if name not in observed_registration_names)
    cleanup_targets = [item["name"] for item in containers if bool(item.get("cleanup_candidate"))]
    policy_violations = [item["name"] for item in containers if not bool(item.get("policy_compliant"))]
    if execute_stray_cleanup:
        for name in cleanup_targets:
            result = await run_command("docker", "rm", "-f", name)
            cleanup_actions.append(
                {
                    "name": name,
                    "returncode": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                }
            )

    status = "PASS"
    if policy_violations:
        status = "FAIL"
    if stale_registrations:
        status = "FAIL"
    if execute_stray_cleanup and any(action["returncode"] != 0 for action in cleanup_actions):
        status = "FAIL"

    return {
        "schema_version": "gitea.local_runner_container_inspection.v1",
        "repo_root": repo_root.resolve().as_posix(),
        "gitea_db": gitea_db.resolve().as_posix(),
        "policy": {
            "name": "container_done_teardown_required",
            "version": "2026-03-12",
            "summary": (
                "Container privileges are allowed only when the container has a proven done-to-teardown path. "
                "If it cannot be spun back down when work is done, the route is non-compliant."
            ),
        },
        "status": status,
        "registered_runner_names": sorted(registered_runner_names),
        "stale_registrations": stale_registrations,
        "summary": {
            "containers_total": len(containers),
            "persistent_runner_policy_violations": sum(
                1
                for item in containers
                if item["classification"] == "persistent_containerized_runner_policy_violation"
            ),
            "cleanup_candidates": len(cleanup_targets),
            "policy_violations": len(policy_violations),
            "stale_registration_policy_violations": len(stale_registrations),
        },
        "containers": containers,
        "cleanup_actions": cleanup_actions,
        "warnings": warnings,
        "environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
        },
    }


def _print_report(report: dict[str, Any]) -> None:
    print("Local Gitea runner container inspection")
    print(f"status={report['status']}")
    print(f"registered_runner_names={report['registered_runner_names']}")
    print(f"stale_registrations={report['stale_registrations']}")
    summary = dict(report["summary"])
    print(
        "summary="
        f"containers_total={summary['containers_total']} "
        f"persistent_runner_policy_violations={summary['persistent_runner_policy_violations']} "
        f"cleanup_candidates={summary['cleanup_candidates']} "
        f"policy_violations={summary['policy_violations']} "
        f"stale_registration_policy_violations={summary['stale_registration_policy_violations']}"
    )
    for container in list(report["containers"]):
        print(
            f"- {container['name']}: {container['classification']} "
            f"(cleanup_candidate={container['cleanup_candidate']} policy_compliant={container['policy_compliant']})"
        )
        print(f"  intended_disposal={container['intended_disposal']}")
        print(f"  required_action={container['required_action']}")
        print(f"  reason={container['reason']}")
        if container.get("observed_failure_signature"):
            print(f"  observed_failure_signature={container['observed_failure_signature']}")


async def _async_main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    gitea_db = (repo_root / str(args.gitea_db)).resolve()

    try:
        report = await build_runner_container_report(
            repo_root=repo_root,
            gitea_db=gitea_db,
            execute_stray_cleanup=bool(args.execute_stray_cleanup),
            skip_logs=bool(args.skip_logs),
        )
    except (RuntimeError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"Runner container inspection failed: {exc}")
        return 1

    out_path = str(args.out).strip()
    if out_path:
        write_payload_with_diff_ledger(Path(out_path), report)
    _print_report(report)
    return 0 if report["status"] == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
