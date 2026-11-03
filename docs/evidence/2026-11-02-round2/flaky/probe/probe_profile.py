import cProfile, pstats, io, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import numpy as np, pod_image
case = Path(tempfile.mkdtemp()); os.environ["MPLCONFIGDIR"] = str(case / "mpl"); pod_image.prepare_backend(case)
centres = np.column_stack([np.linspace(-1, 1, 20), np.linspace(0, 0.1, 20), np.full(20, 0.005)])
state = {"step": 5, "time_s": 5e-7, "cells": 20}; U = np.ones((20, 3)); p = np.linspace(-1, 1, 20)
pr = cProfile.Profile(); pr.enable()
pod_image.render(state, centres, (1, 1, -1), U, p, case / "a")
pr.disable(); s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(28); print(s.getvalue()[:6000])
