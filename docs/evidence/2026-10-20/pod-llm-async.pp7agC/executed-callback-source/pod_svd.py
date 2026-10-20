"""Minimal bridge module: keep ten snapshots, return five SVD modes per component.

Snapshots and modes are also written to python_svd_audit.npz for verify.py.
"""
from pathlib import Path
import numpy as np

_snapshots = []
_case = Path(__file__).resolve().parent


def snapshot_func(array, rank):
    if rank != 0:
        raise ValueError("This validation module requires serial execution")
    values = np.asarray(array)
    if values.ndim != 2 or values.shape[1] != 3 or not np.isfinite(values).all():
        raise ValueError("Expected finite (cells, 3) snapshot")
    if not values.flags.owndata:
        raise ValueError("C++ must supply an owning snapshot array")
    _snapshots.append(values)
    print(f"PYTHON snapshot={len(_snapshots)} shape={values.shape} finite=true", flush=True)
    return len(_snapshots)


def svd_func(rank):
    if rank != 0 or not _snapshots:
        raise ValueError("SVD requires serial snapshots")
    snapshots = np.stack(_snapshots, axis=2)  # cells, components, time
    modes, singular_values = [], []
    for component in range(3):
        u, s, _ = np.linalg.svd(snapshots[:, component, :], full_matrices=False)
        modes.append(u[:, :5])
        singular_values.append(s)
    result = np.ascontiguousarray(np.concatenate(modes, axis=0), dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError("Non-finite SVD modes")
    np.savez(_case / 'python_svd_audit.npz', snapshots=snapshots,
             modes=result, singular_values=np.array(singular_values))
    print(f"PYTHON SVD snapshots={len(_snapshots)} shape={result.shape} finite=true", flush=True)
    _snapshots.clear()
    return result
