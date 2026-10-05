"""QDIV fix author measurements. No runtime/independent approval."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from fractions import Fraction as Q

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'current/c1b1-qdiv-sign-fix-2026-10-05'
SOURCE = ROOT / 'independent_checker/c1b1/impulse'
TARGET = '6a63798adbae7c119439683b356f19ff414ac239'
PARENT = 'd5475e23358cbf7f88018abfb67a8bfd192c5410'
W = 2605253326086889986
PROTECTED = ['claim_adapter.py', 'compare.py', 'contracts.py', 'exact_slow.py',
             'exact_fast.py', 'exact_geometry.py', 'semantic_manifest_v1.json',
             'semantic_manifest_v1.sha256']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('refusing to overwrite evidence: ' + str(path))
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + '\n', encoding='ascii')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def source_hashes():
    return {p.name: sha(p.read_bytes()) for p in sorted(SOURCE.glob('*.py'))}


def initialize():
    assert git('rev-parse', 'HEAD').decode().strip() == TARGET
    assert git('rev-parse', 'HEAD^').decode().strip() == PARENT
    assert not git('diff', '--name-only')
    OUT.mkdir(exist_ok=False)
    paths = git('ls-files', '-z').decode('utf8').split('\0')[:-1]
    save(OUT / 'baseline.json', dict(target=TARGET, parent=PARENT,
         branch=git('branch', '--show-current').decode().strip(),
         tracked_raw_sha256={p: sha((ROOT / p).read_bytes()) for p in paths},
         git_status_after_new_helpers=git('status', '--short').decode('utf8'),
         tracked_changes_before_fix=[]))
    incoming = Path('C:/Users/zun24/.codex/attachments/c903061d-5e30-4a33-b6a3-0c8a2472e851/붙여넣은 텍스트.txt')
    (OUT / 'user-request.txt').write_bytes(incoming.read_bytes())
    fixture = ROOT / 'tests/fixtures/impulse_round_add/COUNTEREXAMPLE_INPUT.json'
    (OUT / 'canonical-input.json').write_bytes(fixture.read_bytes())
    save(OUT / 'received-identity.json', dict(
        request=dict(original=str(incoming), sha256=sha(incoming.read_bytes())),
        canonical_input_sha256=sha(fixture.read_bytes())))
    (OUT / 'resource-before.py').write_bytes((SOURCE / 'resource.py').read_bytes())
    print('BASELINE', len(paths), 'tracked files; target/parent verified')


def imports():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'tests'))


def interval_record(x):
    return dict(lo=dict(n=str(x.lo.numerator), d=str(x.lo.denominator)),
                hi=dict(n=str(x.hi.numerator), d=str(x.hi.denominator)))


def evaluate(obj):
    from independent_checker.c1b1.impulse.producer import evaluate_reference
    from impulse_reference_support import encoded, reference_policy
    data = encoded(obj)
    r = evaluate_reference(data, reference_policy(obj))
    return dict(input_sha256=sha(data), layers=r.layers,
        raw=None if r.raw is None else list(map(str, r.raw)),
        opposite=None if r.opposite is None else list(map(str, r.opposite)),
        certificate=None if r.certificate is None else json.loads(r.certificate),
        failure=None if r.failure is None else json.loads(r.failure), account=r.account,
        scaled_intervals=None if r.scaled_intervals is None else [interval_record(x) for x in r.scaled_intervals],
        input_unchanged=data == encoded(obj))


def mathematical_diagnostics(obj):
    # Same model before/after equality evidence, not an independent oracle.
    from independent_checker.c1b1.impulse.producer import prepared
    from independent_checker.c1b1.impulse.sqrt_enclosure import sqrt_enclosure
    from independent_checker.c1b1.impulse.potential import evaluate_terms, value
    from independent_checker.c1b1.impulse.derivative import derivative
    from impulse_reference_support import encoded, reference_policy
    spec, parsed, binding, reason = prepared(encoded(obj))
    assert reason is None
    policy = reference_policy(obj)
    c = policy.account()
    radius = sqrt_enclosure(sum((x*x for x in parsed.q), Q(0)), policy.N0, c)
    terms = evaluate_terms(spec, radius, policy.P0, policy.exp_order_max, c)
    v = value(terms, c)
    vp = derivative(terms, c)
    return dict(scope='AUTHOR SAME-INPUT MATHEMATICAL EQUALITY / SEPARATE DIAGNOSTIC LEDGER',
                radius=interval_record(radius), V=interval_record(v), V_prime=interval_record(vp),
                exp_orders=[list(row) for row in terms.exp_orders])


def probe(label):
    imports()
    from independent_checker.c1b1.impulse.resource import ResourceAccount, ResourceLimit
    from independent_checker.c1b1.impulse.rounding import nearest_even
    scalar = []
    for divisor in (Q(1), Q(-1)):
        for cap in (40, 43, 44):
            c = ResourceAccount(bit_max=100000, num_bit_max=100000, den_bit_max=100000, work_max=cap)
            row = dict(a='1', b=str(divisor), work_max=cap, result=None, refusal=None)
            try:
                row['result'] = str(c.qdiv(Q(1), divisor))
            except ResourceLimit as err:
                row['refusal'] = err.kind
            row.update(charged_work=c.work, operations=c.operations)
            scalar.append(row)
    rounding = []
    for q, caps in [(Q(7,4), (73,74,75)), (Q(-5,2), (42,44,45))]:
        for cap in caps:
            c = ResourceAccount(bit_max=100000, num_bit_max=100000, den_bit_max=100000, work_max=cap)
            row = dict(q=str(q), work_max=cap, result=None, refusal=None)
            try:
                row['result'] = nearest_even(q,c)
            except ResourceLimit as err:
                row['refusal'] = err.kind
            row.update(charged_work=c.work, operations=c.operations)
            rounding.append(row)
    obj = json.loads((OUT / 'canonical-input.json').read_bytes())
    obj['budget']['work_unit_max'] = str(10**40)
    high = evaluate(obj)
    assert high['raw'] is not None and high['failure'] is None
    observed = high['account']['mathematical_work']
    whole = []
    caps = sorted({W, W+152, observed-1, observed})
    for cap in caps:
        current = json.loads((OUT / 'canonical-input.json').read_bytes())
        current['budget']['work_unit_max'] = str(cap)
        row = evaluate(current)
        row['cap'] = str(cap)
        whole.append(row)
    diagnostics = mathematical_diagnostics(obj)
    result = dict(label=label, source_files=source_hashes(), qdiv=scalar, round_add=rounding,
        observed_work=str(observed), observed_work_scope='CURRENT AUTHOR WRAPPER LEDGER; NOT GLOBAL ACCOUNTING CLOSURE OR PRODUCTION BUDGET',
        sufficient_cap_result=high, whole_call=whole, mathematical_diagnostics=diagnostics)
    if label == 'after':
        before = json.loads((OUT / 'before-boundaries.json').read_text())
        same = dict(raw=high['raw'] == before['sufficient_cap_result']['raw'],
                    J_enclosure=high['scaled_intervals'] == before['sufficient_cap_result']['scaled_intervals'],
                    V_and_derivative=diagnostics == before['mathematical_diagnostics'])
        assert all(same.values())
        result['mathematics_before_after_equal'] = same
        result['additional_qdiv_account_work'] = str(observed-int(before['observed_work']))
        boundary = next(x for x in whole if int(x['cap']) == observed-1)
        assert boundary['raw'] is boundary['opposite'] is boundary['certificate'] is None
        assert (boundary['failure']['reason'],boundary['failure']['resource_kind']) == ('RESOURCE_CAP','WORK')
        save(OUT / 'W2.json', dict(W2=str(observed), scope=result['observed_work_scope'],
            mathematical_raw=high['raw'], operations=high['account']['operations']))
    save(OUT / (label + '-boundaries.json'), result)
    print(label, 'qdiv', scalar, 'rounding', rounding)
    print('OBSERVED WORK', observed, 'operations', high['account']['operations'])
    print('BOUNDARIES', [(x['cap'], x['layers']['producer'], None if x['failure'] is None else x['failure']['reason']) for x in whole])


def preserve():
    old = json.loads((OUT / 'baseline.json').read_text())['tracked_raw_sha256']
    changed = [p for p,h in old.items() if (ROOT/p).exists() and sha((ROOT/p).read_bytes()) != h]
    missing = [p for p in old if not (ROOT/p).exists()]
    protected = {}
    for name in PROTECTED:
        p = 'independent_checker/c1b1/' + name
        data = (ROOT/p).read_bytes()
        protected[p] = dict(sha256=sha(data), equal_target=sha(data)==old[p],
            equal_65d8=data==git('show','65d8fd29ae255529afead70289098d36b825b3b4:'+p))
    history = [p for p in old if p.startswith(('specs/','docs/','audit/','current/'))]
    files = source_hashes()
    bundle = sha((json.dumps(files,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii'))
    save(OUT/'source-identity.json',dict(files=files,source_bundle_sha256=bundle,new_git_commit_sha=None))
    save(OUT/'preservation.json',dict(target=TARGET,base_tracked=len(old),changed=changed,missing=missing,
        unchanged=len(old)-len(changed)-len(missing),historical_count=len(history),
        historical_byte_identical=all(p not in changed+missing for p in history),protected=protected,
        approved_specs_preserved=all(p not in changed+missing for p in old if p.startswith('specs/')),
        rounding_preserved=sha((SOURCE/'rounding.py').read_bytes())==old['independent_checker/c1b1/impulse/rounding.py']))
    (OUT/'resource-after.py').write_bytes((SOURCE/'resource.py').read_bytes())
    (OUT/'resource.diff').write_bytes(git('diff','--','independent_checker/c1b1/impulse/resource.py'))
    assert changed == ['independent_checker/c1b1/impulse/resource.py','tests/test_impulse_round_add_accounting.py']
    assert not missing and all(x['equal_target'] and x['equal_65d8'] for x in protected.values())
    assert all(p not in changed for p in history)
    print('SOURCE',bundle,'CHANGED',changed,'HISTORY PRESERVED',len(history))


if __name__ == '__main__':
    action=argparse.ArgumentParser()
    action.add_argument('action',choices=('init','before','after','preserve'))
    choice=action.parse_args().action
    if choice=='init':initialize()
    elif choice in ('before','after'):probe(choice)
    else:preserve()
