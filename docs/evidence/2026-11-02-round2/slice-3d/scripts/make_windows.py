#!/usr/bin/env python3
"""Test set of the 3D slice test (r2/slice-3d): the solver's slice frames as drawn, and random
windows drawn from each frame's slice arrays with the solver's renderer. Writes requests, truth
and manifest, and the constant-answer baseline from the arrays, before any model runs.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

SEED = 20261101
WINDOWS_PER_FRAME = 2
MARGIN = 0.15            # window-test rule of 2026-10-22
MIN_CELLS = 200
Y_SPAN_M = (0.03, 0.114)
ASPECT = (1.5, 4.0)
RUNS = ("z1", "z3", "z5", "z7")
MODEL = "gemma-4-12b-it-qat-q4_0-vision"
ANSWER_GRID = np.stack(np.meshgrid(np.arange(101.0), np.arange(101.0)), -1).reshape(-1, 1, 2)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def place_window(rng, peak, domain, cells_xy):
    """window_test.place_window (2026-10-22), unchanged."""
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


def baseline(keys):
    """One integer answer for all keys: the most keys within 10 %."""
    out = {}
    for target in ("fastest_flow", "lowest_pressure"):
        points = np.array([(k[target]["x_percent"], k[target]["y_percent"]) for k in keys])
        hits = (np.hypot(*(ANSWER_GRID - points).transpose(2, 0, 1)) <= 10.0).sum(axis=1)
        best = int(hits.argmax())
        out[target] = {"right": int(hits[best]), "of": len(keys),
                       "answer_percent": [float(ANSWER_GRID[best, 0, 0]), float(ANSWER_GRID[best, 0, 1])]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wt", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--design", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    demo = Path(args.wt) / "Solver_Examples/PODFoam/llm_demo"
    sys.path.insert(0, str(demo))
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    os.environ["MPLCONFIGDIR"] = str(out / ".mpl")
    os.environ["MPLBACKEND"] = "Agg"
    import pod_image
    pod_image.prepare_backend(out / ".mpl")
    import readable_request
    from frame_scoring import truth_from_arrays
    from llm_client import encode_json, write_json

    rng = np.random.default_rng(SEED)
    entries, truth = [], {}
    code = {name: sha256((demo / name).read_bytes()) for name in
            ("readable_request.py", "readable_image.py", "frame_scoring.py", "llm_client.py", "pod_image.py",
             "python_module.py")}

    def add(set_name, name, payload, key, sources, design):
        d = out / "requests" / set_name
        d.mkdir(parents=True, exist_ok=True)
        body = encode_json(payload)
        (d / f"{name}.request.json").write_bytes(body)
        truth[f"{set_name}/{name}"] = key
        entries.append({"set": set_name, "name": name, "mode": "describe",
                        "file": f"requests/{set_name}/{name}.request.json",
                        "request_sha256": sha256(body), "request_bytes": len(body),
                        "seed": payload.get("seed"), "cache_prompt": payload.get("cache_prompt"),
                        "sources": sources, "design": design})

    for run in RUNS:
        case = Path(args.run) / run
        z = float((case / "slice-z.txt").read_text().strip())
        frames = sorted((case / "llm_observation").glob("step-*"))
        print(f"{run}: z={z} frames={[f.name for f in frames]}", flush=True)
        for fdir in frames:
            frame, meta, fields = readable_request.load_frame(fdir)
            assert "slice" in meta, f"{fdir}: not a slice frame"
            plotted = [meta["plotted_range_m"]["x"], meta["plotted_range_m"]["y"]]
            centres, U, p = fields["centres"], fields["U"], fields["p"]
            key = truth_from_arrays(centres, U, p, plotted, meta["step"], meta["time_s"])
            key["slice"] = meta["slice"]
            design = {"run": run, "slice_z_m": z, "slice_record": meta["slice"], "step": meta["step"],
                      "time_s": meta["time_s"], "plotted_range_m": meta["plotted_range_m"],
                      "cells_in_window": key["cells_in_window"]}
            name = f"{run}-step{meta['step']:06d}"
            add("solver", name, readable_request.describe_v2_payload(frame, model=MODEL), key,
                {"frame": str(fdir), "fields_sha256": meta["fields_sha256"],
                 "image_sha256": frame["image_sha256"]}, design)
            polygons = {"points": fields["polygon_points"], "offsets": fields["polygon_offsets"],
                        "cells": np.arange(centres.shape[0], dtype=np.int64)}
            domain = [[float(centres[:, 0].min()), float(centres[:, 0].max())],
                      [float(centres[:, 1].min()), float(centres[:, 1].max())]]
            speed = np.linalg.norm(U, axis=1)
            peak = centres[int(np.argmax(speed)), :2]
            for k in range(WINDOWS_PER_FRAME):
                wname = f"{name}-w{k + 1}"
                window = place_window(rng, peak, domain, centres[:, :2])
                wdir = out / "frames" / "window" / wname
                wframe, wmeta = readable_request.render_frame(
                    wdir, centres, polygons, U, p, window, meta["step"], meta["time_s"],
                    view="window", domain_extent=domain,
                    plane_slice={"record": meta["slice"], "mesh_cells": fields["mesh_cells"]})
                wkey = truth_from_arrays(centres, U, p, window, meta["step"], meta["time_s"])
                wkey["slice"] = meta["slice"]
                add("window", wname, readable_request.describe_v2_payload(wframe, model=MODEL), wkey,
                    {"frame": str(wdir), "source_frame": str(fdir), "fields_sha256": wmeta["fields_sha256"],
                     "image_sha256": wframe["image_sha256"]},
                    dict(design, plotted_range_m=wmeta["plotted_range_m"], cells_in_window=wkey["cells_in_window"],
                         window_seed=SEED, window_index=k + 1))
    write_json(out / "truth.json", truth)
    sets = sorted({e["set"] for e in entries})
    base = {s: baseline([truth[f"{e['set']}/{e['name']}"] for e in entries if e["set"] == s]) for s in sets}
    base["all"] = baseline(list(truth.values()))
    write_json(out / "baseline.json", base)
    manifest = {"test": "r2/slice-3d 3D slice picture test 2026-11-01", "design": json.loads(Path(args.design).read_text()),
                "seed": SEED, "windows_per_frame": WINDOWS_PER_FRAME, "model": MODEL,
                "sets": {s: sum(e["set"] == s for e in entries) for s in sets},
                "requests": entries, "truth_sha256": sha256((out / "truth.json").read_bytes()),
                "code_sha256": code, "worktree_head": (Path(args.run) / "HEAD").read_text().strip()}
    write_json(out / "manifest.json", manifest)
    print(json.dumps({"sets": manifest["sets"], "baseline": base}, indent=1))


if __name__ == "__main__":
    main()
