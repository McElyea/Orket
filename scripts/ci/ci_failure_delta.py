#!/usr/bin/env python3
"""Build CI failure delta from Gitea Actions failures."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import dotenv_values


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _http_get_json(url: str, token: str | None) -> Any:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _extract_run_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("workflow_runs", "runs", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _extract_job_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("jobs", "workflow_jobs", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _build_api_url(base_url: str, owner: str, repo: str, suffix: str) -> str:
    quoted_owner = urllib.parse.quote(owner, safe="")
    quoted_repo = urllib.parse.quote(repo, safe="")
    return f"{base_url.rstrip('/')}/api/v1/repos/{quoted_owner}/{quoted_repo}{suffix}"


def _coerce_str(value: Any) -> str:
    return str(value or "").strip()


def _is_run_failed(run: dict[str, Any]) -> bool:
    status = _coerce_str(run.get("status")).lower()
    conclusion = _coerce_str(run.get("conclusion")).lower()
    if conclusion in {"failure", "failed", "cancelled", "timed_out", "startup_failure", "action_required"}:
        return True
    if status in {"failure", "failed"}:
        return True
    return False


def _step_failed(step: dict[str, Any]) -> bool:
    conclusion = _coerce_str(step.get("conclusion")).lower()
    status = _coerce_str(step.get("status")).lower()
    return conclusion in {"failure", "failed", "cancelled", "timed_out"} or status in {"failure", "failed"}


def _job_failed(job: dict[str, Any]) -> bool:
    conclusion = _coerce_str(job.get("conclusion")).lower()
    status = _coerce_str(job.get("status")).lower()
    return conclusion in {"failure", "failed", "cancelled", "timed_out"} or status in {"failure", "failed"}


def _classify_priority(
    workflow_name: str,
    branch: str,
    event: str,
    required_main_workflows: set[str],
    main_branch: str,
) -> str:
    if branch == main_branch and workflow_name in required_main_workflows:
        return "P0"
    if event == "pull_request":
        return "P1"
    return "P2"


def _failure_key(item: dict[str, Any]) -> str:
    return "|".join(
        [
            _coerce_str(item.get("workflow_name")),
            _coerce_str(item.get("branch")),
            _coerce_str(item.get("job_name")),
            _coerce_str(item.get("step_name")),
        ]
    )


def _fetch_failing_runs(base_url: str, owner: str, repo: str, token: str | None) -> list[dict[str, Any]]:
    urls = [
        _build_api_url(base_url, owner, repo, "/actions/runs?status=failure&per_page=100&page=1"),
        _build_api_url(base_url, owner, repo, "/actions/runs?per_page=100&page=1"),
    ]
    last_error: Exception | None = None
    for url in urls:
        try:
            payload = _http_get_json(url, token)
            runs = _extract_run_list(payload)
            if not runs:
                continue
            return [run for run in runs if _is_run_failed(run)]
        except Exception as exc:  # pragma: no cover - resilient fetch
            last_error = exc
            continue
    if last_error:
        raise RuntimeError(str(last_error))
    return []


def _fetch_repo_info(base_url: str, owner: str, repo: str, token: str | None) -> dict[str, Any]:
    url = _build_api_url(base_url, owner, repo, "")
    payload = _http_get_json(url, token)
    return payload if isinstance(payload, dict) else {}


def _fetch_combined_status(
    base_url: str, owner: str, repo: str, ref: str, token: str | None
) -> dict[str, Any]:
    url = _build_api_url(base_url, owner, repo, f"/commits/{urllib.parse.quote(ref, safe='')}/status")
    payload = _http_get_json(url, token)
    return payload if isinstance(payload, dict) else {}


def _fetch_open_pulls(base_url: str, owner: str, repo: str, token: str | None) -> list[dict[str, Any]]:
    url = _build_api_url(base_url, owner, repo, "/pulls?state=open&limit=50&page=1")
    payload = _http_get_json(url, token)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _status_failed(state: str) -> bool:
    normalized = _coerce_str(state).lower()
    return normalized in {"error", "failure", "failed", "cancelled"}


def _normalize_status_failures(
    base_url: str,
    owner: str,
    repo: str,
    token: str | None,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    required = {str(x) for x in policy.get("required_main_workflows", [])}
    main_branch = str(policy.get("main_branch", "main"))
    failures: list[dict[str, Any]] = []

    repo_info = _fetch_repo_info(base_url, owner, repo, token)
    default_branch = _coerce_str(repo_info.get("default_branch")) or main_branch
    refs: list[tuple[str, str, str]] = [("push", default_branch, default_branch)]

    for pull in _fetch_open_pulls(base_url, owner, repo, token):
        head = pull.get("head")
        if not isinstance(head, dict):
            continue
        sha = _coerce_str(head.get("sha"))
        ref = _coerce_str(head.get("ref"))
        if not sha:
            continue
        refs.append(("pull_request", ref or f"pr-{pull.get('number')}", sha))

    seen_refs: set[tuple[str, str, str]] = set()
    for event, branch, ref in refs:
        key = (event, branch, ref)
        if key in seen_refs:
            continue
        seen_refs.add(key)
        payload = _fetch_combined_status(base_url, owner, repo, ref, token)
        statuses = payload.get("statuses", []) if isinstance(payload, dict) else []
        if not isinstance(statuses, list):
            statuses = []
        for status in statuses:
            if not isinstance(status, dict):
                continue
            state = _coerce_str(status.get("state"))
            if not _status_failed(state):
                continue

            context = _coerce_str(status.get("context")) or "commit-status"
            target_url = _coerce_str(status.get("target_url"))
            description = _coerce_str(status.get("description"))
            updated_at = _coerce_str(status.get("updated_at") or status.get("created_at"))
            sha = _coerce_str(status.get("sha")) or _coerce_str(payload.get("sha")) or ref
            priority = _classify_priority(context, branch, event, required, main_branch)
            failures.append(
                {
                    "key": "|".join([context, branch, sha, context, description]),
                    "priority": priority,
                    "workflow_name": context,
                    "run_id": sha,
                    "branch": branch,
                    "event": event,
                    "job_name": context,
                    "step_name": description,
                    "step_number": None,
                    "step_status": state,
                    "step_conclusion": state,
                    "run_url": target_url,
                    "created_at": updated_at,
                    "updated_at": updated_at,
                }
            )

    return failures


def _fetch_failed_jobs(base_url: str, owner: str, repo: str, run_id: str, token: str | None) -> list[dict[str, Any]]:
    url = _build_api_url(base_url, owner, repo, f"/actions/runs/{run_id}/jobs?per_page=100&page=1")
    payload = _http_get_json(url, token)
    jobs = _extract_job_list(payload)
    return [job for job in jobs if _job_failed(job)]


def _normalize_failures(
    runs: list[dict[str, Any]],
    base_url: str,
    owner: str,
    repo: str,
    token: str | None,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    required = {str(x) for x in policy.get("required_main_workflows", [])}
    main_branch = str(policy.get("main_branch", "main"))
    out: list[dict[str, Any]] = []

    for run in runs:
        run_id = _coerce_str(run.get("id") or run.get("run_id"))
        workflow_name = _coerce_str(run.get("name") or run.get("workflow_name"))
        branch = _coerce_str(run.get("head_branch") or run.get("branch"))
        event = _coerce_str(run.get("event"))
        run_url = _coerce_str(run.get("html_url") or run.get("url"))
        run_status = _coerce_str(run.get("status"))
        run_conclusion = _coerce_str(run.get("conclusion"))
        created_at = _coerce_str(run.get("created_at"))
        updated_at = _coerce_str(run.get("updated_at"))

        if not run_id:
            continue

        try:
            failed_jobs = _fetch_failed_jobs(base_url, owner, repo, run_id, token)
        except Exception:
            failed_jobs = []

        if not failed_jobs:
            priority = _classify_priority(workflow_name, branch, event, required, main_branch)
            out.append(
                {
                    "key": "|".join([workflow_name, branch, run_id, "", ""]),
                    "priority": priority,
                    "workflow_name": workflow_name,
                    "run_id": run_id,
                    "branch": branch,
                    "event": event,
                    "job_name": "",
                    "step_name": "",
                    "step_number": None,
                    "step_status": run_status,
                    "step_conclusion": run_conclusion,
                    "run_url": run_url,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )
            continue

        for job in failed_jobs:
            job_name = _coerce_str(job.get("name"))
            steps = job.get("steps")
            if not isinstance(steps, list):
                steps = []
            failed_steps = [step for step in steps if isinstance(step, dict) and _step_failed(step)]
            if not failed_steps:
                failed_steps = [
                    {
                        "number": None,
                        "name": "",
                        "status": _coerce_str(job.get("status")),
                        "conclusion": _coerce_str(job.get("conclusion")),
                    }
                ]

            for step in failed_steps:
                step_name = _coerce_str(step.get("name"))
                step_number = step.get("number")
                step_status = _coerce_str(step.get("status"))
                step_conclusion = _coerce_str(step.get("conclusion"))
                priority = _classify_priority(workflow_name, branch, event, required, main_branch)
                out.append(
                    {
                        "key": "|".join(
                            [workflow_name, branch, run_id, job_name, step_name or str(step_number or "")]
                        ),
                        "priority": priority,
                        "workflow_name": workflow_name,
                        "run_id": run_id,
                        "branch": branch,
                        "event": event,
                        "job_name": job_name,
                        "step_name": step_name,
                        "step_number": step_number,
                        "step_status": step_status,
                        "step_conclusion": step_conclusion,
                        "run_url": run_url,
                        "created_at": created_at,
                        "updated_at": updated_at,
                    }
                )

    return out


def _build_delta(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    prev_map = {_coerce_str(item.get("key")): item for item in previous}
    cur_map = {_coerce_str(item.get("key")): item for item in current}

    new_keys = sorted([key for key in cur_map if key not in prev_map])
    still_keys = sorted([key for key in cur_map if key in prev_map])
    resolved_keys = sorted([key for key in prev_map if key not in cur_map])

    stale_counts: dict[str, int] = {}
    for key in new_keys:
        stale_counts[key] = 1
    for key in still_keys:
        prev_count = int(prev_map[key].get("stale_runs", 1))
        stale_counts[key] = prev_count + 1

    new_failures = [cur_map[key] for key in new_keys]
    still_failing = [cur_map[key] for key in still_keys]
    resolved = [prev_map[key] for key in resolved_keys]
    return new_failures, still_failing, resolved, stale_counts


def _markdown_report(snapshot: dict[str, Any]) -> str:
    summary = snapshot.get("summary", {})
    delta = snapshot.get("delta", {})
    alerts = snapshot.get("alerts", {})
    failures = snapshot.get("failures", [])
    generated_at = _coerce_str(snapshot.get("generated_at"))

    lines: list[str] = []
    lines.append("# CI Failure Dump")
    lines.append("")
    lines.append(f"Generated at (UTC): {generated_at}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"1. `P0`: {summary.get('p0', 0)}")
    lines.append(f"2. `P1`: {summary.get('p1', 0)}")
    lines.append(f"3. `P2`: {summary.get('p2', 0)}")
    lines.append(f"4. Total: {summary.get('total', 0)}")
    lines.append("")
    lines.append("## Alerts")
    lines.append(f"1. `BAD_GATE_ALERT`: {str(alerts.get('BAD_GATE_ALERT', False)).lower()}")
    lines.append(f"2. `STALE_FAILURE_ALERT`: {str(alerts.get('STALE_FAILURE_ALERT', False)).lower()}")
    lines.append("")
    lines.append("## Delta Since Last Run")
    lines.append(f"1. `new_failures`: {len(delta.get('new_failures', []))}")
    lines.append(f"2. `still_failing`: {len(delta.get('still_failing', []))}")
    lines.append(f"3. `resolved_since_last_run`: {len(delta.get('resolved_since_last_run', []))}")
    lines.append("")
    lines.append("## Prioritized Failures")

    if not isinstance(failures, list) or not failures:
        lines.append("1. None")
    else:
        ordered = sorted(
            [item for item in failures if isinstance(item, dict)],
            key=lambda item: (item.get("priority", "P9"), item.get("workflow_name", ""), item.get("branch", "")),
        )
        idx = 1
        for item in ordered:
            lines.append(
                f"{idx}. `{item.get('priority', 'P2')}` {item.get('workflow_name', '')} | "
                f"branch `{item.get('branch', '')}` | job `{item.get('job_name', '')}` | "
                f"step `{item.get('step_name', '')}` | stale_runs `{item.get('stale_runs', 1)}`"
            )
            idx += 1

    lines.append("")
    lines.append("## Raw Failure Dump")
    lines.append("See `benchmarks/results/ci_failure_dump.json`.")
    lines.append("")
    return "\n".join(lines)


def _resolve_setting(cli_value: str, env_key: str, dotenv_map: dict[str, str]) -> str:
    cli = str(cli_value or "").strip()
    if cli:
        return cli
    env_value = str(os.getenv(env_key, "")).strip()
    if env_value:
        return env_value
    return str(dotenv_map.get(env_key, "") or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute CI failure delta from Gitea.")
    parser.add_argument("--policy", default=".ci/ci_failure_policy.json")
    parser.add_argument("--snapshot", default=".orket/durable/ci/last_state.json")
    parser.add_argument("--report-md", default="benchmarks/results/ci_failure_dump.md")
    parser.add_argument("--report-json", default="benchmarks/results/ci_failure_dump.json")
    parser.add_argument("--gitea-url", default="")
    parser.add_argument("--owner", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    policy = _read_json(Path(args.policy), {})
    previous_snapshot = _read_json(Path(args.snapshot), {})
    previous_failures = previous_snapshot.get("failures", []) if isinstance(previous_snapshot, dict) else []
    if not isinstance(previous_failures, list):
        previous_failures = []

    generated_at = dt.datetime.now(dt.UTC).isoformat()
    source_status = "ok"
    source_mode = "actions"
    source_error = ""
    current_failures: list[dict[str, Any]] = []

    dotenv_map: dict[str, str] = {}
    env_file_path = Path(args.env_file)
    if env_file_path.exists():
        loaded = dotenv_values(env_file_path)
        dotenv_map = {
            str(key): str(value)
            for key, value in loaded.items()
            if isinstance(key, str) and value is not None
        }

    gitea_url = _resolve_setting(args.gitea_url, "ORKET_GITEA_URL", dotenv_map)
    owner = _resolve_setting(args.owner, "ORKET_GITEA_OWNER", dotenv_map)
    repo = _resolve_setting(args.repo, "ORKET_GITEA_REPO", dotenv_map)
    token_raw = _resolve_setting(args.token, "ORKET_GITEA_TOKEN", dotenv_map)
    token = token_raw or None

    missing = []
    if not gitea_url:
        missing.append("ORKET_GITEA_URL")
    if not owner:
        missing.append("ORKET_GITEA_OWNER")
    if not repo:
        missing.append("ORKET_GITEA_REPO")
    if not token:
        missing.append("ORKET_GITEA_TOKEN")
    if missing:
        raise SystemExit(
            "Missing required configuration: "
            + ", ".join(missing)
            + ". Provide via CLI flags, environment, or .env."
        )

    try:
        runs = _fetch_failing_runs(gitea_url, owner, repo, token)
        current_failures = _normalize_failures(runs, gitea_url, owner, repo, token, policy)
    except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        exc_text = str(exc)
        # Older Gitea builds may not expose /actions/runs API. Fall back to commit statuses.
        if "404" in exc_text:
            try:
                source_mode = "commit_status_fallback"
                current_failures = _normalize_status_failures(gitea_url, owner, repo, token, policy)
                source_status = "ok"
                source_error = ""
            except (RuntimeError, urllib.error.URLError, TimeoutError, ValueError) as fallback_exc:
                source_status = "fetch_error"
                source_error = str(fallback_exc)
                current_failures = []
        else:
            source_status = "fetch_error"
            source_error = exc_text
            current_failures = []

    new_failures, still_failing, resolved, stale_counts = _build_delta(previous_failures, current_failures)
    for item in current_failures:
        key = _coerce_str(item.get("key"))
        item["stale_runs"] = stale_counts.get(key, 1)

    stale_threshold = int(policy.get("stale_threshold_runs", 3))
    p0 = sum(1 for item in current_failures if item.get("priority") == "P0")
    p1 = sum(1 for item in current_failures if item.get("priority") == "P1")
    p2 = sum(1 for item in current_failures if item.get("priority") == "P2")

    snapshot = {
        "schema_version": "ci_failure_state.v1",
        "generated_at": generated_at,
        "source": {
            "status": source_status,
            "mode": source_mode,
            "error": source_error,
            "gitea_url": gitea_url or None,
            "repository": f"{owner}/{repo}" if owner and repo else None,
        },
        "alerts": {
            "BAD_GATE_ALERT": p0 > 0,
            "STALE_FAILURE_ALERT": any(int(item.get("stale_runs", 1)) >= stale_threshold for item in current_failures),
        },
        "summary": {
            "p0": p0,
            "p1": p1,
            "p2": p2,
            "total": len(current_failures),
        },
        "delta": {
            "new_failures": new_failures,
            "still_failing": still_failing,
            "resolved_since_last_run": resolved,
        },
        "failures": current_failures,
    }

    _write_json(Path(args.snapshot), snapshot)
    _write_json(Path(args.report_json), snapshot)

    report_md = _markdown_report(snapshot)
    report_md_path = Path(args.report_md)
    report_md_path.parent.mkdir(parents=True, exist_ok=True)
    report_md_path.write_text(report_md, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": source_status,
                "summary": snapshot["summary"],
                "alerts": snapshot["alerts"],
                "snapshot": args.snapshot,
                "report_md": args.report_md,
                "report_json": args.report_json,
            }
        )
    )


if __name__ == "__main__":
    main()
