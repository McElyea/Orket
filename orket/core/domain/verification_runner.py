from __future__ import annotations

RUNNER_CODE = r"""
import json
import os
import sys
import socket
import importlib.util
import traceback


def _disable_network():
    def _blocked(*args, **kwargs):
        raise RuntimeError("Network access disabled in verification subprocess")
    socket.create_connection = _blocked
    base_socket = socket.socket
    class GuardedSocket(base_socket):
        def connect(self, *args, **kwargs):
            raise RuntimeError("Network access disabled in verification subprocess")
        def connect_ex(self, *args, **kwargs):
            raise RuntimeError("Network access disabled in verification subprocess")
    socket.socket = GuardedSocket


def _apply_limits():
    try:
        import resource
        cpu_sec = int(os.getenv("ORKET_VERIFY_CPU_SEC", "2"))
        mem_mb = int(os.getenv("ORKET_VERIFY_MEM_MB", "256"))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_sec, cpu_sec))
        mem_bytes = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ImportError, OSError, ValueError, AttributeError):
        pass


def main():
    _disable_network()
    _apply_limits()

    payload = json.loads(sys.stdin.read())
    fixture_path = payload["fixture_path"]
    scenarios = payload.get("scenarios", [])
    response = {"ok": True, "results": [], "fatal_error": None}

    try:
        spec = importlib.util.spec_from_file_location("verification_fixture_subprocess", fixture_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except (FileNotFoundError, ImportError, AttributeError, OSError, SyntaxError, ValueError, TypeError) as exc:
        response["ok"] = False
        response["fatal_error"] = f"{type(exc).__name__}: {exc}"
        response["traceback"] = traceback.format_exc()
        sys.stdout.write(json.dumps(response) + "\n")
        return

    for sc in scenarios:
        scenario_id = sc["id"]
        input_data = sc.get("input_data")
        expected_output = sc.get("expected_output")
        verify_fn = getattr(module, f"verify_{scenario_id}", None) or getattr(module, "verify", None)
        result = {
            "id": scenario_id,
            "expected_output": expected_output,
            "actual_output": None,
            "status": "fail",
            "error": None,
        }
        if verify_fn is None:
            result["error"] = f"No verify function found for scenario {scenario_id}"
            response["results"].append(result)
            continue

        try:
            actual = verify_fn(input_data)
            result["actual_output"] = actual
            result["status"] = "pass" if actual == expected_output else "fail"
        except (RuntimeError, ValueError, TypeError, AssertionError, OSError) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        response["results"].append(result)

    sys.stdout.write(json.dumps(response) + "\n")


if __name__ == "__main__":
    main()
"""
