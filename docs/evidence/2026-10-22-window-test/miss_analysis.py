"""For each wrong position answer (more than 10 % of the plotted range from the true cell), how fast is
the flow, or how low the pressure, at the point the model named, relative to the true extreme?

usage: miss_analysis.py <test set folder> <results folder of one job> [output json]
The answered point is the cell whose centre is nearest to it among the cells inside the plotted range."""
import json
import math
import sys
from pathlib import Path

import numpy as np


def main():
    tests, results = Path(sys.argv[1]), Path(sys.argv[2])
    manifest = json.loads((tests / 'manifest.json').read_text())
    requests = {(r['set'], r['name']): r for r in manifest['requests']}
    truth = json.loads((tests / 'truth.private.json').read_text())
    cache, out = {}, {}
    for model in sorted(p.name for p in results.iterdir() if (p / 'run.json').exists()):
        for set_name in ('flow-window-v1', 'flow-window-v2'):
            path = results / model / set_name / 'metrics.jsonl'
            if not path.exists():
                continue
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            misses = {'fastest_flow': [], 'lowest_pressure': []}
            for r in rows:
                so = r.get('structured_output')
                if not so:
                    continue
                key = truth[f"{set_name}/{r['name']}"]
                frame = tests / requests[(set_name, r['name'])]['sources']['frame']
                if frame not in cache:
                    with np.load(frame / 'fields.npz') as z:
                        cache[frame] = (np.array(z['centres']), np.linalg.norm(z['U'], axis=1), np.array(z['p']))
                c, speed, p = cache[frame]
                (x0, x1), (y0, y1) = key['plotted_range_m']['x'], key['plotted_range_m']['y']
                inside = np.flatnonzero((c[:, 0] >= x0) & (c[:, 0] <= x1) & (c[:, 1] >= y0) & (c[:, 1] <= y1))
                for target, values, best in (('fastest_flow', speed, speed[inside].max()),
                                             ('lowest_pressure', p, p[inside].min())):
                    ax, ay = so[f'{target}_x_percent'], so[f'{target}_y_percent']
                    t = key[target]
                    if math.hypot(ax - t['x_percent'], ay - t['y_percent']) <= 10.0:
                        continue
                    X, Y = x0 + ax / 100 * (x1 - x0), y0 + ay / 100 * (y1 - y0)
                    i = inside[np.argmin((c[inside, 0] - X) ** 2 + (c[inside, 1] - Y) ** 2)]
                    misses[target].append(round(float(values[i] / best), 3))
            out.setdefault(model, {})[set_name] = {
                t: {'misses': len(v), 'ratio_at_answer': sorted(v),
                    'at_least_90_percent_of_extreme': sum(x >= 0.9 for x in v)} for t, v in misses.items()}
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(text + '\n')
    for model, sets in out.items():
        v2 = sets.get('flow-window-v2', {})
        print(model, {t: (d['misses'], d['at_least_90_percent_of_extreme']) for t, d in v2.items()})


if __name__ == '__main__':
    main()
