#!/usr/bin/env python3
"""Fill docs/evidence/2026-11-02-round2/ from the round-2 work folders and write its manifest.

Usage: make_evidence.py copy <evidence dir>       copies the records listed below (small text records only)
       make_evidence.py final <evidence dir>      adds final-branches/: the checks of the final PR branches
                                                  and of the fork's main (2026-11-02 evening), and replaces
                                                  gpu-suites/records/async_v2-version-override.patch by a
                                                  plain `git diff c82c835^ c82c835`
       make_evidence.py r6 <evidence dir>         adds the records named in decision G7 and the r6 rebuild:
                                                  the Docker end-to-end runs 25090624, 25092824 and 25093622, the load
                                                  runs 25089961 to 25089963 of the November tree
                                                  276ea8e, the r6 PR-branch rebuild check, and their sacct rows
       make_evidence.py r7 <evidence dir>         adds final-branches/pr-docs-r7/: the r7 PR-branch rebuild
                                                  (doc and commit-message changes only) and its check
       make_evidence.py r8 <evidence dir>         adds final-branches/pr-docs-r8/: the r8 PR-branch rebuild
                                                  (doc and commit-message changes only) and its check
       make_evidence.py r9 <evidence dir>         adds final-branches/pr-docs-r9/: the r9 PR-branch rebuild
                                                  (doc and commit-message changes only) and its check
       make_evidence.py r10 <evidence dir>        adds final-branches/pr-docs-r10/: the r10 PR-branch rebuild
                                                  (doc and commit-message changes only) and its check
       make_evidence.py r11 <evidence dir>        adds final-branches/pr-docs-r11/: the r11 PR-branch rebuild
                                                  (doc and commit-message changes only) and its check
       make_evidence.py r12 <evidence dir>        adds final-branches/pr-docs-r12/: the r12 PR-branch rebuild
                                                  (doc and commit-message changes only) and its check
       make_evidence.py r13 <evidence dir>        adds final-branches/pr-docs-r13/: the r13 PR-branch rebuild
                                                  (doc and commit-message changes only; commits 1-5 kept) and its check
       make_evidence.py r14 <evidence dir>        adds final-branches/pr-docs-r14/: the r14 PR-branch rebuild
                                                  (doc changes only; commits 1-5 kept) and its check
       make_evidence.py manifest <evidence dir>   writes manifest.json from what is there

The manifest has the shape of docs/evidence/2026-10-30-versions/manifest.json: source_runs, scope, notes
and one entry per file with path, source, kind (byte-preserved, gzip copy, derived, record), bytes and
sha256. Files of kind "gzip copy" are gzip -9 copies (no name, mtime 0) of a solver or test log;
source_sha256 is the hash of the uncompressed bytes. check_manifest.py reads the same fields.

The copy step writes the work file .origins.json; the manifest step reads it, writes manifest.json
and deletes it. A later manifest run (after editing README.md) takes source and kind of each file
from the existing manifest.json, so the work file is not needed again.
"""
import fnmatch
import gzip
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

REPOS = Path("/cluster/medbow/gscratch/syome/github_repos")
R2 = REPOS / "pod-versions-20261030/r2"
TOOLS = REPOS / "pod-versions-20261030/r3/docs/tools"
ORIGINS = ".origins.json"

# (evidence subfolder, source folder under r2, patterns relative to that folder, kind)
# kind "copy" keeps the bytes, "gzip" stores a gzip copy with ".gz" appended.
SPEC = [
    ("pfinal", "pfinal", [
        "README.md", "source-excerpts.md", "verify-20261102.txt",
        "source/*/version-info.txt",
        "demo/run_demo.sbatch", "demo/inner.sh", "demo/summarize.py",
        "demo/slurm/pfinal-demo-25080017.out",
        "demo/runs-25080017/summary.md", "demo/runs-25080017/summary.json",
        "demo/runs-25080017/v2106/case-fork-n1/system/fvSolution",
        "demo/runs-25080017/*/case-*/exit-status",
    ], "copy"),
    ("pfinal", "pfinal", ["demo/runs-25080017/*/case-*/log.solver"], "gzip"),
    ("siblings", "siblings", [
        "round2/summary-all.json",
        "runs/*/result.json",
        "round2/runs/PODFoam_Debug-8-shipped-25088384/result.json",
        "round2/runs/APMOSFoam-8-shipped-25088463/result.json",
        "round2/runs/AEFoam-8-shipped-25088388/result.json",
        "round2/runs/PODFoam_Debug-v2106-stab-25088385/result.json",
        "round2/runs/APMOSFoam-v2106-stab-25088387/result.json",
        "round2/runs/AEFoam-v2106-stab-25088389/result.json",
        "round2/runs/*/summary.txt", "round2/runs/*/ported.diff",
        "logs/sib-*.out", "logs/jobs.txt",
        "round2/logs/sib2-*.out", "round2/logs/jobs.txt",
        "scripts/compare.py", "scripts/inner.sh", "scripts/make_modules.py", "scripts/siblings.sbatch",
        "round2/scripts/compare2.py", "round2/scripts/inner2.sh", "round2/scripts/port_patch.py",
        "round2/scripts/sib2.sbatch", "round2/scripts/test_ae.sbatch", "round2/scripts/test_ae_keras.py",
        "round2/static/*.txt", "round2/static/*.diff",
        "modules/*/module-copy.py", "modules/*/module-recording.py",
    ], "copy"),
    ("scenarios", "scenarios", [
        "scen-v2012/scenarios.json", "scen-v2212/scenarios.json",
        "sched-v2012/schedule.json", "sched-v2212/schedule.json",
        "scenx-*/extra.json",
        "slurm/*.out",
        "compare4.json", "compare4.py", "compare_sched4.json", "compare_sched4.py",
        "compare_extra.json", "compare_extra.py", "messages.json", "messages.py", "msgdiff.py",
        "extra.py", "scenarios.py", "schedule.py", "env.sh", "build_inner.sh", "build_if_missing.sh",
        "job.sbatch", "job_extra.sbatch", "HEADS", "JOBS", "JOBS_EXTRA",
    ], "copy"),
    ("of8-cause", "of8-cause", [
        "NOTES.md", "compare-final.json", "compare-1step.json", "compare.py",
        "source-excerpts-relax.txt", "dicts/fvSolution.*",
        "run.sbatch", "run1.sbatch", "centres.sbatch", "inner.sh", "inner1.sh",
        "slurm/*.out",
        "runs/*/variants.txt", "runs/*/node.txt", "runs/*/image-sha256.txt", "runs/*/*/exit-status",
        "runs1/*/variants.txt", "runs1/*/node.txt", "runs1/*/image-sha256.txt", "runs1/*/*/exit-status",
    ], "copy"),
    ("of8-cause", "of8-cause", ["runs/*/*/log.pimpleFoam", "runs1/*/*/log.pimpleFoam"], "gzip"),
    ("flaky", "flaky", [
        "load/*.out", "load/load.sbatch", "load/run_one.sh", "load/*/job.txt",
        "probe/out/probe-login-20261102.txt", "probe/*.py",
        "regress/regress.sbatch", "regress/probe_refused30.py", "regress/*.out",
        "regress/py31*/job.txt", "regress/py31*/probes-summary.txt", "regress/py31*/probes-clean.jsonl",
        "regress/py31*/test_*.log",
    ], "copy"),
    ("flaky", "flaky", ["load/*/run-*.log", "regress/py31*/loadgen/run-*.log"], "gzip-failed-or-loadgen"),
    ("gpu-ranks", "gpu-ranks", [
        "README.md", "ranks.sbatch", "ranks_inner.sh", "rank_wrap.sh", "check_ranks.py",
        "ranks-25080066.out", "ranks-25080027.out",
        "run-25080027/ranks.json", "run-25080027/check.out", "run-25080027/check-rerun.out",
        "run-25080066/ranks.json", "run-25080066/check.out", "run-25080066/HEAD", "run-25080066/git-status.txt",
        "run-25080066/node.txt", "run-25080066/gpu.txt", "run-25080066/gpu-after.txt", "run-25080066/nvidia-smi.txt",
        "run-25080066/server/*.cmd", "run-25080066/server/*.json", "run-25080066/server/*.txt",
        "run-25080066/*/binary-sha256.txt", "run-25080066/*/image-sha256.txt",
        "run-25080066/*/mpirun-version.txt", "run-25080066/*/mpirun-path.txt", "run-25080066/*/validation.log",
        "run-25080066/*/*/llm_result.json", "run-25080066/*/*/llm_response.json", "run-25080066/*/*/llm_request.json",
        "run-25080066/*/*/rank-*.txt", "run-25080066/*/*/metrics-before.txt", "run-25080066/*/*/metrics-after.txt",
        "run-25080066/*/*/started-at.txt", "run-25080066/*/*/ended-at.txt", "run-25080066/*/*/exit-status",
        "run-25080066/*/*/log.decomposePar", "run-25080066/*/*/telemetry.jsonl",
    ], "copy"),
    ("gpu-ranks", "gpu-ranks", ["run-25080066/*/*/log.PODFoam", "run-25080066/*/*/log.rank1",
                                "run-25080066/server-log-copy.log"], "gzip"),
    ("gpu-suites", "gpu-suites", [
        "records/INDEX.txt", "records/comparison.json", "records/frame-diff-vs-24950817.json",
        "records/async_v2-version-override.patch", "records/collect-stdout.txt",
        "records/gpu-suite-*/*",
        "submit_suite.sh", "collect.py", "frame_diff.py",
        "ref/reference.sbatch", "ref/reference-25080015.out", "ref/jobid.txt", "ref/HEAD", "ref/git-status.txt",
        "ref/node.txt", "ref/image-sha256-*.txt", "ref/validation-*.log",
        "start/mesh-check-*.txt", "start/boundary-diff-*.txt",
        "slurm/*.out", "slurm/jobids.txt",
    ], "copy"),
    ("setup12b", "setup12b", [
        "setup_12b.log", "run_setup.sh", "runtime/sha256.txt", "runtime/runtime_manifest_12b.json",
        "gpu/test_runtime.sbatch", "gpu/slurm-25080013.out", "gpu/symlink-test-login.txt",
        "gpu/run-25080013/*.txt", "gpu/run-25080013/*.log", "gpu/run-25080013/*.json", "gpu/run-25080013/*.out",
        "gpu/run-25080013/HEAD", "gpu/run-25080013/server/*",
        "fixtest/setup.out", "fixtest/runtime/runtime_manifest_12b.json", "fixtest/runtime/sha256.txt",
    ], "copy"),
    ("slice-3d", "slice-3d", [
        "design.json", "NOTES.md",
        "scripts/*.py", "scripts/*.sbatch", "scripts/*.sh",
        "jobs/*.out", "jobs/*.jobid", "jobs/phase2.submit.txt",
        "phase1-25080032/HEAD", "phase1-25080032/git-status.txt", "phase1-25080032/validation.log",
        "phase1-25080032/binary-sha256.txt", "phase1-25080032/image-sha256.txt", "phase1-25080032/node.txt",
        "phase1-25080032/start.txt", "phase1-25080032/end.txt", "phase1-25080032/make_windows.out",
        "phase1-25080032/testset/manifest.json", "phase1-25080032/testset/truth.json", "phase1-25080032/testset/baseline.json",
        "phase2-25088316/HEAD", "phase2-25088316/git-status.txt", "phase2-25088316/node.txt", "phase2-25088316/gpu.txt",
        "phase2-25088316/gpu-after.txt", "phase2-25088316/nvidia-smi.txt", "phase2-25088316/model-sha256.txt",
        "phase2-25088316/start.txt", "phase2-25088316/end.txt", "phase2-25088316/send.out",
        "phase2-25088316/server/*",
        "phase2-25088316/results/summary.json", "phase2-25088316/results/run.json", "phase2-25088316/results/metrics.jsonl",
        "phase2-25088316/results/*/*/metrics.json", "phase2-25088316/results/*/*/result.json",
        "phase2-25088316/results/*/*/response.json",
    ], "copy"),
    ("instability", "instability", [
        "DESIGN.md", "design2.json", "recount.py",
        "jobs/*.sbatch", "jobs/*.txt", "logs/*.out",
        "test-set/manifest.json", "test-set/truth.private.json",
        "results/gpu-25080221/report.md", "results/gpu-25080221/report.json", "results/gpu-25080221/recount.json",
        "results/gpu-25080221/HEAD", "results/gpu-25080221/git-status.txt", "results/gpu-25080221/*.txt",
        "results/gpu-25080221/*.json", "results/gpu-25080221/*.cmd", "results/gpu-25080221/*.log",
        "results/gpu-25080221/server/*",
        "results/gpu-25080221/*/run.json", "results/gpu-25080221/*/*/summary.json", "results/gpu-25080221/*/*/metrics.jsonl",
        "results/gpu-25080221/*/*/*/result.json", "results/gpu-25080221/*/*/*/metrics.json",
    ], "copy"),
]

R4 = REPOS / "pod-versions-20261030/r4"
CLONE = REPOS / "PythonFOAM"
# (subfolder of final-branches/, source folder under r4, patterns); json/md/txt/out/sh/py/sbatch only
FINAL_SPEC = [
    ("fix", "fix", [
        "NOTES.md", "check_msg.py", "jobs/*.sbatch", "jobs/*.sh", "logs/*.out", "msgs/*.txt", "msgs/*.md",
        "account-runs/*/account.json", "account-runs/*/git-status.txt",
        "runs/*/pod-*/verification.json", "runs/*/pod-*/environment.txt",
        "docker-*/*/*/verification.json", "docker-*/*/verification.json",
        "failpaths/*/*/stderr.txt", "failpaths/*/*/stdout.txt",
        "scenarios/compare_r4.json", "scenarios/compare_r4.txt", "scenarios/compare_r4.py",
        "scenarios/scenarios.py", "scenarios/schedule.py", "scenarios/extra.py", "scenarios/job.sbatch",
        "scenarios/build_inner.sh", "scenarios/env.sh",
        "scenarios/scen-*/scenarios.json", "scenarios/sched-*/schedule.json", "scenarios/scenx-*/extra.json",
        "siblings/*/record/record-check.json", "siblings/*/record/result.json", "siblings/*/record/summary.txt",
        "slice3d/compare_slice.py", "slice3d/*/compare_phase1.json", "slice3d/*/pod-*/verification.json",
        "slice3d/*/z3/slice-z.txt",
        "smoke/*/case-*/analysis_log.txt",
    ]),
    ("observer", "observer", [
        "NOTES.md", "jobs/*.sbatch", "jobs/*.sh", "logs/*.out",
        "load/*/job.txt", "load/*/summary.txt",
        "quick/pod-llm-demo.*/demo-verification.json", "quick/pod-llm-async.*/async-verification.json",
        "suite/compare-25090963.txt", "suite/ref.sbatch", "suite/submit_suite.sh",
        "tools/*.py", "tools/*.sh",
        "ranks/*.sbatch", "ranks/*.sh", "ranks/*.py", "ranks/ranks-25090647.out",
        "ranks/run-25090647/ranks.json", "ranks/run-25090647/check.out",
        "pod-async-v2/run-25090963/nvidia-smi.txt", "pod-async-v2/run-25090963/site.txt",
        "pod-async-v2/run-25090963/server/gpu-*.txt",
        "pod-async-v2/run-25090963/pod-llm-async.*/async-verification.json",
        "pod-async-v2/run-25090963/pod-llm-async.*/environment.txt",
    ]),
    ("plain", "plain", [
        "NOTES.md", "build_r5.out", "verify_r5.out", "tools/*.py", "tools/*.sh", "msgs/*.txt",
    ]),
    ("setup12b-check", "../r3/observer/setup12b-check", [
        "hardlinks.txt", "setup.out", "setup-other-revision.out", "runtime/sha256.txt", "runtime/runtime_manifest_12b.json",
    ]),
    ("main", "integrate", [
        "jobs/ci.sbatch", "tools/export.sh", "tools/check_msg.py", "logs/ci-25092222.out",
    ]),
]

W = REPOS / "pod-versions-20261030"
# (subfolder of final-branches/, source folder under W, patterns); the same file types as FINAL_SPEC
R6_SPEC = [
    ("docker-e2e", "r4/texts", [
        "docker_e2e.sh", "docker_e2e.sbatch", "logs/docker-e2e-25090624.out", "e2e-25090624/*/e2e.log",
    ]),
    ("docker-e2e", "r4/textreview", [
        "JOBS.txt", "logs/docker-e2e-25092824.out", "e2e-25092824/*/e2e.log",
    ]),
    ("docker-e2e/r6", "r5/texts", [
        "docker_e2e.sh", "docker_e2e.sbatch", "logs/docker-e2e-25093622.out", "logs/e2e-25093622/*/e2e.log",
        "logs/e2e-25093622/*/verification.json", "logs/sacct-e2e.txt", "logs/stubtest-exit-status.txt",
    ]),
    ("load-before-review", "r3/assemble/load", [
        "run_one.sh", "bin-8x50-25089961/job.txt", "bin-8x50-25089961/summary.txt",
        "bin-8x50-25089962/job.txt", "bin-8x50-25089962/summary.txt",
        "bin-16x30-25089963/job.txt", "bin-16x30-25089963/summary.txt",
    ]),
    ("load-before-review", "r3/assemble/jobs", ["load.sbatch"]),
    ("pr-docs", "r5/pr", [
        "NOTES.md", "build_r6.out", "build_r6.base", "verify_r6.out", "tools/*.sh", "tools/*.py",
        "msgs/c*", "counts/*.txt", "usersite-test/*.txt",
    ]),
    ("main", "r5/main", ["tools/merge_tree.sh"]),
]

# the r7 rebuild of the PR branches: (subfolder of final-branches/, source folder under W, patterns)
R7_SPEC = [
    ("pr-docs-r7", "loop/r6/fix/pr", [
        "build_r7.base", "build_r7.out", "verify_r7.out", "msgs/c*", "counts/pairs.txt",
    ]),
    ("pr-docs-r7", "loop/r6/fix", ["tools/build_r7.sh", "tools/verify_r7.sh", "tools/wrap_msgs.py"]),
]
R8_SPEC = [
    ("pr-docs-r8", "loop/r7/fix/pr", [
        "build_r8.base", "build_r8.out", "verify_r8.out", "msgs/c*", "counts/pairs.txt", "counts/pairs-r6.txt",
    ]),
    ("pr-docs-r8", "loop/r7/fix", ["tools/build_r8.sh", "tools/verify_r8.sh"]),
]
R9_SPEC = [
    ("pr-docs-r9", "loop/r8/fix/pr", [
        "build_r9.base", "build_r9.out", "verify_r9.out", "msgs/c*", "counts/pairs.txt", "counts/pairs-r6.txt",
    ]),
    ("pr-docs-r9", "loop/r8/fix", ["tools/build_r9.sh", "tools/verify_r9.sh"]),
]
R10_SPEC = [
    ("pr-docs-r10", "loop/r9/fix/pr", [
        "build_r10.base", "build_r10.out", "verify_r10.out", "msgs/c*", "counts/pairs.txt", "counts/pairs-r6.txt",
    ]),
    ("pr-docs-r10", "loop/r9/fix", ["tools/build_r10.sh", "tools/verify_r10.sh"]),
]
R11_SPEC = [
    ("pr-docs-r11", "loop/r10/fix/pr", [
        "build_r11.base", "build_r11.out", "verify_r11.out", "msgs/c*", "counts/pairs.txt", "counts/pairs-r6.txt",
    ]),
    ("pr-docs-r11", "loop/r10/fix", ["tools/build_r11.sh", "tools/verify_r11.sh"]),
]
R12_SPEC = [
    ("pr-docs-r12", "loop/r11/fix/pr", [
        "build_r12.base", "build_r12.out", "verify_r12.out", "msgs/c*", "counts/pairs.txt", "counts/pairs-r6.txt",
    ]),
    ("pr-docs-r12", "loop/r11/fix", ["tools/build_r12.sh", "tools/verify_r12.sh"]),
]
R13_SPEC = [
    ("pr-docs-r13", "final/r13/fix/pr", [
        "build_r13.base", "build_r13.out", "verify_r13.out", "msgs/c*", "counts/pairs.txt", "counts/pairs-r6.txt",
    ]),
    ("pr-docs-r13", "final/r13/fix", ["tools/build_r13.sh", "tools/verify_r13.sh"]),
]
R14_SPEC = [
    ("pr-docs-r14", "final/r14/fix/pr", [
        "build_r14.base", "build_r14.out", "verify_r14.out", "msgs/c*", "counts/pairs.txt", "counts/pairs-r6.txt",
    ]),
    ("pr-docs-r14", "final/r14/fix", ["tools/build_r14.sh", "tools/verify_r14.sh"]),
]

SKIP_NAMES = {"__pycache__"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def rel(path):
    return "MedicineBow " + str(Path(path).resolve().relative_to(REPOS)) + " (not released)"


def expand(folder, patterns):
    out = []
    for pattern in patterns:
        hits = sorted(folder.glob(pattern))
        if not hits:
            print(f"  (no match) {folder.name}/{pattern}", file=sys.stderr)
        for hit in hits:
            if hit.is_file() and not (SKIP_NAMES & set(hit.parts)):
                out.append(hit)
    return out


def copy_records(ev):
    origins = {}
    for sub, src, patterns, kind in SPEC:
        folder = R2 / src
        for source in expand(folder, patterns):
            target_rel = Path(sub) / source.relative_to(folder)
            if kind == "gzip-failed-or-loadgen":
                text = source.read_text(errors="ignore")
                if "loadgen" not in source.parts and "FAILED" not in text:
                    continue
                kind_here = "gzip"
            else:
                kind_here = kind
            if kind_here == "gzip":
                target_rel = target_rel.with_name(target_rel.name + ".gz")
            target = ev / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if kind_here == "copy":
                shutil.copyfile(source, target)
                origins[str(target_rel)] = {"source": rel(source), "kind": "byte-preserved"}
            else:
                data = source.read_bytes()
                with open(target, "wb") as raw:
                    with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=raw, mtime=0) as stream:
                        stream.write(data)
                origins[str(target_rel)] = {"source": rel(source), "kind": "gzip copy", "source_sha256": sha256(data)}
    # records made for this folder
    shutil.copyfile(TOOLS / "sacct.txt", ev / "sacct.txt")
    origins["sacct.txt"] = {"source": "sacct -X -P on MedicineBow, 2026-11-02, for the jobs named in README.md", "kind": "record"}
    shutil.copyfile(Path(__file__).resolve(), ev / "make_evidence.py")
    origins["make_evidence.py"] = {"source": "written for this folder", "kind": "derived"}
    (ev / ORIGINS).write_text(json.dumps(origins, indent=1, ensure_ascii=False) + "\n")
    print(f"copied {len(origins)} files into {ev}")


def copy_final(ev):
    """final-branches/ from the r4 work folders, and the plain diff for the gpu-suites record."""
    import subprocess
    if (ev / ORIGINS).exists():
        origins = json.loads((ev / ORIGINS).read_text())
    else:
        old = json.loads((ev / "manifest.json").read_text())
        origins = {e["path"]: {k: e[k] for k in ("source", "kind", "source_sha256", "note") if k in e} for e in old["files"]}
    allowed = (".json", ".md", ".txt", ".out", ".sh", ".py", ".sbatch")
    count = 0
    for sub, src, patterns in FINAL_SPEC:
        folder = R4 / src
        for source in expand(folder, patterns):
            if source.suffix not in allowed or source.stat().st_size > 2_000_000:
                continue
            target_rel = Path("final-branches") / sub / source.relative_to(folder)
            target = ev / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            # The checks of the earlier commit trailers name its model; the repository holds no file
            # with that name, so such a record is kept as a derived copy with the one word replaced.
            import re
            name = re.compile(rb"(?i)f" + rb"able")
            if name.search(data):
                target.write_bytes(name.sub(b"<earlier-model-name>", data))
                origins[str(target_rel)] = {"source": rel(source), "kind": "derived",
                                            "note": "the earlier trailer's model name replaced by <earlier-model-name>",
                                            "source_sha256": sha256(data)}
            else:
                target.write_bytes(data)
                origins[str(target_rel)] = {"source": rel(source), "kind": "byte-preserved"}
            count += 1
    sacct = R4 / "integrate/records/sacct.txt"
    shutil.copyfile(sacct, ev / "final-branches/sacct.txt")
    origins["final-branches/sacct.txt"] = {"source": "sacct -X -P on MedicineBow, 2026-11-02, for the jobs named in "
                                                     "final-branches/ (" + rel(sacct) + ")", "kind": "record"}
    patch = Path("gpu-suites/records/async_v2-version-override.patch")
    diff = subprocess.run(["git", "-C", str(CLONE), "diff", "c82c835^", "c82c835"],
                          capture_output=True, check=True).stdout
    (ev / patch).write_bytes(diff)
    origins[str(patch)] = {"source": "git diff c82c835^ c82c835 (branch r2/gpu-suites, local clone on MedicineBow): "
                                     "the change alone, without the commit header", "kind": "derived"}
    shutil.copyfile(Path(__file__).resolve(), ev / "make_evidence.py")
    (ev / ORIGINS).write_text(json.dumps(origins, indent=1, ensure_ascii=False) + "\n")
    print(f"final-branches: {count} files; {patch} rewritten as a plain diff ({len(diff)} bytes)")


def copy_r6(ev):
    """The G7 records and the r6 rebuild check, added to final-branches/; sacct.txt gets their rows."""
    import re
    old = json.loads((ev / "manifest.json").read_text())
    origins = {e["path"]: {k: e[k] for k in ("source", "kind", "source_sha256", "note") if k in e} for e in old["files"]}
    allowed = (".json", ".md", ".txt", ".out", ".sh", ".py", ".sbatch", ".log", ".base", "")
    count = 0
    name = re.compile(rb"(?i)f" + rb"able")
    for sub, src, patterns in R6_SPEC:
        folder = W / src
        for source in expand(folder, patterns):
            if source.suffix not in allowed or source.stat().st_size > 2_000_000:
                continue
            target_rel = Path("final-branches") / sub / source.relative_to(folder)
            target = ev / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            if name.search(data):
                target.write_bytes(name.sub(b"<earlier-model-name>", data))
                origins[str(target_rel)] = {"source": rel(source), "kind": "derived",
                                            "note": "the earlier trailer's model name replaced by <earlier-model-name>",
                                            "source_sha256": sha256(data)}
            else:
                target.write_bytes(data)
                origins[str(target_rel)] = {"source": rel(source), "kind": "byte-preserved"}
            count += 1
    sacct = W / "r5/main/records/sacct.txt"
    shutil.copyfile(sacct, ev / "final-branches/sacct.txt")
    origins["final-branches/sacct.txt"] = {"source": "sacct -X -P on MedicineBow, 2026-11-02, for the jobs named in "
                                                     "final-branches/ (" + rel(sacct) + ")", "kind": "record"}
    shutil.copyfile(Path(__file__).resolve(), ev / "make_evidence.py")
    (ev / ORIGINS).write_text(json.dumps(origins, indent=1, ensure_ascii=False) + "\n")
    print(f"r6 records: {count} files added or refreshed in final-branches/")


def copy_r7(ev, spec=None, label="r7"):
    """The r7 (or r8 to r14) rebuild records, added to final-branches/pr-docs-r7/ (pr-docs-r8/ to pr-docs-r14/)."""
    import re
    old = json.loads((ev / "manifest.json").read_text())
    origins = {e["path"]: {k: e[k] for k in ("source", "kind", "source_sha256", "note") if k in e} for e in old["files"]}
    name = re.compile(rb"(?i)f" + rb"able")
    count = 0
    for sub, src, patterns in (spec or R7_SPEC):
        folder = W / src
        for source in expand(folder, patterns):
            target_rel = Path("final-branches") / sub / source.relative_to(folder)
            target = ev / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            if name.search(data):
                raise SystemExit(f"banned name in {source}")
            target.write_bytes(data)
            origins[str(target_rel)] = {"source": rel(source), "kind": "byte-preserved"}
            count += 1
    shutil.copyfile(Path(__file__).resolve(), ev / "make_evidence.py")
    (ev / ORIGINS).write_text(json.dumps(origins, indent=1, ensure_ascii=False) + "\n")
    print(f"{label} records: {count} files added in final-branches/pr-docs-{label}/")


def write_manifest(ev):
    origins_file = ev / ORIGINS
    if origins_file.exists():
        origins = json.loads(origins_file.read_text())
    else:
        old = json.loads((ev / "manifest.json").read_text())
        origins = {e["path"]: {k: e[k] for k in ("source", "kind", "source_sha256", "note") if k in e} for e in old["files"]}
    files = []
    for path in sorted(p for p in ev.rglob("*") if p.is_file()):
        relp = str(path.relative_to(ev))
        if relp in ("manifest.json", ORIGINS):
            continue
        data = path.read_bytes()
        origin = origins.get(relp)
        if origin is None:
            if relp == "README.md":
                origin = {"source": "written for this folder", "kind": "derived"}
            else:
                raise SystemExit(f"no origin recorded for {relp}")
        entry = {"path": relp, "source": origin["source"], "kind": origin["kind"], "bytes": len(data), "sha256": sha256(data)}
        if "source_sha256" in origin:
            entry["source_sha256"] = origin["source_sha256"]
        if "note" in origin:
            entry["note"] = origin["note"]
        files.append(entry)
    manifest = {
        "source_runs": ["pod-versions-20261030/r2 on MedicineBow: the Slurm jobs named in README.md",
                        "pod-versions-20261030/r4 on MedicineBow: the checks of the final PR branches and the fork's main (final-branches/)",
                        "pod-versions-20261030/r3 and r5 on MedicineBow: the load runs of the November tree 276ea8e, the Docker end-to-end runs and the r6 rebuild check (final-branches/)",
                        "pod-versions-20261030/loop/r6/fix on MedicineBow: the r7 rebuild check of the PR branches (final-branches/pr-docs-r7/)",
                        "pod-versions-20261030/loop/r7/fix on MedicineBow: the r8 rebuild check of the PR branches (final-branches/pr-docs-r8/)",
                        "pod-versions-20261030/loop/r8/fix on MedicineBow: the r9 rebuild check of the PR branches (final-branches/pr-docs-r9/)",
                        "pod-versions-20261030/loop/r9/fix on MedicineBow: the r10 rebuild check of the PR branches (final-branches/pr-docs-r10/)",
                        "pod-versions-20261030/loop/r10/fix on MedicineBow: the r11 rebuild check of the PR branches (final-branches/pr-docs-r11/)",
                        "pod-versions-20261030/loop/r11/fix on MedicineBow: the r12 rebuild check of the PR branches (final-branches/pr-docs-r12/)",
                        "pod-versions-20261030/final/r13/fix on MedicineBow: the r13 rebuild check of the PR branches (final-branches/pr-docs-r13/)",
                        "pod-versions-20261030/final/r14/fix on MedicineBow: the r14 rebuild check of the PR branches (final-branches/pr-docs-r14/)"],
        "scope": "Round-2 checks of the PR tree bf7a06e and of the original PODFoam at 6fde869 on OpenFOAM v2012, v2106, v2212 and 8, "
                 "the model runs of 2026-11-01 and 2026-11-02, and the checks of the final PR branches; the small records of each job. "
                 "No binaries, images, solver builds, field dumps, pictures, request bodies or model files.",
        "notes": [
            "Files of kind gzip copy are gzip -9 copies (no name, mtime 0) of the named source; source_sha256 is the hash of the uncompressed bytes.",
            "Original records contain cluster paths as provenance.",
        ],
        "files": files,
    }
    (ev / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    if origins_file.exists():
        origins_file.unlink()
    total = sum(f["bytes"] for f in files)
    print(f"manifest: {len(files)} files, {total/1e6:.1f} MB")


def main(argv):
    if len(argv) != 2 or argv[0] not in ("copy", "final", "r6", "r7", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "manifest"):
        print(__doc__)
        return 2
    ev = Path(argv[1]).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    if argv[0] == "copy":
        copy_records(ev)
    elif argv[0] == "final":
        copy_final(ev)
    elif argv[0] == "r6":
        copy_r6(ev)
    elif argv[0] == "r7":
        copy_r7(ev)
    elif argv[0] == "r8":
        copy_r7(ev, R8_SPEC, "r8")
    elif argv[0] == "r9":
        copy_r7(ev, R9_SPEC, "r9")
    elif argv[0] == "r10":
        copy_r7(ev, R10_SPEC, "r10")
    elif argv[0] == "r11":
        copy_r7(ev, R11_SPEC, "r11")
    elif argv[0] == "r12":
        copy_r7(ev, R12_SPEC, "r12")
    elif argv[0] == "r13":
        copy_r7(ev, R13_SPEC, "r13")
    elif argv[0] == "r14":
        copy_r7(ev, R14_SPEC, "r14")
    else:
        write_manifest(ev)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
