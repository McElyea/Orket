"""CLI fixture: an old ready envelope followed by a real framed model request."""
import json
import struct
import sys


def read_frame():
    header = sys.stdin.buffer.read(4)
    if len(header) != 4:
        raise SystemExit(0)
    return json.loads(sys.stdin.buffer.read(struct.unpack(">I", header)[0]))


def send(frame):
    encoded = json.dumps(frame, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(struct.pack(">I", len(encoded)) + encoded)
    sys.stdout.buffer.flush()


bootstrap = read_frame()
frame = {**bootstrap, "sequence": 1, "direction": "child_to_parent", "message_type": "ready",
         "call_id": None, "operation": None, "payload": {
             "supported_protocol_versions": ["agent_stdio_ipc.v1"],
             "supported_contract_versions": ["governed_agent_loop.v1"],
         }}
send(frame)
call = json.loads(sys.argv[1])
send({**frame, "sequence": 2, "message_type": "capability_call", "operation": "model.call.v1",
      "call_id": call["call_id"], "payload": call})
read_frame()
