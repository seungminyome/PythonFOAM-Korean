#!/usr/bin/env python3
"""Check commit messages: subject <= 70, body <= 8 lines (or --long 12), lines <= 80,
blank line + exactly one trailer at the end, no '<earlier-model-name>', no 'upstream'."""
import sys, subprocess
TRAILER = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
def check(text, limit):
    lines = text.rstrip("\n").split("\n")
    problems = []
    subj = lines[0]
    if len(subj) > 70: problems.append(f"subject {len(subj)} chars")
    if lines[-1] != TRAILER or lines[-2] != "": problems.append("trailer")
    if sum(TRAILER == l for l in lines) != 1 or sum(l.startswith("Co-Authored-By") for l in lines) != 1: problems.append("trailer count")
    if lines[1] != "": problems.append("no blank after subject")
    body = lines[2:-2]
    if len(body) > limit: problems.append(f"body {len(body)} lines")
    long = [len(l) for l in body if len(l) > 80]
    if long: problems.append(f"long lines {long}")
    low = text.lower()
    if "<earlier-model-name>" in low: problems.append("<earlier-model-name>")
    if "upstream" in low: problems.append("upstream")
    return len(subj), len(body), max([len(l) for l in body] or [0]), problems
if __name__ == "__main__":
    limit = 8
    args = sys.argv[1:]
    if args and args[0] == "--long": limit = 12; args = args[1:]
    if args and args[0] == "--rev":
        repo, rng = args[1], args[2]
        revs = subprocess.run(["git", "-C", repo, "rev-list", "--reverse", rng], capture_output=True, text=True, check=True).stdout.split()
        bad = 0
        for r in revs:
            text = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%B", r], capture_output=True, text=True, check=True).stdout
            s, b, m, p = check(text.rstrip("\n") + "\n", limit)
            print(r[:8], s, b, m, p or "OK"); bad += bool(p)
        sys.exit(1 if bad else 0)
    bad = 0
    for f in args:
        s, b, m, p = check(open(f, encoding="utf-8").read(), limit)
        print(f, "subject", s, "body", b, "maxline", m, p or "OK"); bad += bool(p)
    sys.exit(1 if bad else 0)
