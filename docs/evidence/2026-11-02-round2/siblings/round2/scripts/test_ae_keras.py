#!/usr/bin/env python3
"""Call the shipped AEFoam python_module.py outside OpenFOAM with the TensorFlow installed in pydeps/tf:
does autoencoder_func raise, and what does encode_func return afterwards? Usage: test_ae_keras.py MODULE_DIR"""
import sys, traceback
import numpy as np
sys.path.insert(0, sys.argv[1])
import tensorflow as tf, keras
print('tensorflow', tf.__version__, 'keras', keras.__version__, 'numpy', np.__version__, flush=True)
import python_module as m
rng = np.random.default_rng(0)
N = 200
for i in range(30):
    m.snapshot_func(rng.random((N, 1)), 0)
print('snapshots', None if m.snapshots is None else m.snapshots.shape, flush=True)
print('--- autoencoder_func(0)', flush=True)
try:
    print('returned', m.autoencoder_func(0), flush=True)
except Exception:
    traceback.print_exc()
    print('AUTOENCODER_FUNC RAISED', flush=True)
print('--- encode_func(array, 0)', flush=True)
try:
    r = m.encode_func(rng.random((N, 1)), 0)
    print('returned type', type(r), 'shape', getattr(r, 'shape', None), 'dtype', getattr(r, 'dtype', None), flush=True)
except Exception:
    traceback.print_exc()
    print('ENCODE_FUNC RAISED', flush=True)
print('has encoder attr:', hasattr(m.autoencoder_class_object, 'encoder'), flush=True)
