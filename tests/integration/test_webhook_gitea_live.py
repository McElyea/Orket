"""Actual disposable Gitea signs and sends a delivery to the owned Orket listener."""

import asyncio
import base64
import hashlib
import hmac
import json
import os

import httpx
import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from tests.helpers.gitea_server import local_gitea
from tests.helpers.webhook import application
from tests.helpers.webhook_listener import webhook_listener

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("ORKET_RUN_GITEA_STATE_ACCEPTANCE") != "1",
        reason="Explicit disposable localhost Gitea acceptance required",
    ),
]


async def test_native_gitea_signature_delivery_and_teardown(tmp_path):
    files = AsyncFileTools(tmp_path)
    async with local_gitea(webhook_host="host.docker.internal") as server:
        app = application(
            tmp_path,
            GITEA_URL=server.url,
            GITEA_ADMIN_USER=server.username,
            GITEA_ADMIN_PASSWORD=server.password,
            ORKET_GITEA_ALLOW_INSECURE="true",
        )
        async with httpx.AsyncClient(base_url=server.url, auth=(server.username, server.password)) as client:
            version = await client.get("/api/v1/version")
            version.raise_for_status()
            await files.write_file("server.txt", server.container_id + "\n" + version.json()["version"])
            repo = await client.post("/api/v1/user/repos", json={"name": "webhook-proof", "auto_init": True})
            repo.raise_for_status()
            path = f"/api/v1/repos/{server.username}/webhook-proof"
            async with webhook_listener(app) as (receiver, address):
                hook = await client.post(
                    path + "/hooks",
                    json={
                        "type": "gitea",
                        "active": True,
                        "events": ["push"],
                        "config": {
                            "url": f"http://host.docker.internal:{address[1]}/webhook/gitea",
                            "content_type": "json",
                            "secret": "test-secret",
                        },
                    },
                )
                hook.raise_for_status()
                hook_id = hook.json()["id"]
                trigger = await client.post(path + f"/hooks/{hook_id}/tests")
                trigger.raise_for_status()
                observation = await asyncio.wait_for(receiver.deliveries.get(), 30)
                await files.write_file("delivery.txt", json.dumps(observation, indent=2))
                signature = hmac.new(b"test-secret", observation["body"].encode(), hashlib.sha256).hexdigest()
                assert observation["headers"]["x-gitea-signature"] == signature
                assert observation["headers"]["x-gitea-delivery"]
                assert observation["status"] == 200
                assert json.loads(observation["response"])["status"] == "ignored"
            assert app.state.webhook_runtime.closed
    await files.write_file("teardown.txt", "Owned webhook listener/client and disposable Gitea teardown verified")


async def _reviewable_pull(client, server, path, branch):
    response = await client.post(path + "/branches", json={"new_branch_name": "review-proof"})
    response.raise_for_status()
    response = await client.post(
        path + "/contents/proof.txt",
        json={
            "branch": "review-proof",
            "message": "Owned review fixture",
            "content": base64.b64encode(b"proof\n").decode(),
        },
    )
    response.raise_for_status()
    response = await client.post(
        path + "/pulls",
        json={
            "base": branch,
            "head": "review-proof",
            "title": "Native webhook review fixture",
        },
    )
    response.raise_for_status()
    number = response.json()["number"]
    response = await client.post(
        "/api/v1/admin/users",
        json={
            "username": "review-proof",
            "email": "review-proof@localhost.invalid",
            "password": server.password,
            "must_change_password": False,
        },
    )
    response.raise_for_status()
    response = await client.put(path + "/collaborators/review-proof", json={"permission": "write"})
    response.raise_for_status()
    return number


async def _advance_rejections(client, server, path, number, receiver, files):
    async with httpx.AsyncClient(base_url=server.url, auth=("review-proof", server.password)) as reviewer:
        for cycle, expected in ((2, "changes_requested"), (3, "escalated"), (4, "rejected")):
            response = await reviewer.post(
                path + f"/pulls/{number}/reviews", json={"event": "REQUEST_CHANGES", "body": f"Review cycle {cycle}"}
            )
            response.raise_for_status()
            observation = await asyncio.wait_for(receiver.deliveries.get(), 30)
            await files.write_file(f"review-cycle-{cycle}.txt", json.dumps(observation, indent=2))
            assert observation["status"] == 200 and json.loads(observation["response"])["status"] == expected
    comments = await client.get(path + f"/issues/{number}/comments")
    comments.raise_for_status()
    assert any("Architect escalation required" in row["body"] for row in comments.json())
    assert any("Requirements review requested" in row["body"] for row in comments.json())
    issues = await client.get(path + "/issues", params={"type": "issues"})
    issues.raise_for_status()
    assert any(row["title"] == f"Requirements Review: PR #{number} failed after 4 cycles" for row in issues.json())
    await files.write_file(
        "remote-rejection.txt",
        json.dumps(
            {
                "comments": [row["body"] for row in comments.json()],
                "issues": [row["title"] for row in issues.json()],
            },
            indent=2,
        ),
    )


async def _replay_review(app, observation, address, server, number, event, receiver):
    headers = {key: value for key, value in observation["headers"].items() if key.startswith("x-gitea-")}
    async with httpx.AsyncClient() as ingress:
        duplicate = await ingress.post(
            f"http://127.0.0.1:{address[1]}/webhook/gitea", content=observation["body"].encode(), headers=headers
        )
    assert duplicate.status_code == 200 and duplicate.json()["status"] == "duplicate"
    replay_observation = await asyncio.wait_for(receiver.deliveries.get(), 3)
    assert json.loads(replay_observation["response"])["status"] == "duplicate"
    assert await app.state.webhook_runtime.db.get_pr_cycle_count(server.username + "/review-proof", number) == (
        1 if event == "REQUEST_CHANGES" else 0
    )


@pytest.mark.parametrize(
    "event, expected", [("REQUEST_CHANGES", "changes_requested"), ("APPROVED", "success"), ("COMMENT", "ignored")]
)
async def test_native_review_reaches_policy_once(tmp_path, event, expected):
    files = AsyncFileTools(tmp_path)
    async with local_gitea(webhook_host="host.docker.internal") as server:
        app = application(
            tmp_path,
            GITEA_URL=server.url,
            GITEA_ADMIN_USER=server.username,
            GITEA_ADMIN_PASSWORD=server.password,
            ORKET_GITEA_ALLOW_INSECURE="true",
        )
        async with httpx.AsyncClient(base_url=server.url, auth=(server.username, server.password)) as client:
            version = await client.get("/api/v1/version")
            version.raise_for_status()
            await files.write_file("server.txt", server.container_id + "\n" + version.json()["version"])
            repo = await client.post("/api/v1/user/repos", json={"name": "review-proof", "auto_init": True})
            repo.raise_for_status()
            path = f"/api/v1/repos/{server.username}/review-proof"
            number = await _reviewable_pull(client, server, path, repo.json()["default_branch"])
            async with webhook_listener(app) as (receiver, address):
                hook = await client.post(
                    path + "/hooks",
                    json={
                        "type": "gitea",
                        "active": True,
                        "events": ["pull_request_review"],
                        "config": {
                            "url": f"http://host.docker.internal:{address[1]}/webhook/gitea",
                            "content_type": "json",
                            "secret": "test-secret",
                        },
                    },
                )
                hook.raise_for_status()
                assert "pull_request_review" in hook.json()["events"]
                async with httpx.AsyncClient(base_url=server.url, auth=("review-proof", server.password)) as reviewer:
                    review = await reviewer.post(
                        path + f"/pulls/{number}/reviews", json={"event": event, "body": "Native review proof"}
                    )
                    review.raise_for_status()
                    await files.write_file("submitted-review.txt", json.dumps({"state": review.json()["state"]}))
                    assert review.json()["state"] == event
                observation = await asyncio.wait_for(receiver.deliveries.get(), 30)
                await files.write_file("review-delivery.txt", json.dumps(observation, indent=2))
                assert observation["status"] == 200
                assert json.loads(observation["response"])["status"] == expected
                await _replay_review(app, observation, address, server, number, event, receiver)
                if event == "REQUEST_CHANGES":
                    await _advance_rejections(client, server, path, number, receiver, files)
                remote = await client.get(path + f"/pulls/{number}")
                remote.raise_for_status()
                assert remote.json()["merged"] == (event == "APPROVED")
                assert remote.json()["state"] == ("open" if event == "COMMENT" else "closed")
                await files.write_file(
                    "remote-result.txt",
                    json.dumps({"merged": remote.json()["merged"], "state": remote.json()["state"]}),
                )
    await files.write_file("teardown.txt", "Owned webhook listener/client and disposable Gitea teardown verified")
