"""F-RESOURCE-ROUND-ADD author regressions; no independent approval."""
import copy
import json
from fractions import Fraction
from pathlib import Path

import pytest

from impulse_reference_support import encoded, reference_policy
from independent_checker.c1b1.impulse.producer import evaluate_reference
from independent_checker.c1b1.impulse.resource import ResourceAccount, ResourceLimit
from independent_checker.c1b1.impulse.rounding import nearest_even


FIXTURE = Path(__file__).parent / 'fixtures/impulse_round_add/COUNTEREXAMPLE_INPUT.json'
W = 2605253326086889986
EXPECTED_RAW = (
    52119986341579705480988,
    31271991804947823288593,
    -20847994536631882192395,
)


def account(work_max):
    return ResourceAccount(bit_max=100000, num_bit_max=100000,
                           den_bit_max=100000, work_max=work_max)


@pytest.mark.parametrize('q,cap,charged_before_add', [
    (Fraction(7, 4), 73, 73),
    (Fraction(7, 4), 74, 73),
    (Fraction(-5, 2), 42, 42),
    (Fraction(-5, 2), 44, 42),
])
def test_increment_refuses_before_add(q, cap, charged_before_add):
    c = account(cap)
    with pytest.raises(ResourceLimit) as err:
        nearest_even(q, c)
    assert err.value.kind == 'WORK'
    # Rejected add must not advance the ledger or return a rounded value.
    assert (c.work, c.operations) == (charged_before_add, 2)


@pytest.mark.parametrize('q,cap,expected', [
    (Fraction(7, 4), 75, 2),
    (Fraction(-5, 2), 45, -2),
])
def test_increment_charged_at_exact_boundary(q, cap, expected):
    c = account(cap)
    assert nearest_even(q, c) == expected
    assert (c.work, c.operations) == (cap, 3)


@pytest.mark.parametrize('q,expected', [
    (Fraction(7, 4), 2), (Fraction(-5, 2), -2),
    (Fraction(5, 2), 2), (Fraction(-7, 2), -4),
    (Fraction(5, 4), 1), (Fraction(-7, 4), -2),
])
def test_unaccounted_mathematical_rounding_unchanged(q, expected):
    assert nearest_even(q) == expected


def test_canonical_whole_call_refuses_at_old_exact_cap():
    data = FIXTURE.read_bytes()
    obj = json.loads(data)
    before = copy.deepcopy(obj)
    result = evaluate_reference(data, reference_policy(obj))
    assert result.raw is result.opposite is result.certificate is None
    assert result.account is None
    failure = json.loads(result.failure)
    assert (failure['reason'], failure['resource_kind'], failure['phase']) == (
        'RESOURCE_CAP', 'WORK', 'PUBLICATION')
    assert result.layers == {
        'producer': 'RESOLVED', 'rechecker': 'NOT_RUN',
        'executor_comparison': 'NOT_RUN', 'arithmetic': 'NOT_RUN',
        'publication': 'NOT_PUBLISHED', 'execution': 'STOP',
    }
    assert failure['status'] == result.layers
    assert failure['attempt_count'] is None
    assert failure['attempt_digest'] == '4127e8735c008c88f0e9105fe8e895d60bc7776a778277763bf8d6bb940aa41e'
    assert obj == before and data == encoded(obj)


def test_canonical_whole_call_exact_additional_room_preserves_raw():
    obj = json.loads(FIXTURE.read_bytes())
    obj['budget']['work_unit_max'] = str(W + 152)
    before = copy.deepcopy(obj)
    data = encoded(obj)
    result = evaluate_reference(data, reference_policy(obj))
    assert result.failure is None and result.raw == EXPECTED_RAW
    assert result.opposite == tuple(-v for v in EXPECTED_RAW)
    assert result.account['mathematical_work'] == W + 152
    assert result.account['operations'] == 35236
    assert result.layers['producer'] == 'RESOLVED'
    assert result.layers['publication'] == 'NOT_PUBLISHED'
    assert result.layers['execution'] == 'STOP'
    cert = json.loads(result.certificate)
    assert tuple(map(int, cert['raw_J'])) == EXPECTED_RAW
    assert 'final_interval' not in cert
    assert obj == before and data == encoded(obj)
