#!/usr/bin/env python3
"""Check links, anchors and quoted section references of the PR docs in one commit.

Usage: check_links.py REPO COMMIT
For every .md file the PR rewrote that exists in COMMIT:
  - each Markdown link (markdown_it, CommonMark + tables): a relative path must
    exist in COMMIT's tree (git cat-file -e), resolved against the doc's folder;
    an anchor (#x) must equal the GitHub slug of a heading in the target file;
  - each quoted reference "X" written next to 'under', 'see', 'as' or 'described'
    must match a heading or a bold list label (**X.**) of the same file;
  - external http(s) links are listed (checked separately with curl).
Exit 1 on any broken item."""
import re
import subprocess
import sys
from posixpath import dirname, join, normpath

from markdown_it import MarkdownIt

DOCS = ["README.md", "Solver_Examples/PODFoam/HOOKS.md",
        "Solver_Examples/PODFoam/validation/README.md",
        "Solver_Examples/PODFoam/llm_demo/README.md",
        "Solver_Examples/PODFoam/llm_demo/hpc/README.md"]
repo, commit = sys.argv[1], sys.argv[2]


def git(*a, check=True):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, check=check)


def exists(path):
    return git("cat-file", "-e", f"{commit}:{path}", check=False).returncode == 0


def text(path):
    return git("show", f"{commit}:{path}").stdout


def slug(h):
    h = h.strip().lower()
    h = re.sub(r"[^\w\- ]", "", h)          # GitHub drops punctuation except - and _
    return h.replace(" ", "-")


def headings(md):
    out, fence = [], False
    for ln in md.split("\n"):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        if not fence and re.match(r"#{1,6} ", ln):
            out.append(re.sub(r"^#{1,6} ", "", ln).replace("`", ""))
    return out


def links(md):
    res = []
    for tok in MarkdownIt("commonmark").enable("table").parse(md):
        for ch in (tok.children or []):
            if ch.type == "link_open":
                res.append(ch.attrs.get("href"))
        if tok.type == "inline":
            for m in re.finditer(r"(?<![(<\[])https?://[^\s)`]+", tok.content):
                res.append(m.group(0))
    return res


bad = 0
external = set()
for doc in DOCS:
    if not exists(doc):
        continue
    md = text(doc)
    n = 0
    for href in links(md):
        n += 1
        if href.startswith(("http://", "https://")):
            external.add(href)
            continue
        path, _, anchor = href.partition("#")
        target = normpath(join(dirname(doc), path)) if path else doc
        if not exists(target):
            print(f"BROKEN {doc}: {href} -> {target} missing")
            bad += 1
            continue
        if anchor:
            slugs = {slug(h) for h in headings(text(target))}
            if anchor not in slugs:
                print(f"BROKEN {doc}: {href} anchor not in {target}")
                bad += 1
                continue
        print(f"ok {doc}: {href} -> {target}{'#' + anchor if anchor else ''}")
    labels = set(headings(md)) | {m.group(1) for m in re.finditer(r"\*\*([^*]+?)\.?\*\*", md)}
    labels = {l.strip().rstrip(".").replace("`", "") for l in labels}
    for m in re.finditer(r"(?:under|see|as|described)\s+\"([^\"]+)\"", md):
        ref = " ".join(m.group(1).split())
        if ref in labels:
            print(f"ok {doc}: quoted reference \"{ref}\"")
        else:
            print(f"BROKEN {doc}: quoted reference \"{ref}\" has no heading or bold label")
            bad += 1
    print(f"   {doc}: {n} links")
for u in sorted(external):
    print(f"external {u}")
sys.exit(1 if bad else 0)
