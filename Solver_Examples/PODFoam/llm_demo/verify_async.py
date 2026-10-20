"""Check one asynchronous demo run: unchanged fields, no stall at the request step, arrival records."""
from pathlib import Path
import base64
import hashlib
import json
import re
import sys
import numpy as np



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


root = Path(sys.argv[1])
settings = json.loads((root/'async-settings.json').read_text())
STEPS, WRITE_EVERY = settings['steps'], settings['write_every']
CALLBACK_FILES = ('python_module.py', 'llm_client.py', 'pod_image.py', 'bounded_ipc.py', 'pod_svd.py')
CASES = ('async-no-llm', 'async-describe', 'async-sequence', 'async-server-error', 'async-timeout')
EXPECTED_STATUS = {'async-no-llm': 'disabled', 'async-describe': 'ok', 'async-sequence': 'ok',
                   'async-server-error': 'error', 'async-timeout': 'timeout'}
reports = {}


def written_dirs(case):
    return sorted((d for d in case.iterdir() if d.is_dir() and re.fullmatch(r'[0-9.eE+-]+', d.name)
                   and float(d.name) > 0 and (d/'U').exists()), key=lambda d: float(d.name))


def check_frame(case, frame):
    """A frame's PNG and arrays belong together and match the written fields of that step."""
    directory = Path(frame['path']).parent
    meta = json.loads((directory/'image-metadata.json').read_text())
    png, fields = directory/'state.png', directory/'fields.npz'
    assert meta['sha256'] == sha256(png) == frame['sha256']
    assert meta['fields_sha256'] == sha256(fields) == frame['fields_sha256']
    assert meta['step'] == frame['step'] and meta['time_s'] == frame['time_s']
    saved = np.load(fields)
    step_dir = case/f"{frame['time_s']:g}"
    if step_dir.is_dir():
        np.testing.assert_allclose(saved['U'], internal_values(step_dir/'U').reshape(-1, 3), rtol=1e-11, atol=0)
        np.testing.assert_allclose(saved['p'], internal_values(step_dir/'p'), rtol=1e-11, atol=0)
        return True
    return False


for name in CASES:
    case = root/name
    for filename in CALLBACK_FILES:
        assert (case/filename).read_bytes() == (root/'executed-callback-source'/filename).read_bytes()
    log = (case/'log.PODFoam').read_text()
    assert re.search(r'^End$', log, re.M) and 'Python finalized successfully' in log
    assert not re.search(r'(?i)\b(nan|inf)\b|FOAM FATAL', log)
    states = [json.loads(line) for line in (case/'telemetry.jsonl').read_text().splitlines()]
    assert len(states) == STEPS, (name, len(states))
    assert all('p_cells' not in s for s in states)
    walls = {int(m[1]): float(m[2]) for m in re.finditer(
        r'POD analysis callback returned: step=(\d+) wall_seconds=(\S+)', log)}
    assert len(walls) == STEPS
    result = json.loads((case/'llm_result.json').read_text())
    request = json.loads((case/'llm_request.json').read_text())
    assert result['status'] == EXPECTED_STATUS[name], (name, result.get('status'), result.get('error'))
    assert result['async'] is True and result['worker_reaped']
    request_step = result['request_step']
    arrival = result['arrived_at_step']
    assert request_step == (settings['sequence_steps'][-1] if name in ('async-sequence', 'async-no-llm')
                            else settings['request_step'])
    assert arrival >= request_step
    # the solver never waited at the request step
    assert walls[request_step] < 0.5, (name, walls[request_step])
    assert result['solver_stall_s'] < 0.5
    # all other steps are quick except the one where the answer landed (bounded
    # report write) and the last step (end wait)
    others = {s: w for s, w in walls.items() if s not in (request_step, arrival, STEPS)}
    assert max(others.values()) < 1.0, (name, max(others.items(), key=lambda kv: kv[1]))
    markers = [json.loads(line.split('PYTHON LLM_MARKER ', 1)[1])
               for line in log.splitlines() if line.startswith('PYTHON LLM_MARKER ')]
    events = [m['event'] for m in markers]
    assert events[0] == 'request_started_async' and events[-1] == 'response_after', (name, events)
    assert markers[-1]['arrived_at_step'] == arrival
    # the arrival line sits after the request step's time line and before (or at) the end
    position = log.index('"event":"response_after"')
    assert position > log.index(f'Time = {states[request_step-1]["time_s"]:g} ')
    # fields identical to the baseline at every written time
    compared = 0
    for folder in written_dirs(root/'async-no-llm'):
        for field in folder.iterdir():
            if field.is_file():
                assert field.read_bytes() == (case/folder.name/field.name).read_bytes(), (name, field)
                compared += 1
    assert compared > 0
    frames_report = None
    baseline_frames = {f['step']: f for f in json.loads((root/'async-no-llm/llm_result.json').read_text())['frames']}
    if name in ('async-sequence', 'async-no-llm'):
        assert [f['step'] for f in result['frames']] == settings['sequence_steps']
        frames_report = [{'step': f['step'], 'written_fields_checked': check_frame(case, f),
                          'fields_sha256': f['fields_sha256'], 'png_sha256': f['sha256'],
                          'same_fields_as_baseline': f['fields_sha256'] == baseline_frames[f['step']]['fields_sha256'],
                          'same_png_as_baseline': f['sha256'] == baseline_frames[f['step']]['sha256']}
                         for f in result['frames']]
        assert all(f['same_fields_as_baseline'] and f['same_png_as_baseline'] for f in frames_report), (name, frames_report)
        body = json.loads((case/'llm_request_body.json').read_bytes())
        parts = body['messages'][1]['content']
        images = [p for p in parts if p['type'] == 'image_url']
        assert len(images) == len(result['frames'])
        for part, frame in zip(images, result['frames']):
            data = part['image_url']['url'].split(',', 1)[1]
            assert hashlib.sha256(base64.b64decode(data)).hexdigest() == frame['sha256']
        assert body['response_format']['json_schema']['name'] == 'fluid_sequence'
    else:
        assert result['image_input'] is True
        if 'image' in result:
            frame = {'path': result['image']['path'], 'sha256': result['image']['sha256'],
                     'fields_sha256': result['image']['fields_sha256'], 'step': result['step'],
                     'time_s': result['time_s']}
            same = (baseline_frames[result['step']]['fields_sha256'] == frame['fields_sha256']
                    if result['step'] in baseline_frames else None)
            frames_report = [{'step': result['step'], 'written_fields_checked': check_frame(case, frame),
                              'fields_sha256': frame['fields_sha256'], 'png_sha256': frame['sha256'],
                              'same_fields_as_baseline_frame': same}]
            assert same is not False, (name, frames_report)
    if name == 'async-timeout':
        assert result['timeout_kind'] == 'callback_deadline'
        fixture = json.loads((case/'timeout-fixture.json').read_text())
        assert len(fixture['requests']) == 1 and fixture['bytes_sent'] > 5
    if name == 'async-server-error':
        assert result['request_sent'] is False and 'refused' in result['error'].lower()
    reports[name] = {'steps': STEPS, 'request_step': request_step, 'arrived_at_step': arrival,
                     'answer_arrived_before_end': arrival < STEPS,
                     'end_wait_s': result.get('end_wait_s'),
                     'files_identical_to_no_request_baseline': compared,
                     'model_status': result['status'], 'mode': result['mode'],
                     'callback_wall_s': {'request_step': walls[request_step],
                                         'arrival_step': walls[arrival],
                                         'last_step': walls[STEPS],
                                         'max_other_steps': max(others.values()),
                                         'median_all_steps': float(np.median(list(walls.values())))},
                     'solver_stall_s': result['solver_stall_s'],
                     'inference_wall_s': result.get('inference_wall_s'),
                     'frames': frames_report,
                     'structured_output': result.get('structured_output')}

timing = json.loads((root/'timings.json').read_text())
for item in timing.values():
    assert item['exit_status'] == 0
reports['timings'] = {k: v['wall_seconds'] for k, v in timing.items()}
reports['resources'] = timing
reports['settings'] = settings
reports['status'] = 'PASS'
print(json.dumps(reports, indent=2))
