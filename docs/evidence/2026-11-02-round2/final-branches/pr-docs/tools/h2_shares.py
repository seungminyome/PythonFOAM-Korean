#!/usr/bin/env python3
"""Word shares per H2 section, counted like r3/docs/tools/readme_shares.py:
whitespace tokens per line, code words and table pipes count, fence lines do not,
a link counts its text, an image 0. The block before the first H2 is 'intro'.
Usage: h2_shares.py FILE [FILE ...]   (prints JSON per file)"""
import json, re, sys
def visible(line):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", line)
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
for p in sys.argv[1:]:
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
    print(json.dumps({"file": p, "total": tot, "shares": {k: round(100 * v / tot, 1) for k, v in words.items()}}))
