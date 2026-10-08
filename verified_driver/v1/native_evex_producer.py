"""Finite independent producer for 13 byte/ELF-PC-bound libc instructions.

This models completed, nonfaulting instructions in 64-bit mode, with CET IBT
and shadow stacks explicitly disabled. Address effects are restricted to the
canonical-48 subset (also canonical under five-level paging); exceptions,
page permissions, and asynchronous/debug effects require separate evidence.
No observation post-state or checker implementation supplies any result.

Intel primary references (instruction headings identify the normative sections):
https://cdrdv2-public.intel.com/782156/325383-sdm-vol-2abcd.pdf
  BZHI; AND; CMP; Jcc; MOV; KMOVW/KMOVB/KMOVQ/KMOVD;
  VPBROADCASTB/W/D/Q--Load With Broadcast Integer Data From GPR;
  VMOVDQU,VMOVDQU8/16/32/64 (Store-Form); RET.
https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf
  ENDBR64 (NOP when IBT disabled).
https://cdrdv2-public.intel.com/782149/253665-sdm-vol-1.pdf
  3.4.1.1 (32-bit destinations zero-extend), 6.2.5 (64-bit stack behavior).
https://cdrdv2-public.intel.com/874249/253668-090-sdm-vol-3a.pdf
  2.3 (RF is automatically cleared after successful instruction execution;
  TF requests a subsequent single-step debug exception).
Undefined AF for AND and AF/PF for BZHI are excluded from comparison masks;
their retained numeric placeholders are explicitly not preservation claims.
RF=1 is outside this finite domain, rather than being called preserved.
TF itself is not changed by these instructions. Debugger-mediated single-step
trap delivery and flag restoration are external to the instruction result;
actual TF acquisition must be bound by the observer, without inferring TF=0.
"""
from copy import deepcopy
import re


PINNED_STEPS = {
    0x1996c0: 'f30f1efa',
    0x1996c4: '62e27d287ac6',
    0x1996ca: '4889f8',
    0x1996cd: '4883fa20',
    0x1996d1: '722d',
    0x199700: '81e7ff0f0000',
    0x199706: '81ffe00f0000',
    0x19970c: '0f87ae000000',
    0x199712: 'b9ffffffff',
    0x199717: 'c4e268f5c9',
    0x19971c: 'c5fb92c9',
    0x199720: '62e17f297f00',
    0x199726: 'c3',
}
_GPRS = {'rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp'} | {
    f'r{i}' for i in range(8, 16)}
_SELECTORS = {'cs', 'ss', 'ds', 'es', 'fs', 'gs'}
_REGS = _GPRS | _SELECTORS | {'rip', 'eflags', 'mxcsr', 'fs_base', 'gs_base'} | {
    f'k{i}' for i in range(8)}
_FPU_SCALARS = {'fctrl', 'fstat', 'ftag', 'fiseg', 'fioff', 'foseg', 'fooff', 'fop'}
_FPU_STACK = {f'st{i}' for i in range(8)}
_U64 = (1 << 64) - 1
_EFLAGS = (1 << 32) - 1
_CF, _PF, _AF, _ZF, _SF, _OF = 1, 4, 16, 64, 128, 2048
_ARITH = _CF | _PF | _AF | _ZF | _SF | _OF


def _unsigned(value, bits, label):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError(f'REFUSED: {label} must be an unsigned {bits}-bit integer')
    return value


def _keys(value, expected, label):
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f'REFUSED: incomplete or unsupported {label} state')


def _hex(value, size, label):
    if type(value) is not str or re.fullmatch('[0-9a-f]{' + str(size * 2) + '}', value) is None:
        raise ValueError(f'REFUSED: {label} must contain {size} raw little-endian bytes')


def _canonical(value, label):
    _unsigned(value, 64, label)
    if not (value < 1 << 47 or value >= (1 << 64) - (1 << 47)):
        raise ValueError(f'REFUSED: unsupported noncanonical-48 {label}')
    return value


def _span(address, size):
    _canonical(address, 'memory address')
    if address > _U64 - (size - 1):
        raise ValueError('REFUSED: memory span overflow')
    _canonical(address + size - 1, 'memory endpoint')


def _validate(before, runtime_pc):
    _keys(before, {'registers', 'vectors', 'fpu', 'unavailable', 'control'}, 'context')
    if type(before['unavailable']) is not list or before['unavailable']:
        raise ValueError('REFUSED: unavailable architectural state')
    _keys(before['control'], {'cet_ibt', 'cet_shstk'}, 'control')
    if any(value is not False for value in before['control'].values()):
        raise ValueError('REFUSED: CET must be explicitly disabled')
    _keys(before['registers'], _REGS, 'register')
    for name, value in before['registers'].items():
        width = 16 if name in _SELECTORS else 32 if name in {'eflags', 'mxcsr'} else 64
        _unsigned(value, width, name)
    if before['registers']['eflags'] & (1 << 16):
        raise ValueError('REFUSED: RF=1 is outside finite successful-instruction domain')
    if before['registers']['rip'] != runtime_pc:
        raise ValueError('REFUSED: before RIP disagrees with ELF PC and load base')
    _keys(before['vectors'], {f'zmm{i}' for i in range(32)}, 'vector')
    for name, value in before['vectors'].items():
        _hex(value, 64, name)
    _keys(before['fpu'], _FPU_SCALARS | _FPU_STACK, 'raw x87')
    for name in _FPU_SCALARS:
        _unsigned(before['fpu'][name], 64 if name in {'fioff', 'fooff'} else 16, name)
    for name in _FPU_STACK:
        _hex(before['fpu'][name], 10, name)


def _szp(value, bits):
    return ((_SF if value & (1 << (bits - 1)) else 0)
            | (_ZF if value == 0 else 0)
            | (_PF if (value & 255).bit_count() % 2 == 0 else 0))


def _compare(flags, left, right, bits):
    mask = (1 << bits) - 1
    left &= mask
    right &= mask
    result = (left - right) & mask
    status = _szp(result, bits)
    if left < right:
        status |= _CF
    if (left ^ right ^ result) & 16:
        status |= _AF
    if (left ^ right) & (left ^ result) & (1 << (bits - 1)):
        status |= _OF
    return (flags & ~_ARITH) | status


def derive_step(elf_pc: int, instruction_bytes: str, before: dict,
                read_memory: callable, load_base: int) -> dict:
    """Derive complete post-context and all activated data-memory effects.

    ``read_memory(address, size)`` must return exactly ``size`` bytes. Only RET
    calls it. Stores are descriptors for every enabled byte, including writes
    that leave memory unchanged, without fictitious CPU reads of prior bytes.
    Callers authenticate instruction-fetch bytes and nonfaulting acquisition.
    ``defined_flags_mask`` applies only to EFLAGS; every other supplied state
    field is exact. Malformed, partial, or unsupported inputs raise ValueError.
    """
    _unsigned(elf_pc, 64, 'ELF PC')
    _unsigned(load_base, 64, 'load base')
    if elf_pc not in PINNED_STEPS or type(instruction_bytes) is not str or instruction_bytes != PINNED_STEPS[elf_pc]:
        raise ValueError('REFUSED: unsupported or tampered PC/instruction bytes')
    if load_base > _U64 - elf_pc:
        raise ValueError('REFUSED: runtime PC overflow')
    runtime_pc = _canonical(load_base + elf_pc, 'runtime PC')
    _validate(before, runtime_pc)
    if not callable(read_memory):
        raise ValueError('REFUSED: memory reader must be callable')
    # Every pinned form is a near/intrasegment or non-control operation.
    # None loads a segment register; preserve the six actual selector inputs.
    # Execution-mode admission is an external acquisition proof, not inferred
    # from selector numbers or the ELF64 file header here.
    after = deepcopy(before)
    regs = after['registers']
    next_pc = runtime_pc + len(instruction_bytes) // 2
    reads, writes, features = [], [], []
    flag_mask = _EFLAGS

    if elf_pc == 0x1996c4:
        after['vectors']['zmm16'] = f'{regs["rsi"] & 255:02x}' * 32 + '00' * 32
        features = ['avx512bw', 'avx512vl']
    elif elf_pc == 0x1996ca:
        regs['rax'] = regs['rdi']
    elif elf_pc == 0x1996cd:
        regs['eflags'] = _compare(regs['eflags'], regs['rdx'], 32, 64)
    elif elf_pc == 0x1996d1:
        if regs['eflags'] & _CF:
            next_pc += 0x2d
    elif elf_pc == 0x199700:
        regs['rdi'] &= 0xfff
        changed = _ARITH & ~_AF
        regs['eflags'] = (regs['eflags'] & ~changed) | _szp(regs['rdi'], 32)
        flag_mask &= ~_AF
    elif elf_pc == 0x199706:
        regs['eflags'] = _compare(regs['eflags'], regs['rdi'], 0xfe0, 32)
    elif elf_pc == 0x19970c:
        if not regs['eflags'] & (_CF | _ZF):
            next_pc += 0xae
    elif elf_pc == 0x199712:
        regs['rcx'] = 0xffffffff
    elif elf_pc == 0x199717:
        index = regs['rdx'] & 255
        source = regs['rcx'] & 0xffffffff
        regs['rcx'] = source if index >= 32 else source & ((1 << index) - 1)
        changed = _CF | _ZF | _SF | _OF
        status = (_CF if index >= 32 else 0) | (_ZF if regs['rcx'] == 0 else 0)
        if regs['rcx'] & 0x80000000:
            status |= _SF
        regs['eflags'] = (regs['eflags'] & ~changed) | status
        flag_mask &= ~(_AF | _PF)
        features = ['bmi2']
    elif elf_pc == 0x19971c:
        regs['k1'] = regs['rcx'] & 0xffffffff
        features = ['avx512bw']
    elif elf_pc == 0x199720:
        lanes = bytes.fromhex(after['vectors']['zmm16'])
        for lane in range(32):
            if regs['k1'] & (1 << lane):
                address = regs['rax'] + lane
                _span(address, 1)
                writes.append(dict(address=address, size=1, after_hex=f'{lanes[lane]:02x}'))
        features = ['avx512bw', 'avx512vl']
    elif elf_pc == 0x199726:
        address = regs['rsp']
        _span(address, 8)
        raw = read_memory(address, 8)
        if type(raw) is not bytes or len(raw) != 8:
            raise ValueError('REFUSED: RET requires exactly eight raw stack bytes')
        next_pc = _canonical(int.from_bytes(raw, 'little'), 'RET target')
        regs['rsp'] = _canonical(address + 8, 'RET stack pointer')
        reads.append(dict(address=address, size=8, bytes_hex=raw.hex()))
    # ENDBR64 has no effects under the explicit disabled-CET contract.
    regs['rip'] = _canonical(next_pc, 'next PC')
    return dict(after=after, reads=reads, writes=writes,
                defined_flags_mask=flag_mask, required_features=features)
