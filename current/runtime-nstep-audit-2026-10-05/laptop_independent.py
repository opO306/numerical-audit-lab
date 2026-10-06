"""Standalone finite numerical replay, written independently by a fresh reviewer.

Standard library only. No lab/producer/translator/checker/oracle import or exec.
Windows is a checker host for stored Linux traces, not an original Gala executor.
This is not a full x86 decoder, source attestation, external audit, or certification.
The inherited untraced base and Python tail remain explicit trust premises.
"""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import re
import struct
import time
import zipfile

FROZEN = '48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780'
WHEEL = 'cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0'
SIGN = 1 << 63
MASK = SIGN - 1
ROLES = ('q', 'full_v', 'latent', 'gradient')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def integer(v, why):
    need(type(v) is int and 0 <= v < 2**64, why)
    return v


def canonical(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pairs(entries):
    result = {}
    for k, v in entries:
        need(k not in result, 'ambiguous duplicate JSON key')
        result[k] = v
    return result


def decode(data):
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def raw_bits(s, width=8):
    need(type(width) is int and 0 < width <= 16 and isinstance(s, str) and
         re.fullmatch(r'0x[0-9a-f]{' + str(2 * width) + '}', s), 'canonical raw bits/width')
    return int(s, 16)


def binary_fraction(bits):
    integer(bits, 'binary64 bits')
    exponent = (bits >> 52) & 2047
    need(exponent != 2047, 'non-finite binary64 outside finite replay contract')
    mantissa = bits & ((1 << 52) - 1)
    power = -1074 if exponent == 0 else exponent - 1075
    if exponent:
        mantissa += 1 << 52
    q = Fraction(mantissa << power, 1) if power >= 0 else Fraction(mantissa, 1 << -power)
    return -q if bits & SIGN else q


def nearest_even(q, negative_zero=False):
    """Integer significand quantization; ties are resolved by parity, not host FP."""
    if not q:
        return SIGN if negative_zero else 0
    sign = SIGN if q < 0 else 0
    q = abs(q)
    num, den = q.numerator, q.denominator
    e = num.bit_length() - den.bit_length()
    too_small = (num < den << e) if e >= 0 else ((num << -e) < den)
    if too_small:
        e -= 1
    unit = max(e - 52, -1074)
    top, bottom = (num, den << unit) if unit >= 0 else (num << -unit, den)
    m, rest = divmod(top, bottom)
    if 2 * rest > bottom or (2 * rest == bottom and m & 1):
        m += 1
    if not m:
        return sign
    if e < -1022:
        need(m <= 1 << 52, 'subnormal normalization')
        return sign | m
    if m == 1 << 53:
        m >>= 1
        e += 1
    need(-1022 <= e <= 1023 and (1 << 52) <= m < (1 << 53), 'finite rounded range')
    return sign | ((e + 1023) << 52) | (m - (1 << 52))


def bop(kind, a, b):
    x, y = binary_fraction(a), binary_fraction(b)
    if kind == 'MUL':
        return nearest_even(x * y, bool((a ^ b) & SIGN))
    effective_b = b ^ SIGN if kind == 'SUB' else b
    need(kind in ('ADD', 'SUB'), 'supported binary64 arithmetic')
    q = x - y if kind == 'SUB' else x + y
    minus_zero = not x and not y and bool(a & SIGN) and bool(effective_b & SIGN)
    return nearest_even(q, minus_zero)


def next_up(v):
    binary_fraction(v)
    if not v & MASK:
        return 1
    result = v - 1 if v & SIGN else v + 1
    binary_fraction(result)
    return result


def upward(q):
    need(q >= 0, 'nonnegative outward rational')
    rounded = nearest_even(q)
    return next_up(rounded) if binary_fraction(rounded) < q else rounded


def plus(a, b):
    return bop('ADD', a, b)


def times(a, b):
    return bop('MUL', a, b)


def padded_sum(a, b):
    return next_up(plus(a, b))


def float_hex(v):
    return struct.unpack('>d', v.to_bytes(8, 'big'))[0].hex()


def from_hex(s):
    need(isinstance(s, str), 'hex Form scalar')
    v = int.from_bytes(struct.pack('>d', float.fromhex(s)), 'big')
    binary_fraction(v)
    need(float_hex(v) == s, 'canonical finite Form hex')
    return v


def form_doc(f):
    return {'coef': [float_hex(v) for v in f[0]], 'box': float_hex(f[1])}


def read_form(v):
    need(set(v) == {'coef', 'box'} and len(v['coef']) == 4, 'four coefficient Form')
    f = (tuple(from_hex(s) for s in v['coef']), from_hex(v['box']))
    need(binary_fraction(f[1]) >= 0, 'nonnegative Form box')
    return f


def rounding_fee(v):
    # The frozen contract rounds abs(v)*2^-52, then adds the minimum
    # subnormal, then takes the next representable value toward +infinity.
    return next_up(plus(times(v & MASK, 0x3CB0000000000000), 1))


def radius(f):
    r = f[1]
    for c in f[0]:
        r = padded_sum(r, c & MASK)
    return r


def propagate(kind, x, y, z, a, b):
    """Independent evaluation of the sealed Form equations, no QR/reseeding."""
    X, Y, Z = binary_fraction(x), binary_fraction(y), binary_fraction(z)
    exact = X + Y if kind == 'ADD' else X - Y if kind == 'SUB' else X * Y
    rho = upward(abs(Z - exact))
    coefficients = []
    excess = 0
    if kind in ('ADD', 'SUB'):
        for ca, cb in zip(a[0], b[0]):
            c = plus(ca, cb ^ SIGN if kind == 'SUB' else cb)
            coefficients.append(c)
            excess = padded_sum(excess, rounding_fee(c))
        box = padded_sum(padded_sum(padded_sum(a[1], b[1]), excess), rho)
    else:
        need(kind == 'MUL', 'supported Form operation')
        # The contract first converts exact represented center Fractions back
        # to floats. Fraction has no negative zero; preserve that distinction
        # from the actual machine-result RNE check performed elsewhere.
        cx, cy = (x if X else 0), (y if Y else 0)
        for ca, cb in zip(a[0], b[0]):
            left, right = times(cx, cb), times(cy, ca)
            c = plus(left, right)
            coefficients.append(c)
            excess = padded_sum(padded_sum(excess, rounding_fee(left)),
                                padded_sum(rounding_fee(right), rounding_fee(c)))
        box = plus(next_up(times(x & MASK, b[1])), next_up(times(y & MASK, a[1])))
        product_radius = next_up(times(radius(a), radius(b)))
        box = padded_sum(padded_sum(box, product_radius), padded_sum(excess, rho))
    return (tuple(coefficients), box)


def value_bytes(v):
    return raw_bits(v['raw_bits'], v['width']).to_bytes(v['width'], 'little')


def storage_keys(s):
    need(s['space'] in ('buffer', 'register', 'elf', 'stack', 'instruction') and isinstance(s['name'], str), 'storage space')
    start = s['byte_offset']
    need(type(start) is int and -(1 << 63) <= start < (1 << 63) and
         (start >= 0 or s['space'] == 'stack'), 'storage signed stack offset')
    width = integer(s['width'], 'storage width')
    need(0 < width <= 16, 'finite storage width')
    return [(s['space'], s['name'], start + k) for k in range(width)]


def state_id(vid, offset=0):
    return 'state:' + vid + ':byte:' + str(offset)


def verify_block(block, region, prior, acq, raw, arithmetic):
    phase = region['occurrence']
    ns = acq + '/' + phase
    ir = block['ir']
    need(ir['namespace'] == ns and ir['acquisition_id'] == acq and ir['region'] == region,
         'actual block acquisition/phase/region identity')
    entry = raw[region['start_seq']]['pre']
    for role, register in (('q', 'rcx'), ('full_v', 'r8'), ('latent', 'r9')):
        need(region['pointers'][role] == int(entry['gpr'][register], 16), 'actual ABI component pointer')
    need(int(entry['gpr']['rsi'], 16) == 1 and int(entry['gpr']['rdx'], 16) == 2, 'actual ABI dimensions')
    for field, register in (('t_bits', 'xmm0'), ('dt_bits', 'xmm1')):
        need(raw_bits(region[field]) == int(entry['xmm'][register], 16) & ((1 << 64) - 1), 'actual entry scalar argument')
    operations, values = ir['operations'], ir['values']
    need(all(type(o['ir_sequence']) is int for o in operations) and
         [o['ir_sequence'] for o in operations] == list(range(len(operations))), 'IR dense operation order')
    need(len(operations) == len(arithmetic), 'all actual arithmetic represented')
    expected_basis = {'k': 4, 'namespace': acq + '/global-error-basis',
                      'meaning': 'computed-minus-true', 'reseeded': False,
                      'conditional_accepted_init_to_step1_gap': True}
    link = block['boundary']
    received_basis = link['shared_form_basis']
    need(received_basis == expected_basis and type(received_basis['k']) is int and
         received_basis['reseeded'] is False and received_basis['conditional_accepted_init_to_step1_gap'] is True,
         'unchanged global error basis')
    carries = {}
    previous = {} if prior is None else {(e['component'], e['byte_offset']): e for e in prior}
    expected_carry_count = 0 if prior is None else 6
    need(len(link['carry']) == expected_carry_count, 'six immediately preceding carried lanes')
    for c in link['carry']:
        role, off = c['component'], integer(c['byte_offset'], 'carry byte offset')
        need(role in ROLES[:3] and off in (0, 8) and (role, off) in previous, 'carry role')
        p = previous[role, off]
        entry = state_id(ns + '/v:boundary:' + phase + ':' + role, off)
        need(c['entry_state_id'] == entry and entry not in carries, 'unique dynamic entry state')
        need(c['audited_endpoint']['form_source_state_id'] == p['state_id'] and
             c['from_occurrence'] == p['occurrence'] and c['to_occurrence'] == phase and
             c['from_acquisition_id'] == c['to_acquisition_id'] == p['acquisition_id'] == acq,
             'immediate prior dynamic state identity')
        need(c['center_bits'] == p['center_bits'] == region['start_state'][role][off // 8] and
             c['form'] == p['form'] and c['process_local_pointer'] == region['pointers'][role],
             'carried actual bits/pointer/Form; no reset')
        carries[entry] = p
    by, order, live = {}, {}, {}
    last_sequence = region['start_seq']
    for index, v in enumerate(values):
        vid = v['value_id']
        need(vid.startswith(ns + '/v:') and vid not in by and v['producer']['phase'] == phase,
             'unique per-occurrence value identity')
        data = value_bytes(v)
        need(v['storage']['width'] == v['width'], 'value/storage width')
        producer = v['producer']
        seq, kind = producer['trace_sequence'], v['producer_kind']
        if seq is None:
            need(kind == 'LOAD_BITS' and producer['role'] == 'boundary' and not v['source_slices'],
                 'only boundary LOAD roots admitted')
            name = producer['boundary']
            need(name in (*ROLES, 'xmm0', 'xmm1'), 'closed numerical boundary root')
            bits = (b''.join(raw_bits(s).to_bytes(8, 'little') for s in region['start_state'][name])
                    if name in ROLES else raw_bits(region['t_bits' if name == 'xmm0' else 'dt_bits']).to_bytes(8, 'little'))
            need(data == bits, 'root matches actual entry snapshot')
            need(vid == ns + '/v:boundary:' + phase + ':' + name, 'boundary dynamic ID')
            if name == 'gradient':
                need(not any(data), 'actual gradient root zero')
        else:
            integer(seq, 'producer trace sequence')
            need(region['start_seq'] <= seq < region['end_seq'] and seq >= last_sequence and seq in raw,
                 'actual chronological value producer')
            last_sequence = seq
            r = raw[seq]
            need(r['occurrence'] == phase and vid.startswith(ns + '/v:r' + str(seq) + ':'), 'raw producer occurrence')
            operand_index = producer.get('operand_index')
            if kind == 'CONST_BITS':
                need(not v['source_slices'] and producer['role'] == 'constant_read', 'constant root role')
                operand = r['operands'][operand_index]
                origin = operand['constant_origin']
                need(data == raw_bits(operand['raw_bits'], operand['width']).to_bytes(operand['width'], 'little') and
                     origin['module_sha256'] == producer['module_sha256'] and
                     origin['file_offset'] == producer['file_offset'], 'actual constant observation binding')
            elif kind == 'ZERO_BITS':
                need(not any(data) and not v['source_slices'], 'zero producer exact bits')
                need(producer['role'] in ('zero_extend', 'zero_upper', 'zero_result', 'integer_zero', 'instruction_zero'),
                     'closed zero producer role')
            elif kind == 'ARITHMETIC_RESULT':
                need(not v['source_slices'] and producer['role'] == 'arithmetic_result' and
                     r['kind'] in ('ADD', 'SUB', 'MUL') and
                     data == raw_bits(r['result_bits']).to_bytes(8, 'little'), 'actual arithmetic value')
            elif kind == 'COPY_BITS':
                covered = [False] * len(data)
                for edge in v['source_slices']:
                    source = edge['value_id']
                    need(source in by and order[source] < index and edge['trace_sequence'] == seq, 'COPY prior def-use')
                    src, dst, width = edge['source_offset'], edge['destination_offset'], edge['width']
                    need(all(type(x) is int for x in (src, dst, width)) and src >= 0 and dst >= 0 and width > 0 and
                         src + width <= by[source]['width'] and dst + width <= len(data), 'COPY slice range')
                    need(data[dst:dst + width] == value_bytes(by[source])[src:src + width], 'COPY bits from identified source')
                    keys = storage_keys(edge['source_storage'])
                    need(len(keys) == width, 'COPY source storage width')
                    for k, key in enumerate(keys):
                        need(not covered[dst + k], 'COPY overlapping slices')
                        covered[dst + k] = True
                        if key in live:
                            need(live[key] == (source, src + k), 'COPY current tracked storage def-use')
                # The IR also records routing copies with only some tracked
                # source bytes. Untracked bytes remain unavailable as numerical
                # roots. bind() still demands one complete eight-byte source
                # slice for every scalar participating in any Form or endpoint.
                need(all(covered) or producer['role'] == 'copy_result', 'numerical COPY complete byte coverage')
                if producer['role'] == 'copy_result':
                    need(r.get('result_bits') is not None and data ==
                         raw_bits(r['result_bits'], len(data)).to_bytes(len(data), 'little'), 'actual copy result bits')
                    if v['storage']['space'] == 'buffer':
                        operand = r['operands'][operand_index]
                        need(operand['kind'] == 'memory' and operand['address'] ==
                             region['pointers'][v['storage']['name']] + v['storage']['byte_offset'], 'actual component store address')
                else:
                    need(producer['role'] in ('arithmetic_destination_pre_read', 'arithmetic_source_read'), 'closed COPY read role')
                    operand = r['operands'][operand_index]
                    need(data == raw_bits(operand['raw_bits'], operand['width']).to_bytes(operand['width'], 'little'),
                         'actual arithmetic PRE read bits')
            else:
                raise ValueError('unsupported numerical producer')
        by[vid], order[vid] = v, index
        if seq is None or kind in ('ZERO_BITS', 'ARITHMETIC_RESULT') or producer['role'] == 'copy_result':
            for k, key in enumerate(storage_keys(v['storage'])):
                if kind == 'COPY_BITS' and not covered[k]:
                    live.pop(key, None)
                else:
                    live[key] = (vid, k)
    need(len([v for v in values if v['producer']['role'] == 'boundary']) == 6, 'six complete unique boundary roots')
    state, forms, busy = {}, {}, set()
    result_order = {o['output_value_id']: k for k, o in enumerate(operations)}
    need(len(result_order) == len(operations), 'unique arithmetic outputs')

    def bind(vid, off=0):
        s = state_id(vid, off)
        if s in state:
            return s
        need(s not in busy and vid in by and type(off) is int and off >= 0 and off + 8 <= by[vid]['width'], 'acyclic scalar state')
        busy.add(s)
        v = by[vid]
        bits = int.from_bytes(value_bytes(v)[off:off + 8], 'little')
        source, sequence = None, None
        kind = v['producer_kind']
        if s in carries:
            p = carries[s]
            need(bits == raw_bits(p['center_bits']), 'actual carried scalar root')
            f, binding, source = read_form(p['form']), 'CARRIED', p['state_id']
        elif kind in ('LOAD_BITS', 'CONST_BITS', 'ZERO_BITS'):
            f, binding = ((0, 0, 0, 0), 0), kind.removesuffix('_BITS')
        elif kind == 'COPY_BITS':
            matches = [e for e in v['source_slices'] if e['destination_offset'] <= off and
                       off + 8 <= e['destination_offset'] + e['width']]
            need(len(matches) == 1, 'single complete scalar COPY')
            edge = matches[0]
            source = bind(edge['value_id'], edge['source_offset'] + off - edge['destination_offset'])
            need(raw_bits(state[source]['raw_center_bits']) == bits, 'scalar COPY center identity')
            f, binding = forms[source], 'COPY'
        else:
            need(kind == 'ARITHMETIC_RESULT' and s in forms, 'no forward arithmetic dependency')
            f, binding, sequence = forms[s], kind, result_order[vid]
        forms[s] = f
        state[s] = {'state_id': s, 'value_id': vid, 'byte_offset': off, 'width': 8,
                    'raw_center_bits': f'0x{bits:016x}', 'form': form_doc(f), 'binding_kind': binding,
                    'source_state_id': source, 'producer_ir_sequence': sequence,
                    'phase': phase, 'trace_sequence': v['producer']['trace_sequence']}
        busy.remove(s)
        return s

    emitted = []
    for k, (op, actual) in enumerate(zip(operations, arithmetic)):
        need(all(op[field] == actual[field] for field in actual), 'ordered actual raw arithmetic correspondence')
        # `step` is the inherited init/body discriminator (0/1), not the
        # occurrence counter. Dynamic identity is the namespaced phase stepK,
        # which must match the raw occurrence and the current block.
        need(op['phase'] == phase and type(op['step']) is int and
             op['step'] == (0 if phase == 'init' else 1), 'operation dynamic phase')
        av, bv, zv = (op[t + '_value_id'] for t in ('input0', 'input1', 'output'))
        a, b = bind(av), bind(bv)
        x, y, z = (raw_bits(op[t + '_raw_bits']) for t in ('input0', 'input1', 'output'))
        need(raw_bits(state[a]['raw_center_bits']) == x and raw_bits(state[b]['raw_center_bits']) == y and
             value_bytes(by[zv]) == z.to_bytes(8, 'little'), 'operation input/output graph centers')
        need(order[av] < order[zv] and order[bv] < order[zv] and
             by[zv]['producer']['trace_sequence'] == op['trace_sequence'], 'operation actual def-use order')
        kind = op['operation_kind'].removesuffix('_BINARY64')
        need(bop(kind, x, y) == z, 'exact Fraction and integer ties-to-even result')
        out = state_id(zv)
        forms[out] = propagate(kind, x, y, z, forms[a], forms[b])
        bind(zv)
        emitted.append({**op, 'v2_sequence': k, 'v2_operation_kind': kind,
                        'input0_state_id': a, 'input1_state_id': b, 'output_state_id': out,
                        'input0_form': form_doc(forms[a]), 'input1_form': form_doc(forms[b]),
                        'output_form': form_doc(forms[out])})
    boundaries = []
    for v in values:
        if v['producer']['role'] == 'boundary':
            boundaries.append({'value_id': v['value_id'], 'boundary': v['producer']['boundary'],
                               'state_ids': [bind(v['value_id'], off) for off in range(0, v['width'], 8)]})
    endpoints = []
    for role in ROLES:
        for off in (0, 8):
            refs = [live['buffer', role, off + k] for k in range(8)]
            vid, start = refs[0]
            need(refs == [(vid, start + k) for k in range(8)], 'actual final scalar tracked storage provenance')
            s = bind(vid, start)
            need(state[s]['raw_center_bits'] == region['end_state'][role][off // 8], 'actual terminal center')
            endpoints.append({'component': role, 'byte_offset': off, 'center_bits': state[s]['raw_center_bits'],
                              'value_id': vid, 'source_byte_offset': start, 'acquisition_id': acq,
                              'occurrence': phase, 'state_id': s, 'form': form_doc(forms[s])})
    v2 = block['v2']
    need(v2['namespace'] == ns and v2['shared_form_basis'] == expected_basis, 'V2 occurrence and basis')
    frozen = v2['frozen_v2']
    need(frozen['k'] == 4 and frozen['module'] == 'lab.v2_bound' and frozen['operator'] == 'step_forms' and
         all(frozen[field] == FROZEN for field in ('lf_sha256', 'imported_lf_sha256', 'requested_lf_sha256')), 'sealed V2 identity claim')
    need(v2['operations'] == emitted and v2['boundaries'] == boundaries and
         v2['state_bindings'] == sorted(state.values(), key=lambda s: (s['value_id'], s['byte_offset'])),
         'independent every-operation/state four-coefficient plus box replay')
    need(block['endpoint'] == endpoints, 'independent last-write endpoint and Form')
    return endpoints, emitted


def semantic_replay(capture, blocks, harness, complete, raw, arithmetic):
    n = integer(capture['requested_steps'], 'finite requested steps')
    need(n in (10, 100) and capture['verdict'] == 'CAPTURED', 'supported actual 10/100 capture')
    phases = ['init'] + ['step' + str(k) for k in range(1, n + 1)]
    need([r['occurrence'] for r in capture['regions']] == phases and len(blocks) == n + 1 and
         len(capture['caller_corridors']) == n - 1, 'all requested native body and caller occurrences')
    acq = capture['acquisition_id']
    need(re.fullmatch('[0-9a-f]{64}', acq) and capture['wheel_sha256'] == WHEEL, 'actual acquisition/wheel identity claim')
    need(capture['harness_completed_normally'] is True and type(capture['gdb_return_code']) is int and
         capture['gdb_return_code'] == 0, 'normal collection completion')
    e = capture['gdb_exit_event']
    need(e['observed'] is True and type(e['exit_code']) is int and e['exit_code'] == 0 and
         e['inferior_pid'] == capture['process_identity']['pid'] and
         e['selected_inferior_pid_after_exit'] == 0, 'observed same-inferior normal exit')
    previous, opcount, coefficient_nonzero, formcount = None, 0, 0, 0
    for region, block in zip(capture['regions'], blocks):
        need(region['dt_bits'] == '0x3f90000000000000', 'frozen represented dt')
        current, emitted = verify_block(block, region, previous, acq, raw, arithmetic[region['occurrence']])
        previous = current
        opcount += len(emitted)
        for o in emitted:
            for field in ('input0_form', 'input1_form', 'output_form'):
                f = read_form(o[field])
                coefficient_nonzero += sum(bool(binary_fraction(c)) for c in f[0])
                formcount += 1
    need(opcount == 14 + 22 * n, 'closed observed arithmetic count')
    need(type(harness['n_steps']) is int and harness['n_steps'] == n, 'honest harness requested range')
    bits = [e['center_bits'] for e in previous if e['component'] in ('q', 'full_v')]
    need(harness['output_bits'] == bits, 'actual final native centers to harness output')
    need(complete['requested_complete'] is True and complete['verdict'] == 'CHECKER_PASS' and
         type(complete['requested_steps']) is int and type(complete['checked_steps']) is int and
         complete['requested_steps'] == complete['checked_steps'] == n and
         complete['acquisition_id'] == acq and complete['operation_count'] == opcount and
         complete['carry_join_count'] == n - 1 and complete['final_endpoint'] == previous and
         complete['trace_sha256'] == capture['trace_sha256'] and
         complete['source_pinset_sha256'] == capture['source_pinset_sha256'], 'honest requested completion evidence')
    need(complete['init_to_step1'] == complete['post_terminal_frontier'] == 'UNTRACED' and
         complete['formal_certification'] is False, 'retained evidence gaps and certification boundary')
    return {'requested_steps': n, 'checked_steps': n, 'operation_count': opcount,
            'four_coefficient_form_comparisons': formcount, 'nonzero_coefficient_occurrences': coefficient_nonzero,
            'final_bits': bits, 'acquisition_id': acq, 'trace_sha256': capture['trace_sha256']}


def read_package(path):
    names = ('capture.json', 'trace.jsonl', 'blocks.json', 'harness_output.json', 'completion.json')
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        need(len(entries) <= 1000 and sum(e.file_size for e in entries) <= 1073741824, 'ZIP finite total size')
        selected = {}
        for name in names:
            hits = [e for e in entries if Path(e.filename).name == name and not e.is_dir()]
            need(len(hits) == 1, 'one unique ZIP member for ' + name)
            selected[name] = hits[0]
        need(selected['trace.jsonl'].file_size <= 536870912, 'trace size ceiling')
        for name in names:
            if name != 'trace.jsonl':
                need(selected[name].file_size <= 67108864, 'receipt/IR size ceiling')
        blobs = {name: z.read(selected[name]) for name in names if name != 'trace.jsonl'}
        capture, blocks, harness, complete = (decode(blobs[name]) for name in
                                             ('capture.json', 'blocks.json', 'harness_output.json', 'completion.json'))
        need(type(blocks) is list and len(blocks) <= 101, 'finite graph block count')
        needed = {v['producer']['trace_sequence'] for b in blocks for v in b['ir']['values']
                  if v['producer']['trace_sequence'] is not None}
        needed.update(r['start_seq'] for r in capture['regions'])
        entries_to_keep = {r['start_seq'] for r in capture['regions']}
        arithmetic = {r['occurrence']: [] for r in capture['regions']}
        regions, corridors = capture['regions'], capture['caller_corridors']
        need(len(regions) >= 2 and len(corridors) == len(regions) - 2, 'finite region/caller list')
        spans = [regions[0], regions[1]]
        for k, c in enumerate(corridors):
            spans.extend((c, regions[k + 2]))
        spans.append(capture['terminal_corridor'])
        frontier = 0
        for span in spans:
            start, end = integer(span['start_seq'], 'span start'), integer(span['end_seq'], 'span end')
            need(start == frontier and start < end <= 125000, 'complete finite region coverage')
            frontier = end
        span_index = 0
        raw, digest, chain, previous, count = {}, hashlib.sha256(), '0' * 64, None, 0
        pid = integer(capture['process_identity']['pid'], 'actual process PID')
        owner = capture['regions'][0]['ptid']
        need(len(owner) == 3 and owner[0] == pid and all(type(x) is int for x in owner), 'actual owner thread')
        gap = capture['regions'][1]['start_seq']
        with z.open(selected['trace.jsonl']) as stream:
            for line in stream:
                need(len(line) <= 1048576, 'bounded instruction row')
                digest.update(line)
                row = decode(line)
                need(type(row['seq']) is int and row['seq'] == count and row['pid'] == pid and row['ptid'] == owner,
                     'ordered unique same-process raw record')
                while span_index < len(spans) and count >= spans[span_index]['end_seq']:
                    span_index += 1
                need(span_index < len(spans) and row['occurrence'] == spans[span_index]['occurrence'],
                     'actual ordered region occurrence coverage')
                chain = hashlib.sha256(bytes.fromhex(chain) + canonical({k: v for k, v in row.items() if k != 'chain'})).hexdigest()
                need(row['chain'] == chain, 'complete raw hash chain')
                registers = ('gpr', 'xmm', 'mxcsr', 'eflags', 'segment_bases')
                if previous is not None and count != gap:
                    need(previous == {k: row['pre'][k] for k in registers}, 'actual raw PRE/POST context seam')
                previous = {k: row['post'][k] for k in registers}
                phase = row['occurrence']
                if row.get('kind') in ('ADD', 'SUB', 'MUL'):
                    need(row['phase'] == phase and type(row['step']) is int and
                         row['step'] == (0 if phase == 'init' else 1), 'raw arithmetic occurrence/body discriminator')
                    need(phase in arithmetic and row['opcode'] == {'ADD': 'addsd', 'SUB': 'subsd', 'MUL': 'mulsd'}[row['kind']],
                         'actual scalar arithmetic instruction family')
                    need(len(row['operands']) == 2 and row['operands'][1]['kind'] == 'register' and
                         row['operands'][1]['register'].startswith('xmm'), 'actual scalar operands')
                    item = {'trace_sequence': count, 'step': row['step'], 'module_sha256': row['module_sha256'],
                            'elf_address': row['elf_address'], 'instruction_bytes': row['bytes'], 'opcode': row['opcode'],
                            'operation_kind': row['kind'] + '_BINARY64', 'mxcsr': row['pre']['mxcsr'],
                            'input0_raw_bits': row['operands'][1]['raw_bits'],
                            'input1_raw_bits': row['operands'][0]['raw_bits'], 'output_raw_bits': row['result_bits']}
                    x, y, out = (raw_bits(item[k]) for k in ('input0_raw_bits', 'input1_raw_bits', 'output_raw_bits'))
                    need(bop(row['kind'], x, y) == out, 'raw exact Fraction/RNE arithmetic')
                    dest = row['operands'][1]['register']
                    need(int(row['post']['xmm'][dest], 16) & ((1 << 64) - 1) == out,
                         'actual scalar post XMM result')
                    # Every replayed scalar requires the recorded RNE/FTZ/DAZ contract.
                    need(item['mxcsr'] & ((3 << 13) | (1 << 15) | (1 << 6)) == 0 and
                         item['mxcsr'] & 0x1f80 == 0x1f80, 'RNE and non-flushing arithmetic')
                    arithmetic[phase].append(item)
                if count in needed:
                    raw[count] = {k: row.get(k) for k in ('seq', 'occurrence', 'kind', 'operands', 'result_bits')}
                    if count in entries_to_keep:
                        raw[count]['pre'] = row['pre']
                count += 1
        need(count == frontier == capture['record_count'] and chain == capture['final_chain'] and
             digest.hexdigest() == capture['trace_sha256'], 'complete actual raw bytes/count')
        need(capture['terminal_corridor']['end_seq'] == count and
             complete['native_terminal_frontier'] == count - 1, 'honest terminal raw frontier')
        need(hashlib.sha256(canonical({k: v for k, v in complete.items() if k != 'completion_sha256'})).hexdigest() ==
             complete['completion_sha256'], 'completion digest')
        components = dict((c['path'], c['sha256']) for c in complete['ordered_component_hashes'])
        need(components.get('blocks.json') == hashlib.sha256(blobs['blocks.json']).hexdigest(), 'received graph bytes integrity')
    return capture, blocks, harness, complete, raw, arithmetic


def self_attacks(inputs):
    cap, blocks, harness, complete, raw, arithmetic = inputs
    reports = []
    for name in ('wrong-result', 'reset-box', 'previous-dynamic-id', 'false-N'):
        cc, bb, hh, dd = copy.deepcopy((cap, blocks, harness, complete))
        if name == 'wrong-result':
            bb[-1]['ir']['operations'][0]['output_raw_bits'] = '0x3ff0000000000000'
        elif name == 'reset-box':
            c = next(c for c in bb[-1]['boundary']['carry'] if read_form(c['form'])[1] != 0)
            c['form']['box'] = '0x0.0p+0'
        elif name == 'previous-dynamic-id':
            bb[-1]['boundary']['carry'][0]['audited_endpoint']['form_source_state_id'] = bb[1]['endpoint'][0]['state_id']
        else:
            cc['requested_steps'] += 1
        try:
            semantic_replay(cc, bb, hh, dd, raw, arithmetic)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            reports.append({'attack': name, 'verdict': 'REFUSED', 'reason': str(exc),
                            'hashes_used_by_semantic_attack': False})
        else:
            raise ValueError('independent self attack wrongly accepted: ' + name)
    return reports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    need(not args.out.exists(), 'exclusive result path')
    started = time.perf_counter()
    report = {'schema': 'agent-independent-numerical-replay-v1', 'checker_host': platform.node(),
              'checker_platform': platform.platform(), 'checker_python': platform.python_version(),
              'checker_role': 'Windows/host checker of stored Linux acquisition; original Gala not replayed here',
              'script_sha256': sha_file(__file__), 'package_sha256': sha_file(args.package),
              'external_audit_closure': False, 'formal_certification': False,
              'init_to_step1': 'UNTRACED', 'post_terminal_frontier': 'UNTRACED',
              'unverified_by_this_script': ['full x86 instruction decode/effects', 'ELF constant bytes',
                  'OS/GDB execution truth and source attestation', 'continuous/physical accuracy', 'universal executions']}
    try:
        data = read_package(args.package)
        report.update(semantic_replay(*data))
        report['self_attacks'] = self_attacks(data)
        report['verdict'] = 'INDEPENDENT_NUMERICAL_REPLAY_PASS'
        report['scope'] = 'finite observed raw scalar order/results, complete graph COPY/root def-use, four coefficients and box at every Form state, immediate dynamic carries'
        report['coefficient_evidence'] = ('native all-zero coefficients; no nonzero-coefficient native validation'
                                          if report['nonzero_coefficient_occurrences'] == 0 else 'nonzero native coefficients observed')
    except Exception as exc:
        report.update(verdict='REFUSED', requested_complete=False, reason=str(exc))
    report['wall_seconds'] = time.perf_counter() - started
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('xb') as f:
        f.write(canonical(report) + b'\n')
    print(json.dumps(report, sort_keys=True))
    return 0 if report['verdict'] == 'INDEPENDENT_NUMERICAL_REPLAY_PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
