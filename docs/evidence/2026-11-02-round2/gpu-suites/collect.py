"""Records of the r2 GPU suites, as docs/evidence/2026-10-30-versions/gpu-suite-<job>/ keeps them, plus a comparison with
job 24950817 (v2212, 1000 steps): model statuses, trend words, scores, frame hashes, timings. Usage: collect.py JOB VER MODE ..."""
import gzip, json, shutil, subprocess, sys
from pathlib import Path
R = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/gpu-suites')
E = Path('/cluster/medbow/gscratch/syome/github_repos/PythonFOAM/docs/evidence/2026-10-30-versions/gpu-suite-24950817')
base = json.loads((E/'async-verification.json').read_text())
CASES = ['async-no-llm', 'async-describe', 'async-sequence', 'async-server-error', 'async-timeout']
def frames(v, case):
    return {f['step']: f.get('fields_sha256') for f in v[case].get('frames', [])}
out = {'baseline_24950817': {'status': base['status'], 'frames_no_llm': frames(base, 'async-no-llm')}}
for job, ver, mode in zip(sys.argv[1::3], sys.argv[2::3], sys.argv[3::3]):
    run = R/'pod-async-v2'/f'run-{job}'
    rec = R/'records'/f'gpu-suite-{job}-{ver}-{mode}'; rec.mkdir(exist_ok=True)
    row = {'job': job, 'version': ver, 'mode': mode, 'run_dir': str(run)}
    out[job] = row
    demos = sorted(run.glob('pod-llm-async.*'))
    row['suite_log_lines'] = (run/'suite.log').read_text().splitlines()[-3:] if (run/'suite.log').exists() else None
    slurm = sorted(R.glob(f'slurm/pod-async-v2-{ver}-{mode}-{job}.out'))
    if slurm:
        shutil.copy2(slurm[0], rec/'job.out')
        row['job_out_tail'] = slurm[0].read_text().splitlines()[-3:]
    for f in ('HEAD', 'git-status.txt'):
        if (run/'git'/f).exists(): shutil.copy2(run/'git'/f, rec/f)
    row['HEAD'] = (run/'git/HEAD').read_text().strip() if (run/'git/HEAD').exists() else None
    row['git_status_clean'] = (run/'git/git-status.txt').read_text().strip() == '' if (run/'git/git-status.txt').exists() else None
    for f in ('site.txt', 'nvidia-smi.txt'):
        if (run/f).exists(): shutil.copy2(run/f, rec/f)
    for c in sorted((run/'server').glob('server-*.cmd')): shutil.copy2(c, rec/'server.cmd')
    for g in sorted((run/'server').glob('gpu-*.txt')): row['gpu'] = g.read_text().strip().splitlines()[-1]
    if (run/'suite.log').exists():
        with open(run/'suite.log', 'rb') as f, gzip.open(rec/'suite.log.gz', 'wb') as z: shutil.copyfileobj(f, z)
    sacct = subprocess.run(['sacct', '-j', job, '-X', '-n', '-P', '-o', 'JobID,State,Elapsed,NodeList,Start,End,ExitCode'], capture_output=True, text=True).stdout.strip()
    row['sacct'] = sacct; (rec/'sacct.txt').write_text(sacct+'\n')
    if not demos:
        row['verification'] = 'no demo directory'; continue
    demo = demos[-1]; row['demo_dir'] = str(demo)
    for f in ('summary.json', 'async-verification.json', 'async-settings.json'):
        if (demo/f).exists(): shutil.copy2(demo/f, rec/f)
    if not (demo/'async-verification.json').exists():
        row['verification'] = 'missing'; continue
    v = json.loads((demo/'async-verification.json').read_text())
    row['verification_status'] = v.get('status')
    row['settings'] = {k: v['settings'].get(k) for k in ('steps', 'request_step', 'sequence_steps', 'start_dir', 'model')}
    row['start_files_sha256_equal_24950817'] = v['settings'].get('start_files_sha256') == base['settings'].get('start_files_sha256')
    row['timings_s'] = {k: round(t, 1) for k, t in v['timings'].items()}
    row['cases'] = {}
    for c in CASES:
        d = v.get(c, {})
        r = {'exit_status': v['resources'].get(c, {}).get('exit_status'), 'model_status': d.get('model_status'),
             'request_step': d.get('request_step'), 'arrived_at_step': d.get('arrived_at_step'),
             'answer_arrived_before_end': d.get('answer_arrived_before_end'), 'solver_stall_s': d.get('solver_stall_s'),
             'inference_wall_s': d.get('inference_wall_s'), 'max_courant': d.get('max_courant'),
             'files_identical_to_no_request_baseline': d.get('files_identical_to_no_request_baseline')}
        so = d.get('structured_output') or {}
        sc = d.get('score') or {}
        if c == 'async-sequence' and so:
            r['trend_words'] = {k: so.get(k) for k in ('max_speed_trend', 'min_pressure_trend', 'fastest_flow_region')}
            r['truth'] = {k: sc.get('truth', {}).get(k) for k in ('max_speed_trend', 'min_pressure_trend', 'fastest_flow_region')}
            r['matches'] = sc.get('scores', {}).get('matches')
        if c == 'async-describe' and so:
            r['answer_percent'] = {k: [so.get(f'{k}_x_percent'), so.get(f'{k}_y_percent')] for k in ('fastest_flow', 'lowest_pressure')}
            r['distance_percent'] = {k: round(sc['scores'][k]['distance_percent'], 1) for k in sc.get('scores', {})}
            r['within_10_percent'] = {k: sc['scores'][k]['within_10_percent'] for k in sc.get('scores', {})}
        row['cases'][c] = r
    fr = frames(v, 'async-no-llm'); row['frames_no_llm_fields_sha256'] = fr
    b = out['baseline_24950817']['frames_no_llm']
    row['frames_equal_24950817'] = {str(s): fr.get(s) == b.get(s) for s in sorted(set(fr) | set(b))} if row['settings']['steps'] == 1000 else 'different step set'
(R/'records'/'comparison.json').write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps(out, indent=1))
