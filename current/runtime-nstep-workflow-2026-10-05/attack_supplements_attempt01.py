"""All identity rebindings repaired; assert the targeted semantic gate, never collateral IR IDs."""
import ast
import copy
import json
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
BASE = ROOT / 'runtime_trace/regular_nstep/artifacts/connected10-final2'
OUT = ROOT / 'runtime_trace/regular_nstep/artifacts/attack-supplements'
OUT.mkdir(exist_ok=False)
from runtime_trace.regular_nstep import checker
from runtime_trace.regular_2step.schema import load
tree = ast.parse(Path(__file__).with_name('attack_matrix.py').read_text())
helpers = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
exec(compile(ast.Module(body=helpers, type_ignores=[]), 'reviewed-attack-helpers', 'exec'))

def rebound(value, old, new):
    if isinstance(value, str): return value.replace(old, new)
    if isinstance(value, list): return [rebound(v, old, new) for v in value]
    if isinstance(value, dict): return {k: rebound(v, old, new) for k, v in value.items()}
    return value

results = []
for name, expected_stage, expected_reason in [
    ('wrong-result-full-rebind', 'SEMANTIC', 'scalar result rounding / operand mutation'),
    ('wrong-source-operand-full-rebind', 'SEMANTIC', 'record operand vs pre raw register'),
    ('wrong-copy-result-full-rebind', 'SEMANTIC', 'post destination bits'),
    ('actual-post-result', 'ACQUISITION', 'exact IEEE-754 result mismatch')]:
    began = time.perf_counter()
    case = OUT / name
    copy_inputs(case)
    cap = load(case / 'capture/capture.json')
    old_id = cap['acquisition_id']
    rows = [json.loads(line) for line in (case / 'capture/trace.jsonl').read_bytes().splitlines()]
    row = next(r for r in rows if r['occurrence'] == 'step2' and r.get('kind') == 'MUL')
    if name.startswith('wrong-result'):
        row['result_bits'] = '0x3ff0000000000000'
    elif name.startswith('wrong-source'):
        row['operands'][0]['raw_bits'] = f"0x{int(row['operands'][0]['raw_bits'],16)^1:016x}"
    elif name.startswith('wrong-copy'):
        row = next(r for r in rows if r['occurrence'] == 'step2' and r.get('kind') == 'MOVE'
            and r['operands'][-1].get('register','').startswith('xmm') and r['operands'][-1]['width'] == 8)
        row['result_bits'] = f"0x{int(row['result_bits'],16)^1:016x}"
    else:
        register = row['operands'][1]['register']
        changed = f"0x{(int(row['post']['xmm'][register],16)&~((1<<64)-1))|0x3ff0000000000000:032x}"
        row['post']['xmm'][register] = changed
        row['result_bits'] = '0x3ff0000000000000'
        for following in rows[row['seq']+1:]:
            original_pre = following['pre']['xmm'][register]
            following['pre']['xmm'][register] = changed
            if original_pre != following['post']['xmm'][register]: break
            following['post']['xmm'][register] = changed
    resign_raw(case, cap, rows)
    del rows
    new_id = load(case / 'capture/capture.json')['acquisition_id']
    for filename in ('blocks.json','native_report.json','completion.json'):
        path = case / 'derived' / filename
        put(path, rebound(load(path), old_id, new_id))
    repin_derived(case)
    report = checker.check(case / 'capture', case / 'derived', ROOT)
    assert report['verdict'] == 'REFUSED' and report['requested_complete'] is False, name
    assert report['failure_stage'] == expected_stage, (name, report)
    assert report['reason'] == expected_reason, (name, report)
    result = {'attack':name,'outer_hashes_repaired':True,'derived_dynamic_identity_rebound':True,
        'targeted_gate_confirmed':True,'category':'SEMANTIC','wall_seconds':time.perf_counter()-began,'report':report}
    put(case / 'attack_result.json', result)
    results.append(result)
    print(json.dumps(result), flush=True)
first = load(ROOT / 'runtime_trace/regular_nstep/artifacts/attack-matrix-01/matrix_report.json')
valid = [r for r in first['attacks'] if r['attack'] != 'wrong-result']
raw = {'missing-dense','duplicate-dense','reorder-dense','body-write-omission','body-read-omission',
    'body-callee-saved','terminal-save-pointer','cross-process','all-stop-off','wrong-gradient',
    'unsupported-opcode','missing-normal-exit'}
for result in valid:
    stage = 'ACQUISITION' if result['attack'] in raw else 'SEMANTIC'
    if result['category'] == 'SEMANTIC':
        assert result['report']['failure_stage'] == stage
        assert result['report']['reason'] not in ('component integrity','raw hash','complete reviewed source set')
put(OUT / 'final_attack_report.json', {'verdict':'TARGETED_ATTACK_SUITE_PASS',
    'semantic_count':22,'control_count':2,'attacks':valid+results,
    'excluded_collateral_case':'attack-matrix-01/wrong-result retained, replaced by full-rebind actual RNE gate test'})
