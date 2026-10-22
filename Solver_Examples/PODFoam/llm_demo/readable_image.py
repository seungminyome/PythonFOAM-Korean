"""Single-field pictures for the 2026-10-21 picture-reading test.

One field per PNG, 1024x576 pixels. Both axes are in percent of the plotted
range (0 at the left and bottom edges) with a grid line every 10 %, so a
position can be read off the picture in the units the describe answer uses.
The colour bar is labelled at its two ends. The colour range is either the
picture's own minimum and maximum or a range shared by several pictures, so
that equal colours mean equal values across a sequence. Each cell is drawn as
its own polygon, as in pod_image.py.
"""
from pathlib import Path
import hashlib

import numpy as np

WIDTH, HEIGHT, DPI = 1024, 576, 100
STYLE = "readable-v2"
FIELDS = {"U": ("|U|", "m/s", "Velocity magnitude |U|"),
          "p": ("p", "m^2/s^2", "Kinematic pressure p")}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def percent_coordinates(points_2d, plotted):
    """Map metres to percent of the plotted range [[x0, x1], [y0, y1]]."""
    (x0, x1), (y0, y1) = plotted
    return np.column_stack([100.0 * (points_2d[:, 0] - x0) / (x1 - x0),
                            100.0 * (points_2d[:, 1] - y0) / (y1 - y0)])


def inside_window(centres_2d, plotted):
    (x0, x1), (y0, y1) = plotted
    x, y = centres_2d[:, 0], centres_2d[:, 1]
    return (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)


def _label(value):
    return f"{value:.4g}"


def render_field(values, polygons, centres, axes, plotted, field, step, time_s, output,
                 colour_range=None, fields_sha256=None):
    """Draw one field; return metadata. colour_range=None uses the cells inside the window."""
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or values.shape[0] != centres.shape[0] or not np.isfinite(values).all():
        raise ValueError("values must be finite, one per cell")
    if polygons is None or polygons["cells"].size != values.shape[0]:
        raise ValueError("one polygon per cell is required")
    symbol, unit, name = FIELDS[field]
    inside = inside_window(centres[:, axes], plotted)
    if inside.sum() < 3:
        raise ValueError("fewer than three cells inside the plotted range")
    shared = colour_range is not None
    low, high = (float(colour_range[0]), float(colour_range[1])) if shared else (
        float(values[inside].min()), float(values[inside].max()))
    if not high > low:
        high = low + max(abs(low), 1.0) * 1e-6
    verts = np.split(percent_coordinates(polygons["points"][:, axes], plotted),
                     polygons["offsets"][1:-1])
    fig = plt.figure(figsize=(WIDTH / DPI, HEIGHT / DPI), dpi=DPI)
    ax = fig.add_axes([0.075, 0.12, 0.76, 0.74])
    cax = fig.add_axes([0.855, 0.12, 0.025, 0.74])
    collection = PolyCollection(verts, array=values[polygons["cells"]], cmap="viridis",
                                edgecolors="none", linewidths=0, antialiased=False, rasterized=True)
    collection.set_clim(low, high)
    ax.add_collection(collection)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("auto")
    ticks = np.arange(0, 101, 10)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.tick_params(labelsize=10)
    ax.set_axisbelow(False)
    ax.grid(True, color="black", alpha=0.35, linewidth=0.6)
    ax.set_xlabel("x, % of plotted range from the left edge", fontsize=10)
    ax.set_ylabel("y, % from the bottom edge", fontsize=10)
    (x0, x1), (y0, y1) = plotted
    ax.set_title(f"{name} ({unit}), step {int(step)}, t = {float(time_s):g} s\n"
                 f"plotted x {x0:g} to {x1:g} m, y {y0:g} to {y1:g} m; white = no cells",
                 fontsize=11)
    bar = fig.colorbar(collection, cax=cax)
    bar.set_ticks(np.linspace(low, high, 5))
    bar.set_ticklabels([_label(v) for v in np.linspace(low, high, 5)])
    bar.ax.tick_params(labelsize=10)
    bar.set_label(f"{symbol} ({unit})" + (", same scale in every image" if shared else
                                         ", this image's min to max"), fontsize=10)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    text = {"Step": str(int(step)), "Time": str(float(time_s)), "Field": field, "Style": STYLE}
    if fields_sha256:
        text["FieldsSHA256"] = fields_sha256
    fig.savefig(output, dpi=DPI, metadata=text)
    plt.close(fig)
    return {"field": field, "symbol": symbol, "unit": unit, "path": output.name,
            "sha256": _sha256(output), "bytes": output.stat().st_size,
            "width": WIDTH, "height": HEIGHT, "colour_range": [low, high],
            "colour_range_shared": shared,
            "range_inside_window": [float(values[inside].min()), float(values[inside].max())]}
