"""PythonFOAM callback based in-situ observer/logger for the llm_demo cases.

validation/python_module.py is staged next to this file as pod_svd.py and
still does the snapshot/SVD work. On top of that, at one chosen step,
analysis_func sends the step's numeric summary (and, if the solver passed
geometry and LLM_IMAGE_INPUT=1, a picture of that step's |U| and p) to the
local model and records the answer. Nothing the model returns is used by the
solver.

Modes (LLM_MODE): observe (default; numbers plus the same-step image),
describe (one image, asks for a description and the position of the extrema),
sequence (images captured at LLM_SEQUENCE_STEPS, sent together at the last of
those steps, asks how the flow changes).

LLM_IMAGE_STYLE chooses the pictures of describe and sequence requests: v1
(default) is one 640x360 PNG with |U| above p (pod_image.py), as sent on
2026-10-13 to 2026-10-20; v2 is one 1024x576 PNG per field with percent axes
(readable_image.py), every frame in llm_observation/step-NNNNNN, and the
request is built by readable_request.py exactly as in the 2026-10-22
picture-reading tests (a v2 sequence takes two or three times, each picture on
its own colour scale; a v2 describe request sends no SVD summary, so none is
computed). observe always sends the v1 picture.

LLM_ASYNC=1 makes the request asynchronous: the worker is forked and the
solver carries on. Each later step polls the worker without blocking; the
answer is recorded with the step at which it arrived. At most
LLM_ASYNC_MAX_PENDING requests are in flight (default 1). At the last step
(end_time_s from the solver, or LLM_FINAL_STEP) a pending request is waited
for until its own deadline (LLM_ASYNC_END=wait) or left running
(LLM_ASYNC_END=detach).
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
from llm_client import (DEFAULT_ENDPOINT, DEFAULT_MODEL, MODES, build_request,
                        build_sequence_request, describe_note, encode_json, redact_request,
                        request_local, write_json)


_case = Path(__file__).resolve().parent
_snapshots = []
_history = []
_attempted = False
_last_callback_outcome = None
_geometry = None
_latest_pressure = None
_latest_velocity = None
_pending = []          # asynchronous jobs still running (requests and frame renders)
_frames = []           # frames captured for the sequence mode, in step order
_sequence_sent = False
_KILL_JOIN_ALLOWANCE_S = 0.02
_SCHEDULING_TOLERANCE_S = 0.05
_RENDER_DEADLINE_S = 30.0
_FRAME_WAIT_S = 5.0


def _mode():
    mode = os.environ.get("LLM_MODE", "observe")
    if mode not in MODES:
        raise ValueError(f"LLM_MODE must be one of {MODES}")
    return mode


def _async():
    return os.environ.get("LLM_ASYNC", "0") == "1"


def _max_pending():
    value = int(os.environ.get("LLM_ASYNC_MAX_PENDING", "1"))
    if not 1 <= value <= 8:
        raise ValueError("LLM_ASYNC_MAX_PENDING must be between 1 and 8")
    return value


def _kill_join_allowance():
    """How long a killed child may take to be reaped (LLM_KILL_JOIN_S, default 0.02 s).

    Reaping a killed child takes longer the more memory it maps: about 16 ms for 200 MB
    and 38 ms for 500 MB on the MedicineBow nodes, where 0.02 s is too short for a worker
    forked from the solver.
    """
    value = float(os.environ.get("LLM_KILL_JOIN_S", _KILL_JOIN_ALLOWANCE_S))
    if not 0 < value <= 2:
        raise ValueError("LLM_KILL_JOIN_S must be in (0, 2]")
    return value


def _image_style():
    style = os.environ.get("LLM_IMAGE_STYLE", "v1")
    if style not in ("v1", "v2"):
        raise ValueError("LLM_IMAGE_STYLE must be v1 or v2")
    return style


def _keeps_svd_window():
    """Whether the request will carry the SVD summary, so its snapshot window is kept.

    Called from snapshot_func, so it must not raise.
    """
    mode = os.environ.get("LLM_MODE", "observe")
    return mode == "observe" or (mode == "describe"
                                 and os.environ.get("LLM_IMAGE_STYLE", "v1") != "v2")


def _sequence_steps():
    text = os.environ.get("LLM_SEQUENCE_STEPS", "")
    steps = sorted({int(item) for item in text.split(",") if item.strip()})
    if len(steps) < 2 or steps[0] < 1:
        raise ValueError("LLM_SEQUENCE_STEPS must list at least two positive steps")
    if len(steps) > 6:
        raise ValueError("LLM_SEQUENCE_STEPS lists more than 6 steps")
    if _image_style() == "v2":
        import readable_request
        if len(steps) > readable_request.MAX_FRAMES:
            raise ValueError("a v2 sequence takes at most 3 steps (two pictures per step)")
    return steps


def _is_final_step(state):
    override = os.environ.get("LLM_FINAL_STEP")
    if override:
        return int(state["step"]) == int(override)
    end = state.get("end_time_s")
    if end is None:
        return int(state["step"]) == 10
    return float(state["time_s"]) + 0.5 * float(state["delta_t_s"]) >= float(end)


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
        if self.pid is None:
            return False
        if self.exitcode is not None:
            return False
        try:
            finished, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            # Another SIGCHLD handler may already have reaped this child.
            self.exitcode = -1  # exit status unavailable, not a successful writer
            return False
        if finished:
            self.exitcode = os.waitstatus_to_exitcode(status)
            return False
        return True

    def kill(self):
        if self.is_alive():
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # child exited between waitpid and kill

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
    global _latest_velocity
    result = pod_svd.snapshot_func(array, rank)
    # the solver hands over its own copy, so keeping the reference is enough
    _latest_velocity = np.asarray(array)
    # The SVD summary window stops growing once the request has gone out; the
    # sequence mode and v2 describe send no summary and keep only the latest snapshot.
    if not _attempted and _keeps_svd_window():
        _snapshots.append(_latest_velocity)
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
        # SVD = Singular Value Decomposition. Keep the legacy field name:
        # leading_energy_fraction = sigma_1**2 / sum(sigma_i**2).
        # This is a dominant numeric-table pattern share (e.g. 99.997%),
        # not AI accuracy or evidence of physical stability. The component
        # matrices are uncentered and have no cell-volume/density weights,
        # so this is not a fraction of the flow's physical kinetic energy.
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
    if _latest_velocity is None:
        raise ValueError("no velocity snapshot received for this step")
    if _image_style() == "v2":
        start = time.perf_counter()
        frame, metadata = _render_v2(state, _frame_directory(state))
        return frame, dict(metadata, render_wall_s=time.perf_counter() - start), None
    if _keeps_svd_window() and len(_snapshots) != int(state["step"]):
        raise ValueError(f"snapshot count {len(_snapshots)} != step {state['step']}")
    start = time.perf_counter()
    image, metadata = pod_image.render(state, _geometry["centres"], _geometry["solution_d"],
                                       _latest_velocity, _latest_pressure,
                                       _case / "llm_observation", polygons=_geometry["polygons"],
                                       x_window=pod_image.parse_window(os.environ.get("LLM_IMAGE_XRANGE")),
                                       y_window=pod_image.parse_window(os.environ.get("LLM_IMAGE_YRANGE")))
    metadata["render_wall_s"] = time.perf_counter() - start
    return image, metadata, None


def _frame_directory(state):
    return _case / "llm_observation" / f"step-{int(state['step']):06d}"


def _frame_sentinel():
    """The file a renderer writes last; it marks a complete frame."""
    if _image_style() == "v2":
        import readable_request
        return readable_request.METADATA
    return "image-metadata.json"


def _v2_ranges():
    """Plotted range and domain extent, [[x0, x1], [y0, y1]] in metres, of v2 pictures."""
    import pod_image
    centres = _geometry["centres"]
    if pod_image.projection_axes(centres, _geometry["solution_d"]) != [0, 1]:
        raise ValueError("v2 pictures need a 2D case in the x-y plane")
    domain = [[float(centres[:, 0].min()), float(centres[:, 0].max())],
              [float(centres[:, 1].min()), float(centres[:, 1].max())]]
    x_window = pod_image.parse_window(os.environ.get("LLM_IMAGE_XRANGE"))
    y_window = pod_image.parse_window(os.environ.get("LLM_IMAGE_YRANGE"))
    return [x_window or domain[0], y_window or domain[1]], domain


def _render_v2(state, directory):
    """One v2 frame of this step (readable_request.render_frame); returns (frame, metadata)."""
    import pod_image
    import readable_request
    if _geometry is None or _geometry["polygons"] is None:
        raise ValueError("v2 pictures need one polygon per cell (a 2D case with an empty patch)")
    if not pod_image._backend["ready"]:
        raise RuntimeError(f"matplotlib is not ready: {pod_image._backend['error']}")
    plotted, domain = _v2_ranges()
    return readable_request.render_frame(
        directory, _geometry["centres"], _geometry["polygons"], _latest_velocity,
        _latest_pressure, plotted, int(state["step"]), float(state["time_s"]),
        view="full" if plotted == domain else "window", domain_extent=domain)


def _v2_frame_record(frame, metadata):
    """What llm_request.json and llm_result.json keep about a v2 frame."""
    directory = Path(frame["directory"])
    return {"style": metadata["style"], "view": metadata["view"], "directory": str(directory),
            "step": metadata["step"], "time_s": metadata["time_s"], "cells": metadata["cells"],
            "projection_axes": metadata["projection_axes"],
            "plotted_range_m": metadata["plotted_range_m"],
            "domain_extent_m": metadata["domain_extent_m"],
            "fields_npz": str(directory / metadata["fields_npz"]),
            "fields_sha256": metadata["fields_sha256"],
            "images": {image["field"]: {"path": str(directory / image["path"]),
                                        "sha256": image["sha256"], "bytes": image["bytes"],
                                        "width": image["width"], "height": image["height"],
                                        "colour_range": image["colour_range"],
                                        "colour_range_shared": image["colour_range_shared"]}
                       for image in metadata["images"]}}


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


def _marker(event, context, timestamp, **extra):
    record = {
        "event": event, "timestamp_utc": timestamp,
        "parent_pid": context["parent_pid"], "writer_pid": os.getpid(),
        "run_id": context["run_id"], "step": context["step"],
        "time_s": context["time_s"],
    }
    if context.get("async"):
        record["async"] = True
    record.update(extra)
    print("PYTHON LLM_MARKER " + encode_json(record).decode("utf-8"), flush=True)
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
        mode = context.get("mode", "observe")
        style = context.get("image_style", "v1")
        if mode == "sequence" or (mode == "describe" and style == "v2"):
            summary, summary_wall = _frame_summary(state), 0.0
        else:
            summary, summary_wall = _summarize(state)
        context["summary_wall_s"] = summary_wall
        image, image_meta, image_skip = _render_image(state)
        if image is not None and style == "v2":
            context["image_input"] = True
            context["text_input_only"] = False
            context["image_render_wall_s"] = image_meta["render_wall_s"]
            context["image"] = dict(_v2_frame_record(image, image_meta),
                                    render_wall_s=image_meta["render_wall_s"])
            summary["scope"] = "fluid PODFoam request; two same-step field pictures (v2)"
            summary["image"] = {k: image_meta[k] for k in (
                "style", "view", "time_s", "step", "cells", "projection_axes",
                "plotted_range_m", "domain_extent_m")}
        elif image is not None:
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
            if "plotted_range_m" in image_meta:
                summary["image"]["plotted_range_m"] = image_meta["plotted_range_m"]
        else:
            context["image_input"] = False
            context["text_input_only"] = True
            context["image_skipped"] = image_skip
        if mode == "observe":
            request = build_request(summary, image)
            sent_input = summary
        elif style == "v2":
            import readable_request
            if image is None:
                raise ValueError(f"{mode} mode needs an image: " + image_skip["reason"])
            model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
            if mode == "describe":
                request = readable_request.describe_v2_payload(image, model=model)
                sent_input = json.loads(request["messages"][1]["content"][0]["text"])
            else:
                collected = _collect_frames(context.get("frames", []))
                frames = [frame for frame, _ in collected] + [image]
                context["frames"] = ([_v2_frame_record(*item) for item in collected]
                                     + [_v2_frame_record(image, image_meta)])
                context["sequence_colour_range"] = "own"
                request = readable_request.sequence_v2_payload(frames, model=model, own_ranges=True)
                sent_input = {"frames": [{"step": f["step"], "time_s": f["time_s"],
                                          "image_sha256": f["image_sha256"]} for f in frames],
                              "text": [part["text"] for part in request["messages"][1]["content"]
                                       if part["type"] == "text"]}
        elif mode == "describe":
            if image is None:
                raise ValueError("describe mode needs an image: " + image_skip["reason"])
            request = build_request(summary, image, mode="describe")
            sent_input = describe_note(summary)
        else:
            if image is None:
                raise ValueError("sequence mode needs an image: " + image_skip["reason"])
            frames = _collect_frames(context.get("frames", []))
            frames.append({"path": str(image), "step": int(state["step"]),
                           "time_s": float(state["time_s"]), "sha256": image_meta["sha256"],
                           "fields_npz": image_meta["fields_npz"],
                           "fields_sha256": image_meta["fields_sha256"],
                           "projection_axes": image_meta["projection_axes"],
                           "domain_extent_m": image_meta["domain_extent_m"],
                           "plotted_range_m": image_meta.get("plotted_range_m",
                                                             image_meta["domain_extent_m"]),
                           "cells": image_meta["cells"]})
            context["frames"] = frames
            request = build_sequence_request(frames)
            sent_input = {"frames": [{k: frame[k] for k in ("step", "time_s", "sha256")}
                                     for frame in frames],
                          "text": [part["text"] for part in request["messages"][1]["content"]
                                   if part["type"] == "text"]}
        body = encode_json(request)
        (_case / "llm_request_body.json").write_bytes(body)
        request_record = {**context, "sent": False, "endpoint": endpoint,
                          "request_attempted": False,
                          "input": sent_input, "request": redact_request(request),
                          "request_bytes": len(body),
                          "request_body_file": "llm_request_body.json",
                          "request_status": "ready"}
        if mode != "observe":
            request_record["numeric_summary"] = summary
        write_json(_case / "llm_request.json", request_record)
        _send_event(events, {"event": "request_ready", "summary_wall_s": summary_wall,
                             "image_input": context["image_input"]})
        if context.get("async"):
            # nobody is waiting on the other side; stamp the request time here
            request_before_at = _stamp()
        else:
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
                raw_response_path=_case / "llm_http_response.raw", mode=mode)
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
    except Exception as error:
        # Report through the pipe even if the case directory cannot be written.
        result["response_write_error"] = f"{type(error).__name__}: {error}"
        if result["status"] in ("ok", "disabled"):
            result.update(status="callback_error", error=result["response_write_error"])
    try:
        _send_event(events, {"event": "complete", "result": result, "context": context})
    finally:
        events.close()
        os.close(ack_fd)


def _send_event(events, payload):
    """Report to the parent; a detached worker whose parent is gone carries on."""
    try:
        events.send(payload)
        return True
    except OSError:
        return False


def _frame_summary(state):
    """Minimal record for the sequence mode (no SVD window is kept)."""
    return {"schema_version": 2, "run_id": os.environ.get("LLM_RUN_ID", _case.name),
            "scope": "fluid PODFoam sequence request; frames only",
            "time_s": state["time_s"], "delta_t_s": state["delta_t_s"],
            "step": state["step"], "cells": state["cells"],
            "residuals": state["residuals"], "courant": state.get("courant"),
            "continuity": state.get("continuity")}


def _collect_frames(frames):
    """Frames captured earlier; wait briefly for a render that is still finishing.

    v1: the frame dictionaries build_sequence_request takes. v2: (frame, metadata)
    pairs, read with every hash checked.
    """
    collected = []
    sentinel = _frame_sentinel()
    for frame in frames:
        meta_path = Path(frame["directory"]) / sentinel
        deadline = time.monotonic() + _FRAME_WAIT_S
        while not meta_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not meta_path.exists():
            raise FileNotFoundError(f"frame for step {frame['step']} was not rendered in time")
        if _image_style() == "v2":
            import readable_request
            loaded, meta, _ = readable_request.load_frame(frame["directory"])
            collected.append((loaded, meta))
            continue
        meta = json.loads(meta_path.read_text())
        collected.append({"path": meta["path"], "step": meta["step"], "time_s": meta["time_s"],
                          "sha256": meta["sha256"], "fields_npz": meta["fields_npz"],
                          "fields_sha256": meta["fields_sha256"],
                          "projection_axes": meta["projection_axes"],
                          "domain_extent_m": meta["domain_extent_m"],
                          "plotted_range_m": meta.get("plotted_range_m", meta["domain_extent_m"]),
                          "cells": meta["cells"]})
    return collected


def _render_frame(state, directory):
    """Body of the forked frame renderer (sequence mode, intermediate steps)."""
    import pod_image
    if _image_style() == "v2":
        _render_v2(state, directory)
        return
    pod_image.render(state, _geometry["centres"], _geometry["solution_d"],
                     _latest_velocity, _latest_pressure, directory,
                     polygons=_geometry["polygons"],
                     x_window=pod_image.parse_window(os.environ.get("LLM_IMAGE_XRANGE")),
                     y_window=pod_image.parse_window(os.environ.get("LLM_IMAGE_YRANGE")))


def _stop_process(process, join_budget_s=None):
    """Best-effort bounded cleanup; a failed cleanup must not stop the solver."""
    if process is None:
        return True
    try:
        if join_budget_s is None:
            try:
                join_budget_s = _kill_join_allowance()
            except ValueError:   # reported by _new_context; cleanup must not raise
                join_budget_s = _KILL_JOIN_ALLOWANCE_S
        if process.is_alive():
            process.kill()
        process.join(timeout=max(0.0, join_budget_s))
        return not process.is_alive()
    except (OSError, ChildProcessError):
        return False


def _close_fd(fd):
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass


def _bounded_writer(target, args, deadline_at):
    """Best-effort child reporting, including when fork or cleanup fails.

    The parent never falls back to direct file/stdout I/O: those can block.
    """
    outcome = {"writer_completed": False, "writer_reaped": True}
    if time.monotonic() >= deadline_at:
        return outcome
    writer = _ForkProcess(target=target, args=args)
    try:
        writer.start()
        writer.join(timeout=max(0.0, deadline_at - time.monotonic()))
        outcome["writer_completed"] = not writer.is_alive() and writer.exitcode == 0
    except Exception as error:
        outcome["writer_error"] = f"{type(error).__name__}: {error}"
    finally:
        outcome["writer_reaped"] = _stop_process(writer)
    return outcome


def _write_final_report(context, result, cleanup_start):
    extra = {}
    if context.get("async"):
        extra = {"arrived_at_step": context.get("arrived_at_step"),
                 "solver_stall_s": context.get("solver_stall_s")}
    _marker("response_after", context, context["response_after_at"], **extra)
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
    line = (f"PYTHON LLM step={context['step']} time={context['time_s']:.12g} "
            f"status={result['status']} image_input={context.get('image_input')} "
            f"analysis_wait={context['callback_elapsed_s']:.6f}s")
    if context.get("async"):
        line += (f" async=1 arrived_at_step={context.get('arrived_at_step')} "
                 f"solver_stall={context.get('solver_stall_s', 0.0):.6f}s")
    print(line, flush=True)


def _new_context(state, mode, frames=None, asynchronous=False):
    deadline_s = float(os.environ.get("LLM_CALLBACK_DEADLINE_S",
                                      os.environ.get("LLM_TIMEOUT_S", "120")))
    if not 0 < deadline_s <= 300:
        raise ValueError("LLM_CALLBACK_DEADLINE_S must be in (0, 300]")
    style = _image_style()
    if style == "v2" and mode == "observe":
        raise ValueError("LLM_IMAGE_STYLE=v2 applies to describe and sequence; "
                         "observe sends the v1 picture")
    context = {
        "parent_pid": os.getpid(),
        "run_id": os.environ.get("LLM_RUN_ID", _case.name),
        "step": state["step"], "time_s": state["time_s"],
        "mode": mode, "image_style": style,
        "image_requested": _image_requested() and _geometry is not None,
        "deadline_s": deadline_s, "cleanup_budget_s": 0.2,
        "connect_timeout_s": float(os.environ.get("LLM_CONNECT_TIMEOUT_S", "2")),
        "read_timeout_s": float(os.environ.get("LLM_READ_TIMEOUT_S", "90")),
        "kill_join_allowance_s": _kill_join_allowance(),
        "scheduling_tolerance_s": _SCHEDULING_TOLERANCE_S,
    }
    if asynchronous:
        context["async"] = True
    if frames is not None:
        context["frames"] = [{"directory": frame["directory"], "step": frame["step"]}
                             for frame in frames]
    if not all(0 < context[name] <= 300 for name in
               ("connect_timeout_s", "read_timeout_s")):
        raise ValueError("HTTP timeouts must be in (0, 300]")
    context["callback_started_at"] = _stamp()
    return context


def _observe(state, start, mode="observe", frames=None):
    """Synchronous request: fork the worker and wait for it, bounded by the deadline."""
    context = _new_context(state, mode, frames)
    deadline_s = context["deadline_s"]
    result = {"status": "timeout", "timeout_kind": "callback_deadline",
              "error": "Whole analysis worker exceeded callback deadline",
              "inference_wall_s": None, "output_text": None}
    request_started = None
    worker = reader = None
    owned_fds = set()
    deadline_at = start + deadline_s
    try:
        events_read, events_write = os.pipe()
        owned_fds.update((events_read, events_write))
        ack_read, ack_write = os.pipe()
        owned_fds.update((ack_read, ack_write))
        worker = _ForkProcess(target=_analysis_worker,
                              args=(state, dict(context), FrameWriter(events_write), ack_read,
                                    (events_read, ack_write)))
        worker.start()
        for fd in (events_write, ack_read):
            os.close(fd)
            owned_fds.remove(fd)
        reader = FrameReader(events_read)
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
    except Exception as error:
        result.update(status="callback_error", timeout_kind=None,
                      error=f"{type(error).__name__}: {error}")
    finally:
        cleanup_start = time.monotonic()
        context["worker_reaped"] = _stop_process(worker)
        # Includes partial setup: second pipe, fork and reader setup can fail.
        for fd in owned_fds:
            _close_fd(fd)
    context["ipc_select_calls"] = reader.select_calls if reader is not None else 0
    context["response_after_at"] = _stamp()
    context["callback_elapsed_s"] = time.monotonic() - start
    context["elapsed_since_request_s"] = (
        time.monotonic() - request_started if request_started is not None else None)
    context["worker_wait_elapsed_s"] = cleanup_start - start
    reporting = _bounded_writer(_write_final_report, (dict(context), result, cleanup_start),
                                cleanup_start + context["cleanup_budget_s"])
    return {**context, **result, **reporting,
            "callback_actual_elapsed_s": time.monotonic() - start}


def _start_async_request(state, start, mode, frames=None):
    """Fork the worker and return at once; the answer is collected by later steps."""
    context = _new_context(state, mode, frames, asynchronous=True)
    context["request_step"] = int(state["step"])
    result = {"status": "timeout", "timeout_kind": "callback_deadline",
              "error": "Whole analysis worker exceeded callback deadline",
              "inference_wall_s": None, "output_text": None}
    job = {"kind": "request", "context": context, "result": result, "start": start,
           "deadline_at": start + context["deadline_s"], "worker": None, "reader": None,
           "owned_fds": set(), "request_started": None}
    try:
        events_read, events_write = os.pipe()
        job["owned_fds"].update((events_read, events_write))
        ack_read, ack_write = os.pipe()
        job["owned_fds"].update((ack_read, ack_write))
        job["worker"] = _ForkProcess(target=_analysis_worker,
                                     args=(state, dict(context), FrameWriter(events_write),
                                           ack_read, (events_read, ack_write)))
        job["worker"].start()
        # the asynchronous worker stamps its own request time; no acknowledgment
        for fd in (events_write, ack_read, ack_write):
            os.close(fd)
            job["owned_fds"].remove(fd)
        job["reader"] = FrameReader(events_read)
    except Exception as error:
        result.update(status="callback_error", timeout_kind=None,
                      error=f"{type(error).__name__}: {error}")
        context["solver_stall_s"] = time.monotonic() - start
        return _finalize_job(job, int(state["step"]))
    context["solver_stall_s"] = time.monotonic() - start
    _pending.append(job)
    _marker("request_started_async", context, _stamp())
    return {**context, "status": "pending"}


def _handle_message(job, message, step):
    """Apply one worker event; True when the job is complete."""
    context, result = job["context"], job["result"]
    if message.get("event") == "request_ready":
        context["summary_wall_s"] = message["summary_wall_s"]
        context["image_input"] = bool(message.get("image_input"))
        context["text_input_only"] = not context["image_input"]
        job["request_started"] = time.monotonic()
        return False
    if message.get("event") == "complete":
        job["result"] = message["result"]
        context.update(message["context"])
        context["arrived_at_step"] = step
        return True
    result.update(status="callback_error", timeout_kind=None,
                  error="Unexpected worker IPC event")
    return True


def _finalize_job(job, step):
    """Stop the worker, close the pipe, write the result files in a bounded child."""
    context, result = job["context"], job["result"]
    cleanup_start = time.monotonic()
    context["worker_reaped"] = _stop_process(job["worker"])
    for fd in job["owned_fds"]:
        _close_fd(fd)
    if job["reader"] is not None:
        _close_fd(job["reader"].fd)
        job["reader"].fd = None
    context["ipc_select_calls"] = job["reader"].select_calls if job["reader"] else 0
    context["response_after_at"] = _stamp()
    context["callback_elapsed_s"] = time.monotonic() - job["start"]
    context.setdefault("arrived_at_step", step)
    context["elapsed_since_request_s"] = (
        time.monotonic() - job["request_started"] if job["request_started"] else None)
    context["worker_wait_elapsed_s"] = cleanup_start - job["start"]
    if "end_wait_started_at" in job:
        context["end_wait_s"] = cleanup_start - job.pop("end_wait_started_at")
    reporting = _bounded_writer(_write_final_report, (dict(context), result, cleanup_start),
                                cleanup_start + context["cleanup_budget_s"])
    if job in _pending:
        _pending.remove(job)
    outcome = {**context, **result, **reporting}
    global _last_callback_outcome
    _last_callback_outcome = outcome
    return outcome


def _poll_request(job, step, block_until=None):
    """Read what the worker has sent; blocking only when block_until is given."""
    reader = job["reader"]
    while True:
        try:
            if block_until is None:
                if not reader.ready(0.0):
                    break
                message = reader.receive(time.monotonic() + 0.1)
            else:
                message = reader.receive(block_until)
        except TimeoutError:
            break
        except EOFError:
            job["result"].update(status="callback_error", timeout_kind=None,
                                 error="Analysis worker exited without a result")
            return _finalize_job(job, step)
        except ValueError as error:
            job["result"].update(status="callback_error", timeout_kind=None,
                                 error=f"Malformed worker IPC frame: {error}")
            return _finalize_job(job, step)
        if _handle_message(job, message, step):
            return _finalize_job(job, step)
    if time.monotonic() >= job["deadline_at"]:
        return _finalize_job(job, step)   # result still says timeout
    return None


def _poll_render(job, step):
    worker = job["worker"]
    if worker.is_alive() and time.monotonic() < job["deadline_at"]:
        return None
    _pending.remove(job)
    frame = job["frame"]
    meta_path = Path(frame["directory"]) / _frame_sentinel()
    if worker.is_alive() or worker.exitcode != 0 or not meta_path.exists():
        _stop_process(worker)
        frame["status"] = "render_failed"
        print(f"PYTHON LLM frame step={frame['step']} render failed", flush=True)
    else:
        frame["status"] = "rendered"
        frame["rendered_by_step"] = step
    return frame


def _poll_pending(step):
    for job in list(_pending):
        if job["kind"] == "render":
            _poll_render(job, step)
        else:
            _poll_request(job, step)


def _capture_frame(state, start):
    """Render this step's image for the sequence; asynchronous unless LLM_ASYNC=0."""
    if _geometry is None or _latest_pressure is None or _latest_velocity is None:
        raise ValueError("sequence capture needs mesh geometry, U and p")
    directory = _frame_directory(state)
    frame = {"directory": str(directory), "step": int(state["step"]),
             "time_s": float(state["time_s"]), "status": "rendering"}
    worker = _ForkProcess(target=_render_frame, args=(dict(state), directory))
    worker.start()
    job = {"kind": "render", "worker": worker, "frame": frame, "start": start,
           "deadline_at": start + _RENDER_DEADLINE_S}
    _frames.append(frame)
    if _async():
        _pending.append(job)
    else:
        worker.join(timeout=_RENDER_DEADLINE_S)
        _pending.append(job)
        _poll_render(job, int(state["step"]))
    print(f"PYTHON LLM frame step={frame['step']} capture started "
          f"async={int(_async())} wall={time.monotonic() - start:.3f}s", flush=True)


def _launch(state, start, mode, frames=None):
    global _last_callback_outcome
    if _async():
        requests_pending = sum(job["kind"] == "request" for job in _pending)
        if requests_pending >= _max_pending():
            _last_callback_outcome = {"status": "skipped_pending", "step": state["step"],
                                      "pending_requests": requests_pending}
            print(f"PYTHON LLM step={state['step']} request skipped: "
                  f"{requests_pending} request(s) still pending", flush=True)
            return
        _last_callback_outcome = _start_async_request(state, start, mode, frames)
    else:
        _last_callback_outcome = _observe(state, start, mode, frames)


def _finish_pending_at_end(step):
    """Last step: wait for pending requests up to their own deadlines, or detach."""
    policy = os.environ.get("LLM_ASYNC_END", "wait")
    for job in list(_pending):
        if job["kind"] == "render":
            job["worker"].join(timeout=max(0.0, job["deadline_at"] - time.monotonic()))
            _poll_render(job, step)
            continue
        if policy == "detach":
            if _poll_request(job, step) is not None:
                continue   # it completed just now
            job["context"]["detached_at_step"] = step
            job["result"] = {"status": "detached", "inference_wall_s": None, "output_text": None,
                             "error": "run ended while the request was pending; the worker "
                                      "keeps running and writes llm_response.json on its own"}
            _pending.remove(job)
            job["worker"] = None   # not killed
            _finalize_job(job, step)
            continue
        job["end_wait_started_at"] = time.monotonic()
        job["context"]["end_wait_started_at_step"] = step
        if _poll_request(job, step, block_until=job["deadline_at"]) is None:
            _finalize_job(job, step)


def analysis_func(state):
    """Observe/log after a step; ordinary observer errors fail open.

    KeyboardInterrupt and SystemExit are intentional process-level interrupts
    and are not swallowed. Snapshot/SVD callbacks retain their existing API.
    """
    global _attempted, _last_callback_outcome, _latest_pressure, _sequence_sent
    start = time.monotonic()
    try:
        # p_cells is the one big array; keep it out of the history
        if isinstance(state, dict):
            state = dict(state)  # never remove fields from the solver's dictionary
        pressure = state.pop("p_cells", None) if isinstance(state, dict) else None
        if pressure is not None:
            _latest_pressure = np.array(pressure, dtype=float, copy=True)
        state = copy.deepcopy(state)
        _history.append(state)
        step = int(state["step"])
        if _pending:
            _poll_pending(step)
        mode = _mode()
        if mode == "sequence":
            steps = _sequence_steps()
            if step in steps and not _sequence_sent:
                if step != steps[-1]:
                    _capture_frame(state, start)
                else:
                    _sequence_sent = True
                    _launch(state, start, mode, frames=list(_frames))
        else:
            target = int(os.environ.get("LLM_ANALYSIS_STEP", "5"))
            if not _attempted and step == target:
                # set first, so a failure is not retried at the next step
                _attempted = True
                _launch(state, start, mode)
        if _is_final_step(state):
            if _pending:
                _finish_pending_at_end(step)
            # about 0.15 s for 6000 states on a login node; scale with the history
            _bounded_writer(_dump_telemetry, (), time.monotonic() + max(0.2, 5e-5 * len(_history)))
    except Exception as error:
        _last_callback_outcome = {
            "status": "callback_error", "error": f"{type(error).__name__}: {error}"}
        reporting = _bounded_writer(_record_callback_error,
                                    (state if isinstance(state, dict) else {}, error),
                                    time.monotonic() + 0.2)
        _last_callback_outcome.update(reporting)
    return None
