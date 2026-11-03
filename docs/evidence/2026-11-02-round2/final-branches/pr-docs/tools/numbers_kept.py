#!/usr/bin/env python3
"""Every number of the r4 doc must still be in the r5 doc.

Usage: numbers_kept.py R4.md R5.md
Two token sets are compared, over the whole file (prose, tables, code):
  numbers      -?digits with . , separators and e-exponents, standalone
               (20,540  0.0001  1e-7  5e-6  2026-11-01 counts as 2026, 11, 01)
  identifiers  words that hold a digit (v2212, b11429, GLIBC_2.38, E2B, 12B,
               640x360, step-000005, libcudart.so.12)
Prints the tokens missing from R5 (exit 1 if any) and the count deltas per token."""
import re, sys
from collections import Counter
NUM = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)*(?:e[-+]?\d+)?(?![\w])")
IDENT = re.compile(r"[A-Za-z_][\w.\-]*\d[\w.\-]*|\d+[A-Za-z][\w.\-]*")
def toks(path):
    t = open(path, encoding="utf-8").read()
    nums = Counter(m.group(0).rstrip(".,") for m in NUM.finditer(t))
    ids = Counter(m.group(0).rstrip(".,-") for m in IDENT.finditer(t))
    return nums, ids
a_n, a_i = toks(sys.argv[1]); b_n, b_i = toks(sys.argv[2])
miss_n = sorted(set(a_n) - set(b_n)); miss_i = sorted(set(a_i) - set(b_i))
new_n = sorted(set(b_n) - set(a_n)); new_i = sorted(set(b_i) - set(a_i))
fewer = {k: (a_n[k], b_n[k]) for k in a_n if b_n[k] and b_n[k] < a_n[k]}
print(f"{sys.argv[2]}: numbers {len(a_n)} distinct in r4, missing {len(miss_n)} {miss_n}; "
      f"identifiers {len(a_i)} distinct, missing {len(miss_i)} {miss_i}")
print(f"   new in r5: numbers {new_n} identifiers {new_i}")
print(f"   fewer occurrences (r4, r5): {fewer}")
sys.exit(1 if miss_n or miss_i else 0)
