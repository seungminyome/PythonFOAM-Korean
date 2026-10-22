#!/usr/bin/env python3
"""Summarize the pimpleFoam log of the developed run (job 24757429): steps, time step and Courant number.

usage: summarize_log.py <log.pimpleFoam>   (the log is in developed-flow-20261022.tar.gz of the release:
       flow-states-20261022/long-100ms/log.pimpleFoam)
pimpleFoam prints, for each step, the Courant number of the current step, then deltaT and Time."""
import json
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()
blocks = [(float(t), float(d), float(c)) for c, d, t in re.findall(
    r'^Courant Number mean: \S+ max: (\S+)\ndeltaT = (\S+)\nTime = (\S+)', text, re.M)]
assert len(blocks) == len(re.findall(r'^Time = ', text, re.M))
first_max = max(blocks, key=lambda b: b[2])
rest = [b for b in blocks if b is not first_max]
late = [b for b in blocks if b[0] >= 0.03]
summary = {
    'steps': len(blocks), 'end_time_s': blocks[-1][0], 'ended': bool(re.search(r'^End$', text, re.M)),
    'turbulence_model': re.search(r'^Selecting turbulence model type (\S+)', text, re.M)[1],
    'delta_t_s_range': [min(b[1] for b in blocks), max(b[1] for b in blocks)],
    'courant_max': {'value': first_max[2], 'time_s': first_max[0], 'step': blocks.index(first_max) + 1},
    'courant_max_other_steps': max(b[2] for b in rest),
    'steps_with_courant_above_0.5': sum(b[2] > 0.5 for b in blocks),
    'last_time_with_courant_above_0.49_s': max(b[0] for b in blocks if b[2] > 0.49),
    'last_time_with_delta_t_below_4.99e-6_s': max(b[0] for b in blocks if b[1] < 4.99e-6),
    'from_0.03_s': {'steps': len(late), 'courant_max': max(b[2] for b in late),
                    'delta_t_s_range': [min(b[1] for b in late), max(b[1] for b in late)]},
    'execution_time_s': float(re.findall(r'^ExecutionTime = (\S+) s', text, re.M)[-1]),
}
print(json.dumps(summary, indent=1))
