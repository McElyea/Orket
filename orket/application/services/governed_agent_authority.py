"""Application-owned invocation of the supplied governed-agent authority guard."""
from orket.core.contracts.governed_agent_ports import GovernedAgentAuthorityGuard


async def ensure_governed_agent_authority(authority_guard: GovernedAgentAuthorityGuard | None) -> None:
    if authority_guard is not None:
        await authority_guard.ensure_active()
