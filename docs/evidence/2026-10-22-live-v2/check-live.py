#!/usr/bin/env python3
"""Re-check the live v2 run of 2026-10-22 from the files in this folder.

Run in this folder:  python3 check-live.py   (needs numpy; writes check-live.json)

1. Each request body sent equals the request builder of the executed callback
   (suite/executed-callback-source/readable_request.py) applied to the saved frame, byte for byte:
   the describe body of the suite and of every sweep case, and the sequence body. The suite's two
   bodies are in this folder and are compared directly; for the sweep the rebuilt body's SHA-256 is
   compared with the one the client recorded for the body it sent (llm_result.json, request_sha256).
   The suite bodies' hashes are also checked against their records.
2. Each frame's pictures and arrays have the hashes in its metadata.
3. Where the answers are right, recomputed from the frame arrays without picture_test.py: the
   fastest cell and the lowest-pressure cell among the cells whose centres lie in the plotted range,
   as percent of that range; the distance to each answer; and the sequence's trend words: the
   change from the first to the last time relative to the larger of the two magnitudes, roughly
   constant within 2 %; the fastest cell 'moves' if the first and last positions are more than
   5 % of the plotted range apart.
4. The one fixed answer that would do best over the sweep (best integer answer within 10 %).
The values are compared with sweep-summary.json and suite/async-verification.json.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True   # leave the recorded sources as they are
sys.path.insert(0, str(HERE / "suite" / "executed-callback-source"))
import readable_request  # noqa: E402
from llm_client import encode_json  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frame(folder):
    meta = json.loads((folder / "readable-metadata.json").read_text())
    for image in meta["images"]:
        assert sha(folder / image["path"]) == image["sha256"], folder
    assert sha(folder / meta["fields_npz"]) == meta["fields_sha256"], folder
    with np.load(folder / meta["fields_npz"]) as data:
        arrays = {k: np.array(data[k]) for k in ("centres", "U", "p")}
    return readable_request.frame_from_metadata(folder, meta), meta, arrays


def extremes(meta, arrays):
    (x0, x1), (y0, y1) = meta["plotted_range_m"]["x"], meta["plotted_range_m"]["y"]
    c = arrays["centres"]
    inside = (c[:, 0] >= x0) & (c[:, 0] <= x1) & (c[:, 1] >= y0) & (c[:, 1] <= y1)
    index = np.flatnonzero(inside)
    speed = np.linalg.norm(arrays["U"], axis=1)
    fast = index[np.argmax(speed[index])]
    low = index[np.argmin(arrays["p"][index])]

    def percent(i):
        return [100 * (c[i, 0] - x0) / (x1 - x0), 100 * (c[i, 1] - y0) / (y1 - y0)]
    return {"cells": int(inside.sum()), "fastest_flow": percent(fast), "lowest_pressure": percent(low),
            "max_speed": float(speed[index].max()), "min_pressure": float(arrays["p"][index].min())}


def distance(answer, truth):
    return math.hypot(answer[0] - truth[0], answer[1] - truth[1])


def sent_body_matches(folder, rebuilt, result):
    """The rebuilt body equals the body sent: by bytes when the body is here, else by the recorded hash."""
    recorded = result["request_sha256"]
    path = folder / "llm_request_body.json"
    if path.exists():
        body = path.read_bytes()
        return body == rebuilt and hashlib.sha256(body).hexdigest() == recorded
    return hashlib.sha256(rebuilt).hexdigest() == recorded


def describe_case(folder, step):
    f, meta, arrays = frame(folder / "llm_observation" / f"step-{step:06d}")
    result = json.loads((folder / "llm_result.json").read_text())
    model = json.loads((folder / "llm_request.json").read_text())["request"]["model"]
    parity = sent_body_matches(folder, encode_json(readable_request.describe_v2_payload(f, model=model)), result)
    truth = extremes(meta, arrays)
    so = result.get("structured_output") or {}
    out = {"body_equals_builder": parity, "status": result["status"], "truth_percent": {
        k: [round(v, 2) for v in truth[k]] for k in ("fastest_flow", "lowest_pressure")}}
    if so:
        for k in ("fastest_flow", "lowest_pressure"):
            out[k + "_answer"] = [so[f"{k}_x_percent"], so[f"{k}_y_percent"]]
            out[k + "_distance_percent"] = round(distance(out[k + "_answer"], truth[k]), 2)
    return out, truth


def main():
    report = {}
    # the suite: describe (the server-error and timeout bodies are the same bytes, see README)
    suite = HERE / "suite"
    report["suite_describe"], _ = describe_case(suite / "async-describe", 250)
    verification = json.loads((suite / "async-verification.json").read_text())
    recorded = verification["async-describe"]["score"]["scores"]
    for k in ("fastest_flow", "lowest_pressure"):
        assert abs(report["suite_describe"][k + "_distance_percent"] - recorded[k]["distance_percent"]) < 0.01, k
    # the suite: sequence
    folder = suite / "async-sequence"
    loaded = [frame(folder / "llm_observation" / f"step-{s:06d}") for s in (3000, 3250, 3750)]
    result = json.loads((folder / "llm_result.json").read_text())
    model = json.loads((folder / "llm_request.json").read_text())["request"]["model"]
    parity = sent_body_matches(folder, encode_json(readable_request.sequence_v2_payload(
        [f for f, _, _ in loaded], model=model, own_ranges=True)), result)
    truths = [extremes(meta, arrays) for _, meta, arrays in loaded]
    def change(first, last):
        return (last - first) / max(abs(first), abs(last))
    speed = change(truths[0]["max_speed"], truths[-1]["max_speed"])
    low = change(truths[0]["min_pressure"], truths[-1]["min_pressure"])
    moved = distance(truths[0]["fastest_flow"], truths[-1]["fastest_flow"])
    words = {"max_speed_trend": "roughly_constant" if abs(speed) < 0.02 else ("increasing" if speed > 0 else "decreasing"),
             "min_pressure_trend": "roughly_constant" if abs(low) < 0.02 else ("less_negative" if low > 0 else "more_negative"),
             "fastest_flow_region": "moves" if moved > 5.0 else "same_place"}
    answer = json.loads((folder / "llm_result.json").read_text())["structured_output"]
    report["suite_sequence"] = {"body_equals_builder": parity, "truth": words,
                                "max_speed_first_last": [round(truths[0]["max_speed"], 3), round(truths[-1]["max_speed"], 3)],
                                "min_pressure_first_last": [round(truths[0]["min_pressure"], 2), round(truths[-1]["min_pressure"], 2)],
                                "fastest_cell_moved_percent": round(moved, 2),
                                "answer": {k: answer[k] for k in words},
                                "right": {k: answer[k] == v for k, v in words.items()}}
    assert words == {k: verification["async-sequence"]["score"]["truth"][k] for k in words}
    # the sweep
    summary = json.loads((HERE / "sweep" / "sweep-summary.json").read_text())
    rows, points = [], {"fastest_flow": [], "lowest_pressure": []}
    for case in summary["cases"]:
        out, truth = describe_case(HERE / "sweep" / case["name"], case["request_step"])
        for k in points:
            points[k].append(truth[k])
            if case["status"] == "ok":
                assert abs(out[k + "_distance_percent"] - case["scores"][k]["distance_percent"]) < 0.01, (case["name"], k)
        rows.append(dict(out, name=case["name"], arrived_at_step=case["arrived_at_step"]))
    fixed = {k: max(sum(distance((x, y), p) <= 10.0 for p in pts) for x in range(101) for y in range(101))
             for k, pts in points.items()}
    report["sweep"] = {"cases": rows, "requests": len(rows),
                       "bodies_equal_builder": sum(r["body_equals_builder"] for r in rows),
                       "fastest_flow_within_10": sum(r.get("fastest_flow_distance_percent", 99) <= 10 for r in rows),
                       "lowest_pressure_within_10": sum(r.get("lowest_pressure_distance_percent", 99) <= 10 for r in rows),
                       "one_fixed_answer": fixed}
    (HERE / "check-live.json").write_text(json.dumps(report, indent=1) + "\n")
    ok = (report["suite_describe"]["body_equals_builder"] and parity
          and report["sweep"]["bodies_equal_builder"] == len(rows))
    print(json.dumps({"suite_describe": {k: v for k, v in report["suite_describe"].items()},
                      "suite_sequence_right": report["suite_sequence"]["right"],
                      "sweep": {k: v for k, v in report["sweep"].items() if k != "cases"}}, indent=1))
    print("all bodies equal the builder" if ok else "SOME BODIES DIFFER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
