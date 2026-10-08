"""Hand-derived raw native span and byte-storage graph producer tests."""
import copy
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x700000000000
LIBC = '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'
STEPS = [(0x1996c0, 'f30f1efa', 'endbr64', 'ROUTING'),
    (0x1996c4, '62e27d287ac6', 'vpbroadcastb', 'ZERO_FILL'),
    (0x1996ca, '4889f8', 'mov', 'ROUTING'),
    (0x1996cd, '4883fa20', 'cmp', 'ROUTING'),
    (0x1996d1, '722d', 'jb', 'CONTROL'),
    (0x199700, '81e7ff0f0000', 'and', 'ROUTING'),
    (0x199706, '81ffe00f0000', 'cmp', 'ROUTING'),
    (0x19970c, '0f87ae000000', 'ja', 'CONTROL'),
    (0x199712, 'b9ffffffff', 'mov', 'ROUTING'),
    (0x199717, 'c4e268f5c9', 'bzhi', 'ROUTING'),
    (0x19971c, 'c5fb92c9', 'kmovd', 'ROUTING'),
    (0x199720, '62e17f297f00', 'vmovdqu8', 'MOVE'),
    (0x199726, 'c3', 'ret', 'CONTROL')]


def bridge():
    try:
        return importlib.import_module('verified_driver.v1.native_evex_graph_producer')
    except ModuleNotFoundError:
        pytest.fail('native storage graph producer bridge is not implemented')


def hx(data):
    return '0x' + bytes(data)[::-1].hex()


def full_state():
    gpr = ['rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp'] + [f'r{i}' for i in range(8, 16)]
    regs = {name: 0 for name in gpr}
    regs.update(rip=BASE + 0x1996c0, rdi=0x20000, rdx=16, rsp=0x900000,
        eflags=0x202, mxcsr=0x1f80, fs_base=0, gs_base=0)
    regs.update({f'k{i}': 0 for i in range(8)})
    regs.update(cs=0x33, ss=0x2b, ds=0, es=0, fs=0, gs=0)
    fp = {name: 0 for name in ['fctrl', 'fstat', 'ftag', 'fiseg', 'fioff', 'foseg', 'fooff', 'fop']}
    fp.update({f'st{i}': '00' * 10 for i in range(8)})
    return dict(registers=regs,
        vectors={f'zmm{i}': ('a5' if i == 16 else '00') * 64 for i in range(32)},
        fpu=fp, control=dict(cet_ibt=False, cet_shstk=False), unavailable=[])


def project(state):
    regs = state['registers']
    return dict(gpr={name: f'0x{value:016x}' for name, value in regs.items()
                    if name in {'rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp', 'rip'}
                    or name.startswith('r') and name[1:].isdigit()},
        xmm={f'xmm{i}': hx(bytes.fromhex(state['vectors'][f'zmm{i}'])[:16]) for i in range(16)},
        extra_vectors={'ymm16': hx(bytes.fromhex(state['vectors']['zmm16'])[:32])},
        segment_bases={name: f'0x{regs[name]:016x}' for name in ['fs_base', 'gs_base']},
        mxcsr=regs['mxcsr'], eflags=regs['eflags'])


def fixture():
    """Fixed 16-byte zero fill. Effects/flags are literals, never model output."""
    rows = []
    context = full_state()
    for seq, (pc, code, opcode, kind) in enumerate(STEPS):
        before = copy.deepcopy(context)
        after = copy.deepcopy(context)
        regs = after['registers']
        regs['rip'] = BASE + (STEPS[seq + 1][0] if seq < 12 else 0x1234)
        if seq == 1:
            after['vectors']['zmm16'] = '00' * 64
        if seq == 2:
            regs['rax'] = 0x20000
        if seq == 3:
            regs['eflags'] = 0x287  # 16-32=-16: SF/PF/CF, no nibble borrow.
        if seq == 5:
            regs.update(rdi=0, eflags=0x246)
        if seq == 6:
            regs['eflags'] = 0x283  # 0-0xfe0: low byte20 odd parity, CF/SF.
        if seq == 8:
            regs['rcx'] = 0xffffffff
        if seq == 9:
            regs.update(rcx=0xffff, eflags=0x202)
        if seq == 10:
            regs['k1'] = 0xffff
        if seq == 12:
            regs['rip'] = 0x1234
            regs['rsp'] = 0x900008
        reads = [dict(address=0x900000, size=8, bytes_hex='3412000000000000')] if seq == 12 else []
        writes = [dict(address=0x20000 + i, size=1, after_hex='00') for i in range(16)] if seq == 11 else []
        oldwrites = [dict(address=w['address'], size=1, before_hex='00', after_hex='00',
                          value_changed=False) for w in writes]
        obs = [dict(**reads[0], kind='IMPLICIT_RET', operand='(%rsp)',
                    status='OK', timing='PRE_INSTRUCTION')] if reads else []
        operands = []
        result = None
        if seq == 1:
            operands = [dict(kind='register', register='esi', width=1, raw_bits='0x00'),
                dict(kind='register', register='ymm16', width=32, raw_bits='0x' + 'a5' * 32)]
            result = '0x' + '00' * 32
        if seq == 11:
            operands = [dict(kind='register', register='ymm16', width=16, raw_bits='0x' + '00' * 16),
                dict(kind='memory', address=0x20000, width=16, raw_bits='0x' + '00' * 16)]
            result = '0x' + '00' * 16
        rows.append(dict(seq=seq, phase='init', occurrence='init', step=0,
            elf_address=pc, bytes=code, instruction_bytes=code, opcode=opcode, kind=kind,
            runtime_pc=BASE + pc, post_pc=regs['rip'], module_load_base=BASE,
            module_sha256=LIBC, module_path='/lib/libc.so.6', operands=operands,
            result_bits=result, pre=project(before), post=project(after),
            native_evex=dict(before=before, after=after, reads=reads, writes=writes),
            possible_memory_writes=oldwrites, pre_memory_observations=obs))
        context = after
    boundary = {name: ['0x0000000000000000'] * 2 for name in ['q', 'full_v', 'latent', 'gradient']}
    region = dict(occurrence='init', start_seq=0, end_seq=13, start_state=copy.deepcopy(boundary),
        end_state=copy.deepcopy(boundary), pointers=dict(q=0x10000, full_v=0x10020,
        latent=0x10040, gradient=0x20000))
    capture = dict(acquisition_id='test-native-actual-rows', regions=[region],
        modules={'/lib/libc.so.6': dict(sha256=LIBC, load_base=BASE)})
    return capture, rows, region


def build(capture, rows, region, spans=None):
    return bridge().build_ir(capture, rows, region, ROOT,
        verified_spans=[dict(start_seq=0, end_seq=13)] if spans is None else spans)


def test_actual_native_zero32_copy16_source_sequence_and_complete_raw_binding():
    capture, rows, region = fixture()
    frozen = copy.deepcopy((capture, rows, region))
    ops, values, terminal = build(capture, rows, region)
    assert ops == []
    zero = next(value for value in values if value['value_id'] == 'v:r1:zero')
    copyvalue = next(value for value in values if value['value_id'] == 'v:r11:copy')
    assert zero == dict(value_id='v:r1:zero', producer_kind='ZERO_BITS', width=32,
        raw_bits='0x' + '00' * 32,
        producer=dict(role='zero_result', trace_sequence=1, operand_index=1, phase='init'),
        storage=dict(space='register', name='v16', byte_offset=0, width=32), source_slices=[])
    assert copyvalue['producer_kind'] == 'COPY_BITS'
    assert copyvalue['raw_bits'] == '0x' + '00' * 16
    assert copyvalue['width'] == 16
    assert copyvalue['storage'] == dict(space='buffer', name='gradient', byte_offset=0, width=16)
    assert copyvalue['source_slices'] == [dict(value_id='v:r1:zero', source_offset=0,
        destination_offset=0, width=16, trace_sequence=11, source_operand_index=0,
        source_storage=dict(space='register', name='v16', byte_offset=0, width=16),
        destination_storage=dict(space='buffer', name='gradient', byte_offset=0, width=16))]
    assert [(ref.value_id, ref.offset) for ref in terminal['gradient']] == [
        ('v:r11:copy', i) for i in range(16)]
    assert (capture, rows, region) == frozen
    flow = bridge().NativeEvexDataflow(rows, capture, ROOT,
        verified_spans=[dict(start_seq=0, end_seq=13)])
    receipt = flow.native_receipts[0]
    import hashlib
    expected_digest = hashlib.sha256(json.dumps(rows, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    assert receipt == dict(start_seq=0, end_seq=13, raw_span_sha256=expected_digest,
                          instruction_count=13, read_count=1, write_count=16)


def test_changed_gpr_provenance_is_invalidated_without_inventing_numeric_values():
    capture, rows, region = fixture()
    flow = bridge().NativeEvexDataflow(rows, capture, ROOT,
        verified_spans=[dict(start_seq=0, end_seq=13)])
    from runtime_trace.numeric_ir.translator import _ByteRef
    for name, seq in [('rax', 2), ('rdi', 5), ('rcx', 8), ('rcx', 9), ('rsp', 12)]:
        flow.state = {('r', name, i): _ByteRef('previous', i, 'old') for i in range(8)}
        flow.process_record(rows[seq])
        assert not any(('r', name, i) in flow.state for i in range(8))
    assert flow.values == []


def test_surrounding_unchanged_flow_copies_and_scalar_operation_keep_actual_provenance():
    capture, rows, region = fixture()
    pre = copy.deepcopy(rows[-1]['post'])
    post = copy.deepcopy(pre)
    source = dict(kind='memory', address=0x20000, width=8, raw_bits='0x0000000000000000',
                  origins=['record:11'] * 8)
    dest = dict(kind='register', register='xmm2', width=8, raw_bits='0x0000000000000000',
                origins=['untracked'] * 8)
    rows.append(dict(seq=13, phase='init', occurrence='init', step=0, kind='MOVE', opcode='movsd',
        operands=[source, dest], result_bits='0x0000000000000000', pre=pre, post=post))
    rows.append(dict(seq=14, phase='init', occurrence='init', step=0, kind='ADD', opcode='addsd',
        operands=[dict(kind='register', register='xmm2', width=8,
            raw_bits='0x0000000000000000', origins=['record:13'] * 8),
            dict(kind='register', register='xmm0', width=8, raw_bits='0x0000000000000000',
            origins=[f'boundary:init:xmm0:{i}' for i in range(8)])],
        result_bits='0x0000000000000000', pre=post, post=copy.deepcopy(post),
        module_sha256='a' * 64, elf_address=0x1234, bytes='f20f58c2'))
    region['end_seq'] = 15
    ops, values, _ = build(capture, rows, region)
    assert len(ops) == 1
    assert ops[0]['trace_sequence'] == 14
    assert ops[0]['instruction_bytes'] == 'f20f58c2'
    copied = next(value for value in values if value['value_id'] == 'v:r13:copy')
    assert copied['source_slices'][0]['value_id'] == 'v:r11:copy'


def test_undefined_flags_are_not_falsely_preserved():
    capture, rows, region = fixture()
    rows[9]['native_evex']['after']['registers']['eflags'] |= 0x14
    for seq in range(10, 13):
        rows[seq]['native_evex']['before']['registers']['eflags'] |= 0x14
        rows[seq]['native_evex']['after']['registers']['eflags'] |= 0x14
    for seq in range(9, 13):
        rows[seq]['pre'] = project(rows[seq]['native_evex']['before'])
        rows[seq]['post'] = project(rows[seq]['native_evex']['after'])
    assert build(capture, rows, region)[0] == []


def mutate(rows, attack):
    if attack == 'code': rows[1]['bytes'] = '62e27d287ac7'
    if attack == 'missing_same_value': rows[11]['possible_memory_writes'].pop()
    if attack == 'outside_write': rows[11]['possible_memory_writes'].append(dict(address=0x20010,size=1,before_hex='00',after_hex='00',value_changed=False))
    if attack == 'sidecar_missing_write': rows[11]['native_evex']['writes'].pop()
    if attack == 'mask': rows[11]['native_evex']['before']['registers']['k1'] = 0xfffe
    if attack == 'width': rows[11]['operands'][1]['width'] = 32
    if attack == 'fill': rows[1]['native_evex']['before']['registers']['rsi'] = 1
    if attack == 'fp': rows[1]['native_evex']['after']['fpu']['st7'] = '01' * 10
    if attack == 'upper_zmm': rows[1]['native_evex']['after']['vectors']['zmm16'] = '00' * 32 + 'a5' * 32
    if attack == 'k7': rows[1]['native_evex']['after']['registers']['k7'] = 1
    if attack == 'ret_read': rows[12]['native_evex']['reads'][0]['bytes_hex'] = '3512000000000000'
    if attack == 'ret_extra_read': rows[12]['pre_memory_observations'].append(copy.deepcopy(rows[12]['pre_memory_observations'][0]))
    if attack == 'missing_fp': rows[1]['native_evex']['before'].pop('fpu')
    if attack == 'projection': rows[1]['pre']['gpr']['rsi'] = '0x0000000000000001'
    if attack == 'seam': rows[2]['native_evex']['before']['registers']['r10'] = 1
    if attack == 'sequence': rows[1]['seq'] = True
    if attack == 'bool_after': rows[1]['native_evex']['after']['registers']['rax'] = False
    if attack == 'bool_write': rows[11]['possible_memory_writes'][0]['size'] = True
    if attack == 'result': rows[11]['result_bits'] = '0x' + '01' * 16
    if attack == 'module': rows[3]['module_sha256'] = 'b' * 64
    if attack == 'kind': rows[9]['kind'] = 'ZERO_FILL'
    if attack == 'observed_byte': rows[11]['possible_memory_writes'][0]['after_hex'] = '01'


@pytest.mark.parametrize('attack', ['code', 'missing_same_value', 'outside_write',
    'sidecar_missing_write', 'mask', 'width', 'fill', 'fp', 'upper_zmm', 'k7',
    'ret_read', 'ret_extra_read', 'missing_fp', 'projection', 'seam', 'sequence',
    'bool_after', 'bool_write', 'result', 'module', 'kind', 'observed_byte'])
def test_native_effect_and_graph_adversarial_cases_refuse(attack):
    capture, rows, region = fixture()
    mutate(rows, attack)
    with pytest.raises(ValueError):
        build(capture, rows, region)


@pytest.mark.parametrize('spans', [[], [dict(start_seq=0,end_seq=12)],
    [dict(start_seq=True,end_seq=13)], [dict(start_seq=0,end_seq=13,verified=True)],
    [dict(start_seq=0,end_seq=13)] * 2])
def test_missing_partial_overlapping_or_trust_flag_span_refuses(spans):
    capture, rows, region = fixture()
    with pytest.raises(ValueError):
        build(capture, rows, region, spans)


def test_old_no_native_flow_keeps_original_graph_contract():
    capture, rows, region = fixture()
    rows = [dict(seq=0, kind='ROUTING', opcode='nop', operands=[], pre=project(full_state()),
        post=project(full_state()), phase='init')]
    region['end_seq'] = 1
    ops, values, terminal = build(capture, rows, region, [])
    assert ops == []
    assert len(values) == 6
    assert terminal['gradient'][0].value_id == 'v:boundary:init:gradient'


def test_native_sidecar_omission_cannot_fall_back_to_unchecked_generic_flow():
    capture, rows, region = fixture()
    for row in rows:
        row.pop('native_evex')
    with pytest.raises(ValueError):
        build(capture, rows, region, [])


def test_raw_mutation_after_span_proof_refuses_before_graph_effect():
    capture, rows, region = fixture()
    flow = bridge().NativeEvexDataflow(rows, capture, ROOT,
        verified_spans=[dict(start_seq=0, end_seq=13)])
    rows[1]['native_evex']['before']['registers']['rsi'] = 1
    with pytest.raises(ValueError):
        flow.process_record(rows[1])
    assert flow.values == []


def test_store_before_bytes_cannot_contradict_prior_buffer_provenance():
    capture, rows, region = fixture()
    for write in rows[11]['possible_memory_writes']:
        write.update(before_hex='01', value_changed=True)
    rows[11]['operands'][1]['raw_bits'] = '0x' + '01' * 16
    with pytest.raises(ValueError, match='prior memory provenance'):
        build(capture, rows, region)


@pytest.mark.parametrize('field', ['module_load_base', 'possible_memory_writes', 'pre_memory_observations', 'pre'])
def test_missing_actual_raw_fields_refuse(field):
    capture, rows, region = fixture()
    rows[0].pop(field)
    with pytest.raises(ValueError):
        build(capture, rows, region)
