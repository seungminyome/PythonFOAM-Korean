#!/usr/bin/env python3
"""Summarise a pimpleFoam log of the cylinder runs of 2026-10-27 (offsetCylinder, OpenFOAM v2212).

Usage: summarize_cylinder_log.py log.pimpleFoam   (JSON to stdout)
Steps, first and last time, whether the run reached 'End', and the largest Courant number over
the run and in its last step.
"""
import json
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(errors="replace")
times = [float(t) for t in re.findall(r"^Time = (\S+)", text, re.M)]
courant = [float(c) for c in re.findall(r"^Courant Number mean: \S+ max: (\S+)", text, re.M)]
print(json.dumps({"steps": len(times), "first_time": times[0], "last_time": times[-1],
                  "ended": bool(re.search(r"^End\s*$", text, re.M)),
                  "courant_max_over_run": max(courant), "courant_max_last_step": courant[-1]}, indent=1))
