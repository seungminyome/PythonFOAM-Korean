"""Check one async suite run (async_v2.slurm) against its own records and two earlier v2212 1000-step runs.
Usage: compare_suite.py <pod-llm-async.* folder>
1. async-verification.json: status, settings, per-case exit/model status/files_identical_to_no_request_baseline/frames.
2. Independent hash pass: every file under every written time folder (name > start time) of each case against the
   same path in async-no-llm.
3. async-no-llm frame fields_sha256 and start_files_sha256 against gpu-suite-24950817 (fork docs evidence, bf7a06e)
   and r3/assemble run-25089703 (b4803de + two test files).
Pattern: r3/assemble/tools/compare_suite.py."""
import hashlib, json, sys
from pathlib import Path

run = Path(sys.argv[1])
new = json.loads((run / 'async-verification.json').read_text())
G = Path('/cluster/medbow/gscratch/syome/github_repos')
REFS = {
    '24950817': G / 'PythonFOAM/docs/evidence/2026-10-30-versions/gpu-suite-24950817/async-verification.json',
    '25089703': G / 'pod-versions-20261030/r3/assemble/pod-async-v2/run-25089703/pod-llm-async.vb0shv/async-verification.json',
}
CASES = ['async-no-llm', 'async-describe', 'async-sequence', 'async-server-error', 'async-timeout']
s = new['settings']
print('status', new['status'], '| steps', s.get('steps'), 'write_every', s.get('write_every'), 'request_step',
      s.get('request_step'), 'sequence', s.get('sequence_steps'), 'start', s.get('start_time_s'))
for c in CASES:
    d = new[c]
    flags = [f.get('same_fields_as_baseline', f.get('same_fields_as_baseline_frame')) for f in d.get('frames', [])]
    print(f"{c:20s} exit={new['resources'][c].get('exit_status')} model={d.get('model_status')} "
          f"files_identical_to_no_request_baseline={d.get('files_identical_to_no_request_baseline')} "
          f"frames={len(flags)} same_fields_flags={flags} stall={d.get('solver_stall_s')} "
          f"infer={d.get('inference_wall_s')} maxCo={d.get('max_courant')}")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def written(case):
    start = float(s.get('start_time_s', 0.1))
    out = {}
    for t in case.iterdir():
        try:
            v = float(t.name)
        except ValueError:
            continue
        if t.is_dir() and v > start + 1e-12:
            for f in sorted(t.rglob('*')):
                if f.is_file():
                    out[str(f.relative_to(case))] = sha(f)
    return out


base = written(run / 'async-no-llm')
folders = sorted({k.split('/')[0] for k in base}, key=float)
print(f"independent hash pass: async-no-llm wrote {len(base)} files in {len(folders)} time folders {folders}")
for c in CASES[1:]:
    w = written(run / c)
    same = sum(1 for k, v in w.items() if base.get(k) == v)
    print(f"  {c:20s} files {len(w)} identical {same} missing {len(set(base) - set(w))} extra {len(set(w) - set(base))}")


def frames(v, c):
    return {f['step']: f.get('fields_sha256') for f in v[c].get('frames', [])}


fn = frames(new, 'async-no-llm')
for name, path in REFS.items():
    ref = json.loads(path.read_text())
    fr = frames(ref, 'async-no-llm')
    print(f"vs {name}: start_files_sha256 equal {s.get('start_files_sha256') == ref['settings'].get('start_files_sha256')}; "
          f"async-no-llm frame fields_sha256 equal {{{', '.join(f'{k}: {fn.get(k) == fr.get(k)}' for k in sorted(set(fn) | set(fr)))}}}")
print('timings_s', {k: round(t, 1) for k, t in new.get('timings', {}).items()})
