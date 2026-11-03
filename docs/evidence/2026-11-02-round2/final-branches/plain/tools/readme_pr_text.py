#!/usr/bin/env python3
"""Extract the PR's own text from a root README: lines absent from the base README
(6fde869), as separate paragraphs; a changed upstream line is cut at '**Replace',
so only the PR's sentences of the prep_env.sh paragraph count.
Usage: readme_pr_text.py BASE.md README.md > out.md"""
import sys
base = set(open(sys.argv[1], encoding="utf-8").read().split("\n"))
out = []
for ln in open(sys.argv[2], encoding="utf-8").read().split("\n"):
    if ln in base or not ln.strip():
        continue
    if "**Replace" in ln:
        ln = ln.split("**Replace")[0].rstrip()
    out.append(ln.strip())
    out.append("")
print("\n".join(out))
