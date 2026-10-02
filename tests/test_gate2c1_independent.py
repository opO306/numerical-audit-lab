import ast
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'audit/gate2c1/independent/checker.py'
spec=importlib.util.spec_from_file_location('gate2c1_independent',PATH)
ind=importlib.util.module_from_spec(spec);spec.loader.exec_module(ind)

def test_independent_imports_only_accepted_operator():
    for node in ast.walk(ast.parse(PATH.read_text())):
        if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith(('lab','benchmarks','numeric_core')):
            assert node.module=='lab.v2_bound'

def test_all_intermediates_recomputed_by_separate_executor():
    from benchmarks.gate2c1.binary_replay import BinaryReplay
    from lab.gate2b_fixture import load
    t=BinaryReplay();rows=load('regular_forward')
    args=[rows[c][0] for c in range(4)]
    a=t.init(*args);b=ind.run_struct(ind.INIT,dict(zip(('x','y','vx','vy'),args)))
    assert a==b
    st=(args[0],args[1],a['vhx'],a['vhy'])
    for _ in range(100):
        a=t.step(*st);b=ind.run_struct(ind.STEP,dict(zip(ind.STATE,st)))
        assert a==b
        st=tuple(a[k] for k in ind.LAT)

def test_independent_connection_rejects_zero_reset_and_gap():
    end={'step':1000,'bin_forms':[{'box':'.1'}]}
    ind.check_link(end,end,1000)
    with pytest.raises(ValueError):ind.check_link(end,{'step':1000,'bin_forms':[{'box':'0'}]},1000)
    with pytest.raises(ValueError):ind.check_link(end,end,999)

def test_trace_opcode_and_value_mutants_rejected(tmp_path):
    import json
    from benchmarks.gate2c1.binary_replay import BinaryReplay
    t=BinaryReplay();regs=t.init(*(ind.bits(v) for v in (0.,0.,.25,.125)))
    records=t.trace('init',regs);p=tmp_path/'trace.json'
    def dump():p.write_text(json.dumps({'phase':'init','v2_input_forms':ind.bf(ind.zero_forms()),'operations':records}))
    dump();ind.compare_trace(p,ind.INIT,regs)
    records[3]['op']='ADD';dump()
    with pytest.raises(ValueError):ind.compare_trace(p,ind.INIT,regs)
    records=t.trace('init',regs);records[4]['result_bits']='3ff0000000000000'
    dump()
    with pytest.raises(ValueError):ind.compare_trace(p,ind.INIT,regs)
