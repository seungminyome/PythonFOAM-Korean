"""Check one asynchronous demo run: unchanged fields, no stall at the request step, arrival records.

For runs with v2 pictures (settings image_style v2) it also checks that every request body
is the shared builder (readable_request.py) applied to the frames on disk, and scores the
answers against the arrays the pictures were drawn from (reported, not asserted).
"""
from pathlib import Path
import base64
import hashlib
import json
import re
import sys
import numpy as np


def check(condition, message=None):
    """Like assert, but kept under python -O: a failed check stops the script."""
    if not condition:
        raise AssertionError(message) if message is not None else AssertionError()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def internal_values(path):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(), flags=re.S)
    match = re.search(r'internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;', text, re.S)
    check(match, path)
    values = np.fromstring(match[3].replace('(', ' ').replace(')', ' '), sep=' ')
    check(values.size == int(match[2]) * (3 if match[1] == 'vector' else 1))
    check(np.isfinite(values).all())
    return values


def main(argv):
    if len(argv) != 2:
        sys.exit(f'usage: {argv[0]} RUN_DIRECTORY')
    root = Path(argv[1])
    settings = json.loads((root/'async-settings.json').read_text())
    STEPS, WRITE_EVERY = settings['steps'], settings['write_every']
    T0 = settings.get('start_time_s', 0.0)
    STYLE = settings.get('image_style', 'v1')
    # every file frozen for the run
    CALLBACK_FILES = tuple(sorted(p.name for p in (root/'executed-callback-source').iterdir() if p.is_file()))
    if STYLE == 'v2':
        # the frozen modules, so the parity check uses exactly the code the solver ran
        sys.path.insert(0, str(root/'executed-callback-source'))
        import readable_request
        from llm_client import encode_json
        sys.path.insert(1, str(Path(__file__).resolve().parent))
        import frame_scoring
    CASES = ('async-no-llm', 'async-describe', 'async-sequence', 'async-server-error', 'async-timeout')
    EXPECTED_STATUS = {'async-no-llm': 'disabled', 'async-describe': 'ok', 'async-sequence': 'ok',
                       'async-server-error': 'error', 'async-timeout': 'timeout'}
    reports = {}


    def written_dirs(case):
        """Time directories the run wrote (the start state, if any, is not one of them)."""
        return sorted((d for d in case.iterdir() if d.is_dir() and re.fullmatch(r'[0-9.eE+-]+', d.name)
                       and float(d.name) > T0 + 1e-12 and (d/'U').exists()), key=lambda d: float(d.name))


    def time_dir(case, time_s):
        """The written directory of a time, or None; names follow timePrecision 10."""
        return next((d for d in written_dirs(case) if abs(float(d.name) - time_s) <= 1e-9 * max(1.0, time_s)), None)


    def check_written_fields(case, fields, time_s):
        step_dir = time_dir(case, time_s)
        if step_dir is None:
            return False
        saved = np.load(fields)
        np.testing.assert_allclose(saved['U'], internal_values(step_dir/'U').reshape(-1, 3), rtol=1e-11, atol=0)
        np.testing.assert_allclose(saved['p'], internal_values(step_dir/'p'), rtol=1e-11, atol=0)
        return True


    def check_frame(case, frame):
        """A frame's PNG and arrays belong together and match the written fields of that step."""
        directory = Path(frame['path']).parent
        meta = json.loads((directory/'image-metadata.json').read_text())
        png, fields = directory/'state.png', directory/'fields.npz'
        check(meta['sha256'] == sha256(png) == frame['sha256'])
        check(meta['fields_sha256'] == sha256(fields) == frame['fields_sha256'])
        check(meta['step'] == frame['step'] and meta['time_s'] == frame['time_s'])
        return check_written_fields(case, fields, frame['time_s'])


    def check_frame_v2(case, record, solver_time_s):
        """v2: both pictures and the arrays match the metadata and the record, the frame carries the
        solver's time of its step, and at a write step its arrays equal the written fields."""
        directory = Path(record['directory'])
        check(directory.resolve().parent == (case/'llm_observation').resolve(), directory)
        frame, meta, _ = readable_request.load_frame(directory)   # checks every hash
        check(meta['fields_sha256'] == record['fields_sha256'])
        check({k: v['sha256'] for k, v in record['images'].items()} == frame['image_sha256'])
        check(meta['step'] == record['step'] and meta['time_s'] == record['time_s'] == solver_time_s, \
            (case.name, record['step'], meta['time_s'], solver_time_s))
        check(not any(image['colour_range_shared'] for image in meta['images']))
        written = check_written_fields(case, directory/'fields.npz', solver_time_s)
        check(written or record['step'] % WRITE_EVERY != 0, (case.name, record['step']))
        return frame, written


    def score_v2(name, result, frames):
        """Scores of the answer against the arrays of its pictures (frame_scoring rules)."""
        output = result.get('structured_output')
        if not output:
            return None
        truths = [frame_scoring.load_v2(f['directory'])[1] for f in frames]
        if result['mode'] == 'describe':
            scores = frame_scoring.score_describe(output, truths[0])
            return {'truth': {k: truths[0][k] for k in ('fastest_flow', 'lowest_pressure', 'plotted_range_m')},
                    'scores': scores}
        truth = frame_scoring.sequence_truth(truths)
        return {'truth': truth, 'scores': frame_scoring.score_sequence(output, truth)}


    for name in CASES:
        case = root/name
        for filename in CALLBACK_FILES:
            check((case/filename).read_bytes() == (root/'executed-callback-source'/filename).read_bytes())
        log = (case/'log.PODFoam').read_text()
        check(re.search(r'^End$', log, re.M) and 'Python finalized successfully' in log)
        check(not re.search(r'(?i)\b(nan|inf)\b|FOAM FATAL', log))
        # telemetry.jsonl exists only complete: a leftover .tmp, or no file at all, means the
        # telemetry did not complete; llm_errors.jsonl and the solver log say why
        check(not (case/'telemetry.jsonl.tmp').exists(), (name, 'final telemetry write did not complete'))
        check((case/'telemetry.jsonl').exists(), (name, 'no telemetry.jsonl: the telemetry did not complete'))
        states = [json.loads(line) for line in (case/'telemetry.jsonl').read_text().splitlines()]
        check(len(states) == STEPS, (name, len(states)))
        check(all('p_cells' not in s for s in states))
        walls = {int(m[1]): float(m[2]) for m in re.finditer(
            r'POD analysis callback returned: step=(\d+) snapshots=\d+ wall_seconds=(\S+)', log)}
        check(len(walls) == STEPS)
        courant = [float(m[1]) for m in re.finditer(r'^Courant Number mean: \S+ max: (\S+)', log, re.M)]
        check(courant, name)
        # from t = 0 the impulsive start gives Co up to 1.05 for a few steps;
        # a run from a developed state must stay below 1 with its fixed time step
        if 'start_files_sha256' in settings:
            check(max(courant) < 1.0, (name, max(courant)))
        if 'start_files_sha256' in settings:
            start = case/Path(settings['start_dir']).name
            check({p.name: sha256(p) for p in start.iterdir() if p.is_file()} == settings['start_files_sha256'])
            check(f"Time = {T0 + float(settings['delta_t_s']):.10g} " in log)
        result = json.loads((case/'llm_result.json').read_text())
        request = json.loads((case/'llm_request.json').read_text())
        check(result['status'] == EXPECTED_STATUS[name], (name, result.get('status'), result.get('error')))
        check(result['async'] is True and result['worker_reaped'])
        request_step = result['request_step']
        arrival = result['arrived_at_step']
        check(request_step == (settings['sequence_steps'][-1] if name in ('async-sequence', 'async-no-llm')
                                else settings['request_step']))
        check(arrival >= request_step)
        # the solver never waited at the request step
        check(walls[request_step] < 0.5, (name, walls[request_step]))
        check(result['solver_stall_s'] < 0.5)
        # all other steps are quick except the one where the answer landed (bounded
        # report write) and the last step (end wait)
        others = {s: w for s, w in walls.items() if s not in (request_step, arrival, STEPS)}
        check(max(others.values()) < 1.0, (name, max(others.items(), key=lambda kv: kv[1])))
        markers = [json.loads(line.split('PYTHON LLM_MARKER ', 1)[1])
                   for line in log.splitlines() if line.startswith('PYTHON LLM_MARKER ')]
        events = [m['event'] for m in markers]
        check(events[0] == 'request_started_async' and events[-1] == 'response_after', (name, events))
        check(markers[-1]['arrived_at_step'] == arrival)
        # the arrival line sits after the request step's time line and before (or at) the end
        position = log.index('"event":"response_after"')
        check(position > log.index(f'Time = {states[request_step-1]["time_s"]:.10g} '))
        # fields identical to the baseline at every written time
        compared = 0
        for folder in written_dirs(root/'async-no-llm'):
            for field in folder.iterdir():
                if field.is_file():
                    check(field.read_bytes() == (case/folder.name/field.name).read_bytes(), (name, field))
                    compared += 1
        check(compared > 0)
        frames_report = None
        scores = None
        baseline_frames = {f['step']: f for f in json.loads((root/'async-no-llm/llm_result.json').read_text())['frames']}
        body_bytes = (case/'llm_request_body.json').read_bytes() if (case/'llm_request_body.json').exists() else None
        if STYLE == 'v2' and name in ('async-sequence', 'async-no-llm'):
            check(result['image_style'] == 'v2' and result['sequence_colour_range'] == 'own')
            check([f['step'] for f in result['frames']] == settings['sequence_steps'])
            frames, frames_report = [], []
            for record in result['frames']:
                frame, written = check_frame_v2(case, record, states[record['step'] - 1]['time_s'])
                base = baseline_frames[record['step']]
                frames.append(frame)
                frames_report.append({'step': record['step'], 'written_fields_checked': written,
                                      'fields_sha256': record['fields_sha256'],
                                      'png_sha256': frame['image_sha256'],
                                      'same_fields_as_baseline': record['fields_sha256'] == base['fields_sha256'],
                                      'same_pngs_as_baseline': {k: v['sha256'] for k, v in record['images'].items()}
                                                               == {k: v['sha256'] for k, v in base['images'].items()}})
            check(all(f['same_fields_as_baseline'] and f['same_pngs_as_baseline'] for f in frames_report), (name, frames_report))
            body = json.loads(body_bytes)
            images = [p for p in body['messages'][1]['content'] if p['type'] == 'image_url']
            check(len(images) == 2 * len(frames))
            for k, frame in enumerate(frames):
                for part, field in zip(images[2 * k:2 * k + 2], ('U', 'p')):
                    data = part['image_url']['url'].split(',', 1)[1]
                    check(hashlib.sha256(base64.b64decode(data)).hexdigest() == frame['image_sha256'][field])
            # LLM_SEQUENCE_PROMPT: own (default), t or tn
            form = result.get('sequence_prompt', 'own')
            truths = [frame_scoring.load_v2(f['directory'])[1] for f in frames]
            options, system = {}, readable_request.SEQUENCE_V2OWN_SYSTEM_PROMPT
            if form == 't':
                options, system = {'thresholds': True}, readable_request.SEQUENCE_V2OWN_T_SYSTEM_PROMPT
            elif form == 'tn':
                options = {'thresholds': True, 'numbers': [frame_scoring.numbers_of(t) for t in truths]}
                system = readable_request.SEQUENCE_V2OWN_TN_SYSTEM_PROMPT
            check(body['messages'][0]['content'] == system)
            check(body['response_format']['json_schema']['name'] == 'fluid_sequence')
            # live request == the tested builder applied to the frames on disk, byte for byte
            check(body_bytes == encode_json(readable_request.sequence_v2_payload(
                frames, model=body['model'], own_ranges=True, **options)), name)
            if 'computed_trends' in result:
                # the callback records the answer key it computed from the frames
                key = frame_scoring.sequence_truth(truths)
                check(result['computed_trends'] == json.loads(json.dumps(key)), name)
                if 'computed_trends_agreement' in result:
                    check(result['computed_trends_agreement'] == frame_scoring.score_sequence(
                        result['structured_output'], result['computed_trends']), name)
            if name == 'async-sequence':
                scores = score_v2(name, result, frames)
        elif STYLE == 'v2' and result['mode'] == 'describe':
            # a worker killed at the deadline (async-timeout) never reports its frame; llm_request.json has it
            record = result.get('image') or request.get('image')
            check(record, (name, 'no v2 frame recorded'))
            check(result['image_style'] == 'v2' and request['image_input'] is True)
            frame, written = check_frame_v2(case, record, states[result['step'] - 1]['time_s'])
            check(frame['step'] == result['step'] and frame['time_s'] == result['time_s'])
            base = baseline_frames.get(result['step'])
            same = base['fields_sha256'] == record['fields_sha256'] if base else None
            frames_report = [{'step': result['step'], 'written_fields_checked': written,
                              'fields_sha256': record['fields_sha256'],
                              'png_sha256': frame['image_sha256'], 'same_fields_as_baseline_frame': same}]
            check(same is not False, (name, frames_report))
            body = json.loads(body_bytes)
            check(body['messages'][0]['content'] == readable_request.DESCRIBE_V2_SYSTEM_PROMPT)
            check(body_bytes == encode_json(readable_request.describe_v2_payload(frame, model=body['model'])), name)
            if name == 'async-describe':
                scores = score_v2(name, result, [frame])
        elif STYLE == 'v2':
            check(result['image_style'] == 'v2')
        elif name in ('async-sequence', 'async-no-llm'):
            check([f['step'] for f in result['frames']] == settings['sequence_steps'])
            frames_report = [{'step': f['step'], 'written_fields_checked': check_frame(case, f),
                              'fields_sha256': f['fields_sha256'], 'png_sha256': f['sha256'],
                              'same_fields_as_baseline': f['fields_sha256'] == baseline_frames[f['step']]['fields_sha256'],
                              'same_png_as_baseline': f['sha256'] == baseline_frames[f['step']]['sha256']}
                             for f in result['frames']]
            check(all(f['same_fields_as_baseline'] and f['same_png_as_baseline'] for f in frames_report), (name, frames_report))
            body = json.loads((case/'llm_request_body.json').read_bytes())
            parts = body['messages'][1]['content']
            images = [p for p in parts if p['type'] == 'image_url']
            check(len(images) == len(result['frames']))
            for part, frame in zip(images, result['frames']):
                data = part['image_url']['url'].split(',', 1)[1]
                check(hashlib.sha256(base64.b64decode(data)).hexdigest() == frame['sha256'])
            check(body['response_format']['json_schema']['name'] == 'fluid_sequence')
        else:
            check(result['image_input'] is True)
            if 'image' in result:
                frame = {'path': result['image']['path'], 'sha256': result['image']['sha256'],
                         'fields_sha256': result['image']['fields_sha256'], 'step': result['step'],
                         'time_s': result['time_s']}
                same = (baseline_frames[result['step']]['fields_sha256'] == frame['fields_sha256']
                        if result['step'] in baseline_frames else None)
                frames_report = [{'step': result['step'], 'written_fields_checked': check_frame(case, frame),
                                  'fields_sha256': frame['fields_sha256'], 'png_sha256': frame['sha256'],
                                  'same_fields_as_baseline_frame': same}]
                check(same is not False, (name, frames_report))
        if name == 'async-timeout':
            check(result['timeout_kind'] == 'callback_deadline')
            fixture = json.loads((case/'timeout-fixture.json').read_text())
            check(len(fixture['requests']) == 1 and fixture['bytes_sent'] > 5)
            # the deadline was enforced at the value the callback recorded
            check(result['deadline_s'] <= result['worker_wait_elapsed_s'] < result['deadline_s'] + 1.0, \
                result['worker_wait_elapsed_s'])
        if name in ('async-timeout', 'async-server-error'):
            # the callback used the fixture deadline the suite set
            check(result['deadline_s'] == settings.get('fixture_deadline_s', 4), (name, result['deadline_s']))
        if name == 'async-server-error':
            check(result['request_sent'] is False and 'refused' in result['error'].lower())
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
                         'image_style': result.get('image_style', 'v1'),
                         'structured_output': result.get('structured_output'),
                         'score': scores,
                         'max_courant': max(courant)}

    timing = json.loads((root/'timings.json').read_text())
    for item in timing.values():
        check(item['exit_status'] == 0)
    reports['timings'] = {k: v['wall_seconds'] for k, v in timing.items()}
    reports['resources'] = timing
    reports['settings'] = settings
    reports['status'] = 'PASS'
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main(sys.argv)
