#!/usr/bin/env python3
"""Write manifest.json for docs/evidence/2026-11-03-wrong-setup-2/ from what is there.

Usage: make_manifest.py <evidence dir>
Each file is compared with its source under the work folders on MedicineBow; a file that equals its
source is kind byte-preserved, a gzip -9 -n copy of a source is kind gzip copy (source_sha256 is the
hash of the uncompressed bytes), and a file written for this folder is kind derived.
"""
import gzip
import hashlib
import json
import sys
from pathlib import Path

BASE = Path('/cluster/medbow/gscratch/syome/github_repos')
WORK = BASE / 'wrong-setup-2-20261103'
RESULTS = WORK / 'results' / 'window-test-25107731'
SOURCES = {
    'design.json': BASE / 'flow-states-20261103' / 'design.json',
    'baselines.json': WORK / 'final' / 'baselines.json',
    'flow-check.json': WORK / 'final' / 'flow-check.json',
    'contact-8000.png': WORK / 'final' / 'contact-8000.png',
    'test-set/manifest.json': WORK / 'final' / 'set' / 'manifest.json',
    'test-set/leak-check.json': WORK / 'final' / 'set' / 'leak-check.json',
    'pilot/contact-8000.png': WORK / 'pilot' / 'contact-8000.png',
    'pilot/design.json': WORK / 'pilot' / 'cases' / 'design.json',
    'pilot/flow-check.json': WORK / 'pilot' / 'flow-check.json',
    'pilot/pilot_visibility.py': WORK / 'pilot' / 'pilot_visibility.py',
    'pilot/visibility-arrays.txt': WORK / 'pilot' / 'visibility-arrays.txt',
    'jobs/build_set.sbatch': WORK / 'jobs' / 'build_set.sbatch',
    'jobs/run_flow.sbatch': WORK / 'jobs' / 'run_flow.sbatch',
    'jobs/submit_gpu.sh': WORK / 'jobs' / 'submit_gpu.sh',
    'jobs/build-25107036.out': WORK / 'final' / 'jobs' / 'build-25107036.out',
    'results/run.json': RESULTS / '31b' / 'run.json',
    'results/server-31b.cmd': RESULTS / 'server-31b.cmd',
    'results/report.md': WORK / 'final' / 'report.md',
    'results/reasons.jsonl': WORK / 'final' / 'reasons.jsonl',
    'results/runtime/llama-server-version.txt': RESULTS / 'llama-server-version.txt',
    'results/runtime/gpu-31b.txt': RESULTS / 'gpu-31b.txt',
    'results/runtime/models-31b.json': RESULTS / 'models-31b.json',
    'results/runtime/nvidia-smi.txt': RESULTS / 'nvidia-smi.txt',
    'results/runtime/sha256.txt': RESULTS / 'sha256.txt',
}
for s in ('stated-t0', 'stated-t07a', 'stated-t07b', 'blind-t0', 'blind-t07a', 'blind-t07b'):
    SOURCES[f'results/wrong-setup2-{s}/metrics.jsonl'] = RESULTS / '31b' / f'wrong-setup2-{s}' / 'metrics.jsonl'
GZIP = {
    'job/pod-window-test-25107731.out.gz': WORK / 'results' / 'pod-window-test-25107731.out',
    'results/runtime/server-31b.log.gz': RESULTS / 'server-31b.log',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main(folder):
    folder = Path(folder)
    files = []
    for path in sorted(p for p in folder.rglob('*') if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        if rel == 'manifest.json':
            continue
        data = path.read_bytes()
        entry = {'path': rel, 'source': 'written for this folder', 'kind': 'derived', 'bytes': len(data), 'sha256': sha(data)}
        if rel in SOURCES:
            src = SOURCES[rel].read_bytes()
            if src != data:
                raise SystemExit(f'{rel} differs from {SOURCES[rel]}')
            entry['source'] = str(SOURCES[rel].relative_to(BASE))
            entry['kind'] = 'byte-preserved'
        elif rel in GZIP:
            src = GZIP[rel].read_bytes()
            if gzip.decompress(data) != src:
                raise SystemExit(f'{rel} is not a gzip copy of {GZIP[rel]}')
            entry['source'] = str(GZIP[rel].relative_to(BASE))
            entry['kind'] = 'gzip copy'
            entry['source_sha256'] = sha(src)
        files.append(entry)
    manifest = {
        'scope': 'Wrong-setup test 2 of 2026-11-03 on MedicineBow: 29 pairs of pimpleFoam runs of the 2D step case, '
                 'each pair one base setup run as written and with one change; one run is one sample; three states '
                 'per run; Gemma 4 31B (QAT Q4_0) on 1,044 requests in six sets (stated or blind note, temperature 0 '
                 'or 0.7 with two seeds); the plan, scoring and baselines fixed before any request; the pilot; the '
                 'answer key as a hash; leak check; flow check; the report and the reasons.',
        'source_runs': [
            'pilot pimpleFoam runs: jobs 25106856 (array 0 to 11) and 25106882 (task 12)',
            'pimpleFoam runs of the design: job 25106926 (array 0 to 59)',
            'flow-check, build, check, baselines, contact: job 25107036',
            'model: window-test-25107731 (job 25107037 failed before any request)',
            'report and reasons: wrong_setup_test2.py report on a login node, 2026-11-04',
        ],
        'notes': [
            "Sources are paths under /cluster/medbow/gscratch/syome/github_repos/ on MedicineBow, or 'written for this folder'.",
            'Files of kind gzip copy are gzip -9 -n copies of the named source; source_sha256 is the hash of the uncompressed bytes.',
            'Every byte-preserved file was compared with its source when this manifest was written.',
            'test-set/truth.private.sha256 is the hash of the answer key, which stays on the cluster; the requests are '
            'not in this folder (1,044 files of 178 to 233 KB, 225 MB in all), their hashes are in test-set/manifest.json.',
        ],
        'files': files,
    }
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(f'{len(files)} files; kinds:', {k: sum(1 for f in files if f['kind'] == k) for k in ('byte-preserved', 'gzip copy', 'derived')})


if __name__ == '__main__':
    main(sys.argv[1])
