#!/usr/bin/env python3
"""For every position answer of the periodic run (Slurm 24903264) more than 10 % of the plotted
range from the true cell: how fast is the flow, or how low the pressure, at the point the model
named, relative to the true extreme in the plotted range?

Usage: misses.py <periodic-describe folder> [output json]   (the folder is in periodic-24903264.tar.gz
of the release: run-24903264/periodic/periodic-describe; needs numpy)
The answered point is the cell whose centre is nearest to it among the cells inside the plotted range.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def main(case, out=None):
    case = Path(case)
    summary = json.loads((HERE / "periodic-summary.json").read_text())
    result = {}
    for target in ("fastest_flow", "lowest_pressure"):
        ratios = []
        for r in summary["requests"]:
            score = r["scores"][target]
            if score["within_10_percent"]:
                continue
            frame = case / "llm_observation" / f"step-{r['step']:06d}"
            meta = json.loads((frame / "readable-metadata.json").read_text())
            (x0, x1), (y0, y1) = meta["plotted_range_m"]["x"], meta["plotted_range_m"]["y"]
            with np.load(frame / "fields.npz") as z:
                c, speed, p = np.array(z["centres"]), np.linalg.norm(z["U"], axis=1), np.array(z["p"])
            inside = np.flatnonzero((c[:, 0] >= x0) & (c[:, 0] <= x1) & (c[:, 1] >= y0) & (c[:, 1] <= y1))
            values, best = (speed, speed[inside].max()) if target == "fastest_flow" else (p, p[inside].min())
            ax, ay = score["answer_percent"]
            X, Y = x0 + ax / 100 * (x1 - x0), y0 + ay / 100 * (y1 - y0)
            i = inside[np.argmin((c[inside, 0] - X) ** 2 + (c[inside, 1] - Y) ** 2)]
            ratios.append({"step": r["step"], "distance_percent": round(score["distance_percent"], 1),
                           "ratio_at_answer": round(float(values[i] / best), 3)})
        result[target] = {"misses": len(ratios),
                          "at_least_90_percent_of_extreme": sum(x["ratio_at_answer"] >= 0.9 for x in ratios),
                          "at_least_80_percent_of_extreme": sum(x["ratio_at_answer"] >= 0.8 for x in ratios),
                          "requests": ratios}
    text = json.dumps(result, indent=1) + "\n"
    if out:
        Path(out).write_text(text)
    for t, v in result.items():
        print(t, v["misses"], "misses;", v["at_least_90_percent_of_extreme"], ">= 90 %;",
              v["at_least_80_percent_of_extreme"], ">= 80 %; ratios", sorted(x["ratio_at_answer"] for x in v["requests"]))


if __name__ == "__main__":
    main(*sys.argv[1:])
