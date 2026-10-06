"""Independent finite native checks; no acquisition/translator/V2 imports."""
from collections import defaultdict
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re

from runtime_trace.regular_2step import structure
from runtime_trace.regular_2step import checker as body_checker
from runtime_trace.caller_transition import checker as caller
from runtime_trace.regular_2step.schema import canonical, load, sha, _pairs
from . import machine_check


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _integer(value, name):
    require(type(value) is int and 0 <= value < 2**64, 'strict integer ' + name)
    return value


def _numeric_types(value):
    exact = {'seq', 'sequence', 'pid', 'pc', 'next_pc', 'runtime_pc', 'post_pc',
             'elf_address', 'file_offset', 'elf_file_offset', 'load_base', 'module_load_base',
             'address', 'width', 'size', 'mxcsr', 'eflags', 'start_seq', 'end_seq',
             'record_count', 'requested_steps', 'step'}
    exact |= {'gdb_return_code', 'scalar_fp_count', 'proc_stat_start_time_ticks'}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in exact:
                _integer(item, key)
            _numeric_types(item)
    elif isinstance(value, list):
        for item in value:
            _numeric_types(item)


def _pc(row):
    return row.get('runtime_pc', row.get('pc')), row.get('post_pc', row.get('next_pc'))


def _base_structure(rows, region, modules):
    shape = body_checker.prefix_structure(rows, region, modules)
    targets = []
    for index, row in enumerate(rows):
        if row['kind'] != 'CONTROL':
            continue
        pc = _pc(row)[1]
        matches = [(m['sha256'], pc - m['load_base']) for m in modules.values()
            if any(s['flags'] & 1 and m['load_base'] + s['vaddr'] <= pc <
                   m['load_base'] + s['vaddr'] + s['filesz'] for s in m['segments'])]
        require(len(matches) == 1, 'unique actual base control target module/RVA')
        targets.append((index, *matches[0]))
    # The old helper expressed cross-module targets relative to the source
    # module base, which depends on ASLR. Preserve target identity with its
    # independently resolved destination module, not address subtraction.
    shape['control'] = targets
    return shape


def _decoded(rows, root, modules):
    frozen = structure._frozen_modules(root)
    for path, module in modules.items():
        require(path == module['path'] and module['sha256'] in frozen, 'complete frozen module identity')
        require(module['segments'] == caller._elf_segments(frozen[module['sha256']][0]),
                'module PT_LOAD metadata vs actual frozen ELF')
    addresses = defaultdict(set)
    for row in rows:
        require(row['module_sha256'] in frozen, 'unregistered binary')
        addresses[row['module_sha256']].add(row['elf_address'])
    decoded = {}
    for digest, wanted in addresses.items():
        path, image = frozen[digest]
        sites = caller._objdump_decode(path, digest, wanted, 'objdump')
        for address, result in sites.items():
            decoded[digest, address] = result
    module_by_hash = {module['sha256']: module for module in modules.values()}
    for row in rows:
        digest, address = row['module_sha256'], row['elf_address']
        encoded, assembly = decoded[digest, address]
        recorded = row.get('bytes', row.get('instruction_bytes'))
        require(encoded == recorded, 'independent instruction bytes/decode')
        image = frozen[digest][1]
        offset = structure._elf_file_offset(image, address, len(bytes.fromhex(encoded)))
        require(row.get('elf_file_offset', row.get('file_offset')) == offset and
                image[offset:offset + len(bytes.fromhex(encoded))].hex() == encoded, 'ELF byte binding')
        base = row.get('module_load_base', row.get('load_base'))
        module = module_by_hash[digest]
        require(base == module['load_base'], 'module load-base identity')
        require(_pc(row)[0] == base + address, 'PC/RVA relation')
        require(int(row['pre']['gpr']['rip'], 16) == _pc(row)[0] and
                int(row['post']['gpr']['rip'], 16) == _pc(row)[1], 'PRE/POST PC')
        require(structure.normalize_decoded_instruction(row.get('instruction', row.get('assembly')), base) ==
                structure.normalize_decoded_instruction(assembly, 0), 'recorded assembly vs independent decode')
        require(any(segment['flags'] & 1 and segment['vaddr'] <= address <
                    segment['vaddr'] + segment['filesz'] for segment in module['segments']), 'executable PT_LOAD membership')
    return decoded


def _closed_caller_sites(root):
    path = root / 'runtime_trace/regular_2step/artifacts/known-03/trace.jsonl'
    old = [json.loads(line) for line in path.read_bytes().splitlines()]
    allowed = {(r['module_sha256'], r['elf_address'], r['instruction_bytes'])
               for r in old if r.get('schema') == 'gala-caller-transition-instruction-v2'}
    # The same pinned libc mutex helpers have an executed single-thread fast
    # branch, absent from the old capture. Exact sites, bytes and all effects
    # are checked; this does not admit a new helper or arbitrary libc code.
    libc = '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'
    allowed.update((libc, address, encoded) for address, encoded in (
        (655696, '448b07'), (655699, '4585c0'), (655702, '75c2'),
        (655704, 'c70701000000'), (655710, 'ebcb'), (662414, 'c70700000000')))
    return allowed


def _memory(rows, decoded, shadow=None):
    shadow = {} if shadow is None else shadow
    for index, row in enumerate(rows):
        # Old helper adds a historical ABI observation at literal sequence 727.
        # Neutralize only that fixture rule, then derive the new ABI event from
        # the decoded native call site and actual last instruction.
        expected = machine_check.observations(row, decoded[row['sequence']])
        observations = row['pre_memory_observations']
        require([(o['kind'], o['operand'], o['size']) for o in observations] == expected,
                'complete derived read/ABI observation set')
        require(row['pre']['segment_bases'] == row['post']['segment_bases'] and
                set(row['pre']['segment_bases']) == {'fs_base', 'gs_base'}, 'FS/GS semantics')
        for o in observations:
            require(o['status'] == 'OK' and o['timing'] == 'PRE_INSTRUCTION' and
                    o['address'] == caller._effective_address(row, o['operand']), 'observed PRE read EA')
            data = bytes.fromhex(o['bytes_hex'])
            require(len(data) == o['size'], 'observed read width')
            for k, byte in enumerate(data):
                address = o['address'] + k
                require(address not in shadow or shadow[address] == byte, 'observed read/shadow def-use')
                shadow[address] = byte
        for w in row['possible_memory_writes']:
            before = int(w['before_bits'], 16).to_bytes(w['size'], 'little')
            after = int(w['after_bits'], 16).to_bytes(w['size'], 'little')
            for k, byte in enumerate(before):
                address = w['address'] + k
                require(address not in shadow or shadow[address] == byte, 'write PRE shadow')
                shadow[address] = after[k]
    return shadow


def _caller_semantics(rows, decoded, modules, allowed):
    require(rows and [r['sequence'] for r in rows] == list(range(len(rows))), 'local caller order')
    local = {r['sequence']: decoded[r['module_sha256'], r['elf_address']][1] for r in rows}
    bases = {m['sha256']: m['load_base'] for m in modules.values()}
    for row in rows:
        require((row['module_sha256'], row['elf_address'], row['instruction_bytes']) in allowed,
                'caller helper/site outside reviewed finite opcode corridor')
    _memory(rows, local)
    caller._validate_register_semantics(rows, local)
    caller._validate_control(rows, local, bases)
    writes = caller._validate_recorded_writes(rows, local)
    return local, writes


def _caller_join(previous, following, corridor, rows, decoded, modules, allowed):
    local, writes = _caller_semantics(rows, decoded, modules, allowed)
    require(corridor['entry_abi']['pointers'] == following['pointers'], 'caller/entry pointers')
    require(corridor['entry_abi']['component_bits'] == following['start_state'], 'caller/entry bits')
    require(corridor['start_component_bits'] == previous['end_state'] and
            corridor['end_component_bits'] == following['start_state'], 'actual caller endpoints')
    for name in ('q', 'full_v', 'latent'):
        pointer = previous['pointers'][name]
        require(following['pointers'][name] == pointer and
                corridor['protected_role_pointers'][name] == pointer, 'live carry pointer')
        require(previous['end_state'][name] == following['start_state'][name], 'actual adjacent carry bits')
        require(not any(w['address'] < pointer + 16 and pointer < w['address'] + w['size']
                        for w in writes), 'protected write overlap, including same-value store')
    gradient = previous['pointers']['gradient']
    require(following['pointers']['gradient'] == gradient and
            following['start_state']['gradient'] == ['0x0000000000000000'] * 2, 'gradient entry/reset')
    reset = structure._validate_gradient_reset(rows, gradient, previous['end_state']['gradient'])
    arguments = {}
    for name, xmm in (('t', '%xmm0'), ('dt', '%xmm1')):
        source = caller._derive_scalar_load(rows, local, xmm)
        require(source == corridor['argument_sources'][name], 'actual last argument load provenance')
        require(source['source_bits'] == following[name + '_bits'], 'argument source/entry bits')
        first = rows[-1]['post']['xmm'][xmm[1:]]
        require(int(first, 16) & (2**64 - 1) == int(following[name + '_bits'], 16), 'argument XMM handoff')
        arguments[name] = source
    abi = corridor['entry_abi']
    require(abi['n'] == 1 and abi['half_ndim'] == 2, 'ABI dimension contract')
    post = rows[-1]['post']
    for register, name in (('rcx', 'q'), ('r8', 'full_v'), ('r9', 'latent')):
        require(int(post['gpr'][register], 16) == following['pointers'][name], 'actual final ABI pointer register')
    observation = following['entry_stack_observations']['gradient_pointer']
    require(observation['address'] == int(post['gpr']['rsp'], 16) + 8 and
            observation['bytes_hex'] == gradient.to_bytes(8, 'little').hex(), 'gradient ABI stack observation')
    require(any(w['address'] == observation['address'] and w['size'] == 8 and
                int(w['after_bits'], 16) == gradient for w in writes), 'actual gradient argument PUSH')
    require(int(post['gpr']['rsi'], 16) == 1 and int(post['gpr']['rdx'], 16) == 2,
            'actual final ABI dimension registers')
    return {'from': previous['occurrence'], 'to': following['occurrence'],
            'gradient_reset': reset, 'arguments': arguments,
            'writes': len(writes), 'same_value_writes': sum(w['value_changed'] is False for w in writes)}


def _output_stores(region, rows, decoded, n):
    """Derive each actual save_all copy, from live source to written destination."""
    stores, source = [], None
    for row in rows:
        opcode, operands = caller._parse_assembly(decoded[row['module_sha256'], row['elf_address']][1])
        if opcode == 'movsd' and operands[-1] == '%xmm0' and caller._is_memory_operand(operands[0]):
            address = caller._effective_address(row, operands[0])
            role = [(name, k) for name in ('q', 'full_v') for k in (0, 8)
                    if address == region['pointers'][name] + k]
            source = (row, role[0]) if role else None
        elif opcode == 'movsd' and operands[0] == '%xmm0' and caller._is_memory_operand(operands[-1]):
            require(source is not None, 'output copy source provenance')
            load, (name, k) = source
            writes = row['possible_memory_writes']
            bits = region['end_state'][name][k // 8]
            require(len(writes) == 1 and writes[0]['size'] == 8 and writes[0]['after_bits'] == bits and
                    writes[0]['address'] == caller._effective_address(row, operands[-1]) and
                    int(load['post']['xmm']['xmm0'], 16) & (2**64 - 1) == int(bits, 16), 'actual output lane copy')
            stores.append(writes[0]['address'])
            source = None
    require(len(stores) == 4 and stores == [stores[0] + k * 8 * (n + 1) for k in range(4)],
            'each native output column/allocation stride')
    return stores


def _terminal(capture, rows, decoded, allowed):
    terminal = capture['terminal_corridor']
    subset = rows[terminal['start_seq']:terminal['end_seq']]
    local, writes = _caller_semantics(subset, decoded, capture['modules'], allowed)
    region = capture['regions'][-1]
    pointers = region['pointers']
    for name in ('q', 'full_v', 'latent'):
        pointer = pointers[name]
        require(not any(w['address'] < pointer + 16 and pointer < w['address'] + w['size']
                        for w in writes), 'terminal protected write overlap')
    stores = []
    last_load = None
    for row in subset:
        assembly = local[row['sequence']]
        opcode, operands = caller._parse_assembly(assembly)
        if opcode == 'movsd' and operands[-1] == '%xmm0' and caller._is_memory_operand(operands[0]):
            address = caller._effective_address(row, operands[0])
            roles = [(name, offset) for name in ('q', 'full_v') for offset in (0, 8)
                     if address == pointers[name] + offset]
            last_load = (row, roles[0]) if roles else None
        elif opcode == 'movsd' and operands[0] == '%xmm0' and caller._is_memory_operand(operands[-1]):
            require(last_load is not None, 'final store lacks actual terminal source load')
            load_row, (name, offset) = last_load
            address = caller._effective_address(row, operands[-1])
            require(len(row['possible_memory_writes']) == 1, 'final scalar store coverage')
            write = row['possible_memory_writes'][0]
            bits = region['end_state'][name][offset // 8]
            require(write['address'] == address and write['size'] == 8 and write['after_bits'] == bits,
                    'final output write bits')
            require(int(load_row['post']['xmm']['xmm0'], 16) & (2**64 - 1) == int(bits, 16), 'final source XMM')
            require(not any(caller._parse_assembly(local[r['sequence']])[0] not in ('mov', 'lea', 'nop', 'nopw')
                            for r in subset[load_row['sequence'] + 1:row['sequence']]), 'unsupported output-load/store corridor')
            stores.append({'component': name, 'byte_offset': offset, 'center_bits': bits,
                           'source_trace_seq': load_row['seq'], 'store_trace_seq': row['seq'],
                           'destination_address': address})
            last_load = None
    require([(s['component'], s['byte_offset']) for s in stores] ==
            [('q', 0), ('q', 8), ('full_v', 0), ('full_v', 8)], 'four ordered final output stores')
    stride = 8 * (capture['requested_steps'] + 1)
    require([s['destination_address'] for s in stores] ==
            [stores[0]['destination_address'] + i * stride for i in range(4)], 'final output allocation/shape stride')
    last = subset[-1]
    require(last['elf_address'] == 202348 and caller._parse_assembly(local[last['sequence']])[0] == 'jne' and
            last['next_pc'] == last['pc'] + len(bytes.fromhex(last['instruction_bytes'])), 'actual final loop exit branch')
    if capture['requested_steps'] > 1:
        t2 = capture['caller_corridors'][0]['argument_sources']['t']['source_memory_address']
        expected_end = t2 + 8 * (capture['requested_steps'] - 1)
        require(int(last['pre']['gpr']['r13'], 16) == int(last['pre']['gpr']['rax'], 16) == expected_end,
                'terminal schedule extent vs observed requested steps')
    return stores


def validate_semantics(capture, rows, root):
    root = Path(root).resolve()
    _numeric_types(capture)
    _numeric_types(rows)
    n = capture['requested_steps']
    require(capture['schema'] == 'gala-regular-nstep-runtime-trace-v1' and
            capture['wheel_sha256'] == 'cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0' and
            capture['machine_mapping_read_by_tracer'] is False, 'original frozen execution acquisition contract')
    require(1 <= n <= 100 and capture['verdict'] == 'CAPTURED', 'supported successful capture request')
    regions, corridors = capture['regions'], capture['caller_corridors']
    require([r['occurrence'] for r in regions] == ['init'] + [f'step{k}' for k in range(1, n + 1)], 'actual N body occurrences')
    require(len(corridors) == n - 1, 'actual N-1 corridors')
    require([r['seq'] for r in rows] == list(range(len(rows))) and len(rows) == capture['record_count'], 'global dense occurrence order')
    pid = capture['process_identity']['pid']
    identity = capture['process_identity']
    require(set(identity) == {'pid', 'linux_boot_id', 'proc_stat_start_time_ticks'} and
            type(identity['proc_stat_start_time_ticks']) is int and identity['proc_stat_start_time_ticks'] > 0 and
            re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', identity['linux_boot_id']) is not None,
            'structured process birth identity')
    owner = regions[0]['ptid']
    require(type(pid) is int and len(owner) == 3 and all(type(v) is int for v in owner), 'actual process/thread identity')
    require(pid > 0 and owner[0] == pid and owner[1] > 0 and owner[2] == 0, 'Linux PTID/process owner relation')
    for row in rows:
        require(row['pid'] == pid and row['ptid'] == owner, 'cross-process/thread transcript splice')
        if 'thread_ptid' in row:
            require(row['thread_ptid'] == owner, 'caller thread occurrence identity')
        for context in (row['pre'], row['post']):
            require(context['mxcsr'] & ((3 << 13) | (1 << 15) | (1 << 6)) == 0 and
                    context['mxcsr'] & 0x1f80 == 0x1f80, 'rounding/FTZ/DAZ environment')
    require(regions[0]['start_seq'] == 0 and regions[0]['end_seq'] == regions[1]['start_seq'], 'base row coverage')
    spans = [regions[0], regions[1]]
    for k, corridor in enumerate(corridors, 1):
        require(corridor['occurrence'] == f'caller{k}-{k+1}', 'caller occurrence identity')
        require(regions[k]['end_seq'] == corridor['start_seq'] and
                corridor['end_seq'] == regions[k + 1]['start_seq'], 'body/caller complete coverage')
        spans.extend([corridor, regions[k + 1]])
    terminal = capture['terminal_corridor']
    require(terminal is not None and terminal['start_seq'] == regions[-1]['end_seq'] and
            terminal['end_seq'] == len(rows), 'terminal complete coverage')
    spans.append(terminal)
    for span in spans:
        require(span['start_seq'] < span['end_seq'], 'empty execution region')
        require(all(r['occurrence'] == span['occurrence'] for r in rows[span['start_seq']:span['end_seq']]), 'raw region occurrence labels')
    for region in regions:
        require(region['ptid'] == owner and region['scheduler_locking'] ==
                'Mode for locking scheduler during execution is "on".' and
                region['entry_pc'] == _pc(rows[region['start_seq']])[0] and
                region['return_pc'] == _pc(rows[region['end_seq'] - 1])[1], 'actual body owner/entry/return/all-stop')
    for corridor in corridors:
        require(corridor['owner_ptid'] == owner, 'actual corridor owner thread')
    require(capture['scalar_fp_count'] == sum(r.get('kind') in ('ADD', 'SUB', 'MUL') for r in rows), 'actual arithmetic row count')
    require(capture['opcode_histogram'] == dict(Counter(r['opcode'] if 'opcode' in r else r['assembly'].split()[0] for r in rows)),
            'actual opcode histogram')
    gap = regions[1]['start_seq']
    for index in range(1, len(rows)):
        if index == gap:
            continue
        require(_pc(rows[index - 1])[1] == _pc(rows[index])[0], 'semantic PC seam/order')
        before, after = rows[index - 1]['post'], rows[index]['pre']
        require(before['gpr'] == after['gpr'] and before['xmm'] == after['xmm'] and
                before['eflags'] == after['eflags'] and before['mxcsr'] == after['mxcsr'] and
                before['segment_bases'] == after['segment_bases'], 'actual complete register seam')
    decoded = _decoded(rows, root, capture['modules'])
    # One memory shadow across body/caller/terminal boundaries. The inherited
    # base gap is the sole explicit reset; no other unseen re-rooting is allowed.
    native_rows = [machine_check.normalized(row) for row in rows]
    native_decoded = {row['seq']: machine_check.effect_assembly(decoded[row['module_sha256'], row['elf_address']][1]) for row in rows}
    _memory(native_rows[:gap], native_decoded)
    _memory(native_rows[gap:], native_decoded)
    bases = {m['sha256']: m['load_base'] for m in capture['modules'].values()}
    machine_check.registers(native_rows, native_decoded)
    machine_check.controls(native_rows, native_decoded, bases)
    machine_check.writes(native_rows, native_decoded)
    body_rows = [r for region in regions for r in rows[region['start_seq']:region['end_seq']]]
    structure._check_observations(body_rows)
    # Compare static bodies while checking fresh bits and provenance for each.
    first = rows[regions[1]['start_seq']:regions[1]['end_seq']]
    for region in regions[1:]:
        require(region['dt_bits'] == '0x3f90000000000000', 'frozen dt')
        structure.compare_step_structures(first, rows[region['start_seq']:region['end_seq']], regions[1], region)
    # Accepted base is independently reconstructed from new actual instructions.
    prefix_rows = rows[:regions[1]['end_seq']]
    ops, values, _ = body_checker.graph(capture, prefix_rows, regions[:2], root, prefix=True)
    old_ir = load(root / 'runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json')
    require(ops == old_ir['operations'] and values == old_ir['values'], 'actual audited init/step1 base graph and bits')
    old_capture = load(root / 'runtime_trace/regular_2step/artifacts/known-03/capture.json')
    old_rows, _ = structure._load_rows(root / 'runtime_trace/regular_2step/artifacts/known-03/trace.jsonl')
    for fresh, old in zip(regions[:2], old_capture['regions'][:2]):
        require(_base_structure(rows[fresh['start_seq']:fresh['end_seq']], fresh, capture['modules']) ==
                _base_structure(old_rows[old['start_seq']:old['end_seq']], old, old_capture['modules']),
                'complete audited base instruction/control/storage topology')
    allowed = _closed_caller_sites(root)
    joins = []
    output_columns = []
    for k, corridor in enumerate(corridors, 1):
        subset = rows[corridor['start_seq']:corridor['end_seq']]
        joins.append(_caller_join(regions[k], regions[k + 1], corridor, subset,
                                  decoded, capture['modules'], allowed))
        output_columns.append(_output_stores(regions[k], subset, decoded, n))
        if k > 1:
            require(corridor['argument_sources']['t']['source_memory_address'] ==
                    corridors[0]['argument_sources']['t']['source_memory_address'] + 8 * (k - 1),
                    'actual contiguous schedule step index')
    stores = _terminal(capture, rows, decoded, allowed)
    output_columns.append([s['destination_address'] for s in stores])
    for k, addresses in enumerate(output_columns):
        require(addresses == [address + 8 * k for address in output_columns[0]],
                'actual adjacent output save index; no overwritten or skipped step')
    require(capture['harness_completed_normally'] is True and capture['gdb_return_code'] == 0,
            'normal completion prerequisite')
    exit_event = capture['gdb_exit_event']
    require(exit_event['observed'] is True and type(exit_event['exit_code']) is int and
            exit_event['exit_code'] == 0 and exit_event['inferior_pid'] == pid and
            exit_event['selected_inferior_pid_after_exit'] == 0, 'actual same-inferior normal exit')
    return {'schema': 'regular-nstep-native-check-v1', 'checked_steps': n,
            'carry_join_count': len(joins), 'joins': joins, 'record_count': len(rows),
            'terminal_output_stores': stores, 'init_to_step1': 'UNTRACED',
            'post_terminal_frontier': 'UNTRACED', 'last_verified_trace_seq': len(rows) - 1,
            'scope': 'finite observed native correspondence, conditional accepted base and original harness tail'}


def validate(capture_dir, root):
    capture_dir, root = Path(capture_dir).resolve(), Path(root).resolve()
    require((capture_dir / 'trace.jsonl').stat().st_size <= 536870912, 'raw size ceiling')
    capture = load(capture_dir / 'capture.json')
    seal = load(capture_dir / 'acquisition_seal.json')
    require(seal['acquisition_id'] == capture['acquisition_id'], 'acquisition seal identity')
    require(set(seal['files']) == {'trace.jsonl', 'capture.json', 'source_pinset.json',
        'gdb.log', 'capture.pending.json', 'harness_output.json'}, 'complete acquisition file set')
    for name, digest in seal['files'].items():
        require(Path(name).name == name and sha(capture_dir / name) == digest, 'sealed file byte identity')
    pins = load(capture_dir / 'source_pinset.json')
    # Deliberately independent literal contract, no producer import.
    expected_sources = {'runtime_trace/harness.py', 'runtime_trace/gdb_capture.py',
        'runtime_trace/semantics.py', 'runtime_trace/regular_2step/acquire.py',
        'runtime_trace/regular_2step/gdb_acquire.py',
        'runtime_trace/caller_transition/gdb_acquire_reads.py',
        'runtime_trace/caller_transition/read_effects.py',
        'runtime_trace/caller_transition/write_effects_reads.py',
        'runtime_trace/caller_transition/write_effects.py',
        'runtime_trace/caller_transition/module_resolver.py',
        'runtime_trace/caller_transition/frozen_modules/manifest.json',
        'runtime_trace/regular_nstep/acquire.py', 'runtime_trace/regular_nstep/gdb_acquire.py',
        'runtime_trace/regular_nstep/harness.py', 'runtime_trace/regular_nstep/resources.py'}
    require(set(pins) == expected_sources, 'complete reviewed source set')
    require(sha(capture_dir / 'source_pinset.json') == capture['source_pinset_sha256'], 'source pinset integrity')
    for relative, digest in pins.items():
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and
                sha(root / relative) == digest, 'reviewed current collector source pin')
    require(sha(capture_dir / 'trace.jsonl') == capture['trace_sha256'], 'raw trace SHA')
    rows, chain = [], '0' * 64
    with (capture_dir / 'trace.jsonl').open('rb') as stream:
        for line in stream:
            row = json.loads(line, object_pairs_hook=_pairs,
                parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite JSON constant')))
            chain = hashlib.sha256(bytes.fromhex(chain) + canonical({k: v for k, v in row.items() if k != 'chain'})).hexdigest()
            require(row['chain'] == chain, 'strict raw global chain')
            rows.append(row)
    require(chain == capture['final_chain'], 'final global chain')
    expected_id = hashlib.sha256(json.dumps({'process': capture['process_identity'],
        'trace': capture['trace_sha256'], 'source': pins,
        'requested_steps': capture['requested_steps']}, sort_keys=True).encode()).hexdigest()
    require(expected_id == capture['acquisition_id'], 'unique acquisition tuple')
    report = validate_semantics(capture, rows, root)
    harness = load(capture_dir / 'harness_output.json')
    require(type(harness['n_steps']) is int and harness['n_steps'] == capture['requested_steps'], 'honest harness request metadata')
    require(harness['output_bits'] == [s['center_bits'] for s in report['terminal_output_stores']], 'final stored output to source-bound harness result')
    return capture, rows, report
