#!/usr/bin/env python3
"""Period of the largest Courant number in the baseline case of the solver run.

Run in this folder:  python3 courant-spectrum.py   (needs numpy)
Reads suite/async-no-llm/telemetry.jsonl.gz (one line per step, 6000 steps of 5e-6 s) and prints
the range of the largest Courant number and the peak of its spectrum (Hann window, mean removed,
zero-padded to 2^18 points; the record is 0.03 s long, so its own resolution is about 33 Hz)."""
import gzip
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
with gzip.open(HERE / "suite" / "async-no-llm" / "telemetry.jsonl.gz", "rt") as handle:
    rows = [json.loads(line) for line in handle if line.strip()]
dt = rows[0]["delta_t_s"]
assert all(abs(r["delta_t_s"] - dt) < 1e-15 for r in rows)
c = np.array([r["courant"]["max"] for r in rows])
x = (c - c.mean()) * np.hanning(len(c))
spectrum = np.abs(np.fft.rfft(x, 2 ** 18))
freq = np.fft.rfftfreq(2 ** 18, dt)
band = (freq > 50) & (freq < 5000)
peak = freq[band][np.argmax(spectrum[band])]
print(json.dumps({"steps": len(c), "delta_t_s": dt, "courant_max_range": [round(float(c.min()), 3), round(float(c.max()), 3)],
                  "spectral_peak_hz": round(float(peak), 1), "period_ms": round(1000 / float(peak), 2),
                  "record_resolution_hz": round(1 / (len(c) * dt), 1)}, indent=1))
