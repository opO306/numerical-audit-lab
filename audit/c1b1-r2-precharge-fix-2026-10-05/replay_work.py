"""Recompute costs from real pre() caller operands; author evidence only."""
from collections import Counter
import json
import sys

from verify import ROOT, OUT, imports, save, sources, record, sha

imports()
from impulse_reference_support import encoded, reference_policy
from independent_checker.c1b1.impulse.producer import evaluate_reference

rows = []
pending = {}
in_r2 = False
entry = None


def formula(name, values):
    if name in ('add', 'multiply', 'divmod'):
        a, b = values['a'], values['b']
        A, B = abs(a).bit_length(), abs(b).bit_length()
        operands = dict(A=A, B=B)
        if name == 'add':
            bits = max(A, B) + 1
            return bits, bits, operands
        if name == 'multiply':
            return A+B, (A+1)*(B+1), operands
        return max(A, B)+1, (A+1)*(B+1)**2, operands
    if name == 'shift':
        A, n = abs(values['a']).bit_length(), values['n']
        return A+n+1, A+n+1, dict(A=A, shift=n)
    if name == 'isqrt':
        A = values['a'].bit_length()
        return A+1, (A+1)**3, dict(A=A)
    if name == 'fraction':
        A, B = abs(values['n']).bit_length(), abs(values['d']).bit_length()
        M = max(A, B)
        return M+1, (2*M+2)*(M+1)**3, dict(A=A, B=B, M=M)
    if name == 'compare':
        A, B = abs(values['u']).bit_length(), abs(values['v']).bit_length()
        return max(A, B)+1, max(A, B)+1, dict(A=A, B=B)
    raise AssertionError('Unassigned actual precharge caller: ' + name)


def profile(frame, event, arg):
    global in_r2, entry
    module = frame.f_globals.get('__name__')
    name = frame.f_code.co_name
    if event == 'return' and module == 'independent_checker.c1b1.impulse.policy' and name == 'account':
        in_r2 = True
    if event == 'call' and module == 'independent_checker.c1b1.impulse.sqrt_enclosure' and name == 'sqrt_enclosure' and entry is None:
        c = frame.f_locals['c']
        entry = dict(r2=str(frame.f_locals['r2']), work=c.work, operations=c.operations)
        in_r2 = False
    if module != 'independent_checker.c1b1.impulse.resource' or name != 'pre':
        return
    if event == 'call':
        c = frame.f_locals['self']
        caller = frame.f_back
        primitive = caller.f_code.co_name
        bits, work, operands = formula(primitive, caller.f_locals)
        assert bits == frame.f_locals['bits'] and work == frame.f_locals['work']
        row = dict(primitive=primitive, wrapper_line=caller.f_lineno, declared_bits=bits,
                   declared_work=frame.f_locals['work'], recomputed_work=work,
                   actual_operand_bit_lengths=operands, work_before=c.work, operations_before=c.operations,
                   scope='R2' if in_r2 else 'FOLLOWING_REFERENCE_PATH')
        if in_r2:
            row['actual_integer_operands'] = {k: str(v) for k, v in caller.f_locals.items()
                                              if k in ('a', 'b', 'n', 'd')}
        pending[id(frame)] = row
    elif event == 'return':
        row = pending.pop(id(frame))
        c = frame.f_locals['self']
        row.update(work_after=c.work, operations_after=c.operations)
        assert c.work-row['work_before'] == row['recomputed_work']
        assert c.operations-row['operations_before'] == 1
        rows.append(row)


obj = json.loads((OUT / 'canonical-input.json').read_bytes())
obj['budget']['work_unit_max'] = str(10**40)
source_before = sources()
previous = sys.getprofile()
try:
    sys.setprofile(profile)
    result = evaluate_reference(encoded(obj), reference_policy(obj))
finally:
    sys.setprofile(previous)
assert result.failure is None and result.raw is not None and not pending
source_after = sources()
assert source_before == source_after
r2 = [row for row in rows if row['scope'] == 'R2']
assert sum(row['recomputed_work'] for row in rows) == result.account['mathematical_work']
assert len(rows) == result.account['operations']
assert sum(row['recomputed_work'] for row in r2) == entry['work']
assert len(r2) == entry['operations']
before = json.loads((OUT / 'before-boundaries.json').read_text())
assert result.account['mathematical_work']-int(before['observed_work']) == entry['work']
finite = ROOT / 'specs/c1b1-independent-impulse-v1-attempt-reason-null/finite-policy.json'
save(OUT / 'actual-work-reconstruction.json', dict(
    scope='AUTHOR REPLAY OF DECLARED COSTS FROM ACTUAL CALLER OPERANDS; NOT A NEW INDEPENDENT AUDIT OR GLOBAL COMPLETENESS PROOF',
    input_sha256=sha(encoded(obj)), source_files=source_before, source_unchanged=True,
    finite_policy_sha256=sha(finite.read_bytes()), declared_schedule=json.loads(finite.read_text())['work_accounting'],
    W3=str(result.account['mathematical_work']), primitive_operations=len(rows),
    classes=dict(Counter(row['primitive'] for row in rows)), R2_entry=entry,
    R2_classes=dict(Counter(row['primitive'] for row in r2)), actual_precharges=rows,
    actual_R2_precharges=r2, result=record(result),
    remaining_open=['O-CONTROL-PARAMETERS', 'O-DIRECT-FRACTION-CONSTRUCTION', 'O-ALLOCATION-AND-WORKER'],
    global_resource_accounting_pass=False, runtime_activation_allowed=False))
print('ACTUAL OPERAND REPLAY', len(rows), 'precharges, work', result.account['mathematical_work'])
print('R2 RECOMPUTED', len(r2), 'precharges, work', entry['work'], 'classes', dict(Counter(row['primitive'] for row in r2)))
print('GLOBAL ACCOUNTING NOT PASS; R2 AUTHOR REGRESSION EVIDENCE ONLY')
