"""telemetry.jsonl and the kept states against main's callback (fork only: needs docs/evidence)."""
import os
from pathlib import Path
import tracemalloc
import unittest
from unittest.mock import patch

import numpy as np

import test_callback
from test_callback import SOURCE, telemetry_state

# python_module.py of main at 2ed6da2, the last callback that kept every state for telemetry.jsonl,
# kept with the evidence of 2026-10-28. The tests that compare with it are skipped in a copy of the
# code without the repository's docs/; in a checkout with docs/ a missing copy is an error.
MAIN_CALLBACK = SOURCE.parents[2] / "docs/evidence/2026-10-28-callback/callback-main/python_module.py"
needs_main = unittest.skipUnless(MAIN_CALLBACK.exists() or (SOURCE.parents[2] / "docs").is_dir(),
                                 f"main's callback for the comparison is not here: {MAIN_CALLBACK}")


class MainTelemetryTests(unittest.TestCase):
    setUp = test_callback.TelemetryTests.setUp
    load = test_callback.TelemetryTests.load
    drive = test_callback.TelemetryTests.drive

    def main_telemetry(self, states, name="main"):
        """telemetry.jsonl as main writes it: every state kept, all written by _dump_telemetry."""
        old, case = self.load(MAIN_CALLBACK, name)
        self.drive(old, states, 0)   # LLM_FINAL_STEP=0: never final, so nothing is forked
        with patch.dict(os.environ, self.environment):   # main reads LLM_RUN_ID when it writes
            try:
                old._dump_telemetry()
            except TypeError:
                pass   # a state that cannot be encoded; main leaves the lines before it in the .tmp
        return old, case

    @needs_main
    def test_bytes_equal_main_over_many_steps_and_any_batch_size(self):
        steps = 2345
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]
        old, main_case = self.main_telemetry(states)
        expected = (main_case / "telemetry.jsonl").read_bytes()
        self.assertEqual(len(expected.splitlines()), steps)
        self.assertIn("Résidu ✓".encode(), expected)
        self.assertIn(b'"feature_status":"partial_nonfinite"', expected)
        for batch in (500, 50):
            with self.subTest(batch=batch):
                new, case = self.load(SOURCE / "python_module.py", f"new-{batch}",
                                      lambda module: setattr(module._telemetry, "BATCH_LINES", batch))
                self.drive(new, states, steps)
                self.assertEqual((case / "telemetry.jsonl").read_bytes(), expected)
                self.assertFalse((case / "telemetry.jsonl.tmp").exists())
                self.assertEqual((new._telemetry.appends, new._telemetry.failed_appends),
                                 (steps // batch + 1, 0))
                self.assertEqual(len(new._recent_states), 3)
        # what later code reads of the kept states: the residual trend and the window start
        snapshots = [np.full((20, 3), float(k)) for k in range(1, 6)]
        old._snapshots, new._snapshots = list(snapshots), list(snapshots)
        with patch.dict(os.environ, self.environment):
            summary_old = old._summarize(old._history[-1])[0]
            summary_new = new._summarize(new._recent_states[-1])[0]
        self.assertEqual(summary_new, summary_old)
        self.assertEqual(summary_new["velocity_svd"]["window_start_time_s"],
                         float(format(states[0]["time_s"], ".6g")))   # the summary keeps 6 digits
        self.assertEqual(summary_new["residuals"]["p"]["recent_initial_first"],
                         [float(format(s["residuals"]["p"]["initial_first"], ".6g")) for s in states[-3:]])

    @needs_main
    def test_memory_stays_flat_over_a_long_run(self):
        steps = 6000
        states = [telemetry_state(step, steps) for step in range(1, steps + 1)]
        grown = {}
        for name, source in (("main", MAIN_CALLBACK), ("new", SOURCE / "python_module.py")):
            callback, case = self.load(source, name)
            self.drive(callback, states, 0, until=1000)
            tracemalloc.start()
            try:
                before = tracemalloc.get_traced_memory()[0]
                with patch.dict(os.environ, dict(self.environment, LLM_FINAL_STEP="0")):
                    for state in states[1000:]:
                        callback.analysis_func(state)
                grown[name] = tracemalloc.get_traced_memory()[0] - before
            finally:
                tracemalloc.stop()
            if name == "new":
                self.assertLessEqual(callback._telemetry.pending_lines, callback._telemetry.BATCH_LINES)
                self.assertEqual(callback._telemetry.lines, steps)
        # main kept every state (about 1.35 KiB each); the callback now keeps at most a batch of lines
        self.assertGreater(grown["main"], 4 << 20)
        self.assertLess(grown["new"], 1 << 20)


if __name__ == "__main__":
    unittest.main()
