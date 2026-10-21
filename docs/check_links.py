#!/usr/bin/env python3
"""Check that relative links in Markdown and HTML files point at existing files.

Usage: check_links.py [root]   (default: repository root)
"""
import re
import sys
from pathlib import Path

SKIP_DIRS = {'.git', 'pod-llm-demo.LRfJBN', 'progress-evidence', 'linux64Gcc', '__pycache__', 'llm-runtime-12b'}


def main(argv):
    root = Path(argv[0]) if argv else Path(__file__).resolve().parents[1]
    bad = []
    files = 0
    for f in root.rglob('*'):
        if f.suffix not in ('.md', '.html') or SKIP_DIRS & set(f.parts):
            continue
        files += 1
        text = f.read_text(errors='ignore')
        links = re.findall(r'\]\(([^)\s]+)\)', text) + re.findall(r'(?:href|src)="([^"]+)"', text)
        for link in links:
            if link.startswith(('http://', 'https://', 'mailto:', '#', 'data:')):
                continue
            target = link.split('#')[0]
            if target and not (f.parent / target).exists():
                bad.append(f'{f.relative_to(root)}: {link}')
    for line in bad:
        print('BROKEN ', line)
    print(f'{files} files scanned, {len(bad)} broken relative links')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
