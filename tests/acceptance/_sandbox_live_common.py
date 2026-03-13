from __future__ import annotations

import asyncio
import json


def lightweight_compose(sandbox, _db_password: str) -> str:
    return f"""services:
  api:
    image: nginx:alpine
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    ports:
      - "{sandbox.ports.api}:80"
    volumes:
      - sandbox-data:/usr/share/nginx/html
volumes:
  sandbox-data:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
networks:
  default:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
"""


async def docker_rows(*cmd: str) -> list[dict[str, object]]:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    rows: list[dict[str, object]] = []
    for line in stdout.decode().splitlines():
        token = line.strip()
        if token:
            rows.append(json.loads(token))
    return rows


async def sandbox_resource_inventory() -> dict[str, set[str]]:
    containers = {
        str(row.get("Names") or "").strip()
        for row in await docker_rows(
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=orket.managed=true",
            "--format",
            "{{json .}}",
        )
        if str(row.get("Names") or "").strip().startswith("orket-sandbox-")
    }
    networks = {
        str(row.get("Name") or "").strip()
        for row in await docker_rows(
            "docker",
            "network",
            "ls",
            "--filter",
            "label=orket.managed=true",
            "--format",
            "{{json .}}",
        )
        if str(row.get("Name") or "").strip().startswith("orket-sandbox-")
    }
    volumes = {
        str(row.get("Name") or "").strip()
        for row in await docker_rows(
            "docker",
            "volume",
            "ls",
            "--filter",
            "label=orket.managed=true",
            "--format",
            "{{json .}}",
        )
        if str(row.get("Name") or "").strip().startswith("orket-sandbox-")
    }
    return {
        "containers": containers,
        "networks": networks,
        "volumes": volumes,
    }


async def compose_cleanup(compose_path: str, compose_project: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "docker-compose",
        "-f",
        compose_path,
        "-p",
        compose_project,
        "down",
        "-v",
        "--remove-orphans",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()
