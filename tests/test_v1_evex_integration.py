"""Explicit finite-profile dispatch; legacy rows never imply new authority."""
import importlib
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).parents[1]

def test_no_native_marker_keeps_legacy_admission():
    api=importlib.import_module('verified_driver.v1.native_evex_profile')
    assert api.admit_capture({},ROOT) is None

@pytest.mark.parametrize('binding',[{}, {'profile_id':'candidate'},
    {'profile_id':'libc-memset-avx512-evex-16zero-v1','manifest_sha256':'a'*64,'source_binding':'b'*64}])
def test_self_issued_or_unregistered_native_binding_refused(binding):
    api=importlib.import_module('verified_driver.v1.native_evex_profile')
    with pytest.raises(ValueError):api.admit_capture({'native_profile_binding':binding},ROOT)

def test_native_block_preserves_original_form_loop_and_source_rows():
    api=importlib.import_module('verified_driver.v1.native_evex_block')
    import inspect
    text=inspect.getsource(api.block)
    assert 'NativeEvexDataflow' in text and 'verified_spans' in text
    assert "for row in rows[region['start_seq']:region['end_seq']]" in text
    assert 'v2_bound.step_forms' in text and '_verify_frozen' in text

def test_new_raw_dispatch_requires_external_profile(monkeypatch):
    from verified_driver.v1.live_chain import raw
    authority=importlib.import_module('verified_driver.v1.native_evex_profile')
    bridge=importlib.import_module('verified_driver.v1.native_evex_raw')
    doc={'metadata':{'capture':{'native_profile_binding':{'untrusted':'marker'}}}}
    monkeypatch.setattr(raw,'verify_checkpoint',lambda *a,**k:doc)
    calls=[]
    def refuse(*a):calls.append('authority');raise ValueError('no VERIFIED')
    monkeypatch.setattr(authority,'admit_capture',refuse)
    monkeypatch.setattr(bridge,'validate_edge',lambda *a:calls.append('effects'))
    with pytest.raises(ValueError,match='no VERIFIED'):raw.validate_edge(Path('/cp'),None,ROOT)
    assert calls==['authority']


def test_checker_keeps_full_raw_sequence_for_both_init_and_step_regions(tmp_path,monkeypatch):
    # This wiring regression covers the previously truncated init view. ISA,
    # graph and Form semantics have independent real-row tests elsewhere.
    from verified_driver.v1.live_chain import checker as live
    from verified_driver.v1 import native_evex_graph_checker as graph
    rows=[{'seq':i} for i in range(28)]
    regions=[dict(start_seq=0,end_seq=14,occurrence='init'),
        dict(start_seq=14,end_seq=28,occurrence='step1')]
    capture=dict(acquisition_id='fresh',regions=regions)
    native=dict(evex_spans=[dict(start_seq=1,end_seq=14,receipt='bound'),
        dict(start_seq=15,end_seq=28,receipt='bound')])
    doc={'metadata':{'evidence_role':'LIVE'}}
    predecessor=SimpleNamespace(generation=0)
    event=SimpleNamespace(completed_step=1)
    monkeypatch.setattr(live,'validate_edge',lambda *a:(doc,event,capture,rows,native,'checkpoint'))
    (tmp_path/'edge.json').write_bytes(b'bound-edge')
    completion={'edge_sha256':live.digest_bytes(b'bound-edge')}
    completion['completion_sha256']=live.content_id(completion)
    expected={'candidate':'fresh-S1'}
    monkeypatch.setattr(live,'load',lambda path:completion if path.name=='completion.json' else expected)
    monkeypatch.setattr(live,'prior_endpoint',lambda prior:{})
    calls=[]
    def full_graph(cap,actual,selected,root,verified_spans):
        assert actual is rows and [r['seq'] for r in actual]==list(range(28))
        assert verified_spans==[{'start_seq':1,'end_seq':14},{'start_seq':15,'end_seq':28}]
        calls.append(selected[0]['occurrence'])
        return [],[],{}
    monkeypatch.setattr(graph,'graph',full_graph)
    monkeypatch.setattr(live,'boundary',lambda *a:{})
    monkeypatch.setattr(live.audited,'final_lanes',lambda *a:[])
    monkeypatch.setattr(live.audited,'expected_forms',lambda *a:({},{}))
    monkeypatch.setattr(live,'edge_document',lambda *a:expected)
    monkeypatch.setattr(live,'completion',lambda *a:{**completion,'requested_complete':True})
    # Supplied completion must equal the independently reconstructed result.
    completion['requested_complete']=True
    completion['completion_sha256']=live.content_id({k:v for k,v in completion.items() if k!='completion_sha256'})
    result=live.check_edge(tmp_path,tmp_path,predecessor,ROOT)
    assert result['verdict']=='CHECKER_PASS',result
    assert calls==['init','step1']
