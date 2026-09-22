"""Standalone supervisor subprocess; never imported or run on the server event loop.

Its threads and blocking OS calls belong to this process. Only the package-owned
directory is added for sibling OS backends; -I -S excludes workspace/startup code.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from owned_command_jsonl import JsonlExchange
from owned_command_limits import JSONL_RESPONSE_LIMIT, decode_jsonl_response, output_limit_bytes

CLEANUP_SECONDS = 3.0
side_effecting = True


def _read_stream(stream, buffer, limited, errors, limit, exchange=None):
    try:
        read = stream.read if exchange is None else stream.read1
        while chunk := read(8192):
            remaining = limit - len(buffer)
            buffer.extend(chunk[:remaining])
            if len(chunk) > remaining:
                limited.set()
            if exchange is not None:
                exchange.observe(chunk)
    except OSError as exc:
        errors.append(f"capture:{type(exc).__name__}:{exc.errno}")
    finally:
        if exchange is not None:
            exchange.eof()
        stream.close()


def _read_stop(stop, errors):
    try:
        # A daemon blocked on BufferedReader's lock can abort CPython at exit.
        # This process-owned reader touches only the raw OS descriptor.
        os.read(sys.stdin.fileno(), 1)
    except OSError as exc:
        errors.append(f"owner_input:{type(exc).__name__}:{exc.errno}")
    finally:
        stop.set()  # Explicit stop, EOF or a broken owner pipe stops admission.


def _read_request():
    data = bytearray()
    while len(data) < 8 * 1024 * 1024:
        chunk = os.read(sys.stdin.fileno(), min(65536, 8 * 1024 * 1024 - len(data)))
        if not chunk:
            raise ValueError("Missing verification request delimiter")
        data.extend(chunk)
        if b"\n" in chunk:
            request, _, pending = data.partition(b"\n")
            return json.loads(request), bool(pending)
    raise ValueError("Verification request exceeds transport limit")


def _write_input(stream, data, errors):
    try:
        stream.write(data)
        stream.flush()
    except BrokenPipeError:
        pass  # Early command exit is assessed from its actual exit and output.
    except OSError as exc:
        errors.append(f"input:{type(exc).__name__}:{exc.errno}")
    finally:
        stream.close()


def _backend():
    if os.name == "nt":
        from owned_command_windows import WindowsJob
        return WindowsJob(), "windows_job"
    if sys.platform == "linux":
        from owned_command_linux import LinuxChildren
        return LinuxChildren(), "linux_subreaper"
    raise OSError("Owned verification requires Windows jobs or Linux subreapers")


def _empty(backend, process):
    return backend.empty() if os.name == "nt" else backend.reap(process)


def _cleanup(backend, process, admitted, errors):
    if process is not None and not admitted:
        # Windows assignment failed while its only initial thread was suspended.
        process.kill()
        process.wait(timeout=CLEANUP_SECONDS)
    if backend is None:
        return process is None
    started = time.monotonic()
    while time.monotonic() - started < CLEANUP_SECONDS:
        if _empty(backend, process):
            return True
        try:
            if os.name == "nt":
                backend.stop()
            else:
                backend.stop(force=time.monotonic() - started >= 0.25)
        except OSError as exc:
            diagnostic = f"terminate:{type(exc).__name__}:{exc.errno}"
            if diagnostic not in errors:
                errors.append(diagnostic)
        time.sleep(0.02)
    return _empty(backend, process)


def _capture(process, input_data, stdout, stderr, limited, errors, limit, exchange=None):
    threads = [threading.Thread(target=_read_stream, args=(stream, buffer, limited, errors, limit,
                exchange if stream is process.stdout else None), daemon=True)
               for stream, buffer in ((process.stdout, stdout), (process.stderr, stderr))]
    if exchange is not None:
        threads.append(threading.Thread(target=exchange.write, args=(process.stdin,), daemon=True))
    elif input_data is not None:
        threads.append(threading.Thread(target=_write_input, args=(process.stdin, input_data, errors), daemon=True))
    for thread in threads:
        thread.start()
    return threads


def _run_until_stop(backend, process, stop, limited, timeout, exchange=None):
    deadline = time.monotonic() + timeout
    while True:
        if stop.is_set():
            return "cancelled"
        if limited.is_set():
            return "output_limit"
        if exchange is not None and (reason := exchange.reason()) is not None:
            return reason
        if os.name == "nt":
            process.poll()
        else:
            backend.reap(process)
        if process.returncode is not None:
            return "completed"
        if time.monotonic() >= deadline:
            return "timeout"
        time.sleep(0.02)


def execute(payload, stop_received=False):
    backend, process, admitted, exchange = None, None, False, None
    stdout, stderr, errors, threads = bytearray(), bytearray(), [], []
    stop, limited = threading.Event(), threading.Event()
    if stop_received or payload.get("stop_requested") is True:
        stop.set()
    record = {"schema_version": "owned_command.v1", "request_id": payload["request_id"], "supervisor_pid": os.getpid(),
              "reason": "launch_failed", "cleanup_confirmed": False, "backend": "unavailable"}
    threading.Thread(target=_read_stop, args=(stop, errors), daemon=True).start()
    try:
        limit = output_limit_bytes(payload.get("output_limit_bytes"))
        backend, record["backend"] = _backend()
        if stop.is_set():
            record["reason"] = "cancelled"
        else:
            # CREATE_SUSPENDED is a Win32 flag not exported by subprocess.
            options = {"creationflags": 0x00000004 | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
            input_data = base64.b64decode(payload["input"], validate=True) if payload.get("input") is not None else None
            if "jsonl_frames" in payload:
                exchange = JsonlExchange(payload["jsonl_frames"], payload["jsonl_timeout"], stop,
                                        decode_response=decode_jsonl_response, line_limit=JSONL_RESPONSE_LIMIT)
            process = subprocess.Popen(payload["argv"], cwd=payload["cwd"], env=payload["env"],
                                       stdin=subprocess.PIPE if input_data is not None or exchange is not None else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
            record["command_pid"] = process.pid
            if os.name == "nt":
                backend.admit(process)
            admitted = True
            threads = _capture(process, input_data, stdout, stderr, limited, errors, limit, exchange)
            if os.name == "nt" and not stop.is_set():
                backend.release(process)
            record["reason"] = _run_until_stop(backend, process, stop, limited, float(payload["timeout"]), exchange)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"launch:{type(exc).__name__}:{getattr(exc, 'errno', None)}")
    finally:
        try:
            record["cleanup_confirmed"] = _cleanup(backend, process, admitted, errors)
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"cleanup:{type(exc).__name__}:{getattr(exc, 'errno', None)}")
        for thread in threads:
            thread.join(timeout=0.5)
        if os.name == "nt" and backend is not None:
            try:
                backend.close()
            except OSError as exc:
                errors.append(f"job_close:{type(exc).__name__}:{exc.errno}")
    if exchange is not None and exchange.failure is not None and record["reason"] == "completed":
        record["reason"] = "protocol_failed"
    result = _result(record, process, stdout, stderr, errors, threads, limited)
    if exchange is not None and exchange.failure is not None:
        result["diagnostics"].append(exchange.failure)
    return result


def _result(record, process, stdout, stderr, errors, threads, limited):
    complete = not any(thread.is_alive() for thread in threads) and not errors and not limited.is_set()
    if not record["cleanup_confirmed"]:
        record["reason"] = "cleanup_unconfirmed"
    elif limited.is_set():
        record["reason"] = "output_limit"
    elif not complete and record["reason"] == "completed":
        record["reason"] = "capture_incomplete"
    if process is not None and os.name == "nt":
        process.poll()
    record.update(returncode=process.returncode if process is not None else None,
                  stdout=base64.b64encode(stdout).decode("ascii"), stderr=base64.b64encode(stderr).decode("ascii"),
                  capture_complete=complete, diagnostics=errors)
    return record


if __name__ == "__main__":
    try:
        request, stop_received = _read_request()
        result = execute(request, stop_received)
        sys.stdout.write(json.dumps(result) + "\n")
        sys.stdout.flush()
    except Exception as exc:
        # True process boundary: no argv, environment or untrusted output is logged.
        sys.stderr.write(f"verification supervisor failed: {type(exc).__name__}\n")
        raise SystemExit(125) from exc
