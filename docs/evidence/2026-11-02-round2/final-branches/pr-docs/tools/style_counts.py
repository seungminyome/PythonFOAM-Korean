#!/usr/bin/env python3
"""Section-F style counts for English Markdown files (ROUND2_DECISIONS.md F).

Usage: style_counts.py [--diff-only BASE] FILE [FILE ...]
       style_counts.py --json FILE ...   (one JSON object per file)

What is counted (fenced code blocks are never prose):
  prose units   paragraphs and list items outside code blocks, tables and headings
  long          sentences of more than 35 words (whitespace tokens, inline code counts);
                sentences end at . ! ? followed by a space, not at colons or semicolons
  parens        parenthesised groups in prose and table cells that are not a unit,
                a job id, a file path or a citation; code spans and link targets are
                removed first, so `f(x)` or `(cells, 3)` in backticks never count
  nums_max      the largest count of numbers in one prose unit; numbers inside code
                spans, version names (v2012, OpenFOAM 8, Python 3.10, Gemma 4, b11429,
                GLIBC_2.38 ...) and model names (E2B, 12B) do not count
  banned        hedging and judgement words (nearly, considerably, clearly, robustly,
                notably, significantly, substantially, essentially, largely, fairly,
                quite, very, arguably, merely, simply), connective openers at sentence
                start (Moreover, Furthermore, In addition, Additionally, Also, Thus,
                Hence, Therefore), "therefore" anywhere else, and every "However"
                after the first
  semis         sentences holding two or more semicolons (clause chains)
  words         whitespace tokens of the file outside code fences, link text only,
                without table pipes and table separator rows
"""
import json
import re
import sys

HEDGES = ["nearly", "considerably", "clearly", "robustly", "notably", "significantly",
          "substantially", "essentially", "largely", "fairly", "quite", "very",
          "arguably", "merely", "simply"]
OPENERS = ["Moreover", "Furthermore", "In addition", "Additionally", "Also", "Thus",
           "Hence", "Therefore"]
UNIT = r"(?:s|ms|min|minutes?|h|m|mm|cm|m/s|m²/s²|m³|GB|MB|kB|B|%|K|Pa|cells?|steps?|cores?|CPUs?)"


def blocks(text):
    """Yield (kind, text) for prose units, table rows and headings."""
    lines = text.split("\n")
    in_fence = False
    cur = []
    out = []

    def flush():
        if cur:
            out.append(("prose", " ".join(s.strip() for s in cur)))
            cur.clear()

    for ln in lines:
        if ln.lstrip().startswith("```"):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        s = ln.strip()
        if not s:
            flush()
            continue
        if s.startswith("#"):
            flush()
            out.append(("heading", s))
            continue
        if s.startswith("|"):
            flush()
            if not re.fullmatch(r"\|[\s|:-]+\|", s):
                out.append(("table", s))
            continue
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+", ln) and not ln.startswith("    \t"):
            flush()
            cur.append(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", ln))
            continue
        cur.append(ln)
    flush()
    return out


def strip_links(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return s


def code_out(s, placeholder="CODE"):
    return re.sub(r"`[^`]*`", placeholder, s)


def sentences(p):
    p = strip_links(p)
    # protect common abbreviations and decimal points
    q = re.sub(r"\b(e\.g|i\.e|etc|vs|cf)\.", lambda m: m.group(0).replace(".", "\x00"), p)
    q = re.sub(r"`[^`]*`", lambda m: m.group(0).replace(".", "\x00").replace(" ", "\x01"), q)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Za-z`\"*(\[|])", q)
    res = []
    for x in parts:
        x = x.replace("\x00", ".").replace("\x01", " ").strip()
        if x:
            res.append(x)
    return res


def words(s):
    return len(s.split())


def allowed_paren(content, raw_inner):
    c = content.strip()
    if not c:
        return True
    if re.fullmatch(r"(?:job|jobs)\s[\d, -]+", c) or re.fullmatch(r"\d{8}(?:[-, ]+\d+)*", c):
        return True
    if re.fullmatch(rf"[~≈]?\s*[\d.,]+(?:\s*(?:to|-|–)\s*[\d.,]+)?\s*{UNIT}", c):
        return True
    if re.fullmatch(rf"{UNIT}", c):
        return True
    # only code spans that look like paths or files
    if re.fullmatch(r"(?:CODE[\s,]*(?:and\s+)?)+", c):
        spans = re.findall(r"`([^`]*)`", raw_inner)
        if spans and all(re.search(r"/|\.(?:py|sh|md|json|jsonl|H|C|txt|slurm|npz|out|log|png|tsv)\b", x) for x in spans):
            return True
    return False


def paren_groups(s):
    """Parenthesised groups outside code spans and link targets."""
    s = strip_links(s)
    raw = s
    masked = code_out(s, "CODE")
    groups = []
    # map: find groups in the masked string; get raw inner by re-finding in raw with code spans
    for m in re.finditer(r"\(([^()]*)\)", masked):
        groups.append(m.group(1))
    # raw inners for code-span checking
    raw_groups = []
    depth = 0
    buf = ""
    i = 0
    in_code = False
    for ch in raw:
        if ch == "`":
            in_code = not in_code
        if not in_code and ch == "(":
            depth += 1
            if depth == 1:
                buf = ""
                continue
        if not in_code and ch == ")" and depth:
            depth -= 1
            if depth == 0:
                raw_groups.append(buf)
                continue
        if depth:
            buf += ch
    out = []
    for k, g in enumerate(groups):
        rg = raw_groups[k] if k < len(raw_groups) else g
        out.append((g, rg, allowed_paren(g, rg)))
    return out


VERSION_RES = [
    r"\bv\d{4}\b", r"\bb\d{4,}\b", r"\bOpenFOAM\s+(?:v)?\d+(?:\.\d+)?\b",
    r"\b(?:Python|Gemma|Ubuntu|GCC|glibc|GLIBC|CUDA|TensorFlow|tensorflow|libstdc\+\+ of GCC)\s+\d+(?:\.\d+)*(?:\s+(?:to|and|or)\s+\d+(?:\.\d+)*)?",
    r"\b(?:GLIBC|GLIBCXX)_\d+(?:\.\d+)*", r"\bE2B\b", r"\b\d+B\b", r"\b[23]D\b",
    r"\bversions?\s+\d+\b", r"\band\s+8\b(?=[\s,.;)]|$)",
]
NUM = r"(?<![\w.\-])-?\d+(?:[.,]\d+)*(?:e[-+]?\d+)?(?:x\d+)?(?![\w])"


def numbers_in(s):
    s = strip_links(s)
    s = code_out(s, " ")
    s = re.sub(r"https?://\S+", " ", s)
    for r in VERSION_RES:
        s = re.sub(r, " ", s)
    return re.findall(NUM, s)


def count(text):
    res = {"long": 0, "long_list": [], "parens": 0, "paren_list": [], "nums_max": 0,
           "nums_max_unit": "", "banned": 0, "banned_list": [], "semis": 0, "words": 0,
           "sentences": 0, "units": 0}
    however = 0
    for kind, b in blocks(text):
        if kind in ("prose", "table"):
            for g, rg, ok in paren_groups(b):
                if not ok:
                    res["parens"] += 1
                    res["paren_list"].append("(" + rg + ")")
        if kind != "prose":
            continue
        res["units"] += 1
        n = numbers_in(b)
        if len(n) > res["nums_max"]:
            res["nums_max"] = len(n)
            res["nums_max_unit"] = b[:90]
        for snt in sentences(b):
            res["sentences"] += 1
            w = words(snt)
            if w > 35:
                res["long"] += 1
                res["long_list"].append(f"{w}: {snt[:80]}")
            if snt.count(";") >= 2:
                res["semis"] += 1
            plain = code_out(strip_links(snt), " ")
            for h in HEDGES:
                for _ in re.finditer(rf"\b{h}\b", plain, re.I):
                    res["banned"] += 1
                    res["banned_list"].append(h)
            st = plain.lstrip("*_\"( ")
            for o in OPENERS:
                if re.match(rf"{o}\b", st):
                    res["banned"] += 1
                    res["banned_list"].append(o + " (opener)")
            body = st if not re.match(r"Therefore\b", st) else st[9:]
            for _ in re.finditer(r"\btherefore\b", body):
                res["banned"] += 1
                res["banned_list"].append("therefore")
            for _ in re.finditer(r"\bHowever\b", plain):
                however += 1
                if however > 1:
                    res["banned"] += 1
                    res["banned_list"].append("However (2nd+)")
    # words: all tokens outside fences, link text only
    in_fence = False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.fullmatch(r"\s*\|[\s|:-]+\|\s*", ln):
            continue
        res["words"] += len([t for t in strip_links(ln).split() if t != "|"])
    return res


def main(argv):
    as_json = False
    if argv and argv[0] == "--json":
        as_json = True
        argv = argv[1:]
    for path in argv:
        r = count(open(path, encoding="utf-8").read())
        if as_json:
            print(json.dumps({"file": path, **r}))
            continue
        print(f"{path}: words {r['words']}, sentences {r['sentences']}, long>35 {r['long']}, "
              f"expl. parens {r['parens']}, numbers/paragraph max {r['nums_max']}, "
              f"banned {r['banned']}, 2+ semicolons {r['semis']}")
        for x in r["long_list"]:
            print("   long", x)
        for x in r["paren_list"]:
            print("   paren", x)
        if r["banned_list"]:
            print("   banned", r["banned_list"])
        print("   max-number unit:", r["nums_max_unit"])


if __name__ == "__main__":
    main(sys.argv[1:])
