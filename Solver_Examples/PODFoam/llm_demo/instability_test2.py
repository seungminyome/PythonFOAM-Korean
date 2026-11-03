#!/usr/bin/env python3
"""Instability test, second round (2026-11-01): the stated times removed.

The set of 2026-10-28 (instability_test.py) states each frame's step and time in the note, the
captions and the picture titles, and the time between frames alone separates the two classes.
Here no request states a step or a time, the picture titles have none, and the text parts of
every request in a set are byte-identical, so only the pictures differ between items.

  instability-eq2ms-notime    (A0) triples whose frames are gap_s (2e-3 s) apart in physical time
                              in both classes: central-dt2e-5 (every step written, crash in step
                              467) gives the unstable triples at run steps (last-200, last-100,
                              last); the ended runs give the stable ones at the same spacing.
  instability-eq2ms-reltime   (A1) the same triples and pictures; the note and captions state
                              t - t1 = 0, gap_s, 2 gap_s, the same string in every item.
  instability-oct28-notime    (B0) the 70 triples of 2026-10-28 (run steps from its manifest),
                              drawn again without times.

build:  python3 instability_test2.py build --design <design2.json> --centres <fields.npz> \\
            --oct28-manifest <manifest.json of the 2026-10-28 set> --output <new dir>
check / run: as picture_test.py, with these sets.
report: python3 instability_test2.py report <run dir>... [--oct28 <results dir of 2026-10-28>]
        the balanced score, flagged counts, the array rules, how early 'unstable' is said, by run,
        the best thresholds (optimistic), and for B0 the item-by-item change against the
        2026-10-28 answers of the same model alias.
"""
import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import numpy as np

import foam_fields
import instability_test as it
import picture_test as pt
import stability_request
from llm_client import DEFAULT_MODEL, _finish_request, _image_part, encode_json, write_json
from readable_request import AXES, MAX_FRAMES, MAX_TOKENS, SEED

SET_A0 = "instability-eq2ms-notime"
SET_A1 = "instability-eq2ms-reltime"
SET_B0 = "instability-oct28-notime"
NEW_SETS = (SET_A0, SET_A1, SET_B0)
TEST_NAME = "instability test 2026-11-01, times removed"
SEED_BUILD = 20261101
OLD_SET = it.SET


# ---------------------------------------------------------------- request

def payload(frames, relative_times=None, model=DEFAULT_MODEL, seed=SEED):
    """The stability request without steps or times. relative_times: t - t1 of each frame in
    seconds, stated in the note and the captions (set A1); None states nothing."""
    if len(frames) != 3 or len(frames) > MAX_FRAMES:
        raise ValueError("three frames")
    header = {"task": "judge whether the run shows signs of numerical instability",
              "times": len(frames), "images": 2 * len(frames),
              "frames": [{"time": k + 1, "images": [2 * k + 1, 2 * k + 2]} for k in range(len(frames))],
              "plotted_axes": AXES, "plotted_range_m": frames[0]["plotted_range_m"]}
    if relative_times is not None:
        for entry, value in zip(header["frames"], relative_times):
            entry["t_minus_t1_s"] = float(value)
    content = [{"type": "text", "text": encode_json(header).decode("utf-8")}]
    for k, f in enumerate(frames):
        when = f"Time {k + 1}." if relative_times is None else \
            f"Time {k + 1}: t - t1 = {float(relative_times[k]):g} s."
        content += [{"type": "text", "text": f"{when} Image {2 * k + 1}: |U| in m/s."},
                    _image_part(f["images"]["U"]),
                    {"type": "text", "text": f"Image {2 * k + 2}: p in m^2/s^2."},
                    _image_part(f["images"]["p"])]
    request = _finish_request(stability_request.STABILITY_V2OWN_SYSTEM_PROMPT, content, "stability")
    request.update(model=model, seed=seed, max_tokens=MAX_TOKENS, cache_prompt=False)
    return request


def text_parts(request):
    """Every text the model receives, in order (system prompt and text parts)."""
    out = []
    for message in request["messages"]:
        content = message.get("content")
        if isinstance(content, str):
            out.append(content)
        else:
            out += [part["text"] for part in content if part.get("type") == "text"]
    return out


# ---------------------------------------------------------------- triples

def _by_step(run):
    return {s["run_step"]: s for s in run["states"]}


def crashed_triples_fixed_gap(run, steps_to_crash, gap_steps, scored):
    """One triple per steps-to-crash value with frames gap_steps run steps apart, all written."""
    by_step = _by_step(run)
    out = []
    for s in steps_to_crash:
        last = run["crash_step"] - s
        steps = [last - 2 * gap_steps, last - gap_steps, last]
        if steps[0] < 1 or any(k not in by_step for k in steps):
            raise ValueError(f"{run['name']}: no written triple ending {s} steps before the crash with gap {gap_steps}")
        out.append({"run": run["name"], "frames": [by_step[k] for k in steps], "gap_run_steps": gap_steps,
                    "stability": "unstable", "scored": scored,
                    "group": "unstable-last" if scored else "unstable-early"})
    return out


def stable_triples_fixed_gap(run, count, gap_states, rng, margin, first_time_s=0.0):
    """count triples of written states gap_states apart, spread over the run as
    instability_test.stable_triples does (equal parts, one start drawn in each)."""
    states = [s for s in run["states"] if s["time_s"] >= first_time_s - 1e-12]
    spacing = np.diff([s["time_s"] for s in states])
    if not np.allclose(spacing, spacing[0], rtol=1e-6, atol=1e-9):
        raise ValueError(f"{run['name']}: written states are not evenly spaced in time")
    usable = [s for s in states if s["run_step"] <= run["logged_steps"] - margin]
    last_start = len(usable) - 1 - 2 * gap_states
    if last_start < count - 1:
        raise ValueError(f"{run['name']}: too few written states for {count} triples")
    out = []
    for j in range(count):
        lo, hi = j * (last_start + 1) // count, (j + 1) * (last_start + 1) // count
        start = int(rng.integers(lo, hi))
        triple = (start, start + gap_states, start + 2 * gap_states)
        out.append({"run": run["name"], "frames": [usable[i] for i in triple],
                    "gap_written_states": gap_states,
                    "gap_run_steps": usable[triple[1]]["run_step"] - usable[triple[0]]["run_step"],
                    "stability": "stable", "scored": True, "group": "stable"})
    return out


def oct28_triples(manifest, runs_by_name):
    """The triples of the 2026-10-28 set, by run and run steps, from its manifest."""
    out = []
    for entry in manifest["requests"]:
        if entry["set"] != OLD_SET:
            continue
        design = entry["design"]
        run = runs_by_name[design["run"]]
        by_step = _by_step(run)
        steps = design["run_steps"]
        if any(k not in by_step for k in steps):
            raise ValueError(f"{entry['name']}: a state of the 2026-10-28 triple is not written")
        out.append({"run": run["name"], "frames": [by_step[k] for k in steps],
                    "gap_run_steps": design["gap_run_steps"],
                    "stability": "stable" if design["group"] == "stable" else "unstable",
                    "scored": design["group"] != "unstable-early", "group": design["group"],
                    "name": entry["name"]})
    return out


# ---------------------------------------------------------------- build

def _gap_states(run, gap_s, first_time_s=0.0):
    states = [s for s in run["states"] if s["time_s"] >= first_time_s - 1e-12]
    spacing = states[1]["time_s"] - states[0]["time_s"]
    ratio = gap_s / spacing
    if abs(ratio - round(ratio)) > 1e-6:
        raise ValueError(f"{run['name']}: gap {gap_s} s is not a whole number of written states ({spacing} s)")
    return int(round(ratio))


def build(args):
    import matplotlib
    import pod_image
    for name in ("design", "centres", "output", "oct28_manifest"):
        setattr(args, name, str(Path(getattr(args, name)).resolve()))
    design = json.loads(Path(args.design).read_text())
    old_manifest = json.loads(Path(args.oct28_manifest).read_text())
    gap_s = float(design["gap_s"])
    repo = Path(__file__).resolve().parents[3]
    roots = [(repo, "")]
    for entry in design["runs"]:
        root = it._flow_root(entry["case"])
        if all(root != r for r, _ in roots):
            roots.append((root, root.name + "/"))
    builder = pt.Builder(args.output, roots=roots)
    pod_image.prepare_backend(builder.output / ".mpl")
    window = [[float(v) for v in pair] for pair in design.get("window_m", it.WINDOW_M)]
    runs = [it.read_run(entry["name"], entry["case"]) for entry in design["runs"]]
    runs_by_name = {run["name"]: run for run in runs}
    first_mesh = runs[0]["case"] / "constant" / "polyMesh"
    mesh = pt.Mesh(first_mesh, args.centres)
    for run in runs[1:]:
        other = {name: pt.file_sha256(run["case"] / "constant" / "polyMesh" / name)
                 for name in ("boundary", "faces", "owner", "points")}
        if other != mesh.sources["polymesh"]:
            raise ValueError(f"{run['name']}: another mesh")
    mesh.views["window"] = window
    faces = it.Faces(first_mesh, mesh.centres, window)
    rng = np.random.default_rng(args.seed)
    # set A: equal spacing in seconds in both classes
    items_a, gaps = [], {}
    for entry, run in zip(design["runs"], runs):
        if not entry.get("in_eq_set", True):
            continue
        if not run["ended"]:
            if run["adaptive_time_step"]:
                raise ValueError(f"{run['name']}: adaptive time step in a crashed run")
            gap_steps = gap_s / run["delta_t_s"]
            if abs(gap_steps - round(gap_steps)) > 1e-6:
                raise ValueError(f"{run['name']}: gap {gap_s} s is not a whole number of steps")
            gap_steps = int(round(gap_steps))
            gaps[run["name"]] = {"run_steps": gap_steps}
            items_a += crashed_triples_fixed_gap(run, range(1, args.within + 1), gap_steps, True)
            items_a += crashed_triples_fixed_gap(run, [int(s) for s in entry.get("early_steps_to_crash", [])],
                                                 gap_steps, False)
        else:
            first = float(entry.get("first_time_s", 0.0))
            g = _gap_states(run, gap_s, first)
            gaps[run["name"]] = {"written_states": g}
            items_a += stable_triples_fixed_gap(run, int(entry["stable_items"]), g, rng, args.margin, first)
    items_b = oct28_triples(old_manifest, runs_by_name)
    # frames: each state drawn once, without step and time, shared by every set
    frames_done, numbers, flow_states = {}, {}, {}

    def frame_of(run, state):
        state_key = f"{run['name']}/{state['time_name']}"
        if state_key not in frames_done:
            velocity = foam_fields.read_internal_field(state["path"] / "U", mesh.cells)
            pressure = foam_fields.read_internal_field(state["path"] / "p", mesh.cells)
            frames_done[state_key] = pt.render_v2(mesh, "window", velocity, pressure, state["step"],
                                                  state["time_s"], builder.frame_dir(run["name"], state["time_name"]),
                                                  show_time=False)
            numbers[state_key] = it.state_numbers(faces, velocity, pressure)
            flow_states[state_key] = {"time_dir": builder.rel(state["path"]),
                                      "U_sha256": pt.file_sha256(state["path"] / "U"),
                                      "p_sha256": pt.file_sha256(state["path"] / "p")}
        return frames_done[state_key], numbers[state_key]

    def add(set_name, item, relative_times):
        run = runs_by_name[item["run"]]
        frames, truths = [], []
        for state in item["frames"]:
            (frame, truth), nums = frame_of(run, state)
            frames.append(frame)
            truths.append(dict(truth, **nums, run_step=state["run_step"], courant_max=state["courant_max"],
                               steps_to_crash=(run["crash_step"] - state["run_step"]) if run["crash_step"] else None,
                               steps_after_in_run=None if run["crash_step"] else run["logged_steps"] - state["run_step"]))
        run_steps = [s["run_step"] for s in item["frames"]]
        times = [s["time_s"] for s in item["frames"]]
        name = item.get("name") or f"{run['name']}-steps{'-'.join(f'{k:05d}' for k in run_steps)}"
        key = {"stability": item["stability"], "scored": item["scored"], "group": item["group"],
               "run": run["name"], "scheme_div_phi_U": run["scheme_div_phi_U"], "delta_t_s": run["delta_t_s"],
               "adaptive_time_step": run["adaptive_time_step"], "crash_step": run["crash_step"],
               "logged_steps": run["logged_steps"], "gap_run_steps": item["gap_run_steps"],
               "gap_s": [times[1] - times[0], times[2] - times[1]],
               "steps_to_crash_last": truths[-1]["steps_to_crash"],
               "plotted_range_m": {"x": window[0], "y": window[1]},
               "cells_in_window": truths[0]["cells_in_window"],
               "numeric": it.numeric_ratios(truths),
               "frames": [{k: t[k] for k in ("step", "time_s", "run_step", "courant_max", "steps_to_crash",
                                             "steps_after_in_run", "max_speed_m_per_s", "min_pressure_m2_per_s2",
                                             "max_pressure_m2_per_s2", "max_speed_domain_m_per_s",
                                             "max_jump_speed_m_per_s", "max_jump_pressure_m2_per_s2")}
                          | {"fastest_flow_percent": [t["fastest_flow"]["x_percent"], t["fastest_flow"]["y_percent"]]}
                          for t in truths]}
        sources = {"frames": [f["directory"] for f in frames],
                   "states": [f"{run['name']}/{s['time_name']}" for s in item["frames"]]}
        item_design = {"run": run["name"], "group": item["group"], "run_steps": run_steps, "times_s": times,
                       "steps_to_crash_last": key["steps_to_crash_last"], "gap_run_steps": item["gap_run_steps"],
                       "times_stated": relative_times is not None}
        builder.add(set_name, name, "stability", payload(frames, relative_times), key, sources, item_design)

    relative = [0.0, gap_s, 2 * gap_s]
    for item in items_a:
        add(SET_A0, item, None)
    for item in items_a:
        add(SET_A1, item, relative)
    for item in items_b:
        add(SET_B0, item, None)
    write_json(builder.output / "truth.private.json", builder.truth)
    shutil.rmtree(builder.output / ".mpl", ignore_errors=True)
    linked = pt.link_duplicate_arrays(builder.output / "frames")
    # the text the model sees must be the same in every item of a set
    identity = {}
    for set_name in NEW_SETS:
        texts = set()
        for entry in builder.entries:
            if entry["set"] == set_name:
                parts = text_parts(json.loads((builder.output / entry["file"]).read_bytes()))
                texts.add(hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest())
                for part in parts:
                    for word in ("time_s", "step", "t = ", "t=") if set_name != SET_A1 else ("time_s", "step"):
                        if word in part:
                            raise ValueError(f"{set_name}/{entry['name']}: '{word}' in the text")
        if len(texts) != 1:
            raise ValueError(f"{set_name}: the text differs between items ({len(texts)} variants)")
        identity[set_name] = {"items": sum(e["set"] == set_name for e in builder.entries),
                              "text_variants": len(texts), "text_sha256": texts.pop(),
                              "note": "SHA-256 over the system prompt and every text part, joined by U+001F; "
                                      "one variant means every item of the set sends the same text"}
    here = Path(__file__).resolve().parent
    code = {name: pt.file_sha256(here / name) for name in
            ("instability_test2.py", "instability_test.py", "stability_request.py", "picture_test.py",
             "frame_scoring.py", "readable_image.py", "readable_request.py", "foam_fields.py", "pod_image.py",
             "snapshot_runner.py", "llm_client.py")}
    groups = Counter(f"{e['set']} {e['design']['group']} {e['design']['run']}" for e in builder.entries)
    manifest = {"schema_version": 2, "test": f"{TEST_NAME} (seed {args.seed})", "seed": args.seed,
                "max_tokens": pt.MAX_TOKENS,
                "sets": {s: sum(e["set"] == s for e in builder.entries) for s in NEW_SETS},
                "requests": builder.entries,
                "truth_sha256": pt.file_sha256(builder.output / "truth.private.json"),
                "build_args": dict(builder.rel(vars(args)), output=Path(args.output).name),
                "design": design, "design_sha256": pt.file_sha256(args.design),
                "oct28_manifest_sha256": pt.file_sha256(args.oct28_manifest),
                "gap_s": gap_s, "gap_by_run": gaps,
                "path_prefixes": {"": "frames/ and requests/ are in this test set, docs/ is the repository"}
                | {prefix: "a folder of pimpleFoam runs" for _, prefix in roots[1:]},
                "mesh": builder.rel(mesh.sources), "plotted_range_m": {"x": window[0], "y": window[1]},
                "label_rule": {"unstable_within_steps": args.within, "stable_margin_steps": args.margin,
                               "note": "as on 2026-10-28: a run crashed when its log has a floating point "
                                       "exception trace and no 'End'; its triples ending 1 to "
                                       "unstable_within_steps steps before the crash are scored 'unstable', "
                                       "earlier ones are not scored; runs that ended give 'stable' triples"},
                "text_identity": identity,
                "pictures": "no step and no time in the titles or the PNG metadata (show_time=False)",
                "runs": [{k: builder.rel(str(run[k])) if k == "case" else run[k]
                          for k in ("name", "case", "scheme_div_phi_U", "delta_t_s", "adaptive_time_step",
                                    "start_time_s", "logged_steps", "ended", "crash_step", "courant_max_logged")}
                         | {"written_states": len(run["states"])} for run in runs],
                "items_by_set_group_and_run": dict(sorted(groups.items())),
                "code_sha256": code, "matplotlib": matplotlib.__version__, "numpy": np.__version__,
                "extra": {"oct17_numeric_summary": None, "flow_states": flow_states},
                "identical_arrays_hard_linked": linked, "truth_withheld_from_model": True,
                "model_name_in_bodies": pt.DEFAULT_MODEL,
                "note": "Each state is drawn once (frames/<run>/<time>/) and used by every triple of every "
                        "set that has it. The runner replaces only the model name."}
    write_json(builder.output / "manifest.json", manifest)
    print(encode_json({"output": str(builder.output), "requests": len(builder.entries),
                       "sets": manifest["sets"], "gap_by_run": gaps, "text_identity": identity,
                       "items_by_set_group_and_run": manifest["items_by_set_group_and_run"]}).decode())
    return 0


# ---------------------------------------------------------------- report

def answers_of(run_dir, set_name, truth):
    meta = json.loads((Path(run_dir) / "run.json").read_text())
    path = Path(run_dir) / set_name / "metrics.jsonl"
    if not path.exists():
        return meta["model"], None, {}
    answers, reasons = {}, {}
    for row in it._rows(path):
        if f"{set_name}/{row['name']}" not in truth:
            raise ValueError(f"{row['name']}: not in the answer key")
        answers[row["name"]] = row["structured_output"]["stability"] if row["successful_response"] else None
        reasons[row["name"]] = row["structured_output"]["reason"] if row["successful_response"] else None
    return meta["model"], answers, reasons


def rules_of(keys):
    rules = [(f"peak |U| grows > {round(100 * (t - 1))} %", "max_speed_last_over_first", t) for t in it.SPEED_RULES]
    rules += [(f"largest |U| jump grows > {round(100 * (t - 1))} %", "max_jump_speed_last_over_first", t)
              for t in it.JUMP_RULES]
    return [(label, {n: ("unstable" if k["numeric"][m] > t else "stable") for n, k in keys.items()})
            for label, m, t in rules]


def oct28_answers(oct28_dir, alias):
    """{item name: answer} of the 2026-10-28 run whose run.json names this model alias."""
    for run_dir in sorted(Path(oct28_dir).iterdir()):
        meta_path = run_dir / "run.json"
        if meta_path.exists() and json.loads(meta_path.read_text())["model"] == alias:
            rows = it._rows(run_dir / OLD_SET / "metrics.jsonl")
            return {r["name"]: (r["structured_output"]["stability"] if r["successful_response"] else None) for r in rows}
    return None


def report(args):
    test_set = Path(args.test_set) if args.test_set else None
    data = None
    for run_dir in args.runs:
        meta = json.loads((Path(run_dir) / "run.json").read_text())
        root = test_set or Path(meta["test_set"])
        this = (root / "truth.private.json").read_bytes()
        if meta.get("truth_sha256") not in (None, pt.sha256(this)):
            raise SystemExit(f"{run_dir}: {root / 'truth.private.json'} is not the answer key this run was made with")
        if data is not None and this != data:
            raise SystemExit(f"{run_dir}: another answer key than the run folders before it")
        data = this
    truth = json.loads(data)
    lines, out = [f"# {TEST_NAME}", ""], {"sets": {}}
    mark = {"unstable": "u", "stable": "s", "cannot_tell": "?", None: "-"}
    for set_name in NEW_SETS:
        keys = {name.split("/", 1)[1]: key for name, key in truth.items() if name.startswith(set_name + "/")}
        if not keys:
            continue
        columns = []
        for run_dir in args.runs:
            model, answers, reasons = answers_of(run_dir, set_name, truth)
            columns.append((model, answers, reasons))
        rules = rules_of(keys)
        scored = [k for k in keys.values() if k["scored"]]
        n_unstable = sum(k["stability"] == "unstable" for k in scored)
        block = {"scored_items": len(scored), "unstable_items": n_unstable, "stable_items": len(scored) - n_unstable,
                 "fixed_answer_right": max(Counter(k["stability"] for k in scored).values()),
                 "answers": {}, "rules": {}, "early": {}, "by_run": {}, "best_threshold": {}, "items": {}}
        lines += [f"## {set_name}", "",
                  f"Balanced score: {len(scored)} scored items, {n_unstable} 'unstable' and {len(scored) - n_unstable} "
                  f"'stable'; a fixed answer gets {block['fixed_answer_right']}/{len(scored)}.", "",
                  "| answers from | answered | right | flagged of crash-bound (said unstable) | crash-bound said stable "
                  "| crash-bound cannot_tell | flagged of normal (said unstable) | normal said stable | normal cannot_tell |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for label, answers in [(m, a) for m, a, _ in columns if a is not None] + rules:
            s = it.score(answers, keys)
            u, t = s["unstable_said"], s["stable_said"]
            (block["answers"] if any(label == m for m, _, _ in columns) else block["rules"])[label] = s
            lines.append(f"| {it._cell(label)} | {s['answered']}/{s['items']} | {s['right']}/{s['items']} | "
                         f"{u['unstable']}/{s['unstable_items']} | {u['stable']} | {u['cannot_tell']} | "
                         f"{t['unstable']}/{s['stable_items']} | {t['stable']} | {t['cannot_tell']} |")
        for model, answers, _ in columns:
            if answers is None:
                lines.append(f"| {model} | no metrics (run incomplete) | | | | | | | |")
        for measure, label in (("max_speed_last_over_first", "peak |U|"), ("max_jump_speed_last_over_first", "largest |U| jump")):
            best, grows = it.best_threshold(keys, measure), it.best_threshold(keys, measure, above=1.0)
            block["best_threshold"][measure] = {"any": best, "growth_only": grows}
            lines.append(f"\nBest single threshold on the {label} ratio (last / first frame), chosen on these items: "
                         f"{best['threshold']:.4g}, {best['right']}/{best['items']} right; above 1 (growth) only: "
                         f"{grows['threshold']:.4g}, {grows['right']}/{grows['items']} right.")
        answer_columns = [(m, a) for m, a, _ in columns if a is not None]
        header = "| last frame, steps before the crash | items | " + " | ".join(it._cell(m) for m, _ in answer_columns) + \
                 " | " + " | ".join(it._cell(label) for label, _ in rules) + " |"
        lines += ["", "How early 'unstable' is said: items from the runs that crashed (scored and early), "
                  "said unstable / items.", "", header, "|---|---:|" + "---:|" * (len(answer_columns) + len(rules))]
        tables = [it.early_table(a, keys) for _, a in answer_columns] + [it.early_table(a, keys) for _, a in rules]
        for b, row in enumerate(tables[0] if tables else []):
            lines.append(f"| {row['bin']} | {row['items']} | " + " | ".join(str(t[b]["said_unstable"]) for t in tables) + " |")
        block["early"] = {label: it.early_table(a, keys) for label, a in answer_columns + rules}
        lines += ["", "Said unstable / scored items, by run.", "",
                  "| run | truth | " + " | ".join(it._cell(m) for m, _ in answer_columns) + " | "
                  + " | ".join(it._cell(rules[i][0]) for i in it.BY_RUN_RULES) + " |",
                  "|---|---|" + "---:|" * (len(answer_columns) + len(it.BY_RUN_RULES))]
        for word in ("unstable", "stable"):
            tables = [it.by_run(a, keys, word) for _, a in answer_columns] + [it.by_run(rules[i][1], keys, word) for i in it.BY_RUN_RULES]
            block["by_run"][word] = {label: it.by_run(a, keys, word) for label, a in answer_columns}
            for run in tables[0]:
                lines.append(f"| {run} | {word} | " + " | ".join(f"{t[run][0]}/{t[run][1]}" for t in tables) + " |")
        if set_name == SET_B0 and args.oct28:
            lines += ["", "Against the 2026-10-28 answers of the same model (same triples, times stated then): "
                      "items whose answer changed.", "",
                      "| model | items compared | same answer | was stable, now unstable | was unstable, now stable | other change |",
                      "|---|---:|---:|---:|---:|---:|"]
            block["against_oct28"] = {}
            for model, answers in answer_columns:
                old = oct28_answers(args.oct28, model)
                if old is None:
                    lines.append(f"| {model} | no 2026-10-28 run with this alias | | | | |")
                    continue
                names = sorted(set(old) & set(answers))
                same = sum(old[n] == answers[n] for n in names)
                s2u = [n for n in names if old[n] == "stable" and answers[n] == "unstable"]
                u2s = [n for n in names if old[n] == "unstable" and answers[n] == "stable"]
                other = len(names) - same - len(s2u) - len(u2s)
                block["against_oct28"][model] = {"items": len(names), "same": same, "stable_to_unstable": s2u,
                                                 "unstable_to_stable": u2s, "other": other}
                lines.append(f"| {it._cell(model)} | {len(names)} | {same} | {len(s2u)} | {len(u2s)} | {other} |")
        lines += ["", "Every item: steps from the last frame to the crash (blank: a run that ended), the two "
                  "numeric ratios and each answer (u unstable, s stable, ? cannot_tell, - no answer).", "",
                  "| item | truth | scored | steps to crash | peak \\|U\\| ratio | jump ratio | "
                  + " | ".join(it._cell(m) for m, _ in answer_columns) + " |",
                  "|---|---|---|---:|---:|---:|" + "---|" * len(answer_columns)]
        for name, key in sorted(keys.items(), key=lambda kv: (kv[1]["stability"] != "unstable", kv[1]["run"],
                                                              kv[1]["steps_to_crash_last"] or 0, kv[0])):
            block["items"][name] = {"truth": key["stability"], "scored": key["scored"], "run": key["run"],
                                    "steps_to_crash_last": key["steps_to_crash_last"], "numeric": key["numeric"],
                                    "answers": {m: a.get(name) for m, a in answer_columns},
                                    "reasons": {m: r.get(name) for m, a, r in columns if a is not None}}
            lines.append(f"| {name} | {key['stability']} | {'yes' if key['scored'] else 'no'} | "
                         f"{'' if key['steps_to_crash_last'] is None else key['steps_to_crash_last']} | "
                         f"{key['numeric']['max_speed_last_over_first']:.4g} | {key['numeric']['max_jump_speed_last_over_first']:.4g} | "
                         + " | ".join(mark[a.get(name)] for _, a in answer_columns) + " |")
        lines.append("")
        out["sets"][set_name] = block
    text = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(text)
        write_json(Path(args.output).with_suffix(".json"), out)
    print(text)
    return 0


def main(argv=None):
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
        parser.add_argument("--design", required=True)
        parser.add_argument("--centres", required=True)
        parser.add_argument("--oct28-manifest", required=True, help="manifest.json of the 2026-10-28 set")
        parser.add_argument("--within", type=int, default=it.WITHIN)
        parser.add_argument("--margin", type=int, default=it.MARGIN)
        parser.add_argument("--seed", type=int, default=SEED_BUILD)
        parser.add_argument("--output", required=True)
        return build(parser.parse_args(argv))
    if argv and argv[0] == "report":
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("command")
        parser.add_argument("runs", nargs="+")
        parser.add_argument("--test-set")
        parser.add_argument("--oct28", help="results folder of 2026-10-28 with <key>/run.json and <key>/instability-v2own/metrics.jsonl")
        parser.add_argument("--output")
        return report(parser.parse_args(argv))
    return pt.main(argv)


if __name__ == "__main__":
    sys.exit(main())
