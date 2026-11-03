#!/usr/bin/env python3
"""Send the prepared describe requests of the 3D slice test to the local llama-server, score
the positions (frame_scoring.score_describe, 10 % rule) and write the summary with the
constant-answer baseline. Nothing here draws a picture or changes a request body (only the
model name is checked). All files of every request are kept."""
import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ANSWER_GRID = np.stack(np.meshgrid(np.arange(101.0), np.arange(101.0)), -1).reshape(-1, 1, 2)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def baseline(keys):
    out = {}
    for target in ("fastest_flow", "lowest_pressure"):
        points = np.array([(k[target]["x_percent"], k[target]["y_percent"]) for k in keys])
        hits = (np.hypot(*(ANSWER_GRID - points).transpose(2, 0, 1)) <= 10.0).sum(axis=1)
        best = int(hits.argmax())
        out[target] = {"right": int(hits[best]), "of": len(keys),
                       "answer_percent": [float(ANSWER_GRID[best, 0, 0]), float(ANSWER_GRID[best, 0, 1])]}
    return out


def summarize(rows, keys):
    ok = [r for r in rows if r["successful_response"]]
    block = {"attempted": len(rows), "successful": len(ok),
             "median_latency_s": statistics.median([r["wall_s"] for r in rows]) if rows else None,
             "median_prompt_tokens": statistics.median([r["usage"]["prompt_tokens"] for r in ok
                                                        if r.get("usage")]) if ok else None}
    for target in ("fastest_flow", "lowest_pressure"):
        d = [r["scores"][target]["distance_percent"] for r in ok]
        block[target] = {"right_within_10_percent": sum(x <= 10.0 for x in d), "of_attempted": len(rows),
                         "of_successful": len(ok),
                         "median_distance_percent": statistics.median(d) if d else None,
                         "distances_percent": d}
    block["constant_answer_baseline"] = baseline(keys)
    return block


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wt", required=True)
    ap.add_argument("--test-set", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", default="gemma-4-12b-it-qat-q4_0-vision")
    ap.add_argument("--timeout-s", type=float, default=120.0)
    ap.add_argument("--server-note", default="")
    args = ap.parse_args()
    demo = Path(args.wt) / "Solver_Examples/PODFoam/llm_demo"
    sys.path.insert(0, str(demo))
    from frame_scoring import score_describe
    from llm_client import encode_json, request_local, write_json

    root = Path(args.test_set)
    manifest = json.loads((root / "manifest.json").read_text())
    truth_bytes = (root / "truth.json").read_bytes()
    if sha256(truth_bytes) != manifest["truth_sha256"]:
        raise SystemExit("truth.json differs from the manifest")
    truth = json.loads(truth_bytes)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "run.json", {"model": args.model, "endpoint": args.endpoint, "server_note": args.server_note,
                                  "test_set": str(root), "manifest_sha256": sha256((root / "manifest.json").read_bytes()),
                                  "truth_sha256": manifest["truth_sha256"], "timeout_s": args.timeout_s,
                                  "started_unix_s": time.time()})
    rows, keys, failures = [], [], 0
    for entry in manifest["requests"]:
        body = (root / entry["file"]).read_bytes()
        if sha256(body) != entry["request_sha256"]:
            raise SystemExit(f"{entry['file']}: changed after the manifest")
        payload = json.loads(body)
        if payload["model"] != args.model:
            raise SystemExit(f"{entry['file']}: model {payload['model']} is not {args.model}")
        key = truth[f"{entry['set']}/{entry['name']}"]
        d = out / entry["set"] / entry["name"]
        d.mkdir(parents=True)
        (d / "request_body.json").write_bytes(body)
        start = time.perf_counter()
        result, response = request_local(payload, args.endpoint, args.timeout_s, connect_timeout_s=2.0,
                                         read_timeout_s=min(240.0, args.timeout_s),
                                         raw_response_path=d / "response.raw", mode="describe")
        wall = time.perf_counter() - start
        write_json(d / "result.json", result)
        write_json(d / "response.json", response)
        ok = result.get("status") == "ok" and result.get("output_format_valid") is True
        structured = result.get("structured_output") if ok else None
        scores = score_describe(structured, key) if ok else None
        row = {"set": entry["set"], "name": entry["name"], "design": entry["design"], "status": result.get("status"),
               "successful_response": ok, "error": result.get("error"), "request_sha256": entry["request_sha256"],
               "wall_s": wall, "usage": result.get("usage"), "server_timings": result.get("server_timings"),
               "structured_output": structured, "scores": scores}
        write_json(d / "metrics.json", row)
        with (out / "metrics.jsonl").open("a", encoding="utf-8") as f:
            f.write(encode_json(row).decode("utf-8") + "\n")
        if not ok:
            failures += 1
        rows.append(row)
        keys.append(key)
        tag = "" if not ok else (f"fast {scores['fastest_flow']['distance_percent']:.1f} "
                                  f"lowp {scores['lowest_pressure']['distance_percent']:.1f}")
        print(f"{entry['set']}/{entry['name']}: {row['status']} {wall:.1f}s {tag}", flush=True)
    summary = {"model": args.model, "sets": {}, "failures": failures}
    for s in sorted({r["set"] for r in rows}):
        chosen = [(r, k) for r, k in zip(rows, keys) if r["set"] == s]
        summary["sets"][s] = summarize([r for r, _ in chosen], [k for _, k in chosen])
    summary["all"] = summarize(rows, keys)
    by_run = {}
    for r, k in zip(rows, keys):
        by_run.setdefault(r["design"]["run"], ([], []))
        by_run[r["design"]["run"]][0].append(r)
        by_run[r["design"]["run"]][1].append(k)
    summary["by_slice"] = {run: {t: summarize(rs, ks)[t]["right_within_10_percent"] for t in ("fastest_flow", "lowest_pressure")}
                           | {"attempted": len(rs)} for run, (rs, ks) in sorted(by_run.items())}
    summary["interpretation"] = ("right_within_10_percent counts answers within 10 % of the plotted range of the true cell, "
                                 "out of attempted requests. constant_answer_baseline: one integer answer for the whole set. "
                                 "The 24 solver frames come from 4 runs of one flow; the 48 windows are drawn from those frames.")
    write_json(out / "summary.json", summary)
    print(json.dumps({k: {t: v[t]["right_within_10_percent"] for t in ("fastest_flow", "lowest_pressure")}
                      | {"attempted": v["attempted"], "baseline": {t: v["constant_answer_baseline"][t]["right"]
                                                                   for t in ("fastest_flow", "lowest_pressure")}}
                      for k, v in list(summary["sets"].items()) + [("all", summary["all"])]}, indent=1))
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
