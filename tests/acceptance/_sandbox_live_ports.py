from __future__ import annotations

import socket

from orket.domain.sandbox import PortAllocation


def patch_orchestrator_port_allocator(orchestrator, monkeypatch) -> None:
    allocator_cls = type(orchestrator.registry.port_allocator)

    def _allocate(self, sandbox_id: str, _tech_stack) -> PortAllocation:
        ports = _allocate_distinct_ports()
        self.allocated_ports[sandbox_id] = ports.api
        return ports

    monkeypatch.setattr(allocator_cls, "allocate", _allocate)


def _allocate_distinct_ports() -> PortAllocation:
    chosen: list[int] = []
    while len(chosen) < 4:
        candidate = _free_port()
        if candidate not in chosen:
            chosen.append(candidate)
    return PortAllocation(
        api=chosen[0],
        frontend=chosen[1],
        database=chosen[2],
        admin_tool=chosen[3],
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])
