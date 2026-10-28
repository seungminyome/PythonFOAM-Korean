#!/usr/bin/env python3
"""Does the model follow the flow features during the periodic run of 2026-10-27 (Slurm 24903264)?

Run in this folder:  python3 tracking.py [--plot]   (reads periodic-summary.json, writes tracking.json;
--plot also writes tracking.png and needs matplotlib)

For the 96 describe requests (one every 250 steps), per target (fastest flow, lowest pressure):
how far the true position moves over the run, how many answers are within 10 % of the plotted
range, and the Pearson correlation between the answered and the true x (and y) percent over the
run. A model that gave one fixed answer would have correlation 0 (undefined) whatever its count.
"""
import json
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGETS = ("fastest_flow", "lowest_pressure")


def pearson(a, b):
    ma, mb = st.fmean(a), st.fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den


def main(plot):
    summary = json.loads((HERE / "periodic-summary.json").read_text())
    reqs = [r for r in summary["requests"] if r["status"] == "ok"]
    out = {"requests": len(reqs), "steps": [reqs[0]["step"], reqs[-1]["step"]], "targets": {}}
    for t in TARGETS:
        ans = [r["scores"][t]["answer_percent"] for r in reqs]
        true = [r["scores"][t]["true_percent"] for r in reqs]
        out["targets"][t] = {
            "within_10_percent": sum(r["scores"][t]["within_10_percent"] for r in reqs),
            "one_fixed_answer": summary["one_fixed_answer_for_all"][t],
            "true_x_percent_range": [round(min(p[0] for p in true), 1), round(max(p[0] for p in true), 1)],
            "true_y_percent_range": [round(min(p[1] for p in true), 1), round(max(p[1] for p in true), 1)],
            "pearson_x": round(pearson([a[0] for a in ans], [p[0] for p in true]), 3),
            "pearson_y": round(pearson([a[1] for a in ans], [p[1] for p in true]), 3),
            "median_distance_percent": round(st.median(r["scores"][t]["distance_percent"] for r in reqs), 2),
        }
    (HERE / "tracking.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    if plot:
        draw(reqs, out)


def draw(reqs, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, surface = "#0b0b0b", "#52514e", "#fcfcfb"
    true_c, ans_c = "#2a78d6", "#eb6834"          # categorical slots 1 and 2
    steps = [r["step"] for r in reqs]
    fig, axes = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True, facecolor=surface)
    titles = {"lowest_pressure": "Lowest pressure (vortex core)", "fastest_flow": "Fastest flow"}
    for ax, t in zip(axes, ("lowest_pressure", "fastest_flow")):
        true_x = [r["scores"][t]["true_percent"][0] for r in reqs]
        ans_x = [r["scores"][t]["answer_percent"][0] for r in reqs]
        ax.set_facecolor(surface)
        ax.plot(steps, true_x, color=true_c, lw=2, label="true x")
        ax.scatter(steps, ans_x, s=22, color=ans_c, edgecolors=surface, linewidths=1, zorder=3,
                   label="Gemma 4 12B answer")
        o = out["targets"][t]
        ax.set_title(f"{titles[t]}: {o['within_10_percent']} of {out['requests']} within 10 %, "
                     f"x correlation {o['pearson_x']:.2f}", loc="left", fontsize=11, color=ink)
        ax.set_ylabel("x, % of plotted range", color=muted, fontsize=9)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", color="#e4e3df", lw=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#c9c8c2")
        ax.tick_params(colors=muted, labelsize=8)
    axes[0].legend(loc="upper left", frameon=False, fontsize=9, ncol=2, labelcolor=ink)
    axes[1].set_xlabel("solver step (request every 250 steps, from t = 0.1 s)", color=muted, fontsize=9)
    fig.tight_layout()
    fig.savefig(HERE / "tracking.png", dpi=110, facecolor=surface)


if __name__ == "__main__":
    main("--plot" in sys.argv[1:])
