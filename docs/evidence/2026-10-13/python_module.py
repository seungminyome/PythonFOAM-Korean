"""PODFoam callback module for the llm_demo cases.

validation/python_module.py is staged next to this file as pod_svd.py and
still does the snapshot/SVD work. On top of that, at one chosen step,
analysis_func sends the step's numeric summary (and, if the solver passed
geometry and LLM_IMAGE_INPUT=1, a picture of that step's |U| and p) to the
local model and records the answer. Nothing the model returns is used by the
solver.
"""
import json
import copy
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import signal
import time

import numpy as np

import pod_svd
from bounded_ipc import FrameReader, FrameWriter, read_frame_blocking
from llm_client import (DEFAULT_ENDPOINT, build_request, encode_json,
                        redact_request, request_local, write_json)


_case = Path(__file__).resolve().parent
_snapshots = []
_history = []
_attempted = False
_last_callback_outcome = None
_geometry = None
_latest_pressure = None
_KILL_JOIN_ALLOWANCE_S = 0.02
_SCHEDULING_TOLERANCE_S = 0.05


class _ForkProcess:
    """Plain fork; multiprocessing.Process would flush the parent's stdio on start.

    The child leaves through os._exit, skipping finalizers and stdio flushing.
    """
    def __init__(self, target, args):
        self.target, self.args = target, args
        self.pid = None
        self.exitcode = None

    def start(self):
        self.pid = os.fork()
        if self.pid == 0:
            try:
                self.target(*self.args)
            except BaseException:
                os._exit(1)
            os._exit(0)

    def is_alive(self):
        if self.exitcode is not None:
            return False
        finished, status = os.waitpid(self.pid, os.WNOHANG)
        if finished:
            self.exitcode = os.waitstatus_to_exitcode(status)
            return False
        return True

    def kill(self):
        if self.is_alive():
            os.kill(self.pid, signal.SIGKILL)

    def join(self, timeout):
        deadline = time.monotonic() + timeout
        while self.is_alive():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.002, remaining))


def _finite_features(value):
    """Replace non-finite floats with None and list where they were."""
    issues = []

    def visit(item, path):
        if isinstance(item, (float, np.floating)):
            if not math.isfinite(item):
                issues.append({"path": path, "status": "nonfinite",
                               "reason": "computed feature is not finite"})
                return None
            return float(item)
        if isinstance(item, dict):
            return {key: visit(child, f"{path}.{key}") for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [visit(child, f"{path}[{index}]") for index, child in enumerate(item)]
        return item

    return visit(value, "$"), issues


def mesh_func(centres, volumes, solution_d, rank, poly_points=None, poly_offsets=None,
              poly_cells=None):
    """Called once from PythonCreate.H with the mesh geometry.

    poly_* describe one polygon per cell for 2D cases (faces of the empty
    patch); without them the renderer falls back to a raster. matplotlib is
    imported here so the import does not land inside the time loop.
    """
    global _geometry
    import pod_image
    centres = np.array(centres, dtype=float, copy=True)
    volumes = np.array(volumes, dtype=float, copy=True)
    polygons = pod_image.cell_polygons(poly_points, poly_offsets, poly_cells, centres.shape[0])
    if centres.ndim != 2 or centres.shape[1] != 3 or volumes.shape != (centres.shape[0],):
        raise ValueError("mesh_func expects centres (cells,3) and volumes (cells,)")
    if not (np.isfinite(centres).all() and np.isfinite(volumes).all()):
        raise ValueError("nonfinite mesh geometry")
    backend = pod_image.prepare_backend(_case)
    _geometry = {"centres": centres, "volumes": volumes, "polygons": polygons,
                 "solution_d": [int(v) for v in solution_d], "rank": int(rank),
                 "backend": dict(backend)}
    print(f"PYTHON LLM mesh geometry received: cells={centres.shape[0]} "
          f"cell_polygons={0 if polygons is None else len(polygons['cells'])} "
          f"solution_d={_geometry['solution_d']} backend_ready={backend['ready']} "
          f"backend_import_wall_s={backend['import_wall_s']:.3f}", flush=True)
    return int(centres.shape[0])


def snapshot_func(array, rank):
    result = pod_svd.snapshot_func(array, rank)
    # the solver hands over its own copy, so keeping the reference is enough
    if not _attempted:
        _snapshots.append(np.asarray(array))
    return result


def svd_func(rank):
    return pod_svd.svd_func(rank)


def _residual_summary(state):
    answer = {}
    for name in ("Ux", "Uy", "p"):
        record = dict(state["residuals"][name])
        current = float(record["initial_first"])
        previous = (float(_history[-2]["residuals"][name]["initial_first"])
                    if len(_history) > 1 else None)
        record["initial_first_change"] = (
            current - previous if previous is not None else None)
        record["initial_first_relative_change"] = (
            (current - previous) / abs(previous)
            if previous is not None and previous != 0 else None)
        record["recent_initial_first"] = [
            item["residuals"][name]["initial_first"] for item in _history[-3:]]
        answer[name] = record
    return answer


def _summarize(state):
    start = time.perf_counter()
    window = np.stack(_snapshots, axis=2)
    components = {}
    for index, name in enumerate(("Ux", "Uy", "Uz")):
        values = np.linalg.svd(window[:, index, :], compute_uv=False)
        energy = float(np.sum(values * values))
        components[name] = {
            "singular_values_top3": values[:3].tolist(),
            "leading_energy_fraction": (float(values[0] ** 2 / energy)
                                        if energy > 0 else None),
            "zero_energy": energy == 0,
        }
    summary = {
        "schema_version": 2,
        "run_id": os.environ.get("LLM_RUN_ID", _case.name),
        "scope": "fluid PODFoam connection test; initial transient; numeric summary",
        "time_s": state["time_s"],
        "delta_t_s": state["delta_t_s"],
        "step": state["step"],
        "cells": state["cells"],
        "residual_definition": (
            "normalized linear-solver residual; not force imbalance; recent values "
            "are chronological, last is current; fixed delta_t_s separates samples"),
        "residuals": _residual_summary(state),
        "courant": state.get("courant", state.get("courants")),
        "continuity": state.get("continuity"),
        "velocity_svd": {
            "method": "uncentered; separate component matrices (cells, snapshots)",
            "mean_removed": False,
            "window_snapshots": len(_snapshots),
            "window_start_time_s": _history[0]["time_s"],
            "window_end_time_s": state["time_s"],
            "components": components,
        },
        "snapshot_values_finite": bool(np.isfinite(window).all()),
        "not_implemented": ["force_equilibrium"],
        "unavailable": {
            "force_equilibrium": {"value": None, "reason": "not computed in this demo"}
        },
    }
    for name in ("courant", "continuity"):
        if summary[name] is None:
            summary["unavailable"][name] = {
                "value": None, "reason": "not supplied by solver callback"}
    # 6 significant digits are plenty for the model; telemetry keeps full precision
    def compact(value):
        if isinstance(value, float):
            return float(format(value, ".6g"))
        if isinstance(value, dict):
            return {key: compact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [compact(item) for item in value]
        return value

    summary, issues = _finite_features(compact(summary))
    summary["feature_status"] = "partial_nonfinite" if issues else "finite"
    summary["feature_issues"] = issues
    encode_json(summary)  # raises on NaN/Infinity
    return summary, time.perf_counter() - start


def _image_requested():
    return os.environ.get("LLM_IMAGE_INPUT", "1") == "1"


def _render_image(state):
    """PNG of this step, or (None, None, reason) when there is nothing to render."""
    import pod_image
    if not _image_requested():
        return None, None, {"reason": "LLM_IMAGE_INPUT=0; numeric summary only"}
    if _geometry is None:
        return None, None, {"reason": "solver did not call mesh_func; numeric summary only"}
    if _latest_pressure is None:
        return None, None, {"reason": "solver state carried no p_cells; numeric summary only"}
    if len(_snapshots) != int(state["step"]):
        raise ValueError(f"snapshot count {len(_snapshots)} != step {state['step']}")
    start = time.perf_counter()
    image, metadata = pod_image.render(state, _geometry["centres"], _geometry["solution_d"],
                                       _snapshots[-1], _latest_pressure,
                                       _case / "llm_observation", polygons=_geometry["polygons"])
    metadata["render_wall_s"] = time.perf_counter() - start
    return image, metadata, None


def _record_callback_error(state, error):
    record = {"status": "callback_error", "step": state.get("step"),
              "time_s": state.get("time_s"),
              "error": f"{type(error).__name__}: {error}"}
    try:
        with (_case / "llm_errors.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, allow_nan=False) + "\n")
    except Exception:
        pass
    print("PYTHON LLM callback failed open: " + record["error"], flush=True)


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _marker(event, context, timestamp):
    print("PYTHON LLM_MARKER " + encode_json({
        "event": event, "timestamp_utc": timestamp,
        "parent_pid": context["parent_pid"], "writer_pid": os.getpid(),
        "run_id": context["run_id"], "step": context["step"],
        "time_s": context["time_s"],
    }).decode("utf-8"), flush=True)
    return timestamp


def _dump_telemetry():
    temporary = _case / "telemetry.jsonl.tmp"
    with temporary.open("w", encoding="utf-8") as stream:
        for state in _history:
            telemetry, issues = _finite_features(state)
            telemetry["run_id"] = os.environ.get("LLM_RUN_ID", _case.name)
            if issues:
                telemetry["feature_status"] = "partial_nonfinite"
                telemetry["feature_issues"] = issues
            stream.write(encode_json(telemetry).decode("utf-8") + "\n")
    temporary.replace(_case / "telemetry.jsonl")


def _analysis_worker(state, context, events, ack_fd, parent_only_fds):
    """Body of the forked worker: summary, image, HTTP, result files."""
    for fd in parent_only_fds:
        os.close(fd)
    response = None
    enabled = os.environ.get("LLM_ENABLED", "1") == "1"
    result = {"status": "callback_error", "output_text": None,
              "inference_wall_s": None}
    try:
        _marker("callback_start", context, context["callback_started_at"])
        _dump_telemetry()
        endpoint = os.environ.get("LLM_ENDPOINT", DEFAULT_ENDPOINT)
        safe_state, issues = _finite_features(state)
        pending = {**context, "sent": False, "endpoint": endpoint,
                   "request_attempted": False,
                   "input": None, "request": None, "request_bytes": 0,
                   "raw_state": safe_state, "raw_state_issues": issues,
                   "request_status": "summary_pending"}
        write_json(_case / "llm_request.json", pending)
        summary, summary_wall = _summarize(state)
        context["summary_wall_s"] = summary_wall
        image, image_meta, image_skip = _render_image(state)
        if image is not None:
            context["image_input"] = True
            context["text_input_only"] = False
            context["image_render_wall_s"] = image_meta["render_wall_s"]
            context["image"] = {k: image_meta[k] for k in (
                "path", "sha256", "bytes", "fields_npz", "fields_sha256", "time_s",
                "step", "cells", "width", "height", "projection_axes", "render_wall_s")}
            summary["scope"] = ("fluid PODFoam connection test; initial transient; numeric "
                                "summary plus one same-step field image")
            summary["image"] = {k: image_meta[k] for k in (
                "time_s", "step", "cells", "projection_axes", "coordinate_unit",
                "panels", "render", "ranges", "domain_extent_m")}
        else:
            context["image_input"] = False
            context["text_input_only"] = True
            context["image_skipped"] = image_skip
        request = build_request(summary, image)
        body = encode_json(request)
        (_case / "llm_request_body.json").write_bytes(body)
        request_record = {**context, "sent": False, "endpoint": endpoint,
                          "request_attempted": False,
                          "input": summary, "request": redact_request(request),
                          "request_bytes": len(body),
                          "request_body_file": "llm_request_body.json",
                          "request_status": "ready"}
        write_json(_case / "llm_request.json", request_record)
        events.send({"event": "request_ready", "summary_wall_s": summary_wall,
                     "image_input": context["image_input"]})
        # wait for the parent to stamp request_before
        acknowledgment = read_frame_blocking(ack_fd, context["deadline_s"])
        request_before_at = acknowledgment["request_before_at"]
        context["request_before_at"] = request_before_at
        _marker("request_before", context, request_before_at)
        request_record.update(request_before_at=request_before_at,
                              sent=None if enabled else False, request_attempted=enabled,
                              request_status="attempted" if enabled else "disabled")
        write_json(_case / "llm_request.json", request_record)
        if enabled:
            result, response = request_local(
                request, endpoint=endpoint, timeout_s=context["deadline_s"],
                connect_timeout_s=context["connect_timeout_s"],
                read_timeout_s=context["read_timeout_s"], isolated=False,
                raw_response_path=_case / "llm_http_response.raw")
            request_record.update(sent=result.get("request_sent", False),
                                  request_status="completed")
            write_json(_case / "llm_request.json", request_record)
        else:
            result = {"status": "disabled", "inference_wall_s": 0.0, "output_text": None}
    except BaseException as error:
        result.update(status="callback_error", error=f"{type(error).__name__}: {error}")
    try:
        write_json(_case / "llm_response.json", {
            **context, "inference_wall_s": result["inference_wall_s"],
            "api_response": response,
        })
        events.send({"event": "complete", "result": result, "context": context})
    finally:
        events.close()
        os.close(ack_fd)


def _stop_process(process, join_budget_s=_KILL_JOIN_ALLOWANCE_S):
    if process.is_alive():
        process.kill()
    process.join(timeout=max(0.0, join_budget_s))
    return not process.is_alive()


def _bounded_writer(target, args, deadline_at):
    """Run target in a child that is killed at deadline_at; the parent writes nothing itself."""
    if time.monotonic() >= deadline_at:
        return {"writer_completed": False, "writer_reaped": True}
    writer = _ForkProcess(target=target, args=args)
    writer.start()
    writer.join(timeout=max(0.0, deadline_at - time.monotonic()))
    completed = not writer.is_alive() and writer.exitcode == 0
    reaped = _stop_process(writer)
    return {"writer_completed": completed, "writer_reaped": reaped}


def _write_final_report(context, result, cleanup_start):
    _marker("response_after", context, context["response_after_at"])
    response_path = _case / "llm_response.json"
    if response_path.exists():
        response_record = json.loads(response_path.read_text())
    else:
        response_record = {"api_response": None,
                           "response_status": "not_completed_before_deadline"}
    raw_path = _case / "llm_http_response.raw"
    response_record.update(context, inference_wall_s=result.get("inference_wall_s"),
                           raw_response_file=raw_path.name if raw_path.exists() else None,
                           raw_response_bytes=raw_path.stat().st_size if raw_path.exists() else 0)
    write_json(response_path, response_record)
    context["cleanup_elapsed_before_result_write_s"] = time.monotonic() - cleanup_start
    write_json(_case / "llm_result.json", {**context, **result})
    print(f"PYTHON LLM step={context['step']} time={context['time_s']:.12g} "
          f"status={result['status']} image_input={context.get('image_input')} "
          f"analysis_wait={context['callback_elapsed_s']:.6f}s",
          flush=True)


def _observe(state, start):
    deadline_s = float(os.environ.get("LLM_CALLBACK_DEADLINE_S",
                                      os.environ.get("LLM_TIMEOUT_S", "120")))
    if not 0 < deadline_s <= 300:
        raise ValueError("LLM_CALLBACK_DEADLINE_S must be in (0, 300]")
    context = {
        "parent_pid": os.getpid(),
        "run_id": os.environ.get("LLM_RUN_ID", _case.name),
        "step": state["step"], "time_s": state["time_s"],
        "image_requested": _image_requested() and _geometry is not None,
        "deadline_s": deadline_s, "cleanup_budget_s": 0.2,
        "connect_timeout_s": float(os.environ.get("LLM_CONNECT_TIMEOUT_S", "2")),
        "read_timeout_s": float(os.environ.get("LLM_READ_TIMEOUT_S", "90")),
        "kill_join_allowance_s": _KILL_JOIN_ALLOWANCE_S,
        "scheduling_tolerance_s": _SCHEDULING_TOLERANCE_S,
    }
    context["callback_started_at"] = _stamp()
    events_read, events_write = os.pipe()
    ack_read, ack_write = os.pipe()
    worker = _ForkProcess(target=_analysis_worker,
                          args=(state, dict(context), FrameWriter(events_write), ack_read,
                                (events_read, ack_write)))
    result = {"status": "timeout", "timeout_kind": "callback_deadline",
              "error": "Whole analysis worker exceeded callback deadline",
              "inference_wall_s": None, "output_text": None}
    request_started = None
    worker.start()
    os.close(events_write)
    os.close(ack_read)
    reader = FrameReader(events_read)
    deadline_at = start + deadline_s
    try:
        while True:
            try:
                message = reader.receive(deadline_at)
            except TimeoutError:
                break
            except EOFError:
                result.update(status="callback_error", timeout_kind=None,
                              error="Analysis worker exited without a result")
                break
            except ValueError as error:
                result.update(status="callback_error", timeout_kind=None,
                              error=f"Malformed worker IPC frame: {error}")
                break
            if message.get("event") == "request_ready":
                context["summary_wall_s"] = message["summary_wall_s"]
                context["image_input"] = bool(message.get("image_input"))
                context["text_input_only"] = not context["image_input"]
                context["request_before_at"] = _stamp()
                request_started = time.monotonic()
                frame = encode_json({"request_before_at": context["request_before_at"]})
                os.write(ack_write, len(frame).to_bytes(4, "big") + frame)
            elif message.get("event") == "complete":
                result = message["result"]
                context.update(message["context"])
                break
            else:
                result.update(status="callback_error", timeout_kind=None,
                              error="Unexpected worker IPC event")
                break
    finally:
        cleanup_start = time.monotonic()
        context["worker_reaped"] = _stop_process(worker)
        reader.close()
        os.close(ack_write)
    context["ipc_select_calls"] = reader.select_calls
    context["response_after_at"] = _stamp()
    context["callback_elapsed_s"] = time.monotonic() - start
    context["elapsed_since_request_s"] = (
        time.monotonic() - request_started if request_started is not None else None)
    context["worker_wait_elapsed_s"] = cleanup_start - start
    reporting = _bounded_writer(_write_final_report, (dict(context), result, cleanup_start),
                                cleanup_start + context["cleanup_budget_s"])
    return {**context, **result, **reporting,
            "callback_actual_elapsed_s": time.monotonic() - start}


def analysis_func(state):
    """Called from PythonAnalysis.H after every completed step."""
    global _attempted, _last_callback_outcome, _latest_pressure
    start = time.monotonic()
    try:
        # p_cells is the one big array; keep it out of the history
        pressure = state.pop("p_cells", None) if isinstance(state, dict) else None
        if pressure is not None:
            _latest_pressure = np.array(pressure, dtype=float, copy=True)
        state = copy.deepcopy(state)
        _history.append(state)
        target = int(os.environ.get("LLM_ANALYSIS_STEP", "5"))
        if _attempted or int(state["step"]) != target:
            if int(state["step"]) == int(os.environ.get("LLM_FINAL_STEP", "10")):
                _bounded_writer(_dump_telemetry, (), start + 0.2)
            return None
        # set first, so a failure is not retried at the next step
        _attempted = True
        _last_callback_outcome = _observe(state, start)
    except Exception as error:
        _last_callback_outcome = {
            "status": "callback_error", "error": f"{type(error).__name__}: {error}"}
        _bounded_writer(_record_callback_error,
                        (state if isinstance(state, dict) else {}, error),
                        time.monotonic() + 0.2)
    return None
