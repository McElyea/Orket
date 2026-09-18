"""Fresh-process factory observations; credentials and effects stay in the test root."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from orket.interfaces import runtime_entrypoints
from orket.runtime.policy.composition import CompositionConfig
from orket.runtime.registry.module_registry import ModuleResolutionError

TRANSPORTS = ('orket.interfaces.api', 'orket.interfaces.cli', 'orket.webhook_server')
FACTORIES = {
    'api': runtime_entrypoints.create_api_app,
    'cli': runtime_entrypoints.create_cli_runtime,
    'webhook': runtime_entrypoints.create_webhook_app,
}


def denied(kind, profile):
    before = [name for name in TRANSPORTS if name in sys.modules]
    try:
        FACTORIES[kind](CompositionConfig(module_profile=profile))
    except ModuleResolutionError as exc:
        return {'error': exc.to_payload(), 'before': before,
                'after': [name for name in TRANSPORTS if name in sys.modules],
                'durable_created': Path('.orket').exists()}
    raise AssertionError('Disabled or unknown profile was admitted')


def api(*, separate_stores=False):
    os.environ['ORKET_API_KEY'] = 'entrypoint-test-key'
    os.environ['ORKET_MODULE_PROFILE'] = 'engine-only'
    roots = [(Path.cwd() / name).resolve() for name in ('one', 'two')]
    apps = []
    for root in roots:
        if separate_stores:
            os.environ['ORKET_DURABLE_ROOT'] = str(root / 'durable')
        apps.append(runtime_entrypoints.create_api_app(CompositionConfig(project_root=root, module_profile='api-runtime')))
    owners = [app.state.api_runtime_context for app in apps]
    assert apps[0] is not apps[1] and owners[0].engine is not owners[1].engine
    assert [owner.project_root for owner in owners] == roots
    with TestClient(apps[0]) as first, TestClient(apps[1]) as second:
        assert first.get('/health').json() == second.get('/health').json() == {'status': 'ok'}
        rejected = first.get('/v1/system/heartbeat')
        admitted = first.get('/v1/system/heartbeat', headers={'X-API-Key': 'entrypoint-test-key'})
        assert rejected.status_code == 403 and rejected.json() == {'detail': 'Could not validate credentials'}
        assert admitted.status_code == 200
        identities = []
        for name, client in zip(('one', 'two'), (first, second), strict=True):
            client.headers['X-API-Key'] = 'entrypoint-test-key'
            created = client.post('/v1/cards', json={'draft': {
                'name': name, 'purpose': 'Factory isolation proof', 'card_kind': 'requirement',
                'prompt': 'Record the declared fixture', 'expected_output_type': 'markdown',
                'inputs': ['requirements.md'], 'expected_outputs': ['summary.md'],
                'display_category': 'Definition', 'notes': 'Local factory proof',
                'constraints': ['fixture only'], 'approval_expectation': 'operator_review',
                'artifact_expectation': 'summary.md',
            }})
            assert created.status_code == 200, created.text
            card_id = created.json()['card_id']
            assert client.get('/v1/cards/' + card_id).json()['summary'] == name
            identities.append(card_id)
        cross_reads = [second.get('/v1/cards/' + identities[0]), first.get('/v1/cards/' + identities[1])]
        assert [response.status_code for response in cross_reads] == ([404, 404] if separate_stores else [200, 200])
        if not separate_stores:
            assert [response.json()['summary'] for response in cross_reads] == ['one', 'two']
        assert not any(owner.closed for owner in owners)
    return {'closed': [owner.closed for owner in owners], 'roots': [str(p) for p in roots],
            'auth_statuses': [rejected.status_code, admitted.status_code],
            'cross_read_statuses': [response.status_code for response in cross_reads],
            'runtime_databases': [str(Path(owner.engine.db_path).relative_to(Path.cwd())) for owner in owners],
            'databases': [str(p.relative_to(Path.cwd())) for p in sorted(Path.cwd().rglob('*.db'))]}


def webhook():
    os.environ.update(GITEA_ADMIN_PASSWORD='entrypoint-test-password', GITEA_WEBHOOK_SECRET='entrypoint-test-secret',
                      GITEA_URL='https://127.0.0.1:1', ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT='0')
    app = runtime_entrypoints.create_webhook_app(CompositionConfig(module_profile='api-webhook-runtime'))
    import orket.webhook_server as transport

    assert not hasattr(transport, "webhook_handler")
    body = b'{}'
    signature = hmac.new(b'entrypoint-test-secret', body, hashlib.sha256).hexdigest()
    with TestClient(app) as client:
        handler = app.state.webhook_runtime
        assert handler is not None
        assert client.get('/health').status_code == 200
        rejected = client.post('/webhook/gitea', content=body, headers={'X-Gitea-Event': 'ping'})
        accepted = client.post('/webhook/gitea', content=body,
                               headers={'X-Gitea-Event': 'ping', 'X-Gitea-Signature': signature})
        assert rejected.status_code == 401
        assert accepted.status_code == 200 and accepted.json()['status'] == 'ignored'
    return {'unsigned_status': rejected.status_code, 'signed_status': accepted.status_code,
            'result': accepted.json(), 'client_closed': handler.client.is_closed,
            'handler_released': handler.closed,
            'scope': 'Signed ignored event uses no outbound Gitea request or sandbox deployment'}


def retired():
    import orket.runtime as runtime
    import orket.runtime.composition as flat
    import orket.runtime.policy.composition as application

    names = ('create_api_app', 'create_cli_runtime', 'create_webhook_app')
    return {'remaining': {module.__name__: [name for name in names if hasattr(module, name)]
                          for module in (runtime, flat, application)},
            'engine_export_retained': runtime.create_engine is application.create_engine,
            'config_export_retained': runtime.CompositionConfig is CompositionConfig}


if __name__ == '__main__':
    mode = sys.argv[1]
    result = denied(*sys.argv[2:]) if mode == 'denied' else {
        'api': api, 'api-separate': lambda: api(separate_stores=True), 'webhook': webhook, 'retired': retired,
    }[mode]()
    print(json.dumps({'origin': runtime_entrypoints.__file__, 'result': result}))
