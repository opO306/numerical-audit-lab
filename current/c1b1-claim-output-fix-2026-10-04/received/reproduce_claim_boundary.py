#!/usr/bin/env python3
"""Reproduce F-CLAIM-1 without an executor oracle or target serialization helper.

Run with Python 3.12/3.13 at its default integer-string limit (4300 digits):
  python reproduce_claim_boundary.py --source-root PATH_TO_PINNED_REPOSITORY
The bundled verified kernel snapshot is the default source-root.
Exit 0 means the documented defect REPRODUCED, not that the adapter passed.
No global numeric limits or repository files are changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback

SPEC = '3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b'
TARGET_ADAPTER_SHA = '8e8894eb2abc0e1540f516418287b9e576e282c6140d7d83af9523788fd0d85e'

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).parent/'source')
    parser.add_argument('--out', type=Path, default=Path(__file__).parent/'claim_boundary_reproduction.json')
    args = parser.parse_args()
    adapter = args.source_root/'independent_checker/c1b1/claim_adapter.py'
    digest = hashlib.sha256(adapter.read_bytes()).hexdigest()
    if digest != TARGET_ADAPTER_SHA:
        raise SystemExit('Refusing to label a different adapter as the audited target.')
    sys.path.insert(0, str(args.source_root.resolve()))
    from independent_checker.c1b1 import contracts as C, exact_slow as S, exact_fast as F
    from independent_checker.c1b1.claim_adapter import compare_claim

    x = 10**2150
    meta = {'scope':'ARITHMETIC_ONLY', 'j_status':'J_NOT_VERIFIED', 'spec_sha256':SPEC}
    grid = {'width':8, 'frac_bits':0, 'kind':'signed_fx', 'rounding':'nearest_even', 'overflow':'refuse'}
    zero = {'numerator':'0', 'denominator':'1'}
    # A deliberately false but shape-correct external claim. No claimed integer
    # exceeds one digit. Exact drift is positive, though all stored deltas are 0.
    claim_value = {'type':'DriftResult',
        'displacement':[dict(zero) for _ in range(6)],
        'endpoint':[dict(zero) for _ in range(6)],
        'delta_i':['0']*3, 'delta_j':['0']*3, 'r_i':['0']*3, 'r_j':['0']*3,
        'checked_order':['i.x','i.y','i.z','j.x','j.y','j.z'], **meta}
    payload = {'schema':'LAB_C1B1_CLAIM_V1', **meta,
        'acquisition_id':'independent', 'record_id':'large-canonical-input',
        'phase_id':'drift', 'operation':'drift',
        'input':{'position_grid':grid, 'momentum_grid':grid,
            'r_i':['0']*3, 'r_j':['0']*3, 'p_i':['1','0','0'], 'p_j':['0']*3,
            'mass_i':{'numerator':str(x+3),'denominator':'1'},
            'mass_j':{'numerator':'1','denominator':'1'},
            'dt':{'numerator':'1','denominator':str(x+1)}},
        'claim':{'type':'Outcome','value':claim_value,'exception_type':'',
                 'scope':meta['scope'],'j_status':meta['j_status']}}
    text = json.dumps(payload, separators=(',', ':'))
    assert len(text.encode()) < 1048576
    assert len(payload['input']['mass_i']['numerator']) == 2151 < 4096
    assert len(payload['input']['dt']['denominator']) == 2151 < 4096
    # The result's denominator has 4301 digits, proved without decimal conversion.
    denominator = (x+1)*(x+3)
    assert 10**4300 <= denominator < 10**4301
    request = C.DriftInput(C.Grid(8,0), C.Grid(8,0), (0,0,0), (0,0,0),
        (1,0,0), (0,0,0), C.Ratio(x+3,1), C.Ratio(1,1), C.Ratio(1,x+1))
    rows = []
    for path, module in [('exact_slow',S), ('exact_fast',F)]:
        result = module.drift(request)
        d = result.displacement[0]
        assert d.numerator*denominator == d.denominator
        assert result.delta_i == result.r_i == (0,0,0)
        observation = {'path':path, 'kernel_exact_result_correct':True}
        try:
            answer = compare_claim(text, path, opt_in=(path == 'exact_fast'))
            observation.update(status=answer.status, exception=None)
        except Exception as exc:
            observation.update(exception=type(exc).__name__,
                is_LabRefusal=isinstance(exc,C.LabRefusal), message=str(exc),
                traceback=traceback.format_exc())
        rows.append(observation)
    reproduced = all(row.get('exception') == 'ValueError' and
                     row.get('is_LabRefusal') is False for row in rows)
    report = {'target':'f806d8ce1ef86a0948b1a8abafe1a22c3058178b',
        'finding':'F-CLAIM-1', 'reproduction':'REPRODUCED' if reproduced else 'NOT_REPRODUCED',
        'python':sys.version, 'int_max_str_digits':sys.get_int_max_str_digits(),
        'input_integer_digits':2151, 'exact_denominator_digits':4301,
        'wire_bytes':len(text.encode()), 'observations':rows,
        'note':'Reproduction success is an adapter FAIL, not a mathematical kernel failure.'}
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if reproduced else 2

if __name__ == '__main__':
    raise SystemExit(main())
