"""Immutable explicit object bytes and deterministic local-state value plans."""

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class KernelTripletInputs:
    body: bytes
    links: bytes
    manifest: bytes

    def __post_init__(self) -> None:
        for value in (self.body, self.links, self.manifest):
            if type(value) is not bytes or not isinstance(json.loads(value), dict):
                raise ValueError("E_KERNEL_TRIPLET_OBJECT_BYTES_REQUIRED")


@dataclass(frozen=True, slots=True)
class TripletDigests:
    dto_type: str | None
    body_digest: str
    links_digest: str
    manifest_digest: str


@dataclass(frozen=True, slots=True)
class RefSource:
    stem: str
    location: str
    relationship: str | None
    artifact_digest: str


@dataclass(frozen=True, slots=True)
class KernelTripletPlan:
    digests: TripletDigests
    objects: tuple[tuple[str, bytes], ...]
    references: tuple[tuple[str, str, RefSource], ...]


def pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def iter_link_refs(links: dict[str, Any]) -> Iterator[tuple[str, str, str, str | None]]:
    for key in sorted(links):
        value = links[key]
        base = "/links/" + pointer_token(key)
        children = enumerate(value) if isinstance(value, list) else [(None, value)]
        for index, child in children:
            if (
                not isinstance(child, dict)
                or not isinstance(child.get("type"), str)
                or not isinstance(child.get("id"), str)
            ):
                continue
            location = base if index is None else f"{base}/{index}"
            relationship = child.get("relationship")
            yield child["type"], child["id"], location, relationship if isinstance(relationship, str) else None


def plan_kernel_triplet(inputs: KernelTripletInputs, *, stem: str) -> KernelTripletPlan:
    if not isinstance(inputs, KernelTripletInputs):
        raise TypeError("E_KERNEL_TRIPLET_INPUTS_REQUIRED")
    body = json.loads(inputs.body)
    dto_type = body.get("dto_type")
    digests = TripletDigests(
        dto_type.strip().lower() if isinstance(dto_type, str) else None,
        *(hashlib.sha256(value).hexdigest() for value in (inputs.body, inputs.links, inputs.manifest)),
    )
    references = tuple(
        (kind, identity, RefSource(stem, location, relationship, digests.links_digest))
        for kind, identity, location, relationship in iter_link_refs(json.loads(inputs.links))
    )
    return KernelTripletPlan(
        digests,
        (
            (digests.body_digest, inputs.body),
            (digests.links_digest, inputs.links),
            (digests.manifest_digest, inputs.manifest),
        ),
        references,
    )
