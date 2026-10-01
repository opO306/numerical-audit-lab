import math
from fractions import Fraction as Q

import pytest

from benchmarks.gate2c.binary_replay import BinaryReplay
from benchmarks.gate2a.henon_heiles import bits, exact_steps
from lab.gate2b_fixture import load, qval
from lab.gate2c_checks import BinBound, cross_check, exact_window, replay_comparison


@pytest.mark.parametrize('orbit', ['regular', 'chaotic'])
def test_binary_replay_frozen_fixture_and_late_tamper(orbit):
    rows = [r[:1001] for r in load(orbit + '_forward')]
    assert replay_comparison(BinaryReplay(), rows)['first_mismatch'] is None
    rows[2][999] ^= 1
    d = replay_comparison(BinaryReplay(), rows)
    assert d['first_mismatch']['step'] == 999
    assert d['steps_checked'] == 1000
    rows[0][700], rows[0][701] = rows[0][701], rows[0][700]
    assert replay_comparison(BinaryReplay(), rows)['first_mismatch']['step'] == 700


@pytest.mark.parametrize('start,n', [((0,0,Q(1,4),Q(1,8)),6), ((0,0,Q(1,2),Q(1,4)),6), ((Q(1,10),Q(-1,7),Q(1,3),Q(1,9)),4)])
def test_binary_exact_target_equals_verlet(start, n):
    t = BinaryReplay(exact=True)
    x,y,vx,vy = map(Q,start)
    regs = t.init(x,y,vx,vy)
    st = (x,y,regs['vhx'],regs['vhy'])
    lab = exact_steps(dict(zip(('x','y','px','py'),map(Q,start))),n)
    for row in lab:
        out = t.step(*st)
        assert tuple(out[k] for k in ('x1','y1','vox','voy')) == tuple(row[k] for k in ('x','y','px','py'))
        st = tuple(out[k] for k in ('x1','y1','vhx1','vhy1'))


def test_nonzero_init_error_is_carried_into_step():
    vals = [0.1,-1/7,1/3,1/9]
    initial = tuple(bits(v) for v in vals)
    t = BinaryReplay()
    init = t.init(*initial)
    b = BinBound(t.init_structure,t.step_structure)
    b.init(init)
    exact = BinaryReplay(exact=True).init(*(Q(v) for v in vals))
    assert any(qval(init[k]) != exact[k] for k in ('vhx','vhy'))
    for k,f in zip(('x','y','vhx','vhy'),b.forms):
        assert abs(qval(init[k])-exact[k]) <= Q(f.rad())
    reg = t.step(initial[0],initial[1],init['vhx'],init['vhy'])
    e = b.step(reg)
    true = BinaryReplay(exact=True).step(Q(vals[0]),Q(vals[1]),exact['vhx'],exact['vhy'])
    assert all(abs(qval(reg[k])-true[k]) <= Q(v) for k,v in zip(('x1','y1','vox','voy'),e))


@pytest.mark.parametrize('orbit', ['regular','chaotic'])
def test_independent_exact_windows(orbit):
    t = BinaryReplay()
    rows = load(orbit+'_forward')
    init = t.init(*(rows[c][0] for c in range(4)))
    st = (rows[0][0],rows[1][0],init['vhx'],init['vhy'])
    assert exact_window(t,st,8)['violations'] == 0


def test_cross_check_uses_exact_sum_and_refuses_nonfinite_or_scale_equality():
    tiny = 2**-54
    a,b = [bits(3.)]*4,[bits(2.)]*4
    e,f = [1.]*4,[tiny]*4
    d = cross_check(a,b,e,f)
    assert d['verdict'] == 'PASS'
    assert d['sum_bounds_q'][0] == str(Q(1)+Q(tiny))
    assert cross_check(a,b,[math.inf]*4,f)['verdict'] == 'REFUSED'
    assert cross_check(a,b,[3.]*4,[0.]*4)['verdict'] == 'REFUSED'
    d = cross_check(a,b,[0.1]*4,[0.1]*4)
    assert d['verdict'] == 'FAIL' and d['raw_enclosure_violations'] == [0,1,2,3]


def test_short_runner_preserves_seals_and_records_actual_scope(tmp_path):
    from run_gate2c import main
    import json
    assert main(['--n','20','--out',str(tmp_path)]) == 0
    r = json.loads((tmp_path/'gate2c_report.json').read_text(encoding='utf-8'))
    d = r['deterministic']
    assert d['gate_verdict'] == 'PASS'
    assert d['scope'] == 'DEVELOPMENT_SHORT_RUN'
    assert d['independent_audit'] == 'NOT_PERFORMED'
    for o in d['orbits'].values():
        assert o['steps_measured'] == 20
        assert o['replay']['first_mismatch'] is None
        assert o['cross']['counts'] == {'PASS':20,'FAIL':0,'REFUSED':0}


def test_output_refuses_exact_scale_equality():
    from lab.gate2c_checks import output_status
    assert output_status([bits(1.)]*4,[1.]*4)[0] == 'REFUSED'
    assert output_status([bits(1.)]*4,[math.inf]*4)[0] == 'REFUSED'
    assert output_status([bits(1.)]*4,None)[0] == 'REFUSED'


def test_finite_cross_sum_outside_float_range_is_refused_without_crash():
    import sys
    d = cross_check([bits(1.)]*4,[bits(1.)]*4,[sys.float_info.max]*4,[sys.float_info.max]*4)
    assert d['verdict'] == 'REFUSED'
    assert d['max_sum_bound'] is None
    assert Q(d['sum_bounds_q'][0]) == 2*Q(sys.float_info.max)


def test_init_nonfinite_forms_are_refused_before_next_step(monkeypatch):
    import lab.gate2c_checks as c
    from lab.v2_bound import Form
    t=BinaryReplay()
    monkeypatch.setattr(c,'rebase',lambda f: ([Form([0.]*4,math.inf) for _ in range(4)],[math.inf]*4))
    b=BinBound(t.init_structure,t.step_structure)
    with pytest.raises(ArithmeticError,match='nonfinite'):
        b.init(t.init(bits(0.),bits(0.),bits(.25),bits(.125)))
    assert b.forms is None


def test_runner_init_fail_stop_has_zero_prefix(monkeypatch):
    import run_gate2c as r
    import time
    def fail(self,regs):
        raise ArithmeticError('injected init fail-stop')
    monkeypatch.setattr(r.BinBound,'init',fail)
    d,_=r.audit_orbit('regular',1,time.perf_counter()+60)
    assert d['first_refused']['step'] == 0
    assert d['certified_prefix'] == 0
    assert d['steps_measured'] == 1


@pytest.mark.parametrize('when',['before','after'])
def test_runner_seal_failure_is_preserved_as_fail_report(monkeypatch,tmp_path,when):
    import run_gate2c as r
    import json
    real=r.verify_seals
    calls=[]
    def check():
        calls.append(1)
        if len(calls)==(1 if when=='before' else 2):
            raise RuntimeError('injected sealed input changed')
        return real()
    monkeypatch.setattr(r,'verify_seals',check)
    assert r.main(['--n','10','--out',str(tmp_path)]) == 1
    d=json.loads((tmp_path/'gate2c_report.json').read_text(encoding='utf-8'))['deterministic']
    assert d['gate_verdict'] == 'FAIL'
    assert d['seal_failures'][0]['phase'] == when
    assert (not d['orbits']) if when=='before' else all(o['steps_measured']==10 for o in d['orbits'].values())


def test_runner_first_refused_prefix_stays_fixed_and_late_mismatch_is_detected(monkeypatch):
    import run_gate2c as r
    import time
    original_load=r.load
    def tampered(name):
        rows=[a[:31] for a in original_load(name)]
        rows[2][25]^=1
        return rows
    monkeypatch.setattr(r,'load',tampered)
    original_status=r.output_status
    calls=[]
    def status(a,e):
        calls.append(1)
        return ('REFUSED','injected scale refusal') if len(calls)==2 else original_status(a,e)
    monkeypatch.setattr(r,'output_status',status)
    d,_=r.audit_orbit('regular',30,time.perf_counter()+60)
    assert d['first_refused']['step']==2
    assert d['certified_prefix']==1
    assert d['replay']['first_mismatch']['step']==25
    assert d['replay']['steps_checked']==30
