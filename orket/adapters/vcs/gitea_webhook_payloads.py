from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


class _WebhookPayloadModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class _WebhookUser(_WebhookPayloadModel):
    login: str


class _WebhookRepository(_WebhookPayloadModel):
    name: str
    owner: _WebhookUser


class _WebhookPullRequestNumber(_WebhookPayloadModel):
    number: int


class _WebhookPullRequestOpened(_WebhookPullRequestNumber):
    title: str


class _WebhookPullRequestMerged(_WebhookPullRequestNumber):
    merged: bool = False
    merged_by: _WebhookUser | None = None


class _WebhookReview(_WebhookPayloadModel):
    user: _WebhookUser
    state: str
    body: str | None = None


class PullRequestDispatchWebhookPayload(_WebhookPayloadModel):
    action: str
    pull_request: _WebhookPullRequestMerged


class PullRequestReviewWebhookPayload(_WebhookPayloadModel):
    pull_request: _WebhookPullRequestNumber
    review: _WebhookReview
    repository: _WebhookRepository


class PullRequestOpenedWebhookPayload(_WebhookPayloadModel):
    action: str
    pull_request: _WebhookPullRequestOpened
    repository: _WebhookRepository


class PullRequestMergedWebhookPayload(_WebhookPayloadModel):
    action: str
    pull_request: _WebhookPullRequestMerged
    repository: _WebhookRepository


def webhook_payload_validation_error(*, event_type: str, exc: ValidationError) -> dict[str, Any]:
    details: list[dict[str, str]] = []
    for error in exc.errors():
        details.append(
            {
                "loc": ".".join(str(part) for part in error.get("loc", ())),
                "message": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
        )
    return {
        "status": "error",
        "error": "webhook_payload_validation_failed",
        "message": f"Invalid {event_type} webhook payload",
        "details": details,
    }
