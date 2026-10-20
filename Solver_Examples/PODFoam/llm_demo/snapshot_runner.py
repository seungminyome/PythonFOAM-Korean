#!/usr/bin/env python3
"""Replay saved snapshots through the describe and sequence prompts and score the answers.

describe: one request per frame; the answer's percent positions of the
fastest flow and the lowest pressure are compared with the saved arrays.
sequence: one request with all frames in time order; the answer's trend words
are compared with the trends of the saved extrema.

Offline preparation is the default; --execute sends the requests to the local
server. Nothing here runs the solver or changes a solver setting.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from ablation_runner import png_text
from llm_client import (DEFAULT_ENDPOINT, DEFAULT_MODEL, TREND_PRESSURE, TREND_REGION,
                        TREND_SPEED, build_request, build_sequence_request, encode_json,
                        request_local, write_json)

TREND_TOLERANCE = 0.02        # relative change below this is "roughly_constant"
REGION_TOLERANCE_PCT = 5.0    # argmax moving less than this (percent of plotted range) is "same_place"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_frame(directory):
    """One saved snapshot: PNG, arrays and metadata that belong together."""
    directory = Path(directory).resolve()
    meta = json.loads((directory / "image-metadata.json").read_text())
    png = (directory / "state.png").read_bytes()
    fields_bytes = (directory / "fields.npz").read_bytes()
    if meta["sha256"] != sha256(png) or meta["fields_sha256"] != sha256(fields_bytes):
        raise ValueError(f"{directory}: PNG or arrays differ from the metadata hashes")
    embedded = png_text(png)
    if embedded.get("FieldsSHA256") != meta["fields_sha256"]:
        raise ValueError(f"{directory}: PNG provenance is not bound to these arrays")
    with np.load(directory / "fields.npz", allow_pickle=False) as arrays:
        centres, velocity, pressure = arrays["centres"], arrays["U"], arrays["p"]
        step, time_s = int(arrays["step"]), float(arrays["time_s"])
    if step != meta["step"] or time_s != meta["time_s"]:
        raise ValueError(f"{directory}: step/time mismatch between arrays and metadata")
    axes = meta["projection_axes"]
    plotted = meta.get("plotted_range_m", meta["domain_extent_m"])
    x = centres[:, "xyz".index(axes[0])]
    y = centres[:, "xyz".index(axes[1])]
    (x0, x1), (y0, y1) = plotted[axes[0]], plotted[axes[1]]
    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    speed = np.linalg.norm(velocity, axis=1)
    if not (np.isfinite(speed).all() and np.isfinite(pressure).all()):
        raise ValueError(f"{directory}: nonfinite fields")
    index = np.flatnonzero(inside)

    def percent(cell):
        return {"x_percent": 100.0 * (x[cell] - x0) / (x1 - x0),
                "y_percent": 100.0 * (y[cell] - y0) / (y1 - y0),
                "x_m": float(x[cell]), "y_m": float(y[cell]), "cell": int(cell)}

    fastest = index[np.argmax(speed[index])]
    lowest = index[np.argmin(pressure[index])]
    truth = {"step": step, "time_s": time_s, "cells_in_window": int(inside.sum()),
             "max_speed_m_per_s": float(speed[index].max()),
             "min_pressure_m2_per_s2": float(pressure[index].min()),
             "fastest_flow": percent(fastest), "lowest_pressure": percent(lowest),
             "plotted_range_m": plotted, "projection_axes": axes,
             "x_span_m": x1 - x0, "y_span_m": y1 - y0}
    frame = {"path": str(directory / "state.png"), "directory": str(directory),
             "step": step, "time_s": time_s, "sha256": meta["sha256"],
             "fields_sha256": meta["fields_sha256"], "cells": meta["cells"],
             "projection_axes": axes, "domain_extent_m": meta["domain_extent_m"],
             "plotted_range_m": plotted, "panels": meta["panels"]}
    return frame, truth


def describe_payload(frame, model, seed, max_tokens):
    summary = {"step": frame["step"], "time_s": frame["time_s"], "cells": frame["cells"],
               "image": {"projection_axes": frame["projection_axes"],
                         "domain_extent_m": frame["domain_extent_m"],
                         "plotted_range_m": frame["plotted_range_m"],
                         "panels": frame["panels"]}}
    request = build_request(summary, frame["path"], mode="describe")
    request.update(model=model, seed=seed, max_tokens=max_tokens)
    return request


def sequence_payload(frames, model, seed, max_tokens):
    request = build_sequence_request(frames)
    request.update(model=model, seed=seed, max_tokens=max_tokens)
    return request


def trend(first, last, tolerance=TREND_TOLERANCE):
    scale = max(abs(first), abs(last), 1e-300)
    change = (last - first) / scale
    if change > tolerance:
        return "increasing", change
    if change < -tolerance:
        return "decreasing", change
    return "roughly_constant", change


def sequence_truth(truths):
    first, last = truths[0], truths[-1]
    speed_trend, speed_change = trend(first["max_speed_m_per_s"], last["max_speed_m_per_s"])
    pressure_word, pressure_change = trend(first["min_pressure_m2_per_s2"],
                                           last["min_pressure_m2_per_s2"])
    # for the pressure minimum the vocabulary is about the sign direction
    pressure_trend = {"increasing": "less_negative", "decreasing": "more_negative",
                      "roughly_constant": "roughly_constant"}[pressure_word]
    if first["min_pressure_m2_per_s2"] >= 0 and last["min_pressure_m2_per_s2"] >= 0:
        pressure_trend = "roughly_constant" if pressure_word == "roughly_constant" else (
            "more_negative" if pressure_word == "decreasing" else "less_negative")
    moved = math.hypot(last["fastest_flow"]["x_percent"] - first["fastest_flow"]["x_percent"],
                       last["fastest_flow"]["y_percent"] - first["fastest_flow"]["y_percent"])
    return {"max_speed_trend": speed_trend, "max_speed_relative_change": speed_change,
            "max_speed_first_last": [first["max_speed_m_per_s"], last["max_speed_m_per_s"]],
            "min_pressure_trend": pressure_trend, "min_pressure_relative_change": pressure_change,
            "min_pressure_first_last": [first["min_pressure_m2_per_s2"], last["min_pressure_m2_per_s2"]],
            "fastest_flow_region": "same_place" if moved <= REGION_TOLERANCE_PCT else "moves",
            "fastest_flow_moved_percent": moved,
            "tolerances": {"relative_change": TREND_TOLERANCE, "region_percent": REGION_TOLERANCE_PCT},
            "frames": [{"step": t["step"], "time_s": t["time_s"], "max_speed_m_per_s": t["max_speed_m_per_s"],
                        "min_pressure_m2_per_s2": t["min_pressure_m2_per_s2"],
                        "fastest_flow_percent": [t["fastest_flow"]["x_percent"], t["fastest_flow"]["y_percent"]]}
                       for t in truths]}


def score_describe(structured, truth):
    out = {}
    for name in ("fastest_flow", "lowest_pressure"):
        dx = structured[f"{name}_x_percent"] - truth[name]["x_percent"]
        dy = structured[f"{name}_y_percent"] - truth[name]["y_percent"]
        out[name] = {"answer_percent": [structured[f"{name}_x_percent"], structured[f"{name}_y_percent"]],
                     "true_percent": [truth[name]["x_percent"], truth[name]["y_percent"]],
                     "error_percent": [dx, dy], "distance_percent": math.hypot(dx, dy),
                     "error_m": [dx / 100.0 * truth["x_span_m"], dy / 100.0 * truth["y_span_m"]],
                     "distance_m": math.hypot(dx / 100.0 * truth["x_span_m"], dy / 100.0 * truth["y_span_m"]),
                     "within_10_percent": math.hypot(dx, dy) <= 10.0}
    return out


def score_sequence(structured, truth):
    out = {}
    for name in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region"):
        out[name] = {"answer": structured[name], "truth": truth[name],
                     "match": structured[name] == truth[name],
                     "cannot_tell": structured[name] == "cannot_tell"}
    out["matches"] = sum(v["match"] for v in out.values() if isinstance(v, dict))
    return out


def run_trial(payload, output, mode, truth, endpoint, timeout_s):
    start = time.perf_counter()
    output = Path(output)
    output.mkdir()
    body = encode_json(payload)
    (output / "request_body.json").write_bytes(body)
    result, response = request_local(payload, endpoint, timeout_s,
                                     connect_timeout_s=min(2.0, timeout_s),
                                     read_timeout_s=min(240.0, timeout_s),
                                     raw_response_path=output / "response.raw", mode=mode)
    write_json(output / "result.json", result)
    write_json(output / "response.json", response)
    successful = result.get("status") == "ok" and result.get("output_format_valid") is True
    structured = result.get("structured_output") if successful else None
    scores = None
    if successful:
        scores = score_describe(structured, truth) if mode == "describe" else score_sequence(structured, truth)
    metrics = {"status": result["status"], "successful_response": successful,
               "error": result.get("error"),
               "request_sha256": sha256(body), "request_bytes": len(body),
               "replay_wall_s": time.perf_counter() - start,
               "client_inference_wall_s": result.get("inference_wall_s"),
               "usage": result.get("usage"), "server_timings": result.get("server_timings"),
               "structured_output": structured, "scores": scores}
    write_json(output / "metrics.json", metrics)
    return metrics


def summarize(mode, rows):
    successful = [r for r in rows if r["successful_response"]]
    report = {"mode": mode, "attempted": len(rows), "successful": len(successful),
              "latency_s_all": [r["replay_wall_s"] for r in rows],
              "prompt_tokens": [(r.get("usage") or {}).get("prompt_tokens") for r in rows],
              "cached_tokens": [((r.get("server_timings") or {}).get("cache_n")) for r in rows]}
    if mode == "describe":
        by_frame = {}
        for r in successful:
            entry = by_frame.setdefault(str(r["frame_step"]), {"fastest_flow_distance_percent": [],
                                                              "lowest_pressure_distance_percent": [],
                                                              "fastest_flow_within_10_percent": 0})
            entry["fastest_flow_distance_percent"].append(r["scores"]["fastest_flow"]["distance_percent"])
            entry["lowest_pressure_distance_percent"].append(r["scores"]["lowest_pressure"]["distance_percent"])
            entry["fastest_flow_within_10_percent"] += r["scores"]["fastest_flow"]["within_10_percent"]
        report["by_frame"] = by_frame
        report["fastest_flow_within_10_percent"] = sum(
            r["scores"]["fastest_flow"]["within_10_percent"] for r in successful)
    else:
        report["field_matches"] = {name: sum(r["scores"][name]["match"] for r in successful)
                                   for name in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region")}
        report["cannot_tell"] = {name: sum(r["scores"][name]["cannot_tell"] for r in successful)
                                 for name in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region")}
    report["interpretation"] = (
        "Repeats of one request are not independent cases. Prompt-cache reuse differs between "
        "requests, so latencies are not comparable unless cache_n is the same. Position scores use the "
        "plotted range of the image; trend words use the saved extrema with the stated tolerances.")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("describe", "sequence"), required=True)
    parser.add_argument("--frames", type=Path, nargs="+", required=True,
                        help="snapshot directories (state.png, fields.npz, image-metadata.json), in time order for sequence")
    parser.add_argument("--output", type=Path, required=True, help="New output directory; never overwritten")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=320)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--timeout-s", type=float, default=300.0)
    parser.add_argument("--server-note", default="unrecorded")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= 50 or not 0 < args.timeout_s <= 300:
        parser.error("repeats must be 1..50; timeout-s must be in (0,300]")
    loaded = [load_frame(d) for d in args.frames]
    frames = [f for f, _ in loaded]
    truths = [t for _, t in loaded]
    if args.mode == "sequence" and len(frames) < 2:
        parser.error("sequence needs at least two frames")
    args.output.mkdir(parents=True, exist_ok=False)
    schedule = []
    if args.mode == "describe":
        for repeat in range(args.repeats):
            for frame, truth in zip(frames, truths):
                payload = describe_payload(frame, args.model, args.seed + repeat, args.max_tokens)
                name = f"describe-step{frame['step']:06d}-r{repeat + 1:02d}"
                schedule.append({"name": name, "repeat": repeat + 1, "frame_step": frame["step"],
                                 "seed": payload["seed"], "payload": payload, "truth": truth})
        write_json(args.output / "ground_truth.private.json", {str(t["step"]): t for t in truths})
    else:
        truth = sequence_truth(truths)
        for repeat in range(args.repeats):
            payload = sequence_payload(frames, args.model, args.seed + repeat, args.max_tokens)
            name = f"sequence-r{repeat + 1:02d}"
            schedule.append({"name": name, "repeat": repeat + 1,
                             "frame_step": [f["step"] for f in frames],
                             "seed": payload["seed"], "payload": payload, "truth": truth})
        write_json(args.output / "ground_truth.private.json", truth)
    manifest_schedule = []
    for entry in schedule:
        body = encode_json(entry["payload"])
        (args.output / f"{entry['name']}.request.json").write_bytes(body)
        manifest_schedule.append({k: entry[k] for k in ("name", "repeat", "frame_step", "seed")}
                                 | {"request_sha256": sha256(body), "request_bytes": len(body)})
    write_json(args.output / "manifest.json", {
        "schema_version": 1, "mode": args.mode, "execute": args.execute, "model": args.model,
        "endpoint": args.endpoint, "server_note": args.server_note, "max_tokens": args.max_tokens,
        "frames": [{k: f[k] for k in ("directory", "step", "time_s", "sha256", "fields_sha256", "plotted_range_m")}
                   for f in frames],
        "schedule": manifest_schedule, "new_solver_run": False,
        "truth_withheld_from_model": True})
    rows = []
    if args.execute:
        for entry in schedule:
            row = run_trial(entry["payload"], args.output / entry["name"], args.mode, entry["truth"],
                            args.endpoint, args.timeout_s)
            row.update(name=entry["name"], repeat=entry["repeat"], frame_step=entry["frame_step"],
                       seed=entry["seed"])
            rows.append(row)
            with (args.output / "metrics.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(encode_json(row).decode("utf-8") + "\n")
            print(f"{entry['name']}: {row['status']} {row['replay_wall_s']:.1f}s", flush=True)
        write_json(args.output / "summary.json", summarize(args.mode, rows))
    print(json.dumps({"output": str(args.output), "mode": args.mode,
                      "prepared_requests": len(schedule), "executed_requests": len(rows)}, indent=2))
    return 0 if not rows or all(r["successful_response"] for r in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
