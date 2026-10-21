"""Tests for the describe and sequence modes and the asynchronous request path.

No solver and no model: a local HTTP fixture answers with schema-valid JSON
after an optional delay. The callback module is driven through ten fake steps
with a 20-cell mesh, as in test_callback.py.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE))
import llm_client  # noqa: E402


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ANSWERS = {
    "fluid_observation": {"observations": "Residual decreased.",
                          "possible_interpretation": "Linear solve settled.",
                          "checks": "Inspect the next step."},
    "fluid_describe": {"flow_description": "Fast flow at the left, slow at the right.",
                       "fastest_flow_x_percent": 10, "fastest_flow_y_percent": 50,
                       "lowest_pressure_x_percent": 12, "lowest_pressure_y_percent": 48,
                       "uncertainties": "Colour bar ticks hard to read."},
    "fluid_sequence": {"change_description": "The bright spot fades between images.",
                       "max_speed_trend": "decreasing", "min_pressure_trend": "less_negative",
                       "fastest_flow_region": "same_place",
                       "uncertainties": "Small differences in colour."},
}


@contextmanager
def fixture(delay_s=0.0):
    """Answers every mode with valid JSON after delay_s; records the bodies."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(body)
            name = body["response_format"]["json_schema"]["name"]
            content = json.dumps(ANSWERS[name])
            time.sleep(delay_s)
            payload = json.dumps({"choices": [{"message": {"content": content},
                                               "finish_reason": "stop"}],
                                  "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


class Harness:
    """A callback module in a temporary case directory, driven step by step."""

    def __init__(self, environment):
        self.directory = tempfile.TemporaryDirectory()
        self.case = Path(self.directory.name)
        for helper in ("python_module.py", "pod_image.py", "bounded_ipc.py", "llm_client.py"):
            shutil.copyfile(SOURCE / helper, self.case / helper)
        shutil.copyfile(SOURCE.parent / "validation/python_module.py", self.case / "pod_svd.py")
        load_module("pod_svd", self.case / "pod_svd.py")
        self.callback = load_module(f"async_case_{id(self)}", self.case / "python_module.py")
        centres = np.column_stack([np.linspace(-1.0, 1.0, 20), np.linspace(0.0, 0.1, 20),
                                   np.full(20, 0.005)])
        self.callback.mesh_func(centres, np.full(20, 1e-9), (1, 1, -1), 0)
        self.environment = {
            "LLM_ENABLED": "1", "LLM_ANALYSIS_STEP": "5", "LLM_TIMEOUT_S": "4",
            "LLM_CALLBACK_DEADLINE_S": "4", "LLM_CONNECT_TIMEOUT_S": "1",
            "LLM_READ_TIMEOUT_S": "3", "LLM_RUN_ID": "unit-test-async", "LLM_IMAGE_INPUT": "1",
            "MPLCONFIGDIR": str(self.case / "mpl-cache"), "LLM_FINAL_STEP": "10",
        }
        self.environment.update(environment)
        self.walls = {}

    def close(self):
        self.directory.cleanup()

    def state(self, step, end_time_s=1e-6):
        return {"schema_version": 1, "time_s": step * 1e-7, "delta_t_s": 1e-7,
                "end_time_s": end_time_s, "step": step, "cells": 20,
                "residuals": {name: {"initial_first": 0.1 / step, "initial_last": 0.01 / step,
                                     "final_last": 0.001 / step, "linear_solves": 1,
                                     "iterations_total": 2}
                              for name in ("Ux", "Uy", "p")},
                "courant": {"mean": 0.001, "max": 0.2, "phase": "post_step_phi"},
                "continuity": {"local": 1e-9, "global": 1e-10, "cumulative": 1e-9,
                               "phase": "last_pressure_correction"},
                "p_cells": np.linspace(-1.0, 1.0, 20) * step}

    def run(self, steps=10, sleep_after=None, sleep_s=0.0):
        with patch.dict(os.environ, self.environment):
            for step in range(1, steps + 1):
                array = np.array(np.arange(60).reshape(20, 3) + step, dtype=float)
                self.callback.snapshot_func(array, 0)
                start = time.monotonic()
                self.callback.analysis_func(self.state(step))
                self.walls[step] = time.monotonic() - start
                if sleep_after is not None and step >= sleep_after:
                    time.sleep(sleep_s)
        return self.result()

    def result(self):
        path = self.case / "llm_result.json"
        return json.loads(path.read_text()) if path.exists() else None

    def request(self):
        return json.loads((self.case / "llm_request.json").read_text())

    def body(self):
        return json.loads((self.case / "llm_request_body.json").read_bytes())


class ClientModeTests(unittest.TestCase):
    def test_validate_describe(self):
        good = json.dumps(ANSWERS["fluid_describe"])
        self.assertEqual(llm_client.validate_structured(good, "describe")["fastest_flow_x_percent"], 10)
        bad = dict(ANSWERS["fluid_describe"], fastest_flow_x_percent=101)
        with self.assertRaises(ValueError):
            llm_client.validate_structured(json.dumps(bad), "describe")
        bad = dict(ANSWERS["fluid_describe"], fastest_flow_y_percent=True)
        with self.assertRaises(ValueError):
            llm_client.validate_structured(json.dumps(bad), "describe")
        with self.assertRaises(ValueError):
            llm_client.validate_structured(json.dumps(ANSWERS["fluid_observation"]), "describe")

    def test_validate_sequence_vocabulary(self):
        good = json.dumps(ANSWERS["fluid_sequence"])
        self.assertEqual(llm_client.validate_structured(good, "sequence")["max_speed_trend"], "decreasing")
        bad = dict(ANSWERS["fluid_sequence"], max_speed_trend="rising")
        with self.assertRaises(ValueError):
            llm_client.validate_structured(json.dumps(bad), "sequence")
        with self.assertRaises(ValueError):
            llm_client.validate_structured(good, "nonsense")

    def test_sequence_request_order(self):
        png = SOURCE.parents[2] / "docs/evidence/2026-10-17/pod-llm-demo.LRfJBN/fixed-pod/llm_observation/state.png"
        frames = [{"path": str(png), "step": 5, "time_s": 5e-7},
                  {"path": str(png), "step": 10, "time_s": 1e-6}]
        request = llm_client.build_sequence_request(frames)
        parts = request["messages"][1]["content"]
        self.assertEqual([p["type"] for p in parts], ["text", "text", "image_url", "text", "image_url"])
        self.assertEqual(request["response_format"]["json_schema"]["name"], "fluid_sequence")
        self.assertIn("Image 2: step 10", parts[3]["text"])
        with self.assertRaises(ValueError):
            llm_client.build_sequence_request(frames[::-1])
        with self.assertRaises(ValueError):
            llm_client.build_sequence_request(frames[:1])

    def test_describe_needs_image(self):
        with self.assertRaises(ValueError):
            llm_client.build_request({"step": 5}, None, mode="describe")


class DescribeModeTests(unittest.TestCase):
    def test_describe_synchronous(self):
        with fixture() as (endpoint, received):
            harness = Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint})
            try:
                result = harness.run()
                request = harness.request()
                body = harness.body()
            finally:
                harness.close()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "describe")
        self.assertNotIn("async", result)
        self.assertEqual(result["structured_output"]["fastest_flow_x_percent"], 10)
        self.assertEqual(request["input"]["task"], "describe this snapshot")
        self.assertIn("numeric_summary", request)
        self.assertEqual(request["numeric_summary"]["step"], 5)
        self.assertEqual(body["messages"][0]["content"], llm_client.DESCRIBE_SYSTEM_PROMPT)
        self.assertEqual([p["type"] for p in body["messages"][1]["content"]], ["text", "image_url"])
        self.assertEqual(len(received), 1)
        note = json.loads(received[0]["messages"][1]["content"][0]["text"])
        self.assertEqual(note["plotted_range_m"]["x"], [-1.0, 1.0])
        self.assertNotIn("ranges", note)

    def test_window_is_plotted_and_announced(self):
        with fixture() as (endpoint, received):
            harness = Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint,
                               "LLM_IMAGE_XRANGE": "-0.5,0.5"})
            try:
                result = harness.run()
                meta = json.loads((harness.case / "llm_observation/image-metadata.json").read_text())
            finally:
                harness.close()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(meta["plotted_range_m"]["x"], [-0.5, 0.5])
        self.assertEqual(meta["domain_extent_m"]["x"], [-1.0, 1.0])
        self.assertGreaterEqual(meta["window_cells"], 3)
        note = json.loads(received[0]["messages"][1]["content"][0]["text"])
        self.assertEqual(note["plotted_range_m"]["x"], [-0.5, 0.5])


class AsyncTests(unittest.TestCase):
    def test_answer_arrives_while_the_solver_runs(self):
        with fixture(delay_s=0.3) as (endpoint, received):
            harness = Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1"})
            try:
                result = harness.run(sleep_after=5, sleep_s=0.5)
                walls = dict(harness.walls)
                telemetry = (harness.case / "telemetry.jsonl").read_text().splitlines()
            finally:
                harness.close()
        self.assertEqual(result["status"], "ok", result)
        self.assertTrue(result["async"])
        self.assertEqual(result["request_step"], 5)
        self.assertGreater(result["arrived_at_step"], 5)
        self.assertLess(result["arrived_at_step"], 10)
        self.assertLess(result["solver_stall_s"], 0.2)
        self.assertLess(walls[5], 0.2)
        self.assertLess(max(walls.values()), 0.5)
        self.assertNotIn("end_wait_s", result)
        self.assertEqual(len(telemetry), 10)
        self.assertEqual(len(received), 1)

    def test_pending_answer_is_waited_for_at_the_end(self):
        with fixture(delay_s=0.5) as (endpoint, _):
            harness = Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1"})
            try:
                result = harness.run()
                walls = dict(harness.walls)
            finally:
                harness.close()
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["arrived_at_step"], 10)
        self.assertEqual(result["end_wait_started_at_step"], 10)
        self.assertLess(max(walls[step] for step in range(1, 10)), 0.3)
        self.assertGreater(walls[10], 0.3)

    def test_detach_policy_leaves_the_worker_running(self):
        with fixture(delay_s=0.5) as (endpoint, _):
            harness = Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1",
                               "LLM_ASYNC_END": "detach"})
            try:
                result = harness.run()
                walls = dict(harness.walls)
                # the detached worker writes its reply by itself; slow runners need longer
                path = harness.case / "llm_response.json"
                deadline = time.monotonic() + 15.0
                response = None
                while time.monotonic() < deadline:
                    if path.exists():
                        response = json.loads(path.read_text())
                        if response.get("api_response"):
                            break
                    time.sleep(0.05)
            finally:
                harness.close()
        self.assertEqual(result["status"], "detached")
        self.assertEqual(result["detached_at_step"], 10)
        self.assertLess(max(walls.values()), 0.5)
        # the detached worker finished on its own and wrote the reply
        self.assertEqual(response["api_response"]["choices"][0]["finish_reason"], "stop")

    def test_timeout_is_detected_by_polling(self):
        from test_llm_client import serve
        with serve("trickle") as endpoint:
            harness = Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1",
                               "LLM_CALLBACK_DEADLINE_S": "0.5", "LLM_READ_TIMEOUT_S": "0.3"})
            try:
                result = harness.run(sleep_after=5, sleep_s=0.2)
                walls = dict(harness.walls)
            finally:
                harness.close()
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["timeout_kind"], "callback_deadline")
        self.assertTrue(result["worker_reaped"])
        self.assertGreater(result["arrived_at_step"], 5)
        self.assertLess(result["arrived_at_step"], 10)
        self.assertLess(max(walls.values()), 0.5)

    def test_connection_refused_is_reported_without_a_stall(self):
        harness = Harness({"LLM_MODE": "describe", "LLM_ASYNC": "1",
                           "LLM_ENDPOINT": "http://127.0.0.1:1/v1/chat/completions"})
        try:
            result = harness.run(sleep_after=5, sleep_s=0.1)
            walls = dict(harness.walls)
        finally:
            harness.close()
        self.assertEqual(result["status"], "error")
        self.assertIn("refused", result["error"].lower())
        self.assertLess(max(walls.values()), 0.5)

    def test_second_request_is_skipped_while_one_is_pending(self):
        with fixture(delay_s=0.5) as (endpoint, received):
            harness = Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1"})
            try:
                with patch.dict(os.environ, harness.environment):
                    for step in range(1, 6):
                        harness.callback.snapshot_func(np.ones((20, 3)) * step, 0)
                        harness.callback.analysis_func(harness.state(step))
                    self.assertEqual(harness.callback._last_callback_outcome["status"], "pending")
                    harness.callback._launch(harness.state(6), time.monotonic(), "describe")
                    self.assertEqual(harness.callback._last_callback_outcome["status"], "skipped_pending")
                    for step in range(6, 11):
                        harness.callback.snapshot_func(np.ones((20, 3)) * step, 0)
                        harness.callback.analysis_func(harness.state(step))
                result = harness.result()
            finally:
                harness.close()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(received), 1)


class SequenceModeTests(unittest.TestCase):
    def check(self, harness, received, asynchronous):
        result = harness.result()
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["mode"], "sequence")
        self.assertEqual(result["step"], 6)
        self.assertEqual([f["step"] for f in result["frames"]], [2, 4, 6])
        for step in (2, 4):
            folder = harness.case / "llm_observation" / f"step-{step:06d}"
            self.assertTrue((folder / "state.png").exists())
            self.assertTrue((folder / "fields.npz").exists())
        self.assertTrue((harness.case / "llm_observation/state.png").exists())
        parts = received[0]["messages"][1]["content"]
        self.assertEqual([p["type"] for p in parts],
                         ["text", "text", "image_url", "text", "image_url", "text", "image_url"])
        self.assertEqual(received[0]["messages"][0]["content"], llm_client.SEQUENCE_SYSTEM_PROMPT)
        header = json.loads(parts[0]["text"])
        self.assertEqual([f["step"] for f in header["frames"]], [2, 4, 6])
        self.assertEqual(result["structured_output"]["max_speed_trend"], "decreasing")
        request = harness.request()
        self.assertEqual([f["step"] for f in request["input"]["frames"]], [2, 4, 6])
        self.assertEqual(bool(result.get("async")), asynchronous)
        return result

    def test_sequence_synchronous(self):
        with fixture() as (endpoint, received):
            harness = Harness({"LLM_MODE": "sequence", "LLM_SEQUENCE_STEPS": "2,4,6",
                               "LLM_ENDPOINT": endpoint})
            try:
                harness.run()
                result = self.check(harness, received, False)
                frames = harness.callback._frames
            finally:
                harness.close()
        self.assertEqual([f["status"] for f in frames], ["rendered", "rendered"])
        self.assertNotIn("arrived_at_step", result)

    def test_sequence_asynchronous(self):
        with fixture(delay_s=0.3) as (endpoint, received):
            harness = Harness({"LLM_MODE": "sequence", "LLM_SEQUENCE_STEPS": "2,4,6",
                               "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1"})
            try:
                harness.run(sleep_after=2, sleep_s=0.3)
                walls = dict(harness.walls)
                result = self.check(harness, received, True)
            finally:
                harness.close()
        self.assertGreater(result["arrived_at_step"], 6)
        # the frame steps and the request step only fork
        self.assertLess(max(walls[step] for step in (2, 4, 6)), 0.2)
        # no step waits for the model; the step that records the reply waits at most
        # 0.2 s for the result writer, and the last step may wait for a late reply
        self.assertLess(max(walls[step] for step in range(1, 10)), 0.5)
        self.assertLess(result["solver_stall_s"], 0.2)


if __name__ == "__main__":
    unittest.main()
