"""Layer: integration. Actual template writes remain owned and reject unsafe archive members."""
import asyncio
import threading
from io import BytesIO
from zipfile import ZipFile

import pytest

from orket.adapters.storage.extension_template_store import ExtensionTemplateStore
from orket.application.services.extension_scaffold_service import create_external_extension

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("fail", [False, True])
async def test_scaffold_cancellation_waits_for_real_publication(tmp_path, monkeypatch, fail):
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = ExtensionTemplateStore._materialize

    def held(self, name, target, force):
        entered.set()
        try:
            assert release.wait(5)
            result = original(self, name, target, force)
            if fail:
                raise OSError("controlled failure after actual publication")
            return result
        finally:
            settled.set()

    monkeypatch.setattr(ExtensionTemplateStore, "_materialize", held)
    target = tmp_path/"scaffold"
    task = asyncio.create_task(create_external_extension(target, template_kind="agent"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
        assert not task.done() and not settled.is_set()
        assert not await asyncio.to_thread(target.exists)
        release.set()
        with pytest.raises(OSError if fail else asyncio.CancelledError):
            await task
        assert settled.is_set()
        assert await asyncio.to_thread((target/"extension.yaml").is_file)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("unsafe_name", ["../escape.txt", "/absolute.txt", "C:/drive.txt", "nested\\escape.txt"])
async def test_scaffold_rejects_archive_escape_before_publication(tmp_path, monkeypatch, unsafe_name):
    import orket.adapters.storage.extension_template_store as storage

    package = tmp_path/"package"
    archives = package/"runtime"/"config"/"assets"/"extension_templates"
    await asyncio.to_thread(archives.mkdir, parents=True)
    buffer = BytesIO()
    portable_name = unsafe_name.replace("\\", "/")
    with ZipFile(buffer, "w") as archive:
        archive.writestr("first.txt", "would otherwise be copied")
        archive.writestr(portable_name, "unsafe")
    # Preserve an actual backslash in both serialized ZIP headers on Windows too.
    payload = buffer.getvalue().replace(portable_name.encode(), unsafe_name.encode())
    with ZipFile(BytesIO(payload)) as archive:
        assert archive.infolist()[-1].orig_filename == unsafe_name
    await asyncio.to_thread((archives/"governed_agent_external.zip").write_bytes, payload)
    monkeypatch.setattr(storage, "files", lambda package_name: package)
    target = tmp_path/"scaffold"
    with pytest.raises(ValueError, match="Invalid packaged template member"):
        await create_external_extension(target, template_kind="agent")
    assert not await asyncio.to_thread(target.exists)
