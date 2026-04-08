from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from orket.application.review.models import ResolvedPolicy, digest_sha256_prefixed, to_canonical_json_bytes
from orket.logging import log_event
from orket.settings import load_user_settings

DEFAULT_POLICY: dict[str, Any] = {
    "policy_version": "review_policy_v0",
    "input_scope": {
        "mode": "code_only",
        "code_extensions": [
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".go",
            ".rs",
            ".java",
            ".kt",
            ".rb",
            ".php",
            ".cs",
            ".c",
            ".cc",
            ".cpp",
            ".h",
            ".hpp",
            ".swift",
            ".scala",
            ".sh",
            ".ps1",
            ".sql",
        ],
    },
    "lanes": {"enabled": ["deterministic"]},
    "bounds": {
        "max_files": 200,
        "max_diff_bytes": 1_000_000,
        "max_blob_bytes": 200_000,
        "max_file_bytes": 100_000,
    },
    "deterministic": {
        "checks": {
            "path_blocklist": [],
            "forbidden_patterns": [
                {"pattern": r"(?i)\b(todo|fixme)\b", "severity": "info"},
                {"pattern": r"(?i)password\s*=\s*['\"](?!\s*['\"])", "severity": "high"},
            ],
            "test_hint_required_roots": ["src/", "orket/"],
            "test_hint_test_roots": ["tests/"],
        }
    },
    "model_assisted": {
        "enabled": False,
        "model_id": "",
        "prompt_profile": "review_critique_v0",
        "contract_version": "review_critique_v0",
        "max_input_bytes": 100_000,
    },
}

_KNOWN_POLICY_KEYS = set(DEFAULT_POLICY)


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_bytes().decode("utf-8"))
    except json.JSONDecodeError as exc:
        log_event(
            "review_policy_file_malformed",
            {"path": str(path), "error": str(exc)},
            level="warn",
        )
        return {}
    except OSError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _warn_unknown_policy_keys(payload: Mapping[str, Any], *, source: str) -> None:
    unknown = sorted(str(key) for key in payload if str(key) not in _KNOWN_POLICY_KEYS)
    if unknown:
        log_event(
            "review_policy_unknown_keys",
            {"source": source, "keys": unknown},
            level="warn",
        )


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, Mapping):
            result[key] = _deep_merge(dict(result[key]), value)
        else:
            result[key] = value
    return result


def resolve_review_policy(
    *,
    cli_overrides: Mapping[str, Any] | None = None,
    repo_root: Path,
    policy_path: Path | None = None,
) -> ResolvedPolicy:
    repo_policy_path = policy_path or (repo_root / ".orket" / "review_policy.json")
    repo_policy = _read_json_file(repo_policy_path)
    user_settings = load_user_settings()
    user_policy = user_settings.get("review_policy") if isinstance(user_settings.get("review_policy"), dict) else {}
    _warn_unknown_policy_keys(repo_policy, source=str(repo_policy_path))
    _warn_unknown_policy_keys(user_policy or {}, source="user_settings.review_policy")
    _warn_unknown_policy_keys(dict(cli_overrides or {}), source="cli_overrides")

    merged = _deep_merge(dict(DEFAULT_POLICY), user_policy or {})
    merged = _deep_merge(merged, repo_policy)
    merged = _deep_merge(merged, dict(cli_overrides or {}))

    digest = digest_sha256_prefixed(to_canonical_json_bytes(merged))
    return ResolvedPolicy(payload=merged, policy_digest=digest)
