"""Layer: integration. Actual TCP observes retry inputs and lease body-limit admission."""
import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from orket.adapters.storage.gitea_state_models import CardSnapshot, LeaseInfo, decode_snapshot, encode_snapshot
from orket.application.services.gitea_state_adapter_factory import create_gitea_state_adapter_async
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_provider_http_environment import _ambient_proxy

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('method', ['POST', 'PATCH'])
@pytest.mark.parametrize('mutate', [False, True], ids=['unchanged-control', 'borrowed-inputs-change'])
async def test_gitea_retries_retain_nested_request_values(tmp_path, method, mutate):
    payload = {'value': [{'identity': 'captured'}]}
    params, headers = {'label': ['captured']}, {'X-Fixture-Identity': 'captured'}
    observed_headers, calls = [], []

    async def respond(request):
        calls.append(request)
        if len(calls) == 1:
            if mutate:
                payload['value'][0]['identity'] = 'changed'
                params['label'][0] = 'changed'
                headers['X-Fixture-Identity'] = 'changed'
            return 429, {'error': 'controlled retry'}
        return 200, {'ok': True}

    async with observed_http_server(respond, request_headers=observed_headers) as server:
        adapter = await create_gitea_state_adapter_async(base_url=server[0], owner='fixture', repo='fixture',
            token='public-token', environment={}, cwd=tmp_path, max_retries=1)
        try:
            result = await asyncio.wait_for(adapter._request_response_with_retry(method, '/issues/1/comments',
                payload=payload, params=params, extra_headers=headers), 5)
            assert result.status_code == 200 and result.json() == {'ok': True}
        finally:
            await adapter.close()
        assert adapter.http._client.is_closed and len(server[1]) == 2
        for (line, body), recorded in zip(server[1], observed_headers, strict=True):
            assert line.split()[0] == method and body == {'value': [{'identity': 'captured'}]}
            assert parse_qs(urlsplit(line.split()[1]).query) == {'label': ['captured']}
            assert recorded['x-fixture-identity'] == 'captured'
            assert recorded['authorization'] == 'token public-token'


@pytest.mark.parametrize('operation', ['acquire_lease', 'renew_lease'])
@pytest.mark.parametrize(('captured', 'ambient', 'later', 'allowed'), [
    ('65000', '1', '1', True), ('1', '65000', '65000', False),
    ('empty', '1', '1', True), (None, '65000', '1', True),
    ('invalid', '1', '1', True), ('0', '65000', '65000', False),
    ('-1', '65000', '65000', False), (' 65000 ', '1', '1', True),
    (None, '65000', '65000', True), (None, '1', '1', False),
])
async def test_gitea_lease_admission_uses_captured_body_limit(tmp_path, monkeypatch, operation,
                                                          captured, ambient, later, allowed):
    key = 'ORKET_GITEA_ISSUE_BODY_MAX_BYTES'
    _ambient_proxy(monkeypatch, '')
    for name in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'SSLKEYLOGFILE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(key, ambient)
    environment = None if captured is None else ({} if captured == 'empty' else {key: captured})
    now = datetime(2026, 9, 22, 12, tzinfo=UTC)
    lease = LeaseInfo(owner_id='fixture-worker', expires_at=(now + timedelta(seconds=30)).isoformat(), epoch=4)
    snapshot = CardSnapshot(card_id='1', state='ready', version=3,
                            lease=lease if operation == 'renew_lease' else LeaseInfo())
    observed_headers = []

    async def respond(request):
        return 200, ({'number': 1, 'body': encode_snapshot(snapshot)} if request[0].startswith('GET ') else {})

    async with observed_http_server(respond, request_headers=observed_headers,
                                   response_headers=[('ETag', '"fixture-v3"')]) as server:
        adapter = await create_gitea_state_adapter_async(base_url=server[0], owner='fixture', repo='fixture',
            token='public-token', environment=environment, cwd=tmp_path, max_retries=0)
        monkeypatch.setattr(adapter, '_now_utc', lambda: now)
        monkeypatch.setenv(key, later)
        if environment is not None:
            environment[key] = later
        try:
            call = getattr(adapter, operation)('1', owner_id='fixture-worker', lease_seconds=30)
            if allowed:
                result = await asyncio.wait_for(call, 5)
                assert result['card_id'] == '1'
            else:
                with pytest.raises(ValueError, match='E_GITEA_SNAPSHOT_BODY_TOO_LARGE'):
                    await asyncio.wait_for(call, 5)
        finally:
            await adapter.close()
        assert adapter.http._client.is_closed
        assert [line.split()[0] for line, _ in server[1]] == (['GET', 'PATCH'] if allowed else ['GET'])
        if allowed:
            published = decode_snapshot(server[1][1][1]['body'])
            assert published.card_id == '1' and published.lease.owner_id == 'fixture-worker'
            assert observed_headers[1]['if-match'] == '"fixture-v3"'


@pytest.mark.parametrize('operation', ['acquire_lease', 'renew_lease'])
@pytest.mark.parametrize('offset', [-1, 0], ids=['one-byte-over-limit', 'exact-byte-limit'])
async def test_gitea_lease_size_boundary_preserves_encoded_body(tmp_path, operation, offset):
    now = datetime(2026, 9, 22, 12, tzinfo=UTC)
    current = LeaseInfo(owner_id='fixture-worker', acquired_at=now.isoformat(),
                       expires_at=(now + timedelta(seconds=10)).isoformat(), epoch=4)
    snapshot = CardSnapshot(card_id='1', state='ready', version=3, metadata={'description': 'λ🐍'},
                            lease=current if operation == 'renew_lease' else LeaseInfo())
    expected = snapshot.model_copy(update={'version': 4, 'lease': LeaseInfo(owner_id='fixture-worker',
        acquired_at=now.isoformat(), expires_at=(now + timedelta(seconds=30)).isoformat(),
        epoch=4 if operation == 'renew_lease' else 1)})
    expected_body = encode_snapshot(expected)
    limit = len(expected_body.encode('utf-8')) + offset

    async def respond(request):
        return 200, ({'number': 1, 'body': encode_snapshot(snapshot)} if request[0].startswith('GET ') else {})

    async with observed_http_server(respond, response_headers=[('ETag', '"fixture-v3"')]) as server:
        adapter = await create_gitea_state_adapter_async(base_url=server[0], owner='fixture', repo='fixture',
            token='public-token', environment={'ORKET_GITEA_ISSUE_BODY_MAX_BYTES': str(limit)}, cwd=tmp_path)
        adapter._now_utc = lambda: now
        try:
            call = getattr(adapter, operation)('1', owner_id='fixture-worker', lease_seconds=30)
            if offset:
                with pytest.raises(ValueError, match='E_GITEA_SNAPSHOT_BODY_TOO_LARGE'):
                    await asyncio.wait_for(call, 5)
            else:
                assert (await asyncio.wait_for(call, 5))['version'] == 4
                assert server[1][1][1]['body'] == expected_body
                assert len(server[1][1][1]['body'].encode('utf-8')) == limit
        finally:
            await adapter.close()
        assert adapter.http._client.is_closed
        assert [line.split()[0] for line, _ in server[1]] == (['GET'] if offset else ['GET', 'PATCH'])
