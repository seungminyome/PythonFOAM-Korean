#!/usr/bin/env python3
"""Summarise the attempts at an unstable flow of 2026-10-27 (pimpleFoam, backward-facing step).

Usage: summarize_unstable.py UNSTABLE_DIR   (the folder with one case per attempt; JSON to stdout)
For each case: the time step and endTime (system/controlDict), the convection scheme of U
(system/fvSchemes, div(phi,U)), the number of time steps in log.pimpleFoam, the largest
Courant number of the first and of the last step, the largest |U| magnitude bound if bounding
was reported, and how the run ended ('End', a floating point exception, or neither).
"""
import json
import re
import sys
from pathlib import Path


def entry(text, key):
    m = re.search(rf"^\s*{re.escape(key)}\s+([^;]+);", text, re.M)
    return m.group(1).strip() if m else None


def main(folder):
    out = {}
    for case in sorted(p for p in Path(folder).iterdir() if p.is_dir()):
        control = (case / "system" / "controlDict").read_text()
        schemes = (case / "system" / "fvSchemes").read_text()
        log = (case / "log.pimpleFoam").read_text(errors="replace")
        courant = [float(x) for x in re.findall(r"^Courant Number mean: \S+ max: (\S+)", log, re.M)]
        out[case.name] = {
            "deltaT": entry(control, "deltaT"), "endTime": entry(control, "endTime"),
            "div(phi,U)": entry(schemes, "div(phi,U)"),
            "steps": len(re.findall(r"^Time = ", log, re.M)),
            "courant_max_first": courant[0] if courant else None,
            "courant_max_last": courant[-1] if courant else None,
            "ended": "End" if re.search(r"^End\s*$", log, re.M) else
                     ("floating point exception" if "sigFpe" in log or "Floating point exception" in log else "neither"),
        }
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
