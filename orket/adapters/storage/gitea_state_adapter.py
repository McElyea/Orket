from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from orket.adapters.storage.gitea_state_models import build_event_comment, decode_snapshot
from orket.core.contracts.state_backend import StateBackendContract
from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.schema import CardStatus, CardType


class GiteaStateAdapter(StateBackendContract):
    """
    Experimental state backend adapter for Gitea issues.

    P1 slices:
    - Implemented: fetch_ready_cards, append_event
    - Pending: lease acquisition, transitions, release/fail semantics
    """

    def __init__(
        self,
        *,
        base_url: str,
        owner: str,
        repo: str,
        token: str,
        ready_label: str = "status/ready",
        timeout_seconds: float = 20.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.owner = owner
        self.repo = repo
        self.ready_label = ready_label
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/json",
        }

    @property
    def _repo_api(self) -> str:
        return f"{self.base_url}/api/v1/repos/{self.owner}/{self.repo}"

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self._repo_api}{path}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(
                method,
                url,
                headers=self.headers,
                params=params,
                json=payload,
            )
            response.raise_for_status()
            if not response.text.strip():
                return None
            return response.json()

    async def fetch_ready_cards(self, *, limit: int = 1) -> List[Dict[str, Any]]:
        payload = await self._request_json(
            "GET",
            "/issues",
            params={
                "state": "open",
                "labels": self.ready_label,
                "limit": max(1, int(limit)),
            },
        )
        if not isinstance(payload, list):
            return []
        cards: List[Dict[str, Any]] = []
        for issue in payload:
            if not isinstance(issue, dict):
                continue
            body = str(issue.get("body") or "")
            try:
                snapshot = decode_snapshot(body)
            except Exception:
                # Ignore non-Orket issues even if they have a ready label.
                continue
            cards.append(
                {
                    "card_id": snapshot.card_id,
                    "issue_number": issue.get("number"),
                    "state": snapshot.state,
                    "version": snapshot.version,
                    "lease": snapshot.lease.model_dump(),
                    "metadata": snapshot.metadata,
                }
            )
        return cards

    async def acquire_lease(
        self,
        card_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("acquire_lease is planned in next gitea adapter slice.")

    async def append_event(
        self,
        card_id: str,
        *,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        comment = build_event_comment(event_type, payload)
        issue_number = int(card_id)
        await self._request_json(
            "POST",
            f"/issues/{issue_number}/comments",
            payload={"body": comment},
        )

    async def transition_state(
        self,
        card_id: str,
        *,
        from_state: str,
        to_state: str,
        reason: Optional[str] = None,
    ) -> None:
        self._validate_transition(from_state=from_state, to_state=to_state)
        raise NotImplementedError("transition_state persistence is planned in next gitea adapter slice.")

    async def release_or_fail(
        self,
        card_id: str,
        *,
        final_state: str,
        error: Optional[str] = None,
    ) -> None:
        raise NotImplementedError("release_or_fail is planned in next gitea adapter slice.")

    @staticmethod
    def _validate_transition(*, from_state: str, to_state: str) -> None:
        """
        Transition rules are derived from the canonical Orket state machine.
        """
        try:
            current = CardStatus(str(from_state))
            requested = CardStatus(str(to_state))
        except ValueError as exc:
            raise ValueError(f"Unknown card status transition: {from_state} -> {to_state}") from exc
        try:
            # Adapter precondition check only; persistence semantics come in later slices.
            StateMachine.validate_transition(
                CardType.ISSUE,
                current,
                requested,
                roles=["system", "integrity_guard"],
            )
        except StateMachineError as exc:
            raise ValueError(f"Invalid state transition: {from_state} -> {to_state}") from exc
