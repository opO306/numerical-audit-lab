"""Data-only sealed machine trace contract; never imports an executor."""
import json
from pathlib import Path

def assert_machine_structure(structure,phase):
    p=Path(__file__).resolve().parents[1]/'audit/gate2c1/machine_mapping.json'
    expected=[r['V2_trace'] for r in json.loads(p.read_bytes())['phases'][phase]]
    observed=[[op,dst,list(args),lit] for op,dst,args,lit in structure]
    if observed!=expected:
        raise ValueError('trace differs from sealed machine arithmetic contract')
