#!/usr/bin/env python3
"""Tests of wrong_setup_test2.py: the paired design, the changes written to a case, the two
request conditions, the leak check on paired texts, the scorer, the baselines and the statistics.
No OpenFOAM, no model, no pictures."""
import json
import math
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wrong_setup_test as ws  # noqa: E402
import wrong_setup_test2 as w2  # noqa: E402
from llm_client import RESPONSE_SCHEMAS, encode_json  # noqa: E402

FIELD = """FoamFile
{
    version     2.0;
    format      ascii;
    class       volVectorField;
    location    "0.1";
    object      U;
}
dimensions      [0 1 -1 0 0 0 0];
internalField   nonuniform List<vector> 2((1 0 0) (2 0 0));
boundaryField
{
    inlet
    {
        type            fixedValue;
        value           uniform (32.2 0 0);
    }
    outlet
    {
        type            zeroGradient;
    }
    upperWall
    {
        type            noSlip;
    }
    lowerWall
    {
        type            noSlip;
    }
}
"""
TRANSPORT = "transportModel  Newtonian;\nnu              [0 2 -1 0 0 0 0] 1.56e-05;\n"
CONTROL = "startTime 0;\nendTime 0.1;\ndeltaT 5e-7;\nwriteControl runTime;\nwriteInterval 0.001;\nadjustTimeStep no;\n"


def tiny_png():
    """A valid 1 x 1 grey PNG."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x80")) + chunk(b"IEND", b""))


def fake_long_case(root):
    """A developed case with one written state and no mesh: enough for prepare's copying."""
    long_case = Path(root) / "long"
    (long_case / "system").mkdir(parents=True)
    (long_case / "constant").mkdir()
    (long_case / "system" / "controlDict").write_text(CONTROL)
    (long_case / "constant" / "transportProperties").write_text(TRANSPORT)
    for start in w2.STARTS:
        (long_case / start).mkdir()
        (long_case / start / "U").write_text(FIELD.replace('"0.1"', f'"{start}"'))
        (long_case / start / "p").write_text(FIELD.replace("volVectorField", "volScalarField").replace("object      U", "object      p")
                                             .replace("nonuniform List<vector> 2((1 0 0) (2 0 0))", "nonuniform List<scalar> 2(0 1)"))
        (long_case / start / "phi").write_text("phi")
    return long_case


class Design(unittest.TestCase):
    def test_thirty_changes_of_four_kinds(self):
        from collections import Counter
        kinds = Counter(k for k, _ in w2.CHANGES)
        self.assertEqual(len(w2.CHANGES), 30)
        self.assertEqual(set(kinds), {"inlet_speed", "viscosity", "walls", "inlet_profile"})

    def test_bases_are_drawn_inside_the_ranges_and_repeat_with_the_seed(self):
        a, b = w2.draw_bases(30, 7), w2.draw_bases(30, 7)
        self.assertEqual(a, b)
        for speed, nu, start in a:
            self.assertTrue(w2.SPEED_RANGE[0] <= speed <= w2.SPEED_RANGE[1])
            self.assertTrue(w2.NU_RANGE[0] <= nu <= w2.NU_RANGE[1])
            self.assertIn(start, w2.STARTS)
        self.assertNotEqual(a, w2.draw_bases(30, 8))

    def test_prepare_writes_pairs_with_the_same_stated_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_case = fake_long_case(tmp)
            changes = [["inlet_speed", 0.5], ["viscosity", 10], ["walls", "both"]]
            Path(tmp, "changes.json").write_text(json.dumps(changes))
            args = type("A", (), {"long": str(long_case), "output": str(Path(tmp) / "out"), "seed": 3,
                                  "pilot": False, "changes": str(Path(tmp, "changes.json"))})
            self.assertEqual(w2.prepare(args), 0)
            design = json.loads((Path(tmp) / "out" / "design.json").read_text())
            runs = design["runs"]
            self.assertEqual([r["name"] for r in runs], ["B1-N", "B1-W", "B2-N", "B2-W", "B3-N", "B3-W"])
            for normal, wrong in zip(runs[::2], runs[1::2]):
                self.assertEqual(normal["stated"], wrong["stated"])
                self.assertEqual(normal["base"], wrong["base"])
                self.assertEqual(normal["cause"], "none")
                self.assertEqual(wrong["cause"], wrong["change"]["kind"])
            self.assertEqual(sorted(r["change"]["kind"] for r in runs[1::2]), ["inlet_speed", "viscosity", "walls"])
            for run in runs:
                text = (Path(run["case"]) / "0.1" / "U").read_text()
                self.assertEqual(ws.read_patch(text, "inlet")["value"][0], run["expected_patches"]["inlet"]["value"][0])
                control = (Path(run["case"]) / "system" / "controlDict").read_text()
                self.assertIn("deltaT 5e-06;", control)
                self.assertIn("writeInterval 500;", control)
            wrong_nu = next(r for r in runs if r["change"]["kind"] == "viscosity")
            self.assertAlmostEqual(wrong_nu["nu"], wrong_nu["stated"]["nu_m2_per_s"] * 10)
            transport = (Path(wrong_nu["case"]) / "constant" / "transportProperties").read_text()
            self.assertIn(f"{wrong_nu['nu']:.6g}", transport)
            walls = next(r for r in runs if r["change"]["kind"] == "walls")
            text = (Path(walls["case"]) / "0.1" / "U").read_text()
            self.assertEqual(ws.read_patch(text, "lowerWall")["type"], "slip")
            self.assertEqual(ws.read_patch(text, "upperWall")["type"], "slip")

    def test_change_texts_name_the_values(self):
        self.assertIn("3.1 m/s instead of 31 m/s", w2.change_text("inlet_speed", 0.1, 31.0, 1.5e-5))
        self.assertIn("instead of 1.5e-05", w2.change_text("viscosity", 100, 31.0, 1.5e-5))
        self.assertIn("lowerWall slip", w2.change_text("walls", "lower", 31.0, 1.5e-5))
        self.assertIn("0.25", w2.change_text("inlet_profile", 0.25, 31.0, 1.5e-5))


class Requests(unittest.TestCase):
    def frame(self, tmp):
        for name in ("U.png", "p.png"):
            Path(tmp, name).write_bytes(tiny_png())
        return {"step": 8000, "time_s": 0.14, "cells": 20540, "plotted_range_m": {"x": [0, 0.12], "y": [0, 0.04]},
                "images": {"U": str(Path(tmp, "U.png")), "p": str(Path(tmp, "p.png"))}, "directory": tmp}

    def test_stated_note_carries_the_setup_and_blind_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame = self.frame(tmp)
            stated = {"inlet_speed_m_per_s": 25.5, "nu_m2_per_s": 1.2e-5}
            try:
                RESPONSE_SCHEMAS[w2.MODE] = w2.SCHEMA
                a = w2.payload(frame, w2.STATED, stated, 0.0, 1)
                b = w2.payload(frame, w2.BLIND, stated, 0.7, 2)
            finally:
                RESPONSE_SCHEMAS.pop(w2.MODE, None)
            note_a = json.loads(a["messages"][1]["content"][0]["text"])
            note_b = json.loads(b["messages"][1]["content"][0]["text"])
            self.assertEqual(note_a["intended_setup"]["inlet_speed_m_per_s"], 25.5)
            self.assertNotIn("intended_setup", note_b)
            self.assertIn("intended inlet speed and kinematic viscosity", a["messages"][0]["content"])
            self.assertIn("not given", b["messages"][0]["content"])
            self.assertEqual((a["temperature"], a["seed"]), (0.0, 1))
            self.assertEqual((b["temperature"], b["seed"]), (0.7, 2))
            self.assertEqual(a["response_format"]["json_schema"]["schema"]["properties"]["cause"]["enum"], list(w2.CAUSES))
            for text in (a["messages"][0]["content"], b["messages"][0]["content"]):
                self.assertNotIn("slip instead", text)
                self.assertNotIn("mistake", text)

    def test_scorer_knows_right_for_the_right_reason(self):
        truth = {"assessment": "inconsistent", "cause": "viscosity"}
        good = w2.score_reply({"reason": "x", "assessment": "inconsistent", "cause": "viscosity"}, truth)
        wrong_cause = w2.score_reply({"reason": "x", "assessment": "inconsistent", "cause": "walls"}, truth)
        miss = w2.score_reply({"reason": "x", "assessment": "consistent", "cause": "none"}, truth)
        self.assertTrue(good["assessment"]["match"] and good["cause"]["right_for_right_reason"])
        self.assertTrue(wrong_cause["assessment"]["match"] and not wrong_cause["cause"]["right_for_right_reason"])
        self.assertFalse(miss["assessment"]["match"])

    def test_the_mode_exists_only_while_a_command_runs(self):
        self.assertNotIn(w2.MODE, RESPONSE_SCHEMAS)
        with self.assertRaises(SystemExit):
            w2.main(["prepare", "--help"])
        self.assertNotIn(w2.MODE, RESPONSE_SCHEMAS)


class Leak(unittest.TestCase):
    def body(self, setup, step, png=b"\x89PNG"):
        note = {"task": "t", "step": step, "time_s": 0.1 + step * 5e-6}
        if setup is not None:
            note["intended_setup"] = setup
        return encode_json({"messages": [{"role": "system", "content": "s"},
                                         {"role": "user", "content": [{"type": "text", "text": encode_json(note).decode()},
                                                                      {"type": "image_url", "image_url": {"url": "data:image/png;base64,"
                                                                       + __import__("base64").b64encode(png).decode()}}]}]})

    def test_paired_setups_give_nothing_away_but_unpaired_ones_do(self):
        import ablation_runner
        original = ablation_runner.png_text
        w2.png_text = lambda png: {"Step": "8000", "Time": "0.14"}
        try:
            paired = {"a": self.body({"u": 1}, 8000), "b": self.body({"u": 1}, 8000), "c": self.body({"u": 2}, 8000), "d": self.body({"u": 2}, 8000)}
            classes = {"a": "normal", "b": "wrong", "c": "normal", "d": "wrong"}
            saved_size, ws.png_size = ws.png_size, (lambda png: (1, 1))
            out = w2.leak_check(paired, classes)
            self.assertEqual(out["problems"], [])
            self.assertEqual(out["bodies_apart_from_pictures_step_time_setup"], 1)
            unpaired = dict(paired, d=self.body({"u": 3}, 8000))
            out = w2.leak_check(unpaired, classes)
            self.assertTrue(any("rule on the request text" in p for p in out["problems"]))
        finally:
            w2.png_text = original
            ws.png_size = saved_size


class Statistics(unittest.TestCase):
    def test_mcnemar_exact(self):
        same = w2.mcnemar_exact([True, False, True], [True, False, True])
        self.assertEqual((same["a_only"], same["b_only"], same["p"]), (0, 0, 1.0))
        out = w2.mcnemar_exact([True] * 10 + [False] * 0, [False] * 10)
        self.assertEqual((out["a_only"], out["b_only"]), (10, 0))
        self.assertAlmostEqual(out["p"], 2 / 2 ** 10)

    def test_bootstrap_interval_contains_the_share(self):
        by_base = {b: [1 if b % 3 else 0, 1] for b in range(30)}
        low, high = w2.bootstrap_ci(by_base, draws=500)
        self.assertTrue(low <= 20 / 30 <= high)

    def test_classifier_never_sees_the_held_out_pair(self):
        rng = np.random.default_rng(0)
        keys, rows = {}, {}
        for base in range(12):
            for cls in ("normal", "wrong"):
                name = f"B{base}-{cls[0]}"
                keys[name] = {"class": cls, "base": base}
                rows[name] = {"f": (1.0 if cls == "wrong" else -1.0) + rng.normal(0, 0.2), "g": rng.normal()}
        answers = w2.classifier_answers(keys, rows, ("f", "g"))
        right = sum(answers[n] == w2.RIGHT_WORD[k["class"]] for n, k in keys.items())
        self.assertGreaterEqual(right, 22)
        self.assertEqual(set(answers), set(keys))

    def test_peak_rule_uses_each_runs_stated_speed(self):
        keys = {"a": {"numeric": {"max_speed_m_per_s": 30.0}, "stated": {"inlet_speed_m_per_s": 20.0}},
                "b": {"numeric": {"max_speed_m_per_s": 30.0}, "stated": {"inlet_speed_m_per_s": 40.0}}}
        self.assertEqual(w2.peak_rule_answers(keys), {"a": "consistent", "b": "inconsistent"})


if __name__ == "__main__":
    unittest.main()
