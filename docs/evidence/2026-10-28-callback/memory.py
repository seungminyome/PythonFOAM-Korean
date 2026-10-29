#!/usr/bin/env python3
"""Memory and cost of telemetry.jsonl in the callback: main's python_module.py (callback-main/)
against this branch's, over the 24,000 recorded states of the 2026-10-27 periodic run.

usage: memory.py [--steps 24000] [--output memory.json]   (needs numpy; Python 3.11 as the solver)

Each version runs in its own Python process, in a new case folder with the callback, its helper
modules and the POD module of the case. LLM_ENABLED=0 and no request (LLM_ANALYSIS_STEP beyond the
run), so only what the callback does with each step's state is measured. The states are the lines of
../2026-10-27-solver/periodic/periodic-no-llm/telemetry.jsonl.gz without the run_id the writer adds,
and LLM_RUN_ID is that run's, so each version should write that file again, byte for byte.

Two passes per version. traced: tracemalloc's count of the Python heap after every 1,000 steps and
its peak (the last step is not made final here, so main's whole-file write is not part of the
count). timed: no tracemalloc; wall time of each analysis_func call, including the last step, which
writes telemetry.jsonl; then the file is compared with the recorded one.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc

HERE = Path(__file__).resolve().parent
LLM_DEMO = HERE.parents[2] / "Solver_Examples" / "PODFoam" / "llm_demo"
RECORDED = HERE.parent / "2026-10-27-solver" / "periodic" / "periodic-no-llm" / "telemetry.jsonl.gz"
VERSIONS = {"main": HERE / "callback-main" / "python_module.py", "branch": LLM_DEMO / "python_module.py"}


def one(version, traced, steps):
    """One version, one pass, in this process; returns its record."""
    recorded = gzip.decompress(RECORDED.read_bytes())
    lines = recorded.splitlines(keepends=True)[:steps]
    states = []
    for line in lines:
        state = json.loads(line)
        run_id = state.pop("run_id")
        states.append(state)
    case = Path(tempfile.mkdtemp(prefix=f"telemetry-{version}-"))
    try:
        shutil.copyfile(VERSIONS[version], case / "python_module.py")
        for helper in ("bounded_ipc.py", "llm_client.py", "pod_image.py"):
            shutil.copyfile(LLM_DEMO / helper, case / helper)
        shutil.copyfile(LLM_DEMO.parent / "validation" / "python_module.py", case / "pod_svd.py")
        sys.path.insert(0, str(case))
        spec = importlib.util.spec_from_file_location("python_module", case / "python_module.py")
        callback = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(callback)
        os.environ.update(LLM_ENABLED="0", LLM_MODE="describe", LLM_IMAGE_STYLE="v2",
                          LLM_ANALYSIS_STEP=str(10 ** 9), LLM_RUN_ID=run_id,
                          LLM_FINAL_STEP="0" if traced else str(steps))
        record = {"version": version, "pass": "traced" if traced else "timed", "steps": steps,
                  "callback_sha256": hashlib.sha256(VERSIONS[version].read_bytes()).hexdigest()}
        if traced:
            tracemalloc.start()
            base = tracemalloc.get_traced_memory()[0]
            heap = []
            for k, state in enumerate(states, 1):
                callback.analysis_func(state)
                if k % 1000 == 0:
                    heap.append({"step": k, "mib": round((tracemalloc.get_traced_memory()[0] - base) / 2**20, 3)})
            peak = tracemalloc.get_traced_memory()[1] - base
            tracemalloc.stop()
            record.update(heap_after_steps=heap, heap_peak_mib=round(peak / 2**20, 3),
                          heap_per_step_kib_last_10000=round(
                              (heap[-1]["mib"] - heap[-11]["mib"]) * 1024 / 10000, 4) if len(heap) > 10 else None)
        else:
            walls = []
            for state in states:
                start = time.perf_counter()
                callback.analysis_func(state)
                walls.append(time.perf_counter() - start)
            written = case / "telemetry.jsonl"
            data = written.read_bytes() if written.exists() else None
            record.update(
                wall_s_last_step=round(walls[-1], 4),
                wall_s_other_steps={"median": round(statistics.median(walls[:-1]), 6),
                                    "mean": round(statistics.fmean(walls[:-1]), 6),
                                    "max": round(max(walls[:-1]), 4),
                                    "max_step": walls.index(max(walls[:-1])) + 1},
                wall_s_steps_500_1000_1500={str(s): round(walls[s - 1], 6) for s in (500, 1000, 1500)
                                            if s < len(walls)},
                telemetry_bytes=len(data) if data is not None else None,
                telemetry_sha256=hashlib.sha256(data).hexdigest() if data is not None else None,
                telemetry_equals_recorded=data == b"".join(lines),
                tmp_left=(case / "telemetry.jsonl.tmp").exists())
            if version == "branch":
                record["appends"] = {"done": callback._telemetry.appends,
                                     "failed": callback._telemetry.failed_appends,
                                     "batch_lines": callback._telemetry.BATCH_LINES}
        return record
    finally:
        shutil.rmtree(case, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--steps", type=int, default=24000)
    parser.add_argument("--output", default=str(HERE / "memory.json"))
    parser.add_argument("--one", nargs=2, metavar=("VERSION", "PASS"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.one:
        print(json.dumps(one(args.one[0], args.one[1] == "traced", args.steps)))
        return
    records = []
    for version in VERSIONS:
        for name in ("traced", "timed"):
            done = subprocess.run([sys.executable, __file__, "--steps", str(args.steps), "--one", version, name],
                                  check=True, capture_output=True, text=True)
            records.append(json.loads(done.stdout.strip().splitlines()[-1]))
    result = {"python": sys.version.split()[0], "states": str(RECORDED.relative_to(HERE.parent)),
              "recorded_sha256": hashlib.sha256(gzip.decompress(RECORDED.read_bytes())).hexdigest(),
              "runs": records}
    Path(args.output).write_text(json.dumps(result, indent=1) + "\n")
    for r in records:
        if r["pass"] == "traced":
            print(r["version"], "heap after", r["heap_after_steps"][-1]["step"], "steps:",
                  r["heap_after_steps"][-1]["mib"], "MiB; peak", r["heap_peak_mib"], "MiB")
        else:
            print(r["version"], "last step", r["wall_s_last_step"], "s; other steps median",
                  r["wall_s_other_steps"]["median"], "s; file equals recorded:", r["telemetry_equals_recorded"])


if __name__ == "__main__":
    main()
