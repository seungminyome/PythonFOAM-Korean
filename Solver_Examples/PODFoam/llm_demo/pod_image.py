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
    if cells.size and np.unique(cells).size != cells.size:
        # an empty patch that holds both the front and the back face of every cell (one
        # 'defaultFaces' patch, as blockMesh writes it): keep the first polygon of each cell
        keep = np.sort(np.unique(cells, return_index=True)[1])
        points = np.concatenate([points[offsets[k]:offsets[k + 1]] for k in keep])
        offsets = np.concatenate([[0], np.cumsum([offsets[k + 1] - offsets[k] for k in keep])])
        cells = cells[keep]
    if cells.min() < 0 or cells.max() >= n_cells or np.unique(cells).size != cells.size:
        raise ValueError("cell polygon indices must map one polygon to one distinct cell")
    if not np.isfinite(points).all():
        raise ValueError("nonfinite cell polygon points")
    return {"points": points, "offsets": offsets, "cells": cells}


def parse_window(text):
    """'x0,x1' in metres from an environment variable, or None for the whole domain."""
    if not text or not text.strip():
        return None
    parts = [float(item) for item in text.split(",")]
    if len(parts) != 2 or not all(np.isfinite(parts)) or parts[0] >= parts[1]:
        raise ValueError("window must be 'low,high' with low < high")
    return parts


def render(state, centres, solution_d, velocity, pressure, output, polygons=None,
           x_window=None, y_window=None):
    """Return (png_path, metadata). Raises on any nonfinite or misaligned input.

    x_window / y_window ([low, high] in metres) plot only that part of the
    domain; the colour range then spans the cells inside the window. The
    saved arrays are always the whole field.
    """
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
    full_extent = {labels[axes[0]]: [float(x.min()), float(x.max())],
                   labels[axes[1]]: [float(y.min()), float(y.max())]}
    x_low, x_high = x_window if x_window is not None else (float(x.min()), float(x.max()))
    y_low, y_high = y_window if y_window is not None else (float(y.min()), float(y.max()))
    inside = (x >= x_low) & (x <= x_high) & (y >= y_low) & (y <= y_high)
    if inside.sum() < 3:
        raise ValueError("fewer than three cells inside the plot window")
    windowed = x_window is not None or y_window is not None
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
            collection.set_clim(float(values[inside].min()), float(values[inside].max()))
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
        gx = np.linspace(x_low, x_high, 560)
        gy = np.linspace(y_low, y_high, 120)
        grid_x, grid_y = np.meshgrid(gx, gy)
        distance, nearest = tree.query(np.column_stack([grid_x.ravel(), grid_y.ravel()]), k=1)
        inside_grid = distance <= 0.75 * local_size[nearest]
        render_note = ("nearest-cell raster (560x120), blank beyond 0.75x the local cell spacing; "
                       "colour range is each panel's min/max; top panel |U|, bottom panel p")
        def draw(a, values):
            raster = np.full(grid_x.size, np.nan)
            raster[inside_grid] = values[nearest[inside_grid]]
            artist = a.pcolormesh(gx, gy, raster.reshape(grid_x.shape), cmap="viridis",
                                  shading="nearest", rasterized=True)
            artist.set_clim(float(values[inside].min()), float(values[inside].max()))
            return artist
    # The channel is about 20x longer than tall; with equal aspect each panel
    # would be a few pixels high, so the vertical axis is stretched.
    fig, ax = plt.subplots(2, 1, figsize=(6.4, 3.6), dpi=100, constrained_layout=True)
    panels = [(ax[0], speed, "|U| (m/s)"), (ax[1], pressure, "p (m^2/s^2, kinematic)")]
    for a, values, title in panels:
        artist = draw(a, values)
        a.set_aspect("auto")
        a.set_xlim(x_low, x_high)
        a.set_ylim(y_low, y_high)
        a.set_xlabel(f"{labels[axes[0]]} (m)")
        a.set_ylabel(f"{labels[axes[1]]} (m)")
        a.set_title(title, fontsize=10)
        fig.colorbar(artist, ax=a, shrink=0.9, pad=0.02)
    title = f"PODFoam cell fields, t={float(state['time_s']):g} s, step={int(state['step'])}"
    if windowed:
        title += f", window {labels[axes[0]]}=[{x_low:g},{x_high:g}] m"
    fig.suptitle(title, fontsize=11)
    x_span = (x_high - x_low) or 1.0
    y_span = (y_high - y_low) or 1.0
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
        "ranges": {"speed_m_per_s": [float(speed[inside].min()), float(speed[inside].max())],
                   "p_m2_per_s2": [float(pressure[inside].min()), float(pressure[inside].max())]},
        "domain_extent_m": full_extent,
    }
    if windowed:
        metadata["plotted_range_m"] = {labels[axes[0]]: [x_low, x_high],
                                       labels[axes[1]]: [y_low, y_high]}
        metadata["window_cells"] = int(inside.sum())
        metadata["full_field_ranges"] = {
            "speed_m_per_s": [float(speed.min()), float(speed.max())],
            "p_m2_per_s2": [float(pressure.min()), float(pressure.max())]}
        metadata["render"] += "; plotted window only, colour range from cells inside the window"
    (output / "image-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return image, metadata
