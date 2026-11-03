"""Records of the 2-rank request job, per version and case (serial, par2): run outcome, request record, which
process sent the request, server request count, frame arrays serial against 2 ranks, and the serial frame against
the serial frame of job 24950818."""
import base64, hashlib, json, re, sys
from pathlib import Path
import numpy as np
run, repo = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo/'Solver_Examples/PODFoam/llm_demo'))
import readable_request, frame_scoring
from llm_client import encode_json
EARLIER = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/refix/gpu-a/run-24950818')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def metric(text, name):
    m = re.search(r'^' + re.escape(name) + r'(?:\{[^}]*\})? (\S+)', text, re.M)
    return float(m[1]) if m else None


def by_position(frame):
    order = np.lexsort(np.round(frame['centres'], 9).T[::-1])
    n = frame['centres'].shape[0]
    return {k: (frame[k][order] if frame[k].ndim and frame[k].shape[0] == n else frame[k]) for k in frame}


def case_record(case, ver):
    row = {}
    row['exit_status'] = int((case/'exit-status').read_text())
    log = (case/'log.PODFoam').read_text(errors='replace')
    row['End'] = bool(re.search(r'^End$', log, re.M))
    row['python_finalized'] = 'Python finalized successfully' in log
    row['foam_fatal_or_nan'] = bool(re.search(r'(?i)\b(nan|inf)\b|FOAM FATAL', log))
    row['time_lines'] = len(re.findall(r'^Time = ', log, re.M))
    m = re.search(r'^nProcs : (\d+)', log, re.M); row['nProcs_in_log'] = int(m[1]) if m else None
    m = re.search(r'^PID\s*: (\d+)', log, re.M); row['master_pid_in_log'] = int(m[1]) if m else None
    m = re.search(r'POD mesh geometry passed to Python: cells=(\d+).*ranks=(\d+)', log)
    row['mesh_line'] = {'cells': int(m[1]), 'ranks': int(m[2])} if m else None
    m = re.search(r'PYTHON LLM mesh geometry received: cells=(\d+) cell_polygons=(\d+)', log)
    row['python_mesh_line'] = {'cells': int(m[1]), 'cell_polygons': int(m[2])} if m else None
    row['python_llm_lines_rank0'] = len(re.findall(r'^PYTHON LLM', log, re.M))
    row['callback_lines'] = len(re.findall(r'POD analysis callback returned', log))
    walls = {int(m[1]): float(m[2]) for m in re.finditer(r'POD analysis callback returned: step=(\d+) wall_seconds=(\S+)', log)}
    row['callback_wall_s_step100'] = walls.get(100); row['callback_wall_s_step110'] = walls.get(110)
    row['max_other_callback_wall_s'] = max((v for k, v in walls.items() if k not in (100, 110)), default=None)
    ranks = sorted(case.glob('rank-*.txt'))
    if ranks:
        row['ranks'] = {}
        for f in ranks:
            text = f.read_text()
            d = dict(kv.split('=', 1) for kv in text.split())
            row['ranks'][f.stem.split('-')[1]] = d
        other = [p for p in case.glob('log.rank*')]
        row['other_rank_logs'] = {p.name: {'lines': len(p.read_text(errors='replace').splitlines()),
                                           'python_llm_lines': len(re.findall(r'^PYTHON LLM', p.read_text(errors='replace'), re.M)),
                                           'llm_mentions': len(re.findall(r'(?i)llm|request|http', p.read_text(errors='replace'))),
                                           'head': p.read_text(errors='replace').splitlines()[:5]} for p in other}
        row['mpirun_log_lines'] = (case/'log.mpirun').read_text(errors='replace').splitlines()[:20] if (case/'log.mpirun').exists() else None
        dec = (case/'log.decomposePar').read_text(errors='replace')
        row['decompose_cells_per_processor'] = [int(x) for x in re.findall(r'Number of cells = (\d+)', dec)]
        row['processor_dirs'] = sorted(p.name for p in case.glob('processor*'))
    before, after = (case/'metrics-before.txt').read_text(), (case/'metrics-after.txt').read_text()
    row['server_metrics'] = {}
    for name in ('llamacpp:prompt_tokens_total', 'llamacpp:tokens_predicted_total', 'llamacpp:n_decode_total', 'llamacpp:requests_processing', 'llamacpp:requests_deferred'):
        b, a = metric(before, name), metric(after, name)
        row['server_metrics'][name] = {'before': b, 'after': a, 'delta': (a - b) if a is not None and b is not None else None}
    row['started_at'] = (case/'started-at.txt').read_text().strip(); row['ended_at'] = (case/'ended-at.txt').read_text().strip()
    result = json.loads((case/'llm_result.json').read_text())
    request = json.loads((case/'llm_request.json').read_text())
    for k in ('status', 'error', 'request_step', 'arrived_at_step', 'worker_reaped', 'solver_stall_s', 'inference_wall_s', 'end_wait_s', 'http_status', 'structured_output', 'parent_pid', 'writer_pid', 'run_id'):
        row[k] = result.get(k)
    row['request_parent_pid'] = request.get('parent_pid')
    row['parent_pid_is_master_pid_in_log'] = row.get('parent_pid') == row['master_pid_in_log']
    if ranks and row.get('parent_pid') is not None:
        # rank-N.txt: 'pid' is the wrapper's pid, 'solver_pid' (second job onwards) the PODFoam process it started
        key = 'solver_pid' if 'solver_pid' in row['ranks'].get('0', {}) else 'pid'
        row['rank_pid_key'] = key
        row['parent_pid_is_rank0'] = str(row['parent_pid']) == row['ranks'].get('0', {}).get(key)
        row['parent_pid_is_other_rank'] = any(str(row['parent_pid']) == d.get(key) for r, d in row['ranks'].items() if r != '0')
    row['usage'] = json.loads((case/'llm_response.json').read_text()).get('usage') if (case/'llm_response.json').exists() else None
    tel = case/'telemetry.jsonl'
    states = [json.loads(l) for l in tel.read_text().splitlines()] if tel.exists() else []
    row['telemetry_lines'] = len(states); row['telemetry_tmp_left'] = (case/'telemetry.jsonl.tmp').exists()
    row['telemetry_cells'] = states[-1]['cells'] if states else None
    row['llm_errors_file'] = (case/'llm_errors.jsonl').exists()
    record = result.get('image') or request.get('image')
    directory = Path(record['directory'])
    row['frame_dir'] = str(directory.relative_to(run)); row['frame_files'] = sorted(p.name for p in directory.iterdir())
    frame, meta, _ = readable_request.load_frame(directory)
    row['frame_hashes_ok'] = True
    row['frame_step_time'] = [meta['step'], meta['time_s']]
    row['frame_cells'] = meta.get('cells'); row['frame_fields_sha256'] = meta['fields_sha256']
    row['png_sha256'] = frame['image_sha256']
    with np.load(directory/'fields.npz') as z:
        arrays = {k: z[k] for k in z.files}
    row['fields_npz_keys'] = {k: list(arrays[k].shape) for k in arrays}
    row['fields_finite'] = all(np.isfinite(arrays[k]).all() for k in arrays if arrays[k].dtype.kind == 'f')
    body_bytes = (case/'llm_request_body.json').read_bytes(); body = json.loads(body_bytes)
    row['body_equals_builder'] = body_bytes == encode_json(readable_request.describe_v2_payload(frame, model=body['model']))
    images = [p for p in body['messages'][1]['content'] if p['type'] == 'image_url']
    row['body_images_equal_frame'] = [hashlib.sha256(base64.b64decode(p['image_url']['url'].split(',', 1)[1])).hexdigest() for p in images] == [frame['image_sha256'][k] for k in ('U', 'p')]
    row['request_sha256'] = hashlib.sha256(body_bytes).hexdigest()
    row['model'] = body['model']; row['max_tokens'] = body.get('max_tokens'); row['seed'] = body.get('seed')
    _, truth = frame_scoring.load_v2(directory)
    row['truth'] = {k: truth[k] for k in ('max_speed_m_per_s', 'min_pressure_m2_per_s2', 'fastest_flow', 'lowest_pressure', 'cells_in_window')}
    row['score'] = frame_scoring.score_describe(result['structured_output'], truth) if result.get('structured_output') else None
    return row, arrays


def difference(a, b):
    pa, pb = by_position(a), by_position(b)
    d_u = np.linalg.norm(pa['U'] - pb['U'], axis=1)
    d_p = np.abs((pa['p'] - pa['p'].mean()) - (pb['p'] - pb['p'].mean()))
    return {'cells': [int(a['p'].size), int(b['p'].size)],
            'centres_identical_after_ordering': bool(np.array_equal(pa['centres'], pb['centres'])),
            'centres_max_m': float(np.abs(pa['centres'] - pb['centres']).max()),
            'same_order_as_stored': bool(np.array_equal(a['centres'], b['centres'])),
            'U_identical': bool(np.array_equal(pa['U'], pb['U'])), 'p_identical': bool(np.array_equal(pa['p'], pb['p'])),
            'U_max': float(d_u.max()), 'U_rms': float(np.sqrt((d_u**2).mean())), 'U_peak': float(np.linalg.norm(pa['U'], axis=1).max()),
            'p_max': float(d_p.max()), 'p_rms': float(np.sqrt((d_p**2).mean())), 'p_range': float(pa['p'].max() - pa['p'].min()),
            'other_keys_identical': {k: bool(np.array_equal(pa[k], pb[k])) for k in a if k not in ('centres', 'U', 'p') and k in b}}


table = {'node': (run/'node.txt').read_text().strip(), 'gpu': (run/'gpu.txt').read_text().strip(), 'HEAD': (run/'HEAD').read_text().strip(),
         'git_status': (run/'git-status.txt').read_text().strip()}
server_log = next(iter((run/'server').glob('server-*.log')), None)
if server_log:
    text = server_log.read_text(errors='replace')
    table['server_log'] = {'launch_slot_lines': len(re.findall(r'launch_slot_', text)), 'post_chat_completions': len(re.findall(r'POST /v1/chat/completions', text)),
                           'n_slots': (re.search(r'n_slots = (\d+)', text) or [None, None])[1], 'file': str(server_log.relative_to(run))}
for ver in ('v2212', '8'):
    out = run/ver
    if not out.exists():
        continue
    t = {'version': ver}; table[ver] = t
    try:
        t['validation_last_line'] = (out/'validation.log').read_text().strip().splitlines()[-1][:12]
        t['validation_pass'] = t['validation_last_line'].startswith('PASS')
        t['binary_sha256'] = (out/'binary-sha256.txt').read_text().split()[0]
        t['mpirun_version'] = (out/'mpirun-version.txt').read_text().splitlines()[0] if (out/'mpirun-version.txt').exists() else None
        for f in ('python_module.py', 'bounded_ipc.py', 'llm_client.py', 'readable_request.py', 'readable_image.py', 'pod_image.py'):
            for case in ('serial', 'par2'):
                assert (out/case/f).read_bytes() == (repo/'Solver_Examples/PODFoam/llm_demo'/f).read_bytes(), f'{case}/{f}'
        t['modules_equal_worktree'] = True
    except Exception as error:
        t['check_error_header'] = f'{type(error).__name__}: {error}'
    frames = {}
    for case in ('serial', 'par2'):
        try:
            t[case], frames[case] = case_record(out/case, ver)
        except Exception as error:
            t[case] = {'check_error': f'{type(error).__name__}: {error}'}
    try:
        if 'serial' in frames and 'par2' in frames:
            t['serial_vs_par2'] = difference(frames['serial'], frames['par2'])
            t['serial_vs_par2']['request_sha256_equal'] = t['serial']['request_sha256'] == t['par2']['request_sha256']
            t['serial_vs_par2']['png_sha256_equal'] = t['serial']['png_sha256'] == t['par2']['png_sha256']
            t['serial_vs_par2']['truth_equal'] = t['serial']['truth'] == t['par2']['truth']
        earlier = EARLIER/ver/'case2d/llm_observation/step-000100'
        if earlier.exists() and 'serial' in frames:
            mine = run/t['serial']['frame_dir']
            t['serial_vs_24950818'] = {f: sha(mine/f) == sha(earlier/f) for f in ('fields.npz', 'U.png', 'p.png')}
            t['serial_vs_24950818']['request_sha256_equal'] = t['serial']['request_sha256'] == json.loads((EARLIER/'part-a.json').read_text())[ver]['request_sha256']
            with np.load(earlier/'fields.npz') as z:
                e = {k: z[k] for k in z.files}
            t['serial_vs_24950818']['arrays_identical'] = all(np.array_equal(frames['serial'][k], e[k]) for k in e) and set(e) == set(frames['serial'])
            if 'par2' in frames:
                t['par2_vs_24950818_serial'] = difference(frames['par2'], e)
    except Exception as error:
        t['check_error_compare'] = f'{type(error).__name__}: {error}'
(run/'ranks.json').write_text(json.dumps(table, indent=2, default=str)+'\n')
def f(v, n=2): return f'{v:.{n}f}' if isinstance(v, float) else str(v)
print('node', table['node'], table['gpu'], 'HEAD', table['HEAD'][:7], 'server', json.dumps(table.get('server_log')))
for ver in ('v2212', '8'):
    t = table.get(ver)
    if not t: continue
    print(f"=== {ver}: validation {t.get('validation_last_line')} modules_equal {t.get('modules_equal_worktree')} {t.get('check_error_header', '')}")
    for case in ('serial', 'par2'):
        r = t[case]
        if 'check_error' in r: print(f'  {case}: CHECK ERROR', r['check_error']); continue
        print(f"  {case}: exit {r['exit_status']} End {r['End']} nProcs {r['nProcs_in_log']} mesh {r['mesh_line']} time_lines {r['time_lines']} telemetry {r['telemetry_lines']} status {r['status']} http {r['http_status']} arrived {r['arrived_at_step']} infer {f(r['inference_wall_s'])}s stall {f(r['solver_stall_s'],3)}s cb100 {f(r['callback_wall_s_step100'],3)} cb110 {f(r['callback_wall_s_step110'],3)} body=builder {r['body_equals_builder']} images=frame {r['body_images_equal_frame']}")
        print(f"    parent_pid {r['parent_pid']} master_pid_in_log {r['master_pid_in_log']} ranks {r.get('ranks')} parent_is_rank0 {r.get('parent_pid_is_rank0')} other_rank_logs {json.dumps(r.get('other_rank_logs'))[:300]}")
        print(f"    server deltas {json.dumps({k: v['delta'] for k, v in r['server_metrics'].items()})}")
        if r.get('score'):
            for n, s in r['score'].items():
                print(f"    {n}: answer {s['answer_percent']} true {[round(x,1) for x in s['true_percent']]} dist {s['distance_percent']:.1f}% within10 {s['within_10_percent']}")
        print('    ', json.dumps(r.get('structured_output'))[:300])
    for k in ('serial_vs_par2', 'serial_vs_24950818', 'par2_vs_24950818_serial'):
        if k in t: print(f'  {k}:', json.dumps(t[k]))
    if 'check_error_compare' in t: print('  COMPARE ERROR', t['check_error_compare'])
