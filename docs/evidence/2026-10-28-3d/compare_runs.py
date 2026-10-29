#!/usr/bin/env python3
"""Compare two runs of slice_test.sbatch file by file; writes a JSON report.

  compare_runs.py <run A> <run B> <output.json>

For every case folder of the test: the frames (llm_observation/), the request body and
the written time directories, by SHA-256. Job 24929500 ran commit 07759b0 and job
24929629 commit c7a25d3; between them only a log line of PythonCreate.H changed.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

CASES = ("serial3d", "par3d", "noobs3d", "slicez3d", "badz3d", "outz3d", "serial2d")


def files(case):
    case = Path(case)
    found = {}
    for path in sorted(case.rglob("*")):
        relative = path.relative_to(case)
        top = relative.parts[0]
        if path.is_file() and (top == "llm_observation" or relative.name == "llm_request_body.json"
                               or (re.fullmatch(r"0\.\d+", top) and top != "0.1")):
            found[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def main(run_a, run_b, output):
    report = {"run_a": str(run_a), "run_b": str(run_b), "cases": {}}
    for name in CASES:
        a, b = files(Path(run_a) / name), files(Path(run_b) / name)
        names = sorted(set(a) | set(b))
        differing = [n for n in names if a.get(n) != b.get(n)]
        report["cases"][name] = {"files": len(names), "identical": len(names) - len(differing),
                                 "differing": differing}
    Path(output).write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: (v["files"], v["identical"]) for k, v in report["cases"].items()}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
