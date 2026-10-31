"""Part A records, per version: exit, End, result, frame, telemetry, request body == builder(frame), scores."""
import base64, hashlib, json, re, sys
from pathlib import Path
run, repo = Path(sys.argv[1]), Path(sys.argv[2])
W = repo.parents[2]
sys.path.insert(0, str(repo/'Solver_Examples/PODFoam/llm_demo'))
import readable_request, frame_scoring
from llm_client import encode_json
BASE = {'v2012': 'v2012-24948648', 'v2106': 'v2106-24948777', 'v2212': 'v2212-24948778', '8': '8-24948779'}
table = {}
for ver in ('v2012', 'v2106', 'v2212', '8'):
    out = run/ver; case = out/'case2d'
    row = {'version': ver}
    table[ver] = row
    try:
        # the modules the solver ran are the clone's: checked byte for byte
        for f in ('python_module.py', 'bounded_ipc.py', 'llm_client.py', 'readable_request.py', 'readable_image.py', 'pod_image.py'):
            assert (case/f).read_bytes() == (repo/'Solver_Examples/PODFoam/llm_demo'/f).read_bytes(), f
        row['validation_last_line'] = (out/'validation.log').read_text().strip().splitlines()[-1][:12]
        row['validation_status_pass'] = (out/'validation.log').read_text().strip().splitlines()[-1].startswith('PASS')
        row['exit_status'] = int((case/'exit-status').read_text())
        log = (case/'log.PODFoam').read_text()
        row['End'] = bool(re.search(r'^End$', log, re.M))
        row['python_finalized'] = 'Python finalized successfully' in log
        row['foam_fatal_or_nan'] = bool(re.search(r'(?i)\b(nan|inf)\b|FOAM FATAL', log))
        row['time_lines'] = len(re.findall(r'^Time = ', log, re.M))
        result = json.loads((case/'llm_result.json').read_text())
        request = json.loads((case/'llm_request.json').read_text())
        row['status'] = result.get('status')
        row['error'] = result.get('error')
        row['request_step'] = result.get('request_step'); row['arrived_at_step'] = result.get('arrived_at_step')
        row['worker_reaped'] = result.get('worker_reaped')
        row['solver_stall_s'] = result.get('solver_stall_s'); row['inference_wall_s'] = result.get('inference_wall_s')
        row['end_wait_s'] = result.get('end_wait_s')
        row['http_status'] = result.get('http_status')
        row['structured_output'] = result.get('structured_output')
        row['usage'] = (json.loads((case/'llm_response.json').read_text()).get('usage') if (case/'llm_response.json').exists() else None)
        tel = (case/'telemetry.jsonl')
        row['telemetry_lines'] = len(tel.read_text().splitlines()) if tel.exists() else None
        row['telemetry_tmp_left'] = (case/'telemetry.jsonl.tmp').exists()
        row['llm_errors_file'] = (case/'llm_errors.jsonl').exists()
        states = [json.loads(l) for l in tel.read_text().splitlines()]
        walls = {int(m[1]): float(m[2]) for m in re.finditer(r'POD analysis callback returned: step=(\d+) wall_seconds=(\S+)', log)}
        row['callback_wall_s_step100'] = walls.get(100); row['callback_wall_s_last'] = walls.get(110)
        row['max_other_callback_wall_s'] = max(v for k, v in walls.items() if k not in (100, result.get('arrived_at_step'), 110))
        record = result.get('image') or request.get('image')
        directory = Path(record['directory'])
        row['frame_dir'] = str(directory.relative_to(run))
        row['frame_files'] = sorted(p.name for p in directory.iterdir())
        frame, meta, _ = readable_request.load_frame(directory)   # checks every hash
        row['frame_hashes_ok'] = True
        row['frame_step_time'] = [meta['step'], meta['time_s']]
        row['frame_time_equals_telemetry'] = meta['time_s'] == states[meta['step']-1]['time_s']
        row['frame_cells'] = meta.get('cells')
        row['frame_fields_sha256'] = meta['fields_sha256']
        row['png_sha256'] = frame['image_sha256']
        body_bytes = (case/'llm_request_body.json').read_bytes()
        body = json.loads(body_bytes)
        row['body_equals_builder'] = body_bytes == encode_json(readable_request.describe_v2_payload(frame, model=body['model']))
        row['body_system_prompt_ok'] = body['messages'][0]['content'] == readable_request.DESCRIBE_V2_SYSTEM_PROMPT
        images = [p for p in body['messages'][1]['content'] if p['type'] == 'image_url']
        row['body_images_equal_frame'] = [hashlib.sha256(base64.b64decode(p['image_url']['url'].split(',', 1)[1])).hexdigest() for p in images] == [frame['image_sha256'][k] for k in ('U', 'p')]
        row['request_sha256'] = hashlib.sha256(body_bytes).hexdigest()
        row['model'] = body['model']; row['max_tokens'] = body.get('max_tokens'); row['seed'] = body.get('seed')
        _, truth = frame_scoring.load_v2(directory)
        row['truth'] = {k: truth[k] for k in ('max_speed_m_per_s', 'min_pressure_m2_per_s2', 'fastest_flow', 'lowest_pressure', 'cells_in_window')}
        row['score'] = frame_scoring.score_describe(result['structured_output'], truth) if result.get('structured_output') else None
        # the same case with no model, earlier today (commit 5cc2755): same frame arrays?
        base = W/'pr/version-runs'/BASE[ver]/'serial2d/llm_observation/step-000100/readable-metadata.json'
        if base.exists():
            row['same_fields_as_no_model_run'] = json.loads(base.read_text())['fields_sha256'] == meta['fields_sha256']
    except Exception as error:
        row['check_error'] = f'{type(error).__name__}: {error}'
(run/'part-a.json').write_text(json.dumps(table, indent=2)+'\n')
def f(v, n=2): return f'{v:.{n}f}' if isinstance(v, float) else str(v)
for ver, r in table.items():
    print(f"--- {ver}: exit {r.get('exit_status')} End {r.get('End')} status {r.get('status')} http {r.get('http_status')} arrived {r.get('arrived_at_step')} infer {f(r.get('inference_wall_s'))}s stall {f(r.get('solver_stall_s'),3)}s telemetry {r.get('telemetry_lines')} body=builder {r.get('body_equals_builder')} images=frame {r.get('body_images_equal_frame')} same-as-no-model {r.get('same_fields_as_no_model_run')}")
    if r.get('check_error'): print('  CHECK ERROR', r['check_error'])
    if r.get('score'):
        for n, s in r['score'].items():
            print(f"  {n}: answer {s['answer_percent']} true {[round(x,1) for x in s['true_percent']]} dist {s['distance_percent']:.1f}% within10 {s['within_10_percent']}")
    print('  ', json.dumps(r.get('structured_output'))[:400])
