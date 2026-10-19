"""Render one step's |U| and p as a small PNG.

The inputs are the velocity snapshot snapshot_func received for the step and
the p_cells array PythonAnalysis.H put into the state dictionary. The arrays
are saved next to the PNG and their hash goes into the PNG metadata.
"""
from pathlib import Path
import hashlib
import json
import os
import time

import numpy as np

_backend = {"ready": False, "import_wall_s": None, "error": None}


def prepare_backend(cache_dir):
    """Import matplotlib once, at startup; forked workers inherit it."""
    if _backend["ready"]:
        return _backend
    start = time.perf_counter()
    try:
        os.environ.setdefault("MPLCONFIGDIR", str(Path(cache_dir) / "mpl-cache"))
        Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot  # noqa: F401  (warm the pyplot import too)
        _backend["ready"] = True
        _backend["version"] = matplotlib.__version__
    except Exception as error:  # pragma: no cover - environment dependent
        _backend["error"] = f"{type(error).__name__}: {error}"
    _backend["import_wall_s"] = time.perf_counter() - start
    return _backend


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def projection_axes(centres, solution_d):
    """Two in-plane axes: the solved directions for 2D cases, else widest spans."""
    solved = [i for i, flag in enumerate(solution_d) if flag == 1]
    if len(solved) == 2:
        return solved
    spans = np.ptp(centres, axis=0)
    return sorted(np.argsort(spans)[-2:].tolist())


def cell_polygons(points, offsets, cells, n_cells):
    """Validate the per-cell polygon description from the solver; None if absent."""
    if points is None or offsets is None or cells is None:
        return None
    points = np.array(points, dtype=float, copy=True).reshape(-1, 3)
    offsets = np.array(offsets, dtype=np.int64, copy=True).ravel()
    cells = np.array(cells, dtype=np.int64, copy=True).ravel()
    if cells.size == 0:
        return None
    if offsets.size != cells.size + 1 or offsets[0] != 0 or offsets[-1] != points.shape[0]:
        raise ValueError("inconsistent cell polygon offsets")
    if not np.all(np.diff(offsets) >= 3):
        raise ValueError("cell polygon with fewer than three vertices")
    if cells.min() < 0 or cells.max() >= n_cells or np.unique(cells).size != cells.size:
        raise ValueError("cell polygon indices must map one polygon to one distinct cell")
    if not np.isfinite(points).all():
        raise ValueError("nonfinite cell polygon points")
    return {"points": points, "offsets": offsets, "cells": cells}


def render(state, centres, solution_d, velocity, pressure, output, polygons=None):
    """Return (png_path, metadata). Raises on any nonfinite or misaligned input."""
    if not _backend["ready"]:
        raise RuntimeError("matplotlib backend not prepared: " + str(_backend["error"]))
    import matplotlib.pyplot as plt

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    centres = np.asarray(centres, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    pressure = np.asarray(pressure, dtype=float)
    cells = int(state["cells"])
    if centres.shape != (cells, 3) or velocity.shape != (cells, 3) or pressure.shape != (cells,):
        raise ValueError(f"field/geometry shape mismatch: {centres.shape} {velocity.shape} {pressure.shape}")
    for name, array in (("centres", centres), ("U", velocity), ("p", pressure)):
        if not np.isfinite(array).all():
            raise ValueError(f"nonfinite {name}; image and model request withheld")

    # keep the arrays the picture was made from
    fields_path = output / "fields.npz"
    np.savez_compressed(fields_path, centres=centres, U=velocity, p=pressure,
                        time_s=np.array(float(state["time_s"])), step=np.array(int(state["step"])))
    fields_sha = _sha256(fields_path)

    axes = projection_axes(centres, solution_d)
    labels = ["x", "y", "z"]
    speed = np.linalg.norm(velocity, axis=1)
    x = centres[:, axes[0]]
    y = centres[:, axes[1]]
    from matplotlib.collections import PolyCollection
    if polygons is not None and polygons["cells"].size == cells:
        mode = "cell_polygons"
        pts2 = polygons["points"][:, axes]
        verts = np.split(pts2, polygons["offsets"][1:-1])
        order = polygons["cells"]
        render_note = ("each cell drawn as its own polygon in its own colour, no interpolation; "
                       "colour range is each panel's min/max; top panel |U|, bottom panel p")
        def draw(a, values):
            collection = PolyCollection(verts, array=values[order], cmap="viridis",
                                        edgecolors="none", linewidths=0, antialiased=False,
                                        rasterized=True)
            collection.set_clim(float(values.min()), float(values.max()))
            a.add_collection(collection)
            return collection
    else:
        # Fallback (3D or no polygons): each pixel shows its nearest cell value,
        # masked beyond 0.75x the local cell spacing. Not used for the 2D POD case.
        mode = "nearest_cell_raster"
        from scipy.spatial import cKDTree
        tree = cKDTree(np.column_stack([x, y]))
        neighbour_distance, _ = tree.query(np.column_stack([x, y]), k=5)
        local_size = neighbour_distance[:, 1:].max(axis=1)
        gx = np.linspace(float(x.min()), float(x.max()), 560)
        gy = np.linspace(float(y.min()), float(y.max()), 120)
        grid_x, grid_y = np.meshgrid(gx, gy)
        distance, nearest = tree.query(np.column_stack([grid_x.ravel(), grid_y.ravel()]), k=1)
        inside = distance <= 0.75 * local_size[nearest]
        render_note = ("nearest-cell raster (560x120), blank beyond 0.75x the local cell spacing; "
                       "colour range is each panel's min/max; top panel |U|, bottom panel p")
        def draw(a, values):
            raster = np.full(grid_x.size, np.nan)
            raster[inside] = values[nearest[inside]]
            return a.pcolormesh(gx, gy, raster.reshape(grid_x.shape), cmap="viridis",
                                shading="nearest", rasterized=True)
    # The channel is about 20x longer than tall; with equal aspect each panel
    # would be a few pixels high, so the vertical axis is stretched.
    fig, ax = plt.subplots(2, 1, figsize=(6.4, 3.6), dpi=100, constrained_layout=True)
    panels = [(ax[0], speed, "|U| (m/s)"), (ax[1], pressure, "p (m^2/s^2, kinematic)")]
    for a, values, title in panels:
        artist = draw(a, values)
        a.set_aspect("auto")
        a.set_xlim(float(x.min()), float(x.max()))
        a.set_ylim(float(y.min()), float(y.max()))
        a.set_xlabel(f"{labels[axes[0]]} (m)")
        a.set_ylabel(f"{labels[axes[1]]} (m)")
        a.set_title(title, fontsize=10)
        fig.colorbar(artist, ax=a, shrink=0.9, pad=0.02)
    fig.suptitle(f"PODFoam cell fields, t={float(state['time_s']):g} s, step={int(state['step'])}",
                 fontsize=11)
    x_span = float(np.ptp(x)) or 1.0
    y_span = float(np.ptp(y)) or 1.0
    image = output / "state.png"
    fig.savefig(image, metadata={"Time": str(state["time_s"]), "Step": str(state["step"]),
                                 "FieldsSHA256": fields_sha})
    plt.close(fig)

    metadata = {
        "path": str(image), "sha256": _sha256(image), "bytes": image.stat().st_size,
        "fields_npz": str(fields_path), "fields_sha256": fields_sha,
        "time_s": float(state["time_s"]), "step": int(state["step"]), "cells": cells,
        "width": 640, "height": 360,
        "projection_axes": [labels[i] for i in axes], "coordinate_unit": "m",
        "panels": ["|U| (m/s)", "kinematic pressure p (m^2/s^2)"],
        "render": render_note, "render_mode": mode,
        "cell_polygons": None if polygons is None else int(polygons["cells"].size),
        "aspect": {"mode": "auto", "x_span_over_y_span": x_span / y_span},
        "ranges": {"speed_m_per_s": [float(speed.min()), float(speed.max())],
                   "p_m2_per_s2": [float(pressure.min()), float(pressure.max())]},
        "domain_extent_m": {labels[axes[0]]: [float(x.min()), float(x.max())],
                            labels[axes[1]]: [float(y.min()), float(y.max())]},
    }
    (output / "image-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return image, metadata
