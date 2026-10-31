#!/usr/bin/env python3
"""Recount the 2026-10-30 wrong-setup test from the recorded answers, the answer key and the gzipped
solver logs, without wrong_setup_test.py or picture_test.py, and compare with the report.

Run in this folder:  python3 recount.py   (standard library only; writes recount.json)

Inputs: test-set/truth.private.json (class, run, step and numbers of each frame),
test-set/manifest.json (the runs and their log numbers), test-set/leak-check.json,
test-set/request-text-example.json, results/<job>/<model>/wrong-setup-v2own/metrics.jsonl (one
parsed answer per request), flow/logs/<run>.log.gz, reports/combined.md, flow/frame-facts.json,
reason-judgement.json and README.md.

It recounts, per model: answered, right, the six answer cells, right by run and the mark of every
frame; the rule on the peak |U| from the key's numbers; each number's range over the normal frames
or logs and which wrong runs fall outside. It reads every log again: 8,000 steps, an End line, no
floating point exception, and the Courant numbers, residuals and continuity errors stored in the
key and the manifest. It checks the labels, that each step and time has 5 normal and 5 wrong
frames, and the leak check's text hashes. Every recomputed table line is looked up in the report.
Beyond the report: whether each model answers alike for the pairs of normal frames that show one
flow time (flow/normal-overlap.json), the answers by step, and how often a model's answers change
within a run.

What the counts rest on (recount.json: what_the_counts_rest_on; written after the answers were read,
so outside the design): 31B against the rule frame by frame and with runs left out, what its reasons
rest on, the checks that need no reference run, the colour-bar numbers alone (flow/frame-facts.json)
and the labels of reason-judgement.json against the recorded answers. Each table line of these is
looked up in README.md.
"""
import gzip
import hashlib
import json
from pathlib import Path
import re
import statistics

HERE = Path(__file__).resolve().parent
SET = "wrong-setup-v2own"
RIGHT = {"normal": "consistent", "wrong": "inconsistent"}
SPEED_REASON = re.compile(r"significantly lower|far below")
STEP_REASON = re.compile(r"no (evidence of a )?backward-facing step|without the geometry of a backward-facing step")
MARK = {"consistent": "c", "inconsistent": "i", "cannot_tell": "?", None: "-"}
INLET = 32.2
FRAME_NUMBERS = (("courant_max", "largest Courant number"), ("courant_mean", "mean Courant number"),
                 ("Ux_initial", "Ux initial residual"), ("Uy_initial", "Uy initial residual"),
                 ("p_initial", "p initial residual, first solve"),
                 ("Ux_final", "Ux final residual"), ("Uy_final", "Uy final residual"),
                 ("p_final", "p final residual, last solve"),
                 ("continuity_local", "continuity error, sum local"),
                 ("continuity_global_abs", "continuity error, global (absolute)"),
                 ("continuity_cumulative_abs", "continuity error, cumulative (absolute)"),
                 ("max_speed_m_per_s", "peak \\|U\\| in the window (m/s)"),
                 ("min_pressure_m2_per_s2", "lowest p in the window (m^2/s^2)"))
LOG_NUMBERS = (("courant_max_whole_run", "largest Courant number, whole run"),
               ("courant_max_from_first_frame", "largest Courant number, from the first frame on"),
               ("courant_mean_from_first_frame", "mean Courant number, from the first frame on"),
               ("last_Ux_initial", "Ux initial residual, last step"),
               ("last_Uy_initial", "Uy initial residual, last step"),
               ("last_p_initial", "p initial residual, first solve of the last step"),
               ("last_Ux_final", "Ux final residual, last step"),
               ("last_Uy_final", "Uy final residual, last step"),
               ("last_p_final", "p final residual, last solve of the last step"),
               ("last_continuity_local", "continuity error, sum local, last step"),
               ("last_continuity_global_abs", "continuity error, global (absolute), last step"),
               ("last_continuity_cumulative_abs", "continuity error, cumulative (absolute), last step"))


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def g(value):
    return f"{value:.4g}"


def span(low, high):
    return g(low) if g(low) == g(high) else f"{g(low)} to {g(high)}"


def by_run(flagged, keys, runs):
    """How many frames of each run are in the set flagged."""
    return {run: sum(name in flagged for name, key in keys.items() if key["run"] == run) for run in runs}


def best_cut(values, keys):
    """The most right answers of 'wrong on one side of one cut' with the cut chosen with the answers."""
    ordered = sorted(set(values.values()))
    best = None
    for low, high in zip(ordered, ordered[1:]):
        cut = (low + high) / 2
        for side in ("above", "below"):
            flagged = {n for n, v in values.items() if (v > cut) == (side == "above")}
            right = sum((n in flagged) == (keys[n]["class"] == "wrong") for n in values)
            if best is None or right > best["right"]:
                best = {"cut": cut, "side": side, "right": right, "flagged": flagged}
    return best


def what_the_counts_rest_on(keys, columns, texts, rule, runs, logs, facts, judgement, look, problems):
    """The tables and counts of the README's section with this name; each table line is looked up there."""
    names = [r["name"] for r in runs]
    wrong_runs = [r["name"] for r in runs if r["class"] == "wrong"]
    normal_runs = [r["name"] for r in runs if r["class"] == "normal"]
    normal = {n for n, k in keys.items() if k["class"] == "normal"}
    short = {"gemma-4-12b": "12B", "gemma-4-26": "26B-A4B", "gemma-4-31": "31B", "qwen": "Qwen"}
    answers = {next(v for p, v in short.items() if m.startswith(p)): a for m, a in columns}
    reasons = {next(v for p, v in short.items() if m.startswith(p)): t for m, t in texts.items()}
    flags = {model: {n for n, word in a.items() if word == "inconsistent"} for model, a in answers.items()}
    rule_flags = {n for n, word in rule.items() if word == "inconsistent"}
    frames = facts["frames"]
    if set(frames) != set(keys):
        problems.append("frame-facts.json holds other frames than the key")
    for name, key in keys.items():
        if abs(frames[name]["colour_bar_U"][1] - key["numeric"]["max_speed_m_per_s"]) > 1e-9 or \
                abs(frames[name]["colour_bar_p"][0] - key["numeric"]["min_pressure_m2_per_s2"]) > 1e-9:
            problems.append(f"{name}: the colour bar's end is not the key's peak |U| or lowest p")

    def right_of(flagged, among=None):
        among = keys if among is None else among
        return sum((n in flagged) == (keys[n]["class"] == "wrong") for n in among)

    def row_of(flagged):
        counts = by_run(flagged, keys, wrong_runs)
        return f"{right_of(flagged)} | {len(flagged & normal)} | " + " | ".join(str(counts[r]) for r in wrong_runs)

    # 31B against the rule
    f31 = flags["31B"]
    right31 = {n for n in keys if (n in f31) == (keys[n]["class"] == "wrong")}
    right_rule = {n for n in keys if (n in rule_flags) == (keys[n]["class"] == "wrong")}
    only31, only_rule = right31 - right_rule, right_rule - right31
    leave_out = {}
    table = {"All": (), "Without M4": ("M4-moving-wall",), "Without M2": ("M2-viscosity",),
             "Without M2 and M4": ("M2-viscosity", "M4-moving-wall")}
    for label, gone in table.items():
        among = [n for n, k in keys.items() if k["run"] not in gone]
        leave_out[label] = {"frames": len(among), "31B": right_of(f31, among), "rule": right_of(rule_flags, among)}
        look(f"| {label} | {len(among)} | {leave_out[label]['31B']} | {leave_out[label]['rule']} |")
    speed_frames = {model: {n for n in flags[model] if SPEED_REASON.search(reasons[model][n])} for model in flags}
    step_frames = {model: {n for n in flags[model] if STEP_REASON.search(reasons[model][n])} for model in flags}
    # the normal frames as answered (a false alarm stays one), a wrong frame right only with the speed reason
    speed_only = right_of(f31, normal) + len(speed_frames["31B"] - normal)
    look(f"| All, 31B's `inconsistent` counted only with the speed reason | 80 | {speed_only} | {leave_out['All']['rule']} |")
    m4_frames = {n for n, k in keys.items() if k["run"] == "M4-moving-wall"}

    # what the reasons rest on
    quoted, mismatches = 0, []
    for model, chosen in speed_frames.items():
        for name in chosen:
            numbers = [v for v in re.findall(r"(\d+(?:\.\d+)?) m/s", reasons[model][name]) if v != "32.2"]
            shown = f"{frames[name]['colour_bar_U'][1]:.4g}"
            quoted += len(numbers)
            if [float(v) for v in numbers] != [float(shown)]:
                mismatches.append((model, name, numbers, shown))
    below = {n for n in keys if frames[n]["colour_bar_U"][1] < INLET}
    words = {model: {"recirculation": sum("recirculation" in reasons[model][n] for n in flags[model] if keys[n]["run"] == "M2-viscosity"),
                     "separation": sum("separation" in reasons[model][n] for n in flags[model] if keys[n]["run"] == "M2-viscosity"),
                     "smooth": sum("smooth" in reasons[model][n] for n in flags[model] if keys[n]["run"] == "M2-viscosity"),
                     "flags_on_M2": sum(keys[n]["run"] == "M2-viscosity" for n in flags[model])} for model in flags}
    m1m5 = {n for n, k in keys.items() if k["run"] in ("M1-inlet-speed", "M5-half-inlet")}

    # checks that need no reference run
    whole_run = {n for n, k in keys.items() if logs[k["run"]]["courant_max_whole_run"] > 1}
    at_frame = {n for n, k in keys.items() if k["numeric"]["courant_max"] > 1}
    look(f"| Peak \\|U\\| rule (the design's) | {row_of(rule_flags)} |")
    look(f"| Largest Courant number of the whole run above 1, flagging all the run's frames | {row_of(whole_run)} |")
    look(f"| Courant number above 1 at the frame's own step | {row_of(at_frame)} |")
    look(f"| The rule or the whole run's Courant number | {row_of(rule_flags | whole_run)} |")
    look(f"| Gemma 4 31B | {row_of(f31)} |")

    # the numbers printed on the pictures
    ends = {"\\|U\\| upper end": {n: f["colour_bar_U"][1] for n, f in frames.items()},
            "\\|U\\| lower end": {n: f["colour_bar_U"][0] for n, f in frames.items()},
            "Lowest p": {n: f["colour_bar_p"][0] for n, f in frames.items()},
            "p upper end": {n: f["colour_bar_p"][1] for n, f in frames.items()}}
    single = dict(ends, **{"p range": {n: f["colour_bar_p"][1] - f["colour_bar_p"][0] for n, f in frames.items()}})
    colour_bars = {}
    for label, values in single.items():
        best = best_cut(values, keys)
        colour_bars[label.replace("\\", "")] = {"cut": best["cut"], "side": best["side"], "right": best["right"],
                                                  "by_run": by_run(best["flagged"], keys, names)}
        look(f"| {label} alone | {best['side']} {best['cut']:.4g} | {row_of(best['flagged'])} |")

    def outside_range(among_runs, values=ends):
        limits = {label: (min(v[n] for n in v if keys[n]["run"] in among_runs), max(v[n] for n in v if keys[n]["run"] in among_runs))
                  for label, v in values.items()}
        return {n for n in keys if any(not limits[label][0] <= v[n] <= limits[label][1] for label, v in values.items())}

    any_end = outside_range(normal_runs)
    look(f"| Any of the four ends outside the normal frames' range | outside | {row_of(any_end)} |")
    low_u, low_p = max(ends["\\|U\\| lower end"][n] for n in normal), max(ends["Lowest p"][n] for n in normal)
    two = {n for n in keys if ends["\\|U\\| lower end"][n] > low_u or ends["Lowest p"][n] > low_p}
    look(f"| \\|U\\| lower end above {low_u:.3g} or lowest p above {low_p:.4g} | above | {row_of(two)} |")
    held_out, wrong_held_out = {}, []
    for run in normal_runs:
        others = [r for r in normal_runs if r != run]
        flagged = outside_range(others)
        held_out[run] = sum(n in flagged for n, k in keys.items() if k["run"] == run)
        wrong_held_out.append(sum(n in flagged for n in keys if n not in normal))
    fair = 40 - sum(held_out.values()) + len(any_end - normal)
    look(f"| The same four ends, each normal run against the other four runs' range | outside | {fair} | {sum(held_out.values())} | "
         + " | ".join(str(by_run(any_end, keys, wrong_runs)[r]) for r in wrong_runs) + " |")

    # the second question: the judge's labels against the recorded answers
    labels = judgement["labels"]
    alias = {key: next(v for p, v in short.items() if model.startswith(p)) for key, model in judgement["source"]["models"].items()}
    seen = set()
    for row in labels:
        model = alias[row["model"]]
        seen.add((model, row["frame"]))
        if row["assessment"] != answers[model][row["frame"]] or row["reason"] != reasons[model][row["frame"]]:
            problems.append(f"reason-judgement.json: {row['model']} {row['frame']} is not the recorded answer")
    if seen != {(model, n) for model, chosen in flags.items() for n in chosen}:
        problems.append("reason-judgement.json does not label exactly the inconsistent answers")
    judged = {}
    for run in wrong_runs + ["normal frames"]:
        rows = [r for r in labels if (r["run"] == run if run != "normal frames" else r["class"] == "normal")]
        judged[run] = {word: sum(r["label"] == word for r in rows) for word in ("names_it", "partly", "no")}
        judged[run]["inconsistent_answers"] = len(rows)
        if run != "normal frames":
            look(f"| {run} | {len(rows)} | {judged[run]['names_it']} | {judged[run]['partly']} | {judged[run]['no']} |")
    totals = {word: sum(judged[r][word] for r in wrong_runs) for word in ("names_it", "partly", "no", "inconsistent_answers")}
    look(f"| All wrong runs | {totals['inconsistent_answers']} | {totals['names_it']} | {totals['partly']} | {totals['no']} |")
    if totals != judgement["counts"]["totals"]["wrong_frames"]:
        problems.append("the labels do not add up to the counts in reason-judgement.json")

    # the facts on the flow, from flow/frame-facts.json
    def percent(pair):
        return f"{100 * pair[0]:.1f} to {100 * pair[1]:.1f} %"

    for group, members in [("Normal runs", normal_runs)] + [(r, [r]) for r in wrong_runs]:
        rows = [facts["by_run"][r] for r in members]
        merged = {k: [min(row[k][0] for row in rows), max(row[k][1] for row in rows)] for k in rows[0]}
        look(f"| {group} | {percent(merged['reversed_share_of_window_by_area'])} | {percent(merged['reversed_share_of_window_by_cells'])} | "
             f"{percent(merged['reversed_share_below_step_height_by_area'])} | {merged['lowest_Ux_in_window'][0]:.3g} to {merged['lowest_Ux_in_window'][1]:.3g} |")

    return {"written_after_the_answers_were_read": True,
            "31B_against_the_rule": {"31B_right_rule_wrong": by_run(only31, keys, names), "rule_right_31B_wrong": sorted(only_rule),
                                     "leave_out": leave_out, "only_the_speed_reason_counts": speed_only,
                                     "false_alarms_if_M4_frames_count_as_what_they_look_like": {"flags": len((f31 & normal) | (f31 & m4_frames)), "frames": 48},
                                     "most_right_from_pictures_without_M4_signal": 72},
            "reasons": {"speed_reason_by_model_and_run": {m: by_run(c, keys, names) for m, c in speed_frames.items()},
                        "missing_step_reason_by_model_and_run": {m: by_run(c, keys, names) for m, c in step_frames.items()},
                        "missing_step_reason_31B_off_M2": {"flags": len([n for n in step_frames["31B"] if keys[n]["run"] != "M2-viscosity"]), "frames": 72},
                        "quoted_maxima": quoted, "quoted_maxima_differing_from_the_colour_bar": mismatches,
                        "colour_bar_maximum_below_32p2": by_run(below, keys, names),
                        "31B_speed_reason_frames_equal_colour_bar_below_32p2": speed_frames["31B"] == below,
                        "flags_on_M1_and_M5_of_16": {m: len(c & m1m5) for m, c in flags.items()},
                        "words_in_the_flags_on_M2": words,
                        "31B_on_M4_and_N5_at_one_step": {str(k): {"M4": answers["31B"][f"M4-moving-wall-step{k:05d}"], "N5": answers["31B"][f"N5-step{k:05d}"]}
                                                         for k in range(4500, 8001, 500)}},
            "no_reference": {"whole_run_courant_above_1": by_run(whole_run, keys, names), "at_the_frame": by_run(at_frame, keys, names)},
            "colour_bars": {"single_cut_chosen_with_the_answers": colour_bars,
                            "any_end_outside": by_run(any_end, keys, names), "two_cuts": by_run(two, keys, names),
                            "two_cuts_limits": [low_u, low_p],
                            "held_out_normal_frames_outside": held_out,
                            "wrong_frames_outside_with_each_four_run_range": wrong_held_out, "held_out_right": fair},
            "judgement": {"by_run": judged, "wrong_frames": totals}}


def read_log(path):
    """Per step: Courant numbers before the step, first initial and last final residual per field,
    last continuity errors. And the end of the log."""
    steps, courant, ended, crashed = [], None, False, False
    with gzip.open(path, "rt", errors="replace") as stream:
        for line in stream:
            if line.startswith("Courant Number mean:"):
                fields = line.split()
                courant = (float(fields[3]), float(fields[5]))
            elif line.startswith("Time = "):
                steps.append({"time": line.split("=")[1].strip(), "courant_mean": courant[0], "courant_max": courant[1]})
            elif "Solving for" in line and steps:
                match = re.search(r"Solving for (\w+), Initial residual = ([^,]+), Final residual = ([^,]+),", line)
                steps[-1].setdefault(match.group(1) + "_initial", float(match.group(2)))
                steps[-1][match.group(1) + "_final"] = float(match.group(3))
            elif line.startswith("time step continuity errors") and steps:
                numbers = re.findall(r"= ([^,\s]+)", line)
                steps[-1]["continuity_local"] = float(numbers[0])
                steps[-1]["continuity_global_abs"] = abs(float(numbers[1]))
                steps[-1]["continuity_cumulative_abs"] = abs(float(numbers[2]))
            elif line.strip() == "End":
                ended = True
            elif "sigFpe::sigHandler" in line:
                crashed = True
    return steps, ended, crashed


def main():
    truth = json.loads((HERE / "test-set" / "truth.private.json").read_text())
    manifest = json.loads((HERE / "test-set" / "manifest.json").read_text())
    leak = json.loads((HERE / "test-set" / "leak-check.json").read_text())
    keys = {name.split("/", 1)[1]: key for name, key in truth.items()}
    report = set((HERE / "reports" / "combined.md").read_text().splitlines())
    readme = set((HERE / "README.md").read_text().splitlines())
    problems, checked, checked_readme = [], 0, 0

    def look(line):
        nonlocal checked
        checked += 1
        if line not in report:
            problems.append(f"not in the report: {line}")

    def look_readme(line):
        nonlocal checked_readme
        checked_readme += 1
        if line not in readme:
            problems.append(f"not in the README: {line}")

    # the key
    runs = manifest["runs"]
    names = [r["name"] for r in runs]
    wrong_runs = [r["name"] for r in runs if r["class"] == "wrong"]
    steps_wanted = list(range(4500, 8001, 500))
    for run in runs:
        frames = sorted(k["run_step"] for k in keys.values() if k["run"] == run["name"])
        if frames != steps_wanted:
            problems.append(f"{run['name']}: frames at {frames}")
    for name, key in keys.items():
        if key["assessment"] != RIGHT[key["class"]]:
            problems.append(f"{name}: label does not follow the class")
        if abs(key["time_s"] - (0.1 + key["run_step"] * 5e-6)) > 1e-9:
            problems.append(f"{name}: time {key['time_s']}")
    # the leak check, from its stored hashes and the key's classes
    groups = {}
    for name, digest in leak["text_sha256_by_request"].items():
        groups.setdefault(digest, []).append(keys[name]["class"])
    balance = sorted((g2.count("normal"), g2.count("wrong")) for g2 in groups.values())
    if balance != [(5, 5)] * 8:
        problems.append(f"text groups: {balance}")
    example = (HERE / "test-set" / "request-text-example.json").read_bytes()
    if hashlib.sha256(example).hexdigest() != leak["text_sha256_by_request"]["N1-step04500"]:
        problems.append("the example text does not have the hash the leak check lists")
    # the logs
    log_numbers = {}
    for run in runs:
        steps, ended, crashed = read_log(HERE / "flow" / "logs" / f"{run['name']}.log.gz")
        log_numbers[run["name"]] = {"steps": len(steps), "ended": ended, "crashed": crashed}
        if len(steps) != 8000 or not ended or crashed:
            problems.append(f"{run['name']}: {len(steps)} steps, End {ended}, crash {crashed}")
        for name, key in keys.items():
            if key["run"] == run["name"]:
                block = steps[key["run_step"] - 1]
                for number, _ in FRAME_NUMBERS[:11]:
                    if block[number] != key["numeric"][number]:
                        problems.append(f"{name}: {number} {block[number]} in the log, {key['numeric'][number]} in the key")
        late = steps[4499:]
        last = steps[-1]
        again = {"courant_max_whole_run": max(s["courant_max"] for s in steps),
                 "courant_max_from_first_frame": max(s["courant_max"] for s in late),
                 "courant_mean_from_first_frame": sum(s["courant_mean"] for s in late) / len(late),
                 **{"last_" + k: last[k] for k in ("Ux_initial", "Uy_initial", "p_initial", "Ux_final", "Uy_final", "p_final",
                                                   "continuity_local", "continuity_global_abs", "continuity_cumulative_abs")}}
        for number, value in again.items():
            if value != run["log"][number]:
                problems.append(f"{run['name']}: {number} {value} in the log, {run['log'][number]} in the manifest")
        log_numbers[run["name"]].update(courant_max_whole_run=again["courant_max_whole_run"],
                                        courant_max_at_step=[s["courant_max"] for s in steps].index(again["courant_max_whole_run"]) + 1,
                                        steps_with_courant_above_1=sum(s["courant_max"] > 1 for s in steps),
                                        first_and_last_step_above_1=[i + 1 for i, s in enumerate(steps) if s["courant_max"] > 1][:1]
                                        + [i + 1 for i, s in enumerate(steps) if s["courant_max"] > 1][-1:])
    # the answers
    columns, texts = [], {}
    for path in sorted((HERE / "results").glob(f"*/*/{SET}/metrics.jsonl")):
        meta = json.loads((path.parents[1] / "run.json").read_text())
        answers = {row["name"]: row["structured_output"]["assessment"] if row["successful_response"] else None for row in rows(path)}
        texts[meta["model"]] = {row["name"]: row["structured_output"]["reason"] if row["successful_response"] else "" for row in rows(path)}
        if set(answers) != set(keys):
            problems.append(f"{path}: other frames than the key's")
        columns.append((meta["model"], answers))
    columns.sort(key=lambda c: ["gemma-4-12b", "gemma-4-26", "gemma-4-31", "qwen"].index(
        next(p for p in ("gemma-4-12b", "gemma-4-26", "gemma-4-31", "qwen") if c[0].startswith(p))))
    rule = {name: "consistent" if INLET <= key["numeric"]["max_speed_m_per_s"] <= 2 * INLET else "inconsistent"
            for name, key in keys.items()}
    counts = {}
    rule_label = "Rule: peak \\|U\\| in the window between 1 and 2 times 32.2 m/s"
    for label, answers in columns + [(rule_label, rule)]:
        normal = [n for n, k in keys.items() if k["class"] == "normal"]
        wrong = [n for n, k in keys.items() if k["class"] == "wrong"]
        said = lambda group, word: sum(answers.get(n) == word for n in group)
        right = said(normal, "consistent") + said(wrong, "inconsistent")
        counts[label] = {"answered": sum(answers.get(n) is not None for n in keys), "right": right,
                         "normal": {w: said(normal, w) for w in RIGHT.values()} | {"cannot_tell": said(normal, "cannot_tell")},
                         "wrong": {w: said(wrong, w) for w in RIGHT.values()} | {"cannot_tell": said(wrong, "cannot_tell")},
                         "by_run": {run: sum(answers.get(n) == RIGHT[k["class"]] for n, k in keys.items() if k["run"] == run) for run in names}}
        look(f"| {label} | {counts[label]['answered']} | {right} | {said(normal, 'consistent')} of 40 | {said(normal, 'inconsistent')} | "
             f"{said(normal, 'cannot_tell')} | {said(wrong, 'inconsistent')} of 40 | {said(wrong, 'consistent')} | {said(wrong, 'cannot_tell')} |")
    look("| Constant baseline | | 40 | | | | | | |")
    for run in runs:
        look(f"| {run['name']} | {run['class']} | {run['change']} | "
             + " | ".join(f"{counts[label]['by_run'][run['name']]} of 8" for label, _ in columns + [(rule_label, rule)]) + " |")
    # the numbers
    outside_frames, outside_logs = {}, {}
    for number, label in FRAME_NUMBERS:
        normal = [k["numeric"][number] for k in keys.values() if k["class"] == "normal"]
        low, high = min(normal), max(normal)
        cells = []
        for run in wrong_runs:
            values = [k["numeric"][number] for k in keys.values() if k["run"] == run]
            count = sum(not low <= v <= high for v in values)
            outside_frames.setdefault(number, {})[run] = count
            cells.append(f"{span(min(values), max(values))} ({count})")
        look(f"| {label} | {span(low, high)} | " + " | ".join(cells) + " |")
    for number, label in LOG_NUMBERS:
        values = [r["log"][number] for r in runs if r["class"] == "normal"]
        low, high = min(values), max(values)
        cells = []
        for run in runs:
            if run["class"] == "wrong":
                value = run["log"][number]
                outside_logs.setdefault(number, {})[run["name"]] = not low <= value <= high
                cells.append(g(value) + (" \\*" if not low <= value <= high else ""))
        look(f"| {label} | {span(low, high)} | " + " | ".join(cells) + " |")
    # every frame
    for name, key in keys.items():
        look(f"| {name} | {key['class']} | {key['numeric']['max_speed_m_per_s']:.4g} | {key['numeric']['min_pressure_m2_per_s2']:.4g} | "
             f"{MARK[rule[name]]} | " + " | ".join(MARK[a.get(name)] for _, a in columns) + " |")
    # the same flow state under another step and time
    overlap = json.loads((HERE / "flow" / "normal-overlap.json").read_text())
    def frame_name(text):
        run, _, step = text.split()
        return f"{run}-step{int(step):05d}"
    pairs = [(frame_name(p["a"]), frame_name(p["b"])) for p in overlap["pairs"]]
    same_state = {model: {"pairs": len(pairs), "same_answer": sum(a.get(x) == a.get(y) for x, y in pairs)} for model, a in columns}
    # the answers by step and how often they change along a run
    by_step, changes = {}, {}
    for model, answers in columns:
        by_step[model] = {str(step): {group: sum(answers.get(n) == RIGHT[group] for n, k in keys.items() if k["class"] == group and k["run_step"] == step)
                                      for group in RIGHT} for step in steps_wanted}
        changes[model] = {}
        for run in names:
            series = [answers.get(f"{run}-step{step:05d}") for step in steps_wanted]
            changes[model][run] = sum(x != y for x, y in zip(series, series[1:]))
    # the prompt length must not differ between the classes at one step
    tokens = {}
    for path in sorted((HERE / "results").glob(f"*/*/{SET}/metrics.jsonl")):
        meta = json.loads((path.parents[1] / "run.json").read_text())
        at_step = {}
        for row in rows(path):
            key = keys[row["name"]]
            at_step.setdefault(key["run_step"], {}).setdefault(key["class"], set()).add((row.get("usage") or {}).get("prompt_tokens"))
        tokens[meta["model"]] = {"same_prompt_tokens_in_both_classes_at_each_step": all(v["normal"] == v["wrong"] for v in at_step.values()),
                                 "prompt_tokens": sorted({t for v in at_step.values() for s in v.values() for t in s}),
                                 "median_wall_s": statistics.median(row["replay_wall_s"] for row in rows(path))}
    resting = what_the_counts_rest_on(keys, columns, texts, rule, runs, log_numbers,
                                      json.loads((HERE / "flow" / "frame-facts.json").read_text()),
                                      json.loads((HERE / "reason-judgement.json").read_text()), look_readme, problems)
    out = {"problems": problems, "report_lines_checked": checked, "readme_lines_checked": checked_readme, "counts": counts, "logs": log_numbers,
           "frames_outside_normal_range": outside_frames, "logs_outside_normal_range": outside_logs, "prompt_tokens": tokens,
           "same_flow_state_other_label": same_state, "right_by_step": by_step, "answer_changes_along_each_run": changes,
           "text_groups_normal_wrong": balance, "what_the_counts_rest_on": resting}
    (HERE / "recount.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"{checked} report lines and {checked_readme} README lines checked, {len(problems)} problems")
    for line in problems[:60]:
        print(line)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
