#!/usr/bin/env python3
"""Fork rows of the scenario runs, before (review-cpp) and after (refix/cpp): lines that changed, and rows for the fixed findings."""
import json, sys
from pathlib import Path
W = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr')
for ver in ('v2106', '8'):
    old = json.loads((W/f'review-cpp/scen-{ver}/scenarios.json').read_text()) if (W/f'review-cpp/scen-{ver}/scenarios.json').exists() else {}
    new = json.loads((W/f'refix/cpp/scen-{ver}/scenarios.json').read_text())
    print('=====', ver, len(old), len(new))
    keys = ('exit', 'timed_out', 'end', 'finalized', 'fatal')
    same = 0
    for name in sorted(set(old) | set(new)):
        if name == 'driver-errors':
            print('driver-errors', new.get(name)); continue
        a = [r for r in old.get(name, []) if isinstance(r, dict) and r.get('build') == 'fork']
        b = [r for r in new.get(name, []) if isinstance(r, dict) and r.get('build') == 'fork']
        ra = [tuple(r.get(k) for k in keys) for r in a]; rb = [tuple(r.get(k) for k in keys) for r in b]
        if ra == rb:
            same += 1
        else:
            print(name, '\n   before', ra, '\n   after ', rb)
            for r in b:
                print('   tail:', [l for l in r['tail'] if any(w in l for w in ('modes', 'must be', 'SystemExit', 'ModuleNot', 'Cannot', 'callable', 'End'))][:5])
    print('unchanged rows:', same)
