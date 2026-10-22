"""Pack one demo run (sources, run records, model request and response) into a tarball; no weights."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile

out = Path(sys.argv[1]).resolve()
source = Path(__file__).resolve().parent.parent
repo = source.parents[1]
workspace = Path(os.environ.get('POD_WORKSPACE', repo.parent))
runtime = Path(os.environ.get('POD_LLM_RUNTIME', workspace/'llm-runtime'))


def save(name, value):
    (out/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


(out/'sources').mkdir(exist_ok=True)
(out/'runtime').mkdir(exist_ok=True)
for path in [source/'PODFoam.C', *source.glob('*.H')]:
    shutil.copy2(path, out/'sources'/path.name)
for directory in ('llm_demo', 'validation', 'Make'):
    shutil.copytree(source/directory, out/'sources'/directory, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'linux64*'))
for name in ('runtime_manifest.json', 'runtime_manifest_12b.json', 'startup.json', 'standalone.json',
             'standalone-request.json'):
    if (runtime/name).exists():
        shutil.copy2(runtime/name, out/'runtime'/name)
# hpc/start_server.sh keeps the command line, log, model list and GPU record per server start
state = Path(os.environ['POD_LLM_STATE']) if os.environ.get('POD_LLM_STATE') else None
if state and state.is_dir():
    for pattern in ('server-*.cmd', 'server-*.log', 'models-*.json', 'gpu-*.txt'):
        for path in state.glob(pattern):
            shutil.copy2(path, out/'runtime'/path.name)
startup = json.loads((runtime/'startup.json').read_text()) if (runtime/'startup.json').exists() else {}
if startup.get('server_log') and Path(startup['server_log']).exists():
    shutil.copy2(startup['server_log'], out/'runtime/server.log')

git = ['git', '-C', str(repo)]
git_error = None
try:
    (out/'HEAD').write_bytes(subprocess.check_output([*git, 'rev-parse', 'HEAD']))
    (out/'git-status.txt').write_bytes(subprocess.check_output([*git, 'status', '--short']))
    (out/'changes.patch').write_bytes(subprocess.check_output([*git, 'diff', '--binary']))
except (subprocess.CalledProcessError, FileNotFoundError) as error:
    # no git inside an OpenFOAM image: use what the job recorded on the host (POD_GIT_RECORDS)
    records = Path(os.environ['POD_GIT_RECORDS']) if os.environ.get('POD_GIT_RECORDS') else None
    if records and (records/'HEAD').exists():
        for name in ('HEAD', 'git-status.txt', 'changes.patch', 'untracked.tar.gz'):
            if (records/name).exists():
                shutil.copy2(records/name, out/name)
    else:
        git_error = repr(error)
        print(f'pack_run: no git records ({git_error})', file=sys.stderr)

build_root = workspace/'llm-demo-work/build'
binary = workspace/'llm-demo-work/bin/PODFoam'
compiled = {p.name: sha256(p) for p in [build_root/'PODFoam.C', *build_root.glob('*.H')]}
for name, digest in compiled.items():
    assert sha256(source/name) == digest, f'{name} in the build directory differs from the source tree'
save('build-inputs.json', {'source_sha256': compiled, 'binary_path': str(binary),
                           'binary_sha256': sha256(binary),
                           'version': f"OpenFOAM {os.environ.get('WM_PROJECT_VERSION', 'v2106')}"})

server = json.loads((out/'resident-server.json').read_text())
if (out/'async-verification.json').exists():
    verification = json.loads((out/'async-verification.json').read_text())
    save('summary.json', {
        'status': verification['status'], 'suite': 'async',
        'server_pid': server['pid'], 'mmproj_loaded': server['mmproj_loaded'],
        'settings': verification['settings'],
        'timings': verification['timings'],
        'cases': {name: {k: verification[name][k] for k in (
            'request_step', 'arrived_at_step', 'answer_arrived_before_end', 'end_wait_s',
            'model_status', 'callback_wall_s', 'solver_stall_s', 'inference_wall_s', 'structured_output')}
                  for name in verification if name.startswith('async-')},
        'source_HEAD': (out/'HEAD').read_text().strip() if (out/'HEAD').exists() else None,
        'source_HEAD_error': git_error,
    })
else:
  verification = json.loads((out/'demo-verification.json').read_text())
  save('summary.json', {
    'status': verification['status'],
    'model': verification['model'],
    'server_pid': server['pid'], 'mmproj_loaded': server['mmproj_loaded'],
    'steps': 10, 'analysis_step': 5, 'analysis_time_s': 5e-7,
    'timings': verification['timings'],
    'structured_output': {k: verification['input_comparison'][k]['structured_output']
                          for k in ('image', 'text_only')},
    'source_HEAD': (out/'HEAD').read_text().strip() if (out/'HEAD').exists() else None,
    'files': {'request': 'fixed-pod/llm_request.json', 'request_body': 'fixed-pod/llm_request_body.json',
              'image': 'fixed-pod/llm_observation/state.png', 'response': 'fixed-pod/llm_response.json',
              'raw_http_body': 'fixed-pod/llm_http_response.raw',
              'text_only_request': 'fixed-pod-text-only/llm_request.json',
              'text_only_response': 'fixed-pod-text-only/llm_response.json'},
})

# Keep the archive small: skip the reference symlink, intermediate time directories and caches.
selected = []
for path in out.rglob('*'):
    relative = path.relative_to(out)
    if path.is_symlink() or not path.is_file():
        continue
    if '__pycache__' in relative.parts or path.name in ('run-archive.tar.gz', 'sha256.json'):
        continue
    if path.suffix in ('.gguf', '.safetensors'):
        raise RuntimeError(f'Model weights found in the run directory: {path}')
    if len(relative.parts) >= 3 and relative.parts[0].startswith('fixed-pod'):
        if relative.parts[1] == 'mpl-cache':
            continue
        if relative.parts[1] not in ('0', 'constant', 'system', '1e-06', '5e-07', 'llm_observation'):
            continue
    if len(relative.parts) >= 3 and relative.parts[0].startswith('async-'):
        if relative.parts[1] == 'mpl-cache':
            continue
    selected.append(path)
save('sha256.json', {str(p.relative_to(out)): sha256(p) for p in selected})
with tarfile.open(out/'run-archive.tar.gz', 'w:gz', dereference=False) as archive:
    for path in selected + [out/'sha256.json']:
        archive.add(path, arcname=str(Path(out.name)/path.relative_to(out)), recursive=False)
print(f'Archive (no weights): {out}/run-archive.tar.gz')
