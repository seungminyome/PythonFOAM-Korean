#!/usr/bin/env python3
"""Where did 12B put the lowest pressure when it missed in the cylinder set, and how much does the
flow change between the ten states?

Usage: cylinder_misses.py <cylinder-window-test-20261027 folder> [output json]
       (the test set is cylinder-window-test-20261027.tar.gz of the release; needs numpy)
For every v2 lowest-pressure answer of 12B more than 10 % off: the answered point in metres, the
pressure at the nearest cell inside the plotted range relative to the true minimum, and where it is
relative to the cylinder (radius 1 m, centre at the origin; the flow comes from -x): behind it
(x > 1 m), at its lower rear (0.7 to 1 m) or below it (otherwise). Also the largest difference of
|U| and p between any of the ten states.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def main(tests, out=None):
    tests = Path(tests)
    manifest = json.loads((tests / "manifest.json").read_text())
    requests = {(r["set"], r["name"]): r for r in manifest["requests"]}
    truth = json.loads((tests / "truth.private.json").read_text())
    rows = [json.loads(line) for line in
            (HERE / "results" / "window-test-24903978" / "12b" / "flow-window-v2" / "metrics.jsonl").read_text().splitlines()
            if line.strip()]
    misses = []
    frames = {}
    for r in rows:
        score = r["scores"]["lowest_pressure"]
        frame = tests / requests[("flow-window-v2", r["name"])]["sources"]["frame"]
        if frame not in frames:
            with np.load(frame / "fields.npz") as z:
                frames[frame] = (np.array(z["centres"]), np.array(z["U"]), np.array(z["p"]))
        if score["within_10_percent"]:
            continue
        c, _, p = frames[frame]
        key = truth[f"flow-window-v2/{r['name']}"]
        (x0, x1), (y0, y1) = key["plotted_range_m"]["x"], key["plotted_range_m"]["y"]
        inside = np.flatnonzero((c[:, 0] >= x0) & (c[:, 0] <= x1) & (c[:, 1] >= y0) & (c[:, 1] <= y1))
        ax, ay = score["answer_percent"]
        X, Y = x0 + ax / 100 * (x1 - x0), y0 + ay / 100 * (y1 - y0)
        i = inside[np.argmin((c[inside, 0] - X) ** 2 + (c[inside, 1] - Y) ** 2)]
        where = "behind" if X > 1.0 else ("lower rear" if X >= 0.7 else "below")
        misses.append({"request": r["name"], "answer_m": [round(X, 3), round(Y, 3)], "where": where,
                       "p_ratio_to_minimum": round(float(p[i] / p[inside].min()), 3)})
    arrays = list(frames.values())
    speed = [np.linalg.norm(a[1], axis=1) for a in arrays]
    result = {"misses": len(misses),
              "where": {w: sum(m["where"] == w for m in misses) for w in ("behind", "lower rear", "below")},
              "requests": misses,
              "states": len(arrays),
              "largest_difference_between_states": {
                  "speed_m_per_s": float(max(np.abs(a - b).max() for a in speed for b in speed)),
                  "p_m2_per_s2": float(max(np.abs(a[2] - b[2]).max() for a in arrays for b in arrays))}}
    text = json.dumps(result, indent=1) + "\n"
    if out:
        Path(out).write_text(text)
    print(result["misses"], result["where"], result["largest_difference_between_states"])


if __name__ == "__main__":
    main(*sys.argv[1:])
