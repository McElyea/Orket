"""Retain existing native lifetime tests verbatim in an external candidate harness."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.ci.candidate_install_support import file_identity

EXPECTED_CASES = {
    "test_verification_process_lifetime": {
        "test_public_runtime_verification_stops_children_and_grandchildren": 10,
    },
    "test_owned_command_output_limits": {
        "test_owned_command_capture_uses_the_admitted_limit": 4,
        "test_invalid_capture_limit_refuses_before_command_admission": 6,
    },
    "test_verification_supervisor_receipts": {
        "test_already_stopped_admission_does_not_execute_a_command": 1,
        "test_excessive_raw_output_cannot_pass_or_admit_the_next_command": 2,
        "test_missing_executable_retains_launch_and_cleanup_observation": 1,
        "test_cancellation_exception_retains_observed_cleanup_for_its_caller": 1,
    },
    "test_outward_command_uncertainty": {
        "test_unfinished_command_retains_dispatch_intent_across_api_reentry": 2,
    },
}
MODULES = tuple(f"tests/integration/{name}.py" for name in EXPECTED_CASES)
SUPPORT = ("tests/__init__.py", "tests/conftest.py", "tests/helpers/outward_authorization.py",
           "tests/helpers/outward_model.py", "tests/integration/verification_lifetime_worker.py")
HARNESS_CONFTEST = '''"""Installed origins are checked before and after native acceptance."""
import importlib
import sys
from pathlib import Path

def _origins():
    prefix = Path(sys.prefix).resolve()
    for name in ("orket", "orket_extension_sdk"):
        importlib.import_module(name)
    for name, module in tuple(sys.modules.items()):
        if name.split(".")[0] in {"orket", "orket_extension_sdk"}:
            origin = getattr(module, "__file__", None)
            locations = [origin] if origin else list(getattr(module, "__path__", ()))
            assert locations and all(Path(p).resolve().is_relative_to(prefix) for p in locations), (name, locations)

def pytest_sessionstart(session):
    _origins()
    # Only copied tests live here. There is no production source package in this tree.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

def pytest_sessionfinish(session, exitstatus):
    _origins()
'''


def copy_process_harness(repo: Path, target: Path) -> list[dict[str, str]]:
    records = []
    for name in (*MODULES, *SUPPORT):
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((repo / name).read_bytes())
        records.append({"source": name, **file_identity(destination)})
    (target / "conftest.py").write_text(HARNESS_CONFTEST, encoding="utf-8")
    (target / "pytest.ini").write_text(
        "[pytest]\nasyncio_mode = auto\nasyncio_default_fixture_loop_scope = function\n"
        "markers =\n    integration: real native boundary\n    contract: explicit invalid-input contract\n",
        encoding="utf-8")
    return [*records, file_identity(target / "conftest.py"), file_identity(target / "pytest.ini")]


def process_test_verdict(path: Path) -> dict:
    """Missing, duplicated, skipped or unsuccessful mandatory items cannot pass."""
    rows, counts, identities = [], {}, set()
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise ValueError("Invalid native process JUnit evidence") from exc
    for item in tree.iter("testcase"):
        module = item.attrib.get("classname", "").rsplit(".", 1)[-1]
        name = item.attrib.get("name", "")
        identity = (module, name)
        if identity in identities:
            raise ValueError("Duplicate mandatory process test identity")
        identities.add(identity)
        function = name.split("[", 1)[0]
        counts.setdefault(module, {})[function] = counts.get(module, {}).get(function, 0) + 1
        verdict = ("failure" if item.find("failure") is not None or item.find("error") is not None
                   else "skipped" if item.find("skipped") is not None else "success")
        rows.append({"module": module, "name": name, "result": verdict})
    complete = counts == EXPECTED_CASES
    return {"ok": complete and all(row["result"] == "success" for row in rows),
            "all_required_items_present": complete, "expected": EXPECTED_CASES, "observed": counts, "tests": rows}
