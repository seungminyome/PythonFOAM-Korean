#!/usr/bin/env python3
"""Random-window picture test (2026-10-22): saved flow states, each drawn several times with
the plotted window placed at random around the fastest cell, so that the answer position
differs from picture to picture and one fixed answer scores low.

  flow-window-v2   single-field pictures with percent axes (readable_image), one per window
  flow-window-v1   the same windows drawn as the solver draws them (pod_image)

build:  python3 window_test.py build --states <case> --centres <fields.npz> \
            --old-manifest <picture-test-20261021/manifest.json> --output <new dir> \
            [--first-step N] [--describe-every N] [--last-step N] [--windows-per-state N] [--seed N]
        States are the case's written times, named step = time / 5e-7 as in picture_test
        (a run with another or an adaptive time step is labelled by time, not by its own count).
check / run / report: as picture_test.py, with these sets allowed. The fixed-answer score is
one answer for the whole set, since every request has its own window.
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

import picture_test as pt
import pod_image
import snapshot_runner
from llm_client import encode_json, write_json

NEW_SETS = ("flow-window-v1", "flow-window-v2")
TEST_NAME = "picture-window test 2026-10-22"
SEED = 20261022
MARGIN = 0.15          # the fastest cell sits at least this fraction from every window edge
MIN_CELLS = 200
Y_SPAN_M = (0.03, 0.114)
ASPECT = (1.5, 4.0)    # x span / y span of a window


def place_window(rng, peak, domain, cells_xy):
    """[[x0, x1], [y0, y1]] around peak (m): random size and random position of the peak in it.
    x stays inside the domain; y may reach below the bottom wall (drawn white, no cells)."""
    (dx0, dx1), (dy0, dy1) = domain
    for _ in range(500):
        y_span = rng.uniform(*Y_SPAN_M)
        x_span = y_span * rng.uniform(*ASPECT)
        px, py = rng.uniform(MARGIN, 1 - MARGIN, size=2)
        x0 = min(max(peak[0] - px * x_span, dx0), dx1 - x_span)
        y0 = min(peak[1] - py * y_span, dy1 - y_span)
        x1, y1 = x0 + x_span, y0 + y_span
        if not (x0 + MARGIN * x_span <= peak[0] <= x1 - MARGIN * x_span
                and y0 + MARGIN * y_span <= peak[1] <= y1 - MARGIN * y_span):
            continue
        inside = ((cells_xy[:, 0] >= x0) & (cells_xy[:, 0] <= x1)
                  & (cells_xy[:, 1] >= y0) & (cells_xy[:, 1] <= y1))
        if inside.sum() < MIN_CELLS:
            continue
        return [[float(x0), float(x1)], [float(y0), float(y1)]]
    raise RuntimeError(f"no window found around {peak}")


def render_v1_window(mesh, plotted, velocity, pressure, step, time_s, directory):
    """pod_image.render with an x and a y window, in a forked child (as picture_test.render_v1)."""
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            pod_image.render({"cells": mesh.cells, "time_s": float(time_s), "step": int(step)},
                             mesh.centres, pt.SOLUTION_D, velocity, pressure, directory,
                             polygons=mesh.polygons, x_window=plotted[0], y_window=plotted[1])
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


def build(args):
    import matplotlib
    for name in ("states", "centres", "old_manifest", "output"):
        setattr(args, name, str(Path(getattr(args, name)).resolve()))
    repo = Path(__file__).resolve().parents[3]
    states = Path(args.states)
    builder = pt.Builder(args.output, roots=((repo, ""), (states.parent, states.parent.name + "/")))
    pod_image.prepare_backend(builder.output / ".mpl")
    mesh = pt.Mesh(states / "constant" / "polyMesh", args.centres)
    old = json.loads(Path(args.old_manifest).read_text())
    steps = list(range(args.first_step or args.describe_every, args.last_step + 1, args.describe_every))
    fields = pt.read_states(builder, mesh, states, steps)
    rng = np.random.default_rng(args.seed)
    domain = mesh.views["full"]
    xy = mesh.centres[:, :2]
    windows = {}
    for step in steps:
        velocity, pressure = fields[step]
        speed = np.linalg.norm(velocity, axis=1)
        peak = xy[int(np.argmax(speed))]
        for k in range(args.windows_per_state):
            name = f"step{step:06d}-w{k + 1}"
            plotted = place_window(rng, peak, domain, xy)
            mesh.views[name] = plotted
            time_s = step * pt.DELTA_T_S
            frame2, truth2 = pt.render_v2(mesh, name, velocity, pressure, step, time_s,
                                          builder.frame_dir("flow-window", name, "v2"))
            design = {"plotted_range_m": {"x": plotted[0], "y": plotted[1]},
                      "fastest_cell_percent": [truth2["fastest_flow"]["x_percent"],
                                               truth2["fastest_flow"]["y_percent"]],
                      "cells_in_window": truth2["cells_in_window"]}
            builder.add("flow-window-v2", name, "describe", pt.describe_v2_payload(frame2), truth2,
                        {"frame": frame2["directory"], "state_step": step}, design)
            frame1, truth1 = render_v1_window(mesh, plotted, velocity, pressure, step, time_s,
                                              builder.frame_dir("flow-window", name, "v1"))
            for key in ("fastest_flow", "lowest_pressure"):
                for axis in ("x_percent", "y_percent"):
                    if abs(truth1[key][axis] - truth2[key][axis]) > 1e-6:
                        raise RuntimeError(f"{name}: v1 and v2 answer keys differ for {key}")
            builder.add("flow-window-v1", name, "describe", pt.describe_v1_payload(frame1), truth1,
                        {"frame": frame1["directory"], "state_step": step}, design)
            windows[name] = design
    write_json(builder.output / "truth.private.json", builder.truth)
    import shutil
    shutil.rmtree(builder.output / ".mpl", ignore_errors=True)
    linked = pt.link_duplicate_arrays(builder.output / "frames")
    here = Path(__file__).resolve().parent
    code = {name: pt.file_sha256(here / name) for name in
            ("window_test.py", "picture_test.py", "readable_image.py", "readable_request.py", "foam_fields.py",
             "pod_image.py", "snapshot_runner.py", "llm_client.py")}
    counts = {name: sum(e["set"] == name for e in builder.entries) for name in NEW_SETS}
    keys = np.array([[w["fastest_cell_percent"][0], w["fastest_cell_percent"][1]] for w in windows.values()])
    manifest = {"schema_version": 2, "test": f"{TEST_NAME} (window seed {args.seed})", "seed": args.seed, "max_tokens": pt.MAX_TOKENS,
                "sets": counts, "requests": builder.entries,
                "truth_sha256": pt.file_sha256(builder.output / "truth.private.json"),
                "build_args": dict(builder.rel(vars(args)), output=Path(args.output).name),
                "path_prefixes": {"": "frames/ and requests/ are in this test set",
                                  states.parent.name + "/": "the folder of the pimpleFoam run without model requests"},
                "mesh": builder.rel(mesh.sources), "domain_m": domain,
                "window_rule": {"peak_margin_fraction": MARGIN, "min_cells": MIN_CELLS,
                                "y_span_m": list(Y_SPAN_M), "aspect_x_over_y": list(ASPECT),
                                "note": "windows are placed at random around the fastest cell of each "
                                        "state; x stays inside the domain, y may reach below the "
                                        "bottom wall (white, no cells)"},
                "fastest_cell_percent_spread": {"x_min": float(keys[:, 0].min()), "x_max": float(keys[:, 0].max()),
                                                "y_min": float(keys[:, 1].min()), "y_max": float(keys[:, 1].max())},
                "code_sha256": code, "matplotlib": matplotlib.__version__, "numpy": np.__version__,
                "extra": {"oct17_numeric_summary": old["extra"]["oct17_numeric_summary"],
                          "flow_states": builder.extra["flow_states"], "windows": windows},
                "identical_arrays_hard_linked": linked, "truth_withheld_from_model": True,
                "model_name_in_bodies": pt.DEFAULT_MODEL,
                "note": "Same states, prompts, renderers and scoring as picture-test-20261021; only the "
                        "plotted window differs per request. The runner replaces only the model name."}
    write_json(builder.output / "manifest.json", manifest)
    print(encode_json({"output": str(builder.output), "requests": len(builder.entries), "sets": counts,
                       "fastest_cell_percent_spread": manifest["fastest_cell_percent_spread"]}).decode())
    return 0


_per_range_baseline = pt.constant_answer_baseline   # kept before main() patches picture_test


def pooled_constant_answer_baseline(mode, keys):
    """picture_test.constant_answer_baseline scores one fixed answer per plotted range. When
    every request has its own window that is trivially n of n, so the fair baseline is one
    fixed answer for the whole set: the best integer (x, y) counted within 10 % over all keys.
    Sets whose requests share plotted ranges keep the per-range baseline."""
    if mode != "describe" or len({json.dumps(k["plotted_range_m"], sort_keys=True) for k in keys}) < len(keys):
        return _per_range_baseline(mode, keys)
    out = {}
    for target in ("fastest_flow", "lowest_pressure"):
        points = np.array([(k[target]["x_percent"], k[target]["y_percent"]) for k in keys])
        hits = (np.hypot(*(pt.ANSWER_GRID - points).transpose(2, 0, 1)) <= 10.0).sum(axis=1)
        out[target] = int(hits.max())
    out["note"] = "one fixed answer for the whole set (every request has its own window)"
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    pt.SETS = tuple(pt.SETS) + NEW_SETS
    pt.constant_answer_baseline = pooled_constant_answer_baseline
    if argv and argv[0] == "build":
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("command")
        parser.add_argument("--states", required=True, help="case with the written time directories")
        parser.add_argument("--centres", required=True, help="fields.npz of a saved frame of the same mesh")
        parser.add_argument("--old-manifest", required=True, help="picture-test-20261021/manifest.json")
        parser.add_argument("--first-step", type=int, default=0,
                            help="first state (default: --describe-every)")
        parser.add_argument("--describe-every", type=int, default=500)
        parser.add_argument("--last-step", type=int, default=6000)
        parser.add_argument("--windows-per-state", type=int, default=4)
        parser.add_argument("--seed", type=int, default=SEED, help="window placement seed")
        parser.add_argument("--output", required=True, help="new directory")
        return build(parser.parse_args(argv))
    return pt.main(argv)


if __name__ == "__main__":
    sys.exit(main())
