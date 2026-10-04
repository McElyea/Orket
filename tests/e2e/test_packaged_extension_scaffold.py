"""Layer: end-to-end. Installed console scaffolding and validation from an unrelated directory."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from orket_extension_sdk import __version__ as sdk_version

pytestmark = [pytest.mark.end_to_end, pytest.mark.asyncio]


async def _cli(cwd, *arguments, parse_json=True):
    executable = Path(sys.executable).parent/("orket.exe" if os.name == "nt" else "orket")
    assert executable.is_file(), "Install this candidate before running its console acceptance"
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1")
    environment.pop("PYTHONPATH", None)
    process = await asyncio.create_subprocess_exec(
        str(executable), *arguments, cwd=cwd, env=environment,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
        output = json.loads(stdout) if parse_json else stdout.decode("utf-8")
        return process.returncode, output, stderr.decode("utf-8", errors="replace")
    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()


@pytest.mark.parametrize("kind", ["default", "agent"])
async def test_packaged_cli_scaffolds_validates_and_refuses_existing_target(tmp_path, kind):
    target = tmp_path/"generated"
    code, payload, stderr = await _cli(tmp_path, "ext", "init", str(target), "--kind", kind, "--json")
    assert code == 0, (payload, stderr)
    assert payload["ok"] and payload["template_kind"] == kind and payload["copied_file_count"] > 0
    manifest = await asyncio.to_thread((target/"extension.yaml").read_bytes)
    code, payload, stderr = await _cli(tmp_path, "ext", "validate", str(target), "--strict", "--json")
    assert code == 0 and payload["ok"], (payload, stderr)
    code, payload, stderr = await _cli(tmp_path, "ext", "init", str(target), "--kind", kind, "--json")
    assert code == 2 and payload["errors"][0]["code"] == "E_EXT_TARGET_EXISTS", (payload, stderr)
    assert await asyncio.to_thread((target/"extension.yaml").read_bytes) == manifest


async def test_installed_sdk_version_matches_package_in_text_and_json(tmp_path):
    """Layer: end-to-end. The installed CLI reports the canonical SDK version in both formats."""
    code, text, stderr = await _cli(tmp_path, "sdk", "--version", parse_json=False)
    assert code == 0 and text.strip() == sdk_version, (text, stderr)
    code, payload, stderr = await _cli(tmp_path, "sdk", "--version", "--json")
    assert code == 0 and payload == {"ok": True, "sdk_version": sdk_version}, (payload, stderr)
