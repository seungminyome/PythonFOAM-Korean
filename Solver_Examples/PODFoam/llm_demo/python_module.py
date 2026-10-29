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
computed). v2 requests always send max_tokens 320, seed 20261021 and
cache_prompt false, as tested; LLM_MAX_TOKENS must then be unset or 320. A v2
frame folder is never overwritten: rerunning in a case folder that already
holds llm_observation/step-NNNNNN from an earlier run is refused rather than
sending that earlier picture. observe always sends the v1 picture.

v2 pictures of a 3D case (2026-10-28) show a plane slice: the solver cuts the
mesh with the plane z = LLM_SLICE_Z (default the middle of the z range, moved
off mesh points) and passes one polygon per cut cell. The v2 frame then holds
the slice cells only (centres, U, p, polygons and their mesh cells) and its
metadata records the slice ("slice": z, number of cells); the request is built
as for 2D.

LLM_ANALYSIS_EVERY=N (2026-10-27; describe with v2 pictures only) sends a
describe request at LLM_ANALYSIS_STEP and every N steps after it, as long as
fewer than LLM_ASYNC_MAX_PENDING requests are pending (otherwise that step is
skipped and recorded). Each request writes its own files in
llm_requests/step-NNNNNN/ (the same names as a single request writes in the
case folder) and the last step writes llm_requests/index.json.

LLM_ASYNC=1 makes the request asynchronous: the worker is forked and the
solver carries on. Each later step polls the worker without blocking; the
answer is recorded with the step at which it arrived. At most
LLM_ASYNC_MAX_PENDING requests are in flight (default 1). At the last step
(end_time_s from the solver, or LLM_FINAL_STEP) a pending request is waited
for until its own deadline (LLM_ASYNC_END=wait) or left running
(LLM_ASYNC_END=detach).

telemetry.jsonl (2026-10-28): each step's line is encoded when the step arrives
and appended to telemetry.jsonl.tmp by a forked child with a deadline, 500
lines (or 60 s) at a time; the last step appends the rest and renames the file
to telemetry.jsonl. Only the first state and the last three are kept (the SVD
summary's window start and residual trend), so neither the memory nor the last
step's write grows with the run. The file's bytes are those of the earlier
writer, which kept every state until the last step. telemetry.jsonl exists only
complete; when the telemetry cannot be completed (also when the last append
fails), llm_errors.jsonl says why.

Computed trends (2026-10-28, v2 sequences): the three trend words of the
picture tests' answer key, computed from the frames' arrays inside the plotted
range, go to llm_result.json as computed_trends (never into the request), and
computed_trends_agreement compares them with the model's words when it
answered. LLM_SEQUENCE_PROMPT=t states the key's thresholds in the prompt, tn
also gives each time's largest |U| and lowest p in the note (the -t and -tn
forms of the 2026-10-27 trend test); the default (own) sends the 2026-10-22
request byte for byte.
"""
import collections
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
_first_state = None    # the first step's state: the SVD summary's window starts at its time
_recent_states = collections.deque(maxlen=3)   # the last three states, for the residual trend
_attempted = False
_last_callback_outcome = None
_geometry = None
_latest_pressure = None
_latest_velocity = None
_pending = []          # asynchronous jobs still running (requests and frame renders)
_frames = []           # frames captured for the sequence mode, in step order
_sequence_sent = False
_request_log = []      # periodic mode (LLM_ANALYSIS_EVERY): one entry per request step
_periodic_refused = False
_KILL_JOIN_ALLOWANCE_S = 0.1
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
    """How long a killed child may take to be reaped (LLM_KILL_JOIN_S, default 0.1 s).

    Reaping a killed child takes longer the more memory it maps: about 16 ms for 200 MB
    and 38 ms for 500 MB on the MedicineBow nodes, where the earlier default of 0.02 s was
    too short for a worker forked from the solver. The allowance is spent only when a
    worker is killed, inside the 0.2 s cleanup budget of the deadline.
    """
    try:
        value = float(os.environ.get("LLM_KILL_JOIN_S", _KILL_JOIN_ALLOWANCE_S))
    except ValueError:
        raise ValueError("LLM_KILL_JOIN_S must be a number in (0, 2]") from None
    if not 0 < value <= 2:
        raise ValueError("LLM_KILL_JOIN_S must be in (0, 2]")
    return value


def _image_style():
    style = os.environ.get("LLM_IMAGE_STYLE", "v1")
    if style not in ("v1", "v2"):
        raise ValueError("LLM_IMAGE_STYLE must be v1 or v2")
    return style


def _periodic_every():
    """LLM_ANALYSIS_EVERY: steps between describe requests, or None (one request)."""
    value = os.environ.get("LLM_ANALYSIS_EVERY")
    if value is None:
        return None
    every = int(value)
    if every < 1:
        raise ValueError("LLM_ANALYSIS_EVERY must be a positive integer")
    if _mode() != "describe" or _image_style() != "v2":
        raise ValueError("LLM_ANALYSIS_EVERY needs LLM_MODE=describe and LLM_IMAGE_STYLE=v2")
    return every


def _record_dir(context):
    """Where a request's files go: the case folder, or its own folder in periodic mode."""
    return Path(context.get("record_dir", _case))


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


def _sequence_prompt():
    """LLM_SEQUENCE_PROMPT of a v2 sequence: own (default, the 2026-10-22 request), t (the
    answer key's thresholds stated in the prompt) or tn (also each time's largest |U| and
    lowest p inside the plotted range in the note)."""
    value = os.environ.get("LLM_SEQUENCE_PROMPT", "own")
    if value not in ("own", "t", "tn"):
        raise ValueError("LLM_SEQUENCE_PROMPT must be own, t or tn")
    if value != "own" and _image_style() != "v2":
        raise ValueError("LLM_SEQUENCE_PROMPT=t or tn needs LLM_IMAGE_STYLE=v2")
    return value


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
              poly_cells=None, slice_plane=None):
    """Called once from PythonCreate.H with the mesh geometry.

    poly_* describe one polygon per cell for 2D cases (faces of the empty
    patch); without them the renderer falls back to a raster. For a 3D case
    the solver passes slice_plane, and poly_* are then the polygons of that
    plane slice, one per cut cell (pod_image.plane_slice): v2 pictures show the
    slice cells only, v1 pictures keep the raster of all cells. matplotlib is
    imported here so the import does not land inside the time loop.
    """
    global _geometry
    import pod_image
    centres = np.array(centres, dtype=float, copy=True)
    volumes = np.array(volumes, dtype=float, copy=True)
    polygons = (pod_image.cell_polygons(poly_points, poly_offsets, poly_cells, centres.shape[0])
                if slice_plane is None else None)
    if centres.ndim != 2 or centres.shape[1] != 3 or volumes.shape != (centres.shape[0],):
        raise ValueError("mesh_func expects centres (cells,3) and volumes (cells,)")
    if not (np.isfinite(centres).all() and np.isfinite(volumes).all()):
        raise ValueError("nonfinite mesh geometry")
    plane = None
    if slice_plane is not None:
        try:
            plane = pod_image.plane_slice(poly_points, poly_offsets, poly_cells, centres, slice_plane)
        except ValueError as error:
            # polygons that fail the checks refuse v2 pictures only; v1 keeps its raster
            unusable = {k: v for k, v in dict(slice_plane).items() if k != "normal"}
            plane = pod_image.plane_slice(None, None, None, centres,
                                          dict(unusable, z_m=None, error=f"slice polygons rejected: {error}"))
    backend = pod_image.prepare_backend(_case)
    _geometry = {"centres": centres, "volumes": volumes, "polygons": polygons,
                 "solution_d": [int(v) for v in solution_d], "rank": int(rank),
                 "backend": dict(backend)}
    if plane is not None:
        _geometry["slice"] = plane
    line = (f"PYTHON LLM mesh geometry received: cells={centres.shape[0]} "
            f"cell_polygons={0 if polygons is None else len(polygons['cells'])} ")
    if plane is not None:
        line += (f"slice_cells={plane['record']['cells']} slice_z_m={plane['record']['z_m']} "
                 + (f"slice_unusable={plane['reason']!r} " if plane["reason"] else ""))
    print(line + f"solution_d={_geometry['solution_d']} backend_ready={backend['ready']} "
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
    recent = list(_recent_states)   # the last is this step's state
    for name in ("Ux", "Uy", "p"):
        record = dict(state["residuals"][name])
        current = float(record["initial_first"])
        previous = (float(recent[-2]["residuals"][name]["initial_first"])
                    if len(recent) > 1 else None)
        record["initial_first_change"] = (
            current - previous if previous is not None else None)
        record["initial_first_relative_change"] = (
            (current - previous) / abs(previous)
            if previous is not None and previous != 0 else None)
        record["recent_initial_first"] = [
            item["residuals"][name]["initial_first"] for item in recent[-3:]]
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
            "window_start_time_s": _first_state["time_s"],
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
        if _frame_directory(state).exists():
            raise FileExistsError(f"{_frame_directory(state)} holds a frame of an earlier run "
                                  "in this case folder")
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
    """Plotted range and domain extent, [[x0, x1], [y0, y1]] in metres, of v2 pictures.

    For a 3D case the domain is that of the slice cells (the slice lies in x-y).
    """
    import pod_image
    plane = _geometry.get("slice")
    if plane is not None:
        centres = plane["centres"]
    else:
        centres = _geometry["centres"]
        if pod_image.projection_axes(centres, _geometry["solution_d"]) != [0, 1]:
            raise ValueError("v2 pictures need a 2D case in the x-y plane")
    domain = [[float(centres[:, 0].min()), float(centres[:, 0].max())],
              [float(centres[:, 1].min()), float(centres[:, 1].max())]]
    x_window = pod_image.parse_window(os.environ.get("LLM_IMAGE_XRANGE"))
    y_window = pod_image.parse_window(os.environ.get("LLM_IMAGE_YRANGE"))
    return [x_window or domain[0], y_window or domain[1]], domain


def _render_v2(state, directory):
    """One v2 frame of this step (readable_request.render_frame); returns (frame, metadata).

    A 3D case draws its plane slice: the frame holds the slice cells only (their
    centres, U, p and polygons) and its metadata says where the slice is.
    """
    import pod_image
    import readable_request
    plane = None if _geometry is None else _geometry.get("slice")
    if plane is not None and plane["reason"]:
        raise ValueError("v2 pictures of a 3D case need a plane slice: " + plane["reason"])
    if plane is None and (_geometry is None or _geometry["polygons"] is None):
        raise ValueError("v2 pictures need one polygon per cell (a 2D case with an empty patch)")
    if not pod_image._backend["ready"]:
        raise RuntimeError(f"matplotlib is not ready: {pod_image._backend['error']}")
    plotted, domain = _v2_ranges()
    view = "full" if plotted == domain else "window"
    if plane is None:
        return readable_request.render_frame(
            directory, _geometry["centres"], _geometry["polygons"], _latest_velocity,
            _latest_pressure, plotted, int(state["step"]), float(state["time_s"]),
            view=view, domain_extent=domain)
    cells = _geometry["centres"].shape[0]
    if _latest_velocity.shape != (cells, 3) or _latest_pressure.shape != (cells,):
        raise ValueError(f"U {_latest_velocity.shape} and p {_latest_pressure.shape} are not "
                         f"the {cells} cells of the mesh")
    rows = plane["mesh_cells"]
    return readable_request.render_frame(
        directory, plane["centres"], plane["polygons"], _latest_velocity[rows],
        _latest_pressure[rows], plotted, int(state["step"]), float(state["time_s"]),
        view=view, domain_extent=domain,
        plane_slice={"record": plane["record"], "mesh_cells": rows})


def _v2_frame_record(frame, metadata):
    """What llm_request.json and llm_result.json keep about a v2 frame."""
    directory = Path(frame["directory"])
    record = {"style": metadata["style"], "view": metadata["view"], "directory": str(directory),
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
    if "slice" in metadata:
        record["slice"] = metadata["slice"]
    return record


# The answer key of the picture tests, for the frames of a v2 sequence. The case folder
# has only the callback's modules, so the rules are repeated here from snapshot_runner.py
# (TREND_TOLERANCE, REGION_TOLERANCE_PCT, trend, sequence_truth, score_sequence) and
# picture_test.py (truth_from_arrays); test_async.ComputedTrendTests checks that both
# give the same result.
TREND_TOLERANCE = 0.02        # relative change of the first and last value below this: roughly_constant
REGION_TOLERANCE_PCT = 5.0    # fastest cell moving at most this (percent of the plotted range): same_place


def _frame_extrema(centres, velocity, pressure, plotted, step, time_s):
    """Largest |U|, lowest p and the fastest cell's place, among the cells whose centres lie in
    the plotted range [[x0, x1], [y0, y1]] (picture_test.truth_from_arrays)."""
    (x0, x1), (y0, y1) = plotted
    x, y = centres[:, 0], centres[:, 1]
    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    speed = np.linalg.norm(velocity, axis=1)
    index = np.flatnonzero(inside)
    fastest = index[np.argmax(speed[index])]
    return {"step": int(step), "time_s": float(time_s),
            "max_speed_m_per_s": float(speed[index].max()),
            "min_pressure_m2_per_s2": float(pressure[index].min()),
            "fastest_flow_percent": [float(100.0 * (x[fastest] - x0) / (x1 - x0)),
                                     float(100.0 * (y[fastest] - y0) / (y1 - y0))]}


def _sequence_extrema(directories):
    """_frame_extrema of each v2 frame folder, from its arrays (every hash checked)."""
    import readable_request
    out = []
    for directory in directories:
        _, meta, fields = readable_request.load_frame(directory)
        plotted = [meta["plotted_range_m"]["x"], meta["plotted_range_m"]["y"]]
        out.append(_frame_extrema(fields["centres"], fields["U"], fields["p"], plotted,
                                  meta["step"], meta["time_s"]))
    return out


def _trend(first, last, tolerance=TREND_TOLERANCE):
    scale = max(abs(first), abs(last), 1e-300)
    change = (last - first) / scale
    if change > tolerance:
        return "increasing", change
    if change < -tolerance:
        return "decreasing", change
    return "roughly_constant", change


def _sequence_trends(extrema):
    """The three trend words from the first and last time (snapshot_runner.sequence_truth)."""
    first, last = extrema[0], extrema[-1]
    speed_trend, speed_change = _trend(first["max_speed_m_per_s"], last["max_speed_m_per_s"])
    pressure_word, pressure_change = _trend(first["min_pressure_m2_per_s2"],
                                            last["min_pressure_m2_per_s2"])
    # for the pressure minimum the vocabulary is about the sign direction
    pressure_trend = {"increasing": "less_negative", "decreasing": "more_negative",
                      "roughly_constant": "roughly_constant"}[pressure_word]
    if first["min_pressure_m2_per_s2"] >= 0 and last["min_pressure_m2_per_s2"] >= 0:
        pressure_trend = "roughly_constant" if pressure_word == "roughly_constant" else (
            "more_negative" if pressure_word == "decreasing" else "less_negative")
    moved = math.hypot(last["fastest_flow_percent"][0] - first["fastest_flow_percent"][0],
                       last["fastest_flow_percent"][1] - first["fastest_flow_percent"][1])
    return {"max_speed_trend": speed_trend, "max_speed_relative_change": speed_change,
            "max_speed_first_last": [first["max_speed_m_per_s"], last["max_speed_m_per_s"]],
            "min_pressure_trend": pressure_trend, "min_pressure_relative_change": pressure_change,
            "min_pressure_first_last": [first["min_pressure_m2_per_s2"], last["min_pressure_m2_per_s2"]],
            "fastest_flow_region": "same_place" if moved <= REGION_TOLERANCE_PCT else "moves",
            "fastest_flow_moved_percent": moved,
            "tolerances": {"relative_change": TREND_TOLERANCE, "region_percent": REGION_TOLERANCE_PCT},
            "frames": [{key: item[key] for key in ("step", "time_s", "max_speed_m_per_s",
                                                   "min_pressure_m2_per_s2", "fastest_flow_percent")}
                       for item in extrema]}


def _trend_agreement(structured, computed):
    """The model's trend words against the computed ones (snapshot_runner.score_sequence)."""
    out = {}
    for name in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region"):
        out[name] = {"answer": structured[name], "truth": computed[name],
                     "match": structured[name] == computed[name],
                     "cannot_tell": structured[name] == "cannot_tell"}
    out["matches"] = sum(v["match"] for v in out.values() if isinstance(v, dict))
    return out


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


def _write_request_index():
    """llm_requests/index.json of the periodic mode (LLM_ANALYSIS_EVERY), once it has entries."""
    if _request_log:
        write_json(_case / "llm_requests" / "index.json",
                   {"every": _periodic_every(), "requests": list(_request_log)})


def _write_telemetry(data, offset, finish):
    """Write data at offset in telemetry.jsonl.tmp; with finish, end the file there and
    rename it to telemetry.jsonl. The first append (offset 0) empties a file left by an
    earlier run. Runs in a forked child."""
    temporary = _case / "telemetry.jsonl.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if offset == 0 else 0), 0o666)
    try:
        if os.fstat(fd).st_size < offset:
            raise OSError(f"{temporary.name} holds fewer than the {offset} bytes appended before")
        view = memoryview(data)
        while view:
            done = os.pwrite(fd, view, offset)
            view, offset = view[done:], offset + done
        if finish:
            os.ftruncate(fd, offset)
    finally:
        os.close(fd)
    if finish:
        temporary.replace(_case / "telemetry.jsonl")


def _telemetry_child(data, offset, rename, report, done_fd, parent_fd):
    """Body of the telemetry child. Writes one status byte to done_fd as soon as the lines
    are written: 1 when they were (and, with rename, telemetry.jsonl is in place), 0 when
    the write failed. report (the last step only): then write the request index and print
    a line that names the file holding the telemetry (telemetry.jsonl when complete, else
    telemetry.jsonl.tmp, or none when neither exists) and why it is incomplete."""
    os.close(parent_fd)
    status, problem = 0, None
    try:
        if data or rename:
            _write_telemetry(data, offset, rename)
        status = 1
    except Exception as error:
        problem = f"{type(error).__name__}: {error}"
    # before the request index, so a slow index write cannot make written lines look failed
    os.write(done_fd, bytes([status]))
    if report is not None:
        try:
            _write_request_index()
        except Exception:
            pass
        problem = report["problem"] or problem   # rename is False exactly when report["problem"] is set
        if problem:
            left = "telemetry.jsonl.tmp" if (_case / "telemetry.jsonl.tmp").exists() else "none"
            where = f"file={left} incomplete: {problem}"
        else:
            where = "file=telemetry.jsonl"
        # a last step with nothing to write or rename is not an append
        print(f"PYTHON LLM telemetry lines={report['lines']} "
              f"appends={report['appends'] + (status and bool(data or rename))} "
              f"failed_appends={report['failed_appends'] + (not status)} {where}", flush=True)


def _bounded_child_status(target, args, deadline_at):
    """_bounded_writer that returns the byte the child wrote to a pipe, or None.

    The byte also arrives when another SIGCHLD handler has reaped the child, in which
    case the exit status alone would make a child that finished look failed."""
    read_fd = write_fd = None
    try:
        read_fd, write_fd = os.pipe()
        _bounded_writer(target, tuple(args) + (write_fd, read_fd), deadline_at)
        os.close(write_fd)
        write_fd = None
        os.set_blocking(read_fd, False)
        try:
            data = os.read(read_fd, 1)
        except BlockingIOError:
            return None   # a child that was not reaped still holds the pipe
        return data[0] if data else None
    except OSError:
        return None
    finally:
        _close_fd(read_fd)
        _close_fd(write_fd)


class _Telemetry:
    """telemetry.jsonl without keeping the states (2026-10-28).

    Each step's line is encoded when the step arrives, byte for byte the line the
    earlier writer made from its history of all states at the last step, and kept
    until a forked child with a deadline appends the pending lines to
    telemetry.jsonl.tmp: every BATCH_LINES lines or BATCH_S seconds. The last step
    appends the rest and renames the file, so telemetry.jsonl is complete or absent:
    no telemetry.jsonl after the last step, or a telemetry.jsonl.tmp left after a run,
    means the telemetry did not complete (verify_async.py and verify_demo.py check
    both). Lines count as written only when the child says so through a pipe;
    otherwise they stay pending and the next child writes them again at the same
    offset, so a killed or failed append leaves no gap and no partial line in the
    finished file. A retry waits for another batch. With appends failing and more
    than MAX_PENDING_LINES pending, the lines are dropped and telemetry.jsonl is not
    written; that, a state that cannot be encoded and a last append that fails are
    reported once in llm_errors.jsonl. A run that stops before its last step leaves
    only the .tmp and reports nothing. Nothing here raises into the solver.
    """
    BATCH_LINES = 500
    BATCH_S = 60.0
    MAX_PENDING_LINES = 10_000

    def __init__(self):
        self.pending = bytearray()   # encoded lines not yet known to be on disk
        self.pending_lines = 0
        self.written = 0             # bytes of telemetry.jsonl.tmp that hold appended lines
        self.lines = 0               # lines encoded
        self.appends = 0             # appends the child reported done
        self.failed_appends = 0
        self.failed_streak = 0
        self.last_attempt = time.monotonic()
        self.problem = None          # why telemetry.jsonl will not be written
        self.finished = False

    def add(self, state):
        if self.finished or self.problem:
            return
        try:
            telemetry, issues = _finite_features(state)
            telemetry["run_id"] = os.environ.get("LLM_RUN_ID", _case.name)
            if issues:
                telemetry["feature_status"] = "partial_nonfinite"
                telemetry["feature_issues"] = issues
            line = encode_json(telemetry) + b"\n"
        except Exception as error:
            self.problem = (f"line {self.lines + 1} could not be encoded ({type(error).__name__}: "
                            f"{error}); telemetry.jsonl.tmp keeps the lines before it")
            return
        self.pending += line
        self.pending_lines += 1
        self.lines += 1

    def due(self):
        return self.pending_lines > 0 and (
            self.pending_lines >= self.BATCH_LINES * (1 + self.failed_streak)
            or time.monotonic() - self.last_attempt >= self.BATCH_S)

    def append(self, finish=False):
        """Append the pending lines in a bounded child; at the last step also rename the
        file and write the request index. The budget scales with the pending lines only.
        Returns the child's status byte (1: written, and renamed at the last step; 0: the
        write failed), or None when the child did not report back before its deadline."""
        self.last_attempt = time.monotonic()
        rename = finish and self.problem is None
        report = None
        if finish:
            report = {"lines": self.lines, "appends": self.appends,
                      "failed_appends": self.failed_appends, "problem": self.problem}
        status = _bounded_child_status(
            _telemetry_child, (self.pending, self.written, rename, report),
            self.last_attempt + max(0.2, 1e-4 * self.pending_lines))
        if status is not None and status & 1:
            if self.pending or rename:   # a last step with nothing to write or rename is no append
                self.appends += 1
            self.written += len(self.pending)
            self.pending = bytearray()
            self.pending_lines = 0
            self.failed_streak = 0
        else:
            self.failed_appends += 1
            self.failed_streak += 1
            if self.pending_lines > self.MAX_PENDING_LINES and not self.problem:
                self.problem = (f"{self.failed_appends} appends failed and {self.pending_lines} "
                                "lines were pending; they were dropped")
                self.pending = bytearray()
                self.pending_lines = 0
        if finish:
            self.finished = True
        return status

    def step(self, state):
        """This step's line, and an append when one is due; never raises."""
        known = self.problem
        try:
            self.add(state)
            if not self.finished and self.due():
                self.append()
        except Exception as error:   # a fault here must not cost the step its request
            self.problem = self.problem or f"{type(error).__name__}: {error}"
        if self.problem and not known:
            _report_telemetry_problem(state, self.problem)

    def finish(self, state):
        """The last step: the rest of the lines, telemetry.jsonl, the request index; never
        raises. A last append that fails is reported once in llm_errors.jsonl (with this
        step), as the problems of earlier steps are; one known before is not repeated."""
        if self.finished:
            return
        known = self.problem
        lines = self.pending_lines
        try:
            status = self.append(finish=True)
            if not (status is not None and status & 1) and self.problem is None:
                self.problem = (f"the last append ({lines} lines, then the rename) "
                                + ("failed (the PYTHON LLM telemetry line gives the error)"
                                   if status is not None else "did not report back before its deadline"))
        except Exception as error:
            self.problem = self.problem or f"{type(error).__name__}: {error}"
        self.finished = True
        if self.problem and not known:
            _report_telemetry_problem(state, self.problem)


def _report_telemetry_problem(state, problem):
    _bounded_writer(_record_callback_error,
                    (state if isinstance(state, dict) else {},
                     RuntimeError(f"telemetry.jsonl will not be written: {problem}")),
                    time.monotonic() + 0.2)


_telemetry = _Telemetry()


def _keep(state):
    """What later code needs of a state (the first one, the last three) and its telemetry line."""
    global _first_state
    if _first_state is None:
        _first_state = state
    _recent_states.append(state)
    _telemetry.step(state)


def _analysis_worker(state, context, events, ack_fd, parent_only_fds):
    """Body of the forked worker: summary, image, HTTP, result files."""
    for fd in parent_only_fds:
        os.close(fd)
    response = None
    enabled = os.environ.get("LLM_ENABLED", "1") == "1"
    result = {"status": "callback_error", "output_text": None,
              "inference_wall_s": None}
    trends = {}   # v2 sequence: the answer key of its frames, recorded but never sent
    try:
        _marker("callback_start", context, context["callback_started_at"])
        # telemetry.jsonl is the parent's (_Telemetry); the worker writes only the index
        _write_request_index()
        endpoint = os.environ.get("LLM_ENDPOINT", DEFAULT_ENDPOINT)
        safe_state, issues = _finite_features(state)
        pending = {**context, "sent": False, "endpoint": endpoint,
                   "request_attempted": False,
                   "input": None, "request": None, "request_bytes": 0,
                   "raw_state": safe_state, "raw_state_issues": issues,
                   "request_status": "summary_pending"}
        rec = _record_dir(context)
        rec.mkdir(parents=True, exist_ok=True)
        write_json(rec / "llm_request.json", pending)
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
            if "slice" in image_meta:
                summary["image"]["slice"] = image_meta["slice"]
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
                prompt = context.get("sequence_prompt", "own")
                extrema = None
                try:
                    extrema = _sequence_extrema([frame["directory"] for frame in frames])
                    trends = {"computed_trends": _sequence_trends(extrema)}
                except Exception as error:
                    if prompt == "tn":
                        raise   # the note needs the numbers
                    trends = {"computed_trends": None,
                              "computed_trends_error": f"{type(error).__name__}: {error}"}
                options = {"own": {}, "t": {"thresholds": True},
                           "tn": {"thresholds": True, "numbers": extrema}}[prompt]
                request = readable_request.sequence_v2_payload(frames, model=model, own_ranges=True,
                                                               **options)
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
        (rec / "llm_request_body.json").write_bytes(body)
        request_record = {**context, "sent": False, "endpoint": endpoint,
                          "request_attempted": False,
                          "input": sent_input, "request": redact_request(request),
                          "request_bytes": len(body),
                          "request_body_file": "llm_request_body.json",
                          "request_status": "ready"}
        if mode != "observe":
            request_record["numeric_summary"] = summary
        write_json(rec / "llm_request.json", request_record)
        # after llm_request.json, so the answer key is not in the request's record; sent to
        # the parent now, so a request that times out still records it
        context.update(trends)
        _send_event(events, {"event": "request_ready", "summary_wall_s": summary_wall,
                             "image_input": context["image_input"], **trends})
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
        write_json(rec / "llm_request.json", request_record)
        if enabled:
            result, response = request_local(
                request, endpoint=endpoint, timeout_s=context["deadline_s"],
                connect_timeout_s=context["connect_timeout_s"],
                read_timeout_s=context["read_timeout_s"], isolated=False,
                raw_response_path=rec / "llm_http_response.raw", mode=mode)
            request_record.update(sent=result.get("request_sent", False),
                                  request_status="completed")
            write_json(rec / "llm_request.json", request_record)
        else:
            result = {"status": "disabled", "inference_wall_s": 0.0, "output_text": None}
        if trends.get("computed_trends") and result.get("status") == "ok":
            result["computed_trends_agreement"] = _trend_agreement(
                result["structured_output"], trends["computed_trends"])
    except BaseException as error:
        result.update(status="callback_error", error=f"{type(error).__name__}: {error}")
    try:
        write_json(_record_dir(context) / "llm_response.json", {
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


def _keep_computed_trends(context, message):
    """A v2 sequence's answer key from the worker's request_ready event."""
    for key in ("computed_trends", "computed_trends_error"):
        if key in message:
            context[key] = message[key]


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
        if _image_style() == "v2" and frame.get("status") == "render_failed":
            raise ValueError(f"frame for step {frame['step']} was not rendered by this run")
        meta_path = Path(frame["directory"]) / sentinel
        deadline = time.monotonic() + _FRAME_WAIT_S
        while not meta_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not meta_path.exists():
            raise FileNotFoundError(f"frame for step {frame['step']} was not rendered in time")
        if _image_style() == "v2":
            import readable_request
            loaded, meta, _ = readable_request.load_frame(frame["directory"])
            if meta["step"] != frame["step"] or meta["time_s"] != frame.get("time_s", meta["time_s"]):
                raise ValueError(f"{frame['directory']} holds a frame of another run "
                                 f"(t = {meta['time_s']}, expected {frame.get('time_s')})")
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
    rec = _record_dir(context)
    rec.mkdir(parents=True, exist_ok=True)
    response_path = rec / "llm_response.json"
    if response_path.exists():
        response_record = json.loads(response_path.read_text())
    else:
        response_record = {"api_response": None,
                           "response_status": "not_completed_before_deadline"}
    raw_path = rec / "llm_http_response.raw"
    response_record.update(context, inference_wall_s=result.get("inference_wall_s"),
                           raw_response_file=raw_path.name if raw_path.exists() else None,
                           raw_response_bytes=raw_path.stat().st_size if raw_path.exists() else 0)
    write_json(response_path, response_record)
    context["cleanup_elapsed_before_result_write_s"] = time.monotonic() - cleanup_start
    write_json(rec / "llm_result.json", {**context, **result})
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
    if style == "v2":
        import readable_request
        if os.environ.get("LLM_MAX_TOKENS", str(readable_request.MAX_TOKENS)) != str(readable_request.MAX_TOKENS):
            raise ValueError("LLM_IMAGE_STYLE=v2 sends max_tokens 320 and seed 20261021, as in the "
                             "picture tests; leave LLM_MAX_TOKENS unset or set it to 320")
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
    if mode == "sequence" and _sequence_prompt() != "own":
        context["sequence_prompt"] = _sequence_prompt()
    if _periodic_every() is not None:
        context["record_dir"] = str(_case / "llm_requests" / f"step-{int(state['step']):06d}")
    if frames is not None:
        # v2 frames also carry the capture time and status, so the worker can refuse a
        # folder left by an earlier run (step numbers restart with every solver process)
        context["frames"] = [dict({"directory": frame["directory"], "step": frame["step"]},
                                  **({"time_s": frame["time_s"], "status": frame["status"]}
                                     if style == "v2" else {}))
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
                _keep_computed_trends(context, message)
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
        _keep_computed_trends(context, message)
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
    context["ipc_bytes_received"] = job["reader"].bytes_received if job["reader"] else 0
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
    for entry in _request_log:
        if entry["step"] == context.get("request_step") and entry["status"] == "pending":
            # record_written: whether the bounded writer finished the record folder in its
            # budget; a reply can arrive (status ok) and still have no llm_result.json
            entry.update(status=result.get("status"), arrived_at_step=context.get("arrived_at_step"),
                         inference_wall_s=result.get("inference_wall_s"),
                         solver_stall_s=context.get("solver_stall_s"),
                         record_written=bool(reporting.get("writer_completed")))
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
    if _image_style() == "v2" and directory.exists():
        frame["status"] = "render_failed"
        _frames.append(frame)
        raise FileExistsError(f"{directory} holds a frame of an earlier run in this case folder")
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
    global _attempted, _last_callback_outcome, _latest_pressure, _latest_velocity, _sequence_sent, _periodic_refused
    start = time.monotonic()
    try:
        # p_cells and u_cells are the big arrays; keep them out of the kept states and telemetry
        if isinstance(state, dict):
            state = dict(state)  # never remove fields from the solver's dictionary
        pressure = state.pop("p_cells", None) if isinstance(state, dict) else None
        if pressure is not None:
            _latest_pressure = np.array(pressure, dtype=float, copy=True)
        velocity = state.pop("u_cells", None) if isinstance(state, dict) else None
        if velocity is not None:
            # the whole mesh's U (gathered to the master in a parallel run); in a serial
            # run the same values snapshot_func received
            _latest_velocity = np.array(velocity, dtype=float, copy=True)
        state = copy.deepcopy(state)
        _keep(state)
        step = int(state["step"])
        if _pending:
            _poll_pending(step)
        mode = _mode()
        every = None
        if not _periodic_refused:
            try:
                every = _periodic_every()
            except Exception:
                _periodic_refused = True   # report a refused LLM_ANALYSIS_EVERY once
                raise
        if mode == "sequence":
            if not _sequence_sent:
                try:
                    steps = _sequence_steps()
                    _sequence_prompt()   # refused before any frame is drawn
                except Exception:
                    _sequence_sent = True   # report a refused LLM_SEQUENCE_STEPS/PROMPT once
                    raise
                if step in steps:
                    if step != steps[-1]:
                        _capture_frame(state, start)
                    else:
                        _sequence_sent = True
                        _launch(state, start, mode, frames=list(_frames))
        else:
            target = int(os.environ.get("LLM_ANALYSIS_STEP", "5"))
            if every is not None:
                if step >= target and (step - target) % every == 0:
                    _launch(state, start, mode)
                    _request_log.append({"step": step, "status": _last_callback_outcome.get("status"),
                                         "pending_requests": _last_callback_outcome.get("pending_requests")})
            elif not _attempted and step == target:
                # set first, so a failure is not retried at the next step
                _attempted = True
                _launch(state, start, mode)
        if _is_final_step(state):
            if _pending:
                _finish_pending_at_end(step)
            # the lines since the last append (at most _Telemetry.BATCH_LINES unless appends
            # failed), not the whole run: the budget is 0.2 s however long the run was, and
            # 0.2 s more to report a last append that failed
            _telemetry.finish(state)
    except Exception as error:
        _last_callback_outcome = {
            "status": "callback_error", "error": f"{type(error).__name__}: {error}"}
        reporting = _bounded_writer(_record_callback_error,
                                    (state if isinstance(state, dict) else {}, error),
                                    time.monotonic() + 0.2)
        _last_callback_outcome.update(reporting)
    return None
