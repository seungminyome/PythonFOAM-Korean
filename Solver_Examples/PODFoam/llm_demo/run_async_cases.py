"""Run the asynchronous cases on a longer PODFoam run; record timings and memory.

Cases (LLM_ASYNC=1, LLM_LONG_STEPS steps of LLM_LONG_DT, written every
LLM_LONG_WRITE steps; request at LLM_LONG_STEP, sequence frames at
LLM_LONG_SEQUENCE_STEPS; LLM_LONG_START=<time directory of an earlier run of
the same mesh> starts every case from that state instead of t = 0, and step
numbers then count from it; the refused and stalled cases get a callback
deadline of LLM_LONG_FIXTURE_DEADLINE_S, default 4 s):
  async-no-llm         sequence mode, frames rendered, request disabled (baseline fields and frames)
  async-describe       one image to the real model; the solver keeps stepping
  async-sequence       frames captured along the run, sent together at the last one
  async-server-error   connection refused, detected by polling
  async-timeout        trickling HTTP fixture, killed at the deadline by polling
"""
from pathlib import Path
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

from run_cases import CALLBACK_FILES, Trickle, descendants, memory, resident_server

STEPS = int(os.environ.get('LLM_LONG_STEPS', '3000'))
DT = os.environ.get('LLM_LONG_DT', '5e-7')
WRITE_EVERY = int(os.environ.get('LLM_LONG_WRITE', '250'))
REQUEST_STEP = os.environ.get('LLM_LONG_STEP', '250')
SEQUENCE_STEPS = os.environ.get('LLM_LONG_SEQUENCE_STEPS', '250,750,1250')
START = Path(os.environ['LLM_LONG_START']).resolve() if os.environ.get('LLM_LONG_START') else None
T0 = float(START.name) if START else 0.0
FIXTURE_DEADLINE_S = os.environ.get('LLM_LONG_FIXTURE_DEADLINE_S', '4')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def start_files():
    """The fields of the start state (U, p, phi, ...); uniform/ is left out, so the time
    index restarts and the writes land at whole multiples of LLM_LONG_WRITE steps."""
    return sorted(path for path in START.iterdir() if path.is_file())


def stage_case(reference, case):
    for directory in ('0', 'constant', 'system'):
        shutil.copytree(reference/'fixed-pod'/directory, case/directory)
    (case/'0/uniform/time').unlink(missing_ok=True)
    control = (case/'system/controlDict').read_text()
    if START:
        for name in ('boundary', 'faces', 'neighbour', 'owner', 'points'):
            assert sha256(START.parent/'constant/polyMesh'/name) == sha256(case/'constant/polyMesh'/name), \
                f'{START} is not on the mesh of the reference case ({name})'
        (case/START.name).mkdir()
        for path in start_files():
            shutil.copy2(path, case/START.name/path.name)
        control = re.sub(r'^startFrom .*$', 'startFrom startTime;', control, flags=re.M)
        control = re.sub(r'^startTime .*$', f'startTime {START.name};', control, flags=re.M)
    end = T0 + float(DT) * STEPS
    control = re.sub(r'^endTime .*$', f'endTime {end:.12g};', control, flags=re.M)
    control = re.sub(r'^deltaT .*$', f'deltaT {DT};', control, flags=re.M)
    control = re.sub(r'^writeInterval .*$', f'writeInterval {WRITE_EVERY};', control, flags=re.M)
    # SVD (and the 15 mode fields it writes) only at output times, not every 10 steps
    control = re.sub(r'^podSvdInterval .*$', 'podSvdInterval 0;', control, flags=re.M)
    (case/'system/controlDict').write_text(control)


def main():
    if len(sys.argv) != 5:
        sys.exit(f'usage: {sys.argv[0]} POD_SOURCE_DIRECTORY REFERENCE_RUN OUTPUT_DIRECTORY PODFOAM')
    source, reference, output, executable = map(Path, sys.argv[1:])
    endpoint = os.environ['LLM_ENDPOINT']
    # server.pid is read from POD_LLM_STATE when set (run_cases.resident_server)
    runtime = Path(os.environ.get('POD_LLM_RUNTIME', source.parents[2]/'llm-runtime'))
    server = resident_server(endpoint, runtime)
    server_pid = server['pid']
    assert os.environ.get('LLM_MODEL') in server['models'], (os.environ.get('LLM_MODEL'), server['models'])
    (output/'resident-server.json').write_text(json.dumps(server, indent=2)+'\n')
    output.joinpath('fixed-pimple').symlink_to(reference/'fixed-pimple', target_is_directory=True)
    frozen = output/'executed-callback-source'
    frozen.mkdir()
    for filename in CALLBACK_FILES:
        shutil.copy2(source/'llm_demo'/filename, frozen/filename)
    shutil.copy2(source/'validation/python_module.py', frozen/'pod_svd.py')
    settings = {'steps': STEPS, 'delta_t_s': float(DT), 'write_every': WRITE_EVERY,
                'request_step': int(REQUEST_STEP), 'sequence_steps': [int(s) for s in SEQUENCE_STEPS.split(',')],
                'image_x_window': os.environ.get('LLM_IMAGE_XRANGE'), 'image_y_window': os.environ.get('LLM_IMAGE_YRANGE'),
                'deadline_s': os.environ.get('LLM_CALLBACK_DEADLINE_S', os.environ.get('LLM_TIMEOUT_S', '120')),
                'image_style': os.environ.get('LLM_IMAGE_STYLE', 'v1'), 'model': os.environ.get('LLM_MODEL'),
                'max_tokens_env': os.environ.get('LLM_MAX_TOKENS'),
                'fixture_deadline_s': float(FIXTURE_DEADLINE_S), 'start_time_s': T0}
    if START:
        settings.update(start_dir=str(START),
                        start_files_sha256={path.name: sha256(path) for path in start_files()})
    (output/'async-settings.json').write_text(json.dumps(settings, indent=2)+'\n')
    timings = {}
    cases = [('async-no-llm', '0', 'sequence'), ('async-describe', '1', 'describe'),
             ('async-sequence', '1', 'sequence'), ('async-server-error', '1', 'describe'),
             ('async-timeout', '1', 'describe')]
    selected = os.environ.get('LLM_LONG_CASES')
    if selected:
        cases = [case for case in cases if case[0] in selected.split(',')]
    for name, enabled, mode in cases:
        case = output/name
        stage_case(reference, case)
        shutil.copy2(frozen/'pod_svd.py', case/'pod_svd.py')
        for filename in CALLBACK_FILES:
            shutil.copy2(frozen/filename, case/filename)
        env = dict(os.environ, LLM_ENABLED=enabled, LLM_IMAGE_INPUT='1', LLM_ASYNC='1', LLM_MODE=mode,
                   LLM_ANALYSIS_STEP=REQUEST_STEP, LLM_SEQUENCE_STEPS=SEQUENCE_STEPS,
                   LLM_RUN_ID=f'{output.name}/{name}', MPLCONFIGDIR=str(case/'mpl-cache'))
        env.pop('LLM_FINAL_STEP', None)
        trickle = None
        if name == 'async-server-error':
            env.update(LLM_ENDPOINT='http://127.0.0.1:1/v1/chat/completions',
                       LLM_CALLBACK_DEADLINE_S=FIXTURE_DEADLINE_S, LLM_CONNECT_TIMEOUT_S='0.5',
                       LLM_READ_TIMEOUT_S='0.3')
        if name == 'async-timeout':
            trickle = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Trickle)
            trickle.daemon_threads = True
            trickle.stop_event = threading.Event()
            trickle.received = []
            trickle.byte_count = 0
            threading.Thread(target=trickle.serve_forever, daemon=True).start()
            env.update(LLM_ENDPOINT=f'http://127.0.0.1:{trickle.server_port}/v1/chat/completions',
                       LLM_CALLBACK_DEADLINE_S=FIXTURE_DEADLINE_S, LLM_CONNECT_TIMEOUT_S='0.5',
                       LLM_READ_TIMEOUT_S='0.3')
        start = time.monotonic()
        deadline = float(env.get('LLM_CALLBACK_DEADLINE_S', env.get('LLM_TIMEOUT_S', '120'))) + 90 + 0.5*STEPS
        events, samples = [], []
        with (case/'log.PODFoam').open('w') as log:
            process = subprocess.Popen([str(executable), '-case', str(case)], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            def read_log():
                for line in process.stdout:
                    log.write(line)
                    if line.startswith(('PYTHON LLM', 'POD analysis callback returned', 'POD mesh geometry',
                                        'Python finalized', 'End')) or line.startswith('Time = ') and \
                            int((float(line.split()[2]) - T0) / float(DT) + 0.5) % WRITE_EVERY == 0:
                        events.append({'wall_since_start_s': time.monotonic()-start,
                                       'monotonic_s': time.monotonic(), 'line': line.rstrip()})
                log.flush()
            reader = threading.Thread(target=read_log, daemon=True)
            reader.start()
            while process.poll() is None:
                if time.monotonic()-start > deadline:
                    process.kill()
                    raise TimeoutError(f'{name}: outer solver timeout')
                tree = [m for pid in descendants(process.pid) if (m := memory(pid))]
                llama = memory(server_pid)
                samples.append({'wall_since_start_s': time.monotonic()-start,
                                'llama_server': llama, 'cfd_python_processes': tree,
                                'cfd_python_rss_sum_kib': sum(m['rss_kib'] or 0 for m in tree),
                                'cfd_python_pss_sum_kib': (sum(m['pss_kib'] for m in tree)
                                    if tree and all(m['pss_kib'] is not None for m in tree) else None)})
                time.sleep(.5)
            reader.join(timeout=5)
        wall = time.monotonic()-start
        if trickle:
            trickle.stop_event.set()
            trickle.shutdown()
            trickle.server_close()
            (case/'timeout-fixture.json').write_text(json.dumps({
                'requests': trickle.received, 'bytes_sent': trickle.byte_count,
                'byte_interval_s': .05, 'read_inactivity_timeout_s': .3,
                'callback_deadline_s': float(FIXTURE_DEADLINE_S)}, indent=2)+'\n')
        (case/'timeline.json').write_text(json.dumps(events, indent=2)+'\n')
        (case/'memory-samples.json').write_text(json.dumps(samples, indent=2)+'\n')
        def peak(key):
            values = [s[key] for s in samples if s.get(key) is not None]
            return max(values) if values else None
        server_samples = [s['llama_server'] for s in samples if s['llama_server']]
        timings[name] = {'wall_seconds': wall, 'exit_status': process.returncode,
                        'solver_pid': process.pid, 'llama_server_pid': server_pid, 'mode': mode,
                        'model_request_enabled': enabled == '1', 'memory_sample_interval_s': .5,
                        'cfd_python_peak_rss_sum_kib': peak('cfd_python_rss_sum_kib'),
                        'cfd_python_peak_pss_sum_kib': peak('cfd_python_pss_sum_kib'),
                        'llama_server_peak_rss_kib': max((s['rss_kib'] or 0 for s in server_samples), default=None),
                        # PSS of a server outside the container's user namespace cannot be read
                        'llama_server_peak_pss_kib': max((s['pss_kib'] for s in server_samples
                                                          if s['pss_kib'] is not None), default=None),
                        'concurrent_samples': sum(bool(s['llama_server'] and s['cfd_python_processes']) for s in samples)}
        (output/'timings.json').write_text(json.dumps(timings, indent=2)+'\n')
        assert process.returncode == 0, (name, process.returncode)
        print(f'{name}: exit={process.returncode} wall={wall:.3f}s', flush=True)
        if name in ('async-describe', 'async-sequence'):
            result_json = json.loads((case/'llm_result.json').read_text())
            assert result_json.get('status') == 'ok', result_json


if __name__ == '__main__': main()
