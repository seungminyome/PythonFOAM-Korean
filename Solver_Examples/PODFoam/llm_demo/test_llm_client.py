"""Client tests against a tiny local HTTP server; no model needed."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import subprocess
import threading
import time
import unittest
from unittest.mock import Mock, patch

import base64
import tempfile
from pathlib import Path

from llm_client import (MAX_RESPONSE_BYTES, build_request, redact_request,
                        request_local, validate_structured)


@contextmanager
def serve(mode):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            if mode == "disconnect":
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
                return
            self.send_response(503 if mode == "http_error" else 200)
            self.end_headers()
            content = {"observations": "Residual decreased.",
                       "possible_interpretation": "Linear solve settled.",
                       "checks": "Inspect the next step."}
            response = {"choices": [{"message": {"content": json.dumps(content)},
                                      "finish_reason": "stop"}]}
            try:
                if mode == "trickle":
                    for _ in range(100):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(0.04)
                elif mode == "stall":
                    time.sleep(1)
                elif mode == "oversize":
                    self.wfile.write(b" " * (MAX_RESPONSE_BYTES + 1))
                elif mode == "malformed":
                    self.wfile.write(b"not json")
                elif mode == "extra_key":
                    content["extra"] = "x"
                    response["choices"][0]["message"]["content"] = json.dumps(content)
                    self.wfile.write(json.dumps(response).encode())
                else:
                    self.wfile.write(json.dumps(response).encode())
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


class ClientTests(unittest.TestCase):
    def test_success(self):
        with serve("success") as endpoint:
            result, response = request_local({"messages": []}, endpoint, 2)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output_format_valid"])
        self.assertTrue(result["http_worker_reaped"])
        self.assertEqual(result["output_text"], response["choices"][0]["message"]["content"])

    def test_refused_connection(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        result, response = request_local({}, f"http://127.0.0.1:{port}/", 2)
        self.assertEqual(result["status"], "error")
        self.assertIsNone(response)

    def test_connection_lost_before_response(self):
        with serve("disconnect") as endpoint:
            result, response = request_local({}, endpoint, 2)
        self.assertEqual(result["status"], "error")
        self.assertTrue(result["request_sent"])
        self.assertTrue(result["http_worker_reaped"])
        self.assertIsNone(response)

    def test_http_error_is_not_a_successful_observation(self):
        with serve("http_error") as endpoint:
            result, _ = request_local({}, endpoint, 2)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["http_status"], 503)
        self.assertIn("503", result["error"])

    def test_trickle_deadline(self):
        with serve("trickle") as endpoint:
            start = time.perf_counter()
            result, response = request_local({}, endpoint, 0.25)
            elapsed = time.perf_counter() - start
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["timeout_kind"], "http_deadline")
        self.assertLess(elapsed, 1.0)
        self.assertIsNone(response)
        self.assertTrue(result["http_worker_reaped"])

    def test_malformed_response(self):
        with serve("malformed") as endpoint:
            result, _ = request_local({}, endpoint, 2)
        self.assertEqual(result["status"], "error")

    def test_oversize_response(self):
        with serve("oversize") as endpoint:
            result, _ = request_local({}, endpoint, 2)
        self.assertEqual(result["status"], "error")
        self.assertIn("byte limit", result["error"])

    def test_read_timeout(self):
        with serve("stall") as endpoint:
            result, _ = request_local({}, endpoint, 2, read_timeout_s=0.1)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["timeout_kind"], "read_inactivity")
        self.assertLess(result["inference_wall_s"], 1.0)

    def test_connect_timeout(self):
        with patch("http.client.HTTPConnection.connect", side_effect=TimeoutError("connect")):
            result, _ = request_local({}, isolated=False)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["timeout_kind"], "connect")
        self.assertFalse(result["request_sent"])

    def test_http_worker_start_failure_is_returned(self):
        with patch("llm_client.subprocess.Popen", side_effect=OSError("no process slots")):
            result, response = request_local({})
        self.assertEqual(result["status"], "error")
        self.assertIn("no process slots", result["error"])
        self.assertIsNone(response)

    def test_communicate_failure_kills_child_and_closes_pipes(self):
        real_popen = subprocess.Popen
        started = []

        def failing_communicate(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            started.append(process)
            process.communicate = Mock(side_effect=OSError("pipe communication failed"))
            return process

        with patch("llm_client.subprocess.Popen", side_effect=failing_communicate):
            result, response = request_local({})
        self.assertEqual(result["status"], "error")
        self.assertIn("pipe communication failed", result["error"])
        self.assertTrue(result["http_worker_reaped"])
        self.assertIsNone(response)
        self.assertEqual(len(started), 1)
        self.assertIsNotNone(started[0].poll())
        self.assertTrue(all(stream.closed for stream in
                            (started[0].stdin, started[0].stdout, started[0].stderr)))

    def test_timeout_status_survives_cleanup_failure(self):
        process = Mock()
        process.communicate.side_effect = subprocess.TimeoutExpired("http worker", 0.1)
        process.poll.return_value = None
        process.kill.side_effect = OSError("cannot reap worker")
        with patch("llm_client.subprocess.Popen", return_value=process):
            result, response = request_local({}, timeout_s=0.1)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["timeout_kind"], "http_deadline")
        self.assertFalse(result["http_worker_reaped"])
        self.assertIn("cannot reap worker", result["http_cleanup_errors"][0])
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close.assert_called_once()
        self.assertIsNone(response)

    def test_connection_close_error_preserves_connect_timeout(self):
        connection = Mock()
        connection.connect.side_effect = TimeoutError("connect stalled")
        connection.close.side_effect = OSError("close failed")
        with patch("llm_client.http.client.HTTPConnection", return_value=connection):
            result, _ = request_local({}, isolated=False)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["timeout_kind"], "connect")
        self.assertIn("connect stalled", result["error"])

    def test_response_format(self):
        request = build_request({"a": 1})
        fmt = request["response_format"]
        self.assertEqual(fmt["type"], "json_schema")
        self.assertNotIn("schema", fmt)
        self.assertEqual(fmt["json_schema"]["schema"]["required"],
                         ["observations", "possible_interpretation", "checks"])
        self.assertTrue(fmt["json_schema"]["strict"])
        self.assertIsInstance(request["messages"][1]["content"], str)

    def test_image_request(self):
        png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.png"
            path.write_bytes(png)
            request = build_request({"a": 1}, path)
            with self.assertRaises(ValueError):
                (Path(directory) / "bad.png").write_bytes(b"notpng")
                build_request({"a": 1}, Path(directory) / "bad.png")
        content = request["messages"][1]["content"]
        self.assertEqual([part["type"] for part in content], ["text", "image_url"])
        url = content[1]["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(url.split(",", 1)[1]), png)
        redacted = redact_request(request)
        self.assertEqual(redacted["messages"][1]["content"][1]["image_url"]["png_bytes"], len(png))
        self.assertNotIn("base64," + url.split(",", 1)[1], json.dumps(redacted))
        # Original request untouched by redaction.
        self.assertEqual(request["messages"][1]["content"][1]["image_url"]["url"], url)

    def test_validate_structured(self):
        good = {"observations": "a", "possible_interpretation": "b", "checks": "c"}
        self.assertEqual(validate_structured(json.dumps(good)), good)
        for bad in ({**good, "extra": "x"}, {**good, "checks": ""}, {**good, "checks": "x" * 161},
                    {"observations": "a", "possible_interpretation": "b"}, ["a"]):
            with self.assertRaises(ValueError):
                validate_structured(json.dumps(bad))

    def test_extra_key_in_response(self):
        with serve("extra_key") as endpoint:
            result, _ = request_local({"messages": []}, endpoint, 2)
        self.assertEqual(result["status"], "invalid_output")
        self.assertFalse(result["output_format_valid"])


if __name__ == "__main__":
    unittest.main()
