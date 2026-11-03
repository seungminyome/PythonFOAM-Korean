#!/usr/bin/env python3
"""From each sibling solver's shipped python_module.py, make two modules:
  module-recording.py   shipped + save the snapshot matrix at the start of the function that consumes it
  module-copy.py        the same + one line at the top of snapshot_func: array = np.array(array, copy=True)
Usage: make_modules.py SOLVER SRC_MODULE OUT_DIR"""
import sys
from pathlib import Path

solver, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
text = src.read_text()


def insert_after_globals(text, def_line, lines):
    """Insert lines after the def line and the global statements that follow it
    (a global statement after a use of the name is a SyntaxError)."""
    i = text.index(def_line) + len(def_line)
    while True:
        nl = text.index('\n', i) + 1
        line = text[i:nl]
        if line.strip() == '' or line.lstrip().startswith('global '):
            i = nl
        else:
            break
    return text[:i] + lines + text[i:]


if solver in ('PODFoam_Debug', 'APMOSFoam'):
    func = 'svd_func(rank)' if solver == 'PODFoam_Debug' else 'apmos_func(placeholder)'
    rank = 'rank' if solver == 'PODFoam_Debug' else 'placeholder'
    marker = f"def {func}:\n"
    assert text.count(marker) == 1, marker
    # insert after the docstring-free def line and its global statements: put it right after the def line
    record = ("    global _snap_count\n    _snap_count += 1\n"
              + f"    np.savez('snapshots-%d-rank%d.npz' % (_snap_count, {rank}), u=u_snapshots, v=v_snapshots, w=w_snapshots)\n")
    recording = insert_after_globals(text, marker, record)
    init = "iter = 0\nu_snapshots = None"
    assert recording.count(init) == 1
    recording = recording.replace(init, "_snap_count = 0\n" + init, 1)
elif solver == 'AEFoam':
    marker = "def autoencoder_func(rank):\n"
    assert text.count(marker) == 1
    record = ("    global _snap_count\n    _snap_count += 1\n"
              + "    np.savez('snapshots-%d-rank%d.npz' % (_snap_count, rank), s=snapshots)\n")
    recording = insert_after_globals(text, marker, record)
    init = "iter = 0\nsnapshots = None"
    assert recording.count(init) == 1
    recording = recording.replace(init, "_snap_count = 0\n" + init, 1)
else:
    sys.exit(f'unknown solver {solver}')

# the globals statement in the consumer must follow the inserted lines: Python requires global before use,
# but the inserted lines use only _snap_count (declared) and module globals read-only, so order is fine.
out.mkdir(parents=True, exist_ok=True)
(out / 'module-recording.py').write_text(recording)

snap = "def snapshot_func(array,rank):\n"
assert recording.count(snap) == 1
copy = recording.replace(snap, snap + "    array = np.array(array, copy=True)\n", 1)
(out / 'module-copy.py').write_text(copy)
print('wrote', out / 'module-recording.py', out / 'module-copy.py')
