from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from urllib import error, request


@dataclass
class Scenario:
    prompt: str
    expects: tuple[str, ...]


SCENARIOS = (
    Scenario("hello", ("chat normally",)),
    Scenario("What can you do in this environment?", ("Operator CLI is available.", "/capabilities")),
    Scenario("can you really converse?", ("yes", "converse")),
    Scenario("can you tell me about this application?", ("Orket",)),
)


def _post_chat_driver(base_url: str, api_key: str, message: str) -> str:
    payload = json.dumps({"message": message}).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/v1/system/chat-driver",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )
    with request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return str(body.get("response", ""))


def main() -> int:
    base_url = os.getenv("ORKET_API_BASE_URL", "http://127.0.0.1:8000")
    api_key = os.getenv("ORKET_API_KEY", "")
    if not api_key:
        print("Missing ORKET_API_KEY.")
        return 2

    failures = 0
    for index, scenario in enumerate(SCENARIOS, start=1):
        try:
            response = _post_chat_driver(base_url, api_key, scenario.prompt)
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            failures += 1
            print(f"[{index}] ERROR prompt={scenario.prompt!r} error={exc}")
            continue

        lowered = response.lower()
        ok = all(expected.lower() in lowered for expected in scenario.expects)
        status = "PASS" if ok else "FAIL"
        print(f"[{index}] {status} prompt={scenario.prompt!r}")
        print(f"  response={response}")
        if not ok:
            print(f"  expected_substrings={scenario.expects}")
            failures += 1

    if failures:
        print(f"Operator canary failed: {failures} scenario(s).")
        return 1
    print("Operator canary passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
