"""Describe requests from a running solver at several steps, each with its own plotted window.

Runs after run_async_cases.py with v2 pictures (LLM_IMAGE_STYLE=v2) and, usually, a start state
(LLM_LONG_START). Every case here starts from the same state as the suite's async-no-llm
baseline, sends one asynchronous v2 describe request at step R with a window placed at random
around the fastest cell of the baseline's written state at R (the window_test.py rule: the
cell at least 15 % from every edge, at least 200 cells, height 0.03 to 0.114 m, width 1.5 to 4
heights), and stops a few hundred steps later. A single window for a whole run would leave the
answer in nearly the same place every time; here one fixed answer scores about one in ten.

Checks per case (asserted at the end, after sweep-summary.json is written): the solver and the
request finished; the answer arrived while the solver kept stepping, not in the end wait; the
request body equals readable_request.describe_v2_payload applied to the frame on disk, byte for
byte; the frame's arrays equal the baseline's written fields at R, so the picture shows the
state the solver reached. A failed case is recorded with its reason and the others go on.
Scores (reported, not asserted): fastest flow and lowest pressure within 10 % of the plotted
range, against the arrays the pictures were drawn from.

usage: run_live_sweep.py <suite run directory> <PODFoam executable> <output directory>
       [--steps 500,1000,...] [--after 300] [--seed 20261024] [--parallel 2]
The model server and the environment are the suite's (LLM_ENDPOINT, LLM_MODEL, POD_LLM_STATE).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent


def internal_values(path):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(), flags=re.S)
    match = re.search(r'internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;', text, re.S)
    assert match, path
    values = np.fromstring(match[3].replace('(', ' ').replace(')', ' '), sep=' ')
    assert values.size == int(match[2]) * (3 if match[1] == 'vector' else 1)
    return values


def time_dir(case, time_s):
    for d in case.iterdir():
        if d.is_dir() and re.fullmatch(r'[0-9.eE+-]+', d.name) and abs(float(d.name) - time_s) <= 1e-9 * max(1.0, time_s):
            return d
    return None


def stage(baseline, case, start_name, end_time):
    for name in ('0', 'constant', 'system') + ((start_name,) if start_name else ()):
        shutil.copytree(baseline/name, case/name)
    control = (case/'system/controlDict').read_text()
    control = re.sub(r'^endTime .*$', f'endTime {end_time:.12g};', control, flags=re.M)
    (case/'system/controlDict').write_text(control)


def run_case(job):
    """One solver run; never raises, so one failed case does not cancel the others."""
    case, env, executable, outer_timeout = job['case'], job['env'], job['executable'], job['timeout']
    start = time.monotonic()
    outcome = {'name': case.name, 'exit_status': None, 'error': None}
    try:
        with (case/'log.PODFoam').open('w') as log:
            process = subprocess.run([str(executable), '-case', str(case)], env=env, stdout=log,
                                     stderr=subprocess.STDOUT, timeout=outer_timeout)
        outcome['exit_status'] = process.returncode
    except subprocess.TimeoutExpired:
        outcome['error'] = f'outer timeout {outer_timeout:.0f} s'
    except OSError as error:
        outcome['error'] = repr(error)
    outcome['wall_seconds'] = time.monotonic() - start
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('suite')
    parser.add_argument('executable')
    parser.add_argument('output')
    parser.add_argument('--steps', default='')
    parser.add_argument('--after', type=int, default=300, help='steps run after the request step')
    parser.add_argument('--seed', type=int, default=20261024)
    parser.add_argument('--parallel', type=int, default=2)
    args = parser.parse_args()
    suite, output = Path(args.suite).resolve(), Path(args.output).resolve()
    settings = json.loads((suite/'async-settings.json').read_text())
    assert settings.get('image_style') == 'v2', 'the sweep needs a suite run with LLM_IMAGE_STYLE=v2'
    frozen = suite/'executed-callback-source'
    sys.dont_write_bytecode = True   # keep the suite's record of the executed sources unchanged
    sys.path[:0] = [str(frozen), str(HERE)]
    import readable_request
    from llm_client import encode_json
    import picture_test
    import snapshot_runner
    import window_test

    baseline = suite/'async-no-llm'
    t0, dt, write_every = settings.get('start_time_s', 0.0), settings['delta_t_s'], settings['write_every']
    start_name = Path(settings['start_dir']).name if settings.get('start_dir') else None
    steps = ([int(s) for s in args.steps.split(',')] if args.steps else
             list(range(2 * write_every, settings['steps'] - args.after + 1, 2 * write_every)))
    if not steps:
        sys.exit(f"no request step fits: the suite ran {settings['steps']} steps written every {write_every}; "
                 f"the default needs at least 2*write_every + after = {2 * write_every + args.after}; pass --steps")
    assert all(s % write_every == 0 and s + args.after <= settings['steps'] for s in steps), steps
    centres_npz = next(baseline.glob('llm_observation/step-*/fields.npz'))
    with np.load(centres_npz) as arrays:
        centres = np.array(arrays['centres'])
    xy = centres[:, :2]
    domain = [[float(xy[:, 0].min()), float(xy[:, 0].max())], [float(xy[:, 1].min()), float(xy[:, 1].max())]]
    rng = np.random.default_rng(args.seed)
    output.mkdir(parents=True, exist_ok=False)
    plan, jobs = [], []
    for step in steps:
        state = time_dir(baseline, t0 + step * dt)
        assert state is not None, f'no written state at step {step}'
        speed = np.linalg.norm(internal_values(state/'U').reshape(-1, 3), axis=1)
        window = window_test.place_window(rng, xy[int(np.argmax(speed))], domain, xy)
        name = f'describe-step{step:06d}'
        case = output/name
        stage(baseline, case, start_name, t0 + (step + args.after) * dt)
        for path in frozen.iterdir():
            if path.is_file():
                shutil.copy2(path, case/path.name)
        # the suite's environment (run_demo.sh): one BLAS thread per solver, no user site
        env = dict(os.environ, LLM_ENABLED='1', LLM_IMAGE_INPUT='1', LLM_ASYNC='1', LLM_MODE='describe',
                   LLM_IMAGE_STYLE='v2', LLM_ANALYSIS_STEP=str(step),
                   LLM_IMAGE_XRANGE=f'{window[0][0]!r},{window[0][1]!r}',
                   LLM_IMAGE_YRANGE=f'{window[1][0]!r},{window[1][1]!r}',
                   LLM_RUN_ID=f'{output.name}/{name}', MPLCONFIGDIR=str(case/'mpl-cache'),
                   OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1')
        for key in ('LLM_FINAL_STEP', 'LLM_SEQUENCE_STEPS', 'PYTHONHOME', 'PYTHONPATH'):
            env.pop(key, None)
        plan.append({'name': name, 'request_step': step, 'state_dir': str(state), 'window_m': window})
        jobs.append({'case': case, 'env': env, 'executable': Path(args.executable),
                     'timeout': 120 + 90 + 0.5 * (step + args.after)})
    (output/'sweep-plan.json').write_text(json.dumps({'suite': str(suite), 'seed': args.seed, 'after': args.after,
                                                      'plan': plan}, indent=2) + '\n')
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        runs = {r['name']: r for r in pool.map(run_case, jobs)}

    reports, truths = [], []
    for item in plan:
        case = output/item['name']
        run = runs[item['name']]
        step = item['request_step']
        report = {'name': item['name'], 'request_step': step, 'window_m': item['window_m'],
                  'wall_seconds': run['wall_seconds'], 'request_step_wall_s': None}
        try:
            if run['error'] or run['exit_status'] != 0:
                report.update(status='solver_failed', error=run['error'] or f"exit {run['exit_status']}")
                reports.append(report)
                continue
            log = (case/'log.PODFoam').read_text()
            if not (re.search(r'^End$', log, re.M) and 'Python finalized successfully' in log):
                report.update(status='solver_failed', error='no End or no Python finalization in log.PODFoam')
                reports.append(report)
                continue
            result = json.loads((case/'llm_result.json').read_text())
            walls = {int(m[1]): float(m[2]) for m in re.finditer(
                r'POD analysis callback returned: step=(\d+) wall_seconds=(\S+)', log)}
            report.update(status=result['status'], arrived_at_step=result.get('arrived_at_step'),
                          end_wait_s=result.get('end_wait_s'), solver_stall_s=result.get('solver_stall_s'),
                          request_step_wall_s=walls.get(step), inference_wall_s=result.get('inference_wall_s'))
            if result['status'] == 'ok':
                folder = case/'llm_observation'/f'step-{step:06d}'
                frame, meta, fields = readable_request.load_frame(folder)
                state = Path(item['state_dir'])
                np.testing.assert_allclose(fields['U'], internal_values(state/'U').reshape(-1, 3), rtol=1e-11, atol=0)
                np.testing.assert_allclose(fields['p'], internal_values(state/'p'), rtol=1e-11, atol=0)
                body = (case/'llm_request_body.json').read_bytes()
                parity = body == encode_json(readable_request.describe_v2_payload(frame, model=json.loads(body)['model']))
                truth = picture_test.load_v2(folder)[1]
                scores = snapshot_runner.score_describe(result['structured_output'], truth)
                report.update(arrived_while_running=(step < result['arrived_at_step'] <= step + args.after
                                                     and result.get('end_wait_s') is None),
                              request_equals_tested_builder=parity, fields_equal_baseline_state=True,
                              structured_output=result['structured_output'],
                              truth={k: truth[k] for k in ('fastest_flow', 'lowest_pressure', 'cells_in_window')},
                              scores=scores)
                truths.append(truth)
        except Exception as error:   # a check failed: record it, never leave the case 'ok'
            report.update(status='check_failed', error=repr(error))
        reports.append(report)
    ok = [r for r in reports if r['status'] == 'ok']
    summary = {
        'requests': len(reports), 'ok': len(ok),
        'all_bodies_equal_tested_builder': all(r['request_equals_tested_builder'] for r in ok),
        'all_arrived_while_running': all(r['arrived_while_running'] for r in ok),
        'fastest_flow_within_10_percent': sum(r['scores']['fastest_flow']['within_10_percent'] for r in ok),
        'lowest_pressure_within_10_percent': sum(r['scores']['lowest_pressure']['within_10_percent'] for r in ok),
        'median_distance_percent': {k: statistics.median(r['scores'][k]['distance_percent'] for r in ok) if ok else None
                                    for k in ('fastest_flow', 'lowest_pressure')},
        'one_fixed_answer_for_all': window_test.pooled_constant_answer_baseline('describe', truths) if truths else None,
        'max_request_step_wall_s': max((r.get('request_step_wall_s') or 0) for r in reports),
        'arrival_delay_steps': [r['arrived_at_step'] - r['request_step'] for r in ok],
        'inference_wall_s': [r['inference_wall_s'] for r in ok],
        'cases': reports,
    }
    (output/'sweep-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'cases'}, indent=2))
    assert (summary['ok'] == summary['requests'] and summary['all_bodies_equal_tested_builder']
            and summary['all_arrived_while_running']), 'sweep failed'


if __name__ == '__main__':
    main()
