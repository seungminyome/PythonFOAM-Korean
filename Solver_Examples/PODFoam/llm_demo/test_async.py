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
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zlib

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


def small_png():
    """The bytes of a valid PNG of one grey pixel."""
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0\0")) + chunk(b"IEND", b""))


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
        with tempfile.TemporaryDirectory() as directory:
            png = Path(directory) / "state.png"
            png.write_bytes(small_png())
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
                result = harness.run(sleep_after=5, sleep_s=1.0)
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
        # the last step also writes the telemetry (a forked writer, up to 0.2 s plus reaping)
        self.assertLess(max(w for step, w in walls.items() if step < 10), 0.5)
        self.assertLess(walls[10], 2.0)

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


class V2Harness(Harness):
    """The same 20 cells, each given a small square polygon, so v2 pictures can be drawn."""

    def __init__(self, environment):
        super().__init__(dict({"LLM_IMAGE_STYLE": "v2", "LLM_MODEL": "unit-test-model"}, **environment))
        for helper in ("readable_image.py", "readable_request.py"):
            shutil.copyfile(SOURCE / helper, self.case / helper)
        centres = np.column_stack([np.linspace(-1.0, 1.0, 20), np.linspace(0.0, 0.1, 20),
                                   np.full(20, 0.005)])
        corners = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], dtype=float)
        points = np.concatenate([np.column_stack([c[:2] + corners * [0.05, 0.003], np.zeros(4)])
                                 for c in centres])
        self.callback.mesh_func(centres, np.full(20, 1e-9), (1, 1, -1), 0,
                                points, np.arange(0, 81, 4), np.arange(20))


class V2PictureTests(unittest.TestCase):
    """LLM_IMAGE_STYLE=v2: the solver sends what readable_request.py builds."""

    def frame_folder(self, harness, step):
        return harness.case / "llm_observation" / f"step-{step:06d}"

    def test_describe_v2_body_is_the_tested_builder_applied_to_the_live_frame(self):
        import readable_request
        with fixture() as (endpoint, received):
            harness = V2Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint})
            try:
                result = harness.run()
                request = harness.request()
                raw = (harness.case / "llm_request_body.json").read_bytes()
                folder = self.frame_folder(harness, 5)
                files = sorted(path.name for path in folder.iterdir())
                frame, meta, arrays = readable_request.load_frame(folder)
                with patch.dict(os.environ, harness.environment):
                    rebuilt = llm_client.encode_json(
                        readable_request.describe_v2_payload(frame, model="unit-test-model"))
                kept = len(harness.callback._snapshots)
            finally:
                harness.close()
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["image_style"], "v2")
        self.assertEqual(files, ["U.png", "fields.npz", "p.png", "readable-metadata.json"])
        self.assertEqual(raw, rebuilt)
        body = json.loads(raw)
        # the frame is the solver state of the request step, not just self-consistent
        note = json.loads(body["messages"][1]["content"][0]["text"])
        self.assertEqual((note["step"], note["time_s"], note["cells"]), (5, 5e-7, 20))
        np.testing.assert_array_equal(arrays["p"], np.linspace(-1.0, 1.0, 20) * 5)
        np.testing.assert_array_equal(arrays["U"], np.arange(60).reshape(20, 3) + 5.0)
        self.assertEqual(body["messages"][0]["content"], readable_request.DESCRIBE_V2_SYSTEM_PROMPT)
        self.assertEqual([p["type"] for p in body["messages"][1]["content"]],
                         ["text", "text", "image_url", "text", "image_url"])
        self.assertEqual((body["model"], body["seed"], body["max_tokens"], body["cache_prompt"]),
                         ("unit-test-model", readable_request.SEED, readable_request.MAX_TOKENS, False))
        self.assertEqual(result["image"]["images"]["U"]["sha256"], meta["images"][0]["sha256"])
        self.assertEqual(request["input"]["plotted_range_m"]["x"], [-1.0, 1.0])
        # no SVD summary is sent, so none is computed and no snapshot window is kept
        self.assertNotIn("velocity_svd", request["numeric_summary"])
        self.assertEqual(kept, 0)
        self.assertEqual(len(received), 1)

    def test_describe_v2_asynchronous_with_a_window(self):
        with fixture(delay_s=0.3) as (endpoint, received):
            harness = V2Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1",
                                 "LLM_IMAGE_XRANGE": "-0.5,0.5"})
            try:
                result = harness.run(sleep_after=5, sleep_s=0.3)
                walls = dict(harness.walls)
                meta = json.loads((self.frame_folder(harness, 5) / "readable-metadata.json").read_text())
            finally:
                harness.close()
        self.assertEqual(result["status"], "ok", result)
        self.assertGreater(result["arrived_at_step"], 5)
        self.assertLess(walls[5], 0.2)
        self.assertEqual(meta["view"], "window")
        self.assertEqual(meta["plotted_range_m"]["x"], [-0.5, 0.5])
        self.assertEqual(meta["domain_extent_m"]["x"], [-1.0, 1.0])
        note = json.loads(received[0]["messages"][1]["content"][0]["text"])
        self.assertEqual(note["plotted_range_m"]["x"], [-0.5, 0.5])

    def test_sequence_v2_sends_two_pictures_per_time_on_their_own_scales(self):
        import readable_request
        with fixture(delay_s=0.3) as (endpoint, received):
            harness = V2Harness({"LLM_MODE": "sequence", "LLM_SEQUENCE_STEPS": "2,4,6",
                                 "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1"})
            try:
                harness.run(sleep_after=2, sleep_s=0.3)
                result = harness.result()
                walls = dict(harness.walls)
                statuses = [f["status"] for f in harness.callback._frames]
                raw = (harness.case / "llm_request_body.json").read_bytes()
                loaded = [readable_request.load_frame(self.frame_folder(harness, s)) for s in (2, 4, 6)]
                frames = [item[0] for item in loaded]
                with patch.dict(os.environ, harness.environment):
                    rebuilt = llm_client.encode_json(readable_request.sequence_v2_payload(
                        frames, model="unit-test-model", own_ranges=True))
            finally:
                harness.close()
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(statuses, ["rendered", "rendered"])
        self.assertEqual([f["step"] for f in result["frames"]], [2, 4, 6])
        self.assertEqual(result["sequence_colour_range"], "own")
        self.assertFalse(any(image["colour_range_shared"] for f in result["frames"]
                             for image in f["images"].values()))
        self.assertEqual(raw, rebuilt)
        body = received[0]
        header = json.loads(body["messages"][1]["content"][0]["text"])
        self.assertEqual([(f["step"], f["time_s"]) for f in header["frames"]], [(s, s * 1e-7) for s in (2, 4, 6)])
        for step, (_, _, arrays) in zip((2, 4, 6), loaded):
            np.testing.assert_array_equal(arrays["p"], np.linspace(-1.0, 1.0, 20) * step)
            np.testing.assert_array_equal(arrays["U"], np.arange(60).reshape(20, 3) + float(step))
        self.assertEqual(body["messages"][0]["content"], readable_request.SEQUENCE_V2OWN_SYSTEM_PROMPT)
        self.assertEqual(sum(p["type"] == "image_url" for p in body["messages"][1]["content"]), 6)
        self.assertLess(max(walls[step] for step in (2, 4, 6)), 0.2)

    def test_observe_and_four_step_sequences_are_refused_without_stopping_the_solver(self):
        for environment, message in (({"LLM_MODE": "observe"}, "LLM_IMAGE_STYLE=v2"),
                                     ({"LLM_MODE": "sequence", "LLM_SEQUENCE_STEPS": "2,4,6,8"},
                                      "at most 3 steps")):
            harness = V2Harness(dict(environment, LLM_ENDPOINT="http://127.0.0.1:1/v1/chat/completions"))
            try:
                harness.run()
                outcome = harness.callback._last_callback_outcome
                result = harness.result()
                errors = (harness.case / "llm_errors.jsonl").read_text().splitlines()
                telemetry = (harness.case / "telemetry.jsonl").read_text().splitlines()
            finally:
                harness.close()
            self.assertEqual(outcome["status"], "callback_error", outcome)
            self.assertIn(message, outcome["error"])
            self.assertIsNone(result)
            # reported once, and the run still writes its final telemetry
            self.assertEqual(len(errors), 1)
            self.assertEqual(len(telemetry), 10)

    def test_a_rerun_in_the_same_case_folder_never_sends_an_earlier_frame(self):
        with fixture() as (endpoint, received):
            harness = V2Harness({"LLM_MODE": "sequence", "LLM_SEQUENCE_STEPS": "2,4,6",
                                 "LLM_ENDPOINT": endpoint})
            try:
                harness.run()
                first = harness.result()
                # a second solver process in the same folder: step numbers start again at 1
                harness.callback = load_module(f"async_rerun_{id(harness)}", harness.case / "python_module.py")
                corners = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], dtype=float)
                centres = np.column_stack([np.linspace(-1.0, 1.0, 20), np.linspace(0.0, 0.1, 20),
                                           np.full(20, 0.005)])
                points = np.concatenate([np.column_stack([c[:2] + corners * [0.05, 0.003], np.zeros(4)])
                                         for c in centres])
                harness.callback.mesh_func(centres, np.full(20, 1e-9), (1, 1, -1), 0,
                                           points, np.arange(0, 81, 4), np.arange(20))
                harness.environment["LLM_SEQUENCE_STEPS"] = "2,5,7"
                harness.run()
                second = harness.result()
            finally:
                harness.close()
        self.assertEqual(first["status"], "ok", first)
        self.assertEqual(second["status"], "callback_error", second)
        self.assertIn("not rendered by this run", second["error"])
        self.assertEqual(len(received), 1)

    def test_telemetry_budget_follows_the_pending_lines_not_the_run(self):
        # the last step appends the pending lines, not one line per state of the run
        harness = Harness({"LLM_MODE": "describe", "LLM_ENABLED": "0", "LLM_FINAL_STEP": "1200"})
        budgets, real = [], harness.callback._bounded_writer

        def spy(target, args, deadline_at):
            if target is harness.callback._telemetry_child:
                budgets.append((args[3] is not None, deadline_at - time.monotonic()))
            return real(target, args, deadline_at)

        harness.callback._bounded_writer = spy
        try:
            with patch.dict(os.environ, harness.environment):
                for step in range(1, 1201):
                    harness.callback.analysis_func(harness.state(step))
                lines = (harness.case / "telemetry.jsonl").read_text().splitlines()
                # a backlog after failed appends gets a longer budget, still 1e-4 s per line
                backlog = harness.callback._Telemetry()
                backlog.pending, backlog.pending_lines = bytearray(b"{}\n" * 8000), 8000
                backlog.append()
        finally:
            harness.close()
        # appends after 500 and 1000 lines, the rest (200) at the last step, 0.2 s each
        self.assertEqual([last for last, _ in budgets[:3]], [False, False, True])
        for _, budget in budgets[:3]:
            self.assertTrue(0.15 < budget <= 0.2, budget)
        self.assertEqual(len(lines), 1200)
        self.assertEqual([json.loads(line)["step"] for line in lines], list(range(1, 1201)))
        self.assertGreater(budgets[3][1], 0.7)


class ScoreDescribeTests(unittest.TestCase):
    def test_distances_and_the_ten_percent_limit(self):
        import frame_scoring
        truth = {"fastest_flow": {"x_percent": 20.0, "y_percent": 30.0},
                 "lowest_pressure": {"x_percent": 80.0, "y_percent": 50.0},
                 "x_span_m": 0.12, "y_span_m": 0.04}
        score = frame_scoring.score_describe(
            {"fastest_flow_x_percent": 26.0, "fastest_flow_y_percent": 38.0,
             "lowest_pressure_x_percent": 74.0, "lowest_pressure_y_percent": 58.5}, truth)
        self.assertEqual(sorted(score), ["fastest_flow", "lowest_pressure"])
        fastest, lowest = score["fastest_flow"], score["lowest_pressure"]
        self.assertEqual(fastest["answer_percent"], [26.0, 38.0])
        self.assertEqual(fastest["true_percent"], [20.0, 30.0])
        self.assertEqual(fastest["error_percent"], [6.0, 8.0])
        self.assertEqual(fastest["distance_percent"], 10.0)
        self.assertTrue(fastest["within_10_percent"])     # exactly at the limit
        self.assertEqual(lowest["error_percent"], [-6.0, 8.5])
        self.assertFalse(lowest["within_10_percent"])
        self.assertAlmostEqual(fastest["error_m"][0], 0.0072)
        self.assertAlmostEqual(fastest["error_m"][1], 0.0032)
        self.assertAlmostEqual(fastest["distance_m"], (0.0072 ** 2 + 0.0032 ** 2) ** 0.5)


class ComputedTrendTests(unittest.TestCase):
    """v2 sequences: the answer key's trend words, computed from the frames' arrays,
    in llm_result.json next to the answer; the request body changes only when asked."""

    def run_sequence(self, environment, trickle=False):
        """The run's result, request record, body, the answer keys of its three frames and the
        bodies the tested builder gives for those frames in each form."""
        import frame_scoring
        import readable_request
        if trickle:
            from test_llm_client import serve
            server = serve("trickle")
        else:
            server = fixture(delay_s=0.3)
        with server as served:
            endpoint, received = (served, []) if trickle else served
            harness = V2Harness(dict({"LLM_MODE": "sequence", "LLM_SEQUENCE_STEPS": "2,4,6",
                                      "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1"}, **environment))
            try:
                harness.run(sleep_after=2, sleep_s=0.3)
                result, request = harness.result(), harness.request()
                raw = (harness.case / "llm_request_body.json").read_bytes()
                folders = [harness.case / "llm_observation" / f"step-{s:06d}" for s in (2, 4, 6)]
                frames = [readable_request.load_frame(folder)[0] for folder in folders]
                truths = [frame_scoring.load_v2(folder)[1] for folder in folders]
                numbers = [frame_scoring.numbers_of(truth) for truth in truths]
                bodies = {form: llm_client.encode_json(readable_request.sequence_v2_payload(
                    frames, model="unit-test-model", own_ranges=True, **options))
                    for form, options in (("own", {}), ("t", {"thresholds": True}),
                                          ("tn", {"thresholds": True, "numbers": numbers}))}
            finally:
                harness.close()
        return result, request, raw, truths, bodies, received

    def test_trends_are_recorded_and_the_default_body_is_unchanged(self):
        import frame_scoring
        import readable_request
        result, request, raw, truths, bodies, received = self.run_sequence({})
        key = json.loads(json.dumps(frame_scoring.sequence_truth(truths)))
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["computed_trends"], key)
        self.assertEqual(result["computed_trends_agreement"],
                         frame_scoring.score_sequence(result["structured_output"], key))
        # the 20-cell fields: |U| grows with the step, p gets lower, the fastest cell stays put;
        # the fixture answers decreasing, less_negative, same_place
        self.assertEqual([key[k] for k in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region")],
                         ["increasing", "more_negative", "same_place"])
        self.assertEqual(result["computed_trends_agreement"]["matches"], 1)
        self.assertEqual(raw, bodies["own"])
        self.assertEqual(received[0]["messages"][0]["content"], readable_request.SEQUENCE_V2OWN_SYSTEM_PROMPT)
        self.assertNotIn("sequence_prompt", result)
        self.assertNotIn("computed_trends", request)   # the request's record holds what was sent
        self.assertNotIn(b"max_speed_m_per_s", raw)

    def test_t_and_tn_send_the_trend_test_forms(self):
        import readable_request
        for form, system in (("t", readable_request.SEQUENCE_V2OWN_T_SYSTEM_PROMPT),
                             ("tn", readable_request.SEQUENCE_V2OWN_TN_SYSTEM_PROMPT)):
            with self.subTest(form=form):
                result, _, raw, _, bodies, received = self.run_sequence({"LLM_SEQUENCE_PROMPT": form})
                self.assertEqual(result["status"], "ok", result)
                self.assertEqual(result["sequence_prompt"], form)
                self.assertEqual(raw, bodies[form])
                self.assertEqual(received[0]["messages"][0]["content"], system)
                header = json.loads(received[0]["messages"][1]["content"][0]["text"])
                self.assertEqual([f.get("min_pressure_m2_per_s2") for f in header["frames"]],
                                 [-2.0, -4.0, -6.0] if form == "tn" else [None] * 3)

    def test_trends_are_recorded_without_an_answer(self):
        disabled = self.run_sequence({"LLM_ENABLED": "0"})[0]
        late = self.run_sequence({"LLM_CALLBACK_DEADLINE_S": "2.5", "LLM_READ_TIMEOUT_S": "2"},
                                 trickle=True)[0]
        for result, status in ((disabled, "disabled"), (late, "timeout")):
            self.assertEqual(result["status"], status, result)
            self.assertEqual(result["computed_trends"]["max_speed_trend"], "increasing")
            self.assertNotIn("computed_trends_agreement", result)

    def test_a_refused_sequence_prompt_draws_no_frame_and_the_run_goes_on(self):
        for environment, message in (({"LLM_SEQUENCE_PROMPT": "numbers"}, "own, t or tn"),
                                     ({"LLM_SEQUENCE_PROMPT": "tn", "LLM_IMAGE_STYLE": "v1"},
                                      "LLM_IMAGE_STYLE=v2")):
            harness = V2Harness(dict({"LLM_MODE": "sequence", "LLM_SEQUENCE_STEPS": "2,4,6",
                                      "LLM_ENDPOINT": "http://127.0.0.1:1/v1/chat/completions"},
                                     **environment))
            try:
                harness.run()
                outcome = harness.callback._last_callback_outcome
                errors = (harness.case / "llm_errors.jsonl").read_text().splitlines()
                telemetry = (harness.case / "telemetry.jsonl").read_text().splitlines()
                drawn = (harness.case / "llm_observation").exists()
            finally:
                harness.close()
            self.assertEqual(outcome["status"], "callback_error", outcome)
            self.assertIn(message, outcome["error"])
            self.assertEqual(len(errors), 1)
            self.assertFalse(drawn)
            self.assertEqual(len(telemetry), 10)

    def test_the_rules_are_the_answer_key_of_the_picture_tests(self):
        import frame_scoring
        harness = V2Harness({})
        callback = harness.callback
        harness.close()

        def same(ours, key):
            self.assertEqual(json.loads(json.dumps(ours)), json.loads(json.dumps(key)))

        rng = np.random.default_rng(20261028)
        compared = drawn = 0
        while compared < 400:   # 400 seeded cases with at least one cell inside the window
            case, drawn = drawn, drawn + 1
            self.assertLess(drawn, 1000)   # about one window in four holds no cell
            cells = int(rng.integers(3, 80))
            centres = np.column_stack([rng.uniform(-1, 1, cells), rng.uniform(0, 0.2, cells), np.zeros(cells)])
            plotted = ([[-1.0, 1.0], [0.0, 0.2]] if case % 3 == 0 else
                       [sorted(rng.uniform(-1, 1, 2).tolist()), sorted(rng.uniform(0, 0.2, 2).tolist())])
            inside = ((centres[:, 0] >= plotted[0][0]) & (centres[:, 0] <= plotted[0][1])
                      & (centres[:, 1] >= plotted[1][0]) & (centres[:, 1] <= plotted[1][1]))
            if not inside.any():
                continue   # the key has nothing to compare; draw another case
            offset = 50.0 if case % 4 == 0 else 0.0   # some sequences with positive pressures only
            fields = [(rng.normal(size=(cells, 3)) * rng.uniform(0.5, 2.0),
                       np.abs(rng.normal(size=cells)) * 10 + offset if offset else rng.normal(size=cells) * 100)
                      for _ in range(int(rng.integers(2, 4)))]
            times = [(100 * (k + 1), 1e-4 * (k + 1)) for k in range(len(fields))]
            key = frame_scoring.sequence_truth([frame_scoring.truth_from_arrays(centres, u, p, plotted, s, t)
                                                for (u, p), (s, t) in zip(fields, times)])
            ours = callback._sequence_trends([callback._frame_extrema(centres, u, p, plotted, s, t)
                                              for (u, p), (s, t) in zip(fields, times)])
            same(ours, key)
            answer = {"max_speed_trend": ("increasing", "decreasing", "roughly_constant", "cannot_tell")[case % 4],
                      "min_pressure_trend": ("more_negative", "less_negative", "roughly_constant")[case % 3],
                      "fastest_flow_region": ("same_place", "moves", "cannot_tell")[case % 3]}
            same(callback._trend_agreement(answer, ours), frame_scoring.score_sequence(answer, key))
            compared += 1
        self.assertEqual(compared, 400)
        # values at the thresholds: 2 % relative change, 5 % of the plotted range
        for first, last in ((1.0, 1.02), (0.98, 1.0), (1.0, 0.98), (-1.0, -1.02), (0.0, 0.0), (-3.0, 3.0)):
            self.assertEqual(callback._trend(first, last), frame_scoring.trend(first, last))
        # the fastest cell moves from x = 10 % to exactly 15 % of the range, or a little further
        centres = np.array([[10.0, 0.5, 0.0], [15.0, 0.5, 0.0], [15.000001, 0.5, 0.0]])
        box = [[0.0, 100.0], [0.0, 1.0]]
        first = np.array([[3.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        for fastest, word in ((1, "same_place"), (2, "moves")):
            last = np.full((3, 3), 0.1)
            last[fastest] = [3.0, 0.0, 0.0]
            fields = [(first, np.zeros(3)), (last, np.zeros(3))]
            key = frame_scoring.sequence_truth([frame_scoring.truth_from_arrays(centres, u, p, box, k, k)
                                                for k, (u, p) in enumerate(fields)])
            same(callback._sequence_trends([callback._frame_extrema(centres, u, p, box, k, k)
                                            for k, (u, p) in enumerate(fields)]), key)
            self.assertEqual(key["fastest_flow_region"], word)


class PeriodicRequestTests(unittest.TestCase):
    """LLM_ANALYSIS_EVERY: a describe request every N steps, each with its own record folder."""

    def test_requests_every_n_steps_write_their_own_records_and_an_index(self):
        import readable_request
        with fixture() as (endpoint, received):
            harness = V2Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1",
                                 "LLM_ANALYSIS_STEP": "2", "LLM_ANALYSIS_EVERY": "3"})
            try:
                harness.run(sleep_after=1, sleep_s=0.4)   # each request completes before the next step
                index = json.loads((harness.case / "llm_requests" / "index.json").read_text())
                records = {}
                for folder in sorted((harness.case / "llm_requests").glob("step-*")):
                    result = json.loads((folder / "llm_result.json").read_text())
                    body = (folder / "llm_request_body.json").read_bytes()
                    frame, meta, arrays = readable_request.load_frame(
                        harness.case / "llm_observation" / f"step-{result['request_step']:06d}")
                    with patch.dict(os.environ, harness.environment):
                        rebuilt = llm_client.encode_json(readable_request.describe_v2_payload(frame, model="unit-test-model"))
                    records[folder.name] = (result["status"], result["request_step"], result["arrived_at_step"],
                                            body == rebuilt, meta["step"])
                single = (harness.case / "llm_result.json").exists()
            finally:
                harness.close()
        self.assertEqual(sorted(records), ["step-000002", "step-000005", "step-000008"])
        for name, (status, step, arrived, parity, meta_step) in records.items():
            self.assertEqual(status, "ok", name)
            self.assertEqual(f"step-{step:06d}", name)
            self.assertEqual(meta_step, step)
            self.assertTrue(parity, name)
            self.assertGreaterEqual(arrived, step)
        self.assertEqual(index["every"], 3)
        self.assertEqual([r["step"] for r in index["requests"]], [2, 5, 8])
        self.assertTrue(all(r["status"] == "ok" for r in index["requests"]), index)
        self.assertTrue(all(r["record_written"] for r in index["requests"]), index)
        self.assertEqual(len(received), 3)
        self.assertFalse(single)

    def test_index_says_when_a_record_was_not_written_in_its_budget(self):
        # Seen in a real run: a reply arrived (status ok) but the writer was stopped at the 0.2 s
        # cleanup budget, so the folder had no llm_result.json while the index said ok.
        with fixture() as (endpoint, received):
            harness = V2Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1",
                                 "LLM_ANALYSIS_STEP": "2", "LLM_ANALYSIS_EVERY": "3"})
            real = harness.callback._write_final_report

            def slow(context, result, cleanup_start):
                if context.get("request_step") == 5:
                    time.sleep(1.0)
                return real(context, result, cleanup_start)
            try:
                with patch.object(harness.callback, "_write_final_report", slow):
                    harness.run(sleep_after=1, sleep_s=0.4)
                index = json.loads((harness.case / "llm_requests" / "index.json").read_text())
                written = {f.name: (f / "llm_result.json").exists()
                           for f in sorted((harness.case / "llm_requests").glob("step-*"))}
            finally:
                harness.close()
        by_step = {r["step"]: r for r in index["requests"]}
        self.assertEqual(by_step[5]["status"], "ok", index)
        self.assertFalse(by_step[5]["record_written"], index)
        self.assertFalse(written["step-000005"], written)
        self.assertTrue(by_step[2]["record_written"] and by_step[8]["record_written"], index)
        self.assertTrue(written["step-000002"] and written["step-000008"], written)

    def test_a_step_is_skipped_while_the_only_allowed_request_is_pending(self):
        with fixture(delay_s=0.6) as (endpoint, received):
            harness = V2Harness({"LLM_MODE": "describe", "LLM_ENDPOINT": endpoint, "LLM_ASYNC": "1",
                                 "LLM_ANALYSIS_STEP": "1", "LLM_ANALYSIS_EVERY": "1", "LLM_ASYNC_MAX_PENDING": "1"})
            try:
                harness.run(sleep_after=1, sleep_s=0.1)
                index = json.loads((harness.case / "llm_requests" / "index.json").read_text())
            finally:
                harness.close()
        statuses = [r["status"] for r in index["requests"]]
        self.assertEqual(len(statuses), 10)
        self.assertEqual(statuses[0], "ok")
        self.assertIn("skipped_pending", statuses)
        self.assertEqual(len(received), statuses.count("ok"))

    def test_periodic_needs_describe_and_v2(self):
        harness = V2Harness({"LLM_MODE": "sequence", "LLM_ANALYSIS_EVERY": "2", "LLM_SEQUENCE_STEPS": "2,4"})
        try:
            with patch.dict(os.environ, harness.environment):
                harness.callback.analysis_func(harness.state(1))
                outcome = harness.callback._last_callback_outcome
        finally:
            harness.close()
        self.assertEqual(outcome["status"], "callback_error")
        self.assertIn("LLM_ANALYSIS_EVERY", outcome["error"])


# The plane PythonSlice.H reports for a mesh of two 0.005 m layers: the middle of the z range
# (0.005 m) lies on mesh points, so the plane moved to the middle of the upper layer.
SLICE_PLANE = {"normal": (0.0, 0.0, 1.0), "z_m": 0.0075, "requested_z_m": 0.005,
               "z_source": "middle of the mesh z range", "moved_off_mesh_points": True,
               "mesh_z_range_m": (0.0, 0.01)}
# the order in which the solver lists the cut cells (scrambled here; the slice is kept in mesh order)
SLICE_CUT = np.array([27, 20, 39, 21, 22, 23, 24, 25, 26, 38, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37])


def square_polygons(xy, z):
    """(points, offsets) of one small square around each centre, in the plane z."""
    corners = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], dtype=float)
    points = np.concatenate([np.column_stack([c + corners * [0.05, 0.003], np.full(4, z)]) for c in xy])
    return points, np.arange(0, 4 * len(xy) + 1, 4)


class SliceHarness(V2Harness):
    """A 3D mesh of 40 cells: V2Harness's 20 cells in two layers, the upper one (cells 20 to 39)
    at the 2D harness's x and y. The solver passes the polygons of the plane slice through the
    upper layer, as PythonCreate.H does for a case without an empty patch. The upper layer carries
    the 2D harness's U and p, the lower layer other values."""

    LOWER = 1000.0   # added to the lower layer's U and p

    def __init__(self, environment, plane=SLICE_PLANE, cut=SLICE_CUT):
        super().__init__(environment)
        upper = np.column_stack([np.linspace(-1.0, 1.0, 20), np.linspace(0.0, 0.1, 20), np.full(20, 0.0075)])
        self.centres = np.concatenate([upper - [0.0, 0.0, 0.005], upper])
        points, offsets = square_polygons(self.centres[cut, :2], 0.0075)
        self.callback.mesh_func(self.centres, np.full(40, 1e-9), (1, 1, 1), 0,
                                points, offsets, cut, dict(plane))

    def state(self, step, end_time_s=1e-6):
        state = super().state(step, end_time_s)
        upper = np.linspace(-1.0, 1.0, 20) * step
        return dict(state, cells=40, p_cells=np.concatenate([upper + self.LOWER, upper]))

    def run(self, steps=10, sleep_after=None, sleep_s=0.0):
        with patch.dict(os.environ, self.environment):
            for step in range(1, steps + 1):
                upper = np.arange(60).reshape(20, 3) + step
                self.callback.snapshot_func(np.array(np.concatenate([upper + self.LOWER, upper]), dtype=float), 0)
                start = time.monotonic()
                self.callback.analysis_func(self.state(step))
                self.walls[step] = time.monotonic() - start
                if sleep_after is not None and step >= sleep_after:
                    time.sleep(sleep_s)
        return self.result()


class PlaneSliceTests(unittest.TestCase):
    """v2 pictures of a 3D case: a plane slice, one polygon per cut cell."""

    def test_describe_v2_of_a_3d_case_draws_the_slice_cells_as_a_2d_case_would(self):
        import matplotlib.image
        import readable_request
        frames = {}
        for name, harness_class in (("3d", SliceHarness), ("2d", V2Harness)):
            harness = harness_class({"LLM_MODE": "describe", "LLM_ENABLED": "0", "LLM_ASYNC": "1"})
            try:
                result = harness.run()
                folder = harness.case / "llm_observation" / "step-000005"
                frame, meta, arrays = readable_request.load_frame(folder)
                with patch.dict(os.environ, harness.environment):
                    rebuilt = llm_client.encode_json(readable_request.describe_v2_payload(frame, model="unit-test-model"))
                frames[name] = {"result": result, "request": harness.request(), "meta": meta, "arrays": arrays,
                                "body": (harness.case / "llm_request_body.json").read_bytes(), "rebuilt": rebuilt,
                                "pixels": {f: matplotlib.image.imread(folder / f"{f}.png") for f in ("U", "p")},
                                "geometry": harness.callback._geometry}
            finally:
                harness.close()
        sliced, flat = frames["3d"], frames["2d"]
        self.assertEqual(sliced["result"]["status"], "disabled", sliced["result"])
        # the frame holds the 20 slice cells, in mesh order, with their own U and p
        arrays = sliced["arrays"]
        np.testing.assert_array_equal(arrays["mesh_cells"], np.arange(20, 40))
        np.testing.assert_array_equal(arrays["centres"][:, :2], flat["arrays"]["centres"][:, :2])
        np.testing.assert_array_equal(arrays["centres"][:, 2], np.full(20, 0.0075))
        np.testing.assert_array_equal(arrays["U"], np.arange(60).reshape(20, 3) + 5.0)
        np.testing.assert_array_equal(arrays["p"], np.linspace(-1.0, 1.0, 20) * 5)
        np.testing.assert_array_equal(arrays["polygon_offsets"], np.arange(0, 81, 4))
        np.testing.assert_array_equal(arrays["polygon_points"],
                                      square_polygons(flat["arrays"]["centres"][:, :2], 0.0075)[0])
        self.assertEqual(sliced["meta"]["slice"], {
            "normal": [0.0, 0.0, 1.0], "z_m": 0.0075, "requested_z_m": 0.005,
            "z_source": "middle of the mesh z range", "moved_off_mesh_points": True,
            "mesh_z_range_m": [0.0, 0.01], "cells": 20, "mesh_cells_total": 40})
        self.assertEqual(sliced["meta"]["cells"], 20)
        self.assertEqual(sliced["result"]["image"]["slice"], sliced["meta"]["slice"])
        self.assertEqual(sliced["request"]["numeric_summary"]["image"]["slice"]["cells"], 20)
        self.assertEqual(sliced["request"]["numeric_summary"]["cells"], 40)
        # v1 pictures of a 3D case keep the raster of all cells: no per-cell polygons for them
        self.assertIsNone(sliced["geometry"]["polygons"])
        # the request is the tested builder applied to the frame, and reads like the 2D one
        self.assertEqual(sliced["body"], sliced["rebuilt"])
        note = json.loads(json.loads(sliced["body"])["messages"][1]["content"][0]["text"])
        self.assertEqual(note["cells"], 20)
        self.assertEqual(sliced["meta"]["plotted_range_m"], flat["meta"]["plotted_range_m"])
        # the same cells with the same values look exactly like the 2D picture
        for field in ("U", "p"):
            np.testing.assert_array_equal(sliced["pixels"][field], flat["pixels"][field])
        self.assertNotIn("slice", flat["meta"])
        self.assertNotIn("slice", flat["result"]["image"])
        self.assertEqual(sorted(flat["arrays"]), ["U", "centres", "p"])

    def test_sequence_v2_of_a_3d_case_uses_slice_frames(self):
        import readable_request
        harness = SliceHarness({"LLM_MODE": "sequence", "LLM_SEQUENCE_STEPS": "2,4,6",
                                "LLM_ENABLED": "0", "LLM_ASYNC": "1"})
        try:
            harness.run(sleep_after=2, sleep_s=0.2)
            result = harness.result()
            loaded = [readable_request.load_frame(harness.case / "llm_observation" / f"step-{s:06d}")
                      for s in (2, 4, 6)]
            raw = (harness.case / "llm_request_body.json").read_bytes()
            with patch.dict(os.environ, harness.environment):
                rebuilt = llm_client.encode_json(readable_request.sequence_v2_payload(
                    [item[0] for item in loaded], model="unit-test-model", own_ranges=True))
        finally:
            harness.close()
        self.assertEqual(result["status"], "disabled", result)
        self.assertEqual(raw, rebuilt)
        for step, (_, meta, arrays) in zip((2, 4, 6), loaded):
            self.assertEqual(meta["slice"]["cells"], 20)
            np.testing.assert_array_equal(arrays["p"], np.linspace(-1.0, 1.0, 20) * step)
        self.assertEqual([f["slice"]["z_m"] for f in result["frames"]], [0.0075] * 3)

    def test_plane_slice_checks_the_solver_polygons(self):
        import pod_image
        centres = np.zeros((40, 3))
        points, offsets = square_polygons(np.zeros((3, 2)), 0.0075)
        good = pod_image.plane_slice(points, offsets, [33, 21, 30], centres, SLICE_PLANE)
        self.assertIsNone(good["reason"])
        np.testing.assert_array_equal(good["mesh_cells"], [21, 30, 33])
        np.testing.assert_array_equal(good["polygons"]["cells"], [0, 1, 2])
        self.assertEqual(good["record"]["cells"], 3)
        moved = points.copy()
        moved[:4, 0] += 5.0   # the polygon of cell 33 is listed first; in mesh order it is last
        reordered = pod_image.plane_slice(moved, offsets, [33, 21, 30], centres, SLICE_PLANE)
        np.testing.assert_array_equal(reordered["polygons"]["points"][8:], moved[:4])
        for cells, plane, message in (
                ([21, 21, 30], SLICE_PLANE, "distinct cell"),
                ([21, 30, 40], SLICE_PLANE, "distinct cell"),
                ([21, 30, 33], dict(SLICE_PLANE, z_m=0.0074), "do not lie in the plane"),
                ([21, 30, 33], dict(SLICE_PLANE, normal=(1.0, 0.0, 0.0)), "normal to z")):
            with self.assertRaisesRegex(ValueError, message):
                pod_image.plane_slice(points, offsets, cells, centres, plane)
        with self.assertRaisesRegex(ValueError, "offsets"):
            pod_image.plane_slice(points, offsets[:-1], [21, 30, 33], centres, SLICE_PLANE)
        empty = pod_image.plane_slice(np.zeros((0, 3)), [0], [], centres, dict(SLICE_PLANE, z_m=1.0))
        self.assertEqual(empty["reason"], "the plane z = 1 m cuts no cells")
        self.assertEqual(empty["record"]["cells"], 0)
        failed = pod_image.plane_slice(np.zeros((0, 3)), [0], [], centres,
                                       {"normal": (0.0, 0.0, 1.0), "z_m": None, "z_source": "POD_SLICE_Z",
                                        "error": "POD_SLICE_Z is not a finite number: 'abc'",
                                        "mesh_z_range_m": (0.0, 0.01)})
        self.assertIn("'abc'", failed["reason"])

    def test_a_3d_case_without_a_usable_slice_refuses_v2_pictures_and_runs_on(self):
        for plane, cut, message in ((dict(SLICE_PLANE, z_m=1.0), SLICE_CUT[:0], "cuts no cells"),
                                    (None, None, "one polygon per cell"),
                                    ("off-plane", SLICE_CUT, "slice polygons rejected")):
            harness = SliceHarness({"LLM_MODE": "describe", "LLM_ENABLED": "0"})
            try:
                if plane == "off-plane":   # polygons that fail plane_slice's checks: no exception
                    points, offsets = square_polygons(harness.centres[cut, :2], 0.002)
                    count = harness.callback.mesh_func(harness.centres, np.full(40, 1e-9), (1, 1, 1), 0,
                                                       points, offsets, cut, dict(SLICE_PLANE))
                    self.assertEqual(count, 40)
                    self.assertIn("do not lie in the plane", harness.callback._geometry["slice"]["reason"])
                elif plane is None:   # a solver that passes no slice
                    harness.callback.mesh_func(harness.centres, np.full(40, 1e-9), (1, 1, 1), 0,
                                               np.zeros((0, 3)), np.zeros(1, dtype=np.int64),
                                               np.zeros(0, dtype=np.int64))
                else:
                    harness.callback.mesh_func(harness.centres, np.full(40, 1e-9), (1, 1, 1), 0,
                                               np.zeros((0, 3)), np.zeros(1, dtype=np.int64), cut, plane)
                result = harness.run()
                telemetry = (harness.case / "telemetry.jsonl").read_text().splitlines()
            finally:
                harness.close()
            self.assertEqual(result["status"], "callback_error", result)
            self.assertIn(message, result["error"])
            self.assertEqual(len(telemetry), 10)


if __name__ == "__main__":
    unittest.main()
