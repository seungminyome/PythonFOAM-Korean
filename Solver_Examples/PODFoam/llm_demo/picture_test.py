#!/usr/bin/env python3
"""Picture-reading test of 2026-10-21.

build (on a machine with matplotlib): draws the pictures and writes every
request body with its answer key. run (on the GPU node): sends the prepared
requests to the local llama-server, scores the answers and writes a summary.
report: tables from one or more run directories. Nothing here runs the solver
or changes a solver setting; the flow states come from a separate PODFoam run
without model requests.

Sets:
  oct17-paired          the six 2026-10-17 paired requests; only the model name changes
  oct17-paired-cold     the same six with cache_prompt false (prompt not reused)
  oct20-replay          the 24 2026-10-20 describe and sequence requests; only the model name changes
  control-position-*    synthetic fields with one bright |U| spot and one dark p spot at chosen places
  planted-position-*    saved PODFoam states with one narrow |U| peak and one narrow p dip added
                        away from the step corner, so the answer is not the corner
  control-trend-*       synthetic three-time sequences, every speed trend x pressure trend x spot
                        motion once
  flow-describe-*       saved PODFoam states, whole domain and window
  flow-sequence-*       three saved states in time order, whole domain and window
v1 is the picture the solver sends (pod_image.py). v2 is readable_image.py with
one colour range shared by the frames of a sequence; v2own is the same picture
with each image's own colour range and the matching prompt, so that
v2 against v2own isolates the shared colour range; the two prompts differ only in the
colour-scale sentence and in what the trends are judged from (colours or colour-bar
numbers). The new sets send cache_prompt false so every request is processed in full.
check: every request file and the answer key against the manifest, before any request.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import time

import numpy as np

import ablation_runner
from llm_client import (DEFAULT_ENDPOINT, DEFAULT_MODEL, _finish_request, _image_part,
                        encode_json, write_json)
import readable_request
from readable_request import (AXES, DESCRIBE_V2_SYSTEM_PROMPT, MAX_TOKENS, SEED,  # noqa: F401
                              SEQUENCE_V2_SYSTEM_PROMPT, SEQUENCE_V2OWN_SYSTEM_PROMPT, _SEQUENCE_V2,
                              describe_v2_payload, sequence_v2_payload)
import snapshot_runner

DELTA_T_S = 5e-7
WINDOW_X_M = (-0.05, 0.15)
SOLUTION_D = [1, 1, 0]
CONTROL_SIGMA_PCT = 4.0
PLANTED_SIGMA_PCT = 2.0
PLANTED_STEPS = (1000, 2500, 4000, 5500)
WORDS = ("max_speed_trend", "min_pressure_trend", "fastest_flow_region")
SETS = ("oct17-paired", "oct17-paired-cold", "oct20-replay",
        "control-position-v1", "control-position-v2",
        "planted-position-v1", "planted-position-v2",
        "control-trend-v1", "control-trend-v2", "control-trend-v2own",
        "flow-describe-v1", "flow-describe-v2",
        "flow-sequence-v1", "flow-sequence-v2", "flow-sequence-v2own")
PAIRED_SETS = (("control-position-v1", "control-position-v2"), ("planted-position-v1", "planted-position-v2"),
               ("flow-describe-v1", "flow-describe-v2"), ("control-trend-v1", "control-trend-v2"),
               ("control-trend-v2own", "control-trend-v2"), ("flow-sequence-v1", "flow-sequence-v2"),
               ("flow-sequence-v2own", "flow-sequence-v2"))   # item-by-item comparisons in report


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_sha256(path):
    return sha256(Path(path).read_bytes())


# ---------------------------------------------------------------- answer keys

def truth_from_arrays(centres, velocity, pressure, plotted, step, time_s):
    """The answer key snapshot_runner.load_frame computes, from arrays and a plotted range."""
    (x0, x1), (y0, y1) = plotted
    x, y = centres[:, 0], centres[:, 1]
    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    speed = np.linalg.norm(velocity, axis=1)
    index = np.flatnonzero(inside)

    def percent(cell):
        return {"x_percent": 100.0 * (x[cell] - x0) / (x1 - x0),
                "y_percent": 100.0 * (y[cell] - y0) / (y1 - y0),
                "x_m": float(x[cell]), "y_m": float(y[cell]), "cell": int(cell)}

    fastest = index[np.argmax(speed[index])]
    lowest = index[np.argmin(pressure[index])]
    return {"step": int(step), "time_s": float(time_s), "cells_in_window": int(inside.sum()),
            "max_speed_m_per_s": float(speed[index].max()),
            "min_pressure_m2_per_s2": float(pressure[index].min()),
            "fastest_flow": percent(fastest), "lowest_pressure": percent(lowest),
            "plotted_range_m": {"x": [x0, x1], "y": [y0, y1]}, "projection_axes": AXES,
            "x_span_m": x1 - x0, "y_span_m": y1 - y0}


# ---------------------------------------------------------------- frames

class Mesh:
    def __init__(self, polymesh, centres_npz):
        import foam_fields
        import pod_image
        with np.load(centres_npz, allow_pickle=False) as arrays:
            self.centres = np.array(arrays["centres"])
        self.cells = self.centres.shape[0]
        points, offsets, cells = foam_fields.empty_patch_polygons(polymesh)
        self.polygons = pod_image.cell_polygons(points, offsets, cells, self.cells)
        y = self.centres[:, 1]
        x = self.centres[:, 0]
        self.views = {"full": [[float(x.min()), float(x.max())], [float(y.min()), float(y.max())]],
                      "window": [list(WINDOW_X_M), [float(y.min()), float(y.max())]]}
        self.sources = {"polymesh": {name: file_sha256(Path(polymesh) / name)
                                     for name in ("boundary", "faces", "owner", "points")},
                        "centres_npz": str(centres_npz), "centres_npz_sha256": file_sha256(centres_npz)}


def render_v1(mesh, view, velocity, pressure, step, time_s, directory):
    """The solver's picture (pod_image.render), then the frame as snapshot_runner loads it.

    Drawn in a forked child, as the solver does: pod_image.render keeps about 30 MB per
    call in a long-lived process, which hundreds of pictures would not survive.
    """
    import pod_image
    window = mesh.views["window"][0] if view == "window" else None
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            pod_image.render({"cells": mesh.cells, "time_s": float(time_s), "step": int(step)},
                             mesh.centres, SOLUTION_D, velocity, pressure, directory,
                             polygons=mesh.polygons, x_window=window)
            code = 0
        except BaseException:
            import traceback
            traceback.print_exc()
        finally:
            os._exit(code)
    _, status = os.waitpid(pid, 0)
    if status != 0:
        raise RuntimeError(f"drawing {directory} failed (status {status})")
    return snapshot_runner.load_frame(directory)


def render_v2(mesh, view, velocity, pressure, step, time_s, directory, colour_ranges=None):
    """Two single-field pictures (|U|, p) and the arrays they were drawn from."""
    plotted = mesh.views[view]
    frame, _ = readable_request.render_frame(directory, mesh.centres, mesh.polygons, velocity, pressure,
                                             plotted, step, time_s, view=view,
                                             domain_extent=mesh.views["full"], colour_ranges=colour_ranges)
    return frame, truth_from_arrays(mesh.centres, velocity, pressure, plotted, step, time_s)


def load_v2(directory):
    """Frame and answer key of a v2 directory, with the hashes checked."""
    frame, meta, fields = readable_request.load_frame(directory)
    plotted = [meta["plotted_range_m"]["x"], meta["plotted_range_m"]["y"]]
    return frame, truth_from_arrays(fields["centres"], fields["U"], fields["p"], plotted,
                                    meta["step"], meta["time_s"])


# ---------------------------------------------------------------- requests

def describe_v1_payload(frame, seed=SEED):
    request = snapshot_runner.describe_payload(frame, DEFAULT_MODEL, seed, MAX_TOKENS)
    request["cache_prompt"] = False
    return request


def sequence_v1_payload(frames, seed=SEED):
    request = snapshot_runner.sequence_payload(frames, DEFAULT_MODEL, seed, MAX_TOKENS)
    request["cache_prompt"] = False
    return request


# ---------------------------------------------------------------- synthetic fields

def _percent_centres(mesh, view):
    (x0, x1), (y0, y1) = mesh.views[view]
    c = mesh.centres
    inside = (c[:, 0] >= x0) & (c[:, 0] <= x1) & (c[:, 1] >= y0) & (c[:, 1] <= y1)
    return np.column_stack([100 * (c[:, 0] - x0) / (x1 - x0), 100 * (c[:, 1] - y0) / (y1 - y0)]), inside


def snap(mesh, view, point):
    """The centre of the cell inside the plotted range nearest to a percent position."""
    pct, inside = _percent_centres(mesh, view)
    index = np.flatnonzero(inside)
    cell = index[np.argmin(np.hypot(*(pct[index] - np.asarray(point, dtype=float)).T))]
    return [float(pct[cell, 0]), float(pct[cell, 1])]


def pick_places(mesh, view, count, rng, margin=8.0, snap_pct=1.0, avoid=(), avoid_pct=0.0):
    """Places spread over the picture (stratified), each on a cell, away from the edges and
    at least avoid_pct from every point in avoid."""
    pct, inside = _percent_centres(mesh, view)
    index = np.flatnonzero(inside)
    side = int(math.ceil(math.sqrt(count)))
    places = []
    for k in range(count):
        i, j = k % side, k // side
        # first inside stratum k; if avoid rules out the whole stratum, anywhere in the picture
        for tries, width in ((2000, (100 - 2 * margin) / side), (5000, None)):
            for _ in range(tries):
                if width is None:
                    target = margin + rng.random(2) * (100 - 2 * margin)
                else:
                    target = np.array([margin + (i + rng.random()) * width, margin + (j + rng.random()) * width])
                distance = np.hypot(*(pct[index] - target).T)
                if distance.min() > snap_pct:
                    continue
                cell = index[np.argmin(distance)]
                place = [float(pct[cell, 0]), float(pct[cell, 1])]
                if all(math.dist(place, a) >= avoid_pct for a in avoid):
                    places.append(place)
                    break
            else:
                continue
            break
        else:
            raise RuntimeError(f"no cell for place {k} in view {view}")
    return places


def _bump(mesh, view, centre, sigma):
    pct, _ = _percent_centres(mesh, view)
    r = np.hypot(pct[:, 0] - centre[0], pct[:, 1] - centre[1])
    return np.exp(-0.5 * (r / sigma) ** 2)


def synthetic_fields(mesh, view, spot, dip, peak, base=5.0, dip_depth=-600.0, background_p=50.0):
    """|U| = base + bump at spot, p = background + dip at dip; the bumps are round in the picture."""
    speed = base + (peak - base) * _bump(mesh, view, spot, CONTROL_SIGMA_PCT)
    velocity = np.column_stack([speed, np.zeros_like(speed), np.zeros_like(speed)])
    pressure = background_p + (dip_depth - background_p) * _bump(mesh, view, dip, CONTROL_SIGMA_PCT)
    return velocity, pressure


def planted_fields(mesh, view, velocity, pressure, spot, dip, sigma=PLANTED_SIGMA_PCT):
    """A real state with a narrow |U| peak at spot and a narrow p dip at dip.

    The peak reaches 1.3 x the state's highest |U| inside the plotted range and the
    dip reaches the lowest p minus 0.3 x the p range, so both are the extremes.
    The velocity keeps its direction.
    """
    _, inside = _percent_centres(mesh, view)
    speed = np.linalg.norm(velocity, axis=1)
    peak = 1.3 * float(speed[inside].max())
    low = float(pressure[inside].min()) - 0.3 * float(np.ptp(pressure[inside]))
    # each bump is 1 at the cell nearest its centre, so that cell reaches the planted value
    up = _bump(mesh, view, spot, sigma)
    up = up / up.max()
    down = _bump(mesh, view, dip, sigma)
    down = down / down.max()
    spot_cell, dip_cell = int(np.argmax(up)), int(np.argmax(down))
    new_speed = speed + (peak - speed[spot_cell]) * up
    direction = np.where(speed[:, None] > 1e-12, velocity / np.maximum(speed, 1e-300)[:, None],
                         np.array([1.0, 0.0, 0.0]))
    new_pressure = pressure + (low - pressure[dip_cell]) * down
    return direction * new_speed[:, None], new_pressure, {"peak_m_per_s": peak, "low_m2_per_s2": low}


TREND_SPEEDS = {"increasing": (40.0, 50.0, 60.0), "decreasing": (60.0, 50.0, 40.0),
                "roughly_constant": (50.0, 50.2, 50.4)}
TREND_DIPS = {"more_negative": (-400.0, -600.0, -800.0), "less_negative": (-800.0, -600.0, -400.0),
              "roughly_constant": (-600.0, -602.0, -604.0)}


def trend_designs():
    """18 sequences: every speed trend x pressure trend x spot motion once, so neither trend
    can be guessed from the other."""
    return [{"max_speed_trend": speed, "min_pressure_trend": pressure, "fastest_flow_region": region}
            for speed in TREND_SPEEDS for pressure in TREND_DIPS for region in ("same_place", "moves")]


# ---------------------------------------------------------------- build

def state_steps(case):
    """{step: time directory} of the written times of a case (step = time / 5e-7)."""
    out = {}
    for path in Path(case).iterdir():
        try:
            value = float(path.name)
        except ValueError:
            continue
        if value > 0 and (path / "U").exists() and (path / "p").exists():
            out[int(round(value / DELTA_T_S))] = path
    return dict(sorted(out.items()))


class Builder:
    def __init__(self, output, roots=()):
        """roots: (folder, prefix) pairs for paths outside the test set."""
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.roots = [(self.output, "")] + [(Path(r).resolve(), prefix) for r, prefix in roots]
        self.entries = []
        self.truth = {}
        self.extra = {}

    def rel(self, value):
        """Paths in the manifest relative to the test set, the repository or the states folder."""
        if isinstance(value, dict):
            return {k: self.rel(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.rel(v) for v in value]
        if isinstance(value, (str, Path)) and str(value).startswith("/"):
            path = Path(value).resolve()
            for root, prefix in self.roots:
                if root in path.parents:
                    return prefix + str(path.relative_to(root))
        return str(value) if isinstance(value, Path) else value

    def add(self, set_name, name, mode, payload, truth, sources, design=None):
        directory = self.output / "requests" / set_name
        directory.mkdir(parents=True, exist_ok=True)
        body = encode_json(payload)
        path = directory / f"{name}.request.json"
        path.write_bytes(body)
        key = f"{set_name}/{name}"
        self.truth[key] = truth
        images = sum(1 for message in payload["messages"] if isinstance(message.get("content"), list)
                     for part in message["content"] if part.get("type") == "image_url")
        entry = {"set": set_name, "name": name, "mode": mode,
                 "file": str(path.relative_to(self.output)), "request_sha256": sha256(body),
                 "request_bytes": len(body), "images": images, "seed": payload.get("seed"),
                 "cache_prompt": payload.get("cache_prompt", True), "sources": self.rel(sources)}
        if design is not None:
            entry["design"] = design
        self.entries.append(entry)

    def frame_dir(self, *parts):
        return self.output.joinpath("frames", *parts)


def build_old_sets(builder, oct17, oct20):
    oct17 = Path(oct17)
    summary = json.loads((oct17 / "numeric_summary.json").read_text())
    truth = json.loads((oct17 / "ground_truth.private.json").read_text())
    builder.extra["oct17_numeric_summary"] = summary
    manifest = json.loads((oct17 / "manifest.json").read_text())
    for entry in manifest["schedule"]:
        source = oct17 / f"{entry['name']}.request.json"
        body = source.read_bytes()
        if sha256(body) != entry["request_sha256"]:
            raise ValueError(f"{source}: differs from its manifest")
        payload = json.loads(body)
        sources = {"request": str(source), "request_sha256": entry["request_sha256"],
                   "condition": entry["condition"], "pair": entry["pair"]}
        builder.add("oct17-paired", entry["name"], "observe", payload, truth, sources)
        cold = copy.deepcopy(payload)
        cold["cache_prompt"] = False
        builder.add("oct17-paired-cold", entry["name"], "observe", cold, truth, sources)
    for directory in sorted(Path(oct20).iterdir()):
        manifest = json.loads((directory / "manifest.json").read_text())
        key = json.loads((directory / "ground_truth.private.json").read_text())
        for entry in manifest["schedule"]:
            source = directory / f"{entry['name']}.request.json"
            body = source.read_bytes()
            if sha256(body) != entry["request_sha256"]:
                raise ValueError(f"{source}: differs from its manifest")
            truth = key[str(entry["frame_step"])] if manifest["mode"] == "describe" else key
            builder.add("oct20-replay", f"{directory.name}-{entry['name']}", manifest["mode"],
                        json.loads(body), truth,
                        {"request": str(source), "request_sha256": entry["request_sha256"],
                         "replay": directory.name, "frame_step": entry["frame_step"]})


def build_controls(builder, mesh, positions_per_view=16):
    rng = np.random.default_rng(SEED)
    for view in ("full", "window"):
        spots = pick_places(mesh, view, positions_per_view, rng)
        dips = pick_places(mesh, view, positions_per_view, rng)
        order = [int(j) for j in rng.permutation(positions_per_view)]
        for k in range(positions_per_view):
            spot = spots[k]
            # a dip far from the spot, so the two answers are not the same place
            far = [j for j in order if math.dist(dips[j], spot) >= 25.0]
            chosen = far[0] if far else max(order, key=lambda j: math.dist(dips[j], spot))
            order.remove(chosen)
            dip = dips[chosen]
            step = 1000 + k
            velocity, pressure = synthetic_fields(mesh, view, spot, dip, peak=60.0)
            name = f"{view}-{k + 1:02d}"
            design = {"spot_percent": spot, "dip_percent": dip, "sigma_percent": CONTROL_SIGMA_PCT,
                      "spot_dip_distance_percent": math.dist(spot, dip), "synthetic": True, "view": view}
            frame1, truth1 = render_v1(mesh, view, velocity, pressure, step, step * DELTA_T_S,
                                       builder.frame_dir("control-position", name, "v1"))
            builder.add("control-position-v1", name, "describe", describe_v1_payload(frame1), truth1,
                        {"frame": frame1["directory"], "png_sha256": frame1["sha256"]}, design)
            frame2, truth2 = render_v2(mesh, view, velocity, pressure, step, step * DELTA_T_S,
                                       builder.frame_dir("control-position", name, "v2"))
            assert truth2 == truth1, "v1 and v2 answer keys differ"
            builder.add("control-position-v2", name, "describe", describe_v2_payload(frame2), truth2,
                        {"frame": frame2["directory"], "png_sha256": frame2["image_sha256"]}, design)
    view = "window"
    for k, design in enumerate(trend_designs()):
        pool = pick_places(mesh, view, 16, rng)
        a = pool[int(rng.integers(16))]
        b = next(s for s in pool if math.dist(s, a) >= 30.0) if design["fastest_flow_region"] == "moves" else a
        mid = snap(mesh, view, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2])
        dip = next(s for s in pool if min(math.dist(s, a), math.dist(s, b), math.dist(s, mid)) >= 25.0)
        speeds, depths = TREND_SPEEDS[design["max_speed_trend"]], TREND_DIPS[design["min_pressure_trend"]]
        positions = [a, mid, b]
        fields = [synthetic_fields(mesh, view, positions[i], dip, peak=speeds[i], dip_depth=depths[i])
                  for i in range(3)]
        steps = [100, 200, 300]
        name = f"trend-{k + 1:02d}"
        frames1, truths1 = zip(*[render_v1(mesh, view, *fields[i], steps[i], steps[i] * DELTA_T_S,
                                           builder.frame_dir("control-trend", name, "v1", f"t{i + 1}"))
                                 for i in range(3)])
        truth = snapshot_runner.sequence_truth(list(truths1))
        for word in WORDS:
            assert truth[word] == design[word], (name, word, truth[word], design[word])
        full_design = dict(design, spots_percent=positions, dip_percent=dip,
                           bump_peaks_m_per_s=list(speeds), dip_depths_m2_per_s2=list(depths),
                           measured=[{"max_speed_m_per_s": t["max_speed_m_per_s"],
                                      "min_pressure_m2_per_s2": t["min_pressure_m2_per_s2"],
                                      "fastest_flow_percent": [t["fastest_flow"]["x_percent"],
                                                               t["fastest_flow"]["y_percent"]],
                                      "lowest_pressure_percent": [t["lowest_pressure"]["x_percent"],
                                                                  t["lowest_pressure"]["y_percent"]]}
                                     for t in truths1],
                           synthetic=True, view=view)
        builder.add("control-trend-v1", name, "sequence", sequence_v1_payload(list(frames1)), truth,
                    {"frames": [f["directory"] for f in frames1]}, full_design)
        shared = shared_ranges(mesh, view, fields)
        frames2 = [render_v2(mesh, view, *fields[i], steps[i], steps[i] * DELTA_T_S,
                             builder.frame_dir("control-trend", name, "v2", f"t{i + 1}"), shared)[0]
                   for i in range(3)]
        builder.add("control-trend-v2", name, "sequence", sequence_v2_payload(frames2), truth,
                    {"frames": [f["directory"] for f in frames2], "shared_colour_range": shared}, full_design)
        frames3 = [render_v2(mesh, view, *fields[i], steps[i], steps[i] * DELTA_T_S,
                             builder.frame_dir("control-trend", name, "v2own", f"t{i + 1}"))[0]
                   for i in range(3)]
        builder.add("control-trend-v2own", name, "sequence", sequence_v2_payload(frames3, own_ranges=True),
                    truth, {"frames": [f["directory"] for f in frames3]}, full_design)


def build_planted(builder, mesh, fields, positions_per_view=16):
    """Real states with a planted narrow peak and dip, away from the state's own extremes."""
    rng = np.random.default_rng(SEED + 1)
    for view in ("full", "window"):
        for k in range(positions_per_view):
            step = PLANTED_STEPS[k % len(PLANTED_STEPS)]
            velocity, pressure = fields[step]
            real = truth_from_arrays(mesh.centres, velocity, pressure, mesh.views[view], step, step * DELTA_T_S)
            corner = [[real["fastest_flow"]["x_percent"], real["fastest_flow"]["y_percent"]],
                      [real["lowest_pressure"]["x_percent"], real["lowest_pressure"]["y_percent"]]]
            spot = pick_places(mesh, view, positions_per_view, rng, avoid=corner, avoid_pct=15.0)[k]
            candidates = pick_places(mesh, view, positions_per_view, rng, avoid=corner + [spot], avoid_pct=15.0)
            dip = max(candidates, key=lambda d: min(math.dist(d, spot), 40.0) + 0.01 * rng.random())
            new_velocity, new_pressure, levels = planted_fields(mesh, view, velocity, pressure, spot, dip)
            name = f"{view}-{k + 1:02d}-step{step:06d}"
            design = dict(levels, spot_percent=spot, dip_percent=dip, sigma_percent=PLANTED_SIGMA_PCT,
                          background_step=step, planted=True, view=view,
                          state_extremes_percent=corner)
            frame1, truth1 = render_v1(mesh, view, new_velocity, new_pressure, step, step * DELTA_T_S,
                                       builder.frame_dir("planted-position", name, "v1"))
            builder.add("planted-position-v1", name, "describe", describe_v1_payload(frame1), truth1,
                        {"frame": frame1["directory"], "state_step": step}, design)
            frame2, truth2 = render_v2(mesh, view, new_velocity, new_pressure, step, step * DELTA_T_S,
                                       builder.frame_dir("planted-position", name, "v2"))
            assert truth2 == truth1
            builder.add("planted-position-v2", name, "describe", describe_v2_payload(frame2), truth2,
                        {"frame": frame2["directory"], "state_step": step}, design)


def shared_ranges(mesh, view, fields):
    """One colour range per field over all frames, from the cells inside the plotted range."""
    (x0, x1), (y0, y1) = mesh.views[view]
    c = mesh.centres
    inside = (c[:, 0] >= x0) & (c[:, 0] <= x1) & (c[:, 1] >= y0) & (c[:, 1] <= y1)
    speeds = [np.linalg.norm(u, axis=1)[inside] for u, _ in fields]
    pressures = [p[inside] for _, p in fields]
    return {"U": [float(min(s.min() for s in speeds)), float(max(s.max() for s in speeds))],
            "p": [float(min(p.min() for p in pressures)), float(max(p.max() for p in pressures))]}


def read_states(builder, mesh, case, steps):
    import foam_fields
    times = state_steps(case)
    missing = [s for s in steps if s not in times]
    if missing:
        raise ValueError(f"states missing in {case}: {missing}")
    fields = {}
    for step in steps:
        fields[step] = (foam_fields.read_internal_field(times[step] / "U", mesh.cells),
                        foam_fields.read_internal_field(times[step] / "p", mesh.cells))
    builder.extra["flow_states"] = {str(step): {"time_dir": builder.rel(times[step]),
                                                "U_sha256": file_sha256(times[step] / "U"),
                                                "p_sha256": file_sha256(times[step] / "p")}
                                    for step in steps}
    return fields


def build_flow(builder, mesh, fields, describe_steps, sequences):
    def frame_v1(view, step):
        directory = builder.frame_dir("flow", f"{view}-step{step:06d}", "v1")
        if not directory.exists():
            render_v1(mesh, view, *fields[step], step, step * DELTA_T_S, directory)
        return snapshot_runner.load_frame(directory)

    def frame_v2(view, step):
        directory = builder.frame_dir("flow", f"{view}-step{step:06d}", "v2")
        if not directory.exists():
            render_v2(mesh, view, *fields[step], step, step * DELTA_T_S, directory)
        return load_v2(directory)

    for view in ("full", "window"):
        for step in describe_steps:
            name = f"{view}-step{step:06d}"
            frame1, truth1 = frame_v1(view, step)
            builder.add("flow-describe-v1", name, "describe", describe_v1_payload(frame1), truth1,
                        {"frame": frame1["directory"], "state_step": step})
            frame2, truth2 = frame_v2(view, step)
            assert truth2 == truth1
            builder.add("flow-describe-v2", name, "describe", describe_v2_payload(frame2), truth2,
                        {"frame": frame2["directory"], "state_step": step})
        for triple in sequences:
            name = f"{view}-steps{'-'.join(f'{s:06d}' for s in triple)}"
            loaded = [frame_v1(view, s) for s in triple]
            truth = snapshot_runner.sequence_truth([t for _, t in loaded])
            builder.add("flow-sequence-v1", name, "sequence", sequence_v1_payload([f for f, _ in loaded]),
                        truth, {"frames": [f["directory"] for f, _ in loaded]})
            shared = shared_ranges(mesh, view, [fields[s] for s in triple])
            frames2 = [render_v2(mesh, view, *fields[s], s, s * DELTA_T_S,
                                 builder.frame_dir("flow-sequence", name, f"t{i + 1}"), shared)[0]
                       for i, s in enumerate(triple)]
            builder.add("flow-sequence-v2", name, "sequence", sequence_v2_payload(frames2), truth,
                        {"frames": [f["directory"] for f in frames2], "shared_colour_range": shared})
            frames3 = [frame_v2(view, s)[0] for s in triple]
            builder.add("flow-sequence-v2own", name, "sequence", sequence_v2_payload(frames3, own_ranges=True),
                        truth, {"frames": [f["directory"] for f in frames3]})


def copy_published(builder, oct17, oct20):
    """The published replies, so report can compare a model with the 2026-10-17/20 E2B answers."""
    target = builder.output / "published"
    (target / "oct17").mkdir(parents=True)
    shutil.copy2(Path(oct17) / "metrics.jsonl", target / "oct17" / "metrics.jsonl")
    for directory in sorted(Path(oct20).iterdir()):
        (target / "oct20" / directory.name).mkdir(parents=True)
        shutil.copy2(directory / "metrics.jsonl", target / "oct20" / directory.name / "metrics.jsonl")


def link_duplicate_arrays(root):
    """Hard-link identical fields.npz files (v1, v2 and v2own frames of the same arrays)."""
    seen, linked = {}, 0
    for path in sorted(Path(root).rglob("fields.npz")):
        digest = file_sha256(path)
        if digest in seen:
            path.unlink()
            os.link(seen[digest], path)
            linked += 1
        else:
            seen[digest] = path
    return linked


def build(args):
    import matplotlib
    import pod_image
    for name in ("states", "centres", "oct17", "oct20", "output"):
        setattr(args, name, str(Path(getattr(args, name)).resolve()))
    repo = Path(__file__).resolve().parents[3]
    states = Path(args.states)
    roots = ((repo, ""), (states.parent, states.parent.name + "/"))
    builder = Builder(args.output, roots=roots)
    pod_image.prepare_backend(builder.output / ".mpl")
    mesh = Mesh(states / "constant" / "polyMesh", args.centres)
    build_old_sets(builder, args.oct17, args.oct20)
    copy_published(builder, args.oct17, args.oct20)
    build_controls(builder, mesh)
    describe_steps = list(range(args.describe_every, args.last_step + 1, args.describe_every))
    sequences = [tuple(int(s) for s in triple.split(",")) for triple in args.sequence]
    needed = sorted(set(describe_steps) | {s for t in sequences for s in t} | set(PLANTED_STEPS))
    fields = read_states(builder, mesh, states, needed)
    build_planted(builder, mesh, fields)
    build_flow(builder, mesh, fields, describe_steps, sequences)
    write_json(builder.output / "truth.private.json", builder.truth)
    shutil.rmtree(builder.output / ".mpl", ignore_errors=True)
    linked = link_duplicate_arrays(builder.output / "frames")
    here = Path(__file__).resolve().parent
    code = {name: file_sha256(here / name) for name in
            ("picture_test.py", "readable_image.py", "readable_request.py", "foam_fields.py",
             "pod_image.py", "snapshot_runner.py", "ablation_runner.py", "llm_client.py")}
    counts = {name: sum(e["set"] == name for e in builder.entries) for name in SETS}
    manifest = {"schema_version": 2, "test": "picture-reading test 2026-10-21", "seed": SEED,
                "max_tokens": MAX_TOKENS, "sets": counts, "requests": builder.entries,
                "truth_sha256": file_sha256(builder.output / "truth.private.json"),
                "build_args": dict(builder.rel(vars(args)), output=Path(args.output).name),
                "path_prefixes": {"": "frames/ and requests/ are in this test set, docs/ is the repository",
                                  states.parent.name + "/": "the folder of the PODFoam run without model requests"},
                "mesh": builder.rel(mesh.sources), "views_m": mesh.views,
                "control_sigma_percent": CONTROL_SIGMA_PCT, "planted_sigma_percent": PLANTED_SIGMA_PCT,
                "trend_tolerances": {"relative_change": snapshot_runner.TREND_TOLERANCE,
                                     "region_percent": snapshot_runner.REGION_TOLERANCE_PCT},
                "code_sha256": code, "matplotlib": matplotlib.__version__, "numpy": np.__version__,
                "extra": builder.extra, "identical_arrays_hard_linked": linked,
                "truth_withheld_from_model": True, "model_name_in_bodies": DEFAULT_MODEL,
                "note": ("The runner replaces only the model name in each body. Old sets are byte "
                         "for byte the published requests apart from that name (oct17-paired-cold "
                         "also sets cache_prompt false).")}
    write_json(builder.output / "manifest.json", manifest)
    print(json.dumps({"output": str(builder.output), "requests": len(builder.entries), "sets": counts}, indent=2))
    return 0


# ---------------------------------------------------------------- run

def check(args):
    """Every request file and the answer key against the manifest; nonzero exit if not."""
    root = Path(args.test_set).resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    problems = []
    if not (root / "truth.private.json").exists():
        problems.append("truth.private.json missing")
    elif manifest.get("truth_sha256") not in (None, file_sha256(root / "truth.private.json")):
        problems.append("truth.private.json differs from the manifest")
    for entry in manifest["requests"]:
        path = root / entry["file"]
        if not path.exists():
            problems.append(f"missing {entry['file']}")
        elif file_sha256(path) != entry["request_sha256"]:
            problems.append(f"changed {entry['file']}")
    for line in problems[:20]:
        print(line)
    print(f"{len(manifest['requests'])} requests checked, {len(problems)} problems")
    return 1 if problems else 0


def run(args):
    root = Path(args.test_set).resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    truth_sha = file_sha256(root / "truth.private.json")
    if manifest.get("truth_sha256") not in (None, truth_sha):
        raise ValueError("truth.private.json differs from the manifest; rebuild or recopy the test set")
    truth = json.loads((root / "truth.private.json").read_text())
    summary17 = manifest["extra"]["oct17_numeric_summary"]
    wanted = args.sets or list(SETS)
    unknown = sorted(set(wanted) - set(SETS))
    if unknown:
        raise SystemExit(f"unknown sets: {unknown}")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "run.json", {"model": args.model, "endpoint": args.endpoint,
                                     "server_note": args.server_note, "sets": wanted,
                                     "limit": args.limit, "timeout_s": args.timeout_s,
                                     "test_set": str(root),
                                     "test_set_manifest_sha256": file_sha256(root / "manifest.json"),
                                     "truth_sha256": truth_sha, "started_unix_s": time.time()})
    failures = 0
    for set_name in wanted:
        entries = [e for e in manifest["requests"] if e["set"] == set_name]
        if args.limit:
            entries = entries[:args.limit]
        directory = output / set_name
        directory.mkdir()
        rows, keys = [], []
        for entry in entries:
            body = (root / entry["file"]).read_bytes()
            if sha256(body) != entry["request_sha256"]:
                raise ValueError(f"{entry['file']}: changed after the manifest was written")
            payload = json.loads(body)
            payload["model"] = args.model
            key = truth[f"{set_name}/{entry['name']}"]
            if entry["mode"] == "observe":
                row = ablation_runner.run_trial(payload, directory / entry["name"], summary17, key,
                                                args.endpoint, args.timeout_s)
                row["condition"] = entry["sources"]["condition"]
                row["replay_wall_s"] = row["replay_callback_wall_s"]
                result = json.loads((directory / entry["name"] / "result.json").read_text())
                row["usage"] = result.get("usage")
                row["server_timings"] = result.get("server_timings")
            else:
                row = snapshot_runner.run_trial(payload, directory / entry["name"], entry["mode"], key,
                                                args.endpoint, args.timeout_s)
            row.update(name=entry["name"], set=set_name, mode=entry["mode"],
                       group=entry["sources"].get("replay") or entry["mode"],
                       prepared_request_sha256=entry["request_sha256"])
            sent = directory / entry["name"] / "request_body.json"
            if not args.keep_bodies and sent.exists():
                # the body sent is the prepared one with this model name; its hash stays in metrics
                if sha256(sent.read_bytes()) == sha256(encode_json(payload)):
                    sent.unlink()
            if not row["successful_response"]:
                failures += 1
            rows.append(row)
            keys.append(key)
            with (directory / "metrics.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(encode_json(row).decode("utf-8") + "\n")
            print(f"{set_name}/{entry['name']}: {row['status']} {row['replay_wall_s']:.1f}s", flush=True)
        write_json(directory / "summary.json", summarize_set(set_name, rows, keys))
    print(json.dumps({"output": str(output), "failures": failures}, indent=2))
    return 0 if failures == 0 else 2


def _usage(row, key):
    return (row.get("usage") or {}).get(key)


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


ANSWER_GRID = np.stack(np.meshgrid(np.arange(101.0), np.arange(101.0)), -1).reshape(-1, 1, 2)


def constant_answer_baseline(mode, keys):
    """What one fixed answer per plotted range would score: for positions, the best integer
    answer (the only kind the schema allows) counted within 10 %; for words, the most common
    true word."""
    if mode == "describe":
        out = {}
        for target in ("fastest_flow", "lowest_pressure"):
            groups = {}
            for key in keys:
                box = json.dumps(key["plotted_range_m"], sort_keys=True)
                groups.setdefault(box, []).append((key[target]["x_percent"], key[target]["y_percent"]))
            out[target] = sum(int((np.hypot(*(ANSWER_GRID - np.array(points)).transpose(2, 0, 1)) <= 10.0)
                                  .sum(axis=1).max()) for points in groups.values())
        return out
    if mode == "sequence":
        return {word: max(sum(k[word] == v for k in keys) for v in {k[word] for k in keys}) for word in WORDS}
    return None


def summarize_mode(mode, rows, keys):
    ok = [r for r in rows if r["successful_response"]]
    block = {"attempted": len(rows), "successful": len(ok),
             "median_latency_s": _median([r["replay_wall_s"] for r in rows]),
             "median_prompt_tokens": _median([_usage(r, "prompt_tokens") for r in rows])}
    if mode == "describe":
        for target in ("fastest_flow", "lowest_pressure"):
            distances = [r["scores"][target]["distance_percent"] for r in ok]
            block[target] = {"within_10_percent": sum(d <= 10.0 for d in distances),
                             "median_distance_percent": _median(distances),
                             "distances_percent": distances}
    elif mode == "sequence":
        for word in WORDS:
            block[word] = {"match": sum(r["scores"][word]["match"] for r in ok),
                           "cannot_tell": sum(r["scores"][word]["cannot_tell"] for r in ok),
                           "answers": [r["scores"][word]["answer"] for r in ok],
                           "truth": [r["scores"][word]["truth"] for r in ok]}
    else:
        block["paired"] = ablation_runner.summarize(rows)
    block["constant_answer_baseline"] = constant_answer_baseline(mode, keys)
    return block


def summarize_set(set_name, rows, keys):
    report = {"set": set_name, "attempted": len(rows),
              "successful": sum(r["successful_response"] for r in rows),
              "latency_s": [r["replay_wall_s"] for r in rows],
              "prompt_tokens": [_usage(r, "prompt_tokens") for r in rows],
              "completion_tokens": [_usage(r, "completion_tokens") for r in rows],
              "cache_n": [((r.get("server_timings") or {}).get("cache_n")) for r in rows],
              "by_mode": {}, "by_group": {}}
    for mode in ("describe", "sequence", "observe"):
        chosen = [(r, k) for r, k in zip(rows, keys) if r["mode"] == mode]
        if chosen:
            report["by_mode"][mode] = summarize_mode(mode, [r for r, _ in chosen], [k for _, k in chosen])
    groups = sorted({r["group"] for r in rows})
    if len(groups) > 1:
        for group in groups:
            chosen = [(r, k) for r, k in zip(rows, keys) if r["group"] == group]
            report["by_group"][group] = summarize_mode(chosen[0][0]["mode"], [r for r, _ in chosen],
                                                       [k for _, k in chosen])
    report["interpretation"] = (
        "Counts are out of attempted requests. Different places or states are separate cases; the "
        "flow states are from one run, so neighbouring states are alike, the fastest flow and the "
        "lowest pressure sit at the step corner in every state, and the flow trend keys hardly vary: "
        "compare with constant_answer_baseline. Repeats of one request (oct20-replay) are not "
        "separate cases. Positions are percent of the plotted range; 10 percent is the distance used "
        "on 2026-10-20. Synthetic controls test reading a simple picture, not physics.")
    return report


# ---------------------------------------------------------------- report

def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _published_matches(run_dir, test_set):
    """How many of this run's 2026-10-17/20 answers equal the published E2B answers."""
    published = Path(test_set) / "published"
    out = {}
    if (run_dir / "oct17-paired" / "metrics.jsonl").exists() and (published / "oct17").exists():
        old = {f"pair-{r['pair']:03d}-{r['condition']}": (r.get("location") or {}).get("coordinates_m")
               for r in _rows(published / "oct17" / "metrics.jsonl")}
        new = {r["name"]: (r.get("location") or {}).get("coordinates_m") for r in _rows(run_dir / "oct17-paired" / "metrics.jsonl")}
        out["oct17-paired"] = f"{sum(new.get(k) == v for k, v in old.items())}/{len(old)} same coordinates"
    if (run_dir / "oct20-replay" / "metrics.jsonl").exists() and (published / "oct20").exists():
        old = {}
        for directory in sorted((published / "oct20").iterdir()):
            for r in _rows(directory / "metrics.jsonl"):
                old[f"{directory.name}-{r['name']}"] = r.get("structured_output")
        new = {r["name"]: r.get("structured_output") for r in _rows(run_dir / "oct20-replay" / "metrics.jsonl")}
        out["oct20-replay"] = f"{sum(new.get(k) == v for k, v in old.items())}/{len(old)} same structured answers"
    return out


def _pairs(run_dir, a, b):
    """Item-by-item comparison of two sets with the same request names."""
    pa, pb = run_dir / a / "metrics.jsonl", run_dir / b / "metrics.jsonl"
    if not (pa.exists() and pb.exists()):
        return None
    def right(row):
        if not row["successful_response"]:
            return False
        if row["mode"] == "describe":
            return row["scores"]["fastest_flow"]["within_10_percent"]
        return row["scores"]["max_speed_trend"]["match"]
    ra = {r["name"]: right(r) for r in _rows(pa)}
    rb = {r["name"]: right(r) for r in _rows(pb)}
    names = sorted(set(ra) & set(rb))
    count = lambda x, y: sum(ra[n] is x and rb[n] is y for n in names)
    return {"items": len(names), "both": count(True, True), f"only {a}": count(True, False),
            f"only {b}": count(False, True), "neither": count(False, False)}


def report(args):
    lines = ["| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    extra, incomplete, notes = [], 0, {}
    for run_dir in args.runs:
        run_dir = Path(run_dir)
        meta = json.loads((run_dir / "run.json").read_text())
        model = meta["model"]
        if meta.get("limit"):
            extra.append(f"{model}: only the first {meta['limit']} requests of each set were sent")
        for set_name in meta["sets"]:
            path = run_dir / set_name / "summary.json"
            if not path.exists():
                lines.append(f"| {model} | {set_name} | | no summary (run incomplete) | | | | | | | | |")
                incomplete += 1
                continue
            summary = json.loads(path.read_text())
            for mode, b in summary["by_mode"].items():
                n = b["attempted"]
                cells = [""] * 5
                base = b.get("constant_answer_baseline") or {}
                if mode == "describe":
                    cells[0] = f"{b['fastest_flow']['within_10_percent']}/{n}"
                    cells[1] = f"{b['lowest_pressure']['within_10_percent']}/{n}"
                    fixed = f"{base.get('fastest_flow')} / {base.get('lowest_pressure')}"
                    if base.get("note"):
                        notes.setdefault(base["note"], set()).add(set_name)
                elif mode == "sequence":
                    cells[2:5] = [f"{b[w]['match']}/{n}" for w in WORDS]
                    fixed = " / ".join(str(base.get(w)) for w in WORDS)
                else:
                    paired = b["paired"]
                    cells[0] = " ; ".join(f"{c}: {paired[c]['location_scored']} located" for c in ablation_runner.CONDITIONS if c in paired)
                    fixed = ""
                median = b.get("median_latency_s")
                tokens = b.get("median_prompt_tokens")
                lines.append(f"| {model} | {set_name} | {mode} | {b['successful']}/{n} | " + " | ".join(cells)
                             + f" | {fixed} | {'' if tokens is None else int(tokens)} | "
                             + f"{'' if median is None else f'{median:.1f}'} |")
        for a, b in PAIRED_SETS:
            paired = _pairs(run_dir, a, b)
            if paired:
                extra.append(f"{model} {a} vs {b}: " + ", ".join(f"{k} {v}" for k, v in paired.items()))
        test_set = args.test_set or meta.get("test_set")
        if test_set and Path(test_set).exists():
            for name, text in _published_matches(run_dir, test_set).items():
                extra.append(f"{model} {name} against the published E2B answers: {text}")
    text = "\n".join(lines) + "\n"
    if extra:
        text += "\n" + "\n".join(f"- {line}" for line in extra) + "\n"
    text += ("\nfixed-answer score: what one fixed answer per plotted range would get"
             + "".join(f"; {', '.join(sorted(sets))}: {note}" for note, sets in notes.items())
             + " (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items "
             "right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).\n")
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 1 if incomplete else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="draw pictures and write the request set")
    b.add_argument("--states", required=True, help="PODFoam case with the written time directories")
    b.add_argument("--centres", required=True, help="fields.npz of a saved frame of the same mesh (cell centres)")
    b.add_argument("--oct17", required=True, help="docs/evidence/2026-10-17/ablation")
    b.add_argument("--oct20", required=True, help="docs/evidence/2026-10-20/replay")
    b.add_argument("--describe-every", type=int, default=500)
    b.add_argument("--last-step", type=int, default=6000)
    b.add_argument("--sequence", action="append", default=[],
                   help="three steps, e.g. 250,750,1250 (repeatable)")
    b.add_argument("--output", required=True, help="new directory")
    r = sub.add_parser("run", help="send a built set to the local server")
    r.add_argument("--test-set", required=True)
    r.add_argument("--sets", nargs="+")
    r.add_argument("--model", required=True, help="alias the server answers to")
    r.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    r.add_argument("--timeout-s", type=float, default=300.0)
    r.add_argument("--server-note", default="unrecorded")
    r.add_argument("--limit", type=int, default=0, help="first N requests of each set (checks)")
    r.add_argument("--keep-bodies", action="store_true",
                   help="keep each sent request_body.json (by default removed: it is the prepared body "
                        "with the model name replaced, and its SHA-256 is in metrics.jsonl)")
    r.add_argument("--output", required=True, help="new directory")
    c = sub.add_parser("check", help="check a copied test set against its manifest")
    c.add_argument("--test-set", required=True)
    t = sub.add_parser("report", help="tables from one or more run directories")
    t.add_argument("runs", nargs="+")
    t.add_argument("--test-set", help="test set with published/ (default: the one in run.json)")
    t.add_argument("--output")
    args = parser.parse_args(argv)
    return {"build": build, "check": check, "run": run, "report": report}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
