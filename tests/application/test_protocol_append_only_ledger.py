from __future__ import annotations

from pathlib import Path
import struct

import pytest

from orket.adapters.storage.protocol_append_only_ledger import (
    AppendOnlyRunLedger,
    LedgerFramingError,
    MAX_LEDGER_PAYLOAD_BYTES,
    decode_lpj_c32_stream,
    encode_lpj_c32_record,
)


def test_lpj_c32_encode_decode_round_trip() -> None:
    first = {"event_seq": 1, "kind": "run_started", "run_id": "r1"}
    second = {"event_seq": 2, "kind": "run_finished", "run_id": "r1"}
    stream = encode_lpj_c32_record(first) + encode_lpj_c32_record(second)
    records = decode_lpj_c32_stream(stream)
    assert records == [first, second]


def test_lpj_c32_decode_ignores_partial_tail() -> None:
    first = {"event_seq": 1, "kind": "run_started"}
    second = {"event_seq": 2, "kind": "run_finished"}
    full_first = encode_lpj_c32_record(first)
    partial_second = encode_lpj_c32_record(second)[:-3]
    records = decode_lpj_c32_stream(full_first + partial_second)
    assert records == [first]


def test_lpj_c32_decode_rejects_checksum_mismatch() -> None:
    payload = {"event_seq": 1, "kind": "run_started", "run_id": "r1"}
    frame = bytearray(encode_lpj_c32_record(payload))
    frame[6] = frame[6] ^ 0x01
    with pytest.raises(LedgerFramingError) as exc:
        decode_lpj_c32_stream(bytes(frame))
    assert exc.value.code == "E_LEDGER_CORRUPT"


def test_lpj_c32_decode_rejects_non_monotonic_event_seq() -> None:
    first = {"event_seq": 1, "kind": "run_started"}
    second = {"event_seq": 1, "kind": "duplicate"}
    stream = encode_lpj_c32_record(first) + encode_lpj_c32_record(second)
    with pytest.raises(LedgerFramingError) as exc:
        decode_lpj_c32_stream(stream)
    assert exc.value.code == "E_LEDGER_SEQ"


def test_lpj_c32_decode_rejects_oversized_record_length() -> None:
    oversized_len = MAX_LEDGER_PAYLOAD_BYTES + 1
    stream = struct.pack(">I", oversized_len)
    with pytest.raises(LedgerFramingError) as exc:
        decode_lpj_c32_stream(stream)
    assert exc.value.code == "E_LEDGER_RECORD_TOO_LARGE"


def test_lpj_c32_encode_rejects_oversized_payload() -> None:
    big_value = "x" * (MAX_LEDGER_PAYLOAD_BYTES + 1024)
    with pytest.raises(LedgerFramingError) as exc:
        encode_lpj_c32_record({"event_seq": 1, "payload": big_value})
    assert exc.value.code == "E_LEDGER_RECORD_TOO_LARGE"


def test_append_only_run_ledger_assigns_monotonic_event_seq(tmp_path: Path) -> None:
    path = tmp_path / "runs" / "r1" / "events.log"
    ledger = AppendOnlyRunLedger(path)

    first = ledger.append_event({"kind": "run_started", "run_id": "r1"})
    second = ledger.append_event({"kind": "run_finished", "run_id": "r1"})
    assert first["event_seq"] == 1
    assert second["event_seq"] == 2

    replayed = ledger.replay_events()
    assert [row["event_seq"] for row in replayed] == [1, 2]
    assert replayed[0]["kind"] == "run_started"
    assert replayed[1]["kind"] == "run_finished"


def test_append_only_run_ledger_rejects_out_of_order_explicit_event_seq(tmp_path: Path) -> None:
    path = tmp_path / "runs" / "r1" / "events.log"
    ledger = AppendOnlyRunLedger(path)

    _ = ledger.append_event({"event_seq": 1, "kind": "run_started"})
    with pytest.raises(LedgerFramingError) as exc:
        ledger.append_event({"event_seq": 3, "kind": "out_of_order"})
    assert exc.value.code == "E_LEDGER_SEQ"


def test_append_only_run_ledger_replay_survives_partial_tail(tmp_path: Path) -> None:
    path = tmp_path / "runs" / "r1" / "events.log"
    ledger = AppendOnlyRunLedger(path)
    _ = ledger.append_event({"kind": "run_started"})
    full_second = encode_lpj_c32_record({"event_seq": 2, "kind": "mid"})
    path.write_bytes(path.read_bytes() + full_second[:-2])

    replayed = ledger.replay_events()
    assert len(replayed) == 1
    assert replayed[0]["event_seq"] == 1


def test_append_only_run_ledger_replay_fails_on_corrupt_record(tmp_path: Path) -> None:
    path = tmp_path / "runs" / "r1" / "events.log"
    first = encode_lpj_c32_record({"event_seq": 1, "kind": "ok"})
    broken = bytearray(encode_lpj_c32_record({"event_seq": 2, "kind": "bad"}))
    broken[-1] = broken[-1] ^ 0xFF
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(first + bytes(broken))

    ledger = AppendOnlyRunLedger(path)
    with pytest.raises(LedgerFramingError) as exc:
        ledger.replay_events()
    assert exc.value.code == "E_LEDGER_CORRUPT"
