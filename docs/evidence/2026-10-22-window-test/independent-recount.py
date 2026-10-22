#!/usr/bin/env python3
"""Recount the 2026-10-22 window and Qwen runs from the recorded answers and the answer keys,
without picture_test.py or window_test.py, and compare every count cell of the jobs' reports.

Run in this folder:  python3 independent-recount.py   (writes independent-recount.json)

For each job, model and set it recomputes from metrics.jsonl (the parsed answers) and the key:
answered, fastest flow and lowest pressure within 10 % of the plotted range (distance in the
plane of x and y percent), the three trend words, and the fixed-answer column (window sets: the
best integer answer for the whole set; the 308-request set: the best integer answer per plotted
range, the most common true word per trend). The October 17 'located' counts are read from the
runner's location field, not recomputed. Token and time columns are not checked. It also
derives the numbers the report cites: median distances, trends on the designs with a clear
change, the three window seeds combined, and the fastest-cell spread of each window set.
The key of the 308 requests is ../2026-10-22-picture-test/test-set/truth.private.json.
"""
import hashlib
import json
import math
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORDS = ("max_speed_trend", "min_pressure_trend", "fastest_flow_region")
TARGETS = ("fastest_flow", "lowest_pressure")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


KEYS = {sha(p): p for p in list((HERE / "test-sets").glob("*/truth.private.json"))
        + [HERE.parent / "2026-10-22-picture-test" / "test-set" / "truth.private.json"]}


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def best_point(points):
    return max(sum(dist((x, y), p) <= 10.0 for p in points) for x in range(101) for y in range(101))


def fixed_answer(kind, set_name, truth):
    keys = [v for k, v in truth.items() if k.startswith(set_name + "/")]
    if not keys:
        return None
    if isinstance(keys[0].get("fastest_flow"), dict):
        boxes = [json.dumps(k["plotted_range_m"], sort_keys=True) for k in keys]
        if kind == "window":
            assert len(set(boxes)) == len(boxes), set_name
            groups = {"all": keys}
        else:
            groups = defaultdict(list)
            for box, k in zip(boxes, keys):
                groups[box].append(k)
        return [sum(best_point([(k[t]["x_percent"], k[t]["y_percent"]) for k in g]) for g in groups.values())
                for t in TARGETS]
    return [max(Counter(k[w] for k in keys).values()) for w in WORDS]


def parse_report(path):
    cells = {}
    for line in path.read_text().splitlines():
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) == 12 and parts[0] not in ("model", "---"):
            cells[(parts[0], parts[1], parts[2])] = parts
    return cells


def recount(job):
    kind = "window" if job.startswith("window-test") else "picture"
    report = parse_report(HERE / "reports" / f"{job}.md")
    out, checks, diffs = {}, 0, []
    for model_dir in sorted(p for p in (HERE / "results" / job).iterdir() if p.is_dir()):
        run = json.loads((model_dir / "run.json").read_text())
        truth_path = KEYS[run["truth_sha256"]]
        truth = json.loads(truth_path.read_text())
        alias = run["model"]
        for set_dir in sorted(p for p in model_dir.iterdir() if p.is_dir() and (p / "metrics.jsonl").exists()):
            name = set_dir.name
            by_mode = defaultdict(list)
            for r in rows(set_dir / "metrics.jsonl"):
                by_mode[r["mode"]].append(r)
            for mode, items in by_mode.items():
                c = {"attempted": len(items), "answered": sum(bool(r.get("successful_response")) for r in items)}
                if mode == "describe":
                    for t in TARGETS:
                        d = []
                        for r in items:
                            so = r.get("structured_output")
                            if not r.get("successful_response") or not so:
                                continue
                            key = truth[f"{name}/{r['name']}"][t]
                            d.append(dist((so[f"{t}_x_percent"], so[f"{t}_y_percent"]), (key["x_percent"], key["y_percent"])))
                        c[t] = sum(x <= 10.0 for x in d)
                        c[t + "_median_distance_percent"] = round(st.median(d), 2) if d else None
                    c["fixed"] = fixed_answer(kind, name, {k: v for k, v in truth.items()
                                                           if k.split("/", 1)[1] in {r["name"] for r in items}
                                                           and k.startswith(name + "/")})
                    expect = [f"{c['answered']}/{c['attempted']}", f"{c['fastest_flow']}/{c['attempted']}",
                              f"{c['lowest_pressure']}/{c['attempted']}", " / ".join(map(str, c["fixed"]))]
                    cell = report.get((alias, name, mode))
                    got = [cell[3], cell[4], cell[5], cell[9]] if cell else None
                elif mode == "sequence":
                    clear = {w: [0, 0] for w in WORDS[:2]}
                    for w in WORDS:
                        c[w] = sum(bool(r.get("successful_response")) and (r.get("structured_output") or {}).get(w)
                                   == truth[f"{name}/{r['name']}"][w] for r in items)
                    for r in items:
                        key = truth[f"{name}/{r['name']}"]
                        so = r.get("structured_output") or {}
                        for w, change in (("max_speed_trend", "max_speed_relative_change"),
                                          ("min_pressure_trend", "min_pressure_relative_change")):
                            if abs(key[change]) >= 0.02:
                                clear[w][1] += 1
                                clear[w][0] += bool(r.get("successful_response")) and so.get(w) == key[w]
                    c["clear_change"] = clear
                    c["fixed"] = fixed_answer(kind, name, {k: v for k, v in truth.items()
                                                           if k.split("/", 1)[1] in {r["name"] for r in items}
                                                           and k.startswith(name + "/")})
                    expect = [f"{c['answered']}/{c['attempted']}"] + [f"{c[w]}/{c['attempted']}" for w in WORDS] \
                        + [" / ".join(map(str, c["fixed"]))]
                    cell = report.get((alias, name, mode))
                    got = [cell[3], cell[6], cell[7], cell[8], cell[9]] if cell else None
                else:
                    located = Counter(r["condition"] for r in items if r["location"]["status"] == "scored")
                    conditions = sorted({r["condition"] for r in items})
                    c["located"] = {k: located.get(k, 0) for k in conditions}
                    expect = [f"{c['answered']}/{c['attempted']}",
                              " ; ".join(f"{k}: {located.get(k, 0)} located" for k in conditions)]
                    cell = report.get((alias, name, mode))
                    got = [cell[3], cell[4]] if cell else None
                checks += 1
                if got != expect:
                    diffs.append({"job": job, "model": alias, "set": name, "mode": mode, "report": got, "recount": expect})
                out.setdefault(model_dir.name, {})[f"{name}:{mode}"] = c
    return out, checks, diffs


def main():
    jobs = sorted(p.name for p in (HERE / "results").iterdir() if p.is_dir())
    result = {"jobs": {}, "report_cells_checked": 0, "differences": []}
    for job in jobs:
        counts, checks, diffs = recount(job)
        result["jobs"][job] = counts
        result["report_cells_checked"] += checks
        result["differences"] += diffs
    # the three window seeds combined (same six models in all three jobs)
    seeds = {"window-test-24757344": "seed 1", "window-test-24757384": "seed 2", "window-test-24757383": "seed 3"}
    combined = {}
    for job in seeds:
        for model, sets in result["jobs"].get(job, {}).items():
            for key, c in sets.items():
                total = combined.setdefault(model, {}).setdefault(key, {"jobs": 0, "attempted": 0, "fastest_flow": 0,
                                                                          "lowest_pressure": 0, "fixed": [0, 0]})
                total["jobs"] += 1
                for f in ("attempted", "fastest_flow", "lowest_pressure"):
                    total[f] += c[f]
                total["fixed"] = [a + b for a, b in zip(total["fixed"], c["fixed"])]
    result["window_seeds_combined"] = {m: v for m, v in combined.items() if all(x["jobs"] == 3 for x in v.values())}
    # where the fastest cell is in each window set (percent of the plotted range, and metres)
    spread = {}
    for path in sorted((HERE / "test-sets").glob("*/truth.private.json")):
        keys = [v for k, v in json.loads(path.read_text()).items() if k.startswith("flow-window-v2/")]
        xs = [k["fastest_flow"]["x_m"] for k in keys]
        ys = [k["fastest_flow"]["y_m"] for k in keys]
        spread[path.parent.name] = {"requests": len(keys), "states": len({k["step"] for k in keys}),
                                    "fastest_cell_x_m": [round(min(xs), 4), round(max(xs), 4)],
                                    "fastest_cell_y_m": [round(min(ys), 4), round(max(ys), 4)]}
    result["fastest_cell_spread"] = spread
    (HERE / "independent-recount.json").write_text(json.dumps(result, indent=1) + "\n")
    print(f"{result['report_cells_checked']} report rows checked, {len(result['differences'])} differ")
    for d in result["differences"]:
        print(" ", d)


if __name__ == "__main__":
    main()
