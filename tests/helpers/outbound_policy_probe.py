"""Real API setup and authenticated requests for outbound policy observations."""

from orket.interfaces.api import create_api_app
from tests.helpers.outward_authorization import TEST_API_KEY


def policy_app(root, environment):
    return create_api_app(
        project_root=root,
        environment={
            "ORKET_API_KEY": TEST_API_KEY,
            "ORKET_DISABLE_SANDBOX": "1",
            "ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED": "0",
            "ORKET_TTS_BACKEND": "null",
            "ORKET_STATE_BACKEND_MODE": "local",
            "ORKET_RUN_LEDGER_MODE": "sqlite",
            "ORKET_DURABLE_ROOT": str(root / "state"),
            "ORKET_GITEA_ARTIFACT_EXPORT": "0",
            **environment,
        },
    )


async def version(client):
    return await client.get("/v1/version", headers={"X-API-Key": TEST_API_KEY})
