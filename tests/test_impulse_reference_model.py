"""PHYSICAL-STATE binding tests; physical mpmath comparison is diagnostic."""
import copy
from fractions import Fraction as Q
import pytest
from impulse_reference_support import input_object,encoded,nominal_diagnostic
from test_impulse_reference_primitives import module,context


@pytest.mark.parametrize('q,reason',[( (0,0,0),'SINGULAR_SEPARATION'),((0,1,0),'PHYSICAL_DOMAIN'),((0,3,0),None)])
def test_domain_before_zero_axis(q,reason):
    d=module('domain').admit(tuple(Q(v) for v in q),module('spec').load_spec())
    assert d==reason


def test_fixed_input_no_external_or_wrong_grid():
    c=module('contracts'); obj=input_object();old=copy.deepcopy(obj)
    parsed=c.validate_input(encoded(obj),module('spec').load_spec())
    assert parsed.q==tuple(Q(v) for v in (6,2,1)) and obj==old
    for edit in ('J','grid','species','phase','id'):
        bad=copy.deepcopy(obj)
        if edit=='J':bad['external_J_raw']=['0']*3
        if edit=='grid':bad['state']['position_grid']['frac_bits']='47'
        if edit=='species':bad['state']['atoms'][0]['species']='Ar39'
        if edit=='phase':bad['acquisition']['phase']='SECOND_HALF_KICK'
        if edit=='id':bad['state']['atoms'][1]['atom_id']=bad['state']['atoms'][0]['atom_id']
        with pytest.raises(c.ContractFailure):c.validate_input(encoded(bad),module('spec').load_spec())


def test_identity_full_state_momentum_and_occurrence_are_distinct():
    ident=module('identity'); spec=module('spec').load_spec(); obj=input_object()
    a=ident.bind(obj,spec)
    moved=copy.deepcopy(obj);moved['state']['atoms'][0]['momentum_raw'][0]='1';b=ident.bind(moved,spec)
    assert a['full_state_sha256']!=b['full_state_sha256'] and a['projection_sha256']==b['projection_sha256']
    second=copy.deepcopy(obj);second['acquisition'].update(phase='SECOND_HALF_KICK',record_id='7'*64,acquisition_id='8'*64,previous_occurrence_sha256=a['occurrence_sha256'])
    d=ident.bind(second,spec)
    assert a['occurrence_sha256']!=d['occurrence_sha256'] and a['projection_sha256']==d['projection_sha256']


def test_bo_minus_one_polynomial_derivative_exact():
    p=module('potential');spec=module('spec').load_spec();m=module('interval');r=m.point(Q(3));c=context()
    poly,derivative=p.polynomial(spec,'BO',1,r,c)
    assert poly.lo==poly.hi and derivative.lo==derivative.hi
    # Literal independently transcribed exact coefficients; includes -a/R^2.
    assert derivative.lo==-Q(54894707,2500)/9+Q(213032369,2500)+6*Q(476626377,5000)


@pytest.mark.parametrize('r',[Q(3),Q(6),Q(17,2)])
def test_value_and_derivative_diagnostic_against_different_method(r):
    import mpmath as mp
    spec=module('spec').load_spec();m=module('interval');c=context();c.work_max=10**40
    with mp.workdps(150):
        want_v,want_d=nominal_diagnostic(mp.mpf(r.numerator)/r.denominator)
        terms=module('potential').evaluate_terms(spec,m.point(r),128,512,c)
        v=module('potential').value(terms,c);d=module('derivative').derivative(terms,c)
        def number(q):return mp.mpf(q.numerator)/q.denominator
        assert number(v.lo)<=want_v<=number(v.hi)
        assert number(d.lo)<=want_d<=number(d.hi)
        assert number(d.hi-d.lo)<mp.mpf('1e-24')
