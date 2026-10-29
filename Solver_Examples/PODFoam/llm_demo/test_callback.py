"""Callback tests without a solver or model."""
import importlib.util
from contextlib import contextmanager, nullcontext
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import tracemalloc
import unittest
from unittest.mock import patch

import numpy as np


SOURCE = Path(__file__).resolve().parent
# python_module.py of main at 2ed6da2, the last callback that kept every state for telemetry.jsonl,
# kept with the evidence of 2026-10-28. The tests that compare with it are skipped in a copy of the
# code without the repository's docs/; in a checkout with docs/ a missing copy is an error.
MAIN_CALLBACK = SOURCE.parents[2] / "docs/evidence/2026-10-28-callback/callback-main/python_module.py"
needs_main = unittest.skipUnless(MAIN_CALLBACK.exists() or (SOURCE.parents[2] / "docs").is_dir(),
                                 f"main's callback for the comparison is not here: {MAIN_CALLBACK}")


@contextmanager
def file_descriptor_1():
    """The lines this process and its forked children write to file descriptor 1."""
    sys.stdout.flush()
    saved = os.dup(1)
    lines = []
    with tempfile.TemporaryFile() as sink:
        os.dup2(sink.fileno(), 1)
        try:
            yield lines
        finally:
            sys.stdout.flush()
            os.dup2(saved, 1)
            os.close(saved)
            sink.seek(0)
            lines.extend(sink.read().decode("utf-8").splitlines())


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def keep_earlier_states(callback, states):
    """States of earlier steps, as analysis_func keeps them (first and last three)."""
    callback._first_state = states[0]
    callback._recent_states.extend(states)


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
                        self.assertNotIn("p_cells", callback._recent_states[-1])
                    actual_wall = time.monotonic() - callback_start
                    limit = deadline + 0.2 + 0.02 + 0.05 if step == 5 else 0.27
                    self.assertLess(actual_wall, limit)
            # closed before the folder is removed (an open file stops that on NFS)
            with np.load(case / "python_svd_audit.npz") as audit:
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
            keep_earlier_states(callback, [{**state, "time_s": step * 1e-7, "step": step}
                                           for step in range(1, 5)])
            if target == "telemetry":
                operation = callback._write_telemetry

                def delayed_telemetry(*args):
                    time.sleep(0.5)
                    operation(*args)

                callback._write_telemetry = delayed_telemetry
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
            elif target in ("parent_flush", "telemetry"):
                # since 2026-10-28 the worker writes no telemetry, so a slow disk does not
                # make the request late; the killed final write leaves no telemetry.jsonl
                self.assertEqual(outcome["status"], "disabled")
                self.assertTrue(outcome["writer_completed"])
                if target == "telemetry":
                    self.assertEqual(callback._telemetry.failed_appends, 1)
                    self.assertFalse((case / "telemetry.jsonl").exists())
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
            keep_earlier_states(callback, [{**state, "step": step, "time_s": step * 1e-7}
                                           for step in range(1, 5)])
            with patch.dict(os.environ, {"LLM_ENABLED": "0", "LLM_ANALYSIS_STEP": "5",
                                         "LLM_IMAGE_INPUT": "0", "LLM_FINAL_STEP": "10",
                                         "LLM_CALLBACK_DEADLINE_S": "0.25",
                                         "LLM_CONNECT_TIMEOUT_S": "0.1",
                                         "LLM_READ_TIMEOUT_S": "0.1"}):
                yield callback, state

    def assert_continues(self, callback, state):
        self.assertIsNone(callback.analysis_func({**state, "step": 6, "time_s": 6e-7}))
        self.assertEqual(callback._recent_states[-1]["step"], 6)

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

    def test_invalid_kill_join_allowance_fails_open(self):
        class Finished:
            def is_alive(self):
                return False

            def join(self, timeout):
                self.timeout = timeout

        for invalid in ("5", "0", "nan", "abc"):
            with self.subTest(invalid=invalid), self.fault_case() as (callback, state), \
                    patch.dict(os.environ, {"LLM_KILL_JOIN_S": invalid}):
                self.assertIsNone(callback.analysis_func(state))
                outcome = callback._last_callback_outcome
                self.assertEqual(outcome["status"], "callback_error")
                self.assertIn("LLM_KILL_JOIN_S", outcome["error"])
                # cleanup never raises; it falls back to the default allowance
                finished = Finished()
                self.assertTrue(callback._stop_process(finished))
                self.assertEqual(finished.timeout, callback._KILL_JOIN_ALLOWANCE_S)

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


def telemetry_state(step, steps):
    """A solver-like state; some steps carry NaN, infinity or non-ASCII text."""
    state = {"schema_version": 1, "time_s": 0.1 + step * 5e-6, "delta_t_s": 5e-6,
             "end_time_s": 0.1 + steps * 5e-6, "step": step, "cells": 20540,
             "residuals": {name: {"initial_first": 1e-3 / (step + k),
                                  "initial_last": 3e-5 * math.sin(step + k) ** 2,
                                  "final_last": 1e-7 * (1 + step % 7), "linear_solves": 1 + step % 6,
                                  "iterations_total": step % 23}
                           for k, name in enumerate(("Ux", "Uy", "p"))},
             "courant": {"mean": 0.017 + 1e-9 * step, "max": 0.28 + 1e-7 * step,
                         "phase": "post_step_phi"},
             "continuity": {"local": 1e-12 * step, "global": -1e-13 * step,
                            "cumulative": -3e-12 * step, "phase": "last_pressure_correction"},
             "p_cells": np.linspace(-1.0, 1.0, 20) * step, "u_cells": np.ones((20, 3)) * step}
    if step % 97 == 0:
        state["residuals"]["p"]["initial_first"] = float("nan")
    if step % 131 == 0:
        state["courant"]["max"] = float("inf")
    if step % 173 == 0:
        state["note"] = "Résidu ✓ – non-ASCII"
    return state


class TelemetryTests(unittest.TestCase):
    """telemetry.jsonl since 2026-10-28: appended in batches, with the bytes main wrote at the
    end from every state it kept."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.environment = {"LLM_ENABLED": "0", "LLM_MODE": "observe", "LLM_IMAGE_INPUT": "0",
                            "LLM_ANALYSIS_STEP": "1000000000", "LLM_RUN_ID": "telemetry-ünï-run"}

    def load(self, source, name, prepare=None):
        case = self.root / name
        case.mkdir()
        for helper in ("bounded_ipc.py", "llm_client.py", "pod_image.py"):
            shutil.copyfile(SOURCE / helper, case / helper)
        shutil.copyfile(source, case / "python_module.py")
        shutil.copyfile(SOURCE.parent / "validation/python_module.py", case / "pod_svd.py")
        load_module("pod_svd", case / "pod_svd.py")
        callback = load_module(f"telemetry_{name}", case / "python_module.py")
        if prepare:
            prepare(callback)
        return callback, case

    def drive(self, callback, states, final_step, until=None):
        with patch.dict(os.environ, dict(self.environment, LLM_FINAL_STEP=str(final_step))):
            for state in states[:until]:
                self.assertIsNone(callback.analysis_func(state))

    def main_telemetry(self, states, name="main"):
        """telemetry.jsonl as main writes it: every state kept, all written by _dump_telemetry."""
        old, case = self.load(MAIN_CALLBACK, name)
        self.drive(old, states, 0)   # LLM_FINAL_STEP=0: never final, so nothing is forked
        with patch.dict(os.environ, self.environment):   # main reads LLM_RUN_ID when it writes
            try:
                old._dump_telemetry()
            except TypeError:
                pass   # a state that cannot be encoded; main leaves the lines before it in the .tmp
        return old, case

    @needs_main
    def test_bytes_equal_main_over_many_steps_and_any_batch_size(self):
        steps = 2345
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]
        old, main_case = self.main_telemetry(states)
        expected = (main_case / "telemetry.jsonl").read_bytes()
        self.assertEqual(len(expected.splitlines()), steps)
        self.assertIn("Résidu ✓".encode(), expected)
        self.assertIn(b'"feature_status":"partial_nonfinite"', expected)
        for batch in (500, 50):
            with self.subTest(batch=batch):
                new, case = self.load(SOURCE / "python_module.py", f"new-{batch}",
                                      lambda module: setattr(module._telemetry, "BATCH_LINES", batch))
                self.drive(new, states, steps)
                self.assertEqual((case / "telemetry.jsonl").read_bytes(), expected)
                self.assertFalse((case / "telemetry.jsonl.tmp").exists())
                self.assertEqual((new._telemetry.appends, new._telemetry.failed_appends),
                                 (steps // batch + 1, 0))
                self.assertEqual(len(new._recent_states), 3)
        # what later code reads of the kept states: the residual trend and the window start
        snapshots = [np.full((20, 3), float(k)) for k in range(1, 6)]
        old._snapshots, new._snapshots = list(snapshots), list(snapshots)
        with patch.dict(os.environ, self.environment):
            summary_old = old._summarize(old._history[-1])[0]
            summary_new = new._summarize(new._recent_states[-1])[0]
        self.assertEqual(summary_new, summary_old)
        self.assertEqual(summary_new["velocity_svd"]["window_start_time_s"],
                         float(format(states[0]["time_s"], ".6g")))   # the summary keeps 6 digits
        self.assertEqual(summary_new["residuals"]["p"]["recent_initial_first"],
                         [float(format(s["residuals"]["p"]["initial_first"], ".6g")) for s in states[-3:]])

    @needs_main
    def test_telemetry_jsonl_appears_complete_at_the_last_step_only(self):
        steps = 120
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]
        _, main_case = self.main_telemetry(states)
        expected = (main_case / "telemetry.jsonl").read_bytes().splitlines(keepends=True)
        new, case = self.load(SOURCE / "python_module.py", "new",
                              lambda module: setattr(module._telemetry, "BATCH_LINES", 50))
        (case / "telemetry.jsonl.tmp").write_text("left by an earlier, longer run\n" * 400)
        self.drive(new, states, steps, until=steps - 1)
        self.assertFalse((case / "telemetry.jsonl").exists())
        self.assertEqual((case / "telemetry.jsonl.tmp").read_bytes(), b"".join(expected[:100]))
        self.drive(new, states[steps - 1:], steps)
        self.assertEqual((case / "telemetry.jsonl").read_bytes(), b"".join(expected))
        self.assertFalse((case / "telemetry.jsonl.tmp").exists())

    @needs_main
    def test_memory_stays_flat_over_a_long_run(self):
        steps = 6000
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]
        grown = {}
        for name, source in (("main", MAIN_CALLBACK), ("new", SOURCE / "python_module.py")):
            callback, case = self.load(source, name)
            self.drive(callback, states, 0, until=1000)
            tracemalloc.start()
            try:
                before = tracemalloc.get_traced_memory()[0]
                with patch.dict(os.environ, dict(self.environment, LLM_FINAL_STEP="0")):
                    for state in states[1000:]:
                        callback.analysis_func(state)
                grown[name] = tracemalloc.get_traced_memory()[0] - before
            finally:
                tracemalloc.stop()
            if name == "new":
                self.assertLessEqual(callback._telemetry.pending_lines, callback._telemetry.BATCH_LINES)
                self.assertEqual(callback._telemetry.lines, steps)
        # main kept every state (about 1.35 KiB each); the callback now keeps at most a batch of lines
        self.assertGreater(grown["main"], 4 << 20)
        self.assertLess(grown["new"], 1 << 20)

    @needs_main
    def test_a_killed_or_failed_append_is_written_again(self):
        steps = 400
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]
        _, main_case = self.main_telemetry(states)
        calls = []

        def prepare(module):
            module._telemetry.BATCH_LINES = 50
            real = module._bounded_writer

            def half_then_hang(data, offset, rename, report, done_fd, parent_fd):
                module._write_telemetry(data[:len(data) // 2], offset, False)
                time.sleep(2)   # killed at the 0.2 s deadline

            def fail(*args):
                raise OSError("disk full")

            def faulty(target, args, deadline_at):
                if target is module._telemetry_child:
                    calls.append(args[1])
                    target = {1: half_then_hang, 2: fail}.get(len(calls), target)
                return real(target, args, deadline_at)

            module._bounded_writer = faulty

        new, case = self.load(SOURCE / "python_module.py", "new", prepare)
        self.drive(new, states, steps)
        self.assertEqual((case / "telemetry.jsonl").read_bytes(),
                         (main_case / "telemetry.jsonl").read_bytes())
        self.assertFalse((case / "telemetry.jsonl.tmp").exists())
        self.assertEqual(new._telemetry.failed_appends, 2)
        # a failed append is retried after one more batch: 50 and 100 lines failed, 150 written
        self.assertEqual(calls[:4], [0, 0, 0, calls[3]])
        self.assertGreater(calls[3], 0)

    def test_appends_that_keep_failing_are_given_up_once_and_the_solver_goes_on(self):
        steps = 100
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]

        def prepare(module):
            module._telemetry.BATCH_LINES = 10
            module._telemetry.MAX_PENDING_LINES = 35

            def fail(*args):
                raise OSError("disk gone")

            module._write_telemetry = fail

        new, case = self.load(SOURCE / "python_module.py", "new", prepare)
        with file_descriptor_1() as printed:
            self.drive(new, states, steps)
        self.assertEqual(new._recent_states[-1]["step"], steps)
        # attempts at 10, 20, 30 and 40 pending lines; then the 40 lines are dropped
        self.assertEqual(new._telemetry.failed_appends, 4)
        self.assertEqual((new._telemetry.lines, new._telemetry.pending_lines), (40, 0))
        self.assertFalse((case / "telemetry.jsonl").exists())
        self.assertFalse((case / "telemetry.jsonl.tmp").exists())
        # reported once, at the step that gave up; the last step adds no second entry
        errors = [json.loads(line) for line in (case / "llm_errors.jsonl").read_text().splitlines()]
        self.assertEqual(len(errors), 1)
        self.assertIn("telemetry.jsonl will not be written", errors[0]["error"])
        self.assertEqual(errors[0]["step"], 40)
        # the last step had nothing to write or rename: no append counted, and no file named
        self.assertEqual(new._telemetry.appends, 0)
        self.assertEqual([line for line in printed if line.startswith("PYTHON LLM telemetry")],
                         ["PYTHON LLM telemetry lines=40 appends=0 failed_appends=4 file=none incomplete: "
                          "4 appends failed and 40 lines were pending; they were dropped"])

    def test_a_last_append_that_fails_is_reported_once(self):
        """The last step's append killed at its deadline, or failing: no telemetry.jsonl, one
        entry in llm_errors.jsonl with the last step, and the step held only for the two
        bounded children (the append and the report)."""
        steps = 25
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]

        def killed(module):   # the only append, at the last step, outlives its 0.2 s deadline
            real = module._write_telemetry

            def slow(data, offset, finish):
                if finish:
                    time.sleep(2)   # before the file is opened
                return real(data, offset, finish)

            module._write_telemetry = slow

        def failed(module):   # appends at steps 10 and 20, then the last one fails
            module._telemetry.BATCH_LINES = 10
            real = module._write_telemetry

            def fail(data, offset, finish):
                if finish:
                    raise OSError("disk full")
                return real(data, offset, finish)

            module._write_telemetry = fail

        cases = (
            (killed, None, 0,
             "the last append (25 lines, then the rename) did not report back before its deadline", []),
            (failed, 20, 2,
             "the last append (5 lines, then the rename) failed (the PYTHON LLM telemetry line gives the error)",
             ["PYTHON LLM telemetry lines=25 appends=2 failed_appends=1 "
              "file=telemetry.jsonl.tmp incomplete: OSError: disk full"]))
        for prepare, tmp_lines, appends, reason, telemetry_line in cases:
            with self.subTest(case=prepare.__name__):
                new, case = self.load(SOURCE / "python_module.py", prepare.__name__, prepare)
                with file_descriptor_1() as printed:
                    self.drive(new, states, steps, until=steps - 1)
                    start = time.monotonic()
                    self.drive(new, states[steps - 1:], steps)
                    last_step_s = time.monotonic() - start
                # two bounded children: 0.2 s each, plus 0.1 s each to reap a killed one
                self.assertLess(last_step_s, 0.8)
                self.assertFalse((case / "telemetry.jsonl").exists())
                tmp = case / "telemetry.jsonl.tmp"
                self.assertEqual(len(tmp.read_bytes().splitlines()) if tmp.exists() else None, tmp_lines)
                self.assertEqual((new._telemetry.appends, new._telemetry.failed_appends), (appends, 1))
                errors = [json.loads(line) for line in (case / "llm_errors.jsonl").read_text().splitlines()]
                self.assertEqual(len(errors), 1)
                self.assertEqual((errors[0]["step"], errors[0]["status"]), (steps, "callback_error"))
                self.assertEqual(errors[0]["error"],
                                 f"RuntimeError: telemetry.jsonl will not be written: {reason}")
                self.assertIn("PYTHON LLM callback failed open: " + errors[0]["error"], printed)
                self.assertEqual([line for line in printed if line.startswith("PYTHON LLM telemetry")],
                                 telemetry_line)

    @needs_main
    def test_a_state_that_cannot_be_encoded_ends_the_telemetry_as_main_did(self):
        steps = 30
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]
        states[11]["residuals"]["Ux"]["unexpected"] = {1, 2}   # a set: not JSON
        _, main_case = self.main_telemetry(states)
        new, case = self.load(SOURCE / "python_module.py", "new")
        self.drive(new, states, steps)
        # main: no telemetry.jsonl, and the .tmp holds the 11 lines before the bad one
        for folder in (main_case, case):
            self.assertFalse((folder / "telemetry.jsonl").exists())
            self.assertEqual(len((folder / "telemetry.jsonl.tmp").read_bytes().splitlines()), 11)
        self.assertEqual((case / "telemetry.jsonl.tmp").read_bytes(),
                         (main_case / "telemetry.jsonl.tmp").read_bytes())
        errors = (case / "llm_errors.jsonl").read_text().splitlines()
        self.assertEqual(len(errors), 1)
        self.assertIn("line 12 could not be encoded", errors[0])

    @needs_main
    def test_lines_are_also_appended_after_batch_seconds(self):
        steps = 30
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]
        _, main_case = self.main_telemetry(states)
        new, case = self.load(SOURCE / "python_module.py", "new",
                              lambda module: setattr(module._telemetry, "BATCH_S", 0.0))
        self.drive(new, states, steps)
        self.assertEqual((case / "telemetry.jsonl").read_bytes(),
                         (main_case / "telemetry.jsonl").read_bytes())
        self.assertEqual(new._telemetry.appends, steps + 1)   # one per step, and the last step's


if __name__ == "__main__":
    unittest.main()
