"""Shared limits for the package transport and its isolated supervisor process."""
import json

DEFAULT_OUTPUT_LIMIT = 4 * 1024 * 1024
MAX_OUTPUT_LIMIT = 64 * 1024 * 1024
JSONL_RESPONSE_LIMIT = 64 * 1024


side_effecting = False


def output_limit_bytes(value: int | None) -> int:
    if value is None:
        return DEFAULT_OUTPUT_LIMIT
    if type(value) is not int or not 1 <= value <= MAX_OUTPUT_LIMIT:
        raise ValueError("E_COMMAND_OUTPUT_LIMIT_INVALID")
    return value


def decode_jsonl_response(line: bytes) -> dict:
    if len(line) > JSONL_RESPONSE_LIMIT:
        raise ValueError("jsonl_response_line_limit")
    try:
        value = json.loads(line.decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise ValueError("jsonl_response_invalid_json") from exc
    if not isinstance(value, dict):
        raise ValueError("jsonl_response_not_object")
    return value


def jsonl_request_frames(values) -> tuple[bytes, ...]:
    frames = tuple(values)
    for frame in frames:
        if not isinstance(frame, bytes) or not frame.endswith(b"\n") or b"\n" in frame[:-1]:
            raise ValueError("E_COMMAND_JSONL_REQUEST_FRAME_INVALID")
        try:
            value = json.loads(frame.decode("utf-8"))
        except (ValueError, RecursionError) as exc:
            raise ValueError("E_COMMAND_JSONL_REQUEST_INVALID") from exc
        if not isinstance(value, dict):
            raise ValueError("E_COMMAND_JSONL_REQUEST_NOT_OBJECT")
    return frames
