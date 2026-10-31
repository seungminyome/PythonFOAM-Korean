#!/usr/bin/env python3
"""The numbers of docs/results-20261030.md (versions, upstream comparison), read from the records in this folder.

Usage: report_numbers.py    writes report-numbers.json next to this script and prints it. Standard library only.
"""
import gzip
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSIONS = ('v2012', 'v2106', 'v2212', '8')
MATRIX = {'v2012': 'v2012-24950780', 'v2106': 'v2106-24950781', 'v2212': 'v2212-24950782', '8': '8-24950783'}
STANDIN = {'v2012': 'v2012-24950794', 'v2106': 'v2106-24950795', 'v2212': 'v2212-24950796', '8': '8-24950797'}
DOC = {'v2012': 'v2012-24950840', 'v2106': 'v2106-24950841', 'v2212': 'v2212-24950842', '8': '8-24950843'}


def load(rel):
    return json.loads((HERE/rel).read_text())


def text(rel):
    return (HERE/rel).read_text(errors='replace')


def versions():
    compare = load('version-compare.json')['versions']
    frames = load('frame-hashes.json')['frames']
    out = {}
    for v in VERSIONS:
        s = compare[v]
        out[v] = {
            'HEAD': s['HEAD'][:7], 'node': s['node'], 'validation_pass': s['validation_pass'],
            'cases_exit_0_End_finalized': sum(c['exit'] == '0' and c['end'] and c['python_finalized'] and not c['fatal'] for c in s['cases'].values()),
            'telemetry_lines': sorted({c['telemetry_lines'] for c in s['cases'].values()}),
            'callback_errors': sum(c['callback_errors'] for c in s['cases'].values()),
            'mesh_cells': {k: c['mesh_cells'] for k, c in s['cases'].items()},
            'p_iterations_per_solve': {k: round(c['p_iterations_per_solve'], 2) for k, c in s['cases'].items()},
            'serial_vs_2_ranks': {k: {'cells': d['cells'], 'max_dU': float(f"{d['U_max']:.3g}"), 'peak_U': float(f"{d['U_peak']:.3g}"),
                                      'max_dp': float(f"{d['p_max']:.3g}"), 'p_range': float(f"{d['p_range']:.3g}")}
                                  for k, d in s['serial_vs_parallel'].items()},
        }
        if s['against_v2212']:
            out[v]['against_v2212'] = {k: {'max_dU': float(f"{d['U_max']:.3g}"), 'rms_dU': float(f"{d['U_rms']:.3g}"), 'peak_U': float(f"{d['U_peak']:.3g}"),
                                           'max_dp': float(f"{d['p_max']:.3g}"), 'rms_dp': float(f"{d['p_rms']:.3g}"), 'p_range': float(f"{d['p_range']:.3g}")}
                                       for k, d in s['against_v2212'].items()}
        out[v]['frame_files_equal_to_v2212'] = sum(frames[MATRIX[v]][c][f] == frames[MATRIX['v2212']][c][f]
                                                   for c in frames[MATRIX[v]] for f in frames[MATRIX[v]][c])
        out[v]['frame_files'] = sum(len(frames[MATRIX[v]][c]) for c in frames[MATRIX[v]])
        run = STANDIN[v]
        job = text(f'stand-in/{run}/job.out')
        out[v]['stand_in'] = {'HEAD': text(f'stand-in/{run}/HEAD').strip()[:7],
                              'suites': {m[1]: m[2] for m in re.finditer(r'^(validation|sync|async-v1|async-v2) exit (\d+): PASS', job, re.M)}}
        doc = text(f'documented-commands/{DOC[v]}.out')
        out[v]['documented_commands'] = {'written_files': re.search(r'written files equal to fixed-pod: (\d+ of \d+)', doc)[1], 'pass': 'DOC COMMANDS PASS' in doc}
        for commit in (2, 3):
            found = sorted((HERE/'commits').glob(f'refix-commit-{commit}-{v}-*.log'))
            log = found[0].read_text(errors='replace')
            out[v][f'commit_{commit}'] = {'job': found[0].stem.rsplit('-', 1)[1], 'code': re.search(r'code \S+ (\w+) ', log)[1], 'pass': bool(re.search(r'^PASS', log, re.M))}
    earlier = load('version-compare.json')['v2212_against_earlier_frames']
    return {'versions': out, 'v2212_against_earlier_frames_bytes': {k: x['bytes_identical'] for k, x in earlier.items()}}


def requests():
    out = {}
    for job, gpu in ((24950818, 'A30'), (24949167, 'L40S')):
        d = load(f'gpu-versions-{job}/part-a.json')
        out[job] = {'gpu': gpu, 'HEAD': text(f'gpu-versions-{job}/HEAD').strip()[:7], 'versions': {}}
        for v in VERSIONS:
            x = d[v]
            out[job]['versions'][v] = {
                'status': x['status'], 'http': x['http_status'], 'exit': x['exit_status'], 'request_step': x['request_step'], 'arrived_at_step': x['arrived_at_step'],
                'model_s': round(x['inference_wall_s'], 2), 'solver_stall_s': round(x['solver_stall_s'], 3),
                'body_equals_builder': x['body_equals_builder'], 'images_equal_frame': x['body_images_equal_frame'],
                'same_fields_as_no_model_run': x.get('same_fields_as_no_model_run'),
                'fastest_flow': {'distance_percent': round(x['score']['fastest_flow']['distance_percent'], 1), 'within_10': x['score']['fastest_flow']['within_10_percent']},
                'lowest_pressure': {'distance_percent': round(x['score']['lowest_pressure']['distance_percent'], 1), 'within_10': x['score']['lowest_pressure']['within_10_percent']},
            }
    return out


def suites():
    out = {}
    for job, gpu in ((24950817, 'A30'), (24949283, 'L40S')):
        s, v = load(f'gpu-suite-{job}/summary.json'), load(f'gpu-suite-{job}/async-verification.json')
        out[job] = {'gpu': gpu, 'HEAD': s['source_HEAD'][:7], 'status': [s['status'], v['status']], 'steps': s['settings']['steps'], 'model': s['settings']['model'],
                    'written_files_equal_to_baseline': {k: v[k]['files_identical_to_no_request_baseline'] for k in v if k.startswith('async-')},
                    'cases': {c: {'status': x['model_status'], 'request_step': x['request_step'], 'arrived_at_step': x['arrived_at_step'],
                                  'model_s': x['inference_wall_s'] if x['inference_wall_s'] is None else round(x['inference_wall_s'], 2),
                                  'solver_stall_s': round(x['solver_stall_s'], 3)} for c, x in s['cases'].items()},
                    'describe_within_10': {k: x['within_10_percent'] for k, x in v['async-describe']['score']['scores'].items()},
                    'sequence_words': {k: x['match'] for k, x in v['async-sequence']['score']['scores'].items() if isinstance(x, dict)}}
    q = 'quick-start-24950804'
    sync, asyn = load(f'{q}/sync/summary.json'), load(f'{q}/async/summary.json')
    va = load(f'{q}/async/async-verification.json')
    vs = load(f'{q}/sync/demo-verification.json')
    out['quick_start_24950804'] = {
        'steps_tsv': [line.split('\t')[:3] for line in text(f'{q}/steps.tsv').splitlines()],
        'sync': {'status': [sync['status'], vs['status']], 'model': sync['model'], 'steps': sync['steps'],
                 'cases': {k: vs[k]['model_status'] for k in vs if k.startswith('fixed-')},
                 'written_files_equal': {k: vs[k]['files_identical_to_no_request_baseline'] for k in vs if k.startswith('fixed-')}},
        'async': {'status': [asyn['status'], va['status']], 'model': asyn['settings']['model'], 'steps': asyn['settings']['steps'], 'style': asyn['settings']['image_style'],
                  'cases': {c: x['model_status'] for c, x in asyn['cases'].items()},
                  'written_files_equal': {k: va[k]['files_identical_to_no_request_baseline'] for k in va if k.startswith('async-')}},
    }
    docker = text('docker-24950798/job.out')
    out['docker_24950798'] = {'code': docker.splitlines()[0][:7], 'python': docker.splitlines()[1], 'validation': bool(re.search(r'^PASS', text('docker-24950798/validation.log'), re.M)),
                              'wmake_exit': re.search(r'wmake exit (\d+)', docker)[1], 'shipped_run_steps_in_120_s': re.search(r'PDE Compute wall time: (\d+)', docker)[1],
                              'exit': re.search(r'PODFoam exit (\d+)', docker)[1]}
    return out


def comparison():
    out = {}
    for folder in sorted((HERE/'upstream-comparison').iterdir()):
        if (folder/'account.json').exists():
            a = load(f'upstream-comparison/{folder.name}/account.json')
            row = {'HEAD': a['HEAD'][:7], 'upstream': a['upstream'][:7], 'runs': {k: {'exit': r['exit'], 'steps': r['steps'], 'written': len(r['written'])} for k, r in a['runs'].items()}}
            for key in [k for k in a if k.startswith('upstream_vs_')]:
                rows = a[key]
                row[key] = {'modes': sum(r['pod_modes'] for r in rows), 'modes_identical': sum(r['pod_values_identical'] for r in rows),
                            **{f: f"{sum(r[f]['identical_bytes'] for r in rows)} of {len(rows)} times byte-identical" for f in ('U', 'p', 'phi')}}
                diffs = [r for r in rows if not r['U']['identical_bytes']]
                if diffs:
                    row[key]['sizes'] = {r['time']: {'U': float(f"{r['U']['max_abs_diff']:.3g}"), 'U_of': float(f"{r['U']['max_abs_value']:.3g}"),
                                                     'p': float(f"{r['p']['max_abs_diff']:.3g}"), 'p_of': float(f"{r['p']['max_abs_value']:.4g}")} for r in (diffs[0], diffs[-1])}
            snaps = a['snapshots_upstream_vs_fork']
            row['snapshot_matrices'] = len(snaps)
            row['upstream_first_two_columns_equal'] = sum(r[k]['upstream_col0_equals_col1'] for r in snaps for k in 'uvw')
            row['fork_first_two_columns_equal'] = sum(r[k]['fork_col0_equals_col1'] for r in snaps for k in 'uvw')
            out[folder.name] = row
        elif (folder/'regression.json').exists():
            r = load(f'upstream-comparison/{folder.name}/regression.json')
            logs = {}
            for c in ('case-upstream', 'case-fork'):
                with gzip.open(folder/f'{c}.log.PODFoam.gz', 'rt', errors='replace') as f:
                    t = f.read()
                logs[c] = {'sigfpe': 'sigFpe' in t, 'nan_read': "found on line 0: word 'nan'" in t}
            out[folder.name] = {'HEAD': (folder/'HEAD').read_text().strip()[:7], 'exit': r['exit'], 'steps': r['steps'], 'logs': logs}
    return out


def schedule():
    out = {}
    for folder in sorted((HERE/'schedule').glob('*-*-*')):
        if not folder.is_dir():
            continue
        d = load(f'schedule/{folder.name}/schedule.json')
        rows = [{k: r.get(k) for k in ('module', 'analysis', 'ranks', 'writeInterval', 'podSvdInterval', 'exit', 'schedule', 'modes')} for r in d if r['build'] == 'fork']
        out[folder.name] = {'fork_runs': len(rows), 'fork_runs_with_problems': sum(bool(r['problems']) for r in d if r['build'] == 'fork'),
                            'fork_rows': rows,
                            'upstream_build': [{k: r.get(k) for k in ('module', 'writeInterval', 'steps', 'exit', 'python_collect')} for r in d if r['build'] == 'upstream']}
    return out


report = {'versions': versions(), 'requests': requests(), 'suites': suites(), 'upstream_comparison': comparison(), 'schedule': schedule()}
(HERE/'report-numbers.json').write_text(json.dumps(report, indent=1)+'\n')
print(json.dumps(report, indent=1))
