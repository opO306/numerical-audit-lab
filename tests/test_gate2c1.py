import importlib
import math
from fractions import Fraction as Q

import pytest

from benchmarks.gate2c1.binary_replay import BinaryReplay, gradient
from lab.gate2c1_checks import BinBound, cross_check, output_status
from benchmarks.gate2a.henon_heiles import bits


def test_gradient_has_instruction_order_and_operands():
    assert [(i.op,i.dst,i.args) for i in gradient('x','y','s')] == [
        ('MUL','xys',('y','x')), ('ADD','axs',('gz','x')),
        ('MUL','xxs',('x','x')), ('ADD','dbls',('xys','xys')),
        ('ADD','gxs',('dbls','axs')), ('MUL','yys',('y','y')),
        ('ADD','ays',('y','gz')), ('SUB','diffs',('xxs','yys')),
        ('ADD','gys',('diffs','ays'))]


@pytest.mark.parametrize('n', ['regular','chaotic'])
def test_short_replay_matches_existing_fixture(n):
    from lab.gate2b_fixture import load
    from lab.gate2c1_checks import replay_comparison
    rows=[r[:101] for r in load(n+'_forward')]
    assert replay_comparison(BinaryReplay(),rows)['first_mismatch'] is None


@pytest.mark.parametrize('bound', [None,[math.inf]*4,[math.nan]*4,[-1.]*4,[1.]*3])
def test_invalid_bound_and_scale_equality_are_refused(bound):
    assert output_status([bits(1.)]*4,bound)[0]=='REFUSED'
    assert output_status([bits(1.)]*4,[1.]*4)[0]=='REFUSED'


def test_cross_violation_is_not_hidden_by_scale_refusal():
    d=cross_check([bits(10.)]*4,[bits(0.)]*4,[0.,20.,20.,20.],[0.]*4)
    assert d['verdict']=='FAIL' and d['raw_enclosure_violations']==[0]


def test_trace_rejects_old_graph_and_modified_literal():
    from benchmarks.gate2c.binary_replay import BinaryReplay as Old
    from benchmarks.gate2c1.binary_replay import assert_machine_structure
    with pytest.raises(ValueError):
        assert_machine_structure(Old().step_structure,'step')
    t=BinaryReplay(); bad=list(t.step_structure)
    bad[0]=('CONST','dt',(),'1/32')
    with pytest.raises(ValueError): assert_machine_structure(bad,'step')


def test_sample_trace_is_one_to_one_with_v2_structure():
    t=BinaryReplay();regs=t.init(*(bits(v) for v in (0.,0.,.25,.125)))
    trace=t.trace('init',regs)
    assert [tuple([r['op'],r['dst'],tuple(r['args']),r['literal']]) for r in trace]==t.init_structure
    assert all(len(r['result_bits'])==16 for r in trace)
    assert [r['machine_address'] for r in trace if r['op']!='CONST']==[
        '1cb85','1cb89','1cb8d','1cb91','1cb95','1cba3','1cba7','1cbac','1cbb0',
        '15941','15993','15997','15993','15997']


def test_init_failure_huge_display_overflow_and_nonfinite_rebase(monkeypatch):
    import sys
    import lab.gate2c1_checks as c
    from lab.v2_bound import Form
    d=c.cross_check([bits(1.)]*4,[bits(1.)]*4,[sys.float_info.max]*4,[sys.float_info.max]*4)
    assert d['verdict']=='REFUSED' and d['max_sum_bound'] is None
    assert Q(d['sum_bounds_q'][0])==2*Q(sys.float_info.max)
    t=BinaryReplay(); b=BinBound(t.init_structure,t.step_structure)
    monkeypatch.setattr(c,'rebase',lambda f:([Form([0.]*4,math.inf) for _ in range(4)],[math.inf]*4))
    with pytest.raises(ArithmeticError): b.init(t.init(*(bits(v) for v in (0.,0.,.25,.125))))
    assert b.forms is None


def test_checkpoint_detects_center_coefficient_and_zero_reset():
    from lab.gate2c1_artifacts import snapshot, assert_segment_connection
    from lab.v2_bound import Form
    import copy
    f=[Form([.01,0.,0.,0.],.001) for _ in range(4)]
    s=snapshot(1000,(1,2,3,4),dict(zip(('x','y','px','py'),(1,2,3,4))),f,f,None,None,None,None)
    assert_segment_connection(s,s,1000)
    for field in ('bin_state','bin_forms'):
        bad=copy.deepcopy(s)
        if field=='bin_state':bad[field][0]='0000000000000000'
        else:bad[field][0]['coefficients'][0]='0000000000000000'
        with pytest.raises(ValueError):assert_segment_connection(s,bad,1000)
    with pytest.raises(ValueError):assert_segment_connection(s,s,999)


def test_runner_init_failure_prefix_zero(monkeypatch):
    import run_gate2c1 as r
    import time
    def failure(self,regs):raise ArithmeticError('injected init failure')
    monkeypatch.setattr(r.BinBound,'init',failure)
    d,_=r.audit_orbit('regular',1,time.perf_counter()+60)
    assert d['certified_prefix']==0 and d['first_refused']['step']==0


@pytest.mark.parametrize('phase',['before','after'])
def test_runner_seal_failure_report_survives(monkeypatch,tmp_path,phase):
    import run_gate2c1 as r
    import json
    real=r.verify_seals;calls=[]
    def verify():
        calls.append(1)
        if len(calls)==(1 if phase=='before' else 2):raise RuntimeError('injected seal change')
        return real()
    monkeypatch.setattr(r,'verify_seals',verify)
    assert r.main(['--n','10','--out',str(tmp_path)])==1
    d=json.loads((tmp_path/'gate2c1_report.json').read_bytes())['deterministic']
    assert d['gate_verdict']=='FAIL' and d['seal_failures'][0]['phase']==phase
    assert not d['orbits'] if phase=='before' else all(v['steps_measured']==10 for v in d['orbits'].values())


def test_first_refusal_sticky_and_late_mismatch(monkeypatch):
    import run_gate2c1 as r
    import time
    real_load=r.load
    def tamper(name):
        rows=[a[:31] for a in real_load(name)];rows[2][25]^=1;return rows
    monkeypatch.setattr(r,'load',tamper)
    real=r.output_status;calls=[]
    def refuse(a,e):
        calls.append(1);return ('REFUSED','injected scale refusal') if len(calls)==2 else real(a,e)
    monkeypatch.setattr(r,'output_status',refuse)
    d,_=r.audit_orbit('regular',30,time.perf_counter()+60)
    assert d['certified_prefix']==1 and d['replay']['first_mismatch']['step']==25


def test_exact_window_saves_output_and_latent():
    from lab.gate2c1_checks import exact_window
    t=BinaryReplay();z=t.init(*(bits(v) for v in (0.,0.,.25,.125)))
    d=exact_window(t,(bits(0.),bits(0.),z['vhx'],z['vhy']),8)
    assert d['violations']==0 and len(d['records'])==8
    assert all(len(row['exact_output'])==len(row['exact_internal'])==4 for row in d['records'])
