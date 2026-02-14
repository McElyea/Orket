from __future__ import annotations

import argparse
import difflib
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from orket.application.services.prompt_resolver import PromptResolver
from orket.application.services.prompt_linter import lint_prompt_file
from orket.schema import DialectConfig, RoleConfig, SkillConfig


VALID_STATUSES = {"draft", "candidate", "canary", "stable", "deprecated"}


def _core_root(root: Path) -> Path:
    return root / "model" / "core"


def _asset_dir(root: Path, kind: str) -> Path:
    if kind == "role":
        return _core_root(root) / "roles"
    if kind == "dialect":
        return _core_root(root) / "dialects"
    raise ValueError(f"Unsupported asset kind: {kind}")


def _iter_assets(root: Path, kind: str) -> List[Path]:
    return sorted(_asset_dir(root, kind).glob("*.json"))


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _kind_and_name_from_id(prompt_id: str) -> Tuple[str, str]:
    raw = str(prompt_id or "").strip()
    if raw.startswith("role."):
        return "role", raw[len("role.") :]
    if raw.startswith("dialect."):
        return "dialect", raw[len("dialect.") :]
    raise ValueError(f"Unsupported prompt id format: {prompt_id}")


def _asset_path_by_id(root: Path, prompt_id: str) -> Path:
    kind, name = _kind_and_name_from_id(prompt_id)
    path = _asset_dir(root, kind) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Prompt asset not found: {path}")
    return path


def _collect_placeholder_issues(text: str, path: Path, field: str) -> List[str]:
    errors: List[str] = []
    if "{{" not in text:
        return errors
    if "}}" not in text or text.count("{{") != text.count("}}"):
        errors.append(f"{path}: {field} has unbalanced placeholder delimiters.")
    return errors


def _validate_prompt_metadata(path: Path, payload: Dict[str, Any], kind: str) -> List[str]:
    errors: List[str] = []
    metadata = payload.get("prompt_metadata")
    if not isinstance(metadata, dict):
        return [f"{path}: prompt_metadata must be an object."]

    prompt_id = str(metadata.get("id") or "").strip()
    version = str(metadata.get("version") or "").strip()
    status = str(metadata.get("status") or "").strip()
    owner = str(metadata.get("owner") or "").strip()
    updated_at = str(metadata.get("updated_at") or "").strip()
    expected_id = f"{kind}.{path.stem}"

    if prompt_id != expected_id:
        errors.append(f"{path}: prompt_metadata.id must equal '{expected_id}' (got '{prompt_id}').")
    if not version:
        errors.append(f"{path}: prompt_metadata.version is required.")
    if status not in VALID_STATUSES:
        errors.append(f"{path}: prompt_metadata.status must be one of {sorted(VALID_STATUSES)}.")
    if not owner:
        errors.append(f"{path}: prompt_metadata.owner is required.")
    if not updated_at:
        errors.append(f"{path}: prompt_metadata.updated_at is required.")

    lineage = metadata.get("lineage")
    if not isinstance(lineage, dict):
        errors.append(f"{path}: prompt_metadata.lineage must be an object.")
    else:
        parent = lineage.get("parent")
        if parent is not None and not str(parent).strip():
            errors.append(f"{path}: prompt_metadata.lineage.parent must be null or non-empty.")

    changelog = metadata.get("changelog")
    if not isinstance(changelog, list) or not changelog:
        errors.append(f"{path}: prompt_metadata.changelog must be a non-empty list.")
    else:
        versions = set()
        for idx, entry in enumerate(changelog):
            if not isinstance(entry, dict):
                errors.append(f"{path}: prompt_metadata.changelog[{idx}] must be an object.")
                continue
            v = str(entry.get("version") or "").strip()
            d = str(entry.get("date") or "").strip()
            n = str(entry.get("notes") or "").strip()
            if not v:
                errors.append(f"{path}: prompt_metadata.changelog[{idx}].version missing.")
            if not d:
                errors.append(f"{path}: prompt_metadata.changelog[{idx}].date missing.")
            if not n:
                errors.append(f"{path}: prompt_metadata.changelog[{idx}].notes missing.")
            if v:
                versions.add(v)
        if version and version not in versions:
            errors.append(f"{path}: prompt_metadata.version '{version}' missing from changelog entries.")

    text_fields: List[Tuple[str, str]] = []
    for key in ("prompt", "description", "dsl_format", "hallucination_guard"):
        if key in payload and isinstance(payload.get(key), str):
            text_fields.append((key, str(payload[key])))
    constraints = payload.get("constraints")
    if isinstance(constraints, list):
        for idx, value in enumerate(constraints):
            if isinstance(value, str):
                text_fields.append((f"constraints[{idx}]", value))

    for field_name, text in text_fields:
        errors.extend(_collect_placeholder_issues(text, path, field_name))
    return errors


def validate_prompt_assets(root: Path) -> List[str]:
    lint = lint_prompt_assets(root)
    return [item["message"] for item in lint["errors"]]


def lint_prompt_assets(root: Path) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    for kind in ("role", "dialect"):
        for path in _iter_assets(root, kind):
            violations.extend(lint_prompt_file(path, kind))
    errors = [item for item in violations if str(item.get("severity") or "") == "strict"]
    warnings = [item for item in violations if str(item.get("severity") or "") != "strict"]
    # Keep CLI-compatible "message" field with file context.
    for item in violations:
        file_path = str(item.get("file") or "").strip()
        message = str(item.get("message") or "").strip()
        item["message"] = f"{file_path}: [{item.get('rule_id')}] {message}"
    return {
        "ok": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "violations": violations,
    }


def list_prompts(root: Path, kind: str = "all", status: str = "") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    kinds = ("role", "dialect") if kind == "all" else (kind,)
    for item_kind in kinds:
        for path in _iter_assets(root, item_kind):
            payload = _load_json(path)
            metadata = payload.get("prompt_metadata") or {}
            row = {
                "kind": item_kind,
                "name": path.stem,
                "path": str(path),
                "id": metadata.get("id"),
                "version": metadata.get("version"),
                "status": metadata.get("status"),
                "owner": metadata.get("owner"),
                "updated_at": metadata.get("updated_at"),
            }
            if status and str(row.get("status") or "").strip() != status:
                continue
            rows.append(row)
    return rows


def show_prompt(root: Path, prompt_id: str) -> Dict[str, Any]:
    path = _asset_path_by_id(root, prompt_id)
    payload = _load_json(path)
    return {"path": str(path), "payload": payload}


def _load_role(root: Path, role_name: str) -> RoleConfig:
    return RoleConfig.model_validate(_load_json(_asset_dir(root, "role") / f"{role_name}.json"))


def _load_dialect(root: Path, dialect_name: str) -> DialectConfig:
    return DialectConfig.model_validate(_load_json(_asset_dir(root, "dialect") / f"{dialect_name}.json"))


def resolve_prompt(
    root: Path,
    *,
    role: str,
    dialect: str,
    selection_policy: str = "stable",
    version_exact: str = "",
    strict: bool = True,
    profile: str = "default",
) -> Dict[str, Any]:
    role_cfg = _load_role(root, role)
    dialect_cfg = _load_dialect(root, dialect)
    skill = SkillConfig(
        name=role_cfg.name or role,
        intent=role_cfg.description,
        responsibilities=[role_cfg.description],
        tools=list(role_cfg.tools or []),
        prompt_metadata=dict(role_cfg.prompt_metadata or {}),
    )
    resolution = PromptResolver.resolve(
        skill=skill,
        dialect=dialect_cfg,
        selection_policy=selection_policy,
        context={
            "prompt_context_profile": profile,
            "prompt_resolver_policy": "resolver_v1",
            "prompt_selection_policy": selection_policy,
            "prompt_selection_strict": bool(strict),
            "prompt_version_exact": version_exact.strip(),
        },
    )
    return {
        "prompt": resolution.system_prompt,
        "metadata": resolution.metadata,
        "layers": resolution.layers,
    }


def _append_changelog(metadata: Dict[str, Any], *, version: str, notes: str) -> None:
    changelog = metadata.setdefault("changelog", [])
    if not isinstance(changelog, list):
        changelog = []
        metadata["changelog"] = changelog
    changelog.append(
        {
            "version": version,
            "date": date.today().isoformat(),
            "notes": notes,
        }
    )


def update_prompt_metadata(
    root: Path,
    *,
    prompt_id: str,
    mode: str,
    version: str = "",
    status: str = "",
    notes: str = "",
    apply_changes: bool = False,
) -> Dict[str, Any]:
    path = _asset_path_by_id(root, prompt_id)
    payload = _load_json(path)
    metadata = dict(payload.get("prompt_metadata") or {})
    old_version = str(metadata.get("version") or "").strip()
    old_status = str(metadata.get("status") or "").strip()
    lineage = metadata.get("lineage")
    if not isinstance(lineage, dict):
        lineage = {"parent": None}
    metadata["lineage"] = lineage

    if mode == "new":
        next_version = str(version or "").strip()
        if not next_version:
            raise ValueError("new requires --version")
        next_status = str(status or "draft").strip()
        if next_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {next_status}")
        lineage["parent"] = old_version or None
        metadata["version"] = next_version
        metadata["status"] = next_status
        metadata["updated_at"] = date.today().isoformat()
        _append_changelog(metadata, version=next_version, notes=notes or "New prompt version created.")
    elif mode == "promote":
        target_status = str(status or "stable").strip()
        if target_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {target_status}")
        metadata["status"] = target_status
        metadata["updated_at"] = date.today().isoformat()
        _append_changelog(
            metadata,
            version=str(metadata.get("version") or old_version or "unknown"),
            notes=notes or f"Prompt promoted to {target_status}.",
        )
    elif mode == "deprecate":
        metadata["status"] = "deprecated"
        metadata["updated_at"] = date.today().isoformat()
        _append_changelog(
            metadata,
            version=str(metadata.get("version") or old_version or "unknown"),
            notes=notes or "Prompt deprecated.",
        )
    else:
        raise ValueError(f"Unsupported update mode: {mode}")

    payload["prompt_metadata"] = metadata
    if apply_changes:
        _save_json(path, payload)
    return {
        "path": str(path),
        "mode": mode,
        "apply_changes": apply_changes,
        "before": {"version": old_version, "status": old_status},
        "after": {"version": metadata.get("version"), "status": metadata.get("status")},
        "metadata": metadata,
    }


def _print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt asset tooling for Orket.")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root containing model/core assets.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List prompt assets.")
    p_list.add_argument("--kind", choices=["all", "role", "dialect"], default="all")
    p_list.add_argument("--status", default="")
    p_list.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="Show one prompt asset by id.")
    p_show.add_argument("--id", required=True, help="Prompt id: role.<name> or dialect.<name>")

    p_validate = sub.add_parser("validate", help="Validate prompt asset contracts.")
    p_validate.add_argument("--json", action="store_true")

    p_resolve = sub.add_parser("resolve", help="Resolve effective prompt for role+dialect.")
    p_resolve.add_argument("--role", required=True)
    p_resolve.add_argument("--dialect", required=True)
    p_resolve.add_argument("--selection-policy", choices=["stable", "canary", "exact"], default="stable")
    p_resolve.add_argument("--version-exact", default="")
    p_resolve.add_argument("--strict", action="store_true", default=True)
    p_resolve.add_argument("--profile", default="default")
    p_resolve.add_argument("--include-prompt", action="store_true")

    p_diff = sub.add_parser("diff", help="Diff resolved prompt outputs across policy/version selections.")
    p_diff.add_argument("--role", required=True)
    p_diff.add_argument("--dialect", required=True)
    p_diff.add_argument("--left-policy", choices=["stable", "canary", "exact"], default="stable")
    p_diff.add_argument("--left-version-exact", default="")
    p_diff.add_argument("--right-policy", choices=["stable", "canary", "exact"], default="canary")
    p_diff.add_argument("--right-version-exact", default="")
    p_diff.add_argument("--strict", action="store_true", default=True)

    p_new = sub.add_parser("new", help="Create new prompt version metadata entry.")
    p_new.add_argument("--id", required=True)
    p_new.add_argument("--version", required=True)
    p_new.add_argument("--status", choices=sorted(VALID_STATUSES), default="draft")
    p_new.add_argument("--notes", default="")
    p_new.add_argument("--apply", action="store_true")

    p_promote = sub.add_parser("promote", help="Promote prompt status.")
    p_promote.add_argument("--id", required=True)
    p_promote.add_argument("--status", choices=sorted(VALID_STATUSES), default="stable")
    p_promote.add_argument("--notes", default="")
    p_promote.add_argument("--apply", action="store_true")

    p_deprecate = sub.add_parser("deprecate", help="Deprecate a prompt.")
    p_deprecate.add_argument("--id", required=True)
    p_deprecate.add_argument("--notes", default="")
    p_deprecate.add_argument("--apply", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.cmd == "list":
        rows = list_prompts(root, kind=args.kind, status=args.status)
        if args.json:
            _print_json({"count": len(rows), "items": rows})
        else:
            for row in rows:
                print(
                    f"{row['id']}  kind={row['kind']} status={row['status']} "
                    f"version={row['version']} path={row['path']}"
                )
        return 0

    if args.cmd == "show":
        _print_json(show_prompt(root, args.id))
        return 0

    if args.cmd == "validate":
        lint = lint_prompt_assets(root)
        payload = {
            "ok": lint["ok"],
            "error_count": lint["error_count"],
            "warning_count": lint["warning_count"],
            "errors": [item["message"] for item in lint["errors"]],
            "warnings": [item["message"] for item in lint["warnings"]],
        }
        if args.json or lint["error_count"]:
            _print_json(payload)
        if lint["error_count"]:
            return 1
        print("Prompt assets valid.")
        return 0

    if args.cmd == "resolve":
        resolved = resolve_prompt(
            root,
            role=args.role,
            dialect=args.dialect,
            selection_policy=args.selection_policy,
            version_exact=args.version_exact,
            strict=bool(args.strict),
            profile=args.profile,
        )
        payload = {
            "metadata": resolved["metadata"],
            "layers": resolved["layers"],
        }
        if args.include_prompt:
            payload["prompt"] = resolved["prompt"]
        _print_json(payload)
        return 0

    if args.cmd == "diff":
        left = resolve_prompt(
            root,
            role=args.role,
            dialect=args.dialect,
            selection_policy=args.left_policy,
            version_exact=args.left_version_exact,
            strict=bool(args.strict),
        )
        right = resolve_prompt(
            root,
            role=args.role,
            dialect=args.dialect,
            selection_policy=args.right_policy,
            version_exact=args.right_version_exact,
            strict=bool(args.strict),
        )
        left_prompt = str(left["prompt"] or "").splitlines()
        right_prompt = str(right["prompt"] or "").splitlines()
        diff_lines = list(
            difflib.unified_diff(
                left_prompt,
                right_prompt,
                fromfile=f"{args.left_policy}:{args.left_version_exact or 'auto'}",
                tofile=f"{args.right_policy}:{args.right_version_exact or 'auto'}",
                lineterm="",
            )
        )
        _print_json(
            {
                "left_metadata": left["metadata"],
                "right_metadata": right["metadata"],
                "prompt_diff": diff_lines,
            }
        )
        return 0

    if args.cmd in {"new", "promote", "deprecate"}:
        result = update_prompt_metadata(
            root,
            prompt_id=args.id,
            mode=args.cmd,
            version=getattr(args, "version", ""),
            status=getattr(args, "status", ""),
            notes=getattr(args, "notes", ""),
            apply_changes=bool(getattr(args, "apply", False)),
        )
        _print_json(result)
        return 0

    parser.error(f"Unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
