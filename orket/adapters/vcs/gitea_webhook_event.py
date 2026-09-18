"""Translate Gitea wire vocabulary into the existing application review contract."""

from typing import Any

from orket.core.contracts.gitea_webhook import NativeGiteaReviewWebhookPayload

side_effecting = False
_REVIEW_KINDS = {
    "pull_request_review_approved": ("pull_request_approved", "approved"),
    "pull_request_review_rejected": ("pull_request_rejected", "changes_requested"),
    "pull_request_review_comment": ("pull_request_comment", "commented"),
}


def normalize_gitea_review(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    review = payload.get("review")
    if event_type == "pull_request_review" and isinstance(review, dict) and "type" not in review:
        return payload
    native = NativeGiteaReviewWebhookPayload.model_validate(payload)
    expected_event, state = _REVIEW_KINDS[native.review.type]
    if event_type not in {expected_event, "pull_request_review"}:
        raise ValueError("Gitea event header conflicts with review type")
    return {**payload, "review": {"user": native.sender.model_dump(), "state": state, "body": native.review.content}}
