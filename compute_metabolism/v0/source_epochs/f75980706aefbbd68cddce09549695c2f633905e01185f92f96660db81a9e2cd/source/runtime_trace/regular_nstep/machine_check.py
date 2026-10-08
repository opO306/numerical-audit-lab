"""Complete effects for the finite native body opcode set, independent of collector."""
import copy
from fractions import Fraction
import struct
from runtime_trace.caller_transition import checker as c
from runtime_trace.regular_2step.form_oracle import check_ieee


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def normalized(row):
    result = {**row, 'sequence': row['seq'],
              'pc': row.get('pc', row.get('runtime_pc')),
              'next_pc': row.get('next_pc', row.get('post_pc')),
              'instruction_bytes': row.get('instruction_bytes', row.get('bytes'))}
    writes = []
    for original in row['possible_memory_writes']:
        w = dict(original)
        for moment in ('before', 'after'):
            if moment + '_hex' in w and moment + '_bits' in w:
                data = bytes.fromhex(w[moment + '_hex'])
                require(len(data) == w['size'] and int.from_bytes(data, 'little') == int(w[moment + '_bits'], 16),
                        'conflicting hex/bits write representations')
            if moment + '_bits' not in w:
                data = bytes.fromhex(w[moment + '_hex'])
                w[moment + '_bits'] = f"0x{int.from_bytes(data, 'little'):0{w['size'] * 2}x}"
        changed = w['before_bits'] != w['after_bits']
        if 'value_changed' in w:
            require(w['value_changed'] is changed, 'honest write change metadata')
        w['value_changed'] = changed
        writes.append(w)
    result['possible_memory_writes'] = writes
    return result


def effect_assembly(assembly):
    # Objdump spells the multi-byte NOP's ignored operand/address prefixes.
    text = assembly
    for prefix in ('data16 ', 'cs '):
        text = text.removeprefix(prefix)
    if text.startswith(('nop ', 'nopw ', 'nopl ')) or text == 'nop':
        return 'nop'
    op, args = c._parse_assembly(text)
    if op == 'xchg' and args == ['%ax', '%ax']:
        return 'nop'  # exact register identity; pinned 66 90 instruction
    require(text == assembly, 'unsupported instruction prefix')
    return assembly


def observations(row, assembly):
    op, args = c._parse_assembly(assembly)
    if op in ('addsd', 'subsd', 'mulsd', 'movapd', 'movslq'):
        width = 4 if op == 'movslq' else 16 if op == 'movapd' else 8
        result = [('EXPLICIT', a, width) for a in args if c._is_memory_operand(a)]
    else:
        result = c._expected_observations({**row, 'sequence': -1}, assembly)
    if row['elf_address'] == 202266:
        require(row['instruction_bytes'] == 'e86141feff', 'exact body entry CALL')
        result.append(('ABI_STACK_ARGUMENT', '(%rsp)', 8))
    return result


def registers(rows, decoded):
    for row in rows:
        assembly = decoded[row['sequence']]
        op, args = c._parse_assembly(assembly)
        if op not in ('addsd', 'subsd', 'mulsd', 'movapd', 'movslq', 'imul', 'nopl', 'jae'):
            c._validate_register_semantics([row], decoded)
            continue
        expected = copy.deepcopy(row['pre'])
        expected['gpr']['rip'] = c._bits(row['next_pc'], 8)
        flag_mask = (1 << 64) - 1
        if op.endswith('sd'):
            x, y = c._source_value(row, args[1], 8), c._source_value(row, args[0], 8)
            z = c._reg_value(row['post'], args[1])[0] & ((1 << 64) - 1)
            for bits in (x, y, z):
                exponent, fraction = (bits >> 52) & 2047, bits & ((1 << 52) - 1)
                require(exponent != 2047 and (exponent != 0 or fraction == 0),
                        'supported finite normal-or-zero body operands/results')
            kind = {'addsd': 'ADD', 'subsd': 'SUB', 'mulsd': 'MUL'}[op]
            check_ieee(kind + '_BINARY64', c._bits(x, 8), c._bits(y, 8), c._bits(z, 8))
            xf, yf, zf = [Fraction(struct.unpack('<d', v.to_bytes(8, 'little'))[0]) for v in (x, y, z)]
            exact = xf + yf if kind == 'ADD' else xf - yf if kind == 'SUB' else xf * yf
            expected['mxcsr'] |= 0x20 if exact != zf else 0
            old = c._reg_value(row['pre'], args[1])[0]
            c._set_register(expected, args[1], old & ~((1 << 64) - 1) | z)
        elif op == 'movapd':
            c._set_register(expected, args[1], c._source_value(row, args[0], 16))
        elif op == 'movslq':
            v = c._source_value(row, args[0], 4)
            c._set_register(expected, args[1], v - (1 << 32) if v & (1 << 31) else v)
        elif op == 'imul':
            require(len(args) == 2, 'finite two-operand IMUL')
            width = c._operand_width(op, args)
            def signed(v):
                return v - (1 << width) if v & (1 << (width - 1)) else v
            exact = signed(c._source_value(row, args[0], width // 8)) * signed(c._source_value(row, args[1], width // 8))
            c._set_register(expected, args[1], exact)
            overflow = not -(1 << (width - 1)) <= exact < (1 << (width - 1))
            expected['eflags'] = expected['eflags'] & ~(1 | 0x800) | int(overflow) | (int(overflow) << 11)
            flag_mask &= ~(4 | 16 | 64 | 128)  # architecturally undefined
        require(expected['gpr'] == row['post']['gpr'] and expected['xmm'] == row['post']['xmm'] and
                expected['mxcsr'] == row['post']['mxcsr'] and expected['segment_bases'] == row['post']['segment_bases'] and
                (expected['eflags'] ^ row['post']['eflags']) & flag_mask == 0, 'complete native body register/flag effects')


def controls(rows, decoded, bases):
    for row in rows:
        op, args = c._parse_assembly(decoded[row['sequence']])
        if op == 'jae':
            target = c._direct_target(decoded[row['sequence']], bases[row['module_sha256']])
            expected = target if not row['pre']['eflags'] & 1 else row['pc'] + len(bytes.fromhex(row['instruction_bytes']))
            require(row['next_pc'] == expected, 'independent JAE target/CF')
        else:
            c._validate_control([row], decoded, bases)


def writes(rows, decoded):
    for row in rows:
        op, args = c._parse_assembly(decoded[row['sequence']])
        if op in ('addsd', 'subsd', 'mulsd', 'movapd', 'movslq', 'imul', 'nopl', 'jae'):
            require(not row['possible_memory_writes'], 'no invented body arithmetic/register writes')
        else:
            c._validate_recorded_writes([row], decoded)
