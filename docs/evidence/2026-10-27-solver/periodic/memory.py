#!/usr/bin/env python3
"""Memory of the solver process over the periodic run (Slurm 24903264), without and with requests.

Run in this folder:  python3 memory.py   (standard library only; writes memory.json; the history size
depends on the Python version: memory.json was written with Python 3.11, the solver's)

PODFoam's POD module (pod_svd.py of the case) keeps 250 velocity snapshots and clears them at each
SVD, every 250 steps, so the process memory rises and falls by hundreds of MiB within each
250-step cycle, and a mean over a quarter of the run depends on where the samples fall. Here each
cycle runs from one 'PYTHON LLM step=' line of the timeline to the next (the callback's line at
every 250th step, in both cases), and the lowest PSS of the samples in it with only the solver
process alive (no worker forked) is taken as that cycle's baseline. It also measures how much
memory the callback's per-step history takes (_history in python_module.py keeps every step's
state until the end of the run, for telemetry.jsonl): 24,000 copies of telemetry records.
"""
import copy
import gzip
import json
import re
import statistics as st
import sys
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def cycles(case):
    timeline = load(HERE / case / "timeline.json.gz")
    marks = [(int(re.search(r"step=(\d+)", e["line"]).group(1)), e["wall_since_start_s"])
             for e in timeline if e["line"].startswith("PYTHON LLM step=")]
    samples = load(HERE / case / "memory-samples.json.gz")
    out = []
    for (s0, w0), (_, w1) in zip(marks, marks[1:]):
        alone = [m["cfd_python_pss_sum_kib"] for m in samples
                 if w0 < m["wall_since_start_s"] < w1 and m["processes"] == 1]
        if alone:
            out.append({"from_step": s0, "min_pss_mib": round(min(alone) / 1024, 1),
                        "max_pss_mib": round(max(alone) / 1024, 1)})
    return out


def main():
    result = {}
    for case in ("periodic-no-llm", "periodic-describe"):
        c = cycles(case)
        q = len(c) // 4
        result[case] = {"cycles": len(c),
                        "baseline_first_quarter_mean_mib": round(st.mean(x["min_pss_mib"] for x in c[:q]), 1),
                        "baseline_last_quarter_mean_mib": round(st.mean(x["min_pss_mib"] for x in c[-q:]), 1),
                        "largest_swing_within_a_cycle_mib": round(max(x["max_pss_mib"] - x["min_pss_mib"] for x in c), 1),
                        "per_cycle": c}
        r = result[case]
        r["baseline_growth_mib"] = round(r["baseline_last_quarter_mean_mib"] - r["baseline_first_quarter_mean_mib"], 1)
    with gzip.open(HERE / "periodic-no-llm" / "telemetry.jsonl.gz", "rt") as f:
        records = [json.loads(line) for line in f]
    tracemalloc.start()
    kept = [copy.deepcopy(records[i % len(records)]) for i in range(24000)]
    used = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    result["history_of_24000_telemetry_records_mib"] = round(used / 2**20, 1)
    result["history_per_step_kib"] = round(used / len(kept) / 1024, 2)
    result["python"] = sys.version.split()[0]
    (HERE / "memory.json").write_text(json.dumps(result, indent=1) + "\n")
    for case in ("periodic-no-llm", "periodic-describe"):
        r = result[case]
        print(case, r["baseline_first_quarter_mean_mib"], "->", r["baseline_last_quarter_mean_mib"],
              "MiB, growth", r["baseline_growth_mib"], "; largest swing in a cycle", r["largest_swing_within_a_cycle_mib"])
    print("history:", result["history_of_24000_telemetry_records_mib"], "MiB,", result["history_per_step_kib"], "KiB per step")


if __name__ == "__main__":
    main()
