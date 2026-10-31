#!/usr/bin/env python3
"""How far the five normal runs are one trajectory: the normal frames that show the same time of the
developed flow (start state + steps x 5e-6 s), compared array by array and picture by picture.

Usage: normal_overlap.py <test set> <developed run> <output.json>   (numpy; reads frames/<run>/<time>/)
For each pair of normal frames at one flow time: the largest difference of |U| and of p over all cells,
and the share of picture pixels that differ inside the plot area (the title holds the step and time and
differs). Also each state's largest difference from the developed run's written state at that time.
"""
import json
from pathlib import Path
import sys
import zlib

import numpy as np

START = {"N1": 0.06, "N2": 0.07, "N3": 0.08, "N4": 0.09, "N5": 0.1}
STEPS = range(4500, 8001, 500)
DT = 5e-6


def read_png_rgba(path):
    """8-bit RGBA PNG without a PNG library (matplotlib writes these): pixels as (height, width, 4)."""
    data = Path(path).read_bytes()
    offset, idat, width, height = 8, bytearray(), None, None
    while offset < len(data):
        size = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        body = data[offset + 8:offset + 8 + size]
        if kind == b"IHDR":
            width, height = int.from_bytes(body[:4], "big"), int.from_bytes(body[4:8], "big")
            assert body[8:10] == b"\x08\x06", "8-bit RGBA expected"
        elif kind == b"IDAT":
            idat += body
        offset += 12 + size
    raw = np.frombuffer(zlib.decompress(bytes(idat)), dtype=np.uint8).reshape(height, 1 + 4 * width)
    out = np.zeros((height, 4 * width), dtype=np.int32)
    for y in range(height):
        kind, line = raw[y, 0], raw[y, 1:].astype(np.int32)
        previous = out[y - 1] if y else np.zeros(4 * width, dtype=np.int32)
        if kind == 0:
            out[y] = line
        elif kind == 2:
            out[y] = (line + previous) & 255
        else:
            row = np.zeros(4 * width, dtype=np.int32)
            for x in range(4 * width):
                a = row[x - 4] if x >= 4 else 0
                b = previous[x]
                c = previous[x - 4] if x >= 4 else 0
                if kind == 1:
                    predict = a
                elif kind == 3:
                    predict = (a + b) // 2
                else:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    predict = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[x] = (line[x] + predict) & 255
            out[y] = row
    return out.reshape(height, width, 4)


def read_internal(path, cells, vector):
    text = Path(path).read_text()
    head = text.index("internalField")
    start = text.index("(", text.index(str(cells), head))
    lines = text[start + 1:].split("\n", cells + 1)[:cells + 1]
    if vector:
        return np.array([[float(v) for v in line.strip("()").split()] for line in lines[1:]])
    return np.array([float(line) for line in lines[1:]])


def main(root, long_run, output):
    root, long_run = Path(root), Path(long_run)
    frames = {}
    for run, start in START.items():
        for step in STEPS:
            flow_time = round(start + step * DT, 6)
            frames.setdefault(flow_time, []).append((run, step))
    pairs, against_long = [], []
    cache = {}

    def arrays(run, step):
        key = (run, step)
        if key not in cache:
            name = f"{0.1 + step * DT:.10g}"
            with np.load(root / "frames" / run / name / "fields.npz", allow_pickle=False) as data:
                cache[key] = (np.linalg.norm(data["U"], axis=1), np.array(data["p"]), root / "frames" / run / name)
        return cache[key]

    for flow_time, members in sorted(frames.items()):
        first = arrays(*members[0])
        for other in members[1:]:
            second = arrays(*other)
            row = {"flow_time_s": flow_time, "a": f"{members[0][0]} step {members[0][1]}", "b": f"{other[0]} step {other[1]}",
                   "max_abs_diff_speed_m_per_s": float(np.abs(first[0] - second[0]).max()),
                   "max_abs_diff_p_m2_per_s2": float(np.abs(first[1] - second[1]).max())}
            for field in ("U", "p"):
                a, b = read_png_rgba(first[2] / f"{field}.png"), read_png_rgba(second[2] / f"{field}.png")
                # the plot and its colour bar: below the two title lines (y from 70 px on)
                row[f"pixels_differing_below_the_title_{field}"] = int((a[70:] != b[70:]).any(axis=2).sum())
            pairs.append(row)
        if flow_time <= 0.1 + 1e-9:
            name = f"{flow_time:g}"
            if (long_run / name / "U").exists():
                cells = first[0].size
                speed = np.linalg.norm(read_internal(long_run / name / "U", cells, True), axis=1)
                pressure = read_internal(long_run / name / "p", cells, False)
                against_long.append({"flow_time_s": flow_time, "frame": f"{members[0][0]} step {members[0][1]}",
                                     "max_abs_diff_speed_m_per_s": float(np.abs(first[0] - speed).max()),
                                     "max_abs_diff_p_m2_per_s2": float(np.abs(first[1] - pressure).max())})
    summary = {"normal_frames": sum(len(m) for m in frames.values()), "different_flow_times": len(frames),
               "frames_per_flow_time": {str(k): [f"{r} step {s}" for r, s in v] for k, v in sorted(frames.items())},
               "pairs_at_one_flow_time": len(pairs),
               "largest_diff_speed_m_per_s": max(p["max_abs_diff_speed_m_per_s"] for p in pairs),
               "largest_diff_p_m2_per_s2": max(p["max_abs_diff_p_m2_per_s2"] for p in pairs),
               "largest_pixels_differing_below_the_title": max(max(p["pixels_differing_below_the_title_U"], p["pixels_differing_below_the_title_p"]) for p in pairs),
               "pairs": pairs, "against_the_developed_run": against_long}
    Path(output).write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("pairs", "frames_per_flow_time", "against_the_developed_run")}, indent=1))
    print(against_long[:3])


if __name__ == "__main__":
    main(*sys.argv[1:4])
