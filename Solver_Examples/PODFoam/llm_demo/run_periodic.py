"""A long run with a describe request every N steps (LLM_ANALYSIS_EVERY), and its twin without
requests; cost, memory, pipe traffic and the answers.

Both cases start from the suite's async-no-llm staging (0/, constant/, system/, the start state)
with a longer end time; the twin has LLM_ENABLED=0 (frames still drawn, nothing sent). Checks:
every written file of the periodic case equals the twin's; every request body equals the tested
builder applied to its frame; every frame's arrays equal the written fields of that step; the
answers are scored against the arrays. Memory (RSS, PSS) of the solver tree and the server is
sampled every 0.5 s; the pipe bytes each request moved come from the callback's records.

usage: run_periodic.py <suite run directory> <PODFoam executable> <output directory>
       [--steps 24000] [--first 250] [--every 250] [--max-pending 1] [--write 250]
The server and the environment are the suite's (LLM_ENDPOINT, LLM_MODEL, POD_LLM_STATE,
LLM_IMAGE_XRANGE/YRANGE).
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_cases import descendants, memory, resident_server  # noqa: E402
from run_live_sweep import internal_values, stage  # noqa: E402


def run_case(case, env, executable, server_pid, timeout_s):
    start = time.monotonic()
    samples, events = [], []
    with (case / 'log.PODFoam').open('w') as log:
        process = subprocess.Popen([str(executable), '-case', str(case)], env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        def read_log():
            for line in process.stdout:
                log.write(line)
                if line.startswith(('PYTHON LLM', 'Python finalized', 'End')):
                    events.append({'wall_since_start_s': time.monotonic() - start, 'line': line.rstrip()})
            log.flush()
        reader = threading.Thread(target=read_log, daemon=True)
        reader.start()
        while process.poll() is None:
            if time.monotonic() - start > timeout_s:
                process.kill()
                raise TimeoutError(f'{case.name}: outer solver timeout')
            tree = [m for pid in descendants(process.pid) if (m := memory(pid))]
            llama = memory(server_pid) if server_pid else None
            samples.append({'wall_since_start_s': time.monotonic() - start, 'llama_server': llama,
                            'processes': len(tree),
                            'cfd_python_rss_sum_kib': sum(m['rss_kib'] or 0 for m in tree),
                            'cfd_python_pss_sum_kib': (sum(m['pss_kib'] for m in tree)
                                                       if tree and all(m['pss_kib'] is not None for m in tree) else None)})
            time.sleep(0.5)
        reader.join(timeout=5)
    (case / 'timeline.json').write_text(json.dumps(events, indent=2) + '\n')
    (case / 'memory-samples.json').write_text(json.dumps(samples, indent=2) + '\n')
    pss = [s['cfd_python_pss_sum_kib'] for s in samples if s['cfd_python_pss_sum_kib'] is not None]
    return {'exit_status': process.returncode, 'wall_seconds': time.monotonic() - start,
            'cfd_python_peak_rss_sum_kib': max((s['cfd_python_rss_sum_kib'] for s in samples), default=None),
            'cfd_python_peak_pss_sum_kib': max(pss, default=None),
            'cfd_python_pss_first_quarter_kib': statistics.median(pss[:max(1, len(pss) // 4)]) if pss else None,
            'cfd_python_pss_last_quarter_kib': statistics.median(pss[-max(1, len(pss) // 4):]) if pss else None,
            'llama_server_peak_rss_kib': max((s['llama_server']['rss_kib'] or 0 for s in samples if s['llama_server']),
                                             default=None)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('suite')
    parser.add_argument('executable')
    parser.add_argument('output')
    parser.add_argument('--steps', type=int, default=24000)
    parser.add_argument('--first', type=int, default=250)
    parser.add_argument('--every', type=int, default=250)
    parser.add_argument('--max-pending', type=int, default=1)
    parser.add_argument('--write', type=int, default=250)
    args = parser.parse_args()
    suite, output = Path(args.suite).resolve(), Path(args.output).resolve()
    settings = json.loads((suite / 'async-settings.json').read_text())
    assert settings.get('image_style') == 'v2', 'needs a suite run with LLM_IMAGE_STYLE=v2'
    frozen = suite / 'executed-callback-source'
    sys.path[:0] = [str(frozen)]
    import readable_request
    from llm_client import encode_json
    import picture_test
    import snapshot_runner
    import window_test
    server = resident_server(os.environ['LLM_ENDPOINT'], Path(os.environ.get('POD_LLM_RUNTIME', '.')))
    baseline = suite / 'async-no-llm'
    t0, dt = settings.get('start_time_s', 0.0), settings['delta_t_s']
    start_name = Path(settings['start_dir']).name if settings.get('start_dir') else None
    output.mkdir(parents=True, exist_ok=False)
    (output / 'resident-server.json').write_text(json.dumps(server, indent=2) + '\n')
    common = dict(os.environ, LLM_IMAGE_INPUT='1', LLM_ASYNC='1', LLM_MODE='describe', LLM_IMAGE_STYLE='v2',
                  LLM_ANALYSIS_STEP=str(args.first), LLM_ANALYSIS_EVERY=str(args.every),
                  LLM_ASYNC_MAX_PENDING=str(args.max_pending), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                  PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1')
    for key in ('LLM_FINAL_STEP', 'LLM_SEQUENCE_STEPS', 'PYTHONHOME', 'PYTHONPATH'):
        common.pop(key, None)
    plan = {'suite': str(suite), 'steps': args.steps, 'first': args.first, 'every': args.every,
            'max_pending': args.max_pending, 'write_every': args.write, 'delta_t_s': dt, 'start_time_s': t0,
            'window_m': {'x': os.environ.get('LLM_IMAGE_XRANGE'), 'y': os.environ.get('LLM_IMAGE_YRANGE')},
            'model': os.environ.get('LLM_MODEL'), 'cases': {}}
    timings = {}
    for name, enabled in (('periodic-no-llm', '0'), ('periodic-describe', '1')):
        case = output / name
        stage(baseline, case, start_name, t0 + args.steps * dt)
        control = (case / 'system/controlDict').read_text()
        control = re.sub(r'^writeInterval .*$', f'writeInterval {args.write};', control, flags=re.M)
        (case / 'system/controlDict').write_text(control)
        for path in frozen.iterdir():
            if path.is_file():
                shutil.copy2(path, case / path.name)
        env = dict(common, LLM_ENABLED=enabled, LLM_RUN_ID=f'{output.name}/{name}', MPLCONFIGDIR=str(case / 'mpl-cache'))
        timings[name] = run_case(case, env, Path(args.executable), server['pid'], 600 + 0.2 * args.steps)
        (output / 'timings.json').write_text(json.dumps(timings, indent=2) + '\n')
        log = (case / 'log.PODFoam').read_text()
        assert timings[name]['exit_status'] == 0 and re.search(r'^End$', log, re.M) and 'Python finalized successfully' in log, name
        print(f'{name}: exit={timings[name]["exit_status"]} wall={timings[name]["wall_seconds"]:.1f}s', flush=True)
    # written files: the periodic case equals its twin
    twin, live = output / 'periodic-no-llm', output / 'periodic-describe'
    same = differ = 0
    for d in twin.iterdir():
        if d.is_dir() and re.fullmatch(r'[0-9.eE+-]+', d.name) and float(d.name) > t0 + 1e-12:
            for f in sorted(p for p in d.rglob('*') if p.is_file()):
                other = live / d.name / f.relative_to(d)
                if other.is_file() and other.read_bytes() == f.read_bytes():
                    same += 1
                else:
                    differ += 1
    # requests
    index = json.loads((live / 'llm_requests' / 'index.json').read_text())
    walls = {int(m[1]): float(m[2]) for m in re.finditer(
        r'POD analysis callback returned: step=(\d+) wall_seconds=(\S+)', (live / 'log.PODFoam').read_text())}
    reports, truths = [], []
    for entry in index['requests']:
        step = entry['step']
        report = dict(entry, request_step_wall_s=walls.get(step))
        folder = live / 'llm_requests' / f'step-{step:06d}'
        if (folder / 'llm_result.json').exists():
            result = json.loads((folder / 'llm_result.json').read_text())
            report.update(ipc_bytes_received=result.get('ipc_bytes_received'), request_bytes=result.get('request_bytes'),
                          arrival_step_wall_s=walls.get(result.get('arrived_at_step')))
            frame_dir = live / 'llm_observation' / f'step-{step:06d}'
            if (frame_dir / readable_request.METADATA).exists():
                frame, meta, fields = readable_request.load_frame(frame_dir)
                body = (folder / 'llm_request_body.json').read_bytes()
                report['request_equals_tested_builder'] = body == encode_json(
                    readable_request.describe_v2_payload(frame, model=json.loads(body)['model']))
                written = live / f'{t0 + step * dt:.10g}'
                if written.is_dir():
                    np.testing.assert_allclose(fields['U'], internal_values(written / 'U').reshape(-1, 3), rtol=1e-11, atol=0)
                    np.testing.assert_allclose(fields['p'], internal_values(written / 'p'), rtol=1e-11, atol=0)
                    report['fields_equal_written'] = True
                truth = picture_test.load_v2(frame_dir)[1]
                if result.get('status') == 'ok':
                    report['scores'] = snapshot_runner.score_describe(result['structured_output'], truth)
                    report['structured_output'] = result['structured_output']
                    truths.append(truth)
        reports.append(report)
    ok = [r for r in reports if r.get('status') == 'ok']
    plan['cases'] = {name: timings[name] for name in timings}
    summary = {
        'requests_planned': len(reports), 'ok': len(ok),
        'statuses': {s: sum(r['status'] == s for r in reports) for s in {r['status'] for r in reports}},
        'all_bodies_equal_tested_builder': all(r.get('request_equals_tested_builder') for r in ok),
        'all_frames_equal_written_fields': all(r.get('fields_equal_written') for r in ok),
        'written_files_identical_to_twin': same, 'written_files_differing': differ,
        'fastest_flow_within_10_percent': sum(r['scores']['fastest_flow']['within_10_percent'] for r in ok),
        'lowest_pressure_within_10_percent': sum(r['scores']['lowest_pressure']['within_10_percent'] for r in ok),
        'median_distance_percent': {k: statistics.median(r['scores'][k]['distance_percent'] for r in ok) if ok else None
                                    for k in ('fastest_flow', 'lowest_pressure')},
        'one_fixed_answer_for_all': picture_test.constant_answer_baseline('describe', truths) if truths else None,
        'arrival_delay_steps': [r['arrived_at_step'] - r['step'] for r in ok],
        'inference_wall_s': [r['inference_wall_s'] for r in ok],
        'solver_stall_s_max': max((r['solver_stall_s'] for r in ok), default=None),
        'request_step_wall_s_max': max((r['request_step_wall_s'] or 0 for r in reports), default=None),
        'arrival_step_wall_s_max': max((r.get('arrival_step_wall_s') or 0 for r in ok), default=None),
        'ipc_bytes_per_request': [r.get('ipc_bytes_received') for r in ok],
        'request_body_bytes': [r.get('request_bytes') for r in ok],
        'wall_seconds': {name: timings[name]['wall_seconds'] for name in timings},
        'seconds_per_step': {name: timings[name]['wall_seconds'] / args.steps for name in timings},
        'memory': {name: {k: v for k, v in timings[name].items() if 'kib' in k} for name in timings},
        'plan': plan, 'requests': reports,
    }
    (output / 'periodic-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('requests', 'plan')}, indent=2))
    assert differ == 0 and summary['all_bodies_equal_tested_builder'] and summary['all_frames_equal_written_fields'], 'periodic run failed'


if __name__ == '__main__':
    main()
