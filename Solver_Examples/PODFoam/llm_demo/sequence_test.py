#!/usr/bin/env python3
"""Trend test on a developed flow (2026-10-27): triples of saved states in a window placed at
random around the fastest cells, so that the maxima rise and fall and the spot moves.

  dev-sequence-v1         the solver's two-panel pictures (pod_image), the 2026-10-20 prompt
  dev-sequence-v2own      single-field pictures, each on its own colour scale, the 2026-10-22 prompt
  dev-sequence-v2own-t    the same pictures, the answer key's thresholds stated in the prompt
  dev-sequence-v2own-tn   the same, plus each time's maximum |U| and minimum p in the note
  dev-sequence-numbers    the note with the numbers and the fastest cell's position, no pictures

build:  python3 sequence_test.py build --states <case> --centres <fields.npz> \
            --old-manifest <picture-test-20261021/manifest.json> --output <new dir> \
            [--first-step N] [--every N] [--last-step N] [--gaps N,N,N] [--count N] [--seed N]
        States are the case's written times, named step = time / 5e-7 as in picture_test.
        Candidate triples (t, t + gap, t + 2 gap) over all gaps and starts get one random window
        each; --count of them are kept so that the nine (speed trend, pressure trend) classes of
        the key are as even as possible.
check / run / report: as picture_test.py, with these sets allowed.
"""
import argparse
import itertools
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from frame_scoring import numbers_of
import picture_test as pt
import pod_image
import readable_request
import snapshot_runner
import window_test
from llm_client import encode_json, write_json

NEW_SETS = ("dev-sequence-v1", "dev-sequence-v2own", "dev-sequence-v2own-t",
            "dev-sequence-v2own-tn", "dev-sequence-numbers")
TEST_NAME = "developed-flow trend test 2026-10-27"
SEED = 20261027
MARGIN = window_test.MARGIN
MIN_CELLS = window_test.MIN_CELLS
ASPECT = window_test.ASPECT


def place_window_around(rng, points, domain, cells_xy, tries=500):
    """[[x0, x1], [y0, y1]] with every point (m) at least MARGIN of the span from each edge."""
    (dx0, dx1), (dy0, dy1) = domain
    points = np.asarray(points, dtype=float)
    low, high = points.min(axis=0), points.max(axis=0)
    for _ in range(tries):
        y_span = rng.uniform(*window_test.Y_SPAN_M)
        x_span = y_span * rng.uniform(*ASPECT)
        if (high - low)[0] > (1 - 2 * MARGIN) * x_span or (high - low)[1] > (1 - 2 * MARGIN) * y_span:
            continue
        x0 = rng.uniform(high[0] + MARGIN * x_span - x_span, low[0] - MARGIN * x_span)
        y0 = rng.uniform(high[1] + MARGIN * y_span - y_span, low[1] - MARGIN * y_span)
        x0 = min(max(x0, dx0), dx1 - x_span)
        y0 = min(y0, dy1 - y_span)
        x1, y1 = x0 + x_span, y0 + y_span
        if not all(x0 + MARGIN * x_span <= px <= x1 - MARGIN * x_span
                   and y0 + MARGIN * y_span <= py <= y1 - MARGIN * y_span for px, py in points):
            continue
        inside = ((cells_xy[:, 0] >= x0) & (cells_xy[:, 0] <= x1)
                  & (cells_xy[:, 1] >= y0) & (cells_xy[:, 1] <= y1))
        if inside.sum() < MIN_CELLS:
            continue
        return [[float(x0), float(x1)], [float(y0), float(y1)]]
    return None


def choose(candidates, count, rng):
    """Spread the kept triples over the (speed, pressure) classes of the key, then over the
    region word, in a random order."""
    order = list(rng.permutation(len(candidates)))
    cap = -(-count // 9)
    kept, cells = [], Counter()
    for index in order:
        key = candidates[index]["truth"]
        cell = (key["max_speed_trend"], key["min_pressure_trend"])
        if cells[cell] < cap:
            kept.append(candidates[index])
            cells[cell] += 1
        if len(kept) == count:
            break
    if len(kept) < count:                       # rare classes exhausted: fill from the rest
        rest = [candidates[i] for i in order if candidates[i] not in kept]
        kept += rest[:count - len(kept)]
    return sorted(kept, key=lambda c: (c["gap"], c["triple"]))


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
    gaps = [int(g) for g in args.gaps.split(",")]
    steps = list(range(args.first_step, args.last_step + 1, args.every))
    fields = pt.read_states(builder, mesh, states, steps)
    rng = np.random.default_rng(args.seed)
    domain = mesh.views["full"]
    xy = mesh.centres[:, :2]
    peaks = {s: xy[int(np.argmax(np.linalg.norm(fields[s][0], axis=1)))] for s in steps}
    candidates = []
    for gap in gaps:
        for start in steps:
            triple = (start, start + gap, start + 2 * gap)
            if triple[-1] > args.last_step or any(s not in fields for s in triple):
                continue
            plotted = place_window_around(rng, [peaks[s] for s in triple], domain, xy)
            if plotted is None:
                continue
            truths = [pt.truth_from_arrays(mesh.centres, *fields[s], plotted, s, s * pt.DELTA_T_S) for s in triple]
            candidates.append({"gap": gap, "triple": triple, "plotted": plotted,
                               "truth": snapshot_runner.sequence_truth(truths), "frame_truths": truths})
    kept = choose(candidates, args.count, rng)
    designs = {}
    for item in kept:
        triple, plotted = item["triple"], item["plotted"]
        name = f"gap{item['gap']:06d}-steps{'-'.join(f'{s:06d}' for s in triple)}"
        mesh.views[name] = plotted
        truth = item["truth"]
        design = {"plotted_range_m": {"x": plotted[0], "y": plotted[1]},
                  "max_speed_m_per_s": truth["max_speed_first_last"],
                  "min_pressure_m2_per_s2": truth["min_pressure_first_last"],
                  "fastest_flow_moved_percent": truth["fastest_flow_moved_percent"]}
        frames2, numbers = [], []
        for k, s in enumerate(triple):
            frame, frame_truth = pt.render_v2(mesh, name, *fields[s], s, s * pt.DELTA_T_S,
                                              builder.frame_dir("dev-sequence", name, f"t{k + 1}-v2"))
            assert frame_truth == item["frame_truths"][k]
            frames2.append(frame)
            numbers.append(numbers_of(frame_truth))
        sources = {"frames": [f["directory"] for f in frames2], "state_steps": list(triple)}
        builder.add("dev-sequence-v2own", name, "sequence",
                    readable_request.sequence_v2_payload(frames2, own_ranges=True), truth, sources, design)
        builder.add("dev-sequence-v2own-t", name, "sequence",
                    readable_request.sequence_v2_payload(frames2, own_ranges=True, thresholds=True),
                    truth, sources, design)
        builder.add("dev-sequence-v2own-tn", name, "sequence",
                    readable_request.sequence_v2_payload(frames2, own_ranges=True, thresholds=True,
                                                         numbers=numbers), truth, sources, design)
        builder.add("dev-sequence-numbers", name, "sequence",
                    readable_request.sequence_v2_payload(frames2, own_ranges=True, thresholds=True,
                                                         numbers=numbers, images=False),
                    truth, dict(sources, images="none"), design)
        frames1 = []
        for k, s in enumerate(triple):
            frame, frame_truth = window_test.render_v1_window(
                mesh, plotted, *fields[s], s, s * pt.DELTA_T_S, builder.frame_dir("dev-sequence", name, f"t{k + 1}-v1"))
            for key in ("fastest_flow", "lowest_pressure"):
                for axis in ("x_percent", "y_percent"):
                    if abs(frame_truth[key][axis] - item["frame_truths"][k][key][axis]) > 1e-6:
                        raise RuntimeError(f"{name}: v1 and v2 answer keys differ for {key}")
            frames1.append(frame)
        builder.add("dev-sequence-v1", name, "sequence", pt.sequence_v1_payload(frames1), truth,
                    {"frames": [f["directory"] for f in frames1], "state_steps": list(triple)}, design)
        designs[name] = design
    write_json(builder.output / "truth.private.json", builder.truth)
    shutil.rmtree(builder.output / ".mpl", ignore_errors=True)
    linked = pt.link_duplicate_arrays(builder.output / "frames")
    here = Path(__file__).resolve().parent
    code = {name: pt.file_sha256(here / name) for name in
            ("sequence_test.py", "window_test.py", "picture_test.py", "frame_scoring.py", "readable_image.py",
             "readable_request.py", "foam_fields.py", "pod_image.py", "snapshot_runner.py", "llm_client.py")}
    counts = {name: sum(e["set"] == name for e in builder.entries) for name in NEW_SETS}
    classes = Counter((c["truth"]["max_speed_trend"], c["truth"]["min_pressure_trend"], c["truth"]["fastest_flow_region"])
                      for c in kept)
    manifest = {"schema_version": 2, "test": f"{TEST_NAME} (seed {args.seed})", "seed": args.seed,
                "max_tokens": pt.MAX_TOKENS, "sets": counts, "requests": builder.entries,
                "truth_sha256": pt.file_sha256(builder.output / "truth.private.json"),
                "build_args": dict(builder.rel(vars(args)), output=Path(args.output).name),
                "path_prefixes": {"": "frames/ and requests/ are in this test set",
                                  states.parent.name + "/": "the folder of the pimpleFoam run"},
                "mesh": builder.rel(mesh.sources), "domain_m": domain,
                "window_rule": {"peak_margin_fraction": MARGIN, "min_cells": MIN_CELLS,
                                "y_span_m": list(window_test.Y_SPAN_M), "aspect_x_over_y": list(ASPECT),
                                "note": "one window per triple, placed at random so that the fastest cell of "
                                        "every frame is at least the margin from each edge"},
                "trend_tolerances": {"relative_change": snapshot_runner.TREND_TOLERANCE,
                                     "region_percent": snapshot_runner.REGION_TOLERANCE_PCT},
                "candidates": len(candidates), "kept": len(kept),
                "classes_speed_pressure_region": {" / ".join(k): v for k, v in sorted(classes.items())},
                "code_sha256": code, "matplotlib": matplotlib.__version__, "numpy": np.__version__,
                "extra": {"oct17_numeric_summary": old["extra"]["oct17_numeric_summary"],
                          "flow_states": builder.extra["flow_states"], "designs": designs},
                "identical_arrays_hard_linked": linked, "truth_withheld_from_model": True,
                "model_name_in_bodies": pt.DEFAULT_MODEL,
                "note": "Same renderers and scoring as picture-test-20261021; the -t sets state the key's "
                        "thresholds in the prompt, -tn and numbers add the extrema from the arrays. The "
                        "runner replaces only the model name."}
    write_json(builder.output / "manifest.json", manifest)
    print(encode_json({"output": str(builder.output), "requests": len(builder.entries), "sets": counts,
                       "candidates": len(candidates), "classes": manifest["classes_speed_pressure_region"]}).decode())
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    pt.SETS = tuple(pt.SETS) + NEW_SETS
    pt.PAIRED_SETS = tuple(pt.PAIRED_SETS) + (
        ("dev-sequence-v2own", "dev-sequence-v2own-t"), ("dev-sequence-v2own-t", "dev-sequence-v2own-tn"),
        ("dev-sequence-numbers", "dev-sequence-v2own-tn"), ("dev-sequence-v1", "dev-sequence-v2own-t"))
    if argv and argv[0] == "build":
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("command")
        parser.add_argument("--states", required=True, help="case with the written time directories")
        parser.add_argument("--centres", required=True, help="fields.npz of a saved frame of the same mesh")
        parser.add_argument("--old-manifest", required=True, help="picture-test-20261021/manifest.json")
        parser.add_argument("--first-step", type=int, default=64000)
        parser.add_argument("--every", type=int, default=2000, help="step between written states")
        parser.add_argument("--last-step", type=int, default=200000)
        parser.add_argument("--gaps", default="2000,4000,6000", help="steps between the frames of a triple")
        parser.add_argument("--count", type=int, default=45, help="triples kept")
        parser.add_argument("--y-span", default=f"{window_test.Y_SPAN_M[0]},{window_test.Y_SPAN_M[1]}",
                            help="window height range in metres (the step case: 0.03,0.114)")
        parser.add_argument("--dt", type=float, default=pt.DELTA_T_S,
                            help="time step the state names are divided by (step = time / dt)")
        parser.add_argument("--seed", type=int, default=SEED)
        parser.add_argument("--output", required=True, help="new directory")
        args = parser.parse_args(argv)
        pt.DELTA_T_S = args.dt
        window_test.Y_SPAN_M = tuple(float(v) for v in args.y_span.split(","))
        return build(args)
    return pt.main(argv)


if __name__ == "__main__":
    sys.exit(main())
