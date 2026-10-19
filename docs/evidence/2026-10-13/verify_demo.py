"""Check one demo run: telemetry against the solver log, image provenance, unchanged fields, callback timing."""
from pathlib import Path
import base64
import hashlib
import json
import re
import sys
import numpy as np

root = Path(sys.argv[1])
reference = json.loads((root/'verification.json').read_text())
assert reference['status'] == 'PASS'
reports = {}
CALLBACK_FILES = ('python_module.py', 'llm_client.py', 'pod_image.py', 'bounded_ipc.py', 'pod_svd.py')
CASES = ('fixed-pod-no-llm', 'fixed-pod', 'fixed-pod-text-only', 'fixed-pod-server-error', 'fixed-pod-timeout')
EXPECTED_STATUS = {'fixed-pod-no-llm': 'disabled', 'fixed-pod': 'ok', 'fixed-pod-text-only': 'ok',
                   'fixed-pod-server-error': 'error', 'fixed-pod-timeout': 'timeout'}
IMAGE_CASES = {'fixed-pod-no-llm', 'fixed-pod', 'fixed-pod-server-error', 'fixed-pod-timeout'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def internal_values(path):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(), flags=re.S)
    match = re.search(r'internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;', text, re.S)
    assert match, path
    values = np.fromstring(match[3].replace('(', ' ').replace(')', ' '), sep=' ')
    assert values.size == int(match[2]) * (3 if match[1] == 'vector' else 1)
    assert np.isfinite(values).all()
    return values


def check_image_provenance(case, request, result):
    """The PNG the model received was made from the fields the solver wrote for that step."""
    observation = case/'llm_observation'
    meta = json.loads((observation/'image-metadata.json').read_text())
    png = observation/'state.png'
    fields = observation/'fields.npz'
    assert png.exists() and fields.exists()
    assert meta['sha256'] == sha256(png) == result['image']['sha256']
    assert meta['fields_sha256'] == sha256(fields) == result['image']['fields_sha256']
    assert meta['step'] == result['step'] and meta['time_s'] == result['time_s']
    assert png.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
    assert b'FieldsSHA256' in png.read_bytes() and meta['fields_sha256'].encode() in png.read_bytes()
    # arrays behind the picture equal the stored fields
    saved = np.load(fields)
    step_dir = case/f"{result['time_s']:g}"
    stored_u = internal_values(step_dir/'U').reshape(-1, 3)
    stored_p = internal_values(step_dir/'p')
    np.testing.assert_allclose(saved['U'], stored_u, rtol=1e-11, atol=0)
    np.testing.assert_allclose(saved['p'], stored_p, rtol=1e-11, atol=0)
    assert float(saved['time_s']) == result['time_s'] and int(saved['step']) == result['step']
    assert saved['centres'].shape == (20540, 3) and np.isfinite(saved['centres']).all()
    # the HTTP body carried that PNG
    body = json.loads((case/'llm_request_body.json').read_bytes())
    user = body['messages'][1]['content']
    assert isinstance(user, list) and [p['type'] for p in user] == ['text', 'image_url']
    url = user[1]['image_url']['url']
    assert url.startswith('data:image/png;base64,')
    assert hashlib.sha256(base64.b64decode(url.split(',', 1)[1])).hexdigest() == meta['sha256']
    assert json.loads(user[0]['text']) == request['input']
    assert request['input']['image']['step'] == result['step']
    assert request['request']['messages'][1]['content'][1]['image_url']['png_sha256'] == meta['sha256']
    assert body['response_format']['type'] == 'json_schema'
    assert set(body['response_format']['json_schema']['schema']['required']) == {
        'observations', 'possible_interpretation', 'checks'}
    return {'png_sha256': meta['sha256'], 'png_bytes': meta['bytes'], 'fields_sha256': meta['fields_sha256'],
            'width': meta['width'], 'height': meta['height'], 'projection_axes': meta['projection_axes'],
            'aspect': meta.get('aspect'), 'ranges': meta['ranges'],
            'render_wall_s': result['image']['render_wall_s']}


residual_pattern = r'Solving for (Ux|Uy|p), Initial residual = ([^,]+), Final residual = ([^,]+), No Iterations (\d+)'
for name in CASES:
    case = root/name
    for filename in CALLBACK_FILES:
        assert (case/filename).read_bytes() == (root/'executed-callback-source'/filename).read_bytes()
    log = (case/'log.PODFoam').read_text()
    states = [json.loads(line) for line in (case/'telemetry.jsonl').read_text().splitlines()]
    assert len(states) == 10
    assert all('p_cells' not in state for state in states)
    assert 'POD mesh geometry passed to Python: cells=20540' in log
    assert 'PYTHON LLM mesh geometry received: cells=20540' in log
    blocks = re.split(r'^Time = ([^\s]+) deltaT = [^\n]+\n', log, flags=re.M)
    assert len(blocks) == 21 and re.search(r'^End$', log, re.M)
    assert not re.search(r'(?i)\b(nan|inf)\b|FOAM FATAL', log)
    assert 'Python finalized successfully' in log
    assert 'mesh_func failed' not in log
    for i, state in enumerate(states):
        assert state['step'] == i+1
        np.testing.assert_allclose(state['time_s'], float(blocks[2*i+1]), rtol=1e-12, atol=0)
        assert state['delta_t_s'] == 1e-7
        solutions = re.findall(residual_pattern, blocks[2*i+2])
        assert set(state['residuals']) == {'Ux', 'Uy', 'p'}
        for field in ('Ux', 'Uy', 'p'):
            records = [item for item in solutions if item[0] == field]
            assert records
            actual = state['residuals'][field]
            expected = [float(records[0][1]), float(records[-1][1]), float(records[-1][2])]
            values = [actual[k] for k in ('initial_first', 'initial_last', 'final_last')]
            np.testing.assert_allclose(values, expected, rtol=2e-11, atol=1e-20)
            assert actual['linear_solves'] == len(records)
            assert actual['iterations_total'] == sum(int(item[3]) for item in records)
        continuity = re.findall(r'time step continuity errors : sum local = ([^,]+), global = ([^,]+), cumulative = ([^\s]+)', blocks[2*i+2])
        assert continuity
        np.testing.assert_allclose([state['continuity'][k] for k in ('local', 'global', 'cumulative')],
                                   np.array(continuity[-1], dtype=float), rtol=2e-10, atol=1e-20)
        assert state['courant']['phase'] == 'post_step_phi'
        assert np.isfinite([state['courant']['mean'], state['courant']['max']]).all()
        if i < 9:
            # The next timestep's pre-step phi is this completed step's phi.
            co = re.findall(r'Courant Number mean: (\S+) max: (\S+)', blocks[2*i+2])[-1]
            np.testing.assert_allclose([state['courant']['mean'], state['courant']['max']],
                                       np.array(co, dtype=float), rtol=2e-10, atol=1e-20)
    # written fields identical to the no-request case
    compared = 0
    for folder in (root/'fixed-pod-no-llm').iterdir():
        if not folder.is_dir() or not re.fullmatch(r'[0-9.eE+-]+', folder.name) or float(folder.name) == 0:
            continue
        for field in folder.iterdir():
            if field.is_file():
                assert field.read_bytes() == (case/folder.name/field.name).read_bytes(), (name, field)
                compared += 1
    result = json.loads((case/'llm_result.json').read_text())
    request = json.loads((case/'llm_request.json').read_text())
    assert result['step'] == 5 and result['time_s'] == 5e-7
    assert log.index('PYTHON LLM step=5') < log.index('Time = 6e-07')
    assert result['status'] == EXPECTED_STATUS[name], (name, result)
    assert len(re.findall(r'PYTHON LLM step=', log)) == 1
    markers = [json.loads(line.split('PYTHON LLM_MARKER ', 1)[1])
               for line in log.splitlines() if line.startswith('PYTHON LLM_MARKER ')]
    assert [m['event'] for m in markers] == ['callback_start', 'request_before', 'response_after'], (name, markers)
    sequence = [log.index('"event":"request_before"'), log.index('"event":"response_after"'),
                log.index('POD analysis callback returned: step=5'),
                log.index('Time = 6e-07'), log.rindex('\nEnd')]
    assert sequence == sorted(sequence)
    callback_actual = float(re.search(r'POD analysis callback returned: step=5 wall_seconds=(\S+)', log)[1])
    assert result['worker_reaped']
    assert callback_actual <= result['deadline_s'] + result['cleanup_budget_s'] + result['kill_join_allowance_s'] + result['scheduling_tolerance_s'], result
    image_report = None
    if name in IMAGE_CASES:
        assert result['image_requested'] is True
        assert result['image_input'] is True and result['text_input_only'] is False, (name, result)
        if 'image' not in result:
            # Worker killed at the deadline before reporting; its request record carries the image.
            assert name == 'fixed-pod-timeout' and request['image_input'] is True
            result = {**request, **result}
        image_report = check_image_provenance(case, request, result)
    else:
        assert result['image_input'] is False and result['text_input_only'] is True
        assert result['image_skipped']['reason'].startswith('LLM_IMAGE_INPUT=0')
        body = json.loads((case/'llm_request_body.json').read_bytes())
        assert isinstance(body['messages'][1]['content'], str)
        assert json.loads(body['messages'][1]['content']) == request['input']
        assert 'image' not in request['input']
    if name == 'fixed-pod-timeout':
        assert result['timeout_kind'] == 'callback_deadline'
        fixture = json.loads((case/'timeout-fixture.json').read_text())
        assert len(fixture['requests']) == 1 and fixture['bytes_sent'] > 5
        assert result['worker_wait_elapsed_s'] >= result['deadline_s'] - .01
        assert (case/'llm_http_response.raw').stat().st_size > 0
    if name == 'fixed-pod-server-error':
        assert result['request_sent'] is False and 'refused' in result['error'].lower()
    differences = {}
    for field in ('U', 'p'):
        baseline = internal_values(root/'fixed-pod-no-llm/1e-06'/field)
        actual = internal_values(case/'1e-06'/field)
        delta = actual-baseline
        ref_norm = float(np.linalg.norm(baseline))
        error_norm = float(np.linalg.norm(delta))
        np.testing.assert_allclose(actual, baseline, rtol=1e-10, atol=1e-9)
        differences[field] = {
            'values': actual.size, 'reference_L2': ref_norm, 'difference_L2': error_norm,
            'difference_Linf': float(np.max(np.abs(delta))),
            'relative_L2': error_norm/ref_norm if ref_norm else None,
            'atol': 1e-9, 'rtol': 1e-10,
            'file_identical': (case/'1e-06'/field).read_bytes()
                == (root/'fixed-pod-no-llm/1e-06'/field).read_bytes()}
    reports[name] = {'steps': 10,
                     'files_identical_to_no_request_baseline': compared,
                     'model_status': result['status'],
                     'image_input': result['image_input'],
                     'cpp_measured_full_callback_s': callback_actual,
                     'callback_limit_s': result['deadline_s'] + result['cleanup_budget_s'] + result['kill_join_allowance_s'] + result['scheduling_tolerance_s'],
                     'worker_deadline_s': result['deadline_s'],
                     'timeout_kind': result.get('timeout_kind'),
                     'image': image_report,
                     'final_U_p_comparison': differences}


def model_record(name):
    case = root/name
    request = json.loads((case/'llm_request.json').read_text())
    result = json.loads((case/'llm_result.json').read_text())
    response = json.loads((case/'llm_response.json').read_text())
    assert request['sent'] is True
    assert result['output_format_valid'], result
    assert result['finish_reason'] == 'stop', result
    assert result['output_text'] == response['api_response']['choices'][0]['message']['content']
    assert set(result['structured_output']) == {'observations', 'possible_interpretation', 'checks'}
    assert request['input']['velocity_svd']['window_snapshots'] == 5
    assert request['input']['velocity_svd']['window_start_time_s'] == 1e-7
    assert request['input']['velocity_svd']['window_end_time_s'] == 5e-7
    assert request['input']['velocity_svd']['mean_removed'] is False
    assert request['input']['run_id'] == root.name + '/' + name
    assert request['input']['feature_status'] == 'finite'
    assert request['input']['unavailable']['force_equilibrium']['value'] is None
    assert request['input']['unavailable']['force_equilibrium']['reason']
    assert result['request_sha256'] == hashlib.sha256((case/'llm_request_body.json').read_bytes()).hexdigest()
    assert result['request_bytes'] == (case/'llm_request_body.json').stat().st_size
    return {'model': request['request']['model'], 'image_input': result['image_input'],
            'request_bytes': result['request_bytes'], 'request_sha256': result['request_sha256'],
            'usage': result.get('usage'), 'server_timings': result.get('server_timings'),
            'inference_wall_s': result['inference_wall_s'], 'callback_elapsed_s': result['callback_elapsed_s'],
            'summary_wall_s': result['summary_wall_s'], 'image_render_wall_s': result.get('image_render_wall_s'),
            'structured_output': result['structured_output']}


image_run = model_record('fixed-pod')
text_run = model_record('fixed-pod-text-only')
assert image_run['image_input'] is True and text_run['image_input'] is False
assert image_run['model'] == text_run['model']
assert text_run['request_bytes'] < 24576
timing = json.loads((root/'timings.json').read_text())
for item in timing.values():
    assert item['exit_status'] == 0 and item['concurrent_samples'] > 0
    assert item['cfd_python_peak_pss_sum_kib'] > 0 and item['llama_server_peak_pss_kib'] > 0
assert len({item['llama_server_pid'] for item in timing.values()}) == 1
server = json.loads((root/'resident-server.json').read_text())
assert server['pid'] == timing['fixed-pod']['llama_server_pid'] and server['mmproj_loaded']
base = timing['fixed-pod-no-llm']['wall_seconds']
reports['timings'] = {'without_request_seconds': base,
                      'with_image_request_seconds': timing['fixed-pod']['wall_seconds'],
                      'with_text_request_seconds': timing['fixed-pod-text-only']['wall_seconds'],
                      'added_wall_seconds_image': timing['fixed-pod']['wall_seconds']-base,
                      'added_wall_seconds_text': timing['fixed-pod-text-only']['wall_seconds']-base,
                      'inference_wall_seconds_image': image_run['inference_wall_s'],
                      'inference_wall_seconds_text': text_run['inference_wall_s'],
                      'cpp_full_callback_seconds_image': reports['fixed-pod']['cpp_measured_full_callback_s'],
                      'cpp_full_callback_seconds_text': reports['fixed-pod-text-only']['cpp_measured_full_callback_s']}
reports['resources'] = timing
reports['resident_server'] = {'pid': server['pid'], 'mmproj_loaded': server['mmproj_loaded'], 'models': server['models']}
reports['model'] = image_run['model']
reports['analysis_time_s'] = 5e-7
reports['input_comparison'] = {'image': image_run, 'text_only': text_run}
reports['status'] = 'PASS'
print(json.dumps(reports, indent=2))
