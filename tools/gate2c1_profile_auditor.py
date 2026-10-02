"""Bounded profiling of the received auditor; never a 100k campaign."""
import cProfile
import hashlib
import importlib.util
import json
import platform
import pstats
import sys
import time
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    target = ROOT / 'audit/gate2c1/prior_auditor/g2c_regular.py'
    out = ROOT / 'audit/gate2c1/cost_survey.json'
    if out.exists():
        raise SystemExit('preserve existing cost survey')
    spec = importlib.util.spec_from_file_location('received_auditor', target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = str(ROOT)  # only filesystem binding; original file bytes untouched
    runs = []
    start = time.perf_counter()
    for n in (128, 512, 1024):
        if time.perf_counter() - start >= 60:
            break
        prof = cProfile.Profile()
        t = time.perf_counter()
        prof.runcall(mod.orbit, 'regular', n)
        elapsed = time.perf_counter() - t
        stat = pstats.Stats(prof)
        entries = [{'file': f, 'line': line, 'function': fn, 'primitive_calls': cc,
                    'calls': nc, 'self_seconds': tt, 'cumulative_seconds': ct}
                   for (f,line,fn),(cc,nc,tt,ct,callers) in stat.stats.items()]
        runs.append({'steps': n, 'wall_seconds_profiled': elapsed,
                     'top_cumulative': sorted(entries,key=lambda e:-e['cumulative_seconds'])[:25],
                     'top_self': sorted(entries,key=lambda e:-e['self_seconds'])[:15]})
    # Observer-only second short execution: no replacement of the accepted operator.
    from lab import v2_bound
    seen = {'inverse_calls': 0, 'max_numerator_bits': 0, 'max_denominator_bits': 0,
            'all_inverse_matrix_inputs_float': True}
    def observer(frame,event,arg):
        if event == 'call' and frame.f_code is v2_bound._inverse.__code__:
            seen['inverse_calls'] += 1
            for row in frame.f_locals['A']:
                for v in row:
                    seen['all_inverse_matrix_inputs_float'] &= type(v) is float
                    q = Fraction(v)
                    seen['max_numerator_bits'] = max(seen['max_numerator_bits'],abs(q.numerator).bit_length())
                    seen['max_denominator_bits'] = max(seen['max_denominator_bits'],q.denominator.bit_length())
    sys.setprofile(observer)
    try:
        mod.orbit('regular',128)
    finally:
        sys.setprofile(None)
    result = {'schema': 'gate2c1-received-auditor-cost-survey-v1',
              'source_path': target.relative_to(ROOT).as_posix(),
              'source_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'source_bytes_changed': False, 'filesystem_binding': str(ROOT),
              'environment': {'python': platform.python_version(), 'system': platform.platform()},
              'runs': runs, 'inverse_input_observer_128steps': seen,
              'total_wall_seconds': time.perf_counter()-start,
              'historical_regular_stdout_or_profile_available': False,
              'historical_runtime_cause_established': False,
              'new_gate2c1_horizon_measured': False, 'new_100000_step_execution': False}
    out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({'cost_survey': str(out), 'runs':[(r['steps'],r['wall_seconds_profiled']) for r in runs],
                      'observer':seen, 'total_wall_seconds':result['total_wall_seconds']},indent=2))

if __name__ == '__main__':
    main()
