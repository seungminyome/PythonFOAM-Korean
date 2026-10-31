#!/usr/bin/env python3
"""Truth table of PODFoam's POD schedule checked against real runs.

Usage (inside the image, OpenFOAM sourced): schedule.py VER OUT_ROOT
The prediction below is written from the rule in the PR's text, not by calling the code:
  podSvdInterval 0, no analysis_func:
      write step and snapshots since last SVD -> SVD, no snapshot
      otherwise                               -> snapshot, no SVD
  podSvdInterval 0, analysis_func: every step a snapshot; write steps also an SVD
  podSvdInterval k>0: every step a snapshot; SVD when snapshot count % k == 0
"""
import json, re, shutil, subprocess, sys, os
from pathlib import Path

R = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/refix/cpp')
VER, OUT = sys.argv[1], Path(sys.argv[2])
FORK = R/'src/fork/Solver_Examples/PODFoam'
UP = R/'src/upstream/Solver_Examples/PODFoam'
PY = sys.executable
OUT.mkdir(parents=True, exist_ok=True)
BIN = {'fork': R/f'build/{VER}/fork/bin/PODFoam', 'upstream': R/f'build/{VER}/upstream/bin/PODFoam'}
DT = 1e-7

ANALYSIS = '''

def analysis_func(state):
    print(f"ANALYSIS step={state['step']} u={state['u_cells'].shape}", flush=True)
'''


def predict(nsteps, wi, analysis, interval, module):
    rows, since, count, k = [], 0, 0, 0
    for step in range(1, nsteps + 1):
        write = step % wi == 0
        if interval:
            collect, svd = True, (count + 1) % interval == 0
        elif analysis:
            collect, svd = True, write
        else:
            collect, svd = (not write or since == 0), (write and since > 0)
        window = None
        if collect:
            since += 1
            count += 1
        modes = None
        if svd:
            window = since
            if module == 'validation':
                modes = min(window, 5)
            else:  # upstream's online SVD keeps k modes and adds the window
                k = min(k + window, 5) if k else min(window, 5)
                modes = k
            since = 0
        rows.append(dict(step=step, write=write, collect=collect, svd=svd, window=window, modes=modes))
    return rows


def module_text(module, analysis):
    src = UP/'Run_Case/python_module.py' if module == 'upstream' else FORK/'validation/python_module.py'
    return src.read_text() + (ANALYSIS if analysis else '')


def base_case():
    base = OUT/'base'
    if not (base/'constant/polyMesh/points').exists():
        stage = OUT/'stage'
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir()
        subprocess.run([PY, str(FORK/'validation/prepare_case.py'), str(FORK), str(stage)], check=True)
        shutil.rmtree(base, ignore_errors=True)
        shutil.copytree(stage/'fixed-pod', base)
        shutil.rmtree(stage)
        subprocess.run(['blockMesh', '-case', str(base)], check=True, stdout=subprocess.DEVNULL)
        (base/'system/decomposeParDict').write_text('FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }\nnumberOfSubdomains 2;\nmethod scotch;\n')
    return base


def make_case(name, module_src, nsteps, wi, interval):
    c = OUT/name
    shutil.rmtree(c, ignore_errors=True)
    shutil.copytree(base_case(), c, symlinks=True)
    cd = c/'system/controlDict'
    t = cd.read_text()
    t = re.sub(r'^endTime .*$', f'endTime {nsteps*DT:.10g};', t, flags=re.M)
    t = re.sub(r'^writeInterval .*$', f'writeInterval {wi};', t, flags=re.M)
    t = re.sub(r'^podSvdInterval .*$', f'podSvdInterval {interval};', t, flags=re.M)
    cd.write_text(t)
    (c/'python_module.py').write_text(module_src)
    return c


def run(c, binary, nprocs=1, timeout=900):
    env = dict(os.environ, MPLCONFIGDIR=str(c/'mpl'))
    cmd = [str(binary), '-case', str(c)]
    if nprocs > 1:
        subprocess.run(['decomposePar', '-case', str(c)], cwd=c, env=env, stdout=open(c/'log.decomposePar', 'w'), stderr=subprocess.STDOUT)
        cmd = ['mpirun', '--oversubscribe', '-np', str(nprocs)] + cmd + ['-parallel']
    try:
        with open(c/'log.PODFoam', 'w') as log:
            p = subprocess.run(cmd, cwd=c, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode
    except subprocess.TimeoutExpired:
        return 'timeout'


def time_dirs(root):
    out = {}
    for d in root.iterdir():
        try:
            t = float(d.name)
        except ValueError:
            continue
        if t > 0:
            out[round(t/DT)] = d
    return out


def modes_in(d):
    return sorted(int(m.group(1)) for f in d.iterdir() if (m := re.fullmatch(r'upod_(\d+)', f.name)))


def check_files(rows, root):
    """Compare written modes and fields in one time-directory tree with the table."""
    problems = []
    dirs = time_dirs(root)
    for r in rows:
        d = dirs.get(r['step'])
        want = list(range(r['modes'])) if r['svd'] else []
        have = modes_in(d) if d else []
        if have != want:
            problems.append(f"step {r['step']}: POD files {have}, expected {want}")
        if r['write'] and not (d and (d/'U').exists()):
            problems.append(f"step {r['step']}: write step without U")
        if not r['write'] and d and (d/'U').exists():
            problems.append(f"step {r['step']}: U written on a non-write step")
    return problems


def check_log(rows, c, analysis, nprocs=1):
    text = (c/'log.PODFoam').read_text(errors='replace')
    parts = re.split(r'^Time = (\S+) deltaT.*$', text, flags=re.M)
    segs = parts[2::2]
    problems = []
    if len(segs) != len(rows):
        problems.append(f"log has {len(segs)} steps, expected {len(rows)}")
    for r, s in zip(rows, segs):
        ncol = len(re.findall(r'^POD snapshot accepted', s, flags=re.M))
        nsvd = re.findall(r'^POD SVD returned to OpenFOAM: rows=\d+ modes=(\d+)', s, flags=re.M)
        py_col = len(re.findall(r'PYTHON snapshot=|Collecting snapshots iteration', s))
        ana = len(re.findall(r'^POD analysis callback returned', s, flags=re.M))
        if ncol != int(r['collect']):
            problems.append(f"step {r['step']}: {ncol} snapshots in C++ log, expected {int(r['collect'])}")
        if py_col != nprocs*int(r['collect']):
            problems.append(f"step {r['step']}: {py_col} snapshot calls in Python, expected {nprocs*int(r['collect'])}")
        if bool(nsvd) != r['svd']:
            problems.append(f"step {r['step']}: SVD {nsvd}, expected {r['svd']}")
        if nsvd and int(nsvd[0]) != r['modes']:
            problems.append(f"step {r['step']}: {nsvd[0]} modes, expected {r['modes']}")
        if analysis and ana != 1:
            problems.append(f"step {r['step']}: {ana} analysis calls")
        if not analysis and ana:
            problems.append(f"step {r['step']}: unexpected analysis call")
    return problems, ('Python finalized successfully' in text), ('FOAM FATAL' in text)


results = []
NSTEPS = {1: 12, 3: 20, 25: 60}
serial = [(m, a, wi, 0) for m in ('upstream', 'validation') for a in (False, True) for wi in (1, 3, 25)]
serial += [('validation', False, 25, 7), ('upstream', False, 3, 7), ('upstream', True, 3, 2)]
for module, analysis, wi, interval in serial:
    name = f"fork-{module}-{'ana' if analysis else 'plain'}-wi{wi}-svd{interval}"
    n = max(NSTEPS[wi], 21 if interval else 0)
    rows = predict(n, wi, analysis, interval, module)
    c = make_case(name, module_text(module, analysis), n, wi, interval)
    status = run(c, BIN['fork'])
    log_problems, finalized, fatal = check_log(rows, c, analysis)
    file_problems = check_files(rows, c)
    table = ''.join('S' if r['svd'] and r['collect'] else 'V' if r['svd'] else 'c' for r in rows)
    res = dict(version=VER, build='fork', module=module, analysis=analysis, writeInterval=wi, podSvdInterval=interval, steps=n,
               exit=status, finalized=finalized, fatal=fatal, schedule=table,
               modes=[r['modes'] for r in rows if r['svd']], problems=log_problems + file_problems)
    results.append(res)
    print(json.dumps({k: res[k] for k in ('module', 'analysis', 'writeInterval', 'podSvdInterval', 'exit', 'schedule', 'modes')}), 'problems:', res['problems'][:5], flush=True)
    for d in c.glob('[0-9]*'):
        for f in ('U', 'p', 'phi', 'uniform'):
            pass

# two ranks: upstream's module; the two ranks must make the same calls and write the same files
for analysis, wi, interval in [(False, 1, 0), (False, 3, 0), (False, 25, 0), (True, 3, 0), (False, 3, 7)]:
    name = f"fork-par2-upstream-{'ana' if analysis else 'plain'}-wi{wi}-svd{interval}"
    n = max(NSTEPS[wi], 21 if interval else 0)
    rows = predict(n, wi, analysis, interval, 'upstream')
    c = make_case(name, module_text('upstream', analysis), n, wi, interval)
    status = run(c, BIN['fork'], nprocs=2)
    log_problems, finalized, fatal = check_log(rows, c, analysis, nprocs=2)
    p0 = check_files(rows, c/'processor0')
    p1 = check_files(rows, c/'processor1')
    res = dict(version=VER, build='fork', module='upstream', ranks=2, analysis=analysis, writeInterval=wi, podSvdInterval=interval, steps=n,
               exit=status, finalized=finalized, fatal=fatal, problems=log_problems + ['p0 ' + x for x in p0] + ['p1 ' + x for x in p1])
    results.append(res)
    print(json.dumps({k: res[k] for k in ('ranks', 'analysis', 'writeInterval', 'podSvdInterval', 'exit')}), 'problems:', res['problems'][:5], flush=True)

# upstream's own solver with the same modules and write intervals, for comparison
for module in ('upstream', 'validation'):
    for wi in (1, 3, 25):
        n = NSTEPS[wi]
        name = f"upstream-{module}-wi{wi}"
        c = make_case(name, module_text(module, False), n, wi, 0)
        status = run(c, BIN['upstream'], timeout=300)
        text = (c/'log.PODFoam').read_text(errors='replace')
        dirs = time_dirs(c)
        res = dict(version=VER, build='upstream', module=module, writeInterval=wi, steps=n, exit=status,
                   python_collect=len(re.findall(r'PYTHON snapshot=|Collecting snapshots iteration', text)),
                   written={k: modes_in(v) for k, v in sorted(dirs.items())},
                   tail=text[-400:])
        results.append(res)
        print(json.dumps({k: res[k] for k in ('module', 'writeInterval', 'exit', 'python_collect')}), flush=True)

(OUT/'schedule.json').write_text(json.dumps(results, indent=1))
bad = [r for r in results if r['build'] == 'fork' and (r['problems'] or r['exit'] != 0 or not r['finalized'] or r['fatal'])]
print('fork runs', sum(r['build'] == 'fork' for r in results), 'with problems', len(bad))
