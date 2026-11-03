"""Render cost: first render in a fresh process, second render, and a render in a forked child after a parent warm-up."""
import json, os, sys, time, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import numpy as np
import pod_image
case = Path(tempfile.mkdtemp())
os.environ["MPLCONFIGDIR"] = str(case / "mpl")
t = time.perf_counter(); pod_image.prepare_backend(case); imp = time.perf_counter() - t
centres = np.column_stack([np.linspace(-1, 1, 20), np.linspace(0, 0.1, 20), np.full(20, 0.005)])
state = {"step": 5, "time_s": 5e-7, "cells": 20}
U = np.ones((20, 3)); p = np.linspace(-1, 1, 20)
def render(tag):
    t = time.perf_counter()
    pod_image.render(state, centres, (1, 1, -1), U, p, case / tag)
    return round(time.perf_counter() - t, 3)
pid = os.fork()
if pid == 0:
    print(json.dumps({"child_cold_after_parent_import_only": render("c0")}), flush=True); os._exit(0)
os.waitpid(pid, 0)
r1 = render("p1"); r2 = render("p2")
pid = os.fork()
if pid == 0:
    print(json.dumps({"child_after_parent_warm_render": render("c1")}), flush=True); os._exit(0)
os.waitpid(pid, 0)
print(json.dumps({"import_s": round(imp, 3), "parent_first": r1, "parent_second": r2}))
