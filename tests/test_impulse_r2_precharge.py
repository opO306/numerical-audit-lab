"""R2 pre-operation author regressions; no global or independent approval."""
import copy
import ast
import inspect
import json
from fractions import Fraction as Q
from pathlib import Path
import sys
import textwrap

import pytest

from impulse_reference_support import encoded, input_object, reference_policy
from independent_checker.c1b1.impulse.producer import evaluate_reference, prepared
from independent_checker.c1b1.impulse.resource import ResourceAccount

FIXTURE = Path(__file__).parent / 'fixtures/impulse_round_add/COUNTEREXAMPLE_INPUT.json'
# Pinned only after actual measurement and before/after equality verification.
# Current wrapper ledger, not a global accounting proof or production budget.
W3 = 2605253326092221245
EXPECTED_RAW = (52119986341579705480988, 31271991804947823288593, -20847994536631882192395)


def trace_r2(obj):
    """Observe the actual account-to-sqrt corridor without replacing functions."""
    events = []
    active = False
    previous = sys.getprofile()
    previous_trace = sys.gettrace()
    multiply_source = ast.parse(textwrap.dedent(inspect.getsource(ResourceAccount.multiply)))
    product = next(n for n in ast.walk(multiply_source) if isinstance(n, ast.Return))
    product_line = ResourceAccount.multiply.__code__.co_firstlineno + product.lineno - 1

    def line_trace(frame, event, arg):
        if frame.f_code is not ResourceAccount.multiply.__code__:
            return None
        if active and event == 'line' and frame.f_lineno == product_line:
            c = frame.f_locals['self']
            events.append(dict(event='integer_product', a=frame.f_locals['a'], b=frame.f_locals['b'],
                               ledger=c.work, operations=c.operations))
        return line_trace

    def profile(frame, event, arg):
        nonlocal active
        module = frame.f_globals.get('__name__')
        name = frame.f_code.co_name
        if event == 'return' and module == 'independent_checker.c1b1.impulse.policy' and name == 'account':
            active = True
        if not active or event != 'call':
            return
        if module == 'fractions' and name in ('_mul', '_add'):
            events.append(dict(event=name, a=str(frame.f_locals['a']), b=str(frame.f_locals['b'])))
        elif module == 'independent_checker.c1b1.impulse.resource' and name == 'pre':
            c = frame.f_locals['self']
            caller = frame.f_back
            events.append(dict(event='pre', primitive=caller.f_code.co_name,
                               work=frame.f_locals['work'], ledger=c.work, operations=c.operations,
                               operands={k: str(v) for k, v in caller.f_locals.items() if k in ('a', 'b', 'n', 'd')}))
        elif module == 'independent_checker.c1b1.impulse.sqrt_enclosure' and name == 'sqrt_enclosure':
            c = frame.f_locals['c']
            events.append(dict(event='sqrt_entry', r2=frame.f_locals['r2'],
                               work=c.work, operations=c.operations))
            active = False

    try:
        sys.setprofile(profile)
        sys.settrace(line_trace)
        result = evaluate_reference(encoded(obj), reference_policy(obj))
    finally:
        sys.settrace(previous_trace)
        sys.setprofile(previous)
    return result, events


def expected_r2_schedule(q):
    """Separate declared-cost arithmetic; does not call ResourceAccount."""
    rows = []

    def multiply(a, b):
        cost = (abs(a).bit_length() + 1) * (abs(b).bit_length() + 1)
        rows.append(('multiply', cost))
        return a * b

    def add(a, b):
        rows.append(('add', max(abs(a).bit_length(), abs(b).bit_length()) + 1))
        return a + b

    def fraction(n, d):
        m = max(abs(n).bit_length(), abs(d).bit_length())
        rows.append(('fraction', (2*m + 2) * (m + 1)**3))
        return Q(n, d)

    value = fraction(0, 1)
    for x in q:
        squared = fraction(multiply(x.numerator, x.numerator),
                           multiply(x.denominator, x.denominator))
        numerator = add(multiply(value.numerator, squared.denominator),
                        multiply(squared.numerator, value.denominator))
        value = fraction(numerator, multiply(value.denominator, squared.denominator))
    return value, rows


@pytest.mark.parametrize('cap,ledger,operations,primitives', [
    (1, 0, 0, ['fraction']),
    (31, 0, 0, ['fraction']),
    (32, 32, 1, ['fraction', 'multiply']),
    (47, 32, 1, ['fraction', 'multiply']),
    (48, 48, 2, ['fraction', 'multiply', 'multiply']),
])
def test_canonical_r2_stops_before_disallowed_operation(cap, ledger, operations, primitives):
    obj = json.loads(FIXTURE.read_bytes())
    obj['budget']['work_unit_max'] = str(cap)
    result, events = trace_r2(obj)
    assert not any(e['event'] in ('_mul', '_add', 'sqrt_entry') for e in events)
    charges = [e for e in events if e['event'] == 'pre']
    assert [e['primitive'] for e in charges] == primitives
    assert (charges[-1]['ledger'], charges[-1]['operations']) == (ledger, operations)
    assert charges[-1]['work'] > cap - ledger
    assert result.raw is result.opposite is result.certificate is result.account is None
    failure = json.loads(result.failure)
    assert (failure['phase'], failure['reason'], failure['resource_kind']) == ('COMPUTE', 'RESOURCE_CAP', 'WORK')
    if cap in (32, 47):
        assert charges[-1]['operands'] == {'a': '5', 'b': '5'}
        assert charges[-1]['work'] == ((5).bit_length() + 1)**2
    products = [e for e in events if e['event'] == 'integer_product']
    assert products == ([] if cap != 48 else [dict(event='integer_product', a=5, b=5, ledger=48, operations=2)])


@pytest.mark.parametrize('q', [(5, 3, -2), (Q(11, 2), Q(-3, 2), 0), (0, -6, 2)])
def test_admitted_r2_schedule_and_exact_result(q):
    obj = input_object(q)
    _, parsed, _, reason = prepared(encoded(obj))
    assert reason is None
    expected, schedule = expected_r2_schedule(parsed.q)
    result, events = trace_r2(obj)
    assert result.failure is None
    assert not any(e['event'] in ('_mul', '_add') for e in events)
    entry = next(e for e in events if e['event'] == 'sqrt_entry')
    assert entry['r2'] == expected == sum((x*x for x in parsed.q), Q(0))
    assert entry['work'] == sum(cost for _, cost in schedule)
    assert entry['operations'] == len(schedule)
    assert [(e['primitive'], e['work']) for e in events if e['event'] == 'pre'] == schedule


def test_canonical_whole_call_one_below_w3_has_no_outputs():
    obj = json.loads(FIXTURE.read_bytes())
    obj['budget']['work_unit_max'] = str(W3 - 1)
    saved = copy.deepcopy(obj)
    result = evaluate_reference(encoded(obj), reference_policy(obj))
    assert obj == saved
    assert result.raw is result.opposite is result.certificate is result.account is None
    failure = json.loads(result.failure)
    assert (failure['phase'], failure['reason'], failure['resource_kind']) == ('PUBLICATION', 'RESOURCE_CAP', 'WORK')
    assert result.layers['producer'] == 'RESOLVED'
    assert (result.layers['publication'], result.layers['execution']) == ('NOT_PUBLISHED', 'STOP')


def test_canonical_whole_call_w3_preserves_exact_raw():
    obj = json.loads(FIXTURE.read_bytes())
    obj['budget']['work_unit_max'] = str(W3)
    saved = copy.deepcopy(obj)
    result = evaluate_reference(encoded(obj), reference_policy(obj))
    assert obj == saved
    assert result.failure is None and result.raw == EXPECTED_RAW
    assert result.opposite == tuple(-x for x in EXPECTED_RAW)
    assert result.certificate is not None
    assert result.account['mathematical_work'] == W3
    assert result.account['operations'] == 36851
    assert (result.layers['publication'], result.layers['execution']) == ('NOT_PUBLISHED', 'STOP')
