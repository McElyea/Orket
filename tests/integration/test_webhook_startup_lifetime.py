"""Integration: owned bootstrap, captured storage roots and refused reinitialization."""

import asyncio
import threading

import pytest

import orket.application.services.gitea_webhook_runtime as runtime_module
from orket.application.services.application_runtime_lifetime import ApplicationRuntimeLifetime
from orket.application.services.webhook_configuration import capture_webhook_configuration
from orket.runtime_paths import resolve_runtime_db_path, resolve_sandbox_lifecycle_db_path
from tests.helpers.webhook import application, environment

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_distinct_webhook_owners_close_independently_under_parent(tmp_path):
    class Parent(ApplicationRuntimeLifetime):
        async def _close_final_resource(self):
            pass

    parent, children = Parent(), []
    try:
        for name in ("first", "second"):
            root = tmp_path / name
            config = capture_webhook_configuration(root, environment=environment(root))
            child = await runtime_module.build_webhook_runtime(config)
            children.append(child)
            parent.register_owned_resource(child)
        await parent.close()
        assert parent.closed
        assert all(child.closed and child.client.is_closed for child in children)
    finally:
        for child in children:
            await child.close()


@pytest.mark.asyncio
async def test_cancelled_bootstrap_drains_constructor_then_closes_real_client(tmp_path, monkeypatch):
    config = capture_webhook_configuration(tmp_path, environment=environment(tmp_path))
    entered, release = threading.Event(), threading.Event()
    created = []
    original = runtime_module.GiteaWebhookHandler

    def held(*args, **kwargs):
        handler = original(*args, **kwargs)
        created.append(handler)
        entered.set()
        assert release.wait(5)
        return handler

    monkeypatch.setattr(runtime_module, "GiteaWebhookHandler", held)
    startup = asyncio.create_task(runtime_module.build_webhook_runtime(config))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        startup.cancel()
        await asyncio.sleep(0)
        startup.cancel()
        assert not startup.done() and not created[0].client.is_closed
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await startup
        assert created[0].closed and created[0].client.is_closed
    finally:
        release.set()
        await asyncio.gather(startup, return_exceptions=True)
        for handler in created:
            await handler.close()


@pytest.mark.asyncio
async def test_overlapping_lifespan_cannot_replace_active_owner(tmp_path):
    app = application(tmp_path)
    async with app.router.lifespan_context(app):
        original = app.state.webhook_runtime
        with pytest.raises(RuntimeError, match="already started"):
            async with app.router.lifespan_context(app):
                pytest.fail("Second owner must not be constructed")
        assert app.state.webhook_runtime is original and original.accepting_work
    assert original.closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:secret@example.com",
        "https://example.com?token=secret",
        "https://example.com/#secret",
        "https:///",
    ],
)
async def test_invalid_url_refuses_startup_without_durable_effects(tmp_path, url):
    app = application(tmp_path, GITEA_URL=url)
    with pytest.raises(ValueError) as raised:
        async with app.router.lifespan_context(app):
            pytest.fail("Invalid endpoint must fail startup")
    assert "secret" not in str(raised.value)
    assert app.state.webhook_runtime is None and not list(tmp_path.iterdir())


def test_captured_runtime_roots_keep_legacy_migration_at_invocation(tmp_path, monkeypatch):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "orket_persistence.db").write_bytes(b"legacy-runtime")
    (before / "sandbox_lifecycle.db").write_bytes(b"legacy-sandbox")
    monkeypatch.chdir(before)
    config = capture_webhook_configuration(tmp_path, environment=environment(tmp_path, ORKET_DURABLE_ROOT="chosen"))
    monkeypatch.chdir(after)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", "changed")
    runtime = resolve_runtime_db_path(invocation_root=config.invocation_root, environment=config.environment)
    sandbox = resolve_sandbox_lifecycle_db_path(invocation_root=config.invocation_root, environment=config.environment)
    assert runtime == str(before / "chosen/db/orket_persistence.db")
    assert sandbox == str(before / "chosen/db/sandbox_lifecycle.db")
    assert (before / "chosen/db/orket_persistence.db").read_bytes() == b"legacy-runtime"
    assert (before / "chosen/db/sandbox_lifecycle.db").read_bytes() == b"legacy-sandbox"
    assert not (before / "orket_persistence.db").exists() and not list(after.iterdir())
