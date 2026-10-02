import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_plan_and_method_preceded_implementation_and_preserve_old_bytes():
    p=ROOT/'audit/gate2c1/plan_seal.json'
    assert hashlib.sha256(p.read_bytes()).hexdigest()=='d61dbaf1ab438ca2ac542e784edbb4b9656c4614cdf05116fdaedc56df783743'
    plan=json.loads(p.read_bytes())
    assert not any(plan['implementation_files_present_at_seal'].values())
    for path,h in {**plan['files'],**plan['preserve_prior_raw_files']}.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
    method=json.loads((ROOT/'audit/gate2c1/method_seal.json').read_bytes())
    assert method['gate2c1_horizon_or_cross_measured'] is False
    for path,h in method['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path


def test_three_layer_mapping_binds_every_arithmetic_occurrence():
    from benchmarks.gate2c1.binary_replay import BinaryReplay,addresses
    t=BinaryReplay();d=json.loads((ROOT/'audit/gate2c1/machine_mapping.json').read_bytes())
    evidence=(ROOT/'benchmarks/gate2b/evidence/disassembly.txt').read_text()
    for phase,S in [('init',t.init_structure),('step',t.step_structure)]:
        rows=d['phases'][phase]
        assert len(rows)==len(S)
        for row,s,a in zip(rows,S,addresses(phase)):
            expected=[s[0],s[1],list(s[2]),s[3]]
            assert row['T_bin']==row['V2_trace']==expected
            if a:assert a+':' in evidence and row['disassembly_address']==a


def test_original_wheel_and_both_so_bytes_present_and_hash_bound():
    import zipfile
    vendor=ROOT/'audit/gate2c1/vendor';w=next(vendor.glob('*.whl'))
    assert hashlib.sha256(w.read_bytes()).hexdigest()=='cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0'
    manifest=json.loads((ROOT/'benchmarks/gate2b/fixtures/cloud-2026-10-01/manifest.json').read_bytes())
    with zipfile.ZipFile(w) as z:
        for p in ['gala/potential/potential/builtin/cybuiltin.cpython-312-x86_64-linux-gnu.so','gala/integrate/cyintegrators/leapfrog.cpython-312-x86_64-linux-gnu.so']:
            b=(vendor/p).read_bytes()
            assert b==z.read(p)
            assert hashlib.sha256(b).hexdigest()==manifest['distribution_files_sha256'][p]
