"""Write a source-linked validation receipt after the fail-fast shell runner."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import sys

root = Path(__file__).resolve().parents[1]
folder = Path(sys.argv[1]).resolve(strict=True)
counts = {}
for name in ['analysis_tests.log', 'dispatcher_tests.log']:
    text = (folder / name).read_text(encoding='utf-8')
    match = re.search(r'Ran (\d+) tests?', text)
    if not match or not re.search(r'^OK\s*$', text, re.MULTILINE) or 'FAILED' in text:
        raise SystemExit('No complete successful test outcome: ' + name)
    counts[name] = int(match[1])
if 'PASS: 8 submission-batch scenarios' not in (folder / 'submission_tests.log').read_text():
    raise SystemExit('Missing C submission-test success')
sources = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
           for base in ['src', 'analysis', 'tests', 'tools'] for p in (root / base).rglob('*')
           if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py', '.c', '.h')}
receipt = {'host': platform.node(), 'kernel': platform.release(), 'python': platform.python_version(),
           'platform': platform.system(),
           'implementation': 'team-reference-integrated-revised', 'status': 'passed',
           'python_test_counts': counts, 'C_submission_scenarios': 8, 'source_sha256': sources,
           'performance_claim': False}
receipt['packages'] = {name: importlib.metadata.version(name) for name in ['numpy', 'pandas', 'matplotlib']}
with (folder / 'validation.json').open('x') as stream:
    json.dump(receipt, stream, indent=2)
print('Saved validation.json')
