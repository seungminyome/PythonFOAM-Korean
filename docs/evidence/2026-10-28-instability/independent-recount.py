#!/usr/bin/env python3
"""Recount the 2026-10-28 instability test from the recorded answers and the answer key, without
instability_test.py or picture_test.py, and compare every count cell of the jobs' reports.

Run in this folder:  python3 independent-recount.py   (standard library only; writes
independent-recount.json)

Inputs: test-set/truth.private.json (the key: label, scored or not, run, steps from the last
frame to the crash, and per frame the largest |U| and the largest cell-to-cell |U| jump inside
the window), results/<job>/<model>/instability-v2own/metrics.jsonl (one parsed answer per
request) and reports/<job>.md. For each model it recounts: answered; right on the scored items;
the six answer cells of the balanced table; said unstable by steps from the last frame to the
crash; said unstable by run; and the per-item marks. It computes the two numeric baselines
again from the per-frame numbers (not from the key's stored ratios, which it checks), with the
thresholds the report uses, and the best single threshold. Then it compares each of these with
the report's cells. It also writes numbers the README cites: how early each model first says
unstable in each crashed run, the cannot_tell and invalid answers, and which items a model calls
unstable that a numeric rule does not. Beyond the reports: the time between frames that the
requests state (each frame's time_s and step, in the note, the captions and the picture
titles), by group and run, and how far a rule on it alone gets; which reasons give a short
time between frames; and the Courant numbers of the frames by run.
"""
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SET = "instability-v2own"
SPEED = (1.05, 1.1, 1.2, 1.5, 2.0)
JUMP = (1.2, 1.5, 2.0, 3.0)
BINS = ((1, 1), (2, 3), (4, 6), (7, 10), (11, 25), (26, 100), (101, 10 ** 9))
MARK = {"unstable": "u", "stable": "s", "cannot_tell": "?", None: "-"}
SHORT_TIME = re.compile(r"short time|time interval", re.I)
SECONDS = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?(?:[eE]-?\d+)?) ?s\b")   # '0.00004 s'; not 'm/s'
INTERVAL_BELOW_S = 0.01      # a time in seconds below this is a time between frames (frame times are about 0.1 s)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_key():
    truth = json.loads((HERE / "test-set" / "truth.private.json").read_text())
    keys, problems = {}, []
    for name, key in truth.items():
        assert name.startswith(SET + "/"), name
        item = name.split("/", 1)[1]
        f = key["frames"]
        speed = f[-1]["max_speed_m_per_s"] / f[0]["max_speed_m_per_s"]
        jump = f[-1]["max_jump_speed_m_per_s"] / f[0]["max_jump_speed_m_per_s"]
        if (speed, jump) != (key["numeric"]["max_speed_last_over_first"], key["numeric"]["max_jump_speed_last_over_first"]):
            problems.append(f"{item}: stored ratios differ from the frames")
        stc = [fr["steps_to_crash"] for fr in f]
        if key["stability"] == "unstable":
            if stc[-1] != key["steps_to_crash_last"] or stc[-1] != key["crash_step"] - f[-1]["run_step"]:
                problems.append(f"{item}: steps to crash inconsistent")
            if key["scored"] != (stc[-1] <= 10):
                problems.append(f"{item}: scored flag does not follow the 10-step rule")
        elif key["crash_step"] is not None or not key["scored"] or min(fr["steps_after_in_run"] for fr in f) < 100:
            problems.append(f"{item}: a stable item from a run that crashed, or within 100 steps of its end")
        keys[item] = {"truth": key["stability"], "scored": key["scored"], "run": key["run"],
                      "stc": key["steps_to_crash_last"], "speed": speed, "jump": jump,
                      "times": [fr["time_s"] for fr in f], "note_steps": [fr["step"] for fr in f],
                      "frames": [(fr["run_step"], fr["courant_max"], fr["steps_to_crash"]) for fr in f]}
    return keys, problems


def frame_gaps(k):
    return [round(b - a, 12) for a, b in zip(k["times"], k["times"][1:])]


def frame_spacing(keys):
    """The time between frames the requests state, by group and run, and a rule on it alone:
    'unstable' when the first two frames are less than a threshold apart (the threshold with
    the most right answers on the scored items, halfway between two observed gaps)."""
    groups = {"scored unstable": lambda k: k["scored"] and k["truth"] == "unstable",
              "early unstable (not scored)": lambda k: not k["scored"],
              "stable": lambda k: k["truth"] == "stable"}
    out = {"by_group": {}, "by_run": {}}
    for label, pick in groups.items():
        group = [k for k in keys.values() if pick(k)]
        gaps = [g for k in group for g in frame_gaps(k)]
        steps = [b - a for k in group for a, b in zip(k["note_steps"], k["note_steps"][1:])]
        out["by_group"][label] = {"items": len(group), "time_between_frames_s": [min(gaps), max(gaps)],
                                  "note_steps_between_frames": [min(steps), max(steps)]}
    for run in sorted({k["run"] for k in keys.values()}):
        out["by_run"][run] = sorted({g for k in keys.values() if k["run"] == run for g in frame_gaps(k)})
    out["both_gaps_equal_in_every_item"] = all(len(set(frame_gaps(k))) == 1 for k in keys.values())
    values = sorted({frame_gaps(k)[0] for k in keys.values()})
    found = None
    for a, b in zip(values, values[1:]):
        right = sum((frame_gaps(k)[0] < (a + b) / 2) == (k["truth"] == "unstable") for k in keys.values() if k["scored"])
        if found is None or right > found[1]:
            found = ((a + b) / 2, right)
    out["rule_unstable_when_frames_closer_than"] = {
        "threshold_s": found[0], "right_scored": found[1], "scored_items": sum(k["scored"] for k in keys.values()),
        "right_all": sum((frame_gaps(k)[0] < found[0]) == (k["truth"] == "unstable") for k in keys.values()),
        "items": len(keys)}
    return out


def short_time_reasons(answers, reasons):
    """Items whose reason gives a short time between frames: the words 'short time' or 'time
    interval', or a time in seconds below INTERVAL_BELOW_S (the frames' own times are about
    0.1 s). With the answer word and the times in seconds the reason gives."""
    out = {}
    for name, reason in sorted(reasons.items()):
        seconds = [float(v) for v in SECONDS.findall(reason)]
        interval = [s for s in seconds if s < INTERVAL_BELOW_S]
        if SHORT_TIME.search(reason) or interval:
            out[name] = {"answer": answers.get(name), "interval_s": interval}
    return out


def courant_of_frames(keys):
    """Largest Courant number computed from each frame's state (printed before the next step),
    over the distinct frames of each run: for a run that crashed, the frames 2 or more steps
    before the crash and, apart, the last state before it."""
    frames = {}
    for k in keys.values():
        for run_step, courant, stc in k["frames"]:
            frames[(k["run"], run_step)] = (k["truth"], courant, stc, k["scored"])
    out = {"by_run": {}}
    for run in sorted({r for r, _ in frames}):
        mine = [v for (r, _), v in frames.items() if r == run]
        if mine[0][0] == "stable":
            out["by_run"][run] = {"frames": len(mine), "range": [min(v[1] for v in mine), max(v[1] for v in mine)]}
        else:
            before = [v[1] for v in mine if v[2] >= 2]
            out["by_run"][run] = {"frames_2_or_more_steps_before_the_crash": len(before),
                                  "range": [min(before), max(before)],
                                  "last_state_before_the_crash": [v[1] for v in mine if v[2] == 1]}
    top = max(v[1] for v in frames.values() if v[0] == "stable")
    crashed = [v for v in frames.values() if v[0] == "unstable" and v[2] >= 2]
    in_scored = {(k["run"], s) for k in keys.values() if k["truth"] == "unstable" and k["scored"]
                 for s, _, stc in k["frames"] if stc >= 2}
    out["largest_in_a_stable_frame"] = top
    out["crashed_frames_2_or_more_steps_before_the_crash_at_or_below_it"] = [
        sum(v[1] <= top for v in crashed), len(crashed)]
    out["same_for_the_frames_of_scored_triples"] = [
        sum(frames[f][1] <= top for f in in_scored), len(in_scored)]
    return out


def balanced(answers, keys):
    scored = {n: k for n, k in keys.items() if k["scored"]}
    out = {"answered": sum(answers.get(n) is not None for n in scored), "items": len(scored),
           "right": sum(answers.get(n) == k["truth"] for n, k in scored.items())}
    for word in ("unstable", "stable"):
        group = [n for n, k in scored.items() if k["truth"] == word]
        out[word] = {"items": len(group)} | {w: sum(answers.get(n) == w for n in group)
                                             for w in ("unstable", "stable", "cannot_tell")}
    return out


def early(answers, keys):
    out = []
    for lo, hi in BINS:
        group = [n for n, k in keys.items() if k["truth"] == "unstable" and lo <= k["stc"] <= hi]
        out.append([len(group), sum(answers.get(n) == "unstable" for n in group)])
    return out


def by_run(answers, keys):
    out = {}
    for n, k in keys.items():
        if k["scored"]:
            cell = out.setdefault(k["run"], [0, 0])
            cell[0] += answers.get(n) == "unstable"
            cell[1] += 1
    return out


def rule(keys, measure, threshold):
    return {n: ("unstable" if k[measure] > threshold else "stable") for n, k in keys.items()}


def best(keys, measure, above=None):
    scored = [k for k in keys.values() if k["scored"]]
    values = sorted({k[measure] for k in scored})
    found = None
    for a, b in zip([0.0] + values, values + [values[-1] * 2]):
        if above is not None and (a + b) / 2 <= above:
            continue
        right = sum((k[measure] > (a + b) / 2) == (k["truth"] == "unstable") for k in scored)
        if found is None or right > found[1]:
            found = ((a + b) / 2, right)
    return found


def table_rows(text):
    """The rows of every Markdown table, as lists of cells (rule lines left out); a pipe written
    as \\| inside a cell is part of the cell."""
    out = []
    for line in text.splitlines():
        if line.startswith("|") and not line.startswith("|---"):
            parts = re.split(r"(?<!\\)\|", line.strip())[1:-1]
            out.append([c.strip().replace("\\|", "|") for c in parts])
    return out


def recount_job(job, keys):
    report = (HERE / "reports" / f"{job}.md").read_text()
    models = {}
    for run_dir in sorted((HERE / "results" / job).iterdir()):
        metrics = run_dir / SET / "metrics.jsonl"
        if not metrics.exists():
            continue
        meta = json.loads((run_dir / "run.json").read_text())
        answers, invalid, reasons = {}, [], {}
        for row in rows(metrics):
            assert row["name"] in keys, row["name"]
            if row["successful_response"]:
                answers[row["name"]] = row["structured_output"]["stability"]
                reasons[row["name"]] = row["structured_output"]["reason"]
            else:
                answers[row["name"]] = None
                invalid.append({"item": row["name"], "status": row["status"], "error": row.get("error")})
        models[meta["model"]] = {"answers": answers, "invalid": invalid, "reasons": reasons,
                                 "requests": len(answers)}
    rules = [(f"peak |U| grows > {round(100 * (t - 1))} %", rule(keys, "speed", t)) for t in SPEED]
    rules += [(f"largest |U| jump grows > {round(100 * (t - 1))} %", rule(keys, "jump", t)) for t in JUMP]
    sources = [(m, v["answers"]) for m, v in models.items()] + rules
    cells = table_rows(report)
    checks, diffs = 0, []

    def expect(row_label, values, where):
        nonlocal checks
        found = [c for c in cells if c and c[0] == row_label and len(c) == len(values) + 1 and where(c)]
        if len(found) != 1:
            diffs.append(f"{job}: row '{row_label}' found {len(found)} times")
            return
        for k, (got, want) in enumerate(zip(found[0][1:], values)):
            checks += 1
            if got != want:
                diffs.append(f"{job}: row '{row_label}' cell {k + 1}: report {got!r}, recount {want!r}")

    out = {"models": {}, "rules": {}}
    for label, answers in sources:
        b = balanced(answers, keys)
        expect(label, [f"{b['answered']}/{b['items']}", f"{b['right']}/{b['items']}",
                       f"{b['unstable']['unstable']}/{b['unstable']['items']}", str(b["unstable"]["stable"]),
                       str(b["unstable"]["cannot_tell"]), f"{b['stable']['stable']}/{b['stable']['items']}",
                       str(b["stable"]["unstable"]), str(b["stable"]["cannot_tell"])], lambda c: "/" in c[1])
        entry = {"balanced": b, "said_unstable_by_steps_to_crash": early(answers, keys), "by_run": by_run(answers, keys)}
        (out["models"] if label in models else out["rules"])[label] = entry
    # how early: one row per bin, the counts of every source in report order
    for i, (lo, hi) in enumerate(BINS):
        label = f"{lo}" if lo == hi else (f"{lo} to {hi}" if hi < 10 ** 8 else f"over {lo - 1}")
        values = [str(early(sources[0][1], keys)[i][0])] + [str(early(a, keys)[i][1]) for _, a in sources]
        expect(label, values, lambda c: True)
    # by run: the models, the 20 % peak |U| rule and the 50 % jump rule
    runs = {}
    for _, a in [(m, v["answers"]) for m, v in models.items()] + [rules[2], rules[len(SPEED) + 1]]:
        for run, (said, n) in by_run(a, keys).items():
            runs.setdefault(run, []).append(f"{said}/{n}")
    for run, values in runs.items():
        truth = next(k["truth"] for k in keys.values() if k["run"] == run)
        expect(run, [truth] + values, lambda c: c[1] in ("stable", "unstable"))
    # every item
    for name, k in keys.items():
        values = [k["truth"], "yes" if k["scored"] else "no", "" if k["stc"] is None else str(k["stc"]),
                  f"{k['speed']:.4g}", f"{k['jump']:.4g}"] + [MARK[v["answers"].get(name)] for v in models.values()]
        expect(name, values, lambda c: True)
    # best thresholds
    for measure, word in (("speed", "peak |U|"), ("jump", "largest |U| jump")):
        cut, right = best(keys, measure)
        cut1, right1 = best(keys, measure, above=1.0)
        match = re.search(rf"Best single threshold on the {re.escape(word)} ratio .*?: ([^,\s]+), (\d+)/\d+ right; "
                          rf"above 1 \(growth\) only: ([^,\s]+), (\d+)/\d+ right", report.replace("\\|", "|"))
        checks += 4
        want = (f"{cut:.4g}", str(right), f"{cut1:.4g}", str(right1))
        if not match or match.groups() != want:
            diffs.append(f"{job}: best thresholds for {word}: report {match.groups() if match else None}, recount {want}")
        out["rules"][f"best threshold on {word}"] = {"threshold": cut, "right": right}
        out["rules"][f"best threshold above 1 on {word}"] = {"threshold": cut1, "right": right1}
    # numbers the README cites
    for model, v in models.items():
        a = v["answers"]
        first = {}
        for run in sorted({k["run"] for k in keys.values() if k["truth"] == "unstable"}):
            items = sorted(((k["stc"], n) for n, k in keys.items() if k["run"] == run), reverse=True)
            said = [stc for stc, n in items if a.get(n) == "unstable"]
            first[run] = {"largest_steps_to_crash_said_unstable": max(said) if said else None,
                          "said_unstable_at": sorted(said),
                          "items_steps_to_crash": sorted(stc for stc, _ in items)}
        flagged_not_by_numbers = sorted(n for n, k in keys.items() if k["truth"] == "unstable" and a.get(n) == "unstable"
                                        and k["speed"] <= 1.2 and k["jump"] <= 1.5)
        out["models"][model].update(
            first_unstable_answer_by_run=first, invalid_answers=v["invalid"],
            answer_words=dict(Counter(str(x) for x in a.values())),
            unstable_items_said_unstable_where_peak_rule_20_and_jump_rule_50_say_stable=flagged_not_by_numbers,
            false_alarms=sorted(n for n, k in keys.items() if k["truth"] == "stable" and a.get(n) == "unstable"),
            reasons=v["reasons"], reasons_giving_a_short_time_between_frames=short_time_reasons(a, v["reasons"]))
    return out, checks, diffs


def main():
    keys, problems = load_key()
    result = {"key_problems": problems, "items": len(keys),
              "groups": dict(Counter(("scored " if k["scored"] else "early ") + k["truth"] for k in keys.values())),
              "jobs": {}, "checks": 0, "differences": []}
    for job_dir in sorted((HERE / "results").iterdir()):
        out, checks, diffs = recount_job(job_dir.name, keys)
        result["jobs"][job_dir.name] = out
        result["checks"] += checks
        result["differences"] += diffs
    result["frame_spacing"] = frame_spacing(keys)
    result["courant_of_frames"] = courant_of_frames(keys)
    (HERE / "independent-recount.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(keys)} items, key problems: {len(problems)}; {result['checks']} report cells checked, "
          f"{len(result['differences'])} differ")
    for line in problems + result["differences"]:
        print(line)
    return 1 if problems or result["differences"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
