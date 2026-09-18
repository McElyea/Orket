"""Contract: admission consumes the explicit monotonic clock and captured limit."""

import pytest

from orket.application.services.webhook_configuration import capture_webhook_configuration
from orket.application.services.webhook_ingress_policy import WebhookIngressPolicy
from tests.helpers.webhook import environment

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


async def test_rate_window_expires_only_after_sixty_elapsed_seconds(tmp_path):
    config = capture_webhook_configuration(tmp_path, environment=environment(tmp_path, ORKET_RATE_LIMIT="1"))
    readings = iter([0, 60, 60.1])
    ingress = WebhookIngressPolicy(config, monotonic=lambda: next(readings))
    assert await ingress.allow()
    assert not await ingress.allow()
    assert await ingress.allow()


@pytest.mark.parametrize("invalid", [-1, float("nan"), float("inf")])
async def test_clock_reversal_or_nonfinite_observation_cannot_authorize_work(tmp_path, invalid):
    config = capture_webhook_configuration(tmp_path, environment=environment(tmp_path))
    readings = iter([0, invalid])
    ingress = WebhookIngressPolicy(config, monotonic=lambda: next(readings))
    assert await ingress.allow()
    with pytest.raises(ValueError, match="finite and nondecreasing"):
        await ingress.allow()
