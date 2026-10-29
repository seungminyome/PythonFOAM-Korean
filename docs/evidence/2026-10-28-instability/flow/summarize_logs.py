#!/usr/bin/env python3
"""Summarise the pimpleFoam logs of the runs the 2026-10-28 instability test uses (standard library).

Usage: summarize_logs.py name=path/log.pimpleFoam [...]   (JSON to stdout)
For each log: steps, first and last time, whether it reached 'End' (if not, it crashed in its
last logged step), and the largest Courant number printed before each step (computed from the
state at the end of the step before): at step 1, the smallest and largest over the run, the
step of the largest, the largest from step 11 on, at the last step. For a run that crashed,
also the whole series.
"""
import json
import re
import sys
from pathlib import Path

out = {}
for arg in sys.argv[1:]:
    name, path = arg.split("=", 1)
    steps, courant, ended = [], None, False
    for line in Path(path).read_text(errors="replace").splitlines():
        match = re.match(r"^Courant Number mean: \S+ max: (\S+)", line)
        if match:
            courant = float(match.group(1))
        elif re.match(r"^Time = \S+\s*$", line):
            steps.append((line.split("=", 1)[1].strip(), courant))
        elif line.strip() == "End":
            ended = True
    values = [c for _, c in steps]
    entry = {"steps": len(steps), "first_time": steps[0][0], "last_time": steps[-1][0], "ended": ended,
             "crash_step": None if ended else len(steps),
             "courant_max_step_1": values[0], "courant_max_min": min(values), "courant_max_max": max(values),
             "courant_max_max_at_step": values.index(max(values)) + 1,
             "courant_max_max_from_step_11": max(values[10:]) if len(values) > 10 else None, "courant_max_last_step": values[-1]}
    if not ended:
        entry["courant_max_by_step"] = values
    out[name] = entry
print(json.dumps(out, indent=1))
