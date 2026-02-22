#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TRIPLET_SUFFIXES = {
    ".body.json": "body",
    ".links.json": "links",
    ".manifest.json": "manifest",
}

STAGE_ORDER = {
    "base_shape": 0,
    "dto_links": 1,
    "relationship_vocabulary": 2,
    "policy": 3,
    "determinism": 4,
}

TYPED_MAPPING: dict[str, dict[str, set[str]]] = {
    "invocation": {
        "skill": {"skill"},
        "entrypoint": {"entrypoint"},
        "validation_result": {"validation_result"},
        "trace_events": {"trace_event"},
    },
    "validation_result": {
        "skill": {"skill"},
        "entrypoint": {"entrypoint"},
        "tool_profile": {"tool_profile"},
        "invocation": {"invocation"},
        "artifacts": {"artifact"},
        "trace_events": {"trace_event"},
    },
}

RELATIONSHIP_VOCABULARY = {
    "declares": {
        "cardinality": "one",
        "allowed_source_dto_types": {"invocation", "validation_result"},
        "allowed_target_reference_types": {"skill", "entrypoint", "tool_profile"},
    },
    "derives_from": {
        "cardinality": "many",
        "allowed_source_dto_types": {"validation_result"},
        "allowed_target_reference_types": {"artifact"},
    },
    "validates": {
        "cardinality": "one",
        "allowed_source_dto_types": {"validation_result"},
        "allowed_target_reference_types": {"invocation"},
    },
    "produces": {
        "cardinality": "many",
        "allowed_source_dto_types": {"invocation", "validation_result"},
        "allowed_target_reference_types": {"trace_event"},
    },
    "causes": {
        "cardinality": "many",
        "allowed_source_dto_types": {"invocation", "validation_result"},
        "allowed_target_reference_types": {"trace_event", "artifact"},
    },
}

RAW_ID_FORBIDDEN_TOKENS = {
    "skill_id",
    "entrypoint_id",
    "validation_result_id",
    "invocation_id",
    "artifact_id",
    "trace_event_id",
    "tool_profile_id",
    "workspace_id",
    "pending_gate_request_id",
}


def _resolve_log_format_version() -> int:
    raw = os.getenv("LOG_FORMAT_VERSION", "1").strip()
    try:
        parsed = int(raw)
    except ValueError:
        return 1
    return parsed if parsed > 0 else 1


LOG_FORMAT_VERSION = _resolve_log_format_version()

VALID_STAGES = set(STAGE_ORDER)
_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]+$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class GatekeeperIssue:
    stage: str
    code: str
    location: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompleteTriplet:
    stem: str
    body_path: str
    links_path: str
    manifest_path: str


@dataclass(frozen=True)
class PluginContext:
    triplet: CompleteTriplet


@dataclass(frozen=True)
class PluginEvent:
    level: str
    stage: str
    code: str
    location: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Reporter:
    errors: int = 0
    warnings: int = 0
    lines: list[str] = field(default_factory=list)

    def emit(
        self,
        level: str,
        code: str,
        location: str,
        message: str,
        *,
        stage: str = "ci",
        **details: Any,
    ) -> None:
        escaped_message = _escape_inline(message)
        details_text = _format_details_json(details) if LOG_FORMAT_VERSION >= 2 else _format_details_legacy(details)
        line = f"[{level}] [STAGE:{stage}] [CODE:{code}] [LOC:{location}] {escaped_message} | {details_text}"
        print(line)
        self.lines.append(line)
        if level == "FAIL":
            self.errors += 1

    def summary(self) -> int:
        outcome = "FAIL" if self.errors > 0 else "PASS"
        line = f"[SUMMARY] outcome={outcome} stage=ci errors={self.errors} warnings={self.warnings}"
        print(line)
        self.lines.append(line)
        return 1 if self.errors > 0 else 0


def _stem_label(stem: str) -> str:
    return Path(stem).name


def _candidate_stem(value: str) -> str | None:
    token = value.strip()
    if not token:
        return None
    if ":" in token:
        token = token.split(":", 1)[0]
    if "/" in token:
        token = token.strip("/").split("/")[-1]
    if _TOKEN_RE.fullmatch(token):
        return token
    return None


def _reference_candidate_stem(reference: dict[str, Any]) -> str | None:
    namespace = reference.get("namespace")
    if isinstance(namespace, str):
        candidate = _candidate_stem(namespace)
        if candidate:
            return candidate
    ref_id = reference.get("id")
    if isinstance(ref_id, str):
        return _candidate_stem(ref_id)
    return None


def _related_stems_plugin(ctx: PluginContext) -> list[PluginEvent]:
    links_path = Path(ctx.triplet.links_path)
    try:
        links_obj = json.loads(links_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(links_obj, dict):
        return []

    source = _stem_label(ctx.triplet.stem)
    related: set[str] = set()
    for value in links_obj.values():
        refs = value if isinstance(value, list) else [value]
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            candidate = _reference_candidate_stem(ref)
            if candidate and candidate != source:
                related.add(candidate)

    return [
        PluginEvent(
            level="INFO",
            stage="relationship_vocabulary",
            code="I_VOCAB_LINKS_RESOLVED",
            location="/links",
            message=f"Resolved links for stem {source}",
            details={"stem": ctx.triplet.stem, "related_stems": sorted(related)},
        )
    ]


PLUGIN_REGISTRY: dict[str, Any] = {
    "related_stems": _related_stems_plugin,
}


def _enabled_plugins() -> list[str]:
    raw = os.getenv("ENABLED_SENTINEL_PLUGINS", "related_stems")
    selected = []
    for item in raw.split(","):
        token = item.strip()
        if token:
            selected.append(token)
    return selected


def _validate_plugin_event(event: PluginEvent) -> str | None:
    if event.level not in {"INFO", "FAIL"}:
        return "level"
    if event.stage not in VALID_STAGES:
        return "stage"
    if not _CODE_RE.fullmatch(event.code):
        return "code"
    if not isinstance(event.location, str) or not event.location.startswith("/"):
        return "location"
    if not isinstance(event.message, str) or not event.message:
        return "message"
    if not isinstance(event.details, dict):
        return "details"
    return None


class Gatekeeper:
    def __init__(self, triplet: CompleteTriplet):
        self._triplet = triplet
        self._body: Any = None
        self._links: Any = None
        self._manifest: Any = None
        self._dto_type: str | None = None

    def validate(self) -> list[GatekeeperIssue]:
        issues: list[GatekeeperIssue] = []
        issues.extend(self._load_json_artifacts())
        if issues:
            return self._sorted_failures(issues)

        issues.extend(self._validate_base_shape())
        issues.extend(self._validate_dto_links())
        issues.extend(self._validate_relationship_vocabulary())
        issues.extend(self._validate_policy())
        issues.extend(self._validate_determinism())
        return self._sorted_failures(issues)

    def _load_json_artifacts(self) -> list[GatekeeperIssue]:
        loaded: dict[str, Any] = {}
        files = {
            "body": self._triplet.body_path,
            "links": self._triplet.links_path,
            "manifest": self._triplet.manifest_path,
        }
        issues: list[GatekeeperIssue] = []

        for name in ("body", "links", "manifest"):
            path = files[name]
            root = f"/{name}"
            try:
                text = Path(path).read_text(encoding="utf-8")
                loaded[name] = json.loads(text)
            except Exception as exc:  # noqa: BLE001
                issues.append(
                    GatekeeperIssue(
                        stage="base_shape",
                        code="E_BASE_SHAPE_INVALID_JSON",
                        location=root,
                        message="Triplet member failed JSON parse.",
                        details={"path": path, "error": str(exc)},
                    )
                )

        if issues:
            return issues

        self._body = loaded["body"]
        self._links = loaded["links"]
        self._manifest = loaded["manifest"]
        self._dto_type = self._infer_dto_type()
        return issues

    def _infer_dto_type(self) -> str | None:
        candidates: list[Any] = []
        if isinstance(self._body, dict):
            candidates.append(self._body.get("dto_type"))
            candidates.append(self._body.get("type"))
        if isinstance(self._manifest, dict):
            candidates.append(self._manifest.get("dto_type"))
            candidates.append(self._manifest.get("type"))

        for candidate in candidates:
            if isinstance(candidate, str):
                normalized = candidate.strip().lower()
                if normalized in TYPED_MAPPING:
                    return normalized

        stem_name = Path(self._triplet.stem).name.lower()
        for dto_type in TYPED_MAPPING:
            if dto_type in stem_name:
                return dto_type
        return None

    def _validate_base_shape(self) -> list[GatekeeperIssue]:
        issues: list[GatekeeperIssue] = []
        if not isinstance(self._body, dict):
            issues.append(
                GatekeeperIssue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_BODY_VALUE",
                    location="/body",
                    message="Triplet body must be a JSON object.",
                    details={"actual_type": type(self._body).__name__},
                )
            )
        if not isinstance(self._links, dict):
            issues.append(
                GatekeeperIssue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_LINKS_VALUE",
                    location="/links",
                    message="Triplet links must be a JSON object.",
                    details={"actual_type": type(self._links).__name__},
                )
            )
            return issues
        if not isinstance(self._manifest, dict):
            issues.append(
                GatekeeperIssue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_MANIFEST_VALUE",
                    location="/manifest",
                    message="Triplet manifest must be a JSON object.",
                    details={"actual_type": type(self._manifest).__name__},
                )
            )

        for key in sorted(self._links):
            pointer = f"/links/{_pointer_token(key)}"
            value = self._links[key]
            if isinstance(value, dict):
                issues.extend(self._validate_reference(value, pointer))
                continue
            if isinstance(value, list):
                for index, item in enumerate(value):
                    ref_pointer = f"{pointer}/{index}"
                    if not isinstance(item, dict):
                        issues.append(
                            GatekeeperIssue(
                                stage="base_shape",
                                code="E_BASE_SHAPE_INVALID_LINKS_VALUE",
                                location=ref_pointer,
                                message="Array links value must contain reference objects.",
                                details={"actual_type": type(item).__name__},
                            )
                        )
                        continue
                    issues.extend(self._validate_reference(item, ref_pointer))
                continue
            issues.append(
                GatekeeperIssue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_LINKS_VALUE",
                    location=pointer,
                    message="Links value is not a valid object or reference shape.",
                    details={"actual_type": type(value).__name__},
                )
            )
        return issues

    def _validate_reference(self, value: dict[str, Any], pointer: str) -> list[GatekeeperIssue]:
        issues: list[GatekeeperIssue] = []
        ref_type = value.get("type")
        ref_id = value.get("id")
        if not isinstance(ref_type, str) or not ref_type:
            issues.append(
                GatekeeperIssue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_REFERENCE",
                    location=f"{pointer}/type",
                    message="Reference object requires non-empty string 'type'.",
                )
            )
        if not isinstance(ref_id, str) or not ref_id:
            issues.append(
                GatekeeperIssue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_REFERENCE",
                    location=f"{pointer}/id",
                    message="Reference object requires non-empty string 'id'.",
                )
            )
        return issues

    def _validate_dto_links(self) -> list[GatekeeperIssue]:
        issues: list[GatekeeperIssue] = []
        if not isinstance(self._links, dict):
            return issues

        if not self._dto_type or self._dto_type not in TYPED_MAPPING:
            issues.append(
                GatekeeperIssue(
                    stage="dto_links",
                    code="E_DTO_LINKS_UNKNOWN_KEY",
                    location="/body/dto_type",
                    message="Unknown dto_type for links validation.",
                    details={"dto_type": self._dto_type},
                )
            )
            return issues

        mapping = TYPED_MAPPING[self._dto_type]
        for key in sorted(self._links):
            pointer = f"/links/{_pointer_token(key)}"
            value = self._links[key]
            if key not in mapping:
                issues.append(
                    GatekeeperIssue(
                        stage="dto_links",
                        code="E_DTO_LINKS_UNKNOWN_KEY",
                        location=pointer,
                        message="Unknown links key for the specified DTO type.",
                        details={"dto_type": self._dto_type, "key": key},
                    )
                )
                continue

            expects_array = key in {"artifacts", "trace_events"}
            if expects_array and not isinstance(value, list):
                issues.append(
                    GatekeeperIssue(
                        stage="dto_links",
                        code="E_DTO_LINKS_WRONG_CONTAINER_SHAPE",
                        location=pointer,
                        message="Scalar/Array container mismatch for links key.",
                        details={"expected": "array", "actual_type": type(value).__name__},
                    )
                )
                continue
            if not expects_array and not isinstance(value, dict):
                issues.append(
                    GatekeeperIssue(
                        stage="dto_links",
                        code="E_DTO_LINKS_WRONG_CONTAINER_SHAPE",
                        location=pointer,
                        message="Scalar/Array container mismatch for links key.",
                        details={"expected": "object", "actual_type": type(value).__name__},
                    )
                )
                continue

            refs = value if isinstance(value, list) else [value]
            for index, ref in enumerate(refs):
                ref_pointer = f"{pointer}/{index}" if isinstance(value, list) else pointer
                if not isinstance(ref, dict):
                    continue
                ref_type = ref.get("type")
                if not isinstance(ref_type, str) or ref_type not in mapping[key]:
                    issues.append(
                        GatekeeperIssue(
                            stage="dto_links",
                            code="E_TYPED_REF_MISMATCH",
                            location=f"{ref_pointer}/type",
                            message="Reference.type not allowed for this links key.",
                            details={"allowed": sorted(mapping[key]), "actual": ref_type, "key": key},
                        )
                    )
        return issues

    def _validate_relationship_vocabulary(self) -> list[GatekeeperIssue]:
        issues: list[GatekeeperIssue] = []
        if not isinstance(self._links, dict) or not self._dto_type:
            return issues

        relationship_counts: dict[str, int] = {}
        for key in sorted(self._links):
            value = self._links[key]
            refs = value if isinstance(value, list) else [value]
            for index, ref in enumerate(refs):
                if not isinstance(ref, dict):
                    continue
                ref_type = ref.get("type")
                relationship = ref.get("relationship")
                pointer = f"/links/{_pointer_token(key)}"
                if isinstance(value, list):
                    pointer = f"{pointer}/{index}"

                if not isinstance(relationship, str) or relationship not in RELATIONSHIP_VOCABULARY:
                    issues.append(
                        GatekeeperIssue(
                            stage="relationship_vocabulary",
                            code="E_RELATIONSHIP_INCOMPATIBLE",
                            location=f"{pointer}/relationship",
                            message="Relationship triplet not permitted for this source/target pair.",
                            details={
                                "dto_type": self._dto_type,
                                "relationship": relationship,
                                "ref_type": ref_type,
                            },
                        )
                    )
                    continue

                rel_rule = RELATIONSHIP_VOCABULARY[relationship]
                if (
                    self._dto_type not in rel_rule["allowed_source_dto_types"]
                    or not isinstance(ref_type, str)
                    or ref_type not in rel_rule["allowed_target_reference_types"]
                ):
                    issues.append(
                        GatekeeperIssue(
                            stage="relationship_vocabulary",
                            code="E_RELATIONSHIP_INCOMPATIBLE",
                            location=pointer,
                            message="Relationship triplet not permitted for this source/target pair.",
                            details={
                                "dto_type": self._dto_type,
                                "relationship": relationship,
                                "ref_type": ref_type,
                            },
                        )
                    )
                    continue

                relationship_counts[relationship] = relationship_counts.get(relationship, 0) + 1

        for relationship, count in sorted(relationship_counts.items()):
            rel_rule = RELATIONSHIP_VOCABULARY[relationship]
            if rel_rule["cardinality"] == "one" and count > 1:
                issues.append(
                    GatekeeperIssue(
                        stage="relationship_vocabulary",
                        code="E_RELATIONSHIP_CARDINALITY_VIOLATION",
                        location="/links",
                        message="Relationship cardinality (one) exceeded.",
                        details={"relationship": relationship, "count": count},
                    )
                )

        return issues

    def _validate_policy(self) -> list[GatekeeperIssue]:
        issues: list[GatekeeperIssue] = []
        allowed_local_ids: set[str] = set()
        if isinstance(self._manifest, dict):
            policy_obj = self._manifest.get("policy")
            if isinstance(policy_obj, dict):
                local_ids = policy_obj.get("allowed_local_ids")
                if isinstance(local_ids, list):
                    allowed_local_ids = {value for value in local_ids if isinstance(value, str)}

        for root_name, value in (("/body", self._body), ("/links", self._links)):
            issues.extend(self._scan_raw_ids(value, root_name, allowed_local_ids))

        return issues

    def _scan_raw_ids(self, value: Any, pointer: str, allowed_local_ids: set[str]) -> list[GatekeeperIssue]:
        issues: list[GatekeeperIssue] = []
        if isinstance(value, dict):
            for key in sorted(value):
                key_pointer = f"{pointer}/{_pointer_token(key)}"
                violating_token = self._match_forbidden_token(key, allowed_local_ids)
                if violating_token is not None:
                    issues.append(
                        GatekeeperIssue(
                            stage="policy",
                            code="E_POLICY_RAW_ID_FORBIDDEN",
                            location=key_pointer,
                            message="Forbidden raw ID token detected in DTO keys.",
                            details={"key": key, "token": violating_token},
                        )
                    )
                issues.extend(self._scan_raw_ids(value[key], key_pointer, allowed_local_ids))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                issues.extend(self._scan_raw_ids(item, f"{pointer}/{index}", allowed_local_ids))
        return issues

    def _match_forbidden_token(self, key: str, allowed_local_ids: set[str]) -> str | None:
        if key in allowed_local_ids:
            return None
        for token in sorted(RAW_ID_FORBIDDEN_TOKENS):
            if key == token or key.endswith("_" + token):
                return token
        return None

    def _validate_determinism(self) -> list[GatekeeperIssue]:
        issues: list[GatekeeperIssue] = []
        if not isinstance(self._manifest, dict) or not isinstance(self._links, dict):
            return issues

        order_insensitive = self._manifest.get("order_insensitive")
        if order_insensitive is None:
            determinism_obj = self._manifest.get("determinism")
            if isinstance(determinism_obj, dict):
                order_insensitive = determinism_obj.get("order_insensitive")

        if not isinstance(order_insensitive, list):
            issues.append(
                GatekeeperIssue(
                    stage="determinism",
                    code="E_DETERMINISM_VIOLATION",
                    location="/manifest/order_insensitive",
                    message="Determinism manifest must define order_insensitive array.",
                    details={"actual_type": type(order_insensitive).__name__},
                )
            )
            return issues

        for index, key in enumerate(order_insensitive):
            key_pointer = f"/manifest/order_insensitive/{index}"
            if not isinstance(key, str):
                issues.append(
                    GatekeeperIssue(
                        stage="determinism",
                        code="E_DETERMINISM_VIOLATION",
                        location=key_pointer,
                        message="Determinism keys must be strings.",
                        details={"actual_type": type(key).__name__},
                    )
                )
                continue
            if key not in self._links or not isinstance(self._links[key], list):
                issues.append(
                    GatekeeperIssue(
                        stage="determinism",
                        code="E_DETERMINISM_VIOLATION",
                        location=key_pointer,
                        message="Determinism key must exist as array-valued links key.",
                        details={"key": key},
                    )
                )

        return issues

    def _sorted_failures(self, issues: list[GatekeeperIssue]) -> list[GatekeeperIssue]:
        return sorted(
            issues,
            key=lambda issue: (
                STAGE_ORDER.get(issue.stage, 99),
                issue.location,
                issue.code,
                _format_details_legacy(issue.details),
            ),
        )


def _escape_inline(value: str) -> str:
    return value.replace("|", r"\u007c").replace("\r", r"\r").replace("\n", r"\n")


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _format_value_legacy(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return _escape_inline(rendered)
    return _escape_inline(str(value))


def _format_details_legacy(details: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in sorted(details):
        parts.append(f"{key}={_format_value_legacy(details[key])}")
    return " ".join(parts)


def _sanitize_json_payload(value: Any) -> Any:
    if isinstance(value, str):
        return _escape_inline(value)
    if isinstance(value, list):
        return [_sanitize_json_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_json_payload(item) for key, item in value.items()}
    return value


def _format_details_json(details: dict[str, Any]) -> str:
    sanitized = _sanitize_json_payload(details)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _git_ref_exists(ref: str) -> bool:
    probe = _run_git(["rev-parse", "--verify", "--quiet", ref])
    return probe.returncode == 0


def _resolve_base_ref() -> str | None:
    # Explicit overrides first.
    direct_env = [os.getenv("BASE_REF"), os.getenv("CI_BASE_REF")]
    for ref in direct_env:
        if ref and _git_ref_exists(ref):
            return ref

    # Common PR base branch env names.
    branch_env = [
        os.getenv("GITHUB_BASE_REF"),
        os.getenv("GITEA_BASE_REF"),
    ]
    for branch in branch_env:
        if not branch:
            continue
        for candidate in (f"origin/{branch}", branch):
            if _git_ref_exists(candidate):
                return candidate

    # Push "before" SHA style env values.
    sha_env = [
        os.getenv("GITHUB_EVENT_BEFORE"),
        os.getenv("CI_COMMIT_BEFORE_SHA"),
    ]
    for sha in sha_env:
        if not sha:
            continue
        normalized = sha.strip()
        if not normalized or set(normalized) == {"0"}:
            continue
        if _git_ref_exists(normalized):
            return normalized

    return None


def _changed_files(base_ref: str) -> list[str]:
    # Three-dot gives merge-base style PR diff semantics.
    diff = _run_git(["diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...HEAD"])
    if diff.returncode != 0:
        raise RuntimeError(diff.stderr.strip() or "git diff failed")
    changed = [line.strip().replace("\\", "/") for line in diff.stdout.splitlines() if line.strip()]
    return sorted(changed)


def _fixture_dir(name: str) -> Path:
    return Path("tools/ci/fixtures") / name


def _fixture_changed_files(name: str) -> tuple[list[str], list[str]]:
    fixture_root = _fixture_dir(name)
    if not fixture_root.exists():
        raise RuntimeError(f"fixture_not_found:{fixture_root}")
    dto_root = fixture_root / "data" / "dto"
    if not dto_root.exists():
        raise RuntimeError(f"fixture_missing_dto_root:{dto_root}")
    changed = sorted(
        str(path).replace("\\", "/")
        for path in fixture_root.rglob("*.json")
        if path.is_file()
    )
    roots = [str(dto_root).replace("\\", "/")]
    return changed, roots


def _triplet_roots() -> list[str]:
    roots_raw = os.getenv("TRIPLELOCK_ROOTS", "data/dto")
    roots = []
    for value in roots_raw.split(","):
        root = value.strip().replace("\\", "/").strip("/")
        if root:
            roots.append(root)
    return roots


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--test-fixture", dest="test_fixture", default=None)
    return parser.parse_args(argv)


def _is_under_roots(path: str, roots: list[str]) -> bool:
    return any(path == root or path.startswith(root + "/") for root in roots)


def _classify(changed: list[str], roots: list[str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    triplet_candidates: list[tuple[str, str, str]] = []
    solo_json: list[str] = []
    for path in changed:
        if not path.endswith(".json"):
            continue
        matched = False
        if _is_under_roots(path, roots):
            for suffix, member in TRIPLET_SUFFIXES.items():
                if path.endswith(suffix):
                    stem = path[: -len(suffix)]
                    triplet_candidates.append((stem, member, path))
                    matched = True
                    break
        if not matched:
            solo_json.append(path)
    return triplet_candidates, solo_json


def _validate_triplets(
    candidates: list[tuple[str, str, str]],
    reporter: Reporter,
) -> list[CompleteTriplet]:
    stems: dict[str, dict[str, str]] = {}
    for stem, member, path in candidates:
        stems.setdefault(stem, {})[member] = path

    complete_triplets: list[CompleteTriplet] = []
    for stem in sorted(stems):
        mapping = stems[stem]
        required = ("body", "links", "manifest")
        missing = [name for name in required if name not in mapping]
        changed = [mapping[name] for name in required if name in mapping]
        loc = f"/ci/diff/{_pointer_token(stem)}"
        if missing:
            reporter.emit(
                "FAIL",
                "E_TRIPLET_INCOMPLETE",
                loc,
                "Triplet change is incomplete under data/dto.",
                changed=changed,
                missing=missing,
            )
            continue

        reporter.emit(
            "INFO",
            "I_TRIPLET_COMPLETE",
            loc,
            "Triplet complete.",
            changed=changed,
        )
        complete_triplets.append(
            CompleteTriplet(
                stem=stem,
                body_path=mapping["body"],
                links_path=mapping["links"],
                manifest_path=mapping["manifest"],
            )
        )

    return complete_triplets


def _run_plugins(triplet: CompleteTriplet, reporter: Reporter) -> None:
    for plugin_name in _enabled_plugins():
        plugin = PLUGIN_REGISTRY.get(plugin_name)
        if plugin is None:
            reporter.emit(
                "FAIL",
                "E_PLUGIN_UNKNOWN",
                "/ci/plugins",
                "Enabled plugin is not registered.",
                plugin=plugin_name,
            )
            continue
        try:
            events = plugin(PluginContext(triplet=triplet))
        except Exception as exc:  # noqa: BLE001
            reporter.emit(
                "FAIL",
                "E_PLUGIN_EXECUTION_FAILED",
                "/ci/plugins",
                "Plugin execution failed.",
                plugin=plugin_name,
                error=str(exc),
                stem=triplet.stem,
            )
            continue
        for event in events:
            invalid_field = _validate_plugin_event(event)
            if invalid_field is not None:
                reporter.emit(
                    "FAIL",
                    "E_PLUGIN_EVENT_INVALID",
                    "/ci/plugins",
                    "Plugin emitted invalid event shape.",
                    plugin=plugin_name,
                    invalid_field=invalid_field,
                    stem=triplet.stem,
                )
                continue
            reporter.emit(
                event.level,
                event.code,
                event.location,
                event.message,
                stage=event.stage,
                **event.details,
            )


def _run_gatekeeper(triplets: list[CompleteTriplet], reporter: Reporter) -> None:
    for triplet in triplets:
        issues = Gatekeeper(triplet).validate()
        for issue in issues:
            reporter.emit(
                "FAIL",
                issue.code,
                issue.location,
                issue.message,
                stage=issue.stage,
                stem=triplet.stem,
                **issue.details,
            )
        if not issues:
            reporter.emit(
                "INFO",
                "I_GATEKEEPER_PASS",
                "/ci/diff/" + _pointer_token(triplet.stem),
                "Gatekeeper pipeline passed for triplet.",
                stem=triplet.stem,
            )
        _run_plugins(triplet, reporter)


def _validate_solo_json(paths: list[str], reporter: Reporter) -> None:
    for path in sorted(paths):
        loc = f"/ci/schema/{_pointer_token(path)}"
        try:
            text = Path(path).read_text(encoding="utf-8")
            json.loads(text)
        except Exception as exc:  # noqa: BLE001 - normalized to contract error code.
            reporter.emit(
                "FAIL",
                "E_BASE_SHAPE_INVALID_JSON",
                loc,
                "Invalid JSON parse.",
                path=path,
                error=str(exc),
            )
            continue
        reporter.emit(
            "INFO",
            "I_SOLO_JSON_VALID",
            loc,
            "Validated solo JSON parse.",
            path=path,
        )


def main() -> int:
    args = _parse_args()
    reporter = Reporter()
    roots = _triplet_roots()

    changed: list[str]
    if args.test_fixture:
        try:
            changed, roots = _fixture_changed_files(args.test_fixture)
        except Exception as exc:  # noqa: BLE001
            reporter.emit(
                "FAIL",
                "E_FIXTURE_UNAVAILABLE",
                "/ci/fixtures",
                "Unable to load requested test fixture.",
                fixture=args.test_fixture,
                error=str(exc),
            )
            return reporter.summary()
        reporter.emit(
            "INFO",
            "I_FIXTURE_MODE",
            "/ci/fixtures",
            "Running sentinel in fixture mode.",
            fixture=args.test_fixture,
            changed_count=len(changed),
        )
    else:
        base_ref = _resolve_base_ref()
        if not base_ref:
            reporter.emit(
                "FAIL",
                "E_DIFF_UNAVAILABLE",
                "/ci/diff",
                "Unable to resolve base ref for git diff.",
                roots=roots,
            )
            return reporter.summary()

        try:
            changed = _changed_files(base_ref)
        except Exception as exc:  # noqa: BLE001 - normalized to contract error code.
            reporter.emit(
                "FAIL",
                "E_DIFF_UNAVAILABLE",
                "/ci/diff",
                "Unable to compute changed files.",
                base_ref=base_ref,
                error=str(exc),
            )
            return reporter.summary()

        reporter.emit(
            "INFO",
            "I_DIFF_READY",
            "/ci/diff",
            "Computed changed files.",
            base_ref=base_ref,
            changed_count=len(changed),
        )

    candidates, solo_json = _classify(changed, roots)

    complete_triplets: list[CompleteTriplet] = []
    if candidates:
        complete_triplets = _validate_triplets(candidates, reporter)
        _run_gatekeeper(complete_triplets, reporter)
    if solo_json:
        _validate_solo_json(solo_json, reporter)
    if not candidates and not solo_json:
        reporter.emit(
            "INFO",
            "I_NO_RELEVANT_JSON",
            "/ci/diff",
            "No relevant changed JSON files found.",
            changed_count=len(changed),
        )

    return reporter.summary()


if __name__ == "__main__":
    sys.exit(main())
