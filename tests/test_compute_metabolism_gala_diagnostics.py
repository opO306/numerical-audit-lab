"""Literal callback tests of GDB recorder framing; never import a producer."""
import ast
import copy
from pathlib import Path
import pytest

ROOT=Path(__file__).parents[1]

def recorder():
    tree=ast.parse((ROOT/'compute_metabolism/v0/gdb_gala_observer.py').read_text(encoding='utf-8'))
    definitions=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))]
    ns={'deepcopy':copy.deepcopy}
    exec(compile(ast.Module(body=definitions,type_ignores=[]),'literal-gdb-recorder','exec'),ns)
    return ns

def test_plt_collection_failure_keeps_actual_call_stack_got_and_no_fabricated_post():
    ns=recorder();result={};states=iter([{'registers':{'rsp':0x8008,'rsi':0,'rdx':16}}, {'registers':{'rip':0x6350}}])
    def state():return next(states)
    reads={(0x35689,5):[bytes.fromhex('e8c20cfdff')],(0x6350,6):[bytes.fromhex('ff253aae0300')],(0x8000,8):[b'oldstack',b'newstack'],(0x41190,8):[b'gotbytes']}
    def memory(a,n):return reads[a,n].pop(0)
    with pytest.raises(StopIteration):ns['record_caller'](state,memory,lambda:None,0x35689,0x6350,0x41190,result)
    attempt=result['attempted_caller']
    assert attempt['stack_write']==dict(address=0x8000,size=8,before_hex=b'oldstack'.hex(),after_hex=b'newstack'.hex())
    assert attempt['got_bytes_hex']==b'gotbytes'.hex()
    assert attempt['after_call']=={'registers':{'rip':0x6350}}
    assert attempt['entry'] is None and result['last_after'] is None

def test_later_native_failure_keeps_successful_same_value_store_samples():
    ns=recorder();base=0x700000;codes=((1,'aa'),(2,'bb'))
    ns['PATH']=codes;result={'native':{'steps':[]}};index=[0]
    def state():return {'registers':{'rip':base+codes[index[0]][0]}}
    samples=[dict(address=0x4000,size=1,before_hex='00',after_hex='00',actual_after_hex='00',value_changed=False)]
    def record(pc,code,before,*args):
        if pc==2:raise ValueError('literal RET acquisition failed')
        index[0]=1
        return dict(before=before,after={'registers':{'rip':base+2}},defined_flags_mask=0xffffffff,write_observations=copy.deepcopy(samples))
    ns['record_step']=record
    with pytest.raises(ValueError):ns['record_native'](state,lambda a,n:bytes.fromhex(codes[index[0]][1]),lambda:None,base,result)
    assert result['enabled_write_observations']==samples
    assert len(result['native']['steps'])==1
