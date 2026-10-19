"""Callback tests without a solver or model."""
import importlib.util
from contextlib import contextmanager, nullcontext
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np


SOURCE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CallbackTests(unittest.TestCase):
    def run_case(self, enabled, summary_delay=0, nonfinite_feature=False,
                 endpoint="http://192.0.2.1/v1/chat/completions", deadline=1,
                 with_mesh=False, image_input="1", nonfinite_pressure=False):
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory)
            for helper in ("python_module.py", "pod_image.py", "bounded_ipc.py", "llm_client.py"):
                shutil.copyfile(SOURCE / helper, case / helper)
            shutil.copyfile(SOURCE.parent / "validation/python_module.py", case / "pod_svd.py")
            load_module("pod_svd", case / "pod_svd.py")
            callback = load_module("test_case_callback", case / "python_module.py")
            if with_mesh:
                centres = np.column_stack([np.linspace(-1.0, 1.0, 20), np.linspace(0.0, 0.1, 20),
                                           np.full(20, 0.005)])
                self.assertEqual(callback.mesh_func(centres, np.full(20, 1e-9), (1, 1, -1), 0), 20)
            if summary_delay:
                summarize = callback._summarize

                def delayed_summary(state):
                    time.sleep(summary_delay)
                    return summarize(state)

                callback._summarize = delayed_summary
            environment = {
                "LLM_ENABLED": "1" if enabled else "0", "LLM_ANALYSIS_STEP": "5",
                # This non-local URL is rejected before attempting networking.
                "LLM_ENDPOINT": endpoint,
                "LLM_TIMEOUT_S": "1", "LLM_MAX_TOKENS": "160",
                "LLM_CALLBACK_DEADLINE_S": str(deadline),
                "LLM_CONNECT_TIMEOUT_S": "1", "LLM_READ_TIMEOUT_S": "0.1",
                "LLM_RUN_ID": "unit-test-run", "LLM_IMAGE_INPUT": image_input,
                "MPLCONFIGDIR": str(case / "mpl-cache"),
            }
            with patch.dict(os.environ, environment):
                for step in range(1, 11):
                    array = np.array(np.arange(60).reshape(20, 3) + step, dtype=float)
                    self.assertEqual(callback.snapshot_func(array, 0), step)
                    if step == 10:
                        modes = callback.svd_func(0)
                        self.assertEqual(modes.shape, (60, 5))
                    state = {"schema_version": 1, "time_s": step * 1e-7,
                             "delta_t_s": 1e-7, "step": step, "cells": 20,
                             "residuals": {
                                 name: {"initial_first": 0.123456789 / step,
                                        "initial_last": 0.0000123456789 / step,
                                        "final_last": 0.000000123456789 / step,
                                        "linear_solves": 6 if name == "p" else 1,
                                        "iterations_total": 8}
                                 for name in ("Ux", "Uy", "p")}}
                    if nonfinite_feature and step == 5:
                        state["residuals"]["p"]["initial_first"] = float("nan")
                    if with_mesh:
                        pressure = np.linspace(-1.0, 1.0, 20) * step
                        if nonfinite_pressure and step == 5:
                            pressure[3] = float("inf")
                        state["p_cells"] = pressure
                    callback_start = time.monotonic()
                    self.assertIsNone(callback.analysis_func(state))
                    if with_mesh:
                        self.assertIs(state["p_cells"], pressure)
                        self.assertNotIn("p_cells", callback._history[-1])
                    actual_wall = time.monotonic() - callback_start
                    limit = deadline + 0.2 + 0.02 + 0.05 if step == 5 else 0.27
                    self.assertLess(actual_wall, limit)
            audit = np.load(case / "python_svd_audit.npz")
            self.assertEqual(audit["snapshots"].shape, (20, 3, 10))
            telemetry = (case / "telemetry.jsonl").read_text().splitlines()
            self.assertEqual(len(telemetry), 10)
            self.assertEqual(json.loads(telemetry[0])["residuals"]["Ux"]["initial_first"],
                             0.123456789)
            if nonfinite_pressure:
                # no picture, so no request either
                result = json.loads((case / "llm_result.json").read_text())
                self.assertEqual(result["status"], "callback_error")
                self.assertIn("nonfinite p", result["error"])
                request = json.loads((case / "llm_request.json").read_text())
                self.assertEqual(request["request_status"], "summary_pending")
                self.assertFalse((case / "llm_observation" / "state.png").exists())
                self.assertFalse((case / "llm_request_body.json").exists())
                return callback._last_callback_outcome, request
            request = json.loads((case / "llm_request.json").read_text())
            self.assertEqual(request["step"], 5)
            if summary_delay:
                self.assertIsNone(request["request"])
                self.assertEqual(request["request_status"], "summary_pending")
            else:
                self.assertEqual(request["input"]["velocity_svd"]["window_snapshots"], 5)
                if not (with_mesh and image_input == "1"):
                    self.assertLess(request["request_bytes"], 6000)
                self.assertFalse(request["input"]["velocity_svd"]["mean_removed"])
            result = json.loads((case / "llm_result.json").read_text())
            self.assertTrue(np.isfinite(modes).all())
            self.assertTrue(result["worker_reaped"])
            self.assertLess(result["callback_elapsed_s"], deadline + 0.2)
            self.assertEqual(result["run_id"], "unit-test-run")
            return result, request

    def test_disabled(self):
        result, _ = self.run_case(False)
        self.assertEqual(result["status"], "disabled")

    def test_unreachable_endpoint(self):
        result, _ = self.run_case(True)
        self.assertEqual(result["status"], "error")

    def test_slow_summary_hits_deadline(self):
        result, _ = self.run_case(True, summary_delay=2, deadline=0.2)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["timeout_kind"], "callback_deadline")
        self.assertNotIn("request_before_at", result)

    def test_nonfinite_feature_becomes_null(self):
        result, request = self.run_case(False, nonfinite_feature=True)
        self.assertEqual(result["status"], "disabled")
        summary = request["input"]
        self.assertIsNone(summary["residuals"]["p"]["initial_first"])
        self.assertEqual(summary["feature_status"], "partial_nonfinite")
        self.assertTrue(summary["feature_issues"])

    def test_trickling_http_hits_deadline(self):
        from test_llm_client import serve
        with serve("trickle") as endpoint:
            result, _ = self.run_case(True, endpoint=endpoint, deadline=0.25)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["timeout_kind"], "callback_deadline")

    def test_nonfinite_snapshot_rejected(self):
        pod = load_module("pod_svd_invalid_test", SOURCE.parent / "validation/python_module.py")
        array = np.ones((20, 3))
        array[0, 0] = float("nan")
        with self.assertRaises(ValueError):
            pod.snapshot_func(array, 0)
        self.assertTrue(np.isnan(array[0, 0]))

    def _run_delayed_io(self, target):
        """Slow down one I/O step and check the caller still returns in time."""
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory)
            shutil.copyfile(SOURCE / "python_module.py", case / "python_module.py")
            shutil.copyfile(SOURCE.parent / "validation/python_module.py", case / "pod_svd.py")
            load_module("pod_svd", case / "pod_svd.py")
            callback = load_module("test_case_delayed_io", case / "python_module.py")
            callback._snapshots = [np.ones((20, 3)) for _ in range(5)]
            state = {"schema_version": 1, "time_s": 5e-7, "delta_t_s": 1e-7,
                     "step": 5, "cells": 20,
                     "residuals": {name: {"initial_first": 0.1, "initial_last": 0.1,
                                           "final_last": 1e-6, "linear_solves": 1,
                                           "iterations_total": 1}
                                   for name in ("Ux", "Uy", "p")}}
            callback._history = [{**state, "time_s": step * 1e-7, "step": step}
                                 for step in range(1, 5)]
            if target == "telemetry":
                operation = callback._dump_telemetry

                def delayed_telemetry():
                    time.sleep(0.5)
                    operation()

                callback._dump_telemetry = delayed_telemetry
            elif target == "marker":
                operation = callback._marker

                def delayed_marker(*args):
                    time.sleep(0.5)
                    return operation(*args)

                callback._marker = delayed_marker
            elif target == "result":
                operation = callback.write_json

                def delayed_write(path, value):
                    if Path(path).name == "llm_result.json":
                        time.sleep(0.5)
                    return operation(path, value)

                callback.write_json = delayed_write
            original_stdout = sys.stdout
            parent_pid = os.getpid()

            class SlowParentFlush:
                def write(self, data):
                    return original_stdout.write(data)

                def flush(self):
                    if os.getpid() == parent_pid:
                        time.sleep(0.5)
                    return original_stdout.flush()

                def __getattr__(self, name):
                    return getattr(original_stdout, name)

            with patch.dict(os.environ, {"LLM_ENABLED": "0", "LLM_ANALYSIS_STEP": "5",
                                         "LLM_CALLBACK_DEADLINE_S": "0.25"}), (
                    patch.object(sys, "stdout", SlowParentFlush())
                    if target == "parent_flush" else nullcontext()):
                start = time.monotonic()
                callback.analysis_func(state)
                actual_elapsed = time.monotonic() - start
                self.assertLess(actual_elapsed, 0.25 + 0.2 + 0.02 + 0.05)
                if target == "telemetry":
                    # the final telemetry write has its own deadline too
                    start = time.monotonic()
                    callback.analysis_func({**state, "step": 10, "time_s": 1e-6})
                    self.assertLess(time.monotonic() - start, 0.27)
            outcome = callback._last_callback_outcome
            self.assertTrue(outcome["worker_reaped"])
            self.assertTrue(outcome["writer_reaped"])
            if target == "result":
                self.assertEqual(outcome["status"], "disabled")
                self.assertFalse(outcome["writer_completed"])
                self.assertFalse((case / "llm_result.json").exists())
            elif target == "parent_flush":
                self.assertEqual(outcome["status"], "disabled")
                self.assertTrue(outcome["writer_completed"])
            else:
                self.assertEqual(outcome["status"], "timeout")
            return actual_elapsed

    def test_slow_result_write_is_killed(self):
        self._run_delayed_io("result")

    def test_slow_telemetry_is_bounded(self):
        self._run_delayed_io("telemetry")

    def test_slow_marker_stdout_is_bounded(self):
        self._run_delayed_io("marker")

    def test_worker_start_does_not_flush_parent_stdout(self):
        self._run_delayed_io("parent_flush")

    def test_image_rendered_when_request_disabled(self):
        # Rendering with matplotlib took over 1 s on a shared CI runner, which
        # made the parent kill the worker at the deadline; allow 4 s here.
        result, request = self.run_case(False, with_mesh=True, deadline=4)
        self.assertEqual(result["status"], "disabled")
        self.assertTrue(result["image_input"])
        self.assertFalse(result["text_input_only"])
        self.assertEqual(result["image"]["step"], 5)
        self.assertEqual(request["input"]["image"]["step"], 5)
        self.assertEqual(request["request"]["messages"][1]["content"][1]["image_url"]["png_sha256"],
                         result["image"]["sha256"])
        self.assertIn("vertical axis", request["request"]["messages"][0]["content"])

    def test_image_disabled_by_environment(self):
        result, request = self.run_case(False, with_mesh=True, image_input="0")
        self.assertFalse(result["image_input"])
        self.assertTrue(result["text_input_only"])
        self.assertIn("LLM_IMAGE_INPUT=0", result["image_skipped"]["reason"])
        self.assertIsInstance(request["request"]["messages"][1]["content"], str)

    def test_no_geometry_falls_back_to_text(self):
        result, _ = self.run_case(False)
        self.assertFalse(result["image_input"])
        self.assertIn("mesh_func", result["image_skipped"]["reason"])

    def test_nonfinite_pressure(self):
        outcome, _ = self.run_case(False, with_mesh=True, nonfinite_pressure=True)
        self.assertEqual(outcome["status"], "callback_error")
        self.assertIn("nonfinite p", outcome["error"])
        self.assertTrue(outcome["worker_reaped"])

    @contextmanager
    def fault_case(self):
        """A ready step-5 observer; inject faults without a solver or model."""
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory)
            shutil.copyfile(SOURCE / "python_module.py", case / "python_module.py")
            shutil.copyfile(SOURCE.parent / "validation/python_module.py", case / "pod_svd.py")
            load_module("pod_svd", case / "pod_svd.py")
            callback = load_module("test_case_fault", case / "python_module.py")
            callback._snapshots = [np.ones((20, 3)) for _ in range(5)]
            state = {"step": 5, "time_s": 5e-7, "delta_t_s": 1e-7, "cells": 20,
                     "residuals": {name: {"initial_first": 0.1, "initial_last": 0.1,
                                           "final_last": 1e-6, "linear_solves": 1,
                                           "iterations_total": 1}
                                   for name in ("Ux", "Uy", "p")}}
            callback._history = [{**state, "step": step, "time_s": step * 1e-7}
                                 for step in range(1, 5)]
            with patch.dict(os.environ, {"LLM_ENABLED": "0", "LLM_ANALYSIS_STEP": "5",
                                         "LLM_IMAGE_INPUT": "0", "LLM_FINAL_STEP": "10",
                                         "LLM_CALLBACK_DEADLINE_S": "0.25",
                                         "LLM_CONNECT_TIMEOUT_S": "0.1",
                                         "LLM_READ_TIMEOUT_S": "0.1"}):
                yield callback, state

    def assert_continues(self, callback, state):
        self.assertIsNone(callback.analysis_func({**state, "step": 6, "time_s": 6e-7}))
        self.assertEqual(callback._history[-1]["step"], 6)

    def test_second_pipe_failure_closes_first_pipe(self):
        with self.fault_case() as (callback, state):
            real_pipe = os.pipe
            opened = []

            def failing_second_pipe():
                if opened:
                    raise OSError("pipe capacity exhausted")
                pair = real_pipe()
                opened.extend(pair)
                return pair

            with patch.object(callback.os, "pipe", side_effect=failing_second_pipe):
                self.assertIsNone(callback.analysis_func(state))
            for fd in opened:
                with self.assertRaises(OSError):
                    os.fstat(fd)
            outcome = callback._last_callback_outcome
            self.assertEqual(outcome["status"], "callback_error")
            self.assertIn("pipe capacity", outcome["error"])
            self.assertTrue(outcome["worker_reaped"])
            self.assert_continues(callback, state)

    def test_worker_and_reporter_fork_failure_fail_open(self):
        with self.fault_case() as (callback, state):
            with patch.object(callback.os, "fork", side_effect=OSError("fork unavailable")):
                self.assertIsNone(callback.analysis_func(state))
            outcome = callback._last_callback_outcome
            self.assertEqual(outcome["status"], "callback_error")
            self.assertIn("fork unavailable", outcome["error"])
            self.assertIn("fork unavailable", outcome["writer_error"])
            self.assertTrue(outcome["worker_reaped"])
            self.assertTrue(outcome["writer_reaped"])
            self.assert_continues(callback, state)

    def test_fallback_error_reporter_cannot_rethrow_fork_failure(self):
        with self.fault_case() as (callback, state):
            with patch.dict(os.environ, {"LLM_CALLBACK_DEADLINE_S": "invalid"}), \
                    patch.object(callback.os, "fork", side_effect=OSError("fork unavailable")):
                self.assertIsNone(callback.analysis_func(state))
            outcome = callback._last_callback_outcome
            self.assertEqual(outcome["status"], "callback_error")
            self.assertIn("ValueError", outcome["error"])
            self.assertFalse(outcome["writer_completed"])
            self.assertIn("fork unavailable", outcome["writer_error"])
            self.assert_continues(callback, state)

    def test_invalid_socket_timeout_is_reported_without_nonfinite_context(self):
        for variable in ("LLM_CONNECT_TIMEOUT_S", "LLM_READ_TIMEOUT_S"):
            for invalid in ("nan", "inf", "0"):
                with self.subTest(variable=variable, invalid=invalid), \
                        self.fault_case() as (callback, state), \
                        patch.dict(os.environ, {variable: invalid}):
                    self.assertIsNone(callback.analysis_func(state))
                    outcome = callback._last_callback_outcome
                    self.assertEqual(outcome["status"], "callback_error")
                    self.assertIn("HTTP timeouts", outcome["error"])
                    self.assertTrue(outcome["writer_completed"])

    def test_reader_setup_failure_reaps_started_worker(self):
        with self.fault_case() as (callback, state):
            with patch.object(callback, "FrameReader", side_effect=OSError("reader setup")):
                self.assertIsNone(callback.analysis_func(state))
            outcome = callback._last_callback_outcome
            self.assertEqual(outcome["status"], "callback_error")
            self.assertIn("reader setup", outcome["error"])
            self.assertTrue(outcome["worker_reaped"])
            self.assert_continues(callback, state)

    def test_acknowledgment_failure_reaps_waiting_worker(self):
        with self.fault_case() as (callback, state):
            parent_pid = os.getpid()
            real_write = os.write

            def fail_parent_write(fd, data):
                if os.getpid() == parent_pid:
                    raise BrokenPipeError("acknowledgment failed")
                return real_write(fd, data)

            with patch.object(callback.os, "write", side_effect=fail_parent_write):
                self.assertIsNone(callback.analysis_func(state))
            outcome = callback._last_callback_outcome
            self.assertEqual(outcome["status"], "callback_error")
            self.assertIn("acknowledgment failed", outcome["error"])
            self.assertTrue(outcome["worker_reaped"])
            self.assert_continues(callback, state)

    def test_failed_result_files_still_report_error_over_pipe(self):
        with self.fault_case() as (callback, state):
            with patch.object(callback, "write_json", side_effect=PermissionError("read-only case")):
                self.assertIsNone(callback.analysis_func(state))
            outcome = callback._last_callback_outcome
            self.assertEqual(outcome["status"], "callback_error")
            self.assertIn("read-only case", outcome["error"])
            self.assertIn("read-only case", outcome["response_write_error"])
            self.assertFalse(outcome["writer_completed"])
            self.assertTrue(outcome["worker_reaped"])
            self.assert_continues(callback, state)

    def test_failed_marker_stdout_does_not_stop_caller(self):
        with self.fault_case() as (callback, state):
            with patch.object(callback, "_marker", side_effect=BrokenPipeError("stdout closed")):
                self.assertIsNone(callback.analysis_func(state))
            outcome = callback._last_callback_outcome
            self.assertEqual(outcome["status"], "callback_error")
            self.assertIn("stdout closed", outcome["error"])
            self.assertFalse(outcome["writer_completed"])
            self.assertTrue(outcome["worker_reaped"])
            self.assert_continues(callback, state)

    def test_explicit_process_interrupt_is_not_swallowed(self):
        with self.fault_case() as (callback, state):
            with patch.object(callback, "_observe", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    callback.analysis_func(state)


if __name__ == "__main__":
    unittest.main()
