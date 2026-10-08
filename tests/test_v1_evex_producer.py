"""Independent hand-derived tests for the pinned native producer contract."""
import copy
import importlib

import pytest


BASE = 0x700000000000
CODES = {
    0x1996c0: 'f30f1efa', 0x1996c4: '62e27d287ac6',
    0x1996ca: '4889f8', 0x1996cd: '4883fa20', 0x1996d1: '722d',
    0x199700: '81e7ff0f0000', 0x199706: '81ffe00f0000',
    0x19970c: '0f87ae000000', 0x199712: 'b9ffffffff',
    0x199717: 'c4e268f5c9', 0x19971c: 'c5fb92c9',
    0x199720: '62e17f297f00', 0x199726: 'c3',
}


def producer():
    try:
        return importlib.import_module('verified_driver.v1.native_evex_producer')
    except ModuleNotFoundError:
        pytest.fail('finite independent native producer is not implemented')


def state(pc):
    regs = {name: 0x111100000000 + i for i, name in enumerate(
        ['rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp']
        + [f'r{i}' for i in range(8, 16)])}
    regs.update(rip=BASE + pc, eflags=0x202, mxcsr=0x1f80,
                fs_base=0x700010000000, gs_base=0)
    regs.update({f'k{i}': 0xffff000000000000 + i for i in range(8)})
    regs.update(cs=0x33, ss=0x2b, ds=0, es=0, fs=0, gs=0)
    fpu = {name: i for i, name in enumerate(
        ['fctrl', 'fstat', 'ftag', 'fiseg', 'fioff', 'foseg', 'fooff', 'fop'])}
    fpu.update({f'st{i}': f'{i + 1:02x}' * 10 for i in range(8)})
    return dict(registers=regs,
        vectors={f'zmm{i}': f'{i + 1:02x}' * 64 for i in range(32)},
        fpu=fpu, unavailable=[], control=dict(cet_ibt=False, cet_shstk=False))


def derive(pc, before=None, memory=None, code=None):
    if before is None:
        before = state(pc)
    if memory is None:
        def memory(*args):
            pytest.fail('unexpected data memory read')
    return producer().derive_step(pc, CODES[pc] if code is None else code,
                                  before, memory, BASE)


def assert_preserved(before, result, changed_regs=(), changed_vectors=()):
    after = result['after']
    assert after is not before
    assert set(after) == set(before)
    for section in ['registers', 'vectors', 'fpu']:
        assert set(after[section]) == set(before[section])
        assert after[section] is not before[section]
    for name, value in before['registers'].items():
        if name not in set(changed_regs) | {'rip'}:
            assert after['registers'][name] == value
    for name, value in before['vectors'].items():
        if name not in changed_vectors:
            assert after['vectors'][name] == value
    assert after['fpu'] == before['fpu']
    assert after['control'] == before['control']
    assert after['unavailable'] == []


def test_broadcast_low_byte_all_lanes_upper_zero_and_full_preservation():
    before = state(0x1996c4)
    before['registers']['rsi'] = 0xdeadbeef80
    frozen = copy.deepcopy(before)
    result = derive(0x1996c4, before)
    assert result['after']['vectors']['zmm16'] == '80' * 32 + '00' * 32
    assert result['after']['registers']['rip'] == BASE + 0x1996ca
    assert result['reads'] == result['writes'] == []
    assert result['required_features'] == ['avx512bw', 'avx512vl']
    assert result['defined_flags_mask'] == 0xffffffff
    assert_preserved(before, result, changed_vectors={'zmm16'})
    assert before == frozen


@pytest.mark.parametrize('mask,lanes', [(0, []), (1, [0]),
    (0x80008001, [0, 15, 31]), (0xffffffff, list(range(32))),
    (0xffffffff00000000, [])])
def test_masked_store_writes_active_byte_lanes_even_same_value(mask, lanes):
    before = state(0x199720)
    before['registers'].update(rax=0x20000, k1=mask)
    before['vectors']['zmm16'] = 'a5' * 64
    result = derive(0x199720, before)
    assert result['writes'] == [dict(address=0x20000 + i, size=1, after_hex='a5')
                                for i in lanes]
    assert result['reads'] == []
    assert result['required_features'] == ['avx512bw', 'avx512vl']
    old_memory = bytearray(b'\xa5' * 32)
    new_memory = bytearray(old_memory)
    for write in result['writes']:
        new_memory[write['address'] - 0x20000] = int(write['after_hex'], 16)
    assert new_memory == old_memory  # Effect descriptors remain even with zero changed bytes.
    assert_preserved(before, result)


@pytest.mark.parametrize('index,expected,flags', [
    (0, 0, 0x40), (16, 0xffff, 0), (31, 0x7fffffff, 0),
    (32, 0xffffffff, 0x81), (255, 0xffffffff, 0x81),
    (256, 0, 0x40), (288, 0xffffffff, 0x81)])
def test_bzhi_boundary_low_index_byte_zero_extension_and_defined_flags(index, expected, flags):
    before = state(0x199717)
    before['registers'].update(rcx=0xaaaaaaaaffffffff, rdx=index, eflags=0xed7)
    result = derive(0x199717, before)
    assert result['after']['registers']['rcx'] == expected
    assert result['after']['registers']['eflags'] & 0x8c1 == flags
    assert result['after']['registers']['eflags'] & 0x600 == 0x600
    assert result['defined_flags_mask'] == 0xffffffeb
    assert result['required_features'] == ['bmi2']
    assert_preserved(before, result, {'rcx', 'eflags'})


@pytest.mark.parametrize('source,index,expected,flags', [
    (0x87654321, 16, 0x4321, 0), (0x87654321, 31, 0x07654321, 0),
    (0x87654321, 32, 0x87654321, 0x81), (0, 255, 0, 0x41)])
def test_bzhi_general_source_is_derived_not_expected_memset_literal(source, index, expected, flags):
    before = state(0x199717)
    before['registers'].update(rcx=source, rdx=index, eflags=0x202)
    result = derive(0x199717, before)
    assert result['after']['registers']['rcx'] == expected
    assert result['after']['registers']['eflags'] & 0x8c1 == flags


@pytest.mark.parametrize('pc,name,value,expected', [
    (0x1996ca, 'rdi', 0xffffffffffffffff, 0xffffffffffffffff),
    (0x199700, 'rdi', 0xabcdef0000000fff, 0xfff),
    (0x199712, 'rcx', 0xffffffffffff0000, 0xffffffff),
    (0x19971c, 'rcx', 0xffff000012345678, 0x12345678)])
def test_mov_and_kmov_widths(pc, name, value, expected):
    before = state(pc)
    before['registers'][name] = value
    result = derive(pc, before)
    output = {0x1996ca: 'rax', 0x199700: 'rdi',
              0x199712: 'rcx', 0x19971c: 'k1'}[pc]
    assert result['after']['registers'][output] == expected
    changes = {output, 'eflags'} if pc == 0x199700 else {output}
    assert_preserved(before, result, changes)


@pytest.mark.parametrize('rdi,flags', [(0, 0x44), (0xfff, 0x04), (0x1000, 0x44)])
def test_and_defined_flags_and_undefined_af(rdi, flags):
    before = state(0x199700)
    before['registers'].update(rdi=rdi, eflags=0xad7)
    result = derive(0x199700, before)
    assert result['after']['registers']['eflags'] & 0x8c5 == flags
    assert result['defined_flags_mask'] == 0xffffffef


@pytest.mark.parametrize('pc,name,value,flags', [
    # Both immediates end in zero: no low-nibble borrow (AF=0).
    # -1 ends ff (even parity); MIN_INT-32 ends e0 (odd parity).
    (0x1996cd, 'rdx', 31, 0x85), (0x1996cd, 'rdx', 32, 0x44),
    (0x1996cd, 'rdx', 33, 0), (0x1996cd, 'rdx', 0x8000000000000000, 0x800),
    (0x199706, 'rdi', 0xfdf, 0x85), (0x199706, 'rdi', 0xfe0, 0x44),
    (0x199706, 'rdi', 0xfe1, 0), (0x199706, 'rdi', 0x100000fe0, 0x44)])
def test_cmp_hand_derived_signed_unsigned_and_auxiliary_flags(pc, name, value, flags):
    before = state(pc)
    before['registers'].update({name: value, 'eflags': 0xad7})
    result = derive(pc, before)
    assert result['after']['registers']['eflags'] & 0x8d5 == flags
    assert result['defined_flags_mask'] == 0xffffffff
    assert_preserved(before, result, {'eflags'})


@pytest.mark.parametrize('pc,flags,target', [
    (0x1996d1, 1, 0x199700), (0x1996d1, 0, 0x1996d3),
    (0x19970c, 0, 0x1997c0), (0x19970c, 1, 0x199712),
    (0x19970c, 0x40, 0x199712), (0x19970c, 0x41, 0x199712)])
def test_conditional_jumps_derive_both_paths(pc, flags, target):
    before = state(pc)
    before['registers']['eflags'] = flags
    result = derive(pc, before)
    assert result['after']['registers']['rip'] == BASE + target
    assert_preserved(before, result)


def test_endbr_with_disabled_cet_and_ret_reads_only_stack_return():
    before = state(0x1996c0)
    result = derive(0x1996c0, before)
    assert result['after']['registers']['rip'] == BASE + 0x1996c4
    assert_preserved(before, result)
    before = state(0x199726)
    before['registers']['rsp'] = 0x10000
    calls = []
    def memory(address, size):
        calls.append((address, size))
        return bytes.fromhex('7856341200700000')
    result = derive(0x199726, before, memory)
    assert calls == [(0x10000, 8)]
    assert result['after']['registers']['rip'] == 0x700012345678
    assert result['after']['registers']['rsp'] == 0x10008
    assert result['reads'] == [dict(address=0x10000, size=8, bytes_hex='7856341200700000')]
    assert result['writes'] == []
    assert_preserved(before, result, {'rsp'})


@pytest.mark.parametrize('mutation', [
    lambda s: s.pop('fpu'), lambda s: s['fpu'].pop('st7'),
    lambda s: s['fpu'].update(st0='00'), lambda s: s['fpu'].update(fctrl=True),
    lambda s: s['vectors'].pop('zmm31'), lambda s: s['vectors'].update(xmm0='00'*16),
    lambda s: s['vectors'].update(zmm0='AA'*64),
    lambda s: s['registers'].pop('k7'), lambda s: s['registers'].update(rax=True),
    lambda s: s['registers'].update(rax=-1), lambda s: s['registers'].update(rax=1<<64),
    lambda s: s['registers'].update(rip=0), lambda s: s.update(after={}),
    lambda s: s.update(unavailable=['st0']), lambda s: s.pop('control'),
    lambda s: s['control'].update(cet_ibt=True), lambda s: s['control'].update(cet_shstk=True),
    lambda s: s['control'].update(cet_ibt=0), lambda s: s['control'].update(extra=False),
])
def test_incomplete_boolean_tampered_or_unbound_full_state_refuses_before_reads(mutation):
    before = state(0x1996c0)
    mutation(before)
    with pytest.raises(ValueError):
        derive(0x1996c0, before)


@pytest.mark.parametrize('code', ['f30f1efb', 'f30f1efa00', 'F30F1EFA', 'f3 0f 1e fa'])
def test_exact_byte_binding_refuses_tamper(code):
    with pytest.raises(ValueError):
        derive(0x1996c0, code=code)


@pytest.mark.parametrize('pc', [True, 0x1996c1, 0x1997c0])
def test_unknown_pc_and_bool_refuse(pc):
    with pytest.raises(ValueError):
        producer().derive_step(pc, 'f30f1efa', state(0x1996c0), None, BASE)


@pytest.mark.parametrize('reply', [b'', b'\x00'*7, b'\x00'*9, '00'*8, None])
def test_ret_missing_or_malformed_read_refuses(reply):
    with pytest.raises(ValueError):
        derive(0x199726, memory=lambda *_: reply)


@pytest.mark.parametrize('pc,name,address', [
    (0x199726, 'rsp', 0x800000000000),
    (0x199726, 'rsp', 0x7ffffffffffc),
    (0x199726, 'rsp', 0xfffffffffffffffc),
    (0x199720, 'rax', 0x800000000000),
    (0x199720, 'rax', 0xffffffffffffffff)])
def test_active_unsupported_memory_addresses_refuse(pc, name, address):
    before = state(pc)
    before['registers'].update({name: address, 'k1': 3})
    with pytest.raises(ValueError):
        derive(pc, before)


def test_ret_unsupported_return_target_refuses():
    with pytest.raises(ValueError):
        derive(0x199726, memory=lambda *_: bytes.fromhex('0000000000800000'))


@pytest.mark.parametrize('base', [True, -1, 1 << 64, 0x800000000000])
def test_unsupported_load_base_refuses(base):
    with pytest.raises(ValueError):
        producer().derive_step(0x1996c0, CODES[0x1996c0], state(0x1996c0), lambda *_: b'', base)


def test_complete_13_step_path_general_inputs_and_derived_return():
    before = state(0x1996c0)
    before['registers'].update(rdi=0x20001, rsi=0xa5, rdx=16, rsp=0x10000)
    baseline = copy.deepcopy(before)
    all_reads, all_writes = [], []
    for pc in CODES:
        result = derive(pc, before, lambda *_: bytes.fromhex('7856341200700000'))
        all_reads.extend(result['reads'])
        all_writes.extend(result['writes'])
        before = result['after']
    assert before['registers']['rax'] == 0x20001
    assert before['registers']['rdi'] == 1
    assert before['registers']['rcx'] == 0xffff
    assert before['registers']['k1'] == 0xffff
    assert before['registers']['rip'] == 0x700012345678
    assert before['registers']['rsp'] == 0x10008
    assert before['vectors']['zmm16'] == 'a5' * 32 + '00' * 32
    assert before['fpu'] == baseline['fpu']
    assert all_reads == [dict(address=0x10000, size=8, bytes_hex='7856341200700000')]
    assert all_writes == [dict(address=0x20001 + i, size=1, after_hex='a5') for i in range(16)]


@pytest.mark.parametrize('name', ['fctrl', 'fstat', 'ftag', 'fiseg', 'foseg', 'fop'])
@pytest.mark.parametrize('value', [1 << 16, (1 << 64) - 1, True, -1])
def test_x87_uint16_fields_refuse_out_of_width_or_non_integer(name, value):
    before = state(0x1996c0)
    before['fpu'][name] = value
    with pytest.raises(ValueError, match=name):
        derive(0x1996c0, before)


@pytest.mark.parametrize('name', ['fctrl', 'fstat', 'ftag', 'fiseg', 'foseg', 'fop'])
def test_x87_uint16_upper_boundary_is_preserved(name):
    before = state(0x1996c0)
    before['fpu'][name] = 0xffff
    result = derive(0x1996c0, before)
    assert result['after']['fpu'][name] == 0xffff


@pytest.mark.parametrize('name', ['fioff', 'fooff'])
def test_x87_pointer_fields_retain_uint64_domain(name):
    before = state(0x1996c0)
    before['fpu'][name] = 0xffffffffffffffff
    result = derive(0x1996c0, before)
    assert result['after']['fpu'][name] == 0xffffffffffffffff
    before['fpu'][name] = 1 << 64
    with pytest.raises(ValueError, match=name):
        derive(0x1996c0, before)


@pytest.mark.parametrize('pc', list(CODES))
def test_resume_flag_input_refuses_before_any_semantics_or_memory(pc):
    before = state(pc)
    before['registers']['eflags'] |= 1 << 16
    with pytest.raises(ValueError, match='RF'):
        derive(pc, before)


@pytest.mark.parametrize('pc', list(CODES))
def test_tf_instruction_result_is_preserved_without_claiming_debug_trap_delivery(pc):
    before = state(pc)
    before['registers']['eflags'] |= 1 << 8
    result = derive(pc, before, lambda *_: bytes.fromhex('7856341200700000'))
    assert result['after']['registers']['eflags'] & (1 << 8)
    assert result['defined_flags_mask'] & (1 << 8)


@pytest.mark.parametrize('rsp', [0x7ffffffffff8, 0xfffffffffffffff8])
def test_ret_rejects_unsupported_successor_rsp_even_when_read_span_is_valid(rsp):
    before = state(0x199726)
    before['registers']['rsp'] = rsp
    reads = []
    def reader(address, size):
        reads.append((address, size))
        return bytes.fromhex('7856341200700000')
    with pytest.raises(ValueError, match='RET stack pointer'):
        derive(0x199726, before, reader)
    assert reads == [(rsp, 8)]


SELECTOR_NAMES = ('cs', 'ss', 'ds', 'es', 'fs', 'gs')


def selector_state(pc):
    # Keep the explicit selector contract clone used by the observed RED stage.
    before = copy.deepcopy(state(pc))
    before['registers'].update(dict(zip(SELECTOR_NAMES, (0x33, 0x2b, 0, 1, 0xfffe, 0xffff))))
    return before


@pytest.mark.parametrize('pc', list(CODES))
def test_all_thirteen_producer_forms_preserve_actual_six_uint16_selectors(pc):
    before = selector_state(pc)
    frozen = copy.deepcopy(before)
    result = derive(pc, before, lambda *_: bytes.fromhex('7856341200700000'))
    for name in SELECTOR_NAMES:
        assert type(result['after']['registers'][name]) is int
        assert result['after']['registers'][name] == frozen['registers'][name]
    assert before == frozen


@pytest.mark.parametrize('name', SELECTOR_NAMES)
def test_producer_missing_actual_selector_refuses(name):
    before = selector_state(0x1996c0)
    # First require the complete expanded input to be accepted: refusal of all
    # expanded states must not satisfy this missing-field negative control.
    derive(0x1996c0, before)
    del before['registers'][name]
    with pytest.raises(ValueError):
        derive(0x1996c0, before)


@pytest.mark.parametrize('name', SELECTOR_NAMES)
@pytest.mark.parametrize('value', [-1, 1 << 16, True, False])
def test_producer_selector_width_and_boolean_refuse(name, value):
    before = selector_state(0x1996c0)
    derive(0x1996c0, before)
    before['registers'][name] = value
    with pytest.raises(ValueError):
        derive(0x1996c0, before)
