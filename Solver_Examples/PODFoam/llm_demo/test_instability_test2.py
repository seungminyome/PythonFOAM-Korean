"""Tests for the instability test of 2026-11-01: requests without steps or times, the
fixed-gap triples and pictures drawn without the step and the time."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import instability_test2 as it2
import readable_image
import stability_request
from test_instability_test import frame_stub


def grid_mesh(nx=4, ny=3):
    """Unit squares, one per cell: centres (cells, 3) and the polygons render_field takes."""
    centres, points = [], []
    for j in range(ny):
        for i in range(nx):
            centres.append([i + 0.5, j + 0.5, 0.0])
            points += [[i, j, 0.0], [i + 1, j, 0.0], [i + 1, j + 1, 0.0], [i, j + 1, 0.0]]
    cells = nx * ny
    polygons = {"points": np.array(points), "offsets": np.arange(0, 4 * cells + 1, 4),
                "cells": np.arange(cells)}
    return np.array(centres), polygons, [[0.0, float(nx)], [0.0, float(ny)]]


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.images = {}
        for field in ("U", "p"):
            path = root / f"{field}.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + field.encode() * 8)
            self.images[field] = str(path)

    def frames(self, first_step, first_time_s):
        return [frame_stub(first_step + 200 * k, first_time_s + 2e-3 * k, self.images) for k in range(3)]

    def test_no_step_or_time_in_any_text_part(self):
        early, late = self.frames(1000, 0.105), self.frames(5000, 0.125)
        parts = it2.text_parts(it2.payload(early))
        self.assertEqual(parts[0], stability_request.STABILITY_V2OWN_SYSTEM_PROMPT)
        self.assertEqual(len(parts), 1 + 1 + 2 * 3)          # prompt, note, two captions per time
        for part in parts:
            for word in ("time_s", "step", "t = ", "t="):
                self.assertNotIn(word, part)
        # frames at other steps and times give the same text; only the pictures could differ
        self.assertEqual(it2.text_parts(it2.payload(late)), parts)
        note = json.loads(parts[1])
        self.assertEqual((note["times"], note["images"]), (3, 6))
        self.assertEqual(note["frames"][2], {"time": 3, "images": [5, 6]})

    def test_relative_times_are_the_same_string_in_every_item(self):
        relative = [0.0, 2e-3, 4e-3]
        parts = it2.text_parts(it2.payload(self.frames(1000, 0.105), relative))
        self.assertEqual(parts, it2.text_parts(it2.payload(self.frames(5000, 0.125), relative)))
        note = json.loads(parts[1])
        self.assertEqual([f["t_minus_t1_s"] for f in note["frames"]], relative)
        self.assertIn("Time 2: t - t1 = 0.002 s. Image 3: |U| in m/s.", parts)
        for part in parts:
            self.assertNotIn("time_s", part)
            self.assertNotIn("step", part)

    def test_three_frames_only(self):
        with self.assertRaises(ValueError):
            it2.payload(self.frames(1000, 0.105)[:2])


class TripleTests(unittest.TestCase):
    def test_crashed_triples_with_a_fixed_gap(self):
        run = {"name": "c", "crash_step": 50, "states": [{"run_step": k} for k in range(1, 50)]}
        items = it2.crashed_triples_fixed_gap(run, range(1, 4), 10, True)
        self.assertEqual([[f["run_step"] for f in i["frames"]] for i in items],
                         [[29, 39, 49], [28, 38, 48], [27, 37, 47]])
        self.assertEqual({(i["stability"], i["scored"], i["group"], i["gap_run_steps"]) for i in items},
                         {("unstable", True, "unstable-last", 10)})
        early = it2.crashed_triples_fixed_gap(run, [20], 10, False)
        self.assertEqual((early[0]["group"], early[0]["scored"]), ("unstable-early", False))
        with self.assertRaises(ValueError):                  # the first frame would be before step 1
            it2.crashed_triples_fixed_gap(run, [30], 10, True)
        gappy = {"name": "g", "crash_step": 50, "states": [{"run_step": k} for k in range(1, 50) if k != 39]}
        with self.assertRaises(ValueError):                  # a frame that was not written
            it2.crashed_triples_fixed_gap(gappy, [1], 10, True)

    def test_stable_triples_with_a_fixed_gap(self):
        states = [{"run_step": 10 * j, "time_s": 0.001 * j} for j in range(1, 101)]
        run = {"name": "s", "logged_steps": 1000, "states": states}
        items = it2.stable_triples_fixed_gap(run, 4, 2, np.random.default_rng(3), margin=100)
        self.assertEqual(len(items), 4)
        for item in items:
            steps = [f["run_step"] for f in item["frames"]]
            self.assertEqual((steps[1] - steps[0], steps[2] - steps[1]), (20, 20))
            self.assertEqual(item["gap_run_steps"], 20)
            self.assertLessEqual(steps[-1], 1000 - 100)
            self.assertEqual((item["stability"], item["scored"], item["group"]), ("stable", True, "stable"))
        uneven = dict(run, states=states[:50] + [dict(s, time_s=s["time_s"] + 1e-4) for s in states[50:]])
        with self.assertRaises(ValueError):
            it2.stable_triples_fixed_gap(uneven, 4, 2, np.random.default_rng(3), margin=100)


class PictureTests(unittest.TestCase):
    def setUp(self):
        import matplotlib
        matplotlib.use("Agg")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def draw(self, name, **options):
        import matplotlib.axes
        from PIL import Image
        centres, polygons, plotted = grid_mesh()
        titles, original = [], matplotlib.axes.Axes.set_title

        def record(ax, label, *args, **kwargs):
            titles.append(label)
            return original(ax, label, *args, **kwargs)
        with patch.object(matplotlib.axes.Axes, "set_title", record):
            readable_image.render_field(np.linspace(1.0, 2.0, len(centres)), polygons, centres, [0, 1],
                                        plotted, "U", 467, 0.10934, self.root / f"{name}.png", **options)
        with Image.open(self.root / f"{name}.png") as image:
            return titles, dict(image.text)

    def test_show_time_false_leaves_step_and_time_out(self):
        titles, text = self.draw("plain", show_time=False)
        self.assertEqual(len(titles), 1)
        self.assertNotIn("step", titles[0])
        self.assertNotIn("t = ", titles[0])
        self.assertTrue(titles[0].startswith("Velocity magnitude |U| (m/s)\n"))
        self.assertNotIn("Step", text)
        self.assertNotIn("Time", text)
        self.assertEqual((text["Field"], text["Style"]), ("U", readable_image.STYLE))

    def test_default_keeps_step_and_time(self):
        titles, text = self.draw("timed")
        self.assertIn(", step 467, t = 0.10934 s\n", titles[0])
        self.assertEqual((text["Step"], text["Time"]), ("467", "0.10934"))


if __name__ == "__main__":
    unittest.main()
