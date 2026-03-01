from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from orket.application.review.models import ResolvedPolicy, digest_sha256_prefixed, to_canonical_json_bytes
from orket.settings import load_user_settings


DEFAULT_POLICY: Dict[str, Any] = {
    "policy_version": "review_policy_v0",
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
            "forbidden_patterns": [r"(?i)\b(todo|fixme)\b", r"(?i)password\s*="],
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


def _read_json_file(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _deep_merge(base: Dict[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, Mapping):
            result[key] = _deep_merge(dict(result[key]), value)
        else:
            result[key] = value
    return result


def resolve_review_policy(
    *,
    cli_overrides: Optional[Mapping[str, Any]] = None,
    repo_root: Path,
    policy_path: Optional[Path] = None,
) -> ResolvedPolicy:
    repo_policy_path = policy_path or (repo_root / ".orket" / "review_policy.json")
    repo_policy = _read_json_file(repo_policy_path)
    user_settings = load_user_settings()
    user_policy = user_settings.get("review_policy") if isinstance(user_settings.get("review_policy"), dict) else {}

    merged = _deep_merge(dict(DEFAULT_POLICY), user_policy or {})
    merged = _deep_merge(merged, repo_policy)
    merged = _deep_merge(merged, dict(cli_overrides or {}))

    digest = digest_sha256_prefixed(to_canonical_json_bytes(merged))
    return ResolvedPolicy(payload=merged, policy_digest=digest)

