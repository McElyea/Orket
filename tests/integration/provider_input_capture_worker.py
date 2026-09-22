"""Controlled actual command observations; no provider/model inference."""
import json
import os
import sys
import time
from pathlib import Path


def main():
    mode, *arguments = sys.argv[1:]
    if mode == "owner":
        observed, release = map(Path, arguments)
        pending = observed.with_suffix(".pending")
        pending.write_text(str(os.getpid()))
        pending.replace(observed)
        deadline = time.monotonic() + 10
        while not release.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("fixture release absent")
            time.sleep(.01)
        print("released")
        return
    if mode == "exchange":
        protocol, marker = arguments
        request = sys.stdin.buffer.readline() if protocol == "jsonl" else sys.stdin.buffer.read()
        print(json.dumps(dict(marker=marker, directory=str(Path.cwd()),
                              environment=os.environ.get("ORKET_TEST_PROVIDER_INPUT"), request=request.decode())))
        return
    observations, executable, command, *rest = arguments
    alias = os.environ["ORKET_TEST_PROVIDER_INPUT"] + "-" + Path.cwd().name
    row = dict(command=[executable, command, *rest], directory=str(Path.cwd()), alias=alias)
    with Path(observations).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")
    loaded = Path("loaded-model.txt")
    if command == "list":
        print("NAME ID SIZE\n" + alias + " fixture 1")
    elif command == "ls":
        print(json.dumps([{"modelKey": alias}]))
    elif command == "ps":
        print(json.dumps([{"identifier": loaded.read_text()}] if loaded.exists() else []))
    elif command == "load":
        loaded.write_text(rest[0])
        print("load acknowledged")
    else:
        raise ValueError("Unsupported fixture command")


if __name__ == "__main__":
    main()
