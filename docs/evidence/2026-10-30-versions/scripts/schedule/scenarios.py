#!/usr/bin/env python3
"""Adversarial runs of PODFoam: failure scenarios, fork against upstream.
Usage (inside the image, OpenFOAM sourced): scenarios.py VER OUT_ROOT [NAME_FILTER]
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

R = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/refix/cpp')
VER, OUT = sys.argv[1], Path(sys.argv[2])
FILTER = sys.argv[3] if len(sys.argv) > 3 else ''
FORK = R/'src/fork/Solver_Examples/PODFoam'
UP = R/'src/upstream/Solver_Examples/PODFoam'
PY = sys.executable
BIN = {'fork': R/f'build/{VER}/fork/bin/PODFoam', 'upstream': R/f'build/{VER}/upstream/bin/PODFoam'}
OUT.mkdir(parents=True, exist_ok=True)
DT = 1e-7
UPMOD = (UP/'Run_Case/python_module.py').read_text()
VALMOD = (FORK/'validation/python_module.py').read_text()
results = {}

MINI = '''
import numpy as np, os, sys
_s = []
def snapshot_func(array, rank):
    _s.append(np.array(array))
    return 0
def _modes(k):
    S = np.stack(_s, axis=2)
    out = []
    for c in range(3):
        u, s, _ = np.linalg.svd(S[:, c, :], full_matrices=False)
        out.append(u[:, :k])
    _s.clear()
    return np.concatenate(out, axis=0)
'''


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
    return base


def make_case(name, module, nsteps=6, wi=3, interval=0, dt=DT, extra=None):
    c = OUT/name
    shutil.rmtree(c, ignore_errors=True)
    shutil.copytree(base_case(), c, symlinks=True)
    cd = c/'system/controlDict'
    t = cd.read_text()
    t = re.sub(r'^endTime .*$', f'endTime {nsteps*dt:.10g};', t, flags=re.M)
    t = re.sub(r'^deltaT .*$', f'deltaT {dt:.10g};', t, flags=re.M)
    t = re.sub(r'^writeInterval .*$', f'writeInterval {wi};', t, flags=re.M)
    t = re.sub(r'^podSvdInterval .*$', f'podSvdInterval {interval};', t, flags=re.M)
    cd.write_text(t)
    if module is not None:
        (c/'python_module.py').write_text(module)
    return c


def decompose(c, n=2, cellmap=None):
    d = f'FoamFile {{ version 2.0; format ascii; class dictionary; object decomposeParDict; }}\nnumberOfSubdomains {n};\n'
    if cellmap is None:
        d += 'method scotch;\n'
    else:
        d += 'method manual;\nmanualCoeffs { dataFile "cellDecomposition"; }\ncoeffs { dataFile "cellDecomposition"; }\n'
        ncells = int(re.search(r'nCells:\s*(\d+)', (c/'constant/polyMesh/owner').read_text(errors='replace')[:2000]).group(1))
        body = ''.join(f'{cellmap(i)}\n' for i in range(ncells))
        (c/'constant/cellDecomposition').write_text(
            'FoamFile { version 2.0; format ascii; class labelList; location "constant"; object cellDecomposition; }\n'
            f'{ncells}\n(\n{body})\n')
    (c/'system/decomposeParDict').write_text(d)
    p = subprocess.run(['decomposePar', '-force', '-case', str(c)], cwd=c, stdout=open(c/'log.decomposePar', 'w'), stderr=subprocess.STDOUT)
    return p.returncode


def run(name, c, build='fork', nprocs=0, timeout=240, cwd=None, env=None, case_arg=None, record=True):
    e = dict(os.environ, MPLCONFIGDIR=str(OUT/'mpl'))
    e.update(env or {})
    cmd = [str(BIN[build]), '-case', case_arg or str(c)]
    if nprocs:
        cmd = ['mpirun', '--oversubscribe', '-np', str(nprocs)] + cmd + ['-parallel']
    cmd = ['timeout', '-k', '10', str(timeout)] + cmd
    logf = c/f'log.{build}'
    with open(logf, 'w') as log:
        p = subprocess.run(cmd, cwd=cwd or c, env=e, stdout=log, stderr=subprocess.STDOUT)
    text = logf.read_text(errors='replace')
    res = dict(scenario=name, build=build, exit=p.returncode, timed_out=p.returncode in (124, 137),
               end='\nEnd\n' in text, finalized='Python finalized successfully' in text,
               fatal='FOAM FATAL' in text, sigfpe=('sigFpe' in text or 'Floating point exception' in text),
               nan_residual=bool(re.search(r'residual = -?nan', text, flags=re.I)),
               time_lines=len(re.findall(r'^Time = ', text, flags=re.M)),
               courant_lines=len(re.findall(r'^Courant Number mean', text, flags=re.M)),
               tail=[l[:200] for l in text.splitlines()[-14:]])
    if record:
        results.setdefault(name, []).append(res)
    print(json.dumps({k: res[k] for k in ('scenario', 'build', 'exit', 'timed_out', 'end', 'finalized', 'fatal', 'sigfpe', 'nan_residual', 'courant_lines')}), flush=True)
    return res


def want(name):
    return FILTER in name


def s_restart_latest():
    # podSvdInterval > 0: SVD on a non-write step writes a time directory holding only POD fields
    if not want('restart'): return
    n = 'restart-latestTime-podSvdInterval'
    c = make_case(n, VALMOD, nsteps=21, wi=25, interval=7)
    run(n + '-first', c)
    results[n + '-first'][-1]['dirs'] = {d.name: sorted(f.name for f in d.iterdir())[:4] for d in c.iterdir() if re.fullmatch(r'[0-9.e-]+', d.name)}
    t = (c/'system/controlDict').read_text()
    t = re.sub(r'^startFrom .*$', 'startFrom latestTime;', t, flags=re.M)
    t = re.sub(r'^endTime .*$', f'endTime {30*DT:.10g};', t, flags=re.M)
    (c/'system/controlDict').write_text(t)
    run(n + '-second', c)
    # same restart with upstream's schedule: only write steps have POD files, and they have U too
    n2 = 'restart-latestTime-default'
    c2 = make_case(n2, VALMOD, nsteps=21, wi=7, interval=0)
    run(n2 + '-first', c2)
    t = (c2/'system/controlDict').read_text()
    t = re.sub(r'^startFrom .*$', 'startFrom latestTime;', t, flags=re.M)
    t = re.sub(r'^endTime .*$', f'endTime {30*DT:.10g};', t, flags=re.M)
    (c2/'system/controlDict').write_text(t)
    run(n2 + '-second', c2)


def s_rank_modes():
    if not want('rankmodes'): return
    mod = MINI + '''
def svd_func(rank):
    return _modes(3 if rank == 0 else 5)
'''
    n = 'rankmodes-rank-dependent-count'
    c = make_case(n, mod, nsteps=24, wi=6)
    decompose(c)
    run(n, c, nprocs=2, timeout=120)
    # the same module with equal counts is the control
    mod2 = MINI + '''
def svd_func(rank):
    return _modes(5)
'''
    n2 = 'rankmodes-equal-count-control'
    c = make_case(n2, mod2, nsteps=24, wi=6)
    decompose(c)
    run(n2, c, nprocs=2, timeout=120)
    # variance rule from the commented-out code in upstream's method_of_snapshots
    mod3 = MINI + '''
def svd_func(rank):
    S = np.stack(_s, axis=2)
    k = 1
    for c in range(3):
        f = S[:, c, :] - S[:, c, :].mean(axis=1, keepdims=True)
        s = np.linalg.svd(f, compute_uv=False)**2
        t = 0
        while t < len(s) and s[:t+1].sum() < 0.999*s.sum():
            t += 1
        k = max(k, t + 1)
    k = min(k, 5)
    print("VARIANCE rank", rank, "modes", k, flush=True)
    return _modes(k)
'''
    n3 = 'rankmodes-variance-rule'
    c = make_case(n3, mod3, nsteps=24, wi=6)
    decompose(c)
    r = run(n3, c, nprocs=2, timeout=120)
    log = (c/'log.fork').read_text(errors='replace')
    r['variance_lines'] = re.findall(r'VARIANCE rank \d modes \d', log)[:12]


def s_small_rank():
    if not want('smallrank'): return
    n = 'smallrank-3-cells-upstream-module'
    c = make_case(n, UPMOD, nsteps=24, wi=6)
    rc = decompose(c, 2, lambda i: 1 if i < 3 else 0)
    r = run(n, c, nprocs=2, timeout=120)
    r['decompose_exit'] = rc
    n = 'smallrank-0-cells-upstream-module'
    c = make_case(n, UPMOD, nsteps=12, wi=6)
    rc = decompose(c, 3, lambda i: 1 if i < 1000 else 0)
    r = run(n, c, nprocs=3, timeout=120)
    r['decompose_exit'] = rc


def s_analysis_master_only():
    if not want('masteronly'): return
    mod = MINI + '''
def svd_func(rank):
    return _modes(5)
if os.environ.get('OMPI_COMM_WORLD_RANK', '0') == '0':
    def analysis_func(state):
        print("ANALYSIS", state["step"], flush=True)
'''
    n = 'masteronly-analysis-defined-on-rank0'
    c = make_case(n, mod, nsteps=12, wi=6)
    decompose(c)
    run(n, c, nprocs=2, timeout=90)


def s_sysexit():
    if not want('sysexit'): return
    for where, code in [('snapshot', 0), ('svd', 0), ('import', 0)]:
        n = f'sysexit-{where}-code{code}'
        if where == 'snapshot':
            mod = MINI + f'''
_real = snapshot_func
def svd_func(rank):
    return _modes(5)
def snapshot_func(array, rank):
    sys.exit({code})
'''
        elif where == 'svd':
            mod = MINI + f'''
def svd_func(rank):
    sys.exit({code})
'''
        else:
            mod = 'import sys\nsys.exit(%d)\n' % code
        c = make_case(n, mod, nsteps=6, wi=3)
        run(n, c, timeout=120)
        run(n, c, build='upstream', timeout=120)


def s_cwd_module():
    if not want('cwd'): return
    n = 'cwd-module-beside-not-in-case'
    c = make_case(n, None, nsteps=6, wi=3)
    (c/'python_module.py').unlink(missing_ok=True)
    work = OUT/(n + '-cwd')
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    (work/'python_module.py').write_text(UPMOD)
    run(n, c, cwd=work, timeout=120)
    run(n, c, build='upstream', cwd=work, timeout=120)
    # relative -case
    n = 'case-relative-path'
    c = make_case(n, UPMOD, nsteps=6, wi=3)
    run(n, c, cwd=OUT, case_arg=n, timeout=120)


def s_traps():
    if not want('traps'): return
    # time step far too large: the run diverges
    for sigfpe in (None, 'false'):
        n = f"traps-diverging-FOAM_SIGFPE-{sigfpe or 'default'}"
        env = {}
        if sigfpe:
            env['FOAM_SIGFPE'] = sigfpe
        for build in ('fork', 'upstream'):
            if VER == '8' and sigfpe:
                continue
            c = make_case(n + '-' + build, UPMOD, nsteps=200, wi=100000, dt=1e-3)
            run(n, c, build=build, env=env, timeout=150)
    # is the trap on in each build when nothing is wrong?
    n = 'traps-env-unset'
    if VER == '8':
        for build in ('fork',):
            c = make_case(n + '-' + build, UPMOD, nsteps=200, wi=100000, dt=1e-3)
            e = dict(os.environ); e.pop('FOAM_SIGFPE', None)
            cmd = ['env', '-u', 'FOAM_SIGFPE', 'timeout', '-k', '10', '150', str(BIN[build]), '-case', str(c)]
            with open(c/'log.fork', 'w') as log:
                p = subprocess.run(cmd, cwd=c, env=dict(os.environ, MPLCONFIGDIR=str(OUT/'mpl')), stdout=log, stderr=subprocess.STDOUT)
            text = (c/'log.fork').read_text(errors='replace')
            results.setdefault(n, []).append(dict(build=build, exit=p.returncode, fatal='FOAM FATAL' in text, tail=[l[:200] for l in text.splitlines()[-8:]]))


def s_sticky():
    if not want('sticky'): return
    # Python leaves FP flags raised; the solver must go on and finish
    mod = MINI + '''
def svd_func(rank):
    return _modes(2)
_orig = snapshot_func
def snapshot_func(array, rank):
    with np.errstate(all='ignore'):
        a = np.array([1.0, 0.0, 1e308])
        _ = a/a[1]
        _ = a*1e308
        _ = np.sqrt(-a)
    return _orig(array, rank)
'''
    n = 'sticky-fp-flags-from-python'
    c = make_case(n, mod, nsteps=9, wi=3)
    run(n, c, timeout=120)


def s_offline_mode():
    if not want('offline'): return
    mod = UPMOD.replace('online_mode = True', 'online_mode = False')
    assert mod != UPMOD
    for wi, nsteps in ((1, 6), (2, 8), (3, 12), (6, 18), (25, 50)):
        n = f'offline-shipped-method-of-snapshots-wi{wi}'
        for build in ('fork', 'upstream'):
            c = make_case(n + '-' + build, mod, nsteps=nsteps, wi=wi)
            r = run(n, c, build=build, timeout=150)
            nanfiles = 0
            for d in c.iterdir():
                if re.fullmatch(r'[0-9.e-]+', d.name) and d.name != '0':
                    for f in d.glob('[uvw]pod_*'):
                        if re.search(r'\bnan\b', f.read_text(errors='replace'), flags=re.I):
                            nanfiles += 1
            r['pod_files_with_nan'] = nanfiles


def s_thread():
    if not want('thread'): return
    mod = MINI + '''
import threading, queue
_q = queue.Queue()
threading.Thread(target=_q.get).start()  # a worker thread that is not a daemon
def svd_func(rank):
    return _modes(2)
'''
    n = 'thread-non-daemon'
    c = make_case(n, mod, nsteps=6, wi=3)
    run(n, c, timeout=60)
    run(n, c, build='upstream', timeout=60)


def s_refcount():
    if not want('refcount'): return
    mod = '''
import numpy as np, weakref, gc, sys
_s, _w = [], {}
def _check(tag):
    gc.collect()
    alive = [k for k, r in _w.items() if r() is not None]
    print("REF", tag, "alive", alive, flush=True)
    _w.clear()
def snapshot_func(array, rank):
    _check("snapshot")
    _s.append(array.copy())
    _w["snapshot"] = weakref.ref(array)
    print("REFCOUNT snapshot", sys.getrefcount(array), array.flags.owndata, flush=True)
    return np.zeros(3)
def svd_func(rank):
    S = np.stack(_s, axis=2)
    out = [np.linalg.svd(S[:, c, :], full_matrices=False)[0][:, :2] for c in range(3)]
    _s.clear()
    r = np.concatenate(out, axis=0)
    _w["modes"] = weakref.ref(r)
    return r
def analysis_func(state):
    _w["u"] = weakref.ref(state["u_cells"])
    _w["p"] = weakref.ref(state["p_cells"])
def mesh_func(centres, volumes, sol, rank, pts, off, cells, *a):
    _w["centres"] = weakref.ref(centres)
    _w["pts"] = weakref.ref(pts)
'''
    n = 'refcount-weakrefs'
    c = make_case(n, mod, nsteps=9, wi=3)
    r = run(n, c, timeout=120)
    log = (c/'log.fork').read_text(errors='replace')
    r['ref_lines'] = sorted(set(re.findall(r'^REF .*$', log, flags=re.M)))
    r['refcount_lines'] = sorted(set(re.findall(r'^REFCOUNT .*$', log, flags=re.M)))


def s_returns():
    if not want('returns'): return
    forms = {
        'fortran': 'np.asfortranarray(m)',
        'reversed-columns': 'm[:, ::-1]',
        'strided-rows': 'np.repeat(m, 2, axis=0)[::2]',
        'matrix': 'np.matrix(m)',
        'float32': 'm.astype(np.float32)',
        'bigendian': 'm.astype(">f8")',
        'list': 'm.tolist()',
        'none': 'None',
        'rows-wrong': 'm[:-3]',
        'six-modes': 'np.tile(m, (1, 3))[:, :6]',
        'nan': 'np.full_like(m, np.nan)',
        'one-d': 'm[:, 0]',
        'zero-modes': 'm[:, :0]',
    }
    for name, expr in forms.items():
        mod = MINI + f'''
def svd_func(rank):
    m = _modes(2)
    np.save("expected.npy", m)
    return {expr}
'''
        n = 'returns-' + name
        c = make_case(n, mod, nsteps=3, wi=3)
        r = run(n, c, timeout=90)
        if name in ('fortran', 'reversed-columns', 'strided-rows', 'matrix') and (c/'expected.npy').exists():
            import numpy as np
            m = np.load(c/'expected.npy')
            if name == 'reversed-columns':
                m = m[:, ::-1]
            d = [x for x in c.iterdir() if re.fullmatch(r'[0-9.e-]+', x.name) and x.name != '0'][0]
            def field(f):
                t = (d/f).read_text()
                b = t[t.index('internalField'):]
                n_ = int(re.search(r'List<scalar>\s*(\d+)', b).group(1))
                body = b[b.index('(')+1:]
                return np.array(body.split()[:n_], dtype=float)
            nc = m.shape[0]//3
            ok = True
            for mode in range(2):
                for cmpt, pre in enumerate(('upod_', 'vpod_', 'wpod_')):
                    ok &= bool(np.allclose(field(f'{pre}{mode}'), m[cmpt*nc:(cmpt+1)*nc, mode], rtol=1e-9, atol=1e-9))
            r['values_match'] = ok


def s_hooks():
    if not want('hooks'): return
    n = 'hooks-analysis-raises-systemexit'
    mod = MINI + '''
def svd_func(rank):
    return _modes(2)
def analysis_func(state):
    sys.exit(3)
'''
    run(n, make_case(n, mod, nsteps=6, wi=3), timeout=120)
    n = 'hooks-mesh-func-wrong-signature'
    mod = MINI + '''
def svd_func(rank):
    return _modes(2)
def mesh_func(only_one):
    pass
def analysis_func(state):
    pass
'''
    run(n, make_case(n, mod, nsteps=6, wi=3), timeout=120)
    n = 'hooks-analysis-not-callable'
    mod = MINI + '''
def svd_func(rank):
    return _modes(2)
analysis_func = 3
'''
    run(n, make_case(n, mod, nsteps=6, wi=3), timeout=120)
    n = 'hooks-snapshot-missing-with-analysis'
    mod = '''
import numpy as np
def svd_func(rank):
    return None
def analysis_func(state):
    pass
def mesh_func(*a):
    print("MESH_FUNC RAN", flush=True)
'''
    run(n, make_case(n, mod, nsteps=6, wi=3), timeout=120)
    n = 'hooks-svd-not-callable'
    mod = '''
import numpy as np
def snapshot_func(a, r):
    pass
svd_func = 3
'''
    run(n, make_case(n, mod, nsteps=6, wi=3), timeout=120)
    n = 'hooks-negative-interval'
    run(n, make_case(n, VALMOD, nsteps=6, wi=3, interval=-1), timeout=120)


def s_parallel_validation():
    if not want('parvalidation'): return
    n = 'parvalidation-module-refuses-rank1'
    c = make_case(n, VALMOD, nsteps=6, wi=3)
    decompose(c)
    run(n, c, nprocs=2, timeout=90)


def s_upstream_parallel():
    if not want('upstreampar'): return
    n = 'upstreampar-baseline'
    c = make_case(n, UPMOD, nsteps=12, wi=6)
    decompose(c)
    r = run(n, c, build='upstream', nprocs=2, timeout=120)
    r['proc_dirs'] = sorted(d.name for d in (c/'processor0').iterdir())[:10]
    r['case_dirs'] = sorted(d.name for d in c.iterdir())[:20]


for f in (s_returns, s_refcount, s_sticky, s_hooks, s_sysexit, s_cwd_module, s_thread, s_restart_latest, s_offline_mode,
          s_parallel_validation, s_upstream_parallel, s_rank_modes, s_small_rank, s_analysis_master_only, s_traps):
    try:
        f()
    except Exception as e:
        results.setdefault('driver-errors', []).append(f'{f.__name__}: {e!r}')
        print('DRIVER ERROR', f.__name__, repr(e), flush=True)
    (OUT/f"scenarios{'-' + FILTER if FILTER else ''}.json").write_text(json.dumps(results, indent=1))
print('done')
