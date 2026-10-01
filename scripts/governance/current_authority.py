"""Bounded current-authority source validation for native repository tooling."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from scripts.common.git_inventory import git_list_files
from scripts.governance.current_authority_commands import bind_command

MANIFEST = "docs/architecture/current_authority.json"
VIEW = "CURRENT_AUTHORITY.md"
REPORT = "benchmarks/results/governance/current_authority_check.json"
HISTORY = "docs/architecture/history/CURRENT_AUTHORITY_PRE_MANIFEST_2026-09-28.md"
MAX_BYTES = 32768
MAX_RECORDS = 40
BASE_FIELDS = {"id", "kind", "label", "source"}
FIELDS = {
    "command": {"command", "proof"},
    "reference": {"role"},
    "contract": {"scope"},
    "owners": {"executor", "authorization", "effect", "terminal", "ceiling"},
    "compatibility": {"condition", "expires_on", "ceiling"},
    "ceiling": {"scope", "posture", "statement"},
    "proof": {"state", "observed_on", "scope", "ceiling"},
}
REFERENCE_ROLES = {"architecture", "dependency_policy", "start_paths", "contracts_index", "workflow",
                   "durable_paths", "script_outputs", "security", "active_plan", "exception_register"}
CEILINGS = {"proposed", "trusted_only", "support_only", "bounded_contract"}
REQUIRED_COMMANDS = {"command." + name for name in
                     ("install", "runtime", "card", "api", "pytest", "quality", "ruff", "taxonomy", "dependency", "docs")}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contained(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or len(name) > 320:
        raise ValueError("invalid authority path")
    if "\\" in name or ":" in name or PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive:
        raise ValueError(f"repository-relative POSIX path required: {name}")
    if any(part in {"", ".", ".."} for part in name.split("/")):
        raise ValueError(f"noncanonical authority path: {name}")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"authority path escapes repository: {name}")
    return target


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError(f"nonfinite JSON value: {value}")


def load_manifest(data: bytes) -> dict:
    if len(data) > MAX_BYTES or data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("authority manifest exceeds 32KiB or contains a UTF-8 BOM")
    try:
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite)
    except RecursionError as exc:
        raise ValueError("authority nesting is unsupported") from exc
    if not isinstance(payload, dict):
        raise ValueError("authority must be an object")
    return payload


class Sources:
    """One Git-visible source observation, retained until publication checks finish."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)
        self.visible = {path.resolve() for path in git_list_files(self.root)}
        self.observed: dict[str, bytes] = {}

    def read(self, name: str) -> str:
        target = contained(self.root, name)
        if target not in self.visible or not target.is_file():
            raise ValueError(f"missing or non-Git-visible authority source: {name}")
        if name not in self.observed:
            with target.open("rb") as stream:
                data = stream.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError(f"authority source exceeds 4MiB: {name}")
            self.observed[name] = data
        return self.observed[name].decode("utf-8-sig")

    def recheck(self) -> None:
        for name, previous in self.observed.items():
            if contained(self.root, name).read_bytes() != previous:
                raise ValueError(f"authority source changed during observation: {name}")


def _keys(value: dict, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"unknown or missing fields: {label}")


def _day(value: str, label: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"invalid date: {label}")
    return date.fromisoformat(value)


def _active_spec(text: str, source: str) -> None:
    statuses = [line.strip() for line in text.splitlines()[:20] if line.strip().startswith("Status:")]
    if len(statuses) != 1 or not re.match(r"Status: Active(?:$|[ ;(])", statuses[0]):
        raise ValueError(f"inactive or ambiguous spec: {source}")


def _implementation(value: str, sources: Sources) -> None:
    path, separator, symbol = value.partition("#")
    text = sources.read(path)
    if not path.endswith(".py") or not separator or not symbol:
        raise ValueError(f"owner requires Python path#declared_symbol: {value}")
    tree = ast.parse(text, filename=path)
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol
               for node in tree.body):
        raise ValueError(f"owner declaration missing: {value}")


def _record_shape(record: dict) -> None:
    if not isinstance(record, dict) or not isinstance(record.get("kind"), str) or record["kind"] not in FIELDS:
        raise ValueError("unknown authority record kind")
    _keys(record, BASE_FIELDS | FIELDS[record["kind"]], "record")
    for key, value in record.items():
        if key in {"expires_on", "observed_on"} and value is None:
            continue
        if not isinstance(value, str) or not value or len(value) > 512:
            raise ValueError(f"nonempty bounded string required: {key}")
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", record["id"]):
        raise ValueError("invalid authority record ID")


def _record_semantics(record: dict, sources: Sources, today: date, proof_ids: set[str]) -> str | None:
    kind = record["kind"]
    text = sources.read(record["source"])
    if record["source"] in {MANIFEST, VIEW}:
        raise ValueError("authority manifest/view cannot support itself")
    if kind == "command":
        if record["proof"] not in proof_ids:
            raise ValueError(f"command proof reference missing: {record['id']}")
        return bind_command(record, sources.read)
    if kind == "reference" and record["role"] not in REFERENCE_ROLES:
        raise ValueError("unknown authority reference role")
    if kind in {"contract", "owners"}:
        _active_spec(text, record["source"])
    if kind == "owners":
        for field in ("executor", "authorization", "effect", "terminal"):
            _implementation(record[field], sources)
    if kind == "compatibility":
        if record["condition"] not in text:
            raise ValueError(f"compatibility condition differs from source: {record['id']}")
        if record["expires_on"] is not None and _day(record["expires_on"], "expiry") <= today:
            raise ValueError(f"compatibility expiry requires disposition: {record['id']}")
        if record["expires_on"] is not None and record["expires_on"] not in text:
            raise ValueError(f"compatibility expiry date is not declared by its source: {record['id']}")
    if kind == "ceiling" and record["posture"] not in CEILINGS:
        raise ValueError("unknown claim ceiling posture")
    if kind == "proof":
        if record["state"] not in {"unavailable", "historical"}:
            raise ValueError("current proof requires an unsupported portable evidence adapter")
        if record["state"] == "historical":
            if _day(record["observed_on"], "proof observation") > today:
                raise ValueError("future proof observation")
        elif record["observed_on"] is not None:
            raise ValueError("unavailable proof cannot claim an observation date")
    return None


def validate(root: Path, *, today: date | None = None) -> tuple[dict, Sources, dict[str, str]]:
    today = today or date.today()
    sources = Sources(root)
    sources.read(MANIFEST)
    payload = load_manifest(sources.observed[MANIFEST])
    _keys(payload, {"schema_version", "updated_on", "history", "records"}, "manifest")
    if payload["schema_version"] != "current_authority.v1" or _day(payload["updated_on"], "updated_on") > today:
        raise ValueError("unsupported authority version or future update date")
    history = payload["history"]
    _keys(history, {"path", "sha256"}, "history")
    if history["path"] != HISTORY or not re.fullmatch(r"[a-f0-9]{64}", str(history["sha256"])):
        raise ValueError("final pre-cutover history binding required")
    sources.read(HISTORY)
    if digest(sources.observed[HISTORY]) != history["sha256"]:
        raise ValueError("pre-cutover authority history bytes changed")
    records = payload["records"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS:
        raise ValueError("authority requires 1..40 current records")
    for record in records:
        _record_shape(record)
    if {row["id"] for row in records if row["kind"] == "command"} != REQUIRED_COMMANDS:
        raise ValueError("canonical command inventory differs")
    if {row["role"] for row in records if row["kind"] == "reference"} != REFERENCE_ROLES:
        raise ValueError("canonical reference inventory differs")
    if {row["kind"] for row in records} != set(FIELDS):
        raise ValueError("a required current-authority section is absent")
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate authority record ID")
    proof_ids = {record["id"] for record in records if record["kind"] == "proof"}
    keys, bindings = set(), {}
    for record in records:
        key = (record["kind"], record.get("scope", record.get("role", record["label"])))
        if key in keys:
            raise ValueError(f"duplicate or conflicting authority scope: {key}")
        keys.add(key)
        binding = _record_semantics(record, sources, today, proof_ids)
        if binding is not None:
            bindings[record["id"]] = binding
    sources.recheck()
    return payload, sources, bindings


def output_path(sources: Sources, name: str, *, view: bool = False) -> Path:
    target = contained(sources.root, name)
    protected = {contained(sources.root, path) for path in sources.observed}
    if not view:
        protected.add(contained(sources.root, VIEW))
    if target in protected or (target.exists() and any(target.samefile(path) for path in protected if path.exists())):
        raise ValueError("output aliases an authority input")
    if not view and target.exists():
        previous = json.loads(target.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
        if not isinstance(previous, dict) or previous.get("schema_version") != "current_authority_check.v1":
            raise ValueError("refusing to replace an unrelated existing report destination")
    sources.recheck()
    return target
