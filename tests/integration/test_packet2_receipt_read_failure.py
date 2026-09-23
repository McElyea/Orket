"""Layer: integration. A later protocol read failure preserves already observed rows."""
import asyncio
import io
import json
from pathlib import Path

import aiofiles.threadpool
import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.runtime.execution.phase_c_runtime_truth import collect_phase_c_packet2_facts
from tests.integration.test_packet2_receipt_parity import receipt_row, write_legacy_turn

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class FaultingReader(io.TextIOWrapper):
    def __init__(self, buffer):
        super().__init__(buffer, encoding='utf-8')
        self.delivered = 0

    def readline(self, size=-1):
        if self.delivered:
            raise OSError('controlled later protocol read failure')
        value = super().readline(size)
        self.delivered += bool(value)
        return value

    def __next__(self):
        value = self.readline()
        if not value:
            raise StopIteration
        return value


async def test_protocol_read_error_preserves_observed_prefix_and_closes_file(tmp_path, monkeypatch):
    workspace = tmp_path / 'workspace'
    directory, _ = await asyncio.to_thread(write_legacy_turn, workspace)
    target = directory / 'protocol_receipts.log'
    content = ''.join(json.dumps(receipt_row(name, sequence=index)) + '\n'
                      for index, name in enumerate(['observed-prefix', 'unobserved-tail'], 1))
    await asyncio.to_thread(target.write_text, content, encoding='utf-8')
    before = await asyncio.to_thread(target.read_bytes)
    original, streams = io.open, []

    def observed(file, *args, **options):
        stream = original(file, *args, **options)
        mode = options.get('mode', args[0] if args else 'r')
        if not isinstance(file, int) and Path(file) == target and mode == 'r':
            stream = FaultingReader(stream.detach())
            streams.append(stream)
        return stream

    monkeypatch.setattr(io, 'open', observed)
    monkeypatch.setattr(aiofiles.threadpool, 'sync_open', observed)
    result = await collect_phase_c_packet2_facts(workspace=workspace, run_id='run',
        cards_repo=AsyncCardRepository(tmp_path / 'cards.sqlite3'))
    entry, = result['narration_to_effect_audit']['entries']
    assert entry['operation_id'] == 'observed-prefix' and entry['audit_status'] == 'verified'
    assert streams and all(stream.closed and stream.delivered == 1 for stream in streams)
    assert await asyncio.to_thread(target.read_bytes) == before
