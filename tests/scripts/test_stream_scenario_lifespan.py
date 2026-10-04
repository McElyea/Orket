# LIFECYCLE: live
"""Layer: integration. Real API startup, scenario traffic and shutdown."""
import shutil
from pathlib import Path

import pytest

from scripts.streaming import run_stream_scenario as runner

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('scenario', [
    's0_unknown_workload_400.yaml',
    's5_backpressure_drop_ranges.yaml',
    's6_finalize_cancel_noop.yaml',
])
def test_scenario_uses_real_api_lifespan(test_root, monkeypatch, scenario):
    shutil.copyfile(ROOT / 'config/organization.json', test_root / 'config/organization.json')
    monkeypatch.chdir(test_root)
    monkeypatch.setenv('ORKET_DISABLE_SANDBOX', '1')
    monkeypatch.setenv('ORKET_DURABLE_ROOT', str(test_root / '.orket/durable'))
    monkeypatch.setenv('ORKET_MODEL_STREAM_PROVIDER', 'stub')
    monkeypatch.setenv('ORKET_API_KEY', 'scenario-lifespan-test')
    created = []
    factory = runner.api_module.create_api_app

    def observe_factory(**kwargs):
        app = factory(**kwargs)
        created.append(app)
        return app

    monkeypatch.setattr(runner.api_module, 'create_api_app', observe_factory)
    result = runner.run_scenario(
        scenario_path=ROOT / 'docs/observability/stream_scenarios' / scenario, timeout_s=20,
    )
    assert result['status'] == 'PASS'
    assert result['law_checker_passed']
    assert len(created) == 1
    assert created[0].state.api_ready is False
