#!/usr/bin/env python3
"""Recount of the 2026-11-01 instability test without the test code: from metrics.jsonl and
truth.private.json only. Usage: python3 recount.py <results dir> <test set> <oct28 results dir>"""
import json, sys
from pathlib import Path

results, test_set, oct28 = map(Path, sys.argv[1:4])
truth = json.loads((test_set / "truth.private.json").read_text())
manifest = json.loads((test_set / "manifest.json").read_text())
sets = list(manifest["sets"])
speed_rules, jump_rules = (1.05, 1.1, 1.2, 1.5, 2.0), (1.2, 1.5, 2.0, 3.0)
out = {"text_identity": manifest["text_identity"], "sets": {}}

def rows(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

def counts(answers, keys):
    scored = {n: k for n, k in keys.items() if k["scored"]}
    unstable = [n for n, k in scored.items() if k["stability"] == "unstable"]
    stable = [n for n, k in scored.items() if k["stability"] == "stable"]
    return {"scored": len(scored), "right": sum(answers.get(n) == scored[n]["stability"] for n in scored),
            "crash_bound": len(unstable), "crash_bound_flagged": sum(answers.get(n) == "unstable" for n in unstable),
            "normal": len(stable), "normal_flagged": sum(answers.get(n) == "unstable" for n in stable),
            "cannot_tell": sum(answers.get(n) == "cannot_tell" for n in scored),
            "no_answer": sum(answers.get(n) is None for n in scored),
            "early_flagged_of_early": [sum(answers.get(n) == "unstable" for n, k in keys.items() if not k["scored"]),
                                       sum(1 for k in keys.values() if not k["scored"])]}

old = {}
for d in sorted(oct28.iterdir()):
    if (d / "run.json").exists():
        alias = json.loads((d / "run.json").read_text())["model"]
        old[alias] = {r["name"]: r["structured_output"]["stability"] if r["successful_response"] else None
                      for r in rows(d / "instability-v2own" / "metrics.jsonl")}
for s in sets:
    keys = {n.split("/", 1)[1]: k for n, k in truth.items() if n.startswith(s + "/")}
    block = {"models": {}, "rules": {}}
    for d in sorted(results.iterdir()):
        if not (d / "run.json").exists() or not (d / s / "metrics.jsonl").exists():
            continue
        alias = json.loads((d / "run.json").read_text())["model"]
        rs = rows(d / s / "metrics.jsonl")
        answers = {r["name"]: r["structured_output"]["stability"] if r["successful_response"] else None for r in rs}
        c = counts(answers, keys)
        c["attempted"] = len(rs); c["successful"] = sum(r["successful_response"] for r in rs)
        c["flagged_items"] = sorted(n for n, a in answers.items() if a == "unstable")
        if s.startswith("instability-oct28") and alias in old:
            o = old[alias]; names = sorted(set(o) & set(answers))
            c["against_oct28"] = {"items": len(names), "same": sum(o[n] == answers[n] for n in names),
                                  "stable_to_unstable": [n for n in names if o[n] == "stable" and answers[n] == "unstable"],
                                  "unstable_to_stable": [n for n in names if o[n] == "unstable" and answers[n] == "stable"],
                                  "oct28_right": sum(o[n] == keys[n]["stability"] for n in names if keys[n]["scored"]),
                                  "now_right": sum(answers[n] == keys[n]["stability"] for n in names if keys[n]["scored"])}
        block["models"][alias] = c
    for label, measure, ths in (("peak", "max_speed_last_over_first", speed_rules), ("jump", "max_jump_speed_last_over_first", jump_rules)):
        for t in ths:
            answers = {n: ("unstable" if k["numeric"][measure] > t else "stable") for n, k in keys.items()}
            block["rules"][f"{label} > {round(100 * (t - 1))} %"] = counts(answers, keys)
    out["sets"][s] = block
print(json.dumps(out, indent=1))
