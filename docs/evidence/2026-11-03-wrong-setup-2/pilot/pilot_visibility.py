#!/usr/bin/env python3
"""Is a change visible inside the window? For each wrong pilot run, the share of window pixels whose
place on the colour bar differs by more than 16 of 256 levels from the base's normal run (P-N3) at the
same step, for |U| and p. The noise reference is the same measure between P-N3's own steps 6000, 7000
and 8000 (how much a normal run moves in time). Reads the pilot test set built by wrong_setup_test2.py.
Usage: pilot_visibility.py <test set> <output.json>
"""
import json
from pathlib import Path
import sys

import numpy as np
from matplotlib import colormaps
from matplotlib.image import imread

ROWS, COLS = (82, 506), (78, 855)
SCALE = np.rint(colormaps["viridis"](np.arange(256))[:, :3] * 255).astype(np.int64)


def positions(png):
    rgb = np.rint(imread(png)[ROWS[0]:ROWS[1], COLS[0]:COLS[1], :3] * 255).astype(np.int64)
    flat = rgb.reshape(-1, 3)
    unique, inverse = np.unique(flat[:, 0] * 65536 + flat[:, 1] * 256 + flat[:, 2], return_inverse=True)
    colours = np.stack([unique >> 16, (unique >> 8) & 255, unique & 255], axis=1)
    distance = np.abs(colours[:, None, :] - SCALE[None, :, :]).max(axis=2)
    nearest = np.where(distance.min(axis=1) <= 16, distance.argmin(axis=1), -1)
    return nearest[inverse].reshape(rgb.shape[:2])


def differs(a, b):
    both = (a >= 0) & (b >= 0)
    return float((np.abs(a - b)[both] > 16).sum() / both.sum())


def main(root, output):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    frames = {}
    for e in manifest["requests"]:
        frames[(e["design"]["run"], e["design"]["run_step"])] = root / e["sources"]["frame"]
    runs = sorted({r for r, _ in frames})
    steps = sorted({s for _, s in frames})
    cache = {}

    def pos(run, step, field):
        key = (run, step, field)
        if key not in cache:
            cache[key] = positions(frames[(run, step)] / f"{field}.png")
        return cache[key]

    out = {"what": __doc__.strip().splitlines()[0], "noise_P-N3_between_steps": {}, "wrong_vs_P-N3_same_step": {}}
    for field in ("U", "p"):
        out["noise_P-N3_between_steps"][field] = {f"{a}-{b}": differs(pos("P-N3", a, field), pos("P-N3", b, field))
                                                  for a in steps for b in steps if a < b}
    for run in runs:
        if run.startswith("P-N"):
            continue
        out["wrong_vs_P-N3_same_step"][run] = {field: {str(s): differs(pos(run, s, field), pos("P-N3", s, field)) for s in steps}
                                              for field in ("U", "p")}
    Path(output).write_text(json.dumps(out, indent=1))
    noise = {f: max(v.values()) for f, v in out["noise_P-N3_between_steps"].items()}
    print(f"noise (largest between P-N3's steps): U {noise['U']:.3f}, p {noise['p']:.3f}")
    for run, d in out["wrong_vs_P-N3_same_step"].items():
        u, p = d["U"][str(max(steps))], d["p"][str(max(steps))]
        print(f"{run:28s} U {u:.3f}  p {p:.3f}  {'VISIBLE' if u > 2 * noise['U'] or p > 2 * noise['p'] else 'not visible'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
