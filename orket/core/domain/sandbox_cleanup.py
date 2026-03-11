from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DockerResourceType(str, Enum):
    CONTAINER = "container"
    NETWORK = "network"
    MANAGED_VOLUME = "managed_volume"


@dataclass(frozen=True)
class ObservedDockerResource:
    resource_type: DockerResourceType
    name: str
    docker_context: str
    docker_host_id: str
    labels: dict[str, str] = field(default_factory=dict)
