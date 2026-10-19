"""Length-framed JSON messages over a pipe, with a deadline on the parent's reads."""
import json
import math
import os
import select
import struct
import time

MAX_EVENT_BYTES = 65536


def _finite_json_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite IPC number")
    return result


def _reject_json_constant(value):
    raise ValueError("Nonfinite IPC value: " + value)


def encode_frame(value):
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    if not 0 < len(payload) <= MAX_EVENT_BYTES:
        raise ValueError("IPC event exceeds 64 KiB limit")
    return struct.pack("!I", len(payload)) + payload


class FrameWriter:
    def __init__(self, fd):
        self.fd = fd

    def send(self, value):
        frame = encode_frame(value)
        position = 0
        while position < len(frame):
            position += os.write(self.fd, frame[position:])

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class FrameReader:
    """Non-blocking read end; every read gets an absolute deadline."""

    def __init__(self, fd):
        self.fd = fd
        os.set_blocking(fd, False)
        self.select_calls = 0

    def _exact(self, count, deadline_at):
        data = bytearray()
        while len(data) < count:
            remaining = deadline_at - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("IPC wall deadline exceeded")
            ready, _, _ = select.select([self.fd], [], [], remaining)
            self.select_calls += 1
            # Readiness does not prove the parent resumed before its deadline.
            if time.monotonic() >= deadline_at:
                raise TimeoutError("IPC wall deadline exceeded")
            if not ready:
                raise TimeoutError("IPC wall deadline exceeded")
            try:
                chunk = os.read(self.fd, count - len(data))
            except BlockingIOError:
                continue
            if not chunk:
                raise EOFError("Worker closed a truncated or absent IPC frame")
            data.extend(chunk)
        return bytes(data)

    def receive(self, deadline_at):
        count = struct.unpack("!I", self._exact(4, deadline_at))[0]
        if not 0 < count <= MAX_EVENT_BYTES:
            raise ValueError("Invalid IPC frame length (limit 64 KiB)")
        value = json.loads(self._exact(count, deadline_at).decode("utf-8"),
                           parse_float=_finite_json_float,
                           parse_constant=_reject_json_constant)
        if not isinstance(value, dict):
            raise ValueError("IPC event must be a JSON object")
        if time.monotonic() >= deadline_at:
            raise TimeoutError("IPC wall deadline exceeded")
        return value

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def read_frame_blocking(fd, timeout_s):
    """Read one frame in the worker, with a timeout."""
    deadline_at = time.monotonic() + timeout_s
    data = bytearray()
    needed = 4
    while len(data) < needed:
        remaining = deadline_at - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Acknowledgment frame not received before deadline")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            raise TimeoutError("Acknowledgment frame not received before deadline")
        chunk = os.read(fd, needed - len(data))
        if not chunk:
            raise EOFError("Acknowledgment pipe closed")
        data.extend(chunk)
        if len(data) == 4 and needed == 4:
            needed = 4 + struct.unpack("!I", bytes(data))[0]
            if not 0 < needed - 4 <= MAX_EVENT_BYTES:
                raise ValueError("Invalid acknowledgment frame length")
    value = json.loads(bytes(data[4:]).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Acknowledgment must be a JSON object")
    return value
