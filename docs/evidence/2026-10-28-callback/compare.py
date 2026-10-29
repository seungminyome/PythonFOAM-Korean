#!/usr/bin/env python3
"""Compare the PODFoam runs of the 2026-10-28 callback check (callback_check.sbatch).

usage: compare.py <run directory>   (writes <run directory>/comparison.json; needs numpy)

Pairs (the same staged case, settings and LLM_RUN_ID; main's python_module.py from callback-main/
or this branch's): describe-main / describe-new, sequence-main / sequence-new, and the 2-rank
par2-describe-main / par2-describe-new. For each pair:
- every file of the two case folders byte for byte (time and processor directories, telemetry.jsonl,
  the frames, the request body, the POD audit file, the inputs), except the callback source, the
  matplotlib cache, the logs and the three JSON records;
- the solver's lines of log.PODFoam (residuals, Courant numbers, continuity errors, times, POD
  snapshot and SVD lines) line for line;
- llm_request.json, llm_response.json and llm_result.json key by key, after replacing the case
  folder's path; timestamps, process ids, wall times, the arrival step and the pipe counts are set
  aside as run-dependent, and keys only the branch writes (computed_trends...) are listed.
Also: sequence-new's computed_trends against snapshot_runner.sequence_truth of its three frames, and
sequence-tn-new's body against readable_request.sequence_v2_payload(..., thresholds=True,
numbers=...) of its frames, whose bytes must equal sequence-new's frames.

On 2 ranks both processes print to one log, in an order that changes from run to run, so there
the solver lines are compared as sorted lists (the in-order result is recorded too); and the test's
POD module (pod_svd.py with its rank check removed, as in the 2026-10-27 MPI test) has both ranks
write python_svd_audit.npz at the same path, so that file is recorded (readable or not, hash) and
not compared.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "Solver_Examples" / "PODFoam" / "llm_demo"))
import picture_test  # noqa: E402
import readable_request  # noqa: E402
import sequence_test  # noqa: E402
import snapshot_runner  # noqa: E402
from llm_client import encode_json  # noqa: E402

PAIRS = ("describe", "sequence", "par2-describe")
RECORDS = ("llm_request.json", "llm_response.json", "llm_result.json")
SKIP_PARTS = {"mpl", "__pycache__"}
SOLVER_LINE = re.compile(r"Solving for |time step continuity errors|^Courant Number|^Time = |^PIMPLE: iteration"
                         r"|^POD snapshot accepted|^PYTHON snapshot=|^PYTHON SVD|^POD SVD returned")
RUN_DEPENDENT = re.compile(r"(_at|_pid|_wall_s|_elapsed_s|elapsed_since_request_s|"
                           r"cleanup_elapsed_before_result_write_s|solver_stall_s|end_wait_s|arrived_at_step|"
                           r"ipc_select_calls|ipc_bytes_received)$")
ADDED = {"computed_trends", "computed_trends_agreement", "computed_trends_error", "sequence_prompt"}
WALL = re.compile(r"POD analysis callback returned: step=(\d+) wall_seconds=(\S+)")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def files(case):
    out = {}
    for path in case.rglob("*"):
        rel = path.relative_to(case)
        if not path.is_file() or SKIP_PARTS & set(rel.parts):
            continue
        if path.suffix == ".py" or path.name.startswith("log.") or path.name in RECORDS:
            continue
        out[str(rel)] = path
    return out


def kind(rel):
    first = rel.split("/")[0]
    if first.startswith("processor"):
        return "processor directories"
    if re.fullmatch(r"[0-9.eE+-]+", first):
        return "inputs" if float(first) <= 0.1 + 1e-12 else "written time directories"
    if first in ("constant", "system"):
        return "inputs"
    if first == "llm_observation":
        return "frames"
    return rel


def flatten(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from flatten(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from flatten(item, f"{path}[{index}]")
    else:
        yield path, value


def leaf(path):
    return re.sub(r"\[\d+\]", "", path).split(".")[-1]


def compare_record(name, a_case, b_case):
    a_path, b_path = a_case / name, b_case / name
    if not (a_path.exists() and b_path.exists()):
        return {"main": a_path.exists(), "branch": b_path.exists()}
    a = dict(flatten(json.loads(a_path.read_text().replace(str(a_case), "<case>"))))
    b = dict(flatten(json.loads(b_path.read_text().replace(str(b_case), "<case>"))))
    run_dependent, added, unexpected = set(), set(), []
    for path in sorted(set(a) | set(b)):
        if a.get(path, KeyError) == b.get(path, KeyError):
            continue
        top = re.split(r"[.\[]", path)[0]
        if top in ADDED and path not in a:
            added.add(top)
        elif RUN_DEPENDENT.search(leaf(path)):
            run_dependent.add(leaf(path))
        else:
            unexpected.append({"path": path, "main": a.get(path, "<absent>"), "branch": b.get(path, "<absent>")})
    return {"keys_compared": len(set(a) | set(b)), "run_dependent_keys_that_differ": sorted(run_dependent),
            "keys_only_the_branch_writes": sorted(added), "unexpected_differences": unexpected}


def solver_lines(case):
    return [line for line in (case / "log.PODFoam").read_text().splitlines() if SOLVER_LINE.search(line)]


def walls(case, steps):
    found = {int(m[1]): float(m[2]) for m in WALL.finditer((case / "log.PODFoam").read_text())}
    return {"steps": len(found), "median_s": sorted(found.values())[len(found) // 2],
            "at_steps_s": {str(s): found.get(s) for s in steps}}


def npz_state(path):
    """Whether an npz file reads back whole (every member's CRC), and its hash."""
    try:
        with zipfile.ZipFile(path) as archive:
            readable = archive.testzip() is None
    except zipfile.BadZipFile:
        readable = False
    return {"readable": readable, "sha256": sha(path)}


def compare_pair(run, name):
    a_case, b_case = run / f"{name}-main", run / f"{name}-new"
    parallel = name.startswith("par2")
    a_files, b_files = files(a_case), files(b_case)
    if parallel:
        report_audit = {side: npz_state(case / "python_svd_audit.npz") for side, case in
                        (("main", a_case), ("branch", b_case))}
        for listing in (a_files, b_files):
            listing.pop("python_svd_audit.npz", None)
    report = {"callback_sources_sha256": {side: {p.name: sha(p) for p in sorted(case.glob("*.py"))}
                                          for side, case in (("main", a_case), ("branch", b_case))},
              "only_main": sorted(set(a_files) - set(b_files)), "only_branch": sorted(set(b_files) - set(a_files)),
              "identical": {}, "differing": []}
    for rel in sorted(set(a_files) & set(b_files)):
        if a_files[rel].read_bytes() == b_files[rel].read_bytes():
            report["identical"][kind(rel)] = report["identical"].get(kind(rel), 0) + 1
        else:
            report["differing"].append(rel)
    telemetry = [case / "telemetry.jsonl" for case in (a_case, b_case)]
    report["telemetry"] = {"lines": [len(t.read_bytes().splitlines()) for t in telemetry],
                           "sha256": sha(telemetry[0]),
                           "identical": telemetry[0].read_bytes() == telemetry[1].read_bytes(),
                           "tmp_left": [(case / "telemetry.jsonl.tmp").exists() for case in (a_case, b_case)]}
    lines = [solver_lines(case) for case in (a_case, b_case)]
    report["solver_log_lines"] = {"compared": len(lines[0]), "identical_in_order": lines[0] == lines[1]}
    if parallel:
        report["solver_log_lines"]["identical_as_sorted_lists"] = sorted(lines[0]) == sorted(lines[1])
        report["solver_log_lines"]["identical"] = report["solver_log_lines"]["identical_as_sorted_lists"]
        report["python_svd_audit_npz_not_compared"] = report_audit
    else:
        report["solver_log_lines"]["identical"] = lines[0] == lines[1]
    report["records"] = {record: compare_record(record, a_case, b_case) for record in RECORDS}
    log = (b_case / "log.PODFoam").read_text()
    report["branch_telemetry_line"] = next((l for l in log.splitlines() if l.startswith("PYTHON LLM telemetry")), None)
    steps = (100, 499, 500, 501, 999, 1000, 1001, 1249, 1250)
    report["callback_wall"] = {"main": walls(a_case, steps), "branch": walls(b_case, steps)}
    report["pass"] = (not report["only_main"] and not report["only_branch"] and not report["differing"]
                      and report["telemetry"]["identical"] and not any(report["telemetry"]["tmp_left"])
                      and report["solver_log_lines"]["identical"] and report["solver_log_lines"]["compared"] > 0
                      and all(not r.get("unexpected_differences", [1]) for r in report["records"].values()))
    return report


def frames_of(case, steps=(100, 150, 200)):
    folders = [case / "llm_observation" / f"step-{s:06d}" for s in steps]
    return ([readable_request.load_frame(f)[0] for f in folders], [picture_test.load_v2(f)[1] for f in folders])


def main():
    run = Path(sys.argv[1]).resolve()
    report = {"run": str(run), "pairs": {name: compare_pair(run, name) for name in PAIRS}}
    # computed trends of the branch's sequence run against the picture tests' answer key
    frames, truths = frames_of(run / "sequence-new")
    key = json.loads(json.dumps(snapshot_runner.sequence_truth(truths)))
    result = json.loads((run / "sequence-new" / "llm_result.json").read_text())
    report["computed_trends"] = {"recorded": result.get("computed_trends"),
                                 "equal_to_answer_key": result.get("computed_trends") == key,
                                 "status": result.get("status")}
    # the tn form: the body is the tested builder with the numbers from the arrays
    tn = run / "sequence-tn-new"
    tn_frames, tn_truths = frames_of(tn)
    body = (tn / "llm_request_body.json").read_bytes()
    model = json.loads(body)["model"]
    expected = encode_json(readable_request.sequence_v2_payload(
        tn_frames, model=model, own_ranges=True, thresholds=True,
        numbers=[sequence_test.numbers_of(t) for t in tn_truths]))
    same_frames = all(sha(p) == sha(run / "sequence-new" / p.relative_to(tn))
                      for p in (tn / "llm_observation").rglob("*") if p.is_file())
    note = json.loads(json.loads(body)["messages"][1]["content"][0]["text"])
    tn_result = json.loads((tn / "llm_result.json").read_text())
    report["tn_form"] = {"body_equals_builder": body == expected,
                         "system_prompt_is_tn": json.loads(body)["messages"][0]["content"]
                         == readable_request.SEQUENCE_V2OWN_TN_SYSTEM_PROMPT,
                         "frames_identical_to_sequence_new": same_frames, "body_bytes": len(body),
                         "body_sha256": hashlib.sha256(body).hexdigest(), "note": note,
                         "sequence_prompt": tn_result.get("sequence_prompt"),
                         "computed_trends_equal_to_sequence_new": tn_result.get("computed_trends")
                         == result.get("computed_trends")}
    seq_body = (run / "sequence-new" / "llm_request_body.json").read_bytes()
    report["sequence_body_equals_default_builder"] = seq_body == encode_json(readable_request.sequence_v2_payload(
        frames, model=json.loads(seq_body)["model"], own_ranges=True))
    report["status"] = "PASS" if (all(p["pass"] for p in report["pairs"].values())
                                  and report["computed_trends"]["equal_to_answer_key"]
                                  and report["sequence_body_equals_default_builder"]
                                  and all(report["tn_form"][k] for k in (
                                      "body_equals_builder", "system_prompt_is_tn",
                                      "frames_identical_to_sequence_new",
                                      "computed_trends_equal_to_sequence_new"))) else "FAIL"
    (run / "comparison.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({name: {k: p[k] for k in ("identical", "differing", "telemetry", "solver_log_lines", "pass")}
                      for name, p in report["pairs"].items()}, indent=1))
    print("computed trends equal to the answer key:", report["computed_trends"]["equal_to_answer_key"],
          "; tn body equals builder:", report["tn_form"]["body_equals_builder"], "; status:", report["status"])
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
