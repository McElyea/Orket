"""Layer: integration. Persist real logging envelopes and project version counts."""
import json

import pytest

from orket.logging import log_event
from scripts.acceptance.report_live_acceptance_patterns import _build_report
from scripts.acceptance.run_live_acceptance_loop import (
    _runtime_event_presence_count,
    _runtime_event_schema_version_count,
)


@pytest.mark.integration
# Layer: integration
def test_logging_and_acceptance_reports_distinguish_current_and_historical_envelopes(tmp_path):
    historical = {"event": "old", "data": {"runtime_event": {"schema_version": "v1", "duration_ms": 0}}}
    log_path = tmp_path / "orket.log"
    original = json.dumps(historical) + "\n"
    log_path.write_text(original, encoding="utf-8")
    for payload in ({}, {"duration_ms": 0.375}):
        log_event("timing_observation", {"session_id": "schema-report", **payload}, workspace=tmp_path)
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert records[0] == historical
    assert [row["data"]["runtime_event"]["duration_ms"] for row in records[1:]] == [None, 0.375]
    metrics = {"runtime_event_envelope_count": _runtime_event_presence_count(records)}
    for version in ("v1", "v2"):
        metrics[f"runtime_event_schema_{version}_count"] = _runtime_event_schema_version_count(records, version)
    report = _build_report("timing", [{"model": "unobserved", "metrics": metrics}])
    assert report["pattern_counters"]["runtime_event_schema_v1_count"] == 1
    assert report["pattern_counters"]["runtime_event_schema_v2_count"] == 2
    assert report["schema_health"] == {"runtime_event_schema_v1_coverage": 1 / 3,
                                      "runtime_event_schema_v2_coverage": 2 / 3}


@pytest.mark.contract
# Layer: contract
def test_old_acceptance_metrics_do_not_fabricate_current_version_coverage():
    report = _build_report("old", [{"model": "unobserved", "metrics": {"runtime_event_envelope_count": 2,
                                               "runtime_event_schema_v1_count": 2}}])
    assert report["schema_health"] == {"runtime_event_schema_v1_coverage": 1.0,
                                      "runtime_event_schema_v2_coverage": 0.0}
