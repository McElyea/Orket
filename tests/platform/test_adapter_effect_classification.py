"""Layer: contract. Native dependency commands must enforce adapter admission metadata."""

import json

import pytest

from tests.helpers.dependency_repository import make_repository, run_command

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    "source",
    [
        "",
        "side_effecting = 0\n",
        "side_effecting = bool(0)\n",
        "if True:\n    side_effecting = False\n",
        "side_effecting = False\nside_effecting = True\n",
        "side_effecting = False\nclass Writer:\n    side_effecting = True\n",
        "side_effecting = False\ndel side_effecting\n",
        "side_effecting = False\nside_effecting |= True\n",
        "from builtins import bool as side_effecting\n",
        "side_effecting = False\nfor side_effecting in [True]:\n    pass\n",
        "side_effecting = False\nif False:\n    side_effecting = True\n",
        "side_effecting = False\nclass Hidden:\n    side_effecting = True\nclass Hidden:\n    pass\n",
        "side_effecting = False\ndef make():\n    class Writer:\n        side_effecting = True\n    return Writer\n",
        'side_effecting = False\nmatch {"a": 1}:\n    case {**side_effecting}:\n        pass\n',
        "side_effecting = False\ndef f(x=(side_effecting := True)):\n    pass\n",
        "side_effecting = False\nclass C((side_effecting := object)):\n    pass\n",
        "side_effecting, other = False\n",
        "side_effecting = False\nf = lambda x=(side_effecting := True): x\n",
    ],
)
def test_native_gate_rejects_missing_or_invalid_adapter_classification(tmp_path, source):
    make_repository(tmp_path, {"orket/adapters/fixture.py": source}, adapter_effect_bound=None)
    process, report = run_command(tmp_path)
    assert process.returncode == 1
    assert report["collection_ok"] and not report["verdict"]["ok"]
    assert report["verdict"]["adapter_effect_violations"]


@pytest.mark.parametrize("value", [True, False])
def test_native_gate_records_declared_bound_without_executing_adapter(tmp_path, value):
    source = (
        f"side_effecting: bool = {value!r}\n"
        "def local():\n    side_effecting = None\n"
        "local_lambda = lambda: (side_effecting := None)\n"
        "flags = {}\nflags[side_effecting] = 1\n"
        "raise RuntimeError('must not import this fixture')\n"
    )
    make_repository(tmp_path, {"orket/adapters/fixture.py": source}, adapter_effect_bound=None)
    process, report = run_command(tmp_path)
    assert process.returncode == 0
    assert report["collection_ok"] and report["verdict"]["ok"]
    assert not report["verdict"]["adapter_effect_violations"]
    assert report["observed"]["adapter_effects"][0]["side_effecting"] is value


def test_native_gate_accepts_explicit_readonly_decision_target(tmp_path):
    path = make_repository(
        tmp_path,
        {
            "orket/decision_nodes/fixture.py": "from orket.adapters.target import normalize\n",
            "orket/adapters/target.py": "side_effecting = False\ndef normalize(value):\n    return value.strip()\n",
        },
        adapter_effect_bound=None,
    )
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["side_effect_free_adapters"] = ["orket.adapters.target"]
    path.write_text(json.dumps(policy), encoding="utf-8")
    process, report = run_command(tmp_path)
    assert process.returncode == 0 and report["verdict"]["ok"]
    assert not report["verdict"]["adapter_effect_violations"]


def test_native_import_exception_cannot_waive_effect_bound(tmp_path):
    path = make_repository(
        tmp_path,
        {
            "orket/decision_nodes/fixture.py": "import orket.adapters.writer\n",
            "orket/adapters/writer.py": "",
        },
        adapter_effect_bound=None,
    )
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["exceptions"] = [
        {
            "id": "fixture-edge",
            "source": "orket.decision_nodes.fixture",
            "target": "orket.adapters.writer",
            "owner": "Fixture",
            "reason": "Exact import exception",
            "introduced": "2026-01-01",
            "removal": "Test teardown",
            "expires": "2099-01-01",
        }
    ]
    path.write_text(json.dumps(policy), encoding="utf-8")
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report["verdict"]["violations"]
    assert report["verdict"]["adapter_effect_violations"]


@pytest.mark.parametrize("mode", ["effectful", "reexport", "missing"])
def test_native_gate_refuses_unsafe_allowlisted_adapter(tmp_path, mode):
    files = {"orket/decision_nodes/fixture.py": "import orket.adapters.target\n"}
    if mode != "missing":
        files["orket/adapters/target.py"] = (
            "side_effecting = True\n"
            if mode == "effectful"
            else "side_effecting = False\nimport orket.adapters.writer\n"
        )
    if mode == "reexport":
        files["orket/adapters/writer.py"] = "side_effecting = True\n"
    path = make_repository(tmp_path, files, adapter_effect_bound=None)
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["side_effect_free_adapters"] = ["orket.adapters.target"]
    path.write_text(json.dumps(policy), encoding="utf-8")
    process, report = run_command(tmp_path)
    assert process.returncode == 1
    assert report["verdict"]["adapter_effect_violations"]
