#!/usr/bin/env python3
"""Check every file listed in an evidence manifest against its recorded size and SHA-256.

Usage: check_manifest.py [evidence-dir ...]   (default: every dated folder next to this script)
Exit status is 1 if any listed file is missing or differs.
"""
import hashlib
import json
import sys
from pathlib import Path


def entries(manifest):
    data = json.loads(manifest.read_text())
    items = data['files'] if isinstance(data, dict) else data
    for item in items:
        yield item.get('path') or item['filename'], item['bytes'], item['sha256']


def check(folder):
    manifest = folder / 'manifest.json'
    bad = 0
    n = 0
    for rel, size, digest in entries(manifest):
        n += 1
        path = folder / rel
        if not path.is_file():
            print(f'MISSING  {folder.name}/{rel}')
            bad += 1
            continue
        data = path.read_bytes()
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            print(f'DIFFERS  {folder.name}/{rel}')
            bad += 1
    print(f'{folder.name}: {n - bad}/{n} files match the manifest')
    return bad


def main(argv):
    here = Path(__file__).resolve().parent
    folders = [Path(a) for a in argv] or sorted(p for p in here.iterdir() if p.is_dir() and (p / 'manifest.json').exists())
    failures = sum(check(f) for f in folders)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
