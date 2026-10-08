"""Negative receipt controls: partial or skipped native selections cannot turn green."""
import xml.etree.ElementTree as ET

import pytest

from scripts.ci.installed_process_controls import EXPECTED_CASES, process_test_verdict

pytestmark = pytest.mark.contract


def evidence(tmp_path):
    suite = ET.Element("testsuite")
    for module, functions in EXPECTED_CASES.items():
        for name, count in functions.items():
            for i in range(count):
                ET.SubElement(suite, "testcase", classname=f"tests.integration.{module}", name=f"{name}[case-{i}]")
    path = tmp_path / "controlled-process-junit.xml"
    return suite, path


@pytest.mark.parametrize("fault", ["missing", "skip", "failure", "error", "unknown", "duplicate"])
def test_incomplete_or_unsuccessful_mandatory_selection_is_rejected(tmp_path, fault):
    suite, path = evidence(tmp_path)
    if fault == "missing":
        suite.remove(suite[0])
    elif fault == "unknown":
        suite[0].set("classname", "different.module")
    elif fault == "duplicate":
        ET.SubElement(suite, "testcase", **suite[0].attrib)
    else:
        ET.SubElement(suite[0], "skipped" if fault == "skip" else fault)
    ET.ElementTree(suite).write(path)
    if fault == "duplicate":
        with pytest.raises(ValueError, match="Duplicate"):
            process_test_verdict(path)
    else:
        assert not process_test_verdict(path)["ok"]


def test_complete_junit_is_only_selection_evidence_and_malformed_receipt_refuses(tmp_path):
    suite, path = evidence(tmp_path)
    ET.ElementTree(suite).write(path)
    assert process_test_verdict(path)["ok"]
    path.write_text("<incomplete", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid native process"):
        process_test_verdict(path)
