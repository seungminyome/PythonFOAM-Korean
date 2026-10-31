#!/usr/bin/env python3
"""Instability test (2026-10-28): can a vision-language model tell from three v2 frames that a
run is going numerically unstable?

  instability-v2own   three times of one pimpleFoam run of the step case, |U| and p each on its
                      own colour scale (the pictures of dev-sequence-v2own), all in the window the
                      solver plots (x 0 to 0.12 m, y 0 to 0.04 m), asked with
                      stability_request.STABILITY_V2OWN_SYSTEM_PROMPT for stable, unstable or
                      cannot_tell and a reason

build:  python3 instability_test.py build --design <design.json> --centres <fields.npz> \
            --output <new dir> [--within N] [--margin N] [--seed N]
        The design names the runs (case folders with system/, constant/polyMesh, log.pimpleFoam
        and the written time directories). A run whose log has 'End' ended. A run whose log
        has a floating point exception trace (Foam::sigFpe) and no 'End' crashed in its last
        logged step. Any other log (a run still going, or stopped by a time limit, by hand or
        by another error) is refused. The triples of a run that crashed end 1 to --within
        steps (default 10) before the crash (key 'unstable', scored), or at the design's
        early_steps_to_crash ('unstable', not in the balanced score: they show how early an
        answer turns). A run that ended gives stable_items 'stable' triples of written
        states, spread over the run, each ending at least --margin steps (default 100) before
        the run's last step. States are named step = time / 5e-7 as in picture_test; the key
        keeps each run's own step numbers. The note, the captions and the picture titles give
        each frame's step and time, so the time between frames is visible to the model: on
        the set of 2026-10-28 it alone separates the two classes.
check / run: as picture_test.py, with this set.
report: the stability tables from one or more run folders: the balanced score, how early
        'unstable' is said, false alarms by run, the fixed answer and two numeric baselines
        computed from the arrays (growth of the peak |U| and of the largest cell-to-cell |U|
        jump in the window from the first to the last frame). All run folders must use one
        answer key, the one each was run with (truth_sha256 in run.json).
"""
import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import numpy as np

import foam_fields
import picture_test as pt
import readable_request
import stability_request
from llm_client import encode_json, write_json

SET = "instability-v2own"
NEW_SETS = (SET,)
TEST_NAME = "instability test 2026-10-28"
SEED = 20261028
WINDOW_M = [[0.0, 0.12], [0.0, 0.04]]       # LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
WITHIN = 10          # a triple whose last frame is at most this many steps before the crash is 'unstable'
MARGIN = 100         # a 'stable' triple ends at least this many steps before its run's last step
CRASHED_GAPS = (1, 2, 3)        # steps between the frames of a triple from a run that crashed
STABLE_GAPS = (1, 2)            # written states between the frames of a triple from a run that ended
EARLY_BINS = ((1, 1), (2, 3), (4, 6), (7, 10), (11, 25), (26, 100), (101, 10 ** 9))
SPEED_RULES = (1.05, 1.1, 1.2, 1.5, 2.0)    # peak |U| last / first above this: 'unstable'
JUMP_RULES = (1.2, 1.5, 2.0, 3.0)           # largest cell-to-cell |U| jump last / first above this
BY_RUN_RULES = (2, len(SPEED_RULES) + 1)    # peak |U| grows > 20 %, largest jump grows > 50 %

_TIME = re.compile(r"^Time = (\S+)\s*$")
_COURANT = re.compile(r"^Courant Number mean: \S+ max: (\S+)")
_FPE = re.compile(r"Foam::sigFpe::sigHandler")     # the stack trace of a floating point exception


# ---------------------------------------------------------------- runs

def read_log(path):
    """Steps of a pimpleFoam log: [(time name, largest Courant number printed before the step)],
    whether the run reached 'End' and whether it stopped with a floating point exception. The
    Courant number printed before step j is computed from the state written at the end of
    step j - 1."""
    steps, courant, ended, crashed = [], None, False, False
    for line in Path(path).read_text(errors="replace").splitlines():
        match = _COURANT.match(line)
        if match:
            courant = float(match.group(1))
            continue
        match = _TIME.match(line)
        if match:
            steps.append((match.group(1), courant))
        elif line.strip() == "End":
            ended = True
        elif _FPE.search(line):
            crashed = True
    return {"steps": steps, "ended": ended, "crashed": crashed}


def _dict_value(text, key):
    match = re.search(rf"^\s*{re.escape(key)}\s+([^;]+);", text, re.M)
    return match.group(1).strip() if match else None


def read_run(name, case):
    """What the build needs to know about one run: settings, how it ended, its written states."""
    case = Path(case)
    control = (case / "system" / "controlDict").read_text()
    schemes = re.sub(r"//[^\n]*", "", (case / "system" / "fvSchemes").read_text())
    log = read_log(case / "log.pimpleFoam")
    if log["ended"] == log["crashed"]:
        raise ValueError(f"{case / 'log.pimpleFoam'}: " + (
            "both 'End' and a floating point exception" if log["ended"] else
            "neither 'End' nor a floating point exception (still running, or stopped another way)"))
    index = {time: j + 1 for j, (time, _) in enumerate(log["steps"])}
    start = float(_dict_value(control, "startTime"))
    states = []
    for step, path in pt.state_steps(case).items():
        if float(path.name) <= start:
            continue
        if path.name not in index:
            raise ValueError(f"{path}: no 'Time = {path.name}' line in the log")
        k = index[path.name]
        courant = log["steps"][k][1] if k < len(log["steps"]) else None
        states.append({"time_name": path.name, "time_s": float(path.name), "step": step,
                       "run_step": k, "courant_max": courant, "path": path})
    states.sort(key=lambda s: s["run_step"])
    adaptive = (_dict_value(control, "adjustTimeStep") or "no") in ("yes", "on", "true")
    return {"name": name, "case": case, "ended": log["ended"], "logged_steps": len(log["steps"]),
            "crash_step": None if log["ended"] else len(log["steps"]),
            "scheme_div_phi_U": _dict_value(schemes, "div(phi,U)"),
            "delta_t_s": None if adaptive else float(_dict_value(control, "deltaT")),
            "adaptive_time_step": adaptive, "start_time_s": start, "states": states,
            "courant_max_logged": [min(c for _, c in log["steps"] if c is not None),
                                   max(c for _, c in log["steps"] if c is not None)]}


# ---------------------------------------------------------------- triples

def crashed_triples(run, steps_to_crash, gaps, rng, scored):
    """One triple per steps-to-crash value: the last frame that many steps before the crash, a
    gap drawn from those that keep every frame a written state of the run's own steps."""
    by_step = {s["run_step"]: s for s in run["states"]}
    out = []
    for s in steps_to_crash:
        last = run["crash_step"] - s
        valid = [g for g in gaps if last - 2 * g >= 1 and all(last - j * g in by_step for j in range(3))]
        if not valid:
            continue
        g = int(rng.choice(valid))
        out.append({"run": run["name"], "frames": [by_step[last - 2 * g], by_step[last - g], by_step[last]],
                    "gap_run_steps": g, "stability": "unstable", "scored": scored,
                    "group": "unstable-last" if scored else "unstable-early"})
    return out


def stable_triples(run, count, gaps, rng, margin, first_time_s=0.0):
    """count triples of written states (gap in written states), spread over the run: the usable
    starts are cut into count equal parts and one start is drawn in each."""
    states = [s for s in run["states"] if s["time_s"] >= first_time_s]
    usable = [s for s in states if s["run_step"] <= run["logged_steps"] - margin]
    last_start = len(usable) - 1 - 2 * max(gaps)
    if last_start < count - 1:
        raise ValueError(f"{run['name']}: too few written states for {count} triples")
    out = []
    for j in range(count):
        lo, hi = j * (last_start + 1) // count, (j + 1) * (last_start + 1) // count
        start, g = int(rng.integers(lo, hi)), int(rng.choice(gaps))
        triple = (start, start + g, start + 2 * g)
        out.append({"run": run["name"], "frames": [usable[i] for i in triple],
                    "gap_written_states": g,
                    "gap_run_steps": usable[triple[1]]["run_step"] - usable[triple[0]]["run_step"],
                    "stability": "stable", "scored": True, "group": "stable"})
    return out


# ---------------------------------------------------------------- numbers from the arrays

class Faces:
    """Owner and neighbour of the internal faces, for cell-to-cell jumps inside the window."""

    def __init__(self, polymesh, centres, window):
        neighbour = foam_fields.read_labels(Path(polymesh) / "neighbour")
        owner = foam_fields.read_labels(Path(polymesh) / "owner")[:neighbour.size]
        (x0, x1), (y0, y1) = window
        x, y = centres[:, 0], centres[:, 1]
        inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
        both = inside[owner] & inside[neighbour]
        self.owner, self.neighbour, self.inside = owner[both], neighbour[both], inside


def state_numbers(faces, velocity, pressure):
    """Extremes and the largest cell-to-cell jumps of |U| and p inside the window, and the
    largest |U| over the whole domain."""
    speed = np.linalg.norm(velocity, axis=1)
    inside = faces.inside
    return {"max_speed_m_per_s": float(speed[inside].max()),
            "min_pressure_m2_per_s2": float(pressure[inside].min()),
            "max_pressure_m2_per_s2": float(pressure[inside].max()),
            "max_speed_domain_m_per_s": float(speed.max()),
            "max_jump_speed_m_per_s": float(np.abs(speed[faces.owner] - speed[faces.neighbour]).max()),
            "max_jump_pressure_m2_per_s2": float(np.abs(pressure[faces.owner] - pressure[faces.neighbour]).max())}


def numeric_ratios(frames):
    first, last = frames[0], frames[-1]
    return {"max_speed_last_over_first": last["max_speed_m_per_s"] / first["max_speed_m_per_s"],
            "max_jump_speed_last_over_first": last["max_jump_speed_m_per_s"] / first["max_jump_speed_m_per_s"]}


# ---------------------------------------------------------------- build

def _flow_root(case):
    """The nearest folder named flow-states-* above a case (its manifest prefix), else its parent."""
    case = Path(case).resolve()
    return next((p for p in case.parents if p.name.startswith("flow-states-")), case.parent)


def build(args):
    import matplotlib
    import pod_image
    for name in ("design", "centres", "output"):
        setattr(args, name, str(Path(getattr(args, name)).resolve()))
    design = json.loads(Path(args.design).read_text())
    repo = Path(__file__).resolve().parents[3]
    roots = [(repo, "")]
    for entry in design["runs"]:
        root = _flow_root(entry["case"])
        if all(root != r for r, _ in roots):
            roots.append((root, root.name + "/"))
    builder = pt.Builder(args.output, roots=roots)
    pod_image.prepare_backend(builder.output / ".mpl")
    window = [[float(v) for v in pair] for pair in design.get("window_m", WINDOW_M)]
    runs =[read_run(entry["name"], entry["case"]) for entry in design["runs"]]
    first_mesh = runs[0]["case"] / "constant" / "polyMesh"
    mesh = pt.Mesh(first_mesh, args.centres)
    for run in runs[1:]:
        other = {name: pt.file_sha256(run["case"] / "constant" / "polyMesh" / name)
                 for name in ("boundary", "faces", "owner", "points")}
        if other != mesh.sources["polymesh"]:
            raise ValueError(f"{run['name']}: another mesh")
    mesh.views["window"] = window                # as the solver names a plotted window
    faces = Faces(first_mesh, mesh.centres, window)
    rng = np.random.default_rng(args.seed)
    items = []
    for entry, run in zip(design["runs"], runs):
        if not run["ended"]:
            if entry.get("stable_items"):
                raise ValueError(f"{run['name']}: stable_items for a run that crashed")
            early = [int(s) for s in entry.get("early_steps_to_crash", [])]
            if any(s <= args.within for s in early):
                raise ValueError(f"{run['name']}: early steps-to-crash must exceed --within")
            items += crashed_triples(run, range(1, args.within + 1), CRASHED_GAPS, rng, True)
            items += crashed_triples(run, early, CRASHED_GAPS, rng, False)
        else:
            if entry.get("early_steps_to_crash"):
                raise ValueError(f"{run['name']}: early_steps_to_crash for a run that ended")
            items += stable_triples(run, int(entry["stable_items"]), STABLE_GAPS, rng, args.margin,
                                    float(entry.get("first_time_s", 0.0)))
    runs_by_name = {run["name"]: run for run in runs}
    frames_done, numbers, flow_states = {}, {}, {}
    for item in items:
        run = runs_by_name[item["run"]]
        frames, truths = [], []
        for state in item["frames"]:
            state_key = f"{run['name']}/{state['time_name']}"
            if state_key not in frames_done:
                velocity = foam_fields.read_internal_field(state["path"] / "U", mesh.cells)
                pressure = foam_fields.read_internal_field(state["path"] / "p", mesh.cells)
                frames_done[state_key] = pt.render_v2(mesh, "window", velocity, pressure, state["step"],
                                                      state["time_s"],
                                                      builder.frame_dir(run["name"], state["time_name"]))
                numbers[state_key] = state_numbers(faces, velocity, pressure)
                flow_states[state_key] = {"time_dir": builder.rel(state["path"]),
                                          "U_sha256": pt.file_sha256(state["path"] / "U"),
                                          "p_sha256": pt.file_sha256(state["path"] / "p")}
            frame, truth = frames_done[state_key]
            frames.append(frame)
            truths.append(dict(truth, **numbers[state_key], run_step=state["run_step"],
                               courant_max=state["courant_max"],
                               steps_to_crash=(run["crash_step"] - state["run_step"]) if run["crash_step"] else None,
                               steps_after_in_run=None if run["crash_step"] else run["logged_steps"] - state["run_step"]))
        run_steps = [s["run_step"] for s in item["frames"]]
        name = f"{run['name']}-steps{'-'.join(f'{k:05d}' for k in run_steps)}"
        key = {"stability": item["stability"], "scored": item["scored"], "group": item["group"],
               "run": run["name"], "scheme_div_phi_U": run["scheme_div_phi_U"], "delta_t_s": run["delta_t_s"],
               "adaptive_time_step": run["adaptive_time_step"], "crash_step": run["crash_step"],
               "logged_steps": run["logged_steps"], "gap_run_steps": item["gap_run_steps"],
               "steps_to_crash_last": truths[-1]["steps_to_crash"],
               "plotted_range_m": {"x": window[0], "y": window[1]},
               "cells_in_window": truths[0]["cells_in_window"],
               "numeric": numeric_ratios(truths),
               "frames": [{k: t[k] for k in ("step", "time_s", "run_step", "courant_max", "steps_to_crash",
                                             "steps_after_in_run", "max_speed_m_per_s", "min_pressure_m2_per_s2",
                                             "max_pressure_m2_per_s2", "max_speed_domain_m_per_s",
                                             "max_jump_speed_m_per_s", "max_jump_pressure_m2_per_s2")}
                          | {"fastest_flow_percent": [t["fastest_flow"]["x_percent"], t["fastest_flow"]["y_percent"]]}
                          for t in truths]}
        sources = {"frames": [f["directory"] for f in frames], "states": [f"{run['name']}/{s['time_name']}" for s in item["frames"]]}
        item_design = {"run": run["name"], "group": item["group"], "run_steps": run_steps,
                       "times_s": [s["time_s"] for s in item["frames"]],
                       "steps_to_crash_last": key["steps_to_crash_last"], "gap_run_steps": item["gap_run_steps"]}
        builder.add(SET, name, "stability", stability_request.stability_v2_payload(frames), key, sources, item_design)
    write_json(builder.output / "truth.private.json", builder.truth)
    shutil.rmtree(builder.output / ".mpl", ignore_errors=True)
    linked = pt.link_duplicate_arrays(builder.output / "frames")
    here = Path(__file__).resolve().parent
    code = {name: pt.file_sha256(here / name) for name in
            ("instability_test.py", "stability_request.py", "picture_test.py", "frame_scoring.py", "readable_image.py", "readable_request.py",
             "foam_fields.py", "pod_image.py", "snapshot_runner.py", "llm_client.py")}
    groups = Counter(f"{e['design']['group']} {e['design']['run']}" for e in builder.entries)
    manifest = {"schema_version": 2, "test": f"{TEST_NAME} (seed {args.seed})", "seed": args.seed,
                "max_tokens": pt.MAX_TOKENS, "sets": {SET: len(builder.entries)}, "requests": builder.entries,
                "truth_sha256": pt.file_sha256(builder.output / "truth.private.json"),
                "build_args": dict(builder.rel(vars(args)), output=Path(args.output).name),
                "design": design, "design_sha256": pt.file_sha256(args.design),
                "path_prefixes": {"": "frames/ and requests/ are in this test set, docs/ is the repository"}
                | {prefix: "a folder of pimpleFoam runs" for _, prefix in roots[1:]},
                "mesh": builder.rel(mesh.sources), "plotted_range_m": {"x": window[0], "y": window[1]},
                "label_rule": {"unstable_within_steps": args.within, "stable_margin_steps": args.margin,
                               "crashed_gaps_steps": list(CRASHED_GAPS), "stable_gaps_written_states": list(STABLE_GAPS),
                               "note": "a run crashed when its log has a floating point exception trace "
                                       "(Foam::sigFpe) and no 'End' line; it crashed in its last logged "
                                       "step. Triples from a run that crashed are 'unstable'; those "
                                       "ending more than unstable_within_steps steps before the crash are "
                                       "not scored in the balanced count. Runs that ended give 'stable' "
                                       "triples."},
                "runs": [{k: builder.rel(str(run[k])) if k == "case" else run[k]
                          for k in ("name", "case", "scheme_div_phi_U", "delta_t_s", "adaptive_time_step",
                                    "start_time_s", "logged_steps", "ended", "crash_step", "courant_max_logged")}
                         | {"written_states": len(run["states"])} for run in runs],
                "items_by_group_and_run": dict(sorted(groups.items())),
                "code_sha256": code, "matplotlib": matplotlib.__version__, "numpy": np.__version__,
                "extra": {"oct17_numeric_summary": None, "flow_states": flow_states},
                "identical_arrays_hard_linked": linked, "truth_withheld_from_model": True,
                "model_name_in_bodies": pt.DEFAULT_MODEL,
                "note": "Each state is drawn once (frames/<run>/<time>/) and used by every triple that "
                        "has it. The runner replaces only the model name."}
    write_json(builder.output / "manifest.json", manifest)
    print(encode_json({"output": str(builder.output), "requests": len(builder.entries),
                       "items_by_group_and_run": manifest["items_by_group_and_run"]}).decode())
    return 0


# ---------------------------------------------------------------- report

def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def answers_of(run_dir, truth):
    """{name: answer word or None (no valid answer)} of one model's run, and its model alias."""
    meta = json.loads((Path(run_dir) / "run.json").read_text())
    rows = _rows(Path(run_dir) / SET / "metrics.jsonl")
    answers = {}
    for row in rows:
        if f"{SET}/{row['name']}" not in truth:
            raise ValueError(f"{row['name']}: not in the answer key")
        answers[row["name"]] = row["structured_output"]["stability"] if row["successful_response"] else None
    return meta["model"], answers


def rule_answers(truth, measure, threshold):
    return {name.split("/", 1)[1]: ("unstable" if key["numeric"][measure] > threshold else "stable")
            for name, key in truth.items()}


def score(answers, keys):
    """Counts on the scored items (balanced classes) for one set of answers."""
    scored = {n: k for n, k in keys.items() if k["scored"]}
    out = {"items": len(scored), "answered": sum(answers.get(n) is not None for n in scored),
           "right": sum(answers.get(n) == k["stability"] for n, k in scored.items())}
    for word in ("unstable", "stable"):
        group = [n for n, k in scored.items() if k["stability"] == word]
        out[f"{word}_items"] = len(group)
        out[f"{word}_said"] = {w: sum(answers.get(n) == w for n in group) for w in ("unstable", "stable", "cannot_tell")}
        out[f"{word}_said"]["no answer"] = sum(answers.get(n) is None for n in group)
    return out


def early_table(answers, keys):
    """Items from runs that crashed, by steps from the last frame to the crash: said unstable / items."""
    out = []
    for lo, hi in EARLY_BINS:
        group = [n for n, k in keys.items() if k["stability"] == "unstable" and lo <= k["steps_to_crash_last"] <= hi]
        out.append({"bin": f"{lo}" if lo == hi else (f"{lo} to {hi}" if hi < 10 ** 8 else f"over {lo - 1}"),
                    "items": len(group), "said_unstable": sum(answers.get(n) == "unstable" for n in group)})
    return out


def by_run(answers, keys, word):
    runs = sorted({k["run"] for k in keys.values() if k["stability"] == word and k["scored"]})
    return {run: [sum(answers.get(n) == "unstable" for n, k in keys.items() if k["run"] == run and k["scored"]),
                  sum(1 for k in keys.values() if k["run"] == run and k["scored"])] for run in runs}


def best_threshold(keys, measure, above=None):
    """The threshold (between two observed ratios) with the most right answers on the scored
    items: an optimistic bound, since it is chosen on the same items. above: only thresholds
    above this value (1: growth only)."""
    scored = [k for k in keys.values() if k["scored"]]
    values = sorted({k["numeric"][measure] for k in scored})
    best = None
    for a, b in zip([0.0] + values, values + [values[-1] * 2]):
        cut = (a + b) / 2
        if above is not None and cut <= above:
            continue
        right = sum((k["numeric"][measure] > cut) == (k["stability"] == "unstable") for k in scored)
        if best is None or right > best[1]:
            best = (cut, right)
    return {"threshold": best[0], "right": best[1], "items": len(scored)}


def _cell(text):
    """Table cell text: a pipe (as in |U|) written as \\| so the Markdown table stays whole."""
    return str(text).replace("|", "\\|")


def report(args):
    test_set = Path(args.test_set) if args.test_set else None
    models, incomplete, key_hashes = [], 0, set()
    for run_dir in args.runs:
        meta = json.loads((Path(run_dir) / "run.json").read_text())
        root = test_set or Path(meta["test_set"])
        data = (root / "truth.private.json").read_bytes()
        key_hashes.add(pt.sha256(data))
        if meta.get("truth_sha256") not in (None, pt.sha256(data)):
            raise SystemExit(f"{run_dir}: {root / 'truth.private.json'} is not the answer key this run was made with")
        if len(key_hashes) > 1:
            raise SystemExit(f"{run_dir}: another answer key than the run folders before it; report them separately")
        truth = json.loads(data)
        if not (Path(run_dir) / SET / "metrics.jsonl").exists():
            incomplete += 1
            models.append((meta["model"], None))
            continue
        models.append(answers_of(run_dir, truth))
    keys = {name.split("/", 1)[1]: key for name, key in truth.items() if name.startswith(SET + "/")}
    columns = [(model, answers) for model, answers in models if answers is not None]
    rules = [(f"peak |U| grows > {round(100 * (t - 1))} %", rule_answers(truth, "max_speed_last_over_first", t))
             for t in SPEED_RULES]
    rules += [(f"largest |U| jump grows > {round(100 * (t - 1))} %",
               rule_answers(truth, "max_jump_speed_last_over_first", t)) for t in JUMP_RULES]
    scored = [k for k in keys.values() if k["scored"]]
    fixed = max(Counter(k["stability"] for k in scored).values())
    n_unstable = sum(k["stability"] == "unstable" for k in scored)
    n_stable = len(scored) - n_unstable
    lines = [f"Balanced score: {len(scored)} scored items, {n_unstable} 'unstable' (last frame 1 to "
             f"{max(k['steps_to_crash_last'] for k in scored if k['stability'] == 'unstable')} steps before the "
             f"crash) and {n_stable} 'stable'; a fixed answer gets {fixed}/{len(scored)}.", "",
             "| answers from | answered | right | unstable said unstable | unstable said stable | unstable cannot_tell "
             "| stable said stable | stable said unstable | stable cannot_tell |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for label, answers in [(m, a) for m, a in columns] + rules:
        s = score(answers, keys)
        u, t = s["unstable_said"], s["stable_said"]
        lines.append(f"| {_cell(label)} | {s['answered']}/{s['items']} | {s['right']}/{s['items']} | "
                     f"{u['unstable']}/{s['unstable_items']} | {u['stable']} | {u['cannot_tell']} | "
                     f"{t['stable']}/{s['stable_items']} | {t['unstable']} | {t['cannot_tell']} |")
    for model, answers in models:
        if answers is None:
            lines.append(f"| {model} | no metrics (run incomplete) | | | | | | | |")
    for measure, label in (("max_speed_last_over_first", "peak |U|"), ("max_jump_speed_last_over_first", "largest |U| jump")):
        best, grows = best_threshold(keys, measure), best_threshold(keys, measure, above=1.0)
        lines.append(f"\nBest single threshold on the {label} ratio (last / first frame), chosen on these items: "
                     f"{best['threshold']:.4g}, {best['right']}/{best['items']} right; above 1 (growth) only: "
                     f"{grows['threshold']:.4g}, {grows['right']}/{grows['items']} right.")
    header = "| last frame, steps before the crash | items | " + " | ".join(_cell(m) for m, _ in columns) + \
             " | " + " | ".join(_cell(label) for label, _ in rules) + " |"
    lines += ["", "How early 'unstable' is said: items from the runs that crashed (scored and early), "
              "said unstable / items.", "", header,
              "|---|---:|" + "---:|" * (len(columns) + len(rules))]
    tables = [early_table(a, keys) for _, a in columns] + [early_table(a, keys) for _, a in rules]
    for b, row in enumerate(tables[0] if tables else []):
        lines.append(f"| {row['bin']} | {row['items']} | " + " | ".join(str(t[b]["said_unstable"]) for t in tables) + " |")
    lines += ["", "Said unstable / scored items, by run.", "",
              "| run | truth | " + " | ".join(_cell(m) for m, _ in columns) + " | "
              + " | ".join(_cell(rules[i][0]) for i in BY_RUN_RULES) + " |",
              "|---|---|" + "---:|" * (len(columns) + len(BY_RUN_RULES))]
    for word in ("unstable", "stable"):
        tables = [by_run(a, keys, word) for _, a in columns] + [by_run(rules[i][1], keys, word) for i in BY_RUN_RULES]
        for run in tables[0]:
            lines.append(f"| {run} | {word} | " + " | ".join(f"{t[run][0]}/{t[run][1]}" for t in tables) + " |")
    lines += ["", "Every item: steps from the last frame to the crash (blank: a run that ended), the two "
              "numeric ratios and each answer (u unstable, s stable, ? cannot_tell, - no answer).", "",
              "| item | truth | scored | steps to crash | peak \\|U\\| ratio | jump ratio | "
              + " | ".join(_cell(m) for m, _ in columns) + " |",
              "|---|---|---|---:|---:|---:|" + "---|" * len(columns)]
    mark = {"unstable": "u", "stable": "s", "cannot_tell": "?", None: "-"}
    for name, key in sorted(keys.items(), key=lambda kv: (kv[1]["stability"] != "unstable", kv[1]["run"],
                                                          kv[1]["steps_to_crash_last"] or 0, kv[0])):
        lines.append(f"| {name} | {key['stability']} | {'yes' if key['scored'] else 'no'} | "
                     f"{'' if key['steps_to_crash_last'] is None else key['steps_to_crash_last']} | "
                     f"{key['numeric']['max_speed_last_over_first']:.4g} | {key['numeric']['max_jump_speed_last_over_first']:.4g} | "
                     + " | ".join(mark[a.get(name)] for _, a in columns) + " |")
    text = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 1 if incomplete else 0


def main(argv=None):
    """picture_test's set lists hold only this set while the command runs (so 'run' without
    --sets sends only this set) and are restored afterwards, also after an error, so other
    code in the same process (other tests) keeps its own."""
    argv = sys.argv[1:] if argv is None else argv
    saved = pt.SETS, pt.PAIRED_SETS
    pt.SETS, pt.PAIRED_SETS = NEW_SETS, ()
    try:
        return _command(argv)
    finally:
        pt.SETS, pt.PAIRED_SETS = saved


def _command(argv):
    if argv and argv[0] == "build":
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("command")
        parser.add_argument("--design", required=True, help="JSON: window_m and runs (name, case, "
                            "stable_items or early_steps_to_crash, optional first_time_s)")
        parser.add_argument("--centres", required=True, help="fields.npz of a saved frame of the same mesh")
        parser.add_argument("--within", type=int, default=WITHIN, help="steps before the crash counted 'unstable'")
        parser.add_argument("--margin", type=int, default=MARGIN, help="steps a stable triple ends before its run's end")
        parser.add_argument("--seed", type=int, default=SEED)
        parser.add_argument("--output", required=True, help="new directory")
        return build(parser.parse_args(argv))
    if argv and argv[0] == "report":
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("command")
        parser.add_argument("runs", nargs="+")
        parser.add_argument("--test-set", help="test set with truth.private.json (default: the one in run.json)")
        parser.add_argument("--output")
        return report(parser.parse_args(argv))
    return pt.main(argv)


if __name__ == "__main__":
    sys.exit(main())
