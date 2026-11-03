"""Does a minimal warm-up figure in the parent make the forked child's real render cheap?"""
import io, json, os, sys, time, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import numpy as np
import pod_image
case = Path(tempfile.mkdtemp()); os.environ["MPLCONFIGDIR"] = str(case / "mpl")
pod_image.prepare_backend(case)
centres = np.column_stack([np.linspace(-1, 1, 20), np.linspace(0, 0.1, 20), np.full(20, 0.005)])
state = {"step": 5, "time_s": 5e-7, "cells": 20}; U = np.ones((20, 3)); p = np.linspace(-1, 1, 20)
def render(tag):
    t = time.perf_counter(); pod_image.render(state, centres, (1, 1, -1), U, p, case / tag); return round(time.perf_counter() - t, 3)
def child(tag):
    pid = os.fork()
    if pid == 0:
        print(json.dumps({tag: render(tag)}), flush=True); os._exit(0)
    os.waitpid(pid, 0)
child("child_cold")
t = time.perf_counter()
import matplotlib.pyplot as plt
fig, axes = plt.subplots(2, 1, figsize=(2, 2), dpi=50)
for a in axes:
    s = a.scatter([0.0, 1.0], [0.0, 1.0], c=[0.0, 1.0], cmap="viridis", s=4)
    fig.colorbar(s, ax=a); a.set_title("warm", fontsize=10); a.set_xlabel("x [m]")
fig.suptitle("warm", fontsize=11)
fig.savefig(io.BytesIO(), format="png"); plt.close(fig)
warm = round(time.perf_counter() - t, 3)
child("child_after_minimal_warm")
print(json.dumps({"minimal_warm_s": warm}))
