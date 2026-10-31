"""Answer keys of saved frames and the scores of a model's answers against them.

truth_from_arrays and load_v2 give one frame's key from its arrays, sequence_truth the trend
words of frames in time order, numbers_of the values a sequence request can state; score_describe
and score_sequence compare a structured answer with a key. verify_async.py and the unit tests
use these functions. Nothing here draws a picture, runs the solver or sends a request.
"""
import math

import numpy as np

import readable_request
from readable_request import AXES

TREND_TOLERANCE = 0.02        # relative change of at most this is "roughly_constant"
REGION_TOLERANCE_PCT = 5.0    # argmax moving at most this (percent of plotted range) is "same_place"


def truth_from_arrays(centres, velocity, pressure, plotted, step, time_s):
    """One frame's answer key, from its arrays and a plotted range."""
    (x0, x1), (y0, y1) = plotted
    x, y = centres[:, 0], centres[:, 1]
    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    speed = np.linalg.norm(velocity, axis=1)
    index = np.flatnonzero(inside)

    def percent(cell):
        return {"x_percent": 100.0 * (x[cell] - x0) / (x1 - x0),
                "y_percent": 100.0 * (y[cell] - y0) / (y1 - y0),
                "x_m": float(x[cell]), "y_m": float(y[cell]), "cell": int(cell)}

    fastest = index[np.argmax(speed[index])]
    lowest = index[np.argmin(pressure[index])]
    return {"step": int(step), "time_s": float(time_s), "cells_in_window": int(inside.sum()),
            "max_speed_m_per_s": float(speed[index].max()),
            "min_pressure_m2_per_s2": float(pressure[index].min()),
            "fastest_flow": percent(fastest), "lowest_pressure": percent(lowest),
            "plotted_range_m": {"x": [x0, x1], "y": [y0, y1]}, "projection_axes": AXES,
            "x_span_m": x1 - x0, "y_span_m": y1 - y0}


def load_v2(directory):
    """Frame and answer key of a v2 directory, with the hashes checked."""
    frame, meta, fields = readable_request.load_frame(directory)
    plotted = [meta["plotted_range_m"]["x"], meta["plotted_range_m"]["y"]]
    return frame, truth_from_arrays(fields["centres"], fields["U"], fields["p"], plotted,
                                    meta["step"], meta["time_s"])


def numbers_of(truth):
    return {"max_speed_m_per_s": truth["max_speed_m_per_s"],
            "min_pressure_m2_per_s2": truth["min_pressure_m2_per_s2"],
            "fastest_flow_percent": [truth["fastest_flow"]["x_percent"], truth["fastest_flow"]["y_percent"]]}


def trend(first, last, tolerance=TREND_TOLERANCE):
    scale = max(abs(first), abs(last), 1e-300)
    change = (last - first) / scale
    if change > tolerance:
        return "increasing", change
    if change < -tolerance:
        return "decreasing", change
    return "roughly_constant", change


def sequence_truth(truths):
    first, last = truths[0], truths[-1]
    speed_trend, speed_change = trend(first["max_speed_m_per_s"], last["max_speed_m_per_s"])
    pressure_word, pressure_change = trend(first["min_pressure_m2_per_s2"],
                                           last["min_pressure_m2_per_s2"])
    # for the pressure minimum the vocabulary is about the sign direction
    pressure_trend = {"increasing": "less_negative", "decreasing": "more_negative",
                      "roughly_constant": "roughly_constant"}[pressure_word]
    if first["min_pressure_m2_per_s2"] >= 0 and last["min_pressure_m2_per_s2"] >= 0:
        pressure_trend = "roughly_constant" if pressure_word == "roughly_constant" else (
            "more_negative" if pressure_word == "decreasing" else "less_negative")
    moved = math.hypot(last["fastest_flow"]["x_percent"] - first["fastest_flow"]["x_percent"],
                       last["fastest_flow"]["y_percent"] - first["fastest_flow"]["y_percent"])
    return {"max_speed_trend": speed_trend, "max_speed_relative_change": speed_change,
            "max_speed_first_last": [first["max_speed_m_per_s"], last["max_speed_m_per_s"]],
            "min_pressure_trend": pressure_trend, "min_pressure_relative_change": pressure_change,
            "min_pressure_first_last": [first["min_pressure_m2_per_s2"], last["min_pressure_m2_per_s2"]],
            "fastest_flow_region": "same_place" if moved <= REGION_TOLERANCE_PCT else "moves",
            "fastest_flow_moved_percent": moved,
            "tolerances": {"relative_change": TREND_TOLERANCE, "region_percent": REGION_TOLERANCE_PCT},
            "frames": [{"step": t["step"], "time_s": t["time_s"], "max_speed_m_per_s": t["max_speed_m_per_s"],
                        "min_pressure_m2_per_s2": t["min_pressure_m2_per_s2"],
                        "fastest_flow_percent": [t["fastest_flow"]["x_percent"], t["fastest_flow"]["y_percent"]]}
                       for t in truths]}


def score_describe(structured, truth):
    out = {}
    for name in ("fastest_flow", "lowest_pressure"):
        dx = structured[f"{name}_x_percent"] - truth[name]["x_percent"]
        dy = structured[f"{name}_y_percent"] - truth[name]["y_percent"]
        out[name] = {"answer_percent": [structured[f"{name}_x_percent"], structured[f"{name}_y_percent"]],
                     "true_percent": [truth[name]["x_percent"], truth[name]["y_percent"]],
                     "error_percent": [dx, dy], "distance_percent": math.hypot(dx, dy),
                     "error_m": [dx / 100.0 * truth["x_span_m"], dy / 100.0 * truth["y_span_m"]],
                     "distance_m": math.hypot(dx / 100.0 * truth["x_span_m"], dy / 100.0 * truth["y_span_m"]),
                     "within_10_percent": math.hypot(dx, dy) <= 10.0}
    return out


def score_sequence(structured, truth):
    out = {}
    for name in ("max_speed_trend", "min_pressure_trend", "fastest_flow_region"):
        out[name] = {"answer": structured[name], "truth": truth[name],
                     "match": structured[name] == truth[name],
                     "cannot_tell": structured[name] == "cannot_tell"}
    out["matches"] = sum(v["match"] for v in out.values() if isinstance(v, dict))
    return out
