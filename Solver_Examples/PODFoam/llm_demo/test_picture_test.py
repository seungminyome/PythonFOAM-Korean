"""Tests for the 2026-10-21 picture-reading test: OpenFOAM reader, pictures, requests, runner."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest

import numpy as np

import foam_fields
from llm_client import response_format
import picture_test as pt
import pod_image
import snapshot_runner
from test_ablation_runner import png_chunk
import zlib  # noqa: E402

HEADER = """FoamFile
{{
    version     2.0;
    format      {fmt};
    class       {cls};
    object      {obj};
}}
// comment
"""


def write_foam(path, cls, obj, body, fmt="ascii"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("/* banner */\n" + HEADER.format(fmt=fmt, cls=cls, obj=obj) + body)


def row_case(root, n=3):
    """n quads in a row along x (z is the empty direction); top and bottom faces left out."""
    mesh = Path(root) / "constant" / "polyMesh"
    index = lambda x, y, z: z * 2 * (n + 1) + y * (n + 1) + x
    points = [(x, y, z) for z in (0, 1) for y in (0, 1) for x in range(n + 1)]
    write_foam(mesh / "points", "vectorField", "points",
               f"{len(points)}\n(\n" + "\n".join(f"({x} {y} {z})" for x, y, z in points) + "\n)\n")
    faces, owner = [], []
    for i in range(n - 1):                       # internal faces at x = i + 1
        faces.append((index(i + 1, 0, 0), index(i + 1, 1, 0), index(i + 1, 1, 1), index(i + 1, 0, 1)))
        owner.append(i)
    faces.append((index(0, 0, 0), index(0, 0, 1), index(0, 1, 1), index(0, 1, 0)))
    owner.append(0)
    faces.append((index(n, 0, 0), index(n, 1, 0), index(n, 1, 1), index(n, 0, 1)))
    owner.append(n - 1)
    for z in (0, 1):                             # front (z = 0) then back (z = 1), both empty
        for i in range(n):
            faces.append((index(i, 0, z), index(i + 1, 0, z), index(i + 1, 1, z), index(i, 1, z)))
            owner.append(i)
    write_foam(mesh / "faces", "faceList", "faces", f"{len(faces)}\n(\n" +
               "\n".join("4(" + " ".join(map(str, f)) + ")" for f in faces) + "\n)\n")
    write_foam(mesh / "owner", "labelList", "owner", f"{len(owner)}\n(\n" + "\n".join(map(str, owner)) + "\n)\n")
    write_foam(mesh / "neighbour", "labelList", "neighbour",
               f"{n - 1}\n(\n" + "\n".join(str(i + 1) for i in range(n - 1)) + "\n)\n")
    write_foam(mesh / "boundary", "polyBoundaryMesh", "boundary", f"""3
(
    walls
    {{
        type            wall;
        inGroups        1(wall);
        nFaces          2;
        startFace       {n - 1};
    }}
    front
    {{
        type            empty;
        nFaces          {n};
        startFace       {n + 1};
    }}
    back
    {{
        type            empty;
        nFaces          {n};
        startFace       {2 * n + 1};
    }}
)
""")
    return mesh


class FoamFieldsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_first_empty_patch_polygons_in_face_order(self):
        mesh = row_case(self.root)
        points, offsets, cells = foam_fields.empty_patch_polygons(mesh)
        np.testing.assert_array_equal(offsets, [0, 4, 8, 12])
        np.testing.assert_array_equal(cells, [0, 1, 2])
        np.testing.assert_allclose(points[:4], [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]])
        np.testing.assert_allclose(points[8:], [[2, 0, 0], [3, 0, 0], [3, 1, 0], [2, 1, 0]])
        self.assertIsNotNone(pod_image.cell_polygons(points, offsets, cells, 3))

    def test_internal_fields_uniform_nonuniform_and_binary_refused(self):
        path = self.root / "U"
        write_foam(path, "volVectorField", "U",
                   "dimensions [0 1 -1 0 0 0 0];\ninternalField   nonuniform List<vector> \n2\n(\n(1 2 3)\n(4e-1 -5 6.5)\n)\n;\n")
        np.testing.assert_allclose(foam_fields.read_internal_field(path, 2), [[1, 2, 3], [0.4, -5, 6.5]])
        write_foam(path, "volScalarField", "p", "internalField   uniform 7;\n")
        np.testing.assert_allclose(foam_fields.read_internal_field(path, 3), [7, 7, 7])
        write_foam(path, "volVectorField", "U", "internalField   uniform (1 0 0);\n")
        np.testing.assert_allclose(foam_fields.read_internal_field(path, 2), [[1, 0, 0], [1, 0, 0]])
        write_foam(path, "volScalarField", "p", "internalField   nonuniform List<scalar> 3(1 2 3);\n")
        with self.assertRaises(ValueError):
            foam_fields.read_internal_field(path, 2)
        write_foam(path, "volScalarField", "p", "internalField uniform 1;\n", fmt="binary")
        with self.assertRaises(ValueError):
            foam_fields.read_internal_field(path, 1)


def frame_fixture(directory, centres, velocity, pressure, step=250, plotted=None):
    """A frame as pod_image writes it, without matplotlib (tiny PNG with the provenance chunk)."""
    directory = Path(directory)
    directory.mkdir(parents=True)
    np.savez_compressed(directory / "fields.npz", centres=centres, U=velocity, p=pressure,
                        step=np.array(step), time_s=np.array(step * 5e-7))
    fields_hash = pt.file_sha256(directory / "fields.npz")
    png = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    png += png_chunk(b"tEXt", b"FieldsSHA256\0" + fields_hash.encode())
    png += png_chunk(b"IDAT", zlib.compress(b"\0\0\0\0")) + png_chunk(b"IEND", b"")
    (directory / "state.png").write_bytes(png)
    x, y = centres[:, 0], centres[:, 1]
    meta = {"sha256": pt.sha256(png), "fields_sha256": fields_hash, "step": step, "time_s": step * 5e-7,
            "cells": len(centres), "projection_axes": ["x", "y"],
            "domain_extent_m": {"x": [float(x.min()), float(x.max())], "y": [float(y.min()), float(y.max())]},
            "panels": ["|U| (m/s)", "kinematic pressure p (m^2/s^2)"]}
    if plotted:
        meta["plotted_range_m"] = plotted
    (directory / "image-metadata.json").write_text(json.dumps(meta))
    return directory


class AnswerKeyTests(unittest.TestCase):
    def test_truth_matches_snapshot_runner_for_whole_domain_and_window(self):
        rng = np.random.default_rng(1)
        centres = np.column_stack([rng.uniform(-1, 1, 50), rng.uniform(0, 0.1, 50), np.full(50, 0.006)])
        velocity = rng.normal(size=(50, 3))
        pressure = rng.normal(size=50)
        with tempfile.TemporaryDirectory() as temp:
            for name, plotted in (("full", None), ("window", {"x": [-0.5, 0.5], "y": [0.0, 0.1]})):
                directory = frame_fixture(Path(temp) / name, centres, velocity, pressure, plotted=plotted)
                _, expected = snapshot_runner.load_frame(directory)
                meta = json.loads((directory / "image-metadata.json").read_text())
                box = meta.get("plotted_range_m", meta["domain_extent_m"])
                got = pt.truth_from_arrays(centres, velocity, pressure, [box["x"], box["y"]], 250, 250 * 5e-7)
                self.assertEqual(got, expected)

    def test_trend_designs_are_crossed_and_scored_as_designed(self):
        designs = pt.trend_designs()
        self.assertEqual(len(designs), 18)
        combos = {(d["max_speed_trend"], d["min_pressure_trend"], d["fastest_flow_region"]) for d in designs}
        self.assertEqual(len(combos), 18)
        # guessing the pressure trend from the speed trend (Bernoulli) is no better than a fixed answer
        partner = {"increasing": "more_negative", "decreasing": "less_negative", "roughly_constant": "roughly_constant"}
        guessed = sum(partner[d["max_speed_trend"]] == d["min_pressure_trend"] for d in designs)
        fixed = max(sum(d["min_pressure_trend"] == v for d in designs) for v in pt.TREND_DIPS)
        self.assertLessEqual(guessed, fixed)
        for word, (first, _, last) in pt.TREND_SPEEDS.items():
            self.assertEqual(snapshot_runner.trend(first, last)[0], word)
        mapping = {"decreasing": "more_negative", "increasing": "less_negative", "roughly_constant": "roughly_constant"}
        for word, (first, _, last) in pt.TREND_DIPS.items():
            self.assertEqual(mapping[snapshot_runner.trend(first, last)[0]], word)


class BaselineTests(unittest.TestCase):
    def test_fixed_answer_baselines(self):
        box = {"x": [0, 1], "y": [0, 1]}
        keys = [{"plotted_range_m": box, "fastest_flow": {"x_percent": x, "y_percent": 10.0},
                 "lowest_pressure": {"x_percent": 50.0, "y_percent": 50.0}} for x in (25.0, 26.0, 90.0)]
        self.assertEqual(pt.constant_answer_baseline("describe", keys), {"fastest_flow": 2, "lowest_pressure": 3})
        # two keys 16 % apart are both within 10 % of their midpoint, though not of each other
        apart = [{"plotted_range_m": box, "fastest_flow": {"x_percent": x, "y_percent": 50.0},
                  "lowest_pressure": {"x_percent": x, "y_percent": 50.0}} for x in (42.0, 58.0)]
        self.assertEqual(pt.constant_answer_baseline("describe", apart)["fastest_flow"], 2)
        words = [{"max_speed_trend": w, "min_pressure_trend": "less_negative", "fastest_flow_region": "same_place"}
                 for w in ("decreasing", "decreasing", "increasing")]
        self.assertEqual(pt.constant_answer_baseline("sequence", words),
                         {"max_speed_trend": 2, "min_pressure_trend": 3, "fastest_flow_region": 3})

    def test_own_range_prompt_differs_only_in_the_scale_sentences(self):
        a, b = pt.SEQUENCE_V2_SYSTEM_PROMPT, pt.SEQUENCE_V2OWN_SYSTEM_PROMPT
        self.assertIn("share one colour scale", a)
        self.assertIn("its own colour scale", b)
        for part in pt._SEQUENCE_V2.replace("{speed_from}", "{x}").replace("{pressure_from}", "{x}").replace(
                "{scale}", "{x}").split("{x}"):
            self.assertIn(part, a)
            self.assertIn(part, b)


class PictureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        backend = pod_image.prepare_backend(cls.root)
        if not backend["ready"]:
            raise unittest.SkipTest("matplotlib not available")
        points, offsets, cells = foam_fields.empty_patch_polygons(row_case(cls.root / "case"))
        cls.mesh = type("M", (), {})()
        cls.mesh.centres = np.array([[0.5, 0.5, 0.5], [1.5, 0.5, 0.5], [2.5, 0.5, 0.5]])
        cls.mesh.cells = 3
        cls.mesh.polygons = pod_image.cell_polygons(points, offsets, cells, 3)
        cls.mesh.views = {"full": [[0.0, 3.0], [0.0, 1.0]], "window": [[0.0, 3.0], [0.0, 1.0]]}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_v2_pictures_size_hashes_shared_range_and_repeatability(self):
        velocity = np.array([[3.0, 0, 0], [9.0, 0, 0], [5.0, 0, 0]])
        pressure = np.array([-2.0, 1.0, 0.5])
        frame, truth = pt.render_v2(self.mesh, "full", velocity, pressure, 250, 1.25e-4, self.root / "a")
        again, _ = pt.render_v2(self.mesh, "full", velocity, pressure, 250, 1.25e-4, self.root / "b")
        self.assertEqual(frame["image_sha256"], again["image_sha256"])
        for field in ("U", "p"):
            png = Path(frame["images"][field]).read_bytes()
            self.assertEqual(struct.unpack(">II", png[16:24]), (1024, 576))
        self.assertEqual(truth["fastest_flow"]["cell"], 1)
        self.assertEqual(truth["lowest_pressure"]["cell"], 0)
        loaded, loaded_truth = pt.load_v2(self.root / "a")
        self.assertEqual(loaded_truth, truth)
        shared, _ = pt.render_v2(self.mesh, "full", velocity, pressure, 500, 2.5e-4, self.root / "c",
                                 {"U": [0.0, 20.0], "p": [-5.0, 5.0]})
        meta = json.loads((self.root / "c" / "readable-metadata.json").read_text())
        self.assertEqual([i["colour_range"] for i in meta["images"]], [[0.0, 20.0], [-5.0, 5.0]])
        self.assertTrue(all(i["colour_range_shared"] for i in meta["images"]))
        (self.root / "a" / "U.png").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            pt.load_v2(self.root / "a")

    def test_v2_requests_carry_two_images_per_time_and_no_extrema(self):
        velocity = np.array([[3.0, 0, 0], [9.0, 0, 0], [5.0, 0, 0]])
        pressure = np.array([-2.0, 1.0, 0.5])
        frames = [pt.render_v2(self.mesh, "full", velocity * k, pressure * k, 100 * k, 5e-5 * k,
                               self.root / f"s{k}", {"U": [0.0, 30.0], "p": [-6.0, 3.0]})[0]
                  for k in (1, 2, 3)]
        describe = pt.describe_v2_payload(frames[0])
        parts = describe["messages"][1]["content"]
        self.assertEqual([p["type"] for p in parts], ["text", "text", "image_url", "text", "image_url"])
        self.assertIs(describe["cache_prompt"], False)
        self.assertEqual(describe["max_tokens"], pt.MAX_TOKENS)
        self.assertEqual(describe["messages"][0]["content"], pt.DESCRIBE_V2_SYSTEM_PROMPT)
        note = json.loads(parts[0]["text"])
        self.assertEqual(set(note), {"task", "step", "time_s", "cells", "images", "plotted_axes",
                                     "plotted_range_m", "percent_convention"})
        sequence = pt.sequence_v2_payload(frames)
        images = [p for p in sequence["messages"][1]["content"] if p["type"] == "image_url"]
        self.assertEqual(len(images), 6)
        self.assertEqual(images[0], pt._image_part(frames[0]["images"]["U"]))
        self.assertEqual(images[1], pt._image_part(frames[0]["images"]["p"]))
        with self.assertRaises(ValueError):
            pt.sequence_v2_payload(frames[::-1])

    def test_planted_peak_and_dip_are_the_answer_key_and_keep_direction(self):
        velocity = np.array([[3.0, 4.0, 0], [9.0, 0, 0], [5.0, 0, 0]])
        pressure = np.array([-2.0, 1.0, 0.5])
        new_velocity, new_pressure, levels = pt.planted_fields(self.mesh, "window", velocity, pressure,
                                                               [16.7, 50.0], [83.3, 50.0], sigma=5.0)
        truth = pt.truth_from_arrays(self.mesh.centres, new_velocity, new_pressure, self.mesh.views["window"], 1, 1e-6)
        self.assertEqual(truth["fastest_flow"]["cell"], 0)
        self.assertEqual(truth["lowest_pressure"]["cell"], 2)
        self.assertAlmostEqual(truth["max_speed_m_per_s"], 1.3 * 9.0)
        self.assertAlmostEqual(levels["low_m2_per_s2"], -2.0 - 0.3 * 3.0)
        np.testing.assert_allclose(new_velocity[0] / np.linalg.norm(new_velocity[0]), [0.6, 0.8, 0.0])

    def test_synthetic_spot_and_dip_are_the_answer_key(self):
        velocity, pressure = pt.synthetic_fields(self.mesh, "window", [50.0, 50.0], [16.7, 50.0], peak=60.0)
        truth = pt.truth_from_arrays(self.mesh.centres, velocity, pressure, self.mesh.views["window"], 1, 1e-6)
        self.assertEqual(truth["fastest_flow"]["cell"], 1)
        self.assertEqual(truth["lowest_pressure"]["cell"], 0)
        self.assertAlmostEqual(truth["max_speed_m_per_s"], 60.0)


@contextmanager
def fake_server():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(body)
            properties = body["response_format"]["json_schema"]["schema"]["properties"]
            if "fastest_flow_x_percent" in properties:
                output = {"flow_description": "fast near the step", "fastest_flow_x_percent": 26,
                          "fastest_flow_y_percent": 11, "lowest_pressure_x_percent": 90,
                          "lowest_pressure_y_percent": 90, "uncertainties": "none"}
            elif "max_speed_trend" in properties:
                output = {"change_description": "slower", "max_speed_trend": "decreasing",
                          "min_pressure_trend": "cannot_tell", "fastest_flow_region": "same_place",
                          "uncertainties": "none"}
            else:
                output = {"observations": "Maximum speed 82.5 m/s.", "possible_interpretation": "May be inflow.",
                          "checks": "Check the inlet."}
            content = json.dumps({"choices": [{"message": {"content": json.dumps(output)}, "finish_reason": "stop"}],
                                  "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                                  "timings": {"cache_n": 0}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions", seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_set(self):
        centres = np.array([[0.0, 0.0, 0.0], [0.26, 0.11, 0.0], [0.9, 0.9, 0.0], [1.0, 1.0, 0.0]])
        velocity = np.array([[1.0, 0, 0], [8.0, 0, 0], [2.0, 0, 0], [1.0, 0, 0]])
        pressure = np.array([0.0, 1.0, -4.0, 0.5])
        frames, truths = [], []
        for k, step in enumerate((250, 750, 1250)):
            directory = frame_fixture(self.root / f"frame{k}", centres, velocity * (1 - 0.1 * k), pressure, step)
            frame, truth = snapshot_runner.load_frame(directory)
            frames.append(frame)
            truths.append(truth)
        builder = pt.Builder(self.root / "set")
        builder.add("flow-describe-v1", "d1", "describe", pt.describe_v1_payload(frames[0]), truths[0], {})
        builder.add("flow-sequence-v1", "s1", "sequence", pt.sequence_v1_payload(frames),
                    snapshot_runner.sequence_truth(truths), {})
        observe = {"model": pt.DEFAULT_MODEL, "messages": [{"role": "user", "content": "x"}],
                   "temperature": 0.0, "max_tokens": 192, "stream": False,
                   "response_format": response_format("observe")}
        truth17 = {"max_speed_m_per_s": 82.5, "max_speed_cells": [1], "max_speed_centres_m": [[0.0005, 0.0127, 0.006]],
                   "unique_maximum": True, "minimum_pressure_m2_per_s2": -3.0, "step": 5, "time_s": 5e-7}
        builder.add("oct17-paired", "pair-001-numeric_only", "observe", observe, truth17, {"condition": "numeric_only"})
        builder.extra["oct17_numeric_summary"] = {"step": 5, "time_s": 5e-7, "cells": 3}
        pt.write_json(builder.output / "truth.private.json", builder.truth)
        pt.write_json(builder.output / "manifest.json", {"requests": builder.entries, "extra": builder.extra})
        return builder.output

    def test_run_scores_each_mode_and_sends_only_the_new_model_name(self):
        test_set = self.make_set()
        with fake_server() as (endpoint, seen):
            code = pt.main(["run", "--test-set", str(test_set), "--sets", "oct17-paired", "flow-describe-v1",
                            "flow-sequence-v1", "--model", "other-model", "--endpoint", endpoint,
                            "--output", str(self.root / "out")])
        self.assertEqual(code, 0)
        self.assertEqual({b["model"] for b in seen}, {"other-model"})
        manifest = json.loads((test_set / "manifest.json").read_text())
        sent = {json.dumps(b, sort_keys=True) for b in seen}
        for entry in manifest["requests"]:
            original = json.loads((test_set / entry["file"]).read_text())
            original["model"] = "other-model"
            self.assertIn(json.dumps(original, sort_keys=True), sent)
        describe = json.loads((self.root / "out" / "flow-describe-v1" / "summary.json").read_text())["by_mode"]["describe"]
        self.assertEqual(describe["fastest_flow"]["within_10_percent"], 1)
        self.assertEqual(describe["lowest_pressure"]["within_10_percent"], 1)
        sequence = json.loads((self.root / "out" / "flow-sequence-v1" / "summary.json").read_text())["by_mode"]["sequence"]
        self.assertEqual(sequence["max_speed_trend"]["match"], 1)
        self.assertEqual(sequence["min_pressure_trend"]["cannot_tell"], 1)
        paired = json.loads((self.root / "out" / "oct17-paired" / "summary.json").read_text())
        self.assertEqual(paired["attempted"], 1)
        self.assertEqual(paired["prompt_tokens"], [10])
        self.assertEqual(paired["by_mode"]["observe"]["paired"]["numeric_only"]["attempted"], 1)
        code = pt.main(["report", str(self.root / "out"), "--output", str(self.root / "report.md")])
        self.assertEqual(code, 0)
        table = (self.root / "report.md").read_text()
        self.assertIn("| other-model | flow-describe-v1 | describe | 1/1 | 1/1 | 1/1 |", table)
        self.assertIn("| other-model | flow-sequence-v1 | sequence | 1/1 |  |  | 1/1 | 0/1 | 1/1 |", table)

    def test_a_set_with_both_modes_is_summarised_per_mode_and_missing_summaries_are_flagged(self):
        test_set = self.make_set()
        manifest = json.loads((test_set / "manifest.json").read_text())
        truth = json.loads((test_set / "truth.private.json").read_text())
        for entry in manifest["requests"]:
            if entry["set"] in ("flow-describe-v1", "flow-sequence-v1"):
                truth[f"oct20-replay/{entry['name']}"] = truth[f"{entry['set']}/{entry['name']}"]
                entry["set"] = "oct20-replay"
                entry["sources"] = {"replay": "describe-full" if entry["mode"] == "describe" else "sequence-full"}
        pt.write_json(test_set / "truth.private.json", truth)
        pt.write_json(test_set / "manifest.json", manifest)
        with fake_server() as (endpoint, _):
            code = pt.main(["run", "--test-set", str(test_set), "--sets", "oct20-replay", "flow-describe-v2",
                            "--model", "m", "--endpoint", endpoint, "--output", str(self.root / "out")])
        self.assertEqual(code, 0)
        summary = json.loads((self.root / "out" / "oct20-replay" / "summary.json").read_text())
        self.assertEqual(set(summary["by_mode"]), {"describe", "sequence"})
        self.assertEqual(set(summary["by_group"]), {"describe-full", "sequence-full"})
        (self.root / "out" / "flow-describe-v2" / "summary.json").unlink()
        code = pt.main(["report", str(self.root / "out"), "--output", str(self.root / "report.md")])
        self.assertEqual(code, 1)
        self.assertIn("no summary (run incomplete)", (self.root / "report.md").read_text())

    def test_changed_request_file_is_refused(self):
        test_set = self.make_set()
        self.assertEqual(pt.main(["check", "--test-set", str(test_set)]), 0)
        path = next((test_set / "requests" / "flow-describe-v1").glob("*.json"))
        path.write_bytes(path.read_bytes().replace(b"describe", b"Describe", 1))
        self.assertEqual(pt.main(["check", "--test-set", str(test_set)]), 1)
        with fake_server() as (endpoint, _):
            with self.assertRaises(ValueError):
                pt.main(["run", "--test-set", str(test_set), "--sets", "flow-describe-v1", "--model", "m",
                         "--endpoint", endpoint, "--output", str(self.root / "out")])


if __name__ == "__main__":
    unittest.main()
