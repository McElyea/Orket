"""Bounded source contracts and real native checker/renderer flows in Git fixtures."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.governance.current_authority import (
    HISTORY,
    MANIFEST,
    REFERENCE_ROLES,
    REPORT,
    REQUIRED_COMMANDS,
    VIEW,
    digest,
    load_manifest,
    output_path,
    validate,
)
from scripts.governance.current_authority_commands import bind_command
from scripts.governance.current_authority_view import render

TOOL_ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, name: str, content: str) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def _save(root: Path, payload: dict) -> None:
    _write(root, MANIFEST, json.dumps(payload, indent=2) + "\n")


@pytest.fixture
def authority_repo(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    history = b"# Retained authority\nHistorical source only.\n"
    _write(root, HISTORY, history.decode())
    _write(root, "README.md", "# Commands\n\n```text\npython server.py\norket runtime\n```\n")
    _write(root, "server.py", "def main():\n    return 0\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n")
    _write(root, "orket/cli.py", "def main():\n    return 0\n")
    _write(root, "pyproject.toml", '[project]\nname="fixture"\n[project.scripts]\norket="orket.cli:main"\n')
    _write(root, "active.md", "# Runtime contract\n\nStatus: Active\n\nClose after explicit migration.\n")
    records = [
        dict(id="command.api", kind="command", label="API", source="README.md", command="python server.py", proof="proof"),
        dict(id="command.runtime", kind="command", label="Runtime", source="README.md", command="orket runtime", proof="proof"),
        dict(id="contract", kind="contract", label="Runtime contract", source="active.md", scope="runtime"),
        dict(id="compat", kind="compatibility", label="Alias", source="active.md",
             condition="Close after explicit migration.", expires_on=None, ceiling="No inferred expiry."),
        dict(id="proof", kind="proof", label="Current proof", source="active.md", state="unavailable",
             observed_on=None, scope="runtime", ceiling="No current runtime evidence adapter."),
    ]
    records.extend(dict(id=name, kind="command", label=name, source="README.md", command="python server.py", proof="proof")
                   for name in sorted(REQUIRED_COMMANDS - {"command.api", "command.runtime"}))
    records.extend(dict(id="reference." + role, kind="reference", label=role, source="active.md", role=role)
                   for role in sorted(REFERENCE_ROLES))
    records += [dict(id="owners", kind="owners", label="Owners", source="active.md", executor="server.py#main",
                     authorization="server.py#main", effect="server.py#main", terminal="server.py#main", ceiling="Fixture."),
                dict(id="ceiling", kind="ceiling", label="Ceiling", source="active.md", scope="runtime",
                     posture="support_only", statement="Fixture only.")]
    payload = dict(schema_version="current_authority.v1", updated_on=date.today().isoformat(),
                   history=dict(path=HISTORY, sha256=digest(history)), records=records)
    _save(root, payload)
    return root, payload


class TestAuthorityContracts:
    pytestmark = pytest.mark.contract

    def test_documented_script_and_console_bind_to_actual_targets(self, authority_repo):
        root, _ = authority_repo
        payload, _, bindings = validate(root)
        assert bindings["command.api"].startswith("server.py#main")
        assert bindings["command.runtime"].startswith("orket/cli.py#main")
        assert render(payload) == render(deepcopy(payload))

    @pytest.mark.parametrize("value", ['{"records":[],"records":[]}', '{"value":NaN}', '[]'])
    def test_duplicate_nonfinite_or_nonobject_json_refuses(self, value):
        with pytest.raises(ValueError):
            load_manifest(value.encode())

    @pytest.mark.parametrize("change", ["missing-server", "module", "symbol", "native-guard"])
    def test_entrypoint_refuses_even_when_documented_command_matches(self, authority_repo, change):
        root, payload = authority_repo
        if change == "missing-server":
            payload["records"][0]["command"] = "python missing-server.py --not-an-option"
            _write(root, "README.md", "`python missing-server.py --not-an-option`\n`orket runtime`\n")
        elif change == "module":
            _write(root, "pyproject.toml", '[project.scripts]\norket="missing.cli:main"\n')
        elif change == "symbol":
            _write(root, "orket/cli.py", "def other():\n    return 0\n")
        else:
            _write(root, "server.py", "def main():\n    return 0\n")
        _save(root, payload)
        with pytest.raises(ValueError, match="missing|entrypoint"):
            validate(root)

    @pytest.mark.parametrize("body", ["echo 'python server.py'", "# python server.py", "python server.py && echo okay"])
    def test_workflow_comments_echo_and_compound_syntax_are_not_argv(self, authority_repo, body):
        root, payload = authority_repo
        payload["records"][0]["source"] = ".gitea/workflows/quality.yml"
        _write(root, ".gitea/workflows/quality.yml", "jobs:\n  quality:\n    steps:\n      - run: |\n          " + body)
        _save(root, payload)
        with pytest.raises(ValueError, match="documented command argv differs"):
            validate(root)

    @pytest.mark.parametrize("change", ["unknown", "duplicate", "too-many", "future-date", "invalid-date", "expired",
                                        "invalid-expiry", "proof-current", "proof-future", "scope-conflict"])
    def test_closed_record_and_time_controls(self, authority_repo, change):
        root, payload = authority_repo
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        if change == "unknown":
            payload["journal"] = []
        elif change == "duplicate":
            payload["records"].append(deepcopy(payload["records"][0]))
        elif change == "too-many":
            payload["records"] = (payload["records"] * 2)[:41]
        elif change == "future-date":
            payload["updated_on"] = tomorrow
        elif change == "invalid-date":
            payload["updated_on"] = "2026-02-30"
        elif change == "expired":
            payload["records"][3]["expires_on"] = date.today().isoformat()
        elif change == "invalid-expiry":
            payload["records"][3]["expires_on"] = "not-a-date"
        elif change == "proof-current":
            payload["records"][4]["state"] = "current_verified"
        elif change == "proof-future":
            payload["records"][4].update(state="historical", observed_on=tomorrow)
        else:
            duplicate = dict(payload["records"][2], id="other-contract")
            payload["records"].append(duplicate)
        _save(root, payload)
        expected = {
            "unknown": "unknown or missing fields", "duplicate": "duplicate authority record ID",
            "too-many": "1..40", "future-date": "future update date", "invalid-date": "day.*out of range",
            "expired": "expiry requires disposition", "invalid-expiry": "invalid date",
            "proof-current": "unsupported portable", "proof-future": "future proof", "scope-conflict": "conflicting",
        }
        with pytest.raises(ValueError, match=expected[change]):
            validate(root)

    @pytest.mark.parametrize("status", ["Draft", "Archived", "Accepted target", "Active\nStatus: Draft"])
    def test_inactive_and_ambiguous_spec_status_refuses(self, authority_repo, status):
        root, _ = authority_repo
        _write(root, "active.md", "# Runtime contract\n\nStatus: " + status + "\nClose after explicit migration.\n")
        with pytest.raises(ValueError, match="inactive or ambiguous"):
            validate(root)

    @pytest.mark.parametrize("change", ["missing", "escape", "ignored", "history", "self-reference", "command-drift"])
    def test_missing_sources_history_and_drift_refuse(self, authority_repo, change):
        root, payload = authority_repo
        if change == "missing":
            (root / "active.md").unlink()
        elif change == "escape":
            payload["records"][2]["source"] = "../elsewhere.md"
        elif change == "ignored":
            _write(root, ".gitignore", "active.md\n")
        elif change == "history":
            _write(root, HISTORY, "Changed historical authority")
        elif change == "self-reference":
            payload["records"][2]["source"] = MANIFEST
        else:
            payload["records"][0]["command"] = "python server.py --undocumented"
        _save(root, payload)
        expected = {"missing": "missing or non-Git-visible", "escape": "noncanonical authority path",
                    "ignored": "missing or non-Git-visible", "history": "history bytes changed",
                    "self-reference": "cannot support itself", "command-drift": "documented command argv differs"}
        with pytest.raises(ValueError, match=expected[change]):
            validate(root)

    def test_source_changes_and_output_collisions_refuse(self, authority_repo):
        root, _ = authority_repo
        _, sources, _ = validate(root)
        with pytest.raises(ValueError, match="aliases"):
            output_path(sources, MANIFEST)
        _write(root, "active.md", "changed")
        with pytest.raises(ValueError, match="changed during"):
            sources.recheck()

    def test_hardlink_output_and_oversized_json_refuse(self, authority_repo):
        root, _ = authority_repo
        _, sources, _ = validate(root)
        target = root / REPORT
        target.parent.mkdir(parents=True)
        os.link(root / MANIFEST, target)
        with pytest.raises(ValueError, match="aliases"):
            output_path(sources, REPORT)
        with pytest.raises(ValueError, match="32KiB"):
            load_manifest(b" " * 32769)

    @pytest.mark.parametrize("change", ["command", "reference", "section", "kind", "field", "expiry"])
    def test_incomplete_or_malformed_current_inventory_refuses(self, authority_repo, change):
        root, payload = authority_repo
        expected = "inventory differs"
        if change == "command":
            payload["records"] = [row for row in payload["records"] if row["id"] != "command.api"]
        elif change == "reference":
            payload["records"] = [row for row in payload["records"] if row.get("role") != "workflow"]
        elif change == "section":
            payload["records"] = [row for row in payload["records"] if row["kind"] != "owners"]
            expected = "section is absent"
        elif change == "kind":
            payload["records"][0]["kind"] = []
            expected = "unknown authority record kind"
        elif change == "field":
            payload["records"][0]["runtime_success"] = True
            expected = "unknown or missing fields"
        else:
            payload["records"][3]["expires_on"] = (date.today() + timedelta(days=10)).isoformat()
            expected = "expiry date is not declared"
        _save(root, payload)
        with pytest.raises(ValueError, match=expected):
            validate(root)


def _native(root: Path, command: str, *options: str) -> subprocess.CompletedProcess:
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", ORKET_DISABLE_SANDBOX="1")
    environment.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(TOOL_ROOT / "scripts/governance" / command),
                           "--repo-root", str(root), *options], cwd=root, env=environment,
                          capture_output=True, text=True, timeout=30, check=False)


class TestAuthorityNativeFlows:
    pytestmark = pytest.mark.integration

    @pytest.mark.parametrize("posture", ["unavailable", "historical"])
    def test_render_check_and_current_proof_refusal_preserve_ledger(self, authority_repo, posture):
        root, payload = authority_repo
        if posture == "historical":
            payload["records"][4].update(state="historical", observed_on=date.today().isoformat())
            _save(root, payload)
        rendered = _native(root, "render_current_authority.py")
        assert rendered.returncode == 0, rendered.stderr
        before = (root / VIEW).read_bytes()
        checked = _native(root, "render_current_authority.py", "--check")
        assert checked.returncode == 0, checked.stderr
        accepted = _native(root, "check_current_authority.py")
        assert accepted.returncode == 0, accepted.stderr
        report = json.loads((root / REPORT).read_text())
        assert report["structural_authority_valid"] is True
        assert report["current_proof_established"] is False
        refused = _native(root, "check_current_authority.py", "--require-current-proof")
        assert refused.returncode == 1, refused.stderr
        report = json.loads((root / REPORT).read_text())
        assert report["structural_authority_valid"] is True
        assert report["requested_proof_satisfied"] is False
        assert report["diff_ledger"]
        assert (root / VIEW).read_bytes() == before

    def test_manual_view_change_and_incomplete_source_cannot_pass(self, authority_repo):
        root, _ = authority_repo
        assert _native(root, "render_current_authority.py").returncode == 0
        assert _native(root, "check_current_authority.py").returncode == 0
        _write(root, VIEW, "Manual green claim")
        assert _native(root, "render_current_authority.py", "--check").returncode == 1
        assert _native(root, "check_current_authority.py").returncode == 1
        previous = (root / REPORT).read_bytes()
        (root / "active.md").unlink()
        assert _native(root, "check_current_authority.py").returncode == 2
        assert (root / REPORT).read_bytes() == previous

    def test_unrelated_report_destination_is_not_overwritten(self, authority_repo):
        root, _ = authority_repo
        assert _native(root, "render_current_authority.py").returncode == 0
        _write(root, REPORT, '{"unrelated": true}\n')
        previous = (root / REPORT).read_bytes()
        refused = _native(root, "check_current_authority.py")
        assert refused.returncode == 2
        assert "unrelated existing report" in refused.stderr
        assert (root / REPORT).read_bytes() == previous


@pytest.mark.contract
@pytest.mark.parametrize("command,expected", [
    ('python -m pip install -e "./orket_extension_sdk[testing]" -e ".[dev]"', "core and SDK packaging"),
    ("python -m pytest -q", "external development dependency: pytest"),
    ("ruff check orket tests", "external development dependency: ruff"),
])
def test_packaging_bindings_observe_declarations_without_running_tools(command, expected):
    texts = {
        "README.md": "`" + command + "`",
        "pyproject.toml": '[project.optional-dependencies]\ndev=["pytest>=8", "ruff>=0.3"]\n',
        "orket_extension_sdk/pyproject.toml": "[project.optional-dependencies]\ntesting=[]\n",
    }
    record = dict(id="package", source="README.md", command=command)
    assert bind_command(record, texts.__getitem__).startswith(expected)


@pytest.mark.contract
@pytest.mark.parametrize("command,expected", [
    ('python -m pip install -e "./orket_extension_sdk[missing]" -e ".[dev]"', "extra missing"),
    ('python -m pip install -e ".[dev]" -e ".[dev]"', "both core and SDK"),
    ("ruff check orket tests", "lacks a development dependency"),
])
def test_invalid_packaging_bindings_refuse(command, expected):
    texts = {
        "README.md": "`" + command + "`",
        "pyproject.toml": "[project.optional-dependencies]\ndev=[]\n",
        "orket_extension_sdk/pyproject.toml": "[project.optional-dependencies]\ntesting=[]\n",
    }
    record = dict(id="package", source="README.md", command=command)
    with pytest.raises(ValueError, match=expected):
        bind_command(record, texts.__getitem__)
