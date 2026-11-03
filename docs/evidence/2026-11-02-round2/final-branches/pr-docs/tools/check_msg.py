"""Check commit message files: subject <= 70, body lines <= 80, body line count limit, trailer, banned words."""
import sys, re
from pathlib import Path
TRAILER = 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
ok = True
for name in sys.argv[1:]:
    limit = 12 if Path(name).stem in ('c1',) else 8
    text = Path(name).read_text()
    lines = text.rstrip('\n').split('\n')
    subject = lines[0]
    assert lines[1] == '', name
    assert lines[-1] == TRAILER and lines[-2] == '', (name, 'trailer')
    body = lines[2:-2]
    while body and body[-1] == '':
        body.pop()
    problems = []
    if len(subject) > 70: problems.append(f'subject {len(subject)}')
    if len(body) > limit: problems.append(f'body lines {len(body)} > {limit}')
    long = [len(l) for l in body if len(l) > 80]
    if long: problems.append(f'long lines {long}')
    if re.search(r'(?i)<earlier-model-name>|upstream', text): problems.append('banned word')
    if text.count('Co-Authored-By') != 1: problems.append('co-authored count')
    print(name, 'subject', len(subject), 'body', len(body), 'maxline', max([len(l) for l in body] or [0]), 'OK' if not problems else problems)
    ok &= not problems
sys.exit(0 if ok else 1)
