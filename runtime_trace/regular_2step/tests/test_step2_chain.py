"""Real captured two-step numerical regressions; no synthetic successful chain."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'runtime_trace/regular_2step'


def test_chain_implementation_exists():
    for name in ('producer', 'checker', 'form_oracle'):
        assert importlib.util.find_spec(f'runtime_trace.regular_2step.{name}'), name


@pytest.fixture(scope='module', params=['known-03', 'fresh-03'])
def built(request, tmp_path_factory):
    from runtime_trace.regular_2step.producer import build
    capture = PACKAGE / 'artifacts' / request.param
    out = tmp_path_factory.mktemp(request.param) / 'derived'
    build(capture, out, ROOT)
    return capture, out


def test_real_chain_and_carried_forms(built):
    from runtime_trace.regular_2step.checker import check
    capture, out = built
    report = check(capture, out, ROOT)
    assert report['verdict'] == 'CHECKER_PASS'
    ir = json.loads((out / 'numeric_ir.json').read_bytes())
    v2 = json.loads((out / 'v2_correspondence.json').read_bytes())
    chain = json.loads((out / 'chain.json').read_bytes())
    assert chain['schema'] == 'REGULAR_2STEP_CHAIN_V1'
    assert len(ir['operations']) == len(v2['operations']) > 0
    assert len(chain['intermediate_boundary']['carry']) == 6
    states = {s['state_id']: s for s in v2['state_bindings']}
    for carry in chain['intermediate_boundary']['carry']:
        state = states[carry['entry_state_id']]
        assert state['form'] == carry['form']
        assert float.fromhex(state['form']['box']) > 0
        assert state['source_state_id'] == carry['audited_endpoint']['form_source_state_id']
    for state in states.values():
        if state['binding_kind'] == 'LOAD':
            assert state['form']['box'] == '0x0.0p+0'
    assert all(v['value_id'].startswith(ir['namespace'] + '/') for v in ir['values'])
    assert chain['intermediate_boundary']['time']['schedule_index'] == 2
    assert chain['audit_status'] == 'INDEPENDENT AUDIT PENDING'


def test_frozen_protocol_receipt(built):
    _, out = built
    v2 = json.loads((out / 'v2_correspondence.json').read_bytes())
    assert v2.get('frozen_v2', {}).get('lf_sha256') == '48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780'


def test_prefix_heap_bijection_preserves_partial_aliases():
    import copy
    from runtime_trace.regular_2step.checker import prefix_structure, module_operand
    capture = json.loads((PACKAGE / 'artifacts/known-03/capture.json').read_bytes())
    rows = [json.loads(line) for line in (PACKAGE / 'artifacts/known-03/trace.jsonl').read_bytes().splitlines()]
    region = capture['regions'][0]
    original = rows[region['start_seq']:region['end_seq']]
    moved = copy.deepcopy(original)
    # Known routing structure at 0x4(%rdi) and (%rdi) partially shares bytes
    # with later 8-byte reads; renaming every observed heap byte consistently
    # preserves structure, changing only one occurrence must break it.
    from runtime_trace.regular_2step.structure import _memory_role
    for row in moved:
        for op in row['operands']:
            if op['kind'] == 'memory' and module_operand(op['address'], op['width'], capture['modules']) is None and _memory_role(op['address'], op['width'], row, region)[0] == 'other':
                op['address'] += 1000000000
                if row['kind'] == 'CONTROL':
                    row['pre']['gpr']['rax'] = hex(int(row['pre']['gpr']['rax'], 16) + 1000000000)
    assert prefix_structure(original, region, capture['modules']) == prefix_structure(moved, region, capture['modules'])
    moved[67]['operands'][0]['address'] += 1
    assert prefix_structure(original, region, capture['modules']) != prefix_structure(moved, region, capture['modules'])


def test_prefix_constant_retains_elf_role():
    from runtime_trace.regular_2step.checker import prefix_structure, module_operand
    capture = json.loads((PACKAGE / 'artifacts/known-03/capture.json').read_bytes())
    rows = [json.loads(line) for line in (PACKAGE / 'artifacts/known-03/trace.jsonl').read_bytes().splitlines()]
    region = capture['regions'][0]
    signature = prefix_structure(rows[region['start_seq']:region['end_seq']], region, capture['modules'])
    assert signature['topology'][139][0][1] == ['elf-constant',
        'a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc', 242528, 8, 242528]


def test_malformed_derived_refused(built, tmp_path):
    import shutil
    from runtime_trace.regular_2step.checker import check
    capture, out = built
    copied = tmp_path / 'bad'
    shutil.copytree(out, copied)
    (copied / 'chain.json').write_text('{"schema": 1, "schema": 2}')
    result = check(capture, copied, ROOT)
    assert result['verdict'] == 'REFUSED'


def test_repaired_boolean_operation_index_is_refused(built, tmp_path):
    import shutil
    from runtime_trace.regular_2step.checker import check
    from runtime_trace.regular_2step.schema import load, write, component_hashes, completion
    capture, out = built
    copied = tmp_path / 'boolean-index'
    shutil.copytree(out, copied)
    ir = load(copied / 'numeric_ir.json')
    ir['operations'][1]['ir_sequence'] = True
    write(copied / 'numeric_ir.json', ir)
    chain = load(copied / 'chain.json')
    hashes = component_hashes(copied)
    chain['ordered_component_hashes'] = hashes
    chain['identities'][3].update(hashes[0])
    chain['completion_sha256'] = completion(chain)
    write(copied / 'chain.json', chain)
    result = check(capture, copied, ROOT)
    assert result['verdict'] == 'REFUSED'
    assert result['stage'] == 'SEMANTIC'


def test_exact_ieee_rounding_and_nonzero_symbolic_form():
    from runtime_trace.regular_2step.form_oracle import oracle, check_ieee
    from lab import v2_bound
    o = oracle(ROOT)
    bits = ('0x3ff0000000000000', '0x3ca0000000000000', '0x3ff0000000000000')
    check_ieee('ADD_BINARY64', *bits)
    with pytest.raises(ValueError):
        check_ieee('ADD_BINARY64', bits[0], bits[1], '0x3ff0000000000001')
    for kind in ('ADD', 'SUB', 'MUL'):
        x, y = '0x3ff0000000000000', '0x4000000000000000'
        z = {'ADD': '0x4008000000000000', 'SUB': '0xbff0000000000000', 'MUL': y}[kind]
        a, b = [0.125, -0.25, 0.0, 0.5], [-0.125, 0.0, 0.25, 0.0]
        independent = o.compute_form(kind + '_BINARY64', z, x, y, o.Form(a, .01), o.Form(b, .02))
        frozen = v2_bound.step_forms([(kind, 'z', ['x', 'y'], None)],
            {'x': int(x, 16), 'y': int(y, 16), 'z': int(z, 16)},
            {'x': v2_bound.Form(a, .01), 'y': v2_bound.Form(b, .02)})['z']
        assert o.fdoc(independent) == o.fdoc(frozen)


def test_actual_module_data_reads_keep_rva():
    from runtime_trace.regular_2step.checker import prefix_structure, module_operand
    capture = json.loads((PACKAGE / 'artifacts/known-03/capture.json').read_bytes())
    rows = [json.loads(line) for line in (PACKAGE / 'artifacts/known-03/trace.jsonl').read_bytes().splitlines()]
    for seq, rva in ((16, 0x413c8), (51, 0x41190), (261, 0x413c8), (296, 0x41190)):
        region = capture['regions'][0 if seq < 200 else 1]
        operand = prefix_structure([rows[seq]], region, capture['modules'])['topology'][0][0]
        assert operand == ['read', ['module', rows[seq]['module_sha256'], rva, 8]]


def test_changed_control_memory_ea_refused():
    from runtime_trace.regular_2step.checker import prefix_structure, module_operand
    capture = json.loads((PACKAGE / 'artifacts/known-03/capture.json').read_bytes())
    rows = [json.loads(line) for line in (PACKAGE / 'artifacts/known-03/trace.jsonl').read_bytes().splitlines()]
    rows[16]['operands'][0]['address'] += 8
    with pytest.raises(ValueError, match='CONTROL effective address'):
        prefix_structure([rows[16]], capture['regions'][0], capture['modules'])


def test_module_operand_relocation_and_rejections():
    import copy
    from runtime_trace.regular_2step.checker import module_operand, prefix_structure
    capture = json.loads((PACKAGE / 'artifacts/known-03/capture.json').read_bytes())
    rows = [json.loads(line) for line in (PACKAGE / 'artifacts/known-03/trace.jsonl').read_bytes().splitlines()]
    row, modules, region = rows[16], capture['modules'], capture['regions'][0]
    moved, relocated = copy.deepcopy(row), copy.deepcopy(modules)
    delta = 0x100000000
    relocated[row['module_path']]['load_base'] += delta
    for key in ('runtime_pc', 'module_load_base', 'post_pc'):
        moved[key] += delta
    moved['pre']['gpr']['rip'] = hex(moved['runtime_pc'])
    moved['operands'][0]['address'] += delta
    assert prefix_structure([row], region, modules) == prefix_structure([moved], region, relocated)
    # A coherent changed displacement/address preserves EA but not module RVA.
    moved = copy.deepcopy(row)
    code = bytes.fromhex(moved['bytes'])
    moved['bytes'] = (code[:2] + (int.from_bytes(code[2:], 'little', signed=True) + 8).to_bytes(4, 'little', signed=True)).hex()
    moved['operands'][0]['address'] += 8
    assert prefix_structure([row], region, modules)['topology'] != prefix_structure([moved], region, modules)['topology']
    address = row['operands'][0]['address']
    ambiguous = copy.deepcopy(modules)
    ambiguous['duplicate'] = copy.deepcopy(modules[row['module_path']])
    with pytest.raises(ValueError, match='ambiguous or cross-boundary'):
        module_operand(address, 8, ambiguous)
    module = modules[row['module_path']]
    segment = next(s for s in module['segments'] if s['flags'] == 6)
    with pytest.raises(ValueError, match='ambiguous or cross-boundary'):
        module_operand(module['load_base'] + segment['vaddr'] + segment['memsz'] - 4, 8, modules)


@pytest.mark.parametrize('seq', [16, 90, 62])
def test_closed_control_memory_forms(seq):
    import copy
    from runtime_trace.regular_2step.checker import check_control_ea
    rows = [json.loads(line) for line in (PACKAGE / 'artifacts/known-03/trace.jsonl').read_bytes().splitlines()]
    row = rows[seq]
    check_control_ea(row)
    for field, value in [('address', row['operands'][0]['address'] + 1), ('width', 4), ('access', 'write')]:
        changed = copy.deepcopy(row)
        changed['operands'][0][field] = value
        with pytest.raises(ValueError, match='CONTROL effective address'):
            check_control_ea(changed)
    changed = copy.deepcopy(row)
    changed['bytes'] = 'ff10'
    with pytest.raises(ValueError, match='unsupported CONTROL memory encoding'):
        check_control_ea(changed)
