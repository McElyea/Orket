from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Iterable
from urllib import error, parse, request


def _run(cmd: list[str], cwd: Path, capture: bool = True) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=capture,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return (proc.stdout or "").strip()


def _slug(name: str) -> str:
    value = name.strip().lower().replace("_", "-")
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "project"


@dataclass
class GiteaClient:
    base_url: str
    username: str
    password: str
    timeout_sec: int = 30

    def _req(self, method: str, path: str, payload: dict | None = None) -> tuple[int, str]:
        url = f"{self.base_url.rstrip('/')}{path}"
        headers = {"Content-Type": "application/json"}
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = request.Request(url=url, method=method, headers=headers, data=body)
        creds = parse.quote(self.username, safe="") + ":" + parse.quote(self.password, safe="")
        req.add_header("Authorization", "Basic " + _b64(creds))

        try:
            with request.urlopen(req, timeout=self.timeout_sec) as resp:
                return int(resp.status), (resp.read() or b"").decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            body_bytes = exc.read() or b""
            return int(exc.code), body_bytes.decode("utf-8", errors="replace")

    def repo_exists(self, owner: str, repo: str) -> bool:
        status, _ = self._req("GET", f"/api/v1/repos/{owner}/{repo}")
        return status == 200

    def create_repo(self, owner: str, repo: str, private: bool) -> bool:
        # Try org repo first, then user repo fallback.
        status, _ = self._req(
            "POST",
            f"/api/v1/orgs/{owner}/repos",
            {"name": repo, "private": private},
        )
        if status in (201, 409):
            return True
        status, _ = self._req("POST", "/api/v1/user/repos", {"name": repo, "private": private})
        return status in (201, 409)


def _b64(raw: str) -> str:
    import base64

    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def discover_projects(product_root: Path) -> list[Path]:
    if not product_root.exists():
        return []
    return sorted([p for p in product_root.iterdir() if p.is_dir()])


def build_push_url(base_url: str, owner: str, repo: str, username: str, password: str) -> str:
    parsed = parse.urlparse(base_url)
    scheme = parsed.scheme or "http"
    host = parsed.netloc or parsed.path
    user = parse.quote(username, safe="")
    pw = parse.quote(password, safe="")
    return f"{scheme}://{user}:{pw}@{host}/{owner}/{repo}.git"


def subtree_commit(repo_root: Path, prefix: str) -> str:
    return _run(["git", "subtree", "split", f"--prefix={prefix}", "HEAD"], cwd=repo_root)


def push_subtree(repo_root: Path, push_url: str, commit_sha: str, branch: str, force: bool) -> None:
    cmd = ["git", "push", push_url, f"{commit_sha}:refs/heads/{branch}"]
    if force:
        cmd.append("--force")
    _run(cmd, cwd=repo_root, capture=True)


def ls_remote_head(repo_root: Path, push_url: str, branch: str) -> str:
    out = _run(["git", "ls-remote", push_url, f"refs/heads/{branch}"], cwd=repo_root, capture=True)
    if not out:
        return ""
    return out.split()[0]


def tree_manifest(repo_root: Path, commit_sha: str) -> str:
    # Commit/tree identity is robust against line-ending checkout normalization.
    return _run(["git", "ls-tree", "-r", commit_sha], cwd=repo_root, capture=True)


def verify_parity(repo_root: Path, local_subtree_sha: str, remote_head_sha: str) -> bool:
    if not remote_head_sha or local_subtree_sha != remote_head_sha:
        return False
    return tree_manifest(repo_root, local_subtree_sha) == tree_manifest(repo_root, remote_head_sha)


def current_branch(repo_root: Path) -> str:
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, capture=True)
    if branch == "HEAD":
        return "main"
    return branch


def validate_git_repo(repo_root: Path) -> None:
    _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root)


def _registry_path(repo_root: Path) -> Path:
    return repo_root / ".orket" / "project_publish_registry.json"


def load_registry(repo_root: Path) -> dict:
    path = _registry_path(repo_root)
    if not path.exists():
        return {"version": 1, "projects": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return {"version": 1, "projects": []}


def save_registry(repo_root: Path, registry: dict) -> None:
    path = _registry_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def upsert_project_record(registry: dict, record: dict) -> None:
    projects = registry.setdefault("projects", [])
    key = (record.get("source_dir"), record.get("project_name"))
    for idx, existing in enumerate(projects):
        if (existing.get("source_dir"), existing.get("project_name")) == key:
            merged = dict(existing)
            merged.update(record)
            projects[idx] = merged
            return
    projects.append(record)


def select_projects(all_projects: list[Path], requested: Iterable[str]) -> list[Path]:
    requested_set = {x.strip() for x in requested if x.strip()}
    if not requested_set:
        return all_projects
    selected: list[Path] = []
    for proj in all_projects:
        if proj.name in requested_set:
            selected.append(proj)
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish <source-dir>/* projects to Gitea as separate repositories via git subtree."
    )
    parser.add_argument("--repo-root", default=".", help="Path to monorepo root (default: current directory).")
    parser.add_argument("--owner", default=os.getenv("GITEA_PRODUCT_OWNER", ""), help="Gitea owner/org.")
    parser.add_argument("--gitea-url", default=os.getenv("GITEA_URL", ""), help="Base Gitea URL.")
    parser.add_argument("--username", default=os.getenv("GITEA_ADMIN_USER", ""), help="Gitea username.")
    parser.add_argument("--password", default=os.getenv("GITEA_ADMIN_PASSWORD", ""), help="Gitea password/token.")
    parser.add_argument(
        "--source-dir",
        default=os.getenv("GITEA_PROJECT_SOURCE_DIR", "product"),
        help="Source directory whose child folders will become repos (default: product).",
    )
    parser.add_argument(
        "--branch",
        default="",
        help="Target branch in destination repos. Defaults to current git branch.",
    )
    parser.add_argument("--repo-prefix", default="", help="Prefix for destination repo names.")
    parser.add_argument("--projects", nargs="*", default=[], help="Optional project folder names to publish.")
    parser.add_argument("--private", action="store_true", help="Create destination repos as private.")
    parser.add_argument("--no-create", action="store_true", help="Do not auto-create missing repos.")
    parser.add_argument("--force", action="store_true", help="Force-push destination branch.")
    parser.add_argument(
        "--verify-parity",
        action="store_true",
        help="Verify remote branch parity (SHA + tree manifest) after push.",
    )
    parser.add_argument(
        "--delete-local",
        action="store_true",
        help="Delete local project folders after successful parity verification.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform API and git push operations. Without this flag, runs in dry-run mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    source_root = (repo_root / args.source_dir).resolve()
    if args.delete_local and (not args.execute):
        print("--delete-local requires --execute.")
        return 2
    if args.delete_local and (not args.verify_parity):
        print("--delete-local requires --verify-parity.")
        return 2

    validate_git_repo(repo_root)
    projects = discover_projects(source_root)
    selected = select_projects(projects, args.projects)
    if not selected:
        print(f"No project folders found/selected under {source_root}.")
        return 1

    missing = [k for k in ("owner", "gitea_url", "username", "password") if not getattr(args, k)]
    if missing:
        print(f"Missing required args/env: {', '.join(missing)}")
        return 2

    target_branch = args.branch or current_branch(repo_root)
    client = GiteaClient(args.gitea_url, args.username, args.password)
    registry = load_registry(repo_root)
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"[{mode}] Publishing {len(selected)} project(s) from {source_root}")
    print(f"Target branch: {target_branch}")

    for proj in selected:
        repo_name = f"{args.repo_prefix}{_slug(proj.name)}"
        prefix = f"{Path(args.source_dir).as_posix().strip('/')}/{proj.name}"
        print(f"\nProject: {proj.name}")
        print(f"  Prefix: {prefix}")
        print(f"  Target: {args.owner}/{repo_name} (branch: {target_branch})")

        exists = client.repo_exists(args.owner, repo_name) if args.execute else False
        if args.execute:
            print(f"  Repo exists: {exists}")
        else:
            print("  Repo exists: (skip in dry-run)")

        if args.execute and (not exists) and (not args.no_create):
            created = client.create_repo(args.owner, repo_name, private=args.private)
            if not created:
                print("  ERROR: failed to create repository in Gitea.")
                return 3
            print("  Repo created.")

        commit_sha = subtree_commit(repo_root, prefix)
        print(f"  Subtree commit: {commit_sha}")

        if not args.execute:
            print("  Push: skipped (dry-run).")
            continue

        push_url = build_push_url(args.gitea_url, args.owner, repo_name, args.username, args.password)
        push_subtree(repo_root, push_url, commit_sha, target_branch, force=args.force)
        print("  Push: OK")

        if args.verify_parity:
            remote_sha = ls_remote_head(repo_root, push_url, target_branch)
            parity_ok = verify_parity(repo_root, commit_sha, remote_sha)
            print(f"  Parity: {'OK' if parity_ok else 'FAILED'}")
            if not parity_ok:
                print("  ERROR: remote parity verification failed.")
                return 4
        else:
            remote_sha = ""
            parity_ok = False

        now = datetime.now(UTC).isoformat()
        upsert_project_record(
            registry,
            {
                "source_dir": Path(args.source_dir).as_posix().strip("/"),
                "project_name": proj.name,
                "prefix": prefix,
                "repo": f"{args.owner}/{repo_name}",
                "branch": target_branch,
                "local_path": str(proj.resolve()),
                "last_published_sha": commit_sha,
                "last_remote_sha": remote_sha,
                "parity_verified": bool(parity_ok),
                "last_published_at": now,
                "archived_at": None,
                "archived_path": None,
                "deleted_at": None,
            },
        )
        save_registry(repo_root, registry)

        if args.delete_local:
            shutil.rmtree(proj)
            print(f"  Local delete: {proj}")
            upsert_project_record(
                registry,
                {
                    "source_dir": Path(args.source_dir).as_posix().strip("/"),
                    "project_name": proj.name,
                    "deleted_at": datetime.now(UTC).isoformat(),
                },
            )
            save_registry(repo_root, registry)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
