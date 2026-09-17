"""Controlled native CLI inventory: an acknowledgement is not a loaded observation."""
import json
import sys
from pathlib import Path

state_path, mode, command = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
state = json.loads(state_path.read_text()) if state_path.exists() else {"loads": 0, "loaded": False}
if command == "ls":
    print(json.dumps([{"modelKey": "fixture"}]))
elif command == "ps":
    print(json.dumps([{"identifier": "fixture"}] if state["loaded"] else []))
elif command == "load":
    assert sys.argv[4] == "fixture"
    state["loads"] += 1
    state["loaded"] = mode == "observed"
    state_path.write_text(json.dumps(state))
    print("load acknowledged")
else:
    raise SystemExit("unsupported fixture command")
