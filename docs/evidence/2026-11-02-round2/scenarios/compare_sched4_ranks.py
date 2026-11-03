#!/usr/bin/env python3
"""compare_sched4.py with the rank count in the row key. compare_sched4.py keyed on 'nprocs',
which no record has (schedule.py writes 'ranks'), so each 2-rank row replaced its serial row.
Reads the records in this repository and writes compare_sched4_ranks.json next to this file."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
E = HERE.parent.parent / '2026-10-30-versions' / 'schedule'
SRC = {'v2012': HERE / 'sched-v2012/schedule.json', 'v2106': E / 'ef78700-v2106-24950748/schedule.json',
       'v2212': HERE / 'sched-v2212/schedule.json', '8': E / 'ef78700-8-24950749/schedule.json'}
KEYS = ('exit', 'finalized', 'fatal', 'schedule', 'modes', 'problems', 'python_collect')
rows, per = {}, {}
for v, p in SRC.items():
    recs = json.loads(p.read_text())
    per[v] = len(recs)
    for r in recs:
        k = (r.get('build'), r.get('module'), r.get('analysis'), r.get('writeInterval'), r.get('podSvdInterval'), r.get('ranks', 1))
        assert v not in rows.get(k, {}), (v, k)
        rows.setdefault(k, {})[v] = {x: r.get(x) for x in KEYS if x in r}
same = sum(1 for byv in rows.values() if len(byv) == 4 and len({json.dumps(x, sort_keys=True) for x in byv.values()}) == 1)
print('records per version:', per, 'rows:', len(rows), 'identical on all four:', same)
(HERE / 'compare_sched4_ranks.json').write_text(json.dumps({'records_per_version': per, 'rows': len(rows), 'identical_on_all_four': same,
    'by_row': {str(k): v for k, v in rows.items()}}, indent=1) + '\n')
