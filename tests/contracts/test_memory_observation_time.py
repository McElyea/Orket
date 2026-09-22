"""Layer: contract. Pure time-sensitive memory decisions have explicit inputs."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from orket.runtime.truthful_memory_policy import (
    classify_memory_trust_level,
    render_reference_context_rows,
    render_scoped_memory_rows,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("metadata", [
    {"stale_at": "2030-01-01T00:01:00Z"},
    {"observed_at": "2030-01-01T00:00:00Z", "max_age_minutes": 1},
])
def test_memory_expiration_uses_only_the_explicit_strict_boundary(metadata):
    boundary = datetime(2030, 1, 1, 0, 1, tzinfo=UTC)
    arguments = dict(scope="project_memory", metadata=metadata)
    assert classify_memory_trust_level(**arguments, observed_at=boundary) == "advisory"
    assert classify_memory_trust_level(**arguments, observed_at=boundary + timedelta(microseconds=1)) == "stale_risk"
    assert classify_memory_trust_level(**arguments, observed_at=boundary) == "advisory"


def test_memory_rendering_observes_the_same_explicit_instant():
    observed = datetime(2030, 1, 1, tzinfo=UTC)
    metadata = {"stale_at": observed.isoformat()}
    row = dict(content="current", metadata=metadata)
    scoped = SimpleNamespace(key="topic", value="current", scope="episodic_memory", metadata=metadata)
    assert "current" in render_reference_context_rows([row], observed_at=observed)
    assert "current" in render_scoped_memory_rows([scoped], prefix="episode", observed_at=observed)[0]
    assert render_reference_context_rows([row], observed_at=observed + timedelta(seconds=1)) == ""
    assert render_scoped_memory_rows([scoped], prefix="episode", observed_at=observed + timedelta(seconds=1)) == []


@pytest.mark.parametrize("entry", ["classify", "reference", "scoped"])
def test_memory_observation_rejects_missing_or_naive_clock_even_without_rows(entry):
    function, arguments = {
        "classify": (classify_memory_trust_level, {"scope": "project_memory"}),
        "reference": (render_reference_context_rows, {"rows": []}),
        "scoped": (render_scoped_memory_rows, {"rows": [], "prefix": "episode"}),
    }[entry]
    with pytest.raises(TypeError, match="observed_at"):
        function(**arguments)
    with pytest.raises(ValueError, match="E_MEMORY_OBSERVATION_REQUIRES_TIMEZONE"):
        function(**arguments, observed_at=datetime(2030, 1, 1))
