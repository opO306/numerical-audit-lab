"""Capture author commands, raw output and actual exits without overwrites."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'current/c1b1-qdiv-sign-fix-2026-10-05'
mode = sys.argv[1]
impulse = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'tests').glob('test_impulse_*.py'))
commands = {
    'targeted': [sys.executable, '-m', 'pytest', '-q', 'tests/test_impulse_qdiv_sign_accounting.py', 'tests/test_impulse_round_add_accounting.py',
                 'tests/test_impulse_resource_allocation.py', 'tests/test_impulse_mutant_resource_probe.py'],
    'impulse': [sys.executable, '-m', 'pytest', '-q', *impulse],
    'spec': [sys.executable, '-m', 'pytest', '-q', 'tests/test_impulse_attempt_reason_spec.py'],
    'full': [sys.executable, '-m', 'pytest', '-q'],
    'static': [sys.executable, 'audit/c1b1-attempt-reason-null-2026-10-05/check_spec.py',
               '--output', str(OUT / 'static-spec-checks.json')],
    'mutants': [sys.executable, 'audit/c1b1-qdiv-sign-fix-2026-10-05/run_mutants.py'],
    'diff-check': ['git', 'diff', '--check'],
}
command = commands[mode]
if mode in ('targeted', 'impulse', 'spec', 'full'):
    command.append('--junitxml=' + str(OUT / (mode + '.xml')))
receipt = OUT / (mode + '-command.json')
if receipt.exists():
    raise ValueError('refusing to overwrite evidence')
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted((ROOT / 'independent_checker/c1b1/impulse').glob('*.py'))}
started = time.monotonic()
r = subprocess.run(command, cwd=ROOT, capture_output=True)
duration = time.monotonic() - started
(OUT / (mode + '-stdout.txt')).write_bytes(r.stdout)
(OUT / (mode + '-stderr.txt')).write_bytes(r.stderr)
after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted((ROOT / 'independent_checker/c1b1/impulse').glob('*.py'))}
receipt.write_text(json.dumps(dict(command=command, exit=r.returncode, elapsed_seconds=duration,
                   source_before=before, source_after=after, source_unchanged=before == after),
                   indent=2) + '\n', encoding='ascii')
print(r.stdout.decode('utf8', errors='replace'))
print(r.stderr.decode('utf8', errors='replace'), file=sys.stderr)
print('ACTUAL_EXIT', r.returncode, 'SOURCE_UNCHANGED', before == after)
sys.exit(r.returncode)
