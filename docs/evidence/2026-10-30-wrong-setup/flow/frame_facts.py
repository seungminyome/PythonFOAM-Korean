#!/usr/bin/env python3
"""What the frames, the mesh and the pictures hold, from the arrays and the pixels. No model answer is read.

Usage: frame_facts.py <test set> <polyMesh> <llm_demo folder> <output.json>
(numpy and matplotlib; reads frames/<run>/<time>/fields.npz, U.png, p.png and readable-metadata.json)

Cells count as inside the window as in the pictures (centre in x 0 to 0.12 m, y 0 to 0.04 m). Shares "by
cells" count cells and shares "by area" weigh each cell with its area; the mesh is much finer near the walls.
Pixels are compared inside the axes, without the axes' edge lines (rows 82 to 505, columns 78 to 854 of the
1024 x 576 picture). Two comparisons of two pictures: "channels" takes the largest change over R, G and B of each
pixel, grid lines included; "scale positions" maps each pixel to its place on the 256 colours of the colour bar
(viridis) and leaves out the grid lines, which are no colour of the bar. A colour bar is the picture's own, so the
same value can have another colour in another picture. "Differs" means by more than 16 of the 256.
"""
import json
from pathlib import Path
import sys

import numpy as np

RUNS = ("N1", "N2", "N3", "N4", "N5", "M1-inlet-speed", "M2-viscosity", "M3-slip-walls", "M4-moving-wall", "M5-half-inlet")
NORMAL = RUNS[:5]
STEPS = tuple(range(4500, 8001, 500))
DT, START = 5e-6, 0.1
INLET = 32.2
STEP_HEIGHT = 0.0127
WINDOW = ((0.0, 0.12), (0.0, 0.04))
NEAR_WALL = 0.0003      # the cells below y = 0.3 mm
THIN_LAYER = 0.0008     # the cells below y = 0.8 mm
ROWS, COLUMNS = (82, 506), (78, 855)
FIELDS = ("U", "p")
LEVELS = 16             # "differs" means by more than this many colour levels in some channel


def frame_dir(root, run, step):
    return Path(root) / "frames" / run / f"{START + step * DT:.10g}"


def load_arrays(root, run, step):
    with np.load(frame_dir(root, run, step) / "fields.npz", allow_pickle=False) as data:
        return np.array(data["U"]), np.array(data["p"]), np.array(data["centres"])


_PICTURES = {}


def load_picture(root, run, step, field):
    """The picture's RGB as integers 0 to 255, inside the axes, and each pixel's position on the colour bar's
    256 colours (-1 for a pixel that is not one of them: the grid lines)."""
    key = run, step, field
    if key not in _PICTURES:
        from matplotlib import colormaps
        from matplotlib.image import imread
        rgba = imread(frame_dir(root, run, step) / f"{field}.png")
        rgb = np.rint(rgba[ROWS[0]:ROWS[1], COLUMNS[0]:COLUMNS[1], :3] * 255).astype(np.int64)
        scale = np.rint(colormaps["viridis"](np.arange(256))[:, :3] * 255).astype(np.int64)
        unique, inverse = np.unique(rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2], return_inverse=True)
        colours = np.stack([unique >> 16, (unique >> 8) & 255, unique & 255], axis=1)
        distance = np.abs(colours[:, None, :] - scale[None, :, :]).max(axis=2)
        nearest = distance.argmin(axis=1)
        nearest[distance.min(axis=1) > 2] = -1
        _PICTURES[key] = rgb.astype(np.int16), nearest[inverse].reshape(rgb.shape[:2]).astype(np.int16)
    return _PICTURES[key]


def compare(a, b):
    """Two pictures as load_picture gives them: the share of pixels that differ by more than LEVELS and the mean
    difference, for the channels and for the scale positions, and the share of pixels on the scale in both."""
    channels = np.abs(a[0] - b[0])
    both = (a[1] >= 0) & (b[1] >= 0)
    positions = np.abs(a[1] - b[1])[both]
    return {"channels_share": float((channels.max(axis=2) > LEVELS).mean()), "channels_mean": float(channels.mean()),
            "positions_share": float((positions > LEVELS).mean()), "positions_mean": float(positions.mean()),
            "on_scale": float(both.mean())}


def span(values):
    return [min(values), max(values)]


def column_at(centres, extent, x):
    """The cells that cover x, by y."""
    cells = np.flatnonzero((extent[:, 0] <= x) & (x < extent[:, 1]))
    return cells[np.argsort(centres[cells, 1])]


def wall_layer_edge(centres, extent, ux, x):
    """y of the lowest cell of the unbroken reverse-flow layer that hangs from the upper wall, at x."""
    edge = None
    for cell in column_at(centres, extent, x)[::-1]:
        if ux[cell] >= 0:
            break
        edge = float(centres[cell, 1])
    return edge


def geometry(polymesh, centres, foam_fields, pod_image):
    """The patches from the mesh's points, and each cell's area from the polygons the pictures are drawn from."""
    sizes, labels = foam_fields.read_faces(polymesh / "faces")
    points = foam_fields.read_points(polymesh / "points")
    starts = np.concatenate([[0], np.cumsum(sizes)])
    patches = {}
    for patch in foam_fields.read_boundary(polymesh / "boundary"):
        if patch["type"] == "empty":
            continue
        corners = np.concatenate([points[labels[starts[i]:starts[i + 1]]]
                                  for i in range(patch["startFace"], patch["startFace"] + patch["nFaces"])])
        patches[patch["name"]] = {"faces": patch["nFaces"], "x_m": span(corners[:, 0].tolist()), "y_m": span(corners[:, 1].tolist())}
    polygons = pod_image.cell_polygons(*foam_fields.empty_patch_polygons(polymesh), centres.shape[0])
    verts = polygons["points"]
    area, extent = np.zeros(centres.shape[0]), np.zeros((centres.shape[0], 2))
    for k, cell in enumerate(polygons["cells"]):
        x, y = verts[polygons["offsets"][k]:polygons["offsets"][k + 1], 0], verts[polygons["offsets"][k]:polygons["offsets"][k + 1], 1]
        area[cell] = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
        extent[cell] = x.min(), x.max()
    return patches, area, extent, {"points_x_m": span(points[:, 0].tolist()), "points_y_m": span(points[:, 1].tolist()),
                           "cell_centres_x_m": span(centres[:, 0].tolist()), "cell_centres_y_m": span(centres[:, 1].tolist())}


def main(root, polymesh, llm_demo, output):
    sys.path.insert(0, str(llm_demo))
    import foam_fields
    import pod_image
    root, polymesh = Path(root), Path(polymesh)
    _, _, centres = load_arrays(root, RUNS[0], STEPS[0])
    patches, area, extent, extents = geometry(polymesh, centres, foam_fields, pod_image)
    x, y = centres[:, 0], centres[:, 1]
    inside = (x >= WINDOW[0][0]) & (x <= WINDOW[0][1]) & (y >= WINDOW[1][0]) & (y <= WINDOW[1][1])
    below_step = inside & (y < STEP_HEIGHT)
    near_wall = inside & (y < NEAR_WALL)
    thin = inside & (y < THIN_LAYER)
    # the cell next to the lower wall behind the step, every millimetre from x = 0.5 mm to the outlet
    wall_x = np.arange(0.0005, patches["outlet"]["x_m"][0], 0.001)
    wall_cells = np.array([column_at(centres, extent, place)[0] for place in wall_x])
    if abs(area[inside].sum() - (WINDOW[0][1] - WINDOW[0][0]) * (WINDOW[1][1] - WINDOW[1][0])) > 0.02 * 0.0048:
        raise SystemExit(f"cells in the window add up to {area[inside].sum()} m^2")

    frames, states = {}, {}
    white = {"pictures": 0, "white_pixels_inside_axes": 0}
    for run in RUNS:
        for step in STEPS:
            velocity, pressure, again = load_arrays(root, run, step)
            if not np.array_equal(again, centres):
                raise SystemExit(f"{run} {step}: other cell centres")
            ux = velocity[:, 0]
            states[run, step] = velocity, pressure
            meta = json.loads((frame_dir(root, run, step) / "readable-metadata.json").read_text())
            bars = {image["field"]: image["colour_range"] for image in meta["images"]}
            reversed_cells = ux < 0
            walls = reversed_cells & near_wall
            # along the lower wall behind the step, the whole channel: where the reverse flow starts and where its
            # first unbroken stretch ends
            wall_reversed = ux[wall_cells] < 0
            first = int(np.argmax(wall_reversed))
            after = np.flatnonzero(~wall_reversed[first:])
            stretch_end = float(wall_x[first + after[0] - 1]) if after.size else float(wall_x[-1])
            in_window = wall_x <= WINDOW[0][1]
            for field in FIELDS:
                picture = load_picture(root, run, step, field)[0]
                white["pictures"] += 1
                white["white_pixels_inside_axes"] += int((picture == 255).all(axis=2).sum())
            frames[f"{run}-step{step:05d}"] = {
                "run": run, "step": step, "colour_bar_U": bars["U"], "colour_bar_p": bars["p"],
                "reversed_share_of_window_by_area": float(area[inside & reversed_cells].sum() / area[inside].sum()),
                "reversed_share_of_window_by_cells": float(reversed_cells[inside].mean()),
                "reversed_share_below_step_height_by_area": float(area[below_step & reversed_cells].sum() / area[below_step].sum()),
                "reversed_share_below_step_height_by_cells": float(reversed_cells[below_step].mean()),
                "lowest_Ux_in_window": float(ux[inside].min()),
                "near_wall_largest_Ux": float(ux[near_wall].max()),
                "near_wall_cells": int(near_wall.sum()), "near_wall_reversed_cells": int(walls.sum()),
                "near_wall_reversed_x_m": span(x[walls].tolist()) if walls.any() else None,
                "wall_reversed_share_of_the_window_length": float(wall_reversed[in_window].mean()),
                "wall_reverse_flow_starts_x_m": float(wall_x[first]),
                "wall_first_stretch_ends_x_m": stretch_end,
                "wall_last_reverse_flow_x_m": float(wall_x[wall_reversed][-1]),
                "thin_layer_mean_speed": float(np.linalg.norm(velocity[thin], axis=1).mean())}

    by_run = {}
    for run in RUNS:
        rows = [f for f in frames.values() if f["run"] == run]
        by_run[run] = {name: span([f[name] for f in rows]) for name in (
            "reversed_share_of_window_by_area", "reversed_share_of_window_by_cells",
            "reversed_share_below_step_height_by_area", "reversed_share_below_step_height_by_cells",
            "lowest_Ux_in_window", "near_wall_largest_Ux", "thin_layer_mean_speed", "wall_reversed_share_of_the_window_length",
            "wall_reverse_flow_starts_x_m", "wall_first_stretch_ends_x_m", "wall_last_reverse_flow_x_m")}
        by_run[run]["colour_bar_U_lower_end"] = span([f["colour_bar_U"][0] for f in rows])
        by_run[run]["colour_bar_U_upper_end"] = span([f["colour_bar_U"][1] for f in rows])
        by_run[run]["colour_bar_p_lower_end"] = span([f["colour_bar_p"][0] for f in rows])
        by_run[run]["colour_bar_p_upper_end"] = span([f["colour_bar_p"][1] for f in rows])

    # each picture against N5's at the same step, and the neighbouring frames of each run
    against_n5, neighbours = {}, {}
    for run in RUNS:
        cells = {}
        for step in STEPS:
            row = {field: compare(load_picture(root, run, step, field), load_picture(root, "N5", step, field)) for field in FIELDS}
            speed_change = np.linalg.norm(states[run, step][0] - states["N5", step][0], axis=1)[inside]
            row["mean_velocity_difference_over_32p2_by_cells"] = float(speed_change.mean() / INLET)
            row["mean_velocity_difference_over_32p2_by_area"] = float((speed_change * area[inside]).sum() / area[inside].sum() / INLET)
            cells[str(step)] = row
        if run != "N5":
            against_n5[run] = {
                "by_step": cells,
                **{f"{name}_{field}_range": span([r[field][name] for r in cells.values()])
                   for name in ("channels_share", "positions_share") for field in FIELDS},
                "mean_velocity_difference_over_32p2_by_cells_range": span([r["mean_velocity_difference_over_32p2_by_cells"] for r in cells.values()]),
                "mean_velocity_difference_over_32p2_by_area_range": span([r["mean_velocity_difference_over_32p2_by_area"] for r in cells.values()])}
        rows = {f"{a}-{b}": {field: compare(load_picture(root, run, a, field), load_picture(root, run, b, field)) for field in FIELDS}
                for a, b in zip(STEPS, STEPS[1:])}
        neighbours[run] = {"by_pair": rows,
                           **{f"{name}_{field}_range": span([r[field][name] for r in rows.values()])
                              for name in ("channels_mean", "positions_mean") for field in FIELDS}}

    # M4: the layer of the moved wall
    m4 = {}
    for step in STEPS:
        ux = states["M4-moving-wall", step][0][:, 0]
        edges = [wall_layer_edge(centres, extent, ux, c) for c in np.linspace(0.001, 0.119, 119)]
        edges = [e for e in edges if e is not None]
        m4[str(step)] = {"layer_lowest_cell_y_m_at_x_0p06": wall_layer_edge(centres, extent, ux, 0.06),
                         "layer_lowest_cell_y_m_over_x_0p001_to_0p119": min(edges) if edges else None,
                         "columns_with_a_layer": len(edges), "columns": 119}
    upper = patches["upperWall"]["y_m"][1]

    # M5: the profile just upstream of the step and the split of the inlet along the channel
    m5 = {"at_the_step": {}, "upper_minus_lower_half_mean_Ux_m_per_s_at_step_8000": {}}
    for label, run in (("N5", "N5"), ("M5", "M5-half-inlet")):
        ux = states[run, 8000][0][:, 0]
        cells = column_at(centres, extent, -0.0093)
        m5["at_the_step"]["x_m"] = -0.0093
        m5["at_the_step"]["y_m"] = [round(float(v), 5) for v in y[cells]][:: max(1, cells.size // 16)]
        m5["at_the_step"][label] = [round(float(v), 2) for v in ux[cells]][:: max(1, cells.size // 16)]
        core = cells[(y[cells] > 0.03) & (y[cells] < 0.1)]
        m5["at_the_step"][f"{label}_core_Ux_y_0p03_to_0p1_m"] = span(ux[core].tolist())
        rows = {}
        for place in (-1.5, -1.2, -0.9, -0.6, -0.3, -0.1, -0.0093):
            cells = column_at(centres, extent, place)
            middle = 0.5 * (STEP_HEIGHT + upper)
            top, bottom = cells[y[cells] >= middle], cells[y[cells] < middle]
            rows[f"{place:g}"] = round(float((ux[top] * area[top]).sum() / area[top].sum() - (ux[bottom] * area[bottom]).sum() / area[bottom].sum()), 2)
        m5["upper_minus_lower_half_mean_Ux_m_per_s_at_step_8000"][label] = rows

    # the two normal frames 31B flagged and the frames that show the same flow time
    twins = {}
    for a, b in ((("N4", 6500), ("N5", 4500)), (("N5", 5500), ("N4", 7500))):
        va, pa = states[a]
        vb, pb = states[b]
        row = {"largest_velocity_difference_m_per_s": float(np.linalg.norm(va - vb, axis=1).max()),
               "largest_speed_difference_m_per_s": float(np.abs(np.linalg.norm(va, axis=1) - np.linalg.norm(vb, axis=1)).max()),
               "largest_pressure_difference_m2_per_s2": float(np.abs(pa - pb).max())}
        for field in FIELDS:
            row[field] = compare(load_picture(root, *a, field), load_picture(root, *b, field))
        twins[f"{a[0]} step {a[1]} and {b[0]} step {b[1]}"] = row

    out = {"what": __doc__.split("\n", 1)[0], "mesh": {"patches": patches, **extents}, "step_lip_m": {"x": 0.0, "y": STEP_HEIGHT},
           "window_m": {"x": WINDOW[0], "y": WINDOW[1], "cells": int(inside.sum()), "area_m2": float(area[inside].sum())},
           "white_pixels": white, "by_run": by_run, "pictures_against_n5_at_the_same_step": against_n5,
           "neighbouring_frames_of_a_run": neighbours, "m4_upper_wall_layer": {"upper_wall_y_m": upper, "by_step": m4},
           "m5": m5, "same_flow_time_pairs": twins, "frames": frames}
    Path(output).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k in ("mesh", "window_m", "white_pixels", "m4_upper_wall_layer", "m5", "same_flow_time_pairs")}, indent=1))
    for run in RUNS:
        print(run, json.dumps(by_run[run]))
    for run, row in against_n5.items():
        print(run, "against N5", *[f"{name} {field} {row[f'{name}_{field}_range'][0]:.3f} to {row[f'{name}_{field}_range'][1]:.3f};"
                                   for name in ("channels_share", "positions_share") for field in FIELDS],
              [round(v, 3) for v in row["mean_velocity_difference_over_32p2_by_cells_range"]],
              [round(v, 3) for v in row["mean_velocity_difference_over_32p2_by_area_range"]])
    for run, row in neighbours.items():
        print(run, "neighbours", *[f"{name} {field} {row[f'{name}_{field}_range'][0]:.2f} to {row[f'{name}_{field}_range'][1]:.2f};"
                                   for name in ("channels_mean", "positions_mean") for field in FIELDS])


if __name__ == "__main__":
    main(*sys.argv[1:5])
