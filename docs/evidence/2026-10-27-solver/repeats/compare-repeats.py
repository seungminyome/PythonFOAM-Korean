#!/usr/bin/env python3
"""Compare the two repeats of 2026-10-27 (Slurm 24903298 and 24903263, NVIDIA A30) with the
first v2 solver run (Slurm 24757460, NVIDIA RTX A6000, in ../../2026-10-22-live-v2/).

Run in this folder:  python3 compare-repeats.py   (standard library only; writes compare-repeats.json)

1. Written files: every file hash of each repeat's suite (sha256.json, as pack_run.py wrote it)
   and sweep (sweep-sha256.json.gz) against the first run's. Files inside time directories
   are counted apart from code, logs and records, and the POD mode files (upod_*, vpod_*, wpod_*,
   which PODFoam writes with the SVD of NumPy/OpenBLAS) apart from the flow fields.
2. Requests: the SHA-256 of every request body each repeat sent (llm_result.json,
   request_sha256) against the first run's.
3. Answers: the parsed answer (structured_output) of the describe and sequence cases and of
   the eleven sweep requests, against the first run's and between the repeats.
"""
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN1 = HERE.parent.parent / "2026-10-22-live-v2"
REPEATS = ("24903298", "24903263")
TIME_DIR = re.compile(r"^\d+(\.\d+)?$")
POD_MODE = re.compile(r"^[uvw]pod_\d+$")


def load(path):
    path = Path(path)
    data = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return json.loads(data)


def kind(path):
    parts = path.split("/")
    name = parts[-1]
    if any(TIME_DIR.match(p) for p in parts[:-1]):
        return "POD mode file" if POD_MODE.match(name) else "time directory, other than POD modes"
    if name.endswith((".py", ".H", ".C", ".patch")) or "executed-callback-source" in parts or "sources" in parts:
        return "code"
    if name.startswith("log.") or name.endswith(".log"):
        return "log"
    if name.startswith("llm_"):
        return "request/reply record"
    return "other record"


def compare_hashes(a, b):
    common = set(a) & set(b)
    differ = sorted(k for k in common if a[k] != b[k])
    return {"compared": len(common), "identical": len(common) - len(differ), "differ": len(differ),
            "differ_by_kind": dict(Counter(kind(k) for k in differ)),
            "differ_in_time_directories_other_than_POD_modes": [k for k in differ if kind(k).startswith("time directory")],
            "only_in_first_run": len(set(a) - set(b)), "only_in_repeat": len(set(b) - set(a))}


def answers(folder):
    out = {}
    for case in ("async-describe", "async-sequence"):
        r = load(folder / case / "llm_result.json")
        out[case] = (r["request_sha256"], r["structured_output"])
    for d in sorted((folder / "sweep").glob("describe-step*")):
        r = load(d / "llm_result.json")
        out[d.name] = (r["request_sha256"], r["structured_output"])
    return out


def diff_fields(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def main():
    run1_suite = load(RUN1 / "suite" / "sha256.json")
    run1_sweep = load(HERE / "run1-sweep-sha256.json.gz")
    run1 = {}
    for case in ("async-describe", "async-sequence"):
        body = hashlib.sha256((RUN1 / "suite" / case / "llm_request_body.json").read_bytes()).hexdigest()
        r = load(RUN1 / "suite" / case / "llm_result.json")
        assert r["request_sha256"] == body
        run1[case] = (body, r["structured_output"])
    for d in sorted((RUN1 / "sweep").glob("describe-step*")):
        r = load(d / "llm_result.json")
        run1[d.name] = (r["request_sha256"], r["structured_output"])
    result = {"first_run": "Slurm 24757460 (NVIDIA RTX A6000), ../../2026-10-22-live-v2", "repeats": {}}
    rep_answers = {}
    for job in REPEATS:
        folder = HERE / job
        rep = rep_answers[job] = answers(folder)
        result["repeats"][job] = {
            "verification": load(folder / "async-verification.json")["status"],
            "suite_files": compare_hashes(run1_suite, load(folder / "sha256.json.gz")),
            "sweep_files": compare_hashes(run1_sweep, load(folder / "sweep" / "sweep-sha256.json.gz")),
            "requests_identical_to_first_run": sum(rep[k][0] == run1[k][0] for k in run1),
            "requests_compared": len(run1),
            "answers_identical_to_first_run": sum(rep[k][1] == run1[k][1] for k in run1),
            "answers_differing_from_first_run": {k: diff_fields(rep[k][1], run1[k][1])
                                                 for k in run1 if rep[k][1] != run1[k][1]},
            "sweep_within_10_percent": {t: load(folder / "sweep" / "sweep-summary.json")[f"{t}_within_10_percent"]
                                        for t in ("fastest_flow", "lowest_pressure")},
        }
    result["repeat_sweeps_against_each_other"] = compare_hashes(*(load(HERE / j / "sweep" / "sweep-sha256.json.gz")
                                                                   for j in REPEATS))
    a, b = (rep_answers[j] for j in REPEATS)
    result["repeats_identical_to_each_other"] = {"requests": sum(a[k][0] == b[k][0] for k in a),
                                                 "answers": sum(a[k][1] == b[k][1] for k in a), "of": len(a)}
    run1_trend = {w: run1["async-sequence"][1][w] for w in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region")}
    rep_trend = {w: a["async-sequence"][1][w] for w in run1_trend}
    truth = load(RUN1 / "check-live.json")["suite_sequence"]["truth"]
    result["sequence_words"] = {"truth (check-live.json)": truth,
                                "first_run": run1_trend, "first_run_right": sum(run1_trend[w] == truth[w] for w in truth),
                                "repeats": rep_trend, "repeats_right": sum(rep_trend[w] == truth[w] for w in truth)}
    (HERE / "compare-repeats.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
