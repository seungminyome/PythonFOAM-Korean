"""Compare every written time directory of each sweep case with the suite's async-no-llm baseline.

usage: compare_sweep_fields.py <suite run dir> <sweep dir> <output json>
A sweep case starts from the same state and runs with the same settings as the baseline, with a
describe request at one step. Files are compared byte for byte; for files that differ, the largest
difference of the internal field relative to the largest magnitude in the baseline file is given."""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def values(path):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(), flags=re.S)
    match = re.search(r'internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;', text, re.S)
    return np.array(match[3].replace('(', ' ').replace(')', ' ').split(), dtype=float)


def time_dirs(case, t0):
    return {d.name: d for d in case.iterdir()
            if d.is_dir() and re.fullmatch(r'[0-9.eE+-]+', d.name) and float(d.name) > t0 + 1e-12}


def main():
    suite, sweep, output = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    t0 = json.loads((suite / 'async-settings.json').read_text())['start_time_s']
    baseline = time_dirs(suite / 'async-no-llm', t0)
    plan = json.loads((sweep / 'sweep-plan.json').read_text())['plan']
    report = {'baseline': 'async-no-llm', 'cases': {}}
    identical, differ_names, worst = 0, set(), 0.0
    total = 0
    for item in plan:
        case = sweep / item['name']
        dirs = time_dirs(case, t0)
        c = {'time_dirs': len(dirs), 'files': 0, 'identical': 0, 'differ': {}, 'not_in_baseline': []}
        for name, d in sorted(dirs.items(), key=lambda kv: float(kv[0])):
            ref = baseline.get(name)
            if ref is None:
                c['not_in_baseline'].append(name)
                continue
            for f in sorted(p for p in d.rglob('*') if p.is_file()):
                rel = str(f.relative_to(d))
                c['files'] += 1
                other = ref / rel
                if other.is_file() and digest(f) == digest(other):
                    c['identical'] += 1
                    continue
                a, b = values(other), values(f)
                r = float(np.abs(a - b).max() / np.abs(a).max())
                c['differ'][rel] = max(c['differ'].get(rel, 0.0), r)
                differ_names.add(rel)
                worst = max(worst, r)
        total += c['files']
        identical += c['identical']
        report['cases'][item['name']] = c
    report.update(files_compared=total, files_identical=identical, files_differing=total - identical,
                  differing_names=sorted(differ_names), largest_relative_difference=worst)
    output.write_text(json.dumps(report, indent=1) + '\n')
    print(f'{identical} of {total} files identical; differing names: {sorted(differ_names)}; '
          f'largest relative difference {worst:.2e}')


if __name__ == '__main__':
    sys.exit(main())
