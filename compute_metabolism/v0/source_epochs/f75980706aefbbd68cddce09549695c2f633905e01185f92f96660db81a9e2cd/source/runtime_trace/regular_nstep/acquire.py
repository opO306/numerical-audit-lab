"""Fresh generic capture launcher; old accepted-case entry points are untouched."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def validate_n(n):
    if type(n) is not int or not 1 <= n <= 100:
        raise ValueError('finite supported step request 1..100 required')
    return n


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def harness_source(root):
    path = Path(root) / 'runtime_trace/harness.py'
    original = path.read_text(encoding='utf-8')
    calculation = 'n_steps=1'
    metadata = '"n_steps": 1'
    if original.count(calculation) != 1 or original.count(metadata) != 1:
        raise ValueError('original harness token contract')
    source = original.replace(calculation, 'n_steps=int(os.environ["RTN_STEPS"])').replace(
        metadata, '"n_steps": int(os.environ["RTN_STEPS"])')
    return source, {'original_sha256': sha(path),
        'executed_lf_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'calculation_replacement': 'n_steps=1 -> n_steps=int(os.environ["RTN_STEPS"])',
        'metadata_replacement': 'n_steps metadata uses the same requested environment parameter',
        'all_other_source_text_identical': True, 'external_gala_modified': False}


def collector_source(original, kind):
    pairs = {
        'body': ('time.perf_counter()-self.started > 120 or self.count >= 5000',
                 'time.perf_counter()-self.started > 600 or self.count >= 125000'),
        'caller': ('self.records >= 100000 or time.perf_counter() - self.started > 180',
                   'self.records >= 100000 or time.perf_counter() - self.started > 600')}
    before, after = pairs[kind]
    if original.count(before) != 1:
        raise ValueError('collector guard source contract: ' + kind)
    return original.replace(before, after), {'kind': kind, 'before': before, 'after': after,
        'replacement_count': 1, 'all_other_source_text_identical': True}


SOURCE_PATHS = ('runtime_trace/harness.py', 'runtime_trace/gdb_capture.py',
    'runtime_trace/semantics.py', 'runtime_trace/regular_2step/acquire.py',
    'runtime_trace/regular_2step/gdb_acquire.py',
    'runtime_trace/caller_transition/gdb_acquire_reads.py',
    'runtime_trace/caller_transition/read_effects.py',
    'runtime_trace/caller_transition/write_effects_reads.py',
    'runtime_trace/caller_transition/write_effects.py',
    'runtime_trace/caller_transition/module_resolver.py',
    'runtime_trace/caller_transition/frozen_modules/manifest.json',
    'runtime_trace/regular_nstep/acquire.py', 'runtime_trace/regular_nstep/gdb_acquire.py',
    'runtime_trace/regular_nstep/harness.py', 'runtime_trace/regular_nstep/resources.py')


def source_pinset(root):
    return {relative: sha(Path(root) / relative) for relative in SOURCE_PATHS}


def write(path, value):
    data = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if len(data) > 67108864:
        raise ValueError('receipt 64 MiB ceiling')
    from .resources import reserve_writer
    reserve_writer(len(data))
    with Path(path).open('xb') as stream:
        stream.write(data)


def read_pending(out, n):
    path = Path(out) / 'capture.pending.json'
    if not path.is_file():
        return {'schema': 'gala-regular-nstep-runtime-trace-v1', 'verdict': 'REFUSED',
                'requested_steps': n, 'reason': 'collector failed before publishing a capture receipt',
                'regions': [], 'record_count': 0, 'trace_sha256': None}
    return json.loads(path.read_bytes())


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    n = validate_n(args.steps)
    root = Path(__file__).resolve().parents[2]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    pins = source_pinset(root)
    write(out / 'source_pinset.json', pins)
    command = ['gdb', '-q', '-nx', '-batch', '-x',
               str(root / 'runtime_trace/regular_nstep/gdb_acquire.py'), '--args',
               sys.executable, str(root / 'runtime_trace/regular_nstep/harness.py')]
    env = dict(os.environ, LD_BIND_NOW='1', RT_OUTPUT=str(out), RTN_STEPS=str(n),
               RT2_CASE='known', CT_ANTECEDENT_LABEL='known')
    try:
        process = subprocess.run(command, cwd=root, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=590)
    except subprocess.TimeoutExpired as exc:
        process = subprocess.CompletedProcess(command, 124, exc.stdout or b'')
    # GDB output is bounded by a successful collector's numerical row ceiling.
    # Retain failures and never publish a successful acquisition on nonzero exit.
    if len(process.stdout) > 16 * 1024 * 1024:
        raise ValueError('GDB log ceiling')
    from .resources import reserve_writer
    reserve_writer(len(process.stdout))
    (out / 'gdb.log').write_bytes(process.stdout)
    capture = read_pending(out, n)
    capture['gdb_return_code'] = process.returncode
    capture['source_pinset_sha256'] = sha(out / 'source_pinset.json')
    capture['harness_source_proof'] = harness_source(root)[1]
    if process.returncode != 0:
        capture.update(verdict='REFUSED', reason='nonzero GDB exit')
    capture['acquisition_id'] = hashlib.sha256(json.dumps({
        'process': capture.get('process_identity'), 'trace': capture.get('trace_sha256'),
        'source': pins, 'requested_steps': n}, sort_keys=True).encode()).hexdigest()
    write(out / 'capture.json', capture)
    names = [name for name in ['trace.jsonl', 'capture.json', 'source_pinset.json', 'gdb.log',
                              'capture.pending.json'] if (out / name).is_file()]
    if (out / 'harness_output.json').exists():
        names.append('harness_output.json')
    write(out / 'acquisition_seal.json', {'schema': 'regular-nstep-acquisition-seal-v1',
        'acquisition_id': capture['acquisition_id'], 'files': {name: sha(out / name) for name in names}})
    print(json.dumps({'verdict': capture['verdict'], 'requested_steps': n,
                      'captured_steps': max(0, len(capture.get('regions', [])) - 1),
                      'reason': capture.get('reason')}))
    return 0 if capture['verdict'] == 'CAPTURED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
