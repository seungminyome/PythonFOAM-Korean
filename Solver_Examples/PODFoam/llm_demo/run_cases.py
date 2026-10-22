"""Run the five demo cases against the running llama-server; record timings and memory.

Cases (all 10 steps of the fixed POD case, observation at LLM_ANALYSIS_STEP):
  fixed-pod-no-llm        image rendered, request disabled (baseline fields)
  fixed-pod               numeric summary + same-step PNG to the real model
  fixed-pod-text-only     numeric summary only to the real model (same step)
  fixed-pod-server-error  image path, connection refused
  fixed-pod-timeout       image path, trickling HTTP fixture, callback deadline
"""
from pathlib import Path
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

CALLBACK_FILES = ('python_module.py', 'llm_client.py', 'pod_image.py', 'bounded_ipc.py',
                  'readable_image.py', 'readable_request.py')


def memory(pid):
    """RSS and PSS of one process from /proc."""
    try:
        status = {}
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in ('VmRSS', 'VmHWM', 'PPid'): status[key] = int(value.split()[0])
        pss = None
        try:
            for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
                if line.startswith('Pss:'): pss = int(line.split()[1])
        except (OSError, ValueError): pass
        return {'pid': pid, 'rss_kib': status.get('VmRSS'), 'hwm_kib': status.get('VmHWM'),
                'pss_kib': pss, 'parent_pid': status.get('PPid')}
    except (OSError, ValueError): return None


def descendants(pid):
    result = [pid]
    for parent in result:
        try:
            children = Path(f'/proc/{parent}/task/{parent}/children').read_text().split()
            result.extend(int(child) for child in children if int(child) not in result)
        except OSError: pass
    return result


class Trickle(http.server.BaseHTTPRequestHandler):
    """Sends one byte every 50 ms; only the callback deadline ends the request."""
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self.server.received.append({'monotonic_s': time.monotonic(), 'event': 'request_received'})
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', '10000')
        self.end_headers()
        try:
            while not self.server.stop_event.is_set():
                self.wfile.write(b' ')
                self.wfile.flush()
                self.server.byte_count += 1
                self.server.stop_event.wait(.05)
        except (BrokenPipeError, ConnectionResetError): pass
    def log_message(self, *args): pass


def resident_server(endpoint, runtime):
    """Check that the server behind endpoint is the one recorded in server.pid.

    server.pid is in POD_LLM_STATE when that is set (hpc/start_server.sh), else in runtime.
    """
    base = endpoint.split('/v1/', 1)[0]
    with urllib.request.urlopen(base + '/health', timeout=5) as response: assert response.status == 200
    with urllib.request.urlopen(base + '/v1/models', timeout=5) as response:
        models = [m['id'] for m in json.load(response)['data']]
    pid = int((Path(os.environ.get('POD_LLM_STATE') or runtime)/'server.pid').read_text())
    cmdline = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    assert b'llama-server' in cmdline[0], cmdline[0]
    assert ('--port').encode() in cmdline and base.rsplit(':', 1)[1].encode() in cmdline, (base, pid)
    return {'pid': pid, 'models': models, 'cmdline': [c.decode() for c in cmdline if c],
            'mmproj_loaded': b'--mmproj' in cmdline and b'--no-mmproj' not in cmdline}


def main():
    source, reference, output, executable = map(Path, sys.argv[1:])
    endpoint = os.environ['LLM_ENDPOINT']
    runtime = Path(os.environ.get('POD_LLM_RUNTIME', source.parents[2]/'llm-runtime'))
    server = resident_server(endpoint, runtime)
    server_pid = server['pid']
    assert os.environ.get('LLM_MODEL') in server['models'], (os.environ.get('LLM_MODEL'), server['models'])
    assert memory(server_pid), 'Run harness in same host process namespace as llama-server'
    (output/'resident-server.json').write_text(json.dumps(server, indent=2)+'\n')
    output.joinpath('fixed-pimple').symlink_to(reference/'fixed-pimple', target_is_directory=True)
    timings = {}
    frozen = output/'executed-callback-source'
    frozen.mkdir()
    for filename in CALLBACK_FILES:
        shutil.copy2(source/'llm_demo'/filename, frozen/filename)
    shutil.copy2(source/'validation/python_module.py', frozen/'pod_svd.py')
    step = os.environ.get('LLM_ANALYSIS_STEP', '5')
    cases = [('fixed-pod-no-llm', '0', '1'), ('fixed-pod', '1', '1'), ('fixed-pod-text-only', '1', '0'),
             ('fixed-pod-server-error', '1', '1'), ('fixed-pod-timeout', '1', '1')]
    for name, enabled, image in cases:
        case = output/name
        for directory in ('0', 'constant', 'system'):
            shutil.copytree(reference/'fixed-pod'/directory, case/directory)
        shutil.copy2(frozen/'pod_svd.py', case/'pod_svd.py')
        for filename in CALLBACK_FILES:
            shutil.copy2(frozen/filename, case/filename)
        # observe mode, so always the v1 picture (LLM_IMAGE_STYLE=v2 would be refused)
        env = dict(os.environ, LLM_ENABLED=enabled, LLM_IMAGE_INPUT=image, LLM_ANALYSIS_STEP=step,
                   LLM_IMAGE_STYLE='v1', LLM_RUN_ID=f'{output.name}/{name}',
                   MPLCONFIGDIR=str(case/'mpl-cache'))
        trickle = None
        if name == 'fixed-pod-server-error':
            env.update(LLM_ENDPOINT='http://127.0.0.1:1/v1/chat/completions',
                       LLM_CALLBACK_DEADLINE_S='4', LLM_CONNECT_TIMEOUT_S='0.5', LLM_READ_TIMEOUT_S='0.3')
        if name == 'fixed-pod-timeout':
            trickle = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Trickle)
            trickle.daemon_threads = True
            trickle.stop_event = threading.Event()
            trickle.received = []
            trickle.byte_count = 0
            threading.Thread(target=trickle.serve_forever, daemon=True).start()
            env.update(LLM_ENDPOINT=f'http://127.0.0.1:{trickle.server_port}/v1/chat/completions',
                       LLM_CALLBACK_DEADLINE_S='4', LLM_CONNECT_TIMEOUT_S='0.5', LLM_READ_TIMEOUT_S='0.3')
        start = time.monotonic()
        deadline = float(env.get('LLM_CALLBACK_DEADLINE_S', env.get('LLM_TIMEOUT_S', '120'))) + 90
        events, samples = [], []
        with (case/'log.PODFoam').open('w') as log:
            process = subprocess.Popen([str(executable), '-case', str(case)], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            def read_log():
                for line in process.stdout:
                    log.write(line)
                    if line.startswith(('Time =', 'PYTHON LLM', 'POD SVD returned', 'POD analysis callback returned',
                                        'POD mesh geometry', 'Python finalized', 'End')):
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
                time.sleep(.1)
            reader.join(timeout=5)
        wall = time.monotonic()-start
        if trickle:
            trickle.stop_event.set()
            trickle.shutdown()
            trickle.server_close()
            (case/'timeout-fixture.json').write_text(json.dumps({
                'requests': trickle.received, 'bytes_sent': trickle.byte_count,
                'byte_interval_s': .05, 'read_inactivity_timeout_s': .3,
                'callback_deadline_s': 4}, indent=2)+'\n')
        (case/'timeline.json').write_text(json.dumps(events, indent=2)+'\n')
        (case/'memory-samples.json').write_text(json.dumps(samples, indent=2)+'\n')
        def peak(key):
            values = [s[key] for s in samples if s.get(key) is not None]
            return max(values) if values else None
        server_samples = [s['llama_server'] for s in samples if s['llama_server']]
        timings[name] = {'wall_seconds': wall, 'exit_status': process.returncode,
                        'solver_pid': process.pid, 'llama_server_pid': server_pid,
                        'image_input_requested': image == '1', 'model_request_enabled': enabled == '1',
                        'memory_sample_interval_s': .1,
                        'cfd_python_peak_rss_sum_kib': peak('cfd_python_rss_sum_kib'),
                        'cfd_python_peak_pss_sum_kib': peak('cfd_python_pss_sum_kib'),
                        'llama_server_peak_rss_kib': max(s['rss_kib'] or 0 for s in server_samples),
                        'llama_server_peak_pss_kib': max((s['pss_kib'] or 0 for s in server_samples), default=None),
                        'concurrent_samples': sum(bool(s['llama_server'] and s['cfd_python_processes']) for s in samples)}
        (output/'timings.json').write_text(json.dumps(timings, indent=2)+'\n')
        assert process.returncode == 0, (name, process.returncode)
        print(f'{name}: exit={process.returncode} wall={wall:.3f}s', flush=True)
        if name in ('fixed-pod', 'fixed-pod-text-only'):
            result_json = json.loads((case/'llm_result.json').read_text())
            assert result_json.get('status') == 'ok', result_json


if __name__ == '__main__': main()
