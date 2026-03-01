#!/usr/bin/env python3
"""Simple Gitea CI helper: status, trigger, and watch workflow runs."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from typing import Any

from dotenv import dotenv_values


def _resolve_setting(cli_value: str, env_key: str, dotenv_map: dict[str, str]) -> str:
    cli = str(cli_value or "").strip()
    if cli:
        return cli
    env_value = str(os.getenv(env_key, "")).strip()
    if env_value:
        return env_value
    return str(dotenv_map.get(env_key, "") or "").strip()


def _build_api_url(base_url: str, owner: str, repo: str, suffix: str) -> str:
    quoted_owner = urllib.parse.quote(owner, safe="")
    quoted_repo = urllib.parse.quote(repo, safe="")
    return f"{base_url.rstrip('/')}/api/v1/repos/{quoted_owner}/{quoted_repo}{suffix}"


def _http_json(
    *,
    method: str,
    url: str,
    token: str | None,
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, method=method.upper(), data=data)
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


def _extract_run_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("workflow_runs", "runs", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _extract_workflow_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("workflows", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _status_failed(state: str) -> bool:
    normalized = str(state or "").strip().lower()
    return normalized in {"error", "failure", "failed", "cancelled"}


def _run_failed(run: dict[str, Any]) -> bool:
    conclusion = str(run.get("conclusion") or "").strip().lower()
    return conclusion in {"failure", "failed", "cancelled", "timed_out", "action_required"}


def _api_get(
    *,
    base_url: str,
    owner: str,
    repo: str,
    token: str | None,
    suffix: str,
) -> Any:
    return _http_json(method="GET", url=_build_api_url(base_url, owner, repo, suffix), token=token)


def _fetch_repo_info(*, base_url: str, owner: str, repo: str, token: str | None) -> dict[str, Any]:
    payload = _api_get(base_url=base_url, owner=owner, repo=repo, token=token, suffix="")
    return payload if isinstance(payload, dict) else {}


def _fetch_open_pulls(*, base_url: str, owner: str, repo: str, token: str | None) -> list[dict[str, Any]]:
    payload = _api_get(base_url=base_url, owner=owner, repo=repo, token=token, suffix="/pulls?state=open&limit=50&page=1")
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _fetch_combined_status(*, base_url: str, owner: str, repo: str, token: str | None, ref: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(str(ref), safe="")
    payload = _api_get(base_url=base_url, owner=owner, repo=repo, token=token, suffix=f"/commits/{encoded}/status")
    return payload if isinstance(payload, dict) else {}


def _actions_api_available(*, base_url: str, owner: str, repo: str, token: str | None) -> bool:
    try:
        _api_get(base_url=base_url, owner=owner, repo=repo, token=token, suffix="/actions/runs?per_page=1&page=1")
        return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def _status_fallback_rows(*, base_url: str, owner: str, repo: str, token: str | None) -> list[dict[str, Any]]:
    repo_info = _fetch_repo_info(base_url=base_url, owner=owner, repo=repo, token=token)
    default_branch = str(repo_info.get("default_branch") or "main")
    refs: list[tuple[str, str, str]] = [("push", default_branch, default_branch)]
    for pull in _fetch_open_pulls(base_url=base_url, owner=owner, repo=repo, token=token):
        head = pull.get("head")
        if not isinstance(head, dict):
            continue
        sha = str(head.get("sha") or "").strip()
        ref = str(head.get("ref") or "").strip()
        if sha:
            refs.append(("pull_request", ref or f"pr-{pull.get('number')}", sha))
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event, branch, ref in refs:
        key = (event, branch, ref)
        if key in seen:
            continue
        seen.add(key)
        payload = _fetch_combined_status(base_url=base_url, owner=owner, repo=repo, token=token, ref=ref)
        statuses = payload.get("statuses", []) if isinstance(payload, dict) else []
        if not isinstance(statuses, list):
            statuses = []
        for item in statuses:
            if not isinstance(item, dict):
                continue
            state = str(item.get("state") or "")
            rows.append(
                {
                    "context": str(item.get("context") or ""),
                    "state": state,
                    "failed": _status_failed(state),
                    "description": str(item.get("description") or ""),
                    "target_url": str(item.get("target_url") or ""),
                    "sha": str(item.get("sha") or ""),
                    "branch": branch,
                    "event": event,
                    "updated_at": str(item.get("updated_at") or item.get("created_at") or ""),
                }
            )
    rows.sort(key=lambda x: (x["branch"], x["context"], x["updated_at"]), reverse=True)
    return rows


def _resolve_workflow_id(
    *,
    base_url: str,
    owner: str,
    repo: str,
    token: str | None,
    workflow: str,
) -> str:
    target = str(workflow or "").strip().lower()
    url = _build_api_url(base_url, owner, repo, "/actions/workflows")
    payload = _http_json(method="GET", url=url, token=token)
    workflows = _extract_workflow_list(payload)
    for item in workflows:
        ident = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip().lower()
        path = str(item.get("path") or "").strip().lower()
        if not ident:
            continue
        if target in {ident.lower(), name, path, path.split("/")[-1]}:
            return ident
    raise RuntimeError(f"Workflow '{workflow}' not found in repository actions workflows.")


def _fetch_runs(
    *,
    base_url: str,
    owner: str,
    repo: str,
    token: str | None,
    limit: int = 20,
    workflow_id: str | None = None,
    branch: str | None = None,
) -> list[dict[str, Any]]:
    suffix = f"/actions/runs?per_page={int(limit)}&page=1"
    if workflow_id:
        suffix += f"&workflow_id={urllib.parse.quote(str(workflow_id), safe='')}"
    if branch:
        suffix += f"&branch={urllib.parse.quote(str(branch), safe='')}"
    payload = _http_json(method="GET", url=_build_api_url(base_url, owner, repo, suffix), token=token)
    return _extract_run_list(payload)


def _trigger_workflow(
    *,
    base_url: str,
    owner: str,
    repo: str,
    token: str | None,
    workflow_id: str,
    ref: str,
) -> None:
    url = _build_api_url(base_url, owner, repo, f"/actions/workflows/{urllib.parse.quote(workflow_id, safe='')}/dispatches")
    _http_json(method="POST", url=url, token=token, payload={"ref": ref})


def _wait_for_new_run(
    *,
    base_url: str,
    owner: str,
    repo: str,
    token: str | None,
    workflow_id: str,
    branch: str,
    min_created_at: str,
    timeout_s: int,
    poll_s: int,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        runs = _fetch_runs(
            base_url=base_url,
            owner=owner,
            repo=repo,
            token=token,
            workflow_id=workflow_id,
            branch=branch,
            limit=10,
        )
        for run in runs:
            created_at = str(run.get("created_at") or "")
            if created_at >= min_created_at:
                return run
        time.sleep(poll_s)
    raise TimeoutError("Timed out waiting for workflow run to appear.")


def _wait_for_completion(
    *,
    base_url: str,
    owner: str,
    repo: str,
    token: str | None,
    run_id: str,
    timeout_s: int,
    poll_s: int,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    url = _build_api_url(base_url, owner, repo, f"/actions/runs/{urllib.parse.quote(run_id, safe='')}")
    last: dict[str, Any] = {}
    while time.time() < deadline:
        payload = _http_json(method="GET", url=url, token=token)
        if isinstance(payload, dict):
            last = payload
            status = str(payload.get("status") or "").strip().lower()
            conclusion = str(payload.get("conclusion") or "").strip().lower()
            if status in {"completed", "success", "failure", "cancelled"} or conclusion:
                return payload
        time.sleep(poll_s)
    raise TimeoutError(f"Timed out waiting for run {run_id} to complete.")


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


def _hint_for_error(*, base_url: str, error: Exception) -> str:
    msg = str(error)
    if "404" in msg:
        if "github.com" in base_url.lower():
            return "Configured URL appears to be GitHub, not Gitea. Set ORKET_GITEA_URL to your Gitea base URL."
        return "Gitea Actions API endpoint not found. Confirm ORKET_GITEA_URL points to a Gitea server with Actions enabled."
    if "401" in msg or "403" in msg:
        return "Authentication failed. Verify ORKET_GITEA_TOKEN has repo/actions scope."
    if "timed out" in msg.lower():
        return "Request timed out. Check network path to Gitea and server availability."
    return "Check ORKET_GITEA_URL/OWNER/REPO/TOKEN values and server action API availability."


def main() -> None:
    parser = argparse.ArgumentParser(description="Easy Gitea CI helper for trigger/watch/status.")
    parser.add_argument("--gitea-url", default="")
    parser.add_argument("--owner", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--env-file", default=".env")
    sub = parser.add_subparsers(dest="command", required=True)

    status_parser = sub.add_parser("status", help="Show latest workflow runs.")
    status_parser.add_argument("--limit", type=int, default=10)

    watch_parser = sub.add_parser("watch", help="Watch a specific run id until completion.")
    watch_parser.add_argument("--run-id", required=True)
    watch_parser.add_argument("--timeout-s", type=int, default=1800)
    watch_parser.add_argument("--poll-s", type=int, default=5)

    trigger_parser = sub.add_parser("trigger", help="Trigger a workflow and optionally wait for completion.")
    trigger_parser.add_argument("--workflow", required=True, help="Workflow id, name, path, or filename")
    trigger_parser.add_argument("--ref", default="main")
    trigger_parser.add_argument("--wait", action="store_true")
    trigger_parser.add_argument("--timeout-s", type=int, default=1800)
    trigger_parser.add_argument("--poll-s", type=int, default=5)
    sub.add_parser("doctor", help="Diagnose Gitea API and actions endpoint compatibility.")

    args = parser.parse_args()

    dotenv_map: dict[str, str] = {}
    env_path = args.env_file
    if env_path and os.path.exists(env_path):
        loaded = dotenv_values(env_path)
        dotenv_map = {
            str(key): str(value)
            for key, value in loaded.items()
            if isinstance(key, str) and value is not None
        }

    base_url = _resolve_setting(args.gitea_url, "ORKET_GITEA_URL", dotenv_map)
    owner = _resolve_setting(args.owner, "ORKET_GITEA_OWNER", dotenv_map)
    repo = _resolve_setting(args.repo, "ORKET_GITEA_REPO", dotenv_map)
    token = _resolve_setting(args.token, "ORKET_GITEA_TOKEN", dotenv_map) or None

    missing = []
    if not base_url:
        missing.append("ORKET_GITEA_URL")
    if not owner:
        missing.append("ORKET_GITEA_OWNER")
    if not repo:
        missing.append("ORKET_GITEA_REPO")
    if not token:
        missing.append("ORKET_GITEA_TOKEN")
    if missing:
        raise SystemExit("Missing required configuration: " + ", ".join(missing))

    try:
        if args.command == "status":
            if _actions_api_available(base_url=base_url, owner=owner, repo=repo, token=token):
                runs = _fetch_runs(base_url=base_url, owner=owner, repo=repo, token=token, limit=max(1, int(args.limit)))
                _print_json(
                    {
                        "status": "ok",
                        "mode": "actions_api",
                        "count": len(runs),
                        "runs": [
                            {
                                "id": str(item.get("id") or item.get("run_id") or ""),
                                "name": str(item.get("name") or item.get("workflow_name") or ""),
                                "branch": str(item.get("head_branch") or item.get("branch") or ""),
                                "status": str(item.get("status") or ""),
                                "conclusion": str(item.get("conclusion") or ""),
                                "created_at": str(item.get("created_at") or ""),
                                "html_url": str(item.get("html_url") or item.get("url") or ""),
                                "failed": _run_failed(item),
                            }
                            for item in runs
                        ],
                    }
                )
            else:
                rows = _status_fallback_rows(base_url=base_url, owner=owner, repo=repo, token=token)
                _print_json(
                    {
                        "status": "ok",
                        "mode": "commit_status_fallback",
                        "count": len(rows),
                        "rows": rows[: max(1, int(args.limit))],
                        "hint": "Actions REST endpoints are unavailable on this Gitea instance; showing commit status contexts.",
                    }
                )
            return

        if args.command == "watch":
            if not _actions_api_available(base_url=base_url, owner=owner, repo=repo, token=token):
                raise RuntimeError(
                    "Actions REST endpoints are unavailable on this Gitea instance; watch requires actions API support."
                )
            run = _wait_for_completion(
                base_url=base_url,
                owner=owner,
                repo=repo,
                token=token,
                run_id=str(args.run_id),
                timeout_s=max(30, int(args.timeout_s)),
                poll_s=max(2, int(args.poll_s)),
            )
            _print_json(
                {
                    "status": "ok",
                    "run_id": str(run.get("id") or run.get("run_id") or ""),
                    "workflow_name": str(run.get("name") or run.get("workflow_name") or ""),
                    "run_status": str(run.get("status") or ""),
                    "conclusion": str(run.get("conclusion") or ""),
                    "html_url": str(run.get("html_url") or run.get("url") or ""),
                }
            )
            return

        if args.command == "trigger":
            if not _actions_api_available(base_url=base_url, owner=owner, repo=repo, token=token):
                raise RuntimeError(
                    "Actions REST endpoints are unavailable on this Gitea instance; trigger requires actions API support."
                )
            workflow_id = _resolve_workflow_id(
                base_url=base_url,
                owner=owner,
                repo=repo,
                token=token,
                workflow=str(args.workflow),
            )
            marker = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
            _trigger_workflow(
                base_url=base_url,
                owner=owner,
                repo=repo,
                token=token,
                workflow_id=workflow_id,
                ref=str(args.ref),
            )
            if not bool(args.wait):
                _print_json(
                    {
                        "status": "ok",
                        "workflow_id": workflow_id,
                        "ref": str(args.ref),
                        "message": "Triggered workflow dispatch.",
                    }
                )
                return
            run = _wait_for_new_run(
                base_url=base_url,
                owner=owner,
                repo=repo,
                token=token,
                workflow_id=workflow_id,
                branch=str(args.ref),
                min_created_at=marker,
                timeout_s=max(30, int(args.timeout_s)),
                poll_s=max(2, int(args.poll_s)),
            )
            run_id = str(run.get("id") or run.get("run_id") or "")
            done = _wait_for_completion(
                base_url=base_url,
                owner=owner,
                repo=repo,
                token=token,
                run_id=run_id,
                timeout_s=max(30, int(args.timeout_s)),
                poll_s=max(2, int(args.poll_s)),
            )
            _print_json(
                {
                    "status": "ok",
                    "workflow_id": workflow_id,
                    "run_id": str(done.get("id") or done.get("run_id") or run_id),
                    "run_status": str(done.get("status") or ""),
                    "conclusion": str(done.get("conclusion") or ""),
                    "html_url": str(done.get("html_url") or done.get("url") or ""),
                }
            )
            return
        if args.command == "doctor":
            version_url = f"{base_url.rstrip('/')}/api/v1/version"
            version_payload = _http_json(method="GET", url=version_url, token=token)
            repo_info = _fetch_repo_info(base_url=base_url, owner=owner, repo=repo, token=token)
            actions_available = _actions_api_available(base_url=base_url, owner=owner, repo=repo, token=token)
            _print_json(
                {
                    "status": "ok",
                    "gitea_url": base_url,
                    "api_version": version_payload,
                    "repo_exists": bool(repo_info),
                    "repo_default_branch": str(repo_info.get("default_branch") or ""),
                    "actions_api_available": actions_available,
                    "guidance": (
                        "Actions endpoints present."
                        if actions_available
                        else "Actions REST endpoints missing (common on older Gitea builds). "
                        "Use status fallback mode or upgrade Gitea for trigger/watch support."
                    ),
                }
            )
            return
    except (RuntimeError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        _print_json(
            {
                "status": "error",
                "error": str(exc),
                "hint": _hint_for_error(base_url=base_url, error=exc),
            }
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
