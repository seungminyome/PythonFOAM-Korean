#!/usr/bin/env python3
"""H2 word shares with 3 decimals, counted exactly like h2_shares.py (r4/plain/tools).
Usage: h2_shares_exact.py OLD.md NEW.md   prints each H2 share old -> new and the change."""
import re, sys
def visible(line):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", line)
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
def shares(p):
    cur, words, fence = "intro", {"intro": 0}, False
    for raw in open(p, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if not fence and line.startswith("## "):
            cur = line[3:].strip()
            words.setdefault(cur, 0)
        words[cur] += len(visible(line).split())
    tot = sum(words.values())
    return {k: 100 * v / tot for k, v in words.items()}
a, b = shares(sys.argv[1]), shares(sys.argv[2])
worst = 0
for k in list(dict.fromkeys(list(a) + list(b))):
    x, y = a.get(k, 0.0), b.get(k, 0.0)
    worst = max(worst, abs(y - x))
    print(f"   {k[:40]:40s} {x:7.3f} -> {y:7.3f}  {y - x:+.3f}")
print(f"   largest change {worst:.3f} points")
