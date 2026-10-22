#!/usr/bin/env python3
"""Re-score the 2026-10-22 picture test from the answer key and the recorded answers, without
picture_test.py; compare with report.md; derive the other numbers the report cites.

Run in this folder:  python3 independent-rescore.py   (writes independent-rescore.json)

Checked against report.md: every count cell (answered, fastest flow and lowest pressure within
10 %, the three trend words, located), the fixed-answer column and the item-by-item lines.
Not checked: the token and time columns (they are copied from metrics.jsonl) and the lines that
compare with the published 2026-10-17/20 answers (those answers are in the input bundle).
"""
import json
import math
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = ["e2b", "e2b-bf16", "e2b-qat", "e4b", "12b", "26b", "31b"]
BIG = ["12b", "26b", "31b"]
truth = json.loads((HERE / "test-set" / "truth.private.json").read_text())


def rows(model, name):
    path = HERE / "results" / model / name / "metrics.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


sets = sorted(p.name for p in (HERE / "results" / "31b").iterdir() if p.is_dir())
alias = {m: json.loads((HERE / "results" / m / "run.json").read_text())["model"] for m in MODELS}
alias_to_key = {v: k for k, v in alias.items()}

# 1. per item: right or wrong, from the answers and the key only
counts, distances, right = {}, {}, {}
for m in MODELS:
    for s in sets:
        for r in rows(m, s):
            t = truth[f"{s}/{r['name']}"]
            mode = r["mode"]
            c = counts.setdefault(m, {}).setdefault(s, {}).setdefault(mode, defaultdict(int))
            c["attempted"] += 1
            c["answered"] += bool(r.get("successful_response"))
            so = r.get("structured_output") or {}
            item = right.setdefault(m, {}).setdefault(s, {}).setdefault(r["name"], {})
            if mode == "describe":
                for k in ("fastest_flow", "lowest_pressure"):
                    d = dist((so[f"{k}_x_percent"], so[f"{k}_y_percent"]), (t[k]["x_percent"], t[k]["y_percent"]))
                    item[k] = d <= 10.0
                    c[f"{k}_within_10"] += item[k]
                    distances.setdefault(m, {}).setdefault(s, {}).setdefault(k, []).append(d)
            elif mode == "sequence":
                for k in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region"):
                    item[k] = so.get(k) == t[k]
                    c[f"{k}_right"] += item[k]
            elif mode == "observe":
                c[f"located_{r['condition']}"] += r["location"]["status"] == "scored"

# 2. one fixed answer per plotted range (integer grid for positions, one word for trends)
def best_point(points):
    return max(sum(dist((x, y), p) <= 10.0 for p in points) for x in range(101) for y in range(101))


fixed = {}
for s in sets:
    groups = defaultdict(lambda: defaultdict(list))
    for k in (k for k in truth if k.startswith(s + "/")):
        t = truth[k]
        if isinstance(t.get("fastest_flow"), dict):
            g = json.dumps(t["plotted_range_m"])
            for f in ("fastest_flow", "lowest_pressure"):
                groups[g][f].append((t[f]["x_percent"], t[f]["y_percent"]))
        elif "max_speed_trend" in t:
            g = "seq:" + k.split("/", 1)[1].split("-")[0]
            for f in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region"):
                groups[g][f].append(t[f])
    out = defaultdict(int)
    for fields in groups.values():
        for f, vals in fields.items():
            out[f] += best_point(vals) if f in ("fastest_flow", "lowest_pressure") else max(vals.count(v) for v in set(vals))
    fixed[s] = dict(out)

# 3. compare with report.md
checked = differing = 0
def check(label, got, want):
    global checked, differing
    checked += 1
    if got != want:
        differing += 1
        print("differs:", label, repr(got), repr(want))

text = (HERE / "report.md").read_text()
for line in text.splitlines():
    if line.startswith("| gemma"):
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        model, s, mode, answered, f10, p10, speed, press, region, fixed_cell = cells[:10]
        m = alias_to_key[model]
        c = counts[m][s][mode]
        n = c["attempted"]
        lab = f"{m} {s} {mode}"
        check(lab + " answered", answered, f"{c['answered']}/{n}")
        if mode == "describe":
            check(lab + " fastest", f10, f"{c['fastest_flow_within_10']}/{n}")
            check(lab + " lowest p", p10, f"{c['lowest_pressure_within_10']}/{n}")
            check(lab + " fixed", fixed_cell, f"{fixed[s]['fastest_flow']} / {fixed[s]['lowest_pressure']}")
        elif mode == "sequence":
            check(lab + " speed", speed, f"{c['max_speed_trend_right']}/{n}")
            check(lab + " pressure", press, f"{c['min_pressure_trend_right']}/{n}")
            check(lab + " region", region, f"{c['fastest_flow_region_right']}/{n}")
            check(lab + " fixed", fixed_cell, f"{fixed[s]['max_speed_trend']} / {fixed[s]['min_pressure_trend']} / {fixed[s]['fastest_flow_region']}")
        elif mode == "observe":
            check(lab + " located", f10, f"numeric_only: {c['located_numeric_only']} located ; "
                                         f"numeric_plus_image: {c['located_numeric_plus_image']} located")
pair_re = re.compile(r"^- (\S+) (\S+) vs (\S+): items (\d+), both (\d+), only \S+ (\d+), only \S+ (\d+), neither (\d+)$")
for line in text.splitlines():
    hit = pair_re.match(line)
    if not hit:
        continue
    model, a, b = hit.group(1), hit.group(2), hit.group(3)
    m = alias_to_key[model]
    key = "fastest_flow" if "position" in a or "describe" in a else "max_speed_trend"
    names = sorted(set(right[m][a]) & set(right[m][b]))
    both = sum(right[m][a][x][key] and right[m][b][x][key] for x in names)
    only_a = sum(right[m][a][x][key] and not right[m][b][x][key] for x in names)
    only_b = sum(right[m][b][x][key] and not right[m][a][x][key] for x in names)
    neither = len(names) - both - only_a - only_b
    check(f"{m} {a} vs {b}", tuple(int(g) for g in hit.groups()[3:]), (len(names), both, only_a, only_b, neither))

# 4. other numbers the report cites
dist_summary = {m: {s: {k: {"median": round(st.median(v), 1), "max": round(max(v), 1)} for k, v in d.items()}
                    for s, d in sd.items()} for m, sd in distances.items()}

trend_split = {}
for m in MODELS:
    for s in ("control-trend-v1", "control-trend-v2", "control-trend-v2own"):
        for f in ("max_speed_trend", "min_pressure_trend"):
            clear = flat = n_clear = n_flat = 0
            for r in rows(m, s):
                want = truth[f"{s}/{r['name']}"][f]
                got = r["structured_output"][f] == want
                if want == "roughly_constant":
                    n_flat += 1; flat += got
                else:
                    n_clear += 1; clear += got
            trend_split.setdefault(m, {}).setdefault(s, {})[f] = {"clear": f"{clear}/{n_clear}", "flat": f"{flat}/{n_flat}"}

answers_by_truth = {}
for m in MODELS:
    for s in [x for x in sets if "trend" in x or "sequence" in x]:
        for f in ("max_speed_trend", "min_pressure_trend"):
            c = Counter()
            for r in rows(m, s):
                if r["mode"] != "sequence":
                    continue
                c[f"{truth[s + '/' + r['name']][f]} -> {r['structured_output'][f]}"] += 1
            answers_by_truth.setdefault(m, {}).setdefault(s, {})[f] = dict(sorted(c.items()))

flow_sequence_changes = {}
for k in sorted(k for k in truth if k.startswith("flow-sequence-v2/")):
    t = truth[k]
    flow_sequence_changes[k.split("/", 1)[1]] = {
        "max_speed_change_percent": round(100 * t["max_speed_relative_change"], 1), "max_speed_trend": t["max_speed_trend"],
        "min_pressure_change_percent": round(100 * t["min_pressure_relative_change"], 1), "min_pressure_trend": t["min_pressure_trend"],
        "fastest_flow_region": t["fastest_flow_region"]}

planted_misses = {}
for m in MODELS:
    for k in ("fastest_flow", "lowest_pressure"):
        miss = near = 0
        for r in rows(m, "planted-position-v2"):
            t = truth[f"planted-position-v2/{r['name']}"][k]
            a = (r["structured_output"][f"{k}_x_percent"], r["structured_output"][f"{k}_y_percent"])
            if dist(a, (t["x_percent"], t["y_percent"])) <= 10.0:
                continue
            miss += 1
            view, step = r["name"].split("-")[0], int(r["name"].split("step")[1])
            own = truth[f"flow-describe-v2/{view}-step{step:06d}"][k]   # the same saved state, nothing planted
            near += dist(a, (own["x_percent"], own["y_percent"])) <= 10.0
        planted_misses.setdefault(m, {})[k] = {"misses": miss, "within_10_of_the_unplanted_state's_own_extreme": near}

pictured = {}
for m in BIG:
    for r in rows(m, "planted-position-v2"):
        if r["name"] == "window-02-step002500":
            so = r["structured_output"]
            pictured[m] = {"fastest_flow": [so["fastest_flow_x_percent"], so["fastest_flow_y_percent"]],
                           "lowest_pressure": [so["lowest_pressure_x_percent"], so["lowest_pressure_y_percent"]],
                           "fastest_within_10": right[m]["planted-position-v2"][r["name"]]["fastest_flow"],
                           "lowest_pressure_within_10": right[m]["planted-position-v2"][r["name"]]["lowest_pressure"]}
t = truth["planted-position-v2/window-02-step002500"]
pictured["key"] = {"fastest_flow": [round(t["fastest_flow"]["x_percent"], 1), round(t["fastest_flow"]["y_percent"], 1)],
                   "lowest_pressure": [round(t["lowest_pressure"]["x_percent"], 1), round(t["lowest_pressure"]["y_percent"], 1)]}

position_counts = {m: [counts[m][s]["describe"][f"{k}_within_10"]
                       for s in ("control-position-v1", "control-position-v2", "planted-position-v1", "planted-position-v2")
                       for k in ("fastest_flow", "lowest_pressure")] for m in ("e2b", "e2b-bf16", "e2b-qat")}
projector_swaps = {
    "e2b vs e2b-bf16 (projector Q8_0 vs BF16, same weights)": max(abs(a - b) for a, b in zip(position_counts["e2b"], position_counts["e2b-bf16"])),
    "e2b-bf16 vs e2b-qat (other weights, Google's BF16 projector file)": max(abs(a - b) for a, b in zip(position_counts["e2b-bf16"], position_counts["e2b-qat"])),
    "e2b vs e2b-qat": max(abs(a - b) for a, b in zip(position_counts["e2b"], position_counts["e2b-qat"])),
}

totals = {}
for m in MODELS:
    pos = pos_n = pos_fixed = words = words_n = words_fixed = 0
    for s in sets:
        c = counts[m][s]
        if "describe" in c:
            pos += c["describe"]["fastest_flow_within_10"] + c["describe"]["lowest_pressure_within_10"]
            pos_n += 2 * c["describe"]["attempted"]
            pos_fixed += fixed[s]["fastest_flow"] + fixed[s]["lowest_pressure"]
        if "sequence" in c:
            words += sum(c["sequence"][f"{k}_right"] for k in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region"))
            words_n += 3 * c["sequence"]["attempted"]
            words_fixed += fixed[s]["max_speed_trend"] + fixed[s]["min_pressure_trend"] + fixed[s]["fastest_flow_region"]
    totals[m] = {"positions_within_10": f"{pos}/{pos_n}", "fixed_answer_positions": pos_fixed,
                 "trend_words_right": f"{words}/{words_n}", "fixed_answer_words": words_fixed}

oct17 = {}
for m in MODELS:
    flags, x0, unknown, tokens = Counter(), Counter(), Counter(), defaultdict(set)
    for s in ("oct17-paired", "oct17-paired-cold"):
        for r in rows(m, s):
            flags[r["grounding"]["assessment"]] += 1
            for fl in r["grounding"].get("unsupported_claim_flags", []):
                flags["flag:" + fl["kind"]] += 1
            tokens[r["condition"]].add(r["usage"]["prompt_tokens"])
            so = json.loads((HERE / "results" / m / s / r["name"] / "result.json").read_text())["structured_output"]
            unknown[r["condition"]] += bool(re.search(r"\bunknown\b", so["observations"], re.I))
            hit = re.search(r"x\s*=\s*0(?:\.0+)?\s*m(?:,\s*y\s*=\s*[-\d.]+\s*m)?", so["possible_interpretation"])
            if hit:
                x0[f"{r['condition']}: {hit.group(0)}"] += 1
    oct17[m] = {"checker": dict(flags), "observations_say_unknown": dict(unknown),
                "possible_interpretation_near_x0": dict(x0),
                "prompt_tokens": {k: sorted(v) for k, v in tokens.items()}}

timing, gpu = {}, {}
for p in sorted((HERE / "runtime" / "server").glob("models-*.json")):
    stamp = p.stem.split("-", 1)[1]
    d = json.loads(p.read_text())["data"][0]
    m = alias_to_key[d["id"]]
    gpu[m] = ((HERE / "runtime" / "server" / f"gpu-{stamp}.txt").read_text().strip().splitlines()[-1], d["meta"])
for m in MODELS:
    walls, gen = [], []
    for s in sets:
        for r in rows(m, s):
            walls.append(r["replay_wall_s"])
            gen.append(r["server_timings"]["predicted_per_second"])
    line, meta = gpu[m]
    used = int(line.split(",")[1].strip().split()[0])
    timing[m] = {"requests": len(walls), "median_s": round(st.median(walls), 2), "min_s": round(min(walls), 2),
                 "max_s": round(max(walls), 2), "total_min": round(sum(walls) / 60, 1),
                 "generated_tokens_per_s_median": round(st.median(gen), 1), "gpu_line_when_ready": line,
                 "parameters": meta["n_params"], "weights_bytes": meta["size"],
                 "weights_MiB": round(meta["size"] / 2**20), "gpu_used_below_weights": used < meta["size"] / 2**20}

out = {"report_cells_checked": checked, "report_cells_differing": differing, "aliases": alias,
       "counts": {m: {s: {mode: dict(c) for mode, c in sd.items()} for s, sd in md.items()} for m, md in counts.items()},
       "fixed_answer": fixed, "distance_percent": dist_summary, "trend_clear_and_flat": trend_split,
       "trend_answers_by_key": answers_by_truth, "flow_sequence_changes": flow_sequence_changes,
       "planted_v2_misses": planted_misses, "pictured_planted_item": pictured,
       "e2b_projector_swaps_max_position_change": projector_swaps, "totals": totals,
       "oct17_pairs": oct17, "time_and_memory": timing}
(HERE / "independent-rescore.json").write_text(json.dumps(out, indent=1) + "\n")
print(f"report.md: {checked} cells and lines checked, {differing} differ")
