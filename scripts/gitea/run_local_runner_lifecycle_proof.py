from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.gitea.inspect_local_runner_containers import DEFAULT_GITEA_DB
    from scripts.gitea.local_runner_lifecycle_support import (
        collect_state,
        completed_job_count,
        create_temp_access_token,
        delete_access_tokens,
        delete_repo_runners_by_prefix,
        dispatch_workflow,
        find_new_run_id,
        get_workflow_run,
        list_non_allowlisted_containers,
        list_run_jobs,
        list_workflow_runs,
        remove_containers,
        run_ephemeral_attempt,
        utc_now,
        workflow_path_matches,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from gitea.inspect_local_runner_containers import DEFAULT_GITEA_DB
    from gitea.local_runner_lifecycle_support import (
        collect_state,
        completed_job_count,
        create_temp_access_token,
        delete_access_tokens,
        delete_repo_runners_by_prefix,
        dispatch_workflow,
        find_new_run_id,
        get_workflow_run,
        list_non_allowlisted_containers,
        list_run_jobs,
        list_workflow_runs,
        remove_containers,
        run_ephemeral_attempt,
        utc_now,
        workflow_path_matches,
    )


DEFAULTS = {
    "gitea_url": "http://localhost:3000",
    "owner": "Orket",
    "repo": "Orket",
    "workflow_id": "monorepo-packages-ci.yml",
    "ref": "main",
    "gitea_container": "vibe-rail-gitea",
    "gitea_username": "Orket",
    "runner_image": "gitea/act_runner:latest",
    "runner_labels": "ubuntu-latest:docker://docker.gitea.com/runner-images:ubuntu-latest",
    "runner_prefix": "codex-runner-lifecycle-proof",
    "allowed_container": ["vibe-rail-gitea"],
    "timeout_seconds": 240,
    "attempt_timeout_seconds": 120,
    "poll_interval_seconds": 2.0,
    "out": "benchmarks/results/gitea/local_runner_lifecycle_proof.json",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local Gitea workflow with teardown-proven ephemeral runners.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--gitea-db", default=DEFAULT_GITEA_DB)
    parser.add_argument("--gitea-url", default=DEFAULTS["gitea_url"])
    parser.add_argument("--owner", default=DEFAULTS["owner"])
    parser.add_argument("--repo", default=DEFAULTS["repo"])
    parser.add_argument("--workflow-id", default=DEFAULTS["workflow_id"])
    parser.add_argument("--ref", default=DEFAULTS["ref"])
    parser.add_argument("--gitea-container", default=DEFAULTS["gitea_container"])
    parser.add_argument("--gitea-username", default=DEFAULTS["gitea_username"])
    parser.add_argument("--runner-image", default=DEFAULTS["runner_image"])
    parser.add_argument("--runner-labels", default=DEFAULTS["runner_labels"])
    parser.add_argument("--runner-prefix", default=DEFAULTS["runner_prefix"])
    parser.add_argument("--allowed-container", action="append", default=list(DEFAULTS["allowed_container"]))
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULTS["timeout_seconds"])
    parser.add_argument("--attempt-timeout-seconds", type=int, default=DEFAULTS["attempt_timeout_seconds"])
    parser.add_argument("--poll-interval-seconds", type=float, default=DEFAULTS["poll_interval_seconds"])
    parser.add_argument("--out", default=DEFAULTS["out"])
    return parser


async def _run_proof(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    repo_root = Path(str(args.repo_root)).resolve()
    gitea_db = (repo_root / str(args.gitea_db)).resolve()
    allowlist = {str(name).strip() for name in list(args.allowed_container) if str(name).strip()}
    deadline = asyncio.get_running_loop().time() + int(args.timeout_seconds)
    token_name = f"{args.runner_prefix}-token"
    report: dict[str, object] = {
        "schema_version": "gitea.local_runner_lifecycle_proof.v1",
        "started_at": utc_now(),
        "path": "primary",
        "status": "failure",
        "gitea_url": str(args.gitea_url),
        "owner": str(args.owner),
        "repo": str(args.repo),
        "workflow_id": str(args.workflow_id),
        "ref": str(args.ref),
        "allowed_containers": sorted(allowlist),
        "start_state": {},
        "run": {"attempts": []},
        "end_state": {},
        "cleanup": {"removed_non_infrastructure_containers": [], "deleted_repo_runners": [], "token": {}},
    }
    token = ""
    try:
        await delete_access_tokens(gitea_db, [token_name])
        token = await create_temp_access_token(str(args.gitea_container), str(args.gitea_username), token_name)
        async with httpx.AsyncClient(
            base_url=str(args.gitea_url).rstrip("/"),
            headers={"Authorization": f"token {token}"},
            timeout=30.0,
        ) as client:
            report["start_state"] = await collect_state(
                repo_root=repo_root,
                gitea_db=gitea_db,
                client=client,
                owner=str(args.owner),
                repo=str(args.repo),
                workflow_id=str(args.workflow_id),
                allowlist=allowlist,
            )
            start_state = dict(report["start_state"])
            if start_state["runner_report"]["status"] != "PASS":
                raise RuntimeError("Runner container inspection did not start clean.")
            if (
                start_state["repo_runners"]
                or start_state["non_infrastructure_containers"]
                or start_state["active_workflow_runs"]
            ):
                raise RuntimeError("Control plane was not clean before proof.")

            previous_run_id = max(
                [
                    int(run.get("id") or 0)
                    for run in await list_workflow_runs(client, str(args.owner), str(args.repo))
                    if workflow_path_matches(run, str(args.workflow_id))
                ],
                default=0,
            )
            await dispatch_workflow(client, str(args.owner), str(args.repo), str(args.workflow_id), str(args.ref))
            run_id = await find_new_run_id(
                client,
                owner=str(args.owner),
                repo=str(args.repo),
                workflow_id=str(args.workflow_id),
                previous_max_run_id=previous_run_id,
                deadline=deadline,
                poll_interval_seconds=float(args.poll_interval_seconds),
            )
            report["run"]["run_id"] = run_id

            attempt_number = 0
            while True:
                run_payload = await get_workflow_run(client, str(args.owner), str(args.repo), run_id)
                jobs_before = await list_run_jobs(client, str(args.owner), str(args.repo), run_id)
                report["run"]["status"] = str(run_payload.get("status") or "")
                report["run"]["conclusion"] = str(run_payload.get("conclusion") or "")
                report["run"]["jobs"] = jobs_before
                if str(run_payload.get("status") or "") == "completed":
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise RuntimeError("Timed out waiting for workflow completion.")

                attempt_number += 1
                attempt = await run_ephemeral_attempt(
                    repo_root=repo_root,
                    client=client,
                    owner=str(args.owner),
                    repo=str(args.repo),
                    gitea_url=str(args.gitea_url),
                    runner_image=str(args.runner_image),
                    runner_labels=str(args.runner_labels),
                    prefix=str(args.runner_prefix),
                    attempt_number=attempt_number,
                    attempt_timeout_seconds=int(args.attempt_timeout_seconds),
                    poll_interval_seconds=float(args.poll_interval_seconds),
                )
                await asyncio.sleep(float(args.poll_interval_seconds))
                jobs_after = await list_run_jobs(client, str(args.owner), str(args.repo), run_id)
                attempt["completed_jobs_before"] = completed_job_count(jobs_before)
                attempt["completed_jobs_after"] = completed_job_count(jobs_after)
                report["run"]["attempts"].append(attempt)
                if attempt["completed_jobs_after"] <= attempt["completed_jobs_before"]:
                    raise RuntimeError("Runner attempt made no workflow progress.")

            if report["run"]["conclusion"] != "success":
                raise RuntimeError(f"Workflow completed with conclusion={report['run']['conclusion']!r}.")

            leftovers = await list_non_allowlisted_containers(allowlist)
            if leftovers:
                report["cleanup"]["removed_non_infrastructure_containers"] = await remove_containers(
                    [item["name"] for item in leftovers]
                )
            report["cleanup"]["deleted_repo_runners"] = await delete_repo_runners_by_prefix(
                client,
                owner=str(args.owner),
                repo=str(args.repo),
                name_prefix=str(args.runner_prefix),
            )
            report["end_state"] = await collect_state(
                repo_root=repo_root,
                gitea_db=gitea_db,
                client=client,
                owner=str(args.owner),
                repo=str(args.repo),
                workflow_id=str(args.workflow_id),
                allowlist=allowlist,
            )
            end_state = dict(report["end_state"])
            if end_state["runner_report"]["status"] != "PASS":
                raise RuntimeError("Runner container inspection did not end clean.")
            if end_state["repo_runners"] or end_state["non_infrastructure_containers"]:
                raise RuntimeError("Control plane did not end clean.")
            report["status"] = "success"
            report["result"] = "success"
            report["finished_at"] = utc_now()
            report["cleanup"]["token"] = {
                "mode": "sqlite_local_state",
                "deleted_rows": await delete_access_tokens(gitea_db, [token_name]),
            }
            return 0, report
    except Exception as exc:
        report["error"] = str(exc)
        report["result"] = "failure"
        report["finished_at"] = utc_now()
        if token:
            async with httpx.AsyncClient(
                base_url=str(args.gitea_url).rstrip("/"),
                headers={"Authorization": f"token {token}"},
                timeout=30.0,
            ) as client:
                leftovers = await list_non_allowlisted_containers(allowlist)
                if leftovers:
                    report["cleanup"]["removed_non_infrastructure_containers"] = await remove_containers(
                        [item["name"] for item in leftovers]
                    )
                report["cleanup"]["deleted_repo_runners"] = await delete_repo_runners_by_prefix(
                    client,
                    owner=str(args.owner),
                    repo=str(args.repo),
                    name_prefix=str(args.runner_prefix),
                )
                report["cleanup"]["token"] = {
                    "mode": "sqlite_local_state",
                    "deleted_rows": await delete_access_tokens(gitea_db, [token_name]),
                }
        return 1, report


async def _async_main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    exit_code, report = await _run_proof(args)
    repo_root = Path(str(args.repo_root)).resolve()
    write_payload_with_diff_ledger(repo_root / str(args.out), report)
    if exit_code == 0:
        print("Local runner lifecycle proof")
        print(f"status={report['status']}")
        print(f"workflow_id={report['workflow_id']}")
        print(f"run_id={report['run'].get('run_id', '')}")
        print(f"attempts={len(report['run']['attempts'])}")
        print(f"conclusion={report['run'].get('conclusion', '')}")
    else:
        print(f"Local runner lifecycle proof failed: {report.get('error', 'unknown error')}")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
