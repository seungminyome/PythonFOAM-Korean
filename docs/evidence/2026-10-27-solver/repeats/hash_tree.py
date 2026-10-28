#!/usr/bin/env python3
"""Write the SHA-256 of every file under a folder as JSON {relative path: hash} (gzip, mtime 0).

Usage: hash_tree.py FOLDER OUT.json.gz
"""
import gzip
import hashlib
import json
import sys
from pathlib import Path


def main(folder, out):
    folder = Path(folder)
    hashes = {}
    for p in sorted(folder.rglob("*")):
        if p.is_file() and not p.is_symlink():
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            hashes[str(p.relative_to(folder))] = h.hexdigest()
    data = (json.dumps(hashes, indent=0, sort_keys=True) + "\n").encode()
    with open(out, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", compresslevel=9, mtime=0, filename="") as g:
            g.write(data)
    print(f"{len(hashes)} files")


if __name__ == "__main__":
    main(*sys.argv[1:])
