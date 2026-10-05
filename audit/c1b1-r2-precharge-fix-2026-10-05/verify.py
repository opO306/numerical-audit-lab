"""R2-only author probes, exact before/after and preservation evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from fractions import Fraction as Q

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'current/c1b1-r2-precharge-fix-2026-10-05'
SOURCE = ROOT / 'independent_checker/c1b1/impulse'
TARGET = 'baba8ea942b896af64ceaa7ab41e2bc5db73112c'
PARENT = '6a63798adbae7c119439683b356f19ff414ac239'
W = 2605253326086889986
W2 = 2605253326092204528


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, obj):
    assert not path.exists(), 'refusing overwrite: ' + str(path)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + '\n', encoding='ascii')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def sources():
    return {p.name: sha(p.read_bytes()) for p in sorted(SOURCE.glob('*.py'))}


def imports():
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]


def initialize():
    assert git('rev-parse', 'HEAD').decode().strip() == TARGET
    assert git('rev-parse', 'HEAD^').decode().strip() == PARENT
    assert not git('diff', '--name-only')
    paths = git('ls-files', '-z').decode().split('\0')[:-1]
    save(OUT / 'baseline.json', dict(target=TARGET, parent=PARENT,
         branch=git('branch', '--show-current').decode().strip(),
         tracked_raw_sha256={p: sha((ROOT / p).read_bytes()) for p in paths},
         source_files=sources(), tracked_changes_before_fix=[],
         scope_authorization='Explicit user reply authorizes minimal R2 fix, derived W3 and required regressions; no commit/push'))
    fixture = ROOT / 'tests/fixtures/impulse_round_add/COUNTEREXAMPLE_INPUT.json'
    (OUT / 'canonical-input.json').write_bytes(fixture.read_bytes())
    (OUT / 'producer-before.py').write_bytes((SOURCE / 'producer.py').read_bytes())
    (OUT / 'r2-test-before-fix.py').write_bytes((ROOT / 'tests/test_impulse_r2_precharge.py').read_bytes())
    received = ROOT / 'current/c1b1-qdiv-limited-reaudit-received-2026-10-05/received-identity.json'
    save(OUT / 'received-audit-binding.json', dict(path=received.relative_to(ROOT).as_posix(), sha256=sha(received.read_bytes()),
         independent_scope='ROUND-ADD / QDIV-SIGN PASS on baba source; R2 CONFIRMED FAIL; full implementation NOT APPROVED'))
    print('BASELINE', len(paths), 'tracked; target/parent match')


def interval(x):
    return dict(lo=dict(n=str(x.lo.numerator), d=str(x.lo.denominator)),
                hi=dict(n=str(x.hi.numerator), d=str(x.hi.denominator)))


def record(result):
    return dict(layers=result.layers, raw=None if result.raw is None else list(map(str, result.raw)),
                opposite=None if result.opposite is None else list(map(str, result.opposite)),
                certificate=None if result.certificate is None else json.loads(result.certificate),
                failure=None if result.failure is None else json.loads(result.failure), account=result.account,
                J=None if result.scaled_intervals is None else [interval(x) for x in result.scaled_intervals])


def diagnostics(obj):
    from independent_checker.c1b1.impulse.producer import prepared
    from independent_checker.c1b1.impulse.sqrt_enclosure import sqrt_enclosure
    from independent_checker.c1b1.impulse.potential import evaluate_terms, value
    from independent_checker.c1b1.impulse.derivative import derivative
    from impulse_reference_support import encoded, reference_policy
    spec, parsed, _, reason = prepared(encoded(obj))
    assert reason is None
    c = reference_policy(obj).account()
    r2 = sum((x*x for x in parsed.q), Q(0))
    radius = sqrt_enclosure(r2, reference_policy(obj).N0, c)
    terms = evaluate_terms(spec, radius, reference_policy(obj).P0, reference_policy(obj).exp_order_max, c)
    return dict(scope='AUTHOR SAME-INPUT EXACT COMPARISON; SEPARATE DIAGNOSTIC LEDGER',
                R2=str(r2), radius=interval(radius), V=interval(value(terms, c)),
                V_prime=interval(derivative(terms, c)), exp_orders=[list(row) for row in terms.exp_orders])


def probe(label):
    imports()
    from impulse_reference_support import encoded, reference_policy, input_object
    from test_impulse_r2_precharge import trace_r2, expected_r2_schedule
    from independent_checker.c1b1.impulse.producer import evaluate_reference, produce, prepared
    cases = []
    for name, obj in [('canonical', json.loads((OUT / 'canonical-input.json').read_bytes())),
                      ('noninteger_dyadic', input_object((Q(11, 2), Q(-3, 2), 0))),
                      ('signed_zero_axis', input_object((0, -6, 2)))]:
        obj['budget']['work_unit_max'] = str(10**40)
        before_bytes = encoded(obj)
        _, parsed, _, reason = prepared(before_bytes)
        assert reason is None
        result, events = trace_r2(obj)
        assert result.failure is None and result.raw is not None
        entry = next(e for e in events if e['event'] == 'sqrt_entry')
        entry['r2'] = str(entry['r2'])
        expected, schedule = expected_r2_schedule(parsed.q)
        assert str(expected) == entry['r2']
        cases.append(dict(name=name, q=[str(x) for x in parsed.q], input=obj, input_sha256=sha(before_bytes),
                          input_unchanged=before_bytes == encoded(obj), domain_admitted=True,
                          result=record(result), R2_trace=events, R2_entry=entry,
                          expected_abstract_schedule=[list(row) for row in schedule],
                          expected_R2_work=str(sum(cost for _, cost in schedule)),
                          diagnostics=diagnostics(obj)))
    observed = cases[0]['result']['account']['mathematical_work']
    low = []
    for cap in (1, 31, 32, 47, 48):
        obj = json.loads((OUT / 'canonical-input.json').read_bytes())
        obj['budget']['work_unit_max'] = str(cap)
        result, events = trace_r2(obj)
        for e in events:
            if e['event'] == 'sqrt_entry':
                e['r2'] = str(e['r2'])
        low.append(dict(cap=cap, input_sha256=sha(encoded(obj)), result=record(result), actual_R2_trace=events))
    whole = []
    for cap in sorted({W, W+152, W2, observed-1, observed}):
        obj = json.loads((OUT / 'canonical-input.json').read_bytes())
        obj['budget']['work_unit_max'] = str(cap)
        result = evaluate_reference(encoded(obj), reference_policy(obj))
        whole.append(dict(cap=str(cap), input_sha256=sha(encoded(obj)), result=record(result)))
    public = produce((OUT / 'canonical-input.json').read_bytes())
    obj = dict(label=label, source_files=sources(), cases=cases, low_cap_R2=low, whole_call=whole,
               observed_work=str(observed), public_result=record(public))
    if label == 'after':
        old = json.loads((OUT / 'before-boundaries.json').read_text())
        equal = {}
        for a, b in zip(old['cases'], cases):
            assert a['name'] == b['name'] and a['input_sha256'] == b['input_sha256']
            equal[b['name']] = dict(R2=a['R2_entry']['r2'] == b['R2_entry']['r2'],
                diagnostics=a['diagnostics'] == b['diagnostics'], J=a['result']['J'] == b['result']['J'],
                raw=a['result']['raw'] == b['result']['raw'])
            assert all(equal[b['name']].values())
            assert b['R2_entry']['work'] == int(b['expected_R2_work'])
        obj['mathematics_before_after_equal'] = equal
        obj['observed_R2_work_delta'] = str(observed-int(old['observed_work']))
        assert observed-int(old['observed_work']) == cases[0]['R2_entry']['work']
        save(OUT / 'W3.json', dict(W3=str(observed), previous_W2=str(W2),
             observed_R2_work_delta=obj['observed_R2_work_delta'],
             R2_operations=cases[0]['R2_entry']['operations'], operations=cases[0]['result']['account']['operations'],
             raw=cases[0]['result']['raw'], scope='CURRENT AUTHOR WRAPPER LEDGER; NOT GLOBAL FULLY-ACCOUNTED OR PRODUCTION BUDGET'))
    save(OUT / (label+'-boundaries.json'), obj)
    print(label, 'OBSERVED WORK', observed, 'operations', cases[0]['result']['account']['operations'])
    print('R2 entry', cases[0]['R2_entry'], 'expected recomputed work', cases[0]['expected_R2_work'])
    print('WHOLE', [(r['cap'], None if r['result']['failure'] is None else r['result']['failure']['reason']) for r in whole])


def preserve():
    baseline = json.loads((OUT / 'baseline.json').read_text())
    old = baseline['tracked_raw_sha256']
    changed = [p for p, h in old.items() if (ROOT / p).is_file() and sha((ROOT / p).read_bytes()) != h]
    missing = [p for p in old if not (ROOT / p).is_file()]
    assert changed == ['independent_checker/c1b1/impulse/producer.py', 'tests/test_impulse_round_add_accounting.py']
    assert not missing
    history = [p for p in old if p.startswith(('specs/', 'docs/', 'audit/', 'current/'))]
    assert all(p not in changed for p in history)
    live = sources()
    assert all(h == baseline['source_files'][p] for p, h in live.items() if p != 'producer.py')
    bundle = sha((json.dumps(live, sort_keys=True, separators=(',', ':'), ensure_ascii=True)+'\n').encode('ascii'))
    save(OUT / 'source-identity.json', dict(files=live, source_bundle_sha256=bundle, new_git_commit_sha=None))
    save(OUT / 'preservation.json', dict(target=TARGET, base_tracked=len(old), changed=changed,
         missing=missing, unchanged=len(old)-len(changed), historical_count=len(history),
         historical_working_raw_preserved=True, approved_specs_preserved=True,
         resource_py_preserved=True, rounding_py_preserved=True,
         scope='Working-byte identity is relative to recorded current baseline; not a claim that working bytes equal all historical Git blobs'))
    (OUT / 'producer-after.py').write_bytes((SOURCE / 'producer.py').read_bytes())
    (OUT / 'producer.diff').write_bytes(git('diff', '--', 'independent_checker/c1b1/impulse/producer.py'))
    print('PRESERVED', len(old)-2, 'baseline working files;', len(history), 'historical working files; BUNDLE', bundle)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=('init', 'before', 'after', 'preserve'))
    action = p.parse_args().action
    if action == 'init':
        initialize()
    elif action in ('before', 'after'):
        probe(action)
    else:
        preserve()
