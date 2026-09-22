"""Sequential pipe protocol inside the isolated OS supervisor, never the server loop."""
from __future__ import annotations

import base64
import threading
import time

side_effecting = True


class JsonlExchange:
    def __init__(self, frames, timeout, stop, *, decode_response, line_limit):
        self.frames = tuple(base64.b64decode(frame, validate=True) for frame in frames)
        self.timeout, self.stop = float(timeout), stop
        self.condition = threading.Condition()
        self.received, self.pending = 0, bytearray()
        self.deadline, self.stage, self.failure = None, "admission", None
        self.decode_response, self.line_limit = decode_response, line_limit

    def _fail(self, message):
        with self.condition:
            if self.failure is None:
                self.failure = message
            self.condition.notify_all()

    def _begin(self, stage):
        with self.condition:
            self.stage, self.deadline = stage, time.monotonic() + self.timeout

    def reason(self):
        with self.condition:
            if self.failure is not None:
                return "protocol_failed"
            if self.deadline is not None and time.monotonic() >= self.deadline:
                self._fail(f"jsonl_timeout:{self.stage}")
                return "timeout"
        return None

    def observe(self, chunk):
        with self.condition:
            if self.failure is not None or self.received >= len(self.frames):
                return
            self.pending.extend(chunk)
            while self.received < len(self.frames):
                delimiter = self.pending.find(b"\n")
                if delimiter < 0:
                    if len(self.pending) > self.line_limit:
                        self._fail("jsonl_response_line_limit")
                    return
                line = bytes(self.pending[:delimiter])
                del self.pending[:delimiter + 1]
                try:
                    self.decode_response(line)
                except ValueError as exc:
                    self._fail(str(exc))
                    return
                self.received += 1
                self.condition.notify_all()
            self.pending.clear()

    def eof(self):
        with self.condition:
            if self.pending and self.received < len(self.frames) and self.failure is None:
                self.observe(b"\n")  # StreamReader.readline also accepts a final EOF-terminated line.
            if self.received < len(self.frames):
                self._fail("subprocess closed stdout before returning all responses")

    def write(self, stream):
        try:
            for index, frame in enumerate(self.frames):
                if self.stop.is_set() or self.failure is not None:
                    return
                self._begin("write")
                stream.write(frame)
                stream.flush()
                self._begin("response")
                with self.condition:
                    while self.received <= index and self.failure is None and not self.stop.is_set():
                        self.condition.wait(0.02)
            self._begin("stdin_close")
        except OSError as exc:
            self._fail(f"jsonl_input:{type(exc).__name__}:{exc.errno}")
        finally:
            try:
                stream.close()
            except OSError as exc:
                self._fail(f"jsonl_close:{type(exc).__name__}:{exc.errno}")
        self._begin("exit")
