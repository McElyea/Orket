"""Isolated live API baseline probe shared by the baseline collector."""

API_FACTORY_PROBE = '''
import asyncio
import json
import os
import tempfile
from pathlib import Path
import httpx
import orket.interfaces.api as api_module
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from orket.settings import set_runtime_settings_context

async def observe(root):
    set_runtime_settings_context(user_settings={}, user_preferences={})
    first = create_api_app(CompositionConfig(project_root=root / "one"))
    second = create_api_app(CompositionConfig(project_root=root / "two"))
    deferred = all(not hasattr(app.state, "api_runtime_context") for app in (first, second))
    async with first.router.lifespan_context(first), second.router.lifespan_context(second):
        first_context = first.state.api_runtime_context
        second_context = second.state.api_runtime_context
        statuses = []
        for app in (first, second):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://baseline") as client:
                statuses.append((await client.get("/health")).status_code)
        observed = {
            "same_app_object": first is second,
            "first_context_replaced": first_context is not first.state.api_runtime_context,
            "first_root_retained": first_context.project_root == (root / "one").resolve(),
            "second_root_retained": second_context.project_root == (root / "two").resolve(),
            "distinct_contexts": first_context is not second_context,
            "distinct_engines": first_context.engine is not second_context.engine,
            "distinct_runtime_states": first_context.runtime_state is not second_context.runtime_state,
            "module_default_owner_absent": not hasattr(api_module, "app"),
            "construction_deferred": deferred,
            "health_statuses": statuses,
        }
    observed["owners_closed"] = first_context.closed and second_context.closed
    return observed

with tempfile.TemporaryDirectory(prefix="orket-api-factory-probe-") as raw:
    root = Path(raw)
    os.environ.update(ORKET_DISABLE_SANDBOX="1", ORKET_ENV="local", ORKET_API_KEY="baseline-local-key",
                      ORKET_ALLOW_INSECURE_NO_API_KEY="0", ORKET_DURABLE_ROOT=str(root / ".orket/durable"),
                      ORKET_OUTWARD_PIPELINE_DB_PATH=str(root / "outward.db"))
    print(json.dumps(asyncio.run(observe(root)), sort_keys=True))
'''
