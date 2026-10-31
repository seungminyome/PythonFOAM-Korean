#!/usr/bin/env python3
"""Fill docs/evidence/2026-10-30-wrong-setup/ from the run data and write its manifest.

Usage: make_evidence.py copy <gpu job id> [<gpu job id> ...]   copies the records
       make_evidence.py manifest <source run> ...              writes manifest.json from what is there
       make_evidence.py refresh <source run> ...               copies the records named in LATER and writes manifest.json,
                                                               taking the other files' origins from the manifest there
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

REPOS = Path("/cluster/medbow/gscratch/syome/github_repos")
EV = REPOS / "PythonFOAM-setup/docs/evidence/2026-10-30-wrong-setup"
FLOW = REPOS / "flow-states-20261030"
HERE = REPOS / "wrong-setup-20261030"
SET = HERE / "wrong-setup-test-20261030"
ORIGIN = EV / ".origins.json"
SET_NAME = "wrong-setup-v2own"
FINAL_TESTS = os.environ.get("FINAL_TESTS", "none")


def rel(path):
    return str(Path(path).resolve().relative_to(REPOS))


class Copier:
    def __init__(self):
        self.origins = {}

    def copy(self, source, target):
        target = EV / target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        self.origins[str(target.relative_to(EV))] = {"source": rel(source), "kind": "byte-preserved"}

    def gzip(self, source, target):
        target = EV / target
        target.parent.mkdir(parents=True, exist_ok=True)
        data = Path(source).read_bytes()
        with open(target, "wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=raw, mtime=0) as stream:
                stream.write(data)
        self.origins[str(target.relative_to(EV))] = {"source": rel(source), "kind": "gzip copy",
                                                     "source_sha256": hashlib.sha256(data).hexdigest()}

    def tail(self, source, target, marker, kind):
        target = EV / target
        target.parent.mkdir(parents=True, exist_ok=True)
        text = Path(source).read_text()
        target.write_text(text[text.index(marker):])
        self.origins[str(target.relative_to(EV))] = {"source": f"{rel(source)}, from the line '{marker}' on", "kind": kind}


def copy_records(jobs):
    c = Copier()
    # the set: design, key, manifest, leak check, numbers, one text
    for name in ("manifest.json", "truth.private.json", "leak-check.json", "numbers.json"):
        c.copy(SET / name, f"test-set/{name}")
    c.copy(FLOW / "design.json", "test-set/design.json")
    body = json.loads((SET / "requests" / SET_NAME / "N1-step04500.request.json").read_bytes())
    for message in body["messages"]:
        if isinstance(message.get("content"), list):
            for part in message["content"]:
                if part.get("type") == "image_url":
                    part["image_url"]["url"] = part["image_url"]["url"].partition(",")[0]
    (EV / "test-set").mkdir(exist_ok=True)
    (EV / "test-set/request-text-example.json").write_bytes(
        json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))
    c.origins["test-set/request-text-example.json"] = {
        "source": f"{rel(SET)}/requests/{SET_NAME}/N1-step04500.request.json with the base64 picture data cut out",
        "kind": "derived"}
    # the runs' settings
    case = FLOW / "N1"
    c.copy(case / "system/controlDict", "flow/cases/controlDict")
    c.copy(case / "system/fvSchemes", "flow/cases/fvSchemes")
    c.copy(case / "system/fvSolution", "flow/cases/fvSolution")
    c.copy(case / "constant/transportProperties", "flow/cases/transportProperties")
    c.copy(FLOW / "M2-viscosity/constant/transportProperties", "flow/cases/transportProperties.M2-viscosity")
    c.copy(case / "constant/turbulenceProperties", "flow/cases/turbulenceProperties")
    c.tail(case / "0.1/p", "flow/cases/p-boundary.txt", "boundaryField", "derived")
    design = json.loads((FLOW / "design.json").read_text())
    for run in design["runs"]:
        c.tail(FLOW / run["name"] / "0.1/U", f"flow/cases/U-boundary.{run['name']}.txt", "boundaryField", "derived")
        c.gzip(FLOW / run["name"] / "log.pimpleFoam", f"flow/logs/{run['name']}.log.gz")
    c.copy(FLOW / "flow-check.json", "flow/flow-check.json")
    # the jobs
    for path in sorted((FLOW / "jobs").iterdir()):
        c.copy(path, f"job/{path.name}")
    for path in sorted((HERE / "jobs").iterdir()):
        if path.name.startswith("unit-tests-") and path.name != f"unit-tests-{FINAL_TESTS}.out":
            continue
        if path.name.startswith(("evidence-copy-", "final-checks-")):
            continue
        c.copy(path, f"job/{path.name}")
    c.copy(HERE / "contact-sheet.png", "contact-sheet.png")
    # the GPU jobs
    for job in jobs:
        out = HERE / "results" / f"window-test-{job}"
        c.copy(HERE / f"pod-window-test-{job}.out", f"job/window-test-{job}.out")
        for name in ("llama-server-version.txt", "modules.txt", "nvidia-smi.txt", "sha256.txt"):
            c.copy(out / name, f"runtime/window-test-{job}/{name}")
        if (out / "failed.txt").exists():
            c.copy(out / "failed.txt", f"runtime/window-test-{job}/failed.txt")
        for run_dir in sorted(p for p in out.iterdir() if p.is_dir() and (p / "run.json").exists()):
            key = run_dir.name
            c.copy(run_dir / "run.json", f"results/window-test-{job}/{key}/run.json")
            for name in ("metrics.jsonl", "summary.json"):
                c.copy(run_dir / SET_NAME / name, f"results/window-test-{job}/{key}/{SET_NAME}/{name}")
            c.copy(out / f"server-{key}.cmd", f"runtime/window-test-{job}/server/{key}.cmd")
            c.copy(out / f"gpu-{key}.txt", f"runtime/window-test-{job}/server/{key}.gpu.txt")
            c.copy(out / f"models-{key}.json", f"runtime/window-test-{job}/server/{key}.models.json")
            c.gzip(out / f"server-{key}.log", f"runtime/window-test-{job}/server/{key}.log.gz")
    for path in sorted((HERE / "reports").glob("*.md")):
        c.copy(path, f"reports/{path.name}")
    c.copy(HERE / "reports" / "reasons-to-judge.jsonl", "reasons-to-judge.jsonl")
    ORIGIN.write_text(json.dumps(c.origins, indent=1))
    print(len(c.origins), "files copied")


# Records made after the first copy: source under HERE, path in the evidence folder.
LATER = {"reason-judgement.json": "reason-judgement.json", "jobs/sacct.txt": "job/sacct.txt",
         "jobs/make_evidence.py": "job/make_evidence.py", "jobs/frame_facts.sbatch": "job/frame_facts.sbatch",
         "jobs/frame-facts-24947868.out": "job/frame-facts-24947868.out", "jobs/final_checks.sbatch": "job/final_checks.sbatch"}


def refresh(source_runs):
    copier = Copier()
    for source, target in LATER.items():
        copier.copy(HERE / source, target)
    known = json.loads((EV / "manifest.json").read_text())["files"]
    origins = {f["path"]: {k: f[k] for k in ("source", "kind", "source_sha256") if k in f} for f in known}
    origins.update(copier.origins)
    ORIGIN.write_text(json.dumps(origins, indent=1))
    write_manifest(source_runs)


SCOPE = ("Wrong-setup picture test of 2026-10-30 on MedicineBow: 80 requests, one per written state, |U| and p on their own "
         "colour scales in the window x 0 to 0.12 m, y 0 to 0.04 m, from five normal and five wrongly set-up pimpleFoam runs of "
         "the step case (8,000 steps each); the system prompt gives the intended setup and asks whether the pictures are "
         "consistent with it; Gemma 4 12B, 26B-A4B, 31B and Qwen3.5-35B-A3B; answer key, leak check, numbers from the arrays and "
         "logs, the reasons judged by one AI agent, what the frames hold, and a recount.")
NOTES = ["Sources are paths under /cluster/medbow/gscratch/syome/github_repos/ on MedicineBow, or 'written for this folder'.",
         "Files of kind gzip copy are gzip -9 copies (no name, mtime 0) of the named source; source_sha256 is the hash of the "
         "uncompressed bytes.",
         "Files of kind derived were cut from the named source as stated.",
         "Every byte-preserved file with a named path was compared with its source when this manifest was written."]


def write_manifest(source_runs):
    origins = json.loads(ORIGIN.read_text())
    files = []
    for path in sorted(p for p in EV.rglob("*") if p.is_file()):
        name = str(path.relative_to(EV))
        if name in ("manifest.json", ".origins.json") or "__pycache__" in name:
            continue
        data = path.read_bytes()
        entry = dict(origins.get(name, {"source": "written for this folder", "kind": "derived"}), path=name,
                     bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        if entry["kind"] == "byte-preserved":
            source = REPOS / entry["source"]
            if source.read_bytes() != data:
                raise SystemExit(f"{name}: differs from {source}")
        files.append({k: entry[k] for k in ("path", "source", "kind", "source_sha256", "bytes", "sha256") if k in entry})
    (EV / "manifest.json").write_text(json.dumps({"scope": SCOPE, "source_runs": source_runs, "notes": NOTES, "files": files},
                                                 indent=1, ensure_ascii=False) + "\n")
    ORIGIN.unlink()
    (EV / ".origins.keep.json").unlink(missing_ok=True)
    total = sum(f["bytes"] for f in files)
    print(f"{len(files)} files, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    if sys.argv[1] == "copy":
        copy_records(sys.argv[2:])
    elif sys.argv[1] == "refresh":
        refresh(sys.argv[2:])
    else:
        write_manifest(sys.argv[2:])
