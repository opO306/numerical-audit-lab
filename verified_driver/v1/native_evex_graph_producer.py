"""V1-owned producer byte graph extension for actual finite EVEX raw rows.

Native proof is rerun from complete pre-state, exact code, and recorded RET
read, before graph construction. The span descriptors are locators, never
trusted PASS flags. Surrounding rows use unchanged audited _Dataflow methods;
all original row identities remain intact. This module grants no profile,
caller, source, or library authority; those belong to the outer raw gate.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from runtime_trace.numeric_ir.translator import _Dataflow, _ByteRef
from .native_evex_producer import PINNED_STEPS, derive_step, _validate


_GPRS = {'rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp', 'rip'} | {
    f'r{i}' for i in range(8, 16)}
_KINDS = ['ROUTING', 'ZERO_FILL', 'ROUTING', 'ROUTING', 'CONTROL',
          'ROUTING', 'ROUTING', 'CONTROL', 'ROUTING', 'ROUTING', 'ROUTING', 'MOVE', 'CONTROL']
_OPCODES = ['endbr64', 'vpbroadcastb', 'mov', 'cmp', 'jb', 'and', 'cmp',
            'ja', 'mov', 'bzhi', 'kmovd', 'vmovdqu8', 'ret']


def _require(condition, reason):
    if not condition:
        raise ValueError('REFUSED: native graph ' + reason)


def _int(value, label):
    _require(type(value) is int and 0 <= value < 1 << 64, 'strict integer ' + label)
    return value


def _hex(raw, size, label):
    _require(type(raw) is str and re.fullmatch('[0-9a-f]{' + str(size * 2) + '}', raw) is not None,
             'raw byte width ' + label)
    return bytes.fromhex(raw)


def _bits(raw, size, label):
    _require(type(raw) is str and raw.startswith('0x'), 'raw bits ' + label)
    data = _hex(raw[2:], size, label)
    return data[::-1]


def _projection(full, legacy):
    required = {'gpr', 'xmm', 'mxcsr', 'eflags', 'segment_bases'}
    _require(type(legacy) is dict and required <= set(legacy) and set(legacy) <= required | {'extra_vectors'},
             'missing legacy context projection')
    regs = full['registers']
    _require(type(legacy['gpr']) is dict and set(legacy['gpr']) == _GPRS,
             'complete legacy GPR projection')
    for name in _GPRS:
        _require(legacy['gpr'][name] == f'0x{regs[name]:016x}', 'GPR/full-state projection ' + name)
    _require(type(legacy['xmm']) is dict and set(legacy['xmm']) == {f'xmm{i}' for i in range(16)},
             'complete legacy XMM projection')
    for i in range(16):
        expected = int.from_bytes(bytes.fromhex(full['vectors'][f'zmm{i}'])[:16], 'little')
        _require(legacy['xmm'][f'xmm{i}'] == f'0x{expected:032x}', 'XMM/full-state projection')
    _require(type(legacy['eflags']) is int and legacy['eflags'] == regs['eflags'] and
             type(legacy['mxcsr']) is int and legacy['mxcsr'] == regs['mxcsr'], 'flags/MXCSR projection')
    _require(legacy['segment_bases'] == {name: f'0x{regs[name]:016x}'
        for name in ('fs_base', 'gs_base')}, 'FS/GS projection')
    extra = legacy.get('extra_vectors', {})
    _require(type(extra) is dict, 'extra vector projection')
    for name, bits in extra.items():
        match = re.fullmatch(r'(xmm|ymm|zmm)([0-9]+)', name)
        _require(match is not None and int(match[2]) < 32, 'extra vector name')
        width = {'xmm': 16, 'ymm': 32, 'zmm': 64}[match[1]]
        expected = bytes.fromhex(full['vectors']['zmm' + match[2]])[:width]
        _require(_bits(bits, width, name) == expected, 'extra vector/full-state projection')


def _memory_record_bytes(record, moment):
    size = _int(record['size'], 'write size')
    _require(size == 1, 'finite activated byte write width')
    forms = []
    if moment + '_hex' in record:
        forms.append(_hex(record[moment + '_hex'], size, moment))
    if moment + '_bits' in record:
        forms.append(_bits(record[moment + '_bits'], size, moment))
    _require(forms and all(raw == forms[0] for raw in forms), 'missing/conflicting write representation')
    return forms[0]


def _verify_row(row, pc, code, kind, opcode, module_hash, base):
    _require(row['elf_address'] == pc and type(row['elf_address']) is int, 'exact native ELF PC')
    _require(row['bytes'] == code and row.get('instruction_bytes', code) == code, 'exact native code bytes')
    _require(row['kind'] == kind and row['opcode'] == opcode, 'exact native kind/opcode')
    _require(row['module_sha256'] == module_hash and row['module_load_base'] == base and
             type(row['module_load_base']) is int, 'native module/load-base continuity')
    native = row['native_evex']
    _require(type(native) is dict and set(native) == {'before', 'after', 'reads', 'writes'}, 'full native sidecar')
    reads = native['reads']
    _require(type(reads) is list and len(reads) == (1 if pc == 0x199726 else 0), 'native read footprint')
    for read in reads:
        _require(type(read) is dict and set(read) == {'address', 'size', 'bytes_hex'}, 'native read descriptor')
        _int(read['address'], 'read address')
        _require(type(read['size']) is int and read['size'] == 8, 'RET read size')
        _hex(read['bytes_hex'], 8, 'RET read')
    def reader(address, size):
        _require(len(reads) == 1 and reads[0]['address'] == address and reads[0]['size'] == size,
                 'derived RET read address/size')
        return bytes.fromhex(reads[0]['bytes_hex'])
    effect = derive_step(pc, code, native['before'], reader, base)
    after = native['after']
    _require(type(after) is dict and type(after.get('registers')) is dict and 'rip' in after['registers'],
             'complete after context')
    _validate(after, after['registers']['rip'])
    checked_after = deepcopy(after)
    observed_flags = checked_after['registers']['eflags']
    expected_flags = effect['after']['registers']['eflags']
    checked_after['registers']['eflags'] = expected_flags
    _require(checked_after == effect['after'] and
             (observed_flags ^ expected_flags) & effect['defined_flags_mask'] == 0,
             'independently derived full native after state')
    _require(native['reads'] == effect['reads'], 'derived native reads')
    _require(type(native['writes']) is list, 'native writes list')
    for write in native['writes']:
        _require(type(write) is dict and set(write) == {'address', 'size', 'after_hex'}, 'native write descriptor')
        _int(write['address'], 'write address')
        _require(type(write['size']) is int and write['size'] == 1, 'activated byte width')
        _hex(write['after_hex'], 1, 'write after')
    _require(native['writes'] == effect['writes'], 'derived every active write including unchanged bytes')
    _projection(native['before'], row['pre'])
    _projection(after, row['post'])
    _require(type(row['runtime_pc']) is int and row['runtime_pc'] == base + pc and
             type(row['post_pc']) is int and row['post_pc'] == after['registers']['rip'], 'actual pre/post PC')
    for name, expected in [('pc', row['runtime_pc']), ('next_pc', row['post_pc']), ('load_base', base)]:
        if name in row:
            _require(type(row[name]) is int and row[name] == expected, 'conflicting raw ' + name)
    observations = row['pre_memory_observations']
    _require(type(observations) is list and len(observations) == len(reads), 'actual read coverage')
    for observed, read in zip(observations, reads):
        _require(type(observed) is dict and type(observed['size']) is int and
                 type(observed['address']) is int and
                 {name: observed[name] for name in ('address', 'size', 'bytes_hex')} == read and
                 observed['kind'] == 'IMPLICIT_RET' and observed['operand'] == '(%rsp)' and
                 observed['status'] == 'OK' and observed['timing'] == 'PRE_INSTRUCTION', 'actual RET read projection')
    records = row['possible_memory_writes']
    _require(type(records) is list and len(records) == len(effect['writes']), 'actual active write coverage')
    before_bytes = bytearray()
    for recorded, expected in zip(records, effect['writes']):
        _require(type(recorded) is dict and _int(recorded['address'], 'write address') == expected['address'],
                 'actual active write address')
        prebyte = _memory_record_bytes(recorded, 'before')
        postbyte = _memory_record_bytes(recorded, 'after')
        _require(postbyte.hex() == expected['after_hex'], 'actual write byte vs derivation')
        _require(type(recorded.get('value_changed')) is bool and recorded['value_changed'] == (prebyte != postbyte),
                 'honest same-value write marker')
        before_bytes.extend(prebyte)
    if pc == 0x1996c4:
        _require(native['before']['registers']['rsi'] & 255 == 0, 'zero fill must originate from pre RSI')
        operands = row['operands']
        _require(type(operands) is list and len(operands) == 2, 'broadcast operands')
        source, destination = operands
        _require(source.get('kind') == 'register' and source.get('register') == 'esi' and
                 type(source.get('width')) is int and source['width'] == 1 and source.get('raw_bits') == '0x00',
                 'broadcast zero byte operand')
        _require(destination.get('kind') == 'register' and destination.get('register') == 'ymm16' and
                 type(destination.get('width')) is int and destination['width'] == 32 and
                 _bits(destination['raw_bits'], 32, 'broadcast destination') ==
                 bytes.fromhex(native['before']['vectors']['zmm16'])[:32] and
                 row['result_bits'] == '0x' + '00' * 32, 'broadcast derived vector operand/result')
    if pc == 0x199720:
        regs = native['before']['registers']
        _require(regs['rdx'] == 16 and regs['k1'] == 0xffff and
                 native['before']['vectors']['zmm16'][:64] == '00' * 32, 'closed 16-byte zero prefix mask/input')
        operands = row['operands']
        _require(type(operands) is list and len(operands) == 2, 'masked store operands')
        source, destination = operands
        _require(source.get('kind') == 'register' and source.get('register') == 'ymm16' and
                 type(source.get('width')) is int and source['width'] == 16 and
                 source.get('raw_bits') == '0x' + '00' * 16, 'masked store source vector prefix')
        _require(destination.get('kind') == 'memory' and type(destination.get('address')) is int and
                 destination['address'] == regs['rax'] and type(destination.get('width')) is int and
                 destination['width'] == 16 and _bits(destination['raw_bits'], 16, 'store before') == bytes(before_bytes) and
                 row['result_bits'] == '0x' + '00' * 16, 'masked store actual memory operand/result')
    return effect


def _verify_spans(rows, capture, spans):
    _require(type(spans) is list, 'span locators list required')
    covered, native, receipts = set(), set(), []
    for index, row in enumerate(rows):
        if type(row) is dict and ('native_evex' in row or
                type(row.get('elf_address')) is int and row['elf_address'] in PINNED_STEPS and
                row.get('bytes') == PINNED_STEPS[row['elf_address']]):
            native.add(index)
    previous_end = 0
    for span in spans:
        _require(type(span) is dict and set(span) == {'start_seq', 'end_seq'}, 'span locators only; no trust flags')
        start, end = _int(span['start_seq'], 'span start'), _int(span['end_seq'], 'span end')
        _require(start >= previous_end and end - start == 13 and end <= len(rows), 'exact ordered disjoint 13-row span')
        previous_end = end
        part = rows[start:end]
        _require(all(type(row) is dict and type(row.get('seq')) is int and row['seq'] == start + i and
                     'native_evex' in row for i, row in enumerate(part)), 'actual dense native raw rows')
        module_hash, base, module_path = part[0]['module_sha256'], _int(part[0]['module_load_base'], 'load base'), part[0]['module_path']
        _require(type(module_hash) is str and re.fullmatch('[0-9a-f]{64}', module_hash) is not None,
                 'native module digest')
        module = capture['modules'][module_path]
        _require(module['sha256'] == module_hash and type(module['load_base']) is int and module['load_base'] == base,
                 'capture native module identity')
        read_count, write_count = 0, 0
        prior = None
        for i, ((pc, code), row) in enumerate(zip(PINNED_STEPS.items(), part)):
            _require(row['module_path'] == module_path, 'native module path continuity')
            if prior is not None:
                _require(prior == row['native_evex']['before'], 'complete full-state native seam')
            effect = _verify_row(row, pc, code, _KINDS[i], _OPCODES[i], module_hash, base)
            prior = row['native_evex']['after']
            read_count += len(effect['reads'])
            write_count += len(effect['writes'])
        _require(part[0]['native_evex']['before']['registers']['rdx'] == 16,
                 'full native span length16 input')
        digest = hashlib.sha256(json.dumps(part, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()
        receipts.append(dict(start_seq=start, end_seq=end, raw_span_sha256=digest,
            instruction_count=13, read_count=read_count, write_count=write_count))
        covered.update(range(start, end))
    _require(covered == native, 'every actual native row exactly covered')
    return covered, receipts


class NativeEvexDataflow(_Dataflow):
    """Audited producer storage flow plus strictly proved native zero/store rows."""
    def __init__(self, rows, capture, root, *, verified_spans):
        try:
            self.native_rows, self.native_receipts = _verify_spans(rows, capture, verified_spans)
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError('REFUSED: incomplete native graph input: ' + str(exc)) from exc
        self._native_row_bytes = {seq: json.dumps(rows[seq], sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False).encode('utf-8') for seq in self.native_rows}
        super().__init__(rows, capture, Path(root))

    def process_record(self, record):
        if record['seq'] not in self.native_rows:
            _require('native_evex' not in record, 'unproved native row')
            return super().process_record(record)
        _require(record is self.rows[record['seq']], 'native row must be the authenticated actual object')
        _require(json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                 allow_nan=False).encode('utf-8') == self._native_row_bytes[record['seq']],
                 'native raw row changed after semantic proof')
        if record['elf_address'] == 0x1996c4:
            self.zero_record(record)
        elif record['elf_address'] == 0x199720:
            source, destination = record['operands']
            refs = self.refs_for_operand(source)
            _require(all(ref is not None for ref in refs) and len(refs) == 16 and
                     all(self.byte_value(ref) == 0 for ref in refs), 'complete source vector byte provenance')
            old_bytes = _bits(destination['raw_bits'], 16, 'store PRE operand')
            for ref, byte in zip(self.refs_for_operand(destination), old_bytes):
                _require(ref is None or self.byte_value(ref) == byte,
                         'masked store PRE bytes disagree with prior memory provenance')
            storage = self.operand_storage(record, destination, 1)
            value_id = f"v:r{record['seq']}:copy"
            self.add_value(value_id, 'COPY_BITS', bytes(16),
                dict(role='copy_result', trace_sequence=record['seq'], operand_index=1, phase=record['phase']),
                storage, self.slices(refs, storage, record['seq'], 0))
            self.put_refs(destination, value_id, range(16), f"record:{record['seq']}")
        # Other forms carry no newly invented numeric zero/copy provenance.
        self.forget_changed_gprs(record, set())


def build_ir(capture, rows, original, root, *, verified_spans):
    """Return (operations, values, terminal) using unchanged body framing.

    The caller keeps its existing Form construction and source-bound raw gate.
    Use ``NativeEvexDataflow`` as a flow factory if that caller already performs
    the same region/entry-origin preparation. ``native_receipts`` binds complete
    actual raw spans for inclusion in the outer edge's native report.
    """
    region = deepcopy(original)
    region['phase'] = region['occurrence']
    for field in ('start_state', 'end_state'):
        region[field] = {name: '0x' + ''.join(lane[2:] for lane in reversed(lanes))
                         for name, lanes in region[field].items()}
    flow = NativeEvexDataflow(rows, capture, root, verified_spans=verified_spans)
    flow.start_region(region, {})
    for register in ('v0', 'v1'):
        for offset in range(8):
            ref = flow.state['r', register, offset]
            flow.state['r', register, offset] = _ByteRef(ref.value_id, ref.offset, ref.origin_tag + ':' + str(offset))
    for row in rows[region['start_seq']:region['end_seq']]:
        flow.process_record(row)
    terminal = flow.end_region(region)
    return flow.operations, flow.values, terminal
